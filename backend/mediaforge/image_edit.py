from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops


class StrictEditError(ValueError):
    """A deterministic strict-edit precondition or invariant failed."""


@dataclass(frozen=True)
class StrictEditPlan:
    width: int
    height: int
    editable_pixels: int
    crop_box: tuple[int, int, int, int]


def _rgba(path: Path, label: str) -> Image.Image:
    try:
        with Image.open(path) as image:
            image.load()
            if image.mode != "RGBA":
                raise StrictEditError(f"{label} must be an 8-bit RGBA image")
            return image.copy()
    except StrictEditError:
        raise
    except (OSError, SyntaxError) as exc:
        raise StrictEditError(f"{label} is not a decodable image") from exc


def editable_mask(path: Path) -> Image.Image:
    mask = _rgba(path, "edit mask")
    luminance = mask.convert("RGB").convert("L")
    return ImageChops.multiply(luminance, mask.getchannel("A"))


def strict_edit_plan(source_path: Path, mask_path: Path) -> StrictEditPlan:
    source = _rgba(source_path, "source image")
    mask = editable_mask(mask_path)
    if mask.size != source.size:
        raise StrictEditError("edit mask dimensions must match the source image")
    bbox = mask.getbbox()
    if bbox is None:
        raise StrictEditError("edit mask must contain at least one editable pixel")
    editable_pixels = source.width * source.height - mask.histogram()[0]
    if editable_pixels == source.width * source.height:
        raise StrictEditError("edit mask must leave at least one protected pixel")
    return StrictEditPlan(
        width=source.width,
        height=source.height,
        editable_pixels=editable_pixels,
        crop_box=bbox,
    )


def compose_strict_edit(
    source_path: Path,
    mask_path: Path,
    generated_patch: Image.Image,
    output_path: Path,
    *,
    patch_box: tuple[int, int, int, int] | None = None,
) -> StrictEditPlan:
    source = _rgba(source_path, "source image")
    mask = editable_mask(mask_path)
    plan = strict_edit_plan(source_path, mask_path)
    effective_box = patch_box or plan.crop_box
    left, top, right, bottom = effective_box
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
        raise StrictEditError("generated patch does not contain the editable mask")
    crop_width = right - left
    crop_height = bottom - top
    patch = generated_patch.convert("RGBA")
    if patch.size != (crop_width, crop_height):
        patch = patch.resize((crop_width, crop_height), Image.Resampling.LANCZOS)
    candidate = source.copy()
    candidate.paste(patch, effective_box[:2])
    generated_layer = source.copy()
    generated_layer.paste(candidate, (0, 0), mask)

    # Re-copy protected pixels from the immutable source. This is deliberately
    # redundant with masked paste: the final invariant is true by construction
    # even if a Pillow behavior changes elsewhere in the pipeline.
    protected = ImageChops.invert(mask)
    generated_layer.paste(source, (0, 0), protected)
    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    generated_layer.save(output_path, format="PNG")
    return plan


def validate_strict_edit(source_path: Path, mask_path: Path, output_path: Path) -> dict[str, object]:
    source = _rgba(source_path, "source image")
    output = _rgba(output_path, "strict edit output")
    mask = editable_mask(mask_path)
    plan = strict_edit_plan(source_path, mask_path)
    if output.size != source.size:
        raise StrictEditError("strict edit output dimensions changed")

    protected_mask = ImageChops.invert(mask.point(lambda value: 255 if value > 0 else 0))
    difference = ImageChops.difference(source, output)
    protected_rgba = Image.merge("RGBA", (protected_mask,) * 4)
    protected_difference = ImageChops.multiply(difference, protected_rgba)
    if any(channel.getbbox() is not None for channel in protected_difference.split()):
        raise StrictEditError("strict edit changed at least one protected pixel")
    return {
        "validator": "image.strict_edit.unmasked_pixel_diff",
        "status": "passed",
        "protected_pixel_difference": 0,
        "editable_pixels": plan.editable_pixels,
    }
