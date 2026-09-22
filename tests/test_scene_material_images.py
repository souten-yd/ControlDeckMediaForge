from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mediaforge.material_binding import SceneTextureRequest
from mediaforge.scenes import SceneCatalog, SceneError, SceneDependency
from mediaforge.store import Store
from test_asset_scene_links import set_context
from test_host_execution import host_client
from test_scenes import _register, _revision_assets, _revision_input
from test_workspace_transport import call


def test_sources_and_variants_are_durable_and_exclude_unrelated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Store(tmp_path / 'data')
    store.initialize()
    photo = _register(store, tmp_path, mime_type='image/png', content=b'photo')
    source = _register(store, tmp_path, mime_type='application/x-blender', content=b'blend', parents=[photo.id])
    _, _, dependency = _revision_assets(store, tmp_path)
    preview = _register(store, tmp_path, mime_type="model/gltf-binary", content=b"preview", parents=[source.id])
    revision_input = _revision_input(source, preview, dependency)
    revision_input.dependencies[0].role = 'material.base_color.mesh.0'
    revision_input.dependencies.append(SceneDependency(role='generation_input', asset_id=photo.id, sha256=photo.sha256))
    scene, revision = SceneCatalog(store).create('user:a', name='Chest', revision=revision_input)
    selection = SceneTextureRequest(scene_id=scene.id, source_revision_id=revision.id,
                                   object_name='Mesh', material_slot=0, uv_map='UVMap').model_dump(mode='json')
    extracted = _register(store, tmp_path, mime_type='image/png', content=b'extracted', parents=[source.id])
    set_context(store, extracted.id, selection, extraction=True)
    provenance = store.get_provenance(extracted.id)
    provenance.operation = 'scene.material.extract'
    with store._connect() as connection:
        connection.execute('UPDATE assets SET provenance_json=? WHERE id=?', (provenance.model_dump_json(), extracted.id))
    edited = _register(store, tmp_path, mime_type='image/png', content=b'edited', parents=[extracted.id])
    twice = _register(store, tmp_path, mime_type='image/png', content=b'twice', parents=[edited.id])
    generated = _register(store, tmp_path, mime_type='image/png', content=b'generated')
    set_context(store, generated.id, selection)
    # Shared photo does not authorize every other 3D branch made from it.
    other_model = _register(store, tmp_path, mime_type='application/x-blender', content=b'other blend', parents=[photo.id])
    _register(store, tmp_path, mime_type='image/png', content=b'other texture', parents=[other_model.id])
    foreign = _register(store, tmp_path, mime_type='image/png', content=b'foreign', parents=[photo.id])
    set_context(store, foreign.id, dict(selection, source_revision_id='revision_' + 'f' * 32))
    malformed = _register(store, tmp_path, mime_type='image/png', content=b'malformed', parents=[photo.id])
    set_context(store, malformed.id, dict(selection, material_slot=-1))
    for index in range(125):
        _register(store, tmp_path, mime_type='image/png', content=str(index).encode())
    with store._connect() as connection:
        connection.execute("UPDATE jobs SET status='succeeded'")
    store.clear_finished_jobs()
    store = Store(store.data_dir)
    def no_bytes(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Picker reads metadata only')
    monkeypatch.setattr(store, 'asset_path', no_bytes)
    items, truncated = store.scene_material_image_records(scene.id, 'user:a')
    assert not truncated
    assert {asset.id: role for asset, _, role in items} == {
        photo.id: 'base', dependency.id: 'used', extracted.id: 'base', edited.id: 'variant',
        twice.id: 'variant', generated.id: 'variant',
    }
    assert items[0][0].id == dependency.id
    with pytest.raises(SceneError):
        store.scene_material_image_records(scene.id, 'user:other')


def test_picker_bounds_are_visible(tmp_path: Path) -> None:
    store = Store(tmp_path / 'data')
    store.initialize()
    source, preview, dependency = _revision_assets(store, tmp_path)
    scene, _ = SceneCatalog(store).create('user:a', name='Chain', revision=_revision_input(source, preview, dependency))
    parent = dependency.id
    for index in range(12):
        parent = _register(store, tmp_path, mime_type='image/png', content=str(index).encode(), parents=[parent]).id
    items, truncated = store.scene_material_image_records(scene.id, 'user:a')
    assert truncated
    assert len(items) == 9
    assert parent not in {asset.id for asset, _, _ in items}


def test_picker_private_routes_use_authenticated_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, headers, _ = host_client(tmp_path / 'app', token='valid-user')
    with client:
        store = client.app.state.store
        source, preview, dependency = _revision_assets(store, tmp_path)
        scene, _ = SceneCatalog(store).create('user:7', name='Host', revision=_revision_input(source, preview, dependency))
        def no_bytes(*args: Any, **kwargs: Any) -> None:
            raise AssertionError('No bytes in picker response')
        monkeypatch.setattr(store, 'asset_path', no_bytes)
        with client.websocket_connect('/ws', headers=headers) as socket:
            response = call(socket, 'scenes.material.images', {'scene_id': scene.id})
            assert response['ok'], response
            assert response['result']['items'][0]['asset_id'] == dependency.id
            assert response['result']['items'][0]['scene_image_kind'] == 'used'
            assert response['result']['truncated'] is False
            for extra in [{'owner': 'user:7'}, {'path': '/tmp/private'}]:
                assert not call(socket, 'scenes.material.images', {'scene_id': scene.id, **extra})['ok']
        assert 'storage_name' not in json.dumps(response)
        assert client.get(f'/workspace-api/scenes/{scene.id}/material-images').status_code == 422
