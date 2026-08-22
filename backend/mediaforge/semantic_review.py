from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .host.ai import HostAIError, HostAIGateway
from .host.client import HostIdentity
from .vision import VisionInputError, vision_message


REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "accepted": {"type": "boolean"},
        "summary": {"type": "string", "maxLength": 300},
    },
    "required": ["accepted", "summary"],
    "additionalProperties": False,
}


class _ReviewPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    accepted: bool
    summary: str = Field(max_length=300)


class SemanticReviewError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SemanticReviewResult:
    accepted: bool
    summary: str
    reviewer: str


class SemanticReviewer(Protocol):
    async def available(self, identity: HostIdentity | None = None) -> bool: ...

    async def review(
        self,
        path: Path,
        intent: str,
        *,
        reference_paths: tuple[Path, ...] = (),
        identity: HostIdentity | None = None,
    ) -> SemanticReviewResult: ...


class HostSemanticReviewer:
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

    async def review(
        self,
        path: Path,
        intent: str,
        *,
        reference_paths: tuple[Path, ...] = (),
        identity: HostIdentity | None = None,
    ) -> SemanticReviewResult:
        if identity is None or "ai.inference" not in identity.granted_capabilities:
            raise SemanticReviewError("host_ai_not_granted", "ControlDeck AI access is not granted")
        prompt = (
            "The first image is the generated candidate. The optional second image is a sheet of "
            "identity/style references. Review whether the candidate visibly satisfies the user's intent "
            "and remains consistent with those references. Judge only semantic content and obvious visual "
            "defects; deterministic file validation is handled separately. Return accepted=true unless "
            f"there is a clear mismatch. User intent: {intent}"
        )
        try:
            result = await self.gateway.complete(
                identity,
                "vision.analyze",
                [vision_message(prompt, path, reference_paths)],
                response_format={
                    "type": "json_schema",
                    "name": "mediaforge_semantic_review",
                    "schema": REVIEW_SCHEMA,
                    "strict": True,
                },
                max_tokens=512,
                timeout_seconds=max(1, min(300, int(self.timeout_sec))),
            )
            payload = _ReviewPayload.model_validate(json.loads(result.content))
        except HostAIError as exc:
            code = "vision_result_invalid" if exc.code == "host_ai_invalid_response" else exc.code
            raise SemanticReviewError(code, str(exc)) from exc
        except (VisionInputError, json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise SemanticReviewError(
                "vision_result_invalid", "ControlDeck returned an invalid vision result"
            ) from exc
        return SemanticReviewResult(payload.accepted, payload.summary, "control-deck:vision.analyze")
