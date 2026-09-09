# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the fixed Media Forge scene-recipe vocabulary inside Blender."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import sys

import bpy


FIXED = {"recipe.json", "source.blend", "scene.blend", "result.json"}
MAX_OPERATIONS = 64
MAX_GROWTH_GEOMETRY = 1_000_000
MAX_SCENE_BONES = 256


def bone_id(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-z][a-z0-9._-]{0,47}", value) is None:
        raise RuntimeError("bone ID differs")
    return value


def rigid_armature(obj: bpy.types.Object, *, allow_animation: bool = False) -> None:
    if obj.type != "ARMATURE" or obj.get("media_forge_rig_schema") != 1:
        raise RuntimeError("rig must be a typed Media Forge armature")
    if not 1 <= len(obj.data.bones) <= 128 or obj.data.users != 1:
        raise RuntimeError("rig bone count or shared data differs")
    if (obj.animation_data is not None and not allow_animation) or obj.data.animation_data is not None or obj.constraints:
        raise RuntimeError("animated or constrained rig is not supported by pose/bind")
    if any(p.constraints for p in obj.pose.bones):
        raise RuntimeError("constrained pose bones are not supported")


def create_armature(operation: dict[str, object]) -> bpy.types.Object:
    definitions = operation.get("bones")
    if not isinstance(definitions, list) or not 1 <= len(definitions) <= 128:
        raise RuntimeError("bone count differs")
    if sum(len(obj.data.bones) for obj in bpy.data.objects if obj.type == "ARMATURE") + len(definitions) > MAX_SCENE_BONES:
        raise RuntimeError("scene bone budget exceeded")
    known = set()
    for definition in definitions:
        key = bone_id(definition.get("bone_id"))
        parent = definition.get("parent_bone_id")
        if key in known or (parent is not None and parent not in known):
            raise RuntimeError("bone hierarchy differs")
        head, tail = vector(definition.get("head")), vector(definition.get("tail"))
        if sum((a-b)**2 for a,b in zip(head,tail)) < 0.000001:
            raise RuntimeError("bone length is too small")
        known.add(key)
    data = bpy.data.armatures.new(str(operation["name"]))
    obj = bpy.data.objects.new(str(operation["name"]), data)
    bpy.context.collection.objects.link(obj)
    obj["media_forge_id"] = str(operation["object_id"])
    obj["media_forge_rig_schema"] = 1
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        for definition in definitions:
            bone = data.edit_bones.new(definition["bone_id"])
            bone.head, bone.tail = vector(definition["head"]), vector(definition["tail"])
            if bone.length < 0.0009:
                raise RuntimeError("bone endpoints collapse at Blender precision")
            parent = definition.get("parent_bone_id")
            if parent is not None:
                bone.parent = data.edit_bones[parent]
            bone.use_deform = True
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def bind_skin(obj: bpy.types.Object, operation: dict[str, object], objects: dict[str, bpy.types.Object]) -> None:
    rigid_armature(obj)
    for pose in obj.pose.bones:
        if any(abs(pose.matrix_basis[i][j] - (1 if i == j else 0)) > 1e-6 for i in range(4) for j in range(4)):
            raise RuntimeError("bind requires rest pose")
    bindings = operation.get("bindings")
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= 64:
        raise RuntimeError("binding count differs")
    selected, seen, vertices = [], set(), 0
    for binding in bindings:
        mesh_id = binding.get("mesh_object_id")
        mesh = objects.get(mesh_id)
        key = bone_id(binding.get("bone_id"))
        if mesh_id in seen or mesh is None or mesh.type != "MESH" or key not in obj.data.bones:
            raise RuntimeError("binding mesh or bone differs")
        seen.add(mesh_id)
        if mesh.parent is not None or mesh.constraints or mesh.animation_data is not None or mesh.vertex_groups:
            raise RuntimeError("bind requires an unparented unweighted unconstrained static mesh")
        if mesh.data.users != 1 or mesh.data.shape_keys is not None or mesh.data.animation_data is not None:
            raise RuntimeError("bind requires independent static mesh data")
        if any(m.type not in {"BEVEL", "MIRROR"} for m in mesh.modifiers):
            raise RuntimeError("bind modifier stack differs")
        vertices += len(mesh.data.vertices)
        if vertices > MAX_GROWTH_GEOMETRY:
            raise RuntimeError("binding vertex budget exceeded")
        selected.append((mesh, key))
    for mesh, key in selected:
        world = mesh.matrix_world.copy()
        mesh.parent = obj
        mesh.matrix_world = world
        group = mesh.vertex_groups.new(name=key)
        group.add(list(range(len(mesh.data.vertices))), 1.0, "REPLACE")
        modifier = mesh.modifiers.new(name="Media Forge Skin", type="ARMATURE")
        modifier.object = obj
        modifier.use_vertex_groups = True
        modifier.use_bone_envelopes = False
    bpy.context.view_layer.update()


def set_pose(obj: bpy.types.Object, operation: dict[str, object]) -> None:
    rigid_armature(obj)
    if bpy.data.actions or any(o.type == "ARMATURE" and
            (o.get("media_forge_rig_schema") != 1 or o.animation_data is not None) for o in bpy.data.objects):
        raise RuntimeError("static typed pose export requires a scene without other rig kinds or actions")
    bones = operation.get("bones")
    if not isinstance(bones, list) or not 1 <= len(bones) <= 128:
        raise RuntimeError("pose count differs")
    selected, seen = [], set()
    for item in bones:
        key = bone_id(item.get("bone_id"))
        rotation = vector(item.get("rotation_degrees"))
        if key in seen or key not in obj.pose.bones or any(abs(v) > 180 for v in rotation):
            raise RuntimeError("pose bone or rotation differs")
        seen.add(key)
        selected.append((obj.pose.bones[key], rotation))
    for pose, rotation in selected:
        pose.rotation_mode = "XYZ"
        pose.rotation_euler = tuple(math.radians(v) for v in rotation)
    bpy.context.view_layer.update()


def create_clip(obj: bpy.types.Object, operation: dict[str, object], objects: dict[str, bpy.types.Object]) -> None:
    rigid_armature(obj, allow_animation=True)
    clip_id = bone_id(operation.get("clip_id"))
    replace = operation.get("replace", False)
    if type(replace) is not bool:
        raise RuntimeError("clip replace must be boolean")
    fps, end = operation.get("fps", 24), operation.get("frame_count")
    if type(fps) is not int or not 1 <= fps <= 60 or type(end) is not int or not 1 <= end <= min(600, fps*120):
        raise RuntimeError("clip frame range or fps differs")
    tracks = operation.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 128:
        raise RuntimeError("clip track count differs")
    parsed = {}
    for track in tracks:
        key = bone_id(track.get("bone_id"))
        values = track.get("keys")
        if key in parsed or key not in obj.pose.bones or not isinstance(values, list) or not 2 <= len(values) <= 256:
            raise RuntimeError("clip bone or key count differs")
        rows, previous = [], -1
        for item in values:
            frame, rotation = item.get("frame"), vector(item.get("rotation_degrees"))
            if type(frame) is not int or not previous < frame <= end or any(abs(v) > 180 for v in rotation):
                raise RuntimeError("clip key differs")
            previous = frame
            rows.append((frame, rotation))
        if rows[0][0] != 0 or rows[-1][0] != end:
            raise RuntimeError("clip endpoints differ")
        if operation.get("loop", False) and rows[0][1] != rows[-1][1]:
            raise RuntimeError("loop rotations differ")
        parsed[key] = rows
    for pose in obj.pose.bones:
        parsed.setdefault(pose.name, [(0, (0,0,0)), (end, (0,0,0))])
    scalar_keys = sum(len(rows)*3 for rows in parsed.values())
    samples = (end+1)*len(obj.data.bones)
    actions = list(bpy.data.actions)
    matches = [a for a in actions if a.get("media_forge_rig_id") == operation["object_id"]
               and a.get("media_forge_clip_id") == clip_id]
    if len(matches) > 1 or (replace and not matches):
        raise RuntimeError("clip replacement target is missing or ambiguous")
    replaced = matches[0] if replace else None
    if len(actions) + 1 - int(replaced is not None) > 32:
        raise RuntimeError("scene clip count exceeded")
    replaced_track = None
    for other in bpy.data.objects:
        if other.type == "ARMATURE":
            rigid_armature(other, allow_animation=True)
        elif other.animation_data is not None:
            raise RuntimeError("non-rig animation is not supported by typed clips")
        if other.animation_data is not None and other.animation_data.drivers:
            raise RuntimeError("drivers are not supported by typed clips")
        if other.animation_data is not None:
            if replaced is not None and other is not obj and other.animation_data.action is replaced:
                raise RuntimeError("replacement clip is shared by another object")
            for track in other.animation_data.nla_tracks:
                if not track.mute or len(track.strips) != 1 or track.strips[0].action not in actions:
                    raise RuntimeError("existing NLA state is not a muted clip stash")
                if replaced is not None and track.strips[0].action is replaced:
                    if other is not obj or replaced_track is not None:
                        raise RuntimeError("replacement clip stash is shared")
                    replaced_track = track
    if replaced is not None:
        if obj.animation_data is None:
            raise RuntimeError("replacement clip has no owning animation data")
        expected_users = 1 + int(replaced.use_fake_user) + int(obj.animation_data.action is replaced)
        if replaced_track is None or replaced.users != expected_users:
            raise RuntimeError("replacement clip has unsupported references")
    if actions and (bpy.context.scene.get("media_forge_clip_fps") != fps or
                    bpy.context.scene.render.fps != fps or bpy.context.scene.render.fps_base != 1):
        raise RuntimeError("clip fps must match the existing scene clips")
    for action in actions:
        rig = objects.get(action.get("media_forge_rig_id"))
        if action.get("media_forge_clip_schema") != 1 or rig is None or rig.type != "ARMATURE":
            raise RuntimeError("existing action is not a typed clip")
        if rig is obj and action.get("media_forge_clip_id") == clip_id and action is not replaced:
            raise RuntimeError("clip ID already exists")
        if len(action.layers) != 1 or len(action.layers[0].strips) != 1 or len(action.slots) != 1:
            raise RuntimeError("existing clip structure differs")
        strip = action.layers[0].strips[0]
        if len(strip.channelbags) != 1 or len(strip.channelbags[0].fcurves) > 384:
            raise RuntimeError("existing clip channels differ")
        old_end = action.get("media_forge_frame_count")
        if type(old_end) is not int or not 1 <= old_end <= 600:
            raise RuntimeError("existing clip frame count differs")
        if action is not replaced:
            samples += (old_end+1)*len(rig.data.bones)
        for curve in strip.channelbags[0].fcurves:
            if not 2 <= len(curve.keyframe_points) <= 256 or curve.modifiers:
                raise RuntimeError("existing clip key bounds differ")
            if re.fullmatch(r'pose.bones\["[a-z][a-z0-9._-]{0,47}"\].rotation_euler', curve.data_path) is None:
                raise RuntimeError("existing clip channel is not a bone rotation")
            for point in curve.keyframe_points:
                if not all(math.isfinite(v) for v in point.co) or not 0 <= point.co.x <= old_end:
                    raise RuntimeError("existing clip key is outside its frame bound")
            if action is not replaced:
                scalar_keys += len(curve.keyframe_points)
    if scalar_keys > 262144 or samples > 250000:
        raise RuntimeError("scene animation key or sample budget exceeded")
    animation = obj.animation_data_create()
    suffix = hashlib.sha256(str(operation["object_id"]).encode()).hexdigest()[:8]
    action_name = "mf." + clip_id + "." + suffix
    if replaced is not None:
        # All validation precedes mutation. This process edits an isolated copy;
        # allocation/export failure cannot commit it over the immutable source.
        # Release the old curves before allocation to retain the peak key budget.
        if animation.action is replaced:
            animation.action = None
        animation.nla_tracks.remove(replaced_track)
        replaced.use_fake_user = False
        bpy.data.actions.remove(replaced, do_unlink=False)
    action = bpy.data.actions.new(action_name)
    action["media_forge_clip_schema"] = 1
    action["media_forge_rig_id"] = str(operation["object_id"])
    action["media_forge_clip_id"] = clip_id
    action["media_forge_frame_count"] = end
    action["media_forge_clip_name"] = str(operation["name"])
    action["media_forge_loop"] = bool(operation.get("loop", False))
    action.use_fake_user = True
    slot = action.slots.new(obj.id_type, obj.name)
    layer = action.layers.new("Media Forge")
    strip = layer.strips.new(type="KEYFRAME")
    bag = strip.channelbags.new(slot)
    for key, rows in parsed.items():
        pose = obj.pose.bones[key]
        pose.rotation_mode = "XYZ"
        pose.location = (0,0,0)
        pose.scale = (1,1,1)
        for axis in range(3):
            curve = bag.fcurves.new(data_path=pose.path_from_id("rotation_euler"), index=axis)
            curve.keyframe_points.add(len(rows))
            for point, (frame, rotation) in zip(curve.keyframe_points, rows):
                point.co = (frame, math.radians(rotation[axis]))
                point.interpolation = "LINEAR"
            curve.update()
    track = animation.nla_tracks.new()
    track.name = action.name
    stash = track.strips.new(action.name, 0, action)
    stash.action_slot = slot
    track.mute, track.lock = True, True
    animation.action, animation.action_slot = action, slot
    bpy.context.scene.render.fps = fps
    bpy.context.scene.render.fps_base = 1
    bpy.context.scene["media_forge_clip_fps"] = fps
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 0, end
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()


