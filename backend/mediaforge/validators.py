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
            # 「RGBA である」と「透けている所がある」は別の主張である。
            # 実使用で、重ね合わせ用の資産が RGBA のまま完全不透明で通過し、
            # 背景の上に角の立った四角として乗った。実際の最小 alpha を見る。
            minimum_alpha = image.getchannel("A").getextrema()[0] if mode == "RGBA" else 255
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
        {
            "validator": "image.alpha",
            "status": "passed",
            "mode_has_alpha_channel": True,
            "has_transparency": minimum_alpha < 255,
            "minimum_alpha": minimum_alpha,
        },
    ]
