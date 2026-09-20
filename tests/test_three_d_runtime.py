from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

from mediaforge.host.jobs import HostExecution
from mediaforge.scene_generation import SceneFromImageRequest
from mediaforge.scenes import SceneError
from mediaforge.three_d_runtime import MODEL_FILES, ThreeDGenerator, ThreeDRuntimeReceipt
from test_glb_import import glb_bytes
from test_scene_recipe_jobs import IDENTITY


def native_runtime(tmp_path: Path, *, script: str = ''):
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    exe = runtime / 'trellis-cli'
    exe.write_text(f'#!{sys.executable}\nimport pathlib,sys,os,time\n' + script + '''
assert 'AUTHORIZATION' not in os.environ
assert '--require-gpu' in sys.argv
assert sys.argv[sys.argv.index('--gpu')+1] == '1'
out = pathlib.Path(sys.argv[sys.argv.index('--output')+1])
out.write_bytes(pathlib.Path(__file__).with_name('output.glb').read_bytes())
''')
    exe.chmod(0o700)
    (runtime/'output.glb').write_bytes(glb_bytes())
    repository = tmp_path/'weights'
    snapshot = repository/'snapshots'/('a'*40)
    snapshot.mkdir(parents=True)
    for name in MODEL_FILES:
        (snapshot/name).write_bytes(b'test model placeholder')
    def facts(path):
        return {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes':path.stat().st_size}
    receipt = ThreeDRuntimeReceipt(
        engine='trellis_cpp', runtime_root=runtime, executable='trellis-cli', runtime_revision='b'*40,
        runtime_files={p.name:facts(p) for p in runtime.iterdir()},
        model_repository=repository, model_snapshot='snapshots/'+snapshot.name,
        model_id='test/model', model_revision=snapshot.name,
        model_files={p.name:facts(p) for p in snapshot.iterdir()}, license='test fixture only',
        license_accepted=True, device_id='gpu0', native_device_index=1, evaluated_resolution=1024,
        measured_peak_vram_bytes=1024**3, measured_runtime_sec=1,
        evaluated_output_sha256=hashlib.sha256(glb_bytes()).hexdigest(), validation='passed',
    )
    path=tmp_path/'receipt.json'
    path.write_text(receipt.model_dump_json())
    return ThreeDGenerator(path), receipt


def test_native_generation_requires_exact_lease_and_produces_verified_facts(tmp_path, monkeypatch):
    generator, receipt = native_runtime(tmp_path)
    work=tmp_path/'work'
    work.mkdir()
    image=work/'image.png'
    image.write_bytes(b'input stub for native fixture')
    request=SceneFromImageRequest(name='Test', input_asset_id='asset_'+'1'*32)
    execution=HostExecution(IDENTITY, 'host-child', 'workflow', True)
    for device,lease in [(None,None),('host','lease'),('gpu1','lease')]:
        execution.device_id,execution.lease_id=device,lease
        with pytest.raises(SceneError, match='GPU lease'):
            asyncio.run(generator.generate(receipt,request,image,work,execution))
    assert list(work.iterdir())==[image]
    execution.device_id,execution.lease_id='gpu0','lease'
    monkeypatch.setenv('AUTHORIZATION','must-not-reach-worker')
    output,facts=asyncio.run(generator.generate(receipt,request,image,work,execution))
    assert output.read_bytes()==glb_bytes()
    assert facts.output_sha256==hashlib.sha256(output.read_bytes()).hexdigest()
    assert facts.model_revision==receipt.model_revision and facts.elapsed_sec>0
    assert generator.status()['state']=='experimental'
    resource_request = generator.resource_request(receipt, execution)
    assert resource_request['estimated_runtime_sec'] == 1
    # Host VramConfidence accepts measured/estimated/low, never high.
    assert resource_request['vram']['confidence'] == 'measured'
    assert resource_request['class'] == 'workflow'
    assert resource_request['priority'] == 0  # Host workflow ceiling is 15.


def test_unadopted_or_changed_runtime_cannot_start(tmp_path):
    generator,receipt=native_runtime(tmp_path)
    with pytest.raises(SceneError):
        generator.resolve('pixal3d')
    with pytest.raises(SceneError):
        generator.resolve(resolution=512)
    model=receipt.model_repository/receipt.model_snapshot/'ss_flow.gguf'
    model.write_bytes(b'x'*model.stat().st_size)
    with pytest.raises(ValueError, match='digest'):
        generator.verify_files(receipt,hashes=True)
    model.unlink()
    assert generator.status()['state']=='unavailable'
    generator.receipt_path.unlink()
    assert generator.status()['state']=='unavailable'


@pytest.mark.parametrize('cancel', [False, True])
def test_native_timeout_or_cancel_reaps_worker(tmp_path,cancel):
    generator,receipt=native_runtime(tmp_path,script="pathlib.Path('pid').write_text(str(os.getpid()))\ntime.sleep(60)\n")
    generator.timeout_sec=10 if cancel else 0.15
    work=tmp_path/'work';work.mkdir()
    image=work/'image.png';image.write_bytes(b'fixture')
    execution=HostExecution(IDENTITY,'host-child','workflow',True,lease_id='lease',device_id='gpu0')
    async def scenario():
        task=asyncio.create_task(generator.generate(receipt,SceneFromImageRequest(name='Test',input_asset_id='asset_'+'1'*32),image,work,execution))
        if cancel:
            for _ in range(100):
                if (work/'pid').exists(): break
                await asyncio.sleep(0.01)
            assert (work/'pid').exists()
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else SceneError):
            await task
    asyncio.run(scenario())
    pid=int((work/'pid').read_text())
    assert not Path(f'/proc/{pid}').exists()
    assert not (work/'generated.glb').exists()


