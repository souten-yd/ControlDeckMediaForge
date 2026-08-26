from __future__ import annotations

"""Bounded Wan 2.2 TI2V adoption probe.

This is an evaluator, not the production video adapter.  The CPU text encoder
and GPU generation phases intentionally run in separate processes so a 30 GiB
host never has to retain UMT5 while loading the diffusion model.
"""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


MODEL_REVISION = "921dbaf3f1674a56f47e83fb80a34bac8a8f203e"
SOURCE_REVISION = "42bf4cfaa384bc21833865abc2f9e6c0e67233dc"
PROMPT = "A small orange field robot folds its solar panels at dusk, locked camera."
NEGATIVE_PROMPT = "blurry, distorted, text, watermark, camera shake"
FPS = 24


@dataclass(frozen=True)
class ProbePreset:
    width: int
    height: int
    frames: int
    steps: int


PRESETS = {
    "smoke": ProbePreset(width=256, height=256, frames=1, steps=1),
    "quality-frame": ProbePreset(width=256, height=256, frames=1, steps=30),
    "short-clip": ProbePreset(width=512, height=320, frames=17, steps=30),
    "practical-clip": ProbePreset(width=256, height=256, frames=49, steps=30),
    "candidate-clip": ProbePreset(width=384, height=256, frames=33, steps=30),
    "candidate-hq-clip": ProbePreset(width=512, height=320, frames=33, steps=30),
}


def _contained(root: Path, candidate: Path, *, must_exist: bool = False) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=must_exist)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("probe path escapes its allowed root")
    return resolved


def _encode(snapshot: Path, output: Path) -> dict[str, Any]:
    import torch
    from safetensors.torch import save_file
    from wan.configs import WAN_CONFIGS
    from wan.modules.t5 import HuggingfaceTokenizer, umt5_xxl

    config = WAN_CONFIGS["ti2v-5B"]
    started = time.monotonic()
    model = umt5_xxl(
        encoder_only=True,
        return_tokenizer=False,
        dtype=config.t5_dtype,
        # Construct only module metadata, then assign the mmap-backed CPU
        # tensors.  Creating an 11 GiB zero-initialized model first would
        # overlap it with the checkpoint during load and exceed safe host RAM.
        device=torch.device("meta"),
    ).eval().requires_grad_(False)
    state = torch.load(
        snapshot / config.t5_checkpoint,
        map_location="cpu",
        mmap=True,
        weights_only=True,
    )
    model.load_state_dict(state, assign=True)
    tokenizer = HuggingfaceTokenizer(
        name=str(snapshot / config.t5_tokenizer),
        seq_len=config.text_len,
        clean="whitespace",
    )

    def encode(text: str) -> Any:
        ids, mask = tokenizer([text], return_mask=True, add_special_tokens=True)
        lengths = mask.gt(0).sum(dim=1).long()
        with torch.no_grad():
            context = model(ids, mask)
        return context[0][:lengths[0]].contiguous()

    positive = encode(PROMPT)
    negative = encode(NEGATIVE_PROMPT)
    save_file({"positive": positive, "negative": negative}, str(output))
    return {
        "phase": "encode",
        "elapsed_sec": round(time.monotonic() - started, 3),
        "positive_shape": list(positive.shape),
        "negative_shape": list(negative.shape),
        "dtype": str(positive.dtype),
        "bytes": output.stat().st_size,
    }


class _PrecomputedEncoder:
    def __init__(self, positive: Any, negative: Any) -> None:
        self.positive = positive
        self.negative = negative
        self.calls = 0

    def __call__(self, _prompts: list[str], _device: Any) -> list[Any]:
        value = self.positive if self.calls == 0 else self.negative
        self.calls += 1
        return [value]


