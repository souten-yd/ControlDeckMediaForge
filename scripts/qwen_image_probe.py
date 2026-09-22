#!/usr/bin/env python3
"""Offline Qwen-Image-2.1 evaluation; run with an isolated image-worker Python.

Provision licensed weights separately. GPU invocations require a caller-held
ControlDeck resource lease. This script neither downloads nor adopts models.
One JSON result is written to stdout, including ordinary failures/cancellation.
An external SIGKILL/OOM kill cannot be converted to JSON by the killed process.
"""
from __future__ import annotations

import argparse
from array import array
from contextlib import redirect_stdout
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import sys
import time
from typing import Any


class ProbeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProbeError("invalid_arguments", message)


def arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = Parser(description=__doc__)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--device", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--dtype", choices=("bf16", "fp16"), required=True)
    parser.add_argument("--quantization", choices=("none", "int8"), required=True)
    parser.add_argument("--offload", action="store_true")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--repeat", type=int, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--rgba", action="store_true")
    parser.add_argument("--steps", type=int, default=40, help="Upstream default: 40")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise ProbeError("invalid_arguments", "revision must be an immutable 40-character commit")
    if not 1 <= args.repeat <= 10 or not 1 <= args.steps <= 100:
        raise ProbeError("invalid_arguments", "repeat must be 1..10 and steps 1..100")
    if any(n < 64 or n > 2048 or n % 32 for n in (args.width, args.height)):
        raise ProbeError("invalid_arguments", "dimensions must be multiples of 32 in 64..2048")
    if args.offload and args.device != "gpu":
        raise ProbeError("invalid_arguments", "CPU offload requires the GPU route")
    return args


def cached_snapshot(args: argparse.Namespace) -> Path:
    from huggingface_hub import snapshot_download

    try:
        root = Path(snapshot_download(args.model_id, revision=args.revision, local_files_only=True))
        index = json.loads((root / "model_index.json").read_text())
        if index.get("_class_name") != "QwenImage21Pipeline":
            raise ProbeError("model_incompatible", "snapshot is not a QwenImage21Pipeline")
        for component in ("text_encoder", "transformer", "vae"):
            directory = root / component
            if not (directory / "config.json").is_file():
                raise FileNotFoundError(component)
            indexes = list(directory.glob("*.safetensors.index.json"))
            if indexes:
                shards = set(json.loads(indexes[0].read_text())["weight_map"].values())
                if not shards or any(Path(name).name != name or not (directory / name).is_file()
                                     for name in shards):
                    raise FileNotFoundError(component)
            elif not any(directory.glob("*.safetensors")):
                raise FileNotFoundError(component)
        return root
    except ProbeError:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise ProbeError("weights_missing", "complete pinned weights are not available in the local HF cache") from exc


def load_pipeline(root: Path, args: argparse.Namespace, torch: Any) -> tuple[Any, dict[str, int]]:
    from diffusers import QwenImage21Pipeline

    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float16
    options: dict[str, Any] = {"torch_dtype": dtype, "local_files_only": True}
    counts: dict[str, int] = {}
    if args.quantization == "int8":
        from diffusers import QwenImage21Transformer2DModel
        from transformers import Qwen3VLForConditionalGeneration
        from optimum.quanto import freeze, qint8, quantization_map, quantize

        # Quantize components in sequence; never hold both full-precision models
        # before quantization. No disk quantization cache or silent fallback.
        for name, cls in (("text_encoder", Qwen3VLForConditionalGeneration),
                          ("transformer", QwenImage21Transformer2DModel)):
            kwargs = {"dtype" if name == "text_encoder" else "torch_dtype": dtype,
                      "local_files_only": True}
            model = cls.from_pretrained(root / name, **kwargs)
            quantize(model, weights=qint8)
            freeze(model)
            counts[name] = len(quantization_map(model))
            if not counts[name]:
                raise ProbeError("quantization_failed", f"no quantized modules in {name}")
            options[name] = model
    pipeline = QwenImage21Pipeline.from_pretrained(root, **options)
    pipeline.set_progress_bar_config(disable=True)
    if args.offload:
        pipeline.enable_model_cpu_offload()
    else:
        pipeline.to("cuda" if args.device == "gpu" else "cpu")
    return pipeline, counts


