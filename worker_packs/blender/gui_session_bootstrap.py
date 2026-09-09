"""Trusted Blender-side control loop for an isolated Media Forge GUI session."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import bpy
import gpu


MAX_COMMAND_BYTES = 16 * 1024
CONTROL_INTERVAL_SEC = 0.2
HEARTBEAT_INTERVAL_SEC = 2.0
AUTOSAVE_INTERVAL_SEC = 120.0


def _arguments() -> tuple[Path, Path, str]:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(args) != 6 or args[0] != "--scene" or args[2] != "--control" or args[4] != "--session-id":
        raise RuntimeError("GUI session bootstrap arguments differ")
    scene = Path(args[1]).resolve(strict=True)
    control = Path(args[3]).resolve(strict=True)
    session_id = args[5]
    if not scene.is_file() or not control.is_dir() or not session_id.startswith("blendersession_"):
        raise RuntimeError("GUI session bootstrap paths differ")
    return scene, control, session_id


SCENE, CONTROL, SESSION_ID = _arguments()
LAST_HEARTBEAT = 0.0
LAST_AUTOSAVE = time.monotonic()


def _atomic_json(name: str, value: dict) -> None:
    destination = CONTROL / name
    temporary = CONTROL / f".{name}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, destination)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _reply(request_id: str, *, ok: bool, result: dict | None = None, error: str | None = None) -> None:
    _atomic_json(
        f"response-{request_id}.json",
        {"schema_version": 1, "request_id": request_id, "ok": ok, "result": result, "error": error},
    )


def _save_snapshot() -> None:
    """Replace only a complete working snapshot; never commit a scene revision."""
    if SCENE.is_symlink() or not SCENE.is_file():
        raise RuntimeError("working snapshot is unavailable")
    with tempfile.TemporaryDirectory(prefix=".autosave-", dir=SCENE.parent) as staging:
        candidate = Path(staging) / "scene.blend"
        result = bpy.ops.wm.save_as_mainfile(
            filepath=str(candidate), check_existing=False, copy=True,
            relative_remap=False, compress=False,
        )
        if result != {"FINISHED"} or candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError("Blender did not finish the snapshot")
        with candidate.open("rb") as handle:
            if handle.read(7) != b"BLENDER":
                raise RuntimeError("Blender snapshot header differs")
            os.fsync(handle.fileno())
        candidate.chmod(0o600)
        os.replace(candidate, SCENE)
        directory = os.open(SCENE.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _autosave(now: float) -> None:
    global LAST_AUTOSAVE
    if now - LAST_AUTOSAVE < AUTOSAVE_INTERVAL_SEC:
        return
    # Both success and failure retry no faster than this interval. Blender may
    # defer timers while a modal operation is active, so this is a target, not SLA.
    LAST_AUTOSAVE = now
    try:
        _save_snapshot()
    except Exception:
        ok = False
    else:
        ok = True
    try:
        _atomic_json("autosave.json", {"schema_version": 1, "session_id": SESSION_ID, "ok": ok})
    except OSError:
        # A full disk may prevent even the failure report. Core detects stale
        # status; keep the timer alive so a later recovery can retry.
        print("Media Forge autosave status unavailable", file=sys.stderr, flush=True)


def _control_tick() -> float:
    global LAST_HEARTBEAT
    now = time.monotonic()
    if now - LAST_HEARTBEAT >= HEARTBEAT_INTERVAL_SEC:
        LAST_HEARTBEAT = now
        try:
            _atomic_json("heartbeat.json", {"schema_version": 1, "session_id": SESSION_ID, "monotonic": now})
        except OSError:
            print("Media Forge session heartbeat unavailable", file=sys.stderr, flush=True)
    command_path = CONTROL / "command.json"
    if not command_path.is_file() or command_path.is_symlink():
        _autosave(now)
        return CONTROL_INTERVAL_SEC
    processing = CONTROL / ".command.processing"
    try:
        if command_path.stat().st_size > MAX_COMMAND_BYTES:
            command_path.unlink()
            return CONTROL_INTERVAL_SEC
        os.replace(command_path, processing)
        value = json.loads(processing.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {"schema_version", "request_id", "action"}:
            raise ValueError("command fields differ")
        request_id = value["request_id"]
        if (
            value["schema_version"] != 1
            or not isinstance(request_id, str)
            or len(request_id) != 32
            or any(char not in "0123456789abcdef" for char in request_id)
        ):
            raise ValueError("command identity differs")
        if value["action"] == "save":
            _save_snapshot()
            _reply(request_id, ok=True, result={"size_bytes": SCENE.stat().st_size, "sha256": _hash(SCENE)})
        elif value["action"] == "ping":
            _reply(request_id, ok=True, result={"blender_version": bpy.app.version_string})
        else:
            _reply(request_id, ok=False, error="unsupported command")
    except Exception as exc:
        request_id = value.get("request_id") if isinstance(locals().get("value"), dict) else None
        if isinstance(request_id, str) and len(request_id) == 32:
            _reply(request_id, ok=False, error=str(exc)[:300])
    finally:
        processing.unlink(missing_ok=True)
    return CONTROL_INTERVAL_SEC


_atomic_json("bootstrap.json", {"schema_version": 1, "session_id": SESSION_ID, "stage": "opening"})
bpy.ops.wm.open_mainfile(filepath=str(SCENE), load_ui=False, use_scripts=False)
# The standard preference would use a separate temporary-file policy. Keep all
# recovery snapshots in this isolated working copy instead; do not save prefs.
bpy.context.preferences.filepaths.use_auto_save_temporary_files = False
LAST_AUTOSAVE = time.monotonic()
_atomic_json("bootstrap.json", {"schema_version": 1, "session_id": SESSION_ID, "stage": "opened"})
bpy.app.timers.register(_control_tick, first_interval=CONTROL_INTERVAL_SEC, persistent=True)
_atomic_json(
    "ready.json",
    {
        "schema_version": 1,
        "session_id": SESSION_ID,
        "blender_version": ".".join(str(value) for value in bpy.app.version[:3]),
        "background": bpy.app.background,
        "autoexec_disabled": not bpy.context.preferences.filepaths.use_scripts_auto_execute,
        "gpu_backend": gpu.platform.backend_type_get(),
        "gpu_renderer": gpu.platform.renderer_get(),
    },
)
(CONTROL / "bootstrap.json").unlink(missing_ok=True)
