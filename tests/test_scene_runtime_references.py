from __future__ import annotations

import asyncio
from pathlib import Path
import threading

import pytest

from mediaforge.blender_session_record import BlenderSessionState, BlenderWebSession
from mediaforge.domain import JobRequest, JobStatus
from mediaforge.scenes import SceneCatalog, SceneWorkingCopy
from mediaforge.store import Store, utc_now
from test_blender_external_management import add_alternative
from test_scene_recipe_jobs import pending_terminal
from test_scenes import RUNTIME_ID, _revision_assets, _revision_input


def scene_store(tmp_path: Path):
    store = Store(tmp_path / "data")
    store.initialize()
    source, preview, _ = _revision_assets(store, tmp_path)
    document, revision = SceneCatalog(store).create(
        "user:7", name="Reference fixture", tags=[], collection=None,
        revision=_revision_input(source, preview))
    return store, document, revision


def session_record(scene_id: str) -> BlenderWebSession:
    return BlenderWebSession(id="blendersession_" + "1" * 32, scene_id=scene_id,
        web_pack_id="fixture-web", web_pack_version="1.0.0", unit_id="mediaforge-blender-" + "1" * 32 + ".service",
        state=BlenderSessionState.QUEUED, created_at=utc_now(), updated_at=utc_now())


@pytest.mark.parametrize("state", list(BlenderSessionState))
def test_gui_states_resolve_unpinned_session_from_scene(tmp_path: Path, state: BlenderSessionState) -> None:
    store, document, _ = scene_store(tmp_path)
    session = session_record(document.id)
    store.create_blender_web_session("user:7", session)
    store.update_blender_web_session("user:7", session.model_copy(update={"state": state}))
    active = state.value in {"queued", "preparing", "starting", "ready", "saving", "stopping"}
    assert store.active_scene_runtime_references(RUNTIME_ID) == {
        "recipe_jobs": 0, "working_copies": 0, "sessions": int(active), "unresolved_sessions": 0}
    assert sum(store.active_scene_runtime_references("another-runtime").values()) == 0
    assert store.scene_runtime_reference_count(RUNTIME_ID) == 1


@pytest.mark.parametrize("state", ["active", "recovery", "released"])
def test_working_copy_and_recovery_pin_are_not_replaced_by_current_scene(tmp_path: Path, state: str) -> None:
    store, document, revision = scene_store(tmp_path)
    moment = utc_now()
    working = SceneWorkingCopy(id="working_" + "2" * 32, scene_id=document.id,
        base_revision_id=revision.id, runtime_id="different-runtime", runtime_version="4.5.13",
        expires_at="2000-01-01T00:00:00+00:00", created_at=moment, updated_at=moment)
    store.acquire_scene_working_copy("user:7", working, now=moment)
    if state != "active":
        store.finish_scene_working_copy("user:7", working.id, state=state, now=moment)
    session = session_record(document.id).model_copy(update={"recovery_source_id": working.id})
    store.create_blender_web_session("user:7", session)
    counts = store.active_scene_runtime_references("different-runtime")
    assert counts["sessions"] == 1 and counts["working_copies"] == int(state == "active")
    assert sum(store.active_scene_runtime_references(RUNTIME_ID).values()) == 0
    # An explicitly pinned session wins over a stale current-scene/recovery pointer.
    store.update_blender_web_session("user:7", session.model_copy(update={"runtime_id": RUNTIME_ID}))
    assert store.active_scene_runtime_references(RUNTIME_ID)["sessions"] == 1


@pytest.mark.parametrize("malformed", ["{", "[]", '{"recovery_source_id":"missing"}',
                                       '{"working_id":42}', '{"working_id":[]}'])
def test_unresolved_active_gui_blocks_all_runtimes(tmp_path: Path, malformed: str) -> None:
    store, document, _ = scene_store(tmp_path)
    session = session_record(document.id)
    store.create_blender_web_session("user:7", session)
    with store._connect() as connection:
        connection.execute("UPDATE blender_web_sessions SET value_json = ? WHERE id = ?", (malformed, session.id))
    for runtime_id in (RUNTIME_ID, "another-runtime"):
        assert store.active_scene_runtime_references(runtime_id)["unresolved_sessions"] == 1


