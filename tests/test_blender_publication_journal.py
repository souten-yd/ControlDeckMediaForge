from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest
from pydantic import ValidationError

from mediaforge.blender_operation import BlenderRuntimeOperationState as State
from mediaforge.blender_publication import PublicationIdentity
from mediaforge.store import Store
from test_blender_host_journal import create


def prepared(tmp_path: Path) -> tuple[Store, str, PublicationIdentity]:
    store = Store(tmp_path)
    store.initialize()
    operation_id = create(store)
    store.bind_blender_runtime_host_job(operation_id, "user:16", "child")
    store.update_blender_runtime_operation(operation_id, state=State.PROBING)
    identity = PublicationIdentity(runtime_id="blender-test", version="4.5.13", action="install",
        archive_sha256="a" * 64, executable_sha256="b" * 64, previous_active_runtime_id=None,
        previous_registration_sha256=None, previous_executable_sha256=None, recovered_directory=False)
    return store, operation_id, identity


@pytest.mark.parametrize("revoked", [False, True])
def test_stop_before_publication_prevents_begin(tmp_path: Path, revoked: bool) -> None:
    store, operation_id, identity = prepared(tmp_path)
    if revoked:
        store.abort_blender_runtime_host_operation(operation_id, "user:16")
    else:
        store.request_blender_runtime_operation_cancel(operation_id)
    with pytest.raises(ValueError, match="Stopped"):
        store.begin_blender_publication(operation_id, identity)
    assert store.blender_publication(operation_id) is None


def test_late_stops_are_separate_and_completion_is_atomic(tmp_path: Path) -> None:
    store, operation_id, identity = prepared(tmp_path)
    before = store.get_blender_runtime_operation(operation_id).model_dump()
    first = store.begin_blender_publication(operation_id, identity)
    assert store.begin_blender_publication(operation_id, identity) == first
    with pytest.raises(KeyError):
        store.abort_blender_runtime_host_operation(operation_id, "user:17")
    assert store.blender_publication(operation_id) == first
    for _ in range(2):
        store.request_blender_runtime_operation_cancel(operation_id)
        store.abort_blender_runtime_host_operation(operation_id, "user:16")
    current = store.get_blender_runtime_operation(operation_id)
    assert not current.cancel_requested and current.error_code is None
    assert current.state == State.PROBING
    assert store.blender_publication(operation_id).stop_requests == ["cancel", "host_context_lost"]
    assert store.blender_runtime_host_journal(operation_id, "user:16")["terminal"] is None
    with pytest.raises(ValueError, match="dedicated completion"):
        store.update_blender_runtime_operation(operation_id, state=State.READY)
    complete = store.complete_blender_publication(operation_id, identity, {"verified": True})
    assert complete.state == State.READY and not complete.cancel_requested and complete.error_code is None
    assert complete.result["publication_stop_requests"] == ["cancel", "host_context_lost"]
    assert store.blender_runtime_host_journal(operation_id, "user:16")["terminal"]["status"] == "succeeded"
    assert store.complete_blender_publication(operation_id, identity, {"verified": True}) == complete
    with pytest.raises(ValueError):
        store.complete_blender_publication(operation_id, identity, {"verified": False})
    assert set(before) == set(complete.model_dump())  # Private identity not a new public field.
    restarted = Store(tmp_path)
    restarted.initialize()
    assert restarted.get_blender_runtime_operation(operation_id) == complete
    assert restarted.blender_publication(operation_id).phase == "committed"


def test_restart_requires_verification_without_fabricating_outcome(tmp_path: Path) -> None:
    store, operation_id, identity = prepared(tmp_path)
    store.begin_blender_publication(operation_id, identity)
    restarted = Store(tmp_path)
    restarted.initialize()
    assert restarted.blender_publication(operation_id).phase == "recovery_required"
    current = restarted.get_blender_runtime_operation(operation_id)
    assert current.state == State.FAILED and current.error_code == "blender_publication_recovery_required"
    assert restarted.blender_runtime_host_journal(operation_id, "user:16")["terminal"] is None
    assert restarted.pending_blender_runtime_host_terminals("user:16") == []
    with pytest.raises(ValueError):
        create(restarted)
    with pytest.raises(ValueError):
        restarted.complete_blender_publication(operation_id, identity, {})
    with pytest.raises(ValueError):
        restarted.begin_blender_publication(operation_id, identity)
    restarted.initialize()
    assert restarted.blender_publication(operation_id).phase == "recovery_required"


def test_identity_rejection_does_not_change_journal(tmp_path: Path) -> None:
    store, operation_id, identity = prepared(tmp_path)
    with pytest.raises(ValidationError):
        PublicationIdentity.model_validate({**identity.model_dump(), "path": "/private/runtime"})
    wrong = identity.model_copy(update={"runtime_id": "different"})
    with pytest.raises(ValueError):
        store.begin_blender_publication(operation_id, wrong)
    assert store.blender_publication(operation_id) is None
    expected = store.begin_blender_publication(operation_id, identity)
    with pytest.raises(ValueError):
        store.begin_blender_publication(operation_id, identity.model_copy(update={"archive_sha256": "c" * 64}))
    with pytest.raises(ValueError):
        store.complete_blender_publication(operation_id, wrong, {})
    assert store.blender_publication(operation_id) == expected


@pytest.mark.parametrize("change", [{"action": "repair"}, {"recovered_directory": True},
                                    {"previous_active_runtime_id": "../../private"}])
def test_identity_requires_bounded_previous_runtime(tmp_path: Path, change: dict[str, object]) -> None:
    _, _, identity = prepared(tmp_path)
    with pytest.raises(ValidationError):
        PublicationIdentity.model_validate({**identity.model_dump(), **change})


def test_begin_and_stop_arbitrate_across_independent_store_connections(tmp_path: Path) -> None:
    store, operation_id, identity = prepared(tmp_path)
    other = Store(tmp_path)  # Do not run startup recovery on a live operation.
    barrier = threading.Barrier(2)

    def begin() -> bool:
        barrier.wait(timeout=5)
        try:
            store.begin_blender_publication(operation_id, identity)
            return True
        except ValueError:
            return False

    def stop() -> None:
        barrier.wait(timeout=5)
        other.request_blender_runtime_operation_cancel(operation_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        started, stopped = pool.submit(begin), pool.submit(stop)
        won = started.result(timeout=5)
        stopped.result(timeout=5)
    current = store.get_blender_runtime_operation(operation_id)
    if won:
        assert not current.cancel_requested
        assert store.blender_publication(operation_id).stop_requests == ["cancel"]
    else:
        assert current.cancel_requested and store.blender_publication(operation_id) is None
