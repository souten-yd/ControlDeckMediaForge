from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
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
    # broker が割り当てた置き場所。"host" ならシステムRAMで走らせる。
    device_id: str | None = None
    # 貸してもらった枠。全常駐に足りなければ、その中で動く形へ切り替える。
    granted_bytes: int | None = None
    # 進捗の間隔と単調増加を見張る門。既定は job ごとに 1 つ。
    #
    # batch は N 件を 1 つの host job にぶら下げるが、host の制限（2Hz、単調
    # 増加）は host job に対して掛かる。件ごとに新しい門を作ると、前の件の
    # 最後の報告と次の件の最初の報告が同じ 0.5 秒に入り、429 で弾かれる
    # （実機の batch で 2 件目以降がこれで落ちた）。共有すれば同じ門が見る。
    progress_gate: ProgressGate | None = None
    # この job が、host job 全体のどこを占めるか。既定は「全部」。
    #
    # batch は N 件を 1 つの host job にぶら下げる。host 側の進捗は単調増加で
    # なければならず（ControlDeck: jobs/service.py の update_external）、件ごとに
    # 0 から測り直すと 2 件目の報告が 422 で弾かれる。件の位置と幅を持たせて、
    # 全体の 0→1 として報告する。1 件だけの依頼では offset 0 / span 1 になり、
    # 従来と同じ値になる。
    progress_offset: float = 0.0
    progress_span: float = 1.0
    identity_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class HostJobReporter:
    def __init__(self, client: ControlDeckHostClient, execution: HostExecution):
        self.client = client
        self.execution = execution
        self.gate = execution.progress_gate or ProgressGate()
        self._last_progress: tuple[str, float, str | None, str | None] | None = None

    def _scaled(self, progress: float) -> float:
        """この job の進捗を、host job 全体の中の位置へ写す。"""
        span = self.execution.progress_span
        if span >= 1.0 and self.execution.progress_offset <= 0.0:
            return progress
        return min(1.0, self.execution.progress_offset + progress * span)

    async def progress(
        self,
        phase: str,
        progress: float,
        *,
        wait_reason: str | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> bool:
        progress = self._scaled(progress)
        signature = (phase, progress, wait_reason, message)
        if not force and signature == self._last_progress:
            return False
        if force:
            delay = max(
                0.0,
                HOST_PROGRESS_INTERVAL_SEC - (time.monotonic() - self.gate.last_sent_at),
            )
            if delay:
                # Waking on the exact boundary can still measure a few
                # microseconds early on the next monotonic read. Keep the
                # forced terminal/attached update safely outside the gate.
                await asyncio.sleep(delay + 0.01)
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
        progress = self._scaled(progress)
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
