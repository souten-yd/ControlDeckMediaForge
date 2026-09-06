from __future__ import annotations

import asyncio
from pathlib import Path
import threading

import pytest

from mediaforge.blender_session_manager import BlenderSessionError
from mediaforge.scenes import SceneError
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
