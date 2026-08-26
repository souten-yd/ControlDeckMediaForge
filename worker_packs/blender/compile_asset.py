# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted fixed G8 compiler executed only by the Media Forge core."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any

import bpy
from mathutils import Vector


FIXED_NAMES = {"source": "source.glb", "output": "asset.glb", "preview": "preview.png"}


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", choices=("request.json",), required=True)
    parser.add_argument("--result", choices=("result.json",), required=True)
    return parser.parse_args(values)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_render_png(path: Path) -> None:
    """Keep deterministic critical PNG chunks and drop Blender timing metadata."""
    content = path.read_bytes()
    if len(content) > 16 * 1024 * 1024 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("preview PNG is invalid or exceeds its bound")
    output = bytearray(content[:8])
    offset = 8
    seen: list[bytes] = []
    while offset < len(content):
        if offset + 12 > len(content):
            raise RuntimeError("preview PNG chunk is truncated")
        length = struct.unpack_from(">I", content, offset)[0]
        end = offset + 12 + length
        if end > len(content):
            raise RuntimeError("preview PNG chunk escapes")
        chunk_type = content[offset + 4 : offset + 8]
        if chunk_type in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            output.extend(content[offset:end])
            seen.append(chunk_type)
        offset = end
    if offset != len(content) or not seen or seen[0] != b"IHDR" or seen[-1] != b"IEND" or b"IDAT" not in seen:
        raise RuntimeError("preview PNG critical chunks differ")
    path.write_bytes(output)


def load_request(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "expected_blender_version", "source", "output", "preview", "source_sha256"
    }:
        raise RuntimeError("compiler request fields differ")
    if value["schema_version"] != 1 or value["expected_blender_version"] != ".".join(map(str, bpy.app.version[:3])):
        raise RuntimeError("compiler request version differs")
    if any(value[name] != expected for name, expected in FIXED_NAMES.items()):
        raise RuntimeError("compiler request file names differ")
    if not isinstance(value["source_sha256"], str) or len(value["source_sha256"]) != 64:
        raise RuntimeError("compiler request source hash is invalid")
    return value


def remove_custom_properties(value: Any) -> int:
    removed = 0
    for key in list(value.keys()) if hasattr(value, "keys") else []:
        del value[key]
        removed += 1
    return removed


def clear_drivers(value: Any) -> int:
    animation = getattr(value, "animation_data", None)
    drivers = list(animation.drivers) if animation is not None and animation.drivers is not None else []
    for driver in drivers:
        animation.drivers.remove(driver)
    return len(drivers)


def scene_bounds(objects: list[Any]) -> tuple[list[float], list[float]]:
    points: list[Vector] = []
    for value in objects:
        if value.type == "MESH":
            points.extend(value.matrix_world @ Vector(corner) for corner in value.bound_box)
    if not points:
        raise RuntimeError("scene has no mesh bounds")
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    if any(not math.isfinite(item) for item in [*minimum, *maximum]):
        raise RuntimeError("scene bounds are non-finite")
    return minimum, maximum


def statistics(objects: list[Any]) -> dict[str, Any]:
    meshes = [value.data for value in objects if value.type == "MESH"]
    for mesh in meshes:
        mesh.calc_loop_triangles()
    minimum, maximum = scene_bounds(objects)
    return {
        "objects": len(objects),
        "meshes": len(meshes),
        "vertices": sum(len(mesh.vertices) for mesh in meshes),
        "edges": sum(len(mesh.edges) for mesh in meshes),
        "triangles": sum(len(mesh.loop_triangles) for mesh in meshes),
        "materials": len(bpy.data.materials),
        "textures": len([image for image in bpy.data.images if image.type == "IMAGE"]),
        "bounds_min": minimum,
        "bounds_max": maximum,
    }


def normalize_scene() -> tuple[dict[str, Any], dict[str, int], list[str]]:
    removed = {"camera_light_objects": 0, "text_blocks": 0, "drivers": 0, "custom_properties": 0}
    for value in list(bpy.data.objects):
        if value.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(value, do_unlink=True)
            removed["camera_light_objects"] += 1
    objects = list(bpy.context.scene.objects)
    unsupported = sorted({value.type for value in objects} - {"MESH", "EMPTY", "ARMATURE"})
    if unsupported:
        raise RuntimeError(f"unsupported object type: {unsupported[0]}")
    if not any(value.type == "MESH" for value in objects):
        raise RuntimeError("scene contains no mesh")
    for text in list(bpy.data.texts):
        bpy.data.texts.remove(text)
        removed["text_blocks"] += 1
    data_blocks = [
        *objects,
        *bpy.data.meshes,
        *bpy.data.armatures,
        *bpy.data.materials,
        *bpy.data.images,
        bpy.context.scene,
    ]
    for value in data_blocks:
        removed["drivers"] += clear_drivers(value)
        removed["custom_properties"] += remove_custom_properties(value)
    for value in objects:
        if any(not math.isfinite(component) for row in value.matrix_world for component in row):
            raise RuntimeError("object transform is non-finite")
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.object.select_all(action="DESELECT")
    for value in objects:
        value.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    warnings: list[str] = []
    for mesh in bpy.data.meshes:
        mesh.calc_loop_triangles()
        if any(triangle.area <= 1e-12 or not math.isfinite(triangle.area) for triangle in mesh.loop_triangles):
            warnings.append("mesh contains a degenerate or non-finite triangle")
        if any(not all(math.isfinite(component) for component in polygon.normal) for polygon in mesh.polygons):
            raise RuntimeError("mesh contains a non-finite normal")
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    return statistics(list(bpy.context.scene.objects)), removed, warnings


def render_preview(path: Path, bounds: tuple[list[float], list[float]]) -> None:
    minimum, maximum = bounds
    center = Vector(tuple((minimum[index] + maximum[index]) / 2 for index in range(3)))
    extent = max(maximum[index] - minimum[index] for index in range(3))
    distance = max(extent, 0.1) * 3.2
    camera_data = bpy.data.cameras.new("MediaForgePreviewCamera")
    camera = bpy.data.objects.new("MediaForgePreviewCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = center + Vector((distance, -distance, distance * 0.75))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 52
    bpy.context.scene.camera = camera
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = False
    scene.display.shading.show_specular_highlight = False
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = str(path)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("MediaForgePreviewWorld")
    scene.world.color = (0.035, 0.035, 0.035)
    bpy.ops.render.render(write_still=True)
    normalize_render_png(path)


def main() -> None:
    args = arguments()
    request = load_request(Path(args.request))
    source = Path(request["source"])
    output = Path(request["output"])
    preview = Path(request["preview"])
    if sha256(source) != request["source_sha256"]:
        raise RuntimeError("compiler source hash differs")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    stats, removed, warnings = normalize_scene()
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_extras=False,
        export_apply=True,
    )
    render_preview(preview, (stats["bounds_min"], stats["bounds_max"]))
    result = {
        "schema_version": 1,
        "blender_version": ".".join(map(str, bpy.app.version[:3])),
        "input_sha256": request["source_sha256"],
        "output_sha256": sha256(output),
        "preview_sha256": sha256(preview),
        "statistics": stats,
        "removed": removed,
        "warnings": warnings,
    }
    Path(args.result).write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
