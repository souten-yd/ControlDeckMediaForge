from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from mediaforge.models import ModelDescriptor, ModelRegistry, ModelRegistryError, ModelState
from mediaforge.routing import ModelRouteError, route_model


def descriptor(identifier: str, *, rank: int, vram: int, state: ModelState = ModelState.AVAILABLE):
    return ModelDescriptor(
        model_id=identifier,
        family="test",
        version="1",
        revision="a" * 40,
        weights_hash="sha256:" + "b" * 64,
        license="Apache-2.0",
        runtime_adapter="test",
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm",),
        state=state,
        policy_rank={"auto": rank, "fast": rank, "balanced": rank, "quality": rank, "low_vram": rank},
        required_files=("config.json",),
        weights=(),
        installed=True,
        healthy=state == ModelState.AVAILABLE,
        local_path=Path("/model") / identifier,
        resident_vram_bytes=max(0, vram - 1),
        execution_peak_vram_bytes=vram,
        cold_load_peak_vram_bytes=vram,
        headroom_vram_bytes=0,
        measured_runtime_sec=1.0,
    )


def test_router_is_deterministic_for_capability_policy_and_measured_vram():
    models = (
        descriptor("quality", rank=20, vram=12_000),
        descriptor("fast-b", rank=10, vram=8_000),
        descriptor("fast-a", rank=10, vram=8_000),
    )
    assert route_model(
        models, capability="image.text_to_image", policy="auto",
        hardware_backend="rocm", free_vram_bytes=10_000,
    ).model_id == "fast-a"


def test_router_never_promotes_unmeasured_or_experimental_model():
    unmeasured = replace(descriptor("unmeasured", rank=1, vram=1), execution_peak_vram_bytes=None)
    experimental = descriptor("experimental", rank=1, vram=1, state=ModelState.EXPERIMENTAL)
    with pytest.raises(ModelRouteError) as error:
        route_model(
            (unmeasured, experimental), capability="image.text_to_image", policy="auto",
            hardware_backend="rocm", free_vram_bytes=100_000,
        )
    assert error.value.code == "capability_unavailable"
    with pytest.raises(ModelRouteError) as manual_error:
        route_model(
            (experimental,), capability="image.text_to_image", policy="manual",
            model_id="experimental", hardware_backend="rocm", free_vram_bytes=100_000,
        )
    assert manual_error.value.code == "model_unavailable"


def test_router_does_not_fall_back_to_another_capability():
    with pytest.raises(ModelRouteError) as error:
        route_model(
            (descriptor("image", rank=1, vram=1),), capability="video.image_to_video",
            policy="auto", hardware_backend="rocm", free_vram_bytes=100,
        )
    assert error.value.code == "capability_unavailable"


def test_registry_detects_exact_huggingface_snapshot(tmp_path):
    digest = "c" * 64
    manifest = tmp_path / "models.json"
    manifest.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [{
            "model_id": "owner/model", "family": "test", "version": "1", "revision": "d" * 40,
            "weights_hash": "sha256:" + "e" * 64, "license": "Apache-2.0", "runtime_adapter": "test",
            "runtime_options": {"device_mode": "direct_device_map", "disable_mmap": True},
            "generation_limits": {"max_width": 1024, "max_height": 768, "max_pixels": 786432},
            "capabilities": ["image.text_to_image"], "hardware_backends": ["rocm"],
            "state": "experimental", "policy_rank": {"auto": 1},
            "measurements": None,
            "required_files": ["config.json"],
            "weights": [{"path": "model.safetensors", "size_bytes": 4, "sha256": digest}],
        }],
    }), encoding="utf-8")
    blob = tmp_path / "huggingface" / "hub" / "models--owner--model" / "blobs" / digest
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"test")
    snapshot = blob.parent.parent / "snapshots" / ("d" * 40)
    snapshot.mkdir(parents=True)
    config_blob = blob.parent / ("f" * 64)
    config_blob.write_text("{}", encoding="utf-8")
    (snapshot / "config.json").symlink_to(config_blob)
    (snapshot / "model.safetensors").symlink_to(blob)
    model = ModelRegistry.load(manifest, hf_home=tmp_path / "huggingface").all()[0]
    assert model.installed is True
    assert model.healthy is False
    assert model.local_path == snapshot.resolve()
    assert model.device_mode == "direct_device_map"
    assert model.disable_mmap is True
    assert (model.max_width, model.max_height, model.max_pixels) == (1024, 768, 786432)


