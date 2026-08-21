from __future__ import annotations

from pathlib import Path

from mediaforge.domain import JobRequest
from mediaforge.host.client import HostIdentity
from mediaforge.host.jobs import HostExecution
from mediaforge.jobs import JobManager, OOM_FLOOR_INCREMENT_BYTES
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
