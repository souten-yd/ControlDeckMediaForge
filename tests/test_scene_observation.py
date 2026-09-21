from __future__ import annotations

import asyncio
import base64
from contextlib import ExitStack
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import jsonschema
from PIL import Image, PngImagePlugin
from pydantic import ValidationError
import pytest

from mediaforge.domain import JobRequest
from mediaforge.scene_observation import ObservationSpec, SceneObserveRequest
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.scenes import SceneError
from mediaforge.store import Store
from test_scene_recipe_jobs import Host, IDENTITY, Workspace, terminal
from test_scene_workspace import FakeResolver, fake_scene_workspace, upload_scene

ROOT = Path(__file__).parents[1]


def request(scene_id: str = 'scene_' + '1'*32, revision_id: str = 'revision_' + '2'*32, **changes: Any) -> SceneObserveRequest:
    return SceneObserveRequest(scene_id=scene_id, revision_id=revision_id,
                               observation=ObservationSpec(center=(0, 0, 0), span_m=2, resolution=256, **changes))


def test_contract_and_manifest() -> None:
    schema = json.loads((ROOT / 'schemas/scene-observe-request.json').read_text())
    assert schema == SceneObserveRequest.model_json_schema()
    jsonschema.validate(request().model_dump(mode='json'), schema)
    tools = json.loads((ROOT / 'addon.json').read_text())['contributions']['agent_tools']
    assert next(t for t in tools if t['id'] == 'media.scene.observe')['schema_path'] == '/schemas/scene-observe-request.json'


@pytest.mark.parametrize('change', [
    {'center': [0, 0]}, {'center': [True, 0, 0]}, {'center': [float('nan'), 0, 0]},
    {'center': [10001, 0, 0]}, {'span_m': 0}, {'span_m': float('inf')}, {'span_m': True},
    {'views': []}, {'views': ['front', 'front']}, {'views': ['../../file']},
    {'resolution': 8192}, {'mode': 'python'}, {'path': '/tmp/input'}, {'frame': 100000},
])
def test_core_and_independent_worker_reject_unsafe_spec(monkeypatch: pytest.MonkeyPatch, change: dict) -> None:
    monkeypatch.setitem(sys.modules, 'bpy', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'mathutils', SimpleNamespace(Vector=object))
    spec = importlib.util.spec_from_file_location('observation_worker_test', ROOT / 'worker_packs/blender/scene_observation.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value = {**request().observation.model_dump(mode='json'), **change}
    with pytest.raises(ValidationError):
        ObservationSpec.model_validate(value)
    with pytest.raises((RuntimeError, ValueError, TypeError)):
        module.validate_spec(value)


def observation_workspace(tmp_path: Path, *, mode: str = 'success') -> tuple[Store, SceneWorkspace, FakeResolver, SceneObserveRequest]:
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b'BLENDER-fixture')
    workspace.observation_worker = workspace.worker
    workspace.process_timeout_sec = 2
    buffer = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('File', '/private/runtime/source.blend')
    metadata.add_text('Date', 'untrusted timestamp')
    Image.new('RGB', (256, 256), 'gray').save(buffer, format='PNG', pnginfo=metadata)
    resolver.runtime.executable.write_text(
        '#!/usr/bin/python3\nimport json,pathlib,base64,time,os\n'
        f'mode={mode!r}\n'
        "spec=json.loads(pathlib.Path('observation.json').read_text())\n"
        "if mode=='slow': time.sleep(30)\n"
        "if mode=='exit': raise SystemExit(1)\n"
        "frames=spec.get('frames') or [0]\n"
        "images=[]\n"
        "for view in spec['views']:\n"
        " for frame in frames:\n"
        "  name='%s-f%d.png'%(view,frame)\n"
        f"  pathlib.Path(name).write_bytes(base64.b64decode({base64.b64encode(buffer.getvalue()).decode()!r}))\n"
        "  images.append({'view':view,'frame':frame,'filename':name})\n"
        "if mode=='bad_image': pathlib.Path(images[-1]['filename']).write_bytes(b'bad')\n"
        "if mode=='symlink':\n pathlib.Path('front-f0.png').unlink()\n pathlib.Path('front-f0.png').symlink_to('back-f0.png')\n"
        "if mode=='bad_spec': spec['span_m']=99\n"
        "pathlib.Path('result.json').write_text(json.dumps({'schema_version':'media-forge.scene-observation-result@1',"
        "'observation':spec,'blender_version':'4.5.9','device':'CPU','frames':frames,"
        "'clip_id':spec.get('clip_id'),'samples':16,"
        "'images':images,'object_colors':[],'autoexec_disabled':True}))\n"
    )
    value = request(imported['scene']['id'], imported['revision']['id'])
    return store, workspace, resolver, value


