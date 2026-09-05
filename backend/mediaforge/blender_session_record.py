"""Durable private records for one isolated Blender GUI session."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BlenderSessionState(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    STARTING = "starting"
    READY = "ready"
    SAVING = "saving"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


ACTIVE_BLENDER_SESSION_STATES = {
    BlenderSessionState.QUEUED,
    BlenderSessionState.PREPARING,
    BlenderSessionState.STARTING,
    BlenderSessionState.READY,
    BlenderSessionState.SAVING,
    BlenderSessionState.STOPPING,
}

TERMINAL_BLENDER_SESSION_STATES = {
    BlenderSessionState.STOPPED,
    BlenderSessionState.FAILED,
    BlenderSessionState.INTERRUPTED,
}


class BlenderWebSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "media-forge.blender-web-session@1"
    id: str = Field(pattern=r"^blendersession_[0-9a-f]{32}$")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    working_id: str | None = Field(default=None, pattern=r"^working_[0-9a-f]{32}$")
    runtime_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$")
    runtime_version: str | None = Field(default=None, pattern=r"^[0-9]+(?:\.[0-9]+){1,3}$")
    web_pack_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$")
    web_pack_version: str = Field(pattern=r"^[0-9]+(?:\.[0-9]+){1,3}$")
    unit_id: str = Field(pattern=r"^mediaforge-blender-[0-9a-f]{32}\.service$")
    state: BlenderSessionState
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = Field(default=None, max_length=300)
    result: dict | None = None
    created_at: str
    updated_at: str
