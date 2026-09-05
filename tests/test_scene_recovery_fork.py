from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.scenes import SceneDependency, SceneError, SceneRevisionInput
from test_host_execution import host_client
from test_scene_workspace import fake_scene_workspace, register_image, upload_scene
from test_workspace_transport import call


def candidate(workspace: SceneWorkspace, owner: str = "user:1") -> tuple[str, str, Path]:
    imported = upload_scene(workspace, b"BLENDER-original", owner=owner)
    scene_id = imported["scene"]["id"]
    working = workspace.acquire_working_copy(owner, scene_id)
    path = workspace.working_path_for_runtime(owner, working.id)
    path.write_bytes(b"BLENDER-unsaved-recovery")
    workspace.retain_working_copy_for_recovery(owner, working.id)
    # Advance the head without changing the candidate's base.
    revision = imported["revision"]
    workspace.catalog.commit(owner, scene_id, revision["id"], SceneRevisionInput(**{
        key: revision[key] for key in SceneRevisionInput.model_fields
    }))
    return scene_id, working.id, path


def test_conflict_fork_preserves_head_candidate_and_lineage_and_is_restart_idempotent(tmp_path: Path) -> None:
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    scene_id, working_id, path = candidate(workspace)
    before = workspace.catalog.get("user:1", scene_id)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(SceneError, match="scene changed"):
        workspace.acquire_recovery_working_copy("user:1", scene_id, working_id)
    result = asyncio.run(workspace.fork_recovery("user:1", scene_id, working_id))
    assert result["scene"]["id"] != scene_id
    assert result["revision"]["sequence"] == 1
    assert workspace.catalog.get("user:1", scene_id) == before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert store.get_scene_working_copy("user:1", working_id).state == "recovery"
    source = store.get_asset(result["revision"]["source_asset_id"])
    provenance = store.get_provenance(source.id)
    assert source.sha256 == digest
    assert before[1][0].source_asset_id in source.parent_asset_ids
    assert provenance.operation == "scene.recovery.fork"
    assert provenance.parameters["source_revision_id"] == before[1][0].id
    assert provenance.parameters["recovery_sha256"] == digest
    assert provenance.reference_asset_hashes[before[1][0].source_asset_id] == store.get_asset(before[1][0].source_asset_id).sha256
    assert resolver.references == 0
    assert not list(workspace.validation_root.iterdir())
    restarted = SceneWorkspace(store, resolver, workspace.worker)  # type: ignore[arg-type]
    restarted.initialize()
    repeated = asyncio.run(restarted.fork_recovery("user:1", scene_id, working_id))
    assert repeated == result
    assert len(store.list_scenes("user:1")) == 2
    assert len(store.list_assets()) == 4


@pytest.mark.parametrize("failure", ["owner", "scene", "missing", "invalid", "symlink", "runtime"])
def test_failed_recovery_fork_preserves_original_and_does_not_publish(tmp_path: Path, failure: str) -> None:
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    scene_id, working_id, path = candidate(workspace)
    original = workspace.catalog.get("user:1", scene_id)
    before_assets = store.list_assets()
    owner = "user:1"
    target_scene = scene_id
    if failure == "owner":
        owner = "user:2"
    elif failure == "scene":
        target_scene = "scene_" + "0" * 32
    elif failure == "missing":
        path.unlink()
    elif failure == "invalid":
        path.write_bytes(b"not-blender")
    elif failure == "symlink":
        other = path.with_name("other.blend")
        path.rename(other)
        path.symlink_to(other.name)
    else:
        resolver.runtime = replace(resolver.runtime, version="4.5.99")
    with pytest.raises(SceneError):
        asyncio.run(workspace.fork_recovery(owner, target_scene, working_id))
    assert workspace.catalog.get("user:1", scene_id) == original
    assert store.list_assets() == before_assets
    assert len(store.list_scenes("user:1")) == 1
    assert store.get_scene_working_copy("user:1", working_id).state == "recovery"
    assert resolver.references == 0
    assert not list(workspace.validation_root.iterdir())


