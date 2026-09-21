"""Report what a typed rig actually is, so a clip can be written for it.

`animation.clip` は最初から任意のキーフレーム列を受ける（骨ごとに最大 256 キー、
XYZ 各 ±180 度）。決まった型は無い。足りていなかったのは語彙ではなく、
**書く側が骨を見られないこと**だった。版が返していたのは件数だけで、骨の名前も
親子も、どの軸を回すとどちらへ曲がるのかも出ていなかった。

ここが出すのは測った事実だけである。特に `rotation_response` は、その骨の
ローカル軸まわりに正の回転を掛けたとき、先端が現実にどちらへ動くかを
実際に計算した単位ベクトルである。これがあると「前へ振る」「持ち上げる」を
軸の当て推量なしに書ける。手で骨を入れたときに何度も外したのがここだった。

骨はリグあたり 128 本までなので、mesh_geometry のような量の上限は要らない。
"""

from __future__ import annotations

import math
from typing import Any

# 応答を測る角度。小さすぎると丸めに埋もれ、大きすぎると回転の非線形が乗る。
PROBE_DEGREES = 5.0
MAX_REPORTED_BONES = 128


def _round3(vector: Any) -> list[float]:
    return [round(float(vector[0]), 4), round(float(vector[1]), 4), round(float(vector[2]), 4)]


def _unit(vector: Any) -> list[float]:
    length = math.sqrt(sum(float(value) ** 2 for value in vector))
    if length <= 1e-9:
        return [0.0, 0.0, 0.0]
    return [round(float(value) / length, 4) for value in vector]


def _rotation_response(bone: Any) -> dict[str, list[float]]:
    """ローカル軸まわりに正の回転を掛けたとき、先端がどちらへどれだけ動くか。

    返すのは単位ベクトルではない。**動く量まで含んだ**ベクトルで、長さ 1 が
    「その軸で動かせる最大」、長さ 0 が「この軸を回しても先端は動かない」を表す。

    単位化してはいけない。骨に沿う軸は先端をほとんど動かさないので、変位は
    丸め誤差しか残らない。それを単位化すると `[0, 0, -1]` のような、
    自信ありげで嘘の向きが出る（実測でそうなった）。読む側はそれを本物の
    「真下へ動く軸」と受け取ってしまう。長さを残せば、短いベクトルは
    そのまま「ここは効かない」と読める。

    回転行列を当てて測るだけで、姿勢は触らない。
    """
    from mathutils import Matrix

    rest = bone.matrix_local  # 骨のローカル軸 → シーン座標
    local_tail = rest.inverted() @ bone.tail_local
    # 長さ L の骨を角度 a 回すと、先端は最大 2L sin(a/2) 動く。これを 1 とする。
    reach = 2.0 * float(bone.length) * math.sin(math.radians(PROBE_DEGREES) / 2.0)
    response = {}
    for name, index in (("x", 0), ("y", 1), ("z", 2)):
        axis = [0.0, 0.0, 0.0]
        axis[index] = 1.0
        turned = Matrix.Rotation(math.radians(PROBE_DEGREES), 4, axis)
        moved = (rest @ (turned @ local_tail)) - bone.tail_local
        if reach <= 1e-9:
            response[name] = [0.0, 0.0, 0.0]
            continue
        scaled = [float(value) / reach for value in moved]
        length = math.sqrt(sum(value * value for value in scaled))
        # 丸めの残りを向きとして出さない。動かない軸は動かないと言う。
        if length < 0.02:
            response[name] = [0.0, 0.0, 0.0]
            continue
        response[name] = [round(value, 4) for value in scaled]
    return response


def facts(obj: Any) -> dict[str, Any] | None:
    """One typed rig, described well enough to animate without guessing."""
    if obj.type != "ARMATURE" or obj.get("media_forge_rig_schema") != 1:
        return None
    rig_object_id = obj.get("media_forge_id")
    if not isinstance(rig_object_id, str):
        return None
    bones = []
    for bone in list(obj.data.bones)[:MAX_REPORTED_BONES]:
        bones.append({
            "bone_id": bone.name,
            "parent_bone_id": bone.parent.name if bone.parent else None,
            "child_bone_ids": [child.name for child in bone.children][:16],
            "head_m": _round3(bone.head_local),
            "tail_m": _round3(bone.tail_local),
            "length_m": round(float(bone.length), 4),
            # ローカル軸そのもの。y は骨に沿う向きである。
            "axis_x": _unit(bone.x_axis) if hasattr(bone, "x_axis") else _unit(bone.matrix_local.col[0]),
            "axis_y": _unit(bone.y_axis) if hasattr(bone, "y_axis") else _unit(bone.matrix_local.col[1]),
            "axis_z": _unit(bone.z_axis) if hasattr(bone, "z_axis") else _unit(bone.matrix_local.col[2]),
            # 単位ベクトルではない。長さが「その軸を回したとき先端がどれだけ動くか」。
            "rotation_response": _rotation_response(bone),
        })
    return {
        "schema_version": "media-forge.scene-skeleton@1",
        "rig_object_id": rig_object_id,
        "bone_count": len(obj.data.bones),
        "reported_bones": len(bones),
        # 回す向きの基準。クリップの rotation_degrees はレスト姿勢に対する相対である。
        "rotation_probe_degrees": PROBE_DEGREES,
        "bones": bones,
    }
