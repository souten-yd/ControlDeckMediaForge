from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import SceneCreateRequest


def clip() -> dict[str, Any]:
    return {"type": "animation.clip", "object_id": "rig", "clip_id": "idle", "name": "Idle",
            "fps": 24, "frame_count": 48, "loop": True, "tracks": [{"bone_id": "head", "keys": [
                {"frame": 0, "rotation_degrees": [0,0,0]},
                {"frame": 24, "rotation_degrees": [10,0,0]},
                {"frame": 48, "rotation_degrees": [0,0,0]}]}]}


def test_clip_published_contracts() -> None:
    recipe = {"operations": [clip()]}
    value = {"name": "Animated robot", "recipe": recipe}
    SceneCreateRequest.model_validate(value)
    root = Path(__file__).parents[1] / "schemas"
    for filename, payload in [("scene-create-request.json", value),
        ("scene-edit-request.json", {"scene_id": "scene_"+"a"*32, "base_revision_id": "revision_"+"b"*32, "recipe": recipe}),
        ("scene-workflow-request.json", {"action": "create", **value})]:
        jsonschema.validate(payload, json.loads((root/filename).read_text()))


@pytest.mark.parametrize("failure", ["fps_zero", "fps_bool", "frames", "duration", "nan", "angle", "duplicate_bone",
                                     "unordered", "first", "last", "loop", "many_keys", "script"])
def test_invalid_clip_rejected(failure: str) -> None:
    op = clip()
    keys = op["tracks"][0]["keys"]
    if failure == "fps_zero": op["fps"] = 0
    elif failure == "fps_bool": op["fps"] = True
    elif failure == "frames": op["frame_count"] = 601
    elif failure == "duration": op.update(fps=1, frame_count=121)
    elif failure == "nan": keys[1]["rotation_degrees"][0] = float("nan")
    elif failure == "angle": keys[1]["rotation_degrees"][0] = 181
    elif failure == "duplicate_bone": op["tracks"] *= 2
    elif failure == "unordered": keys[1]["frame"] = 0
    elif failure == "first": keys[0]["frame"] = 1
    elif failure == "last": keys[-1]["frame"] = 47
    elif failure == "loop": keys[-1]["rotation_degrees"][0] = 1
    elif failure == "many_keys": op["tracks"][0]["keys"] *= 100
    else: op["script"] = "print(1)"
    with pytest.raises(ValidationError):
        SceneCreateRequest.model_validate({"name": "Bad", "recipe": {"operations": [op]}})
