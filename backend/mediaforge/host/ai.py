from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
from typing import Any, Literal

import httpx

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

    async def complete_streamed(
        self,
        identity: HostIdentity,
        capability: HostAICapability,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_seconds: int = 120,
        max_output_bytes: int = 8192,
    ) -> HostAIResult:
        """Assemble bounded text data over the scoped, cancellable Host SSE API.

        No fallback/retry, partial success, tool execution, or provider selection.
        Both the wire and assembled UTF-8 content are bounded. The absolute
        deadline also closes streams which keep emitting without completing.
        """
        if capability != "text.generate":
            raise ValueError("Host streaming supports text.generate only")
        if type(max_output_bytes) is not int or not 1 <= max_output_bytes <= 65536:
            raise ValueError("invalid Host AI output bound")
        payload: dict[str, Any] = {
            "capability": capability, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, "timeout_seconds": timeout_seconds,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        content: list[str] = []
        output_bytes = 0
        wire_bytes = 0
        buffer = b""
        data: list[bytes] = []
        try:
            async with asyncio.timeout(timeout_seconds + 5):
                async with self.host._client.stream(  # same-package scoped transport
                    "POST", f"/api/v1/addon-runtime/{identity.addon_id}/ai/stream",
                    headers=self.host._headers(identity.authorization, identity.addon_id),
                    json=payload, timeout=timeout_seconds + 5,
                ) as response:
                    if response.status_code >= 400:
                        raise HostApiError("host_request_rejected", "Host AI stream rejected",
                                           status_code=response.status_code)
                    if response.headers.get("content-type", "").split(";")[0] != "text/event-stream":
                        raise HostAIError("host_ai_invalid_response", "Expected Host AI event stream")
                    async for chunk in response.aiter_bytes():
                        wire_bytes += len(chunk)
                        if wire_bytes > 2 * 1024 * 1024:
                            raise HostAIError("host_ai_output_too_large", "Host AI stream is too large")
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.rstrip(b"\r")
                            if line.startswith(b"data:"):
                                data.append(line[5:].lstrip(b" "))
                            elif not line and data:
                                event = json.loads(b"\n".join(data))
                                data.clear()
                                if not isinstance(event, dict):
                                    raise ValueError("invalid SSE event")
                                kind = event.get("type")
                                if kind == "done":
                                    return HostAIResult(content="".join(content), capability=capability)
                                if kind == "error":
                                    raise HostAIError("host_ai_unavailable", "Host AI stream failed")
                                if kind == "usage":
                                    continue
                                if kind != "content" or not isinstance(event.get("content"), str):
                                    raise ValueError("invalid SSE content")
                                text = event["content"]
                                output_bytes += len(text.encode("utf-8"))
                                if output_bytes > max_output_bytes:
                                    raise HostAIError("host_ai_output_too_large", "Host AI output is too large")
                                content.append(text)
        except HostApiError as exc:
            raise self._normalize_host_error(exc, capability=capability) from exc
        except (httpx.HTTPError, TimeoutError) as exc:
            raise HostAIError("host_ai_unavailable", "Host AI stream interrupted") from exc
        except (ValueError, UnicodeError) as exc:
            raise HostAIError("host_ai_invalid_response", "Invalid Host AI event stream") from exc
        raise HostAIError("host_ai_invalid_response", "Host AI stream ended without done")

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
