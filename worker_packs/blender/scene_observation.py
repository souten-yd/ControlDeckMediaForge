"""Trusted CPU observation worker. Fixed private filenames; never user scripts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import sys
from typing import Any

import bpy
from mathutils import Vector

VIEWS = {"front": (0, -1, 0), "side": (1, 0, 0), "back": (0, 1, 0),
         "three-quarter": (1, -1, .65)}


def validate_spec(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "center", "span_m", "views", "mode", "resolution"}:
        raise RuntimeError("invalid observation fields")
    if value["schema_version"] != "media-forge.scene-observation@1":
        raise RuntimeError("invalid observation version")
    center = value["center"]
    if not isinstance(center, list) or len(center) != 3:
        raise RuntimeError("invalid observation center")
    for item in [*center, value["span_m"]]:
        if type(item) not in (int, float) or not math.isfinite(item) or abs(item) > 10_000:
            raise RuntimeError("invalid observation coordinate")
    if value["span_m"] <= .001:
        raise RuntimeError("invalid observation span")
    views = value["views"]
    if not isinstance(views, list) or not 1 <= len(views) <= 4 or any(type(v) is not str or v not in VIEWS for v in views) or len(set(views)) != len(views):
        raise RuntimeError("invalid observation views")
    if value["mode"] not in ("material", "clay", "silhouette", "object_id") or type(value["mode"]) is not str:
        raise RuntimeError("invalid observation mode")
    if type(value["resolution"]) is not int or value["resolution"] not in (256, 512):
        raise RuntimeError("invalid observation resolution")
    return value


def material(color: tuple[float, float, float, float], *, emission: bool) -> Any:
    result = bpy.data.materials.new("Observation")
    result.use_nodes = True
    nodes = result.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeEmission" if emission else "ShaderNodeBsdfDiffuse")
    shader.inputs["Color"].default_value = color
    result.node_tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return result


def validate_scene_objects(objects: list[Any]) -> list[Any]:
    """Do not silently render geometry outside the diagnostic mesh vocabulary."""
    if len(objects) > 1024 or any(obj.type not in {"MESH", "ARMATURE", "EMPTY", "LIGHT", "CAMERA"}
                                 or obj.instance_type != "NONE" for obj in objects):
        raise RuntimeError("unsupported observation scene objects")
    meshes = sorted((obj for obj in objects if obj.type == "MESH"), key=lambda obj: obj.name)
    if not 1 <= len(meshes) <= 256:
        raise RuntimeError("observation mesh count exceeds bound")
    total = 0
    for obj in meshes:
        if obj.particle_systems:
            raise RuntimeError("particles are not diagnostic mesh geometry")
        cost = max(len(obj.data.vertices), sum(max(0, p.loop_total - 2) for p in obj.data.polygons))
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE":
                continue
            if modifier.type == "MIRROR":
                cost *= 2 ** sum(modifier.use_axis)
            elif modifier.type == "BEVEL":
                cost *= 24 * int(modifier.segments) + 48
            elif modifier.type == "ARRAY" and modifier.fit_type == "FIXED_COUNT" and 1 <= modifier.count <= 64 and modifier.start_cap is None and modifier.end_cap is None:
                cost *= modifier.count
            else:
                raise RuntimeError("unsupported observation modifier")
            if cost > 1_000_000:
                raise RuntimeError("observation geometry exceeds bound")
        total += cost
        if total > 1_000_000:
            raise RuntimeError("observation geometry exceeds bound")
    return meshes


def render(spec: dict[str, Any]) -> dict[str, Any]:
    scene = bpy.context.scene
    meshes = validate_scene_objects(list(scene.objects))
    scene.frame_set(0)
    for obj in list(bpy.data.objects):
        if obj.type in {"LIGHT", "CAMERA"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    # Never use the imported world's nodes, compositor, sequencer or render settings.
    scene.use_nodes = False
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    if hasattr(scene.cycles, "shading_system"):
        scene.cycles.shading_system = False
    scene.cycles.samples = 16
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.seed = 0
    scene.cycles.max_bounces = 4
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    for layer in scene.view_layers:
        layer.material_override = None
        layer.use = layer == bpy.context.view_layer
    scene.render.use_freestyle = False
    if hasattr(scene.render, "use_motion_blur"):
        scene.render.use_motion_blur = False
    scene.render.use_multiview = False
    scene.render.use_border = False
    scene.render.film_transparent = False
    scene.render.resolution_x = scene.render.resolution_y = spec["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.use_stamp = False
    scene.render.dither_intensity = 0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Raw" if spec["mode"] in {"silhouette", "object_id"} else "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.world = bpy.data.worlds.new("ObservationWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1 if spec["mode"] in {"silhouette", "object_id"} else .35
    object_colors = []
    ids: set[str] = set()
    colors: set[int] = set()
    for obj in meshes:
        object_id = obj.get("media_forge_id")
        if object_id is not None and (not isinstance(object_id, str) or len(object_id) > 64 or object_id in ids):
            raise RuntimeError("invalid stable object identity")
        if object_id is not None:
            ids.add(object_id)
        if spec["mode"] != "material":
            value = int.from_bytes(hashlib.sha256((object_id or obj.name).encode()).digest()[:3], "big")
            if value in colors or value in {0, 0xFFFFFF}:
                raise RuntimeError("object color collision")
            colors.add(value)
            color = tuple(((value >> shift) & 255) / 255 for shift in (16, 8, 0)) + (1.0,)
            if spec["mode"] == "clay":
                color = (.55, .55, .55, 1)
            elif spec["mode"] == "silhouette":
                color = (0, 0, 0, 1)
            obj.data = obj.data.copy()
            obj.data.materials.clear()
            obj.data.materials.append(material(color, emission=spec["mode"] != "clay"))
            for polygon in obj.data.polygons:
                polygon.material_index = 0
            if spec["mode"] == "object_id":
                object_colors.append({"object_id": object_id, "object_name": obj.name, "color_rgb": list(color[:3])})
    center = Vector(spec["center"])
    span = spec["span_m"]
    for offset, energy in [((1, -2, 3), 50), ((-2, -1, 1), 25), ((0, 2, 3), 40)]:
        light = bpy.data.objects.new("ObservationLight", bpy.data.lights.new("ObservationLight", type="AREA"))
        scene.collection.objects.link(light)
        light.location = center + Vector(offset) * span
        light.data.energy = energy * span * span
        light.data.size = span * 2
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    camera = bpy.data.objects.new("ObservationCamera", bpy.data.cameras.new("ObservationCamera"))
    scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = span
    camera.data.clip_start = span * .001
    camera.data.clip_end = span * 10
    scene.camera = camera
    images = []
    for view in spec["views"]:
        camera.location = center + Vector(VIEWS[view]).normalized() * span * 4
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        filename = f"{view}.png"
        scene.render.filepath = str(Path.cwd() / filename)
        bpy.ops.render.render(write_still=True)
        images.append({"view": view, "filename": filename})
    return {"schema_version": "media-forge.scene-observation-result@1", "observation": spec,
            "blender_version": bpy.app.version_string.split()[0], "device": "CPU", "frame": 0,
            "samples": 16, "images": images, "object_colors": object_colors,
            "object_ids": sorted(key for key in ids if re.fullmatch(r"[a-z][a-z0-9._-]{0,63}", key)),
            "autoexec_disabled": not bpy.context.preferences.filepaths.use_scripts_auto_execute}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if bpy.app.version_string.split()[0] != args.expected_version:
        raise RuntimeError("runtime identity differs")
    path = Path.cwd() / "observation.json"
    if path.is_symlink() or path.stat().st_size > 8192:
        raise RuntimeError("observation input exceeds bound")
    spec = validate_spec(json.loads(path.read_text()))
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.ops.wm.open_mainfile(filepath=str(Path.cwd() / "source.blend"), load_ui=False, use_scripts=False)
    result = render(spec)
    (Path.cwd() / "result.json").write_text(json.dumps(result, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
