from __future__ import annotations

import re
from pathlib import Path

from .client import ControlDeckHostClient, HostApiError, HostIdentity


OPAQUE_GRANT = re.compile(r"^grant:[A-Za-z0-9._:-]{1,256}$")


class GrantContentTooLarge(ValueError):
    pass


def require_grant_id(value: str) -> str:
    if not OPAQUE_GRANT.fullmatch(value):
        raise ValueError("a scoped grant ID is required; host paths are never accepted")
    return value


async def read_grant(
    client: ControlDeckHostClient,
    identity: HostIdentity,
    grant_id: str,
    *,
    max_bytes: int | None = None,
) -> tuple[dict, bytes]:
    scoped = require_grant_id(grant_id)
    metadata = await client.grant_metadata(identity, scoped)
    size = metadata.get("size")
    if max_bytes is not None and (not isinstance(size, int) or size < 0 or size > max_bytes):
        raise GrantContentTooLarge("ControlDeck read grant exceeds the caller's content bound")
    try:
        content = await client.grant_content(identity, scoped, max_bytes=max_bytes)
    except HostApiError as exc:
        if exc.code == "host_response_too_large":
            raise GrantContentTooLarge("ControlDeck read grant exceeds the caller's content bound") from exc
        raise
    if metadata.get("kind") != "read" or metadata.get("size") != len(content):
        raise ValueError("ControlDeck read grant metadata does not match its content")
    return metadata, content


async def commit_file(
    client: ControlDeckHostClient,
    identity: HostIdentity,
    *,
    host_job_id: str,
    grant_id: str,
    source: Path,
    filename: str,
    mime_type: str,
    sha256: str,
) -> dict:
    scoped = require_grant_id(grant_id)
    content = source.read_bytes()
    created = await client.create_output(identity, {
        "job_id": host_job_id,
        "grant_id": scoped,
        "filename": filename,
        "size": len(content),
        "sha256": sha256,
        "content_type": mime_type,
    })
    output_id = created.get("output_id")
    if not isinstance(output_id, str) or not output_id:
        raise ValueError("ControlDeck did not return an output ID")
    await client.upload_output(identity, output_id, content)
    return await client.commit_output(identity, output_id)
