from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any

import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationAction, BlenderRuntimeOperationState
from mediaforge.blender_runtime import BlenderRuntimeRegistryError
from mediaforge.store import Store
from test_blender_manager import archive_fixture, response_transport, runtime_manager, wait_terminal


@pytest.mark.parametrize("outcome", ["ready", "failed", "canceled"])
def test_execution_control_and_terminal_persistence_run_off_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))

    async def prepare() -> None:
        await manager.start()
        installed = await manager.request("install")
        assert (await wait_terminal(store, installed.id)).state == BlenderRuntimeOperationState.READY
        await manager.stop()

    asyncio.run(prepare())
    operation = store.create_blender_runtime_operation(
        "blender-4.5.9-linux-x64", "4.5.9", BlenderRuntimeOperationAction.SWITCH, bytes_total=0)
    stage = manager._stage_root(operation.id)
    stage.mkdir(parents=True)
    (stage / "partial").write_bytes(b"discard only this staging data")
    if outcome == "canceled":
        store.request_blender_runtime_operation_cancel(operation.id)
    observed: list[str] = []

    def checked(name: str, original: Any) -> Any:
        def invoke(*args: Any, **kwargs: Any) -> Any:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                observed.append(name)
            else:
                raise AssertionError(f"{name} blocked the execution event loop")
            return original(*args, **kwargs)
        return invoke

    if outcome == "failed":
        def fail(runtime_id: str) -> Any:
            raise BlenderRuntimeRegistryError("blender_runtime_not_ready", "probe rejected")
        monkeypatch.setattr(resolver, "activate", fail)
    for name in ("get_blender_runtime_operation", "blender_runtime_operation_cancel_requested",
                 "update_blender_runtime_operation"):
        monkeypatch.setattr(store, name, checked(name, getattr(store, name)))
    monkeypatch.setattr(resolver, "activate", checked("activate", resolver.activate))
    monkeypatch.setattr(manager, "_stage_root", checked("stage", manager._stage_root))
    asyncio.run(manager._run(operation.id))
    terminal = store.get_blender_runtime_operation(operation.id)
    assert terminal.state.value == outcome
    assert "get_blender_runtime_operation" in observed
    assert "update_blender_runtime_operation" in observed
    if outcome != "canceled":
        assert "activate" in observed
    if outcome != "ready":
        assert not stage.exists()
    assert resolver.resolve_g8() is not None


def test_startup_recovery_reads_and_directories_run_off_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))
    operation = store.create_blender_runtime_operation(
        "blender-4.5.9-linux-x64", "4.5.9", BlenderRuntimeOperationAction.INSTALL, bytes_total=1)
    original_mkdir = Path.mkdir
    original_resume = store.resumable_blender_runtime_operation_ids
    observed: list[str] = []

    def off_loop() -> None:
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()

    def mkdir(path: Path, *args: Any, **kwargs: Any) -> None:
        if path in {resolver.managed_root, manager.download_root}:
            off_loop()
            observed.append("mkdir")
        original_mkdir(path, *args, **kwargs)

    def resumable() -> list[str]:
        off_loop()
        observed.append("resume")
        return original_resume()

    spawned: list[str] = []
    def spawn(operation_id: str) -> None:
        asyncio.get_running_loop()
        spawned.append(operation_id)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(store, "resumable_blender_runtime_operation_ids", resumable)
    monkeypatch.setattr(manager, "_spawn", spawn)
    asyncio.run(manager.start())
    assert observed.count("mkdir") == 2 and "resume" in observed
    assert spawned == [operation.id]


def test_repeated_shutdown_cancellation_waits_for_switch_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))
    entered, release = threading.Event(), threading.Event()
    activate = resolver.activate

    def held(runtime_id: str) -> Any:
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        entered.set()
        assert release.wait(5)
        return activate(runtime_id)

    async def scenario() -> None:
        await manager.start()
        installed = await manager.request("install")
        assert (await wait_terminal(store, installed.id)).state == BlenderRuntimeOperationState.READY
        monkeypatch.setattr(resolver, "activate", held)
        operation = await manager.request("switch", "blender-4.5.9-linux-x64")
        stopping = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            running = manager._tasks[operation.id]
            stopping = asyncio.create_task(manager.stop())
            for _ in range(3):
                await asyncio.sleep(.01)
                stopping.cancel()
                running.cancel()
            await asyncio.sleep(.01)
            assert not running.done() and not stopping.done()
        finally:
            release.set()
            if stopping is not None:
                await asyncio.gather(stopping, return_exceptions=True)
            await manager.stop()
        assert not manager._tasks
        assert store.get_blender_runtime_operation(operation.id).state == BlenderRuntimeOperationState.READY
        assert resolver.resolve_active().runtime_id == operation.runtime_id

    asyncio.run(scenario())


@pytest.mark.parametrize("state", [BlenderRuntimeOperationState.FAILED, BlenderRuntimeOperationState.CANCELED])
def test_terminal_cleanup_is_owned_through_repeated_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: BlenderRuntimeOperationState,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    operation = store.create_blender_runtime_operation(
        "blender-4.5.9-linux-x64", "4.5.9", BlenderRuntimeOperationAction.INSTALL, bytes_total=1)
    if state == BlenderRuntimeOperationState.CANCELED:
        store.request_blender_runtime_operation_cancel(operation.id)
    stage = manager._stage_root(operation.id)
    stage.mkdir(parents=True)
    (stage / "partial").write_bytes(b"staging")
    entered, release = threading.Event(), threading.Event()
    update = store.update_blender_runtime_operation

    def held(operation_id: str, **kwargs: Any) -> Any:
        if kwargs.get("state") == state:
            with pytest.raises(RuntimeError):
                asyncio.get_running_loop()
            assert not stage.exists()
            entered.set()
            assert release.wait(5)
        return update(operation_id, **kwargs)

    async def fail(value: Any) -> None:
        raise OSError("simulated install failure")

    monkeypatch.setattr(store, "update_blender_runtime_operation", held)
    monkeypatch.setattr(manager, "_install", fail)

    async def scenario() -> None:
        running = asyncio.create_task(manager._run(operation.id))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            for _ in range(3):
                running.cancel()
                await asyncio.sleep(.01)
                assert not running.done()
        finally:
            release.set()
            result = await asyncio.gather(running, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
        assert store.get_blender_runtime_operation(operation.id).state == state

    asyncio.run(scenario())