def test_recovery_cancel_cleans_staging_and_allows_retry(tmp_path: Path) -> None:
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    scene_id, working_id, path = candidate(workspace)
    original_validate = workspace._validate

    async def exercise() -> None:
        entered = asyncio.Event()

        async def wait_validate(*args: object) -> None:
            entered.set()
            await asyncio.Event().wait()

        workspace._validate = wait_validate  # type: ignore[method-assign,assignment]
        task = asyncio.create_task(workspace.fork_recovery("user:1", scene_id, working_id))
        await entered.wait()
        with pytest.raises(SceneError) as busy:
            await workspace.fork_recovery("user:1", scene_id, working_id)
        assert busy.value.code == "scene_recovery_busy"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert path.read_bytes() == b"BLENDER-unsaved-recovery"
        assert resolver.references == 0
        assert not list(workspace.validation_root.iterdir())
        assert len(store.list_scenes("user:1")) == 1
        workspace._validate = original_validate  # type: ignore[method-assign]
        await workspace.fork_recovery("user:1", scene_id, working_id)

    asyncio.run(exercise())
    assert len(store.list_scenes("user:1")) == 2


@pytest.mark.parametrize("embedded", [False, True])
def test_recovery_fork_transport_and_candidate_list(tmp_path: Path, embedded: bool) -> None:
    _store, fixture, resolver = fake_scene_workspace(tmp_path / "fixture")
    client, headers, _state = host_client(tmp_path / "app", token="valid-user")
    owner = "user:7" if embedded else "local"
    with client:
        workspace = client.app.state.scene_workspace
        workspace.resolver = resolver
        workspace.worker = fixture.worker
        scene_id, working_id, path = candidate(workspace, owner)
        if embedded:
            with client.websocket_connect("/ws", headers=headers) as socket:
                listed = call(socket, "scenes.list", {})
                assert working_id in {item["id"] for item in listed["result"]["working_copies"]}
                response = call(socket, "scenes.recovery.fork", {"scene_id": scene_id, "recovery_working_id": working_id})
                assert response["ok"], response
                result = response["result"]
        else:
            url = f"/workspace-api/scenes/{scene_id}/recovery/fork"
            assert client.post(url, json={"recovery_working_id": working_id, "path": "/tmp/file"}).status_code == 422
            response = client.post(url, json={"recovery_working_id": working_id})
            assert response.status_code == 200, response.text
            result = response.json()
        assert "path" not in json.dumps(result)
        assert result["scene"]["id"] != scene_id
        assert path.read_bytes() == b"BLENDER-unsaved-recovery"


def test_recovery_fork_preserves_and_verifies_dependency_bytes(tmp_path: Path) -> None:
    store, workspace, _resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER-textured")
    image = register_image(store, tmp_path)
    revision = imported["revision"]
    dependencies = [SceneDependency(role="base-color", asset_id=image.id, sha256=image.sha256)]
    workspace.catalog.commit("user:1", imported["scene"]["id"], revision["id"], SceneRevisionInput(**{
        **{key: revision[key] for key in SceneRevisionInput.model_fields}, "dependencies": dependencies,
    }))
    scene_id = imported["scene"]["id"]
    working = workspace.acquire_working_copy("user:1", scene_id)
    workspace.retain_working_copy_for_recovery("user:1", working.id)
    image_path = store.asset_path(image.id)
    original_image = image_path.read_bytes()
    image_path.write_bytes(b"changed")
    with pytest.raises(SceneError) as changed:
        asyncio.run(workspace.fork_recovery("user:1", scene_id, working.id))
    assert changed.value.code == "scene_dependency_changed"
    assert len(store.list_scenes("user:1")) == 1
    image_path.write_bytes(original_image)
    result = asyncio.run(workspace.fork_recovery("user:1", scene_id, working.id))
    assert result["revision"]["dependencies"] == [item.model_dump() for item in dependencies]


def test_failed_fork_commit_rolls_back_new_assets_and_preview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, workspace, _resolver = fake_scene_workspace(tmp_path)
    scene_id, working_id, path = candidate(workspace)
    before_assets = store.list_assets()

    def fail(*args: object, **kwargs: object) -> None:
        raise SceneError("scene_asset_invalid", "injected commit failure")

    monkeypatch.setattr(workspace.catalog, "create", fail)
    with pytest.raises(SceneError) as failed:
        asyncio.run(workspace.fork_recovery("user:1", scene_id, working_id))
    assert failed.value.code == "scene_asset_invalid"
    assert store.list_assets() == before_assets
    assert len(store.list_scenes("user:1")) == 1
    assert path.read_bytes() == b"BLENDER-unsaved-recovery"
    assert not list(workspace.validation_root.iterdir())
