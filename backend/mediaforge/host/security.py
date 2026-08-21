from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException, Request

from ..config import Settings
from .token import ServiceTokenError, read_signing_key, verify_service_token


def require_host_service_headers(headers: Mapping[str, str], settings: Settings) -> dict:
    addon_id = headers.get("X-Control-Deck-Addon-ID", "")
    authorization = headers.get("Authorization", "")
    if addon_id != "media-forge" or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "host_service_token_required"})
    if settings.host_token_key_file is None:
        raise HTTPException(status_code=503, detail={"code": "host_token_verifier_unconfigured"})
    try:
        key = read_signing_key(settings.host_token_key_file)
        return verify_service_token(authorization[7:], signing_key=key)
    except ServiceTokenError as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_host_service_token"}) from exc


def require_host_service(request: Request, settings: Settings) -> dict:
    return require_host_service_headers(request.headers, settings)


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
