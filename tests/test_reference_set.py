from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
import threading
import time
from typing import Any
import zipfile
import uuid

import pytest
import jsonschema
from PIL import Image, PngImagePlugin
from pydantic import TypeAdapter, ValidationError

from conftest import wait_terminal
from mediaforge.domain import JobRequest, JobStatus
from mediaforge.reference_set import (
    ReferenceSetSpec, ReferenceManifest, ReferenceSetError, ReferenceSetCanceled,
    build_reference_set, read_reference_set,
)
from mediaforge.scene_recipes import SceneCreateRequest, SceneEditRequest, SceneWorkflowRequest
from mediaforge.scenes import SceneError
from mediaforge.store import AssetInUse
from test_scene_workspace import fake_scene_workspace, register_image

ROOT = Path(__file__).parents[1]


def spec(first: str = 'asset_' + 'a'*32, second: str = 'asset_' + 'b'*32, **changes: Any) -> dict:
    return {'name': 'Creature design', 'canonical_asset_id': first,
            'views': [{'view': 'front', 'asset_id': first}, {'view': 'side', 'asset_id': second}],
            'scale_m': 3, 'origin_notes': 'Local design study, rights remain with source assets',
            'parts': [{'id': 'body', 'description': 'torso'}],
            'landmarks': [{'view': 'front', 'part_id': 'body', 'name': 'center', 'uv': [.5, .5]}], **changes}


def request(value: dict) -> dict:
    parsed = ReferenceSetSpec.model_validate(value)
    return {'operation': 'asset.pack', 'intent': 'Freeze the design references',
            'profile': '3d.reference_set', 'inputs': [{'asset_id': i} for i in parsed.asset_ids()],
            'constraints': value, 'output': {'format': 'zip', 'count': 1}}


def inputs(client) -> tuple[str, str]:
    result = []
    for color in ['red', 'green']:
        data = io.BytesIO()
        meta = PngImagePlugin.PngInfo()
        meta.add_text('File', '/private/design.blend')
        Image.new('RGB', (64, 48), color).save(data, format='PNG', pnginfo=meta)
        response = client.post('/api/v1/assets/import?purpose=source', content=data.getvalue(),
                               headers={'content-type': 'image/png'})
        assert response.status_code == 201
        result.append(response.json()['id'])
    return tuple(result)


def package(client, **changes) -> dict:
    value = request(spec(*inputs(client), **changes))
    response = client.post('/api/v1/jobs', json=value)
    assert response.status_code == 202
    job = wait_terminal(client, response.json()['id'])
    assert job['status'] == 'succeeded', job
    return job


def test_contracts_and_discovery(client) -> None:
    for name, schema in [
        ('reference-set-spec', ReferenceSetSpec.model_json_schema()),
        ('reference-set-manifest', ReferenceManifest.model_json_schema()),
    ]:
        assert json.loads((ROOT / f'schemas/{name}.json').read_text()) == schema
    for name, model in [('scene-create-request', SceneCreateRequest), ('scene-edit-request', SceneEditRequest)]:
        schema = json.loads((ROOT / f'schemas/{name}.json').read_text())
        assert schema['properties']['reference_set_asset_id'] == model.model_json_schema()['properties']['reference_set_asset_id']
        assert '$id' in schema and '$schema' in schema
    capability = client.get('/api/v1/capabilities').json()['capabilities']['asset.reference_set']
    assert capability['state'] == 'available' and capability['visual_consistency'] == 'not_reviewed'


