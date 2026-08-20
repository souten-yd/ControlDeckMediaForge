from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_png(path: Path) -> tuple[int, int, list[dict[str, Any]]]:
    with path.open("rb") as stream:
        signature = stream.read(len(PNG_SIGNATURE))
    if path.stat().st_size <= len(PNG_SIGNATURE) or signature != PNG_SIGNATURE:
        raise ValueError("worker output is not a valid PNG")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
    except (OSError, SyntaxError) as exc:
        raise ValueError("worker output is not a decodable PNG") from exc
    if width < 1 or height < 1:
        raise ValueError("worker output has invalid dimensions")
    if mode != "RGBA":
        raise ValueError("worker output must be 8-bit RGBA")
    return width, height, [
        {"validator": "image.non_empty", "status": "passed", "size_bytes": path.stat().st_size},
        {"validator": "image.dimensions", "status": "passed", "width": width, "height": height},
        {"validator": "image.mode", "status": "passed", "mode": mode},
        {"validator": "image.alpha", "status": "passed", "alpha": True},
    ]
