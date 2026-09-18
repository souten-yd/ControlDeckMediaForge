"""Execute trusted observation under the existing scene Job/runtime lifecycle."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
import uuid

from PIL import Image

from . import __version__
from .domain import Asset, Provenance
from .paths import contained
from .scene_observation import SceneObserveRequest
from .scenes import SceneError
from .store import utc_now

if TYPE_CHECKING:
    from .scene_workspace import SceneWorkspace

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_RESULT_BYTES = 128 * 1024


async def observe(
    workspace: "SceneWorkspace", owner: str, job_id: str, value: SceneObserveRequest,
    *, runtime_id: str, runtime_version: str,
) -> dict[str, Any]:
    from .scene_workspace import _bounded_read, _stop_process

    document, revisions = workspace.catalog.get(owner, value.scene_id)
    revision = next((item for item in revisions if item.id == value.revision_id), None)
    if revision is None:
        raise SceneError("scene_revision_not_found", "observation revision is unavailable")
    if (revision.runtime_id, revision.runtime_version) != (runtime_id, runtime_version):
        raise SceneError("scene_runtime_unavailable", "observation runtime changed")
    worker = workspace.observation_worker
    if worker is None or worker.is_symlink() or not worker.is_file():
        raise SceneError("scene_observation_worker_unavailable", "trusted observation worker is unavailable")
    source_asset, _, source = workspace._verified_revision_asset(revision.source_asset_id, "application/x-blender")
    root = contained(workspace.observation_root, workspace.observation_root / f"observe_{uuid.uuid4().hex}")
    root.mkdir(mode=0o700)
    registered: list[str] = []
    try:
        staged = root / "source.blend"
        shutil.copyfile(source, staged)
        staged.chmod(0o600)
        if workspace._sha256(staged) != source_asset.sha256:
            raise SceneError("scene_revision_restore_changed", "staged observation source changed")
        (root / "observation.json").write_text(value.observation.model_dump_json())
        sandbox = root / "blender-user"
        sandbox.mkdir(mode=0o700)
        environment = {
            "PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1", "HOME": str(sandbox),
            "XDG_CACHE_HOME": str(sandbox / "cache"), "XDG_CONFIG_HOME": str(sandbox / "config"),
            "XDG_DATA_HOME": str(sandbox / "data"), "BLENDER_USER_CONFIG": str(sandbox / "blender-config"),
            "BLENDER_USER_SCRIPTS": str(sandbox / "blender-scripts"),
            "BLENDER_USER_DATAFILES": str(sandbox / "blender-data"),
            "LIBGL_ALWAYS_SOFTWARE": "1", "CUDA_VISIBLE_DEVICES": "", "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
        }
        with workspace.resolver.runtime_reference(runtime_id) as runtime:
            if runtime is None or runtime.version != runtime_version:
                raise SceneError("scene_runtime_unavailable", "pinned observation runtime is unavailable")
            process = await asyncio.create_subprocess_exec(
                str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
                "--python-exit-code", "1", "--python", str(worker), "--", "--expected-version", runtime_version,
                cwd=root, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=environment, start_new_session=True,
            )
            readers = [asyncio.create_task(_bounded_read(stream)) for stream in (process.stdout, process.stderr)]
            try:
                _, _, code = await asyncio.wait_for(
                    asyncio.gather(*readers, process.wait()), timeout=workspace.process_timeout_sec
                )
            except BaseException as exc:
                cleanup = asyncio.create_task(_stop_process(process))
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        continue
                cleanup.result()
                for reader in readers:
                    if not reader.done():
                        reader.cancel()
                await asyncio.gather(*readers, return_exceptions=True)
                if isinstance(exc, TimeoutError):
                    raise SceneError("scene_observation_timeout", "scene observation timed out") from exc
                raise
            if code != 0:
                raise SceneError("scene_observation_failed", "scene observation worker failed")
        result_path = root / "result.json"
        if result_path.is_symlink() or not result_path.is_file() or result_path.stat().st_size > MAX_RESULT_BYTES:
            raise SceneError("scene_observation_invalid", "observation report is unavailable or exceeds its bound")
        try:
            result = json.loads(result_path.read_text())
            validate_report(result, value, runtime_version)
        except (ValueError, TypeError, KeyError) as exc:
            raise SceneError("scene_observation_invalid", "observation report differs from the request") from exc
        images = []
        # Validate every image before registering any Asset.
        outputs: list[tuple[str, Path]] = []
        for view in value.observation.views:
            candidate = root / f"{view}.png"
            if candidate.is_symlink():
                raise SceneError("scene_observation_invalid", "observation image cannot be a symlink")
            path = contained(root, candidate)
            if not path.is_file() or not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
                raise SceneError("scene_observation_invalid", "observation image exceeds its bound")
            try:
                with Image.open(path) as image:
                    if image.format != "PNG" or image.size != (value.observation.resolution,) * 2:
                        raise ValueError("image type or dimensions differ")
                    image.verify()
                # Blender embeds its private source path, date and timing in PNG
                # metadata even without a visible stamp. Publish pixels only.
                with Image.open(path) as image:
                    clean = Image.new("RGB", image.size)
                    clean.paste(image.convert("RGB"))
                    clean.save(path, format="PNG")
                if path.stat().st_size > MAX_IMAGE_BYTES:
                    raise ValueError("normalized image exceeds bound")
            except (OSError, ValueError) as exc:
                raise SceneError("scene_observation_invalid", "observation image is invalid") from exc
            outputs.append((view, path))
        for view, path in outputs:
            now = utc_now()
            asset_id, provenance_id = f"asset_{uuid.uuid4().hex}", f"prov_{uuid.uuid4().hex}"
            digest = workspace._sha256(path)
            asset = Asset(
                id=asset_id, job_id=job_id, parent_asset_ids=[source_asset.id], mime_type="image/png",
                width=value.observation.resolution, height=value.observation.resolution,
                size_bytes=path.stat().st_size, sha256=digest,
                suggested_filename=f"scene-{revision.id[9:17]}-{value.observation.mode}-{view}.png",
                provenance_id=provenance_id, created_at=now,
            )
            provenance = Provenance(
                id=provenance_id, asset_id=asset_id, parent_asset_ids=[source_asset.id],
                operation="scene.observe", intent="Observe a fixed Blender scene revision",
                model_id="none", model_version="0", weights_hash="none", license="derived",
                runtime_adapter="blender.scene-observation", runtime_version=runtime_version,
                tool_versions={"media-forge": __version__, "blender": runtime_version}, seed=0,
                parameters={"scene_id": value.scene_id, "revision_id": revision.id, "runtime_id": runtime_id,
                            "view": view, "observation": value.observation.model_dump(mode="json")},
                reference_asset_hashes={source_asset.id: source_asset.sha256}, postprocessing=[],
                validation=[{"validator": "scene.observation", "status": "passed", "device": "CPU",
                             "frame": 0, "samples": 16}], warnings=[], output_sha256=digest, created_at=now,
            )
            workspace.store.register_asset(asset, provenance, path)
            registered.append(asset_id)
            images.append({"view": view, "asset_id": asset_id, "sha256": digest})
        return {"scene": document.model_dump(mode="json"), "revision": revision.model_dump(mode="json"),
                "asset_ids": registered, "observation": value.observation.model_dump(mode="json"),
                "images": images, "object_colors": result["object_colors"],
                "renderer": {"runtime_id": runtime_id, "version": runtime_version, "device": "CPU",
                             "frame": 0, "samples": 16}, "semantic_review": "not_tested"}
    except BaseException:
        workspace._rollback_assets(registered)
        raise
    finally:
        workspace._remove_tree(root, workspace.observation_root)


def validate_report(result: Any, value: SceneObserveRequest, runtime_version: str) -> None:
    if not isinstance(result, dict) or result.get("schema_version") != "media-forge.scene-observation-result@1":
        raise ValueError("invalid report")
    if result.get("observation") != value.observation.model_dump(mode="json") or result.get("blender_version") != runtime_version:
        raise ValueError("report identity differs")
    if result.get("device") != "CPU" or result.get("autoexec_disabled") is not True or result.get("frame") != 0 or result.get("samples") != 16:
        raise ValueError("report execution differs")
    if result.get("images") != [{"view": view, "filename": f"{view}.png"} for view in value.observation.views]:
        raise ValueError("report images differ")
    colors = result.get("object_colors")
    if not isinstance(colors, list) or len(colors) > 256 or (value.observation.mode != "object_id" and colors):
        raise ValueError("object colors exceed bound")
    for item in colors:
        if not isinstance(item, dict) or set(item) != {"object_id", "object_name", "color_rgb"}:
            raise ValueError("invalid object colors")
        if not isinstance(item["object_name"], str) or len(item["object_name"]) > 256:
            raise ValueError("invalid object name")
        if item["object_id"] is not None and (not isinstance(item["object_id"], str) or len(item["object_id"]) > 64):
            raise ValueError("invalid object id")
        color = item["color_rgb"]
        if not isinstance(color, list) or len(color) != 3 or any(type(c) not in (int, float) or not 0 <= c <= 1 for c in color):
            raise ValueError("invalid object color")
