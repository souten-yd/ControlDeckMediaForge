# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted Blender-side preflight for the pinned G8 runtime."""

from __future__ import annotations

import argparse
import json
import sys

import bpy


PREFIX = "MEDIA_FORGE_BLENDER_PREFLIGHT="


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args(values)


def main() -> None:
    expected = tuple(int(part) for part in arguments().expected_version.split("."))
    actual = tuple(int(part) for part in bpy.app.version[:3])
    if actual != expected:
        raise RuntimeError(f"Blender version differs: {actual} != {expected}")
    if not bpy.app.background:
        raise RuntimeError("Blender preflight is not running in background mode")
    if not hasattr(bpy.ops.import_scene, "gltf") or not hasattr(bpy.ops.export_scene, "gltf"):
        raise RuntimeError("Blender glTF operators are unavailable")
    result = {
        "version": ".".join(str(part) for part in actual),
        "background": True,
        "gltf_import": True,
        "gltf_export": True,
        "python": ".".join(str(part) for part in sys.version_info[:3]),
    }
    print(PREFIX + json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
