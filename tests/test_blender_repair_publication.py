from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from mediaforge.blender_publication import PublicationIdentity
from mediaforge.blender_publication_generation import read_generation
from test_blender_install_publication import setup
from test_blender_setup_host import identity


@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("fault", ["old_rename", "candidate_rename", "register_before", "register_after", "complete_before", "complete_after"])
def test_repair_publication_failures_keep_exact_old_or_verified_new_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: bool, fault: str,
) -> None:
    manager, resolver, store, _ = setup(tmp_path)
    async def run() -> None:
        await manager.start()
        try:
            installed = await manager.request("install", identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
            destination = resolver.managed_root / installed.runtime_id
            executable = destination / "install/blender"
            expected = executable.read_bytes()
            old_root = destination.stat()
            old_generation = read_generation(resolver.managed_root, destination)
            registry = resolver.registry_path.read_bytes()
            if missing:
                executable.unlink()
            with monkeypatch.context() as patch:
                if fault.endswith("rename"):
                    original = os.replace
                    def fail_rename(source: Any, target: Any) -> None:
                        if ((fault == "old_rename" and Path(source) == destination)
                                or (fault == "candidate_rename" and Path(source).name == "candidate")):
                            raise OSError("injected repair rename failure")
                        original(source, target)
                    patch.setattr(os, "replace", fail_rename)
                else:
                    target, name = ((resolver, "register_managed") if fault.startswith("register")
                                    else (store, "complete_blender_publication"))
                    original = getattr(target, name)
                    def fail_call(*args: Any, **kwargs: Any) -> Any:
                        if fault.endswith("after"):
                            original(*args, **kwargs)
                        raise OSError("injected repair acknowledgement failure")
                    patch.setattr(target, name, fail_call)
                operation = await manager.request("repair", installed.runtime_id, identity=identity())
                await asyncio.gather(*list(manager._tasks.values()))
            journal = store.blender_publication(operation.id)
            previous = journal.identity
            assert previous.previous_root_inode == old_root.st_ino and previous.previous_root_device == old_root.st_dev
            assert previous.previous_executable_missing == missing
            assert previous.previous_executable_sha256 == (None if missing else hashlib.sha256(expected).hexdigest())
            assert previous.previous_generation == old_generation and previous.generation != old_generation
            assert resolver.registry_path.read_bytes() == registry
            assert not any((resolver.managed_root / ".staging").iterdir())
            result = store.get_blender_runtime_operation(operation.id)
            if fault.endswith("rename"):
                assert result.state.value == "failed" and journal.phase == "rolled_back"
                assert destination.stat().st_ino == old_root.st_ino
                assert not executable.exists() if missing else executable.read_bytes() == expected
                retry = await manager.request("repair", installed.runtime_id, identity=identity())
                await asyncio.gather(*list(manager._tasks.values()))
                assert store.get_blender_runtime_operation(retry.id).state.value == "ready"
                assert executable.read_bytes() == expected
            else:
                assert result.state.value == "ready" and journal.phase == "committed"
                assert result.error_code is None and not result.cancel_requested
                assert destination.stat().st_ino != old_root.st_ino and executable.read_bytes() == expected
                assert read_generation(resolver.managed_root, destination) == previous.generation
                assert store.blender_runtime_host_journal(operation.id, "user:16")["terminal"]["status"] == "succeeded"
            store.initialize()
            assert store.get_blender_runtime_operation(operation.id) == result
        finally:
            await manager.stop()
    asyncio.run(run())


@pytest.mark.parametrize("change", [
    {"previous_root_inode": None}, {"previous_root_device": None}, {"generation": None},
    {"previous_registration_sha256": None}, {"previous_executable_sha256": "c" * 64}, {"recovered_directory": True},
])
def test_missing_previous_executable_requires_complete_identity(change: dict[str, Any]) -> None:
    value = dict(runtime_id="blender-test", version="4.5.9", action="repair",
        archive_sha256="a" * 64, executable_sha256="b" * 64, previous_active_runtime_id="blender-test",
        previous_registration_sha256="c" * 64, previous_executable_sha256=None, recovered_directory=False,
        previous_root_device=1, previous_root_inode=2, previous_executable_missing=True, generation="d" * 32)
    assert PublicationIdentity.model_validate(value).previous_executable_missing
    with pytest.raises(ValidationError):
        PublicationIdentity.model_validate({**value, **change})


@pytest.mark.parametrize("change", ["old_root", "candidate_generation"])
def test_repair_rollback_retains_unproven_old_and_new_trees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    manager, resolver, store, _ = setup(tmp_path)
    async def run() -> None:
        await manager.start()
        try:
            installed = await manager.request("install", identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
            original = os.replace
            def fail(source: Any, target: Any) -> None:
                if Path(source).name != "candidate":
                    return original(source, target)
                candidate = Path(source)
                previous = resolver.managed_root / ".staging" / f"previous-{candidate.parent.name}"
                if change == "old_root":
                    copied = tmp_path / "copied"
                    shutil.copytree(previous, copied)
                    previous.rename(tmp_path / "original-preserved")
                    copied.rename(previous)
                else:
                    (candidate / ".publication-generation").write_text("f" * 32 + "\n")
                raise OSError("injected failure after changed evidence")
            monkeypatch.setattr(os, "replace", fail)
            operation = await manager.request("repair", installed.runtime_id, identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
            assert store.blender_publication(operation.id).phase == "recovery_required"
            assert store.blender_runtime_host_journal(operation.id, "user:16")["terminal"] is None
            stage = resolver.managed_root / ".staging"
            assert (stage / f"previous-{operation.id}" / "install/blender").is_file()
            assert (stage / operation.id / "candidate/install/blender").is_file()
            assert not (resolver.managed_root / installed.runtime_id).exists()
        finally:
            await manager.stop()
    asyncio.run(run())


def test_old_backup_is_not_deleted_until_commit_and_is_retained_if_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    manager, resolver, store, _ = setup(tmp_path)
    async def run() -> None:
        await manager.start()
        try:
            installed = await manager.request("install", identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
            original = store.complete_blender_publication
            def completed(operation_id: str, publication_identity: PublicationIdentity, result: dict[str, Any]):
                previous = resolver.managed_root / ".staging" / f"previous-{operation_id}"
                assert previous.stat().st_ino == publication_identity.previous_root_inode
                value = original(operation_id, publication_identity, result)
                (previous / "install/blender").write_bytes(b"modified old backup")
                return value
            monkeypatch.setattr(store, "complete_blender_publication", completed)
            operation = await manager.request("repair", installed.runtime_id, identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
            assert store.blender_publication(operation.id).phase == "committed"
            assert store.get_blender_runtime_operation(operation.id).state.value == "ready"
            previous = resolver.managed_root / ".staging" / f"previous-{operation.id}"
            assert (previous / "install/blender").read_bytes() == b"modified old backup"
            assert "cleanup incomplete" in caplog.text
            assert resolver.resolve_active().runtime_id == installed.runtime_id
        finally:
            await manager.stop()
    asyncio.run(run())
