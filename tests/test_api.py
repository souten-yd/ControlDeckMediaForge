from __future__ import annotations

from fastapi.testclient import TestClient

from mediaforge.app import create_app


def test_health_defaults_to_setup_required(monkeypatch):
    monkeypatch.delenv("MEDIA_FORGE_ENV_STATUS_FILE", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "setup_required"
    assert payload["contract_version"] == "2.0"
    assert payload["contributions"]["navigation:workspace"] == "available"
    assert payload["contributions"]["workflow_executor:media.generate"]["state"] == "unavailable"


def test_health_supports_all_states_only_when_test_endpoint_is_enabled(monkeypatch):
    monkeypatch.setenv("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS", "1")
    monkeypatch.delenv("MEDIA_FORGE_ENV_STATUS_FILE", raising=False)
    with TestClient(create_app()) as client:
        for state in ("healthy", "degraded", "unavailable", "setup_required"):
            response = client.post("/test/health", json={"status": state})
            assert response.status_code == 200
            assert response.json()["status"] == state


def test_health_switch_is_hidden_by_default(monkeypatch):
    monkeypatch.delenv("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS", raising=False)
    with TestClient(create_app()) as client:
        response = client.post("/test/health", json={"status": "healthy"})

    assert response.status_code == 404


def test_schema_path_cannot_escape_schema_directory():
    with TestClient(create_app()) as client:
        response = client.get("/schemas/not-present.json")

    assert response.status_code == 404
