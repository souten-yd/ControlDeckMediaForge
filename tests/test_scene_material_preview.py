from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from mediaforge.material_binding import MaterialBinding
from mediaforge.scene_material_preview import MaterialPreviewManager
from mediaforge.scenes import SceneError
from test_scene_workspace import fake_scene_workspace, register_image, upload_scene


def fixture(tmp_path: Path, *, now: list[datetime] | None = None) -> tuple[Any, ...]:
    store, workspace, resolver = fake_scene_workspace(tmp_path, now=now)
    imported = upload_scene(workspace, b"BLENDER-original-material")
    image = register_image(store, tmp_path)
    binding = MaterialBinding(source_revision_id=imported["revision"]["id"],
                              image_asset_id=image.id, object_name="Cube",
                              material_slot=0, channel="base_color", uv_map="UVMap")
    manager = MaterialPreviewManager(workspace)
    manager.initialize()
    return store, workspace, resolver, manager, imported["scene"]["id"], binding


def test_prepare_discard_never_publishes_and_adopt_is_idempotent(tmp_path: Path) -> None:
    store, workspace, resolver, manager, scene_id, binding = fixture(tmp_path)
    before = workspace.catalog.get("user:1", scene_id)
    assets_before = [a.id for a in store.list_assets()]
    source_hash = store.get_asset(before[1][0].source_asset_id).sha256

    async def run() -> None:
        candidate = await manager.prepare("user:1", "connection-a", scene_id, binding)
        assert candidate["saved"] is False
        assert not any("path" in key or "owner" in key for key in candidate)
        assert workspace.catalog.get("user:1", scene_id) == before
        assert [a.id for a in store.list_assets()] == assets_before
        assert resolver.references == 1
        content = await manager.read("user:1", "connection-a", candidate["candidate_id"], 0)
        assert base64.b64decode(content["base64"])[:4] == b"glTF"
        await manager.discard("user:1", "connection-a", candidate["candidate_id"])
        assert resolver.references == 0
        assert list(manager.root.iterdir()) == []
        assert workspace.catalog.get("user:1", scene_id) == before
        assert [a.id for a in store.list_assets()] == assets_before
        candidate = await manager.prepare("user:1", "connection-a", scene_id, binding)
        result = await manager.adopt("user:1", "connection-a", candidate["candidate_id"])
        assert result["revision"]["sequence"] == 2
        assert result["revision"]["parent_revision_id"] == binding.source_revision_id
        assert result["revision"]["dependencies"][0]["asset_id"] == binding.image_asset_id
        assert store.get_asset(before[1][0].source_asset_id).sha256 == source_hash
        provenance = store.get_provenance(result["revision"]["source_asset_id"])
        assert provenance.parameters["preview_candidate_id"] == candidate["candidate_id"]
        assert provenance.parameters["preview_source_sha256"] == store.get_asset(result["revision"]["source_asset_id"]).sha256
        assert result == await manager.adopt("user:1", "connection-a", candidate["candidate_id"])
        assert len(workspace.catalog.get("user:1", scene_id)[1]) == 2
        assert resolver.references == 0
        assert list(manager.root.iterdir()) == []
    asyncio.run(run())


def test_preview_owner_connection_bounds_and_expiry(tmp_path: Path) -> None:
    now = [datetime(2026, 9, 5, 12, tzinfo=UTC)]
    _, workspace, resolver, manager, scene_id, binding = fixture(tmp_path, now=now)
    before = workspace.catalog.get("user:1", scene_id)

    async def run() -> None:
        candidate = await manager.prepare("user:1", "a", scene_id, binding)
        key = candidate["candidate_id"]
        for owner, connection in [("user:2", "a"), ("user:1", "b")]:
            for operation in [manager.adopt, manager.discard]:
                with pytest.raises(SceneError, match="unavailable"):
                    await operation(owner, connection, key)
            with pytest.raises(SceneError, match="unavailable"):
                await manager.read(owner, connection, key, 0)
        for offset, length in [(-1, 1), (True, 1), (0, True), (0, 524289), (candidate["total_bytes"], 1)]:
            with pytest.raises(SceneError, match="range"):
                await manager.read("user:1", "a", key, offset, length)
        with pytest.raises(SceneError, match="existing"):
            await manager.prepare("user:1", "a", scene_id, binding)
        await manager.prepare("user:1", "b", scene_id, binding)
        with pytest.raises(SceneError, match="existing"):
            await manager.prepare("user:1", "c", scene_id, binding)
        assert resolver.references == 2
        now[0] += timedelta(minutes=11)
        await manager.expire()
        assert resolver.references == 0
        assert list(manager.root.iterdir()) == []
        with pytest.raises(SceneError, match="unavailable"):
            await manager.adopt("user:1", "a", key)
        assert workspace.catalog.get("user:1", scene_id) == before
    asyncio.run(run())


