from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import sys

import pytest

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
