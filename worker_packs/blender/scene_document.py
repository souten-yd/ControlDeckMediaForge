# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted Blender-side validator and GLB preview exporter for scene revisions."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
import sys
from typing import Any

import bpy


MAX_OBJECTS = 20_000
MAX_MESHES = 10_000
MAX_VERTICES = 5_000_000
MAX_TRIANGLES = 10_000_000
FIXED_NAMES = {
    "source": "scene.blend",
    "preview": "preview.glb",
    "result": "result.json",
}


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=(FIXED_NAMES["source"],), required=True)
    parser.add_argument("--preview", choices=(FIXED_NAMES["preview"],), required=True)
    parser.add_argument("--result", choices=(FIXED_NAMES["result"],), required=True)
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args(values)


def finite(values: object) -> bool:
    try:
        return all(math.isfinite(float(value)) for value in values)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def animation_settings(actions: Any, fps: float) -> dict[str, object]:
    """Observe saved typed metadata and actual ranges; never infer loop intent."""
    clips: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    unreported = 0
    for action in actions:
        rig_id, clip_id = action.get("media_forge_rig_id"), action.get("media_forge_clip_id")
        loop = action.get("media_forge_loop")
        start, end = map(float, action.frame_range)
        valid = (
            action.get("media_forge_clip_schema") == 1
            and isinstance(rig_id, str) and re.fullmatch(r"[a-z][a-z0-9._-]{0,63}", rig_id)
            and isinstance(clip_id, str) and re.fullmatch(r"[a-z][a-z0-9._-]{0,47}", clip_id)
            and type(loop) in (bool, int) and loop in (0, 1)
            and math.isfinite(start) and math.isfinite(end)
            and -2_000_000 <= start <= end <= 2_000_000
        )
        if not valid or len(clips) >= 32 or (rig_id, clip_id) in seen:
            unreported += 1
            continue
        seen.add((rig_id, clip_id))
        clips.append({"object_id": rig_id, "clip_id": clip_id,
                      "frame_start": start, "frame_end": end, "loop_requested": bool(loop)})
    return {"schema_version": "media-forge.animation-settings@1", "fps": fps,
            "clips": clips, "unreported_actions": unreported}


def inspect_scene() -> dict[str, object]:
    objects = list(bpy.data.objects)
    meshes = list(bpy.data.meshes)
    if not objects or len(objects) > MAX_OBJECTS or len(meshes) > MAX_MESHES:
        raise RuntimeError("scene object or mesh count is outside the accepted bound")
    if bpy.data.libraries:
        raise RuntimeError("linked Blender libraries are not accepted")
    external_images = [
        image.name
        for image in bpy.data.images
        if image.source not in {"GENERATED", "VIEWER"} and image.packed_file is None
    ]
    if external_images:
        raise RuntimeError("external Blender image files are not accepted")

    vertices = 0
    triangles = 0
    for obj in objects:
        if not finite(value for row in obj.matrix_world for value in row):
            raise RuntimeError("scene contains a non-finite object transform")
    for mesh in meshes:
        vertices += len(mesh.vertices)
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        if vertices > MAX_VERTICES or triangles > MAX_TRIANGLES:
            raise RuntimeError("scene geometry exceeds its accepted bound")
        for vertex in mesh.vertices:
            if not finite(vertex.co):
                raise RuntimeError("scene contains a non-finite mesh coordinate")

    unit_meters = float(bpy.context.scene.unit_settings.scale_length)
    if not math.isfinite(unit_meters) or unit_meters != 1.0:
        raise RuntimeError("scene unit scale must be exactly one meter")
    return {
        "objects": len(objects),
        "meshes": len(meshes),
        "vertices": vertices,
        "triangles": triangles,
        "materials": len(bpy.data.materials),
        "images": len(bpy.data.images),
        "animations": len(bpy.data.actions),
        "animation_settings": animation_settings(
            bpy.data.actions, bpy.context.scene.render.fps / bpy.context.scene.render.fps_base),
        "text_blocks": len(bpy.data.texts),
        "linked_libraries": 0,
        "external_images": 0,
        "unit_meters": unit_meters,
    }


def main() -> None:
    args = arguments()
    expected = tuple(int(part) for part in args.expected_version.split("."))
    if tuple(bpy.app.version[:3]) != expected or not bpy.app.background:
        raise RuntimeError("Blender scene worker runtime identity differs")
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.ops.wm.open_mainfile(
        filepath=str(Path.cwd() / args.source), load_ui=False, use_scripts=False
    )
    facts = inspect_scene()
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    typed_static_pose = bool(armatures) and not bpy.data.actions and all(
        obj.get("media_forge_rig_schema") == 1 and obj.animation_data is None for obj in armatures
    )
    bpy.ops.export_scene.gltf(
        filepath=str(Path.cwd() / args.preview),
        export_format="GLB",
        export_apply=True,
        export_animations=True,
        export_rest_position_armature=not typed_static_pose,
    )
    result = {
        "schema_version": "media-forge.blender-scene-validation@1",
        "blender_version": args.expected_version,
        "background": True,
        "autoexec_disabled": not bpy.context.preferences.filepaths.use_scripts_auto_execute,
        **facts,
    }
    (Path.cwd() / args.result).write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
