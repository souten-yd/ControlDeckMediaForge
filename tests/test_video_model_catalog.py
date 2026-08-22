from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mediaforge.models import ModelOwnership, ModelRegistry
from mediaforge.routing import ModelRouteError, route_model


ROOT = Path(__file__).parents[1]
VIDEO_IDS = {
    "Wan-AI/Wan2.2-TI2V-5B",
    "Wan-AI/Wan2.2-I2V-A14B",
    "Wan-AI/Wan2.2-T2V-A14B",
    "Wan-AI/Wan2.2-Animate-14B",
    "Lightricks/LTX-2.3",
    "tencent/HunyuanVideo-1.5",
}


def registry() -> ModelRegistry:
    return ModelRegistry.load(
        ROOT / "worker_packs/image/models.json",
        catalog_manifest=ROOT / "worker_packs/image/catalog.json",
    )


def test_video_candidates_are_pinned_unmeasured_and_never_recommended() -> None:
    candidates = {model.model_id: model for model in registry().all() if "video" in model.media_types}

    assert set(candidates) == VIDEO_IDS
    assert all(model.state == "experimental" for model in candidates.values())
    assert all(model.measurement_confidence == "low" for model in candidates.values())
    assert all(model.measured_runtime_sec is None and model.measured_vram_bytes is None for model in candidates.values())
    assert all(model.hardware_backends == ("cuda",) for model in candidates.values())
    assert all(not model.recommended_profiles for model in candidates.values())
    assert all(model.approx_download_bytes >= sum(weight.size_bytes for weight in model.weights)
               for model in candidates.values())


def test_video_checkpoint_identity_hashes_are_reproducible() -> None:
    for model in registry().all():
        if model.model_id not in VIDEO_IDS:
            continue
        canonical = "".join(
            f"{weight.path}\0{weight.size_bytes}\0{weight.sha256}\n"
            for weight in sorted(model.weights, key=lambda item: item.path)
        ).encode()
        assert model.weights_hash == "sha256:" + hashlib.sha256(canonical).hexdigest()


def test_only_bounded_complete_wan_snapshots_are_managed() -> None:
    candidates = {model.model_id: model for model in registry().all() if model.model_id in VIDEO_IDS}

    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.MANAGED} == {
        "Wan-AI/Wan2.2-TI2V-5B",
        "Wan-AI/Wan2.2-I2V-A14B",
        "Wan-AI/Wan2.2-T2V-A14B",
    }
    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.EXTERNAL} == {
        "Wan-AI/Wan2.2-Animate-14B",
        "Lightricks/LTX-2.3",
        "tencent/HunyuanVideo-1.5",
    }


def test_unmeasured_video_candidates_cannot_route_on_r9700() -> None:
    with pytest.raises(ModelRouteError, match="no measured local model"):
        route_model(
            registry().all(),
            capability="video.image_to_video",
            policy="auto",
            hardware_backend="rocm",
            free_vram_bytes=34_208_743_424,
        )
