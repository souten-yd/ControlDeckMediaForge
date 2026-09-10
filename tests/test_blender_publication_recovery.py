from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import shutil
from typing import Any

import httpx
import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationAction as Action
from mediaforge.blender_operation import BlenderRuntimeOperationState as State
from mediaforge.blender_publication import PublicationIdentity
from mediaforge.blender_publication_recovery import BlenderPublicationRecovery
from mediaforge.blender_publication_generation import MARKER_NAME, create_generation, read_generation
from mediaforge.store import Store
from test_blender_manager import archive_content, archive_fixture, catalog_fixture, runtime_manager


def interrupted(tmp_path: Path, action: str = "install", *, marked: bool = False) -> tuple[Any, Store, str, PublicationIdentity]:
    base, manifest = archive_fixture(tmp_path)
    newer = archive_content("4.5.13")
    catalog = catalog_fixture(tmp_path, base, newer)
    store = Store(tmp_path / "data")
    store.initialize()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=(
        newer if "4.5.13" in str(request.url) else base)))
    manager, resolver = runtime_manager(tmp_path, store, manifest, transport, catalog=catalog)

    async def seed() -> None:
        await manager.start()
        try:
            manager.install()
            await asyncio.gather(*list(manager._tasks.values()))
            if action == "update":
                manager.update()
                await asyncio.gather(*list(manager._tasks.values()))
        finally:
            await manager.stop()

    asyncio.run(seed())
    runtime = resolver.resolve_active()
    assert runtime is not None
    spec = resolver._catalog_specs()[runtime.runtime_id]
    operation = store.create_blender_runtime_operation(runtime.runtime_id, runtime.version,
        Action(action), bytes_total=spec.archive_size_bytes, host_owner="user:16")
    store.bind_blender_runtime_host_job(operation.id, "user:16", "recovery-child")
    store.update_blender_runtime_operation(operation.id, state=State.PROBING)
    generation = None
    if marked:
        staged = resolver.managed_root / ".staging" / operation.id / "candidate"
        # A newly extracted repair candidate does not inherit the installed
        # generation. Keep the old marker on the preserved runtime itself.
        shutil.copytree(runtime.root, staged, ignore=shutil.ignore_patterns(MARKER_NAME))
        generation = create_generation(resolver.managed_root, staged)
    identity = PublicationIdentity(runtime_id=runtime.runtime_id, version=runtime.version, action=action,
        archive_sha256=spec.archive_sha256, executable_sha256=hashlib.sha256(runtime.executable.read_bytes()).hexdigest(),
        previous_active_runtime_id="blender-4.5.9-linux-x64" if action != "install" else None,
        previous_registration_sha256=None,
        previous_executable_sha256=hashlib.sha256(runtime.executable.read_bytes()).hexdigest() if action == "repair" else None,
        recovered_directory=False, generation=generation,
        previous_generation=read_generation(resolver.managed_root, runtime.root) if marked else None)
    store.begin_blender_publication(operation.id, identity)
    if marked:
        runtime.root.rename(tmp_path / "previous-runtime")
        staged.rename(runtime.root)
    store.request_blender_runtime_operation_cancel(operation.id)
    store.initialize()
    return manager, store, operation.id, identity


@pytest.mark.parametrize("action", ["install", "update"])
def test_verified_runtime_recovery_preserves_files_and_commits_outbox(tmp_path: Path, action: str) -> None:
    manager, store, operation_id, identity = interrupted(tmp_path, action)
    resolver = manager.resolver
    executable = resolver.resolve_active().executable
    before = (executable.stat().st_ino, executable.read_bytes(), resolver.registry_path.read_bytes())
    recovery = BlenderPublicationRecovery(store, resolver, manager.preflight_script)
    assert recovery.recover(operation_id) == {"status": "committed", "operation_id": operation_id}
    current = store.get_blender_runtime_operation(operation_id)
    assert current.state == State.READY and current.error_code is None and not current.cancel_requested
    assert current.result["publication_recovered"] and current.result["publication_stop_requests"] == ["cancel"]
    assert store.blender_publication(operation_id).phase == "committed"
    assert store.blender_runtime_host_journal(operation_id, "user:16")["terminal"]["status"] == "succeeded"
    assert (executable.stat().st_ino, executable.read_bytes(), resolver.registry_path.read_bytes()) == before
    with pytest.raises(ValueError):
        recovery.recover(operation_id)


