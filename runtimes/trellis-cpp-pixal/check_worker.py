#!/usr/bin/env python3
"""Actual private worker/native entry checks, CPU and synthetic weights only."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import struct
import subprocess
import sys
import time
from typing import Any

from camera import file_sha256
from worker_spec import file_record, load_spec, ROLES
from worker_entry import verify_prepared, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('background-source', 'moge-source', 'background-fixtures', 'camera-fixtures',
                 'pipeline-fixtures', 'binary', 'baseline-binary', 'core-python', 'blender', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True)
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1')
    import numpy as np
    prior = json.loads((args.pipeline_fixtures / 'report.json').read_text())
    background_report = json.loads((args.background_fixtures / 'report.json').read_text())
    assert prior['passed'] and background_report['passed'] and background_report['pretrained_weights'] == 'NOT USED'
    saved = json.loads((args.pipeline_fixtures / 'cascade1024.command.json').read_text())['argv']
    models = {name: Path(saved[saved.index('--' + name) + 1]) for name in ROLES}
    def record(path: Path) -> dict[str, Any]:
        return {'path': str(path.resolve()), **file_record(path)}
    assert all(file_sha256(path) == prior['models'][name] for name, path in models.items())
    fixture = args.pipeline_fixtures / 'cascade1024-input'
    settings = np.load(fixture / 'settings.npy').tolist()
    samplers = np.load(fixture / 'samplers.npy').reshape(3, 7).tolist()
    for sampler in samplers:
        sampler[0] = int(sampler[0])
    spec = {'schema_version': 'media-forge.pixal-worker@1', 'source_kind': 'synthetic',
        'native': record(args.binary), 'models': {name: record(path) for name, path in models.items()},
        'camera': {'source': str(args.moge_source.resolve()), 'checkpoint': record(args.camera_fixtures / 'moge-synthetic.pt'),
                   'num_tokens': None, 'mesh_scale': 1., 'extend_pixel': 0, 'image_resolution': 512},
        'background': {'source': str(args.background_source.resolve()), 'checkpoint': record(args.background_fixtures / 'birefnet-synthetic.safetensors')},
        'options': {'low_size': 12, 'high_size': 16, 'resolution': int(settings[0]), 'max_tokens': int(settings[1]),
            'naf_lr': int(settings[2]), 'naf_hr': int(settings[3]), 'naf_texture': int(settings[4]),
            'texture_size': int(settings[5]), 'target_faces': int(settings[6]),
            'decoder_chunk': 64, 'max_voxels': 100000, 'max_triangles': 200000,
            'samplers': samplers, 'shape_norm': np.load(fixture / 'shape_norm.npy').tolist(),
            'texture_norm': np.load(fixture / 'texture_norm.npy').tolist()}}
    descriptor = root / 'job.json'
    write_json(descriptor, spec)
    allowed = Path(os.path.commonpath([str(root), str(args.background_source.resolve()), str(args.moge_source.resolve()), *[str(p.resolve()) for p in models.values()]]))
    binary_root = args.binary.resolve().parent
    worker = Path(__file__).with_name('worker_entry.py')
    times = {}
    outputs = []
    negatives = []
    def execute(label: str, command: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
        start = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (root / (label + '.log')).write_text(result.stdout + result.stderr)
        times[label] = time.monotonic() - start
        assert result.returncode == expected, (label, result.stdout, result.stderr)
        return result
    def common(mode: str, output: Path, job: Path = descriptor) -> list[str]:
        return [sys.executable, str(worker), mode, '--job', str(job), '--allowed-root', str(allowed),
                '--binary-root', str(binary_root), '--output', str(output)]
    def generate(label: str, prepared: Path, job: Path = descriptor) -> dict[str, Any]:
        target = root / label
        execute(label, common('generate', target, job) + ['--prepared', str(prepared),
            '--prepared-sha256', file_sha256(prepared / 'ready.json'), '--backend', 'cpu'])
        result = json.loads((target / 'complete.json').read_text())
        assert result['asset']['sha256'] == file_sha256(target / 'native/asset.glb')
        assert result['native']['backend'] == 'cpu' and result['native']['device_index'] == -1
        outputs.append(str(target / 'native/asset.glb'))
        return result
    prepared = root / 'prepared'
    execute('prepare', common('prepare', prepared) + ['--input', str(args.background_fixtures / 'opaque.png'), '--seed', '42'])
    ready = json.loads((prepared / 'ready.json').read_text())
    assert ready['preprocessing']['background']['provider_used'] and ready['seed'] == 42
    for name in ('framed.png', 'rgb_low.npy', 'rgb_high.npy', 'camera.npy'):
        assert (prepared / 'inputs' / name).read_bytes() == (args.background_fixtures / 'prepared' / name).read_bytes()
    result = generate('connected', prepared)
    print(json.dumps({'stage': 'connected', 'prepare_seconds': times['prepare'], 'generate_seconds': times['connected']}), flush=True)
    # Compare with the existing evaluation entry, identical sampler/noise/inputs.
    reference_input = root / 'reference-input'
    shutil.copytree(prepared / 'inputs', reference_input)
    np.save(reference_input / 'settings.npy', np.asarray(settings, dtype=np.float32))
    baseline_command = [str(args.baseline_binary), str(reference_input), str(root / 'baseline'), 'cpu',
        *[v for name, path in models.items() for v in ('--' + name, str(path))],
        '--source-sha', file_sha256(descriptor), '--input-sha', file_sha256(prepared / 'ready.json'), '--native-noise']
    execute('baseline', baseline_command)
    def payload(path: Path) -> tuple[dict[str, Any], bytes]:
        content = path.read_bytes()
        count = struct.unpack_from('<I', content, 12)[0]
        value = json.loads(content[20:20 + count])
        value['asset']['extras'].pop('generated')
        return value, content[28 + count:]
    assert payload(root / 'connected/native/asset.glb') == payload(root / 'baseline/asset.glb')
    # The same request repeats exactly apart from the native generation timestamp.
    generate('repeated', prepared)
    assert payload(root / 'connected/native/asset.glb') == payload(root / 'repeated/native/asset.glb')
    seed_cases = []
    for seed in (16777216, 16777217, 2147483647):
        target = root / ('seed-' + str(seed))
        execute('prepare-' + str(seed), common('prepare', target) + ['--input', str(args.camera_fixtures / 'input.png'), '--seed', str(seed)])
        value = generate('generated-' + str(seed), target)
        document, binary = payload(root / ('generated-' + str(seed)) / 'native/asset.glb')
        assert value['native']['seed'] == seed == document['asset']['extras']['seed']
        seed_cases.append({'seed': seed, 'glb_sha256': value['asset']['sha256'], 'binary_sha256': __import__('hashlib').sha256(binary).hexdigest()})
    assert seed_cases[0]['binary_sha256'] != seed_cases[1]['binary_sha256']
    def rejected(name: str, call: Any, message: str) -> None:
        try:
            call()
        except (ValueError, FileNotFoundError, InterruptedError) as error:
            assert message in str(error), (name, str(error))
            negatives.append({'case': name, 'error': str(error)})
        else:
            raise AssertionError(name + ' accepted')
    rejected('prepared_hash', lambda: verify_prepared(prepared, '0' * 64, file_sha256(descriptor), 'synthetic', allowed), 'identity')
    rejected('prepared_other_job', lambda: verify_prepared(prepared, file_sha256(prepared / 'ready.json'), '0' * 64, 'synthetic', allowed), 'different descriptor')
    for label, modify in [
        ('unknown', lambda s: s.update(unknown=True)),
        ('model_role', lambda s: s['models'].pop('naf')),
        ('zero_std', lambda s: s['options']['shape_norm'][1].__setitem__(0, 0)),
        ('bad_sampler', lambda s: s['options']['samplers'][0].__setitem__(0, True)),
        ('resolution', lambda s: s['options'].__setitem__('resolution', 512)),
    ]:
        changed = copy.deepcopy(spec)
        modify(changed)
        path = root / ('bad-' + label + '.json')
        write_json(path, changed)
        rejected(label, lambda: load_spec(path, allowed, binary_root), '' )
    # Tampered arrays cannot reach the native process or create output.
    modified = root / 'modified'
    shutil.copytree(prepared, modified)
    with (modified / 'inputs/rgb_low.npy').open('r+b') as stream:
        stream.seek(-1, 2)
        stream.write(b'\xff')
    failed = execute('modified-input', common('generate', root / 'bad-output') + ['--prepared', str(modified),
        '--prepared-sha256', file_sha256(modified / 'ready.json'), '--backend', 'cpu'], 1)
    assert 'identity changed' in failed.stdout and not (root / 'bad-output').exists()
    negatives.append({'case': 'modified_input', 'output_retained': False})
    # Production native entry rejects evaluation-only knobs and unsafe NPY
    # headers before any graph starts; use real native processes, CPU only.
    native_args = [str(args.binary), 'generate', *[p for role in ROLES for p in ('--' + role, spec['models'][role]['path'])],
        '--source-kind', 'synthetic', '--input', str(prepared / 'inputs'), '--output', str(root / 'native-negative'),
        '--backend', 'cpu', '--precision', 'float32', '--source-sha', file_sha256(descriptor),
        '--input-sha', file_sha256(prepared / 'ready.json'), '--seed', '42']
    for key in ('resolution', 'max_tokens', 'naf_lr', 'naf_hr', 'naf_texture', 'texture_size', 'target_faces', 'decoder_chunk', 'max_voxels', 'max_triangles'):
        native_args += ['--' + key.replace('_', '-'), str(spec['options'][key])]
    for label, changes in [('fault', ['--fault', 'cancel_before']), ('noise', ['--native-noise', 'true']), ('duplicate_seed', ['--seed', '42'])]:
        failed = execute('native-' + label, native_args + changes, 1)
        assert 'stage=' not in failed.stdout and not (root / 'native-negative').exists()
        negatives.append({'case': 'native_' + label, 'error': failed.stderr.strip()})
    malformed = root / 'malformed'
    shutil.copytree(prepared / 'inputs', malformed)
    for label, header in [('huge_shape', b"{'descr': '<f4', 'fortran_order': False, 'shape': (999999999999999999,), }\n"),
                          ('negative_shape', b"{'descr': '<f4', 'fortran_order': False, 'shape': (-1,), }\n"),
                          ('object_dtype', b"{'descr': '|O', 'fortran_order': False, 'shape': (3,), }\n")]:
        (malformed / 'rgb_low.npy').write_bytes(b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header)
        command = [str(malformed) if value == str(prepared / 'inputs') else value for value in native_args]
        failed = execute('native-' + label, command, 1)
        assert 'stage=' not in failed.stdout and not (root / 'native-negative').exists()
        negatives.append({'case': label, 'error': failed.stderr.strip()})
    old_hash = file_sha256(root / 'connected/complete.json')
    failed = execute('existing-output', common('generate', root / 'connected') + ['--prepared', str(prepared),
        '--prepared-sha256', file_sha256(prepared / 'ready.json'), '--backend', 'cpu'], 1)
    assert file_sha256(root / 'connected/complete.json') == old_hash
    negatives.append({'case': 'existing_output', 'preserved': True})
    # Actual SIGTERM while CPU background inference is live; no partial ready.
    cancelled_output = root / 'cancelled-prepare'
    command = common('prepare', cancelled_output) + ['--input', str(args.background_fixtures / 'opaque.png'), '--seed', '42']
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    captured = bytearray()
    try:
        assert child.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 60
            observed = False
            while child.poll() is None and time.monotonic() < deadline:
                for key, _ in selector.select(.1):
                    captured.extend(os.read(key.fileobj.fileno(), 8192))
                    observed = b'background_encoder_layer_0_block_0' in captured
                if observed:
                    break
        assert observed
        start = time.monotonic()
        child.send_signal(signal.SIGTERM)
        tail, _ = child.communicate(timeout=15)
        captured.extend(tail)
        reap = time.monotonic() - start
        assert child.returncode == 1 and not cancelled_output.exists()
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        (root / 'cancelled-prepare.log').write_bytes(captured)
    paths = root / 'outputs.json'
    write_json(paths, outputs)
    code = 'import json,sys; from pathlib import Path; from mediaforge.glb import validate_glb; print(json.dumps({p:validate_glb(Path(p).read_bytes()) for p in json.loads(Path(sys.argv[1]).read_text())}))'
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / 'backend'))
    validation = subprocess.run([str(args.core_python), '-c', code, str(paths)], capture_output=True, text=True, env=env, timeout=120)
    (root / 'core.log').write_text(validation.stdout + validation.stderr)
    assert validation.returncode == 0, validation.stderr
    execute('blender', [str(args.blender), '--background', '--factory-startup', '--threads', '4', '--python',
        str(Path(__file__).with_name('check_surface_blender.py')), '--', str(paths), str(root / 'blender-report.json')])
    report = {'passed': True, 'times': times, 'seed_cases': seed_cases, 'negative_cases': negatives,
        'opaque_arrays_match_previous': True, 'baseline_glb_payload_exact': True, 'repeated_glb_payload_exact': True,
        'background_cancellation': {'exit': child.returncode, 'seconds_to_reap': reap, 'output_retained': False},
        'native': result['native'], 'outputs': outputs, 'blender': json.loads((root / 'blender-report.json').read_text()),
        'binary_sha256': file_sha256(args.binary), 'baseline_binary_sha256': file_sha256(args.baseline_binary),
        'source_kind': 'synthetic', 'backend': 'cpu', 'pretrained_weights': 'NOT USED',
        'not_tested': ['real Host lease/Vulkan', 'trained generation/quality', 'core Scene Jobs integration', 'installed adoption/Library']}
    write_json(root / 'report.json', report)
    print(json.dumps({'passed': True, 'glbs': len(outputs), 'negative_cases': len(negatives), 'prepare_seconds': times['prepare']}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
