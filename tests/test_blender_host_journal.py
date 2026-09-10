from __future__ import annotations

from pathlib import Path
import asyncio
import sqlite3
import threading

import pytest

from mediaforge.blender_operation import BlenderRuntimeOperationAction as Action
from mediaforge.blender_operation import BlenderRuntimeOperationState as State
from mediaforge.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    value = Store(tmp_path)
    value.initialize()
    return value


def create(store: Store, runtime: str = "blender-test", owner: str | None = "user:16") -> str:
    return store.create_blender_runtime_operation(
        runtime, "4.5.13", Action.INSTALL, bytes_total=100, host_owner=owner,
        result={"retained": "local-only-result"},
    ).id


def test_binding_owner_immutability_and_public_contract(store: Store) -> None:
    operation_id = create(store)
    before = store.get_blender_runtime_operation(operation_id).model_dump()
    with pytest.raises(KeyError):
        store.bind_blender_runtime_host_job(operation_id, "user:17", "job_one")
    store.bind_blender_runtime_host_job(operation_id, "user:16", "job_one")
    store.bind_blender_runtime_host_job(operation_id, "user:16", "job_one")
    with pytest.raises(ValueError):
        store.bind_blender_runtime_host_job(operation_id, "user:16", "job_two")
    with pytest.raises(KeyError):
        store.blender_runtime_host_journal(operation_id, "user:17")
    after = store.get_blender_runtime_operation(operation_id).model_dump()
    assert not any(key.startswith("host_") for key in after)
    assert {k: v for k, v in before.items() if k != "updated_at"} == {
        k: v for k, v in after.items() if k != "updated_at"}
    second = create(store, "second")
    with pytest.raises(sqlite3.IntegrityError):
        store.bind_blender_runtime_host_job(second, "user:16", "job_one")
    assert store.blender_runtime_host_journal(second, "user:16")["host_job_id"] is None


@pytest.mark.parametrize("owner,state", [(None, State.QUEUED), ("user:16", State.PREFLIGHT),
                                         ("user:16", State.CANCELED)])
def test_cannot_adopt_unowned_or_started_operation(store: Store, owner: str | None, state: State) -> None:
    operation_id = create(store, owner=owner)
    store.update_blender_runtime_operation(operation_id, state=state)
    with pytest.raises((KeyError, ValueError)):
        store.bind_blender_runtime_host_job(operation_id, "user:16", "job_one")


@pytest.mark.parametrize("state,status", [(State.READY, "succeeded"), (State.FAILED, "failed"),
                                         (State.CANCELED, "canceled")])
def test_terminal_outbox_and_exact_receipt(store: Store, state: State, status: str) -> None:
    operation_id = create(store)
    store.bind_blender_runtime_host_job(operation_id, "user:16", "job_one")
    assert store.blender_runtime_host_journal(operation_id, "user:16")["terminal"] is None
    store.update_blender_runtime_operation(
        operation_id, state=state, error_message="private /path must not enter Host result")
    journal = store.blender_runtime_host_journal(operation_id, "user:16")
    assert journal["terminal"]["status"] == status and not journal["sent"]
    if state == State.FAILED:
        assert isinstance(journal["terminal"]["error"], str)
    assert "private /path" not in str(journal) and "local-only-result" not in str(journal)
    receipt = {"host_job_id": "job_one", "status": status,
               "disposition": "already_terminal", "terminal_matches": False}
    assert not store.reconcile_blender_runtime_terminal(operation_id, "user:16", receipt)
    assert not store.reconcile_blender_runtime_terminal(
        operation_id, "user:16", {**receipt, "status": "interrupted"})
    with pytest.raises(ValueError):
        store.reconcile_blender_runtime_terminal(operation_id, "user:16", {**receipt, "host_job_id": "foreign"})
    with pytest.raises(ValueError):
        store.reconcile_blender_runtime_terminal(operation_id, "user:16", {**receipt, "terminal_matches": 1})
    with pytest.raises(KeyError):
        store.reconcile_blender_runtime_terminal(operation_id, "user:17", receipt)
    assert store.reconcile_blender_runtime_terminal(
        operation_id, "user:16", {**receipt, "terminal_matches": True, "authorization": "discard-me"})
    assert "discard-me" not in str(store.blender_runtime_host_journal(operation_id, "user:16"))
    with pytest.raises(ValueError):
        store.update_blender_runtime_operation(operation_id, state=State.QUEUED)
    assert store.reconcile_blender_runtime_terminal(operation_id, "user:16", receipt)
    assert store.blender_runtime_host_journal(operation_id, "user:16")["reconciliation"]["terminal_matches"]


