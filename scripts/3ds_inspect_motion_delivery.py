"""Run with managed Blender --background --disable-autoexec --python-exit-code 1.

Independently import an OpenCode-delivered GLB and evaluate its skinned geometry.
Does not save or alter the input. This is not an artistic or game-engine gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def inspect(glb: Path) -> dict[str, Any]:
    import bpy

    digest = hashlib.sha256(glb.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 24
    bpy.ops.import_scene.gltf(filepath=str(glb))
    rigs = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    assert len(rigs) == 1, "Expected one robot rig"
    rig = rigs[0]
    helpers = {bone.custom_shape for bone in rig.pose.bones if bone.custom_shape is not None}
    all_meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o not in helpers]
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and any(
        m.type == "ARMATURE" and m.object == rig for m in o.modifiers)]
    assert len(meshes) >= 4, "Expected skinned robot parts"
    assert set(meshes) == set(all_meshes), "Robot contains unbound parts"
    for mesh in meshes:
        for vertex in mesh.data.vertices:
            assert abs(sum(g.weight for g in vertex.groups) - 1) < 1e-5
    assert rig.animation_data is not None
    actions = {}
    for name in ("idle", "arm_swing"):
        matching = [a for a in bpy.data.actions if a.name.startswith("mf." + name + ".")]
        assert len(matching) == 1, (name, [a.name for a in bpy.data.actions])
        actions[name] = matching[0]

    def bounds() -> tuple[dict[str, list[float]], int]:
        result = {}
        triangles = 0
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in meshes:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            try:
                points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
                assert points
                assert all(math.isfinite(value) for point in points for value in point)
                result[obj.name] = [fn(p[i] for p in points) for fn in (min, max) for i in range(3)]
                mesh.calc_loop_triangles()
                triangles += len(mesh.loop_triangles)
            finally:
                evaluated.to_mesh_clear()
        return result, triangles

    observations = {}
    for name, action in actions.items():
        end = 48 if name == "idle" else 24
        assert abs(action.frame_range[0]) < 1e-4 and abs(action.frame_range[1] - end) < 1e-4
        rig.animation_data.action = action
        rig.animation_data.action_slot = action.slots[0]
        for track in rig.animation_data.nla_tracks:
            track.mute = True
        samples = []
        for frame in (0, end // 2, end):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            positions, triangles = bounds()
            assert 0 < triangles <= 3000
            samples.append(positions)
        moving = {key: max(abs(a - b) for a, b in zip(samples[0][key], samples[1][key], strict=True))
                  for key in samples[0]}
        assert max(moving.values()) > 0.001, (name, "No actual skinned movement")
        endpoint_error = max(abs(a - b) for key in samples[0]
                             for a, b in zip(samples[0][key], samples[2][key], strict=True))
        assert endpoint_error < 1e-5, (name, "Loop endpoints differ")
        dimensions = [max(row[i + 3] for row in samples[0].values()) -
                      min(row[i] for row in samples[0].values()) for i in range(3)]
        assert 0.8 <= max(dimensions) <= 1.2, dimensions
        observations[name] = {"duration_sec": end / 24, "triangles": triangles,
                              "dimensions_m": dimensions, "bounds_samples": samples,
                              "movement_m": moving, "loop_endpoint_error_m": endpoint_error}
    assert hashlib.sha256(glb.read_bytes()).hexdigest() == digest
    return {"verified": True, "blender": bpy.app.version_string, "glb_sha256": digest,
            "bone_count": len(rig.data.bones), "skinned_meshes": len(meshes), "clips": observations,
            "not_tested": ["artistic quality", "mesh contact", "source versus GLB comparison",
                           "browser/engine playback", "walking/root motion", "smooth weights"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glb", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    print("MOTION_INSPECTION=" + json.dumps(inspect(args.glb.resolve(strict=True)), ensure_ascii=False))
