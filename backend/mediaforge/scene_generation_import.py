"""Commit generated GLB through the existing Blender/Scene/Asset boundaries."""

from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
import uuid

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
