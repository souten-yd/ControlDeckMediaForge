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
DIFFUSERS_ADAPTER = "diffusers.wan2.1-t2v"
NATIVE_H3_ADAPTER = "native.stable-diffusion-cpp-minimax-h3"
NATIVE_WAN22_ADAPTER = "native.wan2.2"
ADAPTERS = {DIFFUSERS_ADAPTER, NATIVE_H3_ADAPTER, NATIVE_WAN22_ADAPTER}
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
        # native の駆動系。pinned build の sd-cli をここから起動する。
        native_root = os.environ.get("MEDIA_FORGE_NATIVE_RUNTIME_ROOT")
        self.native_runtime_root = Path(native_root) if native_root else None
        wan22 = os.environ.get("MEDIA_FORGE_WAN22_SOURCE_ROOT")
        self.wan22_source_root = Path(wan22) if wan22 else None
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

    # MiniMax H3 は 1 つの gguf では動かない。拡散本体・言語モデル・映像 VAE・
    # 音声 VAE の 4 つを渡す。名前は評価が実際に動かしている組み合わせと同じで、
    # 別のものを掴まないよう snapshot の内側に収まることを確かめてから渡す。
    NATIVE_H3_FILES = (
        ("--diffusion-model", "minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf"),
        ("--llm", "qwen3vl_32b_minimax_h3-Q2_K_M.gguf"),
        ("--vae", "vae/minimax_h3_video_vae_fp16.safetensors"),
        ("--audio-vae", "vae/minimax_h3_audio_vae_fp32.safetensors"),
    )

    def _native_command(
        self, model_path: Path, output: Path, prompt: str, negative: str,
        width: int, height: int, frames: int, steps: int, fps: int, seed: int,
    ) -> list[str]:
        if self.native_runtime_root is None:
            raise ValueError("the native media runtime is not configured")
        executable = _contained(
            self.native_runtime_root, self.native_runtime_root / "build" / "bin" / "sd-cli",
            "native runtime executable",
        )
        if not os.access(executable, os.X_OK):
            raise ValueError("the native media runtime is not executable")
        command = [str(executable), "-M", "vid_gen"]
        for flag, relative in self.NATIVE_H3_FILES:
            command += [flag, str(self._native_model_file(model_path, relative))]
        command += [
            "--prompt", prompt,
            "--cfg-scale", "1.0",
            "--width", str(width),
            "--height", str(height),
            "--steps", str(steps),
            "--video-frames", str(frames),
            "--fps", str(fps),
            "--rng", "cpu",
            "--threads", "8",
            # 言語モデルは CPU、拡散と VAE は GPU。評価がこの配分で通っている。
            "--backend", "te=cpu,diffusion=ROCm0,vae=ROCm0",
            "--params-backend", "te=cpu",
            "--mmap",
            "--diffusion-fa",
            "--seed", str(seed),
            "--output", str(output),
        ]
        if negative:
            command += ["--negative-prompt", negative]
        return command

    @staticmethod
    def _native_model_file(snapshot: Path, relative: str) -> Path:
        """snapshot 内の名前を、実体まで辿ってから境界で確かめる。

        Hub の置き方では snapshot の中身は blobs/ への symlink である。
        snapshot だけを境界にすると、正しい重みが「外にある」と判定される。
        境界はその repository の根（snapshots/ と blobs/ を含む階層）に置く。
        """
        candidate = snapshot / relative
        try:
            resolved = candidate.resolve(strict=True)
            repo_root = snapshot.parent.parent.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"model file {relative} is missing") from exc
        if not resolved.is_relative_to(repo_root):
            raise ValueError(f"model file {relative} is outside the model repository")
        return resolved

    @staticmethod
    def _native_env() -> dict[str, str]:
        """駆動系が要る場所を渡す。無いと libomp.so が見つからず起動しない。

        評価が使っているのと同じ設定である。2 つに分けると、片方だけ直して
        もう片方が動かなくなる。
        """
        env = os.environ.copy()
        rocm_libs = "/opt/rocm/lib/llvm/lib:/opt/rocm/lib"
        existing = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = f"{rocm_libs}:{existing}" if existing else rocm_libs
        env["ROCR_VISIBLE_DEVICES"] = "0"
        env["HIP_VISIBLE_DEVICES"] = "0"
        return env

    def _run_native(self, command: list[str], output: Path, timeout_sec: float) -> None:
        completed = subprocess.run(
            command, check=False, capture_output=True, timeout=timeout_sec,
            env=self._native_env(),
        )
        if completed.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
            detail = completed.stderr.decode("utf-8", "replace")[-300:]
            raise VideoToolError(f"the native video runtime failed: {detail}")

    def _generate_wan22(
        self, model: dict[str, Any], model_path: Path, output_dir: Path, output: Path,
        *, prompt: str, negative: str, width: int, height: int,
        frames: int, steps: int, fps: int, seed: int,
    ) -> dict[str, Any]:
        """上流の wan package に作らせる。符号化と生成は別 process のまま。

        text encoder を CPU、生成を GPU に置くために process を分けてある。
        1 つに畳むと両方が同じ device を掴み、5B が載らなくなる。評価が使って
        いる probe をそのまま呼ぶので、評価と本番で 2 通りの起動を持たない。
        """
        if self.wan22_source_root is None:
            raise ValueError("the Wan 2.2 source is not configured")
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="mediaforge-wan22-", dir=output_dir) as temporary:
            work = Path(temporary)
            raw = work / "raw.mp4"
            probe_script = Path(__file__).resolve().parent / "wan_ti2v_probe.py"
            environment = os.environ.copy()
            source = str(self.wan22_source_root)
            existing = environment.get("PYTHONPATH")
            environment["PYTHONPATH"] = f"{source}:{existing}" if existing else source
            rocm_libs = "/opt/rocm/lib/llvm/lib:/opt/rocm/lib"
            libs = environment.get("LD_LIBRARY_PATH")
            environment["LD_LIBRARY_PATH"] = f"{rocm_libs}:{libs}" if libs else rocm_libs
            completed = subprocess.run(
                [
                    sys.executable, str(probe_script), "run",
                    "--snapshot", str(model_path),
                    "--work-root", str(work),
                    "--output", str(raw),
                    # 頼まれた寸法と長さで作る。preset へ丸めると、選んだ長さと
                    # 返ってくる長さが食い違う。preset は下敷きとしてだけ使う。
                    "--preset", "candidate-clip",
                    "--width", str(width), "--height", str(height),
                    "--frames", str(frames), "--steps", str(steps),
                ],
                check=False, capture_output=True, timeout=3600, env=environment,
            )
            if completed.returncode != 0 or not raw.is_file() or raw.stat().st_size <= 0:
                detail = completed.stderr.decode("utf-8", "replace")[-300:]
                raise VideoToolError(f"the Wan 2.2 runtime failed: {detail}")
            generation_sec = time.monotonic() - started
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
                "id": str(model["id"]),
                "version": str(model["version"]),
                "weights_hash": str(model["weights_hash"]),
                "license": str(model["license"]),
                "runtime_adapter": str(model["runtime_adapter"]),
                "runtime_version": importlib.metadata.version("diffusers"),
            },
            "seed": seed,
            "postprocessing": ["ffmpeg.normalize.mp4"],
            "runtime_metrics": {
                "load_sec": 0.0,
                "generation_sec": generation_sec,
                "normalized_codec": info.codec,
            },
        }

    def _generate_native(
        self, model: dict[str, Any], model_path: Path, output_dir: Path, output: Path,
        *, prompt: str, negative: str, width: int, height: int,
        frames: int, steps: int, fps: int, seed: int,
    ) -> dict[str, Any]:
        """sd-cli に作らせ、公開する形へ正規化する。

        駆動系は webm（vp8 + 音声）を書く。MiniMax H3 は音も作るので、
        正規化でそれを落とさない。公開する形は 1 つに揃えるが、中身は捨てない。
        """
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="mediaforge-native-", dir=output_dir) as temporary:
            raw = Path(temporary) / "raw.webm"
            command = self._native_command(
                model_path, raw, prompt, negative, width, height, frames, steps, fps, seed,
            )
            # 打ち切りは呼び出し側が持つ。ここは進まなくなった場合の最後の砦で、
            # 実測（5 フレーム 149 秒）から余裕を見た上限に置く。
            self._run_native(command, raw, timeout_sec=3600)
            generation_sec = time.monotonic() - started
            info = normalize(NormalizeRequest(
                source_path=raw,
                output_path=output,
                width=width,
                height=height,
                frame_rate=fps,
                duration_sec=frames / fps,
                include_audio=True,
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
                "id": str(model["id"]),
                "version": str(model["version"]),
                "weights_hash": str(model["weights_hash"]),
                "license": str(model["license"]),
                "runtime_adapter": str(model["runtime_adapter"]),
                "runtime_version": self._native_runtime_version(),
            },
            "seed": seed,
            "postprocessing": ["ffmpeg.normalize.mp4"],
            "runtime_metrics": {
                "load_sec": 0.0,
                "generation_sec": generation_sec,
                "normalized_codec": info.codec,
            },
        }

    def _native_runtime_version(self) -> str:
        """pinned build がどれかを記録に残す。版が動けば結果も動く。"""
        if self.native_runtime_root is None:
            return "unknown"
        head = self.native_runtime_root / ".git" / "HEAD"
        try:
            return head.read_text(encoding="utf-8").strip()[:40]
        except OSError:
            return "unknown"

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

        adapter = str(model.get("runtime_adapter"))
        output = output_dir / "output-0.mp4"
        if adapter == NATIVE_WAN22_ADAPTER:
            return self._generate_wan22(
                model, model_path, output_dir, output,
                prompt=prompt, negative=negative, width=width, height=height,
                frames=frames, steps=steps, fps=fps, seed=seed,
            )
        if adapter == NATIVE_H3_ADAPTER:
            return self._generate_native(
                model, model_path, output_dir, output,
                prompt=prompt, negative=negative, width=width, height=height,
                frames=frames, steps=steps, fps=fps, seed=seed,
            )

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
