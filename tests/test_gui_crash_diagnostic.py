"""The optional diagnostic must never signal an unverified process."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["owned", "foreign-runtime", "outside-cgroup", "ambiguous"])
def test_crash_diagnostic_pins_and_checks_only_owned_blender(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts/3ds_save_conflict_cleanup_installed_e2e.py"
    spec = importlib.util.spec_from_file_location("gui_crash_diagnostic", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = tmp_path / "feature/data"
    runtime = data.parent / "runtimes/blender/test-runtime"
    runtime.mkdir(parents=True)
    executable = runtime / "blender"
    executable.touch()
    if case == "foreign-runtime":
        executable = tmp_path / "foreign/blender"
        executable.parent.mkdir()
        executable.touch()
    proc = tmp_path / "proc"
    for pid in (123, 456):
        (proc / str(pid)).mkdir(parents=True)
        (proc / str(pid) / "exe").symlink_to(executable)
    group = tmp_path / "cgroup"
    group.mkdir()
    (group / "cgroup.procs").write_text("456\n" if case == "outside-cgroup" else "123\n")
    calls: list[tuple] = []
    monkeypatch.setattr(module, "DATA", data)
    monkeypatch.setattr(module, "Path", lambda p: proc / str(p).removeprefix("/proc/") if str(p).startswith("/proc/") else Path(p))
    monkeypatch.setattr(module.os, "pidfd_open", lambda pid: calls.append(("open", pid)) or 77)
    monkeypatch.setattr(module.os, "close", lambda fd: calls.append(("close", fd)))
    monkeypatch.setattr(module.signal, "pidfd_send_signal", lambda fd, sig: calls.append(("signal", fd, sig)))
    pids = [123, 456] if case == "ambiguous" else [123]
    if case == "owned":
        assert module.crash_owned_blender(group, pids, "test-runtime") == 123
        assert calls == [("open", 123), ("signal", 77, module.signal.SIGKILL), ("close", 77)]
    else:
        with pytest.raises(AssertionError):
            module.crash_owned_blender(group, pids, "test-runtime")
        assert not any(call[0] == "signal" for call in calls)
        assert calls == ([] if case == "ambiguous" else [("open", 123), ("close", 77)])
