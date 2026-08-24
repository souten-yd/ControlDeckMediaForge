"""User-added Hugging Face models, resolved and pinned before anything is fetched.

The shipped catalog stays the trusted path: every entry there has a pinned
revision, verified digests, and measured VRAM. Users still need models the
catalog does not carry, so this adds an explicit second path rather than
loosening the first one.

The rules that make the trusted path verifiable are kept here too:

* the revision is resolved to an immutable commit SHA before anything is fetched
* every weight carries the digest the Hub reported, so the existing installer
  verifies what it downloaded
* the licence is shown and accepted explicitly, by its text, before adding
* the entry lands as ``experimental``, so routing will not select it until a
  real measurement promotes it

Nothing here executes repository code, and no remote inference path is added.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


_REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_REVISION_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")

# 設定ファイル類は取得前に必ず読む。数と大きさを縛って、任意の repository が
# 無制限のメタデータを持ち込めないようにする。
MAX_REQUIRED_FILES = 64
MAX_WEIGHT_FILES = 256
MAX_CUSTOM_MODELS = 32
MAX_METADATA_BYTES = 4 * 1024 * 1024
REQUIRED_FILE_SUFFIXES = (".json", ".txt", ".yaml", ".yml", ".jinja", ".model")
WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt", ".pth", ".ckpt")

# 実測: stabilityai/stable-diffusion-xl-base-1.0 は全ファイルで 49.95GB あるが、
# その大半は同じ重みの別ランタイム版（Flax / ONNX / OpenVINO）と、
# ひとつの component の fp32 / fp16 の二重持ちである。ひとつ選べば 7.1GB になる。
# 選ばずに全部数えると導入上限 32GB を超え、まともな repository が入らなくなる。
_ALTERNATE_RUNTIME_MARKERS = (".msgpack", ".onnx", ".onnx_data", "openvino_")
# 同じ component の候補を比べる優先順。上ほど優先する。
_VARIANT_PREFERENCE = (".fp16.safetensors", ".safetensors", ".bin", ".ckpt", ".pth", ".pt", ".gguf")


def _is_alternate_runtime(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in _ALTERNATE_RUNTIME_MARKERS)


def _component_key(name: str) -> str:
    """Identify the component a weight file belongs to, ignoring its variant.

    ``unet/diffusion_pytorch_model.fp16.safetensors`` and
    ``unet/diffusion_pytorch_model.safetensors`` are the same component. Sharded
    files keep their shard index, so every shard survives.
    """
    stem = name
    for suffix in _VARIANT_PREFERENCE:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem.replace(".fp16", "").replace("-fp16", "")


def _variant_rank(name: str) -> int:
    for index, suffix in enumerate(_VARIANT_PREFERENCE):
        if name.endswith(suffix):
            return index
    return len(_VARIANT_PREFERENCE)


def select_one_variant(weights: list[ResolvedWeight]) -> tuple[list[ResolvedWeight], int]:
    """Keep one runnable set of weights and report how many bytes were skipped."""
    total = sum(item.size_bytes for item in weights)
    usable = [item for item in weights if not _is_alternate_runtime(item.path)]
    if not usable:
        return weights, 0
    # 直下の単一ファイル checkpoint は、component 別フォルダと同じ重みの別形
    # であることが多い。両方あるならフォルダ側を使う。
    foldered = [item for item in usable if "/" in item.path]
    if foldered:
        usable = foldered
    best: dict[str, ResolvedWeight] = {}
    for item in usable:
        key = _component_key(item.path)
        current = best.get(key)
        if current is None or _variant_rank(item.path) < _variant_rank(current.path):
            best[key] = item
    selected = sorted(best.values(), key=lambda item: item.path)
    return selected, total - sum(item.size_bytes for item in selected)

# Diffusers の pipeline はあるが、Media Forge にその系統の adapter がまだ無い。
# 取り込みと検証はできるが生成には使えない、という状態を正直に持たせる。
UNSUPPORTED_ADAPTER = "unsupported"


class CustomModelError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ResolvedWeight:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CustomModelResolution:
    repo_id: str
    revision: str
    requested_revision: str
    license: str
    license_notice: str
    gated: bool
    pipeline_tag: str
    library_name: str
    weights: tuple[ResolvedWeight, ...]
    required_files: tuple[str, ...]
    total_bytes: int
    runtime_adapter: str
    capabilities: tuple[str, ...]
    max_download_bytes: int
    warnings: tuple[str, ...] = field(default=())

    @property
    def within_download_cap(self) -> bool:
        return self.total_bytes <= self.max_download_bytes

    @property
    def usable_for_generation(self) -> bool:
        return self.runtime_adapter != UNSUPPORTED_ADAPTER

    def document(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "revision": self.revision,
            "requested_revision": self.requested_revision,
            "license": self.license,
            "license_notice": self.license_notice,
            "gated": self.gated,
            "pipeline_tag": self.pipeline_tag,
            "library_name": self.library_name,
            "weight_count": len(self.weights),
            "required_file_count": len(self.required_files),
            "total_bytes": self.total_bytes,
            "max_download_bytes": self.max_download_bytes,
            "within_download_cap": self.within_download_cap,
            "usable_for_generation": self.usable_for_generation,
            "warnings": list(self.warnings),
        }


def _adapter_for(library_name: str, pipeline_tag: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Map the Hub's own labels onto an adapter Media Forge actually ships.

    Guessing an adapter would produce a model that installs and then fails at
    generation time. Say so at add time instead.
    """
    if library_name != "diffusers":
        return UNSUPPORTED_ADAPTER, (), (
            f"この repository は {library_name or '不明'} 用です。"
            "Media Forge は Diffusers 形式の画像モデルだけを扱えます。",
        )
    if pipeline_tag not in {"text-to-image", "image-to-image", "inpainting"}:
        return UNSUPPORTED_ADAPTER, (), (
            f"この repository の用途は {pipeline_tag or '不明'} です。画像生成として扱えません。",
        )
    # Stable Diffusion 系の共通 adapter はまだ実測していない。取り込みと検証は
    # できるが生成には使えない、と明示する。推測で adapter を割り当てない。
    return UNSUPPORTED_ADAPTER, ("image.text_to_image",), (
        "この形式に対応する実行アダプタはまだ実測されていません。"
        "取り込みと検証はできますが、生成にはまだ使えません。",
    )


