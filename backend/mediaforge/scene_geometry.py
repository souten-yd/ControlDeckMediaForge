"""Bounded worker facts, not a core geometry generator."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from .scene_recipes import CurveSection, ObjectId, Vector3


class CurveControlFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: list[CurveSection] = Field(min_length=2, max_length=32)
    radial_segments: int = Field(ge=8, le=32, strict=True)
    samples_per_segment: int = Field(ge=1, le=8, strict=True)
    caps: str = Field(pattern=r"^(both|start|end|none)$")
    up: Vector3
    smooth: bool = Field(strict=True)


class UvMapFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)
    uv_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    loops: int = Field(ge=0, le=1_000_000, strict=True)
    finite: bool = Field(strict=True)
    degenerate_triangles: int | None = Field(default=None, ge=0, le=1_000_000, strict=True)
    bounds_min: tuple[float, float] | None = None
    bounds_max: tuple[float, float] | None = None

    @model_validator(mode="after")
    def finite_bounds(self) -> "UvMapFact":
        import math
        if any(not math.isfinite(x) for bound in (self.bounds_min,self.bounds_max) if bound for x in bound):
            raise ValueError("UV bounds must be finite or null")
        return self


class SkinWeightFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rig_object_id: ObjectId
    vertices: int = Field(ge=0, le=16384, strict=True)
    unweighted_vertices: int = Field(ge=0, le=16384, strict=True)
    invalid_vertices: int = Field(ge=0, le=16384, strict=True)
    max_influences: int = Field(ge=0, le=128, strict=True)
    max_sum_error: float = Field(ge=0, allow_inf_nan=False)


class MeshGeometryFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_id: ObjectId
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    vertices: int = Field(ge=0, le=16384, strict=True)
    triangles: int = Field(ge=0, le=1_000_000, strict=True)
    boundary_edges: int = Field(ge=0, le=1_000_000, strict=True)
    nonmanifold_edges: int = Field(ge=0, le=1_000_000, strict=True)
    inconsistent_edges: int = Field(ge=0, le=1_000_000, strict=True)
    boundary_loops: list[Annotated[list[Annotated[int, Field(ge=0, le=16383, strict=True)]],
                                  Field(min_length=3, max_length=64)]] = Field(max_length=16)
    skin_weights: SkinWeightFact | None = None
    curve: CurveControlFact | None = None
    uv_maps: list[UvMapFact] | None = Field(default=None, max_length=8)

    @model_validator(mode="after")
    def indices(self) -> "MeshGeometryFact":
        for loop in self.boundary_loops:
            if len(set(loop)) != len(loop) or max(loop) >= self.vertices:
                raise ValueError("worker boundary indices differ")
        return self


GEOMETRY_FACTS = TypeAdapter(Annotated[list[MeshGeometryFact], Field(max_length=256)])


def validate_geometry_facts(value: object, object_ids: list[str] | None = None) -> list[dict]:
    """Validate a bounded projection before storing or returning it."""
    facts = GEOMETRY_FACTS.validate_python(value)
    ids = [fact.object_id for fact in facts]
    if len(set(ids)) != len(ids) or (object_ids is not None and not set(ids) <= set(object_ids)):
        raise ValueError("worker geometry IDs differ")
    return [fact.model_dump(mode="json", exclude_none=True) for fact in facts]
