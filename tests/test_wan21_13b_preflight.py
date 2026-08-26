from __future__ import annotations

from worker_packs.video.wan21_13b_preflight import (
    T2V_REPOSITORY,
    T2V_REVISION,
    T2V_SNAPSHOT_BYTES,
    T2V_WEIGHT_BYTES,
    T2V_WEIGHT_FILES,
    VACE_REPOSITORY,
    VACE_REVISION,
    VACE_SNAPSHOT_BYTES,
    VACE_WEIGHT_BYTES,
    VACE_WEIGHT_FILES,
)


def test_wan21_candidates_are_exact_public_apache_diffusers_snapshots() -> None:
    assert T2V_REPOSITORY == "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
    assert T2V_REVISION == "0fad780a534b6463e45facd96134c9f345acfa5b"
    assert T2V_SNAPSHOT_BYTES == 28_935_653_511
    assert T2V_WEIGHT_FILES == 10
    assert T2V_WEIGHT_BYTES == 28_928_720_056

    assert VACE_REPOSITORY == "Wan-AI/Wan2.1-VACE-1.3B-diffusers"
    assert VACE_REVISION == "ec4d2cb062b548996b179d493fdd05340de702a1"
    assert VACE_SNAPSHOT_BYTES == 19_043_130_596
    assert VACE_WEIGHT_FILES == 8
    assert VACE_WEIGHT_BYTES == 19_036_896_776
