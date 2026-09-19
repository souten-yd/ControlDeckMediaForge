#!/usr/bin/env python3
"""Bounded CPU capacity probe for projected NAF; synthetic parameters only.

Uses the full 256-channel NAF encoder architecture and a 1024x1024 target with
1024 value channels, but a 64x64 guide image. This is not full-image/full-model
or GPU memory acceptance. A constant spatial value field supplies an analytic
oracle independent of the encoder/attention scores.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from convert_flow import digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('naf-fixtures', 'binary', 'output-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('fresh output directory required')
    reference = json.loads((args.naf_fixtures / 'report.json').read_text())
    if not reference['passed'] or reference['pretrained_weights'] != 'NOT USED':
        parser.error('use passing synthetic NAF fixtures')
    available = int(re.search(r'MemAvailable:\s+(\d+)', Path('/proc/meminfo').read_text())[1]) * 1024
    if available < 12 * 1024**3:
        parser.error('capacity probe needs at least 12 GiB currently available RAM')
    import numpy as np

    args.output_dir.mkdir(parents=True)
    original = args.naf_fixtures / 'default_encoder'
    shutil.copytree(original / 'weights', args.output_dir / 'weights')
    shutil.copy2(original / 'weights.txt', args.output_dir / 'weights.txt')
    (args.output_dir / 'params.txt').write_text('256 4 4 2 9 128 64 64 1024 1024\n')
    rng = np.random.default_rng(4407)
    np.save(args.output_dir / 'rgb.npy', rng.random((3, 64, 64), dtype=np.float32))
    channels = np.linspace(-1, 1, 1024, dtype=np.float32)
    np.save(args.output_dir / 'low.npy', np.broadcast_to(channels, (64, 64, 1024)).copy())
    # 49,152 distinct coordinates in nontrivial order, with all eight corners.
    corners = np.array([x*4096+y*64+z for x in (0,63) for y in (0,63) for z in (0,63)])
    remaining = np.setdiff1d(np.arange(64**3), corners)
    indices = np.concatenate((corners, rng.choice(remaining, size=49152-8, replace=False)))
    rng.shuffle(indices)
    coords = np.column_stack((indices // 4096, (indices // 64) % 64, indices % 64)).astype(np.float32)
    np.save(args.output_dir / 'coordinates.npy', coords)
    command = ['prlimit', '--as=' + str(16 * 1024**3), '--', '/usr/bin/time', '-v',
               '-o', str(args.output_dir / 'time.txt'), str(args.binary.resolve()),
               str(args.output_dir.resolve()), 'cpu', '--projected-only', '--grid', '64']
    environment = {**os.environ, 'HIP_VISIBLE_DEVICES': '-1', 'ROCR_VISIBLE_DEVICES': '-1',
                   'CUDA_VISIBLE_DEVICES': '-1', 'HF_HUB_OFFLINE': '1'}
    start = time.monotonic()
    with (args.output_dir / 'native.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=environment, start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    seconds = time.monotonic() - start
    report = {'passed': False, 'returncode': process.returncode, 'timed_out': timed_out,
              'seconds': seconds, 'command': command, 'backend': 'cpu', 'pretrained_weights': 'NOT USED',
              'guide': [64, 64], 'target': [1024, 1024], 'encoder_channels': 256,
              'encoder_layers': 2, 'kernel': 9, 'value_channels': 1024, 'tokens': 49152,
              'available_ram_before_bytes': available, 'address_space_limit_bytes': 16 * 1024**3,
              'binary_sha256': digest(args.binary),
              'fixture_report_sha256': digest(args.naf_fixtures / 'report.json'),
              'input_sha256': {str(p.relative_to(args.output_dir)): digest(p)
                               for p in args.output_dir.rglob('*') if p.is_file() and p.suffix in ('.npy', '.txt') and p.name != 'time.txt' and not p.name.startswith('actual_')},
              'full_image_full_model_vulkan': 'NOT TESTED'}
    if process.returncode == 0:
        values = np.load(args.output_dir / 'actual_sparse.npy', mmap_mode='r').reshape(49152, 1024)
        maximum = 0.
        valid = True
        for offset in range(0, len(values), 512):
            tile = values[offset:offset+512]
            maximum = max(maximum, float(np.max(np.abs(tile-channels))))
            valid &= bool(np.isfinite(tile).all() and np.allclose(tile, channels, atol=5e-5, rtol=5e-5))
        stats = json.loads((args.output_dir / 'stats.json').read_text())
        rss = int(re.search(r'Maximum resident set size \(kbytes\):\s+(\d+)', (args.output_dir / 'time.txt').read_text())[1]) * 1024
        report.update(stats=stats, maximum_abs_error=maximum, peak_child_rss_bytes=rss,
                      output_sha256=digest(args.output_dir / 'actual_sparse.npy'))
        report['passed'] = valid and stats['output_bytes'] == 49152*1024*4 and stats['dense_output_bytes'] == 1024**3*4 and stats['attention_queries'] == 49152*4
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'input_sha256'}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