def png_bytes(frame: Any) -> tuple[bytes, dict[str, Any]]:
    """Check floating decoder output before PIL can hide non-finite values."""
    from PIL import Image

    shape = tuple(frame.shape)
    if len(shape) != 3 or shape[2] not in (3, 4) or str(frame.dtype) not in ("float32", "float64"):
        raise ProbeError("output_invalid", "pipeline must return an HWC float RGB/RGBA array")
    height, width, channels = shape
    values = array("f" if str(frame.dtype) == "float32" else "d")
    values.frombytes(frame.tobytes(order="C"))
    if len(values) != height * width * channels or not all(math.isfinite(v) for v in values):
        raise ProbeError("numerical_nonfinite", "decoder output contains non-finite values")
    pixels = bytes(round(min(1.0, max(0.0, float(v))) * 255) for v in values)
    mode = "RGBA" if channels == 4 else "RGB"
    image = Image.frombytes(mode, (width, height), pixels)
    alpha = pixels[3::4] if channels == 4 else b""
    facts = {"mode": mode, "width": width, "height": height,
             "alpha_min": min(alpha) if alpha else None,
             "alpha_max": max(alpha) if alpha else None,
             "nonopaque_pixels": sum(a < 255 for a in alpha),
             "visible_pixels": sum(a > 0 for a in alpha) if alpha else width * height}
    facts["has_alpha"] = bool(alpha and facts["nonopaque_pixels"] and facts["visible_pixels"])
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), facts


