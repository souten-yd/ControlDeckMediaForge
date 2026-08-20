from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from conftest import wait_terminal


def request(intent: str = "a tiny blue robot", **constraints):
    return {
        "operation": "image.generate",
        "intent": intent,
        "model_policy": "auto",
        "constraints": {"width": 96, "height": 64, **constraints},
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


def test_fake_generation_registers_asset_and_complete_provenance(client):
    created = client.post("/api/v1/jobs", json=request())
    assert created.status_code == 202
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
    assert {item["validator"] for item in provenance["validation"]} == {
        "image.non_empty", "image.dimensions", "image.mode", "image.alpha"
    }
    root = Path(__file__).parents[1]
    jsonschema.validate(asset, json.loads((root / "schemas/asset.json").read_text(encoding="utf-8")))
    jsonschema.validate(provenance, json.loads((root / "schemas/provenance.json").read_text(encoding="utf-8")))


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


def test_worker_crash_fails_only_that_job_and_runner_survives(client):
    crashed = client.post("/api/v1/jobs", json=request(_fake_crash=True)).json()
    failed = wait_terminal(client, crashed["id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "worker_crash"

    healthy = client.post("/api/v1/jobs", json=request("the next request")).json()
    assert wait_terminal(client, healthy["id"])["status"] == "succeeded"
    assert client.get("/health").status_code == 200


def test_running_job_can_be_canceled(client):
    created = client.post("/api/v1/jobs", json=request(_fake_delay_sec=2)).json()
    response = client.delete(f"/api/v1/jobs/{created['id']}")
    assert response.status_code == 200
    terminal = wait_terminal(client, created["id"])
    assert terminal["status"] == "canceled"
    assert terminal["asset_ids"] == []


def test_addon_tools_return_ids_without_model_names(client):
    capabilities = client.post("/addon/v1/agent/capabilities", json={"input": {}})
    assert capabilities.status_code == 200
    assert "fake-image" not in json.dumps(capabilities.json())

    generated = client.post("/addon/v1/agent/generate", json={"input": request()})
    assert generated.status_code == 200
    body = generated.json()
    assert body["job_id"].startswith("job_") and body["asset_ids"] == []
    assert "model" not in json.dumps(body).lower()


def test_context_action_requires_opaque_grant_and_rejects_paths(client):
    missing = client.post("/addon/v1/context/edit-image", json={"context": {"resource_id": "asset:1"}})
    assert missing.status_code == 422
    raw = client.post(
        "/addon/v1/context/edit-image",
        json={"context": {"grant_id": "grant:abc", "resource_id": "file:/etc/passwd"}},
    )
    assert raw.status_code == 422
    scoped = client.post(
        "/addon/v1/context/edit-image",
        json={"context": {"grant_id": "grant:abc", "resource_id": "asset:1"}},
    )
    assert scoped.status_code == 409


def test_health_reports_partial_capabilities_without_hiding_workspace(client):
    payload = client.get("/health").json()
    assert payload["status"] == "healthy"
    assert payload["contributions"]["navigation:workspace"] == "available"
    assert payload["contributions"]["context_action:edit-image"]["state"] == "unavailable"
