"""Immutable revision inputs for bounded local texture baking."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scene_recipes import ObjectId


class HighBakeSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    object_id: ObjectId
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SceneBakeRequest(BaseModel):
    """Bake bounded tangent-normal or target-only AO maps from immutable Blender revisions.

    Supply the low scene/revision, stable mesh ID, current cage geometry hash and
    a UV map. Normal baking requires a separately identified high mesh/revision at
    the same Blender runtime. Uses CPU only, frame 0, 16 samples. Returns a detached
    Job; poll media.job.status for image Assets and settings/source-hash evidence.
    No scene head is changed and no map is automatically applied. Assess fixed clay
    shape evidence before final surface work; baking is not visual/UV/rig approval.
    """
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    object_id: ObjectId
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    high_source: HighBakeSource | None = None
    uv_map: str = Field(default="UVMap", min_length=1, max_length=64, pattern=r"^[^\x00-\x1f/\\]+$")
    channels: list[Literal["normal", "ao"]] = Field(default_factory=lambda:["normal", "ao"], min_length=1, max_length=2)
    resolution: Literal[256, 512, 1024] = 512
    margin_px: int = Field(default=8, ge=1, le=32, strict=True)
    cage_extrusion_m: float = Field(default=0.02, ge=0, le=1, allow_inf_nan=False)
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")

    @model_validator(mode="after")
    def coherent_channels(self) -> "SceneBakeRequest":
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("bake channels must be unique")
        if "normal" in self.channels and self.high_source is None:
            raise ValueError("normal baking requires an explicit high source")
        return self

    def worker_spec(self) -> dict:
        """No scene IDs, paths or credentials enter the fixed worker specification."""
        return self.model_dump(mode="json",include={"object_id","geometry_sha256","uv_map","channels",
            "resolution","margin_px","cage_extrusion_m"}) | {
                "high_object_id":self.high_source.object_id if self.high_source else None,
                "high_geometry_sha256":self.high_source.geometry_sha256 if self.high_source else None}
