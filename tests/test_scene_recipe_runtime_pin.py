from __future__ import annotations

import asyncio
from pathlib import Path
import threading

import pytest

from mediaforge.blender_runtime import BlenderRuntimeRegistryError, G8_RUNTIME_ID
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.store import Store
from test_blender_runtime_resolver import MANIFEST, ready_runtime, resolver
from test_scene_recipe_jobs import Host, IDENTITY, Workspace, recipe


def pinned_workspace(tmp_path: Path) -> tuple[Store, Workspace]:
    legacy = tmp_path / "legacy"
    ready_runtime(legacy)
    runtimes = resolver(tmp_path, legacy)
    assert runtimes.register_legacy()
    managed_id = "blender-4.5.9-linux-x64"
    ready_runtime(runtimes.managed_root / managed_id)
    runtimes.register_managed(runtime_id=managed_id, version="4.5.9", location=managed_id,
                              archive_sha256=MANIFEST["archive_sha256"])
    runtimes.activate(managed_id)
    store = Store(tmp_path / "store")
    store.initialize()

    class PinnedWorkspace(Workspace):
        acquire_recipe_runtime = SceneWorkspace.acquire_recipe_runtime
        recipe_runtime_pin = SceneWorkspace.recipe_runtime_pin

    workspace = PinnedWorkspace()
    workspace.resolver = runtimes
    return store, workspace


@pytest.mark.parametrize("outcome", ["success", "host_failure", "cancel", "stop"])
def test_admission_holds_exact_runtime_and_releases_on_all_outcomes(tmp_path: Path, outcome: str) -> None:
    async def scenario() -> None:
        store, workspace = pinned_workspace(tmp_path)
        entered, proceed = asyncio.Event(), asyncio.Event()
        runtime_id = workspace.resolver.resolve_active().runtime_id

        class WaitingHost(Host):
            async def create_or_attach_job(self, *args, **kwargs):
                entered.set()
                await proceed.wait()
                if outcome == "host_failure":
                    return {}
                return await super().create_or_attach_job(*args, **kwargs)

        manager = SceneRecipeJobManager(store, workspace, WaitingHost())
        submission = asyncio.create_task(manager.submit(recipe(), IDENTITY))
        await asyncio.wait_for(entered.wait(), 2)
        await asyncio.to_thread(workspace.resolver.activate, G8_RUNTIME_ID)
        assert workspace.resolver.live_reference_count(runtime_id) == 1
        with pytest.raises(BlenderRuntimeRegistryError, match="live references"):
            await asyncio.to_thread(workspace.resolver.unregister_managed, runtime_id)
        if outcome == "stop":
            await manager.stop()
        elif outcome == "cancel":
            submission.cancel()
        else:
            proceed.set()
        result = await asyncio.gather(submission, return_exceptions=True)
        if outcome == "success":
            job, record = result[0]
            assert record.runtime_id == runtime_id
            await manager.wait_cleanup(job.id)
        else:
            assert isinstance(result[0], BaseException)
        assert workspace.resolver.live_reference_count(runtime_id) == 0
        assert not manager._admissions and not manager._tasks
        assert await asyncio.to_thread(workspace.resolver.unregister_managed, runtime_id)
        await manager.stop()

    asyncio.run(scenario())


def test_cancel_during_thread_acquisition_waits_and_releases(tmp_path: Path) -> None:
    async def scenario() -> None:
        store, workspace = pinned_workspace(tmp_path)
        entered, proceed = threading.Event(), threading.Event()
        original = workspace.acquire_recipe_runtime
        loop_thread = threading.get_ident()

        def acquire(owner, value):
            assert threading.get_ident() != loop_thread
            held = original(owner, value)
            held[0].callback(lambda: assert_worker_thread(loop_thread))
            entered.set()
            assert proceed.wait(3)
            return held

        workspace.acquire_recipe_runtime = acquire
        manager = SceneRecipeJobManager(store, workspace, Host())
        submission = asyncio.create_task(manager.submit(recipe(), IDENTITY))
        assert await asyncio.to_thread(entered.wait, 2)
        submission.cancel()
        await asyncio.sleep(0.01)
        assert not submission.done()
        proceed.set()
        with pytest.raises(asyncio.CancelledError):
            await submission
        assert workspace.resolver.live_reference_count("blender-4.5.9-linux-x64") == 0
        assert not manager._admissions
        await manager.stop()

    asyncio.run(scenario())


def assert_worker_thread(loop_thread: int) -> None:
    assert threading.get_ident() != loop_thread


def test_queue_and_worker_cleanup_keep_runtime_pinned(tmp_path: Path) -> None:
    async def scenario() -> None:
        store, workspace = pinned_workspace(tmp_path)
        started, cleaning, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def apply(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await finish.wait()

        workspace.apply_recipe = apply
        manager = SceneRecipeJobManager(store, workspace, Host())
        runtime_id = workspace.resolver.resolve_active().runtime_id
        await manager._execution_guard.acquire()
        job, _ = await manager.submit(recipe(), IDENTITY)
        assert not started.is_set()
        assert workspace.resolver.live_reference_count(runtime_id) == 1
        manager._execution_guard.release()
        await asyncio.wait_for(started.wait(), 2)
        cancel = asyncio.create_task(manager.cancel(job.id, "user:7"))
        await asyncio.wait_for(cleaning.wait(), 2)
        assert workspace.resolver.live_reference_count(runtime_id) == 1
        assert not cancel.done()
        finish.set()
        await cancel
        await manager.wait_cleanup(job.id)
        assert workspace.resolver.live_reference_count(runtime_id) == 0
        await manager.stop()

    asyncio.run(scenario())
