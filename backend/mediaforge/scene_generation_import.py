"""Commit generated GLB through the existing Blender/Scene/Asset boundaries."""

from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
import uuid

from .domain import ErrorDetail, JobRequest, JobStatus
from .glb import GlbValidationError, validate_glb_path
from .paths import contained
from .scene_generation import GenerationFacts, SceneFromImageRequest
from .scenes import SceneDependency, SceneError, SceneRevisionInput, validate_scene_owner

if TYPE_CHECKING:
    from .blender_runtime import ResolvedBlenderRuntime
    from .scene_workspace import SceneWorkspace


async def _import_worker(workspace: SceneWorkspace, root: Path, runtime: ResolvedBlenderRuntime) -> Path:
    from .scene_workspace import _bounded_read, _stop_process

    worker = workspace.generation_import_worker
    if worker is None or worker.is_symlink() or not worker.is_file():
        raise SceneError("scene_worker_unavailable", "generated GLB importer is unavailable")
    sandbox = root / "blender-user"
    sandbox.mkdir(mode=0o700)
    environment = {
        "PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1", "HOME": str(sandbox),
        "XDG_CACHE_HOME": str(sandbox / "cache"), "XDG_CONFIG_HOME": str(sandbox / "config"),
        "XDG_DATA_HOME": str(sandbox / "data"), "BLENDER_USER_CONFIG": str(sandbox / "blender-config"),
        "BLENDER_USER_SCRIPTS": str(sandbox / "blender-scripts"),
        "BLENDER_USER_DATAFILES": str(sandbox / "blender-data"),
        "LIBGL_ALWAYS_SOFTWARE": "1", "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "", "ROCR_VISIBLE_DEVICES": "",
    }
    try:
        process = await asyncio.create_subprocess_exec(
            str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
            "--python", str(worker), "--", "--expected-version", runtime.version,
            cwd=root, env=environment, start_new_session=True,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise SceneError("scene_worker_unavailable", "generated GLB importer could not start") from exc
    readers = [asyncio.create_task(_bounded_read(process.stdout)), asyncio.create_task(_bounded_read(process.stderr))]
    try:
        _, _, code = await asyncio.wait_for(
            asyncio.gather(*readers, process.wait()), timeout=workspace.process_timeout_sec,
        )
        if code != 0:
            raise SceneError("scene_generation_import_failed", "Blender rejected the generated GLB")
    except BaseException as exc:
        await _stop_process(process)
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        if isinstance(exc, TimeoutError):
            raise SceneError("scene_worker_timeout", "generated GLB import timed out") from exc
        raise
    return contained(root, root / "generated.blend")


async def import_generated_glb(
    workspace: SceneWorkspace, owner: str, job_id: str, value: SceneFromImageRequest,
    source: Path, source_root: Path, facts: GenerationFacts, *, runtime_id: str, runtime_version: str,
    scene_id: str | None = None, base_revision_id: str | None = None,
) -> dict[str, Any]:
    """Only an internal generation caller can provide the staging path and facts.

    `scene_id` / `base_revision_id` を渡すと、新しいシーンを作らずに既存シーンの
    次の版として commit する。2 段目（Pixal3D）の成果物を、1 段目と同じシーンに
    並べて残すための経路であり、外から呼べる API は増やしていない。
    """
    owner = validate_scene_owner(owner)
    appending = scene_id is not None and base_revision_id is not None
    if facts.seed != value.seed or facts.resolution != value.resolution:
        raise SceneError("scene_generation_invalid", "generation facts differ from the request")
    input_asset = workspace.store.get_asset(value.input_asset_id)
    if not input_asset.mime_type.startswith("image/"):
        raise SceneError("scene_generation_input_invalid", "generation requires an image Asset")
    dependency = SceneDependency(role="generation_input", asset_id=input_asset.id, sha256=input_asset.sha256)
    workspace._verified_revision_asset(input_asset.id, input_asset.mime_type)
    try:
        validate_glb_path(source, source_root)
    except (GlbValidationError, ValueError, OSError) as exc:
        raise SceneError("scene_generation_invalid", "generated GLB failed independent validation") from exc
    if workspace._sha256(source) != facts.output_sha256:
        raise SceneError("scene_generation_invalid", "generated GLB hash differs from worker output")
    root = contained(workspace.recipe_root, workspace.recipe_root / f"generation_{uuid.uuid4().hex}")
    root.mkdir(mode=0o700)
    registered: list[str] = []
    preview: Path | None = None
    try:
        staged = root / "generated.glb"
        shutil.copyfile(source, staged)
        staged.chmod(0o600)
        if workspace._sha256(staged) != facts.output_sha256:
            raise SceneError("scene_generation_invalid", "generated GLB changed while staging")
        validate_glb_path(staged, root)
        with workspace.resolver.runtime_reference(runtime_id) as runtime:
            if runtime is None or runtime.version != runtime_version:
                raise SceneError("scene_runtime_unavailable", "pinned Blender runtime is unavailable")
            if appending:
                document, revisions = workspace.catalog.get(owner, str(scene_id))
                if document.current_revision_id != base_revision_id:
                    raise SceneError("scene_revision_conflict", "scene current revision changed")
                parent = next((item for item in revisions if item.id == base_revision_id), None)
                if parent is None:
                    raise SceneError("scene_revision_not_found", "scene revision is unavailable")
                if runtime.runtime_id != parent.runtime_id or runtime.version != parent.runtime_version:
                    raise SceneError("scene_runtime_unavailable", "scene Blender runtime is unavailable")
            blend = await _import_worker(workspace, root, runtime)
            preview, blender_facts, glb_facts = await workspace._validate(blend, runtime)
            current, _, _ = workspace._verified_revision_asset(input_asset.id, input_asset.mime_type)
            if current.sha256 != dependency.sha256:
                raise SceneError("scene_generation_input_invalid", "generation input changed")
            # 版の親子は catalog が記録する。Asset の lineage は「何から作られたか」で、
            # 後段は前段の .blend からではなく同じ入力画像から作られている。
            # 前段を親として名乗らせない（来歴に嘘を入れない）。
            source_asset, preview_asset = workspace._register_assets(
                job_id, blend, preview, runtime, blender_facts, glb_facts,
                parent_revision=None, dependencies=[dependency], operation="scene.from_image",
                parameters={"generation": facts.model_dump(mode="json")}, generation=facts,
            )
            registered.extend([source_asset.id, preview_asset.id])
            revision_input = SceneRevisionInput(
                source_asset_id=source_asset.id, preview_asset_id=preview_asset.id,
                dependencies=[dependency], runtime_id=runtime.runtime_id, runtime_version=runtime.version,
                validation=workspace._validation(blender_facts, glb_facts),
            )
            if appending:
                document, revision = workspace.catalog.commit(
                    owner, str(scene_id), str(base_revision_id), revision_input,
                )
            else:
                document, revision = workspace.catalog.create(
                    owner, name=value.name, tags=value.tags, collection=value.collection,
                    revision=revision_input,
                )
            return {**workspace._scene_projection(document, revision), "asset_ids": registered,
                    "generation": facts.model_dump(mode="json")}
    except BaseException:
        workspace._rollback_assets(registered)
        raise
    finally:
        if preview is not None and preview.exists():
            preview.unlink()
        workspace._remove_tree(root, workspace.recipe_root)


MAX_LIBRARY_GLB_BYTES = 256 * 1024 * 1024


async def import_library_glb(
    workspace: SceneWorkspace, owner: str, asset_id: str, name: str,
    tags: list[str], collection: str,
) -> dict[str, Any]:
    """Make an editable scene out of a GLB that is already in the shared Library.

    生成で作ったシーンは版として残るが、ライブラリに単体で置いた GLB には
    シーンが無く、Web Blender で開けなかった。取り込みは既存の経路をそのまま
    通す（隔離した Blender で GLB を読み、検証してから版を作る）。新しい
    検証経路も第二の Jobs 基盤も作らない。
    """
    from .scenes import SceneRevisionInput

    owner = validate_scene_owner(owner)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise SceneError("scene_name_invalid", "scene name must be 1 to 120 characters")
    asset = workspace.store.get_asset(asset_id)
    if asset.mime_type != "model/gltf-binary":
        raise SceneError("scene_source_invalid", "editing requires a GLB Asset")
    if not 1 <= asset.size_bytes <= MAX_LIBRARY_GLB_BYTES:
        raise SceneError("scene_source_invalid", "GLB Asset exceeds the editable size bound")
    # 版の元になっている GLB は、その版を開けばよい。二重に別シーンを作らせない。
    if workspace.store.scene_revision_for_preview(asset_id) is not None:
        raise SceneError("scene_source_in_use", "this GLB already belongs to a scene revision")
    verified, _, source = workspace._verified_revision_asset(asset.id, asset.mime_type)
    dependency = SceneDependency(role="source_glb", asset_id=asset.id, sha256=verified.sha256)
    runtime = workspace.resolver.resolve_active()
    if runtime is None:
        raise SceneError("scene_runtime_unavailable", "active Blender runtime is unavailable")
    root = contained(workspace.recipe_root, workspace.recipe_root / f"library_{uuid.uuid4().hex}")
    root.mkdir(mode=0o700)
    registered: list[str] = []
    preview: Path | None = None
    job_id: str | None = None
    committed = False
    try:
        staged = root / "generated.glb"
        shutil.copyfile(source, staged)
        staged.chmod(0o600)
        if workspace._sha256(staged) != verified.sha256:
            raise SceneError("scene_source_invalid", "GLB Asset changed while staging")
        validate_glb_path(staged, root)
        job = workspace.store.create_job(JobRequest(
            operation="media.inspect", intent="Open a Library GLB as an editable scene",
        ))
        job_id = job.id
        workspace.store.update_job(job_id, status=JobStatus.RUNNING, phase="validating", progress=0.2)
        with workspace.resolver.runtime_reference(runtime.runtime_id) as pinned:
            if pinned is None or pinned.version != runtime.version:
                raise SceneError("scene_runtime_unavailable", "active Blender runtime is unavailable")
            blend = await _import_worker(workspace, root, pinned)
            preview, blender_facts, glb_facts = await workspace._validate(blend, pinned)
            current, _, _ = workspace._verified_revision_asset(asset.id, asset.mime_type)
            if current.sha256 != dependency.sha256:
                raise SceneError("scene_source_invalid", "GLB Asset changed during import")
            source_asset, preview_asset = workspace._register_assets(
                job_id, blend, preview, pinned, blender_facts, glb_facts,
                parent_revision=None, dependencies=[dependency], operation="scene.from_glb",
                parameters={"source_asset_id": asset.id, "source_sha256": dependency.sha256},
            )
            registered.extend([source_asset.id, preview_asset.id])
            document, revision = workspace.catalog.create(
                owner, name=name.strip(), tags=tags, collection=collection,
                revision=SceneRevisionInput(
                    source_asset_id=source_asset.id, preview_asset_id=preview_asset.id,
                    dependencies=[dependency], runtime_id=pinned.runtime_id,
                    runtime_version=pinned.version,
                    validation=workspace._validation(blender_facts, glb_facts),
                ),
            )
            committed = True
            workspace.store.update_job(job_id, status=JobStatus.SUCCEEDED, progress=1, asset_ids=registered)
            return {**workspace._scene_projection(document, revision), "asset_ids": registered}
    except (Exception, asyncio.CancelledError) as exc:
        if not committed:
            workspace._rollback_assets(registered)
            if job_id is not None:
                workspace.store.update_job(
                    job_id,
                    status=JobStatus.CANCELED if isinstance(exc, asyncio.CancelledError) else JobStatus.FAILED,
                    error=ErrorDetail(code=getattr(exc, "code", "scene_source_import_failed"),
                                      message="Library GLB import did not complete"),
                )
        if isinstance(exc, (SceneError, asyncio.CancelledError)):
            raise
        raise SceneError("scene_source_import_failed", "Library GLB import did not complete") from exc
    finally:
        if preview is not None and preview.exists():
            preview.unlink()
        workspace._remove_tree(root, workspace.recipe_root)
