from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops


class WorkerCompositionError(ValueError):
    """An image worker could not construct a bounded edit input or output."""


@dataclass(frozen=True)
class WorkerStrictEditPlan:
    width: int
    height: int
    crop_box: tuple[int, int, int, int]


@dataclass(frozen=True)
class WorkerOutpaintPlan:
    width: int
    height: int
    source_box: tuple[int, int, int, int]


def _rgba(path: Path, label: str) -> Image.Image:
    try:
        with Image.open(path) as opened:
            opened.load()
            if opened.mode != "RGBA":
                raise WorkerCompositionError(f"{label} must be an 8-bit RGBA image")
            return opened.copy()
    except WorkerCompositionError:
        raise
    except (OSError, SyntaxError) as exc:
        raise WorkerCompositionError(f"{label} is not a decodable image") from exc


def editable_mask(path: Path) -> Image.Image:
    mask = _rgba(path, "edit mask")
    luminance = mask.convert("RGB").convert("L")
    return ImageChops.multiply(luminance, mask.getchannel("A"))


def strict_edit_plan(source_path: Path, mask_path: Path) -> WorkerStrictEditPlan:
    source = _rgba(source_path, "source image")
    mask = editable_mask(mask_path)
    if mask.size != source.size:
        raise WorkerCompositionError("edit mask dimensions must match the source image")
    crop_box = mask.getbbox()
    if crop_box is None:
        raise WorkerCompositionError("edit mask must contain at least one editable pixel")
    if mask.histogram()[0] == 0:
        raise WorkerCompositionError("edit mask must leave at least one protected pixel")
    return WorkerStrictEditPlan(width=source.width, height=source.height, crop_box=crop_box)


def compose_strict_edit(
    source_path: Path,
    mask_path: Path,
    generated_patch: Image.Image,
    output_path: Path,
    *,
    patch_box: tuple[int, int, int, int],
) -> None:
    source = _rgba(source_path, "source image")
    mask = editable_mask(mask_path)
    plan = strict_edit_plan(source_path, mask_path)
    left, top, right, bottom = patch_box
    if (
        left < 0
        or top < 0
        or right > plan.width
        or bottom > plan.height
        or left > plan.crop_box[0]
        or top > plan.crop_box[1]
        or right < plan.crop_box[2]
        or bottom < plan.crop_box[3]
    ):
        raise WorkerCompositionError("generated patch does not contain the editable mask")
    patch = generated_patch.convert("RGBA")
    size = (right - left, bottom - top)
    if patch.size != size:
        patch = patch.resize(size, Image.Resampling.LANCZOS)
    candidate = source.copy()
    candidate.paste(patch, (left, top))
    output = source.copy()
    output.paste(candidate, (0, 0), mask)
    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.save(output_path, format="PNG")


def _outpaint_plan(source: Image.Image, width: int, height: int) -> WorkerOutpaintPlan:
    if width < source.width or height < source.height:
        raise WorkerCompositionError("outpaint canvas must contain the complete source image")
    if width == source.width and height == source.height:
        raise WorkerCompositionError("outpaint must expand at least one canvas dimension")
    left = (width - source.width) // 2
    top = (height - source.height) // 2
    return WorkerOutpaintPlan(
        width=width,
        height=height,
        source_box=(left, top, left + source.width, top + source.height),
    )


def outpaint_reference(
    source_path: Path, width: int, height: int
) -> tuple[Image.Image, WorkerOutpaintPlan]:
    source = _rgba(source_path, "outpaint source")
    plan = _outpaint_plan(source, width, height)
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
) -> None:
    source = _rgba(source_path, "outpaint source")
    plan = _outpaint_plan(source, width, height)
    output = generated.convert("RGBA")
    if output.size != (width, height):
        output = output.resize((width, height), Image.Resampling.LANCZOS)
    output.paste(source, plan.source_box[:2])
    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.save(output_path, format="PNG")
