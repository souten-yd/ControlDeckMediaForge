"""Typed advisory visual review; image evidence is checked independently of the model."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AssetId = Annotated[str, Field(pattern=r"^asset_[0-9a-f]{32}$")]
EvidenceId = Annotated[str, Field(pattern=r"^(observation\.(front|side|back|three-quarter)|reference\.(front|side|back|three-quarter|canonical))$")]
ObjectId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9._-]*$")]
ReviewText = Annotated[str, Field(min_length=1, max_length=300)]


class SceneReviewRequest(BaseModel):
    """Review actual observation images of an exact scene revision through local Host vision.

    Supply 2–4 observation Assets including front and side under identical camera settings.
    The revision's pinned reference images are included automatically. Returns a detached
    Job; poll media.job.status for a ZIP report with up to three evidence-backed issues.
    This is advisory: it neither edits the scene nor approves topology, animation or
    game readiness. Missing vision fails explicitly; there is no text-only fallback.
    """
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(pattern=r"^scene_[0-9a-f]{32}$")
    revision_id: str = Field(pattern=r"^revision_[0-9a-f]{32}$")
    observation_asset_ids: list[AssetId] = Field(min_length=2, max_length=4, json_schema_extra={"uniqueItems": True})
    reference_set_asset_id: AssetId | None = None
    intent: str = Field(min_length=1, max_length=2000)
    retry_job_id: str | None = Field(default=None, pattern=r"^job_[0-9a-f]{32}$")

    @model_validator(mode="after")
    def unique_images(self) -> SceneReviewRequest:
        if len(set(self.observation_asset_ids)) != len(self.observation_asset_ids):
            raise ValueError("observation image Assets must be unique")
        return self


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["object", "scene", "reference"]
    object_id: ObjectId | None
    evidence_ids: list[EvidenceId] = Field(min_length=1, max_length=4)
    description: ReviewText
    expected_improvement: ReviewText
    suggested_operation: str | None = Field(max_length=64, pattern=r"^[a-z][a-z0-9._-]*$")
    confidence: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def coherent_scope(self) -> ReviewIssue:
        if (self.scope == "object") != (self.object_id is not None):
            raise ValueError("only object issues must identify an object")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("issue evidence IDs must be unique")
        return self


class VisualReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["issues_found", "no_visible_issues", "inconclusive"]
    reference_consistency: Literal["consistent", "contradictory", "uncertain", "not_provided"]
    issues: list[ReviewIssue] = Field(max_length=3)
    limitations: list[ReviewText] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def coherent_verdict(self) -> VisualReview:
        if self.verdict == "no_visible_issues" and self.issues:
            raise ValueError("no-visible-issues verdict cannot contain issues")
        if self.verdict == "issues_found" and not self.issues:
            raise ValueError("issues-found verdict requires evidence-backed issues")
        if self.reference_consistency in {"contradictory", "uncertain"} and self.verdict == "no_visible_issues":
            raise ValueError("unresolved references cannot produce a no-visible-issues verdict")
        return self
