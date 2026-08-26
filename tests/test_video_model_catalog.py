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
    "zai-org/CogVideoX-2b",
    "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
    "Wan-AI/Wan2.1-VACE-1.3B-diffusers",
    "tencent/HunyuanVideo-1.5",
    "MiniMaxAI/MiniMax-H3",
    "DiffSynth-Studio/MiniMax-H3-NF4",
    "unsloth/MiniMax-H3-GGUF",
}


def registry() -> ModelRegistry:
    return ModelRegistry.load(
        ROOT / "worker_packs/image/models.json",
        catalog_manifest=ROOT / "worker_packs/image/catalog.json",
    )


def test_video_candidates_are_pinned_and_never_recommended() -> None:
    candidates = {model.model_id: model for model in registry().all() if "video" in model.media_types}

    assert set(candidates) == VIDEO_IDS
    assert all(model.state == "experimental" for model in candidates.values())
    wan = candidates["Wan-AI/Wan2.2-TI2V-5B"]
    assert wan.measurement_confidence == "measured"
    assert wan.hardware_backends == ("cuda", "rocm")
    assert wan.execution_peak_vram_bytes == 30_700_000_000
    assert wan.headroom_vram_bytes == 1024 * 1024 * 1024
    assert wan.measured_runtime_sec == 75.955
    cog = candidates["zai-org/CogVideoX-2b"]
    assert cog.measurement_confidence == "low"
    assert cog.hardware_backends == ("cuda", "rocm")
    vace = candidates["Wan-AI/Wan2.1-VACE-1.3B-diffusers"]
    assert vace.measurement_confidence == "low"
    assert vace.hardware_backends == ("cuda", "rocm")
    assert all(
        model.measurement_confidence == "low"
        and model.measured_runtime_sec is None
        and model.measured_vram_bytes is None
        and model.hardware_backends == ("cuda",)
        for model_id, model in candidates.items()
        if model_id not in {wan.model_id, cog.model_id, vace.model_id}
    )
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


def test_only_bounded_complete_video_snapshots_are_managed() -> None:
    candidates = {model.model_id: model for model in registry().all() if model.model_id in VIDEO_IDS}

    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.MANAGED} == {
        "Wan-AI/Wan2.2-TI2V-5B",
        "Wan-AI/Wan2.2-I2V-A14B",
        "Wan-AI/Wan2.2-T2V-A14B",
        "unsloth/MiniMax-H3-GGUF",
    }
    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.EXTERNAL} == {
        "Wan-AI/Wan2.2-Animate-14B",
        "Lightricks/LTX-2.3",
        "zai-org/CogVideoX-2b",
        "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
        "Wan-AI/Wan2.1-VACE-1.3B-diffusers",
        "tencent/HunyuanVideo-1.5",
        "MiniMaxAI/MiniMax-H3",
        "DiffSynth-Studio/MiniMax-H3-NF4",
    }


def test_wan21_13b_candidates_remain_external_and_unroutable() -> None:
    candidates = {model.model_id: model for model in registry().all()}
    t2v = candidates["Wan-AI/Wan2.1-T2V-1.3B-Diffusers"]
    vace = candidates["Wan-AI/Wan2.1-VACE-1.3B-diffusers"]

    assert t2v.ownership == ModelOwnership.EXTERNAL
    assert t2v.approx_download_bytes == 28_935_653_511
    assert t2v.capabilities == ("video.text_to_video",)
    assert t2v.hardware_backends == ("cuda",)
    assert len(t2v.weights) == 10

    assert vace.ownership == ModelOwnership.EXTERNAL
    assert vace.approx_download_bytes == 19_043_130_596
    assert vace.capabilities == (
        "video.image_to_video",
        "video.multi_keyframe",
        "video.video_to_video",
    )
    assert vace.hardware_backends == ("cuda", "rocm")
    assert len(vace.weights) == 8


def test_minimax_h3_is_license_gated_and_never_claims_r9700_support() -> None:
    model = next(item for item in registry().all() if item.model_id == "MiniMaxAI/MiniMax-H3")

    assert model.version == "fl2va-bf16"
    assert model.gated is True
    assert model.ownership == ModelOwnership.EXTERNAL
    assert model.hardware_backends == ("cuda",)
    assert model.state == "experimental"
    assert model.approx_download_bytes == 144_051_182_625
    assert len(model.weights) == 29
    assert len(model.required_files) == 52
    assert model.license_acceptance_id is not None


def test_minimax_h3_nf4_bundle_is_bounded_below_local_download_limit() -> None:
    model = next(
        item for item in registry().all()
        if item.model_id == "DiffSynth-Studio/MiniMax-H3-NF4"
    )

    assert model.version == "fl2va-pruned-nf4"
    assert model.gated is True
    assert model.ownership == ModelOwnership.EXTERNAL
    assert model.approx_download_bytes == 27_705_875_746
    assert model.approx_download_bytes < 32_000_000_000
    assert len(model.weights) == 4
    assert model.hardware_backends == ("cuda",)
    assert model.state == "experimental"


def test_minimax_h3_gguf_composite_bundle_is_bounded_and_pinned() -> None:
    model = next(item for item in registry().all() if item.model_id == "unsloth/MiniMax-H3-GGUF")

    assert model.version == "fl2va-pruned-ud-q2-k-xl"
    assert model.gated is True
    assert model.ownership == ModelOwnership.MANAGED
    assert model.approx_download_bytes == 26_978_277_946
    assert model.approx_download_bytes < 32_000_000_000
    assert len(model.weights) == 4
    assert {item.source.repo_id for item in model.weights if item.source is not None} == {
        "Comfy-Org/MiniMax-H3"
    }
    assert model.hardware_backends == ("cuda",)
    assert model.state == "experimental"


def test_unmeasured_video_candidates_cannot_route_on_r9700() -> None:
    with pytest.raises(ModelRouteError, match="no measured local model"):
        route_model(
            registry().all(),
            capability="video.image_to_video",
            policy="auto",
            hardware_backend="rocm",
            free_vram_bytes=34_208_743_424,
        )
