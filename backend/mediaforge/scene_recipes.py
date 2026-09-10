"""Strict, bounded scene recipes and durable agent-task records."""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

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


class ObjectDuplicate(BaseModel):
    """Copy a mesh to a new stable ID with independent geometry and absolute transforms."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["object.duplicate"]
    object_id: ObjectId
    source_object_id: ObjectId
    name: str = Field(min_length=1, max_length=120)
    dimensions: Dimensions3 | None = None
    location: Vector3 | None = None
    rotation_degrees: Vector3 | None = None

    @model_validator(mode="after")
    def distinct_ids(self) -> "ObjectDuplicate":
        if self.object_id == self.source_object_id:
            raise ValueError("duplicate requires a new stable object ID")
        return self


class MirrorModifier(BaseModel):
    """Mirror mesh geometry in local or referenced object space; at most one mirror per object."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["modifier.mirror"]
    object_id: ObjectId
    axes: list[Literal["X", "Y", "Z"]] = Field(default_factory=lambda: ["X"], min_length=1, max_length=3,
                                             json_schema_extra={"uniqueItems": True})
    reference_object_id: ObjectId | None = None
    merge_threshold: float = Field(default=0.001, ge=0, le=0.1,
        description="Merge distance in local mesh coordinates; object scale affects world-space tolerance. Zero disables merge.")

    @model_validator(mode="after")
    def valid_axes_and_reference(self) -> "MirrorModifier":
        if len(set(self.axes)) != len(self.axes):
            raise ValueError("mirror axes must be unique")
        if self.reference_object_id == self.object_id:
            raise ValueError("mirror reference must be a different object")
        return self


class ArrayModifier(BaseModel):
    """Repeat a static mesh with a fixed local-space offset; one array per object."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["modifier.array"]
    object_id: ObjectId
    count: int = Field(ge=2, le=64, strict=True, description="Total copies including the original mesh.")
    local_offset: Vector3 = Field(
        description="Nonzero local mesh-space step. Object scale and rotation affect world spacing.",
        json_schema_extra={"not": {"const": [0, 0, 0]}},
    )

    @model_validator(mode="after")
    def nonzero_offset(self) -> "ArrayModifier":
        if not any(self.local_offset):
            raise ValueError("array local_offset must be nonzero")
        return self


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


BoneId = Annotated[str, Field(min_length=1, max_length=48, pattern=r"^[a-z][a-z0-9._-]*$")]


class BoneDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bone_id: BoneId
    head: Vector3
    tail: Vector3
    parent_bone_id: BoneId | None = None

    @model_validator(mode="after")
    def nonzero_length(self) -> "BoneDefinition":
        if sum((a - b) ** 2 for a, b in zip(self.head, self.tail, strict=True)) < 0.000001:
            raise ValueError("bone length must be at least 0.001 meters")
        return self


class ArmatureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["armature.create"]
    object_id: ObjectId
    name: str = Field(min_length=1, max_length=120)
    bones: list[BoneDefinition] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def ordered_hierarchy(self) -> "ArmatureCreate":
        known: set[str] = set()
        for bone in self.bones:
            if bone.bone_id in known or (bone.parent_bone_id is not None and bone.parent_bone_id not in known):
                raise ValueError("bone IDs must be unique and parents must precede their children")
            known.add(bone.bone_id)
        return self


class RigidBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mesh_object_id: ObjectId
    bone_id: BoneId


class SkinBind(BaseModel):
    """Bind each unbound mesh rigidly to one bone, preserving rest world geometry."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["skin.bind"]
    object_id: ObjectId
    bindings: list[RigidBinding] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_meshes(self) -> "SkinBind":
        ids = [binding.mesh_object_id for binding in self.bindings]
        if len(set(ids)) != len(ids) or self.object_id in ids:
            raise ValueError("binding mesh IDs must be distinct from each other and from the rig")
        return self


