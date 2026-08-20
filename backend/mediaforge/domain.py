from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class AssetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")


class OutputOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["png", "webp", "jpeg"] = "png"
    count: int = Field(default=1, ge=1, le=8)


class QAOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deterministic: bool = True
    semantic: bool = False
    max_regeneration_attempts: int = Field(default=0, ge=0, le=3)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["image.generate", "image.edit", "media.inspect", "asset.pack"]
    intent: str = Field(min_length=1, max_length=8000)
    inputs: list[AssetInput] = Field(default_factory=list, max_length=16)
    profile: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9._-]{0,127}$")
    model_policy: Literal["auto", "fast", "balanced", "quality", "low_vram", "manual"] = "auto"
    model_id: str | None = Field(default=None, min_length=1, max_length=200)
    constraints: dict[str, Any] = Field(default_factory=dict)
    output: OutputOptions = Field(default_factory=OutputOptions)
    qa: QAOptions = Field(default_factory=QAOptions)
    local_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> "JobRequest":
        if self.model_policy == "manual" and not self.model_id:
            raise ValueError("manual model_policy requires model_id")
        if self.model_policy != "manual" and self.model_id is not None:
            raise ValueError("model_id is accepted only with manual model_policy")
        if self.operation == "image.generate" and self.inputs:
            raise ValueError("image.generate does not accept input assets")
        if self.operation == "image.edit" and not self.inputs:
            raise ValueError("image.edit requires at least one input asset")
        return self


class ErrorDetail(BaseModel):
    code: str
    message: str


class Job(BaseModel):
    id: str
    status: JobStatus
    phase: str | None = None
    progress: float = Field(ge=0, le=1)
    request: JobRequest
    asset_ids: list[str] = Field(default_factory=list)
    error: ErrorDetail | None = None
    created_at: str
    updated_at: str


class Provenance(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str
    asset_id: str
    parent_asset_ids: list[str]
    operation: str
    intent: str
    model_id: str
    model_version: str
    weights_hash: str
    license: str
    runtime_adapter: str
    runtime_version: str
    tool_versions: dict[str, str]
    seed: int
    parameters: dict[str, Any]
    reference_asset_hashes: dict[str, str]
    postprocessing: list[str]
    validation: list[dict[str, Any]]
    warnings: list[str]
    output_sha256: str
    created_at: str


class Asset(BaseModel):
    id: str
    job_id: str
    parent_asset_ids: list[str]
    mime_type: str
    width: int | None = None
    height: int | None = None
    size_bytes: int
    sha256: str
    suggested_filename: str
    provenance_id: str
    created_at: str
