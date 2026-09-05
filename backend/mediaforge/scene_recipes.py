"""Strict, bounded scene recipes and durable agent-task records."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .material_binding import MaterialBinding


ObjectId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9._-]*$",
        description="Stable recipe object ID used by all later operations; it is not a Blender name.",
    ),
]
SceneLabel = Annotated[
    str, Field(min_length=1, max_length=120, pattern=r"^[^\x00-\x1f/\\]+$")
]
SceneTag = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[^\x00-\x1f/\\]+$")
]
Vector3 = tuple[
    Annotated[float, Field(ge=-10_000, le=10_000)],
    Annotated[float, Field(ge=-10_000, le=10_000)],
    Annotated[float, Field(ge=-10_000, le=10_000)],
]
Dimensions3 = tuple[
    Annotated[float, Field(gt=0, le=1_000)],
    Annotated[float, Field(gt=0, le=1_000)],
    Annotated[float, Field(gt=0, le=1_000)],
]


class PrimitiveAdd(BaseModel):
    """Add one bounded mesh primitive; dimensions and location are in meters."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["primitive.add"]
    object_id: ObjectId
    primitive: Literal["cube", "cylinder", "cone", "uv_sphere"]
    name: str = Field(min_length=1, max_length=120)
    dimensions: Dimensions3
    location: Vector3 = (0.0, 0.0, 0.0)
    rotation_degrees: Vector3 = (0.0, 0.0, 0.0)
    vertices: int = Field(default=32, ge=3, le=128)


class TransformSet(BaseModel):
    """Replace one or more transforms on an existing stable object ID."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["transform.set"]
    object_id: ObjectId
    dimensions: Dimensions3 | None = None
    location: Vector3 | None = None
    rotation_degrees: Vector3 | None = None

    @model_validator(mode="after")
    def require_change(self) -> "TransformSet":
        if self.dimensions is None and self.location is None and self.rotation_degrees is None:
            raise ValueError("transform.set requires at least one transform")
        return self


class BevelModifier(BaseModel):
    """Add a bounded non-destructive bevel modifier to a mesh object."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["modifier.bevel"]
    object_id: ObjectId
    width: float = Field(gt=0, le=10)
    segments: int = Field(default=2, ge=1, le=8)


class MaterialSet(BaseModel):
    """Assign a simple Principled BSDF material without external textures."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["material.set"]
    object_id: ObjectId
    name: str = Field(default="Material", min_length=1, max_length=120)
    base_color: tuple[
        Annotated[float, Field(ge=0, le=1)],
        Annotated[float, Field(ge=0, le=1)],
        Annotated[float, Field(ge=0, le=1)],
        Annotated[float, Field(ge=0, le=1)],
    ]
    metallic: float = Field(default=0, ge=0, le=1)
    roughness: float = Field(default=0.5, ge=0, le=1)


class UvSmartProject(BaseModel):
    """Create a bounded smart-project UV map on a mesh object."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["uv.smart_project"]
    object_id: ObjectId
    island_margin: float = Field(default=0.02, ge=0, le=0.25)


class LightAdd(BaseModel):
    """Add one local light preset with a stable object ID."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["light.add"]
    object_id: ObjectId
    light: Literal["area", "point", "sun"]
    name: str = Field(min_length=1, max_length=120)
    energy: float = Field(gt=0, le=100_000)
    location: Vector3 = (0.0, 0.0, 0.0)
    rotation_degrees: Vector3 = (0.0, 0.0, 0.0)


class CameraAdd(BaseModel):
    """Add and activate one camera with transforms expressed in degrees."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["camera.add"]
    object_id: ObjectId
    name: str = Field(min_length=1, max_length=120)
    location: Vector3
    rotation_degrees: Vector3
    focal_length_mm: float = Field(default=50, ge=1, le=300)


SceneOperation = Annotated[
    PrimitiveAdd
    | TransformSet
    | BevelModifier
    | MaterialSet
    | UvSmartProject
    | LightAdd
    | CameraAdd,
    Field(discriminator="type"),
]


class SceneRecipe(BaseModel):
    """Operations applied sequentially by a fixed worker; scripts and operator names are forbidden."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["media-forge.scene-recipe@1"] = "media-forge.scene-recipe@1"
    operations: list[SceneOperation] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_object_references(self) -> "SceneRecipe":
        known: set[str] = set()
        for operation in self.operations:
            if isinstance(operation, (PrimitiveAdd, LightAdd, CameraAdd)):
                if operation.object_id in known:
                    raise ValueError(f"duplicate object_id: {operation.object_id}")
                known.add(operation.object_id)
            elif operation.object_id not in known:
                # Edits may reference stable IDs already present in the base scene.
                # Creation recipes, which have no base, are checked by the worker.
                continue
        return self


class SceneCreateRequest(BaseModel):
    """Create a new immutable 3D scene and return a detached durable Job immediately."""
    model_config = ConfigDict(extra="forbid")
    name: SceneLabel
    tags: list[SceneTag] = Field(default_factory=list, max_length=32)
    collection: SceneLabel | None = None
    recipe: SceneRecipe
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")


class SceneEditRequest(BaseModel):
    """Edit exactly the named current revision; conflicts fail without overwriting it."""
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    base_revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    recipe: SceneRecipe
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")


class SceneMaterialRequest(BaseModel):
    """Bind an existing Media Forge image Asset to an exact scene revision."""
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    binding: MaterialBinding
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")


class SceneCreateAction(SceneCreateRequest):
    action: Literal["create"]


class SceneEditAction(SceneEditRequest):
    action: Literal["edit"]


class SceneMaterialAction(SceneMaterialRequest):
    action: Literal["material"]


SceneWorkflowRequest = Annotated[
    SceneCreateAction | SceneEditAction | SceneMaterialAction, Field(discriminator="action")
]


class SceneReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")


class SceneExportRequest(SceneReferenceRequest):
    format: Literal["glb", "blend"] = "glb"


class SceneJobReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(pattern=r"^job_[0-9a-f]{32}$")


class SceneTaskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(pattern=r"^job_[0-9a-f]{32}$")
    operation: Literal["scene.create", "scene.edit", "scene.material"]
    owner: str = Field(min_length=1, max_length=256)
    host_job_id: str = Field(min_length=1, max_length=128)
    runtime_id: str = Field(min_length=1, max_length=128)
    runtime_version: str = Field(min_length=1, max_length=64)
    base_revision_id: str | None = None
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage: str = Field(min_length=1, max_length=128)
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    host_terminal: dict[str, Any] | None = None
    host_terminal_sent: bool = False
    retry_of: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")
    created_at: str
    updated_at: str
