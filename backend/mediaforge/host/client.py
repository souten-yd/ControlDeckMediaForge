from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import time
from typing import Any

import httpx


ADDON_ID = "media-forge"
MAX_JSON_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_GRANT_BYTES = 1024 * 1024 * 1024


class HostApiError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class HostIdentity:
    authorization: str = field(repr=False)
    addon_id: str
    subject: str
    expires_at: int
    granted_capabilities: frozenset[str]


class ControlDeckHostClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_sec: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_sec,
            follow_redirects=False,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def incoming_credentials(headers: Mapping[str, str]) -> tuple[str, str]:
        addon_id = headers.get("X-Control-Deck-Addon-ID", "")
        authorization = headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if addon_id != ADDON_ID or separator != " " or scheme.lower() != "bearer" or not token or " " in token:
            raise HostApiError("host_service_token_required", "ControlDeck service token is required", status_code=401)
        return authorization, addon_id

    async def authenticate(self, headers: Mapping[str, str]) -> HostIdentity:
        authorization, addon_id = self.incoming_credentials(headers)
        value = await self._request_raw(
            "POST",
            "/api/v1/addon-runtime/token/introspect",
            authorization=authorization,
            addon_id=addon_id,
        )
        capabilities = value.get("granted_capabilities")
        expires_at = value.get("expires_at")
        now = int(time.time())
        if (
            value.get("active") is not True
            or value.get("addon_id") != ADDON_ID
            or not isinstance(value.get("subject"), str)
            or not value.get("subject")
            or not isinstance(expires_at, int)
            or expires_at <= now
            or expires_at > now + 630
            or not isinstance(capabilities, list)
            or not all(isinstance(item, str) for item in capabilities)
        ):
            raise HostApiError("invalid_host_service_token", "ControlDeck service token is inactive", status_code=401)
        return HostIdentity(
            authorization=authorization,
            addon_id=addon_id,
            subject=value["subject"],
            expires_at=expires_at,
            granted_capabilities=frozenset(capabilities),
        )

    async def create_or_attach_job(self, identity: HostIdentity, *, title: str) -> dict[str, Any]:
        return await self._request(identity, "POST", f"/{ADDON_ID}/jobs", json={"title": title})

    async def update_job(self, identity: HostIdentity, host_job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(identity, "PATCH", f"/{ADDON_ID}/jobs/{host_job_id}", json=payload)

    async def job_control(self, identity: HostIdentity, host_job_id: str) -> dict[str, Any]:
        return await self._request(identity, "GET", f"/{ADDON_ID}/jobs/{host_job_id}/control")

    async def request_resource(self, identity: HostIdentity, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(identity, "POST", f"/{ADDON_ID}/resources/requests", json=payload)

    async def resource_status(self, identity: HostIdentity, request_id: str) -> dict[str, Any]:
        return await self._request(identity, "GET", f"/{ADDON_ID}/resources/requests/{request_id}")

    async def cancel_resource(self, identity: HostIdentity, request_id: str) -> dict[str, Any]:
        return await self._request(identity, "DELETE", f"/{ADDON_ID}/resources/requests/{request_id}")

    async def lease_action(self, identity: HostIdentity, lease_id: str, action: str) -> dict[str, Any]:
        if action not in {"activate", "renew", "release"}:
            raise ValueError("unsupported lease action")
        return await self._request(identity, "POST", f"/{ADDON_ID}/resources/leases/{lease_id}/{action}")

    async def refresh_lease_identity(self, identity: HostIdentity, lease_id: str) -> HostIdentity:
        value = await self._request(
            identity,
            "POST",
            f"/{ADDON_ID}/resources/leases/{lease_id}/credential/refresh",
        )
        token = value.get("access_token")
        if value.get("token_type") != "Bearer" or not isinstance(token, str) or not token or " " in token:
            raise HostApiError("invalid_host_response", "ControlDeck did not return a refreshed service token")
        refreshed = await self.authenticate({
            "Authorization": f"Bearer {token}",
            "X-Control-Deck-Addon-ID": identity.addon_id,
        })
        if refreshed.addon_id != identity.addon_id or refreshed.subject != identity.subject:
            raise HostApiError("invalid_host_response", "ControlDeck changed the service token scope")
        return refreshed

    async def grant_metadata(self, identity: HostIdentity, grant_id: str) -> dict[str, Any]:
        return await self._request(identity, "GET", f"/{ADDON_ID}/grants/{grant_id}")

    async def grant_content(
        self,
        identity: HostIdentity,
        grant_id: str,
        *,
        max_bytes: int | None = None,
    ) -> bytes:
        path = f"/api/v1/addon-runtime/{ADDON_ID}/grants/{grant_id}/content"
        limit = MAX_GRANT_BYTES if max_bytes is None else max_bytes
        if not isinstance(limit, int) or isinstance(limit, bool) or not 0 < limit <= MAX_GRANT_BYTES:
            raise ValueError("grant content bound is invalid")
        chunks: list[bytes] = []
        total = 0
        try:
            async with self._client.stream(
                "GET",
                path,
                headers=self._headers(identity.authorization, identity.addon_id),
            ) as response:
                if response.status_code >= 400:
                    raise HostApiError(
                        "host_request_rejected",
                        f"ControlDeck Host API rejected the request with HTTP {response.status_code}",
                        status_code=response.status_code,
                    )
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > limit:
                        raise HostApiError(
                            "host_response_too_large",
                            "grant content exceeds the 1 GiB bound",
                            status_code=502,
                        )
                    chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise HostApiError("host_unreachable", "ControlDeck Host API is unreachable") from exc
        return b"".join(chunks)

    async def create_output(self, identity: HostIdentity, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(identity, "POST", f"/{ADDON_ID}/files/outputs", json=payload)

    async def upload_output(self, identity: HostIdentity, output_id: str, content: bytes) -> dict[str, Any]:
        return await self._request(identity, "PUT", f"/{ADDON_ID}/files/outputs/{output_id}/content", content=content)

    async def commit_output(self, identity: HostIdentity, output_id: str) -> dict[str, Any]:
        return await self._request(identity, "POST", f"/{ADDON_ID}/files/outputs/{output_id}/commit")

    async def _request(
        self,
        identity: HostIdentity,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        return await self._request_raw(
            method,
            f"/api/v1/addon-runtime{path}",
            authorization=identity.authorization,
            addon_id=identity.addon_id,
            json=json,
            content=content,
            timeout_sec=timeout_sec,
        )

    async def _request_raw(
        self,
        method: str,
        path: str,
        *,
        authorization: str,
        addon_id: str,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        response = await self._send_raw(
            method,
            path,
            authorization=authorization,
            addon_id=addon_id,
            json=json,
            content=content,
            timeout_sec=timeout_sec,
        )
        if len(response.content) > MAX_JSON_RESPONSE_BYTES:
            raise HostApiError("host_response_too_large", "ControlDeck response exceeds the 4 MiB bound")
        try:
            value = response.json()
        except ValueError as exc:
            raise HostApiError("invalid_host_response", "ControlDeck response is not JSON") from exc
        if not isinstance(value, dict):
            raise HostApiError("invalid_host_response", "ControlDeck response is not an object")
        return value

    async def _send(
        self,
        identity: HostIdentity,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        return await self._send_raw(
            method,
            f"/api/v1/addon-runtime{path}",
            authorization=identity.authorization,
            addon_id=identity.addon_id,
            json=json,
            content=content,
        )

    async def _send_raw(
        self,
        method: str,
        path: str,
        *,
        authorization: str,
        addon_id: str,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        timeout_sec: float | None = None,
    ) -> httpx.Response:
        try:
            request_kwargs: dict[str, Any] = {
                "headers": self._headers(authorization, addon_id),
                "json": json,
                "content": content,
            }
            if timeout_sec is not None:
                request_kwargs["timeout"] = timeout_sec
            response = await self._client.request(method, path, **request_kwargs)
        except httpx.HTTPError as exc:
            raise HostApiError("host_unreachable", "ControlDeck Host API is unreachable") from exc
        if response.status_code >= 400:
            raise HostApiError(
                "host_request_rejected",
                f"ControlDeck Host API rejected the request with HTTP {response.status_code}",
                status_code=response.status_code,
            )
        return response

    @staticmethod
    def _headers(authorization: str, addon_id: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": authorization,
            "X-Control-Deck-Addon-ID": addon_id,
        }
