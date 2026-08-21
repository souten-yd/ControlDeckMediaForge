"""Bounded thumbnail rendering for the embedded workspace.

The workspace transport cannot stream: every preview crosses the socket as
base64. Rendering full-size assets for a grid therefore costs megabytes per
card, so the grid uses these bounded thumbnails instead. Rendering happens once
per (asset, size) and is cached next to the asset store.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .paths import contained

MIN_MAX_SIDE = 64
MAX_MAX_SIDE = 512
DEFAULT_MAX_SIDE = 256
THUMBNAIL_BYTE_LIMIT = 64 * 1024
MIME_TYPE = "image/webp"
# Quality is spent before resolution: a noisy 256px PNG measured 220 KB and had
# to shrink to 128px to fit the bound, while WebP holds 256px at 41 KB.
_QUALITY_LADDER = (80, 65, 50)
_FALLBACK_SIDES = (192, 128, 96)


class ThumbnailError(RuntimeError):
    """The asset cannot be represented as a bounded thumbnail."""

    def __init__(self, code: str = "thumbnail_unavailable", message: str = "thumbnail is unavailable"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Thumbnail:
    mime_type: str
    width: int
    height: int
    content: bytes


def clamp_max_side(value: object) -> int:
    """Accept the workspace's requested size without trusting it."""
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_MAX_SIDE
    return max(MIN_MAX_SIDE, min(MAX_MAX_SIDE, value))


def is_thumbnailable(mime_type: str) -> bool:
    """Kept in one place so future media types extend here, not at call sites."""
    return mime_type in {"image/png", "image/jpeg", "image/webp"}


def _render(source: Path, max_side: int, quality: int) -> tuple[bytes, int, int]:
    with Image.open(source) as image:
        image.load()
        prepared = image.convert("RGBA")
    prepared.thumbnail((max_side, max_side), Image.LANCZOS)
    buffer = io.BytesIO()
    prepared.save(buffer, format="WEBP", quality=quality, method=4)
    return buffer.getvalue(), prepared.width, prepared.height


def render(source: Path, max_side: int) -> Thumbnail:
    """Render within the byte bound, spending quality before resolution."""
    content = b""
    width = height = 0
    for side in (max_side, *[value for value in _FALLBACK_SIDES if value < max_side]):
        for quality in _QUALITY_LADDER:
            try:
                content, width, height = _render(source, side, quality)
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                raise ThumbnailError() from exc
            if len(content) <= THUMBNAIL_BYTE_LIMIT:
                return Thumbnail(MIME_TYPE, width, height, content)
    raise ThumbnailError()


def cached(source: Path, cache_dir: Path, asset_id: str, max_side: int) -> Thumbnail:
    """Return the cached thumbnail, rendering it once on first request."""
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = contained(cache_dir, cache_dir / f"{asset_id}_{max_side}.webp")
    if path.is_file():
        try:
            with Image.open(path) as image:
                return Thumbnail(MIME_TYPE, image.width, image.height, path.read_bytes())
        except (OSError, UnidentifiedImageError) as exc:
            raise ThumbnailError() from exc
    thumbnail = render(source, max_side)
    temporary = contained(cache_dir, cache_dir / f".{asset_id}_{max_side}.tmp")
    temporary.write_bytes(thumbnail.content)
    temporary.chmod(0o600)
    temporary.replace(path)
    return thumbnail
