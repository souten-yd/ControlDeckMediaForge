"""Managed Blender-only feasibility probe, not a public recipe or character-quality gate.

Run with --background --factory-startup --disable-autoexec --python-exit-code 1.
Only a new explicit evidence directory is written; no existing scene is opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any


def points(obj: Any) -> list[tuple[float, ...]]:
    import bpy
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [tuple(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def point_set(values: list[tuple[float, ...]]) -> set[tuple[float, ...]]:
    return {tuple(round(value, 5) for value in point) for point in values}


def point_error(first: list[tuple[float, ...]], second: list[tuple[float, ...]]) -> float:
    """Symmetric world-space distance; tolerate exported vertex splitting, not lost geometry."""
    assert first and second
    return max(max(min(math.dist(p, q) for q in second) for p in first),
               max(min(math.dist(p, q) for q in first) for p in second))


def weight_stats(obj: Any, *, normalized: bool = True) -> dict[str, int | float]:
    raw = [[group.weight for group in vertex.groups] for vertex in obj.data.vertices]
    assert all(all(math.isfinite(w) and 0 <= w <= 1 for w in row) for row in raw)
    weights = [[weight for weight in row if weight > 0] for row in raw]
    assert weights and all(row and all(math.isfinite(w) and 0 < w <= 1 for w in row) for row in weights)
    error = max(abs(sum(row) - 1) for row in weights)
    if normalized:
        assert error < 1e-5 and max(map(len, weights)) <= 4, (error, max(map(len, weights)))
    mixed = sum(sum(w > 1e-6 for w in row) > 1 for row in weights)
    assert mixed > 0, "Rigid single-bone assignment is not this probe's goal"
    return {"vertices": len(weights), "mixed_vertices": mixed, "max_influences": max(map(len, weights)),
            "normalization_error": error}


def normalize_weights(obj: Any) -> None:
    """Explicitly retain up to four positive influences and normalize per vertex."""
    for vertex in obj.data.vertices:
        groups = [(group.group, group.weight) for group in vertex.groups]
        selected = sorted(((index, weight) for index, weight in groups if weight > 0),
                          key=lambda item: (-item[1], item[0]))[:4]
        total = sum(weight for _, weight in selected)
        assert math.isfinite(total) and total > 0
        for index, _ in groups:
            obj.vertex_groups[index].remove([vertex.index])
        for index, weight in selected:
            obj.vertex_groups[index].add([vertex.index], weight / total, "REPLACE")


def main() -> None:
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = args.evidence_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=16, radius=1, location=(0, 0, .5))
    mesh = bpy.context.object
    mesh.name = "WeightedSurface"
    mesh.scale = (.15, .15, .65)
    for polygon in mesh.data.polygons:
        polygon.use_smooth = True
    bpy.context.view_layer.update()
    original = points(mesh)
    data = bpy.data.armatures.new("ProbeRig")
    rig = bpy.data.objects.new("ProbeRig", data)
    bpy.context.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    lower = data.edit_bones.new("lower")
    lower.head, lower.tail = (0, 0, 0), (0, 0, .5)
    upper = data.edit_bones.new("upper")
    upper.head, upper.tail, upper.parent = (0, 0, .5), (0, 0, 1), lower
    upper.use_connect = True
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.select_set(True)
    assert bpy.ops.object.parent_set(type="ARMATURE_AUTO", keep_transform=True) == {"FINISHED"}
    bpy.context.view_layer.update()
    raw_stats = weight_stats(mesh, normalized=False)
    normalize_weights(mesh)
    stats = weight_stats(mesh)
    rest = points(mesh)
    assert len(rest) == len(original)
    rest_error = max(abs(a - b) for p, q in zip(original, rest, strict=True) for a, b in zip(p, q, strict=True))
    assert rest_error < 1e-5
    bone = rig.pose.bones["upper"]
    bone.rotation_mode = "XYZ"
    bone.rotation_euler[0] = .6
    bpy.context.view_layer.update()
    posed = points(mesh)
    displacement = max(math.dist(p, q) for p, q in zip(rest, posed, strict=True))
    assert displacement > .01
    bone.rotation_euler[0] = 0
    bpy.context.view_layer.update()
    source, glb = root / "weighted.blend", root / "weighted.glb"
    bpy.ops.wm.save_as_mainfile(filepath=str(source), check_existing=False)
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_skins=True,
                             export_animations=False, export_apply=False)
    provenance = {"kind": "isolated feasibility probe", "blender": bpy.app.version_string,
                  "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    lineage = {"input_assets": [], "fixture": "16x16 UV sphere, two connected bones, 0.6 rad local X pose"}
    files = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
             for p in (source, glb)}
    (root / "provenance.json").write_text(json.dumps(
        {"provenance": provenance, "lineage": lineage, "files": files, "validation": "pending"}, indent=2) + "\n")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    imported_rig, = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    helpers = {bone.custom_shape for bone in imported_rig.pose.bones if bone.custom_shape is not None}
    imported, = [o for o in bpy.context.scene.objects if o.type == "MESH" and o not in helpers]
    assert any(modifier.type == "ARMATURE" and modifier.object == imported_rig for modifier in imported.modifiers)
    imported_stats = weight_stats(imported)
    assert point_set(points(imported)) == point_set(rest)
    imported_bone = imported_rig.pose.bones["upper"]
    imported_bone.rotation_mode = "XYZ"
    imported_bone.rotation_euler[0] = .6
    bpy.context.view_layer.update()
    pose_error = point_error(points(imported), posed)
    comparison = {"raw_heat_weights": raw_stats, "source_weights": stats, "imported_weights": imported_stats,
                  "pose_world_error": pose_error, "rest_error": rest_error,
                  "max_displacement": displacement}
    (root / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps(comparison), flush=True)
    assert pose_error < 1e-5, "Imported local-bone pose does not reproduce source deformation"
    report = {"passed": True, "elapsed_sec": round(time.monotonic() - start, 3),
              "raw_heat_weights": raw_stats, "source_weights": stats, "imported_weights": imported_stats,
              "rest_error": rest_error, "max_displacement": displacement,
              "pose_world_error": pose_error,
              "glb_rest_and_pose_points_match": True,
              "provenance": provenance, "lineage": lineage, "files": files,
              "not_tested": ["typed API", "OpenCode", "complex character", "heat failure handling",
                             "weight correction", "animation clips", "engine import", "artistic quality"]}
    (root / "observations.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
