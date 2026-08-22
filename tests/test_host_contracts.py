from __future__ import annotations

import asyncio
import time

from mediaforge.host.files import require_grant_id
from mediaforge.host.client import HostIdentity
from mediaforge.host.jobs import HostExecution, HostJobReporter, ProgressGate
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


def test_bootstrap_image_lease_does_not_claim_measured_confidence():
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
        resident_vram_bytes=0,
        execution_peak_vram_bytes=30,
        cold_load_peak_vram_bytes=30,
        headroom_vram_bytes=2,
        measured_runtime_sec=1200,
        measurement_confidence="low",
    )

    assert image_model_request("job_123", model)["vram"]["confidence"] == "low"


def test_host_progress_gate_is_monotonic_and_limited_to_two_hz():
    gate = ProgressGate()
    assert gate.accept(progress=0.1, phase="starting", now=1.0)
    assert not gate.accept(progress=0.2, phase="generating", now=1.2)
    assert gate.accept(progress=0.2, phase="generating", now=1.5)
    assert not gate.accept(progress=0.1, phase="generating", now=2.0)
    assert gate.accept(progress=1.0, phase="complete", terminal=True, now=2.01)


def test_forced_host_progress_waits_instead_of_bypassing_two_hz_limit():
    class Client:
        def __init__(self) -> None:
            self.sent_at: list[float] = []

        async def update_job(self, _identity, _job_id, _payload):
            self.sent_at.append(time.monotonic())

    async def scenario() -> list[float]:
        client = Client()
        reporter = HostJobReporter(
            client,  # type: ignore[arg-type]
            HostExecution(
                identity=HostIdentity(
                    authorization="Bearer test",
                    addon_id="media-forge",
                    subject="7",
                    expires_at=2_000_000_000,
                    granted_capabilities=frozenset({"jobs.write"}),
                ),
                host_job_id="host-job",
                workload_class="batch",
                owns_terminal=True,
            ),
        )
        assert await reporter.progress("first", 0.1, force=True)
        assert await reporter.progress("second", 0.2, force=True)
        return client.sent_at

    sent_at = asyncio.run(scenario())
    assert len(sent_at) == 2
    assert sent_at[1] - sent_at[0] >= 0.5


def test_file_boundary_accepts_only_opaque_grant_ids():
    assert require_grant_id("grant:abc-123") == "grant:abc-123"
    for value in ("/tmp/file.png", "file.png", "asset:abc", "grant:/tmp/file.png"):
        try:
            require_grant_id(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unscoped value: {value}")
