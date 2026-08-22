from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ModelOperationAction(StrEnum):
    INSTALL = "install"
    REMOVE = "remove"


class ModelOperationState(StrEnum):
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLING = "installing"
    READY = "ready"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_MODEL_OPERATION_STATES = {
    ModelOperationState.READY,
    ModelOperationState.FAILED,
    ModelOperationState.CANCELED,
}


class ModelOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    model_id: str
    action: ModelOperationAction
    state: ModelOperationState
    bytes_total: int = Field(ge=0)
    bytes_done: int = Field(ge=0)
    error_code: str | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    created_at: str
    updated_at: str


class ModelOperationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