def test_registry_rejects_escape_and_hash_mismatch(tmp_path):
    manifest = tmp_path / "models.json"
    value = {
        "schema_version": "1.0",
        "models": [{
            "model_id": "owner/model", "family": "test", "version": "1", "revision": "d" * 40,
            "weights_hash": "sha256:" + "e" * 64, "license": "Apache-2.0", "runtime_adapter": "test",
            "capabilities": ["image.text_to_image"], "hardware_backends": ["rocm"],
            "state": "experimental", "policy_rank": {"auto": 1},
            "measurements": None,
            "required_files": ["config.json"],
            "weights": [{"path": "../escape", "size_bytes": 4, "sha256": "c" * 64}],
        }],
    }
    manifest.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ModelRegistryError):
        ModelRegistry.load(manifest, hf_home=tmp_path / "huggingface")


def test_registry_requires_complete_positive_runtime_measurements(tmp_path):
    manifest = tmp_path / "models.json"
    base = {
        "model_id": "owner/model", "family": "test", "version": "1", "revision": "d" * 40,
        "weights_hash": "sha256:" + "e" * 64, "license": "Apache-2.0", "runtime_adapter": "test",
        "capabilities": ["image.text_to_image"], "hardware_backends": ["rocm"],
        "state": "available", "policy_rank": {"auto": 1}, "required_files": ["config.json"],
        "weights": [{"path": "model.safetensors", "size_bytes": 4, "sha256": "c" * 64}],
    }
    base["measurements"] = {
        "resident_vram_bytes": 1,
        "execution_peak_vram_bytes": 2,
        "cold_load_peak_vram_bytes": 3,
        "headroom_vram_bytes": 4,
        "measured_runtime_sec": 0,
    }
    manifest.write_text(json.dumps({"schema_version": "1.0", "models": [base]}), encoding="utf-8")

    with pytest.raises(ModelRegistryError, match="runtime measurement"):
        ModelRegistry.load(manifest)


def test_registry_rejects_unknown_runtime_options(tmp_path):
    manifest = tmp_path / "models.json"
    value = {
        "schema_version": "1.0",
        "models": [{
            "model_id": "owner/model", "family": "test", "version": "1", "revision": "d" * 40,
            "weights_hash": "sha256:" + "e" * 64, "license": "Apache-2.0", "runtime_adapter": "test",
            "runtime_options": {"device_mode": "magic"},
            "capabilities": ["image.text_to_image"], "hardware_backends": ["rocm"],
            "state": "experimental", "policy_rank": {"auto": 1}, "measurements": None,
            "required_files": ["config.json"],
            "weights": [{"path": "model.safetensors", "size_bytes": 4, "sha256": "c" * 64}],
        }],
    }
    manifest.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ModelRegistryError, match="runtime_options"):
        ModelRegistry.load(manifest)


def test_registry_rejects_invalid_generation_limits(tmp_path):
    manifest = tmp_path / "models.json"
    value = {
        "schema_version": "1.0",
        "models": [{
            "model_id": "owner/model", "family": "test", "version": "1", "revision": "d" * 40,
            "weights_hash": "sha256:" + "e" * 64, "license": "Apache-2.0", "runtime_adapter": "test",
            "generation_limits": {"max_pixels": True},
            "capabilities": ["image.text_to_image"], "hardware_backends": ["rocm"],
            "state": "experimental", "policy_rank": {"auto": 1}, "measurements": None,
            "required_files": ["config.json"],
            "weights": [{"path": "model.safetensors", "size_bytes": 4, "sha256": "c" * 64}],
        }],
    }
    manifest.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ModelRegistryError, match="generation_limits"):
        ModelRegistry.load(manifest)
