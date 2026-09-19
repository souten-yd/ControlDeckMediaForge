#!/usr/bin/env python3
"""Exercise core process ownership with real CPU/synthetic workers, no adoption.

This does not create a PixalRuntimeReceipt, a Host identity/lease, or any installed
Asset. Core Scene Jobs contract fixtures and this real process gate are separate.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time

from mediaforge.glb import validate_glb_path
from mediaforge.paths import contained
from mediaforge.pixal_runtime import PixalWorkerLaunch, run_worker
from mediaforge.scenes import SceneError
from mediaforge.three_d_runtime_files import sha256_file


def record(path: Path) -> dict[str, object]:
    return {'sha256': sha256_file(path), 'size_bytes': path.stat().st_size}


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def children(pid: int) -> list[int]:
    path = Path(f'/proc/{pid}/task/{pid}/children')
    return [int(x) for x in path.read_text().split()] if path.exists() else []


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('allowed-root', 'output-dir', 'fixtures', 'worker-source', 'worker-python',
                 'native-binary', 'opaque-image', 'alpha-image', 'blender'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    allowed = args.allowed_root.resolve(strict=True)
    root = contained(allowed, args.output_dir)
    root.mkdir(mode=0o700, parents=True)
    old = json.loads((args.fixtures/'report.json').read_text())
    assert old['passed'] and old['backend']=='cpu' and old['source_kind']=='synthetic'
    assert old['pretrained_weights']=='NOT USED'
    job = json.loads((args.fixtures/'job.json').read_text())
    assert job['source_kind']=='synthetic'
    assert sha256_file(args.native_binary)==job['native']['sha256']==old['binary_sha256']
    source = root/'worker'; source.mkdir()
    source_hashes = {}
    for path in args.worker_source.glob('*.py'):
        shutil.copyfile(path, source/path.name)
        assert sha256_file(path)==sha256_file(source/path.name)
        source_hashes[path.name]=sha256_file(path)
    binary = root/'pixal-generate'
    shutil.copyfile(args.native_binary, binary); binary.chmod(0o700)
    job['native']={'path':str(binary),**record(binary)}
    descriptor = root/'job.json'; write(descriptor,job)
    # Process configuration is deliberately not an adoption receipt.
    launcher_parent = contained(allowed, args.worker_python.parent)
    launcher = launcher_parent / args.worker_python.name
    launch = PixalWorkerLaunch(allowed_root=allowed,runtime_root=allowed,
        worker_entry=str((source/'worker_entry.py').relative_to(allowed)),
        python_launcher=str(launcher.relative_to(allowed)),python_interpreter=launcher.resolve(),
        interpreter_file=record(launcher),descriptor_path=descriptor)
    times = {}
    async def run(label: str, mode: str, work: Path, arguments: list[str], config: PixalWorkerLaunch = launch) -> None:
        started=time.monotonic()
        await run_worker(config,work,mode,arguments,120)
        times[label]=time.monotonic()-started
    work=root/'connected';work.mkdir()
    image=work/'input.png';shutil.copyfile(args.opaque_image,image)
    prepared=work/'prepared'
    await run('prepare','prepare',work,['--input',str(image),'--seed','42','--output',str(prepared)])
    for name in ('framed.png','rgb_low.npy','rgb_high.npy','camera.npy'):
        assert (prepared/'inputs'/name).read_bytes()==(args.fixtures/'prepared/inputs'/name).read_bytes()
    generated=work/'generated'
    await run('generate','generate',work,['--prepared',str(prepared),
        '--prepared-sha256',sha256_file(prepared/'ready.json'),'--backend','cpu','--timeout','60','--output',str(generated)])
    complete=json.loads((generated/'complete.json').read_text())
    assert complete['native']['backend']=='cpu' and complete['native']['source_kind']=='synthetic'
    asset=generated/'native/asset.glb'
    assert complete['asset']['sha256']==sha256_file(asset)
    validation=validate_glb_path(asset,root)
    def payload(path: Path) -> tuple[dict,bytes]:
        content=path.read_bytes();count=struct.unpack_from('<I',content,12)[0]
        document=json.loads(content[20:20+count]);document['asset'].pop('extras')
        return document,content[28+count:]
    assert payload(asset)==payload(args.fixtures/'connected/native/asset.glb')
    write(root/'outputs.json',[str(asset)])
    started=time.monotonic()
    blender=subprocess.run([str(args.blender),'--background','--factory-startup','--threads','4',
        '--python',str(source/'check_surface_blender.py'),'--',str(root/'outputs.json'),str(root/'blender.json')],
        text=True,capture_output=True,timeout=60)
    times['blender']=time.monotonic()-started
    (root/'blender.log').write_text(blender.stdout+blender.stderr)
    assert blender.returncode==0,blender.stderr
    print(json.dumps({'stage':'generated','bytes':asset.stat().st_size,'times':times}),flush=True)
    long_job=copy.deepcopy(job);long_job['options']['samplers'][0][0]=1000
    long_descriptor=root/'long-job.json';write(long_descriptor,long_job)
    long_launch=launch.model_copy(update={'descriptor_path':long_descriptor})
    preparation=root/'long-prepare';preparation.mkdir()
    alpha=preparation/'input.png';shutil.copyfile(args.alpha_image,alpha)
    sealed=preparation/'prepared'
    await run('long_prepare','prepare',preparation,['--input',str(alpha),'--seed','42','--output',str(sealed)],long_launch)
    lifecycle=[]
    for case in ('cancel','timeout'):
        case_root=root/case;case_root.mkdir()
        output=case_root/'generated'
        task=asyncio.create_task(run_worker(long_launch,case_root,'generate',[
            '--prepared',str(sealed),'--prepared-sha256',sha256_file(sealed/'ready.json'),
            '--backend','cpu','--timeout','60','--output',str(output)],.7 if case=='timeout' else 120))
        observed=False;tracked=set();group_verified=False;started=time.monotonic();signal_at=None
        try:
            while not task.done() and time.monotonic()-started<60:
                for worker in children(os.getpid()):
                    try:
                        command=Path(f'/proc/{worker}/cmdline').read_bytes()
                        if str(source/'worker_entry.py').encode() not in command: continue
                        tracked.add(worker)
                        for native in children(worker):
                            tracked.add(native)
                            assert os.getpgid(native)==worker
                            group_verified=True
                    except FileNotFoundError:
                        continue
                log=output/'native.stdout.log'
                if log.exists() and b'stage=ss_flow' in log.read_bytes():
                    observed=True
                    if case=='cancel':
                        signal_at=time.monotonic();task.cancel();await asyncio.sleep(0);task.cancel();break
                await asyncio.sleep(.005)
            if case=='cancel':
                assert observed and group_verified
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                else:
                    raise AssertionError('cancellation was swallowed')
            else:
                try:
                    await task
                except SceneError as error:
                    assert error.code=='three_d_generation_timeout'
                else:
                    raise AssertionError('deadline was ignored')
            assert tracked and all(not Path(f'/proc/{pid}').exists() for pid in tracked)
            assert not output.exists()
            lifecycle.append({'case':case,'pids':sorted(tracked),'all_reaped':True,
                'native_same_group_observed':group_verified,'ss_flow_observed':observed,
                'seconds':time.monotonic()-(signal_at or started),'output_retained':False})
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
    repo=Path(__file__).resolve().parents[1]
    core_files=['backend/mediaforge/pixal_runtime.py','backend/mediaforge/three_d_runtime.py',
        'backend/mediaforge/three_d_runtime_files.py','backend/mediaforge/scene_generation.py',
        'backend/mediaforge/scene_generation_jobs.py','scripts/3ds_pixal_worker_process_e2e.py']
    write(root/'report.json',{'passed':True,'times':times,'lifecycle':lifecycle,'output':record(asset),
        'validation':validation,'blender':json.loads((root/'blender.json').read_text()),
        'prior_glb_payload_exact_except_provenance':True,'preprocessing_arrays_exact':True,
        'core_files':{name:sha256_file(repo/name) for name in core_files},'worker_source_files':source_hashes,
        'backend':'cpu','source_kind':'synthetic','adoption_receipt_created':False,'host_lease_created':False,
        'pretrained_weights':'NOT USED','installed_assets_registered':0,
        'not_tested':['trained generation/quality','real Host admission/Vulkan','installed adoption','core Scene Jobs real Host path']})
    print(json.dumps({'passed':True,'lifecycle':lifecycle}),flush=True)


if __name__=='__main__':
    asyncio.run(main())
