from __future__ import annotations

import asyncio
import os
from pathlib import Path
import threading
from typing import Any

import httpx
import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationState as State
from mediaforge.blender_publication_generation import read_generation
from mediaforge.blender_setup_host import BlenderSetupHostControl
from mediaforge.store import Store
from test_blender_manager import archive_fixture, archive_content, catalog_fixture, runtime_manager
from test_blender_setup_host import Host, identity


def setup(tmp_path: Path):
    base, manifest = archive_fixture(tmp_path)
    newer = archive_content("4.5.13")
    catalog = catalog_fixture(tmp_path, base, newer)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=(
        newer if "4.5.13" in str(request.url) else base)))
    store = Store(tmp_path / "data")
    store.initialize()
    manager, resolver = runtime_manager(tmp_path, store, manifest, transport, catalog=catalog)
    host = Host()
    manager.host_control = BlenderSetupHostControl(manager, host)  # type: ignore[arg-type]
    manager.host_control.poll_sec = .01
    return manager, resolver, store, host


@pytest.mark.parametrize("action", ["install", "update"])
@pytest.mark.parametrize("recovered", [False, True])
@pytest.mark.parametrize("revoked", [False, True])
@pytest.mark.parametrize("boundary", ["begin", "registered"])
def test_late_host_stop_preserves_actual_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str,
    recovered: bool, revoked: bool, boundary: str,
) -> None:
    manager, resolver, store, host = setup(tmp_path)
    entered, release = threading.Event(), threading.Event()

    async def run() -> None:
        await manager.start()
        try:
            if action == "update":
                initial = await manager.request("install", identity=identity())
                await asyncio.gather(*list(manager._tasks.values()))
                assert store.get_blender_runtime_operation(initial.id).state == State.READY
            before = resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None
            if recovered:
                seeded = await manager.request(action, identity=identity())
                await asyncio.gather(*list(manager._tasks.values()))
                assert store.get_blender_runtime_operation(seeded.id).state == State.READY
                if before is None:
                    resolver.registry_path.unlink()
                else:
                    resolver.registry_path.write_bytes(before)
            target, name = ((manager, "_begin_publication") if boundary == "begin"
                            else (resolver, "register_managed"))
            original = getattr(target, name)

            def held(*args: Any, **kwargs: Any) -> Any:
                result = original(*args, **kwargs)
                entered.set()
                assert release.wait(5)
                return result

            monkeypatch.setattr(target, name, held)
            operation = await manager.request(action, identity=identity())
            assert await asyncio.to_thread(entered.wait, 5)
            host.revoked, host.cancel = revoked, not revoked
            async with asyncio.timeout(3):
                while not (await asyncio.to_thread(store.blender_publication, operation.id)).stop_requests:
                    await asyncio.sleep(.01)
            assert not store.blender_runtime_operation_cancel_requested(operation.id)
            assert store.get_blender_runtime_operation(operation.id).error_code is None
            release.set()
            await asyncio.gather(*list(manager._tasks.values()))
            result = store.get_blender_runtime_operation(operation.id)
            assert result.state == State.READY and result.error_code is None and not result.cancel_requested
            assert result.result["publication_stop_requests"] == ["host_context_lost" if revoked else "cancel"]
            publication = store.blender_publication(operation.id)
            assert publication.phase == "committed"
            root = resolver.managed_root / operation.runtime_id
            assert read_generation(resolver.managed_root, root) == publication.identity.generation
            assert resolver.resolve_active().runtime_id == operation.runtime_id
            assert store.blender_runtime_host_journal(operation.id, "user:16")["terminal"]["status"] == "succeeded"
            assert not any((resolver.managed_root / ".staging").iterdir())
        finally:
            release.set()
            await manager.stop()

    asyncio.run(run())


@pytest.mark.parametrize("fault", ["rename", "register_before", "register_after", "complete_before", "complete_after"])
def test_uncertain_publication_is_verified_or_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    manager, resolver, store, _host = setup(tmp_path)

    async def run() -> None:
        await manager.start()
        try:
            if fault == "rename":
                original = os.replace
                def fail_rename(source: Any, destination: Any) -> None:
                    if Path(source).name == "candidate":
                        raise OSError("injected rename failure")
                    original(source, destination)
                monkeypatch.setattr(os, "replace", fail_rename)
            else:
                target, name = ((resolver, "register_managed") if fault.startswith("register")
                                else (store, "complete_blender_publication"))
                original = getattr(target, name)
                def fail_call(*args: Any, **kwargs: Any) -> Any:
                    if fault.endswith("after"):
                        original(*args, **kwargs)
                    raise OSError("injected lost acknowledgement")
                monkeypatch.setattr(target, name, fail_call)
            operation = await manager.request("install", identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
            publication = store.blender_publication(operation.id)
            result = store.get_blender_runtime_operation(operation.id)
            journal = store.blender_runtime_host_journal(operation.id, "user:16")
            if fault in {"rename", "register_before"}:
                assert publication.phase == "recovery_required"
                assert result.state == State.FAILED and result.error_code == "blender_publication_recovery_required"
                assert journal["terminal"] is None
                candidate = (resolver.managed_root / ".staging" / operation.id / "candidate"
                             if fault == "rename" else resolver.managed_root / operation.runtime_id)
                assert read_generation(resolver.managed_root, candidate) == publication.identity.generation
                assert (candidate / "install/blender").is_file()
                store.initialize()
                assert store.blender_publication(operation.id).phase == "recovery_required"
            else:
                assert publication.phase == "committed" and result.state == State.READY
                assert result.error_code is None and not result.cancel_requested
                assert resolver.resolve_active().runtime_id == operation.runtime_id
                assert journal["terminal"]["status"] == "succeeded"
                assert not any((resolver.managed_root / ".staging").iterdir())
        finally:
            await manager.stop()

    asyncio.run(run())
