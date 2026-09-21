"""Strict, bounded scene recipes and durable agent-task records."""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .material_binding import MaterialBinding
from .scene_generation import SceneFromImageRequest


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


class MeshCreate(BaseModel):
    """Create authored triangle/quad topology for organic silhouettes, hair clumps,
    garment shells or armor. Coordinates are local meters; faces use zero-based
    vertex indices in outward winding order. Smooth shading changes normals only,
    not geometry. Open garment edges are allowed; no automatic retopology or UVs.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["mesh.create"]
    object_id: ObjectId
    name: SceneLabel
    vertices: list[Vector3] = Field(min_length=3, max_length=4096)
    faces: list[Annotated[list[Annotated[int, Field(ge=0, le=4095, strict=True)]],
                          Field(min_length=3, max_length=4)]] = Field(min_length=1, max_length=4096)
    smooth: bool = Field(default=True, strict=True)
    require_closed: bool = Field(
        default=False, strict=True,
        description="Set true for a requested closed armor/solid shell. Every edge must have exactly two "
        "oppositely directed face uses. Open cloth remains allowed when false. This does not check "
        "self-intersections, vertex fans, volume, outward orientation or visual quality.",
    )
    location: Vector3 = (0.0, 0.0, 0.0)
    rotation_degrees: Vector3 = (0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def topology(self) -> "MeshCreate":
        used: set[int] = set()
        seen: set[tuple[int, ...]] = set()
        for face in self.faces:
            if len(set(face)) != len(face) or max(face) >= len(self.vertices):
                raise ValueError("mesh face indices are invalid")
            identity = tuple(sorted(face))
            if identity in seen:
                raise ValueError("mesh has duplicate faces")
            seen.add(identity)
            used.update(face)
            a = self.vertices[face[0]]
            for offset in range(1, len(face) - 1):
                b, c = self.vertices[face[offset]], self.vertices[face[offset + 1]]
                u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
                cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                if sum(x*x for x in cross) <= 1e-20:
                    raise ValueError("mesh has degenerate faces")
        if len(used) != len(self.vertices):
            raise ValueError("mesh has unreferenced vertices")
        if self.require_closed:
            edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
            for face in self.faces:
                for a, b in zip(face, face[1:] + face[:1]):
                    edges.setdefault(tuple(sorted((a, b))), []).append((a, b))
            boundary = sum(len(uses) == 1 for uses in edges.values())
            multiple = sum(len(uses) > 2 for uses in edges.values())
            winding = sum(len(uses) == 2 and uses[0] != uses[1][::-1] for uses in edges.values())
            if boundary or multiple or winding:
                raise ValueError(f"mesh requires closed consistent edges: boundary={boundary}, "
                                 f"multiple={multiple}, winding={winding}")
        return self


class CurveSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    center: Vector3
    radii: tuple[Annotated[float, Field(ge=0.001, le=100)], Annotated[float, Field(ge=0.001, le=100)]]


class MeshLoft(BaseModel):
    """Generate an elliptical loft in local meters. The worker expands bounded sections;
    caps close ends, not intersections. Same-count sections can later be edited using
    the geometry hash returned by the recipe and snapshot.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["mesh.loft"]
    object_id: ObjectId
    name: SceneLabel
    sections: list[CurveSection] = Field(min_length=2, max_length=32)
    radial_segments: int = Field(default=16, ge=8, le=32, strict=True)
    samples_per_segment: int = Field(default=3, ge=1, le=8, strict=True)
    caps: Literal["both", "start", "end", "none"] = "both"
    up: Vector3 = (0.0, 0.0, 1.0)
    smooth: bool = Field(default=True, strict=True)
    location: Vector3 = (0.0, 0.0, 0.0)
    rotation_degrees: Vector3 = (0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def curve_bounds(self) -> "MeshLoft":
        validate_curve_sections(self.sections, self.up)
        return self


def validate_curve_sections(sections: list[CurveSection], up: Vector3) -> None:
    if sum(x*x for x in up) < 1e-12:
        raise ValueError("curve up vector must be nonzero")
    if any(sum((x-y)**2 for x,y in zip(a.center,b.center)) < 1e-8 for a,b in zip(sections, sections[1:])):
        raise ValueError("adjacent curve centers must be distinct")


class MeshSweep(BaseModel):
    """Sweep a constant elliptical cross-section along a bounded local-meter path."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["mesh.sweep"]
    object_id: ObjectId
    name: SceneLabel
    path_points: list[Vector3] = Field(min_length=2, max_length=32)
    radii: tuple[Annotated[float, Field(ge=0.001, le=100)], Annotated[float, Field(ge=0.001, le=100)]]
    radial_segments: int = Field(default=16, ge=8, le=32, strict=True)
    samples_per_segment: int = Field(default=3, ge=1, le=8, strict=True)
    caps: Literal["both", "start", "end", "none"] = "both"
    up: Vector3 = (0.0, 0.0, 1.0)
    smooth: bool = Field(default=True, strict=True)
    location: Vector3 = (0.0, 0.0, 0.0)
    rotation_degrees: Vector3 = (0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def curve_bounds(self) -> "MeshSweep":
        validate_curve_sections([CurveSection(center=p,radii=self.radii) for p in self.path_points], self.up)
        return self


class MeshSectionsSet(BaseModel):
    """Replace all control sections, preserving vertex/face order, weights and UVs.
    Requires an unchanged procedural mesh and its actual geometry hash. The number
    of sections and sampling settings cannot change through this operation.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["mesh.sections.set"]
    object_id: ObjectId
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sections: list[CurveSection] = Field(min_length=2, max_length=32)


    @model_validator(mode="after")
    def sections_distinct(self) -> "MeshSectionsSet":
        validate_curve_sections(self.sections, (0.0, 0.0, 1.0))
        return self


class MeshBridgeLoops(BaseModel):
    """Join two independent static meshes across equal-sized open boundary loops.
    Requires current geometry hashes and ordered boundary indices, consumes the
    second object, preserves existing faces/materials/UVs, and ends procedural
    section editing. It does not cut holes or prove an intersection-free joint.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["mesh.bridge_loops"]
    object_id: ObjectId
    other_object_id: ObjectId
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    other_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    boundary: list[Annotated[int, Field(ge=0, le=16383, strict=True)]] = Field(min_length=3, max_length=64)
    other_boundary: list[Annotated[int, Field(ge=0, le=16383, strict=True)]] = Field(min_length=3, max_length=64)
    twist_offset: int = Field(default=0, ge=-63, le=63, strict=True)

    @model_validator(mode="after")
    def unique_loops(self) -> "MeshBridgeLoops":
        if self.object_id == self.other_object_id:
            raise ValueError("bridge requires two different objects")
        if len(self.boundary) != len(self.other_boundary) or any(len(set(loop)) != len(loop) for loop in (self.boundary,self.other_boundary)):
            raise ValueError("bridge loops must have equal counts and unique indices")
        return self


class SubdivisionModifier(BaseModel):
    """Add one bounded Catmull-Clark subdivision modifier; estimated scene growth
    is checked before evaluation. This smooths geometry, not semantic quality.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["modifier.subdivision"]
    object_id: ObjectId
    levels: int = Field(default=1, ge=1, le=2, strict=True)


class MeshDecimate(BaseModel):
    """Collapse-decimate one mesh in place, keeping its UVs and material.

    生成した 3D は 1 枚の密なメッシュとして届く。骨を入れる（`skin.bind_auto`）には
    頂点・面の上限があり、そのままでは越える。trellis 側の格子まとめで落とすと
    薄い装甲板が升目に飲まれて表面が虫食いになるので、辺の縮約で落とす。
    平らな面は粗く、エッジは残る。増やす操作ではないので成長量の検査は要らない。
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["mesh.decimate"]
    object_id: ObjectId
    # 残す面の割合。1.0 は何もしないのと同じなので受けない。
    ratio: float = Field(gt=0.001, lt=1.0, allow_inf_nan=False)
    # 下限を割ってまで落とさない。形が消えるくらいなら失敗させる。
    min_faces: int = Field(default=64, ge=4, le=1_000_000, strict=True)


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


class TransformApplyScale(BaseModel):
    """Apply positive scale to independent static mesh coordinates before baking.
    Geometry is hash pinned; only subdivision modifiers are retained. Procedural
    controls become stale when a non-unit scale changes the cage coordinates.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["transform.apply_scale"]
    object_id: ObjectId
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class UvSeamsSet(BaseModel):
    """Mark or clear bounded mesh edges as UV seams using actual geometry selectors."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["uv.seams.set"]
    object_id: ObjectId
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edges: list[tuple[Annotated[int, Field(ge=0, le=16383, strict=True)], Annotated[int, Field(ge=0, le=16383, strict=True)]]] = Field(min_length=1, max_length=4096)
    mark: bool = Field(default=True, strict=True)
    clear_existing: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def unique_edges(self) -> "UvSeamsSet":
        if any(a == b for a,b in self.edges) or len({tuple(sorted(e)) for e in self.edges}) != len(self.edges):
            raise ValueError("seam edges must be unique and distinct")
        return self


class UvUnwrap(BaseModel):
    """Unwrap a bounded mesh after explicit seams; selection is hash pinned."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["uv.unwrap"]
    object_id: ObjectId
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method: Literal["ANGLE_BASED", "CONFORMAL"] = "ANGLE_BASED"
    margin: float = Field(default=0.02, ge=0.001, le=0.25)


class UvPack(BaseModel):
    """Pack existing UV islands into a unit tile under a bounded geometry hash."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["uv.pack"]
    object_id: ObjectId
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    margin: float = Field(default=0.02, ge=0.001, le=0.25)
    rotate: bool = Field(default=True, strict=True)


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


class WeightSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_id: ObjectId
    rig_object_id: ObjectId
    expected_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    vertex_indices: list[Annotated[int, Field(ge=0, le=16383, strict=True)]] = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def distinct_vertices(self) -> "WeightSelection":
        if len(set(self.vertex_indices)) != len(self.vertex_indices) or self.object_id == self.rig_object_id:
            raise ValueError("weight selection must be unique and separate from rig")
        return self


class BoneInfluence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bone_id: BoneId
    weight: float = Field(gt=0, le=1, allow_inf_nan=False)


class SkinWeightsSet(WeightSelection):
    """Replace selected vertex weights with at most four known bone influences summing to one."""
    type: Literal["skin.weights.set"]
    influences: list[BoneInfluence] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def normalized(self) -> "SkinWeightsSet":
        if len({i.bone_id for i in self.influences}) != len(self.influences) or abs(sum(i.weight for i in self.influences)-1)>1e-5:
            raise ValueError("weights must name distinct bones and sum to one")
        return self


class SkinWeightsSmooth(WeightSelection):
    """Average selected weights along actual cage edges, retaining top four influences."""
    type: Literal["skin.weights.smooth"]
    iterations: int = Field(default=1, ge=1, le=8, strict=True)
    factor: float = Field(default=.5, gt=0, le=1, allow_inf_nan=False)


class SkinWeightsNormalize(WeightSelection):
    """Normalize selected nonempty existing weights and retain at most four influences."""
    type: Literal["skin.weights.normalize"]


class IkTargetKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame: int = Field(ge=0, le=120, strict=True)
    target: Vector3
    pole: Vector3


class IkLegBake(BaseModel):
    """Bake a two-bone leg's world target/pole to a bounded rotation clip. No stretch or persistent IK controls."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["ik.leg.bake"]
    object_id: ObjectId
    upper_bone_id: BoneId
    lower_bone_id: BoneId
    clip_id: BoneId
    name: str = Field(min_length=1, max_length=120)
    fps: int = Field(default=24, ge=1, le=60, strict=True)
    frame_count: int = Field(ge=1, le=120, strict=True)
    loop: bool = Field(default=False, strict=True)
    replace: bool = Field(default=False, strict=True)
    pole_angle_degrees: float = Field(default=0, ge=-180, le=180, allow_inf_nan=False)
    targets: list[IkTargetKey] = Field(min_length=2, max_length=121)

    @model_validator(mode="after")
    def ordered_targets(self) -> "IkLegBake":
        frames=[item.frame for item in self.targets]
        if self.upper_bone_id==self.lower_bone_id or frames[0]!=0 or frames[-1]!=self.frame_count or any(a>=b for a,b in zip(frames,frames[1:])):
            raise ValueError("IK chain and ordered endpoint samples must differ")
        if self.loop and (self.targets[0].target!=self.targets[-1].target or self.targets[0].pole!=self.targets[-1].pole):
            raise ValueError("loop target and pole endpoints must match")
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
    """Rest-local XYZ rotation plus optional rest-bone-local translation in meters."""
    model_config = ConfigDict(extra="forbid")
    frame: int = Field(ge=0, le=600, strict=True)
    rotation_degrees: tuple[Annotated[float, Field(ge=-180, le=180)],
                            Annotated[float, Field(ge=-180, le=180)],
                            Annotated[float, Field(ge=-180, le=180)]]

    translation_m: tuple[Annotated[float, Field(ge=-100, le=100, allow_inf_nan=False)],
                         Annotated[float, Field(ge=-100, le=100, allow_inf_nan=False)],
                         Annotated[float, Field(ge=-100, le=100, allow_inf_nan=False)]] | None = None

    @model_serializer(mode="wrap")
    def legacy_omission(self, handler: Any) -> dict[str, Any]:
        result = handler(self)
        if self.translation_m is None:
            result.pop("translation_m", None)
        return result


class AnimationTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bone_id: BoneId
    keys: list[RotationKey] = Field(min_length=2, max_length=256)


class AnimationClip(BaseModel):
    """Create a bone animation clip. For requested looping motion, explicitly set
    loop=true on EVERY clip: matching endpoint keys do not enable loop validation.
    Omitted loop defaults to false. Verify the submitted fields against the request
    before execution; a successful Job alone does not prove the requested motion.
    """
    model_config = ConfigDict(extra="forbid")
    type: Literal["animation.clip"]
    object_id: ObjectId
    clip_id: BoneId
    name: str = Field(min_length=1, max_length=120)
    fps: int = Field(default=24, ge=1, le=60, strict=True)
    frame_count: int = Field(ge=1, le=600, strict=True)
    loop: bool = Field(default=False, description=(
        "Set true explicitly for a requested looping clip (including idle/walk loops). "
        "Omission means false, even when first and last rotations match. True enables "
        "endpoint validation; it does not guarantee velocity continuity or engine playback looping."))
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
            supplied = [key.translation_m is not None for key in track.keys]
            if any(supplied) and not all(supplied):
                raise ValueError("translation must be supplied at every key in its track")
            if self.loop and track.keys[0].translation_m != track.keys[-1].translation_m:
                raise ValueError("loop translation endpoints must match")
            if self.loop and track.keys[0].rotation_degrees != track.keys[-1].rotation_degrees:
                raise ValueError("loop track endpoints must match")
        return self


SceneOperation = Annotated[
    PrimitiveAdd
    | MeshCreate
    | MeshLoft
    | MeshSweep
    | MeshSectionsSet
    | MeshBridgeLoops
    | SubdivisionModifier
    | MeshDecimate
    | TransformSet
    | BevelModifier
    | MaterialSet
    | UvSmartProject
    | TransformApplyScale
    | UvSeamsSet
    | UvUnwrap
    | UvPack
    | LightAdd
    | CameraAdd
    | ObjectDuplicate
    | MirrorModifier
    | ArrayModifier
    | ArmatureCreate
    | SkinBind
    | SkinBindAuto
    | SkinWeightsSet
    | SkinWeightsSmooth
    | SkinWeightsNormalize
    | IkLegBake
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
            if isinstance(operation, (PrimitiveAdd, MeshCreate, MeshLoft, MeshSweep, LightAdd, CameraAdd, ObjectDuplicate, ArmatureCreate)):
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
    reference_set_asset_id: str | None = Field(default=None, pattern=r"^asset_[0-9a-f]{32}$")
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")


class SceneEditRequest(BaseModel):
    """Edit exactly the named current revision; conflicts fail without overwriting it."""
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    base_revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    publish_mode: Literal["advance", "candidate"] = Field(default="advance", description="advance keeps existing behavior; candidate creates a separate scene and retains the original head.")
    recipe: SceneRecipe
    reference_set_asset_id: str | None = Field(default=None, pattern=r"^asset_[0-9a-f]{32}$")
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


class SceneFromImageAction(SceneFromImageRequest):
    action: Literal["from_image"]


SceneWorkflowRequest = Annotated[
    SceneCreateAction | SceneEditAction | SceneMaterialAction | SceneFromImageAction, Field(discriminator="action")
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
    operation: Literal["scene.create", "scene.edit", "scene.material", "scene.observe", "scene.review", "scene.refine", "scene.bake", "scene.from_image"]
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
