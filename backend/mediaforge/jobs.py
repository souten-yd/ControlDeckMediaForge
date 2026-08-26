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
from .evaluator import CreativeEvaluationError, CreativeEvaluator
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.jobs import HostExecution, HostJobReporter
from .host.resources import fake_image_request, image_model_request
from .image_edit import StrictEditError, strict_edit_plan, validate_strict_edit
from .m5_companion import (
    M5CompanionError,
    build_pack as build_m5_pack,
    is_m5_profile,
    parse_pack_entries as parse_m5_pack_entries,
    validate_edit_mask as validate_m5_edit_mask,
    validate_image as validate_m5_image,
)
from .models import ModelDescriptor, ModelRegistry, ModelRegistryError
from .models.generation_defaults import normalize_base_model, snap_to_native
from .outpaint import outpaint_plan, validate_outpaint
from .paths import contained
from .profiles import profile_prompt
from .asset_brief import (
    AssetBrief,
    AssetBriefError,
    BriefDefect,
    ResolvedLayout,
    infer_brief_from_intent,
    inspect_against_brief,
    parse_brief,
)
from .blender_compile import (
    BLENDER_VERSION,
    COMPILER_VERSION,
    BlenderCompileCanceled,
    BlenderCompileError,
    compile_project_package,
    parse_compile_options,
)
from .routing import ModelRoute, ModelRouteError, route
from .host.ai import HostAIGateway, HostAIReleaseResult
from .store import Store, UnreadableJobRecord, utc_now
from .validators import validate_png


# Media Forge is served by Uvicorn in both `mf.sh serve` and the installed
# Add-on. Reuse its configured application logger so bounded worker telemetry
# is visible without configuring a second handler or leaking worker stderr.
logger = logging.getLogger("uvicorn.error")


class BriefDefectError(RuntimeError):
    """The produced asset is objectively wrong for what it was asked to be.

    Separate from WorkerFailure because the cause is the brief contract, and
    separate from evaluator findings because it is not a matter of taste.
    """

    def __init__(self, defects: list[BriefDefect]):
        super().__init__("; ".join(item.detail for item in defects)[:300])
        self.defects = defects
        self.code = defects[0].code if defects else "brief_defect"

# Broker が「VRAM が足りない/待たされる」と言ったときだけ、保持した解放理由を
# 添える。それ以外の受理失敗（policy 拒否など）に AI 常駐の話を混ぜない。
_VRAM_WAIT_REASONS = frozenset({
    "insufficient_vram",
    "device_busy",
    "timeout",
    "yield_thrash_cost",
    "yield_load_cost_unknown",
    "yield_runtime_unknown",
    "yield_minimum_uptime",
    "yield_thrash_window",
    "yield_drain_timeout",
    "waiting",
})
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
OOM_FLOOR_INCREMENT_BYTES = 512 * 1024 * 1024


class WorkerFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ProfileResolutionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def requested_guidance(job: Job, selected: ModelDescriptor) -> float | None:
    """要求が指定したガイダンス。指定が無ければモデルの宣言。

    0 は「CFG を使わない」という指示で、蒸留版はそれを前提に作られている。
    未指定と区別する必要があるので、真偽値ではなく None で判定する。
    """
    value = job.request.constraints.get("guidance_scale")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return selected.guidance_scale
    return float(value)


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
        blender_timeout_sec: float = 180.0,
        host_client: ControlDeckHostClient | None = None,
        lease_renew_sec: float = 10.0,
        model_manifest: Path | None = None,
        model_catalog_manifest: Path | None = None,
        model_store_root: Path | None = None,
        hf_home: Path | None = None,
        image_runtime_python: Path | None = None,
        creative_evaluator: CreativeEvaluator | None = None,
        ai_gateway: HostAIGateway | None = None,
        creative_director: Any | None = None,
        creative_validate: Any | None = None,
        extra_manifests: Any | None = None,
    ):
        self.store = store
        self.worker_timeout_sec = worker_timeout_sec
        self.blender_timeout_sec = blender_timeout_sec
        self.host_client = host_client
        self.lease_renew_sec = lease_renew_sec
        self.model_manifest = model_manifest
        self.model_catalog_manifest = model_catalog_manifest
        self.model_store_root = model_store_root
        self.hf_home = hf_home
        self.image_runtime_python = image_runtime_python
        self.creative_evaluator = creative_evaluator
        self.ai_gateway = ai_gateway
        # 演出の立案と検証。従来は画面が順番に呼び、途中結果をページが持って
        # いた。タブを閉じると失われるので、job の phase として持たせる。
        self.creative_director = creative_director
        self.creative_validate = creative_validate
        # 自作モデルは shipped manifest に居ない。routing がそれを知らないと、
        # 利用者が選べる状態にしても「使えるモデルがありません」で落ちる。
        self.extra_manifests = extra_manifests
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        # AI ターン終了の宣言結果。lease が取れなかったときに理由を添えるために持つ。
        self._ai_release: dict[str, HostAIReleaseResult] = {}
        self._runner: asyncio.Task[None] | None = None
        self._job_tasks: dict[str, asyncio.Task[None]] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._host_executions: dict[str, HostExecution] = {}
        self._host_failures: dict[str, HostApiError] = {}
        self._selected_models: dict[str, ModelDescriptor] = {}
        # 選択の根拠。provenance と UI に「なぜこのモデルか」を出すために持つ。
        self._routes: dict[str, ModelRoute] = {}
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

    def model_in_use(self, model_id: str) -> bool:
        return any(model.model_id == model_id for model in self._selected_models.values())

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
        job = self.store.create_job(request, profile_snapshot=self.resolve_profiles(request))
        self._queue.put_nowait(job.id)
        return job

    def submit_hosted(
        self,
        request: JobRequest,
        execution: HostExecution,
        *,
        profile_snapshot: dict[str, Any] | None = None,
    ) -> Job:
        if self.host_client is None:
            raise RuntimeError("ControlDeck Host client is not configured")
        job = self.store.create_job(
            request,
            host_managed=True,
            profile_snapshot=profile_snapshot if profile_snapshot is not None else self.resolve_profiles(request),
        )
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
            self._routes.pop(job_id, None)
            self._job_tasks.pop(job_id, None)
            self._queue.task_done()

    async def _execute(self, job_id: str) -> None:
        try:
            job = self.store.executable_job(job_id)
        except UnreadableJobRecord:
            # 表示は degraded で続けられるが、実行は fail-closed にする。
            # 現在の契約で読めない指示を推測で実行しない。
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=ErrorDetail(
                    code="job_record_unreadable",
                    message="this job record cannot be read by the current contract",
                ),
            )
            return
        if job.status != JobStatus.QUEUED or self.store.cancel_requested(job_id):
            return
        if job.request.operation not in {"image.generate", "image.edit", "asset.pack"}:
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=ErrorDetail(
                    code="capability_unavailable",
                    message=f"{job.request.operation} has no measured local runtime",
                ),
            )
            return
        execution = self._host_executions.get(job_id)
        reporter = (
            HostJobReporter(self.host_client, execution)
            if execution is not None and self.host_client is not None
            else None
        )
        if job.request.operation == "asset.pack":
            control: asyncio.Task[None] | None = None
            try:
                if execution is not None:
                    control = asyncio.create_task(
                        self._maintain_host_control(job_id, execution),
                        name=f"media-forge-host-control-{job_id}",
                    )
                self._validate_input_assets(job)
                if job.request.profile == "3d.project.glb":
                    await self._execute_3d_pack(job, reporter)
                else:
                    await self._execute_m5_pack(job, reporter)
            except WorkerFailure as exc:
                await self._update(
                    job_id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="validate_request",
                    progress=1,
                    error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
                )
            finally:
                if control is not None:
                    control.cancel()
                    await asyncio.gather(control, return_exceptions=True)
            return
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
                job = await self._prepare_creative(job, reporter)
            except WorkerFailure as exc:
                await self._update(
                    job_id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="direct",
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
                if selected is not None:
                    # 生成の前に AI ターンを閉じる。lease は取らずに宣言だけ行う。
                    # 先に AI 常駐を落としてから受理を求めるので、以後の LLM 再
                    # ロードは broker の受理を通る。二重予約も deadlock も起きない。
                    await self._release_host_ai(job, execution, reporter, selected)
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
                await self._execute_worker(
                    job_id,
                    reporter,
                    execution=execution,
                    maintenance=maintenance,
                )
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
            extra_models, extra_catalog = (
                self.extra_manifests() if self.extra_manifests is not None else ([], [])
            )
            models = ModelRegistry.load(
                self.model_manifest,
                hf_home=self.hf_home,
                catalog_manifest=self.model_catalog_manifest,
                model_store_root=self.model_store_root,
                extra_models=extra_models,
                extra_catalog=extra_catalog,
            ).all()
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
            decision = route(
                models,
                capability=capability,
                policy=job.request.model_policy,
                model_id=job.request.model_id,
                hardware_backend="rocm",
                # ControlDeck performs live admission against current free VRAM.
                free_vram_bytes=2**63 - 1,
                domain=self._job_domain(job),
            )
            self._validate_generation_limits(job, decision.model)
            self._routes[job.id] = decision
            return decision.model
        except ModelRouteError as exc:
            raise WorkerFailure(exc.code, str(exc)) from exc

    def _route_summary(self, job_id: str) -> dict[str, Any]:
        decision = self._routes[job_id]
        return {
            "policy": decision.policy,
            "capability": decision.capability,
            "domain": decision.domain,
            "domain_matched": decision.domain_matched,
            "candidate_count": decision.candidate_count,
        }

    @staticmethod
    def _job_domain(job: Job) -> str:
        plan = job.request.constraints.get("creative_plan")
        if not isinstance(plan, dict):
            return "general"
        domain = plan.get("domain")
        if isinstance(domain, dict):
            return str(domain.get("id") or "general")
        return "general"

    def _model_capability(self, job: Job) -> str:
        if self.store.job_profile_snapshot(job.id).get("reference_asset_ids"):
            return "image.multi_reference_edit"
        if job.request.operation == "image.generate":
            return "image.text_to_image"
        if job.request.constraints.get("edit_mode") == "outpaint":
            return "image.outpaint"
        if job.request.constraints.get("edit_mode") == "multi_reference":
            return "image.multi_reference_edit"
        if job.request.constraints.get("edit_mode") == "variation":
            return "image.variation"
        return (
            "image.strict_edit"
            if job.request.constraints.get("strict_edit") is True
            else "image.single_reference_edit"
        )

    def host_identity(self, job_id: str) -> HostIdentity | None:
        """The Host identity this job runs under, when it has one.

        Direction and evaluation both need it to reach the AI gateway. A local
        job simply has none, and those steps degrade rather than fail.
        """
        execution = self._host_executions.get(job_id)
        return execution.identity if execution is not None else None

    def resolve_profiles(self, request: JobRequest) -> dict[str, Any]:
        requested = {
            "character": request.constraints.get("character_profile_id"),
            "style": request.constraints.get("style_profile_id"),
        }
        requested_role_values = request.constraints.get("creative_plan", {}).get("reference_roles", [])
        if all(value is None for value in requested.values()) and not requested_role_values:
            return {}
        profiles: dict[str, Any] = {}
        reference_asset_ids: list[str] = []
        prompt_parts: list[str] = []
        for expected_kind, profile_id in requested.items():
            if profile_id is None:
                continue
            if not isinstance(profile_id, str):
                raise ProfileResolutionError(
                    "invalid_profile_id", f"{expected_kind} profile ID must be a string"
                )
            try:
                profile = self.store.get_profile(profile_id)
            except KeyError as exc:
                raise ProfileResolutionError(
                    "profile_not_found", f"{expected_kind} profile was not found"
                ) from exc
            if profile.kind != expected_kind:
                raise ProfileResolutionError(
                    "profile_kind_mismatch", f"expected a {expected_kind} profile"
                )
            collection = None
            if profile.reference_collection_id is not None:
                try:
                    collection = self.store.get_reference_collection(profile.reference_collection_id)
                except KeyError as exc:
                    raise ProfileResolutionError(
                        "reference_collection_not_found", "profile reference collection was not found"
                    ) from exc
                for asset_id in collection.asset_ids:
                    try:
                        asset = self.store.get_asset(asset_id)
                    except KeyError as exc:
                        raise ProfileResolutionError(
                            "reference_asset_not_found", "profile reference asset was not found"
                        ) from exc
                    if asset.mime_type != "image/png":
                        raise ProfileResolutionError(
                            "unsupported_reference", "profile references must be PNG assets"
                        )
                    if asset_id not in reference_asset_ids:
                        reference_asset_ids.append(asset_id)
            profiles[expected_kind] = {
                "profile": profile.model_dump(mode="json"),
                "reference_collection": collection.model_dump(mode="json") if collection else None,
            }
            prompt_parts.append(profile_prompt(profile))
        combined_references = list(dict.fromkeys(
            [item.asset_id for item in request.inputs] + reference_asset_ids
        ))
        if len(combined_references) > 4:
            raise ProfileResolutionError(
                "profile_reference_limit",
                "combined job and profile references may contain at most four assets",
            )
        inferred_roles: dict[str, str] = {}
        for expected_kind, value in profiles.items():
            collection_value = value.get("reference_collection")
            if not isinstance(collection_value, dict):
                continue
            stored_roles = collection_value.get("roles", {})
            for asset_id in collection_value.get("asset_ids", []):
                inferred_roles[str(asset_id)] = str(stored_roles.get(asset_id, expected_kind))
        role_values = requested_role_values
        if not isinstance(role_values, list) or len(role_values) > 4:
            raise ProfileResolutionError("invalid_reference_roles", "reference roles are invalid")
        role_overrides: dict[str, dict[str, Any]] = {}
        allowed_roles = {
            "identity", "style", "pose", "composition", "clothing", "palette", "prop", "environment"
        }
        for value in role_values:
            if not isinstance(value, dict) or set(value) != {"asset_id", "role", "strength"}:
                raise ProfileResolutionError("invalid_reference_roles", "reference roles are invalid")
            asset_id = value.get("asset_id")
            role = value.get("role")
            strength = value.get("strength")
            if (
                asset_id not in combined_references
                or role not in allowed_roles
                or not isinstance(strength, (int, float))
                or isinstance(strength, bool)
                or not 0 <= float(strength) <= 1
                or asset_id in role_overrides
            ):
                raise ProfileResolutionError("invalid_reference_roles", "reference roles are invalid")
            role_overrides[str(asset_id)] = {
                "asset_id": str(asset_id), "role": str(role), "strength": float(strength)
            }
        role_asset_ids = list(dict.fromkeys([*reference_asset_ids, *role_overrides]))
        resolved_roles = [
            role_overrides.get(asset_id, {
                "asset_id": asset_id,
                "role": inferred_roles.get(asset_id, "identity"),
                "strength": 1.0,
            })
            for asset_id in role_asset_ids
        ]
        if resolved_roles:
            prompt_parts.append(
                "Reference image roles: " + ", ".join(item["role"] for item in resolved_roles)
            )
        return {
            "profiles": profiles,
            "reference_asset_ids": reference_asset_ids,
            "reference_roles": resolved_roles,
            "prompt": "\n".join(prompt_parts),
        }

    def _validate_input_assets(self, job: Job) -> None:
        if job.request.operation == "asset.pack":
            if job.request.profile == "3d.project.glb":
                if (
                    job.request.output.format != "zip"
                    or job.request.output.count != 1
                    or job.request.model_policy != "auto"
                    or job.request.qa.semantic
                    or job.request.qa.max_regeneration_attempts != 0
                ):
                    raise WorkerFailure(
                        "unsupported_pack_profile",
                        "3d.project.glb requires one deterministic ZIP output with automatic routing",
                    )
                try:
                    parse_compile_options(job.request.constraints)
                except BlenderCompileError as exc:
                    raise WorkerFailure("invalid_compile_options", str(exc)) from exc
                if len(job.request.inputs) != 1:
                    raise WorkerFailure("invalid_pack", "3d.project.glb requires exactly one input asset")
                try:
                    source = self.store.get_asset(job.request.inputs[0].asset_id)
                except KeyError as exc:
                    raise WorkerFailure("asset_not_found", "3D source asset was not found") from exc
                if source.mime_type != "model/gltf-binary":
                    raise WorkerFailure("unsupported_reference", "3d.project.glb requires one GLB input")
                return
            if (
                job.request.profile != "m5.companion.pack"
                or job.request.output.format != "zip"
                or job.request.output.count != 1
                or job.request.model_policy != "auto"
                or job.request.qa.semantic
                or job.request.qa.max_regeneration_attempts != 0
            ):
                raise WorkerFailure(
                    "unsupported_pack_profile",
                    "asset.pack requires one deterministic m5.companion.pack ZIP output",
                )
            if set(job.request.constraints) != {"pack_name", "entries"}:
                raise WorkerFailure("invalid_pack", "M5 companion pack constraints are pack_name and entries only")
            try:
                entries = parse_m5_pack_entries(job.request.constraints.get("entries"))
            except M5CompanionError as exc:
                raise WorkerFailure("invalid_pack", str(exc)) from exc
            requested = [item.asset_id for item in job.request.inputs]
            mapped = [entry.asset_id for entry in entries]
            if len(set(requested)) != len(requested) or set(requested) != set(mapped):
                raise WorkerFailure("invalid_pack", "pack entries must map every input asset exactly once")
            try:
                assets = [self.store.get_asset(asset_id) for asset_id in requested]
            except KeyError as exc:
                raise WorkerFailure("asset_not_found", "pack input asset was not found") from exc
            if any(asset.mime_type != "image/png" for asset in assets):
                raise WorkerFailure("unsupported_reference", "M5 companion packs require PNG inputs")
            return
        if is_m5_profile(job.request.profile):
            if job.request.profile == "m5.companion.pack" or job.request.operation not in {
                "image.generate", "image.edit"
            }:
                raise WorkerFailure("unsupported_profile", "M5 companion profile does not match the operation")
            if (
                job.request.output.format != "png"
                or job.request.constraints.get("width") != 1280
                or job.request.constraints.get("height") != 960
            ):
                raise WorkerFailure(
                    "invalid_dimensions", "M5 companion image jobs require exact 1280x960 PNG output"
                )
        if job.request.operation != "image.edit":
            return
        edit_mode = job.request.constraints.get("edit_mode", "reference")
        expected_multi = edit_mode == "multi_reference"
        if (expected_multi and not 2 <= len(job.request.inputs) <= 4) or (
            not expected_multi and len(job.request.inputs) != 1
        ):
            raise WorkerFailure(
                "invalid_reference_count",
                "multi-reference edit requires 2..4 inputs; other image.edit modes require exactly one",
            )
        try:
            source = self.store.get_asset(job.request.inputs[0].asset_id)
            source_path = self.store.asset_path(source.id)
        except KeyError as exc:
            raise WorkerFailure("asset_not_found", "source image asset was not found") from exc
        try:
            references = [self.store.get_asset(item.asset_id) for item in job.request.inputs[1:]]
        except KeyError as exc:
            raise WorkerFailure("asset_not_found", "reference image asset was not found") from exc
        if source.mime_type != "image/png" or any(item.mime_type != "image/png" for item in references):
            raise WorkerFailure("unsupported_reference", "image.edit currently requires PNG source assets")
        if is_m5_profile(job.request.profile):
            try:
                validate_m5_image(source_path, str(job.request.profile))
            except M5CompanionError as exc:
                raise WorkerFailure("m5_validation_failed", str(exc)) from exc
        strict = job.request.constraints.get("strict_edit", False)
        if not isinstance(strict, bool):
            raise WorkerFailure("invalid_constraint", "strict_edit must be a boolean")
        if edit_mode not in {"reference", "variation", "inpaint", "outpaint", "multi_reference"}:
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
        if edit_mode == "multi_reference" and strict:
            raise WorkerFailure("invalid_constraint", "multi-reference edit cannot request strict_edit")
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
        if is_m5_profile(job.request.profile):
            try:
                validate_m5_edit_mask(mask_path, str(job.request.profile))
            except M5CompanionError as exc:
                raise WorkerFailure("invalid_edit_mask", str(exc)) from exc

    async def _execute_m5_pack(self, job: Job, reporter: HostJobReporter | None) -> None:
        await self._update(job.id, reporter, status=JobStatus.RUNNING, phase="validate", progress=0.1)
        root = contained(self.store.work_dir, self.store.work_dir / job.id)
        root.mkdir(mode=0o700)
        output = contained(root, root / "companion-pack.zip")
        entries = parse_m5_pack_entries(job.request.constraints.get("entries"))
        assets = {entry.asset_id: self.store.get_asset(entry.asset_id) for entry in entries}
        paths = {asset_id: self.store.asset_path(asset_id) for asset_id in assets}
        hashes = {asset_id: asset.sha256 for asset_id, asset in assets.items()}
        try:
            manifest, validation = await asyncio.to_thread(
                build_m5_pack,
                output,
                pack_name=str(job.request.constraints.get("pack_name", "companion")),
                entries=entries,
                asset_paths=paths,
                asset_hashes=hashes,
            )
        except M5CompanionError as exc:
            raise WorkerFailure("m5_validation_failed", str(exc)) from exc
        if output.stat().st_size > MAX_ARTIFACT_BYTES:
            raise WorkerFailure("artifact_too_large", "M5 companion pack exceeded the 64 MiB artifact bound")
        await self._update(job.id, reporter, phase="register_asset", progress=0.9)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        now = utc_now()
        asset_id = f"asset_{uuid.uuid4().hex}"
        provenance_id = f"prov_{uuid.uuid4().hex}"
        parent_ids = [entry.asset_id for entry in entries]
        pack_name = str(job.request.constraints.get("pack_name", "companion"))
        asset = Asset(
            id=asset_id,
            job_id=job.id,
            parent_asset_ids=parent_ids,
            mime_type="application/zip",
            width=None,
            height=None,
            size_bytes=output.stat().st_size,
            sha256=digest,
            suggested_filename=f"{pack_name}-m5-companion.zip",
            provenance_id=provenance_id,
            created_at=now,
        )
        provenance = Provenance(
            id=provenance_id,
            asset_id=asset_id,
            parent_asset_ids=parent_ids,
            operation="asset.pack",
            intent=job.request.intent,
            model_id="media-forge/m5-companion-packer",
            model_version="1.0.0",
            weights_hash="sha256:" + "0" * 64,
            license="derived-from-parent-assets",
            runtime_adapter="deterministic.m5-companion-pack",
            runtime_version="1.0.0",
            tool_versions={"media-forge": __version__, "m5.companion.pack": "1.0.0"},
            seed=0,
            parameters={
                "profile": job.request.profile,
                "pack_name": pack_name,
                "manifest": manifest,
            },
            reference_asset_hashes=hashes,
            postprocessing=["m5.validate", "m5.atlas", "zip.reproducible"],
            validation=validation,
            warnings=[],
            output_sha256=digest,
            created_at=now,
        )
        self.store.register_asset(asset, provenance, output)
        await self._update(
            job.id,
            reporter,
            status=JobStatus.SUCCEEDED,
            phase="package",
            progress=1,
            asset_ids=[asset.id],
        )

    async def _execute_3d_pack(self, job: Job, reporter: HostJobReporter | None) -> None:
        await self._update(job.id, reporter, status=JobStatus.RUNNING, phase="validate", progress=0.1)
        root = contained(self.store.work_dir, self.store.work_dir / job.id)
        root.mkdir(mode=0o700)
        source = self.store.get_asset(job.request.inputs[0].asset_id)
        try:
            options = parse_compile_options(job.request.constraints)
        except BlenderCompileError as exc:
            raise WorkerFailure("invalid_compile_options", str(exc)) from exc
        try:
            package, manifest, validation = await compile_project_package(
                self.store.asset_path(source.id),
                root,
                options=options,
                cancel_requested=lambda: self.store.cancel_requested(job.id),
                process_timeout_sec=self.blender_timeout_sec,
            )
        except BlenderCompileCanceled:
            await self._finish_canceled(job.id, reporter)
            return
        except BlenderCompileError as exc:
            raise WorkerFailure("blender_compile_failed", str(exc)) from exc
        if package.stat().st_size > MAX_ARTIFACT_BYTES:
            raise WorkerFailure("artifact_too_large", "3D project package exceeded the 64 MiB artifact bound")
        await self._update(job.id, reporter, phase="register_asset", progress=0.9)
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        now = utc_now()
        asset_id = f"asset_{uuid.uuid4().hex}"
        provenance_id = f"prov_{uuid.uuid4().hex}"
        asset = Asset(
            id=asset_id,
            job_id=job.id,
            parent_asset_ids=[source.id],
            mime_type="application/zip",
            width=None,
            height=None,
            size_bytes=package.stat().st_size,
            sha256=digest,
            suggested_filename=f"media-forge-project-{job.id[4:12]}.zip",
            provenance_id=provenance_id,
            created_at=now,
        )
        provenance = Provenance(
            id=provenance_id,
            asset_id=asset_id,
            parent_asset_ids=[source.id],
            operation="asset.pack",
            intent=job.request.intent,
            model_id="media-forge/blender-project-compiler",
            model_version=COMPILER_VERSION,
            weights_hash="sha256:" + "0" * 64,
            license="derived-from-parent-assets",
            runtime_adapter="blender.project-compiler",
            runtime_version=BLENDER_VERSION,
            tool_versions={
                "media-forge": __version__,
                "blender": BLENDER_VERSION,
                "compiler.3d-project": COMPILER_VERSION,
                "validator.glb": str(manifest["asset"]["validation_version"]),
            },
            seed=0,
            parameters={"profile": job.request.profile, "manifest": manifest},
            reference_asset_hashes={source.id: source.sha256},
            postprocessing=[str(item["id"]) for item in manifest["operations"]],
            validation=validation,
            warnings=[str(item) for item in manifest["warnings"]],
            output_sha256=digest,
            created_at=now,
        )
        self.store.register_asset(asset, provenance, package)
        await self._update(
            job.id,
            reporter,
            status=JobStatus.SUCCEEDED,
            phase="package",
            progress=1,
            asset_ids=[asset.id],
        )

    def _all_models(self) -> list[ModelDescriptor]:
        """自作分を含む全一覧。LoRA もここに載っている。

        routing と同じ一覧を使う。別に読むと、片方だけが知っている entry が
        できて「選べるのに使えない」が再発する（実測: 自作モデルがそうなった）。
        """
        if self.model_manifest is None or self.hf_home is None:
            return []
        extra_models, extra_catalog = (
            self.extra_manifests() if self.extra_manifests is not None else ([], [])
        )
        try:
            return list(ModelRegistry.load(
                self.model_manifest,
                hf_home=self.hf_home,
                catalog_manifest=self.model_catalog_manifest,
                model_store_root=self.model_store_root,
                extra_models=extra_models,
                extra_catalog=extra_catalog,
            ).all())
        except ModelRegistryError as exc:
            raise WorkerFailure("model_registry_invalid", str(exc)) from exc

    MAX_LORAS = 4

    def _requested_loras(self, job: Job) -> list[dict[str, Any]]:
        value = job.request.constraints.get("loras") or []
        if not isinstance(value, list):
            raise WorkerFailure("invalid_loras", "LoRA の指定が正しくありません")
        if len(value) > self.MAX_LORAS:
            raise WorkerFailure(
                "invalid_loras", f"LoRA は {self.MAX_LORAS} 個までです"
            )
        rows: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict) or not isinstance(item.get("model_id"), str):
                raise WorkerFailure("invalid_loras", "LoRA の指定が正しくありません")
            weight = item.get("weight", 1.0)
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 2:
                raise WorkerFailure("invalid_loras", "LoRA の強さは 0〜2 で指定してください")
            rows.append({"model_id": item["model_id"], "weight": float(weight)})
        return rows

    def _resolved_loras(self, job: Job, selected: ModelDescriptor) -> list[dict[str, Any]]:
        """要求された LoRA を、載せられるものだけに絞って経路に変える。

        系統が合わない LoRA は次元が合わずに落ちるか、運が悪いと形だけ通って
        絵が崩れる。落ちる方がまだよいが、どちらも起きる前にここで断る。
        """
        requested = self._requested_loras(job)
        if not requested:
            return []
        available = {item.model_id: item for item in self._all_models() if item.is_lora}
        target = normalize_base_model(selected.base_model)
        resolved: list[dict[str, Any]] = []
        for row in requested:
            lora = available.get(row["model_id"])
            if lora is None or not lora.installed or lora.local_path is None:
                raise WorkerFailure("lora_not_installed", f"{row['model_id']} が導入されていません")
            family = normalize_base_model(lora.base_model)
            if not target or family != target:
                raise WorkerFailure(
                    "lora_incompatible",
                    f"{lora.display_name or lora.model_id} は {lora.base_model} 用です。"
                    f"選んだモデルの系統（{selected.base_model or '不明'}）には載せられません",
                )
            path = lora.local_path if lora.local_path.is_file() else next(
                iter(sorted(lora.local_path.rglob("*.safetensors"))), None
            )
            if path is None:
                raise WorkerFailure("lora_not_installed", f"{row['model_id']} の本体が見つかりません")
            resolved.append({"id": lora.model_id, "path": str(path), "weight": row["weight"]})
        return resolved

    def _lora_trigger_words(self, job: Job, selected: ModelDescriptor) -> str:
        """載せる LoRA が要求する語をまとめる。

        既に prompt に入っている語は足さない。二重に入れても効きは強く
        ならないが、他の語の重みが薄まる。
        """
        try:
            rows = self._requested_loras(job)
        except WorkerFailure:
            return ""
        if not rows:
            return ""
        available = {item.model_id: item for item in self._all_models() if item.is_lora}
        existing = job.request.intent.lower()
        words: list[str] = []
        for row in rows:
            lora = available.get(row["model_id"])
            for word in (lora.trigger_words if lora else ()):
                if word.lower() not in existing and word not in words:
                    words.append(word)
        return ", ".join(words)

    def _resolved_request(self, job: Job, selected: ModelDescriptor) -> dict[str, Any]:
        """要求に、そのモデル本来の設定を埋めてから worker に渡す。

        worker は寸法も歩数も決めない。決めるのはここである。埋めないと
        worker 側の固定既定が全モデルに掛かり、蒸留済みでないモデルは必ず
        崩れる（SDXL を 4 歩で回した絵がそれだった）。

        利用者が指定した値は動かさない。指定が無かったところだけを埋める。
        寸法は、比を保ったままそのモデルが学習した面積に寄せる。総画素を
        増やすと、モデルが見たことのない広さになり同じ被写体が 2 つ並ぶ。
        """
        request = job.request.model_dump(mode="json")
        constraints = dict(request.get("constraints") or {})
        if constraints.get("steps") is None and selected.default_steps is not None:
            constraints["steps"] = selected.default_steps
        native = selected.native_width, selected.native_height
        width, height = constraints.get("width"), constraints.get("height")
        strict = (
            job.request.operation == "image.edit"
            and constraints.get("strict_edit") is True
        )
        if all(isinstance(side, int) for side in native) and not strict:
            # 編集は元画像の画面をそのまま使う。寄せると元と重ならなくなる。
            if width is None or height is None:
                constraints["width"], constraints["height"] = native
            elif isinstance(width, int) and isinstance(height, int):
                constraints["width"], constraints["height"] = snap_to_native(
                    width, height, int(native[0])
                )
        request["constraints"] = constraints
        return request

    def _validate_generation_limits(self, job: Job, selected: ModelDescriptor) -> None:
        # 詳細設定から来る値。範囲を外れたものは、worker が読み込みを終えて
        # から落ちるより、ここで理由を付けて返す方がよい。
        steps = job.request.constraints.get("steps")
        if steps is not None and (
            isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 50
        ):
            raise WorkerFailure("invalid_steps", "歩数は 1〜50 で指定してください")
        guidance = job.request.constraints.get("guidance_scale")
        if guidance is not None and (
            isinstance(guidance, bool)
            or not isinstance(guidance, (int, float))
            or not 0 <= guidance <= 30
        ):
            raise WorkerFailure("invalid_guidance_scale", "ガイダンスは 0〜30 で指定してください")
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
        if (
            job.request.operation == "image.edit"
            and job.request.constraints.get("strict_edit") is True
            and job.request.constraints.get("edit_mode") != "outpaint"
        ):
            mask_id = job.request.constraints.get("editable_mask_asset_id")
            try:
                assert source is not None and isinstance(mask_id, str)
                plan = strict_edit_plan(self.store.asset_path(source.id), self.store.asset_path(mask_id))
            except (AssertionError, KeyError, StrictEditError) as exc:
                raise WorkerFailure("invalid_edit_mask", "strict edit mask could not be bounded") from exc
            # Real strict edit generates only a context-bearing patch, then the
            # worker composes it onto the full canvas and core independently
            # checks protected pixels. Admit against that bounded inference,
            # conservatively including 64px context on each side.
            crop_width = plan.crop_box[2] - plan.crop_box[0]
            crop_height = plan.crop_box[3] - plan.crop_box[1]
            width = max(256, (crop_width + 128 + 15) // 16 * 16)
            height = max(256, (crop_height + 128 + 15) // 16 * 16)
        if width > selected.max_width or height > selected.max_height or width * height > selected.max_pixels:
            raise WorkerFailure(
                "resource_limit",
                "requested image dimensions exceed this model's measured generation envelope",
            )

    async def _execute_worker(
        self,
        job_id: str,
        reporter: HostJobReporter | None,
        *,
        execution: HostExecution | None = None,
        maintenance: asyncio.Task[None] | None = None,
    ) -> None:
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
                        # 系統ごとの既定。持たないモデルには送らない。
                        **({"negative_prompt": selected.negative_prompt}
                           if selected.negative_prompt else {}),
                        **({"guidance_scale": requested_guidance(job, selected)}
                           if requested_guidance(job, selected) is not None else {}),
                        # core が要求に埋めるので通常は使われない。worker を
                        # 単体で回す経路（評価・benchmark）のための控えである。
                        **({"default_steps": selected.default_steps}
                           if selected.default_steps is not None else {}),
                    },
                },
                "request": self._resolved_request(job, selected),
                "worker_output_dir": str(output_dir),
                "worker_inputs": {**worker_inputs, "loras": self._resolved_loras(job, selected)},
            }
        trigger = self._lora_trigger_words(job, selected) if selected is not None else ""
        if trigger:
            # 起動語を入れない LoRA は何も起こさない。足したことは job に残る。
            target = payload["request"]
            target["intent"] = f"{target.get('intent') or job.request.intent}, {trigger}"
        snapshot = self.store.job_profile_snapshot(job.id)
        if snapshot.get("prompt"):
            target = payload["request"] if selected is not None else payload
            target["intent"] = f"{job.request.intent}\n{snapshot['prompt']}"
        if job.request.qa.semantic:
            candidate_count = job.request.output.count + job.request.qa.max_regeneration_attempts
            target = payload["request"] if selected is not None else payload
            target["output"]["count"] = candidate_count
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
            # The heavyweight process may import only the worker pack and its
            # own runtime dependencies. Do not inherit a development
            # PYTHONPATH that can accidentally expose core implementations.
            environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
            environment["MEDIA_FORGE_MODEL_ROOT"] = str(selected.local_path.parents[1])
            # LoRA は別の repository に入るので、モデルの境界には収まらない。
            # 導入先として使っている根だけを許す。
            environment["MEDIA_FORGE_LORA_ROOTS"] = os.pathsep.join(
                str(root) for root in (self.model_store_root, self.hf_home) if root is not None
            )
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
        # The GPU worker is gone and its outputs are now ordinary files.  Release
        # the generation lease before deterministic post-processing can opt into
        # Host vision evaluation.  Keeping an exclusive image lease while asking
        # the Host to load its VLM creates a Broker deadlock on single-GPU hosts.
        if execution is not None:
            if maintenance is not None:
                maintenance.cancel()
                await asyncio.gather(maintenance, return_exceptions=True)
            if not await self._release_host_resource(execution):
                await self._update(
                    job_id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="release_resource",
                    error=ErrorDetail(
                        code="host_resource_release_failed",
                        message="ControlDeck did not confirm generation resource release",
                    ),
                )
                return
        await self._update(job_id, reporter, phase="postprocess", progress=0.65)
        try:
            asset_ids = await self._register_outputs(job, response, job_root)
        except CreativeEvaluationError as exc:
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="semantic_review",
                error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
            )
            return
        except WorkerFailure as exc:
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="semantic_review",
                error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
            )
            return
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
        except BriefDefectError as exc:
            # 用途に対して客観的に誤っている。予算の話ではないので、成功として
            # 返さず理由を名指しで失敗させる。作り直しは A3 の範囲。
            logger.info(
                "job %s does not satisfy its brief: %s",
                job_id,
                [item.document() for item in exc.defects],
            )
            await self._update(
                job_id,
                reporter,
                status=JobStatus.FAILED,
                phase="validate",
                error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
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

    def _materialize_worker_inputs(self, job: Job, job_root: Path) -> dict[str, Any]:
        snapshot = self.store.job_profile_snapshot(job.id)
        profile_asset_ids = snapshot.get("reference_asset_ids", [])
        if job.request.operation != "image.edit" and not profile_asset_ids:
            return {}
        inputs_dir = contained(job_root, job_root / "inputs")
        inputs_dir.mkdir(mode=0o700)
        result: dict[str, Any] = {}
        if job.request.operation == "image.edit":
            source_id = job.request.inputs[0].asset_id
            source_destination = contained(inputs_dir, inputs_dir / "source.png")
            shutil.copyfile(self.store.asset_path(source_id), source_destination)
            result["source_path"] = str(source_destination)
        reference_paths: list[str] = []
        for index, reference in enumerate(job.request.inputs[1:], start=1):
            destination = contained(inputs_dir, inputs_dir / f"reference-{index}.png")
            shutil.copyfile(self.store.asset_path(reference.asset_id), destination)
            reference_paths.append(str(destination))
        if reference_paths:
            result["reference_paths"] = reference_paths
        profile_reference_paths: list[str] = []
        direct_input_ids = {item.asset_id for item in job.request.inputs}
        for index, asset_id in enumerate(profile_asset_ids, start=1):
            if asset_id in direct_input_ids:
                continue
            destination = contained(inputs_dir, inputs_dir / f"profile-reference-{index}.png")
            shutil.copyfile(self.store.asset_path(str(asset_id)), destination)
            profile_reference_paths.append(str(destination))
        if profile_reference_paths:
            result["profile_reference_paths"] = profile_reference_paths
        if (
            job.request.constraints.get("strict_edit") is True
            and job.request.constraints.get("edit_mode") != "outpaint"
        ):
            mask_id = str(job.request.constraints["editable_mask_asset_id"])
            mask_destination = contained(inputs_dir, inputs_dir / "mask.png")
            shutil.copyfile(self.store.asset_path(mask_id), mask_destination)
            result["mask_path"] = str(mask_destination)
        return result

    async def _prepare_creative(self, job: Job, reporter: HostJobReporter | None) -> Job:
        """Run the direction and validation the browser used to orchestrate.

        These were three separate calls from the page, with the results held
        only in that page: the reference analysis, the director's plan, and the
        validated request. Nothing durable owned the sequence until
        `jobs.create` at the end, so closing the tab lost work that had already
        cost a VLM and an LLM turn — and the Host's "busy" warning was telling
        the truth about it.

        The job record already survives the browser, so the same steps run here
        as phases. Whatever the page still sends is honoured unchanged; this
        only takes over when the request asks for direction.
        """
        constraints = job.request.constraints or {}
        spec = constraints.get("creative_spec")
        mode = str(constraints.get("director_mode") or "original")
        if not isinstance(spec, dict) or self.creative_validate is None:
            return job

        request = job.request
        plan = None
        if mode != "original" and self.creative_director is not None:
            await self._update(job.id, reporter, phase="direct", progress=0.015)
            try:
                directed = await self.creative_director(job, spec, mode)
            except Exception:  # noqa: BLE001 - 演出が立たなくても生成は続ける
                logger.exception("creative direction failed for %s", job.id)
                directed = None
            if directed is not None:
                spec = directed.get("creative_spec", spec)
                plan = directed.get("plan")

        await self._update(job.id, reporter, phase="validate_request", progress=0.02)
        try:
            request = await self.creative_validate(job, request, spec, plan)
        except WorkerFailure:
            raise
        except Exception as exc:  # noqa: BLE001
            raise WorkerFailure("creative_validation_failed", str(exc)[:200]) from exc
        return self.store.replace_job_request(job.id, request)

    async def _release_host_ai(
        self,
        job: Job,
        execution: HostExecution,
        reporter: HostJobReporter | None,
        selected: ModelDescriptor | None = None,
    ) -> None:
        """Ask ControlDeck to end this add-on's AI turn before generation.

        Asking once is deliberate. ControlDeck's own chat, an OpenCode session,
        or another add-on may still be using the shared model, and retrying
        would starve them. A refusal is recorded, not fought: Broker admission
        still decides, and the reason only surfaces if admission then fails.
        """
        self._ai_release.pop(job.id, None)
        if self.ai_gateway is None:
            return
        await self._update(job.id, reporter, phase="release_ai", progress=0.02)
        try:
            # 何バイト要るのかを伝える。伝えないと、Host は「LLM を降ろした」
            # で終わりにする。実測: それでも 1.16GB の embedding が残り、
            # 33.35GB を要る画像モデルが 34.2GB のカードに入らなかった。
            result = await self.ai_gateway.release(
                execution.identity,
                required_bytes=(selected.measured_vram_bytes or 0) if selected else 0,
            )
        except Exception:  # noqa: BLE001 - 解放要求の失敗が生成を止めてはいけない
            logger.exception("failed to declare the AI turn finished for %s", job.id)
            return
        self._ai_release[job.id] = result
        logger.info(
            "ai turn released job=%s released=%s reason=%s freed_bytes=%d",
            job.id,
            result.released,
            result.reason,
            result.freed_bytes,
        )

    def _unverified_hard_constraints(self, job: Job) -> list[str]:
        """Hard constraints nobody in this run was in a position to check.

        Deterministic validation covers geometry, mode and alpha. It cannot
        read a picture, so a requirement like "no text in the image" is only
        ever checked by the evaluator, and the evaluator is off by default on
        purpose. Reporting them as unverified is the honest middle: no forced
        model swap, and no silent implication that the requirement held.
        """
        if job.request.qa.semantic:
            return []
        brief = job.request.constraints.get("asset_brief") if job.request.constraints else None
        if not isinstance(brief, dict):
            return []
        constraints = brief.get("hard_constraints")
        if not isinstance(constraints, list):
            return []
        return [str(item)[:200] for item in constraints if isinstance(item, str) and item.strip()]

    def _admission_failure(self, job_id: str, reason: str) -> ErrorDetail:
        """Name the retained AI residency instead of an anonymous admission failure."""
        release = self._ai_release.get(job_id)
        if release is not None and not release.released and reason in _VRAM_WAIT_REASONS:
            return ErrorDetail(
                code="host_ai_residency_retained",
                message=(
                    "ControlDeck kept its AI model resident, so no GPU capacity was "
                    f"admitted for generation (reason: {release.reason})"
                )[:300],
            )
        return ErrorDetail(
            code="resource_unavailable",
            message=f"ControlDeck admission failed: {reason}"[:300],
        )

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
                # A waiting request does not need a high-frequency busy poll.
                # Keeping this at two checks per second bounds Host traffic for
                # multi-cut jobs while retaining responsive cancellation.
                await asyncio.sleep(0.5)
                status = await self.host_client.resource_status(execution.identity, request_id)
            if status.get("state") != "granted" or not isinstance(status.get("lease_id"), str):
                reason = str(status.get("reason") or status.get("state") or "unknown")
                await self._update(
                    job.id,
                    reporter,
                    status=JobStatus.FAILED,
                    phase="waiting_resource",
                    error=self._admission_failure(job.id, reason),
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

    async def _maintain_host_control(self, job_id: str, execution: HostExecution) -> None:
        """Propagate Host cancellation for CPU-only work that has no GPU lease task."""
        try:
            while True:
                await asyncio.sleep(0.25)
                if await self._host_or_local_cancel_requested(job_id, execution):
                    return
        except asyncio.CancelledError:
            raise
        except HostApiError as exc:
            self._host_failures[job_id] = exc
            self.store.request_cancel(job_id)

    async def _host_or_local_cancel_requested(self, job_id: str, execution: HostExecution) -> bool:
        if self.store.cancel_requested(job_id):
            return True
        assert self.host_client is not None
        control = await self.host_client.job_control(execution.identity, execution.host_job_id)
        if control.get("cancel_requested") is True:
            self.store.request_cancel(job_id)
            return True
        return False

    async def _release_host_resource(self, execution: HostExecution) -> bool:
        if self.host_client is None:
            return True
        try:
            if execution.lease_id is not None:
                await self.host_client.lease_action(execution.identity, execution.lease_id, "release")
            elif execution.request_id is not None:
                await self.host_client.cancel_resource(execution.identity, execution.request_id)
        except HostApiError:
            logger.exception("failed to release ControlDeck resource state for %s", execution.host_job_id)
            return False
        execution.lease_id = None
        execution.request_id = None
        return True

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

    @staticmethod
    def _brief_context(job: Job) -> tuple[AssetBrief | None, ResolvedLayout | None]:
        """The brief this job was resolved against, for defect checks and evaluation."""
        try:
            brief = parse_brief(job.request.constraints.get("asset_brief"))
        except AssetBriefError:
            logger.warning("job %s carries an unreadable asset_brief", job.id)
            return None, None
        if brief is None:
            brief = infer_brief_from_intent(job.request.intent)
        recorded = job.request.constraints.get("resolved_layout")
        if brief is None or not isinstance(recorded, dict):
            return brief, None
        return brief, ResolvedLayout(
            width=int(recorded.get("width", 0)),
            height=int(recorded.get("height", 0)),
            alpha=bool(recorded.get("alpha", False)),
            source=str(recorded.get("source", "")),
            aspect_ratio=str(recorded.get("aspect_ratio", "")),
        )

    @staticmethod
    def _brief_defects(
        job: Job, width: int, height: int, validation: list[dict[str, Any]]
    ) -> list[BriefDefect]:
        """Compare the produced image against what the brief structurally required."""
        try:
            brief = parse_brief(job.request.constraints.get("asset_brief"))
        except AssetBriefError:
            # ingress で弾いているので、ここへ来た不正は記録だけして先へ進める。
            logger.warning("job %s carries an unreadable asset_brief", job.id)
            return []
        if brief is None:
            brief = infer_brief_from_intent(job.request.intent)
        recorded = job.request.constraints.get("resolved_layout")
        if brief is None or not isinstance(recorded, dict):
            return []
        resolved = ResolvedLayout(
            width=int(recorded.get("width", width)),
            height=int(recorded.get("height", height)),
            alpha=bool(recorded.get("alpha", False)),
            source=str(recorded.get("source", "")),
            aspect_ratio=str(recorded.get("aspect_ratio", "")),
        )
        has_alpha = any(
            item.get("validator") == "image.alpha" and item.get("has_transparency") is True
            for item in validation
        )
        return inspect_against_brief(
            brief, resolved, width=width, height=height, has_alpha=has_alpha
        )

    def _validate_output(
        self,
        job: Job,
        output: dict[str, Any],
        job_root: Path,
    ) -> tuple[Path, int, int, list[dict[str, Any]]]:
        path = contained(job_root, Path(output["path"]))
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError("worker artifact exceeded the 64 MiB limit")
        width, height, validation = validate_png(path)
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
        if strict_edit:
            mask_path = contained(job_root, job_root / "inputs" / "mask.png")
            assert source_path is not None
            validation.append(validate_strict_edit(source_path, mask_path, path))
        if outpaint:
            assert source_path is not None
            validation.append(validate_outpaint(
                source_path,
                path,
                width=int(job.request.constraints["width"]),
                height=int(job.request.constraints["height"]),
            ))
        if is_m5_profile(job.request.profile):
            try:
                validation.extend(validate_m5_image(path, str(job.request.profile)))
            except M5CompanionError as exc:
                raise ValueError(str(exc)) from exc
        return path, width, height, validation

    async def _evaluation_selection(
        self,
        job: Job,
        outputs: list[dict[str, Any]],
        validated: list[tuple[Path, int, int, list[dict[str, Any]]]],
    ) -> tuple[list[int], dict[int, tuple[dict[str, Any], list[str], str]]]:
        if not job.request.qa.semantic:
            return list(range(len(outputs))), {}
        execution = self._host_executions.get(job.id)
        identity = execution.identity if execution is not None else None
        target_count = job.request.output.count
        retry_budget = job.request.qa.max_regeneration_attempts
        if self.creative_evaluator is None or not await self.creative_evaluator.available(identity):
            selected = list(range(target_count))
            return selected, {
                index: (
                    {
                        "validator": "evaluation.unified",
                        "passed": True,
                        "available": False,
                        "reason": "vision_analyzer_unavailable",
                    },
                    ["unified evaluator unavailable; deterministic validation passed"],
                    "",
                )
                for index in selected
            }
        snapshot = self.store.job_profile_snapshot(job.id)
        reference_paths = tuple(
            self.store.asset_path(str(asset_id))
            for asset_id in snapshot.get("reference_asset_ids", [])
        )
        creative_plan = job.request.constraints.get("creative_plan", {})
        if not isinstance(creative_plan, dict):
            creative_plan = {}
        # 用途が分かっているなら、単体の美しさではなく用途への適合を訊く。
        brief, resolved_layout = self._brief_context(job)
        selected: list[int] = []
        reviews: dict[int, tuple[dict[str, Any], list[str], str]] = {}
        rejected = 0
        review_budget_used = 0
        for index, (path, _, _, _) in enumerate(validated):
            try:
                evaluated = await self.creative_evaluator.evaluate(
                    path,
                    job.request.intent,
                    creative_plan=creative_plan,
                    reference_paths=reference_paths,
                    identity=identity,
                    brief=brief,
                    resolved_layout=resolved_layout,
                )
            except CreativeEvaluationError as exc:
                selected.extend(
                    candidate for candidate in range(index, len(validated))
                    if candidate not in selected
                )
                selected = selected[:target_count]
                for candidate in selected:
                    reviews.setdefault(candidate, (
                        {
                            "validator": "evaluation.unified",
                            "passed": True,
                            "available": False,
                            "reason": exc.code,
                        },
                        ["unified evaluator unavailable; deterministic validation passed"],
                        "",
                    ))
                return selected, reviews
            review_budget_used += 1
            result = evaluated.result.model_copy(update={"review_budget_used": review_budget_used})
            validation = {
                "validator": "evaluation.unified",
                "passed": result.accepted_for_requested_constraints,
                "evaluation": result.model_dump(mode="json"),
                "relevant_dimensions": list(evaluated.relevant_dimensions),
            }
            if result.accepted_for_requested_constraints:
                selected.append(index)
                reviews[index] = (validation, [], evaluated.evaluator)
            elif retry_budget == 0:
                selected.append(index)
                reviews[index] = (
                    validation,
                    [f"evaluation advisory: {evaluated.summary}"],
                    evaluated.evaluator,
                )
            else:
                rejected += 1
            if len(selected) == target_count:
                return selected, reviews
            if rejected > retry_budget:
                break
        raise WorkerFailure(
            "semantic_review_exhausted",
            f"semantic review rejected all candidates within retry budget {retry_budget}",
        )

    async def _register_outputs(self, job: Job, response: dict[str, Any], job_root: Path) -> list[str]:
        outputs = response["outputs"]
        expected = job.request.output.count + (
            job.request.qa.max_regeneration_attempts if job.request.qa.semantic else 0
        )
        if not isinstance(outputs, list) or len(outputs) != expected:
            raise ValueError("worker returned an unexpected output count")
        model = response["model"]
        reference_hashes = {
            item.asset_id: self.store.get_asset(item.asset_id).sha256 for item in job.request.inputs
        }
        snapshot = self.store.job_profile_snapshot(job.id)
        for asset_id in snapshot.get("reference_asset_ids", []):
            reference_hashes[str(asset_id)] = self.store.get_asset(str(asset_id)).sha256
        if job.request.constraints.get("strict_edit") is True and job.request.constraints.get("edit_mode") != "outpaint":
            mask_id = str(job.request.constraints["editable_mask_asset_id"])
            reference_hashes[mask_id] = self.store.get_asset(mask_id).sha256
        # Complete every deterministic validation before invoking a subjective
        # reviewer. A semantic pass can therefore never mask file/invariant failure.
        validated = [self._validate_output(job, output, job_root) for output in outputs]
        # brief に対して客観的に誤っている候補を落とす。複数枚を頼まれている
        # のに 1 枚の defect で全部を捨てるのは、候補を出す意味を消してしまう。
        # ただし残りが 0 なら理由を名指しで失敗する。黙って返さない。
        defects = [
            self._brief_defects(job, width, height, validation)
            for _path, width, height, validation in validated
        ]
        usable = [index for index, found in enumerate(defects) if not found]
        if not usable:
            raise BriefDefectError(defects[0] if defects else [])
        dropped = len(validated) - len(usable)
        if dropped:
            logger.info(
                "job %s dropped %d candidate(s) that did not satisfy the brief: %s",
                job.id,
                dropped,
                [item.document() for found in defects for item in found],
            )
            outputs = [outputs[index] for index in usable]
            validated = [validated[index] for index in usable]
        brief_warnings = [
            f"{dropped} candidate(s) did not satisfy the asset brief and were discarded"
        ] if dropped else []
        # hard_constraints は「譲れない」と宣言されたものだが、その中身を確かめ
        # られるのは評価器だけである。既定で評価器を回さないのは意図した設計
        # （毎回の model 載せ替えを強いない）なので、ここでは回さない。
        # 黙るのは別で、A5 実行で "no text in the image" を宣言した資産が文字
        # 入りで返り、warnings は空だった。確かめていないことを、確かめたよう
        # に見せない。
        unverified = self._unverified_hard_constraints(job)
        if unverified:
            brief_warnings.append(
                "以下は宣言された必須条件ですが、この実行では検査していません"
                f"（qa.semantic を有効にすると検査します）: {'; '.join(unverified)}"
            )
        selected, evaluations = await self._evaluation_selection(job, outputs, validated)
        asset_ids: list[str] = []
        self.store.update_job(job.id, phase="validate", progress=0.75)
        for result_index, candidate_index in enumerate(selected):
            output = outputs[candidate_index]
            path, width, height, validation = validated[candidate_index]
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            review_validation, warnings, reviewer = evaluations.get(candidate_index, ({}, [], ""))
            warnings = [*brief_warnings, *warnings]
            if review_validation:
                validation.append(review_validation)
            now = utc_now()
            asset_id = f"asset_{uuid.uuid4().hex}"
            provenance_id = f"prov_{uuid.uuid4().hex}"
            parent_asset_ids = (
                [job.request.inputs[0].asset_id]
                if job.request.operation == "image.edit"
                else [item.asset_id for item in job.request.inputs]
            )
            asset = Asset(
                id=asset_id,
                job_id=job.id,
                parent_asset_ids=parent_asset_ids,
                mime_type="image/png",
                width=width,
                height=height,
                size_bytes=path.stat().st_size,
                sha256=sha256,
                suggested_filename=f"media-forge-{job.id[4:12]}-{result_index + 1}.png",
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
                tool_versions={
                    "media-forge": __version__,
                    "validator.png": "1.0.0",
                    **({"evaluator.unified": reviewer} if reviewer else {}),
                },
                seed=int(output.get("seed", response["seed"])),
                parameters={
                    "model_policy": job.request.model_policy,
                    "constraints": job.request.constraints,
                    "output": job.request.output.model_dump(mode="json"),
                    # なぜこのモデルが選ばれたか。provenance にしか置かない。
                    # 生成応答や capability discovery にモデル名を出さない規約
                    # （AGENTS.md 7 / docs/api.md）を保つ。
                    **({"model_route": self._route_summary(job.id)} if self._routes.get(job.id) else {}),
                    **({"resolved_profiles": snapshot.get("profiles", {})} if snapshot else {}),
                },
                reference_asset_hashes=reference_hashes,
                postprocessing=[str(item) for item in response.get("postprocessing", [])],
                validation=validation,
                warnings=warnings,
                output_sha256=sha256,
                created_at=now,
            )
            self.store.update_job(job.id, phase="package", progress=0.85)
            self.store.update_job(job.id, phase="register_asset", progress=0.92)
            self.store.register_asset(asset, provenance, path)
            asset_ids.append(asset_id)
        return asset_ids
