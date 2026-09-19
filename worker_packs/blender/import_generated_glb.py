# SPDX-License-Identifier: GPL-3.0-or-later
"""Import a core-validated generated GLB as an editable packed Blender scene."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import bpy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if tuple(bpy.app.version[:3]) != tuple(map(int, args.expected_version.split("."))):
        raise RuntimeError("Blender generation importer version differs")
    if not bpy.app.background:
        raise RuntimeError("generated GLB import requires background mode")
    source = Path.cwd() / "generated.glb"
    output = Path.cwd() / "generated.blend"
    if source.is_symlink() or not source.is_file() or output.exists():
        raise RuntimeError("generated scene staging is invalid")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.ops.import_scene.gltf(filepath=str(source))
    if not any(obj.type == "MESH" for obj in bpy.data.objects):
        raise RuntimeError("generated GLB has no mesh")
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    for index, obj in enumerate(bpy.data.objects):
        obj["media_forge_id"] = f"generated_{index}"
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)


if __name__ == "__main__":
    main()
