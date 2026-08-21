from __future__ import annotations

import json
import time
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from conftest import wait_terminal
from mediaforge.app import create_app
from mediaforge.config import Settings
from mediaforge.domain import JobRequest
from mediaforge.store import Store


def request(intent: str = "a tiny blue robot", **constraints):
    return {
        "operation": "image.generate",
        "intent": intent,
        "model_policy": "auto",
        "constraints": {"width": 96, "height": 64, **constraints},
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


def test_health_defaults_to_setup_required(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "setup_required"
    assert payload["contract_version"] == "2.0"
    assert payload["contributions"]["navigation:workspace"] == "available"
    assert payload["contributions"]["workflow_executor:media.generate"] == "available"
    assert payload["contributions"]["context_action:edit-image"] == "available"


def test_health_uses_only_control_deck_reason_codes(client):
    allowed = {
        "service_not_running", "service_unreachable", "setup_incomplete", "worker_not_installed",
        "model_not_installed", "runtime_incompatible", "contract_incompatible", "capability_not_granted",
        "permission_denied", "resource_unavailable", "dependency_unavailable", "health_check_failed", "unknown",
    }
    payload = client.get("/health").json()
    for contribution in payload["contributions"].values():
        if isinstance(contribution, dict):
            assert contribution["reason_code"] in allowed


def test_health_supports_all_states_only_when_test_endpoint_is_enabled(client, monkeypatch):
    monkeypatch.setenv("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS", "1")
    for state in ("healthy", "degraded", "unavailable", "setup_required"):
        response = client.post("/test/health", json={"status": state})
        assert response.status_code == 200
        assert response.json()["status"] == state


def test_health_switch_is_hidden_by_default(client, monkeypatch):
    monkeypatch.delenv("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS", raising=False)
    response = client.post("/test/health", json={"status": "healthy"})

    assert response.status_code == 404


def test_schema_path_cannot_escape_schema_directory(client):
    assert client.get("/schemas/not-present.json").status_code == 404


def test_fake_generation_registers_asset_and_complete_provenance(client):
    created = client.post("/api/v1/jobs", json=request())
    assert created.status_code == 202
    assert created.headers["location"].startswith("/api/v1/jobs/job_")
    job = wait_terminal(client, created.json()["id"])
    assert job["status"] == "succeeded"
    assert len(job["asset_ids"]) == 1

    asset_id = job["asset_ids"][0]
    asset = client.get(f"/api/v1/assets/{asset_id}").json()
    assert (asset["width"], asset["height"], asset["mime_type"]) == (96, 64, "image/png")
    content = client.get(f"/api/v1/assets/{asset_id}/content")
    assert content.status_code == 200 and content.content.startswith(b"\x89PNG")

    provenance = client.get(f"/api/v1/assets/{asset_id}/provenance").json()
    assert provenance["asset_id"] == asset_id
    assert provenance["model_id"] == "media-forge/fake-image"
    assert provenance["weights_hash"] and provenance["license"] == "CC0-1.0"
    assert provenance["tool_versions"]["media-forge"] == "0.1.0"
    assert provenance["output_sha256"] == asset["sha256"]
    assert provenance["parent_asset_ids"] == []
    assert provenance["warnings"] == []
    assert {item["validator"] for item in provenance["validation"]} == {
        "image.non_empty",
        "image.dimensions",
        "image.mode",
        "image.alpha",
    }
    root = Path(__file__).parents[1]
    jsonschema.validate(asset, json.loads((root / "schemas/asset.json").read_text(encoding="utf-8")))
    jsonschema.validate(provenance, json.loads((root / "schemas/provenance.json").read_text(encoding="utf-8")))
    stored = client.app.state.store.asset_path(asset_id)
    sidecar = client.app.state.store.asset_dir / f"{asset_id}.provenance.json"
    assert stored.stat().st_mode & 0o777 == 0o600
    assert sidecar.stat().st_mode & 0o777 == 0o600
    assert list(client.app.state.store.work_dir.iterdir()) == []


def test_same_intent_and_seed_are_deterministic(client):
    hashes = []
    for _ in range(2):
        created = client.post("/api/v1/jobs", json=request(seed=17)).json()
        job = wait_terminal(client, created["id"])
        hashes.append(client.get(f"/api/v1/assets/{job['asset_ids'][0]}").json()["sha256"])
    assert hashes[0] == hashes[1]


def test_local_only_remote_request_is_rejected_by_backend(client):
    payload = request()
    payload["local_only"] = False
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422
    assert client.get("/api/v1/jobs").json()["items"] == []


def test_capability_discovery_does_not_expose_model_names(client):
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    serialized = json.dumps(response.json()).lower()
    assert "fake-image" not in serialized
    assert "flux" not in serialized
    assert "qwen" not in serialized


def test_manual_model_policy_is_explicit_opt_in(client):
    missing = request()
    missing["model_policy"] = "manual"
    assert client.post("/api/v1/jobs", json=missing).status_code == 422

    implicit = request()
    implicit["model_id"] = "media-forge/fake-image"
    assert client.post("/api/v1/jobs", json=implicit).status_code == 422


def test_fake_worker_rejects_unsupported_output_format_explicitly(client):
    payload = request()
    payload["output"]["format"] = "webp"
    created = client.post("/api/v1/jobs", json=payload).json()
    failed = wait_terminal(client, created["id"])

    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "unsupported_output_format"


def test_worker_crash_fails_only_that_job_and_runner_survives(client):
    crashed = client.post("/api/v1/jobs", json=request(_fake_crash=True)).json()
    failed = wait_terminal(client, crashed["id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "worker_crash"

    healthy = client.post("/api/v1/jobs", json=request("the next request")).json()
    assert wait_terminal(client, healthy["id"])["status"] == "succeeded"
    assert client.get("/health").status_code == 200


def test_running_and_queued_jobs_can_be_canceled(client):
    running = client.post("/api/v1/jobs", json=request(_fake_delay_sec=1)).json()
    deadline = time.monotonic() + 2
    while client.get(f"/api/v1/jobs/{running['id']}").json()["status"] == "queued":
        assert time.monotonic() < deadline
        time.sleep(0.01)
    queued = client.post("/api/v1/jobs", json=request("queued cancellation")).json()

    assert client.delete(f"/api/v1/jobs/{queued['id']}").json()["status"] == "canceled"
    assert client.delete(f"/api/v1/jobs/{running['id']}").status_code == 200
    assert wait_terminal(client, running["id"])["status"] == "canceled"
    assert list(client.app.state.store.work_dir.iterdir()) == []


def test_worker_timeout_is_explicit_and_core_survives(tmp_path: Path):
    app = create_app(Settings(data_dir=tmp_path / "timeout", worker_timeout_sec=0.05))
    with TestClient(app) as client:
        created = client.post("/api/v1/jobs", json=request(_fake_delay_sec=1)).json()
        failed = wait_terminal(client, created["id"])
        assert failed["status"] == "failed"
        assert failed["error"]["code"] == "worker_timeout"
        assert client.get("/health").status_code == 200


def test_graceful_service_stop_is_not_reported_as_worker_crash(tmp_path: Path):
    data_dir = tmp_path / "shutdown"
    app = create_app(Settings(data_dir=data_dir, worker_timeout_sec=3))
    with TestClient(app) as client:
        created = client.post("/api/v1/jobs", json=request(_fake_delay_sec=2)).json()
        deadline = time.monotonic() + 2
        while client.get(f"/api/v1/jobs/{created['id']}").json()["status"] == "queued":
            assert time.monotonic() < deadline
            time.sleep(0.01)

    stopped = Store(data_dir).get_job(created["id"])
    assert stopped.status == "failed"
    assert stopped.error is not None and stopped.error.code == "service_stopped"


def test_queued_job_resumes_after_service_start(tmp_path: Path):
    data_dir = tmp_path / "resume"
    store = Store(data_dir)
    store.initialize()
    queued = store.create_job(JobRequest(operation="image.generate", intent="resume queued job"))

    with TestClient(create_app(Settings(data_dir=data_dir, worker_timeout_sec=3))) as client:
        resumed = wait_terminal(client, queued.id)

    assert resumed["status"] == "succeeded"


def test_unavailable_operation_fails_explicitly(client):
    payload = request()
    payload["operation"] = "asset.pack"
    created = client.post("/api/v1/jobs", json=payload).json()
    failed = wait_terminal(client, created["id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "capability_unavailable"
