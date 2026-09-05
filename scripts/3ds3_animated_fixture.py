"""Create a small animated GLB for the 3DS-3 real-browser acceptance run.

This script is executed by the pinned Blender runtime, not by Media Forge core.
"""

from __future__ import annotations

from pathlib import Path
import sys

import bpy


def output_argument() -> Path:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(arguments) != 1:
        raise SystemExit("usage: blender --background --python scripts/3ds3_animated_fixture.py -- OUTPUT.glb")
    output = Path(arguments[0]).resolve()
    if output.suffix.lower() != ".glb" or not output.parent.is_dir():
        raise SystemExit("output must be a GLB in an existing directory")
    return output


def main() -> None:
    output = output_argument()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
    cube = bpy.context.active_object
    cube.name = "AnimatedCube"
    cube.keyframe_insert(data_path="rotation_euler", frame=1)
    cube.rotation_euler.z = 3.141592653589793
    cube.location.z = 1.0
    cube.keyframe_insert(data_path="rotation_euler", frame=25)
    cube.keyframe_insert(data_path="location", frame=25)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 25
    scene.render.fps = 24
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        export_animations=True,
        export_materials="EXPORT",
    )


if __name__ == "__main__":
    main()
