"""Typed distributed-skin/clip acceptance, not a completed character or engine test."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auto_weight_probe import points, point_error, weight_stats


def binding() -> dict[str, Any]:
    return {"type": "skin.bind_auto", "object_id": "rig", "mesh_object_ids": ["body"]}


def clip(name: str) -> dict[str, Any]:
    angle = 5 if name == "idle" else 60
    return {"type": "animation.clip", "object_id": "rig", "clip_id": name, "name": name,
            "fps": 24, "frame_count": 48, "loop": True, "tracks": [{"bone_id": "upper", "keys": [
                {"frame": 0, "rotation_degrees": [0, 0, 0]},
                {"frame": 24, "rotation_degrees": [angle, 0, 0]},
                {"frame": 48, "rotation_degrees": [0, 0, 0]}]}]}


def recipe() -> list[dict[str, Any]]:
    return [
        {"type": "primitive.add", "object_id": "body", "primitive": "uv_sphere", "name": "Body",
         "dimensions": [.3, .3, 1.3], "location": [0, 0, .5], "vertices": 16},
        {"type": "armature.create", "object_id": "rig", "name": "Rig", "bones": [
            {"bone_id": "lower", "head": [0, 0, 0], "tail": [0, 0, .5]},
            {"bone_id": "upper", "head": [0, 0, .5], "tail": [0, 0, 1], "parent_bone_id": "lower"}]},
        binding(), clip("idle"),
    ]


def inspect_blend(source: Path, glb: Path, folder: Path, *, edited: bool) -> None:
    import importlib.util
    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    rig = next(o for o in bpy.data.objects if o.get("media_forge_id") == "rig")
    mesh = next(o for o in bpy.data.objects if o.get("media_forge_id") == "body")
    assert len(rig.data.bones) == 2 and mesh.parent == rig
    assert len(mesh.modifiers) == 1 and mesh.modifiers[0].object == rig
    stats = weight_stats(mesh)
    bpy.context.scene.frame_set(0)
    rest = points(mesh)
    mesh.modifiers[0].show_viewport = False
    bpy.context.view_layer.update()
    rest_error = point_error(rest, points(mesh))
    assert rest_error < 1e-5
    mesh.modifiers[0].show_viewport = True
    bpy.context.view_layer.update()
    actions = {a["media_forge_clip_id"]: a for a in bpy.data.actions}
    assert set(actions) == ({"idle", "bend"} if edited else {"idle"})
    expected: dict[str, list] = {}
    for name, action in actions.items():
        rig.animation_data.action = action
        rig.animation_data.action_slot = action.slots[0]
        for track in rig.animation_data.nla_tracks:
            track.mute = True
        samples = []
        for frame in (0, 12, 24, 36, 48):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            samples.append(points(mesh))
        assert point_error(samples[0], samples[-1]) < 1e-5
        assert point_error(samples[0], samples[2]) > (.1 if name == "bend" else .01)
        expected[action.name] = samples
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 24
    bpy.ops.import_scene.gltf(filepath=str(glb))
    rig, = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    helpers = {b.custom_shape for b in rig.pose.bones if b.custom_shape is not None}
    mesh, = [o for o in bpy.context.scene.objects if o.type == "MESH" and o not in helpers]
    imported_stats = weight_stats(mesh)
    errors = {}
    assert len(bpy.data.actions) == len(expected)
    for name, samples in expected.items():
        action = bpy.data.actions[name]
        assert abs(action.frame_range[1] - 48) < 1e-4
        rig.animation_data.action = action
        rig.animation_data.action_slot = action.slots[0]
        for track in rig.animation_data.nla_tracks:
            track.mute = True
        values = []
        for frame, sample in zip((0, 12, 24, 36, 48), samples, strict=True):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            values.append(point_error(points(mesh), sample))
        assert max(values) < 1e-5, (name, values)
        errors[name] = values
    # Real collapsed-surface rejection. Heat can produce weights even for this
    # invalid surface, so it must be caught by preflight. This is an in-memory
    # negative, not a claim that the public primitive API accepts zero dimensions.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    spec = importlib.util.spec_from_file_location("auto_skin_worker", Path(__file__).parents[1] / "worker_packs/blender/scene_recipe.py")
    assert spec and spec.loader
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    objects: dict[str, Any] = {}
    for op in recipe()[:2]:
        worker.apply_operation(op, objects)
    for vertex in objects["body"].data.vertices:
        vertex.co = (0, 0, 0)
    objects["body"].data.update()
    bpy.context.view_layer.update()
    try:
        worker.bind_skin_auto(objects["rig"], binding(), objects)
    except RuntimeError as exc:
        assert str(exc) == "automatic bind requires nondegenerate faces", str(exc)
    else:
        raise AssertionError("Collapsed heat fixture incorrectly accepted")
    report = {"passed": True, "blender": bpy.app.version_string, "source_weights": stats,
              "imported_weights": imported_stats, "rest_error_m": rest_error,
              "clip_world_errors_m": errors, "clip_duration_sec": 2,
              "real_collapsed_surface_rejected_before_heat": True,
              "not_tested": ["complex character", "artistic quality", "engine import", "installed MCP/OpenCode"]}
    (folder / ("posed-inspection.json" if edited else "inspection.json")).write_text(json.dumps(report, indent=2)+"\n")