@pytest.mark.parametrize('changes', [
    {'scale_m': True}, {'scale_m': 0}, {'scale_m': float('nan')}, {'forward_axis': '-Z'},
    {'views': [{'view': 'front', 'asset_id': 'asset_'+'a'*32}]*2},
    {'parts': [{'id': 'body', 'parent_id': 'body', 'description': 'cycle'}]},
    {'parts': [{'id': 'body', 'parent_id': 'absent', 'description': 'missing'}]},
    {'landmarks': [{'view': 'back', 'part_id': 'body', 'name': 'eye', 'uv': [.5, .5]}]},
    {'landmarks': [{'view': 'front', 'part_id': 'body', 'name': 'eye', 'uv': [2, .5]}]},
    {'status': 'approved'}, {'path': '/tmp/reference.png'}, {'origin_notes': ''},
])
def test_invalid_specs_fail_closed(changes: dict) -> None:
    with pytest.raises(ValidationError):
        ReferenceSetSpec.model_validate(spec(**changes))


def test_reproducible_package_lineage_and_unreviewed_state(client) -> None:
    value = request(spec(*inputs(client)))
    hashes = []
    for _ in range(2):
        created = client.post('/api/v1/jobs', json=value).json()
        job = wait_terminal(client, created['id'])
        assert job['status'] == 'succeeded', job
        store = client.app.state.store
        asset = store.get_asset(job['asset_ids'][0])
        hashes.append(asset.sha256)
        manifest = read_reference_set(store, asset.id)
        assert manifest.status == 'needs_review' and manifest.projection == 'unverified'
        assert manifest.images[0].license == store.get_provenance(manifest.images[0].asset_id).license
        with zipfile.ZipFile(store.asset_path(asset.id)) as archive:
            assert len(archive.namelist()) == 3
            for item in manifest.images:
                image = Image.open(io.BytesIO(archive.read(item.filename)))
                assert image.size == (64, 48) and not image.info
                assert item.source_sha256 == store.get_asset(item.asset_id).sha256
        for parent in asset.parent_asset_ids:
            with pytest.raises(AssetInUse):
                store.delete_asset(parent)
    assert hashes[0] == hashes[1]


@pytest.mark.parametrize('mode', ['extra_input', 'duplicate_input', 'missing_input', 'corrupt_image', 'missing_image', 'semantic'])
def test_job_failures_publish_nothing(client, mode: str) -> None:
    value = request(spec(*inputs(client)))
    store = client.app.state.store
    if mode == 'extra_input':
        value['inputs'].append({'asset_id': 'asset_'+'c'*32})
    elif mode == 'duplicate_input':
        value['inputs'].append(value['inputs'][0])
    elif mode == 'missing_input':
        value['inputs'].pop()
    elif mode == 'corrupt_image':
        store.asset_path(value['inputs'][0]['asset_id']).write_bytes(b'corrupt')
    elif mode == 'missing_image':
        store.asset_path(value['inputs'][0]['asset_id']).unlink()
    else:
        value['qa'] = {'semantic': True}
    count = len(store.list_assets())
    created = client.post('/api/v1/jobs', json=value).json()
    terminal = wait_terminal(client, created['id'])
    assert terminal['status'] == 'failed' and not terminal['asset_ids']
    assert len(store.list_assets()) == count


def test_reader_rejects_tampered_archive_and_wrong_profile(client) -> None:
    job = package(client)
    store = client.app.state.store
    source_id = store.get_asset(job['asset_ids'][0]).parent_asset_ids[0]
    with pytest.raises(ReferenceSetError):
        read_reference_set(store, source_id)
    store.asset_path(job['asset_ids'][0]).write_bytes(b'changed')
    with pytest.raises(ReferenceSetError):
        read_reference_set(store, job['asset_ids'][0])


