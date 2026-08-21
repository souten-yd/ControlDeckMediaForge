from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import stat
import time
from pathlib import Path
from typing import Any


class ServiceTokenError(ValueError):
    pass


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def read_signing_key(path: Path) -> bytes:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise ServiceTokenError("service token verification key is unavailable") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ServiceTokenError("service token verification key must be a private regular file")
    key = path.read_bytes()
    if len(key) != 32:
        raise ServiceTokenError("service token verification key is invalid")
    return key


def verify_service_token(
    token: str,
    *,
    signing_key: bytes,
    addon_id: str = "media-forge",
    now: int | None = None,
) -> dict[str, Any]:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(signing_key, encoded.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_decode(signature), expected):
            raise ServiceTokenError("service token signature mismatch")
        payload = json.loads(_decode(encoded))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        if isinstance(exc, ServiceTokenError):
            raise
        raise ServiceTokenError("service token is malformed") from exc
    current = int(time.time()) if now is None else int(now)
    if payload.get("aud") != addon_id or payload.get("kind") != "service":
        raise ServiceTokenError("service token scope mismatch")
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise ServiceTokenError("service token subject is invalid")
    if not isinstance(payload.get("iat"), int) or not isinstance(payload.get("exp"), int):
        raise ServiceTokenError("service token timestamps are invalid")
    if payload["iat"] > current + 30 or payload["exp"] <= current or payload["exp"] - payload["iat"] > 600:
        raise ServiceTokenError("service token is expired or has an invalid lifetime")
    return payload
