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

from .civitai import CivitaiError, CivitaiSource


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
    # 配布元が単一ファイルを配る場合、寸法も歩数も config から読めない。
    # 系統の申告から決めた値をここに載せて、entry に書き出す。
    runtime_options: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default=())
    # 手元のフォルダから取り込んだときだけ入る。配布元から落とす経路では None。
    local_root: Path | None = field(default=None)

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


def _adapter_for(
    library_name: str, pipeline_tag: str, pipeline_class: str = ""
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Map the repository's own declaration onto an adapter Media Forge ships.

    Guessing an adapter would produce a model that installs and then fails at
    generation time. Say so at add time instead.

    The deciding fact is the pipeline class from ``model_index.json``, not the
    Hub's tags: ``diffusers`` + ``text-to-image`` also describes FLUX and
    Qwen-Image, which this adapter cannot run.
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
    adapter = _PIPELINE_ADAPTERS.get(pipeline_class)
    if adapter is not None:
        # SSD-1B（SDXL 系）で実測済みの経路。同じ AutoPipeline を通るが、
        # この repository 自体は測っていないので experimental のまま入る。
        return adapter, ("image.text_to_image",), (
            f"{pipeline_class} として取り込みます。実行経路は実測済みですが、"
            "この repository 自体は未計測なので、使う前に「評価」で確かめてください。",
        )
    return UNSUPPORTED_ADAPTER, ("image.text_to_image",), (
        f"pipeline {pipeline_class or '不明'} に対応する実行アダプタがありません。"
        "取り込みと検証はできますが、生成には使えません。",
    )


# ── 配布元の検索 ────────────────────────────────────────────────────────
#
# repository ID を手で入力させるのは、名前を既に知っている人にしか使えない。
# 探すところから引き受ける。ただし探せることと入れてよいことは別なので、
# 結果は候補のままで、取り込みは従来どおり resolve と明示承諾を通す。

SEARCH_LIMIT = 30
# 配布元。既定は Civitai にしてある。実際に絵を作るのに使われている調整済みの
# モデルはそちらに集まっていて、Hugging Face 側には基盤モデルが並ぶ。
MODEL_SOURCES = ("civitai", "huggingface")
DEFAULT_MODEL_SOURCE = "civitai"
_CIVITAI_REPO = re.compile(r"^civitai/[0-9]{1,12}$")


def source_of(repo_id: str) -> str:
    """その ID がどの配布元のものか。形で決まるので、宣言に頼らない。"""
    return "civitai" if _CIVITAI_REPO.fullmatch(repo_id or "") else "huggingface"
SEARCH_SORTS = ("downloads", "likes", "lastModified", "createdAt")
# 画像生成として扱える組み合わせだけを既定で探す。使えないものを既定で出さない。
SEARCH_PIPELINES = ("text-to-image", "image-to-image", "inpainting")

# 探す人が実際に決めているのは「どんな絵を作るモデルか」であって、
# text-to-image か image-to-image かではない。後者は配布元の技術的な分類で、
# SD 系はほぼ全部が text-to-image なので絞り込みの役に立たない。
# 配布元のタグで、選ぶ基準そのもので絞れるようにする。
SEARCH_STYLES: dict[str, str] = {
    "any": "",
    "anime": "anime",
    "art": "art",
    "realistic": "realistic",
    "pixel-art": "pixel-art",
    "3d": "3d",
    "character": "character",
    "landscape": "landscape",
}


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
    weight_bytes: int = 0
    weight_precision: str = ""

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
            "weight_bytes": self.weight_bytes,
            "weight_precision": self.weight_precision,
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
        style: str = "any",
        limit: int = SEARCH_LIMIT,
    ) -> list[CatalogCandidate]:
        if sort not in SEARCH_SORTS:
            raise CustomModelError("custom_model_sort_invalid", "並び順が正しくありません")
        if pipeline_tag not in SEARCH_PIPELINES:
            raise CustomModelError("custom_model_pipeline_invalid", "用途が正しくありません")
        if style not in SEARCH_STYLES:
            raise CustomModelError("custom_model_style_invalid", "画風の指定が正しくありません")
        if not isinstance(query, str) or len(query) > 200:
            raise CustomModelError("custom_model_query_invalid", "検索語が長すぎます")
        params: dict[str, Any] = {
            "pipeline_tag": pipeline_tag,
            # Diffusers 形式に限る。ここを緩めると、取り込めない候補ばかり並ぶ。
            "library": "diffusers",
            "sort": sort,
            "direction": -1,
            "limit": max(1, min(SEARCH_LIMIT, limit)),
            # expand を使うと応答は要求した項目だけになる。今読んでいる列を
            # 全部並べる必要があり、足すのを忘れると静かに空欄になる。
            "expand[]": [
                "author", "downloads", "likes", "lastModified", "pipeline_tag",
                "library_name", "gated", "tags", "safetensors", "gguf",
            ],
        }
        if SEARCH_STYLES[style]:
            params["filter"] = SEARCH_STYLES[style]
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
            weight_bytes, precision = _weights_from_safetensors(item.get("safetensors"))
            if not weight_bytes:
                weight_bytes, precision = _weights_from_gguf(item.get("gguf"))
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
                weight_bytes=weight_bytes,
                weight_precision=precision,
            ))
        return found


