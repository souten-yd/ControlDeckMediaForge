from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mediaforge.app import create_app
from mediaforge.config import Settings


def fake_settings(tmp_path: Path, **overrides) -> Settings:
    """Use the G0 worker deliberately; production defaults fail closed without weights."""
    root = Path(__file__).parents[1]
    manifest = json.loads((root / "worker_packs/image/models.json").read_text(encoding="utf-8"))
    for model in manifest["models"]:
        model["state"] = "experimental"
        model["measurements"] = None
        model["measurement_confidence"] = "low"
    manifest_path = tmp_path / "test-models.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    values = {"data_dir": tmp_path / "data", "model_manifest": manifest_path, **overrides}
    return Settings(**values)


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(fake_settings(tmp_path, worker_timeout_sec=3))
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
