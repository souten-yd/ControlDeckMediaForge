from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_VISION_IMAGE_BYTES = 2 * 1024 * 1024
MAX_VISION_SIDE = 768


class VisionInputError(RuntimeError):
    pass


def bounded_vision_image(path: Path) -> bytes:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise VisionInputError("vision image is not decodable") from exc
    image.thumbnail((MAX_VISION_SIDE, MAX_VISION_SIDE), Image.Resampling.LANCZOS)
    return _encode(image)


def vision_data_url(path: Path) -> str:
    encoded = base64.b64encode(bounded_vision_image(path)).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def vision_message(prompt: str, candidate: Path, references: tuple[Path, ...]) -> dict[str, object]:
    if len(references) > 4:
        raise VisionInputError("vision references exceeded their bound")
    content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
    content.append({"type": "image_url", "image_url": {"url": vision_data_url(candidate)}})
    if references:
        content.append({
            "type": "image_url",
            "image_url": {"url": _reference_sheet_data_url(references)},
        })
    return {"role": "user", "content": content}


def _reference_sheet_data_url(paths: tuple[Path, ...]) -> str:
    images: list[Image.Image] = []
    try:
        for path in paths:
            with Image.open(path) as opened:
                image = opened.convert("RGB")
                image.thumbnail((384, 384), Image.Resampling.LANCZOS)
                images.append(image.copy())
    except (OSError, UnidentifiedImageError) as exc:
        raise VisionInputError("vision reference is not decodable") from exc
    columns = 2 if len(images) > 1 else 1
    rows = (len(images) + columns - 1) // columns
    cell_width = max(image.width for image in images)
    cell_height = max(image.height for image in images)
    sheet = Image.new("RGB", (cell_width * columns, cell_height * rows), "white")
    for index, image in enumerate(images):
        x = (index % columns) * cell_width + (cell_width - image.width) // 2
        y = (index // columns) * cell_height + (cell_height - image.height) // 2
        sheet.paste(image, (x, y))
    sheet.thumbnail((MAX_VISION_SIDE, MAX_VISION_SIDE), Image.Resampling.LANCZOS)
    encoded = base64.b64encode(_encode(sheet)).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _encode(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    value = buffer.getvalue()
    if not value or len(value) > MAX_VISION_IMAGE_BYTES:
        raise VisionInputError("vision image exceeded its bound")
    return value