# ── 配布元の検索 ────────────────────────────────────────────────────────
#
# repository ID を手で入力させるのは、名前を既に知っている人にしか使えない。
# 探すところから引き受ける。ただし探せることと入れてよいことは別なので、
# 結果は候補のままで、取り込みは従来どおり resolve と明示承諾を通す。

SEARCH_LIMIT = 30
SEARCH_SORTS = ("downloads", "likes", "lastModified", "createdAt")
# 画像生成として扱える組み合わせだけを既定で探す。使えないものを既定で出さない。
SEARCH_PIPELINES = ("text-to-image", "image-to-image", "inpainting")


@dataclass(frozen=True, slots=True)
class CatalogCandidate:
    repo_id: str
    author: str
    downloads: int
    likes: int
    last_modified: str
    pipeline_tag: str
    library_name: str
    gated: bool
    license: str
    tags: tuple[str, ...]

    def document(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "author": self.author,
            "downloads": self.downloads,
            "likes": self.likes,
            "last_modified": self.last_modified,
            "pipeline_tag": self.pipeline_tag,
            "library_name": self.library_name,
            "gated": self.gated,
            "license": self.license,
            "tags": list(self.tags),
        }


def _license_from_tags(tags: list[Any]) -> str:
    for tag in tags:
        if isinstance(tag, str) and tag.startswith("license:"):
            return tag.split(":", 1)[1]
    return "unknown"


