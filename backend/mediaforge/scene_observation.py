"""Bounded, revision-pinned observation contracts; no Blender/core imports."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# scene_recipes と同じ骨/クリップ ID の形。別々に書くと片方だけ緩む。
BoneId = Annotated[str, Field(min_length=1, max_length=48, pattern=r"^[a-z][a-z0-9._-]*$")]
Coordinate = Annotated[float, Field(ge=-10_000, le=10_000, allow_inf_nan=False, strict=True)]
ObservationView = Literal["front", "side", "back", "three-quarter"]


class ObservationSpec(BaseModel):
    """Fixed world-space framing: Z up, front viewed from -Y, side from +X.

    Reuse this exact spec for before/after comparison. No automatic fitting.
    CPU Cycles, fixed lighting, 16 samples and Standard color transform.

    Name a clip_id to pose the rig with that clip and render the listed frames;
    without one the scene renders at its rest pose. Rendering is CPU path
    tracing, so views x frames is capped: ask for the moments that decide the
    question, not a filmstrip.
    """

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["media-forge.scene-observation@1"] = "media-forge.scene-observation@1"
    center: tuple[Coordinate, Coordinate, Coordinate]
    span_m: float = Field(gt=0.001, le=10_000, allow_inf_nan=False, strict=True)
    views: list[ObservationView] = Field(
        default_factory=lambda: ["front", "side", "back", "three-quarter"], min_length=1, max_length=4
    )
    mode: Literal["material", "clay", "silhouette", "object_id"] = "clay"
    resolution: Literal[256, 512] = 512
    # 動いている姿を見るための指定。既定（どちらも省く）は今までどおり
    # レスト姿勢の 1 枚である。
    clip_id: BoneId | None = None
    frames: list[Annotated[int, Field(ge=0, le=600, strict=True)]] | None = Field(
        default=None, min_length=1, max_length=8)

    @model_validator(mode="after")
    def unique_views(self) -> "ObservationSpec":
        if len(self.views) != len(set(self.views)):
            raise ValueError("observation views must be unique")
        if self.frames is not None:
            if self.clip_id is None:
                # クリップを言わずにフレームだけ動かしても、姿勢は変わらない。
                # 「動いて見えない」の原因を探させないために、ここで断る。
                raise ValueError("frames need a clip_id to pose")
            if len(self.frames) != len(set(self.frames)) or self.frames != sorted(self.frames):
                raise ValueError("observation frames must be unique and increasing")
        if self.clip_id is not None and self.frames is None:
            raise ValueError("a clip_id needs the frames to render")
        # CPU のパストレースなので、1 回の観察で描く枚数に歯止めを置く。
        if len(self.views) * len(self.frames or [0]) > 8:
            raise ValueError("views times frames exceeds the render budget of 8 images")
        return self

    def rendered_frames(self) -> list[int]:
        """What the worker must render: the listed frames, or the rest pose."""
        return list(self.frames) if self.frames is not None else [0]


class SceneObserveRequest(BaseModel):
    """Render an authorized immutable revision as ordinary image Assets.

    Historical revisions are valid. This operation never advances the scene head.
    Poll media.job.status; images are not a semantic quality approval.
    """

    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    observation: ObservationSpec
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")
