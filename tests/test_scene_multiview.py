from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
from pydantic import ValidationError
import pytest

from mediaforge.asset_import import import_asset_bytes
from mediaforge.domain import JobStatus
from mediaforge.host.jobs import HostExecution
from mediaforge.library_trash import LibraryTrash
from mediaforge.multiview_runtime import MV_MODEL_FILES, MultiviewRuntimeReceipt
from mediaforge.scene_generation import SceneFromImageRequest
from mediaforge.scenes import SceneError
from mediaforge.store import AssetInUse
from test_scene_generation_jobs import GENERATION_IDENTITY, manager_fixture
from test_three_d_runtime import native_runtime


def rgba_asset(store, index: int):
    image = Image.new('RGBA', (64, 64))
    ImageDraw.Draw(image).rectangle((8 + index*4, 8, 46, 54), fill=(220, 30 + index*30, 15, 255))
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return import_asset_bytes(store, stream.getvalue(), purpose='source', media_type='image/png')


def multiview_manager(tmp_path: Path, count: int = 4, mode: str = 'success'):
    manager, host, original, base = manager_fixture(tmp_path, mode)
    assets = [rgba_asset(manager.store, i) for i in range(count)]
    value = SceneFromImageRequest.model_validate({**original.model_dump(),
        'input_asset_id': assets[0].id, 'additional_views': [
            {'direction': direction, 'asset_id': asset.id}
            for direction, asset in zip(('right', 'back', 'left'), assets[1:])]})
    snapshot = base.model_repository/base.model_snapshot
    for name in MV_MODEL_FILES:
        (snapshot/name).write_bytes(b'fake multiview weight')
    def identity(path: Path) -> dict[str, object]:
        return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
    # The real process boundary must receive all unique views and their cameras.
    executable = base.runtime_root/base.executable
    executable.write_text(executable.read_text().replace("assert '--require-gpu' in sys.argv", """
assert '--require-gpu' in sys.argv
import json
assert '--image' not in sys.argv
assert sys.argv[sys.argv.index('--pixal3d-weights')+1] == 'mv'
root = pathlib.Path(sys.argv[sys.argv.index('--views')+1])
metadata = json.loads((root/'transforms.json').read_text())
assert len(metadata['frames']) == int(sys.argv[sys.argv.index('--num-views')+1])
images = [(root/frame['file_path']).read_bytes() for frame in metadata['frames']]
assert len(set(images)) == len(images)
"""))
    receipt = MultiviewRuntimeReceipt(
        runtime_root=base.runtime_root, executable=base.executable, runtime_revision=base.runtime_revision,
        runtime_files={p.name: identity(p) for p in base.runtime_root.iterdir()},
        model_repository=base.model_repository, model_snapshot=base.model_snapshot,
        model_files={name: identity(snapshot/name) for name in MV_MODEL_FILES},
        model_id=base.model_id, model_revision=base.model_revision, license='test only', license_accepted=True,
        device_id='gpu0', native_device_index=1, evaluated_view_counts=[2, 3, 4],
        measured_peak_vram_bytes=1024**3, measured_runtime_sec=1,
        evaluated_output_sha256=base.evaluated_output_sha256, validation='passed')
    manager.generator.multiview_receipt_path.write_text(receipt.model_dump_json())
    return manager, host, value, receipt


@pytest.mark.parametrize('count', [2, 3, 4])
def test_multiview_uses_every_input_and_publishes_all_parents(tmp_path: Path, count: int) -> None:
    async def scenario() -> None:
        manager, host, value, _ = multiview_manager(tmp_path, count)
        job, record = await manager.submit(value, GENERATION_IDENTITY)
        await manager.wait_cleanup(job.id)
        final = manager.store.get_job(job.id)
        assert final.status == JobStatus.SUCCEEDED, final.error
        provenance = manager.store.get_provenance(final.asset_ids[0])
        assert provenance.parent_asset_ids == value.input_asset_ids()
        facts = provenance.parameters['generation']
        assert facts['runtime_adapter'] == 'native.pixal3d-multiview'
        assert facts['execution'] is None
        assert [v['asset_id'] for v in facts['multiview']['views']] == value.input_asset_ids()
        scene_id = manager.projection(job.id, 'user:7')['result']['scene']['id']
        _, revisions = manager.workspace.catalog.get('user:7', scene_id)
        assert [v.asset_id for v in revisions[0].dependencies] == value.input_asset_ids()
        assert host.events.count('release') == 1
        assert list(manager.workspace.recipe_root.iterdir()) == []
        assert record.request['additional_views'] == value.model_dump()['additional_views']
        await manager.stop()
    asyncio.run(scenario())


