"""Private, bounded material candidates. Preparing never publishes an Asset/revision.

One manager belongs to one SceneWorkspace. Transport supplies its own connection
identifier, calls cleanup on disconnect and expire periodically, and cancels an
in-flight prepare before disconnect cleanup. No client paths are accepted.
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any
import uuid

from pydantic import ValidationError

from .material_binding import MaterialBinding
from .model_viewer import MODEL_CHUNK_BYTES, ModelViewerSession
from .paths import contained
from .scene_workspace import SceneWorkspace, WORKING_TTL
from .scenes import SceneDependency, SceneError, validate_scene_owner


@dataclass
class _Candidate:
    id: str
    owner: str
    connection: str
    scene_id: str
    binding: MaterialBinding
    root: Path
    expires_at: datetime
    pin: ExitStack
    source_sha256: str = ""
    preview_sha256: str = ""
    dependencies: list[SceneDependency] | None = None
    material_result: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class MaterialPreviewManager:
    MAX_CANDIDATES = 2
    MAX_RECEIPTS = 16

    def __init__(self, workspace: SceneWorkspace) -> None:
        self.workspace = workspace
        self.root = contained(workspace.scene_root, workspace.scene_root / "material-previews")
        self._candidates: dict[str, _Candidate] = {}
        self._lock = asyncio.Lock()

    def initialize(self) -> None:
        """Startup only: abandoned previews are not recovery/committed assets."""
        if self._candidates:
            raise RuntimeError("material preview manager is already active")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for entry in self.root.iterdir():
            if entry.is_symlink():
                entry.unlink()
            elif entry.is_dir():
                self.workspace._remove_tree(entry, self.root)
            else:
                contained(self.root, entry).unlink()

    def _remove(self, candidate: _Candidate) -> None:
        try:
            if candidate.root.is_symlink():
                candidate.root.unlink()
            elif candidate.root.exists():
                self.workspace._remove_tree(candidate.root, self.root)
        finally:
            candidate.pin.close()
            self._candidates.pop(candidate.id, None)

    def _expire(self) -> None:
        for candidate in list(self._candidates.values()):
            if candidate.expires_at <= self.workspace._now():
                self._remove(candidate)

    def _get(self, owner: str, connection: str, candidate_id: str) -> _Candidate:
        self._expire()
        candidate = self._candidates.get(candidate_id)
        if (candidate is None or candidate.owner != validate_scene_owner(owner)
                or candidate.connection != connection):
            raise SceneError("scene_material_preview_unavailable", "material preview is unavailable")
        if candidate.result is None and candidate.root.is_symlink():
            raise SceneError("scene_material_preview_changed", "material candidate identity changed")
        return candidate

    async def expire(self) -> None:
        async with self._lock:
            self._expire()

    async def shutdown(self) -> None:
        async with self._lock:
            for candidate in list(self._candidates.values()):
                self._remove(candidate)

    async def dispatch(self, owner: str, connection: str, method: str,
                       params: dict[str, Any]) -> dict[str, Any]:
        """Strict private transport projection; connection is never client input."""
        fields = {
            "prepare": {"scene_id", "binding"},
            "read": {"candidate_id", "offset", "length"},
            "adopt": {"candidate_id"},
            "discard": {"candidate_id"},
        }
        if method not in fields or set(params) != fields[method]:
            raise SceneError("scene_material_preview_request", "material preview fields differ")
        if method == "prepare":
            return await self.prepare(owner, connection, str(params["scene_id"]), params["binding"])
        candidate_id = str(params["candidate_id"])
        if method == "read":
            return await self.read(owner, connection, candidate_id, params["offset"], params["length"])
        if method == "adopt":
            return await self.adopt(owner, connection, candidate_id)
        await self.discard(owner, connection, candidate_id)
        return {"discarded": True}

    async def cleanup(self, owner: str, connection: str) -> None:
        async with self._lock:
            for candidate in list(self._candidates.values()):
                if candidate.owner == validate_scene_owner(owner) and candidate.connection == connection:
                    self._remove(candidate)

    async def discard(self, owner: str, connection: str, candidate_id: str) -> None:
        async with self._lock:
            self._remove(self._get(owner, connection, candidate_id))

    def _verify_file(self, path: Path, digest: str) -> None:
        try:
            contained(self.workspace.store.data_dir, path)
        except ValueError as exc:
            raise SceneError("scene_material_preview_changed", "material candidate identity changed") from exc
        if path.is_symlink() or not path.is_file() or self.workspace._sha256(path) != digest:
            raise SceneError("scene_material_preview_changed", "material candidate identity changed")

    async def prepare(self, owner: str, connection: str, scene_id: str,
                      value: dict[str, Any] | MaterialBinding) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        if not connection or len(connection) > 128:
            raise ValueError("internal connection identity is required")
        try:
            binding = MaterialBinding.model_validate(value)
        except ValidationError as exc:
            raise SceneError("scene_material_binding_invalid", "material binding is invalid") from exc
        async with self._lock:
            self._expire()
            active = [item for item in self._candidates.values() if item.result is None]
            if (len(active) >= self.MAX_CANDIDATES or len(self._candidates) >= self.MAX_RECEIPTS
                    or any(item.connection == connection and item.owner == owner for item in active)):
                raise SceneError("scene_material_preview_limit", "discard the existing material preview first")
            document, revisions = self.workspace.catalog.get(owner, scene_id)
            if document.current_revision_id != binding.source_revision_id:
                raise SceneError("scene_revision_conflict", "material source revision is no longer current")
            base = next(item for item in revisions if item.id == binding.source_revision_id)
            _, _, source = self.workspace._verified_revision_asset(base.source_asset_id, "application/x-blender")
            try:
                texture = self.workspace.store.get_asset(binding.image_asset_id)
                texture_path = self.workspace.store.asset_path(texture.id)
            except KeyError as exc:
                raise SceneError("scene_material_asset_not_found", "material image is unavailable") from exc
            if texture.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise SceneError("scene_material_asset_invalid", "material input must be an image")
            self._verify_file(texture_path, texture.sha256)
            dependencies = [item for item in base.dependencies if item.role != binding.dependency_role()]
            dependencies.append(SceneDependency(role=binding.dependency_role(), asset_id=texture.id, sha256=texture.sha256))
            if len(dependencies) > 128:
                raise SceneError("scene_dependency_limit", "scene dependency count exceeds its bound")
            candidate_id = f"materialpreview_{uuid.uuid4().hex}"
            candidate = _Candidate(candidate_id, owner, connection, scene_id, binding,
                                   contained(self.root, self.root / candidate_id),
                                   self.workspace._now() + WORKING_TTL, ExitStack(), dependencies=dependencies)
            output: Path | None = None
            preview: Path | None = None
            try:
                candidate.root.mkdir(mode=0o700)
                runtime = candidate.pin.enter_context(self.workspace.resolver.runtime_reference(base.runtime_id))
                if runtime is None or runtime.version != base.runtime_version:
                    raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
                result, output = await self.workspace._material_operation(source, runtime, action="apply", binding=binding, texture=texture_path)
                if output is None:
                    raise SceneError("scene_material_worker_invalid", "material output is unavailable")
                prepared = candidate.root / "scene.blend"
                shutil.copyfile(output, prepared)
                prepared.chmod(0o600)
                candidate.source_sha256 = self.workspace._sha256(prepared)
                preview, _, _ = await self.workspace._validate(prepared, runtime)
                ModelViewerSession._validate_browser_memory(preview)
                shutil.copyfile(preview, candidate.root / "preview.glb")
                (candidate.root / "preview.glb").chmod(0o600)
                candidate.preview_sha256 = self.workspace._sha256(candidate.root / "preview.glb")
                candidate.material_result = result["binding"]
                if candidate.expires_at <= self.workspace._now():
                    raise SceneError("scene_material_preview_unavailable", "material preview expired during preparation")
                self._candidates[candidate.id] = candidate
                return {"candidate_id": candidate.id, "scene_id": scene_id,
                        "base_revision_id": base.id, "saved": False,
                        "expires_at": candidate.expires_at.isoformat(),
                        "sha256": candidate.preview_sha256,
                        "total_bytes": (candidate.root / "preview.glb").stat().st_size,
                        "chunk_bytes": MODEL_CHUNK_BYTES}
            except BaseException:
                self._remove(candidate)
                raise
            finally:
                for path in (output, preview):
                    if path is not None and path.exists():
                        path.unlink()

    async def read(self, owner: str, connection: str, candidate_id: str,
                   offset: int, length: int = MODEL_CHUNK_BYTES) -> dict[str, Any]:
        async with self._lock:
            candidate = self._get(owner, connection, candidate_id)
            if candidate.result is not None:
                raise SceneError("scene_material_preview_unavailable", "material preview was already adopted")
            path = candidate.root / "preview.glb"
            self._verify_file(path, candidate.preview_sha256)
            total = path.stat().st_size
            if (type(offset) is not int or type(length) is not int
                    or not 0 <= offset < total or not 1 <= length <= MODEL_CHUNK_BYTES):
                raise SceneError("scene_material_preview_range", "material preview byte range is invalid")
            with path.open("rb") as stream:
                stream.seek(offset)
                content = stream.read(length)
            return {"candidate_id": candidate.id, "offset": offset, "total_bytes": total,
                    "base64": base64.b64encode(content).decode("ascii")}

    async def adopt(self, owner: str, connection: str, candidate_id: str) -> dict[str, Any]:
        async with self._lock:
            candidate = self._get(owner, connection, candidate_id)
            if candidate.result is not None:
                return deepcopy(candidate.result)
            document, _ = self.workspace.catalog.get(owner, candidate.scene_id)
            if document.current_revision_id != candidate.binding.source_revision_id:
                raise SceneError("scene_revision_conflict", "scene changed after material preview")
            self._verify_file(candidate.root / "scene.blend", candidate.source_sha256)
            self._verify_file(candidate.root / "preview.glb", candidate.preview_sha256)
            for dependency in candidate.dependencies or []:
                try:
                    path = self.workspace.store.asset_path(dependency.asset_id)
                    self._verify_file(path, dependency.sha256)
                except KeyError as exc:
                    raise SceneError("scene_dependency_changed", "material dependency is unavailable") from exc
            working = await self.workspace.acquire_working_copy_async(owner, candidate.scene_id)
            try:
                if working.base_revision_id != candidate.binding.source_revision_id:
                    raise SceneError("scene_revision_conflict", "scene changed after material preview")
                target = self.workspace.working_path_for_runtime(owner, working.id)
                shutil.copyfile(candidate.root / "scene.blend", target)
                self._verify_file(target, candidate.source_sha256)
                adoption = asyncio.create_task(self.workspace.commit_working_copy(
                    owner, working.id, dependencies=candidate.dependencies,
                    operation="scene.material.bind",
                    parameters={"binding": candidate.binding.model_dump(mode="json"),
                                "material_result": candidate.material_result,
                                "preview_candidate_id": candidate.id,
                                "preview_source_sha256": candidate.source_sha256,
                                "preview_glb_sha256": candidate.preview_sha256},
                ))
                # Explicit adoption is atomic from the client's perspective. A
                # disconnected request must not abandon its commit/job halfway.
                canceled = False
                while True:
                    try:
                        result = await asyncio.shield(adoption)
                        break
                    except asyncio.CancelledError:
                        if adoption.cancelled():
                            raise
                        canceled = True
                candidate.result = deepcopy(result)
                candidate.pin.close()
                self.workspace._remove_tree(candidate.root, self.root)
                if canceled:
                    raise asyncio.CancelledError
                return deepcopy(result)
            except BaseException:
                current = self.workspace.store.get_scene_working_copy(owner, working.id)
                if current.state == "active":
                    self.workspace.release_working_copy(owner, working.id)
                raise