class CatalogSearchMixin:
    """Search the distribution site for candidates. Adding one still needs consent."""

    async def search(
        self,
        query: str,
        *,
        sort: str = "downloads",
        pipeline_tag: str = "text-to-image",
        limit: int = SEARCH_LIMIT,
    ) -> list[CatalogCandidate]:
        if sort not in SEARCH_SORTS:
            raise CustomModelError("custom_model_sort_invalid", "並び順が正しくありません")
        if pipeline_tag not in SEARCH_PIPELINES:
            raise CustomModelError("custom_model_pipeline_invalid", "用途が正しくありません")
        if not isinstance(query, str) or len(query) > 200:
            raise CustomModelError("custom_model_query_invalid", "検索語が長すぎます")
        params: dict[str, Any] = {
            "pipeline_tag": pipeline_tag,
            # Diffusers 形式に限る。ここを緩めると、取り込めない候補ばかり並ぶ。
            "library": "diffusers",
            "sort": sort,
            "direction": -1,
            "limit": max(1, min(SEARCH_LIMIT, limit)),
        }
        if query.strip():
            params["search"] = query.strip()
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_sec, follow_redirects=True
            ) as client:
                response = await client.get(f"{self.origin}/api/models", params=params)
        except httpx.HTTPError as exc:
            raise CustomModelError(
                "custom_model_source_unreachable", "配布元を検索できませんでした"
            ) from exc
        if response.status_code != 200:
            raise CustomModelError(
                "custom_model_source_unreachable", "配布元を検索できませんでした"
            )
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise CustomModelError(
                "custom_model_metadata_invalid", "検索結果を読み取れませんでした"
            ) from exc
        if not isinstance(payload, list):
            raise CustomModelError("custom_model_metadata_invalid", "検索結果を読み取れませんでした")

        found: list[CatalogCandidate] = []
        for item in payload[:SEARCH_LIMIT]:
            if not isinstance(item, dict):
                continue
            repo_id = str(item.get("id") or item.get("modelId") or "")
            if _REPO_ID.fullmatch(repo_id) is None:
                continue
            tags = item.get("tags") if isinstance(item.get("tags"), list) else []
            found.append(CatalogCandidate(
                repo_id=repo_id,
                author=str(item.get("author") or repo_id.split("/", 1)[0]),
                downloads=int(item.get("downloads") or 0),
                likes=int(item.get("likes") or 0),
                last_modified=str(item.get("lastModified") or ""),
                pipeline_tag=str(item.get("pipeline_tag") or ""),
                library_name=str(item.get("library_name") or ""),
                gated=item.get("gated") not in (False, None),
                license=_license_from_tags(tags),
                tags=tuple(str(tag) for tag in tags[:24] if isinstance(tag, str)),
            ))
        return found


