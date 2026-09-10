from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mediaforge.blender_operation import BlenderRuntimeOperationState as State
from mediaforge.blender_publication import PublicationIdentity
from mediaforge.store import Store
from test_blender_host_journal import create
from test_host_execution import host_client
from test_workspace_transport import call


def seed(store: Store, owner: str | None, runtime: str = "notice-test") -> tuple[str, PublicationIdentity]:
    operation_id = create(store, runtime, owner)
    if owner:
        store.bind_blender_runtime_host_job(operation_id, owner, f"child_{runtime}")
    store.update_blender_runtime_operation(operation_id, state=State.PROBING)
    identity = PublicationIdentity(runtime_id=runtime, version="4.5.13", action="install",
        archive_sha256="a" * 64, executable_sha256="b" * 64, previous_active_runtime_id=None,
        previous_registration_sha256=None, previous_executable_sha256=None, recovered_directory=False)
    store.begin_blender_publication(operation_id, identity)
    return operation_id, identity


@pytest.mark.parametrize("phase", ["committing", "recovery_required", "committed", "rolled_back"])
def test_notice_projection_preserves_outcome_and_hides_private_identity(tmp_path: Path, phase: str) -> None:
    store = Store(tmp_path)
    store.initialize()
    operation_id, identity = seed(store, "user:16")
    store.request_blender_runtime_operation_cancel(operation_id)
    store.abort_blender_runtime_host_operation(operation_id, "user:16")
    if phase != "committing":
        store.require_blender_publication_recovery(operation_id)
    if phase == "committed":
        store.recover_blender_publication(operation_id, identity, {"publication_recovered": True})
    elif phase == "rolled_back":
        store.rollback_blender_publication(operation_id, identity)
    before = store.blender_runtime_host_journal(operation_id, "user:16")
    expected = {"committing": "publication_in_progress", "recovery_required": "publication_recovery_required",
                "committed": "publication_recovered", "rolled_back": "publication_rolled_back"}[phase]
    notices = store.blender_runtime_operation_notices("user:16")
    assert notices[operation_id] == [expected, "late_cancel", "late_context_lost"] + (
        ["host_pending"] if phase in {"committed", "rolled_back"} else [])
    assert store.blender_runtime_operation_notices("user:17") == {}
    assert store.blender_runtime_operation_notices(None) == {}
    assert before == store.blender_runtime_host_journal(operation_id, "user:16")
    assert not any(secret in json.dumps(notices) for secret in ("user:16", "child_", "aaaa", "bbbb", "identity"))


def test_receipt_changes_notify_once_and_preserve_host_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Store(tmp_path)
    store.initialize()
    operation_id, identity = seed(store, "user:16")
    store.complete_blender_publication(operation_id, identity, {})
    events = []
    monkeypatch.setattr(store, "_notify_session", events.append)
    receipt = {"host_job_id": "child_notice-test", "status": "canceled",
               "disposition": "already_terminal", "terminal_matches": False}
    for _ in range(3):
        assert not store.reconcile_blender_runtime_terminal(operation_id, "user:16", receipt)
    assert events == ["blender_runtime"]
    assert store.blender_runtime_operation_notices("user:16")[operation_id] == ["host_mismatch"]
    assert store.get_blender_runtime_operation(operation_id).state == State.READY
    assert store.blender_runtime_host_journal(operation_id, "user:16")["reconciliation"] == receipt
    matched = {**receipt, "status": "succeeded", "terminal_matches": True}
    for _ in range(3):
        assert store.reconcile_blender_runtime_terminal(operation_id, "user:16", matched)
    assert events == ["blender_runtime", "blender_runtime"]
    assert store.blender_runtime_operation_notices("user:16") == {}


@pytest.mark.parametrize("method", ["blender.runtime.status", "workspace.session"])
def test_workspace_projects_only_authenticated_owner_offloop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str,
) -> None:
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.blender_runtime_operations.store
        own, _ = seed(store, "user:7", "own")
        seed(store, "user:8", "other")
        local, _ = seed(store, None, "local")
        original = store.blender_runtime_operation_notices
        def checked(owner: str | None) -> dict[str, list[str]]:
            with pytest.raises(RuntimeError, match="no running event loop"):
                asyncio.get_running_loop()
            return original(owner)
        monkeypatch.setattr(store, "blender_runtime_operation_notices", checked)
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, method, {"parts": ["blender_runtime"]} if method == "workspace.session" else {})
        assert answer["ok"]
        result = answer["result"]["blender_runtime"] if method == "workspace.session" else answer["result"]
        assert result["operation_notices"] == {own: ["publication_in_progress"]}
        # The unauthenticated development mirror must not expose Host notices.
        response = client.get("/workspace-api/blender/runtime")
        assert response.status_code == 200
        assert response.json()["operation_notices"] == {local: ["publication_in_progress"]}


def test_legacy_local_operation_has_no_synthetic_notice(client: TestClient) -> None:
    store = client.app.state.blender_runtime_operations.store
    operation_id = create(store, owner=None)
    assert store.blender_runtime_operation_notices(None) == {}
    assert store.get_blender_runtime_operation(operation_id).state == State.QUEUED


def test_publication_and_lost_context_invalidate_notices_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Store(tmp_path)
    store.initialize()
    events = []
    monkeypatch.setattr(store, "_notify_session", events.append)
    operation_id, identity = seed(store, "user:16")
    # Creation, probing, and publication each invalidate the existing session part.
    assert events == ["blender_runtime"] * 3
    events.clear()
    store.begin_blender_publication(operation_id, identity)
    assert events == []
    for _ in range(3):
        store.abort_blender_runtime_host_operation(operation_id, "user:16")
    assert events == ["blender_runtime"]
    assert store.blender_runtime_operation_notices("user:16")[operation_id] == [
        "publication_in_progress", "late_context_lost"]
