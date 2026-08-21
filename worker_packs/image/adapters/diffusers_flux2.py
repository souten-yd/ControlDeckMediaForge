from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .base import ImageGenerationRequest, ImageGenerationResult


class DiffusersFlux2KleinAdapter:
    """FLUX.2 Klein adapter loaded only inside the heavyweight image runtime."""

    def __init__(self, model_path: Path):
        self.model_path = model_path.resolve(strict=True)
        self.pipeline: Any | None = None
        self.load_sec: float | None = None

    def load(self) -> None:
        if self.pipeline is not None:
            return
        import torch
        from diffusers import Flux2KleinPipeline

        started = time.perf_counter()
        pipeline = Flux2KleinPipeline.from_pretrained(
            self.model_path,
            torch_dtype=torch.bfloat16,
            local_files_only=True,
        )
        pipeline.to("cuda")
        pipeline.set_progress_bar_config(disable=True)
        torch.cuda.synchronize()
        self.pipeline = pipeline
        self.load_sec = time.perf_counter() - started

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        import torch

        self.load()
        assert self.pipeline is not None
        generator = torch.Generator(device="cuda").manual_seed(request.seed)
        result = self.pipeline(
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            num_inference_steps=request.steps,
            guidance_scale=1.0,
            generator=generator,
        )
        image = result.images[0].convert("RGBA")
        request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        image.save(request.output_path, format="PNG")
        return ImageGenerationResult(output_path=request.output_path, seed=request.seed)
