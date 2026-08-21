from __future__ import annotations

from mediaforge.host.files import require_grant_id
from mediaforge.host.jobs import ProgressGate
from mediaforge.host.resources import fake_image_request


def test_fake_lease_request_has_complete_vram_and_runtime_estimate():
    payload = fake_image_request("job_123", runtime_sec=12.5)
    assert payload["owner"] == "addon:media-forge"
    assert payload["estimated_runtime_sec"] == 12.5
    assert payload["vram"]["confidence"] == "low"
    assert set(payload["vram"]) == {
        "resident_bytes", "execution_peak_bytes", "cold_load_peak_bytes", "headroom_bytes", "confidence",
    }


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
