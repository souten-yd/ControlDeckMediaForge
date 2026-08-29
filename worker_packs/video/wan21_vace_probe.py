from __future__ import annotations

"""Local-only, bounded Wan 2.1 VACE 1.3B image-to-video probe."""

import argparse
from dataclasses import dataclass, replace
import gc
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


def _load_pipeline(
    snapshot: Path,
    torch: Any,
    vae_type: Any,
    pipeline_type: Any,
    scheduler_type: Any,
    text_encoder_type: Any,
    tokenizer_type: Any,
    transformer_type: Any,
    offload: str,
    vae_memory: str,
    vae_dtype: str,
) -> tuple[Any, Any, Any]:
    vae = vae_type.from_pretrained(
        snapshot,
        subfolder="vae",
        dtype=torch.float32 if vae_dtype == "float32" else torch.bfloat16,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    scheduler = scheduler_type.from_pretrained(
        snapshot,
        subfolder="scheduler",
        local_files_only=True,
    )
    scheduler = scheduler_type.from_config(scheduler.config, flow_shift=3.0)
    tokenizer = tokenizer_type.from_pretrained(
        snapshot,
        subfolder="tokenizer",
        local_files_only=True,
    )
    text_encoder = text_encoder_type.from_pretrained(
        snapshot,
        subfolder="text_encoder",
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    text_encoder.to("cuda:0")
    prompt_pipeline = pipeline_type(
        tokenizer=tokenizer,
        text_encoder=text_encoder,
        vae=vae,
        scheduler=scheduler,
        transformer=None,
    )
    prompt_embeds, negative_prompt_embeds = prompt_pipeline.encode_prompt(
        prompt=PROMPT,
        negative_prompt=NEGATIVE_PROMPT,
        do_classifier_free_guidance=True,
        num_videos_per_prompt=1,
        max_sequence_length=128,
        device=torch.device("cuda:0"),
        dtype=torch.bfloat16,
    )
    prompt_pipeline.register_modules(text_encoder=None, tokenizer=None)
    del prompt_pipeline, text_encoder, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    transformer = transformer_type.from_pretrained(
        snapshot,
        subfolder="transformer",
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        local_files_only=True,
    )
    pipeline = pipeline_type(
        tokenizer=None,
        text_encoder=None,
        vae=vae,
        scheduler=scheduler,
        transformer=transformer,
    )
    # 34.2GB のカードに 1.3B を載せるのに CPU へ退避させる必要は無い。退避は
    # 毎 step ごとに CPU と GPU を往復するので、収まっているときは値段だけが残る。
    # どちらが速いかは測って決める。既定は従来どおり退避する。
    if offload == "model_cpu":
        pipeline.enable_model_cpu_offload(device="cuda:0")
    else:
        pipeline.to("cuda:0")
    # タイリングとスライシングは VRAM を節約するために小片へ分けて逐次処理する。
    # メモリと引き換えに速度を捨てる設定であり、収まっているなら代金だけが残る。
    # 実測: 256x256 5 フレームの固定費が 101.7 秒あり、1 step の限界費用 0.19 秒に
    # 対して桁が違っていた。効いているのが本当にここかを測って決める。
    if vae_memory == "tiled":
        pipeline.vae.enable_slicing()
        pipeline.vae.enable_tiling()
    return pipeline, prompt_embeds, negative_prompt_embeds


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
    arm_width = max(5, preset.width // 48)
    draw.line(
        (
            body[0],
            preset.height * 3 // 5,
            preset.width * 5 // 16,
            preset.height * 7 // 10,
        ),
        fill=(194, 72, 19),
        width=arm_width,
    )
    draw.line(
        (
            body[2],
            preset.height * 3 // 5,
            preset.width * 11 // 16,
            preset.height * 11 // 20,
        ),
        fill=(194, 72, 19),
        width=arm_width,
    )
    wheel_radius = max(7, preset.width // 40)
    for center_x in (preset.width * 7 // 16, preset.width * 9 // 16):
        draw.ellipse(
            (
                center_x - wheel_radius,
                body[3] - wheel_radius,
                center_x + wheel_radius,
                body[3] + wheel_radius,
            ),
            fill=(44, 47, 53),
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


def _install_trace(pipeline: Any, torch: Any, sink: dict[str, list[float]]) -> None:
    """呼び出しごとの実時間を数える。GPU は非同期なので、測る前に同期する。

    同期しないと、待ち時間が次の呼び出しへずれて記録され、どこが重いのかが
    そのぶん動いてしまう。
    """

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


def _invoke_pipeline(
    pipeline: Any,
    torch: Any,
    preset: ProbePreset,
    prompt_embeds: Any,
    negative_prompt_embeds: Any,
) -> Any:
    video, mask = _conditioning(preset)
    result = pipeline(
        video=video,
        mask=mask,
        prompt_embeds=prompt_embeds,
        negative_prompt_embeds=negative_prompt_embeds,
        width=preset.width,
        height=preset.height,
        num_frames=preset.frames,
        num_inference_steps=preset.steps,
        guidance_scale=5.0,
        max_sequence_length=128,
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


def _generate(
    snapshot: Path, output: Path, preset_name: str, offload: str, steps: int = 0,
    vae_memory: str = "tiled",
    repeat: int = 1,
    traced: bool = False,
    vae_dtype: str = "float32",
) -> dict[str, Any]:
    _offline_environment()
    import torch
    from diffusers import AutoencoderKLWan, WanVACEPipeline, WanVACETransformer3DModel
    from diffusers.schedulers import UniPCMultistepScheduler
    from transformers import AutoTokenizer, UMT5EncoderModel

    if not torch.cuda.is_available() or torch.version.hip is None:
        raise RuntimeError("Wan VACE probe requires ROCm")
    properties = torch.cuda.get_device_properties(0)
    architecture = str(getattr(properties, "gcnArchName", ""))
    if architecture != "gfx1201":
        raise RuntimeError("Wan VACE probe requires the target gfx1201 GPU")

    preset = PRESETS[preset_name]
    if steps > 0:
        preset = replace(preset, steps=steps)
    started = time.monotonic()
    pipeline, prompt_embeds, negative_prompt_embeds = _load_pipeline(
        snapshot,
        torch,
        AutoencoderKLWan,
        WanVACEPipeline,
        UniPCMultistepScheduler,
        UMT5EncoderModel,
        AutoTokenizer,
        WanVACETransformer3DModel,
        offload,
        vae_memory,
        vae_dtype,
    )
    loaded_sec = time.monotonic() - started
    # どこで時間が消えているかは、外から見ていても分からない。VAE の符号化・
    # 復号と transformer の呼び出しを数えて、固定費の在処を名指しする。
    trace: dict[str, list[float]] = {}
    if traced:
        _install_trace(pipeline, torch, trace)
    # 同じ process で 2 回目を測ると、初回だけの支度（HIP kernel の用意など）を
    # 恒常的な費用と取り違えずに済む。長く生きる worker が払うのは 2 回目の方である。
    passes: list[float] = []
    frames = None
    for _ in range(max(repeat, 1)):
        pass_started = time.monotonic()
        frames = _invoke_pipeline(pipeline, torch, preset, prompt_embeds, negative_prompt_embeds)
        passes.append(round(time.monotonic() - pass_started, 3))
    generated_started = time.monotonic() - passes[-1]
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
        "vae_dtype": vae_dtype,
        "offload": offload,
        "vae_memory": vae_memory,
        "pass_sec": passes,
        **({"trace_sec": {
            name: {"calls": len(values), "total": round(sum(values), 3),
                   "slowest": round(max(values), 3)}
            for name, values in trace.items()
        }} if traced else {}),
        "text_encoder_lifecycle": "gpu_encode_then_discard",
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
    parser.add_argument("--offload", choices=("model_cpu", "none"), default="model_cpu")
    # 固定費と 1 step の限界費用を切り分けるための上書き。既定は preset のまま。
    parser.add_argument("--steps", type=int, default=0)
    parser.add_argument("--vae-memory", choices=("tiled", "full"), default="tiled")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--vae-dtype", choices=("float32", "bfloat16"), default="float32")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    work_root = args.work_root.resolve(strict=True)
    output = _contained(work_root, args.output)
    snapshot = _snapshot(args.snapshot)
    try:
        print(json.dumps(_generate(
            snapshot, output, args.preset, args.offload, args.steps,
            args.vae_memory, args.repeat, args.trace, args.vae_dtype,
        ), sort_keys=True))
    except Exception:
        output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
