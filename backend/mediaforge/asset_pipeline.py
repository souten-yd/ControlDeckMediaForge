"""Run image -> 3D -> rig -> export as one named chain, or one step at a time.

道具は既に全部ある。足りないのは**順番と、その順番が守っている理由**である。
個別に呼べば好きな段だけ走らせられるが、繋ぐ側が毎回順番を組み立てると
どこかで 1 手落ちる。落ちたときの症状は分かりにくい（骨入れで `mesh.weld` を
落とすと「骨が入らない」ではなく「重みが 1 つも付かない」で止まる）。

ここは段の並びだけを持つ。**実行は既存の job をそのまま使う。**新しい実行系は
作らない。1 段ごとに job を 1 つ出し、その job_id を覚えておくだけである。

`mode` が 2 つある。

- `auto`    次の段は、前の段が終わっていれば自動で出す
- `confirm` 次の段は `approve` が来るまで出さない（段ごとに人が見る）

進むのは `status` を呼んだときである。裏で走り続ける番人は置かない。置くと
再起動やクラッシュのたびに「誰が続きをやるのか」を決めることになり、job の
所有者が二重になる。呼ばれたときに 1 歩進める形なら、状態は表 1 つで足りる。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scene_recipes import BoneId, ObjectId

# 段の名前。並びはこの順で固定である。
STAGES: tuple[str, ...] = ("image", "model", "rig", "export")
StageName = Literal["image", "model", "rig", "export"]
StageState = Literal["pending", "awaiting_approval", "running", "succeeded", "failed", "skipped"]


class AssetPipelineRequest(BaseModel):
    """Take a prompt or an image all the way to a rigged, exported game asset.

    Runs the steps in the order that works: generate the image, reconstruct the
    3D, weld and reduce and fit a rig by measuring the model, then export a GLB.
    Each step is an ordinary Job you can also run on its own; this only keeps
    the order and remembers where it is.

    mode="confirm" stops before each step so you can look at what the last one
    produced and approve or stop. mode="auto" runs straight through. Either way
    the pipeline only advances when you poll it, so nothing happens unwatched.

    Give a prompt to generate the starting image, or an image_asset_id to start
    from one you already have — exactly one of the two.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.asset-pipeline@1"] = "media-forge.asset-pipeline@1"
    name: str = Field(min_length=1, max_length=120)
    mode: Literal["auto", "confirm"] = "confirm"

    # 出発点。どちらか一方だけ。
    prompt: str | None = Field(default=None, min_length=1, max_length=2000)
    image_asset_id: str | None = Field(default=None, pattern=r"^asset_[0-9a-f]{32}$")
    width: int = Field(default=1024, ge=256, le=2048, strict=True)
    height: int = Field(default=1024, ge=256, le=2048, strict=True)

    # 3D 化。
    resolution: Literal[512, 1024] = 1024
    refine_with_pixal3d: bool = Field(default=False, strict=True)
    seed: int = Field(default=42, ge=0, le=2**31 - 1, strict=True)

    # 骨入れ。rig=false なら段ごと飛ばす。
    rig: bool = Field(default=True, strict=True)
    rig_ratio: float = Field(default=0.6, gt=0.05, lt=1.0, allow_inf_nan=False)
    rig_object_id: ObjectId = "generated_0"
    clip_id: BoneId | None = "walk"

    # 書き出し。
    export: bool = Field(default=True, strict=True)
    export_format: Literal["glb", "blend"] = "glb"

    @model_validator(mode="after")
    def one_starting_point(self) -> "AssetPipelineRequest":
        if (self.prompt is None) == (self.image_asset_id is None):
            raise ValueError("give exactly one of prompt or image_asset_id")
        return self

    def planned_stages(self) -> list[str]:
        """Which steps this run will actually take."""
        stages = ["model"]
        if self.prompt is not None:
            stages.insert(0, "image")
        if self.rig:
            stages.append("rig")
        if self.export:
            stages.append("export")
        return stages


class PipelineStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: StageName
    state: StageState = "pending"
    # confirm のとき、人が「進めてよい」と言ったかどうか。これを持たないと、
    # 承認した直後の poll でまた承認待ちへ戻ってしまう。
    approved: bool = Field(default=False, strict=True)
    job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")
    asset_id: str | None = Field(default=None, pattern=r"^asset_[0-9a-f]{32}$")
    revision_id: str | None = Field(default=None, pattern=r"^revision_[0-9a-f]{32}$")
    # 失敗した理由は、呼んだ側が次に何をするかを決められる粒度で残す。
    error_code: str | None = Field(default=None, min_length=1, max_length=64)
    started_at: str | None = None
    finished_at: str | None = None


class AssetPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["media-forge.asset-pipeline-state@1"] = "media-forge.asset-pipeline-state@1"
    id: str = Field(pattern=r"^pipeline_[0-9a-f]{32}$")
    owner: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=120)
    mode: Literal["auto", "confirm"]
    request: dict[str, Any]
    stages: list[PipelineStage] = Field(min_length=1, max_length=4)
    scene_id: str | None = Field(default=None, pattern=r"^scene_[0-9a-f]{32}$")
    state: Literal["running", "awaiting_approval", "succeeded", "failed", "canceled"] = "running"
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def stages_follow_the_fixed_order(self) -> "AssetPipeline":
        names = [stage.name for stage in self.stages]
        if names != sorted(names, key=STAGES.index) or len(set(names)) != len(names):
            raise ValueError("pipeline stages are out of order")
        return self

    def current(self) -> PipelineStage | None:
        """The step the pipeline is on, or None when there is nothing left."""
        for stage in self.stages:
            if stage.state in {"pending", "awaiting_approval", "running"}:
                return stage
        return None

    def previous_of(self, stage: PipelineStage) -> PipelineStage | None:
        index = self.stages.index(stage)
        return self.stages[index - 1] if index > 0 else None


class AssetPipelineActionRequest(BaseModel):
    """Poll a pipeline, or tell it to go on or to stop.

    Polling is what moves it: nothing runs unwatched. "approve" releases the
    step a confirm-mode run is waiting on; "cancel" stops before the next step
    and leaves whatever is already running to finish on its own.
    """

    model_config = ConfigDict(extra="forbid")
    pipeline_id: str = Field(pattern=r"^pipeline_[0-9a-f]{32}$")
    action: Literal["status", "approve", "cancel"] = "status"
