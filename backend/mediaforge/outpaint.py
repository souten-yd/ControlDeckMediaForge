from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

from .image_edit import StrictEditError


@dataclass(frozen=True)
class OutpaintPlan:
    width: int
    height: int
    source_box: tuple[int, int, int, int]
    generated_pixels: int


def _source_rgba(path: Path) -> Image.Image:
    try:
        with Image.open(path) as opened:
            opened.load()
            if opened.mode != "RGBA":
                raise StrictEditError("outpaint source must be an 8-bit RGBA image")
            return opened.copy()
    except StrictEditError:
        raise
    except (OSError, SyntaxError) as exc:
        raise StrictEditError("outpaint source is not decodable") from exc


def outpaint_plan(source_path: Path, width: int, height: int) -> OutpaintPlan:
    source = _source_rgba(source_path)
    if width < source.width or height < source.height:
        raise StrictEditError("outpaint canvas must contain the complete source image")
    if width == source.width and height == source.height:
        raise StrictEditError("outpaint must expand at least one canvas dimension")
    left = (width - source.width) // 2
    top = (height - source.height) // 2
    return OutpaintPlan(
        width=width,
        height=height,
        source_box=(left, top, left + source.width, top + source.height),
        generated_pixels=width * height - source.width * source.height,
    )


def outpaint_reference(source_path: Path, width: int, height: int) -> tuple[Image.Image, OutpaintPlan]:
    source = _source_rgba(source_path)
    plan = outpaint_plan(source_path, width, height)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(source, plan.source_box[:2])
    return canvas, plan


def compose_outpaint(
    source_path: Path,
    generated: Image.Image,
    output_path: Path,
    *,
    width: int,
    height: int,
) -> OutpaintPlan:
    source = _source_rgba(source_path)
    plan = outpaint_plan(source_path, width, height)
    output = generated.convert("RGBA")
    if output.size != (width, height):
        output = output.resize((width, height), Image.Resampling.LANCZOS)
    output.paste(source, plan.source_box[:2])
    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.save(output_path, format="PNG")
    return plan


def validate_outpaint(source_path: Path, output_path: Path, *, width: int, height: int) -> dict[str, object]:
    source = _source_rgba(source_path)
    plan = outpaint_plan(source_path, width, height)
    try:
        with Image.open(output_path) as opened:
            opened.load()
            if opened.mode != "RGBA" or opened.size != (width, height):
                raise StrictEditError("outpaint output dimensions or mode changed")
            output_source = opened.crop(plan.source_box)
    except StrictEditError:
        raise
    except (OSError, SyntaxError) as exc:
        raise StrictEditError("outpaint output is not decodable") from exc
    difference = ImageChops.difference(source, output_source)
    if any(channel.getbbox() is not None for channel in difference.split()):
        raise StrictEditError("outpaint changed at least one source pixel")
    return {
        "validator": "image.outpaint.source_pixel_diff",
        "status": "passed",
        "source_pixel_difference": 0,
        "generated_pixels": plan.generated_pixels,
        "source_box": list(plan.source_box),
    }
