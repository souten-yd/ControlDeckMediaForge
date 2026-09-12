"""Durable Host child-job orchestration for typed Blender scene recipes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from contextlib import ExitStack
from typing import Any

from .domain import ErrorDetail, Job, JobRequest, JobStatus
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.jobs import HostExecution, HostJobReporter
from .scene_recipes import (
    SceneCreateRequest,
    SceneEditRequest,
    SceneMaterialRequest,
    SceneTaskRecord,
)
from .scenes import SceneError
from .scene_workspace import SceneWorkspace
from .store import Store

logger = logging.getLogger(__name__)


async def _finish_cleanup(task: asyncio.Task[Any]) -> None:
    """Drain owned cleanup despite repeated caller cancellation; keep errors."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    task.result()


class SceneRecipeJobManager:
    """Own in-process execution while SQLite remains the source of job truth."""

    def __init__(
        self,
        store: Store,
        workspace: SceneWorkspace,
        host: ControlDeckHostClient,
        *,
        control_poll_sec: float = 1.0,
        credential_refresh_margin_sec: int = 120,
    ) -> None:
        self.store = store
        self.workspace = workspace
        self.host = host
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._admissions: set[asyncio.Task[tuple[Job, SceneTaskRecord]]] = set()
        self._executions: dict[str, HostExecution] = {}
        self._outbox_tasks: dict[str, asyncio.Task[None]] = {}
        self._outbox_guard = asyncio.Lock()
        self._execution_guard = asyncio.Semaphore(1)
        self.control_poll_sec = control_poll_sec
        self.credential_refresh_margin_sec = credential_refresh_margin_sec
        self._stopping = False

    async def start(self) -> None:
        self._stopping = False

    async def stop(self) -> None:
        self._stopping = True
        admissions = list(self._admissions)
        for task in admissions:
            task.cancel()
        await asyncio.gather(*admissions, return_exceptions=True)
        for job_id, task in list(self._tasks.items()):
            current = self.store.get_job(job_id)
            if current.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(
                        code="service_stopped", message="Service stopped while the scene recipe was active"
                    ),
                )
                self.store.update_scene_recipe_task(job_id, stage="service_stopped")
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._executions.clear()
        for task in self._outbox_tasks.values():
            task.cancel()
        await asyncio.gather(*self._outbox_tasks.values(), return_exceptions=True)
        self._outbox_tasks.clear()

    async def submit(
        self,
        value: SceneCreateRequest | SceneEditRequest | SceneMaterialRequest,
        identity: HostIdentity,
        *,
        retry_of: str | None = None,
    ) -> tuple[Job, SceneTaskRecord]:
        if self._stopping:
            raise SceneError("service_stopped", "Scene recipe admission is stopped")
        task = asyncio.create_task(self._submit(value, identity, retry_of=retry_of))
        self._admissions.add(task)
        try:
            return await task
        finally:
            self._admissions.discard(task)

    async def _submit(
        self,
        value: SceneCreateRequest | SceneEditRequest | SceneMaterialRequest,
        identity: HostIdentity,
        *,
        retry_of: str | None = None,
    ) -> tuple[Job, SceneTaskRecord]:
        missing = {"jobs.write"} - identity.granted_capabilities
        if missing:
            raise SceneError("host_capability_not_granted", "Host jobs.write capability is required")
        owner = identity.actor_subject or identity.subject
        external = value.model_dump(mode="json", exclude={"retry_job_id"})
        retry_pin: tuple[str, str, str | None] | None = None
        if retry_of is not None:
            previous = self.store.get_scene_recipe_task(retry_of, owner=owner)
            previous_job = self.store.get_job(retry_of)
            if previous_job.status not in {JobStatus.FAILED, JobStatus.CANCELED}:
                raise SceneError("scene_retry_invalid", "only a failed or canceled scene job can be retried")
            if external != previous.request:
                raise SceneError("scene_retry_changed", "a retry must preserve the original typed input")
            retry_pin = (previous.runtime_id, previous.runtime_version, previous.base_revision_id)
        operation = (
            "scene.create"
            if isinstance(value, SceneCreateRequest)
            else "scene.material"
            if isinstance(value, SceneMaterialRequest)
            else "scene.edit"
        )
        encoded = json.dumps(external, sort_keys=True, separators=(",", ":")).encode("utf-8")
        acquisition = asyncio.create_task(asyncio.to_thread(
            self.workspace.acquire_recipe_runtime, owner, value,
            **({"retry_pin": retry_pin} if retry_pin is not None else {}),
        ))
        try:
            references, pin = await asyncio.shield(acquisition)
        except asyncio.CancelledError:
            # A started thread must finish before its reference can be released.
            async def release_acquisition() -> None:
                references, _ = await acquisition
                await asyncio.to_thread(references.close)

            await _finish_cleanup(asyncio.create_task(release_acquisition()))
            raise
        try:
            return await self._submit_pinned(
                value, identity, owner, external, operation, encoded, retry_of, references, pin
            )
        except BaseException:
            await _finish_cleanup(asyncio.create_task(asyncio.to_thread(references.close)))
            raise

    async def _submit_pinned(
        self,
        value: SceneCreateRequest | SceneEditRequest | SceneMaterialRequest,
        identity: HostIdentity,
        owner: str,
        external: dict[str, Any],
        operation: str,
        encoded: bytes,
        retry_of: str | None,
        references: ExitStack,
        pin: tuple[str, str, str | None],
    ) -> tuple[Job, SceneTaskRecord]:
        runtime_id, runtime_version, base_revision_id = pin
        attached = await self.host.create_or_attach_job(
            identity, title="Media Forge 3D scene recipe", detached=True
        )
        host_job = attached.get("job")
        access_token = attached.get("access_token")
        expires_at = attached.get("expires_at")
        if (
            attached.get("created") is not True
            or not isinstance(host_job, dict)
            or not isinstance(host_job.get("id"), str)
            or not isinstance(access_token, str)
            or not access_token
            or not isinstance(expires_at, int)
            or expires_at <= int(time.time())
        ):
            raise SceneError("invalid_host_response", "Host child Job response is invalid")
        input_sha256 = hashlib.sha256(encoded).hexdigest()
        idempotency_key = hashlib.sha256(
            owner.encode("utf-8") + b"\0" + operation.encode("ascii") + b"\0" + encoded
        ).hexdigest()
        request = JobRequest(
            operation="media.inspect",
            intent=(
                f"Create typed Blender scene: {value.name}"
                if isinstance(value, SceneCreateRequest)
                else f"Apply a typed material binding to {value.scene_id}"
                if isinstance(value, SceneMaterialRequest)
                else f"Apply typed Blender scene edit to {value.scene_id}"
            ),
            constraints={"scene_operation": operation, "scene_recipe": external},
        )
        job = self.store.create_job(request, host_managed=True)
        record = self.store.create_scene_recipe_task(
            job.id,
            owner=owner,
            host_job_id=host_job["id"],
            operation=operation,
            runtime_id=runtime_id,
            runtime_version=runtime_version,
            base_revision_id=base_revision_id,
            input_sha256=input_sha256,
            idempotency_key=idempotency_key,
            request=external,
            retry_of=retry_of,
        )
        child_identity = HostIdentity(
            authorization=f"Bearer {access_token}",
            addon_id=identity.addon_id,
            subject=f"job:{host_job['id']}",
            expires_at=expires_at,
            granted_capabilities=identity.granted_capabilities,
            actor_subject=identity.actor_subject,
        )
        self._executions[job.id] = HostExecution(
            identity=child_identity,
            host_job_id=host_job["id"],
            workload_class="workflow",
            owns_terminal=attached.get("created") is True,
        )
        started = asyncio.Event()
        task = asyncio.create_task(
            self._run_pinned(job.id, value, references, started), name=f"scene-recipe-{job.id}"
        )
        task.add_done_callback(lambda completed: started.set())
        self._tasks[job.id] = task
        try:
            # Do not return a task that can be canceled before entering its finally.
            await started.wait()
            if task.cancelled():
                raise asyncio.CancelledError
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self._tasks.pop(job.id, None)
            self._executions.pop(job.id, None)
            raise
        return job, record

    async def _run_pinned(
        self,
        job_id: str,
        value: SceneCreateRequest | SceneEditRequest | SceneMaterialRequest,
        references: ExitStack,
        started: asyncio.Event,
    ) -> None:
        try:
            started.set()
            await self._run(job_id, value)
        finally:
            cleanup = asyncio.create_task(asyncio.to_thread(references.close))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await _finish_cleanup(cleanup)
                raise
            finally:
                self._tasks.pop(job_id, None)
                self._executions.pop(job_id, None)

    def creation_list(self, owner: str) -> dict[str, Any]:
        """Off-loop snapshot for the workspace, without exposing another actor."""
        items = []
        for job_id in self.store.list_scene_creation_job_ids(owner):
            task = self.store.get_scene_recipe_task(job_id, owner=owner)
            items.append({**self.projection(job_id, owner), "name": task.request.get("name", "")})
        return {"items": items}

    def projection(self, job_id: str, owner: str) -> dict[str, Any]:
        task = self.store.get_scene_recipe_task(job_id, owner=owner)
        job = self.store.get_job(job_id)
        return {
            "job_id": job.id,
            "status": job.status.value,
            "phase": job.phase,
            "progress": job.progress,
            "asset_ids": job.asset_ids,
            "error": job.error.model_dump(mode="json") if job.error else None,
            "stage": task.stage,
            "operation": task.operation,
            "runtime_id": task.runtime_id,
            "runtime_version": task.runtime_version,
            "base_revision_id": task.base_revision_id,
            "input_sha256": task.input_sha256,
            "idempotency_key": task.idempotency_key,
            "retry_of": task.retry_of,
            "result": task.result,
            "host_terminal_sent": task.host_terminal_sent,
            "host_terminal_reconciliation": task.host_terminal_reconciliation,
        }

    async def reconcile_terminal(self, job_id: str, identity: HostIdentity) -> None:
        self.store.get_scene_recipe_task(job_id, owner=identity.actor_subject or identity.subject)
        await self._consume_terminal(job_id, identity)

    async def _consume_terminal(self, job_id: str, identity: HostIdentity) -> None:
        if identity.expires_at <= int(time.time()) or "jobs.write" not in identity.granted_capabilities:
            return
        async with self._outbox_guard:
            task = self.store.get_scene_recipe_task(job_id)
            if (task.host_terminal_sent or task.host_terminal_reconciliation is not None
                    or task.host_terminal is None or job_id in self._tasks
                    or self.store.get_job(job_id).status not in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}):
                return
            payload = {key: task.host_terminal[key] for key in ("status", "result", "error") if key in task.host_terminal}
            try:
                receipt = await self.host.reconcile_job_terminal(identity, task.host_job_id, payload)
            except HostApiError as exc:
                # Persisted payload remains pending, including on an older Host.
                logger.warning("Terminal outbox pending for %s (Host HTTP %s)", job_id, exc.status_code)
                return
            if (receipt.get("host_job_id") != task.host_job_id
                    or receipt.get("status") not in {"succeeded", "failed", "canceled", "interrupted"}
                    or receipt.get("disposition") not in {"applied", "already_terminal"}
                    or type(receipt.get("terminal_matches")) is not bool
                    or (receipt["disposition"] == "applied" and receipt["terminal_matches"] is not True)):
                logger.warning("Invalid Host terminal receipt for %s; outbox remains pending", job_id)
                return
            if receipt["terminal_matches"] and receipt["status"] != payload["status"]:
                logger.warning("Inconsistent Host terminal receipt for %s; outbox remains pending", job_id)
                return
            self.store.record_scene_terminal_reconciliation(job_id, {
                key: receipt[key] for key in ("host_job_id", "status", "disposition", "terminal_matches")
            })

    async def _retry_terminal(self, job_id: str, identity: HostIdentity) -> None:
        delay = 1.0
        try:
            while not self._stopping and identity.expires_at > int(time.time()):
                await asyncio.sleep(delay)
                await self._consume_terminal(job_id, identity)
                task = self.store.get_scene_recipe_task(job_id)
                if task.host_terminal_sent or task.host_terminal_reconciliation is not None:
                    return
                delay = min(delay * 2, 30.0)
        finally:
            self._outbox_tasks.pop(job_id, None)

    async def cancel(self, job_id: str, owner: str) -> dict[str, Any]:
        self.store.get_scene_recipe_task(job_id, owner=owner)
        current = self.store.get_job(job_id)
        if current.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            self.store.request_cancel(job_id)
            task = self._tasks.get(job_id)
            if task is not None:
                task.cancel()
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        return self.projection(job_id, owner)

    async def wait_cleanup(self, job_id: str, timeout: float = 5.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while job_id in self._tasks:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"scene recipe job {job_id} cleanup did not finish")
            await asyncio.sleep(0.01)

    async def _run(
        self,
        job_id: str,
        value: SceneCreateRequest | SceneEditRequest | SceneMaterialRequest,
    ) -> None:
        execution = self._executions[job_id]
        reporter = HostJobReporter(self.host, execution)
        control = asyncio.create_task(
            self._maintain_control(job_id, execution), name=f"scene-recipe-control-{job_id}"
        )
        try:
            self.store.update_job(job_id, status=JobStatus.RUNNING, phase="validate_recipe", progress=0.05)
            self.store.update_scene_recipe_task(job_id, stage="validate_recipe")
            await self._report_progress(reporter, "validate_recipe", 0.05)
            self.store.update_job(job_id, phase="blender_recipe", progress=0.25)
            self.store.update_scene_recipe_task(job_id, stage="blender_recipe")
            await self._report_progress(reporter, "blender_recipe", 0.25)
            task = self.store.get_scene_recipe_task(job_id)
            acquire = asyncio.create_task(
                self._execution_guard.acquire(),
                name=f"scene-recipe-slot-{job_id}",
            )
            acquired = False
            try:
                done, _ = await asyncio.wait(
                    {acquire, control}, return_when=asyncio.FIRST_COMPLETED
                )
                if control in done:
                    error = control.exception()
                    if error is not None:
                        raise SceneError(
                            "host_context_lost",
                            "ControlDeck child Job control or credential refresh failed",
                        ) from error
                    raise asyncio.CancelledError
                await acquire
                acquired = True
                execution_call = (
                    self.workspace.apply_material_binding(
                        task.owner,
                        value.scene_id,
                        value.binding,
                        external_job_id=job_id,
                        runtime_id=task.runtime_id,
                        runtime_version=task.runtime_version,
                    )
                    if isinstance(value, SceneMaterialRequest)
                    else self.workspace.apply_recipe(
                        task.owner,
                        job_id,
                        value,
                        runtime_id=task.runtime_id,
                        runtime_version=task.runtime_version,
                    )
                )
                recipe_execution = asyncio.create_task(
                    execution_call,
                    name=f"scene-recipe-worker-{job_id}",
                )
                try:
                    done, _ = await asyncio.wait(
                        {recipe_execution, control}, return_when=asyncio.FIRST_COMPLETED
                    )
                    if recipe_execution in done:
                        result = recipe_execution.result()
                    elif control in done:
                        error = control.exception()
                        if error is not None:
                            raise SceneError(
                                "host_context_lost",
                                "ControlDeck child Job control or credential refresh failed",
                            ) from error
                        raise asyncio.CancelledError
                finally:
                    if not recipe_execution.done():
                        recipe_execution.cancel()
                        await asyncio.gather(recipe_execution, return_exceptions=True)
            finally:
                if not acquire.done():
                    acquire.cancel()
                    await asyncio.gather(acquire, return_exceptions=True)
                elif not acquired and not acquire.cancelled():
                    try:
                        acquired = bool(acquire.result())
                    except Exception:
                        acquired = False
                if acquired:
                    self._execution_guard.release()
            self.store.update_job(job_id, phase="publish_revision", progress=0.9)
            self.store.update_scene_recipe_task(job_id, stage="publish_revision")
            assets = list(result.pop("asset_ids")) if "asset_ids" in result else [
                result["revision"]["source_asset_id"],
                result["revision"]["preview_asset_id"],
            ]
            self.store.update_scene_recipe_task(job_id, stage="succeeded", result=result)
            self.store.update_job(
                job_id, status=JobStatus.SUCCEEDED, phase="succeeded", progress=1, asset_ids=assets
            )
            terminal = {
                "status": "succeeded",
                "phase": "succeeded",
                "progress": 1.0,
                "result": {
                    "job_id": job_id,
                    "scene_id": result["scene"]["id"],
                    "revision_id": result["revision"]["id"],
                    "asset_ids": assets,
                },
            }
            self.store.queue_scene_recipe_terminal(job_id, terminal)
            if await self._report_terminal(
                reporter, execution, "succeeded", result=terminal["result"]
            ):
                self.store.mark_scene_recipe_terminal_sent(job_id)
        except asyncio.CancelledError:
            if self._stopping:
                terminal = {
                    "status": "failed",
                    "phase": "failed",
                    "progress": 1.0,
                    "error": "service_stopped",
                }
                self.store.queue_scene_recipe_terminal(job_id, terminal)
                if await self._report_terminal(
                    reporter, execution, "failed", error="service_stopped"
                ):
                    self.store.mark_scene_recipe_terminal_sent(job_id)
            else:
                self.store.update_scene_recipe_task(job_id, stage="canceled")
                self.store.update_job(
                    job_id,
                    status=JobStatus.CANCELED,
                    phase="canceled",
                    progress=self.store.get_job(job_id).progress,
                )
                self.store.queue_scene_recipe_terminal(job_id, {
                    "status": "canceled", "phase": "canceled", "progress": 1.0,
                })
                if await self._report_terminal(reporter, execution, "canceled"):
                    self.store.mark_scene_recipe_terminal_sent(job_id)
            raise
        except (SceneError, HostApiError, KeyError) as exc:
            code = getattr(exc, "code", "scene_recipe_failed")
            self.store.update_scene_recipe_task(job_id, stage=str(code))
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                phase="failed",
                progress=self.store.get_job(job_id).progress,
                error=ErrorDetail(code=str(code), message=str(exc)[:300]),
            )
            self.store.queue_scene_recipe_terminal(job_id, {
                "status": "failed", "phase": "failed", "progress": 1.0,
                "error": str(code),
            })
            if await self._report_terminal(reporter, execution, "failed", error=str(code)):
                self.store.mark_scene_recipe_terminal_sent(job_id)
        except Exception as exc:  # final isolation boundary; one bad recipe must not strand the queue
            self.store.update_scene_recipe_task(job_id, stage="internal_error")
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                phase="failed",
                progress=self.store.get_job(job_id).progress,
                error=ErrorDetail(code="internal_error", message=str(exc)[:300]),
            )
            self.store.queue_scene_recipe_terminal(job_id, {
                "status": "failed", "phase": "failed", "progress": 1.0,
                "error": "internal_error",
            })
            if await self._report_terminal(
                reporter, execution, "failed", error="internal_error"
            ):
                self.store.mark_scene_recipe_terminal_sent(job_id)
        finally:
            control.cancel()
            await asyncio.gather(control, return_exceptions=True)
            record = self.store.get_scene_recipe_task(job_id)
            if not self._stopping and record.host_terminal and not record.host_terminal_sent:
                self._outbox_tasks[job_id] = asyncio.create_task(
                    self._retry_terminal(job_id, execution.identity), name=f"scene-terminal-outbox-{job_id}"
                )

    async def _maintain_control(self, job_id: str, execution: HostExecution) -> bool:
        while True:
            await asyncio.sleep(self.control_poll_sec)
            if execution.identity.expires_at - int(time.time()) <= self.credential_refresh_margin_sec:
                refreshed = await self.host.refresh_job_credential(
                    execution.identity, execution.host_job_id
                )
                token = refreshed.get("access_token")
                expires_at = refreshed.get("expires_at")
                if not isinstance(token, str) or not token or not isinstance(expires_at, int):
                    raise HostApiError(
                        "invalid_host_response",
                        "Host Job credential refresh is invalid",
                        status_code=502,
                    )
                execution.identity = execution.identity.__class__(
                    authorization=f"Bearer {token}",
                    addon_id=execution.identity.addon_id,
                    subject=execution.identity.subject,
                    expires_at=expires_at,
                    granted_capabilities=execution.identity.granted_capabilities,
                    actor_subject=execution.identity.actor_subject,
                )
            control = await self.host.job_control(execution.identity, execution.host_job_id)
            if control.get("cancel_requested") is True:
                return True
            if control.get("status") in {"succeeded", "failed", "interrupted"}:
                raise HostApiError("host_job_terminated", "Host Job ended before local execution finished")

    @staticmethod
    async def _report_progress(reporter: HostJobReporter, phase: str, progress: float) -> None:
        try:
            await reporter.progress(phase, progress)
        except HostApiError:
            # The local durable record remains authoritative if a short-lived
            # Host credential expires after submission.
            return

    async def _report_terminal(
        self,
        reporter: HostJobReporter,
        execution: HostExecution,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        for attempt in range(3):
            try:
                if execution.owns_terminal:
                    await reporter.terminal(
                        status, phase=status, progress=1, result=result, error=error
                    )
                else:
                    await reporter.finish_attached(phase=status, progress=1)
                return True
            except (HostApiError, ValueError):
                if attempt < 2:
                    await asyncio.sleep(min(self.control_poll_sec, 0.25))
        return False
