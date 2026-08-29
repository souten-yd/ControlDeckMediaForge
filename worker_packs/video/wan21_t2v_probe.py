from __future__ import annotations

"""Local-only, bounded Wan 2.1 T2V 1.3B text-to-video probe.

VACE 版との違いは、参照映像とマスクを持たないことだけである。VACE では
その条件付けを潜在空間へ通す vae.encode が 2 回走り、256x256 5 フレームで
100.2 秒を占めていた（復号 1.2 秒、ノイズ除去 0.22 秒）。公開している用途は
「文章から短い動画を作る」であり、その符号化を必要としない。ここで測るのは
その 1 点である。
"""

import argparse
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any


CANDIDATE_REPOSITORY = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
CANDIDATE_REVISION = "0fad780a534b6463e45facd96134c9f345acfa5b"
PROMPT = (
    "A small orange field robot slowly waves one arm at dusk. Its rectangular blue solar panel, "
    "orange body, green field, and locked camera composition remain stable."
)
NEGATIVE_PROMPT = "blurry, distorted, text, watermark, camera shake, changing subject, extra limbs"
SEED = 260826
FPS = 16


@dataclass(frozen=True)
class ProbePreset:
    width: int
    height: int
    frames: int
    steps: int


PRESETS = {
    "smoke": ProbePreset(width=256, height=256, frames=5, steps=1),
    "candidate-clip": ProbePreset(width=512, height=320, frames=33, steps=30),
    "official-clip": ProbePreset(width=832, height=480, frames=81, steps=30),
}


def _offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


def _contained(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("probe output must stay inside the work root")
    return resolved


def _install_trace(pipeline: Any, torch: Any, sink: dict[str, list[float]]) -> None:
    """呼び出しごとの実時間を数える。GPU は非同期なので測る前後で同期する。"""

    def timed(owner: Any, method: str, label: str) -> None:
        original = getattr(owner, method)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            torch.cuda.synchronize()
            started = time.monotonic()
            try:
                return original(*args, **kwargs)
            finally:
                torch.cuda.synchronize()
                sink.setdefault(label, []).append(time.monotonic() - started)

        setattr(owner, method, wrapper)

    timed(pipeline.vae, "encode", "vae.encode")
    timed(pipeline.vae, "decode", "vae.decode")
    timed(pipeline.transformer, "forward", "transformer.forward")


def _encode_frames(frames: Any, output: Path, preset: ProbePreset) -> None:
    from PIL import Image

    if len(frames) != preset.frames:
        raise RuntimeError(f"Wan T2V returned an unexpected frame count: {len(frames)}")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wan21-t2v-frames-", dir=output.parent) as temporary:
        frame_root = Path(temporary)
        for index, frame in enumerate(frames):
            if not isinstance(frame, Image.Image):
                raise RuntimeError("Wan T2V returned an unreadable frame")
            image = frame.convert("RGB")
            if image.size != (preset.width, preset.height):
                raise RuntimeError("Wan T2V returned an unexpected frame size")
            image.save(frame_root / f"{index:06d}.png", format="PNG")
        completed = subprocess.run(
            [
                "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-framerate", str(FPS), "-i", str(frame_root / "%06d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ],
            check=False,
            capture_output=True,
            timeout=300,
        )
    if completed.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
        output.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg rejected the Wan T2V probe frames")


def _generate(
    snapshot: Path,
    output: Path,
    preset_name: str,
    steps: int,
    traced: bool,
    offload: str,
) -> dict[str, Any]:
    _offline_environment()
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline

    if not torch.cuda.is_available() or torch.version.hip is None:
        raise RuntimeError("Wan T2V probe requires ROCm")
    architecture = str(getattr(torch.cuda.get_device_properties(0), "gcnArchName", ""))
    if architecture != "gfx1201":
        raise RuntimeError("Wan T2V probe requires the target gfx1201 GPU")

    preset = PRESETS[preset_name]
    if steps > 0:
        preset = replace(preset, steps=steps)

    started = time.monotonic()
    # VAE だけ float32。bfloat16 にすると ROCm では逆に遅くなることを実測している。
    vae = AutoencoderKLWan.from_pretrained(
        snapshot, subfolder="vae", torch_dtype=torch.float32, local_files_only=True
    )
    pipeline = WanPipeline.from_pretrained(
        snapshot, vae=vae, torch_dtype=torch.bfloat16, local_files_only=True
    )
    if offload == "model_cpu":
        pipeline.enable_model_cpu_offload(device="cuda:0")
    else:
        pipeline.to("cuda:0")
    load_sec = time.monotonic() - started

    trace: dict[str, list[float]] = {}
    if traced:
        _install_trace(pipeline, torch, trace)

    pass_started = time.monotonic()
    result = pipeline(
        prompt=PROMPT,
        negative_prompt=NEGATIVE_PROMPT,
        width=preset.width,
        height=preset.height,
        num_frames=preset.frames,
        num_inference_steps=preset.steps,
        guidance_scale=5.0,
        generator=torch.Generator(device="cuda:0").manual_seed(SEED),
        output_type="pil",
    )
    generate_sec = time.monotonic() - pass_started
    frames = result.frames[0]
    _encode_frames(frames, output, preset)
    return {
        "candidate_repository": CANDIDATE_REPOSITORY,
        "candidate_revision": CANDIDATE_REVISION,
        "gpu": torch.cuda.get_device_name(0),
        "architecture": architecture,
        "torch": torch.__version__,
        "offload": offload,
        "width": preset.width,
        "height": preset.height,
        "frames": preset.frames,
        "steps": preset.steps,
        "fps": FPS,
        "seed": SEED,
        "load_sec": round(load_sec, 3),
        "generate_sec": round(generate_sec, 3),
        "output_bytes": output.stat().st_size,
        **({"trace_sec": {
            name: {"calls": len(values), "total": round(sum(values), 3)}
            for name, values in trace.items()
        }} if traced else {}),
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=("run",))
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", choices=tuple(PRESETS), default="smoke")
    parser.add_argument("--steps", type=int, default=0)
    parser.add_argument("--offload", choices=("model_cpu", "none"), default="none")
    parser.add_argument("--trace", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    work_root = args.work_root.resolve(strict=True)
    output = _contained(work_root, args.output)
    snapshot = args.snapshot.resolve(strict=True)
    try:
        print(json.dumps(
            _generate(snapshot, output, args.preset, args.steps, args.trace, args.offload),
            sort_keys=True,
        ))
    except Exception:
        output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