@pytest.mark.parametrize("status", list(JobStatus))
def test_recipe_durable_reference_tracks_job_state_not_task_stage(tmp_path: Path, status: JobStatus) -> None:
    store = Store(tmp_path)
    store.initialize()
    job_id = pending_terminal(store)
    store.update_job(job_id, status=status)
    assert store.active_scene_runtime_references("blender-test")["recipe_jobs"] == int(
        status in {JobStatus.QUEUED, JobStatus.RUNNING})
    assert store.active_scene_runtime_references("another-runtime")["recipe_jobs"] == 0


def test_managed_removal_preview_rechecks_durable_job_and_runs_off_loop(client, monkeypatch) -> None:
    manager = add_alternative(client)
    from mediaforge.blender_runtime import G8_RUNTIME_ID, G8_MANAGED_RUNTIME_ID
    manager.resolver.activate(G8_RUNTIME_ID)

    async def scenario() -> None:
        thread_id = threading.get_ident()
        original = manager.store.active_scene_runtime_references

        def checked(runtime_id):
            assert threading.get_ident() != thread_id
            return original(runtime_id)

        monkeypatch.setattr(manager.store, "active_scene_runtime_references", checked)
        before = await manager.removal_preview(G8_MANAGED_RUNTIME_ID)
        assert before["can_remove"]
        job = manager.store.create_job(JobRequest(operation="media.inspect", intent="queued fixture"))
        manager.store.create_scene_recipe_task(job.id, owner="user:7", host_job_id="fixture-child",
            operation="scene.create", runtime_id=G8_MANAGED_RUNTIME_ID, runtime_version="4.5.9",
            base_revision_id=None, input_sha256="1" * 64, idempotency_key="2" * 64, request={})
        after = await manager.removal_preview(G8_MANAGED_RUNTIME_ID)
        assert after["live_reference_count"] == 1
        assert after["durable_reference_counts"]["recipe_jobs"] == 1
        assert "live_reference" in after["blocked_reasons"] and not after["can_remove"]
        from mediaforge.blender_operation import BlenderRuntimeOperationError
        with pytest.raises(BlenderRuntimeOperationError) as error:
            await manager.remove(G8_MANAGED_RUNTIME_ID, before["confirmation_fingerprint"])
        assert error.value.code == "blender_runtime_remove_changed"
        assert manager.resolver.resolve_registered(G8_MANAGED_RUNTIME_ID) is not None

    asyncio.run(scenario())


@pytest.mark.parametrize("phase", ["admission", "deletion"])
def test_removal_thread_is_not_abandoned_by_request_cancel(client, monkeypatch, phase: str) -> None:
    from mediaforge.blender_runtime import G8_RUNTIME_ID, G8_MANAGED_RUNTIME_ID
    manager = add_alternative(client)
    manager.resolver.activate(G8_RUNTIME_ID)
    entered, finish = threading.Event(), threading.Event()

    async def scenario() -> None:
        thread_id = threading.get_ident()
        name = "_admit_removal" if phase == "admission" else "_remove_sync"
        original = getattr(manager, name)

        def held(*args):
            assert threading.get_ident() != thread_id
            entered.set()
            assert finish.wait(5)
            return original(*args)

        monkeypatch.setattr(manager, name, held)
        preview = await manager.removal_preview(G8_MANAGED_RUNTIME_ID)
        if phase == "admission":
            task = asyncio.create_task(manager.remove(G8_MANAGED_RUNTIME_ID, preview["confirmation_fingerprint"]))
        else:
            operation = await asyncio.to_thread(
                manager._admit_removal, G8_MANAGED_RUNTIME_ID, preview["confirmation_fingerprint"])
            task = asyncio.create_task(manager._run(operation.id))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            task.cancel()
            await asyncio.sleep(0.01)
            assert not task.done()
        finally:
            finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        if phase == "admission":
            assert manager._tasks  # The durable request still owns an execution task.
            await asyncio.gather(*list(manager._tasks.values()))
        else:
            assert manager.store.get_blender_runtime_operation(operation.id).state == "ready"
        assert manager.resolver.resolve_registered(G8_MANAGED_RUNTIME_ID) is None
        assert not manager._removal_admissions
        await manager.stop()

    asyncio.run(scenario())
