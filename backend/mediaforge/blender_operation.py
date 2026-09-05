from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BlenderRuntimeOperationAction(StrEnum):
    INSTALL = "install"
    UPDATE = "update"
    REPAIR = "repair"
    SWITCH = "switch"
    REMOVE = "remove"


class BlenderRuntimeOperationState(StrEnum):
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLING = "installing"
    PROBING = "probing"
    DELETING = "deleting"
    READY = "ready"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_BLENDER_RUNTIME_OPERATION_STATES = {
    BlenderRuntimeOperationState.READY,
    BlenderRuntimeOperationState.FAILED,
    BlenderRuntimeOperationState.CANCELED,
}


class BlenderRuntimeOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    runtime_id: str
    version: str
    action: BlenderRuntimeOperationAction
    state: BlenderRuntimeOperationState
    bytes_total: int = Field(ge=0)
    bytes_done: int = Field(ge=0)
    error_code: str | None = None
    error_message: str | None = None
    result: dict[str, Any] | None = None
    cancel_requested: bool = False
    created_at: str
    updated_at: str


class BlenderRuntimeOperationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
