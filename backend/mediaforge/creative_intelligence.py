from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .host.ai import HostAIError, HostAIGateway
from .host.client import HostIdentity


CreativeMode = Literal["original", "refine", "art_direct"]
SubjectKind = Literal[
    "person",
    "character",
    "animal",
    "creature",
    "vehicle",
    "robot",
    "product",
    "object",
    "architecture",
    "environment",
    "ui_asset",
    "game_asset",
    "other",
]
EvidenceSource = Literal["user", "observed", "inferred", "suggested"]


class CreativeIntelligenceError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SubjectSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SubjectKind = "other"
    count: int | None = Field(default=None, ge=0, le=64)
    identity_traits: list[str] = Field(default_factory=list, max_length=32)
    appearance_traits: list[str] = Field(default_factory=list, max_length=32)
    materials: list[str] = Field(default_factory=list, max_length=16)


class ActionStateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(default="", max_length=500)
    state: str = Field(default="", max_length=500)
    orientation: str = Field(default="", max_length=300)
    gesture: str = Field(default="", max_length=300)
    gaze: str = Field(default="", max_length=300)
    motion_hint: str = Field(default="", max_length=300)
    body_or_part_relations: list[str] = Field(default_factory=list, max_length=24)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PromptPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = "1"
    original_intent: str = Field(min_length=1, max_length=8000)
    mode: CreativeMode = "refine"
    subject: SubjectSpec = Field(default_factory=SubjectSpec)
    primary_action: ActionStateSpec = Field(default_factory=ActionStateSpec)
    scene: str = Field(default="", max_length=1000)
    composition: str = Field(default="", max_length=1000)
    camera: str = Field(default="", max_length=1000)
    style_cues: list[str] = Field(default_factory=list, max_length=32)
    details: list[str] = Field(default_factory=list, max_length=64)
    hard_constraints: list[str] = Field(default_factory=list, max_length=64)
    optional_suggestions: list[str] = Field(default_factory=list, max_length=64)
    assumptions: list[str] = Field(default_factory=list, max_length=32)


class PaletteColor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    coverage: float = Field(ge=0.0, le=1.0)


class VisualFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = "1"
    width: int = Field(gt=0, le=100_000)
    height: int = Field(gt=0, le=100_000)
    aspect_ratio: float = Field(gt=0.0)
    has_alpha: bool
    opaque_fraction: float = Field(ge=0.0, le=1.0)
    dominant_colors: list[PaletteColor] = Field(default_factory=list, max_length=12)
    accent_colors: list[PaletteColor] = Field(default_factory=list, max_length=8)
    mean_luminance: float = Field(ge=0.0, le=1.0)
    mean_saturation: float = Field(ge=0.0, le=1.0)


class SemanticObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=80)
    value: str = Field(max_length=1000)
    source: EvidenceSource
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class VisualAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = "1"
    asset_hash: str = Field(min_length=1, max_length=128)
    facts: VisualFacts
    subject: SubjectSpec = Field(default_factory=SubjectSpec)
    action_state: ActionStateSpec = Field(default_factory=ActionStateSpec)
    scene: str = Field(default="", max_length=1000)
    composition: str = Field(default="", max_length=1000)
    style: list[str] = Field(default_factory=list, max_length=32)
    clothing_props: list[str] = Field(default_factory=list, max_length=32)
    text_regions: list[str] = Field(default_factory=list, max_length=32)
    observations: list[SemanticObservation] = Field(default_factory=list, max_length=64)
    inferences: list[SemanticObservation] = Field(default_factory=list, max_length=64)
    confidence_by_field: dict[str, float] = Field(default_factory=dict)


class EvaluationScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: float | None = Field(default=None, ge=0.0, le=1.0)
    subject_identity: float | None = Field(default=None, ge=0.0, le=1.0)
    action_state: float | None = Field(default=None, ge=0.0, le=1.0)
    palette: float | None = Field(default=None, ge=0.0, le=1.0)
    composition: float | None = Field(default=None, ge=0.0, le=1.0)
    style: float | None = Field(default=None, ge=0.0, le=1.0)
    props_clothing: float | None = Field(default=None, ge=0.0, le=1.0)
    visual_integrity: float | None = Field(default=None, ge=0.0, le=1.0)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = "1"
    accepted_for_requested_constraints: bool
    scores: EvaluationScores = Field(default_factory=EvaluationScores)
    issues: list[str] = Field(default_factory=list, max_length=32)
    strengths: list[str] = Field(default_factory=list, max_length=32)
    retry_suggestions: list[str] = Field(default_factory=list, max_length=16)
    review_budget_used: int = Field(default=0, ge=0, le=16)


class PromptPlanner:
    """Text-only planner using ControlDeck's provider-neutral text capability."""

    def __init__(self, gateway: HostAIGateway):
        self.gateway = gateway

    async def plan(
        self,
        identity: HostIdentity,
        intent: str,
        *,
        mode: CreativeMode = "refine",
    ) -> PromptPlan:
        normalized = intent.strip()
        if not normalized or len(normalized) > 8000:
            raise CreativeIntelligenceError("invalid_intent", "Intent must contain 1 to 8000 characters")
        if mode == "original":
            return PromptPlan(original_intent=normalized, mode="original")

        instruction = (
            "Convert the user's media-generation intent into the supplied JSON schema. "
            "Preserve every explicit user fact and constraint. Never add a suggestion to hard_constraints. "
            "Put uncertain or newly invented visual direction only in optional_suggestions or assumptions. "
            "Use generic action/state language that works for people, animals, vehicles, robots, products, "
            "architecture and environments. Do not emit engine, sampler, scheduler, model or provider terms. "
        )
        instruction += (
            "For refine mode, clarify useful visible detail without changing the user's meaning."
            if mode == "refine"
            else "For art_direct mode, you may suggest composition, camera, lighting or staging, but mark all additions as optional suggestions."
        )
        response_format = {
            "type": "json_schema",
            "name": "mediaforge_prompt_plan",
            "schema": PromptPlan.model_json_schema(),
            "strict": True,
        }
        try:
            result = await self.gateway.complete(
                identity,
                "text.generate",
                [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": normalized},
                ],
                response_format=response_format,
                temperature=0.1 if mode == "refine" else 0.4,
                max_tokens=2048,
                timeout_seconds=120,
            )
        except HostAIError as exc:
            raise CreativeIntelligenceError(exc.code, str(exc)) from exc
        try:
            value = json.loads(result.content)
            plan = PromptPlan.model_validate(value)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise CreativeIntelligenceError("prompt_plan_invalid", "ControlDeck returned an invalid prompt plan") from exc

        # The model is not authoritative for these two values. Keeping them from
        # the caller makes the original request immutable and prevents a model
        # from silently changing the requested planning mode.
        return plan.model_copy(update={"original_intent": normalized, "mode": mode})


def prompt_plan_to_creative_details(plan: PromptPlan) -> dict[str, str]:
    """Additive projection into fields already understood by CreativeSpec/UI.

    A0 deliberately does not submit or mutate a JobRequest. Later slices may use
    this projection to prefill the existing CreativeSpec controls.
    """
    action_parts = [
        plan.primary_action.action,
        plan.primary_action.state,
        plan.primary_action.orientation,
        plan.primary_action.gesture,
        plan.primary_action.gaze,
    ]
    return {
        "scene_details": plan.scene.strip(),
        "pose_details": "; ".join(value.strip() for value in action_parts if value.strip()),
        "composition_details": plan.composition.strip(),
        "camera_details": plan.camera.strip(),
    }
