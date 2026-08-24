from __future__ import annotations

import ctypes
import importlib.metadata
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from .adapters import (
    DiffusersFlux2KleinAdapter,
    DiffusersStableDiffusionAdapter,
    ImageEditRequest,
    ImageGenerationRequest,
)


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


# 系統ごとの薄い adapter を名前で選ぶ。FLUX.2 が専用なのは pipeline class と
# 参照編集の意味論が固有だからで、SD 系は Diffusers の AutoPipeline が既に
# 吸収している。新しい checkpoint が既知の系統なら、ここへ足す必要はない。
# 名前で引くのは import 時に固めたクラスではなく module 属性にする。
# 固めると、試験が差し替えた偽 adapter が使われなくなる。
# 鍵はカタログが宣言する runtime_adapter そのものである。別名を置くと、
# 宣言はできるが動かないモデルが一覧に並ぶ。実際そうなっていた:
# "diffusers.stable-diffusion" という誰も宣言しない名前で実装し、
# カタログ側の "diffusers.sdxl" は実装の無いまま出ていた。
ADAPTERS = {
    "diffusers.flux2-klein": "DiffusersFlux2KleinAdapter",
    "diffusers.sdxl": "DiffusersStableDiffusionAdapter",
}


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
        self.adapters: dict[str, Any] = {}

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
        runtime_adapter = model.get("runtime_adapter")
        if runtime_adapter not in ADAPTERS:
            raise ValueError("worker model adapter is unsupported")
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("worker model ID is invalid")
        runtime_options = model.get("runtime_options", {})
        # negative_prompt と guidance_scale は SD 系にだけ効く。FLUX.2 Klein は
        # どちらも取らないので、要求ではなくカタログの側に置く。系統ごとの既定を
        # 利用者やエージェントに書かせない、という routing の方針と同じ扱いである。
        if not isinstance(runtime_options, dict) or set(runtime_options) - {
            "device_mode", "disable_mmap", "negative_prompt", "guidance_scale",
        }:
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
        family_options: dict[str, Any] = {}
        if "negative_prompt" in runtime_options:
            value = runtime_options["negative_prompt"]
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError("worker model runtime options are invalid")
            family_options["negative_prompt"] = value
        if "guidance_scale" in runtime_options:
            value = runtime_options["guidance_scale"]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 30:
                raise ValueError("worker model runtime options are invalid")
            family_options["guidance_scale"] = float(value)
        constraints = request.get("constraints", {})
        output = request.get("output", {})
        if not isinstance(constraints, dict) or not isinstance(output, dict):
            raise ValueError("worker constraints or output are invalid")
        if output.get("format", "png") != "png":
            raise ValueError("image worker currently emits PNG only")
        operation = request.get("operation")
        if operation not in {"image.generate", "image.edit"}:
            raise ValueError("image worker operation is unsupported")
        worker_inputs = payload.get("worker_inputs", {})
        if not isinstance(worker_inputs, dict):
            raise ValueError("worker inputs are invalid")
        source_path: Path | None = None
        mask_path: Path | None = None
        reference_paths: tuple[Path, ...] = ()
        profile_reference_paths: tuple[Path, ...] = ()
        source_size: tuple[int, int] | None = None
        if operation == "image.edit":
            source_path = _contained(self.work_root, worker_inputs.get("source_path"), "source image")
            mask_value = worker_inputs.get("mask_path")
            if mask_value is not None:
                mask_path = _contained(self.work_root, mask_value, "edit mask")
            references_value = worker_inputs.get("reference_paths", [])
            if not isinstance(references_value, list):
                raise ValueError("worker reference images are invalid")
            reference_paths = tuple(
                _contained(self.work_root, value, "reference image")
                for value in references_value
            )
            try:
                with Image.open(source_path) as source:
                    source_size = source.size
            except (OSError, SyntaxError) as exc:
                raise ValueError("source image is not decodable") from exc
        profile_references_value = worker_inputs.get("profile_reference_paths", [])
        if not isinstance(profile_references_value, list):
            raise ValueError("worker profile references are invalid")
        profile_reference_paths = tuple(
            _contained(self.work_root, value, "profile reference image")
            for value in profile_references_value
        )
        if len(profile_reference_paths) > 4:
            raise ValueError("worker profile references exceed the bounded limit")
        width_default = source_size[0] if source_size is not None else 1024
        height_default = source_size[1] if source_size is not None else 1024
        width = _integer(constraints.get("width", width_default), "image width")
        height = _integer(constraints.get("height", height_default), "image height")
        steps = _integer(constraints.get("steps", 4), "image steps")
        count = _integer(output.get("count", 1), "image count")
        strict_edit = constraints.get("strict_edit", False)
        edit_mode = constraints.get("edit_mode", "reference")
        if not isinstance(strict_edit, bool):
            raise ValueError("strict_edit must be a boolean")
        if strict_edit:
            if not 1 <= width <= 2048 or not 1 <= height <= 2048:
                raise ValueError("strict edit dimensions must be in the range 1..2048")
        elif not 256 <= width <= 2048 or not 256 <= height <= 2048 or width % 16 or height % 16:
            raise ValueError("image dimensions must be multiples of 16 in the range 256..2048")
        # Public output count remains capped at eight. Three additional bounded
        # candidates are internal-only for semantic retry selection.
        if not 1 <= steps <= 50 or not 1 <= count <= 11:
            raise ValueError("image steps or output count is outside the bounded range")
        prompt = request.get("intent")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("image prompt is required")
        seed = _integer(constraints.get("seed", 0), "image seed")
        if not 0 <= seed <= 2**63 - count:
            raise ValueError("image seed is outside the supported range")
        adapter = self.adapters.get(model_id)
        if adapter is None:
            # 1 度に 1 つだけ常駐させる。単一 GPU では並べられない。
            adapter = globals()[ADAPTERS[runtime_adapter]](
                model_path,
                device_mode=device_mode,
                disable_mmap=disable_mmap,
                **family_options,
            )
            self.adapters = {model_id: adapter}
        outputs = []
        generation_sec = 0.0
        if operation == "image.edit" and strict_edit and edit_mode != "outpaint" and mask_path is None:
            raise ValueError("strict edit requires an edit mask")
        for index in range(count):
            output_seed = seed + index
            output_path = output_dir / f"output-{index}.png"
            if operation == "image.edit":
                assert source_path is not None
                result = adapter.edit(ImageEditRequest(
                    prompt=prompt,
                    source_path=source_path,
                    mask_path=mask_path,
                    width=width,
                    height=height,
                    steps=steps,
                    seed=output_seed,
                    output_path=output_path,
                    strict_edit=strict_edit,
                    edit_mode=edit_mode,
                    reference_paths=reference_paths + profile_reference_paths,
                ))
            else:
                result = adapter.generate(ImageGenerationRequest(
                    prompt=prompt,
                    width=width,
                    height=height,
                    steps=steps,
                    seed=output_seed,
                    output_path=output_path,
                    reference_paths=profile_reference_paths,
                ))
            generation_sec += float(adapter.last_generation_sec or 0)
            outputs.append({
                "path": str(result.output_path),
                "mime_type": "image/png",
                "width": source_size[0] if strict_edit and edit_mode != "outpaint" and source_size is not None else width,
                "height": source_size[1] if strict_edit and edit_mode != "outpaint" and source_size is not None else height,
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
            "postprocessing": (
                ["pil.convert.rgba", "outpaint.source_pixel_copy"]
                if operation == "image.edit" and edit_mode == "outpaint"
                else ["pil.convert.rgba", "strict_edit.mask_composite", "strict_edit.protected_pixel_copy"]
                if operation == "image.edit" and strict_edit
                else ["pil.convert.rgba"]
            ),
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
