"""Host authentication/control adapter for the existing Blender setup manager.

Credentials live only in owned tasks. The Store contains the owner/child/outbox,
not a second scheduler or bearer tokens. All Store calls stay off the loop.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time
from typing import TYPE_CHECKING, Any

from .blender_operation import BlenderRuntimeOperation, BlenderRuntimeOperationError
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity

if TYPE_CHECKING:
    from .blender_manager import BlenderRuntimeManager

logger = logging.getLogger("uvicorn.error")


@dataclass
class SetupExecution:
    owner: str
    identity: HostIdentity
    host_job_id: str
    completed_bytes: int = 0


class BlenderSetupHostControl:
    def __init__(self, manager: BlenderRuntimeManager, host: ControlDeckHostClient) -> None:
        self.manager = manager
        self.host = host
        self.executions: dict[str, SetupExecution] = {}
        self._admission = asyncio.Lock()
        self._reconciliations: dict[str, asyncio.Task[None]] = {}
        self.accepting = True
        self.poll_sec = 5.0
        self.refresh_margin_sec = 120

    @staticmethod
    def owner(identity: HostIdentity) -> str:
        return identity.actor_subject or identity.subject

    @staticmethod
    def validate_identity(identity: HostIdentity) -> None:
        owner = BlenderSetupHostControl.owner(identity).removeprefix("user:")
        if (identity.addon_id != "media-forge" or not identity.authorization
                or identity.expires_at <= time.time() or "jobs.write" not in identity.granted_capabilities
                or not owner.isascii() or not owner.isdecimal()):
            raise BlenderRuntimeOperationError("host_setup_unauthorized", "An active Host Jobs credential is required")

    @staticmethod
    def credential(value: dict[str, Any], parent: HostIdentity, subject: str) -> HostIdentity:
        token, expires = value.get("access_token"), value.get("expires_at")
        now = time.time()
        if (value.get("token_type") != "Bearer" or not isinstance(token, str)
                or not 1 <= len(token) <= 8192 or any(char.isspace() for char in token)
                or type(expires) is not int or not now < expires <= now + 630):
            raise HostApiError("invalid_host_response", "Host setup credential response is invalid")
        return HostIdentity(f"Bearer {token}", parent.addon_id, subject, expires,
                            parent.granted_capabilities, parent.actor_subject)

    def owns(self, operation_id: str) -> bool:
        return operation_id in self.executions

    async def request(
        self, action: str, identifier: str, identity: HostIdentity, *,
        confirmation_fingerprint: str = "", acknowledge_history: bool = False,
    ) -> BlenderRuntimeOperation:
        self.validate_identity(identity)
        if not self.accepting:
            raise BlenderRuntimeOperationError("host_setup_stopping", "Setup manager is stopping")
        owner = self.owner(identity)

        async def admit() -> BlenderRuntimeOperation:
            async with self._admission:
                self.validate_identity(identity)
                if action == "cancel":
                    result = await self.manager._runtime_io(self.manager.cancel, identifier, owner)
                    self.schedule_reconciliation(identity)
                    return result

                def prepare() -> BlenderRuntimeOperation:
                    with self.manager._admission_guard:
                        callbacks = {
                            "install": lambda: self.manager._prepare_install(owner),
                            "web_install": lambda: self.manager._prepare_web(owner),
                            "update": lambda: self.manager._prepare_update(owner),
                            "repair": lambda: self.manager._prepare_repair(identifier, owner),
                            "switch": lambda: self.manager._prepare_switch(identifier, owner),
                            "install_exact": lambda: self.manager._admit_exact(identifier, owner),
                            "remove": lambda: self.manager._admit_removal(
                                identifier, confirmation_fingerprint, acknowledge_history, owner),
                        }
                        if action not in callbacks:
                            raise BlenderRuntimeOperationError("invalid_blender_runtime_action", "Unknown setup action")
                        return callbacks[action]()

                operation = await self.manager._runtime_io(prepare)
                if self.owns(operation.id):
                    return operation
                journal = await self.manager._runtime_io(
                    self.manager.store.blender_runtime_host_journal, operation.id, owner)
                if journal["host_job_id"] is not None:
                    raise BlenderRuntimeOperationError("host_context_lost", "Setup requires a new authenticated attempt")
                try:
                    response = await self.host.create_or_attach_job(
                        identity, title=f"Media Forge Blender setup: {action}", detached=True)
                    job = response.get("job")
                    if (response.get("created") is not True or not isinstance(job, dict)
                            or not isinstance(job.get("id"), str)
                            or type(job.get("owner_user_id")) is not int
                            or job["owner_user_id"] != int(owner.removeprefix("user:"))
                            or job.get("kind") != "addon.runtime.media-forge"
                            or job.get("status") not in {"queued", "running"}):
                        raise HostApiError("invalid_host_response", "Host setup child response is invalid")
                    await self.manager._runtime_io(
                        self.manager.store.bind_blender_runtime_host_job, operation.id, owner, job["id"])
                    child = self.credential(response, identity, f"job:{job['id']}")
                    self.executions[operation.id] = SetupExecution(owner, child, job["id"])
                except Exception as exc:
                    await self.manager._runtime_io(self.manager._fail_sync, operation.id,
                        "host_setup_admission_failed", "Host setup admission failed; no runtime execution was started")
                    await self._flush(operation.id, owner, identity)
                    raise BlenderRuntimeOperationError("host_setup_admission_failed",
                        "Host setup admission failed; inspect the operation before retrying") from exc
                self.manager._spawn(operation.id)
                return operation

        task = asyncio.create_task(admit())
        self.manager._request_admissions.add(task)
        try:
            return await self.manager._await_owned(task)
        finally:
            self.manager._request_admissions.discard(task)

    async def _control(self, operation_id: str, execution: SetupExecution) -> None:
        while True:
            if execution.identity.expires_at <= time.time():
                raise HostApiError("host_context_lost", "Host setup credential expired")
            if execution.identity.expires_at - time.time() <= self.refresh_margin_sec:
                response = await self.host.refresh_job_credential(execution.identity, execution.host_job_id)
                execution.identity = self.credential(response, execution.identity, execution.identity.subject)
            control = await self.host.job_control(execution.identity, execution.host_job_id)
            if control.get("host_job_id") != execution.host_job_id or type(control.get("cancel_requested")) is not bool:
                raise HostApiError("invalid_host_response", "Host setup control response is invalid")
            if control.get("cancel_requested") is True or control.get("status") == "canceled":
                return
            if control.get("status") not in {"queued", "running"}:
                raise HostApiError("host_context_lost", "Host setup child is no longer active")
            if await self.manager._runtime_io(
                self.manager.store.blender_runtime_operation_cancel_requested, operation_id):
                return
            operation = await self.manager._runtime_io(self.manager.store.get_blender_runtime_operation, operation_id)
            if operation.state not in {"ready", "failed", "canceled"}:
                execution.completed_bytes = max(execution.completed_bytes, operation.bytes_done)
                await self.host.update_job(execution.identity, execution.host_job_id,
                    {"phase": operation.state.value, "message": "Blender setup is in progress",
                     "progress": {"completed": execution.completed_bytes,
                                  "total": max(1, operation.bytes_total, execution.completed_bytes)}})
            await asyncio.sleep(self.poll_sec)

    async def run(self, operation_id: str) -> None:
        execution = self.executions[operation_id]
        worker = asyncio.create_task(self.manager._run(operation_id))
        control = asyncio.create_task(self._control(operation_id, execution))
        lost = False
        try:
            done, _ = await asyncio.wait((worker, control), return_when=asyncio.FIRST_COMPLETED)
            if control in done:
                await control
            else:
                await worker
        except HostApiError as exc:
            # Never log the remote message, token, arbitrary error code or body.
            code = exc.code if exc.code in {
                "host_unreachable", "host_request_rejected", "host_context_lost",
                "invalid_host_response", "host_response_too_large",
            } else "unknown_host_error"
            status = exc.status_code if type(exc.status_code) is int else 0
            cause = type(exc.__cause__).__name__ if exc.__cause__ is not None else "none"
            if cause not in {
                "none", "ConnectError", "ConnectTimeout", "ReadError", "ReadTimeout",
                "WriteError", "WriteTimeout", "PoolTimeout", "RemoteProtocolError",
                "LocalProtocolError", "ProxyError",
            }:
                cause = "unknown"
            logger.warning("Blender setup %s control stopped: %s (HTTP %s; cause=%s)",
                           operation_id, code, status, cause)
            lost = True
        except asyncio.CancelledError:
            logger.info("Blender setup %s control task canceled", operation_id)
            lost = True
        except Exception as exc:
            logger.warning("Blender setup %s control failed (%s)", operation_id, type(exc).__name__)
            lost = True
        finally:
            async def finish() -> None:
                control.cancel()
                await asyncio.gather(control, return_exceptions=True)
                if not worker.done():
                    if lost:
                        await self.manager._runtime_io(
                            self.manager.store.abort_blender_runtime_host_operation, operation_id, execution.owner)
                    else:
                        await self.manager._runtime_io(
                            self.manager.store.request_blender_runtime_operation_cancel, operation_id)
                    worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
                operation = await self.manager._runtime_io(self.manager.store.get_blender_runtime_operation, operation_id)
                if operation.state not in {"ready", "failed", "canceled"}:
                    await self.manager._finish_canceled(operation)
                await self._flush(operation_id, execution.owner, execution.identity)

            try:
                await self.manager._await_owned(asyncio.create_task(finish()))
            finally:
                self.executions.pop(operation_id, None)

    async def _flush(self, operation_id: str, owner: str, identity: HostIdentity) -> None:
        journal = await self.manager._runtime_io(self.manager.store.blender_runtime_host_journal, operation_id, owner)
        if journal["sent"] or journal["terminal"] is None or identity.expires_at <= time.time():
            return
        try:
            receipt = await self.host.reconcile_job_terminal(identity, journal["host_job_id"], journal["terminal"])
            await self.manager._runtime_io(
                self.manager.store.reconcile_blender_runtime_terminal, operation_id, owner, receipt)
        except (HostApiError, ValueError) as exc:
            # Durable unsent intent remains visible to a fresh owner request.
            logger.warning("Blender setup %s terminal remains pending (%s)", operation_id, type(exc).__name__)
            return

    async def reconcile_pending(self, identity: HostIdentity) -> None:
        self.validate_identity(identity)
        owner = self.owner(identity)
        for operation_id in await self.manager._runtime_io(
                self.manager.store.pending_blender_runtime_host_terminals, owner):
            if not self.owns(operation_id):
                await self._flush(operation_id, owner, identity)

    def schedule_reconciliation(self, identity: HostIdentity) -> None:
        if not self.accepting:
            return
        owner = self.owner(identity)
        current = self._reconciliations.get(owner)
        if current is not None and not current.done():
            return

        async def reconcile() -> None:
            try:
                await self.reconcile_pending(identity)
            except (BlenderRuntimeOperationError, HostApiError):
                pass  # Remains pending until a valid authenticated request.

        task = asyncio.create_task(reconcile())
        self._reconciliations[owner] = task
        def completed(done: asyncio.Task[None]) -> None:
            if self._reconciliations.get(owner) is done:
                self._reconciliations.pop(owner, None)
        task.add_done_callback(completed)

    async def stop_reconciliation(self) -> None:
        tasks = list(self._reconciliations.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._reconciliations.clear()
