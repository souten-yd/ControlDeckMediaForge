#!/usr/bin/env python3
"""Stdlib-only owner for one Xvnc and Blender GUI process pair."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time


START_TIMEOUT_SEC = 60.0
STOP_TIMEOUT_SEC = 8.0
SESSION_PATTERN = re.compile(r"^blendersession_[0-9a-f]{32}$")
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1
LANDLOCK_ACCESS_FS_WRITE_FILE = 1 << 1
LANDLOCK_ACCESS_FS_REMOVE_DIR = 1 << 4
LANDLOCK_ACCESS_FS_REMOVE_FILE = 1 << 5
LANDLOCK_ACCESS_FS_MAKE_CHAR = 1 << 6
LANDLOCK_ACCESS_FS_MAKE_DIR = 1 << 7
LANDLOCK_ACCESS_FS_MAKE_REG = 1 << 8
LANDLOCK_ACCESS_FS_MAKE_SOCK = 1 << 9
LANDLOCK_ACCESS_FS_MAKE_FIFO = 1 << 10
LANDLOCK_ACCESS_FS_MAKE_BLOCK = 1 << 11
LANDLOCK_ACCESS_FS_MAKE_SYM = 1 << 12
LANDLOCK_ACCESS_FS_REFER = 1 << 13
LANDLOCK_ACCESS_FS_TRUNCATE = 1 << 14
LANDLOCK_WRITE_ACCESS = (
    LANDLOCK_ACCESS_FS_WRITE_FILE
    | LANDLOCK_ACCESS_FS_REMOVE_DIR
    | LANDLOCK_ACCESS_FS_REMOVE_FILE
    | LANDLOCK_ACCESS_FS_MAKE_CHAR
    | LANDLOCK_ACCESS_FS_MAKE_DIR
    | LANDLOCK_ACCESS_FS_MAKE_REG
    | LANDLOCK_ACCESS_FS_MAKE_SOCK
    | LANDLOCK_ACCESS_FS_MAKE_FIFO
    | LANDLOCK_ACCESS_FS_MAKE_BLOCK
    | LANDLOCK_ACCESS_FS_MAKE_SYM
    | LANDLOCK_ACCESS_FS_REFER
    | LANDLOCK_ACCESS_FS_TRUNCATE
)
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446
PR_SET_NO_NEW_PRIVS = 38


class LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class LandlockPathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


class BoundedDiagnostics:
    def __init__(self, process: subprocess.Popen[bytes], limit: int = 4096) -> None:
        self.process = process
        self.limit = limit
        self.value = bytearray()
        self.lock = threading.Lock()
        threading.Thread(target=self._drain, daemon=True).start()

    def _drain(self) -> None:
        assert self.process.stdout is not None
        while chunk := self.process.stdout.read(1024):
            with self.lock:
                self.value.extend(chunk)
                if len(self.value) > self.limit:
                    del self.value[:-self.limit]

    def text(self) -> str:
        with self.lock:
            return bytes(self.value).decode("utf-8", "replace").strip()[-1000:]


def restrict_filesystem(writable: tuple[Path, ...]) -> None:
    """Allow reads globally but writes only below explicitly opened directories."""
    if os.uname().machine != "x86_64":
        raise RuntimeError("Landlock filesystem isolation is unsupported on this architecture")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET, ctypes.c_void_p(), 0, LANDLOCK_CREATE_RULESET_VERSION
    )
    if abi < 3:
        raise RuntimeError("Landlock filesystem isolation is unavailable")
    ruleset_attr = LandlockRulesetAttr(handled_access_fs=LANDLOCK_WRITE_ACCESS)
    ruleset_fd = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.byref(ruleset_attr),
        ctypes.sizeof(ruleset_attr),
        0,
    )
    if ruleset_fd < 0:
        raise RuntimeError(f"Landlock ruleset creation failed: errno {ctypes.get_errno()}")
    try:
        for root in writable:
            descriptor = os.open(root, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = LandlockPathBeneathAttr(
                    allowed_access=LANDLOCK_WRITE_ACCESS, parent_fd=descriptor
                )
                if libc.syscall(
                    SYS_LANDLOCK_ADD_RULE,
                    ruleset_fd,
                    LANDLOCK_RULE_PATH_BENEATH,
                    ctypes.byref(rule),
                    0,
                ) < 0:
                    raise RuntimeError(f"Landlock path rule failed: errno {ctypes.get_errno()}")
            finally:
                os.close(descriptor)
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise RuntimeError(f"Landlock no-new-privileges failed: errno {ctypes.get_errno()}")
        if libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, ruleset_fd, 0) < 0:
            raise RuntimeError(f"Landlock restriction failed: errno {ctypes.get_errno()}")
    finally:
        os.close(ruleset_fd)


def atomic_json(root: Path, name: str, value: dict) -> None:
    path = root / name
    temporary = root / f".{name}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def validated_spec(path: Path) -> tuple[Path, dict]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024:
        raise RuntimeError("session specification is unavailable")
    path = path.resolve(strict=True)
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "session_id", "scene_path", "blender_path", "xvnc_path",
        "bootstrap_path", "preferences_path", "vulkan_icd", "rfb_socket", "geometry", "depth",
        "runtime_version",
    }
    if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != 1:
        raise RuntimeError("session specification fields differ")
    if not isinstance(value["session_id"], str) or not SESSION_PATTERN.fullmatch(value["session_id"]):
        raise RuntimeError("session identity differs")
    if value["geometry"] != "1280x720" or value["depth"] != 24:
        raise RuntimeError("session display bounds differ")
    if not isinstance(value["runtime_version"], str) or not re.fullmatch(
        r"[0-9]+(?:\.[0-9]+){1,3}", value["runtime_version"]
    ):
        raise RuntimeError("runtime version differs")
    root = path.parent
    for key in ("scene_path", "blender_path", "xvnc_path", "bootstrap_path", "preferences_path"):
        selected = Path(value[key])
        if not selected.is_absolute() or selected.is_symlink() or not selected.is_file():
            raise RuntimeError(f"{key} is unavailable")
        value[key] = str(selected.resolve(strict=True))
    icd = Path(value["vulkan_icd"])
    if icd.is_symlink() or not icd.is_absolute() or not icd.is_file() or icd.stat().st_size > 16 * 1024:
        raise RuntimeError("software Vulkan driver is unavailable")
    driver = json.loads(icd.read_text(encoding="utf-8"))
    driver = driver.get("ICD") if isinstance(driver, dict) else None
    library = driver.get("library_path") if isinstance(driver, dict) else None
    if not isinstance(library, str) or Path(library).name != "libvulkan_lvp.so":
        raise RuntimeError("software Vulkan driver differs")
    value["vulkan_icd"] = str(icd.resolve(strict=True))
    socket_path = Path(value["rfb_socket"])
    expected_socket_name = value["session_id"].removeprefix("blendersession_")[:16] + ".sock"
    if (
        not socket_path.is_absolute()
        or not socket_path.parent.is_dir()
        or socket_path.name != expected_socket_name
        or len(os.fsencode(socket_path)) >= 100
    ):
        raise RuntimeError("RFB socket path differs")
    value["rfb_socket"] = str(socket_path)
    return root, value


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=STOP_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=STOP_TIMEOUT_SEC)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: web_session_runner.py SPEC", file=sys.stderr)
        return 2
    root: Path | None = None
    socket_path: Path | None = None
    xvnc: subprocess.Popen | None = None
    blender: subprocess.Popen | None = None
    null_fd: int | None = None
    xvnc_diagnostics: BoundedDiagnostics | None = None
    blender_diagnostics: BoundedDiagnostics | None = None
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        root, spec = validated_spec(Path(argv[0]))
        socket_path = Path(spec["rfb_socket"])
        socket_path.unlink(missing_ok=True)
        environment = {
            "HOME": str(root / "home"),
            "XDG_CACHE_HOME": str(root / "home/cache"),
            "XDG_CONFIG_HOME": str(root / "home/config"),
            "XDG_DATA_HOME": str(root / "home/data"),
            "BLENDER_USER_CONFIG": str(root / "home/blender-config"),
            "BLENDER_USER_SCRIPTS": str(root / "home/blender-scripts"),
            "BLENDER_USER_DATAFILES": str(root / "home/blender-data"),
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONNOUSERSITE": "1",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "VK_DRIVER_FILES": spec["vulkan_icd"],
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
            "DISPLAY": ":99",
            "WAYLAND_DISPLAY": "",
        }
        (root / "home").mkdir(mode=0o700, exist_ok=True)
        x11_socket_root = Path("/tmp/.X11-unix")
        x11_socket_root.mkdir(mode=0o1777, exist_ok=True)
        null_fd = os.open("/dev/null", os.O_RDWR | os.O_CLOEXEC)
        xvnc = subprocess.Popen(
            [
                spec["xvnc_path"], ":99", "-geometry", spec["geometry"], "-depth", str(spec["depth"]),
                "-rendernode", "", "-rfbport", "-1",
                "-rfbunixpath", str(socket_path), "-rfbunixmode", "0600", "-SecurityTypes", "None",
                "-nolisten", "tcp", "-ac",
            ],
            cwd=root, env=environment, stdin=null_fd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        xvnc_diagnostics = BoundedDiagnostics(xvnc)
        deadline = time.monotonic() + START_TIMEOUT_SEC
        while time.monotonic() < deadline and not stopping:
            if xvnc.poll() is not None:
                detail = xvnc_diagnostics.text()
                raise RuntimeError(f"Xvnc exited during startup: {detail}" if detail else "Xvnc exited during startup")
            if socket_path.is_socket():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Xvnc startup timed out")
        # Xvnc is a pinned trusted component and needs its X server lock under
        # /tmp. Apply Landlock after it starts so the untrusted Blender scene
        # can write only its control, working-copy, and RFB-socket roots.
        restrict_filesystem((root, Path(spec["scene_path"]).parent, socket_path.parent))
        preference_setup = subprocess.run(
            [
                spec["blender_path"], "--background", "--factory-startup", "--disable-autoexec",
                "--python", spec["preferences_path"],
            ],
            cwd=root, env=environment, stdin=null_fd, stdout=null_fd,
            stderr=null_fd, timeout=15, check=False,
        )
        if preference_setup.returncode != 0:
            raise RuntimeError("Blender isolated preferences could not be initialized")
        blender = subprocess.Popen(
            [
                spec["blender_path"], "--disable-autoexec",
                "--gpu-backend", "vulkan", "--python",
                spec["bootstrap_path"], "--", "--scene", spec["scene_path"], "--control", str(root),
                "--session-id", spec["session_id"],
            ],
            cwd=root, env=environment, stdin=null_fd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        blender_diagnostics = BoundedDiagnostics(blender)
        ready = root / "ready.json"
        while time.monotonic() < deadline and not stopping:
            if blender.poll() is not None:
                detail = blender_diagnostics.text()
                raise RuntimeError(
                    f"Blender exited during startup: {detail}" if detail else "Blender exited during startup"
                )
            if ready.is_file() and socket_path.is_socket():
                atomic_json(root, "runner.json", {
                    "schema_version": 1, "session_id": spec["session_id"], "state": "ready",
                    "xvnc_pid": xvnc.pid, "blender_pid": blender.pid,
                })
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Blender GUI startup timed out")
        while not stopping:
            if xvnc.poll() is not None or blender.poll() is not None:
                detail = blender_diagnostics.text() if blender.poll() is not None else xvnc_diagnostics.text()
                raise RuntimeError(f"Blender GUI process exited: {detail}" if detail else "Blender GUI process exited")
            time.sleep(0.25)
        return 0
    except Exception as exc:
        if root is not None:
            atomic_json(root, "runner.json", {
                "schema_version": 1, "state": "failed", "error": str(exc)[:300],
            })
        return 1
    finally:
        stop(blender)
        stop(xvnc)
        if socket_path is not None:
            socket_path.unlink(missing_ok=True)
        if null_fd is not None:
            os.close(null_fd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
