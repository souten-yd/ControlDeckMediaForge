"""Protocol fixtures only: no pretrained models, real GPU or Host admission."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import threading
import venv

import pytest

from mediaforge.host.jobs import HostExecution
from mediaforge.pixal_runtime import MODEL_ROLES, PixalRuntimeReceipt, python_launcher
from mediaforge.scene_generation import SceneFromImageRequest
from mediaforge.scenes import SceneError
from mediaforge.three_d_runtime import ThreeDGenerator
from test_glb_import import glb_bytes
from test_scene_recipe_jobs import IDENTITY


WORKER = r'''
import hashlib,json,os,pathlib,sys,time
P=pathlib.Path
def arg(name): return sys.argv[sys.argv.index('--'+name)+1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def record(p): return {'sha256':sha(p),'size_bytes':p.stat().st_size}
def write(p,v): p.write_text(json.dumps(v))
mode=sys.argv[1]
assert P(sys.prefix)==P(__file__).parent/'.venv'
assert P(sys.pycache_prefix)==P.cwd()/(mode+'-user')/'pycache'
assert 'AUTHORIZATION' not in os.environ and 'PYTHONPATH' not in os.environ
P(mode+'.started').write_text(str(os.getpid()))
if FAULT=='sleep_'+mode: time.sleep(60)
if FAULT=='flood_'+mode:
 sys.stdout.write('x'*(16*1024*1024));sys.stdout.flush();time.sleep(60)
out=P(arg('output'));out.mkdir()
job=P(arg('job'))
if mode=='prepare':
 assert os.environ['HIP_VISIBLE_DEVICES']=='-1' and os.environ['ROCR_VISIBLE_DEVICES']=='-1'
 (out/'inputs').mkdir()
 names=['rgb_low.npy','rgb_high.npy','camera.npy','samplers.npy','shape_norm.npy','texture_norm.npy','framed.png','manifest.json']
 for name in names: (out/'inputs'/name).write_bytes(b'protocol fixture only')
 ready={'schema_version':'media-forge.pixal-prepared@1','source_kind':'checkpoint',
  'job_sha256':sha(job),'input_image_sha256':sha(P(arg('input'))),'seed':int(arg('seed')),
  'preprocessing':{'camera':{'backend':'cpu','precision':'float32','method':'moge-2'},'background':{'provider_used':False}},
  'files':{n:record(out/'inputs'/n) for n in names}}
 if FAULT=='manifest_seed': ready['seed']+=1
 write(out/'ready.json',ready)
else:
 time.sleep(.1)
 assert arg('backend')=='vulkan' and arg('device')=='1'
 prepared=P(arg('prepared'));ready=json.loads((prepared/'ready.json').read_text())
 assert sha(prepared/'ready.json')==arg('prepared-sha256')
 (out/'native').mkdir()
 asset=out/'native/asset.glb'
 asset.write_bytes(P(__file__).with_name('output.glb').read_bytes() if FAULT!='corrupt_output' else b'corrupt GLB')
 native={'source_kind':'checkpoint','backend':'vulkan','precision':'float32','device_index':1,
  'seed':ready['seed'],'source_sha256':sha(job),'input_sha256':arg('prepared-sha256'),
  'actual_resolution':1024,'rng_algorithm':'mt19937-box-muller-f32-v1','glb_bytes':asset.stat().st_size}
 if FAULT=='wrong_device': native['device_index']=0
 if FAULT=='wrong_backend': native['backend']='cpu'
 if FAULT=='bad_array_after_generation': (prepared/'inputs/camera.npy').write_bytes(b'tampered')
 complete={'schema_version':'media-forge.pixal-complete@1','job_sha256':sha(job),
  'prepared_sha256':arg('prepared-sha256'),'input_image_sha256':ready['input_image_sha256'],
  'preprocessing':ready['preprocessing'],'asset':{'filename':'native/asset.glb',**record(asset)},'native':native}
 write(out/'complete.json',complete)
'''


def file_identity(path: Path) -> dict[str, object]:
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}


def pixal_runtime(tmp_path: Path, *, allowed_root: Path | None = None, fault: str = '') -> tuple[ThreeDGenerator, PixalRuntimeReceipt]:
    runtime = tmp_path / 'pixal'
    runtime.mkdir(parents=True)
    venv.EnvBuilder(with_pip=False, symlinks=True).create(runtime / '.venv')
    worker = runtime / 'worker_entry.py'
    worker.write_text('FAULT=' + repr(fault) + '\n' + WORKER)
    native = runtime / 'pixal-generate'
    native.write_text('#!/bin/sh\nexit 99\n')  # Never executed by this protocol fixture.
    native.chmod(0o700)
    (runtime / 'output.glb').write_bytes(glb_bytes())
    models = runtime / 'models'; models.mkdir()
    records = {}
    for role in MODEL_ROLES | {'camera', 'background'}:
        p = models / role
        p.write_bytes(b'not model weights: protocol fixture')
        records[role] = {'path': str(p), **file_identity(p)}
    descriptor = runtime / 'descriptor.json'
    descriptor.write_text(json.dumps({'schema_version': 'media-forge.pixal-worker@1', 'source_kind': 'checkpoint',
        'native': {'path': str(native), **file_identity(native)},
        'models': {name: records[name] for name in MODEL_ROLES},
        'camera': {'source': str(models), 'checkpoint': records['camera']},
        'background': {'source': str(models), 'checkpoint': records['background']}, 'options': {'resolution': 1024}}))
    launcher = runtime / '.venv/bin/python'
    receipt = PixalRuntimeReceipt(engine='pixal3d', allowed_root=allowed_root or tmp_path,
        runtime_root=runtime, worker_entry=worker.name, python_launcher='.venv/bin/python',
        python_interpreter=launcher.resolve(), interpreter_file=file_identity(launcher), runtime_revision='b'*40,
        runtime_files={name: file_identity(runtime / name) for name in ('worker_entry.py', 'pixal-generate', '.venv/pyvenv.cfg', 'output.glb')},
        descriptor_path=descriptor, descriptor_file=file_identity(descriptor), model_id='test/pixal-protocol-only',
        model_revision='a'*40, license='test fixture only: no model/GPU adoption', license_accepted=True,
        device_id='gpu0', native_device_index=1, evaluated_resolution=1024,
        measured_peak_vram_bytes=1024**3, measured_runtime_sec=1, measured_preparation_sec=1,
        evaluated_output_sha256=file_identity(runtime / 'output.glb')['sha256'], backend='vulkan', validation='passed')
    receipt_path = tmp_path / 'pixal3d-runtime.json'
    receipt_path.write_text(receipt.model_dump_json())
    return ThreeDGenerator(tmp_path / 'trellis.json', pixal_receipt_path=receipt_path), receipt


def inputs(tmp_path: Path) -> tuple[Path, Path, SceneFromImageRequest, HostExecution]:
    root = tmp_path / 'work'; root.mkdir()
    image = root / 'input.png'; image.write_bytes(b'protocol image stub')
    value = SceneFromImageRequest(name='Pixal fixture', input_asset_id='asset_'+'1'*32, engine='pixal3d', seed=16777217)
    execution = HostExecution(IDENTITY, 'host-child', 'workflow', True, lease_id='lease', device_id='gpu0')
    return root, image, value, execution


def test_pixal_seals_cpu_inputs_uses_venv_and_preserves_provenance(tmp_path, monkeypatch):
    generator, receipt = pixal_runtime(tmp_path)
    root, image, value, execution = inputs(tmp_path)
    monkeypatch.setenv('AUTHORIZATION', 'not-for-the-worker')
    assert python_launcher(receipt) != receipt.python_interpreter
    assert generator.resolve().engine == generator.resolve('pixal3d').engine == 'pixal3d'
    async def run():
        prepared = await generator.prepare(receipt, value, image, root)
        assert not (root / 'generate.started').exists()
        for invalid in (replace(execution, lease_id=None), replace(execution, device_id='gpu1')):
            with pytest.raises(SceneError, match='GPU lease'):
                await generator.generate(receipt, value, image, root, invalid, prepared=prepared)
        path, facts = await generator.generate(receipt, value, image, root, execution, prepared=prepared)
        assert path.read_bytes() == glb_bytes()
        assert facts.seed == 16777217 and facts.runtime_adapter == 'pixal3d'
        assert facts.execution.backend == 'vulkan' and facts.execution.preprocessing_backend == 'cpu'
        assert facts.execution.prepared_sha256 == prepared.manifest_sha256
        assert facts.execution.input_image_sha256 == hashlib.sha256(image.read_bytes()).hexdigest()
    asyncio.run(run())
    assert generator.status()['engines']['pixal3d']['state'] == 'experimental'
    request = generator.resource_request(receipt, execution)
    assert request['residency_key'] == 'mediaforge:pixal3d:' + 'a'*40
    assert request['estimated_runtime_sec'] == 1


@pytest.mark.parametrize('change', ['synthetic', 'descriptor', 'model', 'python', 'worker', 'resolution'])
def test_pixal_rejects_unadopted_or_changed_files(tmp_path, change):
    generator, receipt = pixal_runtime(tmp_path)
    if change == 'resolution':
        with pytest.raises(SceneError, match='resolution'):
            generator.resolve('pixal3d', 512)
        return
    if change == 'synthetic':
        value = json.loads(receipt.descriptor_path.read_text()); value['source_kind'] = 'synthetic'
        receipt.descriptor_path.write_text(json.dumps(value))
        receipt = receipt.model_copy(update={'descriptor_file': type(receipt.descriptor_file).model_validate(file_identity(receipt.descriptor_path))})
    else:
        path = {'descriptor': receipt.descriptor_path, 'model': receipt.runtime_root/'models/dino',
                'worker': receipt.runtime_root/'worker_entry.py', 'python': receipt.runtime_root/'.venv/bin/python'}[change]
        if change == 'python':
            path.unlink(); path.symlink_to(receipt.runtime_root/'pixal-generate')
        else:
            path.write_bytes(b'x'*path.stat().st_size)
    with pytest.raises((ValueError, OSError)):
        generator.verify_files(receipt, hashes=True)


def test_invalid_trellis_receipt_does_not_silently_select_pixal(tmp_path):
    generator, _ = pixal_runtime(tmp_path)
    generator.receipt_path.write_text('{}')
    with pytest.raises(SceneError):
        generator.resolve()
    assert generator.resolve('pixal3d').engine == 'pixal3d'
    assert generator.status()['state'] == 'unavailable'
    assert generator.status()['engines']['pixal3d']['state'] == 'experimental'


@pytest.mark.parametrize('fault', ['manifest_seed', 'corrupt_output', 'wrong_device', 'wrong_backend', 'bad_array_after_generation'])
def test_pixal_rejects_mismatched_prepared_or_generated_output(tmp_path, fault):
    generator, receipt = pixal_runtime(tmp_path, fault=fault)
    root, image, value, execution = inputs(tmp_path)
    async def run():
        with pytest.raises(SceneError):
            prepared = await generator.prepare(receipt, value, image, root)
            await generator.generate(receipt, value, image, root, execution, prepared=prepared)
    asyncio.run(run())


@pytest.mark.parametrize('stage', ['prepare', 'generate'])
@pytest.mark.parametrize('cancel', [False, True])
def test_pixal_timeout_or_repeated_cancel_reaps_process(tmp_path, stage, cancel):
    generator, receipt = pixal_runtime(tmp_path, fault='sleep_'+stage)
    root, image, value, execution = inputs(tmp_path)
    if not cancel:
        if stage == 'prepare': generator.preparation_timeout_sec = .15
        else: generator.timeout_sec = .15
    async def run():
        prepared = None if stage == 'prepare' else await generator.prepare(receipt, value, image, root)
        task = asyncio.create_task(generator.prepare(receipt, value, image, root) if stage == 'prepare' else
            generator.generate(receipt, value, image, root, execution, prepared=prepared))
        for _ in range(200):
            if (root / (stage+'.started')).exists(): break
            await asyncio.sleep(.01)
        assert (root / (stage+'.started')).exists()
        if cancel:
            task.cancel(); await asyncio.sleep(0); task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else SceneError) as caught:
            await task
        if not cancel:
            assert caught.value.code == 'three_d_' + ('preparation' if stage == 'prepare' else 'generation') + '_timeout'
    asyncio.run(run())
    assert not Path('/proc/' + (root/(stage+'.started')).read_text()).exists()


def test_pixal_rejects_sealed_input_change_before_native_start(tmp_path):
    generator, receipt = pixal_runtime(tmp_path)
    root, image, value, execution = inputs(tmp_path)
    async def run():
        prepared = await generator.prepare(receipt, value, image, root)
        (prepared.directory/'inputs/camera.npy').write_bytes(b'tampered')
        with pytest.raises(SceneError, match='verification'):
            await generator.generate(receipt, value, image, root, execution, prepared=prepared)
        assert not (root/'generate.started').exists()
    asyncio.run(run())


def test_pixal_output_bound_reaps_even_when_the_worker_fills_its_pipe(tmp_path):
    generator, receipt = pixal_runtime(tmp_path, fault='flood_prepare')
    root, image, value, _ = inputs(tmp_path)
    async def run():
        with pytest.raises(SceneError, match='output exceeded'):
            await asyncio.wait_for(generator.prepare(receipt, value, image, root), 10)
    asyncio.run(run())
    assert not Path('/proc/' + (root/'prepare.started').read_text()).exists()


def test_pixal_cancellation_drains_started_file_verification_before_return(tmp_path, monkeypatch):
    generator, receipt = pixal_runtime(tmp_path)
    root, image, value, _ = inputs(tmp_path)
    started=threading.Event();finish=threading.Event()
    def verify(*args, **kwargs):
        started.set()
        assert finish.wait(timeout=10)
    monkeypatch.setattr('mediaforge.pixal_runtime.verify_pixal_files',verify)
    async def run():
        task=asyncio.create_task(generator.prepare(receipt,value,image,root))
        for _ in range(100):
            if started.is_set(): break
            await asyncio.sleep(.01)
        assert started.is_set()
        task.cancel();await asyncio.sleep(0);task.cancel()
        await asyncio.sleep(.02)
        assert not task.done() and not (root/'prepare.started').exists()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
