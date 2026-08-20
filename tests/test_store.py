from __future__ import annotations

from pathlib import Path

from mediaforge.domain import JobRequest, JobStatus
from mediaforge.store import Store


def test_store_recovers_interrupted_running_job_as_failed(tmp_path: Path):
    store = Store(tmp_path / "state")
    store.initialize()
    job = store.create_job(JobRequest(operation="image.generate", intent="recover me"))
    store.update_job(job.id, status=JobStatus.RUNNING, phase="generating")

    restarted = Store(tmp_path / "state")
    restarted.initialize()
    recovered = restarted.get_job(job.id)
    assert recovered.status == JobStatus.FAILED
    assert recovered.error is not None and recovered.error.code == "service_restarted"

