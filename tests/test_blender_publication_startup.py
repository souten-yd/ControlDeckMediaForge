from __future__ import annotations

import asyncio
import os
from pathlib import Path
import threading
from typing import Any

import pytest

from mediaforge.blender_publication_rollback import BlenderPublicationRollback
from mediaforge.store import Store
from test_blender_manager import archive_fixture, response_transport, runtime_manager
from test_blender_host_journal import create
from test_blender_publication_journal import prepared
from mediaforge.blender_operation import BlenderRuntimeOperationState as State


@pytest.mark.parametrize("case,missing", [
    ("registered", False), ("unregistered", False), ("rolled_back", False),
    ("repair_previous", False), ("repair_previous", True),
    ("committed_repair", False), ("committed_repair", True),
])
def test_startup_recovers_normal_journal_and_reclaims_only_verified_leftovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, missing: bool,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))

    async def run() -> None:
        await manager.start()
        await manager._publication_recovery
        runtime_id = "blender-4.5.9-linux-x64"
        destination = resolver.managed_root / runtime_id
        old_inode = None
        try:
            if "repair" in case:
                manager.install()
                await asyncio.gather(*list(manager._tasks.values()))
                old_inode = destination.stat().st_ino
                if missing:
                    (destination / "install/blender").unlink()
            with monkeypatch.context() as patch:
                # Simulate process loss at the chosen boundary: leave the
                # actual normal-manager journal, rather than fabricating it.
                patch.setattr(manager, "_fail_sync", lambda *args: None)
                if case == "repair_previous":
                    original = os.replace
                    def hold_previous(source: Any, target: Any) -> None:
                        original(source, target)
                        if Path(source) == destination:
                            raise OSError("process loss after previous rename")
                    patch.setattr(os, "replace", hold_previous)
                else:
                    target, name = ((store, "complete_blender_publication") if case == "committed_repair"
                                    else (resolver, "register_managed"))
                    original = getattr(target, name)
                    def stop(*args: Any, **kwargs: Any) -> None:
                        if case in {"registered", "committed_repair"}:
                            original(*args, **kwargs)
                        raise OSError("process loss at publication boundary")
                    patch.setattr(target, name, stop)
                operation = manager.repair(runtime_id) if "repair" in case else manager.install()
                await asyncio.gather(*list(manager._tasks.values()))
            if case == "rolled_back":
                store.require_blender_publication_recovery(operation.id)
                assert BlenderPublicationRollback(store, resolver).rollback(operation.id)["status"] == "rolled_back"
            before = store.get_blender_runtime_operation(operation.id)
        finally:
            await manager.stop()

        restarted_store = Store(tmp_path / "data")
        restarted_store.initialize()
        restarted, _ = runtime_manager(tmp_path, restarted_store, manifest, response_transport(content))
        entered, release = threading.Event(), threading.Event()
        original_recovery = restarted._recover_startup_publication
        loop_thread = threading.get_ident()
        def held(operation_id: str) -> None:
            assert threading.get_ident() != loop_thread
            entered.set()
            assert release.wait(5)
            original_recovery(operation_id)
        monkeypatch.setattr(restarted, "_recover_startup_publication", held)
        try:
            async with asyncio.timeout(1):
                await restarted.start()  # Does not wait for the held probe.
            assert await asyncio.to_thread(entered.wait, 3)
            assert not restarted._publication_recovery.done()
            release.set()
            await restarted._publication_recovery
            current = restarted_store.get_blender_runtime_operation(operation.id)
            journal = restarted_store.blender_publication(operation.id)
            if case in {"registered", "committed_repair"}:
                assert current.state.value == "ready" and journal.phase == "committed"
                assert (destination / "install/blender").is_file()
            else:
                assert current.state.value == "failed" and journal.phase == "rolled_back"
                if case == "repair_previous":
                    assert destination.stat().st_ino == old_inode
                    assert (destination / "install/blender").exists() == (not missing)
                else:
                    assert not destination.exists()
            if case in {"committed_repair", "rolled_back"}:
                assert current == before
            assert not any((resolver.managed_root / ".staging").iterdir())
        finally:
            release.set()
            await restarted.stop()
    asyncio.run(run())


def test_startup_scan_is_paginated_and_excludes_live_and_new_operations(tmp_path: Path) -> None:
    store, live_id, identity = prepared(tmp_path / "data")
    store.begin_blender_publication(live_id, identity)
    expected = []
    for index in range(104):
        runtime_id = f"runtime-{index}"
        operation_id = create(store, runtime_id, owner=None)
        store.update_blender_runtime_operation(operation_id, state=State.PROBING)
        bound = identity.model_copy(update={"runtime_id": runtime_id})
        store.begin_blender_publication(operation_id, bound)
        store.complete_blender_publication(operation_id, bound, {"verified": True})
        expected.append(operation_id)
        if index == 102:
            through = store.blender_publication_high_watermark()
    after, actual, sizes = 0, [], []
    while batch := store.blender_publication_startup_batch(after, through):
        sizes.append(len(batch))
        actual.extend(operation_id for _, operation_id in batch)
        assert all(after < cursor <= through for cursor, _ in batch)
        after = batch[-1][0]
    assert sizes == [50, 50, 3]
    assert actual == expected[:-1] and live_id not in actual


@pytest.mark.parametrize("scan_failure", [False, True])
def test_startup_failure_is_reported_without_losing_later_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, scan_failure: bool,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    def batch(after: int, through: int) -> list[tuple[int, str]]:
        if scan_failure:
            raise OSError("must-not-log-secret")
        return [(1, "broken"), (2, "later")] if after == 0 else []
    visited = []
    def recover(operation_id: str) -> None:
        visited.append(operation_id)
        if operation_id == "broken":
            raise OSError("must-not-log-secret")
    monkeypatch.setattr(store, "blender_publication_startup_batch", batch)
    monkeypatch.setattr(manager, "_recover_startup_publication", recover)
    asyncio.run(manager._recover_startup_publications(2))
    assert visited == ([] if scan_failure else ["broken", "later"])
    assert "evidence retained" in caplog.text and "must-not-log-secret" not in caplog.text


@pytest.mark.parametrize("cancel_count", [1, 3])
def test_shutdown_drains_started_startup_recovery_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_count: int,
) -> None:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(store, "blender_publication_high_watermark", lambda: 1)
    monkeypatch.setattr(store, "blender_publication_startup_batch", lambda after, through: [(1, "owned")] if after == 0 else [])
    def held(operation_id: str) -> None:
        entered.set()
        assert release.wait(5)
        finished.set()
    monkeypatch.setattr(manager, "_recover_startup_publication", held)
    async def run() -> None:
        await manager.start()
        assert await asyncio.to_thread(entered.wait, 3)
        stopping = asyncio.create_task(manager.stop())
        try:
            for _ in range(cancel_count):
                await asyncio.sleep(.02)
                stopping.cancel()
                manager._publication_recovery.cancel()
            assert not stopping.done() and not finished.is_set()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await stopping
        assert finished.is_set() and manager._publication_recovery is None
    asyncio.run(run())
