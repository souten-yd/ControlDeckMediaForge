from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

from .client import ControlDeckHostClient, HostIdentity


@dataclass
class ProgressGate:
    """Enforce the 2 Hz and monotonic progress boundary before host transport."""

    last_progress: float = 0.0
    last_sent_at: float = 0.0

    def accept(self, *, progress: float, phase: str, terminal: bool = False, now: float | None = None) -> bool:
        if not phase or progress < self.last_progress or not 0 <= progress <= 1:
            return False
        current = time.monotonic() if now is None else now
        if not terminal and current - self.last_sent_at < 0.5:
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

    async def progress(
        self,
        phase: str,
        progress: float,
        *,
        wait_reason: str | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> bool:
        if not force and not self.gate.accept(progress=progress, phase=phase):
            return False
        if force:
            self.gate.last_progress = max(self.gate.last_progress, progress)
            self.gate.last_sent_at = time.monotonic()
        payload: dict[str, Any] = {
            "phase": phase,
            "progress": {"completed": round(progress * 1000), "total": 1000},
        }
        if wait_reason:
            payload["wait_reason"] = wait_reason
        if message:
            payload["message"] = message
        await self.client.update_job(self.execution.identity, self.execution.host_job_id, payload)
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
        # The host records its receive time slightly after our send timestamp;
        # keep a small margin above the exact 2 Hz boundary.
        delay = max(0.0, 0.55 - (time.monotonic() - self.gate.last_sent_at))
        if delay:
            await asyncio.sleep(delay)
        if not await self.progress(phase, progress):
            raise ValueError("attached Host Job final progress was rejected by the local gate")