def test_observation_keeps_old_revision_and_asset_lineage(tmp_path: Path) -> None:
    store, workspace, resolver, value = observation_workspace(tmp_path)
    from mediaforge.scenes import SceneRevisionInput
    document, revisions = workspace.catalog.get('user:1', value.scene_id)
    old = revisions[0]
    new_doc, _ = workspace.catalog.commit('user:1', value.scene_id, old.id,
        SceneRevisionInput(**old.model_dump(include=set(SceneRevisionInput.model_fields))))
    assert new_doc.current_revision_id != old.id
    with pytest.raises((KeyError, SceneError)):
        workspace.recipe_runtime_pin('user:other', value)
    bad = value.model_copy(update={'revision_id': 'revision_'+'f'*32})
    with pytest.raises(SceneError, match='unavailable'):
        workspace.recipe_runtime_pin('user:1', bad)
    pin = workspace.recipe_runtime_pin('user:1', value)
    assert pin[2] == old.id
    before_hash = store.get_asset(old.source_asset_id).sha256
    job = store.create_job(JobRequest(operation='media.inspect', intent='observation'))
    result = asyncio.run(workspace.observe_scene('user:1', job.id, value, runtime_id=pin[0], runtime_version=pin[1]))
    assert len(result['images']) == 4 and result['semantic_review'] == 'not_tested'
    assert workspace.catalog.get('user:1', value.scene_id)[0].current_revision_id == new_doc.current_revision_id
    assert store.get_asset(old.source_asset_id).sha256 == before_hash
    for image in result['images']:
        asset = store.get_asset(image['asset_id'])
        prov = store.get_provenance(asset.id)
        with Image.open(store.asset_path(asset.id)) as image:
            assert image.info == {}  # no private renderer path/date in public PNG
        assert asset.parent_asset_ids == [old.source_asset_id]
        assert prov.reference_asset_hashes == {old.source_asset_id: before_hash}
        assert prov.parameters['revision_id'] == old.id
        assert prov.parameters['observation'] == value.observation.model_dump(mode='json')
    assert resolver.references == 0 and list(workspace.observation_root.iterdir()) == []


@pytest.mark.parametrize('mode', ['exit', 'bad_image', 'bad_spec', 'symlink', 'slow', 'registration'])
def test_worker_failure_rolls_back_and_releases_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    store, workspace, resolver, value = observation_workspace(tmp_path, mode=mode)
    if mode == 'slow':
        workspace.process_timeout_sec = .05
    if mode == 'registration':
        original = store.register_asset
        count = 0
        def failing(*args: Any, **kwargs: Any) -> Any:
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError('registration failed')
            return original(*args, **kwargs)
        monkeypatch.setattr(store, 'register_asset', failing)
    job = store.create_job(JobRequest(operation='media.inspect', intent='observation failure'))
    with pytest.raises((SceneError, RuntimeError)):
        asyncio.run(workspace.observe_scene('user:1', job.id, value,
                    runtime_id=resolver.runtime.runtime_id, runtime_version='4.5.9'))
    assert resolver.references == 0
    assert list(workspace.observation_root.iterdir()) == []
    with store._connect() as connection:
        assert connection.execute('select count(*) from assets where job_id=?', (job.id,)).fetchone()[0] == 0