# 重みの大きさは、押す前に一番知りたい 1 行である。落ちてくる量と、載るか
# どうかが、ほぼこれで決まる。検索の一覧 API は容量を返さないが、safetensors
# の要素数と型は返すので、そこから重み自体の大きさを出す。
# 実配布物にはこれ以外（設定、tokenizer、複数版）も含まれるので、下限として扱う。
_DTYPE_BYTES = {
    "F64": 8, "I64": 8, "U64": 8,
    "F32": 4, "I32": 4, "U32": 4,
    "BF16": 2, "F16": 2, "I16": 2, "U16": 2,
    "F8_E4M3": 1, "F8_E5M2": 1, "I8": 1, "U8": 1, "BOOL": 1,
}


def _weights_from_safetensors(value: Any) -> tuple[int, str]:
    if not isinstance(value, dict):
        return 0, ""
    parameters = value.get("parameters")
    if not isinstance(parameters, dict):
        return 0, ""
    total = 0
    dominant = ("", 0)
    for dtype, count in parameters.items():
        if not isinstance(dtype, str) or not isinstance(count, int) or count < 0:
            continue
        width = _DTYPE_BYTES.get(dtype.upper())
        if width is None:
            # 知らない型を 0 バイトとして黙って足すと、総量が過少に出る。
            return 0, ""
        total += count * width
        if count > dominant[1]:
            dominant = (dtype.upper(), count)
    return total, dominant[0]


def _weights_from_gguf(value: Any) -> tuple[int, str]:
    """GGUF 配布は safetensors を持たない。配布元が返す実バイト数を使う。

    量子化の版を全部足した数なので、実際に落とす 1 本より必ず大きい。
    見出しでそう言い分けられるよう、出所を区別して返す。
    """
    if not isinstance(value, dict):
        return 0, ""
    total = value.get("totalFileSize")
    if not isinstance(total, int) or total <= 0:
        return 0, ""
    return total, "GGUF"


# ── 手元にある重みの取り込み ──────────────────────────────────────────────
#
# 配布元から落とすのが唯一の経路だと、既に手元にある重みが使えない。実際に
# あるのは、別の道具で落とした、別の機械から持ってきた、配布元がもう無い、
# といった場合である。取り込み自体は同じ規則を通す: どのコードも実行せず、
# 重みの digest を自分で計算し、experimental として入れる。
#
# 配布元 API が無いので digest は「配布元がそう言った」ではなく「この機械で
# こう読めた」になる。意味が違うので、その旨を warning に残す。

