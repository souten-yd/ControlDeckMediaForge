from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .host.ai import HostAIError, HostAIGateway
from .host.client import HostIdentity
from .vision import VisionInputError, vision_message


SCORE_NAMES = (
    "identity_match", "style_match", "pose_action_match", "scene_match",
    "composition_match", "obvious_visual_breakage",
)
EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        **{name: {"type": "integer", "minimum": 0, "maximum": 100} for name in SCORE_NAMES},
        "summary": {"type": "string", "maxLength": 300},
    },
    "required": [*SCORE_NAMES, "summary"],
    "additionalProperties": False,
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
        encoded_plan = json.dumps(
            self.creative_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded_plan) > 16 * 1024:
            raise ValueError("creative evaluation plan exceeds 16384 bytes")
        return self


@dataclass(frozen=True)
class CreativeScore:
    scores: dict[str, int]
    summary: str
    evaluator: str

    @property
    def rank_score(self) -> float:
        positive = sum(self.scores[name] for name in SCORE_NAMES[:-1]) / 5
        return round(positive - self.scores["obvious_visual_breakage"] * 0.5, 3)


class CreativeEvaluationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


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
    ) -> CreativeScore: ...


class HostCreativeEvaluator:
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
    ) -> CreativeScore:
        if identity is None or "ai.inference" not in identity.granted_capabilities:
            raise CreativeEvaluationError("host_ai_not_granted", "ControlDeck AI access is not granted")
        plan = json.dumps(
            creative_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )[:4000]
        prompt = (
            "The first image is one generated candidate. The optional second image is a sheet of identity/style "
            "references. Score each named criterion from 0 to 100. Higher is better except "
            "obvious_visual_breakage, where 0 means no visible breakage and 100 means severe breakage. "
            "Return exactly the requested scores plus a short summary. Use the intent when a reference is absent. "
            f"This is advisory ranking only. User intent: {intent}. Creative plan: {plan}"
        )
        try:
            result = await self.gateway.complete(
                identity,
                "vision.analyze",
                [vision_message(prompt, path, reference_paths)],
                response_format={
                    "type": "json_schema",
                    "name": "mediaforge_creative_evaluation",
                    "schema": EVALUATION_SCHEMA,
                    "strict": True,
                },
                max_tokens=512,
                timeout_seconds=max(1, min(300, int(self.timeout_sec))),
            )
            body = json.loads(result.content)
            scores = {name: body[name] for name in SCORE_NAMES}
            summary = body["summary"]
            if any(
                not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100
                for value in scores.values()
            ):
                raise TypeError("creative evaluator scores are invalid")
            if not isinstance(summary, str) or len(summary) > 300:
                raise TypeError("creative evaluator summary is invalid")
        except HostAIError as exc:
            code = "vision_result_invalid" if exc.code == "host_ai_invalid_response" else exc.code
            raise CreativeEvaluationError(code, str(exc)) from exc
        except (VisionInputError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise CreativeEvaluationError(
                "vision_result_invalid", "ControlDeck returned an invalid vision result"
            ) from exc
        return CreativeScore(scores=scores, summary=summary, evaluator="control-deck:vision.analyze")
