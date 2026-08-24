from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .asset_brief import AssetBrief, ResolvedLayout, brief_dimensions, brief_rubric
from .creative_intelligence import EvaluationResult, EvaluationScores
from .host.ai import HostAIError, HostAIGateway
from .host.client import HostIdentity
from .vision import VisionInputError, vision_message


EvaluationDimension = Literal[
    "intent",
    "subject_identity",
    "action_state",
    "palette",
    "composition",
    "style",
    "props_clothing",
    "visual_integrity",
]
EVALUATION_DIMENSIONS: tuple[EvaluationDimension, ...] = (
    "intent",
    "subject_identity",
    "action_state",
    "palette",
    "composition",
    "style",
    "props_clothing",
    "visual_integrity",
)
MIN_ACCEPTED_SCORE = 0.55
_ROLE_DIMENSIONS: dict[str, EvaluationDimension] = {
    "identity": "subject_identity",
    "style": "style",
    "pose": "action_state",
    "composition": "composition",
    "clothing": "props_clothing",
    "palette": "palette",
    "prop": "props_clothing",
    "environment": "composition",
}


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_ids: list[str] = Field(min_length=1, max_length=8)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=4)
    intent: str = Field(min_length=1, max_length=8000)
    creative_plan: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_asset_ids(self) -> "EvaluationRequest":
        values = [*self.asset_ids, *self.reference_asset_ids]
        if any(re.fullmatch(r"asset_[0-9a-f]{32}", value) is None for value in values):
            raise ValueError("creative evaluation accepts asset IDs only")
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("creative evaluation candidates must be unique")
        if len(set(self.reference_asset_ids)) != len(self.reference_asset_ids):
            raise ValueError("creative evaluation references must be unique")
        roles = self.creative_plan.get("reference_roles", [])
        if isinstance(roles, list) and any(
            isinstance(item, dict)
            and isinstance(item.get("asset_id"), str)
            and item["asset_id"] not in self.reference_asset_ids
            for item in roles
        ):
            raise ValueError("creative evaluation role references an unavailable asset")
        encoded_plan = json.dumps(
            self.creative_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded_plan) > 16 * 1024:
            raise ValueError("creative evaluation plan exceeds 16384 bytes")
        return self


BoundedIssue = Annotated[str, Field(min_length=1, max_length=300)]


class _EvaluationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scores: EvaluationScores
    issues: list[BoundedIssue] = Field(max_length=32)
    strengths: list[BoundedIssue] = Field(max_length=32)
    retry_suggestions: list[BoundedIssue] = Field(max_length=16)


class CreativeEvaluationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EvaluatedCandidate:
    result: EvaluationResult
    evaluator: str
    relevant_dimensions: tuple[EvaluationDimension, ...]

    @property
    def rank_score(self) -> float:
        values = [
            value
            for name in self.relevant_dimensions
            if (value := getattr(self.result.scores, name)) is not None
        ]
        return round(sum(values) * 100 / len(values), 3) if values else 0.0

    @property
    def summary(self) -> str:
        values = (
            self.result.strengths
            if self.result.accepted_for_requested_constraints
            else self.result.issues
        )
        return "; ".join(values[:2]) or "評価できる説明はありません。"


class CreativeEvaluator(Protocol):
    async def available(self, identity: HostIdentity | None = None) -> bool: ...

    async def evaluate(
        self,
        path: Path,
        intent: str,
        *,
        creative_plan: dict[str, Any],
        reference_paths: tuple[Path, ...] = (),
        identity: HostIdentity | None = None,
        brief: AssetBrief | None = None,
        resolved_layout: ResolvedLayout | None = None,
    ) -> EvaluatedCandidate: ...


def relevant_dimensions(
    creative_plan: dict[str, Any],
    *,
    has_references: bool,
    brief: AssetBrief | None = None,
) -> tuple[EvaluationDimension, ...]:
    selected: set[EvaluationDimension] = {"intent", "visual_integrity"}
    # 用途が要求する観点を足す。「綺麗か」ではなく「その用途に使えるか」を訊く。
    selected.update(
        name for name in brief_dimensions(brief) if name in EVALUATION_DIMENSIONS
    )
    roles = creative_plan.get("reference_roles", [])
    if isinstance(roles, list):
        for value in roles:
            if isinstance(value, dict) and isinstance(value.get("role"), str):
                dimension = _ROLE_DIMENSIONS.get(value["role"])
                if dimension is not None:
                    selected.add(dimension)
    if has_references and len(selected) == 2:
        # Role-less legacy references still ask for broad subject/style consistency.
        selected.update(("subject_identity", "style"))

    def active(section: str) -> bool:
        value = creative_plan.get(section)
        if isinstance(value, str):
            return value not in {"", "auto"}
        if not isinstance(value, dict):
            return False
        return any(
            item not in (None, "", "auto", False, [], {})
            for key, item in value.items()
            if key not in {"label", "version", "prompt"}
        )

    if active("pose") or active("action_state"):
        selected.add("action_state")
    if active("scene") or active("composition") or active("camera"):
        selected.add("composition")
    if active("domain") or active("style"):
        selected.add("style")
    return tuple(name for name in EVALUATION_DIMENSIONS if name in selected)


