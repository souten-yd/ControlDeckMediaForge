#!/usr/bin/env python3
"""Real CPU native child cancellation/timeout; no Host or GPU simulation."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from camera import file_sha256
from worker_entry import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--alpha-image', type=Path, required=True)
    parser.add_argument('--allowed-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True)
    previous = json.loads((args.fixtures / 'report.json').read_text())
    assert previous['passed'] and previous['backend'] == 'cpu' and previous['source_kind'] == 'synthetic'
    spec = copy.deepcopy(json.loads((args.fixtures / 'job.json').read_text()))
    spec['options']['samplers'][0][0] = 1000
    job = root / 'job.json'
    write_json(job, spec)
    binary_root = Path(spec['native']['path']).resolve().parent
    worker = Path(__file__).with_name('worker_entry.py')
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1')
    def command(mode: str, output: Path) -> list[str]:
        return [sys.executable, str(worker), mode, '--job', str(job), '--allowed-root', str(args.allowed_root),
                '--binary-root', str(binary_root), '--output', str(output)]
    prepared = root / 'prepared'
    run = subprocess.run(command('prepare', prepared) + ['--input', str(args.alpha_image), '--seed', '42'],
                         text=True, capture_output=True, timeout=120)
    (root / 'prepare.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stdout + run.stderr
    reports = []
    for label in ('cancel', 'timeout'):
        output = root / label
        argv = command('generate', output) + ['--prepared', str(prepared), '--prepared-sha256', file_sha256(prepared / 'ready.json'), '--backend', 'cpu']
        if label == 'timeout':
            argv += ['--timeout', '0.2']
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        pid = None
        observed = False
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and proc.poll() is None:
                child_file = Path(f'/proc/{proc.pid}/task/{proc.pid}/children')
                children = child_file.read_text().split() if child_file.exists() else []
                log = output / 'native.stdout.log'
                live_stage = log.exists() and b'stage=ss_flow' in log.read_bytes()
                if children and (label == 'timeout' or live_stage):
                    assert len(children) == 1
                    pid = int(children[0])
                    assert os.getpgid(pid) == proc.pid
                    observed = True
                    break
                time.sleep(.005)
            assert observed, 'native child/stage not observed'
            start = time.monotonic()
            if label == 'cancel':
                proc.send_signal(signal.SIGTERM)
            content, _ = proc.communicate(timeout=15)
            elapsed = time.monotonic() - start
            (root / (label + '.log')).write_bytes(content)
            assert proc.returncode == 1 and pid is not None and not Path(f'/proc/{pid}').exists()
            assert not output.exists()
            expected = b'cancelled' if label == 'cancel' else b'exceeded time bound'
            assert expected in content, content
            reports.append({'case': label, 'worker_exit': proc.returncode, 'native_pid': pid,
                'child_shared_worker_process_group': True, 'observed_stage': 'ss_flow' if label == 'cancel' else 'native_child',
                'seconds_after_observation': elapsed, 'child_reaped': True, 'output_retained': False})
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    write_json(root / 'report.json', {'passed': True, 'backend': 'cpu', 'source_kind': 'synthetic', 'cases': reports})
    print(json.dumps({'passed': True, 'cases': reports}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
