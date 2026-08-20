from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from .domain import Asset, ErrorDetail, Job, JobRequest, JobStatus, Provenance
from .paths import contained
from .store import Store, utc_now
from .validators import validate_png


logger = logging.getLogger(__name__)
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


class WorkerFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class JobManager:
    """Durable queue with a single worker-local execution guard.

    G0 jobs are CPU-only fake jobs. GPU workers added in G1 must acquire and
    renew a ControlDeck broker lease before entering this execution section.
    """

    def __init__(self, store: Store, *, worker_timeout_sec: float = 30.0):
        self.store = store
        self.worker_timeout_sec = worker_timeout_sec
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._runner: asyncio.Task[None] | None = None
        self._processes: dict[str, asyncio.subprocess.Process] = {}
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
        processes = list(self._processes.items())
        for job_id, process in processes:
            current = self.store.get_job(job_id)
            if current.status == JobStatus.RUNNING:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(code="service_stopped", message="Service stopped while the worker was running"),
                )
            if process.returncode is None:
                process.terminate()
        self._runner.cancel()
        try:
            await self._runner
        except asyncio.CancelledError:
            pass
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

    async def cancel(self, job_id: str) -> Job:
        job = self.store.request_cancel(job_id)
        process = self._processes.get(job_id)
        if process is not None and process.returncode is None:
            process.terminate()
        return self.store.get_job(job_id)

    async def _run(self) -> None:
        while True:
            job_id = await self._queue.get()
            if job_id is None:
                return
            try:
                await self._execute(job_id)
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
                self._queue.task_done()

    async def _execute(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if job.status != JobStatus.QUEUED or self.store.cancel_requested(job_id):
            return
        if job.request.operation != "image.generate":
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=ErrorDetail(code="capability_unavailable", message=f"{job.request.operation} is unavailable in G0"),
            )
            return
        self.store.update_job(job_id, status=JobStatus.RUNNING, phase="normalize_request", progress=0.01)
        self.store.update_job(job_id, phase="select_model", progress=0.03)
        self.store.update_job(job_id, phase="generating", progress=0.05)
        job_root = contained(self.store.work_dir, self.store.work_dir / job_id)
        if job_root.exists():
            shutil.rmtree(job_root)
        job_root.mkdir(mode=0o700)
        output_dir = job_root / "outputs"
        payload = job.request.model_dump(mode="json")
        payload["worker_output_dir"] = str(output_dir)
        backend_root = str(Path(__file__).resolve().parents[1])
        environment = dict(os.environ)
        environment["PYTHONPATH"] = backend_root + os.pathsep + environment.get("PYTHONPATH", "")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "mediaforge.workers.fake",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        self._processes[job_id] = process
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(json.dumps(payload).encode("utf-8")), timeout=self.worker_timeout_sec
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=ErrorDetail(code="worker_timeout", message="fake worker exceeded its timeout"),
            )
            return
        finally:
            self._processes.pop(job_id, None)
        if self._stopping:
            return
        if self.store.cancel_requested(job_id):
            self.store.update_job(job_id, status=JobStatus.CANCELED, progress=0)
            return
        if len(stdout) > 1024 * 1024 or len(stderr) > 64 * 1024:
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=ErrorDetail(code="worker_output_too_large", message="worker output exceeded its bound"),
            )
            return
        response: dict[str, Any] = {}
        try:
            response = json.loads(stdout)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        if process.returncode != 0:
            detail = response.get("error", {}) if isinstance(response, dict) else {}
            code = str(detail.get("code", "worker_crash"))
            message = str(detail.get("message", f"worker exited with code {process.returncode}"))
            self.store.update_job(job_id, status=JobStatus.FAILED, error=ErrorDetail(code=code, message=message[:300]))
            return
        self.store.update_job(job_id, phase="postprocess", progress=0.65)
        try:
            asset_ids = self._register_outputs(job, response, job_root)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self.store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=ErrorDetail(code="artifact_integrity_failed", message=str(exc)[:300]),
            )
            return
        self.store.update_job(
            job_id,
            status=JobStatus.SUCCEEDED,
            phase=None,
            progress=1,
            asset_ids=asset_ids,
        )

    def _register_outputs(self, job: Job, response: dict[str, Any], job_root: Path) -> list[str]:
        outputs = response["outputs"]
        if not isinstance(outputs, list) or len(outputs) != job.request.output.count:
            raise ValueError("worker returned an unexpected output count")
        model = response["model"]
        reference_hashes = {
            item.asset_id: self.store.get_asset(item.asset_id).sha256 for item in job.request.inputs
        }
        asset_ids: list[str] = []
        self.store.update_job(job.id, phase="validate", progress=0.75)
        for index, output in enumerate(outputs):
            path = contained(job_root, Path(output["path"]))
            if path.stat().st_size > MAX_ARTIFACT_BYTES:
                raise ValueError("worker artifact exceeded the 64 MiB limit")
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            width, height, validation = validate_png(path)
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
                tool_versions={"media-forge": "0.1.0", "validator.png": "1.0.0"},
                seed=int(response["seed"]),
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
