"""Qwen-Image-2.1 through a separately pinned, local Vulkan sd.cpp build."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

from .base import ImageEditRequest, ImageGenerationRequest, ImageGenerationResult


class NativeQwenImage21Adapter:
    RUNTIME_COMMIT = "6dcb5bbd4278aa8f6d851f7515e87555f8e757b7"
    FILES = (
        ("--diffusion-model", "qwen_image_2.1-Q8_0.gguf"),
        ("--llm", "Qwen3VL-8B-Instruct-Q4_K_M.gguf"),
        ("--vae", "vae/qwen_image_2.1_vae_bf16.safetensors"),
    )

    def __init__(
        self, model_path: Path, *, device_mode: str = "full_device",
        disable_mmap: bool = False, guidance_scale: float = 1.0,
        **_options: object,
    ) -> None:
        if device_mode == "cpu":
            raise ValueError("Qwen native generation requires a Vulkan GPU lease")
        self.model_path = Path(model_path)
        self.disable_mmap = disable_mmap
        self.guidance_scale = guidance_scale
        self.load_sec = 0.0
        self.last_generation_sec: float | None = None
        self.quantization_metrics = {
            "text_encoder_quantization": "gguf.q4_k_m",
            "transformer_quantization": "gguf.q8_0",
        }
        self.placement: dict[str, object] = {
            "component_devices": {"text_encoder": "Vulkan0", "diffusion": "Vulkan0", "vae": "Vulkan0"},
            "device_maps": {}, "offload_hooks": [],
            "non_gpu_devices": {}, "non_gpu_map_targets": [],
        }

    @property
    def runtime_version(self) -> str:
        return self.RUNTIME_COMMIT

    def _model_file(self, relative: str) -> Path:
        resolved = (self.model_path / relative).resolve(strict=True)
        boundary = self.model_path.parent.parent.resolve(strict=True)
        if not resolved.is_relative_to(boundary) or not resolved.is_file():
            raise ValueError("native Qwen weight is outside its model repository")
        return resolved

    def _runtime(self) -> tuple[Path, dict[str, str]]:
        configured = os.environ.get("MEDIA_FORGE_NATIVE_VULKAN_RUNTIME_ROOT")
        if not configured:
            raise ValueError("the native Vulkan runtime is not configured")
        root = Path(configured).resolve(strict=True)
        executable = (root / "build/bin/sd-cli").resolve(strict=True)
        profile_path = (root / "runtime.json").resolve(strict=True)
        if not executable.is_relative_to(root) or not profile_path.is_relative_to(root):
            raise ValueError("the native Vulkan runtime escapes its root")
        profile = json.loads(profile_path.read_text())
        if profile.get("commit") != self.RUNTIME_COMMIT or profile.get("backend") != "vulkan":
            raise ValueError("the native Vulkan runtime has the wrong version or backend")
        index = profile.get("vulkan_device_index")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 32:
            raise ValueError("the native Vulkan runtime has no verified device mapping")
        broker_device = profile.get("broker_device_id")
        if not isinstance(broker_device, str) or not broker_device or os.environ.get("MEDIA_FORGE_GPU_DEVICE_ID") != broker_device:
            raise ValueError("the native Vulkan device does not match the granted GPU")
        if not os.access(executable, os.X_OK):
            raise ValueError("the native Vulkan runtime is not executable")
        with executable.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != profile.get("binary_sha256"):
            raise ValueError("the native Vulkan runtime checksum does not match")
        environment = os.environ.copy()
        environment["GGML_VK_VISIBLE_DEVICES"] = str(index)
        devices = subprocess.run(
            [str(executable), "--list-devices"], env=environment,
            capture_output=True, text=True, check=False, timeout=30,
        )
        expected = "Vulkan0\t" + str(profile.get("device_name", ""))
        if devices.returncode or expected not in devices.stdout.splitlines():
            raise ValueError("the configured Vulkan device is unavailable or changed")
        return executable, environment

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if request.reference_paths:
            raise ValueError("native Qwen reference generation has not been accepted")
        if (not 256 <= request.width <= 1024 or not 256 <= request.height <= 1024
                or request.width % 32 or request.height % 32):
            raise ValueError("native Qwen dimensions must be multiples of 32 within 256..1024")
        budget = int(os.environ.get("MEDIA_FORGE_VRAM_BUDGET_BYTES", "0"))
        if budget < 19297214464 + 1024**3:
            raise ValueError("native Qwen generation requires an admitted VRAM budget")
        executable, environment = self._runtime()
        command = [str(executable), "-M", "img_gen"]
        for flag, relative in self.FILES:
            command.extend((flag, str(self._model_file(relative))))
        command.extend((
            "--backend", "Vulkan0", "--max-vram", str((budget - 512 * 1024**2) / 1024**3),
            "--diffusion-fa", "--cfg-scale", str(self.guidance_scale),
            "--sampling-method", "euler", "--steps", str(request.steps),
            "-W", str(request.width), "-H", str(request.height), "--seed", str(request.seed),
            "-t", "4", "--prompt", request.prompt, "--output", str(request.output_path),
        ))
        if not self.disable_mmap:
            command.append("--mmap")
        request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        started = time.perf_counter()
        child = Path(__file__).resolve().parents[1] / "native_child.py"
        completed = subprocess.run(
            [sys.executable, str(child), str(os.getpid()), *command],
            capture_output=True, env=environment, check=False,
        )
        self.last_generation_sec = time.perf_counter() - started
        if completed.returncode != 0 or not request.output_path.is_file():
            raise ValueError(f"native Qwen generation failed (exit {completed.returncode})")
        with Image.open(request.output_path) as opened:
            opened.load()
            if opened.format != "PNG" or opened.mode != "RGBA" or opened.size != (request.width, request.height):
                raise ValueError("native Qwen returned an invalid RGBA image")
        return ImageGenerationResult(request.output_path, request.seed)

    def edit(self, request: ImageEditRequest) -> ImageGenerationResult:
        raise ValueError("native Qwen editing has not been accepted")