def _evaluation_schema() -> dict[str, Any]:
    nullable_score = {
        "anyOf": [
            {"type": "number", "minimum": 0, "maximum": 1},
            {"type": "null"},
        ]
    }
    bounded_strings = {
        "type": "array",
        "items": {"type": "string", "minLength": 1, "maxLength": 300},
    }
    return {
        "type": "object",
        "properties": {
            "scores": {
                "type": "object",
                "properties": {name: nullable_score for name in EVALUATION_DIMENSIONS},
                "required": list(EVALUATION_DIMENSIONS),
                "additionalProperties": False,
            },
            "issues": {**bounded_strings, "maxItems": 32},
            "strengths": {**bounded_strings, "maxItems": 32},
            "retry_suggestions": {**bounded_strings, "maxItems": 16},
        },
        "required": ["scores", "issues", "strengths", "retry_suggestions"],
        "additionalProperties": False,
    }


class HostCreativeEvaluator:
    """The one product evaluator for advisory ranking and bounded QA retry."""

    def __init__(self, gateway: HostAIGateway, *, timeout_sec: float = 120.0):
        self.gateway = gateway
        self.timeout_sec = timeout_sec

    async def available(self, identity: HostIdentity | None = None) -> bool:
        if identity is None or "ai.inference" not in identity.granted_capabilities:
            return False
        try:
            return await self.gateway.available(identity, "vision.analyze")
        except HostAIError:
            return False

    async def evaluate(
        self,
        path: Path,
        intent: str,
        *,
        creative_plan: dict[str, Any],
        reference_paths: tuple[Path, ...] = (),
        identity: HostIdentity | None = None,
        brief: AssetBrief | None = None,
        resolved_layout: ResolvedLayout | None = None,
    ) -> EvaluatedCandidate:
        if identity is None or "ai.inference" not in identity.granted_capabilities:
            raise CreativeEvaluationError(
                "host_ai_not_granted", "ControlDeck AI access is not granted"
            )
        dimensions = relevant_dimensions(
            creative_plan, has_references=bool(reference_paths), brief=brief
        )
        plan = json.dumps(
            creative_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )[:4000]
        prompt = (
            "The first image is one generated candidate. The optional second image is a bounded sheet of "
            "references. Evaluate only these requested dimensions: "
            + ", ".join(dimensions)
            + ". Return a 0..1 score for each requested dimension and null for every other score. "
            "visual_integrity means absence of visible breakage, so higher is always better. "
            "List concise issues, strengths, and actionable retry suggestions. Deterministic file and edit "
            "validators already ran and are authoritative; do not claim to override them. "
            f"User intent: {intent}. Creative plan: {plan}"
        )
        rubric = brief_rubric(brief, resolved_layout)
        if rubric:
            # 用途が分かっているなら、単体の美しさではなく用途への適合を訊く。
            prompt = f"{prompt} Judge suitability for this specific use. {rubric}"
        try:
            response = await self.gateway.complete(
                identity,
                "vision.analyze",
                [vision_message(prompt, path, reference_paths)],
                response_format={
                    "type": "json_schema",
                    "name": "mediaforge_unified_evaluation",
                    "schema": _evaluation_schema(),
                    "strict": True,
                },
                max_tokens=1024,
                timeout_seconds=max(1, min(300, int(self.timeout_sec))),
            )
            payload = _EvaluationPayload.model_validate(json.loads(response.content))
            for name in EVALUATION_DIMENSIONS:
                value = getattr(payload.scores, name)
                if (name in dimensions) != (value is not None):
                    raise ValueError("evaluator populated the wrong dimensions")
        except HostAIError as exc:
            code = "vision_result_invalid" if exc.code == "host_ai_invalid_response" else exc.code
            raise CreativeEvaluationError(code, str(exc)) from exc
        except (VisionInputError, json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            raise CreativeEvaluationError(
                "vision_result_invalid", "ControlDeck returned an invalid vision result"
            ) from exc

        accepted = all(
            (getattr(payload.scores, name) or 0.0) >= MIN_ACCEPTED_SCORE
            for name in dimensions
        )
        result = EvaluationResult(
            accepted_for_requested_constraints=accepted,
            scores=payload.scores,
            issues=payload.issues,
            strengths=payload.strengths,
            retry_suggestions=payload.retry_suggestions,
            review_budget_used=1,
        )
        return EvaluatedCandidate(
            result=result,
            evaluator="control-deck:vision.analyze",
            relevant_dimensions=dimensions,
        )
