from __future__ import annotations

import errno
import fcntl
import io
import mmap
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

from worker_packs.native_setup import sealed_input

ROOT = Path(__file__).resolve().parents[1]


def test_kernel_seals_deny_write_resize_and_shared_writable_map() -> None:
    with sealed_input.hold_immutable_input(b"native fixture") as held:
        fd = held.descriptor
        assert fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
        assert fcntl.fcntl(fd, fcntl.F_GET_SEALS) == sealed_input.SEALS
        assert Path(held.proc_path).read_bytes() == b"native fixture"
        for change in [lambda: os.write(fd, b"X"), lambda: os.ftruncate(fd, 1),
                       lambda: os.ftruncate(fd, 99), lambda: mmap.mmap(fd, 14, access=mmap.ACCESS_WRITE)]:
            with pytest.raises(OSError) as error:
                change()
            assert error.value.errno in (errno.EPERM, errno.EACCES)
        assert os.pread(fd, 14, 0) == b"native fixture"
    with pytest.raises(OSError) as error:
        os.fstat(fd)
    assert error.value.errno == errno.EBADF


def test_real_os_python_can_consume_sealed_zipapp_and_import_its_module() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("__main__.py", "from payload import VALUE\nprint(VALUE)\n")
        archive.writestr("payload.py", "VALUE = 'SEALED_NATIVE_ZIPAPP_OK'\n")
    with sealed_input.hold_immutable_input(stream.getvalue()) as held:
        result = subprocess.run(["/usr/bin/python3", "-I", held.proc_path],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10, close_fds=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "SEALED_NATIVE_ZIPAPP_OK\n"


def test_actual_policy_verifier_runs_from_sealed_zipapp_without_core_crypto() -> None:
    stream = io.BytesIO()
    bootstrap = '''
import hashlib
import policy_release as policy
manifest = {"schema_version": policy.SCHEMA, "feature_id": "media-forge",
"purpose": policy.PURPOSE, "version": "0.28.80", "source_commit": "a"*40,
"platform": "linux", "architecture": "x86_64",
"artifact_name": "control-deck-media-forge-os-policy-0.28.80-linux-x86_64.deb",
"sha256": hashlib.sha256(b"fixture").hexdigest(), "size_bytes": 7}
try:
    policy.verify_policy_release(policy.canonical_bytes(manifest), b"0"*64, b"fixture",
        expected_version="0.28.80", expected_source_commit="a"*40)
except policy.PolicyReleaseError as error:
    assert str(error) == "native_policy_signature_invalid"
else:
    raise AssertionError("untrusted fixture accepted")
print("NATIVE_VERIFIER_REJECTED_UNTRUSTED_FIXTURE")
'''
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("__main__.py", bootstrap)
        archive.writestr("policy_release.py",
            (ROOT / "worker_packs/native_setup/policy_release.py").read_bytes())
    with sealed_input.hold_immutable_input(stream.getvalue()) as held:
        result = subprocess.run(["/usr/bin/python3", "-I", held.proc_path],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, close_fds=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "NATIVE_VERIFIER_REJECTED_UNTRUSTED_FIXTURE\n"


@pytest.mark.parametrize("data", [b"", bytearray(b"mutable"), "text", b"x" * (8 * 1024 * 1024 + 1)])
def test_bad_inputs_never_allocate(data: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> int:
        pytest.fail("invalid input allocated a descriptor")
    monkeypatch.setattr(sealed_input.os, "memfd_create", forbidden)
    with pytest.raises(ValueError):
        with sealed_input.hold_immutable_input(data):
            pytest.fail("invalid input accepted")


def test_short_writes_are_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    real_write = os.write
    monkeypatch.setattr(sealed_input.os, "write", lambda fd, data: real_write(fd, data[:2]))
    with sealed_input.hold_immutable_input(b"short writes") as held:
        assert Path(held.proc_path).read_bytes() == b"short writes"


@pytest.mark.parametrize("failure", ["write", "seal", "consumer"])
def test_errors_close_owned_descriptor(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[int] = []
    real_create = os.memfd_create
    real_fcntl = fcntl.fcntl
    def create(*args: object) -> int:
        fd = real_create(*args)
        created.append(fd)
        return fd
    def broken_fcntl(fd: int, command: int, *args: object) -> int:
        if command == fcntl.F_ADD_SEALS:
            raise OSError(errno.EPERM, "test seal refusal")
        return real_fcntl(fd, command, *args)
    monkeypatch.setattr(sealed_input.os, "memfd_create", create)
    if failure == "write":
        monkeypatch.setattr(sealed_input.os, "write", lambda *args: 0)
    if failure == "seal":
        monkeypatch.setattr(sealed_input.fcntl, "fcntl", broken_fcntl)
    with pytest.raises((OSError, RuntimeError)):
        with sealed_input.hold_immutable_input(b"fixture"):
            raise RuntimeError("test consumer failure")
    assert len(created) == 1
    with pytest.raises(OSError) as error:
        os.fstat(created[0])
    assert error.value.errno == errno.EBADF


def test_protected_worker_denies_peer_proc_access_but_allows_explicit_fd_transfer() -> None:
    # prctl affects only this short-lived OS worker, never pytest/core.
    script = '''
import errno, os, subprocess, sys
sys.path.insert(0, sys.argv[1])
from worker_packs.native_setup.sealed_input import hold_immutable_input, protect_native_holder
protect_native_holder()
with hold_immutable_input(b"isolated") as held:
    denied = subprocess.run([sys.executable, "-I", "-c", "import os,sys; os.open(sys.argv[1], os.O_RDONLY)", held.proc_path], capture_output=True, timeout=5)
    assert denied.returncode != 0 and b"PermissionError" in denied.stderr
    inherited = subprocess.run([sys.executable, "-I", "-c", "import os,sys; assert os.read(int(sys.argv[1]), 8)==b'isolated'", str(held.descriptor)], pass_fds=(held.descriptor,), capture_output=True, timeout=5)
    assert inherited.returncode == 0
print("PROTECTED_HOLDER_OK")
'''
    result = subprocess.run(["/usr/bin/python3", "-I", "-c", script, str(ROOT)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15, close_fds=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "PROTECTED_HOLDER_OK\n"
