from __future__ import annotations

import asyncio
import hashlib
import io
from pathlib import Path

from PIL import Image
import pytest
from pydantic import ValidationError

from mediaforge.asset_import import import_asset_bytes
from mediaforge.domain import JobRequest
from mediaforge.scene_generation import GenerationFacts, SceneFromImageRequest
from mediaforge.scenes import SceneError
from test_glb_import import glb_bytes
from test_scene_workspace import fake_scene_workspace


def setup(tmp_path: Path):
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    workspace.generation_import_worker = Path(__file__).parents[1] / 'worker_packs/blender/import_generated_glb.py'
    executable = resolver.runtime.executable
    text = executable.read_text()
    text = text.replace('time.sleep(0)\n', "if pathlib.Path('generated.glb').exists():\n pathlib.Path('generated.blend').write_bytes(b'BLENDER-fake-generated-scene')\n sys.exit(0)\n")
    executable.write_text(text)
    image = io.BytesIO()
    Image.new('RGB', (16, 16), (60, 120, 180)).save(image, format='PNG')
    asset = import_asset_bytes(store, image.getvalue(), purpose='source', media_type='image/png')
    request = SceneFromImageRequest(name='Generated test scene', input_asset_id=asset.id)
    source = tmp_path / 'model.glb'
    source.write_bytes(glb_bytes())
    facts = GenerationFacts(
        model_id='test/model', model_revision='a'*40, weights_sha256='b'*64,
        license='test-only', runtime_adapter='native.trellis-cpp', runtime_version='test',
        seed=request.seed, resolution=request.resolution, elapsed_sec=2.5,
        output_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    job = store.create_job(JobRequest(operation='media.inspect', intent='Test generated scene'))
    return store, workspace, resolver, request, source, facts, job


def run_import(data):
    _, workspace, resolver, request, source, facts, job = data
    return workspace.import_generated_glb(
        'user:test', job.id, request, source, source.parent, facts,
        runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version,
    )


def test_generated_scene_records_original_input_and_generation_identity(tmp_path: Path) -> None:
    data = setup(tmp_path)
    store, workspace, resolver, request, source, facts, job = data
    before = source.read_bytes()
    result = asyncio.run(run_import(data))
    scene, revisions = workspace.catalog.get('user:test', result['scene']['id'])
    assert scene.collection == 'experiment' and scene.tags == ['g9']
    assert revisions[0].dependencies[0].asset_id == request.input_asset_id
    source_id, preview_id = result['asset_ids']
    provenance = store.get_provenance(source_id)
    assert provenance.operation == 'scene.from_image'
    assert provenance.parent_asset_ids == [request.input_asset_id]
    assert provenance.model_id == facts.model_id and provenance.model_version == facts.model_revision
    assert provenance.weights_hash == facts.weights_sha256 and provenance.seed == 42
    assert provenance.parameters['generation']['output_sha256'] == facts.output_sha256
    assert store.get_provenance(preview_id).parent_asset_ids == [source_id]
    assert store.get_provenance(preview_id).model_id == facts.model_id
    assert {c.validator for c in revisions[0].validation} == {'blender.scene', 'glb.structure'}
    assert len(store.list_assets()) == 3 and source.read_bytes() == before
    assert resolver.references == 0
    assert list(workspace.recipe_root.iterdir()) == list(workspace.validation_root.iterdir()) == []
    with pytest.raises(SceneError):
        workspace.catalog.get('user:other', scene.id)


@pytest.mark.parametrize('failure', ['bad_glb', 'wrong_hash', 'outside_root', 'changed_input', 'publish'])
def test_failed_generation_import_leaves_no_assets_or_staging(tmp_path: Path, monkeypatch, failure: str) -> None:
    data = setup(tmp_path)
    store, workspace, resolver, request, source, facts, job = data
    if failure == 'bad_glb':
        source.write_bytes(b'not GLB')
    elif failure == 'wrong_hash':
        data = (*data[:5], facts.model_copy(update={'output_sha256': '0'*64}), job)
    elif failure == 'outside_root':
        original = source.read_bytes()
        source.unlink()
        outside = tmp_path.parent / f'{tmp_path.name}-outside.glb'
        outside.write_bytes(original)
        source.symlink_to(outside)
    elif failure == 'changed_input':
        store.asset_path(request.input_asset_id).write_bytes(b'changed')
    else:
        def fail(*args, **kwargs):
            raise SceneError('test_publish_failed', 'Injected scene transaction failure')
        monkeypatch.setattr(workspace.catalog, 'create', fail)
    with pytest.raises(SceneError):
        asyncio.run(run_import(data))
    assert len(store.list_assets()) == 1
    assert resolver.references == 0
    assert list(workspace.recipe_root.iterdir()) == list(workspace.validation_root.iterdir()) == []


def test_generated_import_cancel_reaps_owned_child_and_staging(tmp_path: Path) -> None:
    data = setup(tmp_path)
    store, workspace, resolver, *_ = data
    workspace.process_timeout_sec = 10
    executable = resolver.runtime.executable
    executable.write_text(executable.read_text().replace("if pathlib.Path('generated.glb').exists():", "if pathlib.Path('generated.glb').exists():\n time.sleep(30)"))
    async def cancel():
        task = asyncio.create_task(run_import(data))
        await asyncio.sleep(.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(cancel())
    assert len(store.list_assets()) == 1 and resolver.references == 0
    assert list(workspace.recipe_root.iterdir()) == []


def test_from_image_rejects_remote_or_path_input() -> None:
    base = {'name':'Example', 'input_asset_id':'asset_'+'a'*32}
    for extra in ({'local_only':False}, {'image_path':'/tmp/input.png'}, {'image_url':'https://example.com/image.png'}, {'seed':True}):
        with pytest.raises(ValidationError):
            SceneFromImageRequest.model_validate({**base, **extra})
