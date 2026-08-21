from __future__ import annotations

import time
from itertools import islice
from pathlib import Path
from typing import Any

from PIL import Image

from mediaforge.image_edit import compose_strict_edit, strict_edit_plan

from .base import ImageEditRequest, ImageGenerationRequest, ImageGenerationResult


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
        self.placement: dict[str, Any] = {}

    @staticmethod
    def _hook_uses_offload(hook: object, *, depth: int = 0) -> bool:
        if depth > 4:
            return False
        hook_type = type(hook).__name__.lower()
        if "offload" in hook_type:
            return True
        if getattr(hook, "offload", False) is True:
            return True
        nested = getattr(hook, "hooks", ())
        if not isinstance(nested, (list, tuple)):
            return False
        return any(
            DiffusersFlux2KleinAdapter._hook_uses_offload(item, depth=depth + 1)
            for item in nested[:32]
        )

    @staticmethod
    def _component_device(component: object) -> str | None:
        device = getattr(component, "device", None)
        if device is not None:
            return str(device)
        parameters = getattr(component, "parameters", None)
        if not callable(parameters):
            return None
        try:
            parameter = next(iter(parameters()))
        except (StopIteration, TypeError):
            return None
        value = getattr(parameter, "device", None)
        return str(value) if value is not None else None

    @staticmethod
    def _device_map(component: object) -> dict[str, str]:
        value = getattr(component, "hf_device_map", None)
        if not isinstance(value, dict):
            return {}
        return {
            str(name)[:120]: str(target)[:40]
            for name, target in list(value.items())[:64]
        }

    @classmethod
    def _offload_hook_paths(cls, components: dict[str, object]) -> list[str]:
        found: set[str] = set()
        visited: set[int] = set()
        for component_name, component in components.items():
            candidates: list[tuple[str, object]] = [(component_name, component)]
            named_modules = getattr(component, "named_modules", None)
            if callable(named_modules):
                try:
                    candidates.extend(
                        (f"{component_name}.{name}" if name else component_name, module)
                        for name, module in islice(named_modules(), 8192)
                    )
                except (TypeError, RuntimeError):
                    pass
            for path, module in candidates:
                identity = id(module)
                if identity in visited:
                    continue
                visited.add(identity)
                if cls._hook_uses_offload(getattr(module, "_hf_hook", None)):
                    found.add(path[:200])
                    if len(found) >= 64:
                        return sorted(found)
        return sorted(found)

    def _inspect_placement(self, pipeline: object) -> dict[str, Any]:
        components: dict[str, object] = {"pipeline": pipeline}
        for name in ("text_encoder", "transformer", "vae"):
            component = getattr(pipeline, name, None)
            if component is not None:
                components[name] = component
        devices = {
            name: device
            for name, component in components.items()
            if (device := self._component_device(component)) is not None
        }
        device_maps = {
            name: mapping
            for name, component in components.items()
            if (mapping := self._device_map(component))
        }
        offload_hooks = self._offload_hook_paths(components)
        non_gpu_devices = {
            name: device
            for name, device in devices.items()
            if not device.lower().startswith(("cuda", "hip"))
        }
        non_gpu_map_targets = sorted({
            target
            for mapping in device_maps.values()
            for target in mapping.values()
            if target.lower() in {"cpu", "disk", "meta"}
        })
        return {
            "component_devices": devices,
            "device_maps": device_maps,
            "offload_hooks": offload_hooks,
            "non_gpu_devices": non_gpu_devices,
            "non_gpu_map_targets": non_gpu_map_targets,
        }

    def _verify_direct_placement(self) -> None:
        if self.device_mode != "direct_device_map":
            return
        if (
            self.placement.get("offload_hooks")
            or self.placement.get("non_gpu_devices")
            or self.placement.get("non_gpu_map_targets")
        ):
            raise RuntimeError(
                "direct_device_map unexpectedly selected CPU/disk offload: "
                f"{self.placement}"
            )

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
        self.placement = self._inspect_placement(pipeline)
        self._verify_direct_placement()
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

    @staticmethod
    def _edit_crop_box(
        mask_box: tuple[int, int, int, int],
        width: int,
        height: int,
        *,
        context_pixels: int = 64,
    ) -> tuple[int, int, int, int]:
        left, top, right, bottom = mask_box
        return (
            max(0, left - context_pixels),
            max(0, top - context_pixels),
            min(width, right + context_pixels),
            min(height, bottom + context_pixels),
        )

    @staticmethod
    def _generation_size(width: int, height: int) -> tuple[int, int]:
        return (
            max(256, (width + 15) // 16 * 16),
            max(256, (height + 15) // 16 * 16),
        )

    def edit(self, request: ImageEditRequest) -> ImageGenerationResult:
        import torch

        self.load()
        assert self.pipeline is not None
        try:
            with Image.open(request.source_path) as opened:
                opened.load()
                source = opened.convert("RGBA")
        except (OSError, SyntaxError) as exc:
            raise ValueError("source image is not decodable") from exc

        patch_box = (0, 0, source.width, source.height)
        reference = source
        if request.strict_edit:
            if request.mask_path is None:
                raise ValueError("strict edit requires an edit mask")
            plan = strict_edit_plan(request.source_path, request.mask_path)
            patch_box = self._edit_crop_box(plan.crop_box, plan.width, plan.height)
            reference = source.crop(patch_box)
        generation_size = self._generation_size(reference.width, reference.height)
        if reference.size != generation_size:
            reference = reference.resize(generation_size, Image.Resampling.LANCZOS)

        generator = torch.Generator(device="cuda").manual_seed(request.seed)
        started = time.perf_counter()
        try:
            result = self.pipeline(
                image=reference,
                prompt=request.prompt,
                width=generation_size[0],
                height=generation_size[1],
                num_inference_steps=request.steps,
                guidance_scale=1.0,
                generator=generator,
            )
            generated = result.images[0].convert("RGBA")
        finally:
            torch.cuda.synchronize()
            if self.device_mode == "cpu_offload":
                torch.cuda.empty_cache()
        self.last_generation_sec = time.perf_counter() - started

        if request.strict_edit:
            assert request.mask_path is not None
            compose_strict_edit(
                request.source_path,
                request.mask_path,
                generated,
                request.output_path,
                patch_box=patch_box,
            )
        else:
            output = generated.resize((request.width, request.height), Image.Resampling.LANCZOS)
            request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            output.save(request.output_path, format="PNG")
        return ImageGenerationResult(output_path=request.output_path, seed=request.seed)
