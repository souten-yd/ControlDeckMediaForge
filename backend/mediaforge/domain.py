from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, model_validator


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
    format: Literal["png", "webp", "jpeg", "zip", "mp4", "webm"] = "png"
    count: int = Field(default=1, ge=1, le=8)


class QAOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deterministic: bool = True
    semantic: bool = False
    max_regeneration_attempts: int = Field(default=0, ge=0, le=3)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal[
        "image.generate",
        "image.edit",
        "video.generate",
        "video.edit",
        "media.inspect",
        "asset.pack",
    ]
    intent: str = Field(min_length=1, max_length=8000)
    inputs: list[AssetInput] = Field(default_factory=list, max_length=32)
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
        if self.operation == "video.generate" and len(self.inputs) > 8:
            raise ValueError("video.generate accepts at most eight key images")
        if self.operation == "video.edit" and not self.inputs:
            raise ValueError("video.edit requires at least one input asset")
        if self.operation == "video.edit" and len(self.inputs) > 8:
            raise ValueError("video.edit accepts at most eight input assets")
        if self.operation == "asset.pack" and not self.inputs:
            raise ValueError("asset.pack requires input assets")
        if self.operation != "asset.pack" and self.output.format == "zip":
            raise ValueError("zip output is accepted only by asset.pack")
        is_video = self.operation in {"video.generate", "video.edit"}
        if is_video and self.output.format not in {"mp4", "webm"}:
            raise ValueError("video operations require mp4 or webm output")
        if not is_video and self.output.format in {"mp4", "webm"}:
            raise ValueError("mp4 and webm output are accepted only by video operations")
        return self


# 保存済み行の読み出しは寛容にする。厳格な境界検査は API ingress（JobRequest）
# だけで行う。読み出しでも再検証すると、公開契約を加法的に広げた版が書いた行を
# 旧版が読めなくなり、1 行の不整合が一覧全体を 500 にする。実機で
# inputs 21 件 / output.format="zip" の行が jobs.list 全体を落としていた。
class StoredOutputOptions(OutputOptions):
    model_config = ConfigDict(extra="allow")
    format: str = "png"
    count: int = 1


class StoredQAOptions(QAOptions):
    model_config = ConfigDict(extra="allow")
    max_regeneration_attempts: int = 0


class StoredJobRequest(JobRequest):
    """保存済み job 行の寛容な読み出し表現。

    JobRequest の部分型なので既存の型注釈と consumer をそのまま使える。
    値の意味は変えず、受理範囲だけを広げる。実行経路は StoredJobRequest を
    受け取らない（Store.get_job が strict を要求する）。
    """

    model_config = ConfigDict(extra="allow")

    operation: str = "image.generate"
    intent: str = ""
    inputs: list[AssetInput] = Field(default_factory=list)
    profile: str | None = None
    model_policy: str = "auto"
    model_id: str | None = None
    output: StoredOutputOptions = Field(default_factory=StoredOutputOptions)
    qa: StoredQAOptions = Field(default_factory=StoredQAOptions)
    local_only: bool = True

    @model_validator(mode="after")
    def validate_policy(self) -> "StoredJobRequest":
        # 保存済みの行を再検証しない。ingress で一度検証済みである。
        return self


class ErrorDetail(BaseModel):
    code: str
    message: str


class Job(BaseModel):
    id: str
    status: JobStatus
    phase: str | None = None
    progress: float = Field(ge=0, le=1)
    # SerializeAsAny: StoredJobRequest で読んだ行を宣言型で切り詰めない。
    # 未知フィールドを黙って落とすと、新しい版が書いた記録を古い版が
    # 静かに破壊してしまう。
    request: SerializeAsAny[JobRequest | StoredJobRequest]
    asset_ids: list[str] = Field(default_factory=list)
    error: ErrorDetail | None = None
    # 現在の版で request を厳格に読めなかった行は degraded として残す。
    # 黙って一覧から消さない。
    record_state: Literal["ok", "degraded"] = "ok"
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
    mime_type: Literal[
        "image/png", "image/webp", "image/jpeg", "video/mp4", "video/webm", "application/zip"
    ]
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = Field(default=None, gt=0)
    frame_rate: float | None = Field(default=None, gt=0)
    size_bytes: int
    sha256: str
    suggested_filename: str
    provenance_id: str
    created_at: str
