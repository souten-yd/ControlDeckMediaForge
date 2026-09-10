from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient

from test_host_execution import host_client
from test_workspace_transport import call


def test_runtime_status_checks_do_not_run_on_event_loop(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = client.app.state.blender_runtime_operations.resolver
    original = resolver.status
    threads: list[int] = []

    def checked() -> dict[str, Any]:
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        threads.append(threading.get_ident())
        return original()

    monkeypatch.setattr(resolver, "status", checked)
    response = client.get("/workspace-api/blender/runtime")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "media-forge.blender-runtime-status@1"
    assert threads


def test_status_cancellation_waits_for_started_registry_work(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = client.app.state.blender_runtime_operations.resolver
    original = resolver.status
    entered, release = threading.Event(), threading.Event()
    endpoint = next(route.endpoint for route in client.app.routes
                    if getattr(route, "path", None) == "/workspace-api/blender/runtime")

    def delayed() -> dict[str, Any]:
        entered.set()
        assert release.wait(5)
        return original()

    monkeypatch.setattr(resolver, "status", delayed)

    async def scenario() -> None:
        task = asyncio.create_task(endpoint())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0.01)
                assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


@pytest.mark.parametrize("method", ["blender.runtime.status", "workspace.session"])
def test_workspace_runtime_projection_runs_off_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client:
        resolver = client.app.state.blender_runtime_operations.resolver
        original = resolver.status
        observed = []

        def checked() -> dict[str, Any]:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                observed.append(True)
            else:
                raise AssertionError("runtime status ran on event loop")
            return original()

        monkeypatch.setattr(resolver, "status", checked)
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, method, {"parts": ["blender_runtime"]}
                          if method == "workspace.session" else {})
        assert answer["ok"] and observed
        result = answer["result"]
        if method == "workspace.session":
            result = result["blender_runtime"]
        assert result["schema_version"] == "media-forge.blender-runtime-status@1"
