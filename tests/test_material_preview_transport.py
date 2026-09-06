from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any

import pytest

from mediaforge.material_binding import MaterialBinding
from test_host_execution import host_client
from test_scene_workspace import fake_scene_workspace, register_image, upload_scene
from test_workspace_transport import call


PREFIX = "scenes.material.preview."


def configure(client: Any, root: Path) -> tuple[Any, str, dict[str, Any]]:
    _, fake, resolver = fake_scene_workspace(root / "worker")
    workspace = client.app.state.scene_workspace
    workspace.resolver = resolver
    workspace.worker = fake.worker
    workspace.material_worker = fake.material_worker
    imported = upload_scene(workspace, b"BLENDER-preview-transport", owner="user:7")
    image = register_image(workspace.store, root)
    binding = MaterialBinding(source_revision_id=imported["revision"]["id"], image_asset_id=image.id,
                              object_name="Cube", material_slot=0, channel="base_color", uv_map="UVMap")
    return workspace, imported["scene"]["id"], binding.model_dump(mode="json")


def test_preview_ws_adoption_is_connection_scoped_and_immutable(tmp_path: Path) -> None:
    client, headers, _ = host_client(tmp_path / "app", token="valid-user")
    with client:
        workspace, scene_id, binding = configure(client, tmp_path)
        before = workspace.catalog.get("user:7", scene_id)
        with client.websocket_connect("/ws", headers=headers) as first:
            prepared = call(first, PREFIX + "prepare", {"scene_id": scene_id, "binding": binding})
            assert prepared["ok"], prepared
            candidate = prepared["result"]["candidate_id"]
            assert workspace.catalog.get("user:7", scene_id) == before
            with client.websocket_connect("/ws", headers=headers) as second:
                rejected = call(second, PREFIX + "adopt", {"candidate_id": candidate})
                assert not rejected["ok"]
                assert rejected["error"]["code"] == "scene_material_preview_unavailable"
            preview = call(first, PREFIX + "read", {"candidate_id": candidate, "offset": 0, "length": 524288})
            assert preview["ok"]
            adopted = call(first, PREFIX + "adopt", {"candidate_id": candidate})
            assert adopted["ok"], adopted
            assert adopted["result"]["revision"]["sequence"] == 2
            assert call(first, PREFIX + "adopt", {"candidate_id": candidate}) == adopted
        assert workspace.resolver.references == 0
        assert list(client.app.state.material_previews.root.iterdir()) == []


def test_ws_disconnect_cancels_prepare_and_does_not_block_other_methods(tmp_path: Path) -> None:
    client, headers, _ = host_client(tmp_path / "app", token="valid-user")
    started, canceled = threading.Event(), threading.Event()
    with client:
        workspace, scene_id, binding = configure(client, tmp_path)
        before = workspace.catalog.get("user:7", scene_id)

        async def wait(*args: Any, **kwargs: Any) -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                canceled.set()

        workspace._material_operation = wait
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({"id": "prepare", "method": PREFIX + "prepare",
                              "params": {"scene_id": scene_id, "binding": binding}})
            assert started.wait(3)
            assert call(socket, "jobs.list")["ok"]
            busy = call(socket, PREFIX + "prepare", {"scene_id": scene_id, "binding": binding})
            assert busy["error"]["code"] == "scene_material_preview_busy"
            # Send an actual disconnect and observe cleanup before TestClient's
            # context exit forcibly cancels its ASGI task group.
            socket.close()
            assert canceled.wait(3)

            async def cleaned() -> None:
                async with asyncio.timeout(3):
                    while workspace.resolver.references or list(client.app.state.material_previews.root.iterdir()):
                        await asyncio.sleep(0.01)

            client.portal.call(cleaned)
        assert canceled.wait(3)
        assert workspace.catalog.get("user:7", scene_id) == before
    assert workspace.resolver.references == 0
    assert list(client.app.state.material_previews.root.iterdir()) == []


def test_ws_disconnect_discards_ready_preview_and_shutdown_releases_pin(tmp_path: Path) -> None:
    client, headers, _ = host_client(tmp_path / "app", token="valid-user")
    with client:
        workspace, scene_id, binding = configure(client, tmp_path)
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, PREFIX + "prepare", {"scene_id": scene_id, "binding": binding})
            assert answer["ok"]
            assert workspace.resolver.references == 1
        # The socket context waits for the server's disconnect cleanup.
        assert workspace.resolver.references == 0
        assert list(client.app.state.material_previews.root.iterdir()) == []
        # Independently cover app shutdown of a candidate without a socket.
        client.portal.call(client.app.state.material_previews.prepare, "user:7", "shutdown", scene_id, binding)
        assert workspace.resolver.references == 1
    assert workspace.resolver.references == 0


@pytest.mark.parametrize("method", ["prepare", "read", "adopt", "discard", "unknown"])
def test_preview_transport_rejects_paths_and_client_connection_fields(tmp_path: Path, method: str) -> None:
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        result = call(socket, PREFIX + method, {"path": "/etc/passwd"})
        assert result["error"]["code"] == "unscoped_host_path"
        result = call(socket, PREFIX + method, {"connection": "chosen-by-client"})
        assert result["error"]["code"] == "scene_material_preview_request"
