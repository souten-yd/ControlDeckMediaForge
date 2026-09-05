# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the fixed Media Forge scene-recipe vocabulary inside Blender."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy


FIXED = {"recipe.json", "source.blend", "scene.blend", "result.json"}
MAX_OPERATIONS = 64


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("create", "edit"), required=True)
    parser.add_argument("--recipe", choices=("recipe.json",), required=True)
    parser.add_argument("--source", choices=("source.blend",))
    parser.add_argument("--output", choices=("scene.blend",), required=True)
    parser.add_argument("--result", choices=("result.json",), required=True)
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args(values)


def vector(value: object, *, positive: bool = False) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise RuntimeError("recipe vector differs")
    parsed = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in parsed):
        raise RuntimeError("recipe vector is non-finite")
    if positive and not all(0 < item <= 1_000 for item in parsed):
        raise RuntimeError("recipe dimensions differ")
    if not positive and not all(-10_000 <= item <= 10_000 for item in parsed):
        raise RuntimeError("recipe vector exceeds bounds")
    return parsed  # type: ignore[return-value]


def stable_objects() -> dict[str, bpy.types.Object]:
    result: dict[str, bpy.types.Object] = {}
    for obj in bpy.data.objects:
        value = obj.get("media_forge_id")
        if isinstance(value, str):
            if value in result:
                raise RuntimeError("scene contains duplicate stable object IDs")
            result[value] = obj
    return result


def transform(obj: bpy.types.Object, operation: dict[str, object]) -> None:
    if operation.get("dimensions") is not None:
        obj.dimensions = vector(operation["dimensions"], positive=True)
    if operation.get("location") is not None:
        obj.location = vector(operation["location"])
    if operation.get("rotation_degrees") is not None:
        obj.rotation_euler = tuple(
            math.radians(item) for item in vector(operation["rotation_degrees"])
        )
    bpy.context.view_layer.update()


def primitive(operation: dict[str, object]) -> bpy.types.Object:
    kind = operation["primitive"]
    vertices = int(operation.get("vertices", 32))
    if kind == "cube":
        bpy.ops.mesh.primitive_cube_add()
    elif kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=vertices)
    elif kind == "uv_sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=vertices, ring_count=max(3, vertices // 2))
    else:
        raise RuntimeError("unsupported primitive")
    obj = bpy.context.object
    if obj is None:
        raise RuntimeError("primitive was not created")
    obj.name = str(operation["name"])
    obj["media_forge_id"] = str(operation["object_id"])
    transform(obj, operation)
    return obj


def apply_operation(operation: dict[str, object], objects: dict[str, bpy.types.Object]) -> None:
    kind = operation.get("type")
    object_id = operation.get("object_id")
    if not isinstance(object_id, str):
        raise RuntimeError("recipe object ID differs")
    if kind in {"primitive.add", "light.add", "camera.add"} and object_id in objects:
        raise RuntimeError("recipe object ID already exists")
    if kind == "primitive.add":
        objects[object_id] = primitive(operation)
        return
    if kind == "light.add":
        light = bpy.data.lights.new(str(operation["name"]), type=str(operation["light"]).upper())
        light.energy = float(operation["energy"])
        obj = bpy.data.objects.new(str(operation["name"]), light)
        bpy.context.collection.objects.link(obj)
        obj["media_forge_id"] = object_id
        transform(obj, operation)
        objects[object_id] = obj
        return
    if kind == "camera.add":
        camera = bpy.data.cameras.new(str(operation["name"]))
        camera.lens = float(operation["focal_length_mm"])
        obj = bpy.data.objects.new(str(operation["name"]), camera)
        bpy.context.collection.objects.link(obj)
        obj["media_forge_id"] = object_id
        transform(obj, operation)
        bpy.context.scene.camera = obj
        objects[object_id] = obj
        return
    obj = objects.get(object_id)
    if obj is None:
        raise RuntimeError(f"unknown stable object ID: {object_id}")
    if kind == "transform.set":
        transform(obj, operation)
    elif kind == "modifier.bevel":
        if obj.type != "MESH":
            raise RuntimeError("bevel target is not a mesh")
        modifier = obj.modifiers.new(name="Media Forge Bevel", type="BEVEL")
        modifier.width = float(operation["width"])
        modifier.segments = int(operation["segments"])
    elif kind == "material.set":
        if obj.type != "MESH":
            raise RuntimeError("material target is not a mesh")
        material = bpy.data.materials.new(str(operation["name"]))
        material.use_nodes = True
        node = material.node_tree.nodes.get("Principled BSDF") if material.node_tree else None
        if node is None:
            raise RuntimeError("principled material node is unavailable")
        node.inputs["Base Color"].default_value = tuple(float(v) for v in operation["base_color"])
        node.inputs["Metallic"].default_value = float(operation["metallic"])
        node.inputs["Roughness"].default_value = float(operation["roughness"])
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    elif kind == "uv.smart_project":
        if obj.type != "MESH":
            raise RuntimeError("UV target is not a mesh")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=float(operation["island_margin"]))
        bpy.ops.object.mode_set(mode="OBJECT")
    else:
        raise RuntimeError("unsupported recipe operation")


def main() -> None:
    args = arguments()
    if tuple(bpy.app.version[:3]) != tuple(int(part) for part in args.expected_version.split(".")):
        raise RuntimeError("Blender runtime identity differs")
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    if args.mode == "edit":
        if args.source != "source.blend":
            raise RuntimeError("edit source differs")
        bpy.ops.wm.open_mainfile(filepath=str(Path.cwd() / args.source), load_ui=False, use_scripts=False)
    else:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
    recipe = json.loads((Path.cwd() / args.recipe).read_text(encoding="utf-8"))
    operations = recipe.get("operations") if isinstance(recipe, dict) else None
    if not isinstance(operations, list) or not 1 <= len(operations) <= MAX_OPERATIONS:
        raise RuntimeError("recipe operation count differs")
    objects = stable_objects()
    for operation in operations:
        if not isinstance(operation, dict):
            raise RuntimeError("recipe operation differs")
        apply_operation(operation, objects)
    if not objects:
        raise RuntimeError("recipe produced no stable objects")
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.wm.save_as_mainfile(filepath=str(Path.cwd() / args.output), check_existing=False)
    result = {
        "schema_version": "media-forge.scene-recipe-result@1",
        "blender_version": args.expected_version,
        "autoexec_disabled": not bpy.context.preferences.filepaths.use_scripts_auto_execute,
        "operation_count": len(operations),
        "stable_object_ids": sorted(objects),
    }
    (Path.cwd() / args.result).write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
