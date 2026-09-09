"""Typed stairs: real evaluated geometry, GLB round trip and immutable revisions."""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any


def recipe() -> list[dict[str, Any]]:
    return [
        {"type": "primitive.add", "object_id": "step", "primitive": "cube", "name": "Steps",
         "dimensions": [.4, .8, .2]},
        {"type": "material.set", "object_id": "step", "base_color": [.05, .25, .3, 1]},
        {"type": "modifier.array", "object_id": "step", "count": 6, "local_offset": [1.5, 0, 1.5]},
    ]


def inspect_blend(source: Path, glb: Path, folder: Path, *, edited: bool) -> None:
    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    step = next(obj for obj in bpy.data.objects if obj.get("media_forge_id") == "step")
    assert len(step.data.vertices) == 8 and len(step.data.polygons) == 6
    assert {tuple(v.co) for v in step.data.vertices} == set(itertools.product((-1, 1), repeat=3))
    assert len(step.modifiers) == 1
    modifier = step.modifiers[0]
    assert modifier.type == "ARRAY" and modifier.fit_type == "FIXED_COUNT" and modifier.count == 6
    assert modifier.use_constant_offset and not modifier.use_relative_offset and not modifier.use_object_offset
    assert not modifier.use_merge_vertices
    assert tuple(modifier.constant_offset_displace) == (1.5, 0, 1.5)

    def geometry(objects: list[Any]) -> tuple[set[tuple[float, ...]], int]:
        points = set()
        triangles = 0
        for obj in objects:
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles()
                triangles += len(mesh.loop_triangles)
                points.update(tuple(round(v, 5) for v in evaluated.matrix_world @ vertex.co)
                              for vertex in mesh.vertices)
            finally:
                evaluated.to_mesh_clear()
        return points, triangles

    points, triangles = geometry([step])
    shift = 2 if edited else 0
    expected = {tuple(round(value, 5) for value in ((x + index*1.5)*.2 + shift, y*.4, (z + index*1.5)*.1))
                for index in range(6) for x, y, z in itertools.product((-1, 1), repeat=3)}
    assert points == expected and triangles == 72, (len(points), len(expected), triangles)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    imported, imported_triangles = geometry(meshes)
    assert imported == expected and imported_triangles == triangles
    report = {"blender": bpy.app.version_string, "copies": 6, "base_vertices": 8,
              "triangles": triangles, "unique_evaluated_points": len(points),
              "bounds": [[min(p[i] for p in points), max(p[i] for p in points)] for i in range(3)],
              "glb_reimport_exact_points": True, "local_scale_spacing_verified": True,
              "edited_translation_m": shift, "not_tested": ["engine import", "watertight union"]}
    (folder / ("posed-inspection.json" if edited else "inspection.json")).write_text(json.dumps(report, indent=2) + "\n")
