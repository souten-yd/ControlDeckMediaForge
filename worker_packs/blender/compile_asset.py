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
import bmesh
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
        "schema_version", "expected_blender_version", "source", "output", "preview", "source_sha256", "options"
    }:
        raise RuntimeError("compiler request fields differ")
    if value["schema_version"] != 1 or value["expected_blender_version"] != ".".join(map(str, bpy.app.version[:3])):
        raise RuntimeError("compiler request version differs")
    if any(value[name] != expected for name, expected in FIXED_NAMES.items()):
        raise RuntimeError("compiler request file names differ")
    if not isinstance(value["source_sha256"], str) or len(value["source_sha256"]) != 64:
        raise RuntimeError("compiler request source hash is invalid")
    value["options"] = validate_options(value["options"])
    return value


def validate_options(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version", "apply_transforms", "repair_normals", "remove_degenerate",
        "merge_by_distance_m", "triangle_budget", "lod_ratios", "collision", "materials", "preview",
    }:
        raise RuntimeError("compiler option fields differ")
    if raw["schema_version"] != "3d.compile-options@1" or raw["apply_transforms"] is not True:
        raise RuntimeError("compiler option version or fixed transform differs")
    for name in ("repair_normals", "remove_degenerate"):
        if not isinstance(raw[name], bool):
            raise RuntimeError(f"compiler option {name} is invalid")
    merge = raw["merge_by_distance_m"]
    if merge is not None and (isinstance(merge, bool) or not isinstance(merge, (int, float)) or not 1e-7 <= merge <= 1.0):
        raise RuntimeError("compiler merge distance is invalid")
    budget = raw["triangle_budget"]
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int) or not 12 <= budget <= 200_000):
        raise RuntimeError("compiler triangle budget is invalid")
    ratios = raw["lod_ratios"]
    if (
        not isinstance(ratios, list)
        or len(ratios) > 3
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not 0.05 <= item <= 0.95 for item in ratios)
        or any(left <= right for left, right in zip(ratios, ratios[1:], strict=False))
    ):
        raise RuntimeError("compiler LOD ratios are invalid")
    if raw["collision"] not in {"none", "box", "convex_hull"}:
        raise RuntimeError("compiler collision mode is invalid")
    if raw["materials"] not in {"preserve", "basic_pbr"} or raw["preview"] != "fixed_workbench":
        raise RuntimeError("compiler material or preview mode is invalid")
    return raw


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


def triangle_count(objects: list[Any]) -> int:
    total = 0
    for value in objects:
        if value.type == "MESH":
            value.data.calc_loop_triangles()
            total += len(value.data.loop_triangles)
    return total


def mesh_edits(objects: list[Any], options: dict[str, Any]) -> dict[str, int]:
    before_vertices = sum(len(value.data.vertices) for value in objects if value.type == "MESH")
    before_triangles = triangle_count(objects)
    for value in objects:
        if value.type != "MESH":
            continue
        mesh = value.data
        editable = bmesh.new()
        editable.from_mesh(mesh)
        try:
            if options["repair_normals"] and editable.faces:
                bmesh.ops.recalc_face_normals(editable, faces=list(editable.faces))
            if options["remove_degenerate"] and editable.edges:
                bmesh.ops.dissolve_degenerate(editable, dist=1e-12, edges=list(editable.edges))
            if options["merge_by_distance_m"] is not None and editable.verts:
                bmesh.ops.remove_doubles(
                    editable,
                    verts=list(editable.verts),
                    dist=float(options["merge_by_distance_m"]),
                )
            editable.to_mesh(mesh)
            mesh.update()
        finally:
            editable.free()
    return {
        "vertices_before": before_vertices,
        "vertices_after": sum(len(value.data.vertices) for value in objects if value.type == "MESH"),
        "triangles_before": before_triangles,
        "triangles_after": triangle_count(objects),
    }


