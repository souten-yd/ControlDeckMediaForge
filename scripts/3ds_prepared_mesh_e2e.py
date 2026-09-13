"""Execute a saved, bounded draft through real source-domain Blender.

Local diagnostic only: not OpenCode, MCP, installed acceptance or an AI generator.
The caller owns an empty evidence directory and retains the upstream AI trace.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


def inspect(args: argparse.Namespace) -> None:
    import bpy
    from mathutils import Vector

    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()), load_ui=False, use_scripts=False)
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    assert len(meshes) == 1
    source = meshes[0]
    source.data.calc_loop_triangles()
    triangles = len(source.data.loop_triangles)
    original_dimensions = list(source.dimensions)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.glb.resolve()))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    assert len(meshes) == 1
    mesh = meshes[0]
    mesh.data.calc_loop_triangles()
    assert len(mesh.data.loop_triangles) == triangles
    assert all(abs(a-b) < 1e-5 for a, b in zip(original_dimensions, mesh.dimensions))
    center = sum((mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box), Vector()) / 8
    size = max(mesh.dimensions)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Diagnostic world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .5
    for offset in ((2, -3, 3), (-2, 2, 2)):
        bpy.ops.object.light_add(type="AREA", location=center + Vector(offset)*size)
        light = bpy.context.object
        light.data.energy = 100
        light.data.size = size*3
        light.rotation_euler = (center-light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = size*1.3
    scene.camera = camera
    scene.render.resolution_x = scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    for name, direction in (("front", (0, -3, 0)), ("side", (3, 0, 0)), ("oblique", (2, -3, 1))):
        camera.location = center + Vector(direction)*size
        camera.rotation_euler = (center-camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(args.evidence_dir / f"{name}.png")
        bpy.ops.render.render(write_still=True)
    # Diagnostic shading only; never resave or alter the source/export assets.
    for polygon in mesh.data.polygons:
        polygon.use_smooth = False
    for material in mesh.data.materials:
        node = material.node_tree.nodes.get("Principled BSDF")
        assert node is not None
        node.inputs["Base Color"].default_value = (.5, .5, .5, 1)
        node.inputs["Metallic"].default_value = 0
        node.inputs["Roughness"].default_value = 1
    scene.render.filepath = str(args.evidence_dir / "clay_oblique.png")
    bpy.ops.render.render(write_still=True)
    print(json.dumps({"real_glb_reimport": True, "triangles": triangles,
                      "dimensions_meters": list(mesh.dimensions), "render_device": "CPU"}))


def run(args: argparse.Namespace) -> None:
    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.domain import ErrorDetail, JobRequest, JobStatus
    from mediaforge.scene_recipes import MeshCreate, SceneCreateRequest

    root = args.evidence_dir.resolve(strict=True)
    assert root.is_dir() and not any(root.iterdir()), "Use an empty owned evidence directory"
    recipe = args.recipe.resolve(strict=True)
    assert recipe.stat().st_size <= 8192
    raw = recipe.read_bytes()
    request = SceneCreateRequest.model_validate_json(raw)
    assert len(request.recipe.operations) == 2 and isinstance(request.recipe.operations[0], MeshCreate)
    registry = root / "runtime-registry.json"
    shutil.copyfile(args.registry.resolve(strict=True), registry)
    app = create_app(Settings(data_dir=root / "data", blender_runtime_registry=registry,
                              blender_managed_runtime_root=args.runtime_root.resolve(strict=True)))
    store, workspace = app.state.store, app.state.scene_workspace
    store.initialize()
    workspace.initialize()
    runtime = workspace.resolver.resolve_active()
    assert runtime is not None
    job = store.create_job(JobRequest(operation="media.inspect", intent="Saved AI draft source acceptance"))
    started = time.monotonic()
    try:
        result = asyncio.run(workspace.apply_recipe("local", job.id, request,
            runtime_id=runtime.runtime_id, runtime_version=runtime.version,
            preparation={"diagnostic": "saved_draft_source_execution_not_live_mcp",
                         "input_sha256": hashlib.sha256(raw).hexdigest(), "quality_status": "NOT TESTED"}))
    except Exception:
        store.update_job(job.id, status=JobStatus.FAILED, phase="failed", progress=0,
                         error=ErrorDetail(code="saved_draft_execution_failed", message="Source diagnostic failed"))
        raise
    store.update_job(job.id, status=JobStatus.SUCCEEDED, phase="complete", progress=1,
                     asset_ids=result["asset_ids"])
    creation_sec = time.monotonic() - started
    source, glb = (store.asset_path(result["revision"][key]) for key in ("source_asset_id", "preview_asset_id"))
    process = subprocess.run([str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
        "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--", "--inspect",
        "--source", str(source), "--glb", str(glb), "--evidence-dir", str(root)],
        capture_output=True, text=True, timeout=180, check=False)
    print(process.stdout[-2000:])
    assert process.returncode == 0, process.stderr[-2000:]
    evidence: dict[str, Any] = {"mode": "saved_draft_source_execution_not_live_mcp",
        "creation_sec": round(creation_sec, 3), "runtime_version": runtime.version, "result": result,
        "files": [{"asset_id": result["revision"][key], "bytes": path.stat().st_size,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for key, path in (("source_asset_id", source), ("preview_asset_id", glb))],
        "images": [{"file": name + ".png", "sha256": hashlib.sha256((root / (name + ".png")).read_bytes()).hexdigest(),
                    "source_asset_id": result["revision"]["preview_asset_id"],
                    "revision_id": result["revision"]["id"], "render_device": "CPU", "samples": 16,
                    "diagnostic_flat_clay": name == "clay_oblique"}
                   for name in ("front", "side", "oblique", "clay_oblique")],
        "engine_import": "NOT TESTED", "visual_quality": "requires_review"}
    (root / "observations.json").write_text(json.dumps(evidence, indent=2)+"\n")
    print(json.dumps(evidence))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true")
    for name in ("source", "glb", "recipe", "registry", "runtime-root"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else None)
    inspect(args) if args.inspect else run(args)