def test_same_version_repair_requires_generation_evidence(tmp_path: Path) -> None:
    manager, store, operation_id, _ = interrupted(tmp_path, "repair")
    result = BlenderPublicationRecovery(store, manager.resolver, manager.preflight_script).recover(operation_id)
    assert result == {"status": "recovery_required", "reason": "repair_generation_unproven"}
    assert store.blender_runtime_host_journal(operation_id, "user:16")["terminal"] is None


@pytest.mark.parametrize("condition", ["valid", "restored_old", "wrong_marker", "probe_changes_marker"])
def test_repair_generation_distinguishes_identical_executable_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, condition: str,
) -> None:
    manager, store, operation_id, identity = interrupted(tmp_path, "repair", marked=True)
    runtime = manager.resolver.resolve_active()
    previous = tmp_path / "previous-runtime"
    old_hash = hashlib.sha256((previous / "install/blender").read_bytes()).hexdigest()
    assert old_hash == identity.executable_sha256 == identity.previous_executable_sha256
    if condition == "restored_old":
        runtime.root.rename(tmp_path / "unadopted-runtime")
        previous.rename(runtime.root)
    elif condition == "wrong_marker":
        (runtime.root / MARKER_NAME).write_text("0" * 32 + "\n")
    elif condition == "probe_changes_marker":
        def change_marker(*args: Any) -> dict[str, Any]:
            (runtime.root / MARKER_NAME).write_text("0" * 32 + "\n")
            return {"version": identity.version, "background": True}
        monkeypatch.setattr("mediaforge.blender_publication_recovery.preflight", change_marker)
    result = BlenderPublicationRecovery(store, manager.resolver, manager.preflight_script).recover(operation_id)
    if condition == "valid":
        assert result["status"] == "committed"
        assert store.get_blender_runtime_operation(operation_id).state == State.READY
        assert hashlib.sha256((previous / "install/blender").read_bytes()).hexdigest() == old_hash
    else:
        assert result["status"] == "recovery_required"
        assert store.blender_runtime_host_journal(operation_id, "user:16")["terminal"] is None


@pytest.mark.parametrize("damage", ["executable", "stamp", "missing", "registry", "symlink", "install_escape", "probe", "probe_change"])
def test_uncertain_recovery_never_claims_success_or_deletes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str) -> None:
    manager, store, operation_id, identity = interrupted(tmp_path)
    resolver = manager.resolver
    runtime = resolver.resolve_active()
    assert runtime is not None
    if damage == "executable":
        runtime.executable.write_bytes(b"tampered")
    elif damage == "stamp":
        (runtime.root / ".runtime.json").write_text("{}")
    elif damage == "missing":
        runtime.executable.unlink()
    elif damage == "registry":
        registry = resolver._read_registry()
        registry["active_runtime_id"] = None
        resolver._write_registry(registry)
    elif damage == "symlink":
        runtime.executable.rename(runtime.executable.with_name("old-blender"))
        runtime.executable.symlink_to("old-blender")
    elif damage == "install_escape":
        outside = tmp_path / "outside-install"
        (runtime.root / "install").rename(outside)
        (runtime.root / "install").symlink_to(outside)
    elif damage == "probe":
        from scripts.blender_runtime import BlenderRuntimeError
        def failed(*args: Any) -> dict[str, Any]:
            raise BlenderRuntimeError("probe rejected")
        monkeypatch.setattr("mediaforge.blender_publication_recovery.preflight", failed)
    else:
        def changed(*args: Any) -> dict[str, Any]:
            runtime.executable.write_bytes(b"changed during probe")
            return {"version": identity.version, "background": True}
        monkeypatch.setattr("mediaforge.blender_publication_recovery.preflight", changed)
    registry_before = resolver.registry_path.read_bytes()
    journal_before = store.blender_publication(operation_id)
    result = BlenderPublicationRecovery(store, resolver, manager.preflight_script).recover(operation_id)
    assert result["status"] == "recovery_required"
    assert store.get_blender_runtime_operation(operation_id).state == State.FAILED
    assert store.blender_runtime_host_journal(operation_id, "user:16")["terminal"] is None
    assert store.blender_publication(operation_id) == journal_before
    assert resolver.registry_path.read_bytes() == registry_before and runtime.root.is_dir()
