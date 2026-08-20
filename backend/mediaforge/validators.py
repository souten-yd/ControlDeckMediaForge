from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_png(path: Path) -> tuple[int, int, list[dict[str, Any]]]:
    with path.open("rb") as stream:
        header = stream.read(33)
    if len(header) < 33 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("worker output is not a valid PNG")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", header[16:26])
    if width < 1 or height < 1:
        raise ValueError("worker output has invalid dimensions")
    if bit_depth != 8 or color_type != 6:
        raise ValueError("worker output must be 8-bit RGBA")
    if path.stat().st_size <= 33:
        raise ValueError("worker output is empty")
    return width, height, [
        {"validator": "image.non_empty", "status": "passed", "size_bytes": path.stat().st_size},
        {"validator": "image.dimensions", "status": "passed", "width": width, "height": height},
        {"validator": "image.mode", "status": "passed", "mode": "RGBA"},
        {"validator": "image.alpha", "status": "passed", "alpha": True},
    ]

