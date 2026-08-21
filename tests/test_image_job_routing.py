from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mediaforge.domain import JobRequest
from mediaforge.host.client import HostIdentity
from mediaforge.host.jobs import HostExecution
from mediaforge.jobs import JobManager, OOM_FLOOR_INCREMENT_BYTES, WorkerFailure
from mediaforge.models import ModelDescriptor, ModelState
from mediaforge.store import Store


def measured_model() -> ModelDescriptor:
    return ModelDescriptor(
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
        resident_vram_bytes=100,
        execution_peak_vram_bytes=200,
        cold_load_peak_vram_bytes=300,
        headroom_vram_bytes=50,
        measured_runtime_sec=12.5,
    )


def test_oom_raises_next_broker_admission_floor(tmp_path: Path):
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    model = measured_model()
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    execution = HostExecution(
        identity=HostIdentity(
            authorization="Bearer test",
            addon_id="media-forge",
            subject="user:test",
            expires_at=2**31,
            granted_capabilities=frozenset({"jobs.write", "resources.acquire"}),
        ),
        host_job_id="host-job",
        workload_class="interactive",
        owns_terminal=True,
    )

    manager._record_oom(model)
    request = manager._resource_request(job, execution, model, 1.0)

    expected_total = model.measured_vram_bytes + OOM_FLOOR_INCREMENT_BYTES
    assert request["vram"]["execution_peak_bytes"] + request["vram"]["headroom_bytes"] == expected_total
    assert request["vram"]["cold_load_peak_bytes"] + request["vram"]["headroom_bytes"] == expected_total
    assert request["vram"]["confidence"] == "measured"


def test_real_model_rejects_dimensions_outside_measured_envelope_before_lease(tmp_path: Path):
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    model = measured_model()
    model = replace(model, max_width=1024, max_height=1024, max_pixels=1048576)
    job = store.create_job(JobRequest(
        operation="image.generate",
        intent="test",
        constraints={"width": 1536, "height": 512},
    ))

    with pytest.raises(WorkerFailure) as exc:
        manager._validate_generation_limits(job, model)

    assert exc.value.code == "resource_limit"
