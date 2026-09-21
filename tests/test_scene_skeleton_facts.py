"""クリップを書く側が骨を見られるようにする facts。

`animation.clip` は最初から任意のキーフレーム列を受ける（骨ごとに最大 256 キー、
XYZ 各 ±180 度）。決まったパターンの集合ではない。足りていなかったのは語彙では
なく、版が件数しか返しておらず、骨の名前も回す向きも分からなかったことである。
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import AnimationClip
from mediaforge.scene_skeleton import validate_skeleton_facts


def bone(bone_id: str, **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "bone_id": bone_id, "head_m": [0.0, 0.0, 0.0], "tail_m": [0.0, 0.0, 1.0],
        "length_m": 1.0, "axis_x": [1.0, 0.0, 0.0], "axis_y": [0.0, 0.0, 1.0],
        "axis_z": [0.0, -1.0, 0.0],
        # 骨に沿う軸（y）を回しても先端は動かない。ゼロが正しい答えである。
        # 単位化して丸め誤差から向きを捏造しないことを、ここで固定する。
        "rotation_response": {"x": [0.0, -1.0, 0.0], "y": [0.0, 0.0, 0.0], "z": [1.0, 0.0, 0.0]},
    }
    value.update(changes)
    return value


def skeleton(*bones: dict[str, object], **changes: object) -> list[dict[str, object]]:
    value: dict[str, object] = {
        "schema_version": "media-forge.scene-skeleton@1", "rig_object_id": "rig",
        "bone_count": len(bones), "reported_bones": len(bones),
        "rotation_probe_degrees": 5.0, "bones": list(bones),
    }
    value.update(changes)
    return [value]


def test_a_clip_can_be_written_from_what_the_facts_state() -> None:
    facts = validate_skeleton_facts(
        skeleton(bone("root", child_bone_ids=["leg1_upper"]),
                 bone("leg1_upper", parent_bone_id="root",
                      rotation_response={"x": [0.0, 1.0, 0.0], "y": [0.0, 0.0, 0.0],
                                         "z": [0.0, 0.0, 1.0]})),
        ["rig"],
    )
    reported = {item["bone_id"]: item for item in facts[0]["bones"]}
    # 「前（+Y）へ振る」のに回す軸は、応答が +Y を向いている軸である。当て推量は要らない。
    forward = next(
        axis for axis, direction in reported["leg1_upper"]["rotation_response"].items()
        if direction[1] > 0.5
    )
    assert forward == "x"
    clip = AnimationClip.model_validate({
        "type": "animation.clip", "object_id": "rig", "clip_id": "stride", "name": "stride",
        "fps": 24, "frame_count": 12, "loop": True,
        "tracks": [{"bone_id": "leg1_upper", "keys": [
            {"frame": 0, "rotation_degrees": [0.0, 0.0, 0.0]},
            {"frame": 6, "rotation_degrees": [20.0, 0.0, 0.0]},
            {"frame": 12, "rotation_degrees": [0.0, 0.0, 0.0]}]}],
    })
    assert clip.tracks[0].bone_id in reported


def test_the_clip_vocabulary_is_not_a_fixed_set_of_patterns() -> None:
    """型が縛るのは量と範囲だけで、動きの形は縛っていない。"""
    keys = [{"frame": index, "rotation_degrees": [
        round(40 * math.sin(index / 9), 2), round(-25 * math.cos(index / 5), 2),
        round(12 * math.sin(index / 3), 2)]} for index in range(0, 180, 2)]
    keys[0]["rotation_degrees"] = [0.0, 0.0, 0.0]
    keys.append({"frame": 180, "rotation_degrees": [0.0, 0.0, 0.0]})
    clip = AnimationClip.model_validate({
        "type": "animation.clip", "object_id": "rig", "clip_id": "flail", "name": "flail",
        "fps": 30, "frame_count": 180, "loop": True,
        "tracks": [{"bone_id": "leg1_upper", "keys": keys}],
    })
    assert len(clip.tracks[0].keys) == 91 and clip.frame_count == 180


@pytest.mark.parametrize(
    "failure",
    ["unknown_parent", "unknown_child", "repeat", "count", "not_a_direction", "self_parent",
     "response_too_long"],
)
def test_worker_skeleton_facts_are_not_trusted(failure: str) -> None:
    if failure == "unknown_parent":
        value = skeleton(bone("root"), bone("arm", parent_bone_id="missing"))
    elif failure == "unknown_child":
        value = skeleton(bone("root", child_bone_ids=["missing"]))
    elif failure == "repeat":
        value = skeleton(bone("root"), bone("root"))
    elif failure == "count":
        value = skeleton(bone("root"), reported_bones=2)
    elif failure == "self_parent":
        value = skeleton(bone("root", parent_bone_id="root"))
    elif failure == "response_too_long":
        # 応答は 0〜1。最大を超える動きは測り間違いである。
        value = skeleton(bone("root", rotation_response={
            "x": [2.0, 0.0, 0.0], "y": [0.0, 0.0, 0.0], "z": [1.0, 0.0, 0.0]}))
    else:
        value = skeleton(bone("root", axis_x=[3.0, 0.0, 0.0]))
    with pytest.raises((ValidationError, ValueError)):
        validate_skeleton_facts(value, ["rig"])


def test_an_axis_that_does_not_move_the_tip_says_so() -> None:
    """骨に沿う軸は先端を動かさない。長さを残すので「効かない」と読める。

    単位化してしまうと、丸め誤差しか無い軸から自信ありげな向きが出る。
    実測でそれが起きた（骨に沿う軸が [0, 0, -1] と出た）。
    """
    facts = validate_skeleton_facts(skeleton(bone("root", rotation_response={
        "x": [0.0, -0.98, 0.0], "y": [0.0, 0.0, 0.0], "z": [0.97, 0.0, 0.0]})), ["rig"])
    response = facts[0]["bones"][0]["rotation_response"]
    strength = {axis: sum(value * value for value in direction) ** 0.5
                for axis, direction in response.items()}
    assert strength["y"] == 0.0
    assert strength["x"] > 0.9 and strength["z"] > 0.9


def test_skeleton_facts_must_name_a_known_object() -> None:
    with pytest.raises(ValueError):
        validate_skeleton_facts(skeleton(bone("root")), ["generated_0"])
