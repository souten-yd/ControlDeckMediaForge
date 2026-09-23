"""Validate optional private worker evidence for bounded automatic weight repairs."""
from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scene_recipes import ObjectId, SceneRecipe


class WeightRepairFact(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    object_id: ObjectId
    repaired_vertices: int = Field(ge=1, le=128)
    components: int = Field(ge=1, le=128)
    max_donor_distance_m: float = Field(ge=0, allow_inf_nan=False)
    distance_limit_m: float = Field(gt=0, allow_inf_nan=False)
    body_height_m: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def bounds(self) -> WeightRepairFact:
        if (self.components > self.repaired_vertices
                or self.max_donor_distance_m > self.distance_limit_m
                or not math.isclose(self.distance_limit_m, self.body_height_m * .005, rel_tol=1e-9)):
            raise ValueError('worker weight repair exceeds bounds')
        return self


def validate_weight_repairs(value: Any, stable_ids: list[str], recipe: SceneRecipe) -> list[dict[str, Any]]:
    targets = [operation.object_id for operation in recipe.operations if operation.type == 'rig.auto']
    if not isinstance(value, list) or len(value) > len(targets):
        raise ValueError('worker weight repair count differs')
    result = []
    for raw in value:
        fact = WeightRepairFact.model_validate(raw)
        if fact.object_id not in stable_ids or fact.object_id not in targets:
            raise ValueError('worker weight repair object differs')
        targets.remove(fact.object_id)
        result.append(fact.model_dump())
    return result
