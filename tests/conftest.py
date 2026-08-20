from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mediaforge.app import create_app
from mediaforge.config import Settings


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(Settings(data_dir=tmp_path / "data", worker_timeout_sec=3))
    with TestClient(app) as value:
        yield value


def wait_terminal(client: TestClient, job_id: str, timeout: float = 5) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed", "canceled"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach a terminal state")
