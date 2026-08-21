from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class ModelRegistryError(RuntimeError):
    pass


class ModelState(StrEnum):
    UNAVAILABLE = "unavailable"
    EXPERIMENTAL = "experimental"
    AVAILABLE = "available"


@dataclass(frozen=True)
class WeightFile:
    path: str
    size_bytes: int
    sha256: str


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
    measured_vram_bytes: int | None = None
    measured_runtime_sec: float | None = None


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
        path = _required_string(item, "path")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ModelRegistryError("model registry weight path must be relative and contained")
        size = item.get("size_bytes")
        digest = _required_string(item, "sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0 or _SHA256.fullmatch(digest) is None:
            raise ModelRegistryError("model registry weight metadata is invalid")
        weights.append(WeightFile(path=path, size_bytes=size, sha256=digest))
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
    if _MODEL_ID.fullmatch(model_id) is None or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ModelRegistryError("model registry identity is invalid")
    required_files = _string_tuple(value, "required_files")
    if any(Path(path).is_absolute() or ".." in Path(path).parts for path in required_files):
        raise ModelRegistryError("model registry required file path must be relative and contained")
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
    )


class ModelRegistry:
    def __init__(self, descriptors: tuple[ModelDescriptor, ...]):
        identifiers = [item.model_id for item in descriptors]
        if len(identifiers) != len(set(identifiers)):
            raise ModelRegistryError("model registry contains duplicate model IDs")
        self._descriptors = descriptors

    @classmethod
    def load(cls, manifest: Path, *, hf_home: Path | None = None) -> "ModelRegistry":
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"model registry could not be read: {manifest}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != "1.0":
            raise ModelRegistryError("model registry schema_version is unsupported")
        models = value.get("models")
        if not isinstance(models, list):
            raise ModelRegistryError("model registry models must be an array")
        descriptors = tuple(_descriptor(item) for item in models if isinstance(item, dict))
        if len(descriptors) != len(models):
            raise ModelRegistryError("model registry entry must be an object")
        registry = cls(descriptors)
        return registry.detect_huggingface(hf_home) if hf_home is not None else registry

    def all(self) -> tuple[ModelDescriptor, ...]:
        return self._descriptors

    def detect_huggingface(self, hf_home: Path) -> "ModelRegistry":
        detected: list[ModelDescriptor] = []
        for descriptor in self._descriptors:
            repo_root = hf_home / "hub" / ("models--" + descriptor.model_id.replace("/", "--"))
            snapshot = repo_root / "snapshots" / descriptor.revision
            installed = (
                snapshot.is_dir()
                and all(self._required_file_matches(repo_root, snapshot, item) for item in descriptor.required_files)
                and all(self._weight_matches(repo_root, snapshot, item) for item in descriptor.weights)
            )
            detected.append(replace(
                descriptor,
                installed=installed,
                healthy=installed and descriptor.state == ModelState.AVAILABLE,
                local_path=snapshot.resolve() if installed else None,
            ))
        return ModelRegistry(tuple(detected))

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
