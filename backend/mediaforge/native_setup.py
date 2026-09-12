"""Bounded, read-only native setup discovery. Not an installation API."""
from __future__ import annotations

import asyncio
import json
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .config import REPOSITORY_ROOT

PROBE_SCRIPT = REPOSITORY_ROOT / "worker_packs/native_setup/probe.py"
PROBE_TIMEOUT_SEC = 8.0
MAX_PROBE_BYTES = 4096
T = TypeVar("T")
ProbeError = Literal[
    "native_setup_invalid_reply", "native_setup_packagekit_unavailable",
    "native_setup_authorization_unavailable", "native_setup_arguments_forbidden",
    "native_setup_root_forbidden", "native_setup_gi_unavailable", "native_setup_system_bus_unavailable",
    "native_setup_worker_unavailable", "native_setup_timed_out", "native_setup_output_limit",
    "native_setup_worker_failed",
]


class NativeSetupProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["media-forge.native-setup-probe@1"] = "media-forge.native-setup-probe@1"
    provider: Literal["packagekit"] = "packagekit"
    state: Literal["detected", "unavailable"] = "unavailable"
    error_code: ProbeError | None = None
    version: str | None = Field(default=None, pattern=r"^[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5}$")
    backend: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    local_deb_mime: bool = False
    locked: bool | None = None
    authorization: Literal["not_checked", "granted", "challenge", "denied", "unavailable"] = "not_checked"
    interactive_agent: Literal["not_checked"] = "not_checked"
    installation: Literal["not_implemented"] = "not_implemented"

    @model_validator(mode="after")
    def detected_requires_observations(self) -> NativeSetupProbe:
        if self.state == "detected" and (self.version is None or self.backend is None or self.locked is None):
            raise ValueError("detected provider requires observed properties")
        return self


async def _settle(task: asyncio.Task[T], *, reraise_cancel: bool = False) -> T:
    """Finish bounded child ownership/cleanup despite repeated caller cancellation."""
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            interrupted = True
            continue
    if interrupted and reraise_cancel:
        task.result()
        raise asyncio.CancelledError
    return task.result()


async def _reap(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass  # It exited between the returncode check and kill.
    async def drain_and_wait() -> None:
        # asyncio.wait() alone can deadlock when a killed child's PIPE transport
        # paused at its high-water mark. Discard buffered bytes without retaining
        # them, so pipe closure can be delivered before reaping the process.
        if process.stdout is not None:
            while await process.stdout.read(4096):
                pass
        await process.wait()

    await _settle(asyncio.create_task(drain_and_wait()), reraise_cancel=True)


async def probe_native_setup() -> NativeSetupProbe:
    """No package paths, subjects or commands are accepted from the caller.

    GI and synchronous D-Bus work stay in a short-lived non-root OS process.
    Do not run this automatically in health or a frequently polled status route.
    """
    creation = asyncio.create_task(asyncio.create_subprocess_exec(
        "/usr/bin/python3", "-I", str(PROBE_SCRIPT),
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, close_fds=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        limit=MAX_PROBE_BYTES,
    ))
    try:
        process = await asyncio.shield(creation)
    except asyncio.CancelledError:
        try:
            process = await _settle(creation)
        except OSError:
            pass
        else:
            await _reap(process)
        raise
    except OSError:
        return NativeSetupProbe(error_code="native_setup_worker_unavailable")

    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SEC):
            assert process.stdout is not None
            output = bytearray()
            while chunk := await process.stdout.read(1024):
                output.extend(chunk)
                if len(output) > MAX_PROBE_BYTES:
                    return NativeSetupProbe(error_code="native_setup_output_limit")
            if await process.wait() != 0:
                return NativeSetupProbe(error_code="native_setup_worker_failed")
            try:
                return NativeSetupProbe.model_validate_json(output)
            except (ValueError, ValidationError):
                return NativeSetupProbe(error_code="native_setup_invalid_reply")
    except TimeoutError:
        return NativeSetupProbe(error_code="native_setup_timed_out")
    finally:
        await _reap(process)


if __name__ == "__main__":
    # Developer diagnostic only; the end-user setup path must not require a CLI.
    print(json.dumps(asyncio.run(probe_native_setup()).model_dump(), separators=(",", ":")))
