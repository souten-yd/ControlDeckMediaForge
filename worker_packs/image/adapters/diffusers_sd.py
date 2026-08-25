"""One adapter for the Stable Diffusion family, loaded only inside the image runtime.

FLUX.2 needed its own adapter because its pipeline class and multi-reference edit
semantics are specific to it. SD 1.5 / SDXL / SD 3 do not: Diffusers already
abstracts them behind AutoPipeline, so one thin adapter covers the family and a
new checkpoint of a known family needs no code.

What is actually family-specific, and therefore what this file is for:

* which pipeline class to instantiate (AutoPipeline resolves it from the config)
* the dtype and offload policy for this hardware
* mapping generate / img2img / inpaint onto one Protocol
* negative prompts and guidance, which FLUX.2 Klein does not take

Nothing here decides geometry: the canvas arrives already resolved. Nothing here
selects a model either; routing stays in core.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PIL import Image

from .base import ImageEditRequest, ImageGenerationRequest, ImageGenerationResult


# 実測していない設定を既定にしない。ここは「この系統をどう読むか」だけを持つ。
_SUPPORTED_DEVICE_MODES = {"full_device", "direct_device_map", "cpu_offload"}


class DiffusersStableDiffusionAdapter:
    """Shared adapter for Diffusers-native Stable Diffusion checkpoints."""

    def __init__(
        self,
        model_path: Path,
        *,
        device_mode: str = "full_device",
        disable_mmap: bool = False,
        negative_prompt: str = "",
        guidance_scale: float = 7.0,
    ):
        if device_mode not in _SUPPORTED_DEVICE_MODES:
            raise ValueError("unsupported image device mode")
        self.model_path = model_path.resolve(strict=True)
        self.device_mode = device_mode
        self.disable_mmap = disable_mmap
        self.negative_prompt = negative_prompt
        self.guidance_scale = guidance_scale
        self.pipeline: Any | None = None
        self.load_sec: float | None = None
        self.last_generation_sec: float | None = None
        self.placement: dict[str, Any] = {}
        self._applied_loras: list[tuple[str, float]] = []

    # ── load ────────────────────────────────────────────────────────────

    def load(self) -> None:
        if self.pipeline is not None:
            return
        import torch
        from diffusers import AutoPipelineForText2Image

        started = time.perf_counter()
        load_options: dict[str, Any] = {
            # fp16 は SD 系の実運用既定。bf16 を使う FLUX とは別系統である。
            "torch_dtype": torch.float16,
            "local_files_only": True,
            # 任意の repository のコードを実行しない。取り込んだ重みが
            # コードを持ち込める経路を開かない。
            "trust_remote_code": False,
        }
        variant = self._detect_variant()
        if variant is not None:
            load_options["variant"] = variant
        if self.disable_mmap:
            load_options["disable_mmap"] = True
        if self.device_mode == "direct_device_map":
            load_options["device_map"] = "cuda"
        pipeline = AutoPipelineForText2Image.from_pretrained(self.model_path, **load_options)
        if self.device_mode == "cpu_offload":
            pipeline.enable_model_cpu_offload()
        elif self.device_mode == "full_device":
            pipeline.to("cuda")
        pipeline.set_progress_bar_config(disable=True)
        torch.cuda.synchronize()
        self.placement = self._inspect_placement(pipeline)
        self.pipeline = pipeline
        self.load_sec = time.perf_counter() - started

    def _detect_variant(self) -> str | None:
        """Ask for the variant that is actually on disk, rather than assuming.

        Measured on real hardware: the catalog deliberately fetches one variant
        per component, and for SD checkpoints that is usually the fp16 one
        (``unet/diffusion_pytorch_model.fp16.safetensors``). Diffusers will not
        find those files unless it is told ``variant="fp16"`` — without it,
        loading fails looking for ``model.safetensors``, a file the catalog
        never downloaded. Reading the directory keeps plain repositories, which
        have no variant suffix at all, working unchanged.
        """
        for suffix in ("fp16", "bf16"):
            if any(self.model_path.rglob(f"*.{suffix}.safetensors")):
                return suffix
        return None

    def _inspect_placement(self, pipeline: Any) -> dict[str, Any]:
        """Record where each component actually landed.

        The worker logs this and the acceptance harness asserts on it. A silent
        fall back to CPU looks like a slow success otherwise.
        """
        devices: dict[str, str] = {}
        for name in ("unet", "transformer", "text_encoder", "text_encoder_2", "vae"):
            component = getattr(pipeline, name, None)
            device = getattr(component, "device", None)
            if device is not None:
                devices[name] = str(device)
        pipeline_device = getattr(pipeline, "device", None)
        if pipeline_device is not None:
            devices["pipeline"] = str(pipeline_device)
        return {
            "component_devices": devices,
            "non_gpu_devices": {
                name: value for name, value in devices.items() if not value.startswith("cuda")
            },
            "offload_hooks": [],
            "non_gpu_map_targets": [],
        }


    # ── LoRA ────────────────────────────────────────────────────────────

    def apply_loras(self, requested: list[dict]) -> list[str]:
        """Lay the requested LoRAs on the loaded pipeline.

        The previous set is removed first. Without that they stack: a second
        generation would carry the first request's LoRAs as well, and the
        difference would look like the model behaving inconsistently rather
        than like a bug.
        """
        from .lora import apply as apply_loras

        assert self.pipeline is not None
        wanted = [(item["id"], float(item["weight"])) for item in requested]
        if self._applied_loras == wanted:
            return [item["id"] for item in requested]
        if self._applied_loras:
            self.pipeline.unload_lora_weights()
            self._applied_loras = []
        if not requested:
            return []
        apply_loras(self.pipeline, requested)
        self._applied_loras = wanted
        return [item["id"] for item in requested]

    # ── generate ────────────────────────────────────────────────────────

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        import torch

        self.load()
        assert self.pipeline is not None
        generator = torch.Generator(device="cuda").manual_seed(request.seed)
        started = time.perf_counter()
        try:
            arguments: dict[str, Any] = dict(
                prompt=request.prompt,
                width=request.width,
                height=request.height,
                num_inference_steps=request.steps,
                guidance_scale=self.guidance_scale,
                generator=generator,
            )
            if self.negative_prompt:
                arguments["negative_prompt"] = self.negative_prompt
            image = self.pipeline(**arguments).images[0].convert("RGBA")
        finally:
            torch.cuda.synchronize()
            if self.device_mode == "cpu_offload":
                torch.cuda.empty_cache()
        self.last_generation_sec = time.perf_counter() - started
        request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        image.save(request.output_path, format="PNG")
        return ImageGenerationResult(output_path=request.output_path, seed=request.seed)

    # ── edit ────────────────────────────────────────────────────────────

    def edit(self, request: ImageEditRequest) -> ImageGenerationResult:
        """Not implemented until it is measured on real hardware.

        Editing is not one behaviour: strict inpaint has a protected-pixel
        guarantee that core validates independently, and outpaint has its own
        invariant. Shipping an untested path that claims those guarantees would
        be worse than not having it, so this fails loudly instead.
        """
        raise NotImplementedError(
            "stable diffusion editing is not measured yet; use the text-to-image path"
        )
