from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

from .client import ControlDeckHostClient, HostIdentity

HOST_PROGRESS_INTERVAL_SEC = 0.65


@dataclass
class ProgressGate:
    """Enforce the 2 Hz and monotonic progress boundary before host transport."""

    last_progress: float = 0.0
    last_sent_at: float = 0.0

    def accept(self, *, progress: float, phase: str, terminal: bool = False, now: float | None = None) -> bool:
        if not phase or progress < self.last_progress or not 0 <= progress <= 1:
            return False
        current = time.monotonic() if now is None else now
        # The Host measures the interval after request parsing.  A request that
        # took a few milliseconds longer than its successor could otherwise
        # arrive inside the Host's exact 0.5 second boundary even though this
        # client started both calls 0.5 seconds apart.
        if not terminal and current - self.last_sent_at < HOST_PROGRESS_INTERVAL_SEC:
            return False
        self.last_progress = progress
        self.last_sent_at = current
        return True


class RemoteJobsBridge(Protocol):
    async def register(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def update(self, host_job_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class HostExecution:
    identity: HostIdentity
    host_job_id: str
    workload_class: str
    owns_terminal: bool
    request_id: str | None = None
    lease_id: str | None = None


class HostJobReporter:
    def __init__(self, client: ControlDeckHostClient, execution: HostExecution):
        self.client = client
        self.execution = execution
        self.gate = ProgressGate()
        self._last_progress: tuple[str, float, str | None, str | None] | None = None

    async def progress(
        self,
        phase: str,
        progress: float,
        *,
        wait_reason: str | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> bool:
        signature = (phase, progress, wait_reason, message)
        if not force and signature == self._last_progress:
            return False
        if force:
            delay = max(
                0.0,
                HOST_PROGRESS_INTERVAL_SEC - (time.monotonic() - self.gate.last_sent_at),
            )
            if delay:
                await asyncio.sleep(delay)
        if not self.gate.accept(progress=progress, phase=phase):
            return False
        payload: dict[str, Any] = {
            "phase": phase,
            "progress": {"completed": round(progress * 1000), "total": 1000},
        }
        if wait_reason:
            payload["wait_reason"] = wait_reason
        if message:
            payload["message"] = message
        await self.client.update_job(self.execution.identity, self.execution.host_job_id, payload)
        self._last_progress = signature
        return True

    async def terminal(
        self,
        status: str,
        *,
        phase: str,
        progress: float,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if not self.gate.accept(progress=progress, phase=phase, terminal=True):
            raise ValueError("terminal Host Job progress is not monotonic")
        payload: dict[str, Any] = {
            "phase": phase,
            "progress": {"completed": round(progress * 1000), "total": 1000},
            "status": status,
        }
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error[:2000]
        await self.client.update_job(self.execution.identity, self.execution.host_job_id, payload)

    async def finish_attached(self, *, phase: str, progress: float) -> None:
        # A final attached-job update may intentionally repeat the last waiting
        # phase/progress.  It still has to reach the Host, but only after the
        # same conservative interval used by every forced update.
        if not await self.progress(phase, progress, force=True):
            raise ValueError("attached Host Job final progress was rejected by the local gate")
