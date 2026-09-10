from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
import threading
import time
from typing import Any

import pytest

from mediaforge.domain import ErrorDetail, JobRequest, JobStatus
from mediaforge.host.client import HostApiError, HostIdentity
from mediaforge.host.jobs import HostExecution
from mediaforge.hosted_job_terminals import HostedJobTerminals
from mediaforge.jobs import JobManager
from mediaforge.store import Store
from test_host_execution import generate_input, host_client
from conftest import wait_terminal


def identity() -> HostIdentity:
    return HostIdentity("Bearer secret", "media-forge", "7", int(time.time())+600,
                        frozenset({"jobs.write"}), "user:7")


def seeded(tmp_path: Path, *, terminal: bool = True) -> tuple[Store, str]:
    store = Store(tmp_path)
    store.initialize()
    job = store.create_job(JobRequest.model_validate(generate_input("outbox")), host_managed=True,
                           owned_host_binding=("owned-host", "7"))
    if terminal:
        store.update_job(job.id, status=JobStatus.FAILED, error=ErrorDetail(code="worker_failed", message="actual failure"))
    return store, job.id


@pytest.mark.parametrize("mode", ["ok", "network", "wrong_job", "wrong_status", "false_applied", "mismatch", "malformed"])
def test_receipt_validation_and_restart(tmp_path: Path, mode: str) -> None:
    store, job_id = seeded(tmp_path)
    # No payload was captured before the restart; local terminal truth survives.
    reopened = Store(tmp_path)
    reopened.initialize()
    calls: list[dict[str, Any]] = []
    class Host:
        async def reconcile_job_terminal(self, auth: HostIdentity, host_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            assert host_id == "owned-host" and payload == {"status":"failed","error":"actual failure"}
            calls.append(payload)
            if mode == "network":
                raise HostApiError("host_unreachable", "Unavailable", status_code=503)
            return {"host_job_id":"other" if mode=="wrong_job" else host_id,
                    "status":"succeeded" if mode in {"wrong_status","mismatch"} else "failed",
                    "disposition":"already_terminal" if mode=="mismatch" else "applied",
                    "terminal_matches":"true" if mode=="malformed" else mode not in {"mismatch","false_applied"},
                    "ignored":"not persisted"}
    async def run() -> None:
        loop_thread = threading.get_ident()
        original = reopened.pending_owned_job_terminals
        def checked(owner: str, after: str = "") -> list[str]:
            assert threading.get_ident() != loop_thread
            return original(owner, after)
        reopened.pending_owned_job_terminals = checked
        outbox = HostedJobTerminals(reopened, Host(), lambda _: False)  # type: ignore[arg-type]
        await outbox.reconcile(identity())
    asyncio.run(run())
    value = store.owned_job_terminal(job_id)
    assert value is not None and value["sent"] is (mode=="ok")
    assert (value["receipt"] is not None) is (mode in {"ok","mismatch"})
    if value["receipt"]:
        assert "ignored" not in value["receipt"]
    assert len(calls)==1
    assert b"Bearer secret" not in store.db_path.read_bytes()


@pytest.mark.parametrize("mode", ["other_owner", "expired", "no_capability", "standalone", "other_addon", "active"])
def test_authority_and_live_job_are_not_replayed(tmp_path: Path, mode: str) -> None:
    store, job_id = seeded(tmp_path)
    auth = identity()
    auth = {
        "other_owner": replace(auth,subject="8",actor_subject="user:8"),
        "expired": replace(auth,expires_at=0),
        "no_capability": replace(auth,granted_capabilities=frozenset()),
        "standalone": replace(auth,authorization=""),
        "other_addon": replace(auth,addon_id="other"),
    }.get(mode, auth)
    calls: list[object] = []
    class Host:
        async def reconcile_job_terminal(self, *args: Any) -> dict[str, Any]:
            calls.append(args)
            raise AssertionError("must not reach Host")
    asyncio.run(HostedJobTerminals(store, Host(), lambda _: mode=="active").reconcile(auth))  # type: ignore[arg-type]
    assert calls == []
    assert store.owned_job_terminal(job_id)["sent"] is False


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING])
def test_active_crash_recovers_without_storing_credentials(tmp_path: Path, status: JobStatus) -> None:
    store, job_id = seeded(tmp_path, terminal=False)
    store.update_job(job_id, status=status)
    Store(tmp_path).initialize()
    value = store.owned_job_terminal(job_id)
    assert value is not None and value["payload"]["status"]=="failed"
    assert value["payload"]["error"] == store.get_job(job_id).error.message
    assert not value["sent"]


