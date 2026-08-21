from __future__ import annotations

import ctypes
import importlib.metadata
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

from .adapters import DiffusersFlux2KleinAdapter, ImageGenerationRequest


MAX_MESSAGE_BYTES = 1024 * 1024


def _terminate_with_parent() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    if os.getppid() == 1:
        raise RuntimeError("worker parent exited during startup")


def _contained(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value):
        raise ValueError(f"{label} is required")
    resolved_root = root.resolve(strict=True)
    resolved = Path(value).resolve(strict=True)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"{label} is outside the worker boundary")
    return resolved


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


class ImageWorker:
    def __init__(self):
        self.model_root = Path(os.environ["MEDIA_FORGE_MODEL_ROOT"])
        self.work_root = Path(os.environ["MEDIA_FORGE_WORK_ROOT"])
        self.device_mode_override = os.environ.get("MEDIA_FORGE_IMAGE_DEVICE_MODE")
        if self.device_mode_override is not None and self.device_mode_override not in {
            "full_device", "direct_device_map", "cpu_offload"
        }:
            raise ValueError(
                "MEDIA_FORGE_IMAGE_DEVICE_MODE must be full_device, direct_device_map, or cpu_offload"
            )
        disable_mmap = os.environ.get("MEDIA_FORGE_IMAGE_DISABLE_MMAP")
        if disable_mmap is not None and disable_mmap not in {"0", "1"}:
            raise ValueError("MEDIA_FORGE_IMAGE_DISABLE_MMAP must be 0 or 1")
        self.disable_mmap_override = None if disable_mmap is None else disable_mmap == "1"
        self.adapters: dict[str, DiffusersFlux2KleinAdapter] = {}

    def handle(self, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("worker request must be an object")
        model = payload.get("model")
        request = payload.get("request")
        output_dir_value = payload.get("worker_output_dir")
        if not isinstance(model, dict) or not isinstance(request, dict):
            raise ValueError("worker request is missing model or request")
        model_path = _contained(self.model_root, model.get("path"), "model path")
        output_dir = Path(str(output_dir_value)).resolve()
        if not output_dir.is_relative_to(self.work_root.resolve(strict=True)):
            raise ValueError("output directory is outside the worker boundary")
        output_dir.mkdir(mode=0o700, exist_ok=True)
        output_dir = _contained(self.work_root, output_dir, "output directory")
        if model.get("runtime_adapter") != "diffusers.flux2-klein":
            raise ValueError("worker model adapter is unsupported")
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("worker model ID is invalid")
        runtime_options = model.get("runtime_options", {})
        if not isinstance(runtime_options, dict) or set(runtime_options) - {"device_mode", "disable_mmap"}:
            raise ValueError("worker model runtime options are invalid")
        device_mode = self.device_mode_override or runtime_options.get("device_mode", "full_device")
        disable_mmap = (
            self.disable_mmap_override
            if self.disable_mmap_override is not None
            else runtime_options.get("disable_mmap", False)
        )
        if device_mode not in {"full_device", "direct_device_map", "cpu_offload"} or not isinstance(
            disable_mmap, bool
        ):
            raise ValueError("worker model runtime options are invalid")
        constraints = request.get("constraints", {})
        output = request.get("output", {})
        if not isinstance(constraints, dict) or not isinstance(output, dict):
            raise ValueError("worker constraints or output are invalid")
        if output.get("format", "png") != "png":
            raise ValueError("image worker currently emits PNG only")
        width = _integer(constraints.get("width", 1024), "image width")
        height = _integer(constraints.get("height", 1024), "image height")
        steps = _integer(constraints.get("steps", 4), "image steps")
        count = _integer(output.get("count", 1), "image count")
        if not 256 <= width <= 2048 or not 256 <= height <= 2048 or width % 16 or height % 16:
            raise ValueError("image dimensions must be multiples of 16 in the range 256..2048")
        if not 1 <= steps <= 50 or not 1 <= count <= 8:
            raise ValueError("image steps or output count is outside the bounded range")
        prompt = request.get("intent")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("image prompt is required")
        seed = _integer(constraints.get("seed", 0), "image seed")
        if not 0 <= seed <= 2**63 - count:
            raise ValueError("image seed is outside the supported range")
        adapter = self.adapters.get(model_id)
        if adapter is None:
            adapter = DiffusersFlux2KleinAdapter(
                model_path,
                device_mode=device_mode,
                disable_mmap=disable_mmap,
            )
            self.adapters = {model_id: adapter}
        outputs = []
        generation_sec = 0.0
        for index in range(count):
            output_seed = seed + index
            output_path = output_dir / f"output-{index}.png"
            result = adapter.generate(ImageGenerationRequest(
                prompt=prompt,
                width=width,
                height=height,
                steps=steps,
                seed=output_seed,
                output_path=output_path,
            ))
            generation_sec += float(adapter.last_generation_sec or 0)
            outputs.append({
                "path": str(result.output_path),
                "mime_type": "image/png",
                "width": width,
                "height": height,
                "seed": result.seed,
            })
        return {
            "outputs": outputs,
            "model": {
                "id": model_id,
                "version": str(model["version"]),
                "weights_hash": str(model["weights_hash"]),
                "license": str(model["license"]),
                "runtime_adapter": str(model["runtime_adapter"]),
                "runtime_version": importlib.metadata.version("diffusers"),
            },
            "seed": seed,
            "postprocessing": ["pil.convert.rgba"],
            "runtime_metrics": {
                "load_sec": float(adapter.load_sec or 0),
                "generation_sec": generation_sec,
                "device_mode": device_mode,
                "disable_mmap": disable_mmap,
                "placement": adapter.placement,
            },
        }


def main() -> int:
    _terminate_with_parent()
    worker = ImageWorker()
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_MESSAGE_BYTES:
            return 2
        try:
            value = worker.handle(json.loads(raw))
            response = {"ok": True, "result": value}
        except Exception as exc:
            try:
                import torch

                is_oom = isinstance(exc, torch.OutOfMemoryError)
            except ImportError:
                is_oom = False
            response = {
                "ok": False,
                "error": {
                    "code": "resource_oom" if is_oom else "worker_error",
                    "message": str(exc)[:300],
                },
            }
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        if not response["ok"]:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
