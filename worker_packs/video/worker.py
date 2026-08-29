from __future__ import annotations

"""Video worker: text to a short clip, then a normalized MP4.

core はこの実装を import しない。やり取りは行ごとの JSON で、画像 worker と
同じ規約に揃えてある。

実測にもとづく設計（2026-08-29、AMD Radeon AI PRO R9700 / gfx1201）:

* VAE は float32 のまま扱う。bfloat16 は符号化で 2.4 倍、復号で 18 倍遅かった
* 収まっているうちは CPU へ退避させない。退避しても生成は 5% しか変わらず、
  読み込みだけが倍かかる
* 512x320 33 frames 30 steps で生成 144.6 秒。うちノイズ除去 24.2 秒、
  VAE 復号 118.2 秒。条件付けを持つ VACE では同条件で符号化に 100 秒を払っていた
"""

import ctypes
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

from .ffmpeg import NormalizeRequest, VideoToolError, normalize, probe


MAX_MESSAGE_BYTES = 1024 * 1024
ADAPTERS = {"diffusers.wan-t2v"}
MAX_FRAMES = 161
MAX_STEPS = 50
DEFAULT_FPS = 16


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


def _bounded(value: object, label: str, low: int, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


class VideoWorker:
    def __init__(self) -> None:
        self.model_root = Path(os.environ["MEDIA_FORGE_MODEL_ROOT"])
        self.work_root = Path(os.environ["MEDIA_FORGE_WORK_ROOT"])
        self._pipeline: Any = None
        self._pipeline_path: Path | None = None
        self.load_sec = 0.0

    def _load(self, model_path: Path) -> Any:
        """読み込みは 1 度きり。process が生きている間は使い回す。

        コールドで 162.8 秒かかる。要求ごとに払うと、生成そのものより
        支度の方が高くつく。
        """
        if self._pipeline is not None and self._pipeline_path == model_path:
            return self._pipeline
        import torch
        from diffusers import AutoencoderKLWan, WanPipeline

        started = time.monotonic()
        vae = AutoencoderKLWan.from_pretrained(
            model_path, subfolder="vae", torch_dtype=torch.float32, local_files_only=True
        )
        pipeline = WanPipeline.from_pretrained(
            model_path, vae=vae, torch_dtype=torch.bfloat16, local_files_only=True
        )
        pipeline.to("cuda:0")
        self.load_sec = time.monotonic() - started
        self._pipeline = pipeline
        self._pipeline_path = model_path
        return pipeline

    def _write_frames(self, frames: Any, frame_root: Path, width: int, height: int) -> None:
        from PIL import Image

        for index, frame in enumerate(frames):
            if not isinstance(frame, Image.Image):
                raise ValueError("the video runtime returned an unreadable frame")
            image = frame.convert("RGB")
            if image.size != (width, height):
                raise ValueError("the video runtime returned an unexpected frame size")
            image.save(frame_root / f"{index:06d}.png", format="PNG")

    def _assemble(self, frame_root: Path, raw: Path, fps: int) -> None:
        completed = subprocess.run(
            [
                "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-framerate", str(fps), "-i", str(frame_root / "%06d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw),
            ],
            check=False,
            capture_output=True,
            timeout=300,
        )
        if completed.returncode != 0 or not raw.is_file() or raw.stat().st_size <= 0:
            raise VideoToolError("ffmpeg could not assemble the generated frames")

    def handle(self, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("worker request must be an object")
        model = payload.get("model")
        request = payload.get("request")
        if not isinstance(model, dict) or not isinstance(request, dict):
            raise ValueError("worker request is missing model or request")
        if model.get("runtime_adapter") not in ADAPTERS:
            raise ValueError("worker model adapter is unsupported")
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("worker model ID is invalid")
        model_path = _contained(self.model_root, model.get("path"), "model path")

        output_dir = Path(str(payload.get("worker_output_dir"))).resolve()
        if not output_dir.is_relative_to(self.work_root.resolve(strict=True)):
            raise ValueError("output directory is outside the worker boundary")
        output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        output_dir = _contained(self.work_root, output_dir, "output directory")

        constraints = request.get("constraints") or {}
        width = _bounded(constraints.get("width"), "width", 16, 1024)
        height = _bounded(constraints.get("height"), "height", 16, 1024)
        if width % 2 or height % 2:
            raise ValueError("video dimensions must be even")
        frames = _bounded(constraints.get("frames", 33), "frames", 5, MAX_FRAMES)
        steps = _bounded(constraints.get("steps", 30), "steps", 1, MAX_STEPS)
        fps = _bounded(constraints.get("fps", DEFAULT_FPS), "fps", 1, 120)
        seed = _bounded(request.get("seed", 0), "seed", 0, 2**31 - 1)
        prompt = str(request.get("intent") or "").strip()
        if not prompt:
            raise ValueError("video generation needs an intent")
        negative = str(constraints.get("negative_prompt") or "").strip()

        import torch

        pipeline = self._load(model_path)
        started = time.monotonic()
        result = pipeline(
            prompt=prompt,
            negative_prompt=negative or None,
            width=width,
            height=height,
            num_frames=frames,
            num_inference_steps=steps,
            guidance_scale=float(constraints.get("guidance_scale") or 5.0),
            generator=torch.Generator(device="cuda:0").manual_seed(seed),
            output_type="pil",
        )
        generation_sec = time.monotonic() - started
        produced = result.frames[0]
        if len(produced) != frames:
            raise ValueError("the video runtime returned an unexpected frame count")

        output = output_dir / "output-0.mp4"
        with tempfile.TemporaryDirectory(prefix="mediaforge-frames-", dir=output_dir) as temporary:
            frame_root = Path(temporary)
            self._write_frames(produced, frame_root, width, height)
            raw = frame_root / "raw.mp4"
            self._assemble(frame_root, raw, fps)
            # 公開する形は 1 つに揃える。生成器がどう書き出したかを外へ出さない。
            info = normalize(NormalizeRequest(
                source_path=raw,
                output_path=output,
                width=width,
                height=height,
                frame_rate=fps,
                duration_sec=frames / fps,
            ))
        verified = probe(output)
        return {
            "outputs": [{
                "path": str(output),
                "mime_type": "video/mp4",
                "width": verified.width,
                "height": verified.height,
                "duration_sec": verified.duration_sec,
                "frame_rate": verified.frame_rate,
                "frame_count": verified.frame_count,
                "seed": seed,
            }],
            "model": {
                "id": model_id,
                "version": str(model["version"]),
                "weights_hash": str(model["weights_hash"]),
                "license": str(model["license"]),
                "runtime_adapter": str(model["runtime_adapter"]),
                "runtime_version": importlib.metadata.version("diffusers"),
            },
            "seed": seed,
            "postprocessing": ["pil.convert.rgb", "ffmpeg.normalize.mp4"],
            "runtime_metrics": {
                "load_sec": float(self.load_sec),
                "generation_sec": generation_sec,
                "normalized_codec": info.codec,
            },
        }


def main() -> int:
    _terminate_with_parent()
    worker = VideoWorker()
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