def probe(argv: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"host_peak_rss_bytes": None, "vram_peak_bytes": None,
        "vram_peak_reserved_bytes": None, "vram_measurement": "pytorch_allocator_not_total_device",
        "cold_load_sec": None, "per_image_sec": None, "per_image_seconds": [],
        "output_sha256": [], "identical_outputs": None, "has_alpha": False,
        "output_facts": [], "error": None, "numerical_reference_comparison": "NOT TESTED"}
    torch = None
    gpu = False
    gpu_stats_started = False
    started = None
    owned_output: Path | None = None
    try:
        args = arguments(argv)
        result["config"] = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
        result["blas_environment"] = {key: os.environ.get(key) for key in
                                      ("ROCBLAS_USE_HIPBLASLT", "TORCH_BLAS_PREFER_HIPBLASLT")}
        # Set these before importing any HF/Transformers/Diffusers module.
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                          HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
        import torch as torch_module
        torch = torch_module
        gpu = args.device == "gpu"
        if gpu and not torch.cuda.is_available():
            raise ProbeError("gpu_unavailable", "PyTorch reports no available GPU")
        if gpu:
            result["device_name"] = torch.cuda.get_device_name(0)
            result["hip_version"] = getattr(torch.version, "hip", None)
        root = cached_snapshot(args)
        result["versions"] = {}
        for package in ("torch", "diffusers", "transformers", "tokenizers", "optimum-quanto", "huggingface-hub"):
            try:
                result["versions"][package] = version(package)
            except PackageNotFoundError:
                result["versions"][package] = None
        if args.output_dir:
            output = args.output_dir.expanduser().absolute()
            if output != output.resolve():
                raise ProbeError("output_invalid", "output directory must not traverse symlinks")
            output.mkdir(parents=True, exist_ok=True, mode=0o700)
            if any(output.iterdir()):
                raise ProbeError("output_invalid", "output directory must be empty")
            owned_output = output
        if gpu:
            torch.cuda.reset_peak_memory_stats()
            gpu_stats_started = True
        started = time.perf_counter()
        pipeline, quantized = load_pipeline(root, args, torch)
        if gpu:
            torch.cuda.synchronize()
        result["cold_load_sec"] = time.perf_counter() - started
        result["quantized_module_counts"] = quantized
        result["vae_quantization"] = "none"
        prompt = args.prompt
        if args.rgba:
            prompt = ("This is an RGBA image with transparency. " + prompt
                      + ". The image has alpha channel and the background is transparent.")
        result["effective_prompt"] = prompt
        finite_checks = 0

        def finite_latents(_pipeline: Any, _step: int, _timestep: Any, values: dict[str, Any]) -> dict[str, Any]:
            nonlocal finite_checks
            if not bool(torch.isfinite(values["latents"]).all().item()):
                raise ProbeError("numerical_nonfinite", "denoising latents contain non-finite values")
            finite_checks += 1
            return values

        for index in range(args.repeat):
            generator = torch.Generator(device="cuda" if gpu else "cpu").manual_seed(args.seed)
            previous_checks = finite_checks
            began = time.perf_counter()
            generated = pipeline(prompt=prompt, height=args.height, width=args.width,
                num_inference_steps=args.steps, true_cfg_scale=1.0, generator=generator,
                output_type="np", callback_on_step_end=finite_latents)
            if gpu:
                torch.cuda.synchronize()
            result["per_image_seconds"].append(time.perf_counter() - began)
            if finite_checks == previous_checks:
                raise ProbeError("output_invalid", "pipeline did not run the latent finite check")
            content, facts = png_bytes(generated.images[0])
            if (facts["width"], facts["height"]) != (args.width, args.height):
                raise ProbeError("output_invalid", "generated dimensions differ from the request")
            if args.output_dir:
                with (output / f"sample-{index + 1:02d}.png").open("xb") as stream:
                    stream.write(content)
            result["output_sha256"].append(sha256(content).hexdigest())
            result["output_facts"].append(facts)
        result["identical_outputs"] = len(set(result["output_sha256"])) == 1 if args.repeat > 1 else None
        result["has_alpha"] = all(row["has_alpha"] for row in result["output_facts"])
        result["finite_latents_and_decoder_output"] = True
        result["finite_latent_check_count"] = finite_checks
    except (Exception, KeyboardInterrupt) as exc:
        result["error"] = {"code": exc.code if isinstance(exc, ProbeError) else
                           "canceled" if isinstance(exc, KeyboardInterrupt) else
                           "runtime_unavailable" if isinstance(exc, ImportError) else "probe_failed",
                           "message": str(exc)[:400] or type(exc).__name__}
        if started is not None and result["cold_load_sec"] is None:
            result["cold_load_sec"] = time.perf_counter() - started
    finally:
        result["host_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        if result["per_image_seconds"]:
            result["per_image_sec"] = sum(result["per_image_seconds"]) / len(result["per_image_seconds"])
        if gpu_stats_started and torch is not None:
            try:
                result["vram_peak_bytes"] = torch.cuda.max_memory_allocated()
                result["vram_peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
            except Exception:
                pass  # Null explicitly means this measurement is unavailable.
    if owned_output is not None:
        try:
            # Retain input/revision, seed, dependency versions and output hashes
            # alongside the samples, including partial failed evaluations.
            with (owned_output / "probe-result.json").open("x") as stream:
                json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2)
                stream.write("\n")
        except OSError as exc:
            if result["error"] is None:
                result["error"] = {"code": "evidence_write_failed", "message": str(exc)[:400]}
    return result


def main(argv: list[str] | None = None) -> int:
    def stop(_signum: int, _frame: Any) -> None:
        raise ProbeError("canceled", "probe canceled by signal")

    signal.signal(signal.SIGTERM, stop)
    # Protect stdout from native libraries as well as Python progress messages.
    saved = os.dup(sys.stdout.fileno())
    try:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        with redirect_stdout(sys.stderr):
            result = probe(argv)
        with os.fdopen(os.dup(saved), "w") as output:
            output.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
    finally:
        # Keep fd 1 redirected through process shutdown: buffered C stdio and
        # native finalizers can emit messages after the JSON has been written.
        os.close(saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
