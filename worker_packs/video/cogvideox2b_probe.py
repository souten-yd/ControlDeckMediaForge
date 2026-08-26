from __future__ import annotations

"""Local-only, bounded CogVideoX-2B adoption probe.

This evaluator accepts only the exact pinned local snapshot. It cannot resolve
a repository name or download weights and is not a production adapter.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any


CANDIDATE_REPOSITORY = "zai-org/CogVideoX-2b"
CANDIDATE_REVISION = "1137dacfc2c9c012bed6a0793f4ecf2ca8e7ba01"
PROMPT = "A small orange field robot folds its solar panels at dusk, locked camera."
NEGATIVE_PROMPT = "blurry, distorted, text, watermark, camera shake"
SEED = 260826
FPS = 8


@dataclass(frozen=True)
class ProbePreset:
    width: int
    height: int
    frames: int
    steps: int


PRESETS = {
    # Load/ROCm smoke only. The model's official spatial resolution is retained.
    # Diffusers requires the requested frame count to be divisible by the VAE's
    # temporal compression ratio. The official 49-frame profile is the special
    # 48 generated frames plus its conditioning frame.
    "smoke": ProbePreset(width=720, height=480, frames=8, steps=1),
    # Official frame count, resolution, and inference-step count.
    "official-clip": ProbePreset(width=720, height=480, frames=49, steps=50),
}


def _contained(root: Path, candidate: Path, *, must_exist: bool = False) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=must_exist)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("probe path escapes its allowed root")
    return resolved


def _snapshot(path: Path) -> Path:
    snapshot = path.resolve(strict=True)
    if not snapshot.is_dir() or snapshot.name != CANDIDATE_REVISION:
        raise ValueError("CogVideoX-2B snapshot revision differs from the pinned revision")
    if snapshot.parent.name != "snapshots":
        raise ValueError("CogVideoX-2B snapshot must use a verified Hugging Face cache layout")
    repository = snapshot.parent.parent.resolve(strict=True)
    model_index = (snapshot / "model_index.json").resolve(strict=True)
    if not model_index.is_file() or not model_index.is_relative_to(repository):
        raise ValueError("CogVideoX-2B model index escapes its repository")
    if model_index.stat().st_size > 64 * 1024:
        raise ValueError("CogVideoX-2B model index is unbounded")
    try:
        value = json.loads(model_index.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("CogVideoX-2B model index is unreadable") from exc
    if value.get("_class_name") != "CogVideoXPipeline":
        raise ValueError("CogVideoX-2B snapshot has an unexpected pipeline class")
    return snapshot


def _offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def _load_pipeline(snapshot: Path, torch: Any, pipeline_type: Any) -> Any:
    pipeline = pipeline_type.from_pretrained(
        snapshot,
        dtype=torch.float16,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    pipeline.enable_sequential_cpu_offload(device="cuda:0")
    pipeline.vae.enable_slicing()
    pipeline.vae.enable_tiling()
    return pipeline


def _invoke_pipeline(pipeline: Any, torch: Any, preset: ProbePreset) -> Any:
    generator = torch.Generator(device="cuda:0").manual_seed(SEED)
    result = pipeline(
        prompt=PROMPT,
        negative_prompt=NEGATIVE_PROMPT,
        width=preset.width,
        height=preset.height,
        num_frames=preset.frames,
        num_inference_steps=preset.steps,
        generator=generator,
        output_type="pil",
    )
    return result.frames[0]


def _encode_frames(frames: Any, output: Path, preset: ProbePreset) -> None:
    from PIL import Image

    if len(frames) != preset.frames:
        raise RuntimeError(
            f"CogVideoX-2B returned an unexpected frame count: {len(frames)}"
        )
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cogvideox2b-frames-", dir=output.parent) as temporary:
        frame_root = Path(temporary)
        for index, frame in enumerate(frames):
            if not isinstance(frame, Image.Image):
                raise RuntimeError("CogVideoX-2B returned an unreadable frame")
            image = frame.convert("RGB")
            if image.size != (preset.width, preset.height):
                raise RuntimeError("CogVideoX-2B returned an unexpected frame size")
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
            timeout=120,
        )
    if completed.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
        output.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg rejected the CogVideoX-2B probe frames")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generate(snapshot: Path, output: Path, preset_name: str) -> dict[str, Any]:
    _offline_environment()
    import torch
    from diffusers import CogVideoXPipeline

    if not torch.cuda.is_available() or torch.version.hip is None:
        raise RuntimeError("CogVideoX-2B probe requires ROCm")
    properties = torch.cuda.get_device_properties(0)
    architecture = str(getattr(properties, "gcnArchName", ""))
    if architecture != "gfx1201":
        raise RuntimeError("CogVideoX-2B probe requires the target gfx1201 GPU")

    preset = PRESETS[preset_name]
    started = time.monotonic()
    pipeline = _load_pipeline(snapshot, torch, CogVideoXPipeline)
    loaded_sec = time.monotonic() - started
    generated_started = time.monotonic()
    frames = _invoke_pipeline(pipeline, torch, preset)
    generated_sec = time.monotonic() - generated_started
    _encode_frames(frames, output, preset)
    return {
        "candidate_repository": CANDIDATE_REPOSITORY,
        "candidate_revision": CANDIDATE_REVISION,
        "preset": preset_name,
        "width": preset.width,
        "height": preset.height,
        "frames": preset.frames,
        "steps": preset.steps,
        "fps": FPS,
        "seed": SEED,
        "load_sec": round(loaded_sec, 3),
        "generate_sec": round(generated_sec, 3),
        "elapsed_sec": round(time.monotonic() - started, 3),
        "output_bytes": output.stat().st_size,
        "output_sha256": _sha256(output),
        "torch": torch.__version__,
        "hip": torch.version.hip,
        "gpu": torch.cuda.get_device_name(0),
        "architecture": architecture,
        "dtype": "float16",
        "offload": "sequential_cpu",
        "attention": "pytorch_sdpa",
        "network": "offline",
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=("run",))
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", choices=tuple(PRESETS), default="smoke")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    work_root = args.work_root.resolve(strict=True)
    output = _contained(work_root, args.output)
    snapshot = _snapshot(args.snapshot)
    try:
        print(json.dumps(_generate(snapshot, output, args.preset), sort_keys=True))
    except Exception:
        output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
