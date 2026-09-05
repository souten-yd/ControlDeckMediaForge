from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from conftest import fake_settings
from mediaforge.app import create_app
from mediaforge.host.client import HostIdentity


class Host:
    def __init__(self) -> None:
        self.authentication_count = 0
        self.children = 0
        self.updates: list[dict[str, Any]] = []

    async def authenticate(self, headers: object) -> HostIdentity:
        self.authentication_count += 1
        return HostIdentity(
            authorization=f"Bearer parent-{self.authentication_count}",
            addon_id="media-forge",
            subject=f"job:tool-call-{self.authentication_count}",
            actor_subject="user:7",
            expires_at=int(time.time()) + 600,
            granted_capabilities=frozenset({"jobs.write"}),
        )

    async def create_or_attach_job(
        self, identity: HostIdentity, *, title: str, detached: bool = False
    ) -> dict[str, Any]:
        assert detached is True
        self.children += 1
        return {
            "created": True,
            "job": {"id": f"child-{self.children}"},
            "access_token": f"child-token-{self.children}",
            "expires_at": int(time.time()) + 600,
        }

    async def update_job(
        self, identity: HostIdentity, host_job_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        assert identity.subject == f"job:{host_job_id}"
        self.updates.append(payload)
        return payload

    async def job_control(
        self, identity: HostIdentity, host_job_id: str
    ) -> dict[str, Any]:
        return {"cancel_requested": False}

    async def refresh_job_credential(
        self, identity: HostIdentity, host_job_id: str
    ) -> dict[str, Any]:
        return {"access_token": "refreshed", "expires_at": int(time.time()) + 600}

    async def close(self) -> None:
        return None


def test_scene_agent_returns_detached_job_and_status_uses_stable_actor(
    tmp_path: Path,
) -> None:
    host = Host()
    app = create_app(fake_settings(tmp_path), host_client=host)  # type: ignore[arg-type]
    scene_id = "scene_" + "1" * 32
    revision_id = "revision_" + "2" * 32

    app.state.scene_workspace.recipe_runtime_pin = lambda owner, value: (
        "blender-test",
        "4.5.9",
        None,
    )

    async def apply_recipe(
        owner: str,
        job_id: str,
        value: object,
        *,
        runtime_id: str,
        runtime_version: str,
    ) -> dict[str, Any]:
        assert owner == "user:7"
        await asyncio.sleep(0.02)
        return {
            "scene": {"id": scene_id},
            "revision": {"id": revision_id},
            "asset_ids": ["asset_" + "3" * 32, "asset_" + "4" * 32],
            "recipe": {"operation_count": 1},
        }

    app.state.scene_workspace.apply_recipe = apply_recipe
    headers = {
        "Authorization": "Bearer request",
        "X-Control-Deck-Addon-ID": "media-forge",
    }
    payload = {
        "input": {
            "name": "Agent cube",
            "recipe": {
                "operations": [{
                    "type": "primitive.add",
                    "object_id": "cube",
                    "primitive": "cube",
                    "name": "Cube",
                    "dimensions": [1, 1, 1],
                }]
            },
        }
    }
    with TestClient(app) as client:
        submitted = client.post(
            "/addon/v1/agent/scene/create", json=payload, headers=headers
        )
        assert submitted.status_code == 200, submitted.text
        body = submitted.json()
        assert body["status"] == "queued"
        assert body["detached"] is True
        assert body["host_job_id"] == "child-1"
        deadline = time.monotonic() + 5
        while True:
            status = client.post(
                "/addon/v1/agent/job/status",
                json={"input": {"job_id": body["job_id"]}},
                headers=headers,
            )
            assert status.status_code == 200, status.text
            if (
                status.json()["status"] == "succeeded"
                and status.json()["host_terminal_sent"] is True
            ):
                break
            assert time.monotonic() < deadline
            time.sleep(0.02)
        result = status.json()
        assert result["operation"] == "scene.create"
        assert result["result"]["scene"]["id"] == scene_id
        assert result["host_terminal_sent"] is True
        assert host.authentication_count >= 2


def test_scene_agent_schema_rejects_arbitrary_script_before_host_job(tmp_path: Path) -> None:
    host = Host()
    app = create_app(fake_settings(tmp_path), host_client=host)  # type: ignore[arg-type]
    with TestClient(app) as client:
        response = client.post(
            "/addon/v1/agent/scene/create",
            json={"input": {
                "name": "Unsafe",
                "recipe": {"operations": [{"type": "python.exec", "code": "import os"}]},
            }},
            headers={
                "Authorization": "Bearer request",
                "X-Control-Deck-Addon-ID": "media-forge",
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_scene_recipe"
    assert host.children == 0


def test_scene_read_tools_reject_extra_fields_from_the_runtime_payload(
    tmp_path: Path,
) -> None:
    host = Host()
    app = create_app(fake_settings(tmp_path), host_client=host)  # type: ignore[arg-type]
    headers = {
        "Authorization": "Bearer request",
        "X-Control-Deck-Addon-ID": "media-forge",
    }
    cases = (
        ("/addon/v1/agent/scene/snapshot", {"scene_id": "scene_" + "1" * 32}),
        ("/addon/v1/agent/scene/export", {"scene_id": "scene_" + "1" * 32}),
        ("/addon/v1/agent/job/status", {"job_id": "job_" + "1" * 32}),
        ("/addon/v1/agent/job/cancel", {"job_id": "job_" + "1" * 32}),
    )
    with TestClient(app) as client:
        for endpoint, value in cases:
            response = client.post(
                endpoint,
                json={"input": {**value, "unexpected": True}},
                headers=headers,
            )
            assert response.status_code == 422, (endpoint, response.text)
