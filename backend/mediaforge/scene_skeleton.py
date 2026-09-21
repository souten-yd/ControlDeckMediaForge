"""Bounded rig facts, so a clip can be written without guessing the skeleton.

`animation.clip` は最初から任意のキーフレーム列を受ける。決まったパターンの
集合ではない。足りていなかったのは語彙ではなく、書く側が骨を見られないこと
だった。版が返していたのは件数だけで、骨の名前も親子も、どの軸を回すと
どちらへ曲がるのかも出ていなかった。

`rotation_response` はその穴を埋める。骨のローカル軸まわりに正の回転を掛けた
とき、先端が現実にどちらへ動くかを worker が実際に計算した単位ベクトルである。
「前へ振る」「持ち上げる」を軸の当て推量なしに書ける。
"""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from .scene_recipes import BoneId, ObjectId, Vector3

# 単位ベクトルは丸めて届くので、長さの検査には幅を持たせる。ゼロは「その軸では
# 先端が動かない」を意味するので許す（骨に沿う軸がそれになる）。
_UNIT_TOLERANCE = 0.02


def _is_unit_or_zero(vector: tuple[float, float, float]) -> bool:
    length = math.sqrt(sum(value * value for value in vector))
    return length <= _UNIT_TOLERANCE or abs(length - 1.0) <= _UNIT_TOLERANCE


def _is_bounded(vector: tuple[float, float, float]) -> bool:
    """0（動かない）から 1（最大）までの長さ。丸めのぶんだけ幅を持たせる。"""
    length = math.sqrt(sum(value * value for value in vector))
    return length <= 1.0 + _UNIT_TOLERANCE


class RotationResponse(BaseModel):
    """How far and which way the bone tip moves for a positive turn about each local axis.

    単位ベクトルではない。長さ 1 が「その軸で動かせる最大」、0 が「この軸を
    回しても先端は動かない」。骨に沿う軸は 0 になる。

    長さを捨てて単位化すると、丸め誤差しか残っていない軸から
    `[0, 0, -1]` のような自信ありげで嘘の向きが出る（実測でそうなった）。
    読む側はそれを本物の「真下へ動く軸」と受け取ってしまう。
    """

    model_config = ConfigDict(extra="forbid")
    x: Vector3
    y: Vector3
    z: Vector3

    @model_validator(mode="after")
    def bounded_directions(self) -> "RotationResponse":
        for axis in (self.x, self.y, self.z):
            if not _is_bounded(axis):
                raise ValueError("worker rotation response is out of range")
        return self


class BoneFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bone_id: BoneId
    parent_bone_id: BoneId | None = None
    child_bone_ids: list[BoneId] = Field(default_factory=list, max_length=16)
    head_m: Vector3
    tail_m: Vector3
    length_m: float = Field(gt=0, le=1000, allow_inf_nan=False)
    axis_x: Vector3
    axis_y: Vector3
    axis_z: Vector3
    rotation_response: RotationResponse

    @model_validator(mode="after")
    def unit_axes(self) -> "BoneFact":
        for axis in (self.axis_x, self.axis_y, self.axis_z):
            if not _is_unit_or_zero(axis):
                raise ValueError("worker bone axis is not a direction")
        if self.bone_id in self.child_bone_ids or self.bone_id == self.parent_bone_id:
            raise ValueError("worker bone hierarchy differs")
        return self


class SkeletonFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(pattern=r"^media-forge\.scene-skeleton@1$")
    rig_object_id: ObjectId
    bone_count: int = Field(ge=1, le=128, strict=True)
    reported_bones: int = Field(ge=1, le=128, strict=True)
    rotation_probe_degrees: float = Field(gt=0, le=45, allow_inf_nan=False)
    bones: list[BoneFact] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def consistent_hierarchy(self) -> "SkeletonFact":
        if len(self.bones) != self.reported_bones or self.reported_bones > self.bone_count:
            raise ValueError("worker bone counts differ")
        names = [bone.bone_id for bone in self.bones]
        if len(set(names)) != len(names):
            raise ValueError("worker bone IDs repeat")
        known = set(names)
        for bone in self.bones:
            if bone.parent_bone_id is not None and bone.parent_bone_id not in known:
                raise ValueError("worker bone parent is unknown")
            if not set(bone.child_bone_ids) <= known:
                raise ValueError("worker bone child is unknown")
        return self


SKELETON_FACTS = TypeAdapter(Annotated[list[SkeletonFact], Field(max_length=16)])


def validate_skeleton_facts(value: object, object_ids: list[str] | None = None) -> list[dict]:
    """Validate a bounded projection before storing or returning it."""
    facts = SKELETON_FACTS.validate_python(value)
    ids = [fact.rig_object_id for fact in facts]
    if len(set(ids)) != len(ids) or (object_ids is not None and not set(ids) <= set(object_ids)):
        raise ValueError("worker skeleton IDs differ")
    return [fact.model_dump(mode="json") for fact in facts]
