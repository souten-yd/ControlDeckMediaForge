from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.jobs import HostExecution, HostJobReporter
from .models import (
    ModelDescriptor,
    ModelOperation,
    ModelOperationAction,
    ModelOperationError,
    ModelOperationState,
    ModelRegistry,
    ModelRegistryError,
)
from .config import REPOSITORY_ROOT
from .paths import contained
from .store import Store


H3_MODEL_ID = "unsloth/MiniMax-H3-GGUF"
H3_RUNTIME_ADAPTER = "native.stable-diffusion-cpp-minimax-h3"
H3_RUNTIME_COMMIT = "97d2990807fe6d558e395f8764198d7c7e7b411c"
H3_ESTIMATED_RUNTIME_SEC = 1800.0
H3_EXECUTION_PEAK_BYTES = 30_000_000_000
H3_COLD_LOAD_PEAK_BYTES = 32_000_000_000
H3_HEADROOM_BYTES = 1024 * 1024 * 1024
H3_EVALUATION_WIDTH = 640
H3_EVALUATION_HEIGHT = 384
H3_EVALUATION_STEPS = 1
H3_EVALUATION_FRAMES = 5
H3_EVALUATION_PRESET = "bounded_smoke"
H3_EVALUATION_PROMPT = (
    "Integrated multimodal description: An adult boyish young woman in a polished anime illustration style, "
    "with short dark hair and vivid orange mesh highlights, smiles warmly at the viewer. In one continuous "
    "locked medium shot she raises one hand for a small friendly wave and gives a single playful wink; her "
    "face, outfit, proportions, and orange highlights remain consistent. Clean linework, soft warm lighting, "
    "stable background, restrained natural motion, no camera shake, no text. Overall soundscape: a quiet indoor "
    "room with a faint natural clothing rustle synchronized to the wave. Non-diegetic music: none."
)
WAN_MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B"
WAN_RUNTIME_ADAPTER = "native.wan2.2"
WAN_MODEL_REVISION = "921dbaf3f1674a56f47e83fb80a34bac8a8f203e"
WAN_SOURCE_REVISION = "42bf4cfaa384bc21833865abc2f9e6c0e67233dc"
WAN_SOURCE_PATCH_SHA256 = "4fd9b36b24f3385057445de8551c79b947498f253c061f56a457dc42a21afb93"
WAN_ESTIMATED_RUNTIME_SEC = 1800.0
WAN_EXECUTION_PEAK_BYTES = 30_700_000_000
WAN_COLD_LOAD_PEAK_BYTES = 30_700_000_000
WAN_HEADROOM_BYTES = 1024 * 1024 * 1024
HUNYUAN_MODEL_ID = "tencent/HunyuanVideo-1.5"
HUNYUAN_RUNTIME_ADAPTER = "native.hunyuan-video-1.5"
HUNYUAN_MODEL_REVISION = "9b49404b3f5df2a8f0b31df27a0c7ab872e7b038"
HUNYUAN_CONVERSION_REVISION = "1abb14f06518f37448dcf3a6917dd086dd7045c7"
HUNYUAN_ESTIMATED_RUNTIME_SEC = 3600.0
HUNYUAN_EXECUTION_PEAK_BYTES = 30_700_000_000
HUNYUAN_COLD_LOAD_PEAK_BYTES = 32_000_000_000
HUNYUAN_HEADROOM_BYTES = 1024 * 1024 * 1024
COGVIDEOX2B_MODEL_ID = "zai-org/CogVideoX-2b"
COGVIDEOX2B_RUNTIME_ADAPTER = "diffusers.cogvideox"
COGVIDEOX2B_MODEL_REVISION = "1137dacfc2c9c012bed6a0793f4ecf2ca8e7ba01"
COGVIDEOX2B_ESTIMATED_RUNTIME_SEC = 3600.0
COGVIDEOX2B_EXECUTION_PEAK_BYTES = 30_700_000_000
COGVIDEOX2B_COLD_LOAD_PEAK_BYTES = 32_000_000_000
COGVIDEOX2B_HEADROOM_BYTES = 1024 * 1024 * 1024
WAN21_VACE_MODEL_ID = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"
WAN21_VACE_RUNTIME_ADAPTER = "diffusers.wan2.1-vace"
WAN21_VACE_MODEL_REVISION = "ec4d2cb062b548996b179d493fdd05340de702a1"
WAN21_VACE_ESTIMATED_RUNTIME_SEC = 3600.0
WAN21_VACE_EXECUTION_PEAK_BYTES = 30_700_000_000
WAN21_VACE_COLD_LOAD_PEAK_BYTES = 32_000_000_000
WAN21_VACE_HEADROOM_BYTES = 1024 * 1024 * 1024
logger = logging.getLogger("uvicorn.error")


@dataclass
class RuntimeMetrics:
    started_at: float
    baseline_vram_bytes: int
    baseline_pswpin: int
    baseline_pswpout: int
    peak_rss_bytes: int = 0
    peak_process_swap_bytes: int = 0
    peak_vram_bytes: int = 0