class SkinBindAuto(BaseModel):
    """Bone-heat bind unweighted static meshes to a rest typed rig; normalize to four influences.

    No modifiers or existing weights are replaced. Limits: 50,000 vertices,
    100,000 polygons and 1,000,000 vertex/bone pairs across the selected meshes.
    Missing or invalid heat weights fail the operation without committing a revision.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["skin.bind_auto"]
    object_id: ObjectId
    mesh_object_ids: list[ObjectId] = Field(min_length=1, max_length=16,
                                           json_schema_extra={"uniqueItems": True})

    @model_validator(mode="after")
    def unique_meshes(self) -> "SkinBindAuto":
        if len(set(self.mesh_object_ids)) != len(self.mesh_object_ids) or self.object_id in self.mesh_object_ids:
            raise ValueError("auto binding mesh IDs must be distinct from each other and from the rig")
        return self


class BonePose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bone_id: BoneId
    rotation_degrees: tuple[Annotated[float, Field(ge=-180, le=180)],
                            Annotated[float, Field(ge=-180, le=180)],
                            Annotated[float, Field(ge=-180, le=180)]]


class PoseSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["pose.set"]
    object_id: ObjectId
    bones: list[BonePose] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def unique_bones(self) -> "PoseSet":
        ids = [bone.bone_id for bone in self.bones]
        if len(set(ids)) != len(ids):
            raise ValueError("pose bone IDs must be unique")
        return self


class RotationKey(BaseModel):
    """One key in a rest-local XYZ rotation track."""
    model_config = ConfigDict(extra="forbid")
    frame: int = Field(ge=0, le=600, strict=True)
    rotation_degrees: tuple[Annotated[float, Field(ge=-180, le=180)],
                            Annotated[float, Field(ge=-180, le=180)],
                            Annotated[float, Field(ge=-180, le=180)]]


class AnimationTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bone_id: BoneId
    keys: list[RotationKey] = Field(min_length=2, max_length=256)


class AnimationClip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["animation.clip"]
    object_id: ObjectId
    clip_id: BoneId
    name: str = Field(min_length=1, max_length=120)
    fps: int = Field(default=24, ge=1, le=60, strict=True)
    frame_count: int = Field(ge=1, le=600, strict=True)
    loop: bool = False
    replace: bool = Field(default=False, strict=True)
    tracks: list[AnimationTrack] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def bounded_tracks(self) -> "AnimationClip":
        if self.frame_count > self.fps * 120:
            raise ValueError("clip duration exceeds 120 seconds")
        seen: set[str] = set()
        for track in self.tracks:
            frames = [key.frame for key in track.keys]
            if track.bone_id in seen:
                raise ValueError("track bones must be unique")
            seen.add(track.bone_id)
            if frames[0] != 0 or frames[-1] != self.frame_count or any(a >= b for a,b in zip(frames, frames[1:])):
                raise ValueError("track frames must increase from zero to frame_count")
            if self.loop and track.keys[0].rotation_degrees != track.keys[-1].rotation_degrees:
                raise ValueError("loop track endpoints must match")
        return self


SceneOperation = Annotated[
    PrimitiveAdd
    | TransformSet
    | BevelModifier
    | MaterialSet
    | UvSmartProject
    | LightAdd
    | CameraAdd
    | ObjectDuplicate
    | MirrorModifier
    | ArrayModifier
    | ArmatureCreate
    | SkinBind
    | SkinBindAuto
    | PoseSet
    | AnimationClip,
    Field(discriminator="type"),
]


def scene_operation_types() -> list[str]:
    """Derive capability discovery from the same discriminated schema as requests."""
    union = get_args(SceneOperation)[0]
    return [get_args(model.model_fields["type"].annotation)[0] for model in get_args(union)]


class SceneRecipe(BaseModel):
    """Operations applied sequentially by a fixed worker; scripts and operator names are forbidden."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["media-forge.scene-recipe@1"] = "media-forge.scene-recipe@1"
    operations: list[SceneOperation] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_object_references(self) -> "SceneRecipe":
        known: set[str] = set()
        for operation in self.operations:
            if isinstance(operation, (PrimitiveAdd, LightAdd, CameraAdd, ObjectDuplicate, ArmatureCreate)):
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
    host_terminal_reconciliation: dict[str, Any] | None = None
    retry_of: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")
    created_at: str
    updated_at: str
