from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


RUNNER = Path(__file__).resolve().parents[1] / "worker_packs/blender/web_session_runner.py"


def runner_module():
    spec = importlib.util.spec_from_file_location("gui_runner_isolation", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(sys.platform != "linux", reason="GUI isolation targets Linux")
def test_kernel_policy_blocks_outside_reads_listing_writes_and_child_escape(tmp_path: Path) -> None:
    working = tmp_path / "working"
    working.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    canary = outside / "canary"
    canary.write_text("harmless canary", encoding="utf-8")
    (working / "escape").symlink_to(canary)
    readable = tmp_path / "bootstrap.py"
    readable.write_text("# trusted readable file", encoding="utf-8")
    code = r'''
import importlib.util, json, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("runner", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
working, outside, readable = map(Path, sys.argv[2:])
module.restrict_filesystem((working,), (readable,))
results = {}
for name, operation in (
    ("read", lambda: (outside / "canary").read_bytes()),
    ("list", lambda: list(outside.iterdir())),
    ("write", lambda: (outside / "new").write_bytes(b"no")),
    ("symlink", lambda: (working / "escape").read_bytes()),
):
    try:
        operation()
        results[name] = False
    except PermissionError:
        results[name] = True
assert readable.read_text() == "# trusted readable file"
(working / "saved").write_text("saved")
assert (working / "saved").read_text() == "saved"
child = os.fork()
if child == 0:
    try:
        (outside / "canary").read_bytes()
    except PermissionError:
        os._exit(0)
    os._exit(1)
results["child"] = os.waitpid(child, 0)[1] == 0
child = os.fork()
if child == 0:
    try:
        os.execv(sys.executable, [sys.executable, "-c", "pass"])
    except PermissionError:
        os._exit(0)
    os._exit(1)
results["execute"] = os.waitpid(child, 0)[1] == 0
print(json.dumps(results))
'''
    result = subprocess.run(
        [sys.executable, "-c", code, str(RUNNER), str(working), str(outside), str(readable)],
        capture_output=True, text=True, timeout=15, check=True,
    )
    assert json.loads(result.stdout) == {"read": True, "list": True, "write": True, "symlink": True, "child": True, "execute": True}
    assert canary.read_text() == "harmless canary" and not (outside / "new").exists()


def test_readable_dependencies_do_not_grant_runtime_parent_or_host_tree(tmp_path: Path, monkeypatch) -> None:
    runner = runner_module()
    monkeypatch.setattr(runner, "SYSTEM_READ_PATHS", ())
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "4.5").mkdir()
    (runtime / "lib").mkdir()
    files = {name: tmp_path / name for name in ("bootstrap_path", "preferences_path", "vulkan_icd")}
    files["blender_path"] = runtime / "blender"
    for path in files.values():
        path.write_text("fixture", encoding="utf-8")
    result = set(runner.readable_dependencies({**{key: str(path) for key, path in files.items()}, "runtime_version": "4.5.13"}))
    assert result == set(files.values()) | {runtime / "4.5", runtime / "lib"}
    assert runtime not in result and tmp_path not in result


def test_runtime_resource_symlink_escape_is_rejected(tmp_path: Path, monkeypatch) -> None:
    runner = runner_module()
    monkeypatch.setattr(runner, "SYSTEM_READ_PATHS", ())
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    blender = runtime / "blender"
    blender.write_text("fixture", encoding="utf-8")
    (runtime / "4.5").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeError, match="escapes its runtime"):
        runner.readable_dependencies({"blender_path": str(blender), "runtime_version": "4.5.13",
                                      "bootstrap_path": str(blender), "preferences_path": str(blender), "vulkan_icd": str(blender)})


def test_handled_rights_include_read_listing_and_execution() -> None:
    runner = runner_module()
    assert runner.LANDLOCK_ALL_ACCESS & 0b1111 == 0b1111
    assert not {"/", "/etc", "/proc", "/usr", "/data1tb", "/home"}.intersection(runner.SYSTEM_READ_PATHS)


@pytest.mark.skipif(sys.platform != "linux", reason="GUI isolation targets Linux")
def test_ipc_scope_denies_external_peers_but_preserves_children_and_rename(tmp_path: Path) -> None:
    program = r'''
import importlib.util,os,signal,socket,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('runner',sys.argv[1])
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
root=Path(sys.argv[2])
outside='\0mf-ipc-test-'+str(os.getpid())
server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
server.bind(outside)
server.listen(1)
received=[]
signal.signal(signal.SIGUSR1,lambda *_:received.append(True))
parent=os.getpid()
child=os.fork()
if child==0:
    runner.restrict_ipc()
    runner.restrict_filesystem((root,))
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        try:
            client.connect(outside)
        except PermissionError:
            pass
        else:
            os._exit(2)
    try:
        os.kill(parent,signal.SIGUSR1)
    except PermissionError:
        pass
    else:
        os._exit(3)
    inside='\0mf-inside-test-'+str(os.getpid())
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as local:
        local.bind(inside)
        local.listen(1)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.connect(inside)
    (root/'stage').mkdir()
    (root/'stage/file').write_text('saved')
    (root/'stage/file').rename(root/'saved')
    assert (root/'saved').read_text()=='saved'
    grandchild=os.fork()
    if grandchild==0:
        signal.pause()
        os._exit(4)
    os.kill(grandchild,signal.SIGTERM)
    assert os.waitpid(grandchild,0)[1]==signal.SIGTERM
    os._exit(0)
assert os.waitpid(child,0)[1]==0
assert not received
server.close()
print('IPC scope denied outside, allowed internal socket/signal and staged save')
'''
    result = subprocess.run([sys.executable, "-c", program, str(RUNNER), str(tmp_path)],
                            capture_output=True, text=True, timeout=15, check=True)
    assert "IPC scope denied outside" in result.stdout


def test_ipc_scope_fails_closed_without_required_abi(monkeypatch) -> None:
    runner = runner_module()

    class UnsupportedKernel:
        def syscall(self, *args: int) -> int:
            assert args == (444, 0, 0, 1)
            return 5

    monkeypatch.setattr(runner.ctypes, "CDLL", lambda *args, **kwargs: UnsupportedKernel())
    monkeypatch.setattr(runner.os, "uname", lambda: type("Platform", (), {"machine": "x86_64"})())
    with pytest.raises(RuntimeError, match="requires ABI 6"):
        runner.restrict_ipc()