@pytest.mark.parametrize('mode', ['path', 'duplicate', 'compressed', 'approved', 'pixel_hash', 'size', 'lineage'])
def test_reader_rejects_invalid_package_even_with_matching_outer_digest(client, tmp_path: Path, mode: str) -> None:
    job = package(client)
    store = client.app.state.store
    original = store.get_asset(job['asset_ids'][0])
    provenance = store.get_provenance(original.id)
    with zipfile.ZipFile(store.asset_path(original.id)) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    manifest = json.loads(entries['manifest.json'])
    if mode == 'path':
        entries['../escape.png'] = b'invalid'
    elif mode == 'approved':
        manifest['status'] = 'approved'
    elif mode == 'pixel_hash':
        entries[manifest['images'][0]['filename']] = b'not an image'
    elif mode == 'size':
        manifest['images'][0]['width'] = 8192
    entries['manifest.json'] = json.dumps(manifest).encode()
    output = tmp_path / 'malformed.zip'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED if mode == 'compressed' else zipfile.ZIP_STORED) as target:
        for name, data in entries.items():
            target.writestr(name, data)
        if mode == 'duplicate':
            with pytest.warns(UserWarning):
                target.writestr('manifest.json', entries['manifest.json'])
    asset = original.model_copy(update={'id': 'asset_'+uuid.uuid4().hex,
        'provenance_id': 'prov_'+uuid.uuid4().hex, 'size_bytes': output.stat().st_size,
        'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    provenance = provenance.model_copy(update={'id': asset.provenance_id, 'asset_id': asset.id,
        'output_sha256': asset.sha256})
    if mode == 'lineage':
        provenance.reference_asset_hashes = {}
    store.register_asset(asset, provenance, output)
    with pytest.raises(ReferenceSetError):
        read_reference_set(store, asset.id)


def test_repeated_task_cancel_waits_for_thread_exit(client, monkeypatch) -> None:
    import mediaforge.jobs as jobs_module
    entered, release, exited = threading.Event(), threading.Event(), threading.Event()
    def writer(*args, canceled, **kwargs):
        entered.set()
        try:
            assert release.wait(3)
            assert canceled()
            raise ReferenceSetCanceled('canceled')
        finally:
            exited.set()
    monkeypatch.setattr(jobs_module, 'build_reference_set', writer)
    job = client.app.state.store.create_job(JobRequest.model_validate(request(spec(*inputs(client)))))
    async def scenario():
        task = asyncio.create_task(client.app.state.jobs._execute_reference_pack(job, None))
        while not entered.is_set():
            await asyncio.sleep(.005)
        task.cancel()
        await asyncio.sleep(.01)
        task.cancel()
        await asyncio.sleep(.01)
        assert not task.done() and not exited.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert exited.is_set()
    client.portal.call(scenario)
    assert len(client.app.state.store.list_assets()) == 2


def test_cancel_during_cpu_pack_drains_writer_before_cleanup(client, monkeypatch) -> None:
    import mediaforge.jobs as jobs_module
    original = jobs_module.build_reference_set
    entered = threading.Event()
    exited = threading.Event()

    def delayed(*args, canceled, **kwargs):
        entered.set()
        try:
            deadline = time.monotonic() + 3
            while not canceled() and time.monotonic() < deadline:
                time.sleep(.005)
            return original(*args, canceled=canceled, **kwargs)
        finally:
            exited.set()

    monkeypatch.setattr(jobs_module, 'build_reference_set', delayed)
    value = request(spec(*inputs(client)))
    created = client.post('/api/v1/jobs', json=value).json()
    assert entered.wait(3)
    assert client.delete(f"/api/v1/jobs/{created['id']}").status_code == 200
    assert wait_terminal(client, created['id'])['status'] == 'canceled'
    assert exited.wait(3)
    client.portal.call(client.app.state.jobs.wait_cleanup, created['id'])
    assert not (client.app.state.store.work_dir / created['id']).exists()
    assert len(client.app.state.store.list_assets()) == 2


