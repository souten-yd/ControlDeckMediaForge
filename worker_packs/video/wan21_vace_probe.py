from __future__ import annotations

"""Local-only, bounded Wan 2.1 VACE 1.3B image-to-video probe."""

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


CANDIDATE_REPOSITORY = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"
CANDIDATE_REVISION = "ec4d2cb062b548996b179d493fdd05340de702a1"
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


def _contained(root: Path, candidate: Path, *, must_exist: bool = False) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=must_exist)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("probe path escapes its allowed root")
    return resolved


def _snapshot(path: Path) -> Path:
    snapshot = path.resolve(strict=True)
    if not snapshot.is_dir() or snapshot.name != CANDIDATE_REVISION:
        raise ValueError("Wan VACE snapshot revision differs from the pinned revision")
    if snapshot.parent.name != "snapshots":
        raise ValueError("Wan VACE snapshot must use a verified Hugging Face cache layout")
    repository = snapshot.parent.parent.resolve(strict=True)
    model_index = (snapshot / "model_index.json").resolve(strict=True)
    if not model_index.is_file() or not model_index.is_relative_to(repository):
        raise ValueError("Wan VACE model index escapes its repository")
    if model_index.stat().st_size > 64 * 1024:
        raise ValueError("Wan VACE model index is unbounded")
    try:
        value = json.loads(model_index.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Wan VACE model index is unreadable") from exc
    if value.get("_class_name") != "WanVACEPipeline":
        raise ValueError("Wan VACE snapshot has an unexpected pipeline class")
    return snapshot


def _offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def _load_pipeline(snapshot: Path, torch: Any, vae_type: Any, pipeline_type: Any, scheduler_type: Any) -> Any:
    vae = vae_type.from_pretrained(
        snapshot,
        subfolder="vae",
        dtype=torch.float32,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    pipeline = pipeline_type.from_pretrained(
        snapshot,
        vae=vae,
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    pipeline.scheduler = scheduler_type.from_config(pipeline.scheduler.config, flow_shift=3.0)
    pipeline.enable_model_cpu_offload(device="cuda:0")
    pipeline.vae.enable_slicing()
    pipeline.vae.enable_tiling()
    return pipeline


def _source_image(preset: ProbePreset) -> Any:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (preset.width, preset.height), (238, 143, 92))
    draw = ImageDraw.Draw(image)
    horizon = preset.height * 3 // 5
    draw.rectangle((0, horizon, preset.width, preset.height), fill=(62, 105, 55))
    body = (
        preset.width * 3 // 8,
        preset.height * 9 // 20,
        preset.width * 5 // 8,
        preset.height * 4 // 5,
    )
    draw.rounded_rectangle(body, radius=max(4, preset.width // 64), fill=(221, 91, 26))
    panel = (
        preset.width // 4,
        preset.height * 7 // 20,
        preset.width * 3 // 4,
        preset.height // 2,
    )
    draw.rectangle(panel, fill=(31, 91, 145), outline=(215, 235, 245), width=max(2, preset.width // 128))
    draw.ellipse(
        (
            preset.width * 7 // 16,
            preset.height * 23 // 40,
            preset.width * 9 // 16,
            preset.height * 27 // 40,
        ),
        fill=(245, 216, 83),
    )
    return image


def _conditioning(preset: ProbePreset) -> tuple[list[Any], list[Any]]:
    from PIL import Image

    source = _source_image(preset)
    video = [source]
    video.extend([Image.new("RGB", source.size, (128, 128, 128))] * (preset.frames - 1))
    mask = [Image.new("L", source.size, 0)]
    mask.extend([Image.new("L", source.size, 255)] * (preset.frames - 1))
    return video, mask


def _invoke_pipeline(pipeline: Any, torch: Any, preset: ProbePreset) -> Any:
    video, mask = _conditioning(preset)
    result = pipeline(
        video=video,
        mask=mask,
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
    return result.frames[0]


def _encode_frames(frames: Any, output: Path, preset: ProbePreset) -> None:
    from PIL import Image

    if len(frames) != preset.frames:
        raise RuntimeError(f"Wan VACE returned an unexpected frame count: {len(frames)}")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wan21-vace-frames-", dir=output.parent) as temporary:
        frame_root = Path(temporary)
        for index, frame in enumerate(frames):
            if not isinstance(frame, Image.Image):
                raise RuntimeError("Wan VACE returned an unreadable frame")
            image = frame.convert("RGB")
            if image.size != (preset.width, preset.height):
                raise RuntimeError("Wan VACE returned an unexpected frame size")
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
        raise RuntimeError("ffmpeg rejected the Wan VACE probe frames")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generate(snapshot: Path, output: Path, preset_name: str) -> dict[str, Any]:
    _offline_environment()
    import torch
    from diffusers import AutoencoderKLWan, WanVACEPipeline
    from diffusers.schedulers import UniPCMultistepScheduler

    if not torch.cuda.is_available() or torch.version.hip is None:
        raise RuntimeError("Wan VACE probe requires ROCm")
    properties = torch.cuda.get_device_properties(0)
    architecture = str(getattr(properties, "gcnArchName", ""))
    if architecture != "gfx1201":
        raise RuntimeError("Wan VACE probe requires the target gfx1201 GPU")

    preset = PRESETS[preset_name]
    started = time.monotonic()
    pipeline = _load_pipeline(snapshot, torch, AutoencoderKLWan, WanVACEPipeline, UniPCMultistepScheduler)
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
        "transformer_dtype": "bfloat16",
        "vae_dtype": "float32",
        "offload": "model_cpu",
        "attention": "pytorch_sdpa",
        "network": "offline",
        "conditioning": "first_frame_mask",
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
