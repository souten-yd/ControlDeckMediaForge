"""Durable systemd-user owner for isolated software-rendered Blender GUI sessions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any, Callable
import uuid

from .blender_runtime import BlenderRuntimeResolver
from .blender_session_record import (
    ACTIVE_BLENDER_SESSION_STATES,
    BlenderSessionState,
    BlenderWebSession,
)
from .blender_web import BlenderWebPack
from .paths import contained
from .scene_workspace import SceneWorkspace
from .scenes import SceneError, validate_scene_owner
from .store import Store


START_TIMEOUT_SEC = 90.0
COMMAND_TIMEOUT_SEC = 30.0
UNIT_COMMAND_TIMEOUT_SEC = 15.0
MAX_UNIT_OUTPUT_BYTES = 64 * 1024
LAVAPIPE_ICD_CANDIDATES = (
    Path("/usr/share/vulkan/icd.d/lvp_icd.json"),
    Path("/etc/vulkan/icd.d/lvp_icd.json"),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class BlenderSessionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


async def _bounded_process(command: list[str], *, timeout: float) -> tuple[int, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as exc:
        raise BlenderSessionError("blender_session_runner_unavailable", "session controller is unavailable") from exc
    async def bounded_output() -> bytes:
        assert process.stdout is not None
        value = bytearray()
        while chunk := await process.stdout.read(4096):
            value.extend(chunk)
            if len(value) > MAX_UNIT_OUTPUT_BYTES:
                raise BlenderSessionError(
                    "blender_session_runner_output", "session controller output exceeded its bound"
                )
        return bytes(value)

    try:
        output, _ = await asyncio.wait_for(
            asyncio.gather(bounded_output(), process.wait()), timeout=timeout
        )
    except (TimeoutError, BlenderSessionError) as exc:
        process.kill()
        await process.wait()
        if isinstance(exc, BlenderSessionError):
            raise
        raise BlenderSessionError("blender_session_runner_timeout", "session controller timed out") from exc
    return process.returncode or 0, output.decode("utf-8", "replace")[:1000]


class SystemdUserSessionController:
    """Create a transient user service with no IP sockets and three writable roots."""

    async def start(
        self, unit_id: str, runner: Path, spec: Path, writable: tuple[Path, Path, Path]
    ) -> None:
        command = [
            "/usr/bin/systemd-run", "--user", "--quiet", "--collect", f"--unit={unit_id}",
            "--property=Type=exec", "--property=KillMode=control-group", "--property=TimeoutStopSec=15s",
            "--property=SendSIGKILL=yes", "--property=NoNewPrivileges=yes", "--property=PrivateTmp=yes",
            "--property=PrivateNetwork=yes", "--property=ProtectSystem=strict", "--property=ProtectHome=yes",
            "--property=RestrictAddressFamilies=AF_UNIX", "--property=RestrictSUIDSGID=yes",
            "--property=LockPersonality=yes", "--property=UMask=0077", "--property=TasksMax=128",
            "--property=MemoryMax=8G", f"--property=ReadWritePaths={writable[0]}",
            f"--property=ReadWritePaths={writable[1]}", f"--property=ReadWritePaths={writable[2]}",
            "/usr/bin/python3", str(runner), str(spec),
        ]
        code, output = await _bounded_process(command, timeout=UNIT_COMMAND_TIMEOUT_SEC)
        if code != 0:
            raise BlenderSessionError(
                "blender_session_runner_failed", f"isolated session unit did not start: {output.strip()}"
            )

    async def stop(self, unit_id: str) -> None:
        code, output = await _bounded_process(
            ["/usr/bin/systemctl", "--user", "stop", unit_id], timeout=UNIT_COMMAND_TIMEOUT_SEC
        )
        if code not in {0, 5} and "not loaded" not in output:
            raise BlenderSessionError("blender_session_stop_failed", "isolated session unit did not stop")

    async def active(self, unit_id: str) -> bool:
        code, _ = await _bounded_process(
            ["/usr/bin/systemctl", "--user", "is-active", "--quiet", unit_id],
            timeout=UNIT_COMMAND_TIMEOUT_SEC,
        )
        return code == 0


class BlenderSessionManager:
    def __init__(
        self,
        store: Store,
        scene_workspace: SceneWorkspace,
        resolver: BlenderRuntimeResolver,
        web_pack: BlenderWebPack,
        *,
        runner: Path,
        bootstrap: Path,
        preferences_bootstrap: Path,
        controller: SystemdUserSessionController | None = None,
        start_timeout_sec: float = START_TIMEOUT_SEC,
        command_timeout_sec: float = COMMAND_TIMEOUT_SEC,
        now: Callable[[], str] | None = None,
        socket_root: Path | None = None,
        software_vulkan_icd: Path | None = None,
    ) -> None:
        self.store = store
        self.scene_workspace = scene_workspace
        self.resolver = resolver
        self.web_pack = web_pack
        self.runner = Path(os.path.abspath(runner))
        self.bootstrap = Path(os.path.abspath(bootstrap))
        self.preferences_bootstrap = Path(os.path.abspath(preferences_bootstrap))
        self.root = contained(store.data_dir, store.data_dir / "sessions/blender")
        runtime_root = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        self.socket_root = (socket_root or runtime_root / "mediaforge-blender").resolve()
        self.controller = controller or SystemdUserSessionController()
        self.start_timeout_sec = start_timeout_sec
        self.command_timeout_sec = command_timeout_sec
        self._now = now or _now
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._gateway_sessions: set[str] = set()
        self._gateway_lock = asyncio.Lock()
        self.software_vulkan_icd = (
            Path(os.path.abspath(software_vulkan_icd)) if software_vulkan_icd is not None else None
        )

    async def start(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        active = self.store.list_active_blender_web_sessions()
        if active:
            self._ensure_socket_root()
        for owner, session in active:
            self._spawn(owner, session.id, resume=True)

    async def stop(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        async with self._gateway_lock:
            self._gateway_sessions.clear()

    def create(self, owner: str, scene_id: str) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        web_status = self.web_pack.status()
        if web_status.get("state") != "ready":
            raise BlenderSessionError("blender_web_runtime_unavailable", "browser-operation pack is unavailable")
        self._validate_lavapipe_icd(self.software_vulkan_icd)
        self._ensure_socket_root()
        if not isinstance(scene_id, str):
            raise BlenderSessionError("blender_session_invalid", "scene identity is invalid")
        # Owner and existence are checked transactionally again by Store.create.
        self.store.get_scene(scene_id, owner)
        session_id = f"blendersession_{uuid.uuid4().hex}"
        now = self._now()
        session = BlenderWebSession(
            id=session_id,
            scene_id=scene_id,
            web_pack_id=str(web_status["pack_id"]),
            web_pack_version=str(web_status["version"]),
            unit_id=f"mediaforge-blender-{session_id.removeprefix('blendersession_')}.service",
            state=BlenderSessionState.QUEUED,
            created_at=now,
            updated_at=now,
        )
        try:
            self.store.create_blender_web_session(owner, session)
        except SceneError as exc:
            raise BlenderSessionError(exc.code, str(exc)) from exc
        self._spawn(owner, session.id, resume=False)
        return self._projection(session)

    def list(self, owner: str) -> dict[str, Any]:
        return {"items": [self._projection(item) for item in self.store.list_blender_web_sessions(owner)]}

    def get(self, owner: str, session_id: str) -> dict[str, Any]:
        try:
            return self._projection(self.store.get_blender_web_session(owner, session_id))
        except SceneError as exc:
            raise BlenderSessionError(exc.code, str(exc)) from exc

    async def acquire_gateway(self, owner: str, session_id: str) -> Path:
        """Reserve the sole browser control channel and return its internal socket."""
        owner = validate_scene_owner(owner)
        try:
            session = self.store.get_blender_web_session(owner, session_id)
        except SceneError as exc:
            raise BlenderSessionError(exc.code, str(exc)) from exc
        if session.state != BlenderSessionState.READY:
            raise BlenderSessionError("blender_session_not_ready", "Blender session is not ready")
        async with self._gateway_lock:
            if session_id in self._gateway_sessions:
                raise BlenderSessionError(
                    "blender_session_already_connected", "Blender session already has a controller"
                )
            if not await self.controller.active(session.unit_id):
                raise BlenderSessionError(
                    "blender_session_runner_lost", "isolated session unit is no longer active"
                )
            # Re-read after the await so a concurrent save/stop cannot attach a stale session.
            current = self.store.get_blender_web_session(owner, session_id)
            socket_path = self._session_socket(session_id)
            if current.state != BlenderSessionState.READY or not self._is_socket(socket_path):
                raise BlenderSessionError("blender_session_not_ready", "Blender session is not ready")
            self._gateway_sessions.add(session_id)
            return socket_path

    async def release_gateway(self, session_id: str) -> None:
        async with self._gateway_lock:
            self._gateway_sessions.discard(session_id)

    def save_and_stop(self, owner: str, session_id: str) -> dict[str, Any]:
        return self._begin_finish(owner, session_id, save=True)

    def discard_and_stop(self, owner: str, session_id: str) -> dict[str, Any]:
        return self._begin_finish(owner, session_id, save=False)

    def _begin_finish(self, owner: str, session_id: str, *, save: bool) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        try:
            current = self.store.get_blender_web_session(owner, session_id)
        except SceneError as exc:
            raise BlenderSessionError(exc.code, str(exc)) from exc
        if save and current.state != BlenderSessionState.READY:
            raise BlenderSessionError("blender_session_not_ready", "Blender session is not ready")
        stoppable = {
            BlenderSessionState.QUEUED,
            BlenderSessionState.PREPARING,
            BlenderSessionState.STARTING,
            BlenderSessionState.READY,
        }
        if not save and current.state not in stoppable:
            raise BlenderSessionError("blender_session_not_active", "Blender session is not active")
        state = BlenderSessionState.SAVING if save else BlenderSessionState.STOPPING
        current = self._update(owner, current, state=state)
        existing = self._tasks.pop(session_id, None)
        if existing is not None:
            existing.cancel()
        task = asyncio.create_task(self._finish(owner, session_id, save=save), name=f"blender-finish-{session_id}")
        self._track(session_id, task)
        return self._projection(current)

    def _spawn(self, owner: str, session_id: str, *, resume: bool) -> None:
        if session_id in self._tasks:
            return
        task = asyncio.create_task(self._resume(owner, session_id) if resume else self._prepare(owner, session_id))
        self._track(session_id, task)

    def _track(self, session_id: str, task: asyncio.Task[None]) -> None:
        self._tasks[session_id] = task

        def finished(completed: asyncio.Task[None]) -> None:
            if self._tasks.get(session_id) is completed:
                self._tasks.pop(session_id, None)

        task.add_done_callback(finished)

    async def _prepare(self, owner: str, session_id: str) -> None:
        session = self.store.get_blender_web_session(owner, session_id)
        working_id: str | None = None
        try:
            session = self._update(owner, session, state=BlenderSessionState.PREPARING)
            working = self.scene_workspace.acquire_working_copy(owner, session.scene_id)
            working_id = working.id
            runtime = self.resolver.resolve_registered(working.runtime_id)
            if runtime is None or runtime.version != working.runtime_version:
                raise BlenderSessionError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
            session = self._update(
                owner, session, state=BlenderSessionState.STARTING, working_id=working.id,
                runtime_id=runtime.runtime_id, runtime_version=runtime.version,
            )
            scene_path = self.scene_workspace.working_path_for_runtime(owner, working.id)
            spec = self._write_spec(session, runtime.executable, scene_path)
            await self.controller.start(
                session.unit_id, self.runner, spec,
                (spec.parent, scene_path.parent, self.socket_root),
            )
            await self._await_ready(owner, session)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                await self.controller.stop(session.unit_id)
            except BlenderSessionError:
                pass
            await self._fail(owner, session_id, working_id, exc)

    async def _resume(self, owner: str, session_id: str) -> None:
        session = self.store.get_blender_web_session(owner, session_id)
        if session.state == BlenderSessionState.QUEUED and session.working_id is None:
            await self._prepare(owner, session_id)
            return
        if session.state in {BlenderSessionState.SAVING, BlenderSessionState.STOPPING}:
            await self.controller.stop(session.unit_id)
            await self._fail(
                owner, session.id, session.working_id,
                BlenderSessionError("blender_session_interrupted", "service restarted during session finalization"),
                interrupted=True,
            )
            return
        if not await self.controller.active(session.unit_id):
            await self._fail(
                owner, session.id, session.working_id,
                BlenderSessionError("blender_session_runner_lost", "isolated session unit is no longer active"),
                interrupted=True,
            )
            return
        if session.state in {BlenderSessionState.PREPARING, BlenderSessionState.STARTING}:
            await self._await_ready(owner, session)
            return
        await self._monitor(owner, session.id)

    async def _await_ready(self, owner: str, session: BlenderWebSession) -> None:
        root = self._session_root(session.id)
        ready_path = contained(root, root / "ready.json")
        socket_path = self._session_socket(session.id)
        deadline = asyncio.get_running_loop().time() + self.start_timeout_sec
        while asyncio.get_running_loop().time() < deadline:
            if not await self.controller.active(session.unit_id):
                raise BlenderSessionError("blender_session_runner_lost", "isolated session unit stopped during startup")
            if ready_path.is_file() and not ready_path.is_symlink() and self._is_socket(socket_path):
                value = self._read_json(ready_path, 64 * 1024)
                expected = {
                    "schema_version", "session_id", "blender_version", "background",
                    "autoexec_disabled", "gpu_backend", "gpu_renderer",
                }
                if (
                    not isinstance(value, dict)
                    or set(value) != expected
                    or value.get("schema_version") != 1
                    or value.get("session_id") != session.id
                    or value.get("blender_version") != session.runtime_version
                    or value.get("background") is not False
                    or value.get("autoexec_disabled") is not True
                    or value.get("gpu_backend") != "VULKAN"
                    or not isinstance(value.get("gpu_renderer"), str)
                    or "llvmpipe" not in value["gpu_renderer"].lower()
                ):
                    raise BlenderSessionError("blender_session_probe_failed", "Blender GUI identity differs")
                self._update(owner, session, state=BlenderSessionState.READY)
                await self._monitor(owner, session.id)
                return
            await asyncio.sleep(0.1)
        raise BlenderSessionError("blender_session_start_timeout", "Blender GUI startup timed out")

    async def _monitor(self, owner: str, session_id: str) -> None:
        while True:
            await asyncio.sleep(30)
            session = self.store.get_blender_web_session(owner, session_id)
            if session.state != BlenderSessionState.READY:
                return
            if not await self.controller.active(session.unit_id):
                await self._fail(
                    owner, session.id, session.working_id,
                    BlenderSessionError("blender_session_runner_lost", "isolated session unit stopped"),
                    interrupted=True,
                )
                return
            if session.working_id is not None:
                self.scene_workspace.renew_working_copy(owner, session.working_id)

    async def _finish(self, owner: str, session_id: str, *, save: bool) -> None:
        session = self.store.get_blender_web_session(owner, session_id)
        try:
            save_result = await self._command(session, "save") if save else None
            await self.controller.stop(session.unit_id)
            session = self._update(owner, session, state=BlenderSessionState.STOPPING)
            if save:
                if session.working_id is None:
                    raise BlenderSessionError("blender_session_invalid", "session working copy is unavailable")
                result = await self.scene_workspace.commit_working_copy(owner, session.working_id)
                result = {"saved": True, "scene": result, "working_file": save_result}
            else:
                if session.working_id is not None:
                    self.scene_workspace.release_working_copy(owner, session.working_id)
                result = {"saved": False}
            await asyncio.to_thread(self._remove_session_root, session.id)
            self._update(owner, session, state=BlenderSessionState.STOPPED, result=result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                await self.controller.stop(session.unit_id)
            finally:
                await self._fail(owner, session.id, session.working_id, exc)

    async def _command(self, session: BlenderWebSession, action: str) -> dict[str, Any]:
        root = self._session_root(session.id)
        command = contained(root, root / "command.json")
        if command.exists() or command.is_symlink() or (root / ".command.processing").exists():
            raise BlenderSessionError("blender_session_command_busy", "Blender session command is already active")
        request_id = uuid.uuid4().hex
        response = contained(root, root / f"response-{request_id}.json")
        self._atomic_json(command, {"schema_version": 1, "request_id": request_id, "action": action})
        deadline = asyncio.get_running_loop().time() + self.command_timeout_sec
        while asyncio.get_running_loop().time() < deadline:
            if response.is_file() and not response.is_symlink():
                value = self._read_json(response, 64 * 1024)
                response.unlink()
                if not isinstance(value, dict) or set(value) != {
                    "schema_version", "request_id", "ok", "result", "error"
                } or value.get("schema_version") != 1 or value.get("request_id") != request_id:
                    raise BlenderSessionError("blender_session_command_invalid", "Blender command response differs")
                if value.get("ok") is not True or not isinstance(value.get("result"), dict):
                    raise BlenderSessionError("blender_session_save_failed", "Blender could not save the working copy")
                return value["result"]
            if not await self.controller.active(session.unit_id):
                raise BlenderSessionError("blender_session_runner_lost", "isolated session unit stopped during save")
            await asyncio.sleep(0.1)
        raise BlenderSessionError("blender_session_save_timeout", "Blender save command timed out")

    async def _fail(
        self, owner: str, session_id: str, working_id: str | None, exc: Exception, *, interrupted: bool = False
    ) -> None:
        try:
            current = self.store.get_blender_web_session(owner, session_id)
            if current.state in ACTIVE_BLENDER_SESSION_STATES:
                self._update(
                    owner, current,
                    state=BlenderSessionState.INTERRUPTED if interrupted else BlenderSessionState.FAILED,
                    error_code=getattr(exc, "code", "blender_session_failed"),
                    error_message=str(exc)[:300],
                )
        finally:
            if working_id is not None:
                try:
                    self.scene_workspace.retain_working_copy_for_recovery(owner, working_id)
                except SceneError:
                    pass

    def _write_spec(self, session: BlenderWebSession, blender: Path, scene: Path) -> Path:
        trusted_files = (self.runner, self.bootstrap, self.preferences_bootstrap)
        if any(path.is_symlink() or not path.is_file() for path in trusted_files):
            raise BlenderSessionError("blender_session_runner_unavailable", "trusted GUI runner is unavailable")
        spec = self.web_pack.spec()
        pack = self.web_pack.destination(spec)
        xvnc = contained(pack, pack / "install/tigervnc/usr/bin/Xvnc")
        if xvnc.is_symlink() or not xvnc.is_file() or not os.access(xvnc, os.X_OK):
            raise BlenderSessionError("blender_web_runtime_unavailable", "Xvnc is unavailable")
        root = self._session_root(session.id)
        root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.exists() or root.is_symlink():
            raise BlenderSessionError("blender_session_root_unsafe", "session root already exists")
        root.mkdir(mode=0o700)
        software_vulkan_icd = self._validate_lavapipe_icd(self.software_vulkan_icd)
        value = {
            "schema_version": 1, "session_id": session.id, "scene_path": str(scene),
            "blender_path": str(blender), "xvnc_path": str(xvnc), "bootstrap_path": str(self.bootstrap),
            "preferences_path": str(self.preferences_bootstrap),
            "vulkan_icd": str(software_vulkan_icd),
            "rfb_socket": str(self._session_socket(session.id)), "geometry": "1280x720", "depth": 24,
            "runtime_version": session.runtime_version,
        }
        path = contained(root, root / "session.json")
        self._atomic_json(path, value)
        return path

    @staticmethod
    def _validate_lavapipe_icd(selected: Path | None) -> Path:
        candidates = (selected,) if selected is not None else LAVAPIPE_ICD_CANDIDATES
        for candidate in candidates:
            if candidate is None:
                continue
            path = Path(os.path.abspath(candidate))
            try:
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024:
                    continue
                value = json.loads(path.read_text(encoding="utf-8"))
                driver = value.get("ICD") if isinstance(value, dict) else None
                library = driver.get("library_path") if isinstance(driver, dict) else None
                if isinstance(library, str) and Path(library).name == "libvulkan_lvp.so":
                    return path
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
        raise BlenderSessionError(
            "blender_software_renderer_unavailable", "Mesa Lavapipe software renderer is unavailable"
        )

    def _update(self, owner: str, session: BlenderWebSession, **changes: Any) -> BlenderWebSession:
        value = session.model_copy(update={**changes, "updated_at": self._now()})
        return self.store.update_blender_web_session(owner, value)

    def _session_root(self, session_id: str) -> Path:
        if not session_id.startswith("blendersession_") or len(session_id) != 47:
            raise BlenderSessionError("blender_session_invalid", "session identity is invalid")
        return contained(self.root, self.root / session_id)

    def _session_socket(self, session_id: str) -> Path:
        if not session_id.startswith("blendersession_") or len(session_id) != 47:
            raise BlenderSessionError("blender_session_invalid", "session identity is invalid")
        filename = session_id.removeprefix("blendersession_")[:16] + ".sock"
        path = contained(self.socket_root, self.socket_root / filename)
        if len(os.fsencode(path)) >= 100:
            raise BlenderSessionError("blender_session_socket_path", "RFB socket root is too long")
        return path

    def _ensure_socket_root(self) -> None:
        if not self.socket_root.is_absolute() or self.socket_root.is_symlink():
            raise BlenderSessionError("blender_session_socket_path", "RFB socket root is unsafe")
        try:
            self.socket_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.socket_root.chmod(0o700)
        except OSError as exc:
            raise BlenderSessionError(
                "blender_session_socket_path", "RFB socket root is unavailable"
            ) from exc

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        os.replace(temporary, path)

    @staticmethod
    def _read_json(path: Path, limit: int) -> Any:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise BlenderSessionError("blender_session_probe_failed", "session control file is invalid")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderSessionError("blender_session_probe_failed", "session control file is invalid") from exc

    @staticmethod
    def _is_socket(path: Path) -> bool:
        try:
            return stat.S_ISSOCK(path.stat(follow_symlinks=False).st_mode)
        except (FileNotFoundError, OSError):
            return False

    def _remove_session_root(self, session_id: str) -> None:
        root = self._session_root(session_id)
        self._session_socket(session_id).unlink(missing_ok=True)
        if root.exists():
            if root.is_symlink():
                raise BlenderSessionError("blender_session_root_unsafe", "session root is unsafe")
            shutil.rmtree(root)

    def _projection(self, session: BlenderWebSession) -> dict[str, Any]:
        connected = session.id in self._gateway_sessions
        return {
            "schema_version": session.schema_version,
            "id": session.id,
            "scene_id": session.scene_id,
            "state": session.state,
            "runtime_id": session.runtime_id,
            "runtime_version": session.runtime_version,
            "web_pack_id": session.web_pack_id,
            "web_pack_version": session.web_pack_version,
            "display": {"mode": "software", "width": 1280, "height": 720, "depth": 24},
            "can_save": session.state == BlenderSessionState.READY,
            "connection_state": (
                "connected" if connected else
                "disconnected" if session.state == BlenderSessionState.READY else
                "unavailable"
            ),
            "can_connect": session.state == BlenderSessionState.READY and not connected,
            "can_stop": session.state in {
                BlenderSessionState.QUEUED,
                BlenderSessionState.PREPARING,
                BlenderSessionState.STARTING,
                BlenderSessionState.READY,
            },
            "error_code": session.error_code,
            "error_message": session.error_message,
            "result": session.result,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }
