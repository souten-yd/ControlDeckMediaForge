"""Real typed robot rig acceptance, not a replacement for animation acceptance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from robot_fixture import recipe as static_recipe


def recipe() -> list[dict[str, Any]]:
    operations = static_recipe()
    bones = [{"bone_id": "root", "head": [0,0,0.97], "tail": [0,0,1.12]},
             {"bone_id": "spine", "head": [0,0,1.12], "tail": [0,0,1.68], "parent_bone_id": "root"},
             {"bone_id": "head", "head": [0,0,1.68], "tail": [0,0,2], "parent_bone_id": "spine"}]
    mapping = {"pelvis": "root", "waist": "root", "torso": "spine", "chest": "spine",
               "neck": "head", "head": "head", "visor": "head"}
    for suffix, sign in (("", 1), ("_l", -1)):
        for key, head, tail, parent in (
            ("upper_arm", [sign*0.46,0,1.53], [sign*0.46,0,1.10], "spine"),
            ("forearm", [sign*0.46,0,1.10], [sign*0.46,0,0.69], "upper_arm"+suffix),
            ("thigh", [sign*0.17,0,0.97], [sign*0.17,0,0.49], "root"),
            ("shin", [sign*0.17,0,0.49], [sign*0.17,0,0.09], "thigh"+suffix)):
            bones.append({"bone_id": key+suffix, "head": head, "tail": tail, "parent_bone_id": parent})
        for part, key in (("shoulder", "upper_arm"), ("upper_arm", "upper_arm"), ("elbow", "forearm"),
                          ("forearm", "forearm"), ("fist", "forearm"), ("thigh", "thigh"),
                          ("knee", "shin"), ("shin", "shin"), ("foot", "shin")):
            mapping[part+suffix] = key+suffix
    operations.extend([
        {"type": "armature.create", "object_id": "rig", "name": "Robot Rig", "bones": bones},
        {"type": "skin.bind", "object_id": "rig", "bindings": [
            {"mesh_object_id": part, "bone_id": key} for part,key in mapping.items()]},
    ])
    return operations


def inspect_blend(source: Path, glb: Path, folder: Path, *, posed: bool) -> None:
    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    objects = {o.get("media_forge_id"): o for o in bpy.data.objects}
    rig = objects["rig"]
    assert len(rig.data.bones) == 11
    assert rig.data.bones["forearm"].parent.name == "upper_arm"
    vertices = {}
    for key, obj in objects.items():
        if obj.type != "MESH":
            continue
        assert obj.parent is rig and obj.modifiers[-1].type == "ARMATURE"
        assert all(len(v.groups) == 1 and abs(v.groups[0].weight-1) < 1e-6 for v in obj.data.vertices)
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            vertices[key] = [list(evaluated.matrix_world @ v.co) for v in mesh.vertices]
        finally:
            evaluated.to_mesh_clear()
    assert len(vertices) == 25
    if posed:
        rest = json.loads((folder / "inspection.json").read_text())["world_vertices"]
        movement = max(sum((a-b)**2 for a,b in zip(u,v))**0.5
                       for u,v in zip(vertices["forearm"], rest["forearm"], strict=True))
        unchanged = max(abs(a-b) for u,v in zip(vertices["torso"],rest["torso"],strict=True) for a,b in zip(u,v))
        assert movement > 0.1 and unchanged < 1e-6, (movement, unchanged)
    else:
        movement = 0
        # Disable each skin in memory and compare the actual evaluated rest vertices.
        for key, saved in vertices.items():
            obj = objects[key]
            obj.modifiers[-1].show_viewport = False
            bpy.context.view_layer.update()
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                baseline = [list(evaluated.matrix_world @ v.co) for v in mesh.vertices]
                assert max(abs(a-b) for u,v in zip(saved,baseline,strict=True) for a,b in zip(u,v)) < 1e-5
            finally:
                evaluated.to_mesh_clear()
                obj.modifiers[-1].show_viewport = True
                bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    imported = list(bpy.context.scene.objects)
    rigs = [o for o in imported if o.type == "ARMATURE"]
    assert rigs and any(len(o.data.bones) >= 11 for o in rigs)
    custom_shapes = {p.custom_shape for r in rigs for p in r.pose.bones if p.custom_shape is not None}
    meshes = [o for o in imported if o.type == "MESH" and o not in custom_shapes]
    assert len(meshes) == 25, [(o.name, o.get("media_forge_id")) for o in meshes]
    assert all(any(m.type == "ARMATURE" for m in o.modifiers) for o in meshes)
    assert all(abs(sum(g.weight for g in v.groups)-1) < 1e-5 for o in meshes for v in o.data.vertices)
    forearm = next(o for o in meshes if o.name == "Forearm")
    evaluated = forearm.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        actual = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        for axis in range(3):
            for bound in (min, max):
                expected = bound(v[axis] for v in vertices["forearm"])
                observed = bound(v[axis] for v in actual)
                assert abs(expected-observed) < 1e-4, ("GLB pose bounds", posed, axis, expected, observed)
    finally:
        evaluated.to_mesh_clear()
    report = {"blender": bpy.app.version_string, "bones": 11, "bound_meshes": 25,
              "world_vertices": vertices, "forearm_max_movement_m": movement,
              "rest_preserved": not posed, "glb_reimport_skin_weights": True,
              "importer_bone_display_helpers": len(custom_shapes),
              "glb_forearm_pose_bounds_preserved": True,
              "not_tested": ["animation clips", "distributed vertex weights", "installed MCP", "engine import"]}
    (folder / ("posed-inspection.json" if posed else "inspection.json")).write_text(json.dumps(report)+"\n")
