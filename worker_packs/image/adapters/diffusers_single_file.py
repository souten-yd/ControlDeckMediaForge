"""Load a checkpoint distributed as one safetensors file.

Civitai and similar sites ship a single file, not a diffusers repository.
``AutoPipelineForText2Image.from_pretrained`` cannot read that: it looks for
``model_index.json`` and a directory of components, neither of which exists.
``from_single_file`` can, but it has to be told which family the file belongs
to — the file itself does not say.

The family is not guessed from the tensors. Telling SDXL from SD 1.5 means
reading the UNet's cross-attention dimension, and the derivatives people
actually use (Pony, Illustrious, NoobAI) break that reasoning while still
being SDXL. The distribution site states the base model, and that statement
is what is used. A file with no stated family is not loaded, because loading
it with the wrong pipeline produces either a crash or, worse, a picture that
is quietly wrong.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .base import ImageEditRequest, ImageGenerationRequest, ImageGenerationResult

_SUPPORTED_DEVICE_MODES = {"full_device", "direct_device_map", "cpu_offload"}

# 配布元が名乗る base model と、それを読む pipeline クラス。名前は配布元の
# 表記そのままではなく、正規化してから引く。
SINGLE_FILE_PIPELINES = {
    "sd15": "StableDiffusionPipeline",
    "sd20": "StableDiffusionPipeline",
    "sd21": "StableDiffusionPipeline",
    "sdxl": "StableDiffusionXLPipeline",
    "pony": "StableDiffusionXLPipeline",
    "illustrious": "StableDiffusionXLPipeline",
    "noobai": "StableDiffusionXLPipeline",
    "sd35": "StableDiffusion3Pipeline",
    "sd3": "StableDiffusion3Pipeline",
}


class DiffusersSingleFileAdapter:
    """Adapter for one-file checkpoints, chosen by the declared base model."""

    def __init__(
        self,
        model_path: Path,
        *,
        device_mode: str = "full_device",
        disable_mmap: bool = False,
        negative_prompt: str = "",
        guidance_scale: float = 7.0,
        base_model: str = "",
    ):
        if device_mode not in _SUPPORTED_DEVICE_MODES:
            raise ValueError("unsupported image device mode")
        self.model_path = model_path.resolve(strict=True)
        self.device_mode = device_mode
        self.disable_mmap = disable_mmap
        self.negative_prompt = negative_prompt
        self.guidance_scale = guidance_scale
        self.base_model = base_model
        self.pipeline: Any | None = None
        self.load_sec: float | None = None
        self.last_generation_sec: float | None = None
        self.placement: dict[str, Any] = {}

    # ── load ────────────────────────────────────────────────────────────

    def _checkpoint(self) -> Path:
        if self.model_path.is_file():
            return self.model_path
        files = sorted(self.model_path.rglob("*.safetensors"))
        if len(files) != 1:
            # 2 つ以上あるものは、どれが本体か分からない。当てて読むと、
            # VAE や refiner を本体として読み込むことになる。
            raise ValueError("single-file checkpoint is not identifiable")
        return files[0]

    def _pipeline_class(self) -> str:
        name = SINGLE_FILE_PIPELINES.get(normalize_base_model(self.base_model))
        if name is None:
            raise ValueError("checkpoint base model was not declared")
        return name

    def load(self) -> None:
        if self.pipeline is not None:
            return
        import torch
        import diffusers

        started = time.perf_counter()
        pipeline_class = getattr(diffusers, self._pipeline_class())
        options: dict[str, Any] = {
            "torch_dtype": torch.float16,
            # 単一ファイルは構成を持たないので、diffusers は既定の設定を
            # 配布元から取りに行く。手元にあるものだけで読む。
            "local_files_only": True,
            "config": str(self.model_path.parent / "config")
            if (self.model_path.parent / "config").is_dir() else None,
        }
        options = {key: value for key, value in options.items() if value is not None}
        if self.disable_mmap:
            options["disable_mmap"] = True
        pipeline = pipeline_class.from_single_file(str(self._checkpoint()), **options)
        if self.device_mode == "cpu_offload":
            pipeline.enable_model_cpu_offload()
        else:
            pipeline.to("cuda")
        pipeline.set_progress_bar_config(disable=True)
        torch.cuda.synchronize()
        self.placement = self._inspect_placement(pipeline)
        self.pipeline = pipeline
        self.load_sec = time.perf_counter() - started

    def _inspect_placement(self, pipeline: Any) -> dict[str, Any]:
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

    def edit(self, request: ImageEditRequest) -> ImageGenerationResult:
        raise NotImplementedError(
            "single-file checkpoint editing is not measured yet; use the text-to-image path"
        )


def normalize_base_model(value: str) -> str:
    """配布元の表記を、系統を引ける形に揃える。

    Civitai は "SD 1.5"、"SD 1.5 Hyper"、"SDXL 1.0"、"Pony"、"Illustrious"
    のように、同じ系統を何通りにも書く。記号と版を落として先頭で見る。
    """
    folded = "".join(character for character in value.lower() if character.isalnum())
    for prefix, key in (
        ("sd35", "sd35"), ("sd3", "sd3"),
        ("sdxl", "sdxl"), ("pony", "pony"),
        ("illustrious", "illustrious"), ("noobai", "noobai"),
        ("sd15", "sd15"), ("sd20", "sd20"), ("sd21", "sd21"),
        ("sd1", "sd15"), ("sd2", "sd21"),
    ):
        if folded.startswith(prefix):
            return key
    return ""
