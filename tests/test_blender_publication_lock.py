from __future__ import annotations

import asyncio
import fcntl
from pathlib import Path
import threading

import httpx
import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationState as State
from mediaforge.store import Store
from test_blender_manager import archive_fixture, archive_content, catalog_fixture, runtime_manager, wait_terminal


@pytest.mark.parametrize("action", ["install", "update", "repair"])
@pytest.mark.parametrize("cancel", [False, True])
def test_registry_wait_does_not_publish_or_replace_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, cancel: bool,
) -> None:
    base, manifest = archive_fixture(tmp_path)
    newer = archive_content("4.5.13")
    catalog = catalog_fixture(tmp_path, base, newer)
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, content=newer if "4.5.13" in str(request.url) else base))
    store = Store(tmp_path / "data")
    store.initialize()
    manager, resolver = runtime_manager(tmp_path, store, manifest, transport, catalog=catalog)

    async def run() -> None:
        await manager.start()
        if action != "install":
            initial = manager.install()
            assert (await wait_terminal(store, initial.id)).state == State.READY
        runtime_id = "blender-4.5.13-linux-x64" if action == "update" else "blender-4.5.9-linux-x64"
        destination = resolver.managed_root / runtime_id
        executable = destination / "install/blender"
        before = (executable.stat().st_ino, executable.read_bytes()) if action == "repair" else None
        registry = resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None
        lock_path = resolver.registry_path.with_suffix(resolver.registry_path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        entered = threading.Event()
        original = fcntl.flock
        loop_thread = threading.get_ident()

        def observed_flock(descriptor: object, mode: int) -> None:
            if mode == fcntl.LOCK_EX:
                assert threading.get_ident() != loop_thread
                entered.set()
            original(descriptor, mode)

        with lock_path.open("a") as held:
            original(held, fcntl.LOCK_EX)
            monkeypatch.setattr(fcntl, "flock", observed_flock)
            try:
                operation = manager.repair(runtime_id) if action == "repair" else getattr(manager, action)()
                assert await asyncio.to_thread(entered.wait, 5)
                assert not manager._tasks[operation.id].done()
                if before is None:
                    assert not destination.exists(), "runtime published before acquiring registry lock"
                else:
                    assert (executable.stat().st_ino, executable.read_bytes()) == before
                assert (resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None) == registry
                assert not list((resolver.managed_root / ".staging").glob("previous-*"))
                if cancel:
                    await asyncio.to_thread(manager.cancel, operation.id)
            finally:
                original(held, fcntl.LOCK_UN)
                monkeypatch.setattr(fcntl, "flock", original)
        try:
            result = await wait_terminal(store, operation.id)
            assert result.state == (State.CANCELED if cancel else State.READY)
            if cancel:
                assert (resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None) == registry
                if before is None:
                    assert not destination.exists()
                else:
                    assert (executable.stat().st_ino, executable.read_bytes()) == before
            else:
                assert resolver.resolve_active().runtime_id == runtime_id
            assert not any((resolver.managed_root / ".staging").iterdir())
        finally:
            await manager.stop()

    asyncio.run(run())
