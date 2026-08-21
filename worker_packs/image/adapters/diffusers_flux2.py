from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .base import ImageGenerationRequest, ImageGenerationResult


class DiffusersFlux2KleinAdapter:
    """FLUX.2 Klein adapter loaded only inside the heavyweight image runtime."""

    def __init__(
        self,
        model_path: Path,
        *,
        device_mode: str = "full_device",
        disable_mmap: bool = False,
    ):
        if device_mode not in {"full_device", "direct_device_map", "cpu_offload"}:
            raise ValueError("unsupported image device mode")
        self.model_path = model_path.resolve(strict=True)
        self.device_mode = device_mode
        self.disable_mmap = disable_mmap
        self.pipeline: Any | None = None
        self.load_sec: float | None = None
        self.last_generation_sec: float | None = None

    def load(self) -> None:
        if self.pipeline is not None:
            return
        import torch
        from diffusers import Flux2KleinPipeline

        started = time.perf_counter()
        text_encoder: Any | None = None
        if self.disable_mmap:
            # Diffusers 0.40 forwards disable_mmap to Diffusers components but
            # not to Transformers components. Load Qwen explicitly so half of
            # the pipeline does not silently remain on the slow mmap transfer
            # path (huggingface/diffusers#12599).
            from transformers import Qwen3ForCausalLM

            text_encoder_options: dict[str, Any] = {
                "dtype": torch.bfloat16,
                "local_files_only": True,
                "disable_mmap": True,
            }
            if self.device_mode == "direct_device_map":
                text_encoder_options["device_map"] = "cuda"
            text_encoder = Qwen3ForCausalLM.from_pretrained(
                self.model_path / "text_encoder",
                **text_encoder_options,
            )
        load_options: dict[str, Any] = {
            "torch_dtype": torch.bfloat16,
            "local_files_only": True,
            "disable_mmap": self.disable_mmap,
        }
        if text_encoder is not None:
            load_options["text_encoder"] = text_encoder
        if self.device_mode == "direct_device_map":
            load_options["device_map"] = "cuda"
        pipeline = Flux2KleinPipeline.from_pretrained(self.model_path, **load_options)
        if self.device_mode == "cpu_offload":
            pipeline.enable_model_cpu_offload()
        elif self.device_mode == "full_device":
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
        started = time.perf_counter()
        try:
            result = self.pipeline(
                prompt=request.prompt,
                width=request.width,
                height=request.height,
                num_inference_steps=request.steps,
                guidance_scale=1.0,
                generator=generator,
            )
            image = result.images[0].convert("RGBA")
        finally:
            torch.cuda.synchronize()
            if self.device_mode == "cpu_offload":
                torch.cuda.empty_cache()
        self.last_generation_sec = time.perf_counter() - started
        request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        image.save(request.output_path, format="PNG")
        return ImageGenerationResult(output_path=request.output_path, seed=request.seed)
