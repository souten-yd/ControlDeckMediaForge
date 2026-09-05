"""Create isolated Blender GUI preferences without evaluating inline code."""

from __future__ import annotations

import bpy


bpy.ops.wm.save_userpref()