_LOCAL_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# model_index.json の _class_name から adapter を決める。Hub のタグでは
# FLUX も Qwen-Image も「diffusers + text-to-image」で同じ顔になるので、
# repository 自身の申告を見る。
#
# 下の一覧は diffusers の AUTO_TEXT2IMAGE_PIPELINES_MAPPING をそのまま写した
# もので、AutoPipelineForText2Image が構築できるクラスである。つまり
# diffusers.sdxl（AutoPipeline の上に載っている）が読み込める形式の全部で、
# 推測ではない。実測は SSD-1B（SDXL 系）だけなので、他は取り込めても
# experimental のまま入り、使う前に「評価」を通す必要がある。
#
# ここが実体とずれたら test_custom_models が気づく（image runtime がある
# 環境では、実行時の mapping と突き合わせる）。
AUTO_TEXT2IMAGE_CLASSES = (
    "AuraFlowPipeline",
    "ChromaPipeline",
    "CogView3PlusPipeline",
    "CogView4ControlPipeline",
    "CogView4Pipeline",
    "Flux2Pipeline",
    "FluxControlNetPipeline",
    "FluxControlPipeline",
    "FluxKontextPipeline",
    "FluxPipeline",
    "GlmImagePipeline",
    "HeliosPipeline",
    "HeliosPyramidPipeline",
    "HunyuanDiTPAGPipeline",
    "HunyuanDiTPipeline",
    "IFPipeline",
    "Ideogram4Pipeline",
    "Kandinsky3Pipeline",
    "KandinskyCombinedPipeline",
    "KandinskyV22CombinedPipeline",
    "KolorsPAGPipeline",
    "KolorsPipeline",
    "Krea2Pipeline",
    "LatentConsistencyModelPipeline",
    "Lumina2Pipeline",
    "LuminaPipeline",
    "NucleusMoEImagePipeline",
    "OvisImagePipeline",
    "PRXPipeline",
    "PixArtAlphaPipeline",
    "PixArtSigmaPAGPipeline",
    "PixArtSigmaPipeline",
    "QwenImageControlNetPipeline",
    "QwenImagePipeline",
    "SanaPAGPipeline",
    "SanaPipeline",
    "StableCascadeCombinedPipeline",
    "StableDiffusion3ControlNetPipeline",
    "StableDiffusion3PAGPipeline",
    "StableDiffusion3Pipeline",
    "StableDiffusionControlNetPAGPipeline",
    "StableDiffusionControlNetPipeline",
    "StableDiffusionPAGPipeline",
    "StableDiffusionPipeline",
    "StableDiffusionXLControlNetPAGPipeline",
    "StableDiffusionXLControlNetPipeline",
    "StableDiffusionXLControlNetUnionPipeline",
    "StableDiffusionXLPAGPipeline",
    "StableDiffusionXLPipeline",
    "WuerstchenCombinedPipeline",
    "ZImageControlNetInpaintPipeline",
    "ZImageControlNetPipeline",
    "ZImageOmniPipeline",
    "ZImagePipeline",
)

# 専用の adapter を持つものはそちらへ。Flux2KleinPipeline は
# DiffusersFlux2KleinAdapter が text encoder ごと面倒を見る。
_DEDICATED_ADAPTERS = {"Flux2KleinPipeline": "diffusers.flux2-klein"}

_PIPELINE_ADAPTERS = {
    **_DEDICATED_ADAPTERS,
    **{name: "diffusers.sdxl" for name in AUTO_TEXT2IMAGE_CLASSES},
}


