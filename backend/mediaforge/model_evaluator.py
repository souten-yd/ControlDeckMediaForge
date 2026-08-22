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
from .paths import contained
from .store import Store


H3_MODEL_ID = "unsloth/MiniMax-H3-GGUF"
H3_RUNTIME_ADAPTER = "native.stable-diffusion-cpp-minimax-h3"
H3_RUNTIME_COMMIT = "97d2990807fe6d558e395f8764198d7c7e7b411c"
H3_ESTIMATED_RUNTIME_SEC = 1800.0
H3_EXECUTION_PEAK_BYTES = 30_000_000_000
H3_COLD_LOAD_PEAK_BYTES = 32_000_000_000
H3_HEADROOM_BYTES = 1024 * 1024 * 1024
H3_EVALUATION_PROMPT = (
    "Integrated multimodal description: An adult boyish young woman in a polished anime illustration style, "
    "with short dark hair and vivid orange mesh highlights, smiles warmly at the viewer. In one continuous "
    "locked medium shot she raises one hand for a small friendly wave and gives a single playful wink; her "
    "face, outfit, proportions, and orange highlights remain consistent. Clean linework, soft warm lighting, "
    "stable background, restrained natural motion, no camera shake, no text. Overall soundscape: a quiet indoor "
    "room with a faint natural clothing rustle synchronized to the wave. Non-diegetic music: none."
)
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
    """Private, bounded H3 smoke evaluator backed by a real Host Job and lease."""

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
        lease_renew_sec: float,
        timeout_sec: float,
        command_builder: Callable[[ModelDescriptor, Path, Path], list[str]] | None = None,
        artifact_validator: Callable[[Path], dict[str, Any]] | None = None,
        vram_probe: Callable[[], int] | None = None,
        model_resolver: Callable[[str], ModelDescriptor] | None = None,
    ) -> None:
        self.store = store
        self.host = host
        self.model_manifest = model_manifest
        self.catalog_manifest = catalog_manifest
        self.model_store_root = model_store_root.resolve()
        self.hf_home = hf_home.resolve()
        self.runtime_root = runtime_root.resolve()
        self.output_root = (store.data_dir / "model-evaluations").resolve()
        self.lease_renew_sec = lease_renew_sec
        self.timeout_sec = timeout_sec
        self.command_builder = command_builder or self._command
        self.artifact_validator = artifact_validator or self._validate_artifact
        self.vram_probe = vram_probe or self._r9700_vram_used
        self.model_resolver = model_resolver
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
        try:
            model = self._model(H3_MODEL_ID)
            self._preflight(model)
        except (ModelOperationError, OSError):
            return []
        return [H3_MODEL_ID]

    def evaluate(self, model_id: str, identity: HostIdentity) -> ModelOperation:
        missing = {"jobs.write", "resources.acquire"} - identity.granted_capabilities
        if missing:
            raise ModelOperationError("host_capability_not_granted", "Host evaluation capabilities are unavailable")
        if model_id != H3_MODEL_ID:
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
                output_path = contained(output_dir, output_dir / "smoke.webm")
                log_path = contained(output_dir, output_dir / "runtime.log")
                command = self.command_builder(model, output_path, self._runtime_executable())
                metrics = self._new_metrics()
                with log_path.open("wb") as log_stream:
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=log_stream,
                        stderr=asyncio.subprocess.STDOUT,
                        env=self._runtime_env(),
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
                media = await asyncio.to_thread(self.artifact_validator, output_path)
                result = self._result(output_path, media, metrics)
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
                if execution is not None:
                    await self._release(execution)
                self._host_failures.pop(operation_id, None)

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
            "--width", "640",
            "--height", "384",
            "--steps", "1",
            "--video-frames", "5",
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

    def _runtime_env(self) -> dict[str, str]:
        env = os.environ.copy()
        rocm_libs = "/opt/rocm/lib/llvm/lib:/opt/rocm/lib"
        existing = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = f"{rocm_libs}:{existing}" if existing else rocm_libs
        env["ROCR_VISIBLE_DEVICES"] = "0"
        env["HIP_VISIBLE_DEVICES"] = "0"
        return env

    @staticmethod
    def _resource_request(host_job_id: str, model: ModelDescriptor) -> dict[str, Any]:
        return {
            "job_id": host_job_id,
            "device": "auto",
            "vram": {
                "resident_bytes": 0,
                "execution_peak_bytes": H3_EXECUTION_PEAK_BYTES,
                "cold_load_peak_bytes": H3_COLD_LOAD_PEAK_BYTES,
                "headroom_bytes": H3_HEADROOM_BYTES,
                "confidence": "low",
            },
            "compute_mode": "exclusive-preferred",
            "priority": 0,
            "class": "batch",
            "residency_key": f"mediaforge:{model.model_id}:{model.revision}",
            "estimated_runtime_sec": H3_ESTIMATED_RUNTIME_SEC,
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
        try:
            values = self._proc_status(pid)
        except OSError:
            values = {}
        metrics.peak_rss_bytes = max(metrics.peak_rss_bytes, values.get("VmRSS", 0) * 1024)
        metrics.peak_process_swap_bytes = max(
            metrics.peak_process_swap_bytes,
            values.get("VmSwap", 0) * 1024,
        )
        try:
            metrics.peak_vram_bytes = max(metrics.peak_vram_bytes, self.vram_probe())
        except OSError:
            pass

    def _result(self, output_path: Path, media: dict[str, Any], metrics: RuntimeMetrics) -> dict[str, Any]:
        pswpin, pswpout = self._vmstat_swap()
        return {
            "evaluation_id": output_path.parent.name,
            "preset": "smoke",
            "runtime_commit": H3_RUNTIME_COMMIT,
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
            or video["width"] != 640
            or video["height"] != 384
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
