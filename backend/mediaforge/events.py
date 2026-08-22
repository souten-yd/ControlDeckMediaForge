"""Job change fan-out for the embedded workspace.

The workspace used to poll one job per second from a single panel, so progress
disappeared whenever the user moved away from it. Job state changes are
published here instead, and the socket pushes them to whoever is watching.

Publishing must never affect job execution: the store calls this from whichever
thread owns the update, and every delivery failure is contained per subscriber.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .domain import Job
    from .models import ModelOperation

MAX_WATCHED_JOBS = 10
QUEUE_LIMIT = 64


class JobSubscription:
    """One workspace connection's view of the jobs it asked to watch."""

    def __init__(self, bus: "JobEventBus", loop: asyncio.AbstractEventLoop):
        self._bus = bus
        self._loop = loop
        self.queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=QUEUE_LIMIT)
        self.job_ids: set[str] = set()

    def watch(self, job_ids: list[str]) -> list[str]:
        for job_id in job_ids:
            if len(self.job_ids) >= MAX_WATCHED_JOBS:
                break
            self.job_ids.add(job_id)
        return sorted(self.job_ids)

    def unwatch(self, job_ids: list[str]) -> list[str]:
        self.job_ids.difference_update(job_ids)
        return sorted(self.job_ids)

    def wants(self, job: "Job") -> bool:
        return job.id in self.job_ids

    def deliver(self, job: "Job") -> None:
        """Called from the publishing thread; never raises into the caller."""
        try:
            self._loop.call_soon_threadsafe(self._offer, job)
        except RuntimeError:
            # The workspace loop is gone. The socket cleans itself up.
            pass

    def _offer(self, job: "Job") -> None:
        try:
            self.queue.put_nowait(job)
        except asyncio.QueueFull:
            # A slow reader must not stall the worker; the next event carries
            # the newer state anyway.
            pass

    def close(self) -> None:
        self._bus.remove(self)


class JobEventBus:
    def __init__(self) -> None:
        self._subscriptions: list[JobSubscription] = []

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> JobSubscription:
        subscription = JobSubscription(self, loop)
        self._subscriptions.append(subscription)
        return subscription

    def remove(self, subscription: JobSubscription) -> None:
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    def publish(self, job: "Job") -> None:
        for subscription in list(self._subscriptions):
            if not subscription.wants(job):
                continue
            try:
                subscription.deliver(job)
            except Exception:  # noqa: BLE001 - a broken subscriber never fails a job
                continue


class ModelOperationSubscription:
    def __init__(self, bus: "ModelOperationEventBus", loop: asyncio.AbstractEventLoop):
        self._bus = bus
        self._loop = loop
        self.queue: asyncio.Queue[ModelOperation] = asyncio.Queue(maxsize=QUEUE_LIMIT)
        self.operation_ids: set[str] = set()

    def watch(self, operation_ids: list[str]) -> list[str]:
        for operation_id in operation_ids:
            if len(self.operation_ids) >= MAX_WATCHED_JOBS:
                break
            self.operation_ids.add(operation_id)
        return sorted(self.operation_ids)

    def unwatch(self, operation_ids: list[str]) -> list[str]:
        self.operation_ids.difference_update(operation_ids)
        return sorted(self.operation_ids)

    def deliver(self, operation: "ModelOperation") -> None:
        try:
            self._loop.call_soon_threadsafe(self._offer, operation)
        except RuntimeError:
            pass

    def _offer(self, operation: "ModelOperation") -> None:
        try:
            self.queue.put_nowait(operation)
        except asyncio.QueueFull:
            pass

    def close(self) -> None:
        self._bus.remove(self)


class ModelOperationEventBus:
    def __init__(self) -> None:
        self._subscriptions: list[ModelOperationSubscription] = []

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> ModelOperationSubscription:
        subscription = ModelOperationSubscription(self, loop)
        self._subscriptions.append(subscription)
        return subscription

    def remove(self, subscription: ModelOperationSubscription) -> None:
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    def publish(self, operation: "ModelOperation") -> None:
        for subscription in list(self._subscriptions):
            if operation.id in subscription.operation_ids:
                try:
                    subscription.deliver(operation)
                except Exception:  # noqa: BLE001 - observation never fails installation
                    continue
