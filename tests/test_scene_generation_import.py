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
from mediaforge.store import AssetInUse
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


def test_library_glb_becomes_an_editable_scene(tmp_path):
    """シーンを持たないライブラリの GLB を、そのまま Blender で開けるようにする。"""
    store, workspace, resolver, *_ = setup(tmp_path / 'workspace')
    resolver.resolve_active = lambda: resolver.runtime
    asset = import_asset_bytes(store, glb_bytes(), purpose='source', media_type='model/gltf-binary')
    result = asyncio.run(workspace.import_library_glb(
        'user:7', asset.id, name='Library model'))
    assert result['scene']['name'] == 'Library model'
    assert result['revision']['sequence'] == 1
    # 元の GLB は依存として記録し、来歴の親に置く。どこから来たか辿れること。
    assert [d['role'] for d in result['revision']['dependencies']] == ['source_glb']
    assert result['revision']['dependencies'][0]['asset_id'] == asset.id
    blend = store.get_provenance(result['revision']['source_asset_id'])
    assert blend.operation == 'scene.from_glb'
    assert blend.parent_asset_ids == [asset.id]
    assert blend.parameters['source_asset_id'] == asset.id
    # 元の GLB は使われているので消せない。
    with pytest.raises(AssetInUse):
        store.delete_asset(asset.id)


def test_library_listing_hides_glbs_a_scene_already_owns(tmp_path):
    store, workspace, resolver, *_ = setup(tmp_path / 'workspace')
    resolver.resolve_active = lambda: resolver.runtime
    asset = import_asset_bytes(store, glb_bytes(), purpose='source', media_type='model/gltf-binary')
    assert [item.id for item in store.list_editable_glb_assets()] == [asset.id]
    result = asyncio.run(workspace.import_library_glb('user:7', asset.id, name='Library model'))
    # 版のプレビューになった GLB は、もう「シーンが無いもの」ではない。
    listed = {item.id for item in store.list_editable_glb_assets()}
    assert result['revision']['preview_asset_id'] not in listed
    assert asset.id in listed  # 元の GLB 自体は依存であってプレビューではない


def test_a_glb_that_already_has_a_scene_is_refused(tmp_path):
    store, workspace, resolver, *_ = setup(tmp_path / 'workspace')
    resolver.resolve_active = lambda: resolver.runtime
    asset = import_asset_bytes(store, glb_bytes(), purpose='source', media_type='model/gltf-binary')
    result = asyncio.run(workspace.import_library_glb('user:7', asset.id, name='Library model'))
    preview = result['revision']['preview_asset_id']
    with pytest.raises(SceneError, match='already belongs to a scene revision'):
        asyncio.run(workspace.import_library_glb('user:7', preview, name='Again'))


def test_non_glb_and_bad_names_are_refused(tmp_path):
    store, workspace, resolver, *_ = setup(tmp_path / 'workspace')
    resolver.resolve_active = lambda: resolver.runtime
    image = io.BytesIO()
    Image.new('RGB', (16, 16), (10, 20, 30)).save(image, format='PNG')
    png = import_asset_bytes(store, image.getvalue(), purpose='source', media_type='image/png')
    with pytest.raises(SceneError, match='requires a GLB Asset'):
        asyncio.run(workspace.import_library_glb('user:7', png.id, name='Not a model'))
    glb = import_asset_bytes(store, glb_bytes(), purpose='source', media_type='model/gltf-binary')
    with pytest.raises(SceneError, match='1 to 120 characters'):
        asyncio.run(workspace.import_library_glb('user:7', glb.id, name='   '))
