#!/usr/bin/env python3
"""CPU regression: a valid 1024 offset shell reaches bounded simplification.

Runs the real upstream remesher, then deliberately cancels before QEM/UV export.
This does not evaluate a trained model, GPU, final GLB or runtime adoption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--baseline-binary', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    import numpy as np

    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = root / 'input'
    source.mkdir()
    vertices = np.array([[-1,-1,-1], [1,-1,-1], [1,1,-1], [-1,1,-1],
                         [-1,-1,1], [1,-1,1], [1,1,1], [-1,1,1]], dtype='<f4') * .49
    faces = [[0,2,1], [0,3,2], [4,5,6], [4,6,7], [0,1,5], [0,5,4],
             [1,2,6], [1,6,5], [2,3,7], [2,7,6], [3,0,4], [3,4,7]]
    for name, value in {'vertices': vertices, 'faces': faces, 'coords': [[512,512,512]],
                        'pbr': [[.5,.5,.5,0,.7,1]], 'settings': [1024,32,1000,1,42]}.items():
        np.save(source / (name + '.npy'), np.asarray(value, dtype='<f4'), allow_pickle=False)
    reports = []
    candidates = [('fixed', args.binary)]
    if args.baseline_binary:
        candidates.insert(0, ('baseline', args.baseline_binary))
    for label, candidate in candidates:
        binary = candidate.resolve(strict=True)
        output = root / label
        command = ['prlimit', '--as=12884901888', '--core=0', '--', str(binary),
                   str(source), str(output), 'webp', 'synthetic', '0'*64, '0'*64,
                   '--fault', 'cancel_simplify']
        started = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        elapsed = time.monotonic() - started
        (root / (label + '.stdout.log')).write_text(result.stdout)
        (root / (label + '.stderr.log')).write_text(result.stderr)
        # Independent observed remesher output, before the MediaForge bound.
        shell = 'V=12024064 F=24048120' in result.stdout
        simplified = 'stage=simplify' in result.stdout
        expected = ('surface export cancelled at simplify' if label == 'fixed'
                    else 'invalid surface mesh dimensions')
        passed = (result.returncode == 1 and shell and expected in result.stderr
                  and simplified == (label == 'fixed') and not output.exists())
        reports.append({'label': label, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                        'exit_code': result.returncode, 'elapsed_sec': elapsed,
                        'reached_simplify': simplified, 'passed': passed})
    report = {'gpu_executed': False, 'glb_published': False, 'cases': reports,
              'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.iterdir())},
              'passed': all(item['passed'] for item in reports)}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
