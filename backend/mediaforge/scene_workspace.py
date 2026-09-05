"""Bounded private `.blend` intake and versioned scene working copies."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
import signal
import threading
from typing import Any, Callable
import uuid

from pydantic import ValidationError

from . import __version__
from .blender_runtime import BlenderRuntimeResolver, ResolvedBlenderRuntime
from .domain import Asset, ErrorDetail, JobRequest, JobStatus, Provenance
from .glb import GlbValidationError, validate_glb_path
from .paths import contained
from .scenes import (
    SceneCatalog,
    SceneDocument,
    SceneError,
    SceneRevision,
    SceneRevisionInput,
    SceneValidationCheck,
    SceneWorkingCopy,
    validate_scene_owner,
)
from .store import Store, utc_now


MAX_BLEND_BYTES = 256 * 1024 * 1024
BLEND_CHUNK_BYTES = 512 * 1024
UPLOAD_TTL = timedelta(minutes=10)
WORKING_TTL = timedelta(minutes=10)
SCENE_WORKER_TIMEOUT_SEC = 180.0
MAX_PROCESS_OUTPUT_BYTES = 128 * 1024


@dataclass
class _Upload:
    id: str
    owner: str
    path: Path
    root: Path
    size: int
    sha256: str
    received: int
    expires_at: datetime
    name: str
    tags: list[str]
    collection: str | None


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SceneError("scene_working_invalid", "working copy time is invalid") from exc
    if parsed.tzinfo is None:
        raise SceneError("scene_working_invalid", "working copy time has no timezone")
    return parsed.astimezone(UTC)


async def _bounded_read(stream: asyncio.StreamReader | None) -> bytes:
    if stream is None:
        return b""
    value = bytearray()
    while True:
        chunk = await stream.read(16 * 1024)
        if not chunk:
            return bytes(value)
        value.extend(chunk)
        if len(value) > MAX_PROCESS_OUTPUT_BYTES:
            raise SceneError("scene_worker_output_bound", "Blender scene worker output exceeded its bound")


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        await process.wait()


class SceneWorkspace:
    """Own upload staging, trusted Blender validation, and working-copy leases."""

    def __init__(
        self,
        store: Store,
        resolver: BlenderRuntimeResolver,
        worker: Path,
        *,
        now: Callable[[], datetime] | None = None,
        process_timeout_sec: float = SCENE_WORKER_TIMEOUT_SEC,
    ) -> None:
        self.store = store
        self.resolver = resolver
        self.worker = Path(os.path.abspath(worker))
        self.catalog = SceneCatalog(store)
        self.scene_root = contained(store.data_dir, store.data_dir / "scenes")
        self.upload_root = contained(self.scene_root, self.scene_root / "uploads")
        self.working_root = contained(self.scene_root, self.scene_root / "working")
        self.validation_root = contained(self.scene_root, self.scene_root / "validation")
        self._now = now or (lambda: datetime.now(UTC))
        self.process_timeout_sec = process_timeout_sec
        self._guard = threading.RLock()
        self._uploads: dict[str, _Upload] = {}

    def initialize(self) -> None:
        for root in (self.scene_root, self.upload_root, self.working_root, self.validation_root):
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for entry in self.upload_root.iterdir():
            bounded = contained(self.upload_root, entry)
            if bounded.is_dir() and not bounded.is_symlink():
                shutil.rmtree(bounded)
            else:
                bounded.unlink()
        for entry in self.validation_root.iterdir():
            bounded = contained(self.validation_root, entry)
            if bounded.is_dir() and not bounded.is_symlink():
                shutil.rmtree(bounded)
            else:
                bounded.unlink()

    def begin_upload(
        self,
        owner: str,
        *,
        size: int,
        sha256: str,
        name: str,
        tags: list[str] | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= MAX_BLEND_BYTES:
            raise SceneError("scene_upload_invalid", "Blender upload size is invalid")
        if not isinstance(sha256, str) or len(sha256) != 64 or any(
            char not in "0123456789abcdef" for char in sha256
        ):
            raise SceneError("scene_upload_invalid", "Blender upload SHA-256 is invalid")
        now = self._now()
        try:
            metadata = SceneDocument(
                id="scene_" + "0" * 32,
                name=name.strip() if isinstance(name, str) else name,
                tags=tags or [],
                collection=collection,
                current_revision_id="revision_" + "0" * 32,
                revision_count=1,
                created_at=_iso(now),
                updated_at=_iso(now),
            )
        except ValidationError as exc:
            raise SceneError("scene_upload_invalid", "scene metadata is invalid") from exc
        with self._guard:
            self._expire_uploads(now)
            if any(item.owner == owner for item in self._uploads.values()):
                raise SceneError("scene_upload_busy", "owner already has an active Blender upload")
            upload_id = f"sceneupload_{uuid.uuid4().hex}"
            root = contained(self.upload_root, self.upload_root / upload_id)
            root.mkdir(mode=0o700)
            path = contained(root, root / "scene.blend")
            path.touch(mode=0o600)
            upload = _Upload(
                id=upload_id,
                owner=owner,
                path=path,
                root=root,
                size=size,
                sha256=sha256,
                received=0,
                expires_at=now + UPLOAD_TTL,
                name=metadata.name,
                tags=metadata.tags,
                collection=metadata.collection,
            )
            self._uploads[upload_id] = upload
        return self._upload_projection(upload)

    def append_upload(
        self, owner: str, upload_id: str, offset: int, content: bytes, sha256: str
    ) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        if not content or len(content) > BLEND_CHUNK_BYTES:
            raise SceneError("scene_upload_chunk_invalid", "Blender upload chunk size is invalid")
        if hashlib.sha256(content).hexdigest() != sha256:
            raise SceneError("scene_upload_chunk_invalid", "Blender upload chunk hash differs")
        with self._guard:
            upload = self._active_upload(owner, upload_id)
            if isinstance(offset, bool) or not isinstance(offset, int) or offset != upload.received:
                raise SceneError("scene_upload_offset_conflict", "Blender upload offset changed")
            if upload.received + len(content) > upload.size:
                raise SceneError("scene_upload_chunk_invalid", "Blender upload exceeds its declaration")
            with upload.path.open("ab") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            upload.received += len(content)
            return self._upload_projection(upload)

    def cancel_upload(self, owner: str, upload_id: str) -> bool:
        owner = validate_scene_owner(owner)
        with self._guard:
            upload = self._uploads.get(upload_id)
            if upload is None or upload.owner != owner:
                raise SceneError("scene_upload_not_found", "Blender upload is unavailable")
            self._uploads.pop(upload_id, None)
            self._remove_tree(upload.root, self.upload_root)
        return True

    async def commit_upload(self, owner: str, upload_id: str) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        with self._guard:
            upload = self._active_upload(owner, upload_id)
            if upload.received != upload.size:
                raise SceneError("scene_upload_incomplete", "Blender upload is incomplete")
            if self._sha256(upload.path) != upload.sha256:
                raise SceneError("scene_upload_hash_changed", "Blender upload identity changed")
        registered: list[str] = []
        job_id: str | None = None
        try:
            with self.resolver.active_reference() as runtime:
                if runtime is None:
                    raise SceneError("scene_runtime_unavailable", "active Blender runtime is unavailable")
                job = self.store.create_job(
                    JobRequest(operation="media.inspect", intent="Import local Blender scene")
                )
                job_id = job.id
                self.store.update_job(job.id, status=JobStatus.RUNNING, phase="validating", progress=0.2)
                preview, blender_facts, glb_facts = await self._validate(upload.path, runtime)
                source_asset, preview_asset = self._register_assets(
                    job.id,
                    upload.path,
                    preview,
                    runtime,
                    blender_facts,
                    glb_facts,
                    parent_revision=None,
                )
                registered.extend([source_asset.id, preview_asset.id])
                document, revision = self.catalog.create(
                    owner,
                    name=upload.name,
                    tags=upload.tags,
                    collection=upload.collection,
                    revision=SceneRevisionInput(
                        source_asset_id=source_asset.id,
                        preview_asset_id=preview_asset.id,
                        runtime_id=runtime.runtime_id,
                        runtime_version=runtime.version,
                        validation=self._validation(blender_facts, glb_facts),
                    ),
                )
                self.store.update_job(
                    job.id,
                    status=JobStatus.SUCCEEDED,
                    progress=1,
                    asset_ids=[source_asset.id, preview_asset.id],
                )
                return self._scene_projection(document, revision)
        except Exception as exc:
            self._rollback_assets(registered)
            if job_id is not None:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(code=getattr(exc, "code", "scene_import_failed"), message=str(exc)[:300]),
                )
            if isinstance(exc, SceneError):
                raise
            raise SceneError(
                "scene_import_failed", "Blender scene import failed"
            ) from exc
        finally:
            with self._guard:
                upload = self._uploads.pop(upload_id, None)
                if upload is not None:
                    self._remove_tree(upload.root, self.upload_root)

    def acquire_working_copy(self, owner: str, scene_id: str) -> SceneWorkingCopy:
        owner = validate_scene_owner(owner)
        document, revisions = self.catalog.get(owner, scene_id)
        current = next(
            item for item in revisions if item.id == document.current_revision_id
        )
        runtime = self.resolver.resolve_registered(current.runtime_id)
        if runtime is None or runtime.version != current.runtime_version:
            raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
        now = self._now()
        working = SceneWorkingCopy(
            id=f"working_{uuid.uuid4().hex}",
            scene_id=scene_id,
            base_revision_id=current.id,
            runtime_id=runtime.runtime_id,
            runtime_version=runtime.version,
            expires_at=_iso(now + WORKING_TTL),
            created_at=_iso(now),
            updated_at=_iso(now),
        )
        root = contained(self.working_root, self.working_root / working.id)
        try:
            root.mkdir(mode=0o700)
            target = contained(root, root / "scene.blend")
            source = self.store.asset_path(current.source_asset_id)
            shutil.copyfile(source, target)
            target.chmod(0o600)
            if self._sha256(target) != self.store.get_asset(current.source_asset_id).sha256:
                raise SceneError("scene_working_copy_changed", "working copy source identity changed")
            return self.store.acquire_scene_working_copy(
                owner, working, now=_iso(now)
            )
        except Exception as exc:
            if root.exists():
                self._remove_tree(root, self.working_root)
            if isinstance(exc, SceneError):
                raise
            raise SceneError(
                "scene_working_copy_failed", "working copy could not be created"
            ) from exc

    def renew_working_copy(self, owner: str, working_id: str) -> SceneWorkingCopy:
        owner = validate_scene_owner(owner)
        self.store.expire_scene_working_copies(_iso(self._now()))
        current = self.store.get_scene_working_copy(owner, working_id)
        now = self._now()
        renewed = current.model_copy(
            update={"expires_at": _iso(now + WORKING_TTL), "updated_at": _iso(now)}
        )
        return self.store.renew_scene_working_copy(owner, renewed, now=_iso(now))

    def release_working_copy(self, owner: str, working_id: str) -> SceneWorkingCopy:
        owner = validate_scene_owner(owner)
        value = self.store.finish_scene_working_copy(
            owner, working_id, "released", now=_iso(self._now())
        )
        root = contained(self.working_root, self.working_root / working_id)
        if root.exists():
            self._remove_tree(root, self.working_root)
        return value

    def retain_working_copy_for_recovery(self, owner: str, working_id: str) -> SceneWorkingCopy:
        """End the writer lease without deleting bytes after a GUI/session failure."""
        return self.store.finish_scene_working_copy(
            validate_scene_owner(owner), working_id, "recovery", now=_iso(self._now())
        )

    async def commit_working_copy(self, owner: str, working_id: str) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        self.store.expire_scene_working_copies(_iso(self._now()))
        working = self.store.get_scene_working_copy(owner, working_id)
        if working.state != "active" or _parse_time(working.expires_at) <= self._now():
            raise SceneError("scene_working_expired", "working copy lease expired")
        source = contained(
            self.working_root, self.working_root / working.id / "scene.blend"
        )
        if source.is_symlink() or not source.is_file():
            raise SceneError("scene_working_missing", "working copy bytes are unavailable")
        registered: list[str] = []
        job_id: str | None = None
        try:
            with self.resolver.runtime_reference(working.runtime_id) as runtime:
                if runtime is None or runtime.version != working.runtime_version:
                    raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
                job = self.store.create_job(
                    JobRequest(operation="media.inspect", intent="Commit Blender scene revision")
                )
                job_id = job.id
                self.store.update_job(job.id, status=JobStatus.RUNNING, phase="validating", progress=0.2)
                preview, blender_facts, glb_facts = await self._validate(source, runtime)
                _, base_revisions = self.catalog.get(owner, working.scene_id)
                base = next(item for item in base_revisions if item.id == working.base_revision_id)
                source_asset, preview_asset = self._register_assets(
                    job.id,
                    source,
                    preview,
                    runtime,
                    blender_facts,
                    glb_facts,
                    parent_revision=base,
                )
                registered.extend([source_asset.id, preview_asset.id])
                document, revision = self.catalog.commit_working_copy(
                    owner,
                    working.id,
                    working.scene_id,
                    working.base_revision_id,
                    SceneRevisionInput(
                        source_asset_id=source_asset.id,
                        preview_asset_id=preview_asset.id,
                        dependencies=base.dependencies,
                        runtime_id=runtime.runtime_id,
                        runtime_version=runtime.version,
                        validation=self._validation(blender_facts, glb_facts),
                    ),
                    committed_at=_iso(self._now()),
                )
                self.store.update_job(
                    job.id,
                    status=JobStatus.SUCCEEDED,
                    progress=1,
                    asset_ids=[source_asset.id, preview_asset.id],
                )
                root = contained(self.working_root, self.working_root / working.id)
                self._remove_tree(root, self.working_root)
                return self._scene_projection(document, revision)
        except SceneError as exc:
            self._rollback_assets(registered)
            if exc.code == "scene_revision_conflict" and working.state == "active":
                self.store.finish_scene_working_copy(
                    owner, working.id, "recovery", now=utc_now()
                )
            if job_id is not None:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
                )
            raise
        except Exception as exc:
            self._rollback_assets(registered)
            if job_id is not None:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(code="scene_commit_failed", message=str(exc)[:300]),
                )
            raise SceneError("scene_commit_failed", "scene revision commit failed") from exc

    def working_path_for_runtime(self, owner: str, working_id: str) -> Path:
        """Internal-only handoff for 3DS-5; never project this path to a client."""
        self.store.expire_scene_working_copies(_iso(self._now()))
        value = self.store.get_scene_working_copy(validate_scene_owner(owner), working_id)
        if value.state != "active" or _parse_time(value.expires_at) <= self._now():
            raise SceneError("scene_working_expired", "working copy lease expired")
        path = contained(self.working_root, self.working_root / value.id / "scene.blend")
        if path.is_symlink() or not path.is_file():
            raise SceneError("scene_working_missing", "working copy bytes are unavailable")
        return path

    def list_working_copies(self, owner: str) -> list[SceneWorkingCopy]:
        owner = validate_scene_owner(owner)
        self.store.expire_scene_working_copies(_iso(self._now()))
        return self.store.list_scene_working_copies(owner)

    async def _validate(
        self, source: Path, runtime: ResolvedBlenderRuntime
    ) -> tuple[Path, dict[str, Any], dict[str, Any]]:
        if source.is_symlink() or not source.is_file():
            raise SceneError("scene_blend_invalid", "Blender source is unavailable")
        size = source.stat().st_size
        with source.open("rb") as stream:
            header = stream.read(7)
        if not 1 <= size <= MAX_BLEND_BYTES or header != b"BLENDER":
            raise SceneError("scene_blend_invalid", "Blender source header or size is invalid")
        if self.worker.is_symlink() or not self.worker.is_file():
            raise SceneError("scene_worker_unavailable", "trusted Blender scene worker is unavailable")
        root = contained(self.validation_root, self.validation_root / f"validation_{uuid.uuid4().hex}")
        root.mkdir(mode=0o700)
        staged = contained(root, root / "scene.blend")
        shutil.copyfile(source, staged)
        staged.chmod(0o600)
        preview = contained(root, root / "preview.glb")
        result_path = contained(root, root / "result.json")
        sandbox = contained(root, root / "blender-user")
        sandbox.mkdir(mode=0o700)
        environment = {
            "PATH": "/usr/bin:/bin",
            "PYTHONNOUSERSITE": "1",
            "HOME": str(sandbox),
            "XDG_CACHE_HOME": str(sandbox / "cache"),
            "XDG_CONFIG_HOME": str(sandbox / "config"),
            "XDG_DATA_HOME": str(sandbox / "data"),
            "BLENDER_USER_CONFIG": str(sandbox / "blender-config"),
            "BLENDER_USER_SCRIPTS": str(sandbox / "blender-scripts"),
            "BLENDER_USER_DATAFILES": str(sandbox / "blender-data"),
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
        }
        command = [
            str(runtime.executable),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python",
            str(self.worker),
            "--",
            "--source",
            "scene.blend",
            "--preview",
            "preview.glb",
            "--result",
            "result.json",
            "--expected-version",
            runtime.version,
        ]
        try:
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=root,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=environment,
                    start_new_session=True,
                )
            except OSError as exc:
                raise SceneError(
                    "scene_worker_unavailable", "Blender scene worker could not start"
                ) from exc
            stdout_task = asyncio.create_task(_bounded_read(process.stdout))
            stderr_task = asyncio.create_task(_bounded_read(process.stderr))
            try:
                stdout, stderr, returncode = await asyncio.wait_for(
                    asyncio.gather(stdout_task, stderr_task, process.wait()),
                    timeout=self.process_timeout_sec,
                )
            except BaseException as exc:
                await _stop_process(process)
                for task in (stdout_task, stderr_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
                if isinstance(exc, TimeoutError):
                    raise SceneError(
                        "scene_worker_timeout", "Blender scene validation timed out"
                    ) from exc
                raise
            if returncode != 0:
                raise SceneError(
                    "scene_blend_invalid",
                    "Blender rejected the scene; inspect the bounded service log",
                )
            if (
                preview.is_symlink()
                or not preview.is_file()
                or result_path.is_symlink()
                or not result_path.is_file()
                or result_path.stat().st_size > MAX_PROCESS_OUTPUT_BYTES
            ):
                raise SceneError("scene_worker_invalid", "Blender scene worker output is missing")
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SceneError("scene_worker_invalid", "Blender scene result is invalid") from exc
            self._validate_worker_result(result, runtime.version)
            try:
                glb = validate_glb_path(preview, root)
            except GlbValidationError as exc:
                raise SceneError("scene_preview_invalid", str(exc)) from exc
            retained = contained(self.validation_root, self.validation_root / f"preview_{uuid.uuid4().hex}.glb")
            os.replace(preview, retained)
            return retained, result, glb
        finally:
            if root.exists():
                self._remove_tree(root, self.validation_root)

    @staticmethod
    def _validate_worker_result(value: object, version: str) -> None:
        expected = {
            "schema_version", "blender_version", "background", "autoexec_disabled",
            "objects", "meshes", "vertices", "triangles", "materials", "images",
            "animations", "text_blocks", "linked_libraries", "external_images", "unit_meters",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise SceneError("scene_worker_invalid", "Blender scene result fields differ")
        if (
            value["schema_version"] != "media-forge.blender-scene-validation@1"
            or value["blender_version"] != version
            or value["background"] is not True
            or value["autoexec_disabled"] is not True
            or value["linked_libraries"] != 0
            or value["external_images"] != 0
            or value["unit_meters"] != 1.0
        ):
            raise SceneError("scene_worker_invalid", "Blender scene validation differs")
        for name in expected - {
            "schema_version", "blender_version", "background", "autoexec_disabled", "unit_meters"
        }:
            if isinstance(value[name], bool) or not isinstance(value[name], int) or value[name] < 0:
                raise SceneError("scene_worker_invalid", "Blender scene count is invalid")

    def _register_assets(
        self,
        job_id: str,
        source: Path,
        preview: Path,
        runtime: ResolvedBlenderRuntime,
        blender_facts: dict[str, Any],
        glb_facts: dict[str, Any],
        *,
        parent_revision: SceneRevision | None,
    ) -> tuple[Asset, Asset]:
        now = utc_now()
        source_hash = self._sha256(source)
        source_id = f"asset_{uuid.uuid4().hex}"
        source_provenance_id = f"prov_{uuid.uuid4().hex}"
        parent_assets = [parent_revision.source_asset_id] if parent_revision is not None else []
        source_asset = Asset(
            id=source_id,
            job_id=job_id,
            parent_asset_ids=parent_assets,
            mime_type="application/x-blender",
            size_bytes=source.stat().st_size,
            sha256=source_hash,
            suggested_filename=f"media-forge-scene-{source_id[6:14]}.blend",
            provenance_id=source_provenance_id,
            created_at=now,
        )
        source_provenance = Provenance(
            id=source_provenance_id,
            asset_id=source_id,
            parent_asset_ids=parent_assets,
            operation="scene.import" if parent_revision is None else "scene.commit",
            intent="Import Blender scene" if parent_revision is None else "Commit Blender scene revision",
            model_id="none",
            model_version="0",
            weights_hash="none",
            license="user-provided",
            runtime_adapter="blender.scene-document",
            runtime_version=runtime.version,
            tool_versions={"media-forge": __version__, "blender": runtime.version},
            seed=0,
            parameters={"runtime_id": runtime.runtime_id},
            reference_asset_hashes={
                dependency.asset_id: dependency.sha256
                for dependency in (parent_revision.dependencies if parent_revision else [])
            },
            postprocessing=[],
            validation=[blender_facts],
            warnings=[],
            output_sha256=source_hash,
            created_at=now,
        )
        self.store.register_asset(source_asset, source_provenance, source)

        preview_hash = self._sha256(preview)
        preview_id = f"asset_{uuid.uuid4().hex}"
        preview_provenance_id = f"prov_{uuid.uuid4().hex}"
        preview_asset = Asset(
            id=preview_id,
            job_id=job_id,
            parent_asset_ids=[source_id],
            mime_type="model/gltf-binary",
            size_bytes=preview.stat().st_size,
            sha256=preview_hash,
            suggested_filename=f"media-forge-scene-preview-{preview_id[6:14]}.glb",
            provenance_id=preview_provenance_id,
            created_at=now,
        )
        preview_provenance = source_provenance.model_copy(
            update={
                "id": preview_provenance_id,
                "asset_id": preview_id,
                "parent_asset_ids": [source_id],
                "operation": "scene.preview",
                "intent": "Export validated scene preview",
                "validation": [glb_facts],
                "output_sha256": preview_hash,
            }
        )
        try:
            self.store.register_asset(preview_asset, preview_provenance, preview)
        except Exception:
            try:
                self.store.delete_asset(source_asset.id)
            except (KeyError, OSError, RuntimeError):
                pass
            raise
        preview.unlink()
        return source_asset, preview_asset

    @staticmethod
    def _validation(
        blender_facts: dict[str, Any], glb_facts: dict[str, Any]
    ) -> list[SceneValidationCheck]:
        return [
            SceneValidationCheck(
                validator="blender.scene", status="passed", facts=blender_facts
            ),
            SceneValidationCheck(
                validator="glb.structure", status="passed", facts=glb_facts
            ),
        ]

    def _rollback_assets(self, asset_ids: list[str]) -> None:
        for asset_id in reversed(asset_ids):
            try:
                self.store.delete_asset(asset_id)
            except (KeyError, OSError, RuntimeError):
                continue

    def _active_upload(self, owner: str, upload_id: str) -> _Upload:
        now = self._now()
        self._expire_uploads(now)
        upload = self._uploads.get(upload_id)
        if upload is None or upload.owner != owner:
            raise SceneError("scene_upload_not_found", "Blender upload is unavailable")
        return upload

    def _expire_uploads(self, now: datetime) -> None:
        for upload_id, upload in list(self._uploads.items()):
            if upload.expires_at <= now:
                self._uploads.pop(upload_id, None)
                self._remove_tree(upload.root, self.upload_root)

    @staticmethod
    def _upload_projection(value: _Upload) -> dict[str, Any]:
        return {
            "upload_id": value.id,
            "size": value.size,
            "received": value.received,
            "chunk_bytes": BLEND_CHUNK_BYTES,
            "expires_at": _iso(value.expires_at),
        }

    @staticmethod
    def _scene_projection(document: SceneDocument, revision: SceneRevision) -> dict[str, Any]:
        return {
            "scene": document.model_dump(mode="json"),
            "revision": revision.model_dump(mode="json"),
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _remove_tree(path: Path, root: Path) -> None:
        bounded = contained(root, path)
        if bounded.is_symlink():
            bounded.unlink()
        elif bounded.exists():
            shutil.rmtree(bounded)