def test_scene_reference_replacement_keeps_old_revision_and_checks_owner(client, tmp_path: Path) -> None:
    # Real package storage with a fake Blender process isolates scene lineage rules.
    first = package(client)['asset_ids'][0]
    second = package(client, name='Revised design')['asset_ids'][0]
    store = client.app.state.store
    _, workspace, resolver = fake_scene_workspace(tmp_path / 'blender')
    from mediaforge.scenes import SceneCatalog
    workspace.store = store
    workspace.catalog = SceneCatalog(store)

    async def worker(*args, **kwargs):
        path = tmp_path / 'generated.blend'
        path.write_bytes(b'BLENDER-fixture')
        return path, {'stable_object_ids': ['body']}
    workspace._apply_recipe_worker = worker
    recipe = {'operations': [{'type': 'primitive.add', 'primitive': 'cube', 'object_id': 'body', 'name': 'Body', 'dimensions': [1, 1, 1]}]}

    async def scenario():
        job = store.create_job(JobRequest(operation='media.inspect', intent='Scene test'))
        create = SceneCreateRequest(name='Creature', recipe=recipe, reference_set_asset_id=first)
        result = await workspace.apply_recipe('user:1', job.id, create,
            runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version)
        scene_id, old_id = result['scene']['id'], result['revision']['id']
        edit = SceneEditRequest(scene_id=scene_id, base_revision_id=old_id, recipe=recipe, reference_set_asset_id=second)
        with pytest.raises((KeyError, SceneError)):
            await workspace.apply_recipe('user:other', job.id, edit,
                runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version)
        result = await workspace.apply_recipe('user:1', job.id, edit,
            runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version)
        assert result['revision']['dependencies'][0]['asset_id'] == second
        _, revisions = workspace.catalog.get('user:1', scene_id)
        assert next(r for r in revisions if r.id == old_id).dependencies[0].asset_id == first
        keep = edit.model_copy(update={'base_revision_id': result['revision']['id'], 'reference_set_asset_id': None})
        result = await workspace.apply_recipe('user:1', job.id, keep,
            runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version)
        assert result['revision']['dependencies'][0]['asset_id'] == second
        with pytest.raises(SceneError):
            await workspace.apply_recipe('user:1', job.id, edit,
                runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version)
        assert resolver.references == 0
        from mediaforge.scene_backup import SceneBackupCodec
        codec = SceneBackupCodec(store)
        codec.initialize()
        owner, active_scene = 'user:1', scene_id
        for generation in range(2):
            backup = codec.root / f'reference-{generation}.zip'
            codec.export(owner, active_scene, backup)
            owner = f'user:restored{generation}'
            restored = codec.restore(owner, backup)
            active_scene = restored['scene']['id']
            document, revisions = workspace.catalog.get(owner, active_scene)
            head = next(r for r in revisions if r.id == document.current_revision_id)
            reference = next(d for d in head.dependencies if d.role == 'reference_set')
            assert reference.asset_id != second
            assert reference.sha256 == store.get_asset(second).sha256
            assert read_reference_set(store, reference.asset_id) == read_reference_set(store, second)
            change = SceneEditRequest(scene_id=active_scene, base_revision_id=head.id, recipe=recipe)
            result = await workspace.apply_recipe(owner, job.id, change,
                runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version)
            assert result['revision']['dependencies'][0]['asset_id'] == reference.asset_id
    asyncio.run(scenario())


def test_legacy_scene_retry_payload_omits_absent_reference(tmp_path: Path) -> None:
    from test_scene_recipe_jobs import Host, FailOnceWorkspace, IDENTITY, recipe
    from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
    from mediaforge.store import Store
    async def scenario():
        store = Store(tmp_path)
        store.initialize()
        manager = SceneRecipeJobManager(store, FailOnceWorkspace(), Host())
        await manager.start()
        job, _ = await manager.submit(recipe(), IDENTITY)
        await manager.wait_cleanup(job.id)
        assert 'reference_set_asset_id' not in store.get_scene_recipe_task(job.id).request
        assert store.get_job(job.id).status == JobStatus.FAILED
        retry = recipe().model_copy(update={'retry_job_id': job.id})
        next_job, _ = await manager.submit(retry, IDENTITY, retry_of=job.id)
        await manager.wait_cleanup(next_job.id)
        assert store.get_job(next_job.id).status == JobStatus.SUCCEEDED
        await manager.stop()
    asyncio.run(scenario())
