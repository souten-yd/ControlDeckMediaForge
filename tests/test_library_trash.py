from pathlib import Path
import json
import pytest

from mediaforge.library_trash import LibraryTrash
from mediaforge.scenes import SceneCatalog, SceneError
from mediaforge.store import Store
from mediaforge.domain import JobRequest, JobStatus
from test_scenes import _revision_assets, _revision_input, _register


@pytest.fixture
def fixture(tmp_path):
    store = Store(tmp_path / 'data')
    store.initialize()
    catalog = SceneCatalog(store)
    first = _revision_assets(store, tmp_path)
    document, rev1 = catalog.create('user:owner', name='Robot', revision=_revision_input(*first))
    second = _revision_assets(store, tmp_path)
    document, rev2 = catalog.commit('user:owner', document.id, rev1.id, _revision_input(*second))
    with store._connect() as db:
        for revision in (rev1, rev2):
            raw = revision.model_dump(mode='json')
            raw['validation'][0]['facts']['external_images'] = 0
            db.execute('UPDATE scene_revisions SET value_json=? WHERE id=?', (json.dumps(raw), revision.id))
    return store, LibraryTrash(store), document, rev1, rev2, first, second


def apply(trash, ids, action='trash', owner='user:owner'):
    params = {'asset_ids': ids, 'action': action}
    plan = trash.preview(owner, params)
    result = trash.apply(owner, {**params, 'confirmation_fingerprint': plan['confirmation_fingerprint']})
    return plan, result


