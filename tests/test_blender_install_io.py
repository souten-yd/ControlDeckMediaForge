from __future__ import annotations

import asyncio
import os
from pathlib import Path
import threading
from typing import Any

import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationAction
from mediaforge.store import Store
import mediaforge.blender_manager as manager_module
from test_blender_manager import archive_fixture, response_transport, runtime_manager
from test_blender_web import fixture_manifest, manager_fixture, response_transport as web_transport


@pytest.mark.parametrize("kind", ["install", "recovered", "repair", "web", "web_recovered"])
def test_install_filesystem_and_journal_stages_are_off_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    if kind.startswith("web"):
        manifest, contents = fixture_manifest(tmp_path)
        manager, pack = manager_fixture(tmp_path, store, manifest, web_transport(contents))
        spec = pack.spec()
        runtime_id, version = spec.pack_id, spec.version
        size = spec.archive_size_bytes
    else:
        content, manifest = archive_fixture(tmp_path)
        manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
        runtime_id, version, size = "blender-4.5.9-linux-x64", "4.5.9", len(content)
    asyncio.run(manager.start())
    if kind in {"recovered", "repair", "web_recovered"}:
        first = store.create_blender_runtime_operation(
            runtime_id, version, BlenderRuntimeOperationAction.INSTALL, bytes_total=size)
        asyncio.run(manager._run(first.id))
        assert store.get_blender_runtime_operation(first.id).state == "ready"
    action = BlenderRuntimeOperationAction.REPAIR if kind == "repair" else BlenderRuntimeOperationAction.INSTALL
    operation = store.create_blender_runtime_operation(runtime_id, version, action, bytes_total=size)
    observed: set[str] = set()

    def checked(name: str, original: Any, *, path_method: bool = False) -> Any:
        def invoke(*args: Any, **kwargs: Any) -> Any:
            if not path_method or str(args[0]).startswith(str(tmp_path)):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    observed.add(name)
                else:
                    raise AssertionError(f"install {name} ran on event loop")
            return original(*args, **kwargs)
        return invoke

    for name in ("stat", "mkdir", "open", "unlink", "chmod", "read_text", "write_text"):
        monkeypatch.setattr(Path, name, checked(name, getattr(Path, name), path_method=True))
    for name in ("get_blender_runtime_operation", "blender_runtime_operation_cancel_requested",
                 "update_blender_runtime_operation"):
        monkeypatch.setattr(store, name, checked(name, getattr(store, name)))
    asyncio.run(manager._run(operation.id))
    terminal = store.get_blender_runtime_operation(operation.id)
    assert terminal.state == "ready", terminal
    assert {"stat", "read_text", "update_blender_runtime_operation"} <= observed
    if "recovered" in kind:
        assert terminal.result["recovered"] is True
    else:
        assert {"mkdir", "write_text", "open"} <= observed


@pytest.mark.parametrize("kind", ["install", "web"])
def test_shutdown_keeps_started_archive_stage_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    if kind == "web":
        manifest, contents = fixture_manifest(tmp_path)
        manager, pack = manager_fixture(tmp_path, store, manifest, web_transport(contents))
        spec = pack.spec()
        runtime_id, version, size = spec.pack_id, spec.version, spec.archive_size_bytes
        validation_name = "validate_web_pack_archive"
    else:
        content, manifest = archive_fixture(tmp_path)
        manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
        runtime_id, version, size = "blender-4.5.9-linux-x64", "4.5.9", len(content)
        validation_name = "validate_archive"
    operation = store.create_blender_runtime_operation(
        runtime_id, version, BlenderRuntimeOperationAction.INSTALL, bytes_total=size)
    entered, release = threading.Event(), threading.Event()
    validate = getattr(manager_module, validation_name)

    def held(*args: Any, **kwargs: Any) -> Any:
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        entered.set()
        assert release.wait(5)
        return validate(*args, **kwargs)

    monkeypatch.setattr(manager_module, validation_name, held)

    async def scenario() -> None:
        await manager.start()  # Resume the real queued journal through the manager.
        stopping = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            running = manager._tasks[operation.id]
            stopping = asyncio.create_task(manager.stop())
            for _ in range(3):
                await asyncio.sleep(.01)
                running.cancel()
                stopping.cancel()
            await asyncio.sleep(.01)
            assert not running.done() and not stopping.done()
        finally:
            release.set()
            if stopping is not None:
                await asyncio.gather(stopping, return_exceptions=True)
            await manager.stop()
        assert not manager._tasks
        terminal = await asyncio.to_thread(store.get_blender_runtime_operation, operation.id)
        assert terminal.state == "ready", terminal

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory"])
def test_partial_metadata_never_writes_through_unsafe_target(tmp_path: Path, kind: str) -> None:
    from mediaforge.blender_operation import BlenderRuntimeOperationError
    partial = tmp_path / "archive.partial"
    metadata = tmp_path / "archive.partial.json"
    target = tmp_path / "untouched"
    target.write_bytes(b"original")
    if kind == "symlink":
        metadata.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(metadata)
    else:
        metadata.mkdir()
    with pytest.raises((OSError, BlenderRuntimeOperationError)):
        manager_module.BlenderRuntimeManager._prepare_partial(partial, metadata, '"etag"')
    assert target.read_bytes() == b"original"
    assert not partial.exists()


def test_partial_creation_is_exclusive_and_metadata_is_private(tmp_path: Path) -> None:
    partial = tmp_path / "archive.partial"
    metadata = tmp_path / "archive.partial.json"
    metadata.write_bytes(b"stale metadata with trailing bytes")
    metadata.chmod(0o666)
    manager_module.BlenderRuntimeManager._prepare_partial(partial, metadata, '"etag"')
    assert metadata.read_text() == '{"etag": "\\\"etag\\\""}\n'
    assert metadata.stat().st_mode & 0o777 == 0o600
    assert partial.stat().st_mode & 0o777 == 0o600


def test_empty_partial_after_interruption_restarts_download(tmp_path: Path) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    spec = manager.spec
    operation = store.create_blender_runtime_operation(
        "blender-4.5.9-linux-x64", "4.5.9", BlenderRuntimeOperationAction.INSTALL, bytes_total=len(content))
    partial = tmp_path / "archive.partial"
    metadata = tmp_path / "archive.partial.json"
    partial.touch()
    metadata.write_text('{"etag":"old"}')
    asyncio.run(manager._download_attempt(operation, spec, partial, metadata))
    assert partial.read_bytes() == content
    assert store.get_blender_runtime_operation(operation.id).bytes_done == len(content)
