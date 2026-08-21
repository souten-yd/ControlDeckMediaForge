from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException, Request

from .client import ControlDeckHostClient, HostApiError, HostIdentity


async def require_host_service_headers(
    headers: Mapping[str, str], host: ControlDeckHostClient,
) -> HostIdentity:
    try:
        return await host.authenticate(headers)
    except HostApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc


async def require_host_service(request: Request, host: ControlDeckHostClient) -> HostIdentity:
    return await require_host_service_headers(request.headers, host)


def reject_host_paths(value: object) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            reject_host_paths(nested)
    elif isinstance(value, list):
        for nested in value:
            reject_host_paths(nested)
    elif isinstance(value, str):
        if value.startswith(("/", "~/", "file:")) or (len(value) >= 3 and value[1] == ":" and value[2] in "\\/"):
            raise HTTPException(status_code=422, detail={"code": "unscoped_host_path"})
