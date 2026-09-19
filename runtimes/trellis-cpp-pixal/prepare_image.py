"""Worker-side Pixal foreground framing/compositing and DINO input resize.

Opaque inputs require an explicit background-removal provider; this module does
not download or load one. Camera estimation is separate. No GPU use here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import numpy as np
    from PIL import Image


@dataclass(frozen=True)
class ForegroundFrame:
    image: Image.Image
    original_size: tuple[int, int]
    resized_size: tuple[int, int]
    used_input_alpha: bool
    crop_box: tuple[float, float, float, float]


def frame_foreground(
    image: Image.Image,
    *,
    remove_background: Callable[[Image.Image], Image.Image] | None = None,
    background: tuple[int, int, int] = (0, 0, 0),
) -> ForegroundFrame:
    """Match pinned Pixal preprocess_image, including Pillow crop rounding.

    The provider owns its model/lease/lifetime and receives resized RGB. Empty
    and degenerate masks fail explicitly instead of producing unusable images.
    """
    import numpy as np
    from PIL import Image

    if not isinstance(image, Image.Image):
        raise TypeError("foreground preprocessing requires a decoded PIL image")
    if min(image.size) < 1:
        raise ValueError("foreground input is empty")
    if len(background) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in background):
        raise ValueError("background must contain three integer RGB values in 0..255")
    original_size = image.size
    # Source detects transparency before resizing; preserve that decision even
    # if a tiny transparent region disappears during downsampling.
    has_alpha = image.mode == "RGBA" and not np.all(np.array(image)[:, :, 3] == 255)
    scale = min(1, 1024 / max(image.size))
    if scale < 1:
        size = (int(image.width * scale), int(image.height * scale))
        if min(size) < 1:
            raise ValueError("foreground aspect ratio collapses at the 1024-pixel limit")
        image = image.resize(size, Image.Resampling.LANCZOS)
    if has_alpha:
        output = image
    else:
        if remove_background is None:
            raise ValueError("opaque input requires an explicit background-removal provider")
        output = remove_background(image.convert("RGB"))
        if not isinstance(output, Image.Image) or output.mode != "RGBA" or output.size != image.size:
            raise ValueError("background provider must return RGBA at the resized input extent")
    alpha = np.array(output)[:, :, 3]
    foreground = np.argwhere(alpha > 0.8 * 255)
    if not len(foreground):
        raise ValueError("foreground alpha has no pixels above the Pixal threshold")
    x0, y0 = np.min(foreground[:, 1]), np.min(foreground[:, 0])
    x1, y1 = np.max(foreground[:, 1]), np.max(foreground[:, 0])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    size = int(max(x1 - x0, y1 - y0) * 1.1)
    box = tuple(float(v) for v in (cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2))
    if size // 2 == 0:
        raise ValueError("foreground crop has a degenerate extent")
    framed = np.array(output.crop(box)).astype(np.float32) / 255
    rgb, a = framed[:, :, :3], framed[:, :, 3:4]
    bg = np.array(background, dtype=np.float32) / 255.0
    result = Image.fromarray((np.clip(rgb * a + bg * (1.0 - a), 0, 1) * 255).astype(np.uint8))
    return ForegroundFrame(result, original_size, image.size, bool(has_alpha), box)


def prepare_rgb(image: Image.Image, image_size: int) -> np.ndarray:
    import numpy as np
    from PIL import Image

    if type(image_size) is not int or not 1 <= image_size <= 1024:
        raise ValueError("DINO image size must be between 1 and 1024")
    if not isinstance(image, Image.Image):
        raise TypeError("DINO preprocessing requires a decoded PIL image")
    resized = image.resize((image_size, image_size), Image.Resampling.LANCZOS)
    rgb = np.array(resized.convert("RGB")).astype(np.float32)/255
    return np.ascontiguousarray(rgb.transpose(2, 0, 1))