def test_cancel_observation_terminates_worker(tmp_path: Path) -> None:
    store, workspace, resolver, value = observation_workspace(tmp_path, mode='slow')
    job = store.create_job(JobRequest(operation='media.inspect', intent='cancel observation'))
    async def scenario() -> None:
        task = asyncio.create_task(workspace.observe_scene('user:1', job.id, value,
            runtime_id=resolver.runtime.runtime_id, runtime_version='4.5.9'))
        await asyncio.sleep(.04)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert resolver.references == 0 and list(workspace.observation_root.iterdir()) == []


def test_observation_uses_durable_existing_jobs_and_owner(tmp_path: Path) -> None:
    class Observer(Workspace):
        def recipe_runtime_pin(self, owner: str, value: SceneObserveRequest) -> tuple[str, str, str]:
            return 'blender-test', '4.5.9', value.revision_id
        async def observe_scene(self, owner: str, job_id: str, value: SceneObserveRequest, **kwargs: Any) -> dict[str, Any]:
            assert owner == 'user:7'
            return {'scene': {'id': value.scene_id}, 'revision': {'id': value.revision_id},
                    'asset_ids': ['asset_'+'3'*32], 'images': [], 'semantic_review': 'not_tested'}
        async def apply_recipe(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError('observation is not an edit')
    async def scenario() -> None:
        store = Store(tmp_path);store.initialize()
        manager = SceneRecipeJobManager(store, Observer(), Host())
        job, record = await manager.submit(request(), IDENTITY)
        assert record.operation == 'scene.observe' and record.base_revision_id == request().revision_id
        await terminal(store, job.id)
        await manager.wait_cleanup(job.id)
        assert manager.projection(job.id, 'user:7')['status'] == 'succeeded'
        with pytest.raises(KeyError):
            manager.projection(job.id, 'user:8')
        reopened = Store(tmp_path);reopened.initialize()
        assert reopened.get_scene_recipe_task(job.id, owner='user:7').operation == 'scene.observe'
        await manager.stop()
    asyncio.run(scenario())


def test_authenticated_observe_route_and_invalid_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import time
    from fastapi.testclient import TestClient
    from conftest import fake_settings
    from mediaforge.app import create_app
    from test_scene_agent_api import Host as APIHost

    host = APIHost()
    app = create_app(fake_settings(tmp_path), host_client=host)
    value = request()
    app.state.scene_workspace.acquire_recipe_runtime = lambda owner, payload: (
        ExitStack(), ('blender-test', '4.5.9', payload.revision_id))
    async def observed(owner: str, job_id: str, payload: SceneObserveRequest, **kwargs: Any) -> dict:
        assert owner == 'user:7' and payload == value
        return {'scene': {'id': payload.scene_id}, 'revision': {'id': payload.revision_id},
                'asset_ids': ['asset_'+'3'*32], 'images': [], 'semantic_review': 'not_tested'}
    app.state.scene_workspace.observe_scene = observed
    headers = {'Authorization': 'Bearer request', 'X-Control-Deck-Addon-ID': 'media-forge'}
    with TestClient(app) as client:
        monkeypatch.setattr(app.state.blender_runtimes, 'resolve_g8', lambda: None)
        assert client.get('/api/v1/capabilities').json()['capabilities']['3d.scene_observation']['state'] == 'unavailable'
        submitted = client.post('/addon/v1/agent/scene/observe', json={'input': value.model_dump(mode='json')}, headers=headers)
        assert submitted.status_code == 200 and submitted.json()['detached'] is True
        deadline = time.monotonic()+3
        while True:
            status = client.post('/addon/v1/agent/job/status', headers=headers,
                                 json={'input': {'job_id': submitted.json()['job_id']}}).json()
            if status['status'] == 'succeeded' and status['host_terminal_sent']:
                break
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert status['operation'] == 'scene.observe'
        assert status['result']['revision']['id'] == value.revision_id
        invalid = client.post('/addon/v1/agent/scene/observe', headers=headers,
                              json={'input': {**value.model_dump(mode='json'), 'python': 'exec'}})
        assert invalid.status_code == 422 and host.children == 1


@pytest.mark.parametrize("stage", ["queued", "validate_recipe", "blender_recipe", "publish_observation"])
def test_restart_marks_observation_failed_without_reexecution(tmp_path: Path, stage: str) -> None:
    from mediaforge.domain import JobStatus
    store = Store(tmp_path); store.initialize()
    job = store.create_job(JobRequest(operation='media.inspect', intent='interrupted observation'), host_managed=True)
    store.create_scene_recipe_task(job.id, owner='user:7', host_job_id='child', operation='scene.observe',
        runtime_id='blender-test', runtime_version='4.5.9', base_revision_id=request().revision_id,
        input_sha256='1'*64, idempotency_key='2'*64, request=request().model_dump(mode='json'))
    store.update_job(job.id, status=JobStatus.RUNNING)
    store.update_scene_recipe_task(job.id, stage=stage)
    restarted = Store(tmp_path);restarted.initialize()
    assert restarted.get_job(job.id).status == JobStatus.FAILED
    assert restarted.get_scene_recipe_task(job.id).stage == 'service_restarted'


def test_queued_observation_cancel_and_retry_preserve_input(tmp_path: Path) -> None:
    class Waiting(Workspace):
        def __init__(self) -> None:
            self.started = asyncio.Event()
        def recipe_runtime_pin(self, owner: str, value: SceneObserveRequest) -> tuple[str, str, str]:
            return 'blender-test', '4.5.9', value.revision_id
        async def observe_scene(self, *args: Any, **kwargs: Any) -> None:
            self.started.set()
            await asyncio.Event().wait()
    async def scenario() -> None:
        store = Store(tmp_path);store.initialize()
        workspace = Waiting()
        manager = SceneRecipeJobManager(store, workspace, Host())
        await manager._execution_guard.acquire()
        job, _ = await manager.submit(request(), IDENTITY)
        await manager.cancel(job.id, 'user:7')
        await manager.wait_cleanup(job.id)
        assert not workspace.started.is_set()
        assert manager.projection(job.id, 'user:7')['status'] == 'canceled'
        with pytest.raises(SceneError, match='preserve'):
            await manager.submit(request(mode='silhouette'), IDENTITY, retry_of=job.id)
        retry, record = await manager.submit(request(), IDENTITY, retry_of=job.id)
        assert record.base_revision_id == request().revision_id and record.retry_of == job.id
        await manager.cancel(retry.id, 'user:7')
        await manager.wait_cleanup(retry.id)
        manager._execution_guard.release()
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('invalid', ['curve', 'instance', 'particles', 'nodes', 'growth', 'meshes'])
def test_unsupported_or_amplified_geometry_is_rejected_before_render(monkeypatch: pytest.MonkeyPatch, invalid: str) -> None:
    monkeypatch.setitem(sys.modules, 'bpy', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'mathutils', SimpleNamespace(Vector=object))
    spec = importlib.util.spec_from_file_location('observation_geometry_test', ROOT / 'worker_packs/blender/scene_observation.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    mesh = SimpleNamespace(type='MESH', name='body', instance_type='NONE', particle_systems=[], modifiers=[],
                           data=SimpleNamespace(vertices=range(3), polygons=[SimpleNamespace(loop_total=3)]))
    assert module.validate_scene_objects([mesh]) == [mesh]
    objects = [mesh]
    if invalid == 'curve': mesh.type = 'CURVE'
    if invalid == 'instance': mesh.instance_type = 'COLLECTION'
    if invalid == 'particles': mesh.particle_systems = [object()]
    if invalid == 'nodes': mesh.modifiers = [SimpleNamespace(type='NODES')]
    if invalid == 'growth': mesh.modifiers = [SimpleNamespace(type='BEVEL', segments=100000)]
    if invalid == 'meshes': objects = [mesh] * 257
    with pytest.raises(RuntimeError):
        module.validate_scene_objects(objects)
