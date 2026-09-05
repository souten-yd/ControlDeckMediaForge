from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest

from mediaforge.domain import JobRequest, JobStatus
from mediaforge.host.client import HostIdentity
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_recipes import SceneCreateRequest
from mediaforge.scenes import SceneError
from mediaforge.store import Store


IDENTITY = HostIdentity(
    authorization="Bearer secret",
    addon_id="media-forge",
    subject="job:host-parent",
    expires_at=4_000_000_000,
    granted_capabilities=frozenset({"jobs.write"}),
    actor_subject="user:7",
)


def recipe() -> SceneCreateRequest:
    return SceneCreateRequest.model_validate({
        "name": "Sword",
        "recipe": {
            "operations": [
                {
                    "type": "primitive.add",
                    "object_id": "blade",
                    "primitive": "cube",
                    "name": "Blade",
                    "dimensions": [0.08, 0.02, 1.2],
                },
                {
                    "type": "material.set",
                    "object_id": "blade",
                    "name": "Steel",
                    "base_color": [0.3, 0.35, 0.4, 1],
                    "metallic": 0.9,
                    "roughness": 0.25,
                },
            ]
        },
    })


class Host:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    async def create_or_attach_job(
        self, identity: HostIdentity, *, title: str, detached: bool = False
    ) -> dict[str, Any]:
        self.created.append({"subject": identity.subject, "title": title, "detached": detached})
        return {
            "created": True,
            "job": {"id": "host-child"},
            "access_token": "child-secret",
            "expires_at": 4_000_000_000,
        }

    async def update_job(
        self, identity: HostIdentity, host_job_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        assert identity.subject == "job:host-child"
        assert identity.authorization == "Bearer child-secret"
        self.updates.append({"id": host_job_id, **payload})
        return payload

    async def job_control(
        self, identity: HostIdentity, host_job_id: str
    ) -> dict[str, Any]:
        assert identity.subject == "job:host-child"
        return {"cancel_requested": False}

    async def refresh_job_credential(
        self, identity: HostIdentity, host_job_id: str
    ) -> dict[str, Any]:
        return {"access_token": "refreshed", "expires_at": 4_000_000_000}


class Workspace:
    def recipe_runtime_pin(
        self, owner: str, value: SceneCreateRequest
    ) -> tuple[str, str, None]:
        return "blender-test", "4.5.9", None

    async def apply_recipe(
        self,
        owner: str,
        job_id: str,
        value: SceneCreateRequest,
        *,
        runtime_id: str,
        runtime_version: str,
    ) -> dict[str, Any]:
        assert owner == "user:7"
        return {
            "scene": {"id": "scene_" + "1" * 32},
            "revision": {"id": "revision_" + "2" * 32},
            "asset_ids": ["asset_" + "3" * 32, "asset_" + "4" * 32],
            "recipe": {"operation_count": len(value.recipe.operations)},
        }


async def terminal(store: Store, job_id: str) -> None:
    for _ in range(200):
        if store.get_job(job_id).status in {
            JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED
        }:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("scene job did not finish")


def test_scene_recipe_is_a_detached_durable_owner_scoped_job(tmp_path: Path) -> None:
    asyncio.run(_durable_case(tmp_path))


async def _durable_case(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.initialize()
    host = Host()
    manager = SceneRecipeJobManager(store, Workspace(), host)  # type: ignore[arg-type]
    await manager.start()
    job, record = await manager.submit(recipe(), IDENTITY)
    assert host.created == [{
        "subject": "job:host-parent",
        "title": "Media Forge 3D scene recipe",
        "detached": True,
    }]
    assert len(record.input_sha256) == 64
    await terminal(store, job.id)
    await manager.wait_cleanup(job.id)
    projection = manager.projection(job.id, "user:7")
    assert projection["status"] == "succeeded"
    assert projection["stage"] == "succeeded"
    assert projection["operation"] == "scene.create"
    assert projection["runtime_id"] == "blender-test"
    assert projection["runtime_version"] == "4.5.9"
    assert projection["base_revision_id"] is None
    assert len(projection["idempotency_key"]) == 64
    assert projection["result"]["scene"]["id"].startswith("scene_")
    assert len(projection["asset_ids"]) == 2
    with pytest.raises(KeyError):
        manager.projection(job.id, "job:another")
    assert host.updates[-1]["status"] == "succeeded"
    assert projection["host_terminal_sent"] is True
    await manager.stop()


class BlockingWorkspace:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    def recipe_runtime_pin(self, owner: str, value: object) -> tuple[str, str, None]:
        return "blender-test", "4.5.9", None

    async def apply_recipe(
        self,
        owner: str,
        job_id: str,
        value: object,
        *,
        runtime_id: str,
        runtime_version: str,
    ) -> dict[str, Any]:
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


def test_scene_recipe_cancel_is_owner_scoped_and_terminal(tmp_path: Path) -> None:
    asyncio.run(_cancel_case(tmp_path))


async def _cancel_case(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.initialize()
    host = Host()
    workspace = BlockingWorkspace()
    manager = SceneRecipeJobManager(store, workspace, host)  # type: ignore[arg-type]
    job, _ = await manager.submit(recipe(), IDENTITY)
    await workspace.started.wait()
    with pytest.raises(KeyError):
        await manager.cancel(job.id, "job:another")
    canceled = await manager.cancel(job.id, "user:7")
    assert canceled["status"] == "canceled"
    assert canceled["stage"] == "canceled"
    assert host.updates[-1]["status"] == "canceled"
    await manager.stop()


class RemoteCancelHost(Host):
    async def job_control(
        self, identity: HostIdentity, host_job_id: str
    ) -> dict[str, Any]:
        return {"cancel_requested": True}


def test_host_child_cancel_stops_the_scene_runner(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = Store(tmp_path)
        store.initialize()
        host = RemoteCancelHost()
        workspace = BlockingWorkspace()
        manager = SceneRecipeJobManager(
            store, workspace, host, control_poll_sec=0.01  # type: ignore[arg-type]
        )
        job, _ = await manager.submit(recipe(), IDENTITY)
        await manager.wait_cleanup(job.id)
        value = manager.projection(job.id, "user:7")
        assert value["status"] == "canceled"
        assert value["host_terminal_sent"] is True
        await manager.stop()

    asyncio.run(scenario())


def test_host_cancel_stops_a_job_waiting_for_the_blender_slot(tmp_path: Path) -> None:
    class TwoJobHost(Host):
        def __init__(self) -> None:
            super().__init__()
            self.count = 0

        async def create_or_attach_job(
            self, identity: HostIdentity, *, title: str, detached: bool = False
        ) -> dict[str, Any]:
            self.count += 1
            return {
                "created": True,
                "job": {"id": f"host-child-{self.count}"},
                "access_token": "child-secret",
                "expires_at": 4_000_000_000,
            }

        async def update_job(
            self, identity: HostIdentity, host_job_id: str, payload: dict[str, Any]
        ) -> dict[str, Any]:
            self.updates.append({"id": host_job_id, **payload})
            return payload

        async def job_control(
            self, identity: HostIdentity, host_job_id: str
        ) -> dict[str, Any]:
            return {"cancel_requested": host_job_id == "host-child-2"}

    async def scenario() -> None:
        store = Store(tmp_path)
        store.initialize()
        host = TwoJobHost()
        workspace = BlockingWorkspace()
        manager = SceneRecipeJobManager(
            store, workspace, host, control_poll_sec=0.01  # type: ignore[arg-type]
        )
        first, _ = await manager.submit(recipe(), IDENTITY)
        await workspace.started.wait()
        second, _ = await manager.submit(recipe(), IDENTITY)
        await manager.wait_cleanup(second.id)
        assert manager.projection(second.id, "user:7")["status"] == "canceled"
        assert store.get_job(first.id).status == JobStatus.RUNNING
        await manager.cancel(first.id, "user:7")
        await manager.stop()

    asyncio.run(scenario())


def test_scene_manager_shutdown_reports_failed_child_terminal(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = Store(tmp_path)
        store.initialize()
        host = Host()
        workspace = BlockingWorkspace()
        manager = SceneRecipeJobManager(store, workspace, host)  # type: ignore[arg-type]
        job, _ = await manager.submit(recipe(), IDENTITY)
        await workspace.started.wait()
        await manager.stop()
        value = manager.projection(job.id, "user:7")
        assert value["status"] == "failed"
        assert value["stage"] == "service_stopped"
        assert value["host_terminal_sent"] is True
        assert host.updates[-1]["status"] == "failed"
        assert host.updates[-1]["error"] == "service_stopped"

    asyncio.run(scenario())


class FailOnceWorkspace(Workspace):
    def __init__(self) -> None:
        self.calls = 0

    async def apply_recipe(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            raise SceneError("scene_recipe_failed", "first attempt failed")
        return await super().apply_recipe(*args, **kwargs)


def test_failed_scene_job_retries_as_new_attempt_with_same_input(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = Store(tmp_path)
        store.initialize()
        manager = SceneRecipeJobManager(
            store, FailOnceWorkspace(), Host()  # type: ignore[arg-type]
        )
        first, _ = await manager.submit(recipe(), IDENTITY)
        await manager.wait_cleanup(first.id)
        assert manager.projection(first.id, "user:7")["status"] == "failed"
        retry = recipe().model_copy(update={"retry_job_id": first.id})
        second, _ = await manager.submit(retry, IDENTITY, retry_of=first.id)
        await manager.wait_cleanup(second.id)
        first_value = manager.projection(first.id, "user:7")
        second_value = manager.projection(second.id, "user:7")
        assert second.id != first.id
        assert second_value["status"] == "succeeded"
        assert second_value["retry_of"] == first.id
        assert second_value["input_sha256"] == first_value["input_sha256"]
        assert second_value["idempotency_key"] == first_value["idempotency_key"]
        await manager.stop()

    asyncio.run(scenario())


class RefreshHost(Host):
    def __init__(self) -> None:
        super().__init__()
        self.refreshes = 0

    async def create_or_attach_job(
        self, identity: HostIdentity, *, title: str, detached: bool = False
    ) -> dict[str, Any]:
        value = await super().create_or_attach_job(
            identity, title=title, detached=detached
        )
        value["expires_at"] = int(time.time()) + 2
        return value

    async def refresh_job_credential(
        self, identity: HostIdentity, host_job_id: str
    ) -> dict[str, Any]:
        self.refreshes += 1
        return {
            "access_token": "refreshed",
            "expires_at": int(time.time()) + 600,
        }

    async def update_job(
        self, identity: HostIdentity, host_job_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        assert identity.authorization in {"Bearer child-secret", "Bearer refreshed"}
        self.updates.append({"id": host_job_id, **payload})
        return payload


class SlowWorkspace(Workspace):
    async def apply_recipe(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return await super().apply_recipe(*args, **kwargs)


def test_scene_job_refreshes_child_credential_before_expiry(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = Store(tmp_path)
        store.initialize()
        host = RefreshHost()
        manager = SceneRecipeJobManager(
            store,
            SlowWorkspace(),  # type: ignore[arg-type]
            host,  # type: ignore[arg-type]
            control_poll_sec=0.005,
        )
        job, _ = await manager.submit(recipe(), IDENTITY)
        await manager.wait_cleanup(job.id)
        assert manager.projection(job.id, "user:7")["status"] == "succeeded"
        assert host.refreshes == 1
        await manager.stop()

    asyncio.run(scenario())


def test_scene_recipe_rejects_unknown_operations_and_unbounded_values() -> None:
    with pytest.raises(ValueError):
        SceneCreateRequest.model_validate({
            "name": "unsafe",
            "recipe": {"operations": [{"type": "python.exec", "code": "import os"}]},
        })
    with pytest.raises(ValueError):
        SceneCreateRequest.model_validate({
            "name": "huge",
            "recipe": {"operations": [{
                "type": "primitive.add", "object_id": "cube", "primitive": "cube",
                "name": "Cube", "dimensions": [1001, 1, 1],
            }]},
        })


def test_scene_task_restart_fails_closed_with_persisted_stage(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.initialize()
    for running in (False, True):
        job = store.create_job(
            JobRequest(
                operation="media.inspect",
                intent="scene task",
                constraints={"scene_operation": "scene.create"},
            ),
            host_managed=True,
        )
        store.create_scene_recipe_task(
            job.id,
            owner="user:7",
            host_job_id="host-child",
            operation="scene.create",
            runtime_id="blender-test",
            runtime_version="4.5.9",
            base_revision_id=None,
            input_sha256="1" * 64,
            idempotency_key="2" * 64,
            request=recipe().model_dump(mode="json", exclude={"retry_job_id"}),
        )
        if running:
            store.update_job(job.id, status=JobStatus.RUNNING, phase="blender_recipe")
            store.update_scene_recipe_task(job.id, stage="blender_recipe")
    Store(tmp_path).initialize()
    values = sorted(
        (
            Store(tmp_path).get_job(item.id).error.code,
            Store(tmp_path).get_scene_recipe_task(item.id).stage,
        )
        for item in store.list_jobs()
    )
    assert values == [
        ("host_context_lost", "host_context_lost"),
        ("service_restarted", "service_restarted"),
    ]