def test_remove_image_revision_or_both_without_expanding_other_versions(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    before = {a.id: store.asset_path(a.id).read_bytes() for a in first + second}
    plan, _ = apply(trash, [first[2].id])
    assert plan['asset_ids'] == [first[2].id]
    assert store.get_scene(doc.id, 'user:owner').current_revision_id == rev2.id
    plan, _ = apply(trash, [rev1.preview_asset_id])
    assert set(plan['asset_ids']) == {rev1.source_asset_id, rev1.preview_asset_id}
    assert plan['scenes'] == [{'name': 'Robot', 'sequence': 1}]
    assert [r.id for r in store.list_scene_revisions(doc.id, 'user:owner')] == [rev2.id]
    assert store.asset_scene_links(rev1.preview_asset_id, 'user:owner') == []
    assert store.scene_membership([rev2.preview_asset_id])[rev2.preview_asset_id]['scene_revision_count'] == 1
    assert {a.id for a in store.list_assets()} == {a.id for a in second}
    assert {a.id for a, _ in store.list_asset_records(100, trash=True)} == {a.id for a in first}
    assert all(store.asset_path(aid).read_bytes() == raw for aid, raw in before.items())
    apply(trash, [rev1.source_asset_id, first[2].id], 'restore')
    assert store.trashed_asset_ids() == set()


def test_current_revision_falls_back_and_all_removed_scene_is_restorable(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    apply(trash, [rev2.preview_asset_id])
    assert store.get_scene(doc.id, 'user:owner').current_revision_id == rev1.id
    apply(trash, [rev1.source_asset_id])
    assert store.list_scenes('user:owner') == []
    with pytest.raises(SceneError):
        store.get_scene(doc.id, 'user:owner')
    apply(trash, [rev1.preview_asset_id], 'restore')
    assert store.get_scene(doc.id, 'user:owner').current_revision_id == rev1.id
    assert store.get_asset(first[2].id) and store.get_asset(second[2].id)


def test_purge_only_selected_bytes_and_keep_lineage_tombstone(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    source = first[2]
    # Deliberately retain a descendant's lineage to the deleted image.
    child = _register(store, store.data_dir, mime_type='image/png', content=b'child', parents=[source.id])
    path = store.asset_path(source.id)
    sidecar = store.asset_dir / f'{source.id}.provenance.json'
    thumbnail = store.thumbnail_dir / f'{source.id}-160.webp'
    thumbnail.write_bytes(b'cached')
    apply(trash, [source.id])
    apply(trash, [source.id], 'purge')
    assert not path.exists() and not sidecar.exists() and not thumbnail.exists()
    with pytest.raises(KeyError):
        store.get_asset(source.id)
    with pytest.raises(KeyError):
        store.asset_path(source.id)
    assert store.asset_path(child.id).read_bytes() == b'child'
    relations = store.asset_relations(child.id)
    assert relations['parents'][0]['purged'] is True
    assert relations['parents'][0]['sha256'] == source.sha256
    assert store.list_asset_records(100, trash=True) == []
    assert store.get_provenance(child.id).parent_asset_ids == [source.id]
    assert len(store.list_scene_revisions(doc.id, 'user:owner')) == 2
    with pytest.raises(SceneError, match='cannot be restored'):
        apply(trash, [source.id], 'restore')


def test_purge_revision_keeps_other_revision_and_source_images(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    paths = [store.asset_path(a.id) for a in first[:2]]
    apply(trash, [rev1.preview_asset_id])
    apply(trash, [rev1.preview_asset_id], 'purge')
    assert all(not p.exists() for p in paths)
    assert store.get_scene(doc.id, 'user:owner').current_revision_id == rev2.id
    assert store.get_asset(first[2].id) and store.get_asset(second[2].id)
    assert store.scene_runtime_reference_count(rev1.runtime_id) == 1
    apply(trash, [rev2.preview_asset_id])
    apply(trash, [rev2.preview_asset_id], 'purge')
    assert store.scene_runtime_reference_count(rev1.runtime_id) == 0


def test_stale_confirmation_and_foreign_owner_never_mutate(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    args = {'asset_ids': [rev1.preview_asset_id], 'action': 'trash'}
    preview = trash.preview('user:owner', args)
    with pytest.raises(SceneError) as foreign:
        trash.preview('user:other', args)
    assert foreign.value.code == 'library_scene_owner_required'
    apply(trash, [rev2.preview_asset_id])
    with pytest.raises(SceneError) as changed:
        trash.apply('user:owner', {**args, 'confirmation_fingerprint': preview['confirmation_fingerprint']})
    assert changed.value.code == 'library_selection_changed'
    assert store.get_asset(rev1.source_asset_id)
    assert rev1.source_asset_id not in store.trashed_asset_ids()


def test_running_job_blocks_removal_then_completed_job_does_not(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    job = store.create_job(JobRequest(operation='image.edit', intent='edit', inputs=[{'asset_id': first[2].id}]))
    with pytest.raises(SceneError) as busy:
        apply(trash, [first[2].id])
    assert busy.value.code == 'library_production_busy'
    store.update_job(job.id, status=JobStatus.CANCELED)
    apply(trash, [first[2].id])


def test_partial_cleanup_is_durable_and_retryable(fixture, monkeypatch):
    store, trash, doc, rev1, rev2, first, second = fixture
    target = first[2]
    path = store.asset_path(target.id)
    apply(trash, [target.id])
    original = Path.unlink
    def fail(self, *args, **kwargs):
        if self == path:
            raise PermissionError('fixture')
        return original(self, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', fail)
        with pytest.raises(SceneError) as pending:
            apply(trash, [target.id], 'purge')
        assert pending.value.code == 'library_purge_cleanup_pending'
        assert {a.id for a, _ in store.list_asset_records(100, trash=True)} == {target.id}
        with pytest.raises(SceneError):
            apply(trash, [target.id], 'restore')
    restarted = Store(store.data_dir)
    restarted.initialize()
    assert LibraryTrash(restarted).cleanup() == set()
    assert not path.exists() and restarted.list_asset_records(100, trash=True) == []


def test_purge_requires_trash_and_valid_identity(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    with pytest.raises(SceneError) as error:
        apply(trash, [first[2].id], 'purge')
    assert error.value.code == 'library_trash_required'
    for invalid in ([], ['../x'], ['asset_../../x'], [None], ['asset_a'] * 101):
        with pytest.raises(SceneError):
            trash.preview('user:owner', {'asset_ids': invalid, 'action': 'trash'})
    assert store.trashed_asset_ids() == set()


def test_embedded_texture_guard_and_atomic_multi_selection(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    with store._connect() as db:
        raw = json.loads(db.execute('SELECT value_json FROM scene_revisions WHERE id=?', (rev1.id,)).fetchone()[0])
        raw['validation'][0]['facts'].pop('external_images')
        db.execute('UPDATE scene_revisions SET value_json=? WHERE id=?', (json.dumps(raw), rev1.id))
    apply(trash, [first[2].id, second[2].id])
    with pytest.raises(SceneError) as error:
        apply(trash, [first[2].id, second[2].id], 'purge')
    assert error.value.code == 'library_texture_not_embedded'
    assert store.get_asset(first[2].id) and store.get_asset(second[2].id)
    # Deleting that revision together with its texture needs no retained-texture promise.
    apply(trash, [rev1.preview_asset_id])
    apply(trash, [rev1.preview_asset_id, first[2].id], 'purge')
    assert store.asset_is_purged(first[2].id)


def test_cleanup_refuses_symlink_escape(fixture, tmp_path):
    store, trash, doc, rev1, rev2, first, second = fixture
    target = first[2]
    original_path = store.asset_path(target.id)
    original_path.unlink()
    outside = tmp_path / 'outside'
    outside.write_bytes(b'keep')
    original_path.symlink_to(outside)
    apply(trash, [target.id])
    with pytest.raises(SceneError) as error:
        apply(trash, [target.id], 'purge')
    assert error.value.code == 'library_purge_cleanup_pending'
    assert outside.read_bytes() == b'keep'


def test_backup_after_purge_snapshots_only_retained_data(fixture, tmp_path):
    from mediaforge.scene_backup import SceneBackupCodec, SceneBackupManifest
    import zipfile
    store, trash, doc, rev1, rev2, first, second = fixture
    before = store.list_scene_revisions(doc.id, 'user:owner')[-1].model_dump()
    apply(trash, [rev1.preview_asset_id, second[2].id])
    apply(trash, [rev1.preview_asset_id, second[2].id], 'purge')
    codec = SceneBackupCodec(store)
    codec.initialize()
    target = codec.root / 'backup.zip'
    codec.export('user:owner', doc.id, target)
    with zipfile.ZipFile(target) as archive:
        manifest = SceneBackupManifest.model_validate_json(archive.read('manifest.json'))
        assert len(manifest.revisions) == 1
        assert manifest.revisions[0].sequence == 1
        assert manifest.revisions[0].dependencies == []
    assert store.list_scene_revisions(doc.id, 'user:owner')[-1].model_dump() == before


def test_private_http_and_websocket_share_trash_and_purge(tmp_path):
    from test_host_execution import host_client
    from test_workspace_transport import call, import_asset
    client, headers, _ = host_client(tmp_path, token='valid-user')
    with client:
        asset = import_asset(client)
        asset_id = asset['id']
        params = {'asset_ids': [asset_id], 'action': 'trash'}
        with client.websocket_connect('/ws', headers=headers) as socket:
            plan = call(socket, 'library.trash.preview', params)
            assert plan['ok'], plan
            applied = call(socket, 'library.trash.apply', {**params, 'confirmation_fingerprint': plan['result']['confirmation_fingerprint']})
            assert applied['ok'], applied
            normal = call(socket, 'library.list', {'thumbnails': False})
            removed = call(socket, 'library.list', {'trash': True, 'thumbnails': False})
            assert normal['result']['items'] == []
            assert removed['result']['items'][0]['asset_id'] == asset_id
        params['action'] = 'purge'
        plan = client.post('/workspace-api/library/trash/preview', json=params)
        assert plan.status_code == 200
        result = client.post('/workspace-api/library/trash/apply', json={**params, 'confirmation_fingerprint': plan.json()['confirmation_fingerprint']})
        assert result.status_code == 200
        assert client.get(f'/api/v1/assets/{asset_id}').status_code == 404
        assert client.post('/workspace-api/library', json={'trash': True}).json()['items'] == []
        assert not any('/library/trash/' in path for path in client.get('/openapi.json').json()['paths'])


def test_empty_trash_binds_full_scope_and_keeps_unselected_library(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    apply(trash, [first[2].id])
    args = {'all_trashed': True, 'action': 'purge'}
    plan = trash.preview('user:owner', args)
    apply(trash, [second[2].id])
    with pytest.raises(SceneError) as changed:
        trash.apply('user:owner', {**args, 'confirmation_fingerprint': plan['confirmation_fingerprint']})
    assert changed.value.code == 'library_selection_changed'
    plan = trash.preview('user:owner', args)
    assert set(plan['asset_ids']) == {first[2].id, second[2].id}
    trash.apply('user:owner', {**args, 'confirmation_fingerprint': plan['confirmation_fingerprint']})
    assert store.list_asset_records(100, trash=True) == []
    assert len(store.list_scene_revisions(doc.id, 'user:owner')) == 2


def test_empty_trash_does_not_take_another_owners_revision(fixture):
    store, trash, doc, rev1, rev2, first, second = fixture
    apply(trash, [rev1.preview_asset_id])
    with pytest.raises(SceneError) as empty:
        trash.preview('user:other', {'all_trashed': True, 'action': 'purge'})
    assert empty.value.code == 'library_trash_empty'
    assert store.get_asset(rev1.preview_asset_id)
