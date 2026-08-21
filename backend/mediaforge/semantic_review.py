from __future__ import annotations

import base64
from io import BytesIO
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError


REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "accepted": {"type": "boolean"},
        "summary": {"type": "string", "maxLength": 300},
    },
    "required": ["accepted", "summary"],
    "additionalProperties": False,
}


class SemanticReviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class SemanticReviewResult:
    accepted: bool
    summary: str
    reviewer: str


class SemanticReviewer(Protocol):
    async def available(self) -> bool: ...

    async def review(
        self,
        path: Path,
        intent: str,
        *,
        reference_paths: tuple[Path, ...] = (),
    ) -> SemanticReviewResult: ...


def loopback_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("semantic reviewer URL must be a loopback HTTP origin")
    return value.rstrip("/")


class OllamaSemanticReviewer:
    def __init__(self, origin: str, model: str, *, timeout_sec: float = 120.0):
        self.origin = loopback_origin(origin)
        if not model or len(model) > 200:
            raise ValueError("semantic reviewer model must be a bounded non-empty name")
        if timeout_sec <= 0:
            raise ValueError("semantic reviewer timeout must be positive")
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

    async def review(
        self,
        path: Path,
        intent: str,
        *,
        reference_paths: tuple[Path, ...] = (),
    ) -> SemanticReviewResult:
        if len(reference_paths) > 4:
            raise SemanticReviewError("semantic review references exceeded their bound")
        images = [path, *reference_paths]
        encoded = [base64.b64encode(_bounded_review_image(item)).decode("ascii") for item in images]
        payload = self.request_payload(encoded, intent)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(f"{self.origin}/api/chat", json=payload)
                response.raise_for_status()
            body = response.json()
            result = json.loads(body["message"]["content"])
            accepted = result["accepted"]
            summary = result["summary"]
            if not isinstance(accepted, bool) or not isinstance(summary, str):
                raise TypeError("semantic review result has invalid types")
            return SemanticReviewResult(
                accepted=accepted,
                summary=summary[:300],
                reviewer=f"ollama:{self.model}",
            )
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, OSError, TypeError) as exc:
            raise SemanticReviewError("local semantic reviewer failed") from exc

    def request_payload(self, images: list[str], intent: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "stream": False,
            "think": False,
            # Keep the CPU model only long enough for bounded retries; do not
            # retain several GiB of RAM as a standing Media Forge dependency.
            "keep_alive": "1m",
            "format": REVIEW_SCHEMA,
            "options": {"temperature": 0, "num_gpu": 0, "num_ctx": 4096},
            "messages": [{
                "role": "user",
                "content": (
                    "The first image is the generated candidate. Any later images are identity/style references. "
                    "Review whether the candidate visibly satisfies the user's intent and remains consistent "
                    "with those references. "
                    "Judge only semantic content and obvious visual defects; deterministic file "
                    "validation is handled separately. Return accepted=true unless there is a "
                    f"clear mismatch. User intent: {intent}"
                ),
                "images": images,
            }],
        }


def _bounded_review_image(path: Path) -> bytes:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise SemanticReviewError("semantic review image is not decodable") from exc
    image.thumbnail((768, 768), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    value = buffer.getvalue()
    if len(value) > 2 * 1024 * 1024:
        raise SemanticReviewError("semantic review image exceeded its bound")
    return value
