from __future__ import annotations

import re


OPAQUE_GRANT = re.compile(r"^grant:[A-Za-z0-9._:-]{1,256}$")


def require_grant_id(value: str) -> str:
    if not OPAQUE_GRANT.fullmatch(value):
        raise ValueError("a scoped grant ID is required; host paths are never accepted")
    return value