def _scan_local_directory(root: Path, *, limit_bytes: int) -> tuple[list[ResolvedWeight], list[str], int]:
    """Walk one model directory, hashing weights and listing config files."""
    weights: list[ResolvedWeight] = []
    required: list[str] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CustomModelError(
                "custom_model_path_invalid", f"{path.name} は symlink です。実体だけを取り込みます"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        name = path.name.lower()
        if name.endswith(WEIGHT_SUFFIXES):
            size = path.stat().st_size
            total += size
            if total > limit_bytes:
                raise CustomModelError(
                    "custom_model_too_large", "このフォルダは取り込み上限を超えています"
                )
            if len(weights) >= MAX_WEIGHT_FILES:
                raise CustomModelError("custom_model_too_many_files", "ファイル数が多すぎます")
            weights.append(ResolvedWeight(
                path=relative, size_bytes=size, sha256=_sha256_file(path)
            ))
        elif name.endswith(REQUIRED_FILE_SUFFIXES) and len(required) < MAX_REQUIRED_FILES:
            required.append(relative)
    return weights, sorted(required), total


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()




# 単一ファイルの checkpoint を、どの寸法・歩数で回すか。ディレクトリ形式と
# 違って config が無いので、系統の申告から決めるしかない。SD 1.5 は 512 で
# 学習されており、1024 で回すと構図が二重になる。
_SINGLE_FILE_NATIVE = {
    "sd15": 512, "sd20": 512, "sd21": 512,
    "sdxl": 1024, "pony": 1024, "illustrious": 1024, "noobai": 1024,
    "sd3": 1024, "sd35": 1024,
}


def single_file_runtime_options(base_model: str) -> dict[str, Any]:
    from worker_packs.image.adapters.diffusers_single_file import normalize_base_model

    side = _SINGLE_FILE_NATIVE.get(normalize_base_model(base_model))
    if side is None:
        raise CustomModelError(
            "custom_model_family_unknown",
            f"{base_model} を読む pipeline が分かりません",
        )
    return {
        "base_model": base_model,
        "native_width": side,
        "native_height": side,
        # 蒸留版かどうかは配布元の表記からは分からない。多い側に倒す。
        "default_steps": 30,
    }


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
        self.civitai = CivitaiSource(transport=transport, timeout_sec=timeout_sec)
        self.transport = transport
        self.timeout_sec = timeout_sec
        # installer と同じ上限。取得を始めてから落とすより先に伝える。
        self.max_download_bytes = max_download_bytes

    # ── 配布元 ─────────────────────────────────────────────────────────────

    async def search_source(
        self, source: str, query: str, *, sort: str = "downloads",
        model_type: str = "checkpoint", **options: Any
    ) -> list[dict[str, Any]]:
        """配布元を選んで検索する。

        Hugging Face は diffusers 形式の基盤モデルが並ぶ。Civitai は実際に
        絵を作るのに使われている調整済みのものが並ぶ。どちらか一方しか
        引けないと、探しているものが「存在しない」ことになる。
        """
        if source == "civitai":
            try:
                return await self.civitai.search(query, sort=sort, model_type=model_type)
            except CivitaiError as exc:
                raise CustomModelError(exc.code, str(exc)) from exc
        if source == "huggingface":
            if model_type != "checkpoint":
                # Hugging Face 側に LoRA の取り込み経路がまだ無い。空を返して
                # 「無い」ように見せると、探し方が悪いのだと思わせる。
                raise CustomModelError(
                    "custom_model_type_unsupported",
                    "Hugging Face からの LoRA 取り込みには未対応です。Civitai を選んでください",
                )
            return [item.document() for item in await self.search(query, sort=sort, **options)]
        raise CustomModelError("custom_model_source_invalid", "配布元の指定が正しくありません")

    async def resolve_source(
        self, source: str, repo_id: str, revision: str
    ) -> CustomModelResolution:
        """取り込む。配布元が指定されていなければ ID の形から決める。

        検索の既定は Civitai だが、取り込みでその既定を当てると、
        Hugging Face の repository を Civitai に問い合わせることになる。
        ``civitai/123`` は他の配布元の ID と衝突しない形なので、迷わない。
        """
        source = source or source_of(repo_id)
        if source == "civitai":
            return await self.resolve_civitai(repo_id, revision)
        if source == "huggingface":
            return await self.resolve(repo_id, revision)
        raise CustomModelError("custom_model_source_invalid", "配布元の指定が正しくありません")

    async def resolve_civitai(self, repo_id: str, revision: str) -> CustomModelResolution:
        """Civitai の 1 つの版を、取り込める形にする。

        digest は配布元が公表しているものを使う。手元で計算した値では
        「落ちてきたものが壊れていない」しか言えず、配布元の意図した中身か
        どうかは言えない。
        """
        prefix, _, number = repo_id.partition("/")
        if prefix != "civitai" or not number.isdigit():
            raise CustomModelError("custom_model_repo_invalid", "Civitai の model ID ではありません")
        try:
            version = await self.civitai.version(
                int(number), int(revision) if str(revision).isdigit() else None
            )
        except CivitaiError as exc:
            raise CustomModelError(exc.code, str(exc)) from exc
        weight = ResolvedWeight(
            path=version.file.name, size_bytes=version.file.size_bytes, sha256=version.file.sha256
        )
        if version.model_type == "lora":
            return self._lora_resolution(repo_id, revision, version, weight)
        return CustomModelResolution(
            repo_id=repo_id,
            revision=str(version.version_id),
            requested_revision=str(revision or ""),
            license="配布元の表記に従う",
            license_notice=(
                "Civitai の配布物です。利用条件は配布元のページで確認してください。"
            ),
            gated=False,
            pipeline_tag="text-to-image",
            library_name="single-file",
            weights=(weight,),
            required_files=(),
            total_bytes=version.file.size_bytes,
            runtime_adapter="diffusers.sdxl-single-file",
            capabilities=("image.text_to_image",),
            max_download_bytes=self.max_download_bytes,
            runtime_options=single_file_runtime_options(version.base_model),
            warnings=(
                f"{version.base_model} として読み込みます。"
                "実行経路は未計測なので、使う前に「評価」で確かめてください。",
            ),
        )


    def _lora_resolution(
        self, repo_id: str, revision: str, version: Any, weight: ResolvedWeight
    ) -> CustomModelResolution:
        """LoRA は単体では絵を作れない。

        capability を `image.lora` にしておくと、routing は最初から候補に
        入れない（`capability in item.capabilities` で絞るため）。旗を立てて
        後から除外する作りにすると、除外を書き忘れた経路が 1 つでもあれば
        LoRA が本体として選ばれる。
        """
        from worker_packs.image.adapters.diffusers_single_file import normalize_base_model

        family = normalize_base_model(version.base_model)
        if not family:
            raise CustomModelError(
                "custom_model_family_unknown",
                f"{version.base_model} 用の LoRA を載せられる系統が分かりません",
            )
        return CustomModelResolution(
            repo_id=repo_id,
            revision=str(version.version_id),
            requested_revision=str(revision or ""),
            license="配布元の表記に従う",
            license_notice="Civitai の配布物です。利用条件は配布元のページで確認してください。",
            gated=False,
            pipeline_tag="text-to-image",
            library_name="lora",
            weights=(weight,),
            required_files=(),
            total_bytes=weight.size_bytes,
            runtime_adapter="lora.diffusers",
            capabilities=("image.lora",),
            max_download_bytes=self.max_download_bytes,
            runtime_options={
                "base_model": version.base_model,
                **({"trigger_words": list(version.trigger_words)}
                   if version.trigger_words else {}),
            },
            warnings=(
                f"{version.base_model} の checkpoint に載せる LoRA です。"
                + ("起動語を prompt に入れないと効きません。"
                   if version.trigger_words else "起動語の指定はありません。"),
            ),
        )

    async def lora_base_requirement(self, base_model: str, installed_families: set[str]) -> dict[str, Any]:
        """その LoRA を載せられる checkpoint が手元にあるか。

        無いなら、何を一緒に落とすことになるのかを押す前に見せる。LoRA は
        40MB 前後だが土台は 2〜7GB あるので、黙って始めると 40MB のつもりが
        7GB 落ちてくる。
        """
        from worker_packs.image.adapters.diffusers_single_file import normalize_base_model

        family = normalize_base_model(base_model)
        if family and family in installed_families:
            return {"satisfied": True, "family": family, "candidate": None}
        candidate = None
        try:
            candidate = await self.civitai.base_candidate(base_model)
        except CivitaiError:
            # 候補が引けないことは、土台が無いという事実を変えない。
            candidate = None
        return {"satisfied": False, "family": family, "candidate": candidate}

    # ── resolve ────────────────────────────────────────────────────────────

    async def resolve(self, repo_id: str, revision: str) -> CustomModelResolution:
        if not isinstance(repo_id, str) or _REPO_ID.fullmatch(repo_id) is None:
            raise CustomModelError("custom_model_repo_invalid", "repository ID の形式が正しくありません")
        if not isinstance(revision, str) or _REVISION_REF.fullmatch(revision) is None:
            raise CustomModelError("custom_model_revision_invalid", "revision の形式が正しくありません")
        payload = await self._metadata(repo_id, revision)
        # どの系統かは repository 自身の model_index.json が持っている。
        # Hub のタグでは FLUX と Qwen-Image まで同じ顔になる。
        pipeline_class = await self._pipeline_class(repo_id, str(payload.get("sha") or ""))
        return self._resolution(repo_id, revision, payload, pipeline_class)

    async def _pipeline_class(self, repo_id: str, revision: str) -> str:
        """Read `_class_name` from the repository's own model_index.json.

        One small extra fetch, and the only way to know which family this is.
        Failing to read it is not fatal — it simply means we cannot claim an
        adapter, which is the same position as before.
        """
        if _COMMIT.fullmatch(revision) is None:
            return ""
        url = f"{self.origin}/{repo_id}/resolve/{revision}/model_index.json"
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_sec, follow_redirects=True
            ) as client:
                response = await client.get(url)
            if response.status_code != 200 or len(response.content) > MAX_METADATA_BYTES:
                return ""
            document = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            return ""
        if not isinstance(document, dict):
            return ""
        name = document.get("_class_name")
        return name[:128] if isinstance(name, str) else ""

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
        self, repo_id: str, requested: str, payload: dict[str, Any],
        pipeline_class: str = "",
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
            str(payload.get("library_name") or ""),
            str(payload.get("pipeline_tag") or ""),
            pipeline_class,
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

    # ── 手元のフォルダ ──────────────────────────────────────────────────

    def resolve_local(self, directory: str, *, name: str) -> CustomModelResolution:
        """Describe a model that is already on this machine, without any network.

        The verification story changes and the caller must be told: a digest
        here means "this is what this machine read", not "this is what the
        publisher published". Everything else stays the same — no repository
        code runs, and the entry lands as experimental.
        """
        if not _LOCAL_MODEL_ID.fullmatch(name or ""):
            raise CustomModelError(
                "custom_model_name_invalid",
                "名前は英数字と . _ - だけ、64 文字までにしてください",
            )
        try:
            root = Path(directory).expanduser()
        except (OSError, ValueError) as exc:
            raise CustomModelError("custom_model_path_invalid", "場所を読み取れませんでした") from exc
        if not root.is_absolute():
            raise CustomModelError("custom_model_path_invalid", "場所は絶対パスで指定してください")
        if root.is_symlink():
            raise CustomModelError("custom_model_path_invalid", "symlink ではなく実体を指定してください")
        try:
            root = root.resolve(strict=True)
        except OSError as exc:
            raise CustomModelError("custom_model_path_missing", "その場所が見つかりません") from exc
        if not root.is_dir():
            raise CustomModelError("custom_model_path_invalid", "フォルダを指定してください")

        index = root / "model_index.json"
        if not index.is_file():
            raise CustomModelError(
                "custom_model_not_diffusers",
                "model_index.json がありません。Diffusers 形式のフォルダを指定してください",
            )
        if index.stat().st_size > MAX_METADATA_BYTES:
            raise CustomModelError("custom_model_metadata_invalid", "model_index.json が大きすぎます")
        try:
            document = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise CustomModelError(
                "custom_model_metadata_invalid", "model_index.json を読み取れませんでした"
            ) from exc
        pipeline = str((document or {}).get("_class_name") or "") if isinstance(document, dict) else ""

        weights, required, total_bytes = _scan_local_directory(
            root, limit_bytes=self.max_download_bytes
        )
        if not weights:
            raise CustomModelError(
                "custom_model_no_weights", "このフォルダに取り込める重みがありません"
            )

        adapter = _PIPELINE_ADAPTERS.get(pipeline, UNSUPPORTED_ADAPTER)
        warnings = (
            "digest はこの機械で読み取った値です。配布元が公表した値との照合はしていません。",
        )
        if adapter == UNSUPPORTED_ADAPTER:
            warnings = warnings + (
                f"pipeline {pipeline or '不明'} に対応する実行アダプタがありません。"
                "取り込みと検証はできますが、生成には使えません。",
            )
        capabilities = () if adapter == UNSUPPORTED_ADAPTER else ("image.text_to_image",)

        # revision は「この中身」を指す値にする。フォルダは後から書き換わりうるので、
        # 読み取った時点の内容を identity にしておかないと来歴が嘘になる。
        revision = hashlib.sha256(
            "\n".join(f"{item.path}:{item.sha256}" for item in weights).encode("utf-8")
        ).hexdigest()
        return CustomModelResolution(
            repo_id=f"local/{name}",
            revision=revision,
            requested_revision="local",
            license="unknown",
            license_notice=(
                "手元のフォルダから取り込みます。配布元のライセンスは利用者が確認してください。"
            ),
            gated=False,
            pipeline_tag="text-to-image",
            library_name="diffusers",
            weights=tuple(sorted(weights, key=lambda item: item.path)),
            required_files=tuple(required),
            total_bytes=total_bytes,
            runtime_adapter=adapter,
            capabilities=capabilities,
            max_download_bytes=self.max_download_bytes,
            warnings=warnings,
            local_root=root,
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
        entry = self._entry(resolution, display_name=display_name, domains=domains)
        existing = next(
            (index for index, item in enumerate(entries)
             if item.get("registry", {}).get("model_id") == resolution.repo_id),
            None,
        )
        if existing is not None:
            # 拒むのではなく置き換える。同じ repository を確認し直して入れ直す
            # のは「もう一度やり直したい」という意味で、拒否すると、古い判定で
            # 入った entry を直す方法が無くなる（実測: adapter を後から実装
            # しても、既に入っている分は unsupported のままだった）。
            if entries[existing] == entry:
                raise CustomModelError("custom_model_exists", "そのモデルは既に追加されています")
            entries[existing] = entry
            self._write(entries)
            return entry
        if len(entries) >= MAX_CUSTOM_MODELS:
            raise CustomModelError("custom_model_limit", "追加できるモデルの数を超えています")
        entries.append(entry)
        self._write(entries)
        return entry

    def add_bundle(
        self,
        items: tuple[tuple[CustomModelResolution, str, str], ...],
        *,
        domains: tuple[str, ...] = ("general",),
    ) -> list[dict[str, Any]]:
        """Register a LoRA and its base dependency in one durable write.

        A partially written catalog would leave the UI claiming that a LoRA
        can be downloaded while its required base is unknown.  Validate every
        license and limit first, then replace the catalog once.
        """
        if not items:
            raise CustomModelError("custom_model_bundle_empty", "取り込むモデルがありません")
        entries = self.entries()
        additions: list[dict[str, Any]] = []
        for resolution, display_name, acceptance in items:
            if acceptance != resolution.license:
                raise CustomModelError(
                    "custom_model_license_not_accepted",
                    "表示したライセンスをそのまま承諾してください",
                )
            if not resolution.within_download_cap:
                raise CustomModelError(
                    "custom_model_too_large", "この repository は取り込み上限を超えています"
                )
            entry = self._entry(resolution, display_name=display_name, domains=domains)
            existing = next(
                (index for index, item in enumerate(entries)
                 if item.get("registry", {}).get("model_id") == resolution.repo_id),
                None,
            )
            if existing is None:
                if len(entries) >= MAX_CUSTOM_MODELS:
                    raise CustomModelError(
                        "custom_model_limit", "追加できるモデルの数を超えています"
                    )
                entries.append(entry)
            elif entries[existing] != entry:
                entries[existing] = entry
            additions.append(entry)
        self._write(entries)
        return additions

    def record_measurement(self, model_id: str, measurements: dict[str, Any]) -> dict[str, Any]:
        """Promote an entry from "nobody has run this" to "this is what it costs".

        Until a model has been run here it stays experimental and routing will
        not pick it, because choosing one would mean guessing its VRAM and
        finding out during someone's work. Once there are real numbers from
        this machine, the guess is gone and the model can be routed.

        Only entries this catalog owns are touched — the shipped manifest is
        not rewritten at runtime.
        """
        entries = self.entries()
        for entry in entries:
            registry = entry.get("registry")
            if not isinstance(registry, dict) or registry.get("model_id") != model_id:
                continue
            if registry.get("runtime_adapter") == UNSUPPORTED_ADAPTER:
                raise CustomModelError(
                    "custom_model_unsupported",
                    "実行アダプタが無いモデルは、測っても使えるようにはなりません",
                )
            registry["measurements"] = measurements
            registry["measurement_confidence"] = "measured"
            registry["state"] = "available"
            self._write(entries)
            return entry
        raise CustomModelError("custom_model_not_added", "そのモデルは追加されていません")

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
                **({"runtime_options": dict(resolution.runtime_options)}
                   if resolution.runtime_options else {}),
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
                    "kind": source_of(resolution.repo_id),
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
