from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import shutil
from typing import Any

import pytest

from mediaforge.blender_publication_generation import MARKER_NAME, read_generation
from mediaforge.blender_publication_rollback import BlenderPublicationRollback
from test_blender_install_publication import setup
from test_blender_setup_host import identity


def interrupted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manager, resolver, store, _ = setup(tmp_path)
    async def run():
        await manager.start()
        try:
            with monkeypatch.context() as patch:
                def fail(**kwargs: Any) -> None:
                    raise OSError("registration not performed")
                patch.setattr(resolver, "register_managed", fail)
                patch.setattr(BlenderPublicationRollback, "rollback",
                    lambda *args: {"status": "recovery_required"})
                operation = await manager.request("install", identity=identity())
                await asyncio.gather(*list(manager._tasks.values()))
            assert store.blender_publication(operation.id).phase == "recovery_required"
            return operation
        finally:
            await manager.stop()
    return manager, resolver, store, asyncio.run(run())


@pytest.mark.parametrize("stop", [None, "cancel", "host_context_lost"])
def test_verified_rollback_preserves_candidate_and_has_immutable_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str | None,
) -> None:
    manager, resolver, store, operation = interrupted(tmp_path, monkeypatch)
    destination = resolver.managed_root / operation.runtime_id
    old_inode = (destination / "install/blender").stat().st_ino
    journal = store.blender_publication(operation.id)
    if stop == "cancel":
        store.request_blender_runtime_operation_cancel(operation.id)
    elif stop:
        store.abort_blender_runtime_host_operation(operation.id, "user:16")
    result = BlenderPublicationRollback(store, resolver).rollback(operation.id)
    assert result["status"] == "rolled_back"
    candidate = resolver.managed_root / ".staging" / operation.id / "candidate"
    assert not destination.exists() and (candidate / "install/blender").stat().st_ino == old_inode
    assert read_generation(resolver.managed_root, candidate) == journal.identity.generation
    assert not resolver.registry_path.exists()
    current = store.get_blender_runtime_operation(operation.id)
    assert current.state.value == ("canceled" if stop == "cancel" else "failed")
    assert current.result["publication_rolled_back"]
    assert store.blender_runtime_host_journal(operation.id, "user:16")["terminal"]["status"] == current.state.value
    assert store.rollback_blender_publication(operation.id, journal.identity) == current
    store.request_blender_runtime_operation_cancel(operation.id)
    store.require_blender_publication_recovery(operation.id)
    store.initialize()
    assert store.get_blender_runtime_operation(operation.id) == current
    assert store.blender_publication(operation.id).phase == "rolled_back"


@pytest.mark.parametrize("condition", ["registered", "active_changed", "generation", "executable", "both", "missing", "parent_link", "live", "history"])
def test_ambiguous_or_referenced_candidate_is_never_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, condition: str,
) -> None:
    manager, resolver, store, operation = interrupted(tmp_path, monkeypatch)
    destination = resolver.managed_root / operation.runtime_id
    candidate = resolver.managed_root / ".staging" / operation.id / "candidate"
    if condition == "registered":
        resolver.register_managed(runtime_id=operation.runtime_id, version=operation.version,
            location=operation.runtime_id, archive_sha256=manager.spec.archive_sha256)
    elif condition == "active_changed":
        previous = resolver._read_registry
        monkeypatch.setattr(resolver, "_read_registry", lambda: {**previous(), "active_runtime_id": "another-runtime"})
    elif condition == "generation":
        (destination / MARKER_NAME).write_text("f" * 32 + "\n")
    elif condition == "executable":
        (destination / "install/blender").write_bytes(b"changed executable")
    elif condition == "both":
        shutil.copytree(destination, candidate)
    elif condition == "missing":
        destination.rename(tmp_path / "preserved")
    elif condition == "parent_link":
        alternate = resolver.managed_root / "alternate"
        candidate.parent.rename(alternate)
        candidate.parent.symlink_to(alternate)
    elif condition == "live":
        monkeypatch.setattr(resolver, "live_reference_count", lambda runtime_id: 1)
    else:
        monkeypatch.setattr(store, "scene_runtime_reference_count", lambda runtime_id: 1)
    def snapshot() -> dict[str, tuple[int, str | None]]:
        # Runtime bytes/inodes and registry are the rollback invariant. SQLite
        # is allowed to reclaim its transient WAL/SHM files when readers close.
        roots = [resolver.managed_root, tmp_path / "preserved"]
        paths = [path for root in roots if root.exists() for path in root.rglob("*")]
        return {str(path.relative_to(tmp_path)): (path.lstat().st_ino,
            os.readlink(path) if path.is_symlink() else
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None) for path in paths}
    before = snapshot()
    registry = resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None
    result = BlenderPublicationRollback(store, resolver).rollback(operation.id)
    assert result["status"] == "recovery_required"
    assert store.blender_publication(operation.id).phase == "recovery_required"
    assert store.blender_runtime_host_journal(operation.id, "user:16")["terminal"] is None
    assert snapshot() == before
    assert (resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None) == registry


def test_rollback_commit_failure_is_retryable_without_losing_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, resolver, store, operation = interrupted(tmp_path, monkeypatch)
    original = store.rollback_blender_publication
    def fail(*args: Any) -> None:
        raise OSError("database acknowledgement unavailable")
    monkeypatch.setattr(store, "rollback_blender_publication", fail)
    with pytest.raises(OSError):
        BlenderPublicationRollback(store, resolver).rollback(operation.id)
    assert store.blender_publication(operation.id).phase == "recovery_required"
    assert not (resolver.managed_root / operation.runtime_id).exists()
    monkeypatch.setattr(store, "rollback_blender_publication", original)
    assert BlenderPublicationRollback(store, resolver).rollback(operation.id)["status"] == "rolled_back"
