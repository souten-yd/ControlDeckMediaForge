from __future__ import annotations

import asyncio
from pathlib import Path
import threading
import time
from typing import Any

import pytest
import httpx

from mediaforge.blender_operation import BlenderRuntimeOperationError, BlenderRuntimeOperationState as State
from mediaforge.blender_setup_host import BlenderSetupHostControl
from mediaforge.host.client import HostApiError, HostIdentity
from mediaforge.store import Store
from test_blender_manager import archive_content, archive_fixture, catalog_fixture, response_transport, runtime_manager


def identity(owner: str = "user:16", token: str = "parent") -> HostIdentity:
    return HostIdentity(f"Bearer {token}", "media-forge", "16", int(time.time()) + 600,
                        frozenset({"jobs.write"}), owner)


class Host:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.refreshes = 0
        self.updates = 0
        self.cancel = False
        self.revoked = False
        self.fail_receipt = False
        self.invalid_credential = False
        self.admission_gate: asyncio.Event | None = None
        self.entered: asyncio.Event | None = None

    async def create_or_attach_job(self, caller: HostIdentity, *, title: str, detached: bool) -> dict[str, Any]:
        assert detached and caller.authorization
        if self.entered is not None:
            self.entered.set()
        if self.admission_gate is not None:
            await self.admission_gate.wait()
        job_id = f"child_{len(self.jobs)}"
        job = {"id": job_id, "kind": "addon.runtime.media-forge", "status": "running",
               "owner_user_id": int((caller.actor_subject or caller.subject).removeprefix("user:"))}
        self.jobs[job_id] = job
        return {"created": True, "job": job, "token_type": "Bearer",
                "access_token": "" if self.invalid_credential else "child-secret",
                "expires_at": int(time.time()) + 30}

    async def refresh_job_credential(self, caller: HostIdentity, job_id: str) -> dict[str, Any]:
        self.refreshes += 1
        return {"access_token": "refreshed-secret", "token_type": "Bearer", "expires_at": int(time.time()) + 600}

    async def job_control(self, caller: HostIdentity, job_id: str) -> dict[str, Any]:
        if self.revoked:
            raise HostApiError("revoked", "revoked", status_code=403)
        return {"host_job_id": job_id, "status": self.jobs[job_id]["status"], "cancel_requested": self.cancel}

    async def update_job(self, caller: HostIdentity, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.updates += 1
        return {}

    async def reconcile_job_terminal(self, caller: HostIdentity, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.fail_receipt:
            raise HostApiError("unreachable", "unreachable")
        self.jobs[job_id].update(payload)
        return {"host_job_id": job_id, "status": payload["status"],
                "disposition": "applied", "terminal_matches": True}


def setup(tmp_path: Path) -> tuple[Any, Store, Host]:
    content, manifest = archive_fixture(tmp_path)
    store = Store(tmp_path / "data")
    store.initialize()
    manager, _ = runtime_manager(tmp_path, store, manifest, response_transport(content))
    host = Host()
    manager.host_control = BlenderSetupHostControl(manager, host)  # type: ignore[arg-type]
    manager.host_control.poll_sec = 0.01
    return manager, store, host


def test_real_manager_install_refresh_terminal_and_offloop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager, store, host = setup(tmp_path)
    for name in ("create_blender_runtime_operation", "blender_runtime_host_journal",
                 "bind_blender_runtime_host_job", "reconcile_blender_runtime_terminal",
                 "get_blender_runtime_operation", "check_blender_runtime_operation_owner"):
        original = getattr(store, name)
        def checked(*args: Any, _original: Any = original, **kwargs: Any) -> Any:
            with pytest.raises(RuntimeError, match="no running event loop"):
                asyncio.get_running_loop()
            return _original(*args, **kwargs)
        monkeypatch.setattr(store, name, checked)

    async def run() -> str:
        await manager.start()
        operation = await manager.request("install", identity=identity())
        await asyncio.gather(*list(manager._tasks.values()))
        await manager.stop()
        return operation.id

    operation_id = asyncio.run(run())
    assert store.get_blender_runtime_operation(operation_id).state == State.READY
    journal = store.blender_runtime_host_journal(operation_id, "user:16")
    assert journal["sent"] and journal["terminal"]["status"] == "succeeded"
    assert host.refreshes == 1 and len(host.jobs) == 1
    assert "secret" not in str(journal)


@pytest.mark.parametrize("revoked", [False, True])
def test_host_cancel_or_revocation_drains_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revoked: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    manager, store, host = setup(tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_control = host.job_control

    async def control(caller: HostIdentity, job_id: str) -> dict[str, Any]:
        if host.revoked:
            raise HostApiError("host_request_rejected", "DO_NOT_LOG_BEARER", status_code=403) from httpx.ReadError("DO_NOT_LOG_TRANSPORT")
        return await original_control(caller, job_id)

    monkeypatch.setattr(host, "job_control", control)

    async def worker(operation_id: str) -> None:
        await manager._runtime_io(store.update_blender_runtime_operation, operation_id, state=State.PREFLIGHT)
        def stage() -> None:
            entered.set()
            assert release.wait(5)
            finished.set()
        await manager._runtime_io(stage)

    monkeypatch.setattr(manager, "_run", worker)

    async def run() -> str:
        await manager.start()
        operation = await manager.request("install", identity=identity())
        assert await asyncio.to_thread(entered.wait, 5)
        host.revoked, host.cancel = revoked, not revoked
        await asyncio.sleep(0.06)
        assert operation.id in manager._tasks and not finished.is_set()
        release.set()
        await asyncio.gather(*list(manager._tasks.values()))
        await manager.stop()
        return operation.id

    operation_id = asyncio.run(run())
    record = store.get_blender_runtime_operation(operation_id)
    assert finished.is_set()
    assert record.state == (State.FAILED if revoked else State.CANCELED)
    assert record.error_code == ("host_context_lost" if revoked else None)
    assert store.blender_runtime_host_journal(operation_id, "user:16")["sent"]
    assert "DO_NOT_LOG_BEARER" not in caplog.text and "child-secret" not in caplog.text
    assert "DO_NOT_LOG_TRANSPORT" not in caplog.text
    if revoked:
        assert "host_request_rejected (HTTP 403; cause=ReadError)" in caplog.text


@pytest.mark.parametrize("revoked", [False, True])
def test_repair_cancel_during_registration_restores_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revoked: bool,
) -> None:
    manager, store, host = setup(tmp_path)
    entered, release = threading.Event(), threading.Event()

    async def run() -> None:
        await manager.start()
        initial = await manager.request("install", identity=identity())
        await asyncio.gather(*list(manager._tasks.values()))
        assert store.get_blender_runtime_operation(initial.id).state == State.READY
        destination = manager.resolver.managed_root / initial.runtime_id
        executable = destination / "install/blender"
        old_inode, old_bytes = executable.stat().st_ino, executable.read_bytes()
        registry = manager.resolver.registry_path.read_bytes()
        original = manager.resolver.register_managed

        def held_registration(**kwargs: Any) -> Any:
            value = original(**kwargs)
            entered.set()
            assert release.wait(5)
            return value

        monkeypatch.setattr(manager.resolver, "register_managed", held_registration)
        try:
            operation = await manager.request("repair", initial.runtime_id, identity=identity())
            assert await asyncio.to_thread(entered.wait, 5)
            host.revoked, host.cancel = revoked, not revoked
            async with asyncio.timeout(3):
                while not await asyncio.to_thread(store.blender_runtime_operation_cancel_requested, operation.id):
                    await asyncio.sleep(.01)
            release.set()
            await asyncio.gather(*list(manager._tasks.values()))
            result = store.get_blender_runtime_operation(operation.id)
            assert result.state == (State.FAILED if revoked else State.CANCELED)
            assert result.error_code == ("host_context_lost" if revoked else None)
            assert executable.stat().st_ino == old_inode and executable.read_bytes() == old_bytes
            assert manager.resolver.registry_path.read_bytes() == registry
            assert not any((manager.resolver.managed_root / ".staging").iterdir())
            journal = store.blender_runtime_host_journal(operation.id, "user:16")
            assert journal["terminal"]["status"] == ("failed" if revoked else "canceled")
            assert journal["sent"] is True
        finally:
            release.set()
            await manager.stop()

    asyncio.run(run())


@pytest.mark.parametrize("action", ["install", "update"])
@pytest.mark.parametrize("recovered", [False, True])
@pytest.mark.parametrize("revoked", [False, True])
def test_install_registration_cancel_preserves_registry_and_previous_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, recovered: bool, revoked: bool,
) -> None:
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
    entered, release = threading.Event(), threading.Event()

    async def run() -> None:
        await manager.start()
        original = resolver.register_managed
        try:
            if action == "update":
                initial = await manager.request("install", identity=identity())
                await asyncio.gather(*list(manager._tasks.values()))
                assert store.get_blender_runtime_operation(initial.id).state == State.READY
            before = resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None
            target = resolver.managed_root / ("blender-4.5.13-linux-x64" if action == "update" else "blender-4.5.9-linux-x64")
            executable = target / "install/blender"
            if recovered:
                seeded = await manager.request(action, identity=identity())
                await asyncio.gather(*list(manager._tasks.values()))
                assert store.get_blender_runtime_operation(seeded.id).state == State.READY
                old_inode, old_bytes = executable.stat().st_ino, executable.read_bytes()
                # Emulate an already probed directory left before registry commit.
                if before is None:
                    resolver.registry_path.unlink()
                else:
                    resolver.registry_path.write_bytes(before)

            def held_registration(**kwargs: Any) -> Any:
                entered.set()
                assert release.wait(5)
                return original(**kwargs)

            monkeypatch.setattr(resolver, "register_managed", held_registration)
            operation = await manager.request(action, identity=identity())
            assert await asyncio.to_thread(entered.wait, 5)
            host.revoked, host.cancel = revoked, not revoked
            async with asyncio.timeout(3):
                while not await asyncio.to_thread(store.blender_runtime_operation_cancel_requested, operation.id):
                    await asyncio.sleep(.01)
            release.set()
            await asyncio.gather(*list(manager._tasks.values()))
            result = store.get_blender_runtime_operation(operation.id)
            assert result.state == (State.FAILED if revoked else State.CANCELED)
            assert result.error_code == ("host_context_lost" if revoked else None)
            assert (resolver.registry_path.read_bytes() if resolver.registry_path.exists() else None) == before
            if recovered:
                assert executable.stat().st_ino == old_inode and executable.read_bytes() == old_bytes
            else:
                assert not target.exists()
            assert not any((resolver.managed_root / ".staging").iterdir())
            journal = store.blender_runtime_host_journal(operation.id, "user:16")
            assert journal["sent"] and journal["terminal"]["status"] == ("failed" if revoked else "canceled")
            host.revoked = host.cancel = False
            monkeypatch.setattr(resolver, "register_managed", original)
            retry = await manager.request(action, identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
            assert store.get_blender_runtime_operation(retry.id).state == State.READY
            assert resolver.resolve_active().runtime_id == operation.runtime_id
        finally:
            release.set()
            await manager.stop()

    asyncio.run(run())


def test_disconnect_duplicate_and_foreign_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager, store, host = setup(tmp_path)

    async def run() -> str:
        host.admission_gate, host.entered = asyncio.Event(), asyncio.Event()
        worker_gate = asyncio.Event()
        async def worker(operation_id: str) -> None:
            await worker_gate.wait()
            await manager._runtime_io(store.update_blender_runtime_operation, operation_id, state=State.READY)
        monkeypatch.setattr(manager, "_run", worker)
        await manager.start()
        task = asyncio.create_task(manager.request("install", identity=identity()))
        await host.entered.wait()
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        host.admission_gate.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        operation = await manager.request("install", identity=identity())
        assert len(host.jobs) == 1
        with pytest.raises(BlenderRuntimeOperationError):
            await manager.request("install", identity=identity("user:17"))
        with pytest.raises(BlenderRuntimeOperationError):
            await manager.request("cancel", operation.id)
        with pytest.raises(BlenderRuntimeOperationError):
            await manager.request("cancel", operation.id, identity=identity("user:17"))
        worker_gate.set()
        await asyncio.gather(*list(manager._tasks.values()))
        await manager.stop()
        return operation.id

    operation_id = asyncio.run(run())
    assert store.blender_runtime_host_journal(operation_id, "user:16")["sent"]


def test_invalid_child_credential_fails_without_starting_runtime(tmp_path: Path) -> None:
    manager, store, host = setup(tmp_path)
    host.invalid_credential = True

    async def run() -> None:
        await manager.start()
        with pytest.raises(BlenderRuntimeOperationError, match="admission failed"):
            await manager.request("install", identity=identity())
        assert not manager._tasks
        await manager.stop()
    asyncio.run(run())
    operation = store.list_blender_runtime_operations()[0]
    assert operation.state == State.FAILED
    assert store.blender_runtime_host_journal(operation.id, "user:16")["sent"]


def test_pending_terminal_reconciles_only_with_fresh_owner(tmp_path: Path) -> None:
    manager, store, host = setup(tmp_path)
    host.fail_receipt = True

    async def run() -> str:
        await manager.start()
        operation = await manager.request("install", identity=identity())
        await asyncio.gather(*list(manager._tasks.values()))
        assert not (await manager._runtime_io(store.blender_runtime_host_journal, operation.id, "user:16"))["sent"]
        host.fail_receipt = False
        await manager.host_control.reconcile_pending(identity("user:17"))
        assert not (await manager._runtime_io(store.blender_runtime_host_journal, operation.id, "user:16"))["sent"]
        await manager.host_control.reconcile_pending(identity(token="fresh"))
        await manager.stop()
        return operation.id
    operation_id = asyncio.run(run())
    assert store.blender_runtime_host_journal(operation_id, "user:16")["sent"]


def test_queued_work_renews_and_can_be_canceled_from_host(tmp_path: Path) -> None:
    manager, store, host = setup(tmp_path)
    async def run() -> str:
        await manager.start()
        await manager._guard.acquire()
        try:
            operation = await manager.request("install", identity=identity())
            await asyncio.sleep(.06)
            current = await manager._runtime_io(store.get_blender_runtime_operation, operation.id)
            assert current.state == State.QUEUED and host.refreshes == 1 and host.updates > 0
            host.cancel = True
            await asyncio.gather(*list(manager._tasks.values()))
        finally:
            manager._guard.release()
            await manager.stop()
        return operation.id
    operation_id = asyncio.run(run())
    assert store.get_blender_runtime_operation(operation_id).state == State.CANCELED
    assert store.blender_runtime_host_journal(operation_id, "user:16")["sent"]


def test_shutdown_drains_owned_setup_with_repeated_cancellation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager, store, host = setup(tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    async def worker(operation_id: str) -> None:
        await manager._runtime_io(store.update_blender_runtime_operation, operation_id, state=State.PROBING)
        def stage() -> None:
            entered.set()
            assert release.wait(5)
            finished.set()
        await manager._runtime_io(stage)
    monkeypatch.setattr(manager, "_run", worker)
    async def run() -> str:
        await manager.start()
        operation = await manager.request("install", identity=identity())
        assert await asyncio.to_thread(entered.wait, 5)
        stopping = asyncio.create_task(manager.stop())
        await asyncio.sleep(.01)
        for _ in range(3):
            stopping.cancel()
            await asyncio.sleep(.01)
            assert not stopping.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await stopping
        assert not manager._tasks and not manager.host_control.executions
        return operation.id
    operation_id = asyncio.run(run())
    assert finished.is_set()
    assert store.get_blender_runtime_operation(operation_id).error_code == "host_context_lost"
    assert store.blender_runtime_host_journal(operation_id, "user:16")["sent"]


@pytest.mark.parametrize("expires", [0, True, 2**60])
def test_bad_refresh_stops_queued_work_without_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, expires: int) -> None:
    manager, store, host = setup(tmp_path)
    async def refresh(*args: Any) -> dict[str, Any]:
        return {"token_type": "Bearer", "access_token": "bad", "expires_at": expires}
    monkeypatch.setattr(host, "refresh_job_credential", refresh)
    async def run() -> str:
        await manager.start()
        await manager._guard.acquire()
        try:
            operation = await manager.request("install", identity=identity())
            await asyncio.gather(*list(manager._tasks.values()))
        finally:
            manager._guard.release()
            await manager.stop()
        return operation.id
    operation_id = asyncio.run(run())
    assert store.get_blender_runtime_operation(operation_id).state == State.FAILED
    assert store.get_blender_runtime_operation(operation_id).error_code == "host_context_lost"
    assert not (manager.resolver.managed_root / 'blender-4.5.9-linux-x64').exists()
