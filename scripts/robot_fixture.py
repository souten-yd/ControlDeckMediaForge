"""Typed static robot fixture and real evaluated-mesh visual acceptance.

Diagnostic only: renders on CPU, never changes the input blend or user settings.
No animation/rigging or engine-quality claim is implied by this fixture.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def recipe() -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    colors = {"armor": [0.055, 0.19, 0.28, 1], "joint": [0.035, 0.045, 0.055, 1],
              "accent": [0.95, 0.28, 0.055, 1], "visor": [0.06, 0.8, 0.75, 1]}

    def part(name: str, size: list[float], at: list[float], color: str,
             *, pair: bool = False, primitive: str = "cube") -> None:
        operations.extend([
            {"type": "primitive.add", "object_id": name, "name": name.replace("_", " ").title(),
             "primitive": primitive, "dimensions": size, "location": at, "vertices": 12},
            {"type": "material.set", "object_id": name, "base_color": colors[color],
             "metallic": 0.65 if color == "armor" else 0.2, "roughness": 0.32},
        ])
        if primitive == "cube":
            operations.append({"type": "modifier.bevel", "object_id": name,
                               "width": min(size) * 0.12, "segments": 2})
        if pair:
            operations.append({"type": "object.duplicate", "source_object_id": name,
                "object_id": name + "_l", "name": name.title() + " L", "location": [-at[0], at[1], at[2]]})

    part("pelvis", [0.52, 0.32, 0.22], [0, 0, 0.97], "armor")
    part("waist", [0.28, 0.25, 0.24], [0, 0, 1.12], "joint")
    part("torso", [0.64, 0.38, 0.48], [0, 0, 1.40], "armor")
    part("chest", [0.36, 0.10, 0.20], [0, -0.19, 1.44], "accent")
    part("neck", [0.18, 0.20, 0.22], [0, 0, 1.68], "joint")
    part("head", [0.34, 0.30, 0.30], [0, -0.01, 1.85], "armor")
    part("visor", [0.27, 0.08, 0.09], [0, -0.155, 1.87], "visor")
    part("shoulder", [0.30, 0.40, 0.29], [0.40, 0, 1.53], "accent", pair=True)
    part("upper_arm", [0.20, 0.25, 0.32], [0.46, 0, 1.30], "armor", pair=True)
    part("elbow", [0.22, 0.24, 0.22], [0.46, 0, 1.10], "joint", pair=True, primitive="uv_sphere")
    part("forearm", [0.25, 0.30, 0.32], [0.46, -0.025, 0.91], "armor", pair=True)
    part("fist", [0.21, 0.26, 0.20], [0.46, -0.035, 0.69], "joint", pair=True)
    part("thigh", [0.21, 0.27, 0.38], [0.17, 0, 0.73], "armor", pair=True)
    part("knee", [0.23, 0.31, 0.18], [0.17, -0.02, 0.49], "accent", pair=True)
    part("shin", [0.22, 0.27, 0.34], [0.17, 0, 0.28], "armor", pair=True)
    part("foot", [0.28, 0.44, 0.18], [0.17, -0.085, 0.09], "armor", pair=True)
    return operations


def contact_pairs() -> list[tuple[str, str]]:
    pairs = [("pelvis", "waist"), ("waist", "torso"), ("torso", "chest"),
             ("torso", "neck"), ("neck", "head"), ("head", "visor")]
    for suffix in ("", "_l"):
        for a, b in (("shoulder", "upper_arm"), ("upper_arm", "elbow"), ("elbow", "forearm"),
                     ("forearm", "fist"), ("thigh", "knee"), ("knee", "shin"), ("shin", "foot")):
            pairs.append((a + suffix, b + suffix))
        pairs.extend([("torso", "shoulder" + suffix), ("pelvis", "thigh" + suffix)])
    return pairs


def inspect_blend(source: Path, destination: Path) -> None:
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    objects = {obj.get("media_forge_id"): obj for obj in bpy.data.objects if obj.type == "MESH"}
    meshes = {}
    triangle_count = 0
    for key, obj in objects.items():
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
            edges = {tuple(sorted((t[i], t[(i + 1) % 3]))) for t in triangles for i in range(3)}
            meshes[key] = (vertices, edges, BVHTree.FromPolygons(vertices, triangles, all_triangles=True))
            triangle_count += len(triangles)
        finally:
            evaluated.to_mesh_clear()

    def crosses(a: str, b: str) -> bool:
        vertices, edges, _ = meshes[a]
        tree = meshes[b][2]
        for u, v in edges:
            direction = vertices[v] - vertices[u]
            if direction.length < 1e-8:
                continue
            hit = tree.ray_cast(vertices[u], direction.normalized(), direction.length + 1e-6)
            if hit[0] is not None:
                return True
        return False

    contacts = [{"a": a, "b": b, "surface_intersection": crosses(a, b) or crosses(b, a)}
                for a, b in contact_pairs()]
    # Negative fixture: an actually separated head must not pass the ray test.
    original_head = meshes["head"]
    head_vertices, head_edges, _ = original_head
    meshes["head"] = ([v + Vector((0, 0, 5)) for v in head_vertices], head_edges, original_head[2])
    # Test translated head edges against the unmodified neck triangles only;
    # do not use the original head BVH for this negative assertion.
    separated_head_rejected = not crosses("head", "neck")
    meshes["head"] = original_head
    assert separated_head_rejected
    report = {"blender": bpy.app.version_string, "mesh_count": len(meshes), "triangles": triangle_count,
              "contacts": contacts, "contact_method": "evaluated world-mesh edge rays against triangle BVH",
              "separated_head_rejected": separated_head_rejected,
              "not_tested": ["rig/animation", "engine import", "arbitrary enclosed/coplanar contact",
                             "user approval of artistic quality"]}
    destination.write_text(json.dumps(report, indent=2) + "\n")
    assert all(row["surface_intersection"] for row in contacts), contacts
    assert triangle_count < 10_000
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.world.color = (0.18, 0.18, 0.18)
    for name, position, power, size in (("key", (3, -4, 5), 650, 4), ("fill", (-3, -2, 3), 350, 3),
                                        ("rim", (1, 3, 4), 700, 3)):
        light = bpy.data.lights.new(name, "AREA")
        light.energy, light.shape, light.size = power, "DISK", size
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector((0, 0, 1)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    camera = bpy.data.objects.new("Acceptance camera", bpy.data.cameras.new("Acceptance camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type, camera.data.ortho_scale = "ORTHO", 2.4
    for name, position in (("front", (0, -5, 1.05)), ("side", (5, 0, 1.05)), ("three-quarter", (3, -5, 2.8))):
        camera.location = position
        camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(destination.parent / (name + ".png"))
        bpy.ops.render.render(write_still=True)
