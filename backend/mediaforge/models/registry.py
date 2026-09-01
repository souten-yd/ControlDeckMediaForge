from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from .generation_defaults import (  # noqa: F401
    native_side_from_config,
    base_model_from_config,
    normalize_base_model,
    pipeline_class_from_config,
    resolution_buckets,
    resolve_steps,
    snap_to_native,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_CIVITAI_MODEL_ID = re.compile(r"^civitai/[0-9]{1,12}$")
_CIVITAI_REVISION = re.compile(r"^[0-9]{1,12}$")
# 配布元ごとに、revision が何を指すかが違う。Hugging Face は commit、
# Civitai は version の番号である。片方の形を両方に当てると、取り込めるはずの
# ものを弾くか、指していないものを指せるようになる。
_SOURCE_REVISIONS = {
    "huggingface": re.compile(r"^[0-9a-f]{40}$"),
    "civitai": re.compile(r"^[0-9]{1,12}$"),
}
_SOURCE_KINDS = frozenset(_SOURCE_REVISIONS)


def _source_revision_valid(source: "ModelSource") -> bool:
    pattern = _SOURCE_REVISIONS.get(source.kind)
    return pattern is not None and pattern.fullmatch(source.revision) is not None


def _model_revision_valid(model_id: str, revision: str) -> bool:
    """Validate the immutable identity used for the installed snapshot.

    Hugging Face names an immutable commit. Civitai has no Git commit in its
    public contract; its immutable identity is the numeric model-version ID.
    Only the explicit ``civitai/<number>`` namespace gets that exception, so a
    generic repository cannot weaken the 40-hex requirement.
    """
    return _GIT_REVISION.fullmatch(revision) is not None or (
        _CIVITAI_MODEL_ID.fullmatch(model_id) is not None
        and _CIVITAI_REVISION.fullmatch(revision) is not None
    )
_DOMAINS = {"general", "anime", "illustration", "photoreal", "game2d", "poster", "character_sheet", "background"}
_MEDIA_TYPES = {"image", "video", "audio_video"}


class ModelRegistryError(RuntimeError):
    pass


class ModelState(StrEnum):
    UNAVAILABLE = "unavailable"
    EXPERIMENTAL = "experimental"
    AVAILABLE = "available"


class ModelOwnership(StrEnum):
    MANAGED = "managed"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ModelSource:
    kind: str
    repo_id: str
    revision: str


@dataclass(frozen=True)
class WeightFile:
    path: str
    size_bytes: int
    sha256: str
    source: ModelSource | None = None


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    family: str
    version: str
    revision: str
    weights_hash: str
    license: str
    runtime_adapter: str
    capabilities: tuple[str, ...]
    hardware_backends: tuple[str, ...]
    state: ModelState
    policy_rank: dict[str, int]
    required_files: tuple[str, ...]
    weights: tuple[WeightFile, ...]
    installed: bool = False
    healthy: bool = False
    local_path: Path | None = None
    resident_vram_bytes: int | None = None
    execution_peak_vram_bytes: int | None = None
    cold_load_peak_vram_bytes: int | None = None
    headroom_vram_bytes: int | None = None
    measured_runtime_sec: float | None = None
    measurement_confidence: str = "measured"
    device_mode: str = "full_device"
    disable_mmap: bool = False
    # SD 系だけが取る。FLUX.2 Klein では常に既定のままになる。
    negative_prompt: str = ""
    guidance_scale: float | None = None
    # ステップ数はモデル固有である。FLUX.2 Klein は蒸留済みで 4 歩で絵になるが、
    # SDXL 系を 4 歩で回すと像を結ばない。共通の既定を置くと、片方が必ず壊れる。
    default_steps: int | None = None
    # 歩数がどこから来たか。宣言・モデルが名乗った・判別できず置いた、の別。
    default_steps_source: str = "assumed"
    # 単一ファイルの checkpoint が、どの系統として配られているか。ファイル
    # 自身は名乗らないので、配布元の申告をそのまま持つ。
    base_model: str = ""
    # LoRA が効くために prompt へ入れる必要のある語。持たない LoRA もある。
    trigger_words: tuple[str, ...] = ()

    @property
    def is_lora(self) -> bool:
        return "image.lora" in self.capabilities
    # そのモデルが学習された画面寸法。宣言が無ければ導入時に repository の
    # config から読む。None は「まだ分かっていない」で、1024 とは違う。
    native_width: int | None = None
    native_height: int | None = None
    max_width: int = 2048
    max_height: int = 2048
    max_pixels: int = 2048 * 2048
    display_name: str = ""
    domains: tuple[str, ...] = ()
    media_types: tuple[str, ...] = ()
    description: str = ""
    approx_download_bytes: int = 0
    source: ModelSource | None = None
    ownership: ModelOwnership = ModelOwnership.EXTERNAL
    supports_lora: bool = False
    # 実測にもとづく動画の作り方。持たないモデルは None。
    video: dict[str, Any] | None = None
    upscale: dict[str, Any] | None = None
    max_references: int = 0
    reference_roles: tuple[str, ...] = ()
    supports_reference_strength: bool = False
    recommended_profiles: tuple[str, ...] = ()
    gated: bool = False
    license_notice: str = ""

    @property
    def measured_vram_bytes(self) -> int | None:
        values = (self.execution_peak_vram_bytes, self.cold_load_peak_vram_bytes, self.headroom_vram_bytes)
        if any(value is None for value in values):
            return None
        return max(self.execution_peak_vram_bytes or 0, self.cold_load_peak_vram_bytes or 0) + (
            self.headroom_vram_bytes or 0
        )

    @property
    def removable(self) -> bool:
        return self.installed and self.ownership == ModelOwnership.MANAGED

    @property
    def license_acceptance_id(self) -> str | None:
        """Bind an explicit acceptance to the exact catalog license and revision."""
        if not self.gated:
            return None
        canonical = "\0".join((self.model_id, self.revision, self.license, self.license_notice))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _required_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ModelRegistryError(f"model registry field {key} must be a non-empty string")
    return result


def _string_tuple(value: dict[str, Any], key: str) -> tuple[str, ...]:
    result = value.get(key)
    if not isinstance(result, list) or not result or any(not isinstance(item, str) or not item for item in result):
        raise ModelRegistryError(f"model registry field {key} must be a non-empty string array")
    return tuple(result)


def _descriptor(value: dict[str, Any]) -> ModelDescriptor:
    weights_value = value.get("weights")
    if not isinstance(weights_value, list) or not weights_value:
        raise ModelRegistryError("model registry weights must be a non-empty array")
    weights: list[WeightFile] = []
    for item in weights_value:
        if not isinstance(item, dict):
            raise ModelRegistryError("model registry weight entry must be an object")
        if set(item) - {"path", "size_bytes", "sha256", "source"}:
            raise ModelRegistryError("model registry weight entry fields are invalid")
        path = _required_string(item, "path")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ModelRegistryError("model registry weight path must be relative and contained")
        size = item.get("size_bytes")
        digest = _required_string(item, "sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0 or _SHA256.fullmatch(digest) is None:
            raise ModelRegistryError("model registry weight metadata is invalid")
        source_value = item.get("source")
        source = None
        if source_value is not None:
            if not isinstance(source_value, dict) or set(source_value) != {"kind", "repo_id", "revision"}:
                raise ModelRegistryError("model registry weight source is invalid")
            source = ModelSource(
                kind=_required_string(source_value, "kind"),
                repo_id=_required_string(source_value, "repo_id"),
                revision=_required_string(source_value, "revision"),
            )
            if (
                _MODEL_ID.fullmatch(source.repo_id) is None
                or not _source_revision_valid(source)
            ):
                raise ModelRegistryError("model registry weight source is invalid")
        weights.append(WeightFile(path=path, size_bytes=size, sha256=digest, source=source))
    policy = value.get("policy_rank")
    if not isinstance(policy, dict) or not policy or any(
        key not in {"auto", "fast", "balanced", "quality", "low_vram"}
        or not isinstance(rank, int) or isinstance(rank, bool) or rank < 0
        for key, rank in policy.items()
    ):
        raise ModelRegistryError("model registry policy_rank is invalid")
    weights_hash = _required_string(value, "weights_hash")
    if not weights_hash.startswith("sha256:") or _SHA256.fullmatch(weights_hash.removeprefix("sha256:")) is None:
        raise ModelRegistryError("model registry weights_hash is invalid")
    try:
        state = ModelState(_required_string(value, "state"))
    except ValueError as exc:
        raise ModelRegistryError("model registry state is invalid") from exc
    model_id = _required_string(value, "model_id")
    revision = _required_string(value, "revision")
    if _MODEL_ID.fullmatch(model_id) is None or not _model_revision_valid(model_id, revision):
        raise ModelRegistryError("model registry identity is invalid")
    required_value = value.get("required_files")
    if (
        not isinstance(required_value, list)
        or any(not isinstance(path, str) or not path for path in required_value)
    ):
        raise ModelRegistryError(
            "model registry field required_files must be a string array"
        )
    # A Civitai single-file model has no config files beside its one verified
    # weight.  The weights array remains non-empty and digest-bound; requiring
    # an unrelated extra file would make every valid single-file entry fail.
    required_files = tuple(required_value)
    if any(Path(path).is_absolute() or ".." in Path(path).parts for path in required_files):
        raise ModelRegistryError("model registry required file path must be relative and contained")
    measurements = value.get("measurements")
    measurement_values: dict[str, int | float | None] = {
        "resident_vram_bytes": None,
        "execution_peak_vram_bytes": None,
        "cold_load_peak_vram_bytes": None,
        "headroom_vram_bytes": None,
        "measured_runtime_sec": None,
    }
    if measurements is not None:
        if not isinstance(measurements, dict) or set(measurements) != set(measurement_values):
            raise ModelRegistryError("model registry measurements are invalid")
        for key in measurement_values:
            measured = measurements[key]
            if key == "measured_runtime_sec":
                if not isinstance(measured, (int, float)) or isinstance(measured, bool) or measured <= 0:
                    raise ModelRegistryError("model registry runtime measurement is invalid")
                measurement_values[key] = float(measured)
            else:
                if not isinstance(measured, int) or isinstance(measured, bool) or measured < 0:
                    raise ModelRegistryError("model registry VRAM measurement is invalid")
                measurement_values[key] = measured
    confidence = value.get("measurement_confidence", "measured" if measurements is not None else "low")
    if confidence not in {"low", "measured"}:
        raise ModelRegistryError("model registry measurement_confidence is invalid")
    runtime_options = value.get("runtime_options", {})
    # negative_prompt と guidance_scale は SD 系にだけ効く。FLUX.2 Klein は
    # どちらも取らない。系統ごとの既定なので、要求ではなくカタログに置く。
    if not isinstance(runtime_options, dict) or set(runtime_options) - {
        "device_mode", "disable_mmap", "negative_prompt", "guidance_scale",
        "default_steps", "native_width", "native_height", "base_model",
        "trigger_words", "video", "upscale",
    }:
        raise ModelRegistryError("model registry runtime_options are invalid")
    negative_prompt = runtime_options.get("negative_prompt", "")
    if not isinstance(negative_prompt, str) or len(negative_prompt) > 2000:
        raise ModelRegistryError("model registry runtime_options are invalid")
    guidance_scale = runtime_options.get("guidance_scale")
    # 0 は「CFG を使わない」という指示である。Turbo 系はそれを前提に蒸留されて
    # いるので、0 を弾くとそのモデルを正しく回せない。
    if guidance_scale is not None and (
        isinstance(guidance_scale, bool)
        or not isinstance(guidance_scale, (int, float))
        or not 0 <= guidance_scale <= 30
    ):
        raise ModelRegistryError("model registry runtime_options are invalid")
    default_steps = runtime_options.get("default_steps")
    if default_steps is not None and (
        isinstance(default_steps, bool) or not isinstance(default_steps, int)
        or not 1 <= default_steps <= 50
    ):
        raise ModelRegistryError("model registry runtime_options are invalid")
    native_size = {
        key: runtime_options[key]
        for key in ("native_width", "native_height")
        if key in runtime_options
    }
    if any(
        isinstance(side, bool) or not isinstance(side, int) or not 256 <= side <= 2048 or side % 16
        for side in native_size.values()
    ):
        raise ModelRegistryError("model registry runtime_options are invalid")
    # 動画の作り方はモデルごとに違う。fps も、取れるフレーム数の並びも、
    # 測った寸法も違う。画面が共通の決め打ちを持つと、どれかのモデルで
    # 「選べるのに作れない」値を出すことになる。測った事実をここに置く。
    video = runtime_options.get("video")
    if video is not None:
        if not isinstance(video, dict) or set(video) - {
            "fps", "frame_step", "frame_min", "frame_max", "sizes",
            "measured_width", "measured_height", "measured_frames",
            "fixed_sec", "per_frame_sec", "measured_steps",
        }:
            raise ModelRegistryError("model registry video options are invalid")
        for key in ("fps", "frame_step", "frame_min", "frame_max", "measured_steps"):
            # 外側の value は model の中身そのものである。潰さない。
            bound = video.get(key)
            if bound is not None and (
                isinstance(bound, bool) or not isinstance(bound, int) or not 1 <= bound <= 600
            ):
                raise ModelRegistryError("model registry video options are invalid")
        # 目安時間は 1 点からの比例では出せない。読み込みの固定費が大きく、
        # 短い clip では比例が過小に、長い clip では過大になる。実測から
        # 固定費と 1 フレーム単価に分けて持つ。
        for key in ("fixed_sec", "per_frame_sec"):
            cost = video.get(key)
            if cost is not None and (
                isinstance(cost, bool) or not isinstance(cost, (int, float))
                or not 0 <= cost <= 3600
            ):
                raise ModelRegistryError("model registry video options are invalid")
        sizes = video.get("sizes")
        if sizes is not None and (
            not isinstance(sizes, list)
            or not all(
                isinstance(item, list) and len(item) == 2
                and all(isinstance(side, int) and 16 <= side <= 2048 and side % 2 == 0 for side in item)
                for item in sizes
            )
        ):
            raise ModelRegistryError("model registry video options are invalid")

    # 拡大は倍率を重みが持っている。核が掛け算をするので、その値と、どこまでを
    # 受けるかをモデルの側から言う。画面が共通の決め打ちを持つと、別の倍率の
    # 重みを足したときに黙って外れる。
    upscale = runtime_options.get("upscale")
    if upscale is not None:
        if not isinstance(upscale, dict) or set(upscale) - {
            "scale", "max_source_pixels", "per_source_megapixel_sec", "measured_source_pixels",
        }:
            raise ModelRegistryError("model registry upscale options are invalid")
        scale = upscale.get("scale")
        # 1 は「寸法を変えずに直す」である（ブレ補正など）。作り直さずに直す
        # という点は拡大と同じで、経路もタイルの回し方も共通なのでここに置く。
        if isinstance(scale, bool) or not isinstance(scale, int) or not 1 <= scale <= 8:
            raise ModelRegistryError("model registry upscale options are invalid")
        for key in ("max_source_pixels", "measured_source_pixels"):
            bound = upscale.get(key)
            if bound is not None and (
                isinstance(bound, bool) or not isinstance(bound, int)
                or not 1 <= bound <= 24_000_000
            ):
                raise ModelRegistryError("model registry upscale options are invalid")
        # 出力が取り込みの上限を超える設定は、作れないものを選ばせることになる。
        source_bound = upscale.get("max_source_pixels")
        if source_bound is not None and source_bound * scale * scale > 24_000_000:
            raise ModelRegistryError("model registry upscale options are invalid")
        cost = upscale.get("per_source_megapixel_sec")
        if cost is not None and (
            isinstance(cost, bool) or not isinstance(cost, (int, float)) or not 0 < cost <= 3600
        ):
            raise ModelRegistryError("model registry upscale options are invalid")

    base_model = runtime_options.get("base_model", "")
    if not isinstance(base_model, str) or len(base_model) > 64:
        raise ModelRegistryError("model registry runtime_options are invalid")
    trigger_words = runtime_options.get("trigger_words", [])
    if (
        not isinstance(trigger_words, list)
        or len(trigger_words) > 12
        or any(not isinstance(word, str) or not word or len(word) > 80 for word in trigger_words)
    ):
        raise ModelRegistryError("model registry runtime_options are invalid")
    generation_limits = value.get("generation_limits", {})
    if not isinstance(generation_limits, dict) or set(generation_limits) - {
        "max_width", "max_height", "max_pixels"
    }:
        raise ModelRegistryError("model registry generation_limits are invalid")
    limits = {
        "max_width": generation_limits.get("max_width", 2048),
        "max_height": generation_limits.get("max_height", 2048),
        "max_pixels": generation_limits.get("max_pixels", 2048 * 2048),
    }
    if any(not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0 for limit in limits.values()):
        raise ModelRegistryError("model registry generation_limits are invalid")
    device_mode = runtime_options.get("device_mode", "full_device")
    disable_mmap = runtime_options.get("disable_mmap", False)
    if device_mode not in {"full_device", "direct_device_map", "cpu_offload"} or not isinstance(
        disable_mmap, bool
    ):
        raise ModelRegistryError("model registry runtime_options are invalid")
    return ModelDescriptor(
        model_id=model_id,
        family=_required_string(value, "family"),
        version=_required_string(value, "version"),
        revision=revision,
        weights_hash=weights_hash,
        license=_required_string(value, "license"),
        runtime_adapter=_required_string(value, "runtime_adapter"),
        capabilities=_string_tuple(value, "capabilities"),
        hardware_backends=_string_tuple(value, "hardware_backends"),
        state=state,
        policy_rank=dict(policy),
        required_files=required_files,
        weights=tuple(weights),
        measurement_confidence=confidence,
        device_mode=device_mode,
        disable_mmap=disable_mmap,
        negative_prompt=negative_prompt,
        guidance_scale=float(guidance_scale) if guidance_scale is not None else None,
        default_steps=default_steps,
        base_model=base_model,
        video=video,
        upscale=upscale,
        trigger_words=tuple(trigger_words),
        **({"default_steps_source": "declared"} if default_steps is not None else {}),
        **native_size,
        **limits,
        **measurement_values,
    )


def _catalog_metadata(value: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "model_id", "display_name", "domains", "media_types", "description", "approx_download_bytes",
        "source", "ownership", "supports_lora", "max_references", "recommended_profiles",
        "reference_roles", "supports_reference_strength", "gated", "license_notice",
    }
    optional = {"reference_roles", "supports_reference_strength"}
    if set(value) - allowed or (allowed - optional) - set(value):
        raise ModelRegistryError("model catalog entry fields are invalid")
    model_id = _required_string(value, "model_id")
    if _MODEL_ID.fullmatch(model_id) is None:
        raise ModelRegistryError("model catalog identity is invalid")
    domains = _string_tuple(value, "domains")
    if any(domain not in _DOMAINS for domain in domains) or len(domains) != len(set(domains)):
        raise ModelRegistryError("model catalog domains are invalid")
    media_types = _string_tuple(value, "media_types")
    if any(item not in _MEDIA_TYPES for item in media_types) or len(media_types) != len(set(media_types)):
        raise ModelRegistryError("model catalog media_types are invalid")
    recommended_profiles = value.get("recommended_profiles")
    if not isinstance(recommended_profiles, list) or any(
        not isinstance(item, str) or not item for item in recommended_profiles
    ):
        raise ModelRegistryError("model catalog recommended_profiles must be a string array")
    reference_roles = value.get("reference_roles", [])
    allowed_roles = {"identity", "style", "pose", "composition", "clothing", "palette", "prop", "environment"}
    if (
        not isinstance(reference_roles, list)
        or any(not isinstance(item, str) or item not in allowed_roles for item in reference_roles)
        or len(reference_roles) != len(set(reference_roles))
    ):
        raise ModelRegistryError("model catalog reference_roles are invalid")
    approx_download_bytes = value.get("approx_download_bytes")
    max_references = value.get("max_references")
    if (
        not isinstance(approx_download_bytes, int)
        or isinstance(approx_download_bytes, bool)
        or approx_download_bytes <= 0
        or not isinstance(max_references, int)
        or isinstance(max_references, bool)
        or max_references < 0
    ):
        raise ModelRegistryError("model catalog numeric metadata is invalid")
    source_value = value.get("source")
    if not isinstance(source_value, dict) or set(source_value) != {"kind", "repo_id", "revision"}:
        raise ModelRegistryError("model catalog source is invalid")
    source = ModelSource(
        kind=_required_string(source_value, "kind"),
        repo_id=_required_string(source_value, "repo_id"),
        revision=_required_string(source_value, "revision"),
    )
    if (
        source.repo_id != model_id
        or not _source_revision_valid(source)
    ):
        raise ModelRegistryError("model catalog source is invalid")
    try:
        ownership = ModelOwnership(_required_string(value, "ownership"))
    except ValueError as exc:
        raise ModelRegistryError("model catalog ownership is invalid") from exc
    supports_lora = value.get("supports_lora")
    supports_reference_strength = value.get("supports_reference_strength", False)
    gated = value.get("gated")
    if (
        not isinstance(supports_lora, bool)
        or not isinstance(supports_reference_strength, bool)
        or not isinstance(gated, bool)
    ):
        raise ModelRegistryError("model catalog boolean metadata is invalid")
    return {
        "display_name": _required_string(value, "display_name"),
        "domains": domains,
        "media_types": media_types,
        "description": _required_string(value, "description"),
        "approx_download_bytes": approx_download_bytes,
        "source": source,
        "ownership": ownership,
        "supports_lora": supports_lora,
        "max_references": max_references,
        "reference_roles": tuple(reference_roles),
        "supports_reference_strength": supports_reference_strength,
        "recommended_profiles": tuple(recommended_profiles),
        "gated": gated,
        "license_notice": _required_string(value, "license_notice"),
    }


class ModelRegistry:
    def __init__(self, descriptors: tuple[ModelDescriptor, ...]):
        identifiers = [item.model_id for item in descriptors]
        if len(identifiers) != len(set(identifiers)):
            raise ModelRegistryError("model registry contains duplicate model IDs")
        self._descriptors = descriptors

    @classmethod
    def load(
        cls,
        manifest: Path,
        *,
        hf_home: Path | None = None,
        catalog_manifest: Path | None = None,
        model_store_root: Path | None = None,
        extra_models: list[dict[str, Any]] | None = None,
        extra_catalog: list[dict[str, Any]] | None = None,
        measurements: dict[str, dict[str, Any]] | None = None,
    ) -> "ModelRegistry":
        """Load the shipped registry, optionally extended by user-added entries.

        The extra halves are validated by exactly the same parsers as the shipped
        manifests. A user-added model gets no weaker checks than a shipped one.

        `measurements` は、この機械で実際に測った値を出荷 manifest の上へ重ねる。
        出荷 manifest を実行時に書き換えない、という決まりは守る。測った値と、
        使ってよいと決めることは別なので、state は動かさない。測っただけで
        routing に載るなら、評価を押すことが採用を意味してしまう。
        """
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"model registry could not be read: {manifest}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != "1.0":
            raise ModelRegistryError("model registry schema_version is unsupported")
        models = value.get("models")
        if not isinstance(models, list):
            raise ModelRegistryError("model registry models must be an array")
        models = [*models, *(extra_models or [])]
        if measurements:
            models = [
                {**item, "measurements": measurements[item["model_id"]]}
                if isinstance(item, dict) and item.get("model_id") in measurements
                else item
                for item in models
            ]
        descriptors = tuple(_descriptor(item) for item in models if isinstance(item, dict))
        if len(descriptors) != len(models):
            raise ModelRegistryError("model registry entry must be an object")
        registry = cls(descriptors)
        if catalog_manifest is not None:
            registry = registry.with_catalog(catalog_manifest, extra_entries=extra_catalog)
        if hf_home is not None or model_store_root is not None:
            registry = registry.detect_installations(hf_home=hf_home, model_store_root=model_store_root)
        return registry

    def all(self) -> tuple[ModelDescriptor, ...]:
        return self._descriptors

    def with_catalog(
        self,
        catalog_manifest: Path,
        *,
        extra_entries: list[dict[str, Any]] | None = None,
    ) -> "ModelRegistry":
        try:
            value = json.loads(catalog_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"model catalog could not be read: {catalog_manifest}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != "1.0":
            raise ModelRegistryError("model catalog schema_version is unsupported")
        entries = value.get("models")
        if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
            raise ModelRegistryError("model catalog models must be an object array")
        entries = [*entries, *(extra_entries or [])]
        metadata: dict[str, dict[str, Any]] = {}
        for entry in entries:
            parsed = _catalog_metadata(entry)
            model_id = entry["model_id"]
            if model_id in metadata:
                raise ModelRegistryError("model catalog contains duplicate model IDs")
            metadata[model_id] = parsed
        registry_ids = {item.model_id for item in self._descriptors}
        if set(metadata) != registry_ids:
            raise ModelRegistryError("model catalog and runtime registry IDs differ")
        for descriptor in self._descriptors:
            source = metadata[descriptor.model_id]["source"]
            if source.revision != descriptor.revision:
                raise ModelRegistryError("model catalog source revision differs from runtime registry")
            media_types = set(metadata[descriptor.model_id]["media_types"])
            capability_families = {name.split(".", 1)[0] for name in descriptor.capabilities}
            expected = {"image" for family in capability_families if family == "image"}
            if "video" in capability_families:
                expected.add("video")
            if not expected.issubset(media_types) or (
                "audio_video" in media_types and "video" not in capability_families
            ):
                raise ModelRegistryError("model catalog media_types differ from runtime capabilities")
        return ModelRegistry(tuple(replace(item, **metadata[item.model_id]) for item in self._descriptors))

    def detect_huggingface(self, hf_home: Path) -> "ModelRegistry":
        return self.detect_installations(hf_home=hf_home)

    def detect_installations(
        self,
        *,
        hf_home: Path | None,
        model_store_root: Path | None = None,
    ) -> "ModelRegistry":
        detected: list[ModelDescriptor] = []
        for descriptor in self._descriptors:
            external = self._installation(descriptor, hf_home) if hf_home is not None else None
            managed = self._installation(descriptor, model_store_root) if model_store_root is not None else None
            if external is not None and managed is not None:
                raise ModelRegistryError(f"model ownership is ambiguous: {descriptor.model_id}")
            snapshot = managed or external
            ownership = ModelOwnership.MANAGED if managed is not None else (
                ModelOwnership.EXTERNAL if external is not None else descriptor.ownership
            )
            installed = snapshot is not None
            detected.append(replace(
                descriptor,
                installed=installed,
                healthy=installed and descriptor.state == ModelState.AVAILABLE,
                local_path=snapshot,
                ownership=ownership,
                **(self._observed_defaults(descriptor, snapshot) if installed else {}),
            ))
        return ModelRegistry(tuple(detected))

    @classmethod
    def _observed_defaults(cls, descriptor: ModelDescriptor, snapshot: Path) -> dict[str, Any]:
        """宣言が無いものだけ、置いてある repository 自身から読む。

        Hub から落とすモデルは追加した時点でまだ手元に無いので、そこでは
        読めない。導入が済んだここが、モデルの中身を初めて見られる場所である。
        宣言があるならそれを尊重する。実測して直した値を上書きしない。
        """
        observed: dict[str, Any] = {}
        # diffusers の repository の形をしているものだけ。動画系の native ランタイムは
        # 別の設定体系を持つので、読めた気になって埋めない。
        if not descriptor.runtime_adapter.startswith("diffusers."):
            return {}
        if descriptor.native_width is None or descriptor.native_height is None:
            side = native_side_from_config(snapshot)
            if side is not None:
                observed["native_width"] = side
                observed["native_height"] = side
        if not descriptor.base_model:
            observed["base_model"] = base_model_from_config(snapshot)
        if descriptor.default_steps is None:
            steps, source = resolve_steps(pipeline_class_from_config(snapshot), snapshot)
            observed["default_steps"] = steps
            observed["default_steps_source"] = source
        # LoRA を載せられるかは、宣言ではなく実際に載せられるかで決まる。
        # 載る条件は diffusers の checkpoint であることと、系統が分かることの
        # 2 つで、_resolved_loras() もそれしか見ていない。利用者が自分で足した
        # モデルは常に supports_lora=false で登録されるため、この旗を信じている
        # 画面だけが、worker なら載せられる組み合わせを隠していた。
        # 立てる方向にしか動かさない。宣言で false にした本当に載らないものは、
        # 系統を持たないので、ここでも false のままになる。
        if not descriptor.supports_lora:
            family = observed.get("base_model") or descriptor.base_model
            if normalize_base_model(str(family)):
                observed["supports_lora"] = True
        return observed

    @classmethod
    def _installation(cls, descriptor: ModelDescriptor, root: Path) -> Path | None:
        repo_root = root / "hub" / ("models--" + descriptor.model_id.replace("/", "--"))
        snapshot = repo_root / "snapshots" / descriptor.revision
        try:
            resolved_root = root.resolve(strict=True)
            resolved_repo = repo_root.resolve(strict=True)
            resolved_snapshot = snapshot.resolve(strict=True)
            if not resolved_repo.is_relative_to(resolved_root) or not resolved_snapshot.is_relative_to(resolved_repo):
                return None
        except OSError:
            return None
        installed = (
            resolved_snapshot.is_dir()
            and all(cls._required_file_matches(resolved_repo, resolved_snapshot, item) for item in descriptor.required_files)
            and all(cls._weight_matches(resolved_repo, resolved_snapshot, item) for item in descriptor.weights)
        )
        return resolved_snapshot if installed else None

    @staticmethod
    def _required_file_matches(repo_root: Path, snapshot: Path, relative: str) -> bool:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            return False
        try:
            resolved = (snapshot / path).resolve(strict=True)
            return resolved.is_relative_to(repo_root.resolve(strict=True)) and resolved.is_file()
        except OSError:
            return False

    @staticmethod
    def _weight_matches(repo_root: Path, snapshot: Path, weight: WeightFile) -> bool:
        candidate = snapshot / weight.path
        try:
            resolved = candidate.resolve(strict=True)
            if (
                not resolved.is_relative_to(repo_root.resolve(strict=True))
                or not resolved.is_file()
                or resolved.stat().st_size != weight.size_bytes
            ):
                return False
        except OSError:
            return False
        return resolved.name == weight.sha256
