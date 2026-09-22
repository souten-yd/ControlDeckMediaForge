from __future__ import annotations

import json
from typing import Any

import pytest
from pathlib import Path

from mediaforge.material_binding import SceneTextureRequest
from mediaforge.scenes import SceneCatalog
from mediaforge.store import Store
from test_host_execution import host_client
from test_scenes import _register, _revision_assets, _revision_input
from test_workspace_transport import call


def set_context(store: Store, asset_id: str, value: dict[str, Any], *, extraction: bool = False) -> None:
    provenance = store.get_provenance(asset_id)
    provenance.parameters = {"scene_texture": value} if extraction else {"constraints": {"scene_texture": value}}
    with store._connect() as connection:
        connection.execute("UPDATE assets SET provenance_json = ? WHERE id = ?", (provenance.model_dump_json(), asset_id))


def test_texture_links_survive_edits_job_removal_and_new_revisions(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    source, preview, _ = _revision_assets(store, tmp_path)
    catalog = SceneCatalog(store)
    scene, revision = catalog.create("user:alpha", name="Chest", revision=_revision_input(source, preview))
    texture = _register(store, tmp_path, mime_type="image/png", content=b"extracted", parents=[source.id])
    context = SceneTextureRequest(scene_id=scene.id, source_revision_id=revision.id,
                                  object_name="Mesh_0", material_slot=0, uv_map="UVMap").model_dump(mode="json")
    set_context(store, texture.id, context, extraction=True)
    edited = _register(store, tmp_path, mime_type="image/png", content=b"edited", parents=[texture.id])
    twice = _register(store, tmp_path, mime_type="image/png", content=b"edited again", parents=[edited.id])
    next_source, next_preview, _ = _revision_assets(store, tmp_path)
    _, next_revision = catalog.commit("user:alpha", scene.id, revision.id, _revision_input(next_source, next_preview))
    with store._connect() as connection:
        connection.execute("UPDATE jobs SET status = 'succeeded'")
    assert store.clear_finished_jobs() > 0
    assert store.list_jobs() == []
    reloaded = Store(store.data_dir)
    links = reloaded.asset_relations(twice.id, owner="user:alpha")["scene_links"]
    assert len(links) == 1
    assert links[0] == {"scene_id": scene.id, "scene_name": "Chest", "source_revision_id": revision.id,
                       "source_sequence": 1, "current_revision_id": next_revision.id,
                       "preview_asset_id": preview.id, "material_selection": context}
    assert reloaded.asset_scene_links(preview.id, "user:alpha")[0]["source_revision_id"] == revision.id
    assert reloaded.asset_scene_links(next_preview.id, "user:alpha")[0]["source_sequence"] == 2
    assert not reloaded.asset_scene_links(twice.id, "user:other")
    assert reloaded.asset_relations(twice.id)["scene_links"] == []


def test_context_without_parent_and_foreign_revision_are_checked(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    source, preview, _ = _revision_assets(store, tmp_path)
    scene, revision = SceneCatalog(store).create("user:alpha", name="Allowed", revision=_revision_input(source, preview))
    other_source, other_preview, _ = _revision_assets(store, tmp_path)
    other_scene, other_revision = SceneCatalog(store).create("user:other", name="Secret", revision=_revision_input(other_source, other_preview))
    image = _register(store, tmp_path, mime_type="image/png", content=b"new texture")
    context = SceneTextureRequest(scene_id=scene.id, source_revision_id=revision.id,
                                  object_name="Mesh", material_slot=0, uv_map="UV").model_dump(mode="json")
    set_context(store, image.id, context)
    assert store.asset_scene_links(image.id, "user:alpha")[0]["material_selection"] == context
    provenance = store.get_provenance(image.id)
    provenance.parameters = {"constraints": {"source_scene_texture": context}}
    with store._connect() as connection:
        connection.execute("UPDATE assets SET provenance_json = ? WHERE id = ?", (provenance.model_dump_json(), image.id))
    assert store.asset_scene_links(image.id, "user:alpha")[0]["material_selection"] == context
    for forged in [dict(context, source_revision_id=other_revision.id),
                   dict(context, scene_id=other_scene.id, source_revision_id=other_revision.id),
                   dict(context, material_slot=-1)]:
        set_context(store, image.id, forged)
        assert store.asset_scene_links(image.id, "user:alpha") == []


def test_scene_links_private_transports_are_owner_scoped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, headers, _ = host_client(tmp_path / "app", token="valid-user")
    with client:
        store = client.app.state.store
        source, preview, _ = _revision_assets(store, tmp_path)
        scene, _ = SceneCatalog(store).create("user:7", name="Host scene", revision=_revision_input(source, preview))
        def no_bytes(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("navigation must read metadata only")
        monkeypatch.setattr(store, "asset_path", no_bytes)
        with client.websocket_connect("/ws", headers=headers) as socket:
            result = call(socket, "assets.relations", {"asset_id": preview.id})
            assert result["ok"], result
            assert result["result"]["scene_links"][0]["scene_id"] == scene.id
            assert not call(socket, "assets.relations", {"asset_id": preview.id, "owner": "user:7"})["ok"]
        assert client.get(f"/workspace-api/assets/{preview.id}/relations").json()["scene_links"] == []
        assert "storage_name" not in json.dumps(result)