def test_restart_stops_owned_preserves_local_and_outbox(store: Store) -> None:
    owned = create(store)
    unbound = create(store, "unbound")
    local = create(store, "local", None)
    canceled = create(store, "canceled")
    store.bind_blender_runtime_host_job(owned, "user:16", "job_one")
    store.bind_blender_runtime_host_job(canceled, "user:16", "job_cancel")
    store.request_blender_runtime_operation_cancel(canceled)
    assert store.blender_runtime_host_journal(canceled, "user:16")["terminal"]["status"] == "canceled"
    assert store.resumable_blender_runtime_operation_ids() == [local]
    for operation_id in (owned, unbound, local):
        store.update_blender_runtime_operation(operation_id, state=State.DOWNLOADING, bytes_done=42)
    restarted = Store(store.data_dir)
    restarted.initialize()
    for operation_id in (owned, unbound):
        record = restarted.get_blender_runtime_operation(operation_id)
        assert record.state == State.FAILED and record.error_code == "host_context_lost"
        assert record.bytes_done == 42 and record.result == {"retained": "local-only-result"}
    assert restarted.resumable_blender_runtime_operation_ids() == [local]
    journal = restarted.blender_runtime_host_journal(owned, "user:16")
    assert journal["terminal"]["status"] == "failed" and not journal["sent"]
    restarted.initialize()
    assert restarted.blender_runtime_host_journal(owned, "user:16") == journal


def test_old_schema_migration_preserves_ready_rows(tmp_path: Path) -> None:
    store = Store(tmp_path)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("""CREATE TABLE blender_runtime_operations (
            id TEXT PRIMARY KEY, runtime_id TEXT NOT NULL, version TEXT NOT NULL,
            action TEXT NOT NULL, state TEXT NOT NULL, bytes_total INTEGER NOT NULL,
            bytes_done INTEGER NOT NULL, error_code TEXT, error_message TEXT,
            result_json TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        connection.execute("""INSERT INTO blender_runtime_operations VALUES
            ('old','blender-test','4.5.13','install','ready',100,100,NULL,NULL,
             '{"old":true}',0,'2026-09-10T00:00:00Z','2026-09-10T00:00:00Z')""")
        before = connection.execute("SELECT * FROM blender_runtime_operations").fetchone()
    store.initialize()
    with sqlite3.connect(store.db_path) as connection:
        after = connection.execute("SELECT * FROM blender_runtime_operations").fetchone()
    assert after[:len(before)] == before
    assert after[len(before):] == (None, None, None, 0, None, None)


@pytest.mark.parametrize("job_id", ["", "Bearer secret", "../../job", "x" * 129])
def test_invalid_host_id_does_not_modify_journal(store: Store, job_id: str) -> None:
    operation_id = create(store)
    with pytest.raises(ValueError):
        store.bind_blender_runtime_host_job(operation_id, "user:16", job_id)
    assert store.blender_runtime_host_journal(operation_id, "user:16")["host_job_id"] is None


def test_restart_recovers_terminal_intent_and_running_cancel(store: Store) -> None:
    completed = create(store)
    canceling = create(store, "canceling")
    store.bind_blender_runtime_host_job(completed, "user:16", "job_done")
    store.bind_blender_runtime_host_job(canceling, "user:16", "job_cancel")
    store.update_blender_runtime_operation(canceling, state=State.DOWNLOADING)
    store.request_blender_runtime_operation_cancel(canceling)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE blender_runtime_operations SET state='ready' WHERE id=?", (completed,))
    store.initialize()
    for operation_id, status in ((completed, "succeeded"), (canceling, "canceled")):
        journal = store.blender_runtime_host_journal(operation_id, "user:16")
        assert journal["terminal"]["status"] == status and not journal["sent"]


def test_app_startup_migration_is_off_loop_and_drained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from conftest import fake_settings
    from mediaforge.app import create_app

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = Store.initialize

    def initialize(value: Store) -> None:
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        entered.set()
        assert release.wait(5)
        original(value)
        finished.set()

    monkeypatch.setattr(Store, "initialize", initialize)
    app = create_app(fake_settings(tmp_path))

    async def scenario() -> None:
        async def start() -> None:
            async with app.router.lifespan_context(app):
                raise AssertionError("canceled startup must not launch workers")
        task = asyncio.create_task(start())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0.01)
                assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(scenario())
