from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import SceneCreateRequest


def rig() -> dict[str, Any]:
    return {"type": "armature.create", "object_id": "rig", "name": "Rig", "bones": [
        {"bone_id": "root", "head": [0,0,0], "tail": [0,0,1]},
        {"bone_id": "arm", "head": [0,0,1], "tail": [1,0,1], "parent_bone_id": "root"}]}


def test_rig_matches_all_published_schemas() -> None:
    recipe = {"operations": [rig(), {"type": "skin.bind", "object_id": "rig",
        "bindings": [{"mesh_object_id": "mesh", "bone_id": "arm"}]},
        {"type": "pose.set", "object_id": "rig", "bones": [{"bone_id": "arm", "rotation_degrees": [45,0,0]}]}]}
    value = {"name": "Rigged robot", "recipe": recipe}
    SceneCreateRequest.model_validate(value)
    root = Path(__file__).parents[1] / "schemas"
    for filename, payload in [("scene-create-request.json", value),
        ("scene-edit-request.json", {"scene_id": "scene_"+"a"*32, "base_revision_id": "revision_"+"b"*32, "recipe": recipe}),
        ("scene-workflow-request.json", {"action": "create", **value})]:
        jsonschema.validate(payload, json.loads((root / filename).read_text()))


@pytest.mark.parametrize("failure", ["zero", "cycle", "duplicate", "count", "nan", "long_id", "script"])
def test_invalid_skeleton_rejected(failure: str) -> None:
    operation = rig()
    if failure == "zero": operation["bones"][0]["tail"] = [0,0,0]
    elif failure == "cycle": operation["bones"][0]["parent_bone_id"] = "arm"
    elif failure == "duplicate": operation["bones"][1]["bone_id"] = "root"
    elif failure == "count": operation["bones"] *= 65
    elif failure == "nan": operation["bones"][0]["head"][0] = float("nan")
    elif failure == "long_id": operation["bones"][0]["bone_id"] = "b"*49
    else: operation["python"] = "print(1)"
    with pytest.raises(ValidationError):
        SceneCreateRequest.model_validate({"name": "Bad", "recipe": {"operations": [operation]}})


@pytest.mark.parametrize("operation", [
    {"type": "skin.bind", "object_id": "rig", "bindings": []},
    {"type": "skin.bind", "object_id": "rig", "bindings": [{"mesh_object_id": "rig", "bone_id": "root"}]},
    {"type": "skin.bind", "object_id": "rig", "bindings": [{"mesh_object_id": "mesh", "bone_id": "root"}]*2},
    {"type": "pose.set", "object_id": "rig", "bones": [{"bone_id": "root", "rotation_degrees": [181,0,0]}]},
    {"type": "pose.set", "object_id": "rig", "bones": [{"bone_id": "root", "rotation_degrees": [0,0,0]}]*2},
])
def test_invalid_binding_pose_rejected(operation: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SceneCreateRequest.model_validate({"name": "Bad", "recipe": {"operations": [operation]}})
