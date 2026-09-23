"""Typed image-to-3D inputs and measured generation provenance."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scenes import SceneTag


class AdditionalGenerationView(BaseModel):
    model_config = ConfigDict(extra='forbid')
    direction: Literal['right', 'back', 'left']
    asset_id: str = Field(pattern=r'^asset_[0-9a-f]{32}$')


class GenerationViewCamera(BaseModel):
    """Shared turntable camera assumptions; does not calibrate arbitrary photos."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    fov_degrees: float = Field(default=20.0, ge=1, le=160, strict=True)
    distance: float = Field(default=3.1192049980163574, ge=.01, le=100, strict=True)
    elevation_degrees: float = Field(default=0.0, ge=-45, le=45, strict=True)
    mesh_scale: float = Field(default=1.0, ge=.01, le=100, strict=True)


class SceneFromImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    input_asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    engine: Literal["auto", "trellis_cpp", "pixal3d"] = "auto"
    # 既定は trellis.cpp までで終える。true のときだけ、その後ろに Pixal3D を
    # 足して同じシーンの次の版として保存する。engine=pixal3d を明示した場合は
    # すでに Pixal3D なので、この指定は段を増やさない。
    refine_with_pixal3d: bool = False
    resolution: Literal[512, 1024] = 1024
    seed: int = Field(default=42, ge=0, le=2**31 - 1, strict=True)
    local_only: Literal[True] = True
    tags: list[SceneTag] = Field(default_factory=lambda: ["g9"], max_length=32)
    collection: str = Field(default="experiment", min_length=1, max_length=120)
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")
    additional_views: list[AdditionalGenerationView] = Field(default_factory=list, max_length=3)
    view_camera: GenerationViewCamera | None = None

    @model_validator(mode='after')
    def distinct_views(self) -> SceneFromImageRequest:
        if len(set(self.input_asset_ids())) != len(self.input_asset_ids()):
            raise ValueError('each view must use a different image Asset')
        if len({v.direction for v in self.additional_views}) != len(self.additional_views):
            raise ValueError('each additional view must have a different direction')
        if self.additional_views and (self.engine == 'trellis_cpp' or self.refine_with_pixal3d or self.resolution != 1024):
            raise ValueError('multiple views require Pixal3D at 1024, without the single-image refinement chain')
        if not self.additional_views and self.view_camera is not None:
            raise ValueError('view_camera requires additional views')
        return self

    def ordered_views(self) -> list[tuple[str, str]]:
        by_direction = {v.direction: v.asset_id for v in self.additional_views}
        return [('front', self.input_asset_id), *[(d, by_direction[d]) for d in ('right', 'back', 'left') if d in by_direction]]

    def input_asset_ids(self) -> list[str]:
        return [asset_id for _, asset_id in self.ordered_views()]


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


class GenerationViewFacts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    direction: Literal['front', 'right', 'back', 'left']
    asset_id: str = Field(pattern=r'^asset_[0-9a-f]{32}$')
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    pixels_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class MultiviewExecutionFacts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    backend: Literal['vulkan'] = 'vulkan'
    precision: Literal['q8_0_flows_f16_shared'] = 'q8_0_flows_f16_shared'
    receipt_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    prepared_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    camera: GenerationViewCamera
    views: list[GenerationViewFacts] = Field(min_length=2, max_length=4)


class GenerationFacts(BaseModel):
    """Worker facts plus identities verified by the core before execution."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_./-]+$")
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    weights_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str = Field(min_length=1, max_length=256)
    runtime_adapter: Literal["native.trellis-cpp", "pixal3d", "native.pixal3d-multiview"]
    runtime_version: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._+-]+$")
    seed: int = Field(ge=0, le=2**31 - 1, strict=True)
    resolution: Literal[512, 1024]
    elapsed_sec: float = Field(ge=0, le=86400)
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution: GenerationExecutionFacts | None = None
    multiview: MultiviewExecutionFacts | None = None
