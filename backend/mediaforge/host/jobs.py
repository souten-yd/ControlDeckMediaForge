from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol


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
