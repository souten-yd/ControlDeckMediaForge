from __future__ import annotations

import json
from typing import Annotated, Literal

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


class PromptPlanDraft(BaseModel):
    """AI-authored fields only; user-owned immutable fields are excluded."""

    model_config = ConfigDict(extra="forbid")

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


class PromptPlan(PromptPlanDraft):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = "1"
    original_intent: str = Field(min_length=1, max_length=8000)
    mode: CreativeMode = "refine"


class ActionVariationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PromptPlanDraft
    actions: list[ActionStateSpec] = Field(min_length=2, max_length=4)


class DirectedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PromptPlan
    creative_spec: dict
    applied_fields: list[str] = Field(default_factory=list)
    assistance_used: bool
    skipped_reason: str | None = None
    reference_context: list[dict] = Field(default_factory=list, max_length=4)


class DirectedActionVariations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PromptPlan
    actions: list[ActionStateSpec] = Field(default_factory=list, max_length=4)
    assistance_used: bool
    skipped_reason: str | None = None
    reference_context: list[dict] = Field(default_factory=list, max_length=4)


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
    confidence_by_field: dict[
        Annotated[str, Field(min_length=1, max_length=80)],
        Annotated[float, Field(ge=0.0, le=1.0)],
    ] = Field(default_factory=dict, max_length=64)


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


