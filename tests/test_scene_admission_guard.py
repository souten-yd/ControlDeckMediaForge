from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any

import pytest

from mediaforge.blender_session_manager import BlenderSessionError
from mediaforge.scenes import SceneError
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_recipes import SceneEditRequest
from mediaforge.host.client import HostIdentity
from unittest.mock import AsyncMock
from test_blender_session_manager import OWNER, session_fixture, wait_state


@pytest.mark.parametrize("recovery", [False, True])
def test_working_admission_serializes_removal_snapshot(tmp_path: Path, monkeypatch, recovery: bool) -> None:
    store, workspace, scene_id, _, _ = session_fixture(tmp_path)
    candidate = workspace.acquire_working_copy(OWNER, scene_id) if recovery else None
    if candidate is not None:
        workspace.retain_working_copy_for_recovery(OWNER, candidate.id)
    entered, finish = threading.Event(), threading.Event()
    name = "_acquire_recovery_working_copy" if recovery else "_acquire_working_copy"
    original = getattr(workspace, name)

    def held(*args):
        entered.set()
        assert finish.wait(5)
        return original(*args)

    monkeypatch.setattr(workspace, name, held)

    async def scenario() -> None:
        request = asyncio.create_task(workspace.acquire_working_copy_async(
            OWNER, scene_id, recovery_working_id=candidate.id if candidate else None))
        contender_entered = threading.Event()

        def removal_snapshot():
            contender_entered.set()
            with workspace.resolver.removal_guard():
                return store.active_scene_runtime_references(workspace.resolver.runtime.runtime_id)

        try:
            assert await asyncio.to_thread(entered.wait, 3)
            contender = asyncio.create_task(asyncio.to_thread(removal_snapshot))
            assert await asyncio.to_thread(contender_entered.wait, 3)
            await asyncio.sleep(0.02)
            assert not contender.done()
        finally:
            finish.set()
        working = await request
        assert (await contender)["working_copies"] == 1
        await asyncio.to_thread(workspace.release_working_copy, OWNER, working.id)
        assert store.active_scene_runtime_references(working.runtime_id)["working_copies"] == 0
        if candidate:
            assert store.get_scene_working_copy(OWNER, candidate.id).state == "recovery"

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["stop", "interrupt", "shutdown"])
def test_gui_finish_waits_for_canceled_copy_thread(tmp_path: Path, monkeypatch, action: str) -> None:
    store, workspace, scene_id, controller, manager = session_fixture(tmp_path)
    entered, finish = threading.Event(), threading.Event()
    original = workspace._acquire_working_copy

    def held(*args):
        entered.set()
        assert finish.wait(5)
        return original(*args)

    monkeypatch.setattr(workspace, "_acquire_working_copy", held)

    async def scenario() -> None:
        created = await manager.create(OWNER, scene_id)
        assert created["runtime_id"] == workspace.resolver.runtime.runtime_id
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            if action == "shutdown":
                stopping = asyncio.create_task(manager.stop())
            elif action == "stop":
                manager.discard_and_stop(OWNER, created["id"])
            else:
                manager.interrupt(OWNER, created["id"], code="blender_session_host_disabled")
            await asyncio.sleep(0.02)
            if action == "shutdown":
                assert not stopping.done()
            else:
                assert manager.get(OWNER, created["id"])["state"] == "stopping"
            assert controller.starts == 0
        finally:
            finish.set()
        if action == "shutdown":
            await stopping
        else:
            await wait_state(manager, created["id"], "stopped" if action == "stop" else "interrupted")
            await manager.stop()
        assert all(copy.state == "released" for copy in store.list_scene_working_copies(OWNER))
        assert not list(workspace.working_root.iterdir())
        assert controller.units == {} and controller.starts == 0

    asyncio.run(scenario())


