from __future__ import annotations

import asyncio
import os
from pathlib import Path
import threading
from typing import Any

import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationAction
from mediaforge.store import Store
from test_blender_manager import archive_fixture, response_transport, runtime_manager


@pytest.mark.parametrize("stage", ["progress", "fsync"])
def test_download_progress_and_fsync_run_off_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    spec = manager.spec
    operation = store.create_blender_runtime_operation("blender-4.5.9-linux-x64", "4.5.9",
        BlenderRuntimeOperationAction.INSTALL, bytes_total=len(content))
    partial = tmp_path / "downloads/archive.partial"
    loop_thread = threading.get_ident()
    observed: list[int] = []
    original_update, original_fsync = store.update_blender_runtime_operation, os.fsync

    def update(*args: Any, **kwargs: Any) -> Any:
        if "bytes_done" in kwargs and stage == "progress":
            observed.append(threading.get_ident())
            assert threading.get_ident() != loop_thread
        return original_update(*args, **kwargs)

    def fsync(fd: int) -> None:
        if stage == "fsync":
            observed.append(threading.get_ident())
            assert threading.get_ident() != loop_thread
        original_fsync(fd)

    monkeypatch.setattr(store, "update_blender_runtime_operation", update)
    monkeypatch.setattr(os, "fsync", fsync)
    asyncio.run(manager._download_attempt(operation, spec, partial, partial.with_suffix(".json")))
    assert observed
    assert partial.read_bytes() == content
    assert store.get_blender_runtime_operation(operation.id).bytes_done == len(content)


@pytest.mark.parametrize("stage", ["progress", "fsync"])
@pytest.mark.parametrize("cancel_count", [1, 3])
def test_download_cancellation_drains_started_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, cancel_count: int,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    spec = manager.spec
    operation = store.create_blender_runtime_operation("blender-4.5.9-linux-x64", "4.5.9",
        BlenderRuntimeOperationAction.INSTALL, bytes_total=len(content))
    partial = tmp_path / "downloads/archive.partial"
    entered, release = threading.Event(), threading.Event()
    original_update, original_fsync = store.update_blender_runtime_operation, os.fsync

    def hold() -> None:
        entered.set()
        assert release.wait(5)

    def update(*args: Any, **kwargs: Any) -> Any:
        if "bytes_done" in kwargs and stage == "progress":
            hold()
        return original_update(*args, **kwargs)

    def fsync(fd: int) -> None:
        if stage == "fsync":
            hold()
        original_fsync(fd)

    monkeypatch.setattr(store, "update_blender_runtime_operation", update)
    monkeypatch.setattr(os, "fsync", fsync)

    async def scenario() -> None:
        request = asyncio.create_task(manager._download_attempt(operation, spec, partial, partial.with_suffix(".json")))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            for _ in range(cancel_count):
                request.cancel()
                await asyncio.sleep(0.01)
            assert not request.done()
        finally:
            release.set()
            result = await asyncio.gather(request, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)

    asyncio.run(scenario())
    assert partial.read_bytes() == content
    assert store.get_blender_runtime_operation(operation.id).bytes_done == len(content)


@pytest.mark.parametrize("kind", ["symlink", "missing", "wrong_size", "fifo"])
def test_download_reopen_refuses_changed_partial(tmp_path: Path, kind: str) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    operation = store.create_blender_runtime_operation("blender-4.5.9-linux-x64", "4.5.9",
        BlenderRuntimeOperationAction.INSTALL, bytes_total=len(content))
    partial = tmp_path / "changed.partial"
    target = tmp_path / "untouched"
    target.write_bytes(b"original")
    if kind == "symlink":
        partial.symlink_to(target)
    elif kind == "wrong_size":
        partial.write_bytes(b"unexpected")
    elif kind == "fifo":
        os.mkfifo(partial)
    from mediaforge.blender_operation import BlenderRuntimeOperationError
    with pytest.raises((OSError, BlenderRuntimeOperationError)):
        manager._append_download_chunk(operation.id, partial, b"x", 1, 0)
    assert target.read_bytes() == b"original"
    assert store.get_blender_runtime_operation(operation.id).bytes_done == 0
