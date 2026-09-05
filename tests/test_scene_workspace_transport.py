from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from mediaforge.scene_workspace import BLEND_CHUNK_BYTES
from test_host_execution import host_client
from test_scene_workspace import fake_scene_workspace
from test_workspace_transport import call


def test_authenticated_workspace_transport_imports_and_locks_without_paths(tmp_path: Path) -> None:
    _store, fixture_workspace, resolver = fake_scene_workspace(tmp_path / "fixture")
    client, headers, _state = host_client(tmp_path / "app", token="valid-user")
    content = b"BLENDER" + b"transport-scene" * 20
    digest = hashlib.sha256(content).hexdigest()
    with client:
        workspace = client.app.state.scene_workspace
        workspace.resolver = resolver
        workspace.worker = fixture_workspace.worker
        with client.websocket_connect("/ws", headers=headers) as socket:
            begun = call(
                socket,
                "scenes.import.begin",
                {"size": len(content), "sha256": digest, "name": "Transport scene"},
            )
            upload_id = begun["result"]["upload_id"]
            chunked = call(
                socket,
                "scenes.import.chunk",
                {
                    "upload_id": upload_id,
                    "offset": 0,
                    "sha256": digest,
                    "base64": base64.b64encode(content).decode("ascii"),
                },
            )
            imported = call(socket, "scenes.import.commit", {"upload_id": upload_id})
            scene_id = imported["result"]["scene"]["id"]
            acquired = call(socket, "scenes.working.acquire", {"scene_id": scene_id})
            working_id = acquired["result"]["id"]
            locked = call(socket, "scenes.working.acquire", {"scene_id": scene_id})
            renewed = call(socket, "scenes.working.renew", {"working_id": working_id})
            committed = call(socket, "scenes.working.commit", {"working_id": working_id})
        with client.websocket_connect("/ws", headers=headers) as abandoned_socket:
            abandoned = call(
                abandoned_socket,
                "scenes.import.begin",
                {"size": len(content), "sha256": digest, "name": "Abandoned scene"},
            )
        with client.websocket_connect("/ws", headers=headers) as resumed_socket:
            resumed = call(
                resumed_socket,
                "scenes.import.begin",
                {"size": len(content), "sha256": digest, "name": "Resumed scene"},
            )
            canceled = call(
                resumed_socket,
                "scenes.import.cancel",
                {"upload_id": resumed["result"]["upload_id"]},
            )

    assert begun["ok"] is True and begun["result"]["chunk_bytes"] == BLEND_CHUNK_BYTES
    assert chunked["result"]["received"] == len(content)
    assert imported["ok"] is True and "path" not in json.dumps(imported)
    assert acquired["ok"] is True and "path" not in json.dumps(acquired)
    assert locked["ok"] is False and locked["error"]["code"] == "scene_working_locked"
    assert renewed["ok"] is True
    assert committed["ok"] is True and committed["result"]["revision"]["sequence"] == 2
    assert abandoned["ok"] is True and resumed["ok"] is True
    assert canceled["result"] == {"canceled": True}


def test_standalone_scene_transport_uses_the_same_bounded_domain_service(tmp_path: Path) -> None:
    _store, fixture_workspace, resolver = fake_scene_workspace(tmp_path / "fixture")
    client, _headers, _state = host_client(tmp_path / "app")
    content = b"BLENDER-standalone"
    digest = hashlib.sha256(content).hexdigest()
    with client:
        workspace = client.app.state.scene_workspace
        workspace.resolver = resolver
        workspace.worker = fixture_workspace.worker
        begun = client.post(
            "/workspace-api/scenes/import/begin",
            json={"size": len(content), "sha256": digest, "name": "Standalone scene"},
        )
        assert begun.status_code == 200
        upload_id = begun.json()["upload_id"]
        chunked = client.post(
            "/workspace-api/scenes/import/chunk",
            json={
                "upload_id": upload_id,
                "offset": 0,
                "sha256": digest,
                "base64": base64.b64encode(content).decode("ascii"),
            },
        )
        imported = client.post(
            "/workspace-api/scenes/import/commit", json={"upload_id": upload_id}
        )
        scene_id = imported.json()["scene"]["id"]
        working = client.post(f"/workspace-api/scenes/{scene_id}/working")
        released = client.post(
            f"/workspace-api/scenes/working/{working.json()['id']}",
            json={"action": "release"},
        )
        injected = client.post(
            "/workspace-api/scenes/import/begin",
            json={
                "size": len(content),
                "sha256": digest,
                "name": "Injected",
                "path": "/tmp/scene.blend",
            },
        )

    assert chunked.status_code == 200 and chunked.json()["received"] == len(content)
    assert imported.status_code == 200 and "path" not in imported.text
    assert working.status_code == 200 and "path" not in working.text
    assert released.status_code == 200 and released.json()["state"] == "released"
    assert injected.status_code == 422 and injected.json()["detail"]["code"] == "unscoped_host_path"
