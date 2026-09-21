"""rig.auto は「測って骨を置く」を型の中に閉じる。

座標を書くのは操作する側ではなくこちらなので、受けるのは何を測るかだけである。
並びの組み立ても 1 か所に置く。画面と MCP で別々に組むと、どちらかが weld を
落として「重みが 1 つも付かない」で止まる。
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import SceneCreateRequest, SceneRecipe
from mediaforge.scene_rig import SceneRigRequest
from mediaforge.scene_workspace import SceneWorkspace

ROOT = Path(__file__).parents[1]


def operation(**changes: object) -> dict[str, object]:
    value = {"type": "rig.auto", "object_id": "generated_0", "rig_object_id": "rig",
             "name": "Auto rig", "clip_id": "walk"}
    value.update(changes)
    return value


def test_auto_rig_matches_all_published_schemas() -> None:
    recipe = {"operations": [
        {"type": "mesh.weld", "object_id": "generated_0", "distance_m": 0.00001},
        {"type": "mesh.decimate", "object_id": "generated_0", "ratio": 0.6, "min_faces": 20000},
        operation()]}
    value = {"name": "Rigged robot", "recipe": recipe}
    SceneCreateRequest.model_validate(value)
    for filename, payload in [
        ("scene-create-request.json", value),
        ("scene-edit-request.json", {"scene_id": "scene_" + "a" * 32,
                                     "base_revision_id": "revision_" + "b" * 32, "recipe": recipe}),
        ("scene-workflow-request.json", {"action": "create", **value}),
    ]:
        jsonschema.validate(payload, json.loads((ROOT / "schemas" / filename).read_text()))


@pytest.mark.parametrize("failure", ["same_object", "script", "clip_case", "fps", "frames"])
def test_invalid_auto_rig_rejected(failure: str) -> None:
    value = operation()
    if failure == "same_object":
        # armature を自分のメッシュへ被せると、測った相手が消える。
        value["rig_object_id"] = "generated_0"
    elif failure == "script":
        value["python"] = "print(1)"
    elif failure == "clip_case":
        value["clip_id"] = "Walk"
    elif failure == "fps":
        value["fps"] = 0
    else:
        value["frame_count"] = 1
    with pytest.raises(ValidationError):
        SceneCreateRequest.model_validate({"name": "Bad", "recipe": {"operations": [value]}})


def test_the_rig_sequence_is_built_in_one_place() -> None:
    recipe = SceneWorkspace.rig_recipe(
        "generated_0", "rig", "Auto rig", "walk", 0.6, 0.00001, 20000, 24, 24)
    SceneRecipe.model_validate(recipe)
    # 繋ぐ→落とす→測って組む。glTF は継ぎ目で頂点を割るので、weld が先に
    # 来ないと bone heat が 1 頂点も解けない。
    assert [item["type"] for item in recipe["operations"]] == [
        "mesh.weld", "mesh.decimate", "rig.auto"]
    # 既に軽いモデルには落とす手を挟まない。繋ぐのは常に要る。
    light = SceneWorkspace.rig_recipe(
        "generated_0", "rig", "Auto rig", None, None, 0.00001, 2000, 24, 24)
    SceneRecipe.model_validate(light)
    assert [item["type"] for item in light["operations"]] == ["mesh.weld", "rig.auto"]
    assert "clip_id" not in light["operations"][-1]


def test_the_tool_input_stays_flat() -> None:
    """道具の schema はモデルの制約付きデコードへそのまま渡る。

    入れ子を深くすると文法が膨らみ、tool を 1 つ有効にしただけでモデルが
    使えなくなる事故が実際に起きている。この道具が受けるのは平たい値だけ。
    """
    schema = json.loads((ROOT / "schemas/scene-rig-request.json").read_text())
    assert schema["additionalProperties"] is False
    assert "$defs" not in schema
    for name, field in schema["properties"].items():
        kinds = {field.get("type")} | {
            option.get("type") for option in field.get("anyOf", []) if isinstance(option, dict)
        }
        assert not kinds & {"object", "array"}, f"{name} is not a flat value"
    value = SceneRigRequest.model_validate(
        {"scene_id": "scene_" + "a" * 32, "base_revision_id": "revision_" + "b" * 32})
    jsonschema.validate(value.model_dump(), schema)
    # 生成した 3D の既定の ID と、歩かせる既定がそのまま使える。
    assert value.object_id == "generated_0" and value.clip_id == "walk" and value.ratio == 0.6
