from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from mediaforge.blender_manager import RUNTIME_ID
from mediaforge.blender_operation import BlenderRuntimeOperationState
from mediaforge.scenes import SceneCatalog
from mediaforge.store import Store
from test_blender_manager import (
    archive_content, archive_fixture, catalog_fixture, catalog_transport,
    runtime_manager, wait_terminal,
    response_transport,
)
from test_scenes import _revision_assets, _revision_input


@pytest.mark.parametrize("fault", ["hash", "preflight_space", "extraction_space"])
def test_failed_repair_keeps_old_runtime_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    async def scenario() -> None:
        content, manifest = archive_fixture(tmp_path)
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(tmp_path, store, manifest, response_transport(content))
        await manager.start()
        try:
            assert (await wait_terminal(store, manager.install().id)).state == BlenderRuntimeOperationState.READY
            executable = resolver.resolve_active().executable
            original_bytes, inode = executable.read_bytes(), executable.stat().st_ino
            registration = resolver.registry_path.read_bytes()
            archive = manager.download_root / manager.spec.archive_name
            original_disk_usage = shutil.disk_usage
            if fault == "hash":
                archive.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
            else:
                values = iter((0,) if fault == "preflight_space" else (10_000_000_000, 0))
                monkeypatch.setattr("mediaforge.blender_manager.shutil.disk_usage",
                                    lambda _path: SimpleNamespace(free=next(values)))
            failed = await wait_terminal(store, manager.repair(RUNTIME_ID).id)
            assert failed.state == BlenderRuntimeOperationState.FAILED
            assert failed.error_code == ("blender_runtime_install_failed" if fault == "hash" else "insufficient_disk")
            assert executable.read_bytes() == original_bytes and executable.stat().st_ino == inode
            assert resolver.registry_path.read_bytes() == registration
            assert not (resolver.managed_root / ".staging" / failed.id).exists()
            monkeypatch.setattr("mediaforge.blender_manager.shutil.disk_usage", original_disk_usage)
            archive.write_bytes(content)
            repaired = await wait_terminal(store, manager.repair(RUNTIME_ID).id)
            assert repaired.state == BlenderRuntimeOperationState.READY
            assert executable.read_bytes() == original_bytes and executable.stat().st_ino != inode
            assert resolver.registry_path.read_bytes() == registration
        finally:
            await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["none", "missing_ack", "invalid_ack", "active", "catalog"])
@pytest.mark.parametrize("journal_state", ["queued", "preflight", "deleting"])
def test_history_removal_restart_rechecks_acknowledgement_and_identity(
    tmp_path: Path, change: str, journal_state: str,
) -> None:
    async def scenario() -> None:
        base, manifest = archive_fixture(tmp_path)
        recommended = archive_content("4.5.13")
        catalog = catalog_fixture(tmp_path, base, recommended)
        transport = catalog_transport({"4.5.9": base, "4.5.13": recommended})
        store = Store(tmp_path / "data")
        store.initialize()
        manager, resolver = runtime_manager(tmp_path, store, manifest, transport, catalog=catalog)
        await manager.start()
        assert (await wait_terminal(store, manager.install().id)).state == BlenderRuntimeOperationState.READY
        assert (await wait_terminal(store, manager.update().id)).state == BlenderRuntimeOperationState.READY
        source, glb, image = _revision_assets(store, tmp_path)
        document, revision = SceneCatalog(store).create("user:7", name="History", tags=[], collection=None,
            revision=_revision_input(source, glb, image))
        preview = await manager.removal_preview(RUNTIME_ID)
        operation = await asyncio.to_thread(manager._admit_removal, RUNTIME_ID, preview["confirmation_fingerprint"], True)
        store.update_blender_runtime_operation(operation.id, state=BlenderRuntimeOperationState(journal_state))
        await manager.stop()  # Durable acceptance exists but no executor was spawned.
        if change in {"missing_ack", "invalid_ack"}:
            result = dict(operation.result)
            result.pop("acknowledge_history")
            if change == "invalid_ack":
                result["acknowledge_history"] = "true"
            store.update_blender_runtime_operation(operation.id, result=result)
        elif change == "active":
            resolver.activate(RUNTIME_ID)
        elif change == "catalog":
            value = json.loads(catalog.read_text())
            value["runtimes"][0]["spec"]["archive_sha256"] = "f" * 64
            catalog.write_text(json.dumps(value))
            manifest.write_text(json.dumps(value["runtimes"][0]["spec"]))
        reopened = Store(tmp_path / "data")
        reopened.initialize()
        restarted, runtimes = runtime_manager(tmp_path, reopened, manifest, transport, catalog=catalog)
        await restarted.start()
        try:
            result = await wait_terminal(reopened, operation.id)
            if change == "none":
                assert result.state == BlenderRuntimeOperationState.READY
                assert result.result["acknowledge_history"] is True
                assert result.result["removal_preview"] == preview
                assert not (runtimes.managed_root / RUNTIME_ID).exists()
            else:
                assert result.state == BlenderRuntimeOperationState.FAILED
                assert (runtimes.managed_root / RUNTIME_ID / "install/blender").is_file()
                assert result.error_code == {
                    "missing_ack": "blender_runtime_in_use",
                    "invalid_ack": "blender_runtime_confirmation_invalid",
                    "active": "blender_runtime_remove_changed",
                    "catalog": "blender_runtime_remove_changed",
                }[change]
            assert SceneCatalog(reopened).get("user:7", document.id) == (document, [revision])
        finally:
            await restarted.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize("field,value", [("archive_sha256", "e" * 64), ("archive_size_bytes", 999)])
def test_exact_install_restart_refuses_changed_archive(tmp_path: Path, field: str, value: object) -> None:
    async def scenario() -> None:
        base, manifest = archive_fixture(tmp_path)
        recommended = archive_content("4.5.13")
        catalog = catalog_fixture(tmp_path, base, recommended)
        store = Store(tmp_path / "data")
        store.initialize()
        transport = catalog_transport({"4.5.9": base, "4.5.13": recommended})
        manager, _ = runtime_manager(tmp_path, store, manifest, transport, catalog=catalog)
        operation = await asyncio.to_thread(manager._admit_exact, RUNTIME_ID)
        modified = json.loads(catalog.read_text())
        modified["runtimes"][0]["spec"][field] = value
        catalog.write_text(json.dumps(modified))
        manifest.write_text(json.dumps(modified["runtimes"][0]["spec"]))
        restarted, resolver = runtime_manager(tmp_path, store, manifest, transport, catalog=catalog)
        await restarted.start()
        try:
            result = await wait_terminal(store, operation.id)
            assert result.state == BlenderRuntimeOperationState.FAILED
            assert result.error_code == "blender_runtime_catalog_changed"
            assert not (resolver.managed_root / RUNTIME_ID).exists()
        finally:
            await restarted.stop()
    asyncio.run(scenario())
