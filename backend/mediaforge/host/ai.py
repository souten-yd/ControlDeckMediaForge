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


@dataclass(frozen=True, slots=True)
class HostAIReleaseResult:
    """Outcome of asking ControlDeck to end this add-on's AI turn.

    ControlDeck stays the authority: it may refuse because its own chat, an
    OpenCode session, or another add-on is still using the shared model. The
    reason is carried through so a later admission failure can say why instead
    of surfacing an anonymous out-of-memory.
    """

    released: bool
    reason: str
    freed_bytes: int = 0


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
                timeout_sec=timeout_seconds + 5,
            )
        except HostApiError as exc:
            raise self._normalize_host_error(exc, capability=capability) from exc
        content = value.get("content")
        returned_capability = value.get("capability")
        if not isinstance(content, str) or returned_capability != capability:
            raise HostAIError("host_ai_invalid_response", "ControlDeck AI response is invalid")
        # Deliberately ignore every other field. Provider/model identity is not
        # part of Media Forge's behavioral contract even if a future Host adds it.
        return HostAIResult(content=content, capability=capability)

    async def release(self, identity: HostIdentity) -> HostAIReleaseResult:
        """Declare that this add-on's AI turn is over.

        This is a request, never a preemption. Media Forge owns the ordering
        (analyze, release, generate) and the failure policy; ControlDeck owns
        the model lifetime and the decision. Ask once — retrying would starve
        the Host's own consumers.
        """
        try:
            value = await self.host._request(  # same-package bounded Add-on Runtime transport
                identity,
                "POST",
                f"/{identity.addon_id}/ai/release",
                json={},
            )
        except HostApiError as exc:
            if exc.status_code == 404:
                # An older Host has no explicit release. That is a known state,
                # not an error: fall through to Broker admission as before.
                return HostAIReleaseResult(released=False, reason="host_release_unsupported")
            if exc.status_code == 403:
                return HostAIReleaseResult(released=False, reason="host_ai_not_granted")
            return HostAIReleaseResult(released=False, reason="host_release_failed")
        released = value.get("released") is True
        reason = value.get("reason")
        freed = value.get("freed_bytes")
        return HostAIReleaseResult(
            released=released,
            reason=str(reason) if isinstance(reason, str) and reason else (
                "released" if released else "host_release_refused"
            ),
            freed_bytes=int(freed) if isinstance(freed, int) and not isinstance(freed, bool) else 0,
        )

    @staticmethod
    def _normalize_host_error(
        exc: HostApiError, *, capability: HostAICapability | None = None
    ) -> HostAIError:
        if exc.status_code == 403:
            return HostAIError("host_ai_not_granted", "ControlDeck AI access is not granted")
        if exc.status_code == 503:
            if capability == "vision.analyze":
                return HostAIError(
                    "vision_analyzer_unavailable",
                    "Requested ControlDeck vision capability is unavailable",
                )
            return HostAIError("host_ai_unavailable", "Requested ControlDeck AI capability is unavailable")
        if exc.code == "host_unreachable":
            return HostAIError("host_ai_unavailable", "ControlDeck AI service is unavailable")
        return HostAIError("host_ai_unavailable", "ControlDeck AI request failed")
