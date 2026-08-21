from __future__ import annotations

from .base import ImageGenerationRequest, ImageGenerationResult


class NativeImageAdapter:
    """Extension boundary for models that cannot use Diffusers.

    G1 does not ship a native model implementation. Keeping this interface in
    the worker pack prevents a future native runtime from changing core APIs.
    """

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise NotImplementedError("no native image model is installed")
