"""Bounded saved-action observations, not animation quality certification."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnimationClipFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    object_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,63}$")
    clip_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,47}$")
    frame_start: float = Field(ge=-2_000_000, le=2_000_000, allow_inf_nan=False)
    frame_end: float = Field(ge=-2_000_000, le=2_000_000, allow_inf_nan=False)
    loop_requested: bool = Field(description="Saved action metadata, not proof of loop quality or engine playback settings.")

    @model_validator(mode="after")
    def ordered_range(self) -> "AnimationClipFact":
        if self.frame_end < self.frame_start:
            raise ValueError("animation frame range is reversed")
        return self


class AnimationSettingsFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["media-forge.animation-settings@1"]
    fps: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)
    clips: list[AnimationClipFact] = Field(max_length=32)
    unreported_actions: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def unique_clips(self) -> "AnimationSettingsFact":
        identities = {(clip.object_id, clip.clip_id) for clip in self.clips}
        if len(identities) != len(self.clips):
            raise ValueError("animation clip identities are duplicated")
        return self