def test_receipt_may_measure_more_than_one_resolution(tmp_path):
    """採用は解像度ごとに測る。上へ上げても下を落とさない。

    実機は trellis.cpp を 512 で採用していた。1024 へ上げるだけだと、密な入力が
    1024 でホスト RAM を使い切るときに逃げ道が無くなる。既定は上、選択肢に下も残す。
    """
    generator, receipt = native_runtime(tmp_path)
    generator.receipt_path.write_text(receipt.model_copy(update={
        'evaluated_resolution': 1024, 'evaluated_resolutions': [1024, 512],
        'measured_runtime_by_resolution': {'1024': 513.6, '512': 104.1},
    }).model_dump_json())
    adopted = generator.resolve('trellis_cpp')
    assert adopted.measured_resolutions() == [1024, 512]
    # 既定が先頭。画面はこれを既定として出す。
    assert adopted.evaluated_resolution == 1024
    assert adopted.runtime_sec(512) == 104.1 and adopted.runtime_sec(1024) == 513.6
    for resolution in (512, 1024):
        assert generator.resolve('trellis_cpp', resolution).evaluated_resolution == 1024
    status = generator.status()
    assert status['resolutions'] == [1024, 512]
    assert status['estimated_runtime_by_resolution'] == {'1024': 513.6, '512': 104.1}
    assert status['engines']['trellis_cpp']['resolutions'] == [1024, 512]


def test_unmeasured_resolution_is_still_refused(tmp_path):
    generator, receipt = native_runtime(tmp_path)
    generator.receipt_path.write_text(receipt.model_copy(update={
        'evaluated_resolution': 1024, 'evaluated_resolutions': [1024],
    }).model_dump_json())
    with pytest.raises(SceneError, match='has not been measured'):
        generator.resolve('trellis_cpp', 512)


def test_receipt_rejects_a_default_outside_its_measured_set(tmp_path):
    generator, receipt = native_runtime(tmp_path)
    for update in (
        # 既定が宣言の外
        {'evaluated_resolution': 1024, 'evaluated_resolutions': [512]},
        # 宣言が重複
        {'evaluated_resolution': 512, 'evaluated_resolutions': [512, 512]},
        # 計測時間が宣言と食い違う
        {'evaluated_resolution': 512, 'evaluated_resolutions': [512],
         'measured_runtime_by_resolution': {'1024': 1.0}},
        # 計測時間が不正
        {'evaluated_resolution': 512, 'evaluated_resolutions': [512],
         'measured_runtime_by_resolution': {'512': 0.0}},
    ):
        payload = receipt.model_copy(update=update).model_dump(mode='json')
        with pytest.raises(ValidationError):
            ThreeDRuntimeReceipt.model_validate(payload)


def test_existing_single_resolution_receipts_still_load(tmp_path):
    """省略時は今までどおり 1 つだけ測ったものとして読む。"""
    generator, receipt = native_runtime(tmp_path)
    assert receipt.evaluated_resolutions is None
    adopted = generator.resolve('trellis_cpp')
    assert adopted.measured_resolutions() == [receipt.evaluated_resolution]
    assert adopted.runtime_sec(receipt.evaluated_resolution) == receipt.measured_runtime_sec
    assert generator.status()['resolutions'] == [receipt.evaluated_resolution]
