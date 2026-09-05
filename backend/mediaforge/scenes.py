"""Owner-scoped immutable scene documents and revision records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
import uuid
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from .store import Store


SCENE_RECORD_BYTES = 128 * 1024


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SceneError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


SceneTag = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[^\x00-\x1f/\\]+$")]


class SceneDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9._-]*$")
    asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SceneValidationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validator: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    status: Literal["passed", "failed", "not_checked"]
    facts: dict[str, Any] = Field(default_factory=dict)


class SceneRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.scene-revision@1"] = "media-forge.scene-revision@1"
    id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    sequence: int = Field(ge=1, le=1_000_000)
    parent_revision_id: str | None = Field(default=None, pattern=r"^revision_[0-9a-f]{32}$")
    source_asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    preview_asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    dependencies: list[SceneDependency] = Field(default_factory=list, max_length=128)
    runtime_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    runtime_version: str = Field(min_length=1, max_length=64, pattern=r"^[0-9]+(?:\.[0-9]+){1,3}$")
    validation: list[SceneValidationCheck] = Field(min_length=2, max_length=64)
    created_at: str

    @model_validator(mode="after")
    def validate_identity_and_checks(self) -> "SceneRevision":
        if self.source_asset_id == self.preview_asset_id:
            raise ValueError("source and preview assets must differ")
        keys = [(item.role, item.asset_id) for item in self.dependencies]
        if len(keys) != len(set(keys)):
            raise ValueError("scene dependencies must be unique")
        if any(
            item.asset_id in {self.source_asset_id, self.preview_asset_id}
            for item in self.dependencies
        ):
            raise ValueError("source and preview cannot be repeated as dependencies")
        statuses = {item.validator: item.status for item in self.validation}
        if statuses.get("blender.scene") != "passed" or statuses.get("glb.structure") != "passed":
            raise ValueError("scene revision requires passed Blender and GLB validation")
        if any(item.status == "failed" for item in self.validation):
            raise ValueError("failed validation cannot become an immutable revision")
        if len(self.model_dump_json().encode("utf-8")) > SCENE_RECORD_BYTES:
            raise ValueError("scene revision record exceeds its byte bound")
        return self


class SceneDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.scene-document@1"] = "media-forge.scene-document@1"
    id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    name: str = Field(min_length=1, max_length=120)
    tags: list[SceneTag] = Field(default_factory=list, max_length=32)
    collection: str | None = Field(default=None, min_length=1, max_length=120)
    unit_meters: Literal[1.0] = 1.0
    current_revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    revision_count: int = Field(ge=1, le=1_000_000)
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def normalize_unique_tags(self) -> "SceneDocument":
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("scene tags must be unique")
        return self


class SceneRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    preview_asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    dependencies: list[SceneDependency] = Field(default_factory=list, max_length=128)
    runtime_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    runtime_version: str = Field(min_length=1, max_length=64, pattern=r"^[0-9]+(?:\.[0-9]+){1,3}$")
    validation: list[SceneValidationCheck] = Field(min_length=2, max_length=64)


class SceneCatalog:
    """Create and advance owner-scoped scene heads without exposing storage paths."""

    def __init__(self, store: "Store"):
        self.store = store

    @staticmethod
    def _owner(value: str) -> str:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 256
            or any(ord(char) < 32 for char in value)
        ):
            raise SceneError("scene_owner_invalid", "scene owner is invalid")
        return value

    def create(
        self,
        owner: str,
        *,
        name: str,
        revision: SceneRevisionInput,
        tags: list[str] | None = None,
        collection: str | None = None,
    ) -> tuple[SceneDocument, SceneRevision]:
        owner = self._owner(owner)
        now = _utc_now()
        scene_id = f"scene_{uuid.uuid4().hex}"
        revision_record = SceneRevision(
            id=f"revision_{uuid.uuid4().hex}",
            scene_id=scene_id,
            sequence=1,
            parent_revision_id=None,
            created_at=now,
            **revision.model_dump(),
        )
        document = SceneDocument(
            id=scene_id,
            name=name.strip(),
            tags=tags or [],
            collection=collection,
            current_revision_id=revision_record.id,
            revision_count=1,
            created_at=now,
            updated_at=now,
        )
        self.store.create_scene(owner, document, revision_record)
        return document, revision_record

    def commit(
        self,
        owner: str,
        scene_id: str,
        base_revision_id: str,
        revision: SceneRevisionInput,
    ) -> tuple[SceneDocument, SceneRevision]:
        owner = self._owner(owner)
        current = self.store.get_scene(scene_id, owner)
        now = _utc_now()
        record = SceneRevision(
            id=f"revision_{uuid.uuid4().hex}",
            scene_id=scene_id,
            sequence=current.revision_count + 1,
            parent_revision_id=base_revision_id,
            created_at=now,
            **revision.model_dump(),
        )
        document = current.model_copy(
            update={
                "current_revision_id": record.id,
                "revision_count": record.sequence,
                "updated_at": now,
            }
        )
        self.store.commit_scene(owner, base_revision_id, document, record)
        return document, record

    def get(self, owner: str, scene_id: str) -> tuple[SceneDocument, list[SceneRevision]]:
        owner = self._owner(owner)
        return self.store.get_scene(scene_id, owner), self.store.list_scene_revisions(scene_id, owner)

    def list(self, owner: str) -> list[SceneDocument]:
        return self.store.list_scenes(self._owner(owner))


def canonical_scene_json(value: BaseModel) -> str:
    """Stable JSON for fingerprints and future backup manifests."""
    return json.dumps(
        value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
