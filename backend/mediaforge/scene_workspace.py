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

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError

from . import __version__
from .blender_runtime import BlenderRuntimeResolver, ResolvedBlenderRuntime
from .domain import Asset, ErrorDetail, JobRequest, JobStatus, Provenance
from .glb import GlbValidationError, validate_glb_path
from .material_binding import MaterialBinding
from .paths import contained
from .scenes import (
    SceneCatalog,
    SceneDocument,
    SceneDependency,
    SceneError,
    SceneRevision,
    SceneRevisionInput,
    SceneValidationCheck,
    SceneWorkingCopy,
    validate_scene_owner,
)
from .scene_recipes import SceneCreateRequest, SceneEditRequest, SceneMaterialRequest, SceneRecipe
from .store import Store, utc_now


MAX_BLEND_BYTES = 256 * 1024 * 1024
BLEND_CHUNK_BYTES = 512 * 1024
UPLOAD_TTL = timedelta(minutes=10)
WORKING_TTL = timedelta(minutes=10)
SCENE_WORKER_TIMEOUT_SEC = 180.0
MAX_PROCESS_OUTPUT_BYTES = 128 * 1024
MAX_TEXTURE_SIDE = 8192
MAX_TEXTURE_PIXELS = 67_108_864


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
        material_worker: Path | None = None,
        recipe_worker: Path | None = None,
        now: Callable[[], datetime] | None = None,
        process_timeout_sec: float = SCENE_WORKER_TIMEOUT_SEC,
    ) -> None:
        self.store = store
        self.resolver = resolver
        self.worker = Path(os.path.abspath(worker))
        self.material_worker = (
            Path(os.path.abspath(material_worker)) if material_worker is not None else None
        )
        self.recipe_worker = (
            Path(os.path.abspath(recipe_worker)) if recipe_worker is not None else None
        )
        self.catalog = SceneCatalog(store)
        self.scene_root = contained(store.data_dir, store.data_dir / "scenes")
        self.upload_root = contained(self.scene_root, self.scene_root / "uploads")
        self.working_root = contained(self.scene_root, self.scene_root / "working")
        self.validation_root = contained(self.scene_root, self.scene_root / "validation")
        self.material_root = contained(self.scene_root, self.scene_root / "materials")
        self.recipe_root = contained(self.scene_root, self.scene_root / "recipes")
        self._now = now or (lambda: datetime.now(UTC))
        self.process_timeout_sec = process_timeout_sec
        self._guard = threading.RLock()
        self._uploads: dict[str, _Upload] = {}

    def initialize(self) -> None:
        for root in (
            self.scene_root,
            self.upload_root,
            self.working_root,
            self.validation_root,
            self.material_root,
            self.recipe_root,
        ):
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
        for entry in self.material_root.iterdir():
            bounded = contained(self.material_root, entry)
            if bounded.is_dir() and not bounded.is_symlink():
                shutil.rmtree(bounded)
            else:
                bounded.unlink()
        for entry in self.recipe_root.iterdir():
            bounded = contained(self.recipe_root, entry)
            if bounded.is_dir() and not bounded.is_symlink():
                shutil.rmtree(bounded)
            else:
                bounded.unlink()

    async def apply_recipe(
        self,
        owner: str,
        job_id: str,
        value: SceneCreateRequest | SceneEditRequest,
        *,
        runtime_id: str,
        runtime_version: str,
    ) -> dict[str, Any]:
        """Run a typed recipe and atomically publish a validated scene revision."""
        owner = validate_scene_owner(owner)
        registered: list[str] = []
        with self.resolver.runtime_reference(runtime_id) as runtime:
            if runtime is None or runtime.version != runtime_version:
                raise SceneError("scene_runtime_unavailable", "pinned Blender runtime is unavailable")
            parent: SceneRevision | None = None
            source: Path | None = None
            if isinstance(value, SceneEditRequest):
                document, revisions = self.catalog.get(owner, value.scene_id)
                if document.current_revision_id != value.base_revision_id:
                    raise SceneError("scene_revision_conflict", "scene current revision changed")
                parent = next(
                    (item for item in revisions if item.id == value.base_revision_id), None
                )
                if parent is None:
                    raise SceneError("scene_revision_not_found", "scene revision is unavailable")
                if runtime.runtime_id != parent.runtime_id or runtime.version != parent.runtime_version:
                    raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
                _, _, source = self._verified_revision_asset(
                    parent.source_asset_id, "application/x-blender"
                )
            generated, worker_facts = await self._apply_recipe_worker(
                value.recipe, runtime, source=source
            )
            try:
                preview, blender_facts, glb_facts = await self._validate(generated, runtime)
                source_asset, preview_asset = self._register_assets(
                    job_id,
                    generated,
                    preview,
                    runtime,
                    blender_facts,
                    glb_facts,
                    parent_revision=parent,
                    dependencies=parent.dependencies if parent is not None else [],
                    operation="scene.recipe.create" if parent is None else "scene.recipe.edit",
                    parameters={
                        "recipe_schema": value.recipe.schema_version,
                        "recipe_sha256": hashlib.sha256(
                            value.recipe.model_dump_json().encode("utf-8")
                        ).hexdigest(),
                        "operation_count": len(value.recipe.operations),
                        "stable_object_ids": worker_facts["stable_object_ids"],
                    },
                )
                registered.extend([source_asset.id, preview_asset.id])
                revision_value = SceneRevisionInput(
                    source_asset_id=source_asset.id,
                    preview_asset_id=preview_asset.id,
                    dependencies=parent.dependencies if parent is not None else [],
                    runtime_id=runtime.runtime_id,
                    runtime_version=runtime.version,
                    validation=self._validation(blender_facts, glb_facts),
                )
                if isinstance(value, SceneCreateRequest):
                    document, revision = self.catalog.create(
                        owner,
                        name=value.name,
                        tags=value.tags,
                        collection=value.collection,
                        revision=revision_value,
                    )
                else:
                    document, revision = self.catalog.commit(
                        owner, value.scene_id, value.base_revision_id, revision_value
                    )
                return {
                    **self._scene_projection(document, revision),
                    "asset_ids": [source_asset.id, preview_asset.id],
                    "recipe": worker_facts,
                }
            except BaseException:
                self._rollback_assets(registered)
                raise
            finally:
                if generated.exists():
                    generated.unlink()

    def recipe_runtime_pin(
        self, owner: str, value: SceneCreateRequest | SceneEditRequest | SceneMaterialRequest
    ) -> tuple[str, str, str | None]:
        owner = validate_scene_owner(owner)
        if isinstance(value, (SceneEditRequest, SceneMaterialRequest)):
            document, revisions = self.catalog.get(owner, value.scene_id)
            base_revision_id = (
                value.base_revision_id
                if isinstance(value, SceneEditRequest)
                else value.binding.source_revision_id
            )
            if document.current_revision_id != base_revision_id:
                raise SceneError("scene_revision_conflict", "scene current revision changed")
            revision = next(
                (item for item in revisions if item.id == base_revision_id), None
            )
            if revision is None:
                raise SceneError("scene_revision_not_found", "scene revision is unavailable")
            runtime = self.resolver.resolve_registered(revision.runtime_id)
            if runtime is None or runtime.version != revision.runtime_version:
                raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
            return runtime.runtime_id, runtime.version, revision.id
        runtime = self.resolver.resolve_active()
        if runtime is None:
            raise SceneError("scene_runtime_unavailable", "active Blender runtime is unavailable")
        return runtime.runtime_id, runtime.version, None

    async def _apply_recipe_worker(
        self,
        recipe: SceneRecipe,
        runtime: ResolvedBlenderRuntime,
        *,
        source: Path | None,
    ) -> tuple[Path, dict[str, Any]]:
        if self.recipe_worker is None or self.recipe_worker.is_symlink() or not self.recipe_worker.is_file():
            raise SceneError("scene_recipe_worker_unavailable", "trusted scene recipe worker is unavailable")
        root = contained(self.recipe_root, self.recipe_root / f"recipe_{uuid.uuid4().hex}")
        root.mkdir(mode=0o700)
        recipe_path = contained(root, root / "recipe.json")
        recipe_path.write_text(recipe.model_dump_json() + "\n", encoding="utf-8")
        recipe_path.chmod(0o600)
        mode = "edit" if source is not None else "create"
        if source is not None:
            staged = contained(root, root / "source.blend")
            shutil.copyfile(source, staged)
            staged.chmod(0o600)
        output = contained(root, root / "scene.blend")
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
            str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
            "--python", str(self.recipe_worker), "--", "--mode", mode,
            "--recipe", "recipe.json", "--output", "scene.blend", "--result", "result.json",
            "--expected-version", runtime.version,
        ]
        if source is not None:
            command.extend(["--source", "source.blend"])
        retained = contained(self.recipe_root, self.recipe_root / f"scene_{uuid.uuid4().hex}.blend")
        try:
            process = await asyncio.create_subprocess_exec(
                *command, cwd=root, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env=environment, start_new_session=True,
            )
            stdout_task = asyncio.create_task(_bounded_read(process.stdout))
            stderr_task = asyncio.create_task(_bounded_read(process.stderr))
            try:
                _, _, returncode = await asyncio.wait_for(
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
                    raise SceneError("scene_recipe_timeout", "scene recipe timed out") from exc
                raise
            if returncode != 0:
                raise SceneError("scene_recipe_failed", "Blender rejected the typed scene recipe")
            if output.is_symlink() or not output.is_file() or result_path.is_symlink() or not result_path.is_file():
                raise SceneError("scene_recipe_worker_invalid", "scene recipe worker output is missing")
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SceneError("scene_recipe_worker_invalid", "scene recipe result is invalid") from exc
            expected = {"schema_version", "blender_version", "autoexec_disabled", "operation_count", "stable_object_ids"}
            if (
                not isinstance(result, dict) or set(result) != expected
                or result["schema_version"] != "media-forge.scene-recipe-result@1"
                or result["blender_version"] != runtime.version
                or result["autoexec_disabled"] is not True
                or result["operation_count"] != len(recipe.operations)
                or not isinstance(result["stable_object_ids"], list)
                or not all(isinstance(item, str) for item in result["stable_object_ids"])
            ):
                raise SceneError("scene_recipe_worker_invalid", "scene recipe result differs")
            os.replace(output, retained)
            return retained, result
        except OSError as exc:
            raise SceneError("scene_recipe_worker_unavailable", "scene recipe worker could not start") from exc
        finally:
            if root.exists():
                self._remove_tree(root, self.recipe_root)

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
                    job_id,
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

    def acquire_recovery_working_copy(
        self, owner: str, scene_id: str, recovery_working_id: str
    ) -> SceneWorkingCopy:
        """Copy retained GUI bytes into a new writer lease; keep the candidate immutable."""
        owner = validate_scene_owner(owner)
        candidate = self.store.get_scene_working_copy(owner, recovery_working_id)
        if candidate.state != "recovery" or candidate.scene_id != scene_id:
            raise SceneError("scene_recovery_unavailable", "recovery candidate is unavailable")
        document, _ = self.catalog.get(owner, scene_id)
        if document.current_revision_id != candidate.base_revision_id:
            raise SceneError("scene_recovery_conflict", "scene changed after the recovery candidate was created")
        runtime = self.resolver.resolve_registered(candidate.runtime_id)
        if runtime is None or runtime.version != candidate.runtime_version:
            raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
        source_root = contained(self.working_root, self.working_root / candidate.id)
        source = contained(source_root, source_root / "scene.blend")
        if source.is_symlink() or not source.is_file() or not 1 <= source.stat().st_size <= MAX_BLEND_BYTES:
            raise SceneError("scene_recovery_missing", "recovery candidate bytes are unavailable")
        with source.open("rb") as stream:
            if stream.read(7) != b"BLENDER":
                raise SceneError("scene_recovery_invalid", "recovery candidate is not a Blender file")
        now = self._now()
        working = candidate.model_copy(update={
            "id": f"working_{uuid.uuid4().hex}",
            "state": "active",
            "expires_at": _iso(now + WORKING_TTL),
            "created_at": _iso(now),
            "updated_at": _iso(now),
        })
        root = contained(self.working_root, self.working_root / working.id)
        try:
            root.mkdir(mode=0o700)
            target = contained(root, root / "scene.blend")
            shutil.copyfile(source, target)
            target.chmod(0o600)
            if self._sha256(target) != self._sha256(source):
                raise SceneError("scene_recovery_changed", "recovery candidate identity changed")
            return self.store.acquire_scene_working_copy(owner, working, now=_iso(now))
        except Exception as exc:
            if root.exists():
                self._remove_tree(root, self.working_root)
            if isinstance(exc, SceneError):
                raise
            raise SceneError("scene_recovery_failed", "recovery candidate could not be opened") from exc

    def retire_recovery_working_copy(self, owner: str, working_id: str) -> None:
        """Retire and remove a candidate only after its replacement revision committed."""
        owner = validate_scene_owner(owner)
        self.store.retire_scene_recovery(owner, working_id, now=_iso(self._now()))
        root = contained(self.working_root, self.working_root / working_id)
        if root.exists():
            self._remove_tree(root, self.working_root)

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
        owner = validate_scene_owner(owner)
        current = self.store.get_scene_working_copy(owner, working_id)
        if current.state == "recovery":
            return current
        return self.store.finish_scene_working_copy(
            owner, working_id, "recovery", now=_iso(self._now())
        )

    async def commit_working_copy(
        self,
        owner: str,
        working_id: str,
        *,
        dependencies: list[SceneDependency] | None = None,
        operation: str = "scene.commit",
        parameters: dict[str, Any] | None = None,
        external_job_id: str | None = None,
    ) -> dict[str, Any]:
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
                if external_job_id is None:
                    job = self.store.create_job(
                        JobRequest(operation="media.inspect", intent="Commit Blender scene revision")
                    )
                    job_id = job.id
                    self.store.update_job(job.id, status=JobStatus.RUNNING, phase="validating", progress=0.2)
                else:
                    job_id = external_job_id
                preview, blender_facts, glb_facts = await self._validate(source, runtime)
                _, base_revisions = self.catalog.get(owner, working.scene_id)
                base = next(item for item in base_revisions if item.id == working.base_revision_id)
                revision_dependencies = dependencies if dependencies is not None else base.dependencies
                source_asset, preview_asset = self._register_assets(
                    job_id,
                    source,
                    preview,
                    runtime,
                    blender_facts,
                    glb_facts,
                    parent_revision=base,
                    dependencies=revision_dependencies,
                    operation=operation,
                    parameters=parameters,
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
                        dependencies=revision_dependencies,
                        runtime_id=runtime.runtime_id,
                        runtime_version=runtime.version,
                        validation=self._validation(blender_facts, glb_facts),
                    ),
                    committed_at=_iso(self._now()),
                )
                if external_job_id is None:
                    self.store.update_job(
                        job_id,
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
            if job_id is not None and external_job_id is None:
                self.store.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=ErrorDetail(code=exc.code, message=str(exc)[:300]),
                )
            raise
        except Exception as exc:
            self._rollback_assets(registered)
            if job_id is not None and external_job_id is None:
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

    def restore_revision(
        self,
        owner: str,
        scene_id: str,
        base_revision_id: str,
        target_revision_id: str,
    ) -> dict[str, Any]:
        """Adopt an older validated revision as a new immutable scene head."""
        owner = validate_scene_owner(owner)
        document, revisions = self.catalog.get(owner, scene_id)
        if document.current_revision_id != base_revision_id:
            raise SceneError("scene_revision_conflict", "scene current revision changed")
        if target_revision_id == base_revision_id:
            raise SceneError("scene_revision_restore_invalid", "current revision cannot be restored")
        by_id = {item.id: item for item in revisions}
        target = by_id.get(target_revision_id)
        current = by_id.get(base_revision_id)
        if target is None or current is None:
            raise SceneError("scene_revision_not_found", "scene revision is unavailable")

        source, source_provenance, source_path = self._verified_revision_asset(
            target.source_asset_id, "application/x-blender"
        )
        preview, preview_provenance, preview_path = self._verified_revision_asset(
            target.preview_asset_id, "model/gltf-binary"
        )
        for dependency in target.dependencies:
            try:
                asset = self.store.get_asset(dependency.asset_id)
                provenance = self.store.get_provenance(dependency.asset_id)
                path = self.store.asset_path(dependency.asset_id)
            except KeyError as exc:
                raise SceneError(
                    "scene_revision_not_found",
                    "scene revision dependency is unavailable",
                ) from exc
            if (
                path.is_symlink()
                or not path.is_file()
                or asset.sha256 != dependency.sha256
                or path.stat().st_size != asset.size_bytes
                or self._sha256(path) != dependency.sha256
                or provenance.asset_id != asset.id
                or provenance.output_sha256 != dependency.sha256
            ):
                raise SceneError(
                    "scene_revision_restore_changed",
                    "scene revision dependency identity changed",
                )

        registered: list[str] = []
        job_id: str | None = None
        try:
            job = self.store.create_job(
                JobRequest(operation="media.inspect", intent="Restore validated scene revision")
            )
            job_id = job.id
            self.store.update_job(
                job.id, status=JobStatus.RUNNING, phase="restoring", progress=0.2
            )
            now = utc_now()
            source_id = f"asset_{uuid.uuid4().hex}"
            source_provenance_id = f"prov_{uuid.uuid4().hex}"
            source_parents = list(dict.fromkeys([
                current.source_asset_id,
                target.source_asset_id,
                *(item.asset_id for item in target.dependencies),
            ]))
            source_copy = source.model_copy(update={
                "id": source_id,
                "job_id": job.id,
                "parent_asset_ids": source_parents,
                "provenance_id": source_provenance_id,
                "suggested_filename": f"media-forge-scene-{source_id[6:14]}.blend",
                "created_at": now,
            })
            source_copy_provenance = source_provenance.model_copy(update={
                "id": source_provenance_id,
                "asset_id": source_id,
                "parent_asset_ids": source_parents,
                "operation": "scene.revision.restore",
                "intent": "Restore a validated scene revision as a new revision",
                "runtime_adapter": "scene.revision-restore",
                "runtime_version": __version__,
                "tool_versions": {**source_provenance.tool_versions, "media-forge": __version__},
                "parameters": {
                    "scene_id": scene_id,
                    "base_revision_id": base_revision_id,
                    "restored_revision_id": target_revision_id,
                },
                "reference_asset_hashes": {
                    current.source_asset_id: self.store.get_asset(current.source_asset_id).sha256,
                    target.source_asset_id: source.sha256,
                    **{item.asset_id: item.sha256 for item in target.dependencies},
                },
                "postprocessing": [*source_provenance.postprocessing, "scene-revision-restore"],
                "created_at": now,
            })
            self.store.register_asset(source_copy, source_copy_provenance, source_path)
            registered.append(source_copy.id)

            preview_id = f"asset_{uuid.uuid4().hex}"
            preview_provenance_id = f"prov_{uuid.uuid4().hex}"
            preview_parents = [source_copy.id, target.preview_asset_id]
            preview_copy = preview.model_copy(update={
                "id": preview_id,
                "job_id": job.id,
                "parent_asset_ids": preview_parents,
                "provenance_id": preview_provenance_id,
                "suggested_filename": f"media-forge-scene-preview-{preview_id[6:14]}.glb",
                "created_at": now,
            })
            preview_copy_provenance = preview_provenance.model_copy(update={
                "id": preview_provenance_id,
                "asset_id": preview_id,
                "parent_asset_ids": preview_parents,
                "operation": "scene.preview.restore",
                "intent": "Reuse the validated preview for a restored scene revision",
                "runtime_adapter": "scene.revision-restore",
                "runtime_version": __version__,
                "tool_versions": {**preview_provenance.tool_versions, "media-forge": __version__},
                "parameters": {
                    "scene_id": scene_id,
                    "base_revision_id": base_revision_id,
                    "restored_revision_id": target_revision_id,
                },
                "reference_asset_hashes": {
                    source_copy.id: source_copy.sha256,
                    target.preview_asset_id: preview.sha256,
                },
                "postprocessing": [*preview_provenance.postprocessing, "scene-revision-restore"],
                "created_at": now,
            })
            self.store.register_asset(preview_copy, preview_copy_provenance, preview_path)
            registered.append(preview_copy.id)

            restored_document, revision = self.catalog.commit(
                owner,
                scene_id,
                base_revision_id,
                SceneRevisionInput(
                    source_asset_id=source_copy.id,
                    preview_asset_id=preview_copy.id,
                    dependencies=target.dependencies,
                    runtime_id=target.runtime_id,
                    runtime_version=target.runtime_version,
                    validation=target.validation,
                ),
            )
            self.store.update_job(
                job.id,
                status=JobStatus.SUCCEEDED,
                progress=1,
                asset_ids=[source_copy.id, preview_copy.id],
            )
            return {
                **self._scene_projection(restored_document, revision),
                "restored_from_revision_id": target_revision_id,
            }
        except SceneError as exc:
            self._rollback_assets(registered)
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
                    error=ErrorDetail(code="scene_revision_restore_failed", message=str(exc)[:300]),
                )
            raise SceneError(
                "scene_revision_restore_failed", "scene revision could not be restored"
            ) from exc

    def _verified_revision_asset(
        self, asset_id: str, expected_mime: str
    ) -> tuple[Asset, Provenance, Path]:
        try:
            asset = self.store.get_asset(asset_id)
            provenance = self.store.get_provenance(asset_id)
            path = self.store.asset_path(asset_id)
        except KeyError as exc:
            raise SceneError(
                "scene_revision_not_found", "scene revision asset is unavailable"
            ) from exc
        if asset.mime_type != expected_mime:
            raise SceneError(
                "scene_revision_restore_invalid", "scene revision asset type differs"
            )
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != asset.size_bytes
            or self._sha256(path) != asset.sha256
            or provenance.asset_id != asset.id
            or provenance.output_sha256 != asset.sha256
        ):
            raise SceneError(
                "scene_revision_restore_changed", "scene revision asset identity changed"
            )
        return asset, provenance, path

    async def material_targets(self, owner: str, scene_id: str) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        document, revisions = self.catalog.get(owner, scene_id)
        revision = next(item for item in revisions if item.id == document.current_revision_id)
        with self.resolver.runtime_reference(revision.runtime_id) as runtime:
            if runtime is None or runtime.version != revision.runtime_version:
                raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
            result, _ = await self._material_operation(
                self.store.asset_path(revision.source_asset_id), runtime, action="inspect"
            )
        return {
            "schema_version": result["schema_version"],
            "scene_id": scene_id,
            "revision_id": revision.id,
            "targets": result["targets"],
        }

    async def apply_material_binding(
        self,
        owner: str,
        scene_id: str,
        value: MaterialBinding | dict[str, Any],
        *,
        external_job_id: str | None = None,
        runtime_id: str | None = None,
        runtime_version: str | None = None,
    ) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        try:
            binding = value if isinstance(value, MaterialBinding) else MaterialBinding.model_validate(value)
        except ValidationError as exc:
            raise SceneError("scene_material_binding_invalid", "material binding is invalid") from exc
        document, _ = self.catalog.get(owner, scene_id)
        if document.current_revision_id != binding.source_revision_id:
            raise SceneError("scene_revision_conflict", "material source revision is no longer current")
        try:
            texture_asset = self.store.get_asset(binding.image_asset_id)
            texture_path = self.store.asset_path(binding.image_asset_id)
        except KeyError as exc:
            raise SceneError("scene_material_asset_not_found", "material image is unavailable") from exc
        if texture_asset.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise SceneError("scene_material_asset_invalid", "material input must be an image")
        if (
            texture_path.is_symlink()
            or not texture_path.is_file()
            or texture_path.stat().st_size != texture_asset.size_bytes
            or self._sha256(texture_path) != texture_asset.sha256
        ):
            raise SceneError("scene_dependency_changed", "material image identity changed")

        working = self.acquire_working_copy(owner, scene_id)
        try:
            if working.base_revision_id != binding.source_revision_id:
                raise SceneError(
                    "scene_revision_conflict", "material source revision is no longer current"
                )
            runtime = self.resolver.resolve_registered(working.runtime_id)
            if runtime is None or runtime.version != working.runtime_version:
                raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
            if (
                runtime_id is not None
                and (runtime.runtime_id != runtime_id or runtime.version != runtime_version)
            ):
                raise SceneError("scene_runtime_unavailable", "pinned Blender runtime changed")
            source = self.working_path_for_runtime(owner, working.id)
            _, revisions = self.catalog.get(owner, scene_id)
            base = next(item for item in revisions if item.id == working.base_revision_id)
            role = binding.dependency_role()
            dependencies = [item for item in base.dependencies if item.role != role]
            dependencies.append(
                SceneDependency(role=role, asset_id=texture_asset.id, sha256=texture_asset.sha256)
            )
            if len(dependencies) > 128:
                raise SceneError(
                    "scene_dependency_limit", "scene dependency count exceeds its bound"
                )
            result, output = await self._material_operation(
                source,
                runtime,
                action="apply",
                binding=binding,
                texture=texture_path,
            )
            if output is None:
                raise SceneError("scene_material_worker_invalid", "material output is unavailable")
            try:
                os.replace(output, source)
            finally:
                if output.exists():
                    output.unlink()
            committed = await self.commit_working_copy(
                owner,
                working.id,
                dependencies=dependencies,
                operation="scene.material.bind",
                parameters={
                    "binding": binding.model_dump(mode="json"),
                    "material_result": result["binding"],
                },
                external_job_id=external_job_id,
            )
            committed["binding"] = result["binding"]
            return committed
        except BaseException:
            try:
                current = self.store.get_scene_working_copy(owner, working.id)
                if current.state == "active":
                    self.release_working_copy(owner, working.id)
            except SceneError:
                pass
            raise

    async def _material_operation(
        self,
        source: Path,
        runtime: ResolvedBlenderRuntime,
        *,
        action: str,
        binding: MaterialBinding | None = None,
        texture: Path | None = None,
    ) -> tuple[dict[str, Any], Path | None]:
        if self.material_worker is None or self.material_worker.is_symlink() or not self.material_worker.is_file():
            raise SceneError("scene_material_worker_unavailable", "trusted material worker is unavailable")
        root = contained(self.material_root, self.material_root / f"material_{uuid.uuid4().hex}")
        root.mkdir(mode=0o700)
        try:
            staged = contained(root, root / "scene.blend")
            shutil.copyfile(source, staged)
            staged.chmod(0o600)
            result_path = contained(root, root / "result.json")
            output = contained(root, root / "bound.blend")
            sandbox = contained(root, root / "blender-user")
            sandbox.mkdir(mode=0o700)
        except BaseException:
            self._remove_tree(root, self.material_root)
            raise
        command = [
            str(runtime.executable),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python",
            str(self.material_worker),
            "--",
            "--action",
            action,
            "--source",
            "scene.blend",
            "--result",
            "result.json",
            "--expected-version",
            runtime.version,
        ]
        if action == "apply":
            if binding is None or texture is None:
                self._remove_tree(root, self.material_root)
                raise SceneError("scene_material_binding_invalid", "material input is incomplete")
            staged_texture = contained(root, root / "texture.png")
            try:
                self._normalize_texture(texture, staged_texture)
                digest = self._sha256(staged_texture)
                binding_path = contained(root, root / "binding.json")
                self._atomic_json(binding_path, binding.worker_value(texture_sha256=digest))
            except BaseException:
                self._remove_tree(root, self.material_root)
                raise
            command.extend([
                "--texture", "texture.png", "--binding", "binding.json", "--output", "bound.blend",
            ])
        elif action != "inspect":
            self._remove_tree(root, self.material_root)
            raise SceneError("scene_material_action_invalid", "material action is invalid")
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
        retained: Path | None = None
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
                    "scene_material_worker_unavailable", "Blender material worker could not start"
                ) from exc
            stdout_task = asyncio.create_task(_bounded_read(process.stdout))
            stderr_task = asyncio.create_task(_bounded_read(process.stderr))
            try:
                _stdout, _stderr, returncode = await asyncio.wait_for(
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
                    raise SceneError("scene_material_timeout", "Blender material operation timed out") from exc
                raise
            if returncode != 0:
                raise SceneError(
                    "scene_material_rejected", "Blender rejected the material operation"
                )
            if result_path.is_symlink() or not result_path.is_file() or result_path.stat().st_size > MAX_PROCESS_OUTPUT_BYTES:
                raise SceneError("scene_material_worker_invalid", "material worker result is unavailable")
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SceneError("scene_material_worker_invalid", "material worker result is invalid") from exc
            self._validate_material_result(
                result,
                runtime.version,
                action,
                expected_binding=(
                    binding.worker_value(texture_sha256=digest)
                    if action == "apply" and binding is not None
                    else None
                ),
            )
            if action == "apply":
                if output.is_symlink() or not output.is_file() or not 1 <= output.stat().st_size <= MAX_BLEND_BYTES:
                    raise SceneError("scene_material_worker_invalid", "material worker output is invalid")
                with output.open("rb") as stream:
                    if stream.read(7) != b"BLENDER":
                        raise SceneError("scene_material_worker_invalid", "material output is not a Blender file")
                retained = contained(
                    self.material_root, self.material_root / f"bound_{uuid.uuid4().hex}.blend"
                )
                os.replace(output, retained)
            return result, retained
        finally:
            if root.exists():
                self._remove_tree(root, self.material_root)

    @staticmethod
    def _validate_material_result(
        value: object,
        version: str,
        action: str,
        expected_binding: dict[str, object] | None = None,
    ) -> None:
        expected = {
            "schema_version", "blender_version", "background", "autoexec_disabled",
            "action", "targets", "binding",
        }
        if (
            not isinstance(value, dict)
            or set(value) != expected
            or value["schema_version"] != "media-forge.material-operation-result@1"
            or value["blender_version"] != version
            or value["background"] is not True
            or value["autoexec_disabled"] is not True
            or value["action"] != action
        ):
            raise SceneError("scene_material_worker_invalid", "material worker identity differs")
        if action == "inspect":
            if (
                value["binding"] is not None
                or not isinstance(value["targets"], list)
                or len(value["targets"]) > 2_000
            ):
                raise SceneError("scene_material_worker_invalid", "material targets are invalid")
            object_names: set[str] = set()
            for target in value["targets"]:
                if not isinstance(target, dict) or set(target) != {
                    "object_name", "material_slots", "uv_maps"
                }:
                    raise SceneError("scene_material_worker_invalid", "material target fields differ")
                if (
                    not isinstance(target["object_name"], str)
                    or not 1 <= len(target["object_name"]) <= 128
                    or target["object_name"] in object_names
                    or not isinstance(target["material_slots"], list)
                    or not 1 <= len(target["material_slots"]) <= 256
                    or not isinstance(target["uv_maps"], list)
                    or len(target["uv_maps"]) > 64
                ):
                    raise SceneError("scene_material_worker_invalid", "material target exceeds its bound")
                object_names.add(target["object_name"])
                if any(
                    not isinstance(slot, dict)
                    or set(slot) != {"index", "name"}
                    or isinstance(slot["index"], bool)
                    or not isinstance(slot["index"], int)
                    or slot["index"] < 0
                    or slot["index"] > 255
                    or not isinstance(slot["name"], str)
                    or len(slot["name"]) > 128
                    for slot in target["material_slots"]
                ):
                    raise SceneError("scene_material_worker_invalid", "material slots are invalid")
                slot_indexes = [slot["index"] for slot in target["material_slots"]]
                if len(slot_indexes) != len(set(slot_indexes)):
                    raise SceneError("scene_material_worker_invalid", "material slots repeat")
                if any(
                    not isinstance(uv, str) or not 1 <= len(uv) <= 128
                    for uv in target["uv_maps"]
                ):
                    raise SceneError("scene_material_worker_invalid", "UV maps are invalid")
                if len(target["uv_maps"]) != len(set(target["uv_maps"])):
                    raise SceneError("scene_material_worker_invalid", "UV maps repeat")
        else:
            binding = value["binding"]
            fields = {
                "object_name", "material_slot", "material_name", "channel",
                "uv_map", "packed", "texture_sha256",
            }
            if (
                value["targets"] is not None
                or not isinstance(binding, dict)
                or set(binding) != fields
                or expected_binding is None
                or binding["object_name"] != expected_binding["object_name"]
                or isinstance(binding["material_slot"], bool)
                or not isinstance(binding["material_slot"], int)
                or binding["material_slot"] != expected_binding["material_slot"]
                or binding["channel"] != expected_binding["channel"]
                or binding["uv_map"] != expected_binding["uv_map"]
                or binding["texture_sha256"] != expected_binding["texture_sha256"]
                or binding["packed"] is not True
                or not isinstance(binding["material_name"], str)
                or not 1 <= len(binding["material_name"]) <= 128
            ):
                raise SceneError("scene_material_worker_invalid", "material binding result is invalid")

    @staticmethod
    def _normalize_texture(source: Path, destination: Path) -> None:
        try:
            with Image.open(source) as opened:
                opened.load()
                image = ImageOps.exif_transpose(opened)
                width, height = image.size
                if (
                    width < 1
                    or height < 1
                    or width > MAX_TEXTURE_SIDE
                    or height > MAX_TEXTURE_SIDE
                    or width * height > MAX_TEXTURE_PIXELS
                ):
                    raise SceneError("scene_material_asset_invalid", "material image dimensions exceed limits")
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                image.convert(mode).save(destination, format="PNG", compress_level=9)
            destination.chmod(0o600)
        except SceneError:
            raise
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise SceneError("scene_material_asset_invalid", "material image could not be decoded") from exc

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        os.replace(temporary, path)

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
        dependencies: list[SceneDependency] | None = None,
        operation: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[Asset, Asset]:
        now = utc_now()
        source_hash = self._sha256(source)
        source_id = f"asset_{uuid.uuid4().hex}"
        source_provenance_id = f"prov_{uuid.uuid4().hex}"
        provenance_dependencies = (
            dependencies
            if dependencies is not None
            else parent_revision.dependencies if parent_revision is not None else []
        )
        parent_assets = list(dict.fromkeys([
            *([parent_revision.source_asset_id] if parent_revision is not None else []),
            *(dependency.asset_id for dependency in provenance_dependencies),
        ]))
        reference_hashes = {
            dependency.asset_id: dependency.sha256
            for dependency in provenance_dependencies
        }
        if parent_revision is not None:
            reference_hashes[parent_revision.source_asset_id] = self.store.get_asset(
                parent_revision.source_asset_id
            ).sha256
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
            operation=operation or ("scene.import" if parent_revision is None else "scene.commit"),
            intent={
                "scene.material.bind": "Apply scene material binding",
                "scene.recipe.create": "Create a Blender scene from a typed recipe",
                "scene.recipe.edit": "Edit a Blender scene with a typed recipe",
            }.get(
                operation,
                "Import Blender scene" if parent_revision is None else "Commit Blender scene revision",
            ),
            model_id="none",
            model_version="0",
            weights_hash="none",
            license=(
                "generated-local"
                if operation == "scene.recipe.create"
                else "derived"
                if operation in {"scene.recipe.edit", "scene.material.bind"}
                else "user-provided"
            ),
            runtime_adapter=(
                "blender.scene-recipe"
                if operation in {"scene.recipe.create", "scene.recipe.edit"}
                else "blender.scene-document"
            ),
            runtime_version=runtime.version,
            tool_versions={
                "media-forge": __version__,
                "blender": runtime.version,
                **(
                    {"scene-recipe": "1.0.0"}
                    if operation in {"scene.recipe.create", "scene.recipe.edit"}
                    else {}
                ),
            },
            seed=0,
            parameters={"runtime_id": runtime.runtime_id, **(parameters or {})},
            reference_asset_hashes=reference_hashes,
            postprocessing=(
                ["typed-scene-recipe"]
                if operation in {"scene.recipe.create", "scene.recipe.edit"}
                else []
            ),
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