def _provider_strict_schema(schema: dict) -> dict:
    """Make every provider-authored object field explicit for strict JSON output.

    Canonical product models keep ergonomic defaults for trusted local callers.
    The provider schema is stricter so an empty object cannot silently expand to
    a seemingly valid but content-free plan through those defaults.
    """
    value = json.loads(json.dumps(schema))

    def visit(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if node.get("type") == "object" and isinstance(properties, dict):
                node["required"] = list(properties)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return value


def _has_useful_direction(plan: PromptPlanDraft) -> bool:
    action = plan.primary_action
    return any((
        plan.subject.kind != "other",
        plan.subject.count is not None,
        plan.subject.identity_traits,
        plan.subject.appearance_traits,
        plan.subject.materials,
        action.action,
        action.state,
        action.orientation,
        action.gesture,
        action.gaze,
        action.motion_hint,
        action.body_or_part_relations,
        plan.scene,
        plan.composition,
        plan.camera,
        plan.style_cues,
        plan.details,
        plan.hard_constraints,
        plan.optional_suggestions,
    ))


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
        reference_context: list[dict] | None = None,
    ) -> PromptPlan:
        normalized = intent.strip()
        if not normalized or len(normalized) > 8000:
            raise CreativeIntelligenceError("invalid_intent", "Intent must contain 1 to 8000 characters")
        if mode == "original":
            return PromptPlan(original_intent=normalized, mode="original")

        instruction = (
            "Convert the user's media-generation intent into the supplied JSON schema. "
            "Populate every schema field. Extract the visible subject and primary action/state; do not "
            "return an empty plan when the user described either one. Use empty strings or arrays only "
            "for facts that are genuinely absent. "
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
        accepted_context = _validated_reference_context(reference_context)
        user_content = normalized
        if accepted_context:
            user_content += "\nAccepted structured reference context (do not infer fields that are absent):\n"
            user_content += json.dumps(accepted_context, ensure_ascii=False, sort_keys=True)
        response_format = {
            "type": "json_schema",
            "name": "mediaforge_prompt_plan",
            "schema": _provider_strict_schema(PromptPlanDraft.model_json_schema()),
            "strict": True,
        }
        try:
            result = await self.gateway.complete(
                identity,
                "text.generate",
                [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user_content},
                ],
                response_format=response_format,
                temperature=0.1 if mode == "refine" else 0.4,
                max_tokens=2048,
                timeout_seconds=120,
            )
        except HostAIError as exc:
            raise CreativeIntelligenceError(exc.code, str(exc)) from exc
        try:
            authored = json.loads(result.content)
            if not isinstance(authored, dict):
                raise TypeError("prompt plan must be an object")
            # These fields are owned by Media Forge. A provider may echo a full
            # PromptPlan despite the requested draft schema; discard only the
            # protected fields and keep fail-closed validation for every other
            # unknown field.
            for protected in ("version", "original_intent", "mode"):
                authored.pop(protected, None)
            draft = PromptPlanDraft.model_validate(authored)
            if not _has_useful_direction(draft):
                raise ValueError("prompt plan contains no extracted direction")
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            raise CreativeIntelligenceError("prompt_plan_invalid", "ControlDeck returned an invalid prompt plan") from exc

        # The AI never authors these values. The original request is therefore
        # immutable by construction rather than being trusted and overwritten later.
        return PromptPlan(
            **draft.model_dump(mode="python"),
            original_intent=normalized,
            mode=mode,
        )

    async def plan_action_variations(
        self,
        identity: HostIdentity,
        intent: str,
        *,
        mode: CreativeMode,
        count: int,
        reference_context: list[dict] | None = None,
    ) -> tuple[PromptPlan, list[ActionStateSpec]]:
        normalized = intent.strip()
        if not normalized or len(normalized) > 8000:
            raise CreativeIntelligenceError("invalid_intent", "Intent must contain 1 to 8000 characters")
        if mode == "original" or not 2 <= count <= 4:
            raise CreativeIntelligenceError(
                "action_variation_invalid", "Directed action variations require 2 to 4 candidates"
            )
        instruction = (
            "Structure the user's media-generation intent and propose exactly the requested number of "
            "visibly distinct action/state alternatives in one response. Populate every schema field and "
            "extract the visible subject and action/state. Preserve every explicit identity, "
            "count, color, object, scene and style constraint. Vary only action, gesture, orientation, gaze, "
            "motion or body/part relations. Use language that works for people, animals, vehicles, robots, "
            "products and objects. Never emit model, provider, sampler, scheduler, port or engine terms. "
            "Do not put invented ideas in hard_constraints."
        )
        response_format = {
            "type": "json_schema",
            "name": "mediaforge_action_variations",
            "schema": _provider_strict_schema(ActionVariationDraft.model_json_schema()),
            "strict": True,
        }
        accepted_context = _validated_reference_context(reference_context)
        user_content = f"count={count}\n{normalized}"
        if accepted_context:
            user_content += "\nAccepted structured reference context (vary actions only):\n"
            user_content += json.dumps(accepted_context, ensure_ascii=False, sort_keys=True)
        try:
            result = await self.gateway.complete(
                identity,
                "text.generate",
                [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user_content},
                ],
                response_format=response_format,
                temperature=0.2 if mode == "refine" else 0.4,
                max_tokens=3072,
                timeout_seconds=120,
            )
        except HostAIError as exc:
            raise CreativeIntelligenceError(exc.code, str(exc)) from exc
        try:
            authored = json.loads(result.content)
            if not isinstance(authored, dict) or not isinstance(authored.get("plan"), dict):
                raise TypeError("action variation plan must be an object")
            for protected in ("version", "original_intent", "mode"):
                authored["plan"].pop(protected, None)
            draft = ActionVariationDraft.model_validate(authored)
            if len(draft.actions) != count:
                raise ValueError("action variation count does not match request")
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            raise CreativeIntelligenceError(
                "prompt_plan_invalid", "ControlDeck returned invalid action variations"
            ) from exc
        plan = PromptPlan(
            **draft.plan.model_dump(mode="python"),
            original_intent=normalized,
            mode=mode,
        )
        return plan, draft.actions