@pytest.mark.parametrize("change", ["source", "preview", "dependency", "head"])
def test_adopt_rejects_changed_input_and_preserves_head(tmp_path: Path, change: str) -> None:
    store, workspace, resolver, manager, scene_id, binding = fixture(tmp_path)

    async def run() -> None:
        candidate = await manager.prepare("user:1", "a", scene_id, binding)
        key = candidate["candidate_id"]
        if change == "head":
            await workspace.apply_material_binding("user:1", scene_id, binding)
        else:
            path = (store.asset_path(binding.image_asset_id) if change == "dependency"
                    else manager.root / key / ("scene.blend" if change == "source" else "preview.glb"))
            path.write_bytes(b"changed")
        before = workspace.catalog.get("user:1", scene_id)
        with pytest.raises(SceneError, match="changed"):
            await manager.adopt("user:1", "a", key)
        assert workspace.catalog.get("user:1", scene_id) == before
        await manager.cleanup("user:1", "a")
        assert resolver.references == 0
        assert list(manager.root.iterdir()) == []
    asyncio.run(run())


def test_prepare_cancel_and_restart_cleanup(tmp_path: Path) -> None:
    _, workspace, resolver, manager, scene_id, binding = fixture(tmp_path)
    before = workspace.catalog.get("user:1", scene_id)

    async def run() -> None:
        original = workspace._material_operation
        entered = asyncio.Event()

        async def wait(*args: Any, **kwargs: Any) -> None:
            entered.set()
            await asyncio.Event().wait()

        workspace._material_operation = wait
        task = asyncio.create_task(manager.prepare("user:1", "a", scene_id, binding))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        workspace._material_operation = original
        assert resolver.references == 0
        assert list(manager.root.iterdir()) == []
        assert workspace.catalog.get("user:1", scene_id) == before
        await manager.prepare("user:1", "a", scene_id, binding)
        await manager.cleanup("user:1", "a")
    asyncio.run(run())
    orphan = manager.root / "orphan"
    orphan.mkdir()
    (orphan / "scene.blend").write_bytes(b"BLENDER-orphan")
    restarted = MaterialPreviewManager(workspace)
    restarted.initialize()
    assert list(restarted.root.iterdir()) == []
    assert workspace.catalog.get("user:1", scene_id) == before


def test_adoption_finishes_on_disconnect_and_retry_does_not_duplicate(tmp_path: Path) -> None:
    _, workspace, resolver, manager, scene_id, binding = fixture(tmp_path)

    async def run() -> None:
        candidate = await manager.prepare("user:1", "a", scene_id, binding)
        entered, finish = asyncio.Event(), asyncio.Event()
        original = workspace.commit_working_copy

        async def commit(*args: Any, **kwargs: Any) -> dict[str, Any]:
            entered.set()
            await finish.wait()
            return await original(*args, **kwargs)

        workspace.commit_working_copy = commit
        task = asyncio.create_task(manager.adopt("user:1", "a", candidate["candidate_id"]))
        await entered.wait()
        task.cancel()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        result = await manager.adopt("user:1", "a", candidate["candidate_id"])
        assert result["revision"]["sequence"] == 2
        assert len(workspace.catalog.get("user:1", scene_id)[1]) == 2
        assert resolver.references == 0
        assert list(manager.root.iterdir()) == []
    asyncio.run(run())


def test_preview_directory_symlink_is_rejected_without_deleting_target(tmp_path: Path) -> None:
    _, _, resolver, manager, scene_id, binding = fixture(tmp_path)

    async def run() -> None:
        candidate = await manager.prepare("user:1", "a", scene_id, binding)
        root = manager.root / candidate["candidate_id"]
        original = manager.root / "preserved"
        root.rename(original)
        root.symlink_to(original, target_is_directory=True)
        with pytest.raises(SceneError, match="changed"):
            await manager.read("user:1", "a", candidate["candidate_id"], 0)
        await manager.cleanup("user:1", "a")
        assert original.is_dir()
        assert not root.is_symlink()
        assert resolver.references == 0
    asyncio.run(run())
