"""Fault-injector boundaries; actual Blender/process acceptance is separate."""
import os
from pathlib import Path
import threading

import pytest

from scripts.blender_probe_fault import probe_matches, terminate_candidate_probe
import scripts.blender_probe_fault as injection


@pytest.mark.parametrize('changed', ['none', 'parent', 'executable', 'argv', 'missing'])
def test_probe_identity_is_exact(tmp_path: Path, changed: str) -> None:
    proc = tmp_path / 'proc'
    proc.mkdir()
    executable = tmp_path / 'blender'
    executable.write_bytes(b'fixture')
    (proc / 'exe').symlink_to(executable)
    (proc / 'status').write_text('Name:\tblender\nPPid:\t1234\n')
    argv = [str(executable), '--background']
    (proc / 'cmdline').write_bytes(b'\0'.join(os.fsencode(v) for v in argv) + b'\0')
    if changed == 'parent':
        (proc / 'status').write_text('PPid:\t5678\n')
    elif changed == 'executable':
        executable = tmp_path / 'other'
    elif changed == 'argv':
        argv.append('--unexpected')
    elif changed == 'missing':
        (proc / 'cmdline').unlink()
    assert probe_matches(proc, parent_pid=1234, executable=executable, argv=argv) == (changed == 'none')


def test_invalid_identity_never_opens_pidfd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> None:
        pytest.fail('must not open any process descriptor')
    monkeypatch.setattr(os, 'pidfd_open', forbidden)
    with pytest.raises(ValueError):
        terminate_candidate_probe(tmp_path, '../other', parent_pid=os.getpid(),
            script=Path(__file__).resolve(), version='4.5.13', stop=threading.Event())


def test_pre_canceled_injection_does_not_signal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stop = threading.Event()
    stop.set()
    def forbidden(*args: object) -> None:
        pytest.fail('must not open any process descriptor')
    monkeypatch.setattr(os, 'pidfd_open', forbidden)
    with pytest.raises(TimeoutError):
        terminate_candidate_probe(tmp_path, 'blenderop_' + 'a' * 32, parent_pid=os.getpid(),
            script=Path(__file__).resolve(), version='4.5.13', stop=stop)


@pytest.mark.parametrize('still_matches', [True, False])
def test_descriptor_identity_rechecked_and_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, still_matches: bool) -> None:
    children = tmp_path / 'children'
    children.write_text('1234')
    monkeypatch.setattr(Path, 'glob', lambda *_: iter([children]))
    stop = threading.Event()
    checks = 0
    def matches(*args: object, **kwargs: object) -> bool:
        nonlocal checks
        checks += 1
        if checks == 2:
            if not still_matches:
                stop.set()
            return still_matches
        return True
    monkeypatch.setattr(injection, 'probe_matches', matches)
    monkeypatch.setattr(os, 'pidfd_open', lambda pid: 999999 if pid == 1234 else pytest.fail('wrong PID'))
    closed: list[int] = []
    sent: list[tuple[int, int]] = []
    original_close = os.close
    monkeypatch.setattr(os, 'close', lambda fd: closed.append(fd) if fd == 999999 else original_close(fd))
    monkeypatch.setattr(injection.signal, 'pidfd_send_signal', lambda fd, sig: sent.append((fd, sig)))
    args = (tmp_path, 'blenderop_' + 'b' * 32)
    kwargs = dict(parent_pid=os.getpid(), script=Path(__file__).resolve(), version='4.5.13', stop=stop)
    if still_matches:
        assert terminate_candidate_probe(*args, **kwargs)['pid'] == 1234
        assert sent == [(999999, injection.signal.SIGTERM)]
    else:
        with pytest.raises(TimeoutError):
            terminate_candidate_probe(*args, **kwargs)
        assert not sent
    assert checks == 2 and closed == [999999]
