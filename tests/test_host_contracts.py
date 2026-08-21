from __future__ import annotations

from mediaforge.host.files import require_grant_id
from mediaforge.host.jobs import ProgressGate
from pathlib import Path

from mediaforge.host.resources import fake_image_request, image_model_request
from mediaforge.models import ModelDescriptor, ModelState


def test_fake_lease_request_has_complete_vram_and_runtime_estimate():
    payload = fake_image_request("job_123", runtime_sec=12.5)
    assert "owner" not in payload
    assert payload["estimated_runtime_sec"] == 12.5
    assert payload["vram"]["confidence"] == "low"
    assert set(payload["vram"]) == {
        "resident_bytes", "execution_peak_bytes", "cold_load_peak_bytes", "headroom_bytes", "confidence",
    }


def test_measured_image_lease_preserves_all_vram_dimensions():
    model = ModelDescriptor(
        model_id="owner/model",
        family="test",
        version="1",
        revision="a" * 40,
        weights_hash="sha256:" + "b" * 64,
        license="Apache-2.0",
        runtime_adapter="test",
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm",),
        state=ModelState.AVAILABLE,
        policy_rank={"auto": 1},
        required_files=("config.json",),
        weights=(),
        installed=True,
        healthy=True,
        local_path=Path("/model"),
        resident_vram_bytes=11,
        execution_peak_vram_bytes=22,
        cold_load_peak_vram_bytes=33,
        headroom_vram_bytes=44,
        measured_runtime_sec=55.5,
    )
    payload = image_model_request("job_123", model, workload_class="workflow")

    assert payload["vram"] == {
        "resident_bytes": 11,
        "execution_peak_bytes": 22,
        "cold_load_peak_bytes": 33,
        "headroom_bytes": 44,
        "confidence": "measured",
    }
    assert payload["estimated_runtime_sec"] == 55.5
    assert payload["class"] == "workflow"
    assert payload["residency_key"] == "mediaforge:owner/model:" + "a" * 40


def test_host_progress_gate_is_monotonic_and_limited_to_two_hz():
    gate = ProgressGate()
    assert gate.accept(progress=0.1, phase="starting", now=1.0)
    assert not gate.accept(progress=0.2, phase="generating", now=1.2)
    assert gate.accept(progress=0.2, phase="generating", now=1.5)
    assert not gate.accept(progress=0.1, phase="generating", now=2.0)
    assert gate.accept(progress=1.0, phase="complete", terminal=True, now=2.01)


def test_file_boundary_accepts_only_opaque_grant_ids():
    assert require_grant_id("grant:abc-123") == "grant:abc-123"
    for value in ("/tmp/file.png", "file.png", "asset:abc", "grant:/tmp/file.png"):
        try:
            require_grant_id(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unscoped value: {value}")
