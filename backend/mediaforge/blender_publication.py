"""Private, bounded identities for durable Blender runtime publication."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RuntimeID = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Generation = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


class PublicationIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    runtime_id: RuntimeID
    version: Annotated[str, Field(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")]
    action: Literal["install", "update", "repair"]
    archive_sha256: Digest
    executable_sha256: Digest
    previous_active_runtime_id: RuntimeID | None
    previous_registration_sha256: Digest | None
    previous_executable_sha256: Digest | None
    recovered_directory: bool
    generation: Generation | None = None
    previous_generation: Generation | None = None

    @model_validator(mode="after")
    def previous_runtime_required(self) -> PublicationIdentity:
        if (self.action == "repair" or self.recovered_directory) and self.previous_executable_sha256 is None:
            raise ValueError("Existing runtime publication requires its previous executable identity")
        if self.action == "repair" and self.generation is not None and self.generation == self.previous_generation:
            raise ValueError("Repair publication requires a new generation")
        return self


class PublicationJournal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    phase: Literal["committing", "committed", "recovery_required"]
    identity: PublicationIdentity
    started_at: str = Field(min_length=20, max_length=40)
    completed_at: str | None = Field(default=None, min_length=20, max_length=40)
    stop_requests: list[Literal["cancel", "host_context_lost"]] = Field(default_factory=list, max_length=2)
