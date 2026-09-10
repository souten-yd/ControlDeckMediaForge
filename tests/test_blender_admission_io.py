from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any

from fastapi.testclient import TestClient
import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationAction
from test_host_execution import host_client
from test_workspace_transport import call


@pytest.mark.parametrize("action", ["install", "web_install", "update", "repair", "switch", "cancel"])
def test_http_setup_admission_checks_run_off_loop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, action: str,
) -> None:
    manager = client.app.state.blender_runtime_operations
    payload = {"action": action}
    if action in {"repair", "switch"}:
        payload["runtime_id"] = "blender-4.5.9-linux-x64"
    if action == "cancel":
        operation = manager.store.create_blender_runtime_operation(
            "blender-4.5.9-linux-x64", "4.5.9", BlenderRuntimeOperationAction.INSTALL, bytes_total=1)
        payload["operation_id"] = operation.id
    observed: list[int] = []

    def checked(original: Any) -> Any:
        def invoke(*args: Any, **kwargs: Any) -> Any:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                observed.append(threading.get_ident())
            else:
                raise AssertionError("setup admission blocked the event loop")
            return original(*args, **kwargs)
        return invoke

    monkeypatch.setattr(manager, "_catalog", checked(manager._catalog))
    monkeypatch.setattr(manager.store, "get_blender_runtime_operation", checked(manager.store.get_blender_runtime_operation))
    if manager.web_pack is not None:
        monkeypatch.setattr(manager.web_pack, "spec", checked(manager.web_pack.spec))

    def spawn(operation_id: str) -> None:
        asyncio.get_running_loop()  # Task creation must remain on the loop.

    monkeypatch.setattr(manager, "_spawn", spawn)
    response = client.post("/workspace-api/blender/runtime/operations", json=payload)
    assert response.status_code in {200, 422}
    assert observed


def test_repeated_cancellation_and_shutdown_wait_for_durable_admission(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = client.app.state.blender_runtime_operations
    entered, release = threading.Event(), threading.Event()
    spawned: list[str] = []

    def prepare() -> Any:
        entered.set()
        assert release.wait(5)
        return manager.store.create_blender_runtime_operation(
            "blender-4.5.9-linux-x64", "4.5.9", BlenderRuntimeOperationAction.INSTALL, bytes_total=1)

    def spawn(operation_id: str) -> None:
        asyncio.get_running_loop()
        spawned.append(operation_id)

    monkeypatch.setattr(manager, "_prepare_install", prepare, raising=False)
    monkeypatch.setattr(manager, "_spawn", spawn)

    async def scenario() -> None:
        request = asyncio.create_task(manager.request("install"))
        stopping = None
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _ in range(3):
                request.cancel()
                await asyncio.sleep(.01)
                assert not request.done()
            stopping = asyncio.create_task(manager.stop())
            await asyncio.sleep(.01)
            assert not stopping.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await request
        if stopping is not None:
            await stopping
        assert len(spawned) == 1
        assert manager.store.get_blender_runtime_operation(spawned[0]).state.value == "queued"

    asyncio.run(scenario())


@pytest.mark.parametrize("action,method", [
    ("install", "blender.runtime.install"),
    ("web_install", "blender.web.install"),
    ("update", "blender.runtime.update"),
    ("repair", "blender.runtime.repair"),
    ("switch", "blender.runtime.switch"),
    ("cancel", "blender.runtime.operations.cancel"),
])
def test_workspace_routes_use_async_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, method: str,
) -> None:
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client:
        manager = client.app.state.blender_runtime_operations
        operation = manager.store.create_blender_runtime_operation(
            "blender-4.5.9-linux-x64", "4.5.9", BlenderRuntimeOperationAction.INSTALL, bytes_total=1)
        seen: list[tuple[str, str]] = []

        async def request(value: str, identifier: str = "", *, identity: Any = None) -> Any:
            await asyncio.sleep(0)
            assert identity is not None and identity.authorization
            seen.append((value, identifier))
            return operation

        monkeypatch.setattr(manager, "request", request)
        params = {}
        identifier = ""
        if action in {"repair", "switch"}:
            identifier = operation.runtime_id
            params["runtime_id"] = identifier
        elif action == "cancel":
            identifier = operation.id
            params["operation_id"] = identifier
        with client.websocket_connect("/ws", headers=headers) as socket:
            result = call(socket, method, params)
        assert result["ok"] and result["result"]["id"] == operation.id
        assert seen == [(action, identifier)]


def test_concurrent_duplicate_admission_reuses_one_journal_row(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = client.app.state.blender_runtime_operations
    entered, release = threading.Event(), threading.Event()
    original = manager.store.create_blender_runtime_operation
    inserts: list[int] = []

    def create(*args: Any, **kwargs: Any) -> Any:
        inserts.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(manager.store, "create_blender_runtime_operation", create)
    monkeypatch.setattr(manager, "_spawn", lambda operation_id: None)

    async def scenario() -> None:
        first = asyncio.create_task(manager.request("install"))
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            second = asyncio.create_task(manager.request("install"))
            await asyncio.sleep(.05)
            assert len(inserts) == 1 and not second.done()
        finally:
            release.set()
        assert second is not None
        a, b = await asyncio.gather(first, second)
        assert a.id == b.id and len(inserts) == 1
        assert not manager._request_admissions

    asyncio.run(scenario())
