from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .client import ControlDeckHostClient, HostApiError, HostIdentity


HostAICapability = Literal["text.generate", "vision.analyze"]


class HostAIError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class HostAIResult:
    content: str
    capability: HostAICapability


class HostAIGateway:
    """Scoped Media Forge client for ControlDeck-owned AI inference.

    The caller supplies only a logical capability and task payload. Provider,
    runtime, port, model identity, lifecycle and admission remain ControlDeck
    responsibilities. This class intentionally has no provider/model arguments.
    """

    def __init__(self, host: ControlDeckHostClient):
        self.host = host

    async def capabilities(self, identity: HostIdentity) -> dict[HostAICapability, bool]:
        try:
            value = await self.host._request(  # same-package bounded Add-on Runtime transport
                identity,
                "GET",
                f"/{identity.addon_id}/ai/capabilities",
            )
        except HostApiError as exc:
            raise self._normalize_host_error(exc) from exc
        result: dict[HostAICapability, bool] = {
            "text.generate": False,
            "vision.analyze": False,
        }
        for capability in result:
            item = value.get(capability)
            if isinstance(item, dict):
                result[capability] = item.get("available") is True
        return result

    async def available(self, identity: HostIdentity, capability: HostAICapability) -> bool:
        return (await self.capabilities(identity)).get(capability, False)

    async def complete(
        self,
        identity: HostIdentity,
        capability: HostAICapability,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_seconds: int = 120,
    ) -> HostAIResult:
        payload: dict[str, Any] = {
            "capability": capability,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout_seconds": timeout_seconds,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        try:
            value = await self.host._request(  # same-package bounded Add-on Runtime transport
                identity,
                "POST",
                f"/{identity.addon_id}/ai/complete",
                json=payload,
            )
        except HostApiError as exc:
            raise self._normalize_host_error(exc) from exc
        content = value.get("content")
        returned_capability = value.get("capability")
        if not isinstance(content, str) or returned_capability != capability:
            raise HostAIError("host_ai_invalid_response", "ControlDeck AI response is invalid")
        # Deliberately ignore every other field. Provider/model identity is not
        # part of Media Forge's behavioral contract even if a future Host adds it.
        return HostAIResult(content=content, capability=capability)

    @staticmethod
    def _normalize_host_error(exc: HostApiError) -> HostAIError:
        if exc.status_code == 403:
            return HostAIError("host_ai_not_granted", "ControlDeck AI access is not granted")
        if exc.status_code == 503:
            return HostAIError("host_ai_capability_unavailable", "Requested ControlDeck AI capability is unavailable")
        if exc.code == "host_unreachable":
            return HostAIError("host_ai_unavailable", "ControlDeck AI service is unavailable")
        return HostAIError("host_ai_failed", "ControlDeck AI request failed")
