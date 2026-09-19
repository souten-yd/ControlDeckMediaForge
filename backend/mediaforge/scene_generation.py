"""Typed image-to-3D inputs and measured generation provenance."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .scenes import SceneTag


class SceneFromImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    input_asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    engine: Literal["auto", "trellis_cpp", "pixal3d"] = "auto"
    resolution: Literal[512, 1024] = 1024
    seed: int = Field(default=42, ge=0, le=2**31 - 1, strict=True)
    local_only: Literal[True] = True
    tags: list[SceneTag] = Field(default_factory=lambda: ["g9"], max_length=32)
    collection: str = Field(default="experiment", min_length=1, max_length=120)
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")


class GenerationExecutionFacts(BaseModel):
    """Additive record of explicit Pixal backend and CPU preprocessing identity."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    backend: Literal["vulkan"]
    precision: Literal["float32"]
    descriptor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prepared_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preprocessing_backend: Literal["cpu"]
    preprocessing_precision: Literal["float32"]
    preprocessing_elapsed_sec: float = Field(ge=0, le=86400)


class GenerationFacts(BaseModel):
    """Worker facts plus identities verified by the core before execution."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_./-]+$")
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    weights_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str = Field(min_length=1, max_length=256)
    runtime_adapter: Literal["native.trellis-cpp", "pixal3d"]
    runtime_version: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._+-]+$")
    seed: int = Field(ge=0, le=2**31 - 1, strict=True)
    resolution: Literal[512, 1024]
    elapsed_sec: float = Field(ge=0, le=86400)
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution: GenerationExecutionFacts | None = None