class H3ModelEvaluator:
    """Private, bounded native-model evaluator backed by a real Host Job and lease."""

    def __init__(
        self,
        store: Store,
        host: ControlDeckHostClient,
        *,
        model_manifest: Path,
        catalog_manifest: Path,
        model_store_root: Path,
        hf_home: Path,
        runtime_root: Path,
        wan_runtime_python: Path | None = None,
        wan_source_root: Path | None = None,
        wan_evaluation_preset: str = "smoke",
        hunyuan_runtime_python: Path | None = None,
        hunyuan_snapshot_root: Path | None = None,
        hunyuan_evaluation_preset: str = "smoke",
        cogvideox2b_runtime_python: Path | None = None,
        cogvideox2b_snapshot_root: Path | None = None,
        cogvideox2b_evaluation_preset: str = "smoke",
        wan21_vace_runtime_python: Path | None = None,
        wan21_vace_snapshot_root: Path | None = None,
        wan21_vace_evaluation_preset: str = "smoke",
        lease_renew_sec: float,
        timeout_sec: float,
        command_builder: Callable[[ModelDescriptor, Path, Path], list[str]] | None = None,
        artifact_validator: Callable[[Path], dict[str, Any]] | None = None,
        vram_probe: Callable[[], int] | None = None,
        model_resolver: Callable[[str], ModelDescriptor] | None = None,
        registry_loader: Callable[[], list[ModelDescriptor]] | None = None,
        image_runtime_python: Path | None = None,
        image_measure: Callable[..., Any] | None = None,
        record_measurement: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self.store = store
        self.host = host
        self.model_manifest = model_manifest
        self.catalog_manifest = catalog_manifest
        self.model_store_root = model_store_root.resolve()
        self.hf_home = hf_home.resolve()
        self.runtime_root = runtime_root.resolve()
        self.wan_runtime_python = (
            Path(os.path.abspath(wan_runtime_python)) if wan_runtime_python is not None else None
        )
        self.wan_source_root = wan_source_root.resolve() if wan_source_root is not None else None
        if wan_evaluation_preset not in {
            "smoke", "quality-frame", "short-clip", "practical-clip", "candidate-clip",
            "candidate-hq-clip"
        }:
            raise ValueError("Wan evaluation preset is invalid")
        self.wan_evaluation_preset = wan_evaluation_preset
        self.hunyuan_runtime_python = (
            Path(os.path.abspath(hunyuan_runtime_python))
            if hunyuan_runtime_python is not None else None
        )
        self.hunyuan_snapshot_root = (
            hunyuan_snapshot_root.resolve() if hunyuan_snapshot_root is not None else None
        )
        if hunyuan_evaluation_preset not in {"smoke", "candidate-clip", "official-clip"}:
            raise ValueError("Hunyuan evaluation preset is invalid")
        self.hunyuan_evaluation_preset = hunyuan_evaluation_preset
        self.cogvideox2b_runtime_python = (
            Path(os.path.abspath(cogvideox2b_runtime_python))
            if cogvideox2b_runtime_python is not None else None
        )
        self.cogvideox2b_snapshot_root = (
            cogvideox2b_snapshot_root.resolve() if cogvideox2b_snapshot_root is not None else None
        )
        if cogvideox2b_evaluation_preset not in {"smoke", "official-clip"}:
            raise ValueError("CogVideoX-2B evaluation preset is invalid")
        self.cogvideox2b_evaluation_preset = cogvideox2b_evaluation_preset
        self.wan21_vace_runtime_python = (
            Path(os.path.abspath(wan21_vace_runtime_python))
            if wan21_vace_runtime_python is not None else None
        )
        self.wan21_vace_snapshot_root = (
            wan21_vace_snapshot_root.resolve() if wan21_vace_snapshot_root is not None else None
        )
        if wan21_vace_evaluation_preset not in {"smoke", "candidate-clip", "official-clip"}:
            raise ValueError("Wan 2.1 VACE evaluation preset is invalid")
        self.wan21_vace_evaluation_preset = wan21_vace_evaluation_preset
        self.output_root = (store.data_dir / "model-evaluations").resolve()
        self.lease_renew_sec = lease_renew_sec
        self.timeout_sec = timeout_sec
        self.command_builder = command_builder or self._command
        self._custom_artifact_validator = artifact_validator is not None
        self.artifact_validator = artifact_validator or self._validate_artifact
        self.vram_probe = vram_probe or self._r9700_vram_used
        self.model_resolver = model_resolver
        # 自作モデルは shipped manifest に居ないので、custom entry まで含めた
        # 一覧を持っている側から渡してもらう。
        self.registry_loader = registry_loader
        self.image_runtime_python = image_runtime_python
        self.image_measure = image_measure
        self.record_measurement = record_measurement
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._host_failures: dict[str, HostApiError] = {}
        self._guard = asyncio.Semaphore(1)

    async def start(self) -> None:
        self.output_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    async def stop(self) -> None:
        tasks = list(self._tasks.values())
        for operation_id in list(self._processes):
            await self._terminate(operation_id)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def available_model_ids(self) -> list[str]:
        """Every installed model that can actually be measured here.

        Was a single hardcoded entry, which meant the workspace told people to
        "評価で確かめてください" while offering the control on one model. Any
        installed diffusers model can be run once and measured; that is the
        whole procedure.
        """
        found: list[str] = []
        try:
            model = self._model(H3_MODEL_ID)
            self._preflight(model)
            found.append(H3_MODEL_ID)
        except (ModelOperationError, OSError):
            pass
        try:
            model = self._model(COGVIDEOX2B_MODEL_ID)
            self._preflight(model)
            found.append(COGVIDEOX2B_MODEL_ID)
        except (ModelOperationError, OSError):
            pass
        try:
            model = self._model(WAN_MODEL_ID)
            self._preflight(model)
            found.append(WAN_MODEL_ID)
        except (ModelOperationError, OSError):
            pass
        try:
            model = self._model(HUNYUAN_MODEL_ID)
            self._preflight(model)
            found.append(HUNYUAN_MODEL_ID)
        except (ModelOperationError, OSError):
            pass
        try:
            model = self._model(WAN21_VACE_MODEL_ID)
            self._preflight(model)
            found.append(WAN21_VACE_MODEL_ID)
        except (ModelOperationError, OSError):
            pass
        for model in self._image_candidates():
            found.append(model.model_id)
        return found

    def _image_candidates(self) -> list[ModelDescriptor]:
        if self.image_measure is None or self.image_runtime_python is None:
            return []
        if not self.image_runtime_python.is_file():
            return []
        if self.registry_loader is None:
            return []
        try:
            models = self.registry_loader()
        except (ModelRegistryError, OSError):
            return []
        return [
            model for model in models
            if model.installed
            and model.local_path is not None
            and "image" in model.media_types
            and model.runtime_adapter.startswith("diffusers.")
            # 既に測ってあるものを測り直す道は、ここでは出さない。
            and model.measurement_confidence != "measured"
        ]

    def evaluate(self, model_id: str, identity: HostIdentity) -> ModelOperation:
        missing = {"jobs.write", "resources.acquire"} - identity.granted_capabilities
        if missing:
            raise ModelOperationError("host_capability_not_granted", "Host evaluation capabilities are unavailable")
        if model_id not in {
            H3_MODEL_ID, WAN_MODEL_ID, HUNYUAN_MODEL_ID, COGVIDEOX2B_MODEL_ID, WAN21_VACE_MODEL_ID
        } and model_id not in {
            model.model_id for model in self._image_candidates()
        }:
            raise ModelOperationError("model_evaluation_unsupported", "model has no bounded evaluation preset")
        active = next(
            (
                item for item in self.store.list_model_operations()
                if item.model_id == model_id
                and item.action == ModelOperationAction.EVALUATE
                and item.state not in {
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                }
            ),
            None,
        )
        if active is not None:
            return active
        model = self._model(model_id)
        self._preflight(model)
        try:
            operation = self.store.create_model_operation(
                model_id,
                ModelOperationAction.EVALUATE,
                bytes_total=0,
            )
        except ValueError as exc:
            raise ModelOperationError("model_in_use", "another operation is active for this model") from exc
        task = asyncio.create_task(
            self._run(operation.id, identity),
            name=f"model-evaluation-{operation.id}",
        )
        self._tasks[operation.id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(operation.id, None))
        return operation

    async def _run(self, operation_id: str, identity: HostIdentity) -> None:
        async with self._guard:
            execution: HostExecution | None = None
            reporter: HostJobReporter | None = None
            lease_task: asyncio.Task[None] | None = None
            try:
                operation = self.store.update_model_operation(
                    operation_id,
                    state=ModelOperationState.PREFLIGHT,
                )
                if self.store.model_operation_cancel_requested(operation_id):
                    await self._finish_canceled(operation_id, None)
                    return
                model = self._model(operation.model_id)
                if model.runtime_adapter.startswith("diffusers.") and "image" in model.media_types:
                    # 画像モデルは普段の生成と同じワーカーで 1 回走らせて測る。
                    # 別経路で測ると、実際に使う経路ではないものを測ることになる。
                    await self._run_image_evaluation(operation_id, model)
                    return
                self._preflight(model)
                attached = await self.host.create_or_attach_job(
                    identity,
                    title="Media Forge model evaluation",
                )
                host_job = attached.get("job")
                if not isinstance(host_job, dict) or not isinstance(host_job.get("id"), str):
                    raise ModelOperationError("invalid_host_response", "ControlDeck did not return a Host Job")
                execution = HostExecution(
                    identity=identity,
                    host_job_id=host_job["id"],
                    workload_class="batch",
                    owns_terminal=attached.get("created") is True,
                )
                reporter = HostJobReporter(self.host, execution)
                self.store.update_model_operation(operation_id, host_job_id=execution.host_job_id)
                await reporter.progress("evaluation_preflight", 0.02, force=True)
                self.store.update_model_operation(
                    operation_id,
                    state=ModelOperationState.ACQUIRING_RESOURCE,
                )
                status = await self.host.request_resource(
                    execution.identity,
                    self._resource_request(execution.host_job_id, model),
                )
                request_id = status.get("request_id")
                if not isinstance(request_id, str) or not request_id:
                    raise ModelOperationError("invalid_host_response", "ControlDeck did not return a resource request")
                execution.request_id = request_id
                while status.get("state") == "waiting":
                    await reporter.progress(
                        "waiting_resource",
                        0.03,
                        wait_reason=str(status.get("reason") or "resource_wait"),
                    )
                    if await self._cancel_requested(operation_id, execution):
                        await self._finish_canceled(operation_id, reporter)
                        return
                    await asyncio.sleep(0.5)
                    status = await self.host.resource_status(execution.identity, request_id)
                lease_id = status.get("lease_id")
                if status.get("state") != "granted" or not isinstance(lease_id, str):
                    raise ModelOperationError(
                        "resource_unavailable",
                        f"ControlDeck admission failed: {status.get('reason') or status.get('state') or 'unknown'}",
                    )
                execution.lease_id = lease_id
                await self.host.lease_action(execution.identity, lease_id, "activate")
                await reporter.progress("evaluation_loading", 0.08, force=True)
                self.store.update_model_operation(operation_id, state=ModelOperationState.LOADING)

                output_dir = contained(self.output_root, self.output_root / operation_id)
                output_dir.mkdir(mode=0o700)
                suffix = ".mp4" if model.model_id in {
                    WAN_MODEL_ID, HUNYUAN_MODEL_ID, COGVIDEOX2B_MODEL_ID, WAN21_VACE_MODEL_ID
                } else ".webm"
                output_path = contained(output_dir, output_dir / f"smoke{suffix}")
                log_path = contained(output_dir, output_dir / "runtime.log")
                command = self.command_builder(model, output_path, self._runtime_executable())
                metrics = self._new_metrics()
                with log_path.open("wb") as log_stream:
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=log_stream,
                        stderr=asyncio.subprocess.STDOUT,
                        env=self._runtime_env(model),
                        start_new_session=True,
                    )
                    self._processes[operation_id] = process
                    lease_task = asyncio.create_task(
                        self._maintain(operation_id, execution, metrics),
                        name=f"model-evaluation-monitor-{operation_id}",
                    )
                    self.store.update_model_operation(operation_id, state=ModelOperationState.GENERATING)
                    await reporter.progress("evaluation_generating", 0.15, force=True)
                    try:
                        return_code = await asyncio.wait_for(process.wait(), timeout=self.timeout_sec)
                    except TimeoutError as exc:
                        await self._terminate(operation_id)
                        raise ModelOperationError("model_evaluation_timeout", "bounded evaluation timed out") from exc
                if lease_task is not None:
                    lease_task.cancel()
                    await asyncio.gather(lease_task, return_exceptions=True)
                    lease_task = None
                self._sample_metrics(process.pid, metrics)
                self._processes.pop(operation_id, None)
                host_failure = self._host_failures.pop(operation_id, None)
                if host_failure is not None:
                    raise ModelOperationError(host_failure.code, str(host_failure))
                if self.store.model_operation_cancel_requested(operation_id):
                    await self._finish_canceled(operation_id, reporter)
                    return
                if return_code != 0:
                    raise ModelOperationError(
                        "model_evaluation_failed",
                        f"native runtime exited with code {return_code}",
                    )
                self.store.update_model_operation(operation_id, state=ModelOperationState.VALIDATING)
                await reporter.progress("evaluation_validating", 0.92, force=True)
                if model.model_id == WAN_MODEL_ID and not self._custom_artifact_validator:
                    validator = self._validate_wan_artifact
                elif model.model_id == HUNYUAN_MODEL_ID and not self._custom_artifact_validator:
                    validator = self._validate_hunyuan_artifact
                elif model.model_id == COGVIDEOX2B_MODEL_ID and not self._custom_artifact_validator:
                    validator = self._validate_cogvideox2b_artifact
                elif model.model_id == WAN21_VACE_MODEL_ID and not self._custom_artifact_validator:
                    validator = self._validate_wan21_vace_artifact
                else:
                    validator = self.artifact_validator
                media = await asyncio.to_thread(validator, output_path)
                result = self._result(output_path, media, metrics, model=model)
                if len(json.dumps(result, separators=(",", ":")).encode("utf-8")) > 16 * 1024:
                    raise ModelOperationError(
                        "model_evaluation_invalid_output",
                        "evaluation result exceeds the bounded metadata limit",
                    )
                self.store.update_model_operation(
                    operation_id,
                    state=ModelOperationState.READY,
                    result=result,
                )
                if execution.owns_terminal:
                    await reporter.terminal(
                        "succeeded",
                        phase="evaluation_complete",
                        progress=1.0,
                        result=result,
                    )
                else:
                    await reporter.finish_attached(phase="evaluation_complete", progress=1.0)
            except asyncio.CancelledError:
                await self._terminate(operation_id)
                raise
            except (ModelOperationError, ModelRegistryError, HostApiError, OSError, ValueError) as exc:
                code = exc.code if isinstance(exc, (ModelOperationError, HostApiError)) else "model_evaluation_failed"
                self.store.update_model_operation(
                    operation_id,
                    state=ModelOperationState.FAILED,
                    error_code=code,
                    error_message=str(exc)[:300],
                )
                if reporter is not None and execution is not None and execution.owns_terminal:
                    try:
                        await reporter.terminal(
                            "failed",
                            phase="evaluation_failed",
                            progress=max(reporter.gate.last_progress, 0.08),
                            error=str(exc),
                        )
                    except (HostApiError, ValueError):
                        logger.exception("failed to report model evaluation failure")
            except Exception as exc:  # noqa: BLE001 - native worker isolation boundary
                logger.exception("model evaluation %s failed unexpectedly", operation_id)
                self.store.update_model_operation(
                    operation_id,
                    state=ModelOperationState.FAILED,
                    error_code="model_evaluation_failed",
                    error_message=str(exc)[:300],
                )
            finally:
                if lease_task is not None:
                    lease_task.cancel()
                    await asyncio.gather(lease_task, return_exceptions=True)
                await self._terminate(operation_id)
                try:
                    self._cleanup_probe_intermediates(operation_id)
                except (OSError, ValueError):
                    logger.exception("failed to clean model evaluation intermediates")
                if execution is not None:
                    await self._release(execution)
                self._host_failures.pop(operation_id, None)

    def _cleanup_probe_intermediates(self, operation_id: str) -> None:
        try:
            operation = self.store.get_model_operation(operation_id)
            output_dir = contained(self.output_root, self.output_root / operation_id)
        except (KeyError, OSError, ValueError):
            return
        contained(output_dir, output_dir / "prompt.safetensors").unlink(missing_ok=True)
        if operation.state == ModelOperationState.READY:
            return
        for name in ("smoke.mp4", "smoke.webm", "probe.json"):
            contained(output_dir, output_dir / name).unlink(missing_ok=True)
        frames = contained(output_dir, output_dir / "frames")
        if frames.is_dir():
            for item in frames.iterdir():
                candidate = contained(frames, item)
                if candidate.is_file() and not candidate.is_symlink():
                    candidate.unlink()
            try:
                frames.rmdir()
            except OSError:
                pass

    async def _maintain(
        self,
        operation_id: str,
        execution: HostExecution,
        metrics: RuntimeMetrics,
    ) -> None:
        renew_at = asyncio.get_running_loop().time() + self.lease_renew_sec
        try:
            while True:
                await asyncio.sleep(0.5)
                process = self._processes.get(operation_id)
                if process is not None:
                    self._sample_metrics(process.pid, metrics)
                if execution.identity.expires_at - int(time.time()) <= 120:
                    execution.identity = await self.host.refresh_lease_identity(
                        execution.identity,
                        execution.lease_id or "",
                    )
                if await self._cancel_requested(operation_id, execution):
                    await self._terminate(operation_id)
                    return
                if asyncio.get_running_loop().time() >= renew_at:
                    await self.host.lease_action(execution.identity, execution.lease_id or "", "renew")
                    renew_at = asyncio.get_running_loop().time() + self.lease_renew_sec
        except asyncio.CancelledError:
            raise
        except HostApiError as exc:
            self._host_failures[operation_id] = exc
            self.store.request_model_operation_cancel(operation_id)
            await self._terminate(operation_id)

    async def _cancel_requested(self, operation_id: str, execution: HostExecution) -> bool:
        if self.store.model_operation_cancel_requested(operation_id):
            return True
        control = await self.host.job_control(execution.identity, execution.host_job_id)
        if control.get("cancel_requested") is True:
            self.store.request_model_operation_cancel(operation_id)
            return True
        return False

    async def _finish_canceled(
        self,
        operation_id: str,
        reporter: HostJobReporter | None,
    ) -> None:
        self.store.update_model_operation(operation_id, state=ModelOperationState.CANCELED)
        if reporter is not None and reporter.execution.owns_terminal:
            try:
                await reporter.terminal(
                    "canceled",
                    phase="evaluation_canceled",
                    progress=reporter.gate.last_progress,
                )
            except (HostApiError, ValueError):
                logger.exception("failed to report model evaluation cancellation")

    async def _terminate(self, operation_id: str) -> None:
        process = self._processes.get(operation_id)
        if process is None or process.returncode is not None:
            self._processes.pop(operation_id, None)
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            self._processes.pop(operation_id, None)
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
        self._processes.pop(operation_id, None)

    async def _release(self, execution: HostExecution) -> None:
        try:
            if execution.lease_id is not None:
                await self.host.lease_action(execution.identity, execution.lease_id, "release")
            elif execution.request_id is not None:
                await self.host.cancel_resource(execution.identity, execution.request_id)
        except HostApiError:
            logger.exception("failed to release model evaluation resource state")

    async def _run_image_evaluation(self, operation_id: str, model: ModelDescriptor) -> None:
        """Run it once, write down what it cost, and let routing use it.

        No Host lease is taken here. The measurement is a normal generation of
        one small picture, and the ordinary admission path already governs real
        work; adding a second reservation route for a 512x512 probe would be
        more machinery than the thing it protects.
        """
        assert self.image_measure is not None and self.image_runtime_python is not None
        self.store.update_model_operation(operation_id, state=ModelOperationState.GENERATING)
        try:
            measurement = await self.image_measure(
                model,
                runtime_python=self.image_runtime_python,
                work_root=self.output_root,
                repository_root=REPOSITORY_ROOT,
                timeout_sec=self.timeout_sec,
            )
        except Exception as exc:  # noqa: BLE001 - 失敗の理由をそのまま伝える
            code = getattr(exc, "code", "model_evaluation_failed")
            self.store.update_model_operation(
                operation_id,
                state=ModelOperationState.FAILED,
                error_code=code,
                error_message=str(exc)[:300],
            )
            return
        self.store.update_model_operation(operation_id, state=ModelOperationState.VALIDATING)
        measurements = measurement.catalog_measurements()
        if self.record_measurement is not None:
            try:
                self.record_measurement(model.model_id, measurements)
            except Exception as exc:  # noqa: BLE001
                # 測れたのに書き残せないなら、成功と言ってはいけない。次に
                # 開いたとき、また「未計測」に戻っている。
                self.store.update_model_operation(
                    operation_id,
                    state=ModelOperationState.FAILED,
                    error_code=getattr(exc, "code", "model_evaluation_failed"),
                    error_message=str(exc)[:300],
                )
                return
        self.store.update_model_operation(
            operation_id,
            state=ModelOperationState.READY,
            result={
                "kind": "image",
                "measurements": measurements,
                "width": measurement.width,
                "height": measurement.height,
                "output_bytes": measurement.output_bytes,
            },
        )

    def _model(self, model_id: str) -> ModelDescriptor:
        if self.model_resolver is not None:
            return self.model_resolver(model_id)
        registry = ModelRegistry.load(
            self.model_manifest,
            catalog_manifest=self.catalog_manifest,
            hf_home=self.hf_home,
            model_store_root=self.model_store_root,
        )
        try:
            return next(item for item in registry.all() if item.model_id == model_id)
        except StopIteration as exc:
            raise ModelOperationError("model_not_found", "model is not in the trusted catalog") from exc

    def _preflight(self, model: ModelDescriptor) -> None:
        if model.model_id == WAN_MODEL_ID:
            self._wan_preflight(model)
            return
        if model.model_id == HUNYUAN_MODEL_ID:
            self._hunyuan_preflight(model)
            return
        if model.model_id == COGVIDEOX2B_MODEL_ID:
            self._cogvideox2b_preflight(model)
            return
        if model.model_id == WAN21_VACE_MODEL_ID:
            self._wan21_vace_preflight(model)
            return
        if model.model_id != H3_MODEL_ID or model.runtime_adapter != H3_RUNTIME_ADAPTER:
            raise ModelOperationError("model_evaluation_unsupported", "model has no bounded evaluation preset")
        if not model.installed or model.local_path is None:
            raise ModelOperationError("model_not_found", "model must be installed before evaluation")
        executable = self._runtime_executable()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ModelOperationError("model_runtime_unavailable", "pinned native runtime is unavailable")
        commit_marker = contained(self.runtime_root, self.runtime_root / ".git")
        head = contained(commit_marker, commit_marker / "HEAD")
        if not head.is_file():
            raise ModelOperationError("model_runtime_unavailable", "runtime revision cannot be verified")
        resolved_head = head.read_text(encoding="utf-8").strip()
        if resolved_head != H3_RUNTIME_COMMIT:
            raise ModelOperationError("model_runtime_unavailable", "runtime revision differs from the pinned commit")

    def _runtime_executable(self) -> Path:
        return contained(self.runtime_root, self.runtime_root / "build" / "bin" / "sd-cli")

    def _command(self, model: ModelDescriptor, output_path: Path, executable: Path) -> list[str]:
        if model.model_id == WAN_MODEL_ID:
            assert model.local_path is not None
            assert self.wan_runtime_python is not None
            return [
                str(self.wan_runtime_python),
                str(REPOSITORY_ROOT / "worker_packs/video/wan_ti2v_probe.py"),
                "run",
                "--snapshot", str(model.local_path),
                "--work-root", str(self.output_root),
                "--output", str(output_path),
                "--preset", self.wan_evaluation_preset,
            ]
        if model.model_id == HUNYUAN_MODEL_ID:
            assert self.hunyuan_runtime_python is not None
            assert self.hunyuan_snapshot_root is not None
            return [
                str(self.hunyuan_runtime_python),
                str(REPOSITORY_ROOT / "worker_packs/video/hunyuan15_probe.py"),
                "run",
                "--snapshot", str(self.hunyuan_snapshot_root),
                "--work-root", str(self.output_root),
                "--output", str(output_path),
                "--preset", self.hunyuan_evaluation_preset,
            ]
        if model.model_id == COGVIDEOX2B_MODEL_ID:
            assert self.cogvideox2b_runtime_python is not None
            assert self.cogvideox2b_snapshot_root is not None
            return [
                str(self.cogvideox2b_runtime_python),
                str(REPOSITORY_ROOT / "worker_packs/video/cogvideox2b_probe.py"),
                "run",
                "--snapshot", str(self.cogvideox2b_snapshot_root),
                "--work-root", str(self.output_root),
                "--output", str(output_path),
                "--preset", self.cogvideox2b_evaluation_preset,
            ]
        if model.model_id == WAN21_VACE_MODEL_ID:
            assert self.wan21_vace_runtime_python is not None
            assert self.wan21_vace_snapshot_root is not None
            return [
                str(self.wan21_vace_runtime_python),
                str(REPOSITORY_ROOT / "worker_packs/video/wan21_vace_probe.py"),
                "run",
                "--snapshot", str(self.wan21_vace_snapshot_root),
                "--work-root", str(self.output_root),
                "--output", str(output_path),
                "--preset", self.wan21_vace_evaluation_preset,
            ]
        assert model.local_path is not None
        snapshot = model.local_path
        files = {item.path: self._model_file(snapshot, item.path) for item in model.weights}
        return [
            str(executable),
            "-M", "vid_gen",
            "--diffusion-model", str(files["minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf"]),
            "--llm", str(files["qwen3vl_32b_minimax_h3-Q2_K_M.gguf"]),
            "--vae", str(files["vae/minimax_h3_video_vae_fp16.safetensors"]),
            "--audio-vae", str(files["vae/minimax_h3_audio_vae_fp32.safetensors"]),
            "--prompt", H3_EVALUATION_PROMPT,
            "--cfg-scale", "1.0",
            "--width", str(H3_EVALUATION_WIDTH),
            "--height", str(H3_EVALUATION_HEIGHT),
            "--steps", str(H3_EVALUATION_STEPS),
            "--video-frames", str(H3_EVALUATION_FRAMES),
            "--fps", "24",
            "--rng", "cpu",
            "--threads", "8",
            "--backend", "te=cpu,diffusion=ROCm0,vae=ROCm0",
            "--params-backend", "te=cpu",
            "--mmap",
            "--diffusion-fa",
            "--output", str(output_path),
        ]

    def _model_file(self, snapshot: Path, relative: str) -> Path:
        candidate = snapshot / relative
        try:
            resolved = candidate.resolve(strict=True)
            repo_root = snapshot.parent.parent.resolve(strict=True)
        except OSError as exc:
            raise ModelOperationError("model_verify_failed", "evaluation weight is unavailable") from exc
        if not resolved.is_relative_to(repo_root) or not resolved.is_file():
            raise ModelOperationError("model_verify_failed", "evaluation weight escapes the managed repository")
        return resolved

    def _runtime_env(self, model: ModelDescriptor) -> dict[str, str]:
        env = os.environ.copy()
        rocm_libs = "/opt/rocm/lib/llvm/lib:/opt/rocm/lib"
        existing = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = f"{rocm_libs}:{existing}" if existing else rocm_libs
        env["ROCR_VISIBLE_DEVICES"] = "0"
        env["HIP_VISIBLE_DEVICES"] = "0"
        if model.model_id == WAN_MODEL_ID and self.wan_source_root is not None:
            existing_pythonpath = env.get("PYTHONPATH")
            source = str(self.wan_source_root)
            env["PYTHONPATH"] = f"{source}:{existing_pythonpath}" if existing_pythonpath else source
        return env

    @staticmethod
    def _resource_request(host_job_id: str, model: ModelDescriptor) -> dict[str, Any]:
        if model.model_id == WAN_MODEL_ID:
            execution_peak = WAN_EXECUTION_PEAK_BYTES
            cold_peak = WAN_COLD_LOAD_PEAK_BYTES
            headroom = WAN_HEADROOM_BYTES
            runtime = WAN_ESTIMATED_RUNTIME_SEC
            confidence = "measured"
        elif model.model_id == HUNYUAN_MODEL_ID:
            execution_peak = HUNYUAN_EXECUTION_PEAK_BYTES
            cold_peak = HUNYUAN_COLD_LOAD_PEAK_BYTES
            headroom = HUNYUAN_HEADROOM_BYTES
            runtime = HUNYUAN_ESTIMATED_RUNTIME_SEC
            confidence = "low"
        elif model.model_id == COGVIDEOX2B_MODEL_ID:
            execution_peak = COGVIDEOX2B_EXECUTION_PEAK_BYTES
            cold_peak = COGVIDEOX2B_COLD_LOAD_PEAK_BYTES
            headroom = COGVIDEOX2B_HEADROOM_BYTES
            runtime = COGVIDEOX2B_ESTIMATED_RUNTIME_SEC
            confidence = "low"
        elif model.model_id == WAN21_VACE_MODEL_ID:
            execution_peak = WAN21_VACE_EXECUTION_PEAK_BYTES
            cold_peak = WAN21_VACE_COLD_LOAD_PEAK_BYTES
            headroom = WAN21_VACE_HEADROOM_BYTES
            runtime = WAN21_VACE_ESTIMATED_RUNTIME_SEC
            confidence = "low"
        else:
            execution_peak = H3_EXECUTION_PEAK_BYTES
            cold_peak = H3_COLD_LOAD_PEAK_BYTES
            headroom = H3_HEADROOM_BYTES
            runtime = H3_ESTIMATED_RUNTIME_SEC
            confidence = "low"
        return {
            "job_id": host_job_id,
            "device": "auto",
            "vram": {
                "resident_bytes": 0,
                "execution_peak_bytes": execution_peak,
                "cold_load_peak_bytes": cold_peak,
                "headroom_bytes": headroom,
                "confidence": confidence,
            },
            "compute_mode": "exclusive-preferred",
            "priority": 0,
            "class": "batch",
            "residency_key": f"mediaforge:{model.model_id}:{model.revision}",
            "estimated_runtime_sec": runtime,
            "max_wait_sec": 3600,
            "on_insufficient": "queue",
        }

    def _new_metrics(self) -> RuntimeMetrics:
        pswpin, pswpout = self._vmstat_swap()
        baseline_vram = self.vram_probe()
        return RuntimeMetrics(
            started_at=time.monotonic(),
            baseline_vram_bytes=baseline_vram,
            baseline_pswpin=pswpin,
            baseline_pswpout=pswpout,
            peak_vram_bytes=baseline_vram,
        )

    def _sample_metrics(self, pid: int, metrics: RuntimeMetrics) -> None:
        values = self._process_group_status(pid)
        metrics.peak_rss_bytes = max(metrics.peak_rss_bytes, values.get("VmRSS", 0) * 1024)
        metrics.peak_process_swap_bytes = max(
            metrics.peak_process_swap_bytes,
            values.get("VmSwap", 0) * 1024,
        )
        try:
            metrics.peak_vram_bytes = max(metrics.peak_vram_bytes, self.vram_probe())
        except OSError:
            pass

    @classmethod
    def _process_group_status(cls, group_id: int) -> dict[str, int]:
        """Sum evaluator RSS/swap across its isolated process group."""
        totals = {"VmRSS": 0, "VmSwap": 0}
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if os.getpgid(int(entry.name)) != group_id:
                    continue
                values = cls._proc_status(int(entry.name))
            except (OSError, ProcessLookupError, PermissionError, ValueError):
                continue
            for name in totals:
                totals[name] += values.get(name, 0)
        return totals

    def _result(
        self,
        output_path: Path,
        media: dict[str, Any],
        metrics: RuntimeMetrics,
        *,
        model: ModelDescriptor | None = None,
    ) -> dict[str, Any]:
        pswpin, pswpout = self._vmstat_swap()
        return {
            "evaluation_id": output_path.parent.name,
            "preset": (
                f"wan_ti2v_{self.wan_evaluation_preset}"
                if model and model.model_id == WAN_MODEL_ID
                else f"hunyuan15_{self.hunyuan_evaluation_preset}"
                if model and model.model_id == HUNYUAN_MODEL_ID
                else f"cogvideox2b_{self.cogvideox2b_evaluation_preset}"
                if model and model.model_id == COGVIDEOX2B_MODEL_ID
                else f"wan21_vace_{self.wan21_vace_evaluation_preset}"
                if model and model.model_id == WAN21_VACE_MODEL_ID
                else H3_EVALUATION_PRESET
            ),
            "runtime_commit": (
                WAN_SOURCE_REVISION
                if model and model.model_id == WAN_MODEL_ID
                else HUNYUAN_CONVERSION_REVISION
                if model and model.model_id == HUNYUAN_MODEL_ID
                else COGVIDEOX2B_MODEL_REVISION
                if model and model.model_id == COGVIDEOX2B_MODEL_ID
                else WAN21_VACE_MODEL_REVISION
                if model and model.model_id == WAN21_VACE_MODEL_ID
                else H3_RUNTIME_COMMIT
            ),
            "elapsed_sec": round(time.monotonic() - metrics.started_at, 3),
            "peak_rss_bytes": metrics.peak_rss_bytes,
            "peak_process_swap_bytes": metrics.peak_process_swap_bytes,
            "baseline_vram_bytes": metrics.baseline_vram_bytes,
            "peak_vram_bytes": metrics.peak_vram_bytes,
            "execution_vram_delta_bytes": max(0, metrics.peak_vram_bytes - metrics.baseline_vram_bytes),
            "system_pswpin_pages_delta": max(0, pswpin - metrics.baseline_pswpin),
            "system_pswpout_pages_delta": max(0, pswpout - metrics.baseline_pswpout),
            "output_bytes": output_path.stat().st_size,
            "output_sha256": self._sha256(output_path),
            "media": media,
        }

    def _wan_preflight(self, model: ModelDescriptor) -> None:
        if model.runtime_adapter != WAN_RUNTIME_ADAPTER or model.revision != WAN_MODEL_REVISION:
            raise ModelOperationError("model_evaluation_unsupported", "model has no bounded evaluation preset")
        if not model.installed or model.local_path is None:
            raise ModelOperationError("model_not_found", "model must be installed before evaluation")
        if self.wan_runtime_python is None or not self.wan_runtime_python.is_file():
            raise ModelOperationError("model_runtime_unavailable", "pinned Wan runtime is unavailable")
        if self.wan_source_root is None:
            raise ModelOperationError("model_runtime_unavailable", "pinned Wan source is unavailable")
        completed = subprocess.run(
            ["git", "-C", str(self.wan_source_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode != 0 or completed.stdout.strip() != WAN_SOURCE_REVISION:
            raise ModelOperationError("model_runtime_unavailable", "Wan source revision differs from the pinned commit")
        source_diff = subprocess.run(
            ["git", "-C", str(self.wan_source_root), "diff", "--binary", "--", "wan/__init__.py"],
            check=False,
            capture_output=True,
            timeout=10,
        )
        if (
            source_diff.returncode != 0
            or hashlib.sha256(source_diff.stdout).hexdigest() != WAN_SOURCE_PATCH_SHA256
        ):
            raise ModelOperationError("model_runtime_unavailable", "Wan evaluator source patch differs")
        source_status = subprocess.run(
            ["git", "-C", str(self.wan_source_root), "status", "--porcelain", "--untracked-files=all"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if source_status.returncode != 0 or source_status.stdout != " M wan/__init__.py\n":
            raise ModelOperationError("model_runtime_unavailable", "Wan evaluator source tree has other changes")

    def _hunyuan_preflight(self, model: ModelDescriptor) -> None:
        if (
            model.runtime_adapter != HUNYUAN_RUNTIME_ADAPTER
            or model.revision != HUNYUAN_MODEL_REVISION
        ):
            raise ModelOperationError("model_evaluation_unsupported", "model has no bounded evaluation preset")
        if self.hunyuan_runtime_python is None or not self.hunyuan_runtime_python.is_file():
            raise ModelOperationError("model_runtime_unavailable", "pinned Hunyuan runtime is unavailable")
        if self.hunyuan_snapshot_root is None or not self.hunyuan_snapshot_root.is_dir():
            raise ModelOperationError("model_not_found", "pinned Hunyuan conversion snapshot is unavailable")
        if (
            self.hunyuan_snapshot_root.name != HUNYUAN_CONVERSION_REVISION
            or self.hunyuan_snapshot_root.parent.name != "snapshots"
        ):
            raise ModelOperationError("model_verify_failed", "Hunyuan conversion revision differs")
        try:
            repository = self.hunyuan_snapshot_root.parent.parent.resolve(strict=True)
            model_index = (self.hunyuan_snapshot_root / "model_index.json").resolve(strict=True)
        except OSError as exc:
            raise ModelOperationError("model_verify_failed", "Hunyuan conversion snapshot is incomplete") from exc
        if not model_index.is_file() or not model_index.is_relative_to(repository):
            raise ModelOperationError("model_verify_failed", "Hunyuan conversion snapshot is incomplete")
        if model_index.stat().st_size > 64 * 1024:
            raise ModelOperationError("model_verify_failed", "Hunyuan conversion model index is unbounded")
        try:
            value = json.loads(model_index.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelOperationError("model_verify_failed", "Hunyuan conversion model index is unreadable") from exc
        if value.get("_class_name") != "HunyuanVideo15Pipeline":
            raise ModelOperationError("model_verify_failed", "Hunyuan conversion pipeline differs")

    def _validate_hunyuan_artifact(self, path: Path) -> dict[str, Any]:
        expected = {
            "smoke": (256, 256, 5),
            "candidate-clip": (640, 384, 33),
            "official-clip": (848, 480, 121),
        }[self.hunyuan_evaluation_preset]
        media = self._validate_silent_mp4(path, label="Hunyuan", expected_fps="24/1")
        if (
            media["width"] != expected[0]
            or media["height"] != expected[1]
            or media["frame_count"] != expected[2]
        ):
            raise ModelOperationError("model_evaluation_invalid_output", "Hunyuan video bounds differ")
        media.pop("frame_count")
        return media

    def _validate_cogvideox2b_artifact(self, path: Path) -> dict[str, Any]:
        expected = {
            "smoke": (720, 480, 8),
            "official-clip": (720, 480, 49),
        }[self.cogvideox2b_evaluation_preset]
        media = self._validate_silent_mp4(
            path,
            label="CogVideoX-2B",
            expected_fps="8/1",
            max_duration_sec=7,
        )
        if (
            media["width"] != expected[0]
            or media["height"] != expected[1]
            or media["frame_count"] != expected[2]
        ):
            raise ModelOperationError(
                "model_evaluation_invalid_output", "CogVideoX-2B video bounds differ"
            )
        media.pop("frame_count")
        return media

    def _validate_wan21_vace_artifact(self, path: Path) -> dict[str, Any]:
        expected = {
            "smoke": (256, 256, 5),
            "candidate-clip": (512, 320, 33),
            "official-clip": (832, 480, 81),
        }[self.wan21_vace_evaluation_preset]
        media = self._validate_silent_mp4(
            path,
            label="Wan 2.1 VACE",
            expected_fps="16/1",
        )
        if (
            media["width"] != expected[0]
            or media["height"] != expected[1]
            or media["frame_count"] != expected[2]
        ):
            raise ModelOperationError(
                "model_evaluation_invalid_output", "Wan 2.1 VACE video bounds differ"
            )
        media.pop("frame_count")
        return media

    @staticmethod
    def _validate_silent_mp4(
        path: Path,
        *,
        label: str,
        expected_fps: str,
        max_duration_sec: float = 6,
    ) -> dict[str, Any]:
        if not path.is_file() or path.stat().st_size <= 0:
            raise ModelOperationError("model_evaluation_invalid_output", f"{label} runtime produced no video")
        completed = subprocess.run(
            ["/usr/bin/ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) > 256 * 1024:
            raise ModelOperationError("model_evaluation_invalid_output", f"ffprobe rejected the {label} video")
        try:
            value = json.loads(completed.stdout)
            streams = value["streams"]
            video = next(item for item in streams if item.get("codec_type") == "video")
            if any(item.get("codec_type") == "audio" for item in streams):
                raise ValueError("unexpected audio")
            duration = float(value["format"]["duration"])
            frame_count = int(video["nb_frames"])
            containers = str(value["format"]["format_name"]).split(",")
        except (json.JSONDecodeError, KeyError, StopIteration, TypeError, ValueError) as exc:
            raise ModelOperationError("model_evaluation_invalid_output", f"{label} video metadata is invalid") from exc
        if (
            not 0 < duration <= max_duration_sec
            or video.get("codec_name") != "h264"
            or video.get("avg_frame_rate") != expected_fps
            or "mp4" not in containers
        ):
            raise ModelOperationError("model_evaluation_invalid_output", f"{label} video encoding differs")
        return {
            "width": int(video["width"]),
            "height": int(video["height"]),
            "video_codec": str(video.get("codec_name") or "unknown")[:32],
            "frame_rate": str(video.get("avg_frame_rate") or "unknown")[:32],
            "frame_count": frame_count,
            "duration_sec": round(duration, 3),
            "audio_present": False,
        }

    def _cogvideox2b_preflight(self, model: ModelDescriptor) -> None:
        if (
            model.runtime_adapter != COGVIDEOX2B_RUNTIME_ADAPTER
            or model.revision != COGVIDEOX2B_MODEL_REVISION
        ):
            raise ModelOperationError("model_evaluation_unsupported", "model has no bounded evaluation preset")
        if self.cogvideox2b_runtime_python is None or not self.cogvideox2b_runtime_python.is_file():
            raise ModelOperationError("model_runtime_unavailable", "pinned CogVideoX-2B runtime is unavailable")
        snapshot = self.cogvideox2b_snapshot_root
        if snapshot is None or not snapshot.is_dir():
            raise ModelOperationError("model_not_found", "pinned CogVideoX-2B snapshot is unavailable")
        if snapshot.name != COGVIDEOX2B_MODEL_REVISION or snapshot.parent.name != "snapshots":
            raise ModelOperationError("model_verify_failed", "CogVideoX-2B snapshot revision differs")
        try:
            repository = snapshot.parent.parent.resolve(strict=True)
            model_index = (snapshot / "model_index.json").resolve(strict=True)
            required = [
                (snapshot / relative).resolve(strict=True)
                for relative in (*model.required_files, *(weight.path for weight in model.weights))
            ]
        except OSError as exc:
            raise ModelOperationError("model_verify_failed", "CogVideoX-2B snapshot is incomplete") from exc
        if not model_index.is_file() or model_index.stat().st_size > 64 * 1024:
            raise ModelOperationError("model_verify_failed", "CogVideoX-2B model index is invalid")
        if any(not item.is_file() or not item.is_relative_to(repository) for item in required):
            raise ModelOperationError("model_verify_failed", "CogVideoX-2B snapshot is incomplete")
        try:
            value = json.loads(model_index.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelOperationError("model_verify_failed", "CogVideoX-2B model index is unreadable") from exc
        if value.get("_class_name") != "CogVideoXPipeline":
            raise ModelOperationError("model_verify_failed", "CogVideoX-2B pipeline differs")

    def _wan21_vace_preflight(self, model: ModelDescriptor) -> None:
        if (
            model.runtime_adapter != WAN21_VACE_RUNTIME_ADAPTER
            or model.revision != WAN21_VACE_MODEL_REVISION
        ):
            raise ModelOperationError("model_evaluation_unsupported", "model has no bounded evaluation preset")
        if self.wan21_vace_runtime_python is None or not self.wan21_vace_runtime_python.is_file():
            raise ModelOperationError("model_runtime_unavailable", "pinned Wan VACE runtime is unavailable")
        snapshot = self.wan21_vace_snapshot_root
        if snapshot is None or not snapshot.is_dir():
            raise ModelOperationError("model_not_found", "pinned Wan VACE snapshot is unavailable")
        if snapshot.name != WAN21_VACE_MODEL_REVISION or snapshot.parent.name != "snapshots":
            raise ModelOperationError("model_verify_failed", "Wan VACE snapshot revision differs")
        try:
            repository = snapshot.parent.parent.resolve(strict=True)
            model_index = (snapshot / "model_index.json").resolve(strict=True)
            required = [
                (snapshot / relative).resolve(strict=True)
                for relative in (*model.required_files, *(weight.path for weight in model.weights))
            ]
        except OSError as exc:
            raise ModelOperationError("model_verify_failed", "Wan VACE snapshot is incomplete") from exc
        if not model_index.is_file() or model_index.stat().st_size > 64 * 1024:
            raise ModelOperationError("model_verify_failed", "Wan VACE model index is invalid")
        if any(not item.is_file() or not item.is_relative_to(repository) for item in required):
            raise ModelOperationError("model_verify_failed", "Wan VACE snapshot is incomplete")
        try:
            value = json.loads(model_index.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelOperationError("model_verify_failed", "Wan VACE model index is unreadable") from exc
        if value.get("_class_name") != "WanVACEPipeline":
            raise ModelOperationError("model_verify_failed", "Wan VACE pipeline differs")

    def _validate_wan_artifact(self, path: Path) -> dict[str, Any]:
        if not path.is_file() or path.stat().st_size <= 0:
            raise ModelOperationError("model_evaluation_invalid_output", "Wan runtime produced no video")
        completed = subprocess.run(
            ["/usr/bin/ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) > 256 * 1024:
            raise ModelOperationError("model_evaluation_invalid_output", "ffprobe rejected the Wan video")
        try:
            value = json.loads(completed.stdout)
            streams = value["streams"]
            video = next(item for item in streams if item.get("codec_type") == "video")
            duration = float(value["format"]["duration"])
            frame_count = int(video["nb_frames"])
        except (json.JSONDecodeError, KeyError, StopIteration, TypeError, ValueError) as exc:
            raise ModelOperationError("model_evaluation_invalid_output", "Wan video metadata is invalid") from exc
        expected = {
            "smoke": (256, 256, 1),
            "quality-frame": (256, 256, 1),
            "short-clip": (512, 320, 17),
            "practical-clip": (256, 256, 49),
            "candidate-clip": (384, 256, 33),
            "candidate-hq-clip": (512, 320, 33),
        }[self.wan_evaluation_preset]
        if (
            video.get("width") != expected[0]
            or video.get("height") != expected[1]
            or frame_count != expected[2]
            or not 0 < duration <= 3
        ):
            raise ModelOperationError("model_evaluation_invalid_output", "Wan video bounds differ")
        return {
            "width": expected[0],
            "height": expected[1],
            "video_codec": str(video.get("codec_name") or "unknown")[:32],
            "frame_rate": str(video.get("avg_frame_rate") or "unknown")[:32],
            "duration_sec": round(duration, 3),
            "audio_present": False,
        }

    @staticmethod
    def _validate_artifact(path: Path) -> dict[str, Any]:
        if not path.is_file() or path.stat().st_size <= 0:
            raise ModelOperationError("model_evaluation_invalid_output", "native runtime produced no video")
        completed = subprocess.run(
            [
                "/usr/bin/ffprobe",
                "-v", "error",
                "-show_streams",
                "-show_format",
                "-of", "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) > 256 * 1024:
            raise ModelOperationError("model_evaluation_invalid_output", "ffprobe rejected the generated video")
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ModelOperationError("model_evaluation_invalid_output", "ffprobe returned invalid metadata") from exc
        streams = value.get("streams") if isinstance(value, dict) else None
        if not isinstance(streams, list):
            raise ModelOperationError("model_evaluation_invalid_output", "generated video has no stream metadata")
        video = next(
            (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"),
            None,
        )
        audio = next(
            (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"),
            None,
        )
        if (
            not isinstance(video, dict)
            or not isinstance(video.get("width"), int)
            or not isinstance(video.get("height"), int)
            or video["width"] != H3_EVALUATION_WIDTH
            or video["height"] != H3_EVALUATION_HEIGHT
        ):
            raise ModelOperationError("model_evaluation_invalid_output", "generated video dimensions differ")
        if not isinstance(audio, dict):
            raise ModelOperationError("model_evaluation_invalid_output", "generated video has no audio stream")
        format_value = value.get("format") if isinstance(value, dict) else None
        try:
            duration = float(format_value["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelOperationError("model_evaluation_invalid_output", "generated video duration is invalid") from exc
        if not 0 < duration <= 10:
            raise ModelOperationError("model_evaluation_invalid_output", "generated video duration is out of bounds")
        return {
            "width": video["width"],
            "height": video["height"],
            "video_codec": str(video.get("codec_name") or "unknown")[:32],
            "frame_rate": str(video.get("avg_frame_rate") or "unknown")[:32],
            "duration_sec": round(duration, 3),
            "audio_present": True,
            "audio_codec": str(audio.get("codec_name") or "unknown")[:32],
            "audio_channels": int(audio.get("channels", 0)),
        }

    @staticmethod
    def _proc_status(pid: int) -> dict[str, int]:
        result: dict[str, int] = {}
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition(":")
            if separator and name in {"VmRSS", "VmSwap"}:
                result[name] = int(value.strip().split()[0])
        return result

    @staticmethod
    def _vmstat_swap() -> tuple[int, int]:
        values: dict[str, int] = {}
        for line in Path("/proc/vmstat").read_text(encoding="utf-8").splitlines():
            name, value = line.split()
            if name in {"pswpin", "pswpout"}:
                values[name] = int(value)
        return values.get("pswpin", 0), values.get("pswpout", 0)

    @staticmethod
    def _r9700_vram_used() -> int:
        for card in sorted(Path("/sys/class/drm").glob("card[0-9]")):
            total_path = card / "device" / "mem_info_vram_total"
            used_path = card / "device" / "mem_info_vram_used"
            try:
                total = int(total_path.read_text(encoding="utf-8").strip())
                used = int(used_path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
            if total >= 30_000_000_000:
                return used
        raise OSError("R9700 VRAM counters are unavailable")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
