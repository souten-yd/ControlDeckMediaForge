from __future__ import annotations

import hashlib
from pathlib import Path

from mediaforge.models import ModelOwnership, ModelRegistry


ROOT = Path(__file__).parents[1]
CANDIDATE_IDS = {
    "Qwen/Qwen-Image-2512",
    "OnomaAIResearch/Illustrious-XL-v2.0",
}


def registry() -> ModelRegistry:
    return ModelRegistry.load(
        ROOT / "worker_packs/image/models.json",
        catalog_manifest=ROOT / "worker_packs/image/catalog.json",
    )


def test_image_catalog_has_distinct_unmeasured_candidate_roles() -> None:
    candidates = {model.model_id: model for model in registry().all() if model.model_id in CANDIDATE_IDS}

    assert set(candidates) == CANDIDATE_IDS
    assert all(model.media_types == ("image",) for model in candidates.values())
    assert all(model.state == "experimental" for model in candidates.values())
    assert all(model.measurement_confidence == "low" for model in candidates.values())
    assert all(model.hardware_backends == ("cuda",) for model in candidates.values())
    assert all(not model.recommended_profiles for model in candidates.values())
    assert all(
        model.approx_download_bytes >= sum(weight.size_bytes for weight in model.weights)
        for model in candidates.values()
    )
    assert candidates["Qwen/Qwen-Image-2512"].domains == (
        "general", "illustration", "poster", "background",
    )
    assert candidates["OnomaAIResearch/Illustrious-XL-v2.0"].domains == (
        "anime", "illustration", "game2d",
    )


def test_ssd_1b_is_routable_because_it_was_measured_on_real_hardware() -> None:
    """AMD Radeon AI PRO R9700 / ROCm 7.2.1 / torch 2.10 で実測した値。

    1024x1024 / 20 steps を 1 回。読み込みのピーク 4.52GB、生成のピーク
    17.4GB、327 秒。FLUX の 29.6GB より明確に省メモリで、明確に遅い。
    その通りに順位を付ける: low_vram でだけ前に出し、既定では選ばない。
    """
    model = next(item for item in registry().all() if item.model_id == "segmind/SSD-1B")

    assert model.state == "available"
    assert model.measurement_confidence == "measured"
    assert model.runtime_adapter == "diffusers.sdxl"
    # 測っていないものを capability として名乗らない。編集系は未実装である。
    assert model.capabilities == ("image.text_to_image",)
    assert model.execution_peak_vram_bytes == 17_423_816_704
    assert model.cold_load_peak_vram_bytes == 4_520_802_304
    assert model.measured_runtime_sec == 326.97
    assert model.device_mode == "full_device"

    flux = next(item for item in registry().all() if item.model_id.endswith("FLUX.2-klein-4B"))
    assert model.execution_peak_vram_bytes < flux.execution_peak_vram_bytes
    assert model.measured_runtime_sec > flux.measured_runtime_sec
    assert model.policy_rank["low_vram"] < flux.policy_rank["low_vram"]
    assert model.policy_rank["auto"] > flux.policy_rank["auto"]


def test_image_candidate_checkpoint_identity_hashes_are_reproducible() -> None:
    for model in registry().all():
        if model.model_id not in CANDIDATE_IDS:
            continue
        canonical = "".join(
            f"{weight.path}\0{weight.size_bytes}\0{weight.sha256}\n"
            for weight in sorted(model.weights, key=lambda item: item.path)
        ).encode()
        assert model.weights_hash == "sha256:" + hashlib.sha256(canonical).hexdigest()


def test_only_bounded_image_candidates_are_managed() -> None:
    candidates = {model.model_id: model for model in registry().all() if model.model_id in CANDIDATE_IDS}

    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.MANAGED} == {
        "OnomaAIResearch/Illustrious-XL-v2.0",
    }
    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.EXTERNAL} == {
        "Qwen/Qwen-Image-2512",
    }
