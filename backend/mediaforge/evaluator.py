from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .semantic_review import bounded_review_image, loopback_origin


SCORE_NAMES = (
    "identity_match",
    "style_match",
    "pose_action_match",
    "scene_match",
    "composition_match",
    "obvious_visual_breakage",
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
            self.creative_plan,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
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
    pass


class CreativeEvaluator(Protocol):
    async def available(self) -> bool: ...

    async def evaluate(
        self,
        path: Path,
        intent: str,
        *,
        creative_plan: dict[str, Any],
        reference_paths: tuple[Path, ...] = (),
    ) -> CreativeScore: ...


class OllamaCreativeEvaluator:
    def __init__(self, origin: str, model: str, *, timeout_sec: float = 120.0):
        self.origin = loopback_origin(origin)
        if not model or len(model) > 200:
            raise ValueError("creative evaluator model must be a bounded non-empty name")
        if timeout_sec <= 0:
            raise ValueError("creative evaluator timeout must be positive")
        self.model = model
        self.timeout_sec = timeout_sec

    async def available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.origin}/api/tags")
                response.raise_for_status()
            models = response.json().get("models", [])
            return any(item.get("name") == self.model for item in models if isinstance(item, dict))
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError):
            return False

    async def evaluate(
        self,
        path: Path,
        intent: str,
        *,
        creative_plan: dict[str, Any],
        reference_paths: tuple[Path, ...] = (),
    ) -> CreativeScore:
        if len(reference_paths) > 4:
            raise CreativeEvaluationError("creative evaluation references exceeded their bound")
        images = [path, *reference_paths]
        encoded = [base64.b64encode(bounded_review_image(item)).decode("ascii") for item in images]
        payload = self.request_payload(encoded, intent, creative_plan)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(f"{self.origin}/api/chat", json=payload)
                response.raise_for_status()
            body = json.loads(response.json()["message"]["content"])
            scores = {name: body[name] for name in SCORE_NAMES}
            if any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100
                   for value in scores.values()):
                raise TypeError("creative evaluator scores are invalid")
            summary = body["summary"]
            if not isinstance(summary, str):
                raise TypeError("creative evaluator summary is invalid")
            return CreativeScore(scores=scores, summary=summary[:300], evaluator=f"ollama:{self.model}")
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, OSError, TypeError) as exc:
            raise CreativeEvaluationError("local creative evaluator failed") from exc

    def request_payload(
        self, images: list[str], intent: str, creative_plan: dict[str, Any]
    ) -> dict[str, Any]:
        plan = json.dumps(creative_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:4000]
        return {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": "1m",
            "format": EVALUATION_SCHEMA,
            "options": {
                "temperature": 0,
                "num_gpu": 0,
                "num_ctx": 4096,
                "num_predict": 512,
            },
            "messages": [{
                "role": "user",
                "content": (
                    "/no_think\n"
                    "The first image is one generated candidate. Later images are identity/style references. "
                    "Score each named criterion from 0 to 100. Higher is better except "
                    "obvious_visual_breakage, where 0 means no visible breakage and 100 means severe breakage. "
                    "Return exactly these scores: identity_match, style_match, pose_action_match, scene_match, "
                    "composition_match, obvious_visual_breakage, plus a short summary. "
                    "Use the intent when a reference is absent. This is advisory ranking only. "
                    f"User intent: {intent}. Creative plan: {plan}"
                ),
                "images": images,
            }],
        }
