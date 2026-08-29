"""Bounded thumbnail rendering for the embedded workspace.

The workspace transport cannot stream: every preview crosses the socket as
base64. Rendering full-size assets for a grid therefore costs megabytes per
card, so the grid uses these bounded thumbnails instead. Rendering happens once
per (asset, size) and is cached next to the asset store.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import zipfile

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
_PROJECT_ENTRIES = ["asset.glb", "manifest.json", "preview.png"]
_PROJECT_MANIFEST_LIMIT = 1024 * 1024
_PROJECT_PREVIEW_LIMIT = 8 * 1024 * 1024
_PROJECT_TOTAL_LIMIT = 128 * 1024 * 1024


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
    return mime_type in {
        "image/png", "image/jpeg", "image/webp", "application/zip", "video/mp4",
    }


def _render_content(source: Path | io.BytesIO, max_side: int, quality: int) -> tuple[bytes, int, int]:
    with Image.open(source) as image:
        image.load()
        prepared = image.convert("RGBA")
    prepared.thumbnail((max_side, max_side), Image.LANCZOS)
    buffer = io.BytesIO()
    prepared.save(buffer, format="WEBP", quality=quality, method=4)
    return buffer.getvalue(), prepared.width, prepared.height


# 動画 1 本ぶんを一覧へ運ぶことはできない。1 枚目だけを取り出して、
# 以降は静止画と同じ経路に乗せる。worker の FFmpeg 実装は import しない。
# ここが呼ぶのは system の binary であり、配列引数・timeout 付き・出力先は
# 使い捨ての directory の中だけである。
_VIDEO_POSTER_LIMIT = 8 * 1024 * 1024
_VIDEO_POSTER_TIMEOUT_SEC = 20


def _video_poster(source: Path) -> bytes:
    """Take the first frame so a clip can sit in a grid of stills."""
    if source.is_symlink() or not source.is_file():
        raise ThumbnailError()
    with tempfile.TemporaryDirectory(prefix="mediaforge-poster-") as temporary:
        frame = Path(temporary) / "poster.png"
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                    "-i", str(source), "-frames:v", "1", "-f", "image2", str(frame),
                ],
                check=False,
                capture_output=True,
                timeout=_VIDEO_POSTER_TIMEOUT_SEC,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ThumbnailError() from exc
        if completed.returncode != 0 or not frame.is_file():
            raise ThumbnailError()
        if frame.stat().st_size <= 0 or frame.stat().st_size > _VIDEO_POSTER_LIMIT:
            raise ThumbnailError()
        return frame.read_bytes()


def _project_preview(source: Path) -> bytes:
    """Read a validated project preview without extracting archive content."""
    if source.is_symlink() or not source.is_file():
        raise ThumbnailError()
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if [info.filename for info in infos] != _PROJECT_ENTRIES:
                raise ThumbnailError()
            if any(info.is_dir() or info.flag_bits & 0x1 for info in infos):
                raise ThumbnailError()
            if sum(info.file_size for info in infos) > _PROJECT_TOTAL_LIMIT:
                raise ThumbnailError()
            by_name = {info.filename: info for info in infos}
            if by_name["manifest.json"].file_size > _PROJECT_MANIFEST_LIMIT:
                raise ThumbnailError()
            if by_name["preview.png"].file_size > _PROJECT_PREVIEW_LIMIT:
                raise ThumbnailError()
            manifest_content = archive.read("manifest.json")
            preview = archive.read("preview.png")
            manifest = json.loads(manifest_content.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, zipfile.BadZipFile) as exc:
        raise ThumbnailError() from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "media-forge.3d-project@1":
        raise ThumbnailError()
    if manifest.get("profile") != "3d.project.glb":
        raise ThumbnailError()
    preview_record = manifest.get("preview")
    if not isinstance(preview_record, dict) or preview_record != {
        "filename": "preview.png",
        "mime_type": "image/png",
        "size_bytes": len(preview),
        "sha256": hashlib.sha256(preview).hexdigest(),
    }:
        raise ThumbnailError()
    return preview


def render(source: Path, max_side: int, mime_type: str = "image/png") -> Thumbnail:
    """Render within the byte bound, spending quality before resolution."""
    content = b""
    width = height = 0
    try:
        if mime_type == "application/zip":
            preview = _project_preview(source)
        elif mime_type == "video/mp4":
            preview = _video_poster(source)
        else:
            preview = None
    except ThumbnailError:
        raise
    for side in (max_side, *[value for value in _FALLBACK_SIDES if value < max_side]):
        for quality in _QUALITY_LADDER:
            try:
                opened: Path | io.BytesIO = io.BytesIO(preview) if preview is not None else source
                content, width, height = _render_content(opened, side, quality)
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                raise ThumbnailError() from exc
            if len(content) <= THUMBNAIL_BYTE_LIMIT:
                return Thumbnail(MIME_TYPE, width, height, content)
    raise ThumbnailError()


def cached(
    source: Path,
    cache_dir: Path,
    asset_id: str,
    max_side: int,
    mime_type: str = "image/png",
) -> Thumbnail:
    """Return the cached thumbnail, rendering it once on first request."""
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = contained(cache_dir, cache_dir / f"{asset_id}_{max_side}.webp")
    if path.is_file():
        try:
            with Image.open(path) as image:
                return Thumbnail(MIME_TYPE, image.width, image.height, path.read_bytes())
        except (OSError, UnidentifiedImageError) as exc:
            raise ThumbnailError() from exc
    thumbnail = render(source, max_side, mime_type)
    temporary = contained(cache_dir, cache_dir / f".{asset_id}_{max_side}.tmp")
    temporary.write_bytes(thumbnail.content)
    temporary.chmod(0o600)
    temporary.replace(path)
    return thumbnail