def apply_triangle_budget(objects: list[Any], budget: int | None) -> dict[str, Any]:
    before = triangle_count(objects)
    if budget is None or before <= budget:
        return {"requested": budget, "triangles_before": before, "triangles_after": before, "applied": False}
    ratio = budget / before
    for value in objects:
        if value.type != "MESH":
            continue
        bpy.context.view_layer.objects.active = value
        value.select_set(True)
        modifier = value.modifiers.new(name="MediaForgeTriangleBudget", type="DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        value.select_set(False)
    after = triangle_count(objects)
    if after > budget:
        raise RuntimeError(f"triangle budget was not met: {after} > {budget}")
    return {"requested": budget, "triangles_before": before, "triangles_after": after, "applied": True}


def create_lods(objects: list[Any], ratios: list[float]) -> dict[str, Any]:
    source_objects = [value for value in objects if value.type == "MESH"]
    created: list[dict[str, Any]] = []
    for level, ratio in enumerate(ratios, start=1):
        for source in source_objects:
            duplicate = source.copy()
            duplicate.data = source.data.copy()
            duplicate.name = f"{source.name}_LOD{level}"
            bpy.context.scene.collection.objects.link(duplicate)
            bpy.context.view_layer.objects.active = duplicate
            duplicate.select_set(True)
            modifier = duplicate.modifiers.new(name=f"MediaForgeLOD{level}", type="DECIMATE")
            modifier.decimate_type = "COLLAPSE"
            modifier.ratio = float(ratio)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            duplicate.select_set(False)
            created.append({"name": duplicate.name, "level": level, "ratio": ratio, "triangles": triangle_count([duplicate])})
    return {"requested_ratios": ratios, "created": created}


def create_collision(objects: list[Any], mode: str) -> dict[str, Any]:
    if mode == "none":
        return {"mode": mode, "created": False}
    points = [value.matrix_world @ vertex.co for value in objects if value.type == "MESH" for vertex in value.data.vertices]
    if not points:
        raise RuntimeError("collision generation has no vertices")
    mesh = bpy.data.meshes.new("UCX_MediaForge")
    collision = bpy.data.objects.new("UCX_MediaForge", mesh)
    bpy.context.scene.collection.objects.link(collision)
    if mode == "box":
        minimum = [min(point[axis] for point in points) for axis in range(3)]
        maximum = [max(point[axis] for point in points) for axis in range(3)]
        vertices = [(x, y, z) for x in (minimum[0], maximum[0]) for y in (minimum[1], maximum[1]) for z in (minimum[2], maximum[2])]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        mesh.from_pydata(vertices, [], faces)
    else:
        editable = bmesh.new()
        try:
            vertices = [editable.verts.new(point) for point in points]
            editable.verts.ensure_lookup_table()
            bmesh.ops.convex_hull(editable, input=vertices, use_existing_faces=False)
            editable.to_mesh(mesh)
        finally:
            editable.free()
    mesh.update()
    return {"mode": mode, "created": True, "vertices": len(mesh.vertices), "triangles": triangle_count([collision])}


def simplify_materials(mode: str) -> dict[str, Any]:
    if mode == "preserve":
        return {"mode": mode, "materials": len(bpy.data.materials), "changed": 0}
    changed = 0
    for material in bpy.data.materials:
        color = tuple(material.diffuse_color)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        shader = nodes.new("ShaderNodeBsdfPrincipled")
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = 0.5
        material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
        changed += 1
    return {"mode": mode, "materials": len(bpy.data.materials), "changed": changed}


def normalize_scene(options: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int], list[str], list[dict[str, Any]]]:
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
    has_rig_or_animation = (
        any(value.type == "ARMATURE" for value in objects)
        or bool(bpy.data.actions)
        or any(getattr(value, "animation_data", None) is not None for value in objects)
    )
    destructive_options = (
        options["repair_normals"]
        or options["remove_degenerate"]
        or options["merge_by_distance_m"] is not None
        or options["triangle_budget"] is not None
        or bool(options["lod_ratios"])
        or options["materials"] != "preserve"
    )
    if has_rig_or_animation and destructive_options:
        raise RuntimeError("geometry or material options are not accepted for rigged or animated input")
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
    operations: list[dict[str, Any]] = [
        {"id": "sanitize.scene", "parameters": {}, "results": removed, "warnings": []},
        {"id": "normalize.unit-meters", "parameters": {"apply_transforms": True}, "results": {"objects": len(objects)}, "warnings": []},
    ]
    edit_results = mesh_edits(objects, options)
    operations.append({
        "id": "edit.mesh",
        "parameters": {
            "repair_normals": options["repair_normals"],
            "remove_degenerate": options["remove_degenerate"],
            "merge_by_distance_m": options["merge_by_distance_m"],
        },
        "results": edit_results,
        "warnings": [],
    })
    budget_results = apply_triangle_budget(objects, options["triangle_budget"])
    operations.append({"id": "budget.triangles", "parameters": {"triangle_budget": options["triangle_budget"]}, "results": budget_results, "warnings": []})
    material_results = simplify_materials(options["materials"])
    operations.append({"id": "materials.normalize", "parameters": {"mode": options["materials"]}, "results": material_results, "warnings": []})
    lod_results = create_lods(objects, options["lod_ratios"])
    operations.append({"id": "lod.generate", "parameters": {"ratios": options["lod_ratios"]}, "results": lod_results, "warnings": []})
    collision_results = create_collision(objects, options["collision"])
    operations.append({"id": "collision.generate", "parameters": {"mode": options["collision"]}, "results": collision_results, "warnings": []})
    warnings: list[str] = []
    for mesh in bpy.data.meshes:
        mesh.calc_loop_triangles()
        if any(triangle.area <= 1e-12 or not math.isfinite(triangle.area) for triangle in mesh.loop_triangles):
            warnings.append("mesh contains a degenerate or non-finite triangle")
        if any(not all(math.isfinite(component) for component in polygon.normal) for polygon in mesh.polygons):
            raise RuntimeError("mesh contains a non-finite normal")
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    operations.append({"id": "validate.normals", "parameters": {"repair": options["repair_normals"]}, "results": {"warnings": len(warnings)}, "warnings": list(warnings)})
    return statistics(list(bpy.context.scene.objects)), removed, warnings, operations


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
    stats, removed, warnings, operations = normalize_scene(request["options"])
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
    operations.extend([
        {"id": "export.glb-embedded-y-up", "parameters": {}, "results": {"sha256": sha256(output)}, "warnings": []},
        {"id": "preview.fixed-workbench", "parameters": {}, "results": {"sha256": sha256(preview)}, "warnings": []},
    ])
    result = {
        "schema_version": 1,
        "blender_version": ".".join(map(str, bpy.app.version[:3])),
        "input_sha256": request["source_sha256"],
        "output_sha256": sha256(output),
        "preview_sha256": sha256(preview),
        "statistics": stats,
        "removed": removed,
        "warnings": warnings,
        "operations": operations,
    }
    Path(args.result).write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
