from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from conftest import wait_terminal
from mediaforge.app import create_app
from mediaforge.config import Settings


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def issue(key: bytes, *, aud: str = "media-forge", now: int | None = None, lifetime: int = 600) -> str:
    issued = int(time.time()) if now is None else now
    encoded = _b64(json.dumps({
        "aud": aud,
        "sub": "job:test",
        "kind": "service",
        "iat": issued,
        "exp": issued + lifetime,
        "nonce": "test-nonce",
    }, sort_keys=True, separators=(",", ":")).encode())
    signature = _b64(hmac.new(key, encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def host_client(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    key = b"k" * 32
    key_file = tmp_path / "addon-token.key"
    key_file.write_bytes(key)
    key_file.chmod(0o600)
    app = create_app(Settings(data_dir=tmp_path / "data", worker_timeout_sec=3, host_token_key_file=key_file))
    headers = {
        "Authorization": f"Bearer {issue(key)}",
        "X-Control-Deck-Addon-ID": "media-forge",
    }
    return TestClient(app), headers


def generate_input(intent: str = "host generated robot") -> dict:
    return {
        "operation": "image.generate",
        "intent": intent,
        "constraints": {"width": 48, "height": 32},
        "local_only": True,
    }


def test_host_execution_requires_valid_audience_bound_token(tmp_path: Path):
    client, headers = host_client(tmp_path)
    with client:
        assert client.post("/addon/v1/agent/capabilities", json={}).status_code == 401
        wrong = dict(headers)
        wrong["Authorization"] = f"Bearer {issue(b'k' * 32, aud='another-addon')}"
        assert client.post("/addon/v1/agent/capabilities", json={}, headers=wrong).status_code == 401
        expired = dict(headers)
        expired["Authorization"] = f"Bearer {issue(b'k' * 32, now=int(time.time()) - 601)}"
        assert client.post("/addon/v1/agent/capabilities", json={}, headers=expired).status_code == 401
        assert client.post("/addon/v1/agent/capabilities", json={}, headers=headers).status_code == 200


def test_agent_capabilities_never_disclose_model_names(tmp_path: Path):
    client, headers = host_client(tmp_path)
    with client:
        response = client.post("/addon/v1/agent/capabilities", json={"input": {}}, headers=headers)
    serialized = json.dumps(response.json()).lower()
    assert response.status_code == 200
    assert "fake-image" not in serialized and "flux" not in serialized and "qwen" not in serialized


def test_workflow_and_agent_generate_return_opaque_references(tmp_path: Path):
    client, headers = host_client(tmp_path)
    with client:
        workflow = client.post(
            "/addon/v1/workflow/execute",
            json={"input": generate_input(), "correlation": {"execution_id": "7", "node_id": "n1"}},
            headers=headers,
        )
        assert workflow.status_code == 200
        assert set(workflow.json()) == {"job_id", "status", "asset_ids"}
        assert wait_terminal(client, workflow.json()["job_id"])["status"] == "succeeded"

        agent = client.post(
            "/addon/v1/agent/generate",
            json={"input": generate_input("agent robot"), "correlation": {"job_id": "host-job"}},
            headers=headers,
        )
        assert agent.status_code == 200
        assert agent.json()["job_id"].startswith("job_")
        assert agent.json()["asset_id"].startswith("asset_")


def test_host_payload_rejects_raw_paths_and_context_requires_grant(tmp_path: Path):
    client, headers = host_client(tmp_path)
    with client:
        raw = client.post(
            "/addon/v1/workflow/execute",
            json={"input": {**generate_input(), "constraints": {"source": "/etc/passwd"}}},
            headers=headers,
        )
        assert raw.status_code == 422
        assert raw.json()["detail"]["code"] == "unscoped_host_path"

        missing = client.post(
            "/addon/v1/context/edit-image",
            json={"input": {}, "context": {"type": "file", "resource_id": "file-1", "grant_id": "token"}},
            headers=headers,
        )
        assert missing.status_code == 422
        accepted = client.post(
            "/addon/v1/context/edit-image",
            json={"input": {}, "context": {"type": "file", "resource_id": "grant:abc", "grant_id": "opaque-token"}},
            headers=headers,
        )
        assert accepted.status_code == 200
        assert "grant_id" not in json.dumps(accepted.json())


def test_workspace_uses_host_bridge_without_browser_storage(tmp_path: Path):
    client, _headers = host_client(tmp_path)
    with client:
        index = client.get("/")
        script = client.get("/static/app.js")
    assert index.status_code == 200 and 'data-bridge="waiting"' in index.text
    assert script.status_code == 200
    assert "control-deck-addon.connect" in script.text
    assert "theme.changed" in script.text and "route.sync" in script.text and "disable.pending" in script.text
    assert "localStorage" not in script.text and "sessionStorage" not in script.text and "document.cookie" not in script.text
