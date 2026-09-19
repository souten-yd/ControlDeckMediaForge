"""Worker-side DINO input resize, after pipeline foreground framing/compositing.

This deliberately does not replace Pixal's background removal or camera model.
The caller supplies a framed image and retains its original unnormalized RGB
for NAF. No pretrained models, network or GPU are used here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from PIL import Image


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
