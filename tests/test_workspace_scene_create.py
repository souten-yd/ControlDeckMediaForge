from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mediaforge.domain import JobStatus
from mediaforge.domain import JobRequest
from mediaforge.host.client import HostApiError
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_recipes import workspace_scene_create_request
from mediaforge.scenes import SceneError
from test_host_execution import host_client
from test_workspace_transport import call


@pytest.mark.parametrize("params", [
    {}, {"name": ""}, {"name": "   "}, {"name": "x" * 121}, {"name": "../file"},
    {"name": "a\nb"}, {"name": 42}, {"name": "cube", "owner": "user:8"},
    {"name": "cube", "recipe": {}}, {"name": "cube", "runtime_id": "other"},
])
def test_workspace_request_is_label_only(params: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        workspace_scene_create_request(params)


def test_workspace_recipe_is_fixed_and_each_request_is_independent() -> None:
    first = workspace_scene_create_request({"name": "  ロボットの試作  "})
    assert first.name == "ロボットの試作"
    assert first.retry_job_id is None and first.tags == [] and first.collection is None
    operation = first.recipe.operations[0]
    assert operation.type == "primitive.add" and operation.primitive == "cube"
    assert operation.name == "Cube" and operation.dimensions == (2, 2, 2)
    first.recipe.operations.clear()
    assert len(workspace_scene_create_request({"name": "Next"}).recipe.operations) == 1


def test_authenticated_websocket_uses_existing_durable_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[Any] = []
    async def submit(self: Any, value: Any, identity: Any, *, retry_of: Any = None) -> Any:
        received.append((value, identity, retry_of))
        return (SimpleNamespace(id="job_" + "a" * 32, status=JobStatus.QUEUED, asset_ids=[]),
                SimpleNamespace(host_job_id="host-child", input_sha256="b" * 64))
    monkeypatch.setattr(SceneRecipeJobManager, "submit", submit)
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        answer = call(socket, "scenes.create", {"name": "New scene"})
        invalid = call(socket, "scenes.create", {"name": "bad", "script": "print(1)"})
    assert answer["ok"] is True, answer
    assert answer["result"] == {
        "job_id": "job_" + "a" * 32, "status": "queued", "asset_ids": [],
        "detached": True, "host_job_id": "host-child", "input_sha256": "b" * 64,
    }
    assert invalid["ok"] is False and len(received) == 1
    value, identity, retry = received[0]
    assert value.name == "New scene" and retry is None
    assert (identity.actor_subject or identity.subject) == "user:7"


@pytest.mark.parametrize("failure", [
    SceneError("blender_runtime_missing", "runtime missing"),
    HostApiError("host_unreachable", "host unavailable"),
])
def test_admission_errors_are_returned_without_claiming_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception,
) -> None:
    async def submit(*args: Any, **kwargs: Any) -> Any:
        raise failure
    monkeypatch.setattr(SceneRecipeJobManager, "submit", submit)
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        answer = call(socket, "scenes.create", {"name": "New scene"})
    assert answer["ok"] is False and answer["error"]["code"] == failure.code
    assert "result" not in answer


def test_creation_history_is_owned_durable_and_ignores_cleared_jobs(tmp_path: Path) -> None:
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.store
        ids = []
        for owner, operation in [("user:7", "scene.create"), ("user:8", "scene.create"), ("user:7", "scene.edit")]:
            job = store.create_job(JobRequest(operation="media.inspect", intent="fixture"), host_managed=True)
            ids.append(job.id)
            store.create_scene_recipe_task(job.id, owner=owner, host_job_id="fixture", operation=operation,
                runtime_id="fixture", runtime_version="4.5.9", base_revision_id=None,
                input_sha256="a" * 64, idempotency_key="b" * 64, request={"name": "<b>Robot</b>"})
        for _ in range(2):
            with client.websocket_connect("/ws", headers=headers) as socket:
                answer = call(socket, "scenes.creation.list", {})
                assert answer["ok"] is True, answer
                assert [item["job_id"] for item in answer["result"]["items"]] == [ids[0]]
                assert answer["result"]["items"][0]["name"] == "<b>Robot</b>"
                denied = call(socket, "scenes.creation.cancel", {"job_id": ids[1]})
                assert denied["ok"] is False
        assert store.get_job(ids[1]).status == JobStatus.QUEUED
        assert not store.cancel_requested(ids[1])
        store.update_job(ids[0], status=JobStatus.SUCCEEDED)
        store.clear_finished_jobs()
        assert store.list_scene_creation_job_ids("user:7") == []


def test_creation_capability_requires_host_identity_even_without_runtime(tmp_path: Path) -> None:
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client:
        with client.websocket_connect("/ws", headers=headers) as socket:
            result = call(socket, "capabilities.get", {})["result"]
            assert result["capabilities"]["3d.scene_recipe"]["workspace_create"] is True
        result = client.get("/api/v1/capabilities").json()
        assert result["capabilities"]["3d.scene_recipe"]["workspace_create"] is False
