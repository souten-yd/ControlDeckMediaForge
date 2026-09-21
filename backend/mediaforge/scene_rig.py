"""Fit a rig and a walk loop to a generated model, in one named request.

生成した 3D に骨を入れるには、決まった並びを守る必要がある。

1. `mesh.weld` — glTF は UV の継ぎ目で頂点を割る。繋がないと bone heat は
   1 頂点も解けない（実測: 11,466 個の破片に分かれていた）。繋ぐだけで
   頂点が半分近く減る。
2. `mesh.decimate` — `skin.bind_auto` には 5 万頂点・10 万面の上限がある。
   格子まとめで落とすと薄い板が升目に飲まれるので、辺の縮約で落とす。
3. `rig.auto` — 模型を測って骨を置き、縛り、歩行ループを付ける。

この並びを呼ぶ側が毎回組み立てると、どこかで 1 手落ちる。落ちたときの症状は
「骨が入らない」ではなく「重みが 1 つも付かない」なので、原因に辿り着きにくい。
ここが並びとして持つ。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .scene_recipes import BoneId, ObjectId


class SceneRigRequest(BaseModel):
    """Measure a generated model and fit a rig, skin weights and a walk loop to it.

    Point it at a scene revision holding one dense generated mesh. The model is
    welded (glTF splits vertices at UV seams, and bone heat solves nothing until
    they are joined), decimated to fit the bind limits, then measured: a root
    through the body, one bone per protrusion, and two per limb found in a
    horizontal band near the base. Limbs are counted from the shape, so six legs
    give a tripod gait and four give a diagonal one.

    Returns a detached Job; poll media.job.status. Success appends a revision
    whose preview GLB carries the skin and the clip. Nothing is overwritten.

    It needs a legged shape. A model with fewer than two limbs in that band
    fails rather than inventing bones, and rigging a character by hand stays
    media.scene.edit with armature.create.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.scene-rig@1"] = "media-forge.scene-rig@1"
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    base_revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    # 測る相手。生成した 3D は既定でこの ID で入る。
    object_id: ObjectId = "generated_0"
    rig_object_id: ObjectId = "rig"
    name: str = Field(default="Auto rig", min_length=1, max_length=120)
    # 残す面の割合。省くと落とさない（既に軽いモデル向け）。
    ratio: float | None = Field(default=0.6, gt=0.05, lt=1.0, allow_inf_nan=False)
    min_faces: int = Field(default=2000, ge=4, le=1_000_000, strict=True)
    weld_distance_m: float = Field(default=0.00001, gt=0.0, le=0.01, allow_inf_nan=False)
    # 歩行ループの ID。null にすると骨だけ入れて動きは付けない。
    clip_id: BoneId | None = "walk"
    fps: int = Field(default=24, ge=1, le=60, strict=True)
    frame_count: int = Field(default=24, ge=2, le=120, strict=True)