class CustomModelCatalog(CatalogSearchMixin):
    """Durable store of user-added catalog entries, and search over the source."""

    def __init__(
        self,
        path: Path,
        *,
        origin: str = "https://huggingface.co",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_sec: float = 20.0,
        max_download_bytes: int = 32_000_000_000,
    ):
        self.path = path
        self.origin = origin.rstrip("/")
        self.transport = transport
        self.timeout_sec = timeout_sec
        # installer と同じ上限。取得を始めてから落とすより先に伝える。
        self.max_download_bytes = max_download_bytes

    # ── resolve ────────────────────────────────────────────────────────────

    async def resolve(self, repo_id: str, revision: str) -> CustomModelResolution:
        if not isinstance(repo_id, str) or _REPO_ID.fullmatch(repo_id) is None:
            raise CustomModelError("custom_model_repo_invalid", "repository ID の形式が正しくありません")
        if not isinstance(revision, str) or _REVISION_REF.fullmatch(revision) is None:
            raise CustomModelError("custom_model_revision_invalid", "revision の形式が正しくありません")
        payload = await self._metadata(repo_id, revision)
        return self._resolution(repo_id, revision, payload)

    async def _metadata(self, repo_id: str, revision: str) -> dict[str, Any]:
        url = f"{self.origin}/api/models/{repo_id}/revision/{revision}"
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_sec, follow_redirects=True
            ) as client:
                response = await client.get(url, params={"blobs": "true"})
        except httpx.HTTPError as exc:
            raise CustomModelError(
                "custom_model_source_unreachable", "モデル情報を取得できませんでした"
            ) from exc
        if response.status_code == 404:
            raise CustomModelError(
                "custom_model_not_found", "その repository と revision は見つかりませんでした"
            )
        if response.status_code in (401, 403):
            raise CustomModelError(
                "custom_model_access_denied",
                "この repository は許可が要ります。配布元で条件を承諾してください",
            )
        if response.status_code != 200:
            raise CustomModelError(
                "custom_model_source_unreachable", "モデル情報を取得できませんでした"
            )
        if len(response.content) > MAX_METADATA_BYTES:
            raise CustomModelError(
                "custom_model_metadata_too_large", "モデル情報が大きすぎます"
            )
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise CustomModelError(
                "custom_model_metadata_invalid", "モデル情報を読み取れませんでした"
            ) from exc
        if not isinstance(payload, dict):
            raise CustomModelError("custom_model_metadata_invalid", "モデル情報を読み取れませんでした")
        return payload

    def _resolution(
        self, repo_id: str, requested: str, payload: dict[str, Any]
    ) -> CustomModelResolution:
        commit = str(payload.get("sha") or "")
        if _COMMIT.fullmatch(commit) is None:
            raise CustomModelError(
                "custom_model_revision_unresolved",
                "取得した revision が固定できる形式ではありません",
            )
        siblings = payload.get("siblings")
        if not isinstance(siblings, list):
            raise CustomModelError("custom_model_metadata_invalid", "ファイル一覧を読み取れませんでした")

        weights: list[ResolvedWeight] = []
        required: list[str] = []
        for item in siblings:
            if not isinstance(item, dict):
                continue
            name = item.get("rfilename")
            if not isinstance(name, str) or not name:
                continue
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise CustomModelError(
                    "custom_model_path_invalid", "ファイル名に使えない経路が含まれています"
                )
            lfs = item.get("lfs")
            if isinstance(lfs, dict) and name.endswith(WEIGHT_SUFFIXES):
                digest = lfs.get("sha256")
                size = lfs.get("size", item.get("size"))
                if not isinstance(digest, str) or len(digest) != 64:
                    raise CustomModelError(
                        "custom_model_digest_missing",
                        f"{name} の digest が配布元にありません。検証できないものは取り込めません",
                    )
                if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                    raise CustomModelError(
                        "custom_model_metadata_invalid", f"{name} の大きさを読み取れませんでした"
                    )
                weights.append(ResolvedWeight(path=name, size_bytes=size, sha256=digest))
            elif name.endswith(REQUIRED_FILE_SUFFIXES):
                required.append(name)

        if not weights:
            raise CustomModelError(
                "custom_model_no_weights", "この repository に取り込める重みがありません"
            )
        if len(weights) > MAX_WEIGHT_FILES:
            raise CustomModelError("custom_model_too_many_files", "ファイル数が多すぎます")
        weights, skipped_bytes = select_one_variant(weights)
        required = sorted(required)[:MAX_REQUIRED_FILES]

        card = payload.get("cardData")
        license_name = str((card or {}).get("license") or "") if isinstance(card, dict) else ""
        adapter, capabilities, warnings = _adapter_for(
            str(payload.get("library_name") or ""), str(payload.get("pipeline_tag") or "")
        )
        gated = payload.get("gated") not in (False, None)
        if gated:
            warnings = warnings + ("この repository は配布元での条件承諾が要ります。",)
        total_bytes = sum(item.size_bytes for item in weights)
        if skipped_bytes:
            warnings = warnings + (
                f"別ランタイム版と重複する重み {skipped_bytes:,} バイトは取り込みません。",
            )
        if total_bytes > self.max_download_bytes:
            warnings = warnings + (
                f"この repository の重みは合計 {total_bytes:,} バイトあり、"
                f"取り込み上限 {self.max_download_bytes:,} バイトを超えています。",
            )
        return CustomModelResolution(
            repo_id=repo_id,
            revision=commit,
            requested_revision=requested,
            license=license_name or "unknown",
            license_notice=(
                f"ライセンス: {license_name or '不明'}。配布元のモデルカードを読んでから使ってください。"
            ),
            gated=gated,
            pipeline_tag=str(payload.get("pipeline_tag") or ""),
            library_name=str(payload.get("library_name") or ""),
            weights=tuple(sorted(weights, key=lambda item: item.path)),
            required_files=tuple(required),
            total_bytes=total_bytes,
            runtime_adapter=adapter,
            capabilities=capabilities,
            max_download_bytes=self.max_download_bytes,
            warnings=warnings,
        )

    # ── persistence ────────────────────────────────────────────────────────

    def entries(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError):
            # 読めない追加分のせいで shipped catalog まで失わせない。
            return []
        entries = value.get("entries") if isinstance(value, dict) else None
        return [item for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []

    def add(
        self,
        resolution: CustomModelResolution,
        *,
        display_name: str,
        license_acceptance: str,
        domains: tuple[str, ...] = ("general",),
    ) -> dict[str, Any]:
        if license_acceptance != resolution.license:
            raise CustomModelError(
                "custom_model_license_not_accepted",
                "表示したライセンスをそのまま承諾してください",
            )
        if not resolution.within_download_cap:
            raise CustomModelError(
                "custom_model_too_large",
                "この repository は取り込み上限を超えています",
            )
        entries = self.entries()
        if any(item.get("registry", {}).get("model_id") == resolution.repo_id for item in entries):
            raise CustomModelError("custom_model_exists", "そのモデルは既に追加されています")
        if len(entries) >= MAX_CUSTOM_MODELS:
            raise CustomModelError("custom_model_limit", "追加できるモデルの数を超えています")
        entry = self._entry(resolution, display_name=display_name, domains=domains)
        entries.append(entry)
        self._write(entries)
        return entry

    def remove(self, model_id: str) -> None:
        entries = self.entries()
        remaining = [
            item for item in entries if item.get("registry", {}).get("model_id") != model_id
        ]
        if len(remaining) == len(entries):
            raise CustomModelError("custom_model_not_added", "そのモデルは追加されていません")
        self._write(remaining)

    def _write(self, entries: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps({"schema_version": "1.0", "entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def _entry(
        self,
        resolution: CustomModelResolution,
        *,
        display_name: str,
        domains: tuple[str, ...],
    ) -> dict[str, Any]:
        name = display_name.strip() or resolution.repo_id
        digest = hashlib.sha256(
            "\n".join(f"{item.path}:{item.sha256}" for item in resolution.weights).encode("utf-8")
        ).hexdigest()
        return {
            "registry": {
                "model_id": resolution.repo_id,
                "family": "custom",
                "version": resolution.revision[:12],
                "revision": resolution.revision,
                "weights_hash": f"sha256:{digest}",
                "license": resolution.license,
                "runtime_adapter": resolution.runtime_adapter,
                "capabilities": list(resolution.capabilities),
                "hardware_backends": ["rocm", "cuda"],
                # 実測するまで routing 対象にしない。experimental は unroutable。
                "state": "experimental",
                "measurement_confidence": "low",
                "policy_rank": {"auto": 1_000_000},
                "required_files": list(resolution.required_files),
                "weights": [
                    {"path": item.path, "size_bytes": item.size_bytes, "sha256": item.sha256}
                    for item in resolution.weights
                ],
            },
            "catalog": {
                "model_id": resolution.repo_id,
                "display_name": name,
                "domains": list(domains),
                "media_types": ["image"],
                "description": " ".join(resolution.warnings) or "利用者が追加したモデル。",
                "approx_download_bytes": resolution.total_bytes,
                "source": {
                    "kind": "huggingface",
                    "repo_id": resolution.repo_id,
                    "revision": resolution.revision,
                },
                "ownership": "managed",
                "supports_lora": False,
                "max_references": 0,
                "reference_roles": [],
                "supports_reference_strength": False,
                "recommended_profiles": [],
                "gated": resolution.gated,
                "license_notice": resolution.license_notice,
            },
        }

    def manifests(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return the registry and catalog halves the ModelRegistry expects."""
        entries = self.entries()
        return (
            [item["registry"] for item in entries if isinstance(item.get("registry"), dict)],
            [item["catalog"] for item in entries if isinstance(item.get("catalog"), dict)],
        )
