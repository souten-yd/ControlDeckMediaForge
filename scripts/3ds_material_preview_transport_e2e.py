"""Real TCP WebSocket + Blender acceptance with an explicit fixture identity.

PYTHONPATH=backend:. core Python. Creates a NEW isolated data directory and a
loopback ephemeral Uvicorn server. Does not test installed Host authentication.
"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import socket
import time
from typing import Any

import uvicorn
import websockets

from mediaforge.app import create_app
from mediaforge.config import Settings
from mediaforge.host.client import ControlDeckHostClient, HostApiError, HostIdentity


class FixtureHost(ControlDeckHostClient):
    async def authenticate(self, headers: Mapping[str, str]) -> HostIdentity:
        if headers.get("authorization") != "Bearer preview-fixture":
            raise HostApiError("invalid_fixture", "fixture token required", status_code=401)
        return HostIdentity("Bearer preview-fixture", "media-forge", "local",
                            int(time.time()) + 600, frozenset(), actor_subject="local")


async def run(args: argparse.Namespace) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("preview_core", Path(__file__).with_name("3ds_material_preview_core_e2e.py"))
    assert spec and spec.loader
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    core = await fixture.run(args)
    host = FixtureHost("http://127.0.0.1:1")
    app = create_app(Settings(data_dir=args.data_dir, blender_legacy_runtime_root=args.legacy_runtime_root), host_client=host)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    evidence: dict[str, Any] = {"authentication": "fixture-only; not installed Host", "transport": "real loopback TCP WebSocket", "runtime": core["runtime_version"]}

    async def wait_until(predicate: Any) -> None:
        async with asyncio.timeout(10):
            while not predicate():
                if serving.done():
                    await serving
                    raise RuntimeError("source server stopped")
                await asyncio.sleep(0.01)

    async def call(ws: Any, method: str, params: dict[str, Any]) -> dict[str, Any]:
        await ws.send(json.dumps({"id": method, "method": method, "params": params}))
        async with asyncio.timeout(30):
            while True:
                message = json.loads(await ws.recv())
                if message.get("id") == method:
                    return message

    def connect() -> Any:
        return websockets.connect(f"ws://127.0.0.1:{port}/ws", additional_headers={"Authorization": "Bearer preview-fixture"}, proxy=None)

    try:
        await wait_until(lambda: server.started)
        manager = app.state.material_previews
        workspace = app.state.scene_workspace
        scene_id = core["scene_id"]
        prefix = "scenes.material.preview."
        binding = {"source_revision_id": core["revision"]["id"], "image_asset_id": core["revision"]["dependencies"][0]["asset_id"],
                   "object_name": "Cube", "material_slot": 0, "channel": "base_color", "uv_map": "UVMap"}
        before = workspace.catalog.get("local", scene_id)
        async with connect() as ws:
            prepared = await call(ws, prefix + "prepare", {"scene_id": scene_id, "binding": binding})
            assert prepared["ok"], prepared
            candidate = prepared["result"]["candidate_id"]
            assert workspace.catalog.get("local", scene_id) == before
            async with connect() as other:
                denied = await call(other, prefix + "adopt", {"candidate_id": candidate})
                assert denied["error"]["code"] == "scene_material_preview_unavailable"
            data = await call(ws, prefix + "read", {"candidate_id": candidate, "offset": 0, "length": 524288})
            assert data["ok"]
            evidence["preview_bytes"] = data["result"]["total_bytes"]
            assert (await call(ws, prefix + "discard", {"candidate_id": candidate}))["ok"]
            assert workspace.catalog.get("local", scene_id) == before
            prepared = await call(ws, prefix + "prepare", {"scene_id": scene_id, "binding": binding})
            assert prepared["ok"], prepared
            candidate = prepared["result"]["candidate_id"]
            adopted = await call(ws, prefix + "adopt", {"candidate_id": candidate})
            assert adopted["ok"], adopted
            assert adopted == await call(ws, prefix + "adopt", {"candidate_id": candidate})
            assert adopted["result"]["revision"]["sequence"] == 3
            binding["source_revision_id"] = adopted["result"]["revision"]["id"]
        after = workspace.catalog.get("local", scene_id)
        async with connect() as ws:
            prepared = await call(ws, prefix + "prepare", {"scene_id": scene_id, "binding": binding})
            assert prepared["ok"], prepared
        await wait_until(lambda: not manager._candidates)
        assert not workspace.resolver._live_references
        assert workspace.catalog.get("local", scene_id) == after
        async with connect() as ws:
            await ws.send(json.dumps({"id": "disconnect-prepare", "method": prefix + "prepare", "params": {"scene_id": scene_id, "binding": binding}}))
            await wait_until(lambda: bool(list(manager.root.iterdir())))
        await wait_until(lambda: not list(manager.root.iterdir()) and not workspace.resolver._live_references)
        assert workspace.catalog.get("local", scene_id) == after
        async with connect() as ws:
            prepared = await call(ws, prefix + "prepare", {"scene_id": scene_id, "binding": binding})
            assert prepared["ok"], prepared
            clock = workspace._now
            advanced = clock() + timedelta(minutes=11)
            workspace._now = lambda: advanced
            await wait_until(lambda: not manager._candidates)
            workspace._now = clock
            assert not workspace.resolver._live_references
        assert workspace.catalog.get("local", scene_id) == after
        evidence.update({"prepare_discard_head_unchanged": True, "cross_connection_adopt_denied": True,
                         "adopt_and_retry_revision_count": len(after[1]), "ready_disconnect_cleanup": True,
                         "preparing_disconnect_cleanup": True, "periodic_expiry_with_advanced_clock": True,
                         "runtime_references_remaining": 0, "candidate_directories_remaining": 0,
                         "not_tested": ["browser UI", "installed Host", "signed bundle"]})
        return evidence
    finally:
        server.should_exit = True
        await serving
        listener.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--legacy-runtime-root", required=True, type=Path)
    args = parser.parse_args()
    evidence = asyncio.run(run(args))
    (args.data_dir / "transport-observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
