from __future__ import annotations

import hashlib
from pathlib import Path

from mediaforge.models import ModelOwnership, ModelRegistry


ROOT = Path(__file__).parents[1]
CANDIDATE_IDS = {
    "Qwen/Qwen-Image-2512",
    "OnomaAIResearch/Illustrious-XL-v2.0",
    "segmind/SSD-1B",
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
    assert candidates["segmind/SSD-1B"].policy_rank["low_vram"] == 20


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
        "segmind/SSD-1B",
    }
    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.EXTERNAL} == {
        "Qwen/Qwen-Image-2512",
    }
