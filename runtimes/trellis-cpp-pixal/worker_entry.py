#!/usr/bin/env python3
"""Private prepare/generate processes; the parent owns adoption and Host lease.

Prepare runs CPU models and exits before GPU admission. Generate verifies the
sealed result and runs one explicitly selected native backend, never a fallback.
No success here registers an Asset or grants GPU authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import time
from typing import Any, Callable

from camera import contained_file, file_sha256
from worker_spec import (INTEGER_OPTIONS, PREPARED_FILES, ROLES, directory,
                         file_record, hash_string, integer, keys, load_spec, read_json, verified_file)

Cancel = Callable[[], bool]


def check_cancel(cancelled: Cancel | None) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError('Pixal worker cancelled')


def destination(path: Path, root: Path) -> Path:
    path = path.absolute()
    parent = directory(str(path.parent), root)
    target = parent / path.name
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    return target


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')
    path.chmod(0o600)


def native_models(spec: dict[str, Any]) -> list[str]:
    return [part for role in ROLES for part in ('--' + role, spec['models'][role]['path'])] + ['--source-kind', spec['source_kind']]


def run_native(command: list[str], work: Path, label: str, *, timeout: float,
               cancelled: Cancel | None = None) -> None:
    """Reap before returning. Children share the caller-owned process group."""
    check_cancel(cancelled)
    user = work / (label + '-user')
    user.mkdir(mode=0o700)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(user), 'XDG_CACHE_HOME': str(user / 'cache'),
           'XDG_CONFIG_HOME': str(user / 'config'), 'HF_HUB_OFFLINE': '1'}
    logs = [work / (label + '.stdout.log'), work / (label + '.stderr.log')]
    with logs[0].open('xb') as stdout, logs[1].open('xb') as stderr:
        process = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr)
        started = time.monotonic()
        try:
            while process.poll() is None:
                check_cancel(cancelled)
                if time.monotonic() - started > timeout:
                    raise TimeoutError('Pixal native process exceeded time bound')
                if any(path.stat().st_size > 32 * 1024**2 for path in logs):
                    raise ValueError('Pixal native output exceeds log bound')
                time.sleep(.05)
            check_cancel(cancelled)
            if process.returncode != 0:
                with logs[1].open('rb') as errors:
                    errors.seek(max(0, logs[1].stat().st_size - 2048))
                    detail = errors.read().decode('utf-8', errors='replace').strip()
                raise RuntimeError(f'Pixal native {label} exited {process.returncode}: {detail}')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def prepare_job(spec_path: Path, image: Path, output: Path, *, seed: int,
                allowed_root: Path, binary_root: Path, cancelled: Cancel | None = None,
                progress: Callable[[str, int, int], None] | None = None) -> dict[str, Any]:
    from background import BackgroundSpec
    from prepare_camera import prepare_camera_input
    import numpy as np

    integer(seed, 0, 2**31 - 1, 'seed')
    output = destination(output, allowed_root)
    image = contained_file(image, allowed_root)
    spec_path = contained_file(spec_path, allowed_root)
    spec_sha, image_sha = file_sha256(spec_path), file_sha256(image)
    spec = load_spec(spec_path, allowed_root, binary_root, cancelled)
    output.mkdir(mode=0o700)
    try:
        run_native([spec['native']['path'], 'inspect', *native_models(spec)], output, 'inspect', timeout=120, cancelled=cancelled)
        cam, background, options = spec['camera'], spec['background'], spec['options']
        prepared = output / 'inputs'
        camera = prepare_camera_input(source=Path(cam['source']), checkpoint=Path(cam['checkpoint']['path']),
            checkpoint_sha256=cam['checkpoint']['sha256'], allowed_root=allowed_root,
            image_path=image, output_dir=prepared, source_kind=spec['source_kind'],
            low_size=options['low_size'], high_size=options['high_size'],
            num_tokens=cam['num_tokens'], mesh_scale=cam['mesh_scale'], extend_pixel=cam['extend_pixel'],
            image_resolution=cam['image_resolution'], cancelled=cancelled, progress=progress,
            background_spec=BackgroundSpec(Path(background['source']), Path(background['checkpoint']['path']),
                background['checkpoint']['sha256'], spec['source_kind']))
        for name in ('samplers', 'shape_norm', 'texture_norm'):
            np.save(prepared / (name + '.npy'), np.asarray(options[name], dtype='<f4'), allow_pickle=False)
        if file_sha256(image) != image_sha or file_sha256(spec_path) != spec_sha:
            raise ValueError('worker input identity changed during preparation')
        load_spec(spec_path, allowed_root, binary_root, cancelled)
        manifest = {'schema_version': 'media-forge.pixal-prepared@1', 'job_sha256': spec_sha,
            'input_image_sha256': image_sha, 'source_kind': spec['source_kind'], 'seed': seed,
            'preprocessing': {'camera': camera['camera'], 'background': camera['background']},
            'files': {name: file_record(prepared / name) for name in PREPARED_FILES}}
        check_cancel(cancelled)
        write_json(output / 'ready.partial', manifest)
        check_cancel(cancelled)
        (output / 'ready.partial').rename(output / 'ready.json')
        return manifest
    except BaseException:
        shutil.rmtree(output)
        raise


def verify_prepared(prepared: Path, expected_sha: str, spec_sha: str, source_kind: str,
                    allowed_root: Path) -> dict[str, Any]:
    prepared = directory(str(prepared), allowed_root)
    ready = contained_file(prepared / 'ready.json', prepared)
    if file_sha256(ready) != hash_string(expected_sha):
        raise ValueError('prepared manifest identity changed')
    value = read_json(ready)
    keys(value, {'schema_version', 'job_sha256', 'input_image_sha256', 'source_kind', 'seed', 'preprocessing', 'files'}, 'prepared manifest')
    if value['schema_version'] != 'media-forge.pixal-prepared@1' or value['job_sha256'] != spec_sha or value['source_kind'] != source_kind:
        raise ValueError('prepared manifest belongs to a different descriptor')
    hash_string(value['input_image_sha256'])
    integer(value['seed'], 0, 2**31 - 1, 'prepared seed')
    keys(value['files'], set(PREPARED_FILES), 'prepared files')
    for name, record in value['files'].items():
        verified_file(record, prepared, with_path=False, path=prepared / 'inputs' / name)
    return value


def generate_job(spec_path: Path, prepared: Path, prepared_sha256: str, output: Path, *,
                 allowed_root: Path, binary_root: Path, backend: str, device: int | None,
                 timeout: float = 1800, cancelled: Cancel | None = None) -> dict[str, Any]:
    if backend not in {'cpu', 'vulkan'} or (backend == 'vulkan') != (device is not None):
        raise ValueError('explicit worker backend/device required')
    if device is not None:
        integer(device, 0, 31, 'Vulkan device index')
    if type(timeout) not in (int, float) or not 0 < timeout <= 86400:
        raise ValueError('invalid worker timeout')
    output = destination(output, allowed_root)
    spec_path = contained_file(spec_path, allowed_root)
    spec_sha = file_sha256(spec_path)
    spec = load_spec(spec_path, allowed_root, binary_root, cancelled)
    prepared = directory(str(prepared), allowed_root)
    value = verify_prepared(prepared, prepared_sha256, spec_sha, spec['source_kind'], allowed_root)
    options = spec['options']
    output.mkdir(mode=0o700)
    try:
        command = [spec['native']['path'], 'generate', *native_models(spec),
            '--input', str(prepared / 'inputs'), '--output', str(output / 'native'),
            '--backend', backend, '--precision', 'float32', '--source-sha', spec_sha,
            '--input-sha', prepared_sha256, '--seed', str(value['seed'])]
        if device is not None:
            command += ['--device', str(device)]
        command += [part for key in INTEGER_OPTIONS if key not in {'low_size', 'high_size'}
                    for part in ('--' + key.replace('_', '-'), str(options[key]))]
        run_native(command, output, 'native', timeout=timeout, cancelled=cancelled)
        report = read_json(contained_file(output / 'native/report.json', output))
        for key, expected in {'source_kind': spec['source_kind'], 'backend': backend,
            'device_index': -1 if device is None else device, 'precision': 'float32',
            'seed': value['seed'], 'source_sha256': spec_sha, 'input_sha256': prepared_sha256}.items():
            if report.get(key) != expected:
                raise ValueError('native report identity differs: ' + key)
        asset = contained_file(output / 'native/asset.glb', output)
        size = asset.stat().st_size
        with asset.open('rb') as stream:
            header = stream.read(12)
        if not 20 <= size <= 64 * 1024**2 or header != struct.pack('<4sII', b'glTF', 2, size) or report.get('glb_bytes') != size:
            raise ValueError('native output is not a bounded GLB')
        if file_sha256(spec_path) != spec_sha:
            raise ValueError('worker descriptor changed during generation')
        load_spec(spec_path, allowed_root, binary_root, cancelled)
        verify_prepared(prepared, prepared_sha256, spec_sha, spec['source_kind'], allowed_root)
        complete = {'schema_version': 'media-forge.pixal-complete@1', 'job_sha256': spec_sha,
            'prepared_sha256': prepared_sha256, 'input_image_sha256': value['input_image_sha256'],
            'asset': {'filename': 'native/asset.glb', **file_record(asset)}, 'native': report,
            'preprocessing': value['preprocessing']}
        check_cancel(cancelled)
        write_json(output / 'complete.partial', complete)
        check_cancel(cancelled)
        (output / 'complete.partial').rename(output / 'complete.json')
        return complete
    except BaseException:
        shutil.rmtree(output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'generate'))
    for name in ('job', 'allowed-root', 'binary-root', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--prepared-sha256')
    parser.add_argument('--backend', choices=('cpu', 'vulkan'))
    parser.add_argument('--device', type=int)
    parser.add_argument('--timeout', type=float, default=1800)
    args = parser.parse_args()
    stop = False
    def request_stop(_signal: int, _frame: Any) -> None:
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    def progress(stage: str, done: int, total: int) -> None:
        print(json.dumps({'stage': stage, 'done': done, 'total': total}), flush=True)
    try:
        if args.mode == 'prepare':
            if args.input is None or args.seed is None or any(v is not None for v in (args.prepared, args.prepared_sha256, args.backend, args.device)):
                raise ValueError('prepare requires input/seed and accepts no backend or prepared input')
            os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1')
            import torch
            torch.set_num_threads(2)
            prepare_job(args.job, args.input, args.output, seed=args.seed, allowed_root=args.allowed_root,
                binary_root=args.binary_root, cancelled=lambda: stop, progress=progress)
            filename = 'ready.json'
        else:
            if args.prepared is None or args.prepared_sha256 is None or args.backend is None or args.input is not None or args.seed is not None:
                raise ValueError('generate requires prepared input/hash/backend and accepts no raw image or seed')
            generate_job(args.job, args.prepared, args.prepared_sha256, args.output,
                allowed_root=args.allowed_root, binary_root=args.binary_root, backend=args.backend,
                device=args.device, timeout=args.timeout, cancelled=lambda: stop)
            filename = 'complete.json'
        print(json.dumps({'completed': True, 'manifest': filename, 'sha256': file_sha256(args.output / filename)}), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({'completed': False, 'error': str(error)}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