def test_duplicate_pixels_fail_before_child_job_or_gpu_request(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, host, value, _ = multiview_manager(tmp_path, 2)
        duplicate = rgba_asset(manager.store, 0)
        assert duplicate.id != value.input_asset_id
        value = SceneFromImageRequest.model_validate({**value.model_dump(), 'additional_views': [
            {'direction': 'right', 'asset_id': duplicate.id}]})
        with pytest.raises(SceneError) as exc:
            await manager.submit(value, GENERATION_IDENTITY)
        assert exc.value.code == 'scene_multiview_duplicate_image'
        assert not host.created and not host.events
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('mode', ['waiting', 'worker'])
def test_cancel_protects_all_images_and_releases_before_return(tmp_path: Path, mode: str) -> None:
    async def scenario() -> None:
        manager, host, value, _ = multiview_manager(tmp_path, 3, mode)
        job, _ = await manager.submit(value, GENERATION_IDENTITY)
        await asyncio.wait_for(host.requested.wait(), 3)
        pid = None
        if mode == 'worker':
            for _ in range(200):
                paths = list(manager.workspace.recipe_root.glob('native_*/stage1/pid'))
                if paths:
                    pid = int(paths[0].read_text()); break
                await asyncio.sleep(.01)
            assert pid is not None
        trash = LibraryTrash(manager.store)
        for asset_id in value.input_asset_ids():
            with pytest.raises(AssetInUse):
                manager.store.delete_asset(asset_id)
            with pytest.raises(SceneError) as exc:
                trash.preview('user:7', {'asset_ids': [asset_id], 'action': 'trash'})
            assert exc.value.code == 'library_production_busy'
        await manager.cancel(job.id, 'user:7')
        await manager.wait_cleanup(job.id)
        assert manager.store.get_job(job.id).status == JobStatus.CANCELED
        assert host.events[-1] == ('cancel_request' if mode == 'waiting' else 'release')
        if pid is not None: assert not Path(f'/proc/{pid}').exists()
        assert list(manager.workspace.recipe_root.iterdir()) == []
        for asset_id in value.input_asset_ids(): manager.store.delete_asset(asset_id)
        await manager.stop()
    asyncio.run(scenario())


def test_unadopted_multiview_never_falls_back_to_single_image(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, host, value, _ = multiview_manager(tmp_path, 2)
        manager.generator.multiview_receipt_path.unlink()
        separate = tmp_path/'unchanged-single-view'
        separate.mkdir()
        single, _ = native_runtime(separate)
        manager.generator.receipt_path = single.receipt_path
        assert manager.generator.status()['state'] == 'experimental'
        assert manager.generator.status()['multiview']['state'] == 'unavailable'
        with pytest.raises(SceneError) as exc:
            await manager.submit(value, GENERATION_IDENTITY)
        assert exc.value.code == 'three_d_multiview_unavailable'
        assert not host.created
        await manager.stop()
    asyncio.run(scenario())


def test_changed_secondary_image_invalidates_retry(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, host, value, _ = multiview_manager(tmp_path, 2, 'waiting')
        job, _ = await manager.submit(value, GENERATION_IDENTITY)
        await asyncio.wait_for(host.requested.wait(), 3)
        await manager.cancel(job.id, 'user:7')
        await manager.wait_cleanup(job.id)
        manager.store.asset_path(value.additional_views[0].asset_id).write_bytes(b'changed')
        with pytest.raises(SceneError):
            await manager.submit(value.model_copy(update={'retry_job_id': job.id}), GENERATION_IDENTITY)
        assert len(host.created) == 1
        await manager.stop()
    asyncio.run(scenario())


def test_single_image_persisted_payload_stays_compatible(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager, _, value, _ = manager_fixture(tmp_path, 'waiting')
        job, record = await manager.submit(value, GENERATION_IDENTITY)
        assert 'additional_views' not in record.request and 'view_camera' not in record.request
        await manager.cancel(job.id, 'user:7')
        await manager.wait_cleanup(job.id)
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('changed', ['image', 'camera', 'runtime'])
def test_prepared_data_changes_never_start_the_native_process(tmp_path: Path, changed: str) -> None:
    async def scenario() -> None:
        manager, _, value, receipt = multiview_manager(tmp_path, 2)
        stage = tmp_path/'prepared-stage'; stage.mkdir()
        image = stage/'front.png'
        shutil.copyfile(manager.store.asset_path(value.input_asset_id), image)
        shutil.copyfile(manager.store.asset_path(value.additional_views[0].asset_id), stage/'view-source-1')
        prepared = await manager.generator.prepare(receipt, value, image, stage)
        if changed == 'image':
            (prepared.directory/'view-1.png').write_bytes(image.read_bytes())
        elif changed == 'camera':
            metadata = prepared.directory/'transforms.json'
            contents = json.loads(metadata.read_text())
            contents['mesh_scale'] = .5
            metadata.write_text(json.dumps(contents, sort_keys=True))
        else:
            executable = receipt.runtime_root/receipt.executable
            executable.write_text(executable.read_text()+'\n# changed after preparation\n')
        execution = HostExecution(GENERATION_IDENTITY, 'host-child', 'interactive', True,
                                  lease_id='test-only', device_id='gpu0')
        with pytest.raises(SceneError) as exc:
            await manager.generator.generate(receipt, value, image, stage, execution, prepared=prepared)
        assert exc.value.code == 'scene_multiview_input_changed'
        assert not (stage/'pid').exists() and not (stage/'generated.glb').exists()
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('change', [
    {'engine': 'trellis_cpp'}, {'resolution': 512}, {'refine_with_pixal3d': True},
    {'additional_views': [{'direction': 'right', 'asset_id': 'asset_'+'1'*32}]},
    {'additional_views': [{'direction': 'back', 'asset_id': 'asset_'+'2'*32}]},
    {'view_camera': {'fov_degrees': float('nan')}},
    {'view_camera': {'distance': True}},
])
def test_invalid_multiview_contract(change: dict[str, object]) -> None:
    base = {'name': 'test', 'input_asset_id': 'asset_'+'1'*32,
            'additional_views': [{'direction': 'right', 'asset_id': 'asset_'+'2'*32}]}
    with pytest.raises(ValidationError): SceneFromImageRequest.model_validate({**base, **change})