def test_pending_pages_and_attached_jobs_are_excluded(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.initialize()
    request = JobRequest.model_validate(generate_input("outbox"))
    for index in range(52):
        job = store.create_job(request, host_managed=True, owned_host_binding=(f"host-{index}","7"))
        store.update_job(job.id,status=JobStatus.CANCELED)
    attached = store.create_job(request,host_managed=True)
    store.update_job(attached.id,status=JobStatus.SUCCEEDED)
    page = store.pending_owned_job_terminals("7")
    assert len(page)==50 and len(store.pending_owned_job_terminals("7",page[-1]))==2
    assert store.owned_job_terminal(attached.id) is None


def test_workspace_terminal_failure_is_reconciled_on_reconnect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, headers, state = host_client(tmp_path, token="valid-user")
    manager = client.app.state.jobs
    host = manager.host_client
    original = host.update_job
    receipts: list[str] = []
    async def update(auth: HostIdentity, host_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("status"):
            raise HostApiError("host_unreachable", "terminal unavailable", status_code=503)
        return await original(auth,host_id,payload)
    async def reconcile(auth: HostIdentity, host_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert auth.actor_subject=="user:7" and payload["status"]=="succeeded"
        receipts.append(host_id)
        return {"host_job_id":host_id,"status":"succeeded","disposition":"applied","terminal_matches":True}
    monkeypatch.setattr(host,"update_job",update)
    monkeypatch.setattr(host,"reconcile_job_terminal",reconcile)
    with client:
        with client.websocket_connect('/ws',headers=headers) as socket:
            socket.send_json({'id':'create','method':'jobs.create','params':generate_input('ordinary outbox')})
            job_id=socket.receive_json()['result']['id']
            async def finished() -> None:
                async with asyncio.timeout(10):
                    while job_id in manager._host_executions:
                        await asyncio.sleep(.01)
            client.portal.call(finished)
        value=manager.store.owned_job_terminal(job_id)
        assert value and value['payload']['status']=='succeeded' and not value['sent']
        with client.websocket_connect('/ws',headers=headers):
            async def delivered() -> None:
                async with asyncio.timeout(5):
                    while not (await asyncio.to_thread(manager.store.owned_job_terminal,job_id))['sent']:
                        await asyncio.sleep(.01)
            client.portal.call(delivered)
        assert receipts==['host-created-1']


def test_disconnected_admission_is_drained_off_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Store(tmp_path)
    store.initialize()
    entered, release = threading.Event(), threading.Event()
    original = store.create_job
    def delayed(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(store,"create_job",delayed)
    async def run() -> None:
        manager = object.__new__(JobManager)
        manager.store, manager.host_client = store, object()
        manager._host_executions, manager._queue = {}, asyncio.Queue()
        request = JobRequest.model_validate(generate_input("disconnected admission"))
        task = asyncio.create_task(manager.submit_hosted(request,HostExecution(identity(),"owned-host","interactive",True),profile_snapshot={}))
        try:
            async with asyncio.timeout(2):
                while not entered.is_set():
                    await asyncio.sleep(.001)
            task.cancel()
            await asyncio.sleep(.01)
            assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        job_id = manager._queue.get_nowait()
        assert job_id in manager._host_executions
        assert (await asyncio.to_thread(store.get_job,job_id)).status==JobStatus.QUEUED
    asyncio.run(run())


def test_concurrent_scheduling_does_not_duplicate_replay(tmp_path: Path) -> None:
    store, job_id = seeded(tmp_path)
    calls: list[str] = []
    class Host:
        async def reconcile_job_terminal(self, auth: HostIdentity, host_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            calls.append(host_id)
            await asyncio.sleep(.02)
            return {"host_job_id":host_id,"status":"failed","disposition":"applied","terminal_matches":True}
    async def run() -> None:
        outbox = HostedJobTerminals(store,Host(),lambda _: False)  # type: ignore[arg-type]
        for _ in range(3):
            outbox.schedule(identity())
        await asyncio.gather(*list(outbox.tasks.values()))
        await outbox.stop()
        outbox.schedule(identity())
        assert not outbox.tasks
    asyncio.run(run())
    assert calls==['owned-host'] and store.owned_job_terminal(job_id)['sent']


def test_orderly_shutdown_drains_settled_terminal_notification(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, headers, state = host_client(tmp_path, token="valid-user")
    manager = client.app.state.jobs
    original = manager.host_client.update_job
    async def delayed(auth: HostIdentity, host_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("status"):
            await asyncio.sleep(.1)
        return await original(auth,host_id,payload)
    monkeypatch.setattr(manager.host_client,"update_job",delayed)
    with client:
        with client.websocket_connect('/ws',headers=headers) as socket:
            socket.send_json({'id':'create','method':'jobs.create','params':generate_input('shutdown delivery')})
            job_id=socket.receive_json()['result']['id']
            assert wait_terminal(client,job_id)['status']=='succeeded'
    assert state['jobs']['host-created-1']['status']=='succeeded'
    assert manager.store.owned_job_terminal(job_id)['sent']


@pytest.mark.parametrize("status", [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED])
def test_atomic_guard_preserves_settled_truth_against_late_updates(tmp_path: Path, status: JobStatus) -> None:
    store, job_id = seeded(tmp_path,terminal=False)
    error = ErrorDetail(code="service_stopped",message="stopped") if status==JobStatus.FAILED else None
    before = store.update_job(job_id,status=status,error=error)
    after = store.update_job(job_id,status=JobStatus.RUNNING,phase="normalize_request",preserve_terminal=True)
    assert after==before
    opposite = JobStatus.FAILED if status==JobStatus.SUCCEEDED else JobStatus.SUCCEEDED
    assert store.update_job(job_id,status=opposite,preserve_terminal=True)==before
