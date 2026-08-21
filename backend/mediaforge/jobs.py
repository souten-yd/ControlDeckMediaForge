from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from . import __version__
from .config import REPOSITORY_ROOT
from .domain import Asset, ErrorDetail, Job, JobRequest, JobStatus, Provenance
from .host.client import ControlDeckHostClient, HostApiError
from .host.jobs import HostExecution, HostJobReporter
from .host.resources import fake_image_request, image_model_request
from .image_edit import StrictEditError, strict_edit_plan, validate_strict_edit
from .models import ModelDescriptor, ModelRegistry, ModelRegistryError
from .outpaint import outpaint_plan, validate_outpaint
from .paths import contained
from .routing import ModelRouteError, route_model
from .store import Store, utc_now
from .validators import validate_png


# Media Forge is served by Uvicorn in both `mf.sh serve` and the installed
# Add-on. Reuse its configured application logger so bounded worker telemetry
# is visible without configuring a second handler or leaking worker stderr.
logger = logging.getLogger("uvicorn.error")
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
OOM_FLOOR_INCREMENT_BYTES = 512 * 1024 * 1024


class WorkerFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class JobManager:
    """Durable queue with a single worker-local execution guard.

    Host-originated jobs use the ControlDeck broker contract even with the G0
    fake worker. Standalone jobs remain usable without a host connection.
    """

    def __init__(
        self,
        store: Store,
        *,
        worker_timeout_sec: float = 30.0,
        host_client: ControlDeckHostClient | None = None,
        lease_renew_sec: float = 10.0,
        model_manifest: Path | None = None,
        hf_home: Path | None = None,
        image_runtime_python: Path | None = None,
    ):
        self.store = store
        self.worker_timeout_sec = worker_timeout_sec
        self.host_client = host_client
        self.lease_renew_sec = lease_renew_sec
        self.model_manifest = model_manifest
        self.hf_home = hf_home
        self.image_runtime_python = image_runtime_python
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._runner: asyncio.Task[None] | None = None
        self._job_tasks: dict[str, asyncio.Task[None]] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._host_executions: dict[str, HostExecution] = {}
        self._host_failures: dict[str, HostApiError] = {}
        self._selected_models: dict[str, ModelDescriptor] = {}
        self._admission_floor_bytes: dict[str, int] = {}
        self._execution_guard = asyncio.Semaphore(1)
        self._stopping = False

    async def start(self) -> None:
        if self._runner is not None:
            return
        self._stopping = False
        for job_id in self.store.queued_job_ids():
            self._queue.put_nowait(job_id)
        self._runner = asyncio.create_task(self._run(), name="media-forge-job-runner")

    async def stop(self) -> None:
        if self._runner is None:
            return
        self._stopping = True
        active_job_ids = list(self._job_tasks)
        for job_id in active_job_ids:
            current = self.store.get_job(job_id)
            if current.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(code="service_stopped", message="Service stopped while the job was active"),
                )
        processes = list(self._processes.items())
        for job_id, process in processes:
            if process.returncode is None:
                process.terminate()
        self._runner.cancel()
        try:
            await self._runner
        except asyncio.CancelledError:
            pass
        tasks = list(self._job_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for _, process in processes:
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except TimeoutError:
                    process.kill()
                    await process.wait()
        self._runner = None

    def submit(self, request: JobRequest) -> Job:
        job = self.store.create_job(request)
        self._queue.put_nowait(job.id)
        return job

    def submit_hosted(self, request: JobRequest, execution: HostExecution) -> Job:
        if self.host_client is None:
            raise RuntimeError("ControlDeck Host client is not configured")
        job = self.store.create_job(request, host_managed=True)
        self._host_executions[job.id] = execution
        self._queue.put_nowait(job.id)
        return job

    async def cancel(self, job_id: str) -> Job:
        job = self.store.request_cancel(job_id)
        process = self._processes.get(job_id)
        if process is not None and process.returncode is None:
            process.terminate()
        return self.store.get_job(job_id)

    async def wait_cleanup(self, job_id: str, timeout: float = 5.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while job_id in self._job_tasks:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"job {job_id} cleanup did not finish")
            await asyncio.sleep(0.01)

    async def _run(self) -> None:
        while True:
            job_id = await self._queue.get()
            if job_id is None:
                return
            task = asyncio.create_task(self._run_one(job_id), name=f"media-forge-job-{job_id}")
            self._job_tasks[job_id] = task

    async def _run_one(self, job_id: str) -> None:
        try:
            await self._execute(job_id)
        except asyncio.CancelledError:
            raise
        except WorkerFailure as exc:
            current = self.store.get_job(job_id)
            if current.status not in {JobStatus.CANCELED, JobStatus.SUCCEEDED, JobStatus.FAILED}:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
                )
        except Exception as exc:  # final isolation boundary; runner must survive a job defect
            try:
                current = self.store.get_job(job_id)
                if current.status not in {JobStatus.CANCELED, JobStatus.SUCCEEDED, JobStatus.FAILED}:
                    self.store.update_job(
                        job_id,
                        status=JobStatus.FAILED,
                        error=ErrorDetail(code="internal_error", message=str(exc)[:300]),
                    )
            except KeyError:
                pass
        finally:
            job_root = contained(self.store.work_dir, self.store.work_dir / job_id)
            if job_root.exists():
                try:
                    shutil.rmtree(job_root)
                except OSError:
                    logger.exception("failed to remove bounded job work directory for %s", job_id)
            self._host_executions.pop(job_id, None)
            self._host_failures.pop(job_id, None)
            self._selected_models.pop(job_id, None)
            self._job_tasks.pop(job_id, None)
            self._queue.task_done()

    async def _execute(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if job.status != JobStatus.QUEUED or self.store.cancel_requested(job_id):
            return
        if job.request.operation not in {"image.generate", "image.edit"}:
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=ErrorDetail(code="capability_unavailable", message=f"{job.request.operation} is unavailable in G0"),
            )
            return
        execution = self._host_executions.get(job_id)
        reporter = (
            HostJobReporter(self.host_client, execution)
            if execution is not None and self.host_client is not None
            else None
        )
        maintenance: asyncio.Task[None] | None = None
        try:
            try:
                self._validate_input_assets(job)
            except WorkerFailure as exc:
                await self._update(
                    job_id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="validate_request",
                    error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
                )
                return
            try:
                selected = self._select_real_model(job)
            except WorkerFailure as exc:
                await self._update(
                    job_id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="select_model",
                    error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
                )
                return
            if selected is not None:
                if execution is None:
                    self.store.update_job(
                        job_id,
                        status=JobStatus.FAILED,
                        error=ErrorDetail(
                            code="host_lease_required",
                            message="real GPU generation requires a ControlDeck-managed execution",
                        ),
                    )
                    return
                self._selected_models[job_id] = selected
            if execution is not None:
                admitted = await self._acquire_host_lease(job, execution, reporter)
                if not admitted:
                    return
                maintenance = asyncio.create_task(
                    self._maintain_host_lease(job_id, execution),
                    name=f"media-forge-lease-{job_id}",
                )
            async with self._execution_guard:
                if self.store.cancel_requested(job_id):
                    await self._finish_canceled(job_id, reporter)
                    return
                await self._execute_worker(job_id, reporter)
        finally:
            if maintenance is not None:
                maintenance.cancel()
                await asyncio.gather(maintenance, return_exceptions=True)
            if execution is not None:
                await self._release_host_resource(execution)

    def _select_real_model(self, job: Job) -> ModelDescriptor | None:
        if self.model_manifest is None or self.hf_home is None:
            return None
        try:
            models = ModelRegistry.load(self.model_manifest, hf_home=self.hf_home).all()
        except ModelRegistryError as exc:
            raise WorkerFailure("model_registry_invalid", str(exc)) from exc
        capability = self._model_capability(job)
        available = any(
            item.state.value == "available"
            for item in models
            if capability in item.capabilities
        )
        if not available and job.request.model_policy != "manual":
            if any(item.state.value == "available" for item in models):
                raise WorkerFailure(
                    "capability_unavailable",
                    f"no installed model provides {capability}",
                )
            return None
        try:
            selected = route_model(
                models,
                capability=capability,
                policy=job.request.model_policy,
                model_id=job.request.model_id,
                hardware_backend="rocm",
                # ControlDeck performs live admission against current free VRAM.
                free_vram_bytes=2**63 - 1,
            )
            self._validate_generation_limits(job, selected)
            return selected
        except ModelRouteError as exc:
            raise WorkerFailure(exc.code, str(exc)) from exc

    @staticmethod
    def _model_capability(job: Job) -> str:
        if job.request.operation == "image.generate":
            return "image.text_to_image"
        if job.request.constraints.get("edit_mode") == "outpaint":
            return "image.outpaint"
        if job.request.constraints.get("edit_mode") == "variation":
            return "image.variation"
        return (
            "image.strict_edit"
            if job.request.constraints.get("strict_edit") is True
            else "image.single_reference_edit"
        )

    def _validate_input_assets(self, job: Job) -> None:
        if job.request.operation != "image.edit":
            return
        if len(job.request.inputs) != 1:
            raise WorkerFailure("invalid_reference_count", "single-reference image.edit requires exactly one input")
        try:
            source = self.store.get_asset(job.request.inputs[0].asset_id)
            source_path = self.store.asset_path(source.id)
        except KeyError as exc:
            raise WorkerFailure("asset_not_found", "source image asset was not found") from exc
        if source.mime_type != "image/png":
            raise WorkerFailure("unsupported_reference", "image.edit currently requires a PNG source asset")
        strict = job.request.constraints.get("strict_edit", False)
        if not isinstance(strict, bool):
            raise WorkerFailure("invalid_constraint", "strict_edit must be a boolean")
        edit_mode = job.request.constraints.get("edit_mode", "reference")
        if edit_mode not in {"reference", "variation", "inpaint", "outpaint"}:
            raise WorkerFailure("invalid_constraint", "edit_mode is unsupported")
        if strict and edit_mode == "variation":
            raise WorkerFailure("invalid_constraint", "variation cannot request strict_edit")
        if edit_mode == "inpaint" and not strict:
            raise WorkerFailure("invalid_constraint", "inpaint requires strict_edit")
        if edit_mode == "outpaint":
            if not strict:
                raise WorkerFailure("invalid_constraint", "outpaint requires strict_edit")
            if "editable_mask_asset_id" in job.request.constraints:
                raise WorkerFailure("invalid_constraint", "outpaint derives its mask and does not accept one")
            width = job.request.constraints.get("width")
            height = job.request.constraints.get("height")
            if (
                not isinstance(width, int)
                or isinstance(width, bool)
                or not isinstance(height, int)
                or isinstance(height, bool)
                or width % 16
                or height % 16
            ):
                raise WorkerFailure("invalid_dimensions", "outpaint dimensions must be integer multiples of 16")
            try:
                outpaint_plan(source_path, width, height)
            except StrictEditError as exc:
                raise WorkerFailure("invalid_dimensions", str(exc)) from exc
            return
        if not strict and "editable_mask_asset_id" in job.request.constraints:
            raise WorkerFailure("invalid_constraint", "editable_mask_asset_id requires strict_edit")
        if not strict:
            return
        mask_id = job.request.constraints.get("editable_mask_asset_id")
        if not isinstance(mask_id, str) or not mask_id.startswith("asset_"):
            raise WorkerFailure("invalid_edit_mask", "strict edit requires editable_mask_asset_id")
        try:
            mask = self.store.get_asset(mask_id)
            mask_path = self.store.asset_path(mask.id)
        except KeyError as exc:
            raise WorkerFailure("invalid_edit_mask", "edit mask asset was not found") from exc
        if mask.mime_type != "image/png":
            raise WorkerFailure("invalid_edit_mask", "edit mask must be a PNG asset")
        for key, actual in (("width", source.width), ("height", source.height)):
            requested = job.request.constraints.get(key, actual)
            if requested != actual:
                raise WorkerFailure("invalid_dimensions", "strict edit dimensions must match the source image")
        try:
            strict_edit_plan(source_path, mask_path)
        except StrictEditError as exc:
            raise WorkerFailure("invalid_edit_mask", str(exc)) from exc

    def _validate_generation_limits(self, job: Job, selected: ModelDescriptor) -> None:
        source = None
        if job.request.operation == "image.edit":
            try:
                source = self.store.get_asset(job.request.inputs[0].asset_id)
            except (IndexError, KeyError):
                pass
        width = job.request.constraints.get("width", source.width if source and source.width else 1024)
        height = job.request.constraints.get("height", source.height if source and source.height else 1024)
        if (
            not isinstance(width, int)
            or isinstance(width, bool)
            or not isinstance(height, int)
            or isinstance(height, bool)
        ):
            raise WorkerFailure("invalid_dimensions", "image dimensions must be integers")
        if width > selected.max_width or height > selected.max_height or width * height > selected.max_pixels:
            raise WorkerFailure(
                "resource_limit",
                "requested image dimensions exceed this model's measured generation envelope",
            )

    async def _execute_worker(self, job_id: str, reporter: HostJobReporter | None) -> None:
        job = self.store.get_job(job_id)
        await self._update(job_id, reporter, status=JobStatus.RUNNING, phase="normalize_request", progress=0.01)
        await self._update(job_id, reporter, phase="select_model", progress=0.03)
        await self._update(job_id, reporter, phase="generating", progress=0.05)
        job_root = contained(self.store.work_dir, self.store.work_dir / job_id)
        if job_root.exists():
            shutil.rmtree(job_root)
        job_root.mkdir(mode=0o700)
        output_dir = job_root / "outputs"
        worker_inputs = self._materialize_worker_inputs(job, job_root)
        selected = self._selected_models.get(job_id)
        payload: dict[str, Any]
        if selected is None:
            payload = job.request.model_dump(mode="json")
            payload["worker_output_dir"] = str(output_dir)
            payload["worker_inputs"] = worker_inputs
        else:
            assert selected.local_path is not None
            payload = {
                "model": {
                    "id": selected.model_id,
                    "path": str(selected.local_path),
                    "version": selected.version,
                    "weights_hash": selected.weights_hash,
                    "license": selected.license,
                    "runtime_adapter": selected.runtime_adapter,
                    "runtime_options": {
                        "device_mode": selected.device_mode,
                        "disable_mmap": selected.disable_mmap,
                    },
                },
                "request": job.request.model_dump(mode="json"),
                "worker_output_dir": str(output_dir),
                "worker_inputs": worker_inputs,
            }
        backend_root = str(Path(__file__).resolve().parents[1])
        environment = dict(os.environ)
        environment["PYTHONPATH"] = backend_root + os.pathsep + environment.get("PYTHONPATH", "")
        module = "mediaforge.workers.fake"
        executable = Path(sys.executable)
        stdin_payload = json.dumps(payload).encode("utf-8")
        timeout_sec = self.worker_timeout_sec
        if selected is not None:
            assert self.image_runtime_python is not None and selected.local_path is not None
            if not self.image_runtime_python.is_file():
                raise WorkerFailure("worker_not_installed", "image runtime is not installed")
            executable = self.image_runtime_python
            module = "worker_packs.image.worker"
            repository_root = str(REPOSITORY_ROOT)
            environment["PYTHONPATH"] = repository_root + os.pathsep + environment.get("PYTHONPATH", "")
            environment["MEDIA_FORGE_MODEL_ROOT"] = str(selected.local_path.parents[1])
            environment["MEDIA_FORGE_WORK_ROOT"] = str(self.store.work_dir.resolve())
            stdin_payload += b"\n"
            timeout_sec = max(self.worker_timeout_sec, float(selected.measured_runtime_sec or 0) * 3 + 30)
        process = await asyncio.create_subprocess_exec(
            str(executable),
            "-m",
            module,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        self._processes[job_id] = process
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(stdin_payload), timeout=timeout_sec
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="generating",
                error=ErrorDetail(code="worker_timeout", message="image worker exceeded its timeout"),
            )
            return
        finally:
            self._processes.pop(job_id, None)
        if self._stopping:
            return
        host_failure = self._host_failures.get(job_id)
        if host_failure is not None:
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="generating",
                error=ErrorDetail(code=host_failure.code, message=str(host_failure)[:300]),
            )
            return
        if self.store.cancel_requested(job_id):
            await self._finish_canceled(job_id, reporter)
            return
        if len(stdout) > 1024 * 1024 or len(stderr) > 64 * 1024:
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="generating",
                error=ErrorDetail(code="worker_output_too_large", message="worker output exceeded its bound"),
            )
            return
        response: dict[str, Any] = {}
        try:
            response = json.loads(stdout)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        if selected is not None and isinstance(response, dict):
            if response.get("ok") is True and isinstance(response.get("result"), dict):
                response = response["result"]
            elif response.get("ok") is False:
                detail = response.get("error", {})
                error_code = str(detail.get("code", "worker_error"))
                if error_code == "resource_oom":
                    self._record_oom(selected)
                await self._update(
                    job_id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="generating",
                    error=ErrorDetail(
                        code=error_code,
                        message=str(detail.get("message", "image worker failed"))[:300],
                    ),
                )
                return
        if process.returncode != 0:
            detail = response.get("error", {}) if isinstance(response, dict) else {}
            code = str(detail.get("code", "worker_crash"))
            message = str(detail.get("message", f"worker exited with code {process.returncode}"))
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="generating",
                error=ErrorDetail(code=code, message=message[:300]),
            )
            return
        metrics = response.get("runtime_metrics") if isinstance(response, dict) else None
        if isinstance(metrics, dict):
            load_sec = metrics.get("load_sec")
            generation_sec = metrics.get("generation_sec")
            if (
                isinstance(load_sec, (int, float))
                and not isinstance(load_sec, bool)
                and 0 <= load_sec <= timeout_sec
                and isinstance(generation_sec, (int, float))
                and not isinstance(generation_sec, bool)
                and 0 <= generation_sec <= timeout_sec
            ):
                logger.info(
                    "image worker timing job=%s load_sec=%.6f generation_sec=%.6f",
                    job_id,
                    float(load_sec),
                    float(generation_sec),
                )
            placement = metrics.get("placement")
            if isinstance(placement, dict):
                logger.info(
                    "image worker placement job=%s device_mode=%s component_devices=%s "
                    "offload_hooks=%s non_gpu_devices=%s non_gpu_map_targets=%s",
                    job_id,
                    str(metrics.get("device_mode", "unknown"))[:40],
                    placement.get("component_devices", {}),
                    placement.get("offload_hooks", []),
                    placement.get("non_gpu_devices", {}),
                    placement.get("non_gpu_map_targets", []),
                )
        await self._update(job_id, reporter, phase="postprocess", progress=0.65)
        try:
            asset_ids = self._register_outputs(job, response, job_root)
        except StrictEditError as exc:
            code = (
                "outpaint_invariant_failed"
                if job.request.constraints.get("edit_mode") == "outpaint"
                else "strict_edit_invariant_failed"
            )
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="validate",
                error=ErrorDetail(code=code, message=str(exc)[:300]),
            )
            return
        except (KeyError, TypeError, ValueError, OSError) as exc:
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="validate",
                error=ErrorDetail(code="artifact_integrity_failed", message=str(exc)[:300]),
            )
            return
        await self._update(
            job_id,
            reporter,
            status=JobStatus.SUCCEEDED,
            phase="register_asset",
            progress=1,
            asset_ids=asset_ids,
        )

    def _materialize_worker_inputs(self, job: Job, job_root: Path) -> dict[str, str]:
        if job.request.operation != "image.edit":
            return {}
        inputs_dir = contained(job_root, job_root / "inputs")
        inputs_dir.mkdir(mode=0o700)
        source_id = job.request.inputs[0].asset_id
        source_destination = contained(inputs_dir, inputs_dir / "source.png")
        shutil.copyfile(self.store.asset_path(source_id), source_destination)
        result = {"source_path": str(source_destination)}
        if (
            job.request.constraints.get("strict_edit") is True
            and job.request.constraints.get("edit_mode") != "outpaint"
        ):
            mask_id = str(job.request.constraints["editable_mask_asset_id"])
            mask_destination = contained(inputs_dir, inputs_dir / "mask.png")
            shutil.copyfile(self.store.asset_path(mask_id), mask_destination)
            result["mask_path"] = str(mask_destination)
        return result

    async def _acquire_host_lease(
        self,
        job: Job,
        execution: HostExecution,
        reporter: HostJobReporter | None,
    ) -> bool:
        assert self.host_client is not None and reporter is not None
        selected = self._selected_models.get(job.id)
        delay = float(job.request.constraints.get("_fake_delay_sec", 0))
        estimate = max(1.0, min(self.worker_timeout_sec, delay + 1.0))
        try:
            resource_request = self._resource_request(job, execution, selected, estimate)
            status = await self.host_client.request_resource(execution.identity, resource_request)
            request_id = status.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                raise HostApiError("invalid_host_response", "ControlDeck did not return a resource request ID")
            execution.request_id = request_id
            while status.get("state") == "waiting":
                reason = status.get("reason")
                await self._update(
                    job.id,
                    reporter,
                    phase="waiting_resource",
                    progress=max(self.store.get_job(job.id).progress, 0.03),
                    wait_reason=reason if isinstance(reason, str) else None,
                )
                if await self._host_or_local_cancel_requested(job.id, execution):
                    await self._finish_canceled(job.id, reporter)
                    return False
                await asyncio.sleep(0.1)
                status = await self.host_client.resource_status(execution.identity, request_id)
            if status.get("state") != "granted" or not isinstance(status.get("lease_id"), str):
                reason = str(status.get("reason") or status.get("state") or "unknown")
                await self._update(
                    job.id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="waiting_resource",
                    error=ErrorDetail(code="resource_unavailable", message=f"ControlDeck admission failed: {reason}"),
                )
                return False
            execution.lease_id = status["lease_id"]
            await self.host_client.lease_action(execution.identity, execution.lease_id, "activate")
            await self._update(job.id, reporter, phase="starting", progress=0.04)
            return True
        except HostApiError as exc:
            await self._update(
                job.id,
                reporter=None,
                status=JobStatus.FAILED,
                phase="waiting_resource",
                error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
            )
            return False

    def _resource_request(
        self,
        job: Job,
        execution: HostExecution,
        selected: ModelDescriptor | None,
        fake_runtime_sec: float,
    ) -> dict[str, Any]:
        request = (
            image_model_request(execution.host_job_id, selected, workload_class=execution.workload_class)
            if selected is not None
            else fake_image_request(
                execution.host_job_id, runtime_sec=fake_runtime_sec, workload_class=execution.workload_class
            )
        )
        if selected is not None:
            floor = self._admission_floor_bytes.get(selected.model_id)
            if floor is not None:
                headroom = int(request["vram"]["headroom_bytes"])
                peak_floor = max(0, floor - headroom)
                for key in ("execution_peak_bytes", "cold_load_peak_bytes"):
                    request["vram"][key] = max(int(request["vram"][key]), peak_floor)
        return request

    def _record_oom(self, selected: ModelDescriptor) -> None:
        measured = selected.measured_vram_bytes or 0
        current_floor = self._admission_floor_bytes.get(selected.model_id, measured)
        self._admission_floor_bytes[selected.model_id] = max(measured, current_floor) + OOM_FLOOR_INCREMENT_BYTES

    async def _maintain_host_lease(self, job_id: str, execution: HostExecution) -> None:
        assert self.host_client is not None and execution.lease_id is not None
        loop = asyncio.get_running_loop()
        renew_at = loop.time() + self.lease_renew_sec
        try:
            while True:
                await asyncio.sleep(0.25)
                if execution.identity.expires_at - int(time.time()) <= 120:
                    execution.identity = await self.host_client.refresh_lease_identity(
                        execution.identity, execution.lease_id
                    )
                if await self._host_or_local_cancel_requested(job_id, execution):
                    process = self._processes.get(job_id)
                    if process is not None and process.returncode is None:
                        process.terminate()
                    return
                if loop.time() >= renew_at:
                    await self.host_client.lease_action(execution.identity, execution.lease_id, "renew")
                    renew_at = loop.time() + self.lease_renew_sec
        except asyncio.CancelledError:
            raise
        except HostApiError as exc:
            self._host_failures[job_id] = exc
            self.store.request_cancel(job_id)
            process = self._processes.get(job_id)
            if process is not None and process.returncode is None:
                process.terminate()

    async def _host_or_local_cancel_requested(self, job_id: str, execution: HostExecution) -> bool:
        if self.store.cancel_requested(job_id):
            return True
        assert self.host_client is not None
        control = await self.host_client.job_control(execution.identity, execution.host_job_id)
        if control.get("cancel_requested") is True:
            self.store.request_cancel(job_id)
            return True
        return False

    async def _release_host_resource(self, execution: HostExecution) -> None:
        if self.host_client is None:
            return
        try:
            if execution.lease_id is not None:
                await self.host_client.lease_action(execution.identity, execution.lease_id, "release")
            elif execution.request_id is not None:
                await self.host_client.cancel_resource(execution.identity, execution.request_id)
        except HostApiError:
            logger.exception("failed to release ControlDeck resource state for %s", execution.host_job_id)

    async def _finish_canceled(self, job_id: str, reporter: HostJobReporter | None) -> None:
        current = self.store.get_job(job_id)
        effective_reporter = reporter
        if reporter is not None and reporter.execution.owns_terminal and self.host_client is not None:
            try:
                control = await self.host_client.job_control(
                    reporter.execution.identity,
                    reporter.execution.host_job_id,
                )
                if control.get("status") == "canceled":
                    effective_reporter = None
            except HostApiError:
                effective_reporter = None
        await self._update(
            job_id,
            effective_reporter,
            status=JobStatus.CANCELED,
            phase=current.phase or "canceled",
            progress=current.progress,
        )

    async def _update(
        self,
        job_id: str,
        reporter: HostJobReporter | None,
        *,
        status: JobStatus | None = None,
        phase: str,
        progress: float | None = None,
        asset_ids: list[str] | None = None,
        error: ErrorDetail | None = None,
        wait_reason: str | None = None,
    ) -> Job:
        current = self.store.get_job(job_id)
        normalized_progress = current.progress if progress is None else progress
        terminal = status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}
        if reporter is not None and terminal:
            if reporter.execution.owns_terminal:
                await reporter.terminal(
                    status.value,
                    phase=phase,
                    progress=normalized_progress,
                    result={"asset_ids": asset_ids} if status == JobStatus.SUCCEEDED else None,
                    error=error.message if error is not None else None,
                )
            else:
                await reporter.finish_attached(phase=phase, progress=normalized_progress)
        result = self.store.update_job(
            job_id,
            status=status,
            phase=None if terminal else phase,
            progress=normalized_progress,
            asset_ids=asset_ids,
            error=error,
        )
        if reporter is not None and not terminal:
            await reporter.progress(phase, normalized_progress, wait_reason=wait_reason)
        return result

    def _register_outputs(self, job: Job, response: dict[str, Any], job_root: Path) -> list[str]:
        outputs = response["outputs"]
        if not isinstance(outputs, list) or len(outputs) != job.request.output.count:
            raise ValueError("worker returned an unexpected output count")
        model = response["model"]
        reference_hashes = {
            item.asset_id: self.store.get_asset(item.asset_id).sha256 for item in job.request.inputs
        }
        outpaint = (
            job.request.operation == "image.edit"
            and job.request.constraints.get("edit_mode") == "outpaint"
        )
        strict_edit = (
            job.request.operation == "image.edit"
            and job.request.constraints.get("strict_edit") is True
            and not outpaint
        )
        source_path = contained(job_root, job_root / "inputs" / "source.png") if strict_edit or outpaint else None
        mask_path = contained(job_root, job_root / "inputs" / "mask.png") if strict_edit else None
        if strict_edit:
            mask_id = str(job.request.constraints["editable_mask_asset_id"])
            reference_hashes[mask_id] = self.store.get_asset(mask_id).sha256
        asset_ids: list[str] = []
        self.store.update_job(job.id, phase="validate", progress=0.75)
        for index, output in enumerate(outputs):
            path = contained(job_root, Path(output["path"]))
            if path.stat().st_size > MAX_ARTIFACT_BYTES:
                raise ValueError("worker artifact exceeded the 64 MiB limit")
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            width, height, validation = validate_png(path)
            if strict_edit:
                assert source_path is not None and mask_path is not None
                validation.append(validate_strict_edit(source_path, mask_path, path))
            if outpaint:
                assert source_path is not None
                validation.append(validate_outpaint(
                    source_path,
                    path,
                    width=int(job.request.constraints["width"]),
                    height=int(job.request.constraints["height"]),
                ))
            now = utc_now()
            asset_id = f"asset_{uuid.uuid4().hex}"
            provenance_id = f"prov_{uuid.uuid4().hex}"
            asset = Asset(
                id=asset_id,
                job_id=job.id,
                parent_asset_ids=[item.asset_id for item in job.request.inputs],
                mime_type="image/png",
                width=width,
                height=height,
                size_bytes=path.stat().st_size,
                sha256=sha256,
                suggested_filename=f"media-forge-{job.id[4:12]}-{index + 1}.png",
                provenance_id=provenance_id,
                created_at=now,
            )
            provenance = Provenance(
                id=provenance_id,
                asset_id=asset_id,
                parent_asset_ids=asset.parent_asset_ids,
                operation=job.request.operation,
                intent=job.request.intent,
                model_id=str(model["id"]),
                model_version=str(model["version"]),
                weights_hash=str(model["weights_hash"]),
                license=str(model["license"]),
                runtime_adapter=str(model["runtime_adapter"]),
                runtime_version=str(model["runtime_version"]),
                tool_versions={"media-forge": __version__, "validator.png": "1.0.0"},
                seed=int(output.get("seed", response["seed"])),
                parameters={
                    "model_policy": job.request.model_policy,
                    "constraints": job.request.constraints,
                    "output": job.request.output.model_dump(mode="json"),
                },
                reference_asset_hashes=reference_hashes,
                postprocessing=[str(item) for item in response.get("postprocessing", [])],
                validation=validation,
                warnings=[],
                output_sha256=sha256,
                created_at=now,
            )
            self.store.update_job(job.id, phase="package", progress=0.85)
            self.store.update_job(job.id, phase="register_asset", progress=0.92)
            self.store.register_asset(asset, provenance, path)
            asset_ids.append(asset_id)
        return asset_ids
