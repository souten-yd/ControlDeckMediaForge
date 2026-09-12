from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mediaforge.domain import JobStatus
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