class CreativeDirector:
    """Fail-soft product wrapper around the one provider-neutral PromptPlanner."""

    def __init__(self, planner: PromptPlanner):
        self.planner = planner

    async def available(self, identity: HostIdentity | None) -> bool:
        if identity is None or "ai.inference" not in identity.granted_capabilities:
            return False
        try:
            return await self.planner.gateway.available(identity, "text.generate")
        except HostAIError:
            return False

    async def direct(
        self,
        identity: HostIdentity | None,
        intent: str,
        creative_spec: dict,
        *,
        mode: CreativeMode,
        reference_context: list[dict] | None = None,
    ) -> DirectedPlan:
        normalized = intent.strip()
        fallback = PromptPlan(original_intent=normalized, mode=mode)
        if mode == "original":
            return DirectedPlan(
                plan=fallback, creative_spec=creative_spec, assistance_used=False,
                skipped_reason="original_mode",
            )
        if identity is None or "ai.inference" not in identity.granted_capabilities:
            return DirectedPlan(
                plan=fallback, creative_spec=creative_spec, assistance_used=False,
                skipped_reason="text_generator_unavailable",
            )
        try:
            plan = await self.planner.plan(
                identity, normalized, mode=mode, reference_context=reference_context,
            )
        except CreativeIntelligenceError as exc:
            return DirectedPlan(
                plan=fallback, creative_spec=creative_spec, assistance_used=False,
                skipped_reason=exc.code,
            )
        projected, applied = project_plan_to_creative_spec(plan, creative_spec)
        return DirectedPlan(
            plan=plan, creative_spec=projected, applied_fields=applied, assistance_used=True,
            reference_context=_validated_reference_context(reference_context),
        )

    async def action_variations(
        self,
        identity: HostIdentity | None,
        intent: str,
        *,
        mode: CreativeMode,
        count: int,
        reference_context: list[dict] | None = None,
    ) -> DirectedActionVariations:
        normalized = intent.strip()
        fallback = PromptPlan(original_intent=normalized, mode=mode)
        if mode == "original" or identity is None or "ai.inference" not in identity.granted_capabilities:
            reason = "original_mode" if mode == "original" else "text_generator_unavailable"
            return DirectedActionVariations(
                plan=fallback, assistance_used=False, skipped_reason=reason,
            )
        try:
            plan, actions = await self.planner.plan_action_variations(
                identity, normalized, mode=mode, count=count,
                reference_context=reference_context,
            )
        except CreativeIntelligenceError as exc:
            return DirectedActionVariations(
                plan=fallback, assistance_used=False, skipped_reason=exc.code,
            )
        return DirectedActionVariations(
            plan=plan, actions=actions, assistance_used=True,
            reference_context=_validated_reference_context(reference_context),
        )


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
        plan.primary_action.motion_hint,
        *plan.primary_action.body_or_part_relations,
    ]
    return {
        "scene_details": plan.scene.strip(),
        "pose_details": _bounded_join(action_parts, 500),
        "composition_details": plan.composition.strip(),
        "camera_details": plan.camera.strip(),
    }


def action_state_to_pose_details(action: ActionStateSpec) -> str:
    return _bounded_join([
        action.action, action.state, action.orientation, action.gesture, action.gaze,
        action.motion_hint, *action.body_or_part_relations,
    ], 500)


def project_plan_to_creative_spec(plan: PromptPlan, creative_spec: dict) -> tuple[dict, list[str]]:
    """Fill only automatic/empty compatibility fields; explicit user controls win."""
    value = json.loads(json.dumps(creative_spec))
    details = prompt_plan_to_creative_details(plan)
    applied: list[str] = []
    for field in ("scene", "composition", "camera"):
        current = value.setdefault(field, {"preset": "auto", "details": ""})
        detail = details[f"{field}_details"]
        if current.get("preset", "auto") == "auto" and not str(current.get("details", "")).strip() and detail:
            current["details"] = detail
            applied.append(field)
    pose = value.setdefault("pose", {"preset": "auto", "details": ""})
    if pose.get("preset", "auto") == "auto" and not str(pose.get("details", "")).strip() and details["pose_details"]:
        pose.update({"preset": "custom", "details": details["pose_details"]})
        applied.append("action_state")
    return value, applied


def _bounded_join(values: list[str], limit: int) -> str:
    result = ""
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        candidate = f"{result}; {value}" if result else value
        if len(candidate) > limit:
            remaining = limit - len(result) - (2 if result else 0)
            if remaining > 0:
                result = f"{result}; {value[:remaining]}" if result else value[:remaining]
            break
        result = candidate
    return result


def _validated_reference_context(value: list[dict] | None) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 4 or any(not isinstance(item, dict) for item in value):
        raise CreativeIntelligenceError("reference_context_invalid", "Reference context is invalid")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode()) > 16 * 1024 or any(
        forbidden in encoded.lower() for forbidden in ("data:image", "base64", "file://")
    ):
        raise CreativeIntelligenceError("reference_context_invalid", "Reference context is invalid")
    return json.loads(encoded)