def _generate(
    snapshot: Path,
    embeddings: Path,
    output: Path,
    preset: ProbePreset,
) -> dict[str, Any]:
    import torch
    from safetensors.torch import load_file

    from wan.configs import WAN_CONFIGS
    from wan.modules.attention import attention
    import wan.modules.model as model_module
    from wan.modules.model import WanModel
    from wan.modules.vae2_2 import Wan2_2_VAE
    from wan.textimage2video import WanTI2V

    # Upstream already ships this SDPA fallback.  Select it instead of adding
    # a CUDA-only FlashAttention dependency or maintaining a custom kernel.
    model_module.flash_attention = attention

    config = WAN_CONFIGS["ti2v-5B"]
    values = load_file(str(embeddings), device="cpu")
    started = time.monotonic()
    device = torch.device("cuda:0")

    pipeline = object.__new__(WanTI2V)
    pipeline.device = device
    pipeline.config = config
    pipeline.rank = 0
    pipeline.t5_cpu = True
    pipeline.init_on_cpu = True
    pipeline.num_train_timesteps = config.num_train_timesteps
    pipeline.param_dtype = config.param_dtype
    pipeline.vae_stride = config.vae_stride
    pipeline.patch_size = config.patch_size
    pipeline.sp_size = 1
    pipeline.sample_neg_prompt = NEGATIVE_PROMPT
    pipeline.text_encoder = _PrecomputedEncoder(values["positive"], values["negative"])
    vae_started = time.monotonic()
    pipeline.vae = Wan2_2_VAE(
        vae_pth=str(snapshot / config.vae_checkpoint),
        device=device,
    )
    vae_load_sec = time.monotonic() - vae_started
    transformer_started = time.monotonic()
    pipeline.model = WanModel.from_pretrained(
        snapshot,
        torch_dtype=config.param_dtype,
        low_cpu_mem_usage=True,
    )
    pipeline.model = pipeline._configure_model(
        model=pipeline.model,
        use_sp=False,
        dit_fsdp=False,
        shard_fn=None,
        convert_model_dtype=False,
    )
    transformer_load_sec = time.monotonic() - transformer_started

    # The evaluator process exits after one decode, so retaining the transformer
    # on CPU only creates about 10 GiB of avoidable host-memory pressure.  Keep
    # upstream's offload boundary, but discard parameter storage to meta tensors
    # there instead of materializing a reusable CPU copy.
    def discard_transformer() -> Any:
        pipeline.model.to_empty(device=torch.device("meta"))
        return pipeline.model

    pipeline.model.cpu = discard_transformer  # type: ignore[method-assign]

    decode_sec = 0.0
    original_decode = pipeline.vae.decode

    def measured_decode(latents: Any) -> Any:
        nonlocal decode_sec
        decode_started = time.monotonic()
        result = original_decode(latents)
        decode_sec = time.monotonic() - decode_started
        return result

    pipeline.vae.decode = measured_decode

    sample_started = time.monotonic()
    frames = pipeline.t2v(
        input_prompt=PROMPT,
        size=(preset.width, preset.height),
        frame_num=preset.frames,
        sampling_steps=preset.steps,
        guide_scale=5.0,
        n_prompt=NEGATIVE_PROMPT,
        seed=260826,
        offload_model=True,
    )
    sample_sec = time.monotonic() - sample_started
    if frames is None or tuple(frames.shape) != (
        3, preset.frames, preset.height, preset.width
    ):
        raise RuntimeError(f"Wan returned an unexpected tensor shape: {getattr(frames, 'shape', None)}")
    frame_dir = output.parent / "frames"
    frame_dir.mkdir(mode=0o700)
    for index in range(preset.frames):
        image = ((frames[:, index].float().clamp(-1, 1) + 1) * 127.5).byte()
        from PIL import Image
        Image.fromarray(image.permute(1, 2, 0).cpu().numpy()).save(frame_dir / f"{index:06d}.png")
    completed = subprocess.run(
        [
            "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-framerate", str(FPS), "-i", str(frame_dir / "%06d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
        ],
        check=False,
        capture_output=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError("ffmpeg rejected the Wan probe frames")
    return {
        "phase": "generate",
        "elapsed_sec": round(time.monotonic() - started, 3),
        "vae_load_sec": round(vae_load_sec, 3),
        "transformer_load_sec": round(transformer_load_sec, 3),
        "sample_sec": round(sample_sec, 3),
        "decode_sec": round(decode_sec, 3),
        "shape": list(frames.shape),
        "preset": {
            "width": preset.width,
            "height": preset.height,
            "frames": preset.frames,
            "steps": preset.steps,
        },
        "dtype": str(frames.dtype),
        "output_bytes": output.stat().st_size,
    }


def _run(snapshot: Path, work_root: Path, output: Path, preset_name: str) -> None:
    work_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    work = _contained(work_root, output.parent)
    embeddings = _contained(work, work / "prompt.safetensors")
    report = _contained(work, work / "probe.json")
    command = [sys.executable, str(Path(__file__).resolve())]
    common = ["--snapshot", str(snapshot), "--work-root", str(work_root)]
    observations: list[dict[str, Any]] = []
    for phase, extra, timeout in (
        ("encode", ["--output", str(embeddings)], 600),
        (
            "generate",
            ["--embeddings", str(embeddings), "--output", str(output), "--preset", preset_name],
            1800,
        ),
    ):
        completed = subprocess.run(
            [*command, phase, *common, *extra],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        (work / f"{phase}.log").write_text(
            completed.stdout + "\n" + completed.stderr,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Wan {phase} phase exited with code {completed.returncode}")
        observations.append(json.loads(completed.stdout))
    report.write_text(json.dumps({"phases": observations}, sort_keys=True), encoding="utf-8")
    embeddings.unlink(missing_ok=True)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "encode", "generate"))
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path)
    parser.add_argument("--preset", choices=tuple(PRESETS), default="smoke")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    snapshot = args.snapshot.resolve(strict=True)
    work_root = args.work_root.resolve(strict=True)
    output = _contained(work_root, args.output)
    preset = PRESETS[args.preset]
    if args.mode == "run":
        _run(snapshot, work_root, output, args.preset)
    elif args.mode == "encode":
        print(json.dumps(_encode(snapshot, output), sort_keys=True))
    else:
        if args.embeddings is None:
            raise ValueError("generate requires --embeddings")
        embeddings = _contained(work_root, args.embeddings, must_exist=True)
        print(json.dumps(_generate(snapshot, embeddings, output, preset), sort_keys=True))


if __name__ == "__main__":
    main()
