"""Fault fixture executed by real candidate Blender, never a production probe."""
import json

import bpy

version = ".".join(str(part) for part in bpy.app.version[:3])
assert version == "4.5.13"
print("MEDIA_FORGE_BLENDER_PREFLIGHT=" + json.dumps({
    "version": version,
    "background": False,
    "fixture": "deliberately_rejected_candidate_probe",
}))