def geometry_cost(obj: bpy.types.Object) -> int:
    """Conservative pre-allocation estimate for the bounded static modifier vocabulary."""
    if obj.type != "MESH":
        return 0
    cost = max(len(obj.data.vertices), sum(max(0, p.loop_total - 2) for p in obj.data.polygons))
    for modifier in obj.modifiers:
        if modifier.type == "MIRROR":
            cost *= 2 ** sum(modifier.use_axis)
        elif modifier.type == "BEVEL":
            cost *= 24 * int(modifier.segments) + 48
        elif modifier.type == "ARRAY":
            if (modifier.fit_type != "FIXED_COUNT" or not 1 <= modifier.count <= 64
                    or modifier.use_relative_offset or modifier.use_object_offset
                    or not modifier.use_constant_offset or modifier.offset_object is not None
                    or modifier.start_cap is not None or modifier.end_cap is not None):
                raise RuntimeError("apply unsupported array settings before geometry growth")
            cost *= modifier.count
        else:
            raise RuntimeError("apply unsupported modifiers before geometry growth")
        if cost > MAX_GROWTH_GEOMETRY:
            raise RuntimeError("recipe geometry growth budget exceeded")
    return cost


def check_growth(objects: dict[str, bpy.types.Object], added_cost: int) -> None:
    if added_cost < 0 or sum(geometry_cost(obj) for obj in objects.values()) + added_cost > MAX_GROWTH_GEOMETRY:
        raise RuntimeError("recipe geometry growth budget exceeded")


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
    if kind in {"primitive.add", "light.add", "camera.add", "object.duplicate", "armature.create"} and object_id in objects:
        raise RuntimeError("recipe object ID already exists")
    if kind == "armature.create":
        objects[object_id] = create_armature(operation)
        return
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
    if kind == "object.duplicate":
        source = objects.get(str(operation.get("source_object_id")))
        if source is None or source.type != "MESH":
            raise RuntimeError("duplicate source is not a known mesh")
        if source.parent is not None or source.constraints or source.animation_data is not None:
            raise RuntimeError("duplicate of parented, constrained or animated mesh is not supported")
        if source.data.shape_keys is not None or source.data.animation_data is not None:
            raise RuntimeError("duplicate of shape-key or animated mesh data is not supported")
        check_growth(objects, geometry_cost(source))
        obj = source.copy()
        obj.data = source.data.copy()
        obj.name = str(operation["name"])
        obj["media_forge_id"] = object_id
        bpy.context.collection.objects.link(obj)
        transform(obj, operation)
        objects[object_id] = obj
        return
    obj = objects.get(object_id)
    if obj is None:
        raise RuntimeError(f"unknown stable object ID: {object_id}")
    if kind == "animation.clip":
        create_clip(obj, operation, objects)
    elif kind == "skin.bind":
        bind_skin(obj, operation, objects)
    elif kind == "pose.set":
        set_pose(obj, operation)
    elif kind == "transform.set":
        transform(obj, operation)
    elif kind == "modifier.bevel":
        if obj.type != "MESH":
            raise RuntimeError("bevel target is not a mesh")
        if any(m.type == "ARRAY" for m in obj.modifiers):
            check_growth(objects, geometry_cost(obj) * (24 * int(operation["segments"]) + 47))
        modifier = obj.modifiers.new(name="Media Forge Bevel", type="BEVEL")
        modifier.width = float(operation["width"])
        modifier.segments = int(operation["segments"])
    elif kind == "modifier.mirror":
        if obj.type != "MESH":
            raise RuntimeError("mirror target is not a mesh")
        axes = operation.get("axes", ["X"])
        if not isinstance(axes, list) or not axes or len(axes) > 3 or any(a not in ("X", "Y", "Z") for a in axes) or len(set(axes)) != len(axes):
            raise RuntimeError("mirror axes differ")
        if any(m.type == "MIRROR" for m in obj.modifiers):
            raise RuntimeError("only one mirror modifier per object is supported")
        reference_id = operation.get("reference_object_id")
        reference = objects.get(str(reference_id)) if reference_id is not None else None
        if reference_id is not None and (reference is None or reference is obj):
            raise RuntimeError("mirror reference differs")
        threshold = float(operation.get("merge_threshold", 0.001))
        if not math.isfinite(threshold) or not 0 <= threshold <= 0.1:
            raise RuntimeError("mirror merge threshold differs")
        check_growth(objects, geometry_cost(obj) * (2 ** len(axes) - 1))
        modifier = obj.modifiers.new(name="Media Forge Mirror", type="MIRROR")
        modifier.use_axis = tuple(axis in axes for axis in ("X", "Y", "Z"))
        modifier.use_mirror_merge = threshold > 0
        modifier.merge_threshold = threshold
        modifier.mirror_object = reference
    elif kind == "modifier.array":
        if obj.type != "MESH":
            raise RuntimeError("array target is not a mesh")
        if (obj.parent is not None or obj.constraints or obj.animation_data is not None
                or obj.data.shape_keys is not None or obj.data.animation_data is not None):
            raise RuntimeError("array requires an unparented unconstrained static mesh")
        if any(m.type == "ARRAY" for m in obj.modifiers):
            raise RuntimeError("only one array modifier per object is supported")
        count = operation.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or not 2 <= count <= 64:
            raise RuntimeError("array count differs")
        offset = vector(operation.get("local_offset"))
        if not any(offset):
            raise RuntimeError("array local offset must be nonzero")
        check_growth(objects, geometry_cost(obj) * (count - 1))
        modifier = obj.modifiers.new(name="Media Forge Array", type="ARRAY")
        modifier.fit_type = "FIXED_COUNT"
        modifier.count = count
        modifier.use_relative_offset = False
        modifier.use_object_offset = False
        modifier.use_constant_offset = True
        modifier.constant_offset_displace = offset
        modifier.use_merge_vertices = False
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
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise RuntimeError("recipe operation differs")
        try:
            apply_operation(operation, objects)
        except Exception as exc:
            # Only fixed reason codes cross the process boundary, never bpy text,
            # source paths, user names or traceback contents.
            reason = {
                f"unknown stable object ID: {operation.get('object_id')}": "object_not_found",
                "recipe object ID already exists": "object_exists",
                "clip replacement target is missing or ambiguous": "clip_target_missing",
            }.get(str(exc), "operation_rejected")
            (Path.cwd() / args.result).write_text(json.dumps({
                "schema_version": "media-forge.scene-recipe-failure@1",
                "blender_version": args.expected_version,
                "operation_index": index,
                "reason": reason,
            }) + "\n", encoding="utf-8")
            raise
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
