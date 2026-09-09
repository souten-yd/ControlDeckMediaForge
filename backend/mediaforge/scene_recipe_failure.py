"""Read bounded worker failure context without exposing worker exception text."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat

from .scene_recipes import SceneRecipe


REASONS = {
    "operation_rejected": "operation rejected; inspect the scene and operation constraints",
    "object_not_found": "target object does not exist; inspect stable object IDs",
    "object_exists": "target object ID already exists; choose a new stable ID",
    "clip_target_missing": "clip replacement target is missing or ambiguous",
}


def recipe_failure_message(path: Path, recipe: SceneRecipe, version: str) -> str:
    """Run in a worker thread; malformed/missing diagnostics remain generic."""
    fallback = "Blender rejected the typed scene recipe"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
                return fallback
            data = os.read(fd, 4097)
        finally:
            os.close(fd)
        if len(data) > 4096:
            return fallback
        result = json.loads(data)
    except (OSError, ValueError, RecursionError):
        return fallback
    if not isinstance(result, dict) or set(result) != {
        "schema_version", "blender_version", "operation_index", "reason"
    }:
        return fallback
    index, reason = result["operation_index"], result["reason"]
    if (
        result["schema_version"] != "media-forge.scene-recipe-failure@1"
        or result["blender_version"] != version
        or type(index) is not int or not 0 <= index < len(recipe.operations)
        or not isinstance(reason, str) or reason not in REASONS
    ):
        return fallback
    operation = recipe.operations[index]
    return (
        f"Operation {index + 1}/{len(recipe.operations)} "
        f"({operation.type}, object_id={operation.object_id}) failed: {REASONS[reason]}"
    )
