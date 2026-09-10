"""Private terminal reconciliation for owned ordinary media Jobs, not parents."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .store import Store

logger = logging.getLogger("uvicorn.error")


def terminal_owner(identity: HostIdentity) -> str:
    return (identity.actor_subject or identity.subject).removeprefix("user:")


class HostedJobTerminals:
    def __init__(self, store: Store, host: ControlDeckHostClient, active: Callable[[str], bool]) -> None:
        self.store, self.host, self.active = store, host, active
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.accepting = True

    def schedule(self, identity: HostIdentity) -> None:
        if (not self.accepting or identity.addon_id != "media-forge" or not identity.authorization
                or identity.expires_at <= time.time() or "jobs.write" not in identity.granted_capabilities):
            return
        owner = terminal_owner(identity)
        if owner in self.tasks and not self.tasks[owner].done():
            return
        self.tasks[owner] = asyncio.create_task(self.reconcile(identity), name="media-host-terminal-reconcile")
        def completed(task: asyncio.Task[None]) -> None:
            if self.tasks.get(owner) is task:
                self.tasks.pop(owner, None)
        self.tasks[owner].add_done_callback(completed)

    async def reconcile(self, identity: HostIdentity) -> None:
        if (identity.addon_id != "media-forge" or not identity.authorization
                or identity.expires_at <= time.time() or "jobs.write" not in identity.granted_capabilities):
            return
        owner = terminal_owner(identity)
        after = ""
        try:
            while identity.expires_at > time.time():
                identifiers = await asyncio.to_thread(self.store.pending_owned_job_terminals, owner, after)
                if not identifiers:
                    return
                for job_id in identifiers:
                    after = job_id
                    if self.active(job_id):
                        continue
                    record = await asyncio.to_thread(self.store.owned_job_terminal, job_id)
                    if not record or record["owner"] != owner or record["sent"] or record["receipt"] is not None:
                        continue
                    try:
                        receipt = await self.host.reconcile_job_terminal(identity, record["host_job_id"], record["payload"])
                    except HostApiError as exc:
                        logger.warning("Owned media terminal remains pending job=%s HTTP=%s", job_id, exc.status_code)
                        return
                    matched = receipt.get("terminal_matches")
                    if (receipt.get("host_job_id") != record["host_job_id"]
                            or receipt.get("status") not in {"succeeded", "failed", "canceled", "interrupted"}
                            or receipt.get("disposition") not in {"applied", "already_terminal"}
                            or type(matched) is not bool
                            or (receipt["disposition"] == "applied" and not matched)
                            or (matched and receipt["status"] != record["payload"]["status"])):
                        logger.warning("Invalid owned media terminal receipt job=%s", job_id)
                        return
                    receipt = {key: receipt[key] for key in ("host_job_id", "status", "disposition", "terminal_matches")}
                    await asyncio.to_thread(self.store.acknowledge_owned_job_terminal, job_id,
                                            record["payload"], sent=matched, receipt=receipt)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Owned media terminal reconciliation failed; persisted payload remains pending")

    async def stop(self) -> None:
        self.accepting = False
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
