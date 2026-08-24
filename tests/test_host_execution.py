from __future__ import annotations

import base64
import asyncio
import hashlib
import json
import os
from io import BytesIO
import time
from pathlib import Path
from typing import Any

import httpx
import mediaforge.app as mediaforge_app
import pytest
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from conftest import fake_settings, wait_terminal
from mediaforge.app import create_app
from mediaforge.config import Settings
from mediaforge.host import client as host_client_module
from mediaforge.host.client import ControlDeckHostClient, HostApiError
from mediaforge.host.files import commit_file, read_grant
from mediaforge.store import Store


def control_deck_stub() -> tuple[FastAPI, dict[str, Any]]:
    app = FastAPI()
    grant_buffer = BytesIO()
    Image.new("RGBA", (3, 2), (10, 20, 30, 255)).save(grant_buffer, format="PNG")
    state: dict[str, Any] = {
        "jobs": {},
        "job_updates": [],
        "resource_requests": [],
        "lease_actions": [],
        "grant_content": grant_buffer.getvalue(),
        "outputs": {},
        "serialize_resources": False,
        "reserved_leases": set(),
        "reject_resources": False,
        "next_job": 0,
        "token_ttl_sec": 600,
        "credential_refreshes": 0,
        "ai_capabilities": {"text.generate": False, "vision.analyze": False},
        "ai_responses": [],
        "ai_calls": [],
        "ai_reserved_lease_snapshots": [],
        "ai_releases": [],
        # 既定は「使用中でなかったので降ろした」。テストごとに書き換える。
        "ai_release_result": {"released": True, "reason": "released", "freed_bytes": 17_000_000_000},
    }

    def subject(authorization: str | None) -> str | None:
        return {
            "Bearer valid-user": "7",
            "Bearer valid-job": "job:host-agent",
            "Bearer valid-workflow": "workflow:42",
            "Bearer valid-context": "context:7",
            "Bearer expired-active": "7",
            "Bearer valid-refreshed": "7",
        }.get(authorization)

    @app.post("/api/v1/addon-runtime/token/introspect")
    async def introspect(
        authorization: str | None = Header(default=None),
        addon_id: str | None = Header(default=None, alias="X-Control-Deck-Addon-ID"),
    ) -> dict[str, Any]:
        token_subject = subject(authorization)
        if token_subject is None or addon_id != "media-forge":
            return {"active": False}
        return {
            "active": True,
            "addon_id": "media-forge",
            "subject": token_subject,
            "expires_at": int(time.time()) + (
                -1 if authorization == "Bearer expired-active"
                else 600 if authorization == "Bearer valid-refreshed"
                else state["token_ttl_sec"]
            ),
            "granted_capabilities": [
                "jobs.write", "resources.acquire", "files.pick", "files.export", "ai.inference",
            ],
        }

    @app.get("/api/v1/addon-runtime/media-forge/ai/capabilities")
    async def ai_capabilities() -> dict[str, dict[str, bool]]:
        return {
            name: {"available": available}
            for name, available in state["ai_capabilities"].items()
        }

    @app.post("/api/v1/addon-runtime/media-forge/ai/complete")
    async def ai_complete(payload: dict[str, Any]) -> dict[str, Any]:
        state["ai_calls"].append(payload)
        state["ai_reserved_lease_snapshots"].append(set(state["reserved_leases"]))
        capability = payload.get("capability")
        if not state["ai_capabilities"].get(capability, False):
            raise HTTPException(status_code=503, detail={"code": "ai_capability_unavailable"})
        if not state["ai_responses"]:
            raise HTTPException(status_code=503, detail={"code": "ai_response_unavailable"})
        return {"capability": capability, "content": state["ai_responses"].pop(0)}

    @app.post("/api/v1/addon-runtime/media-forge/jobs", status_code=201)
    async def create_job(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token_subject = subject(authorization)
        if token_subject == "job:host-agent":
            host_job_id, created = "host-agent", False
        elif token_subject in {"7", "workflow:42"}:
            state["next_job"] += 1
            host_job_id, created = f"host-created-{state['next_job']}", True
        else:
            raise HTTPException(status_code=403)
        state["jobs"].setdefault(host_job_id, {"id": host_job_id, "status": "running"})
        return {"created": created, "job": state["jobs"][host_job_id]}

    @app.patch("/api/v1/addon-runtime/media-forge/jobs/{host_job_id}")
    async def update_job(host_job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        state["job_updates"].append({"job_id": host_job_id, **payload})
        job = state["jobs"].setdefault(host_job_id, {"id": host_job_id, "status": "running"})
        if payload.get("status"):
            job["status"] = payload["status"]
        job.update({"phase": payload["phase"], "progress": payload.get("progress")})
        return job

    @app.get("/api/v1/addon-runtime/media-forge/jobs/{host_job_id}/control")
    async def control(host_job_id: str) -> dict[str, Any]:
        job = state["jobs"].setdefault(host_job_id, {"id": host_job_id, "status": "running"})
        return {"host_job_id": host_job_id, "cancel_requested": job["status"] == "canceled", "status": job["status"], "revision": 1}

    @app.post("/api/v1/addon-runtime/media-forge/ai/release")
    async def ai_release() -> dict[str, Any]:
        if state["ai_release_result"] is None:
            # 旧 Host には明示解放が無い。
            raise HTTPException(status_code=404)
        state["ai_releases"].append({"reserved_leases": sorted(state["reserved_leases"])})
        return state["ai_release_result"]

    @app.post("/api/v1/addon-runtime/media-forge/resources/requests", status_code=202)
    async def request_resource(payload: dict[str, Any]) -> dict[str, Any]:
        if state["reject_resources"]:
            raise HTTPException(status_code=503)
        assert "owner" not in payload
        assert payload["estimated_runtime_sec"] > 0
        assert set(payload["vram"]) == {
            "resident_bytes", "execution_peak_bytes", "cold_load_peak_bytes", "headroom_bytes", "confidence",
        }
        request_id = f"request-{len(state['resource_requests']) + 1}"
        lease_id = f"lease-{request_id}"
        if state["serialize_resources"] and state["reserved_leases"]:
            value = {"request_id": request_id, "state": "waiting", "lease_id": None, "reason": "held_by_other_owner"}
        else:
            value = {"request_id": request_id, "state": "granted", "lease_id": lease_id, "reason": None}
            state["reserved_leases"].add(lease_id)
        state["resource_requests"].append({"payload": payload, **value})
        return value

    @app.get("/api/v1/addon-runtime/media-forge/resources/requests/{request_id}")
    async def resource_status(request_id: str) -> dict[str, Any]:
        return next(item for item in state["resource_requests"] if item["request_id"] == request_id)

    @app.delete("/api/v1/addon-runtime/media-forge/resources/requests/{request_id}")
    async def cancel_resource(request_id: str) -> dict[str, Any]:
        return {"request_id": request_id, "state": "canceled"}

    @app.post("/api/v1/addon-runtime/media-forge/resources/leases/{lease_id}/{action}")
    async def lease_action(lease_id: str, action: str) -> dict[str, Any]:
        state["lease_actions"].append((lease_id, action))
        if action == "release":
            state["reserved_leases"].discard(lease_id)
            waiting = next((item for item in state["resource_requests"] if item["state"] == "waiting"), None)
            if waiting is not None:
                waiting["state"] = "granted"
                waiting["reason"] = None
                waiting["lease_id"] = f"lease-{waiting['request_id']}"
                state["reserved_leases"].add(waiting["lease_id"])
        return {"lease_id": lease_id, "job_id": "host", "device_id": "gpu0", "state": "released" if action == "release" else "active"}

    @app.post("/api/v1/addon-runtime/media-forge/resources/leases/{lease_id}/credential/refresh")
    async def refresh_credential(lease_id: str) -> dict[str, Any]:
        assert lease_id in state["reserved_leases"]
        state["credential_refreshes"] += 1
        return {"access_token": "valid-refreshed", "token_type": "Bearer", "expires_at": int(time.time()) + 600}

    @app.get("/api/v1/addon-runtime/media-forge/grants/grant:read-1")
    async def grant_metadata() -> dict[str, Any]:
        return {"grant_id": "grant:read-1", "kind": "read", "name": "reference.png", "size": len(state["grant_content"])}

    @app.get("/api/v1/addon-runtime/media-forge/grants/grant:read-1/content")
    async def grant_content() -> bytes:
        from fastapi.responses import Response
        return Response(state["grant_content"], media_type="application/octet-stream")

    @app.post("/api/v1/addon-runtime/media-forge/files/outputs", status_code=201)
    async def create_output(payload: dict[str, Any]) -> dict[str, Any]:
        output_id = f"output-{len(state['outputs']) + 1}"
        state["outputs"][output_id] = {"metadata": payload, "content": b""}
        return {"output_id": output_id, "name": payload["filename"], "size": payload["size"], "received": 0}

    @app.put("/api/v1/addon-runtime/media-forge/files/outputs/{output_id}/content")
    async def upload_output(output_id: str, payload: bytes = Body()) -> dict[str, Any]:
        state["outputs"][output_id]["content"] = payload
        return {"output_id": output_id, "received": len(payload)}

    @app.post("/api/v1/addon-runtime/media-forge/files/outputs/{output_id}/commit")
    async def commit_output(output_id: str) -> dict[str, Any]:
        output = state["outputs"][output_id]
        assert len(output["content"]) == output["metadata"]["size"]
        return {"asset_id": "asset:committed", "job_id": output["metadata"]["job_id"], "name": output["metadata"]["filename"]}

    return app, state


def host_client(
    tmp_path: Path,
    *,
    token: str = "valid-job",
    renew_sec: float = 10.0,
    model_download_transport: httpx.AsyncBaseTransport | None = None,
    **settings_overrides: Any,
) -> tuple[TestClient, dict[str, str], dict[str, Any]]:
    host_app, state = control_deck_stub()
    bridge = ControlDeckHostClient(
        "https://control-deck.test",
        transport=httpx.ASGITransport(app=host_app),
    )
    app = create_app(
        fake_settings(
            tmp_path,
            worker_timeout_sec=3,
            control_deck_url="https://control-deck.test",
            host_lease_renew_sec=renew_sec,
            **settings_overrides,
        ),
        host_client=bridge,
        model_download_transport=model_download_transport,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Control-Deck-Addon-ID": "media-forge",
    }
    return TestClient(app), headers, state


def generate_input(intent: str = "host generated robot") -> dict:
    return {
        "operation": "image.generate",
        "intent": intent,
        "constraints": {"width": 48, "height": 32},
        "local_only": True,
    }


@pytest.mark.parametrize(
    "origin",
    [
        "http://control-deck.example",
        "http://127.0.0.1:8765/api/v1",
        "https://user:password@control-deck.example",
        "file:///data1tb/ControlDeck",
    ],
)
def test_control_deck_origin_rejects_unscoped_or_insecure_urls(tmp_path: Path, origin: str):
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, control_deck_url=origin)


def test_host_execution_requires_valid_audience_bound_token(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
    with client:
        assert client.post("/addon/v1/agent/capabilities", json={}).status_code == 401
        wrong = dict(headers)
        wrong["X-Control-Deck-Addon-ID"] = "another-addon"
        assert client.post("/addon/v1/agent/capabilities", json={}, headers=wrong).status_code == 401
        expired = dict(headers)
        expired["Authorization"] = "Bearer expired-active"
        assert client.post("/addon/v1/agent/capabilities", json={}, headers=expired).status_code == 401
        assert client.post("/addon/v1/agent/capabilities", json={}, headers=headers).status_code == 200


def test_agent_capabilities_never_disclose_model_names(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
    with client:
        response = client.post("/addon/v1/agent/capabilities", json={"input": {}}, headers=headers)
    serialized = json.dumps(response.json()).lower()
    assert response.status_code == 200
    assert "fake-image" not in serialized and "flux" not in serialized and "qwen" not in serialized


def test_agent_inspect_does_not_disclose_model_identity(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
    with client:
        created = client.post("/api/v1/jobs", json=generate_input("inspect robot")).json()
        terminal = wait_terminal(client, created["id"])
        response = client.post(
            "/addon/v1/agent/inspect",
            json={"input": {"asset_id": terminal["asset_ids"][0]}, "correlation": {"job_id": "host-inspect"}},
            headers=headers,
        )
    serialized = json.dumps(response.json()).lower()
    assert response.status_code == 200
    assert "model_id" not in serialized and "fake-image" not in serialized
    assert response.json()["provenance"]["license"] == "CC0-1.0"


def test_agent_pack_atomically_places_one_asset_through_an_opaque_grant(tmp_path: Path):
    client, headers, state = host_client(tmp_path)
    with client:
        created = client.post("/api/v1/jobs", json=generate_input("project robot")).json()
        terminal = wait_terminal(client, created["id"])
        media_asset_id = terminal["asset_ids"][0]
        asset = client.get(f"/api/v1/assets/{media_asset_id}").json()
        response = client.post(
            "/addon/v1/agent/pack",
            json={"input": {
                "asset_id": media_asset_id,
                "output_grant_id": "grant:export-1",
                "filename": "robot-player.png",
            }, "correlation": {"job_id": "host-agent"}},
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "asset_id": "asset:committed",
        "media_asset_id": media_asset_id,
        "name": "robot-player.png",
        "mime_type": "image/png",
        "size": asset["size_bytes"],
        "sha256": asset["sha256"],
    }
    output = state["outputs"]["output-1"]
    assert output["metadata"] == {
        "job_id": "host-agent",
        "grant_id": "grant:export-1",
        "filename": "robot-player.png",
        "size": asset["size_bytes"],
        "sha256": asset["sha256"],
        "content_type": "image/png",
    }
    assert hashlib.sha256(output["content"]).hexdigest() == asset["sha256"]
    serialized = json.dumps(response.json())
    assert str(tmp_path) not in serialized and "model" not in serialized and "path" not in serialized


@pytest.mark.parametrize(
    ("patch", "expected_code"),
    [
        ({"output_grant_id": "/tmp/project"}, "unscoped_host_path"),
        ({"output_grant_id": "not-a-grant"}, "invalid_project_asset_placement"),
        ({"filename": "../outside.png"}, "invalid_project_asset_placement"),
        ({"filename": "wrong.jpg"}, "asset_placement_rejected"),
    ],
)
def test_agent_pack_rejects_paths_invalid_grants_and_mismatched_types(
    tmp_path: Path, patch: dict[str, str], expected_code: str,
):
    client, headers, state = host_client(tmp_path)
    with client:
        created = client.post("/api/v1/jobs", json=generate_input("bounded robot")).json()
        terminal = wait_terminal(client, created["id"])
        payload = {
            "asset_id": terminal["asset_ids"][0],
            "output_grant_id": "grant:export-1",
            "filename": "robot.png",
            **patch,
        }
        response = client.post(
            "/addon/v1/agent/pack",
            json={"input": payload, "correlation": {"job_id": "host-agent"}},
            headers=headers,
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == expected_code
    assert state["outputs"] == {}


def test_agent_pack_requires_the_token_bound_host_job(tmp_path: Path):
    client, headers, state = host_client(tmp_path)
    with client:
        created = client.post("/api/v1/jobs", json=generate_input("scoped robot")).json()
        terminal = wait_terminal(client, created["id"])
        response = client.post(
            "/addon/v1/agent/pack",
            json={"input": {
                "asset_id": terminal["asset_ids"][0],
                "output_grant_id": "grant:export-1",
            }, "correlation": {"job_id": "another-job"}},
            headers=headers,
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "host_job_scope_mismatch"
    assert state["outputs"] == {}


def test_workflow_and_agent_generate_return_opaque_references(tmp_path: Path):
    client, headers, state = host_client(tmp_path)
    with client:
        workflow_headers = {**headers, "Authorization": "Bearer valid-workflow"}
        workflow = client.post(
            "/addon/v1/workflow/execute",
            json={"input": generate_input(), "correlation": {"execution_id": "7", "node_id": "n1"}},
            headers=workflow_headers,
        )
        assert workflow.status_code == 200
        assert workflow.json()["job_id"].startswith("job_")
        assert wait_terminal(client, workflow.json()["job_id"])["status"] == "succeeded"
        assert state["resource_requests"][0]["payload"]["class"] == "workflow"

        agent = client.post(
            "/addon/v1/agent/generate",
            json={"input": generate_input("agent robot"), "correlation": {"job_id": "host-job"}},
            headers=headers,
        )
        assert agent.status_code == 200
        assert agent.json()["job_id"].startswith("job_")
        assert agent.json()["asset_id"].startswith("asset_")
        assert state["resource_requests"][-1]["payload"]["job_id"] == "host-agent"
        assert [action for _lease, action in state["lease_actions"]] == [
            "activate", "release", "activate", "release",
        ]
        attached_updates = [update for update in state["job_updates"] if update["job_id"] == "host-agent"]
        assert not any(update.get("status") for update in attached_updates)


def test_semantic_evaluation_runs_after_generation_lease_release(tmp_path: Path):
    client, headers, state = host_client(tmp_path)
    state["ai_capabilities"]["vision.analyze"] = True
    scores = {
        "intent": 0.9,
        "subject_identity": None,
        "action_state": None,
        "palette": None,
        "composition": None,
        "style": None,
        "props_clothing": None,
        "visual_integrity": 0.9,
    }
    state["ai_responses"].append(json.dumps({
        "scores": scores,
        "issues": [],
        "strengths": ["clear match"],
        "retry_suggestions": [],
    }))
    payload = generate_input("semantic lease handoff robot")
    payload["qa"] = {
        "deterministic": True,
        "semantic": True,
        "max_regeneration_attempts": 0,
    }

    with client:
        response = client.post(
            "/addon/v1/agent/generate",
            json={"input": payload, "correlation": {"job_id": "host-agent"}},
            headers=headers,
        )

    assert response.status_code == 200, response.text
    assert len(state["ai_calls"]) == 1
    assert state["ai_calls"][0]["capability"] == "vision.analyze"
    assert state["ai_reserved_lease_snapshots"] == [set()]
    assert [action for _lease, action in state["lease_actions"]].count("release") == 1


def test_host_payload_rejects_raw_paths_and_context_requires_grant(tmp_path: Path):
    client, headers, _state = host_client(tmp_path)
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
            json={"input": {}, "context": {
                "type": "file", "resource_id": "grant:read-1", "grant_id": "grant:read-1",
            }},
            headers=headers,
        )
        assert accepted.status_code == 200
        assert accepted.json()["action"] == "open_route"
        assert "grant_id" not in json.dumps(accepted.json())
        assert accepted.json()["context"]["source"] == {
            "name": "reference.png", "size": len(_state["grant_content"]),
            "width": 3, "height": 2, "mode": "RGBA",
        }
        _state["grant_content"] = b"not-an-image"
        invalid_image = client.post(
            "/addon/v1/context/edit-image",
            json={"input": {}, "context": {
                "type": "file", "resource_id": "grant:read-1", "grant_id": "grant:read-1",
            }},
            headers=headers,
        )
        assert invalid_image.status_code == 422
        assert invalid_image.json()["detail"]["code"] == "invalid_context_image"


def test_context_image_bound_is_enforced_before_content_transfer(tmp_path: Path, monkeypatch):
    client, headers, state = host_client(tmp_path)
    monkeypatch.setattr(mediaforge_app, "MAX_CONTEXT_IMAGE_BYTES", len(state["grant_content"]) - 1)
    with client:
        response = client.post(
            "/addon/v1/context/edit-image",
            json={"input": {}, "context": {
                "type": "file", "resource_id": "grant:read-1", "grant_id": "grant:read-1",
            }},
            headers=headers,
        )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "context_image_too_large"


def test_workspace_uses_host_bridge_without_browser_storage(tmp_path: Path):
    client, _headers, _state = host_client(tmp_path)
    with client:
        index = client.get("/")
        script = client.get("/static/app.js")
    assert index.status_code == 200 and 'data-bridge="waiting"' in index.text
    assert "MEDIA_FORGE_INLINE_STYLE" not in index.text
    assert "MEDIA_FORGE_INLINE_SCRIPT" not in index.text
    assert "control-deck-addon.connect" in index.text
    assert script.status_code == 200
    assert "control-deck-addon.connect" in script.text
    assert "theme.changed" in script.text and "route.sync" in script.text and "disable.pending" in script.text
    assert "localStorage" not in script.text and "sessionStorage" not in script.text and "document.cookie" not in script.text


def test_workspace_embeds_creative_catalog_and_standalone_validation_is_private(tmp_path: Path):
    client, _headers, _state = host_client(tmp_path)
    request = generate_input("directed robot")
    with client:
        index = client.get("/")
        compiled = client.post("/workspace-api/creative/validate", json={
            "request": request,
            "creative_spec": {"domain": "anime", "pose": {"preset": "wave"}},
        })
        rejected = client.post("/workspace-api/creative/validate", json={
            "request": request,
            "creative_spec": {
                "scene": {"preset": "coding_at_desk"},
                "pose": {"preset": "wave"},
            },
        })
        openapi = client.get("/openapi.json").json()

    assert index.status_code == 200
    assert 'id="creative-template-data"' in index.text
    assert 'id="workspace-config-data"' in index.text
    assert '"max_reference_assets":4' in index.text
    assert '"catalog_version":"2026.08.22"' in index.text
    assert compiled.status_code == 200
    assert compiled.json()["request"]["model_id"] is None
    assert compiled.json()["request"]["constraints"]["creative_plan"]["domain"]["id"] == "anime"
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "creative_combination_invalid"
    assert "/workspace-api/creative/validate" not in openapi["paths"]


def test_workspace_response_delay_is_bounded_and_test_only(monkeypatch):
    from mediaforge.app import workspace_test_response_delay_sec

    monkeypatch.setenv("MEDIA_FORGE_TEST_WORKSPACE_DELAY_SEC", "10")
    assert workspace_test_response_delay_sec() == 0.0
    monkeypatch.setenv("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS", "1")
    assert workspace_test_response_delay_sec() == 2.0
    monkeypatch.setenv("MEDIA_FORGE_TEST_WORKSPACE_DELAY_SEC", "invalid")
    assert workspace_test_response_delay_sec() == 0.0


def test_workspace_websocket_uses_host_token_and_structured_asset_transport(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    with client:
        try:
            with client.websocket_connect("/ws"):
                pass
        except Exception:
            pass
        else:
            raise AssertionError("workspace WebSocket accepted a request without a host token")

        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({"id": "path", "method": "assets.list", "params": {"path": "/tmp/escape"}})
            rejected = socket.receive_json()
            assert rejected["ok"] is False
            assert rejected["error"]["code"] == "unscoped_host_path"

            socket.send_json({"id": "create", "method": "jobs.create", "params": generate_input("socket robot")})
            created = socket.receive_json()
            assert created["ok"] is True
            job_id = created["result"]["id"]

            deadline = time.monotonic() + 5
            terminal = None
            while time.monotonic() < deadline:
                socket.send_json({"id": "get", "method": "jobs.get", "params": {"job_id": job_id}})
                terminal = socket.receive_json()["result"]
                if terminal["status"] in {"succeeded", "failed", "canceled"}:
                    break
                time.sleep(0.02)
            assert terminal is not None and terminal["status"] == "succeeded"

            asset_id = terminal["asset_ids"][0]
            socket.send_json({"id": "content", "method": "assets.content", "params": {"asset_id": asset_id}})
            content = socket.receive_json()
            assert content["ok"] is True
            assert base64.b64decode(content["result"]["base64"]).startswith(b"\x89PNG")
    assert state["resource_requests"][0]["payload"]["job_id"] == "host-created-1"
    assert any(update.get("status") == "succeeded" for update in state["job_updates"])


def test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_up(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    image = Image.frombytes("RGBA", (512, 512), os.urandom(512 * 512 * 4))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    content = buffer.getvalue()
    assert len(content) > 1024 * 1024

    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({
                "id": "begin",
                "method": "assets.import.begin",
                "params": {"purpose": "source", "size": len(content)},
            })
            upload = socket.receive_json()["result"]
            for offset in range(0, len(content), upload["chunk_bytes"]):
                chunk = content[offset:offset + upload["chunk_bytes"]]
                socket.send_json({
                    "id": f"chunk-{offset}",
                    "method": "assets.import.chunk",
                    "params": {
                        "upload_id": upload["upload_id"],
                        "offset": offset,
                        "base64": base64.b64encode(chunk).decode("ascii"),
                    },
                })
                assert socket.receive_json()["result"]["received"] == offset + len(chunk)
            socket.send_json({
                "id": "commit",
                "method": "assets.import.commit",
                "params": {"upload_id": upload["upload_id"]},
            })
            imported = socket.receive_json()
            assert imported["ok"] is True
            assert imported["result"]["width"] == 512
            assert imported["result"]["height"] == 512

        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({
                "id": "orphan",
                "method": "assets.import.begin",
                "params": {"purpose": "edit_mask", "size": 100},
            })
            orphan = socket.receive_json()["result"]
            socket.send_json({
                "id": "incomplete",
                "method": "assets.import.commit",
                "params": {"upload_id": orphan["upload_id"]},
            })
            rejected = socket.receive_json()
            assert rejected["ok"] is False
            assert "incomplete" in rejected["error"]["message"]

        assert list(client.app.state.store.work_dir.iterdir()) == []


def test_scoped_file_bridge_reads_and_commits_without_host_paths(tmp_path: Path):
    host_app, state = control_deck_stub()
    bridge = ControlDeckHostClient(
        "https://control-deck.test",
        transport=httpx.ASGITransport(app=host_app),
    )
    source = tmp_path / "result.png"
    source.write_bytes(b"generated-output")

    async def scenario() -> None:
        identity = await bridge.authenticate({
            "Authorization": "Bearer valid-user",
            "X-Control-Deck-Addon-ID": "media-forge",
        })
        metadata, content = await read_grant(bridge, identity, "grant:read-1")
        assert metadata["name"] == "reference.png"
        assert content == state["grant_content"]
        committed = await commit_file(
            bridge,
            identity,
            host_job_id="host-created-1",
            grant_id="grant:export-1",
            source=source,
            filename="result.png",
            mime_type="image/png",
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        assert committed["asset_id"] == "asset:committed"
        await bridge.close()

    asyncio.run(scenario())
    serialized = json.dumps(state["outputs"], default=lambda value: f"<{len(value)} bytes>")
    assert str(tmp_path) not in serialized and "path" not in serialized


def test_grant_content_stream_is_bounded(monkeypatch):
    host_app, _ = control_deck_stub()
    bridge = ControlDeckHostClient(
        "https://control-deck.test",
        transport=httpx.ASGITransport(app=host_app),
    )
    monkeypatch.setattr(host_client_module, "MAX_GRANT_BYTES", 4)

    async def scenario() -> None:
        identity = await bridge.authenticate({
            "Authorization": "Bearer valid-user",
            "X-Control-Deck-Addon-ID": "media-forge",
        })
        try:
            await bridge.grant_content(identity, "grant:read-1")
        except HostApiError as exc:
            assert exc.code == "host_response_too_large"
        else:
            raise AssertionError("oversized grant response was accepted")
        await bridge.close()

    asyncio.run(scenario())


def test_real_test_endpoint_exercises_scoped_file_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS", "1")
    client, headers, state = host_client(tmp_path, token="valid-user")
    with client:
        response = client.post(
            "/test/host-files/roundtrip",
            json={
                "read_grant_id": "grant:read-1",
                "export_grant_id": "grant:export-1",
                "filename": "roundtrip.bin",
            },
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert response.json()["output"]["asset_id"] == "asset:committed"
    assert state["outputs"]["output-1"]["content"] == state["grant_content"]
    assert any(update.get("status") == "succeeded" for update in state["job_updates"])


def test_scoped_file_roundtrip_endpoint_is_hidden_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS", raising=False)
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client:
        response = client.post(
            "/test/host-files/roundtrip",
            json={
                "read_grant_id": "grant:read-1",
                "export_grant_id": "grant:export-1",
                "filename": "roundtrip.bin",
            },
            headers=headers,
        )
    assert response.status_code == 404


def test_hosted_jobs_wait_outside_worker_guard_renew_and_release(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user", renew_sec=0.05)
    state["serialize_resources"] = True
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({
                "id": "first",
                "method": "jobs.create",
                "params": generate_input("first serialized") | {"constraints": {"_fake_delay_sec": 0.3}},
            })
            first = socket.receive_json()["result"]
            socket.send_json({
                "id": "second",
                "method": "jobs.create",
                "params": generate_input("second serialized") | {"constraints": {"_fake_delay_sec": 0.1}},
            })
            second = socket.receive_json()["result"]

            deadline = time.monotonic() + 3
            observed_waiting = False
            while time.monotonic() < deadline:
                first_job = client.app.state.store.get_job(first["id"])
                second_job = client.app.state.store.get_job(second["id"])
                if first_job.status == "running" and second_job.phase == "waiting_resource":
                    observed_waiting = True
                    assert len(client.app.state.jobs._processes) == 1
                    break
                time.sleep(0.01)
            assert observed_waiting
            assert wait_terminal(client, first["id"])["status"] == "succeeded"
            assert wait_terminal(client, second["id"])["status"] == "succeeded"

        deadline = time.monotonic() + 2
        while len([action for _lease, action in state["lease_actions"] if action == "release"]) < 2:
            assert time.monotonic() < deadline
            time.sleep(0.01)

    actions = [action for _lease, action in state["lease_actions"]]
    assert actions.count("activate") == 2
    assert actions.count("release") == 2
    assert "renew" in actions


def test_long_hosted_job_refreshes_scoped_identity_before_expiry(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user", renew_sec=0.05)
    state["token_ttl_sec"] = 1
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({
                "id": "refresh",
                "method": "jobs.create",
                "params": generate_input("refresh credential") | {"constraints": {"_fake_delay_sec": 0.3}},
            })
            created = socket.receive_json()["result"]
            assert wait_terminal(client, created["id"])["status"] == "succeeded"

    assert state["credential_refreshes"] == 1
    assert "renew" in [action for _lease, action in state["lease_actions"]]


def test_host_cancel_stops_worker_and_releases_lease(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({
                "id": "create",
                "method": "jobs.create",
                "params": generate_input("host canceled") | {"constraints": {"_fake_delay_sec": 1}},
            })
            created = socket.receive_json()["result"]
            deadline = time.monotonic() + 2
            while not client.app.state.jobs._processes:
                assert time.monotonic() < deadline
                time.sleep(0.01)
            state["jobs"]["host-created-1"]["status"] = "canceled"
            terminal = wait_terminal(client, created["id"])
            assert terminal["status"] == "canceled"

        deadline = time.monotonic() + 2
        while not any(action == "release" for _lease, action in state["lease_actions"]):
            assert time.monotonic() < deadline
            time.sleep(0.01)
    assert not any(update.get("status") == "canceled" for update in state["job_updates"])


def test_service_stop_fails_hosted_job_and_releases_lease(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({
                "id": "stop",
                "method": "jobs.create",
                "params": generate_input("stop hosted") | {"constraints": {"_fake_delay_sec": 2}},
            })
            job_id = socket.receive_json()["result"]["id"]
            deadline = time.monotonic() + 2
            while not any(action == "activate" for _lease, action in state["lease_actions"]):
                assert time.monotonic() < deadline
                time.sleep(0.01)

    stopped = Store(tmp_path / "data").get_job(job_id)
    assert stopped.status == "failed"
    assert stopped.error is not None and stopped.error.code == "service_stopped"
    assert any(action == "release" for _lease, action in state["lease_actions"])


def test_host_resource_rejection_fails_before_worker_start(tmp_path: Path):
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["reject_resources"] = True
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({"id": "create", "method": "jobs.create", "params": generate_input("rejected")})
            created = socket.receive_json()["result"]
            terminal = wait_terminal(client, created["id"])
            assert terminal["status"] == "failed"
            assert terminal["error"]["code"] == "host_request_rejected"
            assert client.app.state.jobs._processes == {}
    assert state["lease_actions"] == []
