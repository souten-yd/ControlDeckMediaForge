"""Actual clip evaluation/reimport diagnostic for the typed robot rig."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def clip(name: str) -> dict[str, Any]:
    end, bone, angle = (48, "spine", 3) if name == "idle" else (24, "forearm", -60)
    return {"type": "animation.clip", "object_id": "rig", "clip_id": name, "name": name,
            "fps": 24, "frame_count": end, "loop": True, "tracks": [{"bone_id": bone, "keys": [
                {"frame": 0, "rotation_degrees": [0,0,0]},
                {"frame": end//2, "rotation_degrees": [angle,0,0]},
                {"frame": end, "rotation_degrees": [0,0,0]}]}]}


def recipe() -> list[dict[str, Any]]:
    from rig_fixture import recipe as rig_recipe
    return rig_recipe() + [clip("idle")]


def inspect_blend(source: Path, glb: Path, folder: Path, *, edited: bool) -> None:
    import importlib.util
    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    rig = next(o for o in bpy.data.objects if o.get("media_forge_id") == "rig")
    names = ("idle", "arm_swing") if edited else ("idle",)
    actions = {a["media_forge_clip_id"]: a for a in bpy.data.actions if a.get("media_forge_clip_schema") == 1}
    assert set(actions) == set(names)
    spec = importlib.util.spec_from_file_location("motion_worker", Path(__file__).parents[1] / "worker_packs/blender/scene_recipe.py")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    objects = {o.get("media_forge_id"): o for o in bpy.data.objects if o.get("media_forge_id")}
    original_count = len(bpy.data.actions)
    for kind in ("duplicate", "fps"):
        request = clip("idle" if kind == "duplicate" else "probe")
        if kind == "fps":
            bpy.context.scene.render.fps = 30
        try:
            worker.create_clip(rig, request, objects)
        except RuntimeError as exc:
            assert ("already exists" if kind == "duplicate" else "fps") in str(exc)
        else:
            raise AssertionError("Invalid clip addition succeeded: " + kind)
        finally:
            bpy.context.scene.render.fps = 24
        assert len(bpy.data.actions) == original_count

    def curves(action: Any) -> list[Any]:
        return [(f.data_path, f.array_index, [list(p.co) for p in f.keyframe_points])
                for f in action.layers[0].strips[0].channelbags[0].fcurves]

    idle_curves = curves(actions["idle"])
    if edited:
        before = json.loads((folder / "inspection.json").read_text())
        assert json.loads(json.dumps(idle_curves)) == before["idle_curves"], "Existing idle clip changed"

    def samples(target: Any, action: Any, mesh_name: str, end: int) -> list[list[float]]:
        target.animation_data.action = action
        target.animation_data.action_slot = action.slots[0]
        for track in target.animation_data.nla_tracks:
            track.mute = True
        obj = bpy.data.objects[mesh_name]
        result = []
        for frame in (0, end//2, end):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
                # Bounding-box center is independent of glTF vertex splitting.
                result.append([(min(v[i] for v in vertices)+max(v[i] for v in vertices))/2 for i in range(3)])
            finally:
                evaluated.to_mesh_clear()
        assert max(abs(a-b) for a,b in zip(result[0],result[-1])) < 1e-5, "Loop endpoints differ"
        assert sum((a-b)**2 for a,b in zip(result[0],result[1]))**0.5 > 0.005, "Clip has no actual movement"
        return result

    expected = {}
    for name in names:
        expected[name] = samples(rig, actions[name], "Head" if name == "idle" else "Forearm", 48 if name == "idle" else 24)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 24
    bpy.ops.import_scene.gltf(filepath=str(glb))
    imported = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    imported_actions = {name: next(a for a in bpy.data.actions if a.name.startswith("mf."+name+".")) for name in names}
    actual = {}
    for name in names:
        action = imported_actions[name]
        end = 48 if name == "idle" else 24
        assert abs(action.frame_range[0]) < 1e-4 and abs(action.frame_range[1]-end) < 1e-4, (name, list(action.frame_range))
        actual[name] = samples(imported, action, "Head" if name == "idle" else "Forearm", end)
        assert max(abs(a-b) for u,v in zip(expected[name],actual[name]) for a,b in zip(u,v)) < 1e-4, name
    report = {"blender": bpy.app.version_string, "clips": list(names), "idle_curves": idle_curves,
              "source_samples": expected, "glb_samples": actual, "durations_sec": {n: 2 if n == "idle" else 1 for n in names},
              "existing_clip_unchanged": edited, "loop_endpoints_equal": True, "glb_motion_preserved": True,
              "duplicate_clip_and_changed_fps_rejected": True,
              "not_tested": ["walking/root motion", "IK/FK", "engine playback", "installed MCP", "artistic quality"]}
    (folder / ("posed-inspection.json" if edited else "inspection.json")).write_text(json.dumps(report,indent=2)+"\n")


def render_clip(source: Path, folder: Path) -> None:
    """CPU diagnostic video with explicit source lineage, no input blend writes."""
    import hashlib
    import bpy
    from mathutils import Vector

    folder.mkdir(exist_ok=False, mode=0o700)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    rig = next(o for o in bpy.data.objects if o.get("media_forge_id") == "rig")
    action = next(a for a in bpy.data.actions if a.get("media_forge_clip_id") == "arm_swing")
    rig.animation_data.action, rig.animation_data.action_slot = action, action.slots[0]
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    scene = bpy.context.scene
    scene.render.engine, scene.cycles.device = "CYCLES", "CPU"
    scene.cycles.samples = 16
    scene.render.resolution_x, scene.render.resolution_y = 480, 540
    scene.render.resolution_percentage = 100
    scene.world.color = (0.18,0.18,0.18)
    for name, position, power in (("key", (3,-4,5), 650), ("fill", (-3,-2,3), 350), ("rim", (1,3,4), 700)):
        light = bpy.data.lights.new(name, "AREA")
        light.energy, light.size = power, 3
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector((0,0,1))-obj.location).to_track_quat("-Z","Y").to_euler()
    camera = bpy.data.objects.new("Motion camera", bpy.data.cameras.new("Motion camera"))
    scene.collection.objects.link(camera)
    camera.location = (3,-5,2.8)
    camera.rotation_euler = (Vector((0,0,1))-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 2.4
    scene.camera = camera
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format, scene.render.ffmpeg.codec = "MPEG4", "H264"
    scene.render.filepath = str(folder / "arm-swing.mp4")
    scene.frame_start, scene.frame_end = 0, 23
    scene.render.fps, scene.render.fps_base = 24, 1
    bpy.ops.render.render(animation=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    video = folder / "arm-swing.mp4"
    (folder / "provenance.json").write_text(json.dumps({"source_blend_sha256": before,
        "output_sha256": hashlib.sha256(video.read_bytes()).hexdigest(), "size_bytes": video.stat().st_size,
        "blender": bpy.app.version_string, "renderer": "Cycles CPU", "samples": 16,
        "frames": [0,23], "fps": 24, "clip_id": "arm_swing", "diagnostic_only": True}, indent=2)+"\n")


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--render-dir", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    render_clip(args.source, args.render_dir)
