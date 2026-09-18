"""Bounded candidate refinement; no automatic change to the original scene head."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scene_observation import ObservationSpec
from .scene_recipes import MeshSectionsSet, TransformSet
from .scene_review import ReviewIssue


class SceneRefineRequest(BaseModel):
    """Render, review and locally refine an exact current scene into separate candidates.

    Uses Host vision.analyze and text.generate with actual fixed clay observations.
    The original scene head is retained. At most three issues are addressed per
    attempt; two consecutive non-improvements stop the loop. A returned selected
    candidate is advisory and does not approve deformation or game readiness.
    Missing vision/text capabilities fail without a text-only visual substitute.
    Poll the detached Job and read its refinement report before choosing a result.
    """
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    base_revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    intent: str = Field(min_length=1, max_length=2000)
    observation: ObservationSpec
    max_iterations: int = Field(default=3, ge=1, le=6, strict=True)
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")

    @model_validator(mode="after")
    def fixed_clay_views(self) -> "SceneRefineRequest":
        if self.observation.mode != "clay" or not {"front","side"} <= set(self.observation.views):
            raise ValueError("refinement requires fixed clay front and side views")
        return self


class LocalRepair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue_indices: list[Annotated[int, Field(ge=0, le=2, strict=True)]] = Field(min_length=1, max_length=3)
    explanation: str = Field(min_length=1, max_length=600)
    operations: list[Annotated[MeshSectionsSet | TransformSet, Field(discriminator="type")]] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def unique_issues(self) -> "LocalRepair":
        if len(set(self.issue_indices)) != len(self.issue_indices):
            raise ValueError("repair issue indices must be unique")
        return self


class ComparisonIssue(ReviewIssue):
    scope: Literal["object", "scene"]
    evidence_ids: list[Annotated[str, Field(pattern=r"^candidate\.(front|side|back|three-quarter)$")]] = Field(min_length=1, max_length=4)


class ImageComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change: Literal["improved", "unchanged", "worse", "inconclusive"]
    explanation: str = Field(min_length=1, max_length=600)
    evidence_ids: list[Annotated[str, Field(pattern=r"^(baseline|candidate)\.(front|side|back|three-quarter)$")]] = Field(min_length=2, max_length=8)
    remaining_issues: list[ComparisonIssue] = Field(max_length=3)
    limitations: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def both_sides(self) -> "ImageComparison":
        if len(set(self.evidence_ids)) != len(self.evidence_ids) or not all(any(e.startswith(k+'.') for e in self.evidence_ids) for k in ('baseline','candidate')):
            raise ValueError("comparison must cite both actual image sets")
        return self
