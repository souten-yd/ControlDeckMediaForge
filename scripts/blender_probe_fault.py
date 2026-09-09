"""Acceptance-only fault injection for one exact, newly staged Blender probe.

Never import this module from production. PID descriptors bind the signal to
the process checked here, not a numeric PID that could have been reused.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import signal
import threading
import time


def probe_matches(proc: Path, *, parent_pid: int, executable: Path, argv: list[str]) -> bool:
    """Read-only identity check; missing/racing processes are not candidates."""
    try:
        if proc.stat().st_uid != os.getuid():
            return False
        status = dict(line.split(':', 1) for line in (proc / 'status').read_text().splitlines() if ':' in line)
        if int(status['PPid'].strip()) != parent_pid:
            return False
        if (proc / 'exe').resolve(strict=True) != executable:
            return False
        return (proc / 'cmdline').read_bytes().split(b'\0') == [os.fsencode(v) for v in argv] + [b'']
    except (OSError, KeyError, ValueError):
        return False


def terminate_candidate_probe(
    managed_root: Path, operation_id: str, *, parent_pid: int,
    script: Path, version: str, stop: threading.Event, timeout: float = 120,
) -> dict[str, int | str]:
    """Signal only the exact owned candidate, or time out without signalling."""
    if not re.fullmatch(r'blenderop_[0-9a-f]{32}', operation_id):
        raise ValueError('exact operation ID is required')
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or parent_pid <= 1 or not 0 < timeout <= 300:
        raise ValueError('exact version and parent process are required')
    if managed_root.resolve(strict=True) != managed_root or script.resolve(strict=True) != script:
        raise ValueError('symlinked roots/scripts are not allowed')
    executable = managed_root / '.staging' / operation_id / 'candidate/install/blender'
    argv = [str(executable), '--background', '--factory-startup', '--disable-autoexec',
            '--python', str(script), '--', '--expected-version', version]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not stop.is_set():
        # A subprocess launched by a worker thread appears in that thread's
        # children file, not necessarily the main thread's children file.
        children: set[int] = set()
        for entry in (Path('/proc') / str(parent_pid) / 'task').glob('*/children'):
            try:
                children.update(int(v) for v in entry.read_text().split())
            except (OSError, ValueError):
                continue
        for pid in sorted(children):
            proc = Path('/proc') / str(pid)
            if not probe_matches(proc, parent_pid=parent_pid, executable=executable, argv=argv):
                continue
            try:
                descriptor = os.pidfd_open(pid)
            except ProcessLookupError:
                continue
            try:
                if not probe_matches(proc, parent_pid=parent_pid, executable=executable, argv=argv) or stop.is_set():
                    continue
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                return {'pid': pid, 'parent_pid': parent_pid, 'operation_id': operation_id,
                        'executable': str(executable), 'signal': 'SIGTERM'}
            finally:
                os.close(descriptor)
        stop.wait(0.01)
    raise TimeoutError('exact owned candidate probe was not observed; no process was signalled')