def test_gui_admission_and_working_copy_reject_runtime_removed_first(tmp_path: Path, monkeypatch) -> None:
    store, workspace, scene_id, _, manager = session_fixture(tmp_path)
    monkeypatch.setattr(workspace.resolver, "resolve_registered", lambda runtime_id: None)

    async def scenario() -> None:
        with pytest.raises(BlenderSessionError) as error:
            await manager.create(OWNER, scene_id)
        assert error.value.code == "scene_runtime_unavailable"
        with pytest.raises(SceneError) as error:
            await workspace.acquire_working_copy_async(OWNER, scene_id)
        assert error.value.code == "scene_runtime_unavailable"
        assert store.list_blender_web_sessions(OWNER) == []
        assert store.list_scene_working_copies(OWNER) == []

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["gui", "working", "recipe"])
def test_admission_waits_for_removal_then_rejects_missing_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    store, workspace, scene_id, controller, manager = session_fixture(tmp_path)
    entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
    host = AsyncMock()
    jobs_before = store.list_jobs()
    host.create_or_attach_job.side_effect = AssertionError("unavailable runtime reached Host")
    recipe_manager = SceneRecipeJobManager(store, workspace, host)
    original = (manager._create_guarded if kind == "gui" else workspace.acquire_recipe_runtime
                if kind == "recipe" else workspace.acquire_working_copy)

    def observed(*args: Any, **kwargs: Any) -> Any:
        attempted.set()
        return original(*args, **kwargs)

    if kind == "gui":
        monkeypatch.setattr(manager, "_create_guarded", observed)
    elif kind == "recipe":
        monkeypatch.setattr(workspace, "acquire_recipe_runtime", observed)
    else:
        monkeypatch.setattr(workspace, "acquire_working_copy", observed)

    def removal() -> None:
        with workspace.resolver.removal_guard():
            entered.set()
            assert release.wait(5)
            monkeypatch.setattr(workspace.resolver, "resolve_registered", lambda runtime_id: None)

    async def scenario() -> None:
        removing = asyncio.create_task(asyncio.to_thread(removal))
        request = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            if kind == "recipe":
                document, _ = await asyncio.to_thread(workspace.catalog.get, OWNER, scene_id)
                value = SceneEditRequest.model_validate({"scene_id": scene_id,
                    "base_revision_id": document.current_revision_id,
                    "recipe": {"operations": [{"type": "primitive.add", "object_id": "probe",
                        "primitive": "cube", "name": "Never executed", "dimensions": [1, 1, 1]}]}})
                identity = HostIdentity(authorization="Bearer fixture", addon_id="media-forge",
                    subject="job:fixture", actor_subject=OWNER, expires_at=4_000_000_000,
                    granted_capabilities=frozenset({"jobs.write"}))
                request = asyncio.create_task(recipe_manager.submit(value, identity))
            else:
                request = asyncio.create_task(manager.create(OWNER, scene_id) if kind == "gui"
                    else workspace.acquire_working_copy_async(OWNER, scene_id))
            assert await asyncio.to_thread(attempted.wait, 3)
            await asyncio.sleep(0.02)
            assert not request.done()
        finally:
            release.set()
            await removing
            if request is not None:
                with pytest.raises((SceneError, BlenderSessionError)) as error:
                    await request
                assert error.value.code == "scene_runtime_unavailable"
        assert store.list_blender_web_sessions(OWNER) == []
        assert store.list_scene_working_copies(OWNER) == []
        assert controller.starts == 0
        host.create_or_attach_job.assert_not_awaited()
        assert store.list_jobs() == jobs_before
        assert not recipe_manager._admissions and not recipe_manager._tasks
        await recipe_manager.stop()
        await manager.stop()

    asyncio.run(scenario())


def test_gui_record_is_pinned_before_releasing_removal_guard(tmp_path: Path, monkeypatch) -> None:
    store, workspace, scene_id, _, manager = session_fixture(tmp_path)
    entered, finish = threading.Event(), threading.Event()
    original = manager._create_record
    monkeypatch.setattr(manager, "_spawn", lambda *args, **kwargs: None)

    def held(*args):
        entered.set()
        assert finish.wait(5)
        return original(*args)

    monkeypatch.setattr(manager, "_create_record", held)

    async def scenario() -> None:
        request = asyncio.create_task(manager.create(OWNER, scene_id))
        def snapshot():
            with workspace.resolver.removal_guard():
                return store.active_scene_runtime_references(workspace.resolver.runtime.runtime_id)
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            contender = asyncio.create_task(asyncio.to_thread(snapshot))
            await asyncio.sleep(0.02)
            assert not contender.done()
            request.cancel()
            await asyncio.sleep(0.01)
            assert not request.done()
        finally:
            finish.set()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert (await contender)["sessions"] == 1
        assert store.list_blender_web_sessions(OWNER)[0].runtime_id == workspace.resolver.runtime.runtime_id
        assert not manager._admissions

    asyncio.run(scenario())
