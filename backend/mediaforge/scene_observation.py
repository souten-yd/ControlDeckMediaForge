"""Bounded, revision-pinned observation contracts; no Blender/core imports."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Coordinate = Annotated[float, Field(ge=-10_000, le=10_000, allow_inf_nan=False, strict=True)]
ObservationView = Literal["front", "side", "back", "three-quarter"]


class ObservationSpec(BaseModel):
    """Fixed world-space framing: Z up, front viewed from -Y, side from +X.

    Reuse this exact spec for before/after comparison. No automatic fitting.
    CPU Cycles, frame 0, fixed lighting, 16 samples and Standard color transform.
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

    @model_validator(mode="after")
    def unique_views(self) -> "ObservationSpec":
        if len(self.views) != len(set(self.views)):
            raise ValueError("observation views must be unique")
        return self


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
