"""Owned source-domain/real-Blender mesh acceptance, not a live MCP/engine gate.

Produces a stylized character blockout to expose silhouette/garment/hair limitations.
The fixture uses only public recipe inputs; inspection/rendering is a trusted test.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


def loft(identifier: str, rings: list[tuple[float, float, float, float, float]],
         color: list[float], segments: int = 16, metallic: float = 0) -> list[dict[str, Any]]:
    """Each ring is center x/y/z and ellipse x/y radii; outward quad winding."""
    vertices = [[x + rx*math.cos(2*math.pi*i/segments), y + ry*math.sin(2*math.pi*i/segments), z]
                for x, y, z, rx, ry in rings for i in range(segments)]
    faces = [[r*segments+i, r*segments+(i+1)%segments,
              (r+1)*segments+(i+1)%segments, (r+1)*segments+i]
             for r in range(len(rings)-1) for i in range(segments)]
    for top, r in ((False, 0), (True, len(rings)-1)):
        center = len(vertices)
        vertices.append(list(rings[r][:3]))
        for i in range(segments):
            a, b = r*segments+i, r*segments+(i+1)%segments
            faces.append([center, a, b] if top else [center, b, a])
    return [{"type": "mesh.create", "object_id": identifier, "name": identifier,
             "vertices": vertices, "faces": faces, "smooth": True},
            {"type": "material.set", "object_id": identifier, "base_color": color,
             "metallic": metallic, "roughness": .45}]


def character_recipe() -> dict[str, Any]:
    skin, teal, leather = [0.62,.32,.20,1], [.025,.18,.20,1], [.045,.025,.022,1]
    gold, hair = [.63,.36,.10,1], [.06,.022,.015,1]
    operations: list[dict[str, Any]] = []

    def piece(name: str, rings: list[tuple[float, float, float, float, float]], color: list[float], metal: float = 0) -> None:
        operations.extend(loft(name, rings, color, metallic=metal))

    def oval(name: str, center: tuple[float, float, float], radii: tuple[float, float, float], color: list[float]) -> None:
        x, y, z = center
        rx, ry, rz = radii
        piece(name, [(x,y,z+rz*t,rx*math.sqrt(1-t*t),ry*math.sqrt(1-t*t))
                     for t in [-.98,-.8,-.4,0,.4,.8,.98]], color)

    piece("tunic", [(0,0,.70,.26,.16),(0,0,.84,.25,.15),(0,0,1.02,.17,.11),
                    (0,0,1.15,.145,.095),(0,0,1.30,.20,.13),(0,0,1.44,.235,.13),
                    (0,0,1.50,.16,.10)], teal)
    piece("belt", [(0,0,1.055,.169,.116),(0,0,1.115,.153,.109)], gold, .65)
    piece("neck", [(0,0,1.45,.075,.072),(0,0,1.62,.067,.069)], skin)
    piece("head", [(0,-.035,1.59,.060,.075),(0,-.02,1.65,.115,.12),
                   (0,0,1.75,.168,.152),(0,.005,1.85,.170,.155),
                   (0,.015,1.94,.130,.12),(0,.02,1.99,.025,.025)], skin)
    oval("hair_cap", (0,.068,1.86), (.18,.15,.15), hair)
    for index, x in enumerate([-.14,-.07,0,.07,.14]):
        piece(f"hair_lock_{index}", [(x*1.12,-.15,1.77+abs(x)*.25,.006,.008),
              (x*1.10,-.17,1.86,.036,.026),(x,-.09,1.96,.048,.05)], hair)
    oval("nose", (0,-.157,1.752), (.028,.043,.048), skin)
    oval("mouth", (0,-.143,1.673), (.046,.009,.010), [.27,.045,.035,1])
    for side, sign in (("left", -1), ("right", 1)):
        oval(f"ear_{side}", (sign*.165,.008,1.785), (.032,.038,.06), skin)
        oval(f"eye_{side}", (sign*.074,-.138,1.811), (.044,.024,.022), [.85,.86,.79,1])
        oval(f"pupil_{side}", (sign*.074,-.160,1.811), (.013,.007,.016), [.022,.05,.04,1])
        piece(f"sleeve_{side}", [(sign*.40,0,1.01,.047,.053),(sign*.37,0,1.17,.063,.063),
              (sign*.30,0,1.32,.075,.08),(sign*.225,0,1.43,.091,.094)], teal)
        oval(f"hand_{side}", (sign*.414,-.008,.956), (.055,.048,.091), skin)
        piece(f"leg_{side}", [(sign*.115,0,.16,.061,.074),(sign*.12,0,.41,.072,.083),
              (sign*.12,0,.62,.071,.086),(sign*.12,0,.84,.09,.098)], leather)
        piece(f"boot_{side}", [(sign*.115,-.053,.04,.08,.15),(sign*.115,-.048,.10,.083,.15),
              (sign*.115,-.018,.18,.071,.10),(sign*.115,0,.40,.077,.088)], leather)
        piece(f"pauldron_{side}", [(sign*.29,0,1.32,.10,.12),(sign*.28,0,1.39,.128,.15),
              (sign*.25,0,1.49,.094,.10),(sign*.23,0,1.51,.03,.04)], gold, .7)
    return {"name": "Authored mesh adventurer - quality blockout", "recipe": {"operations": operations}}


def inspect(args: argparse.Namespace) -> None:
    import bpy
    from mathutils import Vector
    bpy.ops.wm.open_mainfile(filepath=str(args.source), load_ui=False, use_scripts=False)
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    assert len(meshes) == 28, len(meshes)
    assert all(obj.get("media_forge_id") and all(p.use_smooth for p in obj.data.polygons) for obj in meshes)
    triangles = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
        for material in obj.data.materials:
            material.diffuse_color = material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
    before = triangles
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.glb))
    imported = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    assert len(imported) == len(meshes)
    triangles = sum(len(obj.data.polygons) for obj in imported)
    assert triangles == before
    for obj in imported:
        for material in obj.data.materials:
            material.diffuse_color = material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 8
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.12,.15,.19,1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .5
    for location, energy in [((2,-4,5), 700), ((-3,-2,3), 450), ((0,3,4), 850)]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.shape, light.data.size = energy, "DISK", 4
        light.rotation_euler = (Vector((0,0,1))-light.location).to_track_quat("-Z","Y").to_euler()
    bpy.ops.object.camera_add(location=(2.6,-6,2.7))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0,0,1.05))-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 2.45
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 768, 896, 100
    scene.render.filepath = str(args.evidence_dir / "character.png")
    bpy.ops.render.render(write_still=True)
    print(json.dumps({"real_glb_reimport": True, "mesh_count": len(imported), "triangles": triangles}))


def run(args: argparse.Namespace) -> None:
    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.domain import JobRequest, JobStatus
    from mediaforge.scene_recipes import SceneCreateRequest
    args.evidence_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    app = create_app(Settings(data_dir=args.evidence_dir / "data", blender_legacy_runtime_root=args.runtime_root))
    store, workspace = app.state.store, app.state.scene_workspace
    store.initialize()
    workspace.initialize()
    runtime = workspace.resolver.resolve_active()
    assert runtime is not None
    value = SceneCreateRequest.model_validate(character_recipe())
    job = store.create_job(JobRequest(operation="media.inspect", intent="Owned authored character acceptance"))
    began = time.monotonic()
    result = asyncio.run(workspace.apply_recipe("local", job.id, value,
        runtime_id=runtime.runtime_id, runtime_version=runtime.version))
    store.update_job(job.id, status=JobStatus.SUCCEEDED, phase="complete", progress=1, asset_ids=result["asset_ids"])
    source, glb = (store.asset_path(result["revision"][key]) for key in ("source_asset_id", "preview_asset_id"))
    creation_sec = time.monotonic()-began
    process = subprocess.run([str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
        "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--", "--inspect",
        "--source", str(source), "--glb", str(glb), "--evidence-dir", str(args.evidence_dir)],
        capture_output=True, text=True, timeout=180, check=False)
    print(process.stdout[-4000:])
    assert process.returncode == 0, process.stderr[-2000:]
    evidence = {"mode": "source_domain_real_blender_not_live_mcp", "creation_sec": round(creation_sec,3),
        "operation_count": len(value.recipe.operations), "result": result,
        "files": [{"size": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in (source,glb)], "visual_quality": "requires_review", "engine_import": "NOT TESTED"}
    (args.evidence_dir / "observations.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(evidence,ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--glb", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else None)
    inspect(args) if args.inspect else run(args)
