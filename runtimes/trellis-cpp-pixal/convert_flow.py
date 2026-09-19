#!/usr/bin/env python3
"""Convert an authorized local Pixal3D flow safetensors checkpoint to GGUF.

Worker environment only. No downloads, pickle, model instantiation or GPU use.
The output directory is published atomically with a provenance manifest; this
conversion does not adopt a runtime or establish model quality/licensing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

ARCHITECTURE = "pixal3d-flow"
SCHEMA = 1
PIXAL_REVISION = "f7cf38429b0bd264f1995f0f8743a88b1c728b94"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        if key in value:
            raise ValueError(f"duplicate config key: {key}")
        value[key] = item
    return value


def flow_spec(config: dict[str, Any], stage: str) -> dict[str, int]:
    """Accept only the inference configuration represented by the native graph."""
    if set(config) - {"name", "args", "_comment"} or not isinstance(config.get("args"), dict):
        raise ValueError("expected checkpoint {name,args} config, not a training/pipeline config")
    names = ("SparseStructureFlowModel",) if stage == "ss" else ("SLatFlowModel", "ElasticSLatFlowModel")
    if stage not in {"ss", "shape", "texture"} or config.get("name") not in names:
        raise ValueError("model class does not match the requested flow stage")
    args = config["args"]
    known = {"resolution", "in_channels", "out_channels", "model_channels", "cond_channels",
             "num_blocks", "num_heads", "num_head_channels", "mlp_ratio", "pe_mode", "rope_freq",
             "dtype", "use_checkpoint", "share_mod", "initialization", "qk_rms_norm",
             "qk_rms_norm_cross", "image_attn_mode", "proj_in_channels", "vae_in_channels"}
    if set(args) - known:
        raise ValueError(f"unknown model arguments: {sorted(set(args) - known)}")
    required = {"pe_mode": "rope", "share_mod": True, "qk_rms_norm": True,
                "qk_rms_norm_cross": True, "image_attn_mode": "proj"}
    for key, expected in required.items():
        if type(args.get(key)) is not type(expected) or args[key] != expected:
            raise ValueError(f"unsupported {key}: native flow requires {expected!r}")
    if args.get("rope_freq", [1.0, 10000.0]) != [1.0, 10000.0]:
        raise ValueError("unsupported rotary frequency range")
    if args.get("vae_in_channels") is not None:
        raise ValueError("gated/VAE projection is not implemented")
    if args.get("dtype", "float32") not in {"float32", "float16", "bfloat16"}:
        raise ValueError("unsupported checkpoint dtype")

    def integer(name: str, maximum: int, default: int | None = None) -> int:
        value = args.get(name, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f"invalid {name}")
        return value

    hidden = integer("model_channels", 4096)
    if args.get("num_heads") is not None:
        heads = integer("num_heads", 64)
    else:
        per_head = integer("num_head_channels", 256, 64)
        if hidden % per_head:
            raise ValueError("model width is not divisible by num_head_channels")
        heads = hidden // per_head
    head_dim = hidden // heads
    if not 1 <= heads <= 64 or hidden % heads or not 8 <= head_dim <= 256 or head_dim % 2:
        raise ValueError("unsupported attention head dimensions")
    ratio = args.get("mlp_ratio", 4.0)
    if type(ratio) not in (float, int) or not math.isfinite(ratio) or not 1 <= ratio <= 16:
        raise ValueError("invalid mlp_ratio")
    cond = integer("cond_channels", 4096)
    proj = cond if args.get("proj_in_channels") is None else integer("proj_in_channels", 8192)
    spec = {"n_blocks": integer("num_blocks", 64), "n_heads": heads, "head_dim": head_dim,
            "d_model": hidden, "d_mlp": int(hidden * ratio), "d_cond": cond,
            "proj_in_channels": proj, "in_ch": integer("in_channels", 256),
            "out_ch": integer("out_channels", 256), "resolution": integer("resolution", 256)}
    if spec["resolution"] < 2 or spec["in_ch"] != spec["out_ch"] * (2 if stage == "texture" else 1):
        raise ValueError("stage input/output channels or grid resolution mismatch")
    return spec


def expected_shapes(spec: dict[str, int]) -> dict[str, tuple[int, ...]]:
    d, c, p = spec["d_model"], spec["d_cond"], spec["proj_in_channels"]
    shapes: dict[str, tuple[int, ...]] = {}

    def linear(name: str, outputs: int, inputs: int) -> None:
        shapes[name + ".weight"] = (outputs, inputs)
        shapes[name + ".bias"] = (outputs,)

    linear("input_layer", d, spec["in_ch"])
    linear("out_layer", spec["out_ch"], d)
    linear("t_embedder.mlp.0", d, 256)
    linear("t_embedder.mlp.2", d, d)
    linear("adaLN_modulation.1", 6*d, d)
    for i in range(spec["n_blocks"]):
        prefix = f"blocks.{i}."
        shapes[prefix + "modulation"] = (6*d,)
        shapes[prefix + "norm2.weight"] = (d,)
        shapes[prefix + "norm2.bias"] = (d,)
        linear(prefix + "self_attn.to_qkv", 3*d, d)
        linear(prefix + "self_attn.to_out", d, d)
        cross = prefix + "cross_attn.cross_attn_block."
        linear(cross + "to_q", d, d)
        linear(cross + "to_kv", 2*d, c)
        linear(cross + "to_out", d, d)
        for attention in (prefix + "self_attn.", cross):
            for norm in ("q_rms_norm.gamma", "k_rms_norm.gamma"):
                shapes[attention + norm] = (spec["n_heads"], spec["head_dim"])
        linear(prefix + "cross_attn.proj_linear", d, p)
        linear(prefix + "mlp.mlp.0", spec["d_mlp"], d)
        linear(prefix + "mlp.mlp.2", d, spec["d_mlp"])
    return shapes


def convert(checkpoint: Path, config_path: Path, output_dir: Path, *, stage: str,
            storage: str, source_repository: str, source_revision: str,
            source_kind: str) -> dict[str, Any]:
    if storage not in {"f32", "f16"} or source_kind not in {"synthetic", "checkpoint"}:
        raise ValueError("invalid storage or source kind")
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision) or not re.fullmatch(r"[\w./-]{1,200}", source_repository):
        raise ValueError("source repository and full revision are required")
    checkpoint, config_path = checkpoint.resolve(strict=True), config_path.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ValueError("output directory already exists; refusing overwrite")
    if not checkpoint.is_file() or not 8 <= checkpoint.stat().st_size <= 32*1024**3:
        raise ValueError("invalid checkpoint size/type")
    if not config_path.is_file() or config_path.stat().st_size > 65536:
        raise ValueError("invalid config size/type")
    raw_config = config_path.read_bytes()
    config = json.loads(raw_config, object_pairs_hook=unique_object)
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    spec = flow_spec(config, stage)
    shapes = expected_shapes(spec)
    original_hash = digest(checkpoint)
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1",
                       "CUDA_VISIBLE_DEVICES": "-1", "HF_HUB_OFFLINE": "1"})
    import gguf
    import numpy as np
    import torch
    from safetensors import safe_open

    if importlib.metadata.version("gguf") != "0.19.0":
        raise ValueError("install the pinned gguf-lock.txt in the worker environment")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with safe_open(checkpoint, framework="pt", device="cpu") as tensors:
        if set(tensors.keys()) != set(shapes):
            raise ValueError(f"checkpoint tensor set mismatch: missing={sorted(set(shapes)-set(tensors.keys()))}, "
                             f"extra={sorted(set(tensors.keys())-set(shapes))}")
        # Validate all metadata before reading/converting large tensors.
        for name, shape in shapes.items():
            view = tensors.get_slice(name)
            if tuple(view.get_shape()) != shape or view.get_dtype() not in {"F32", "F16", "BF16"}:
                raise ValueError(f"checkpoint shape/dtype mismatch: {name}")
            if len(name.encode()) >= 64:
                raise ValueError("tensor name exceeds pinned GGML name capacity")
        with tempfile.TemporaryDirectory(prefix=".pixal-convert-", dir=output_dir.parent) as temporary:
            directory = Path(temporary) / "result"
            directory.mkdir()
            result = directory / "model.gguf"
            writer = gguf.GGUFWriter(result, ARCHITECTURE, use_temp_file=True)
            writer.add_name(f"Pixal3D {stage} flow")
            writer.add_string("trellis.config_json", raw_config.decode())
            writer.add_uint32("pixal.schema_version", SCHEMA)
            writer.add_string("pixal.stage", stage)
            writer.add_string("pixal.storage", storage)
            writer.add_string("pixal.reference_revision", PIXAL_REVISION)
            for name, value in spec.items():
                writer.add_uint32("pixal.flow." + name, value)
            provenance = {"checkpoint_sha256": original_hash,
                          "config_sha256": hashlib.sha256(raw_config).hexdigest(),
                          "source_repository": source_repository, "source_revision": source_revision,
                          "source_kind": source_kind}
            for key, value in provenance.items():
                writer.add_string("pixal." + key, value)
            records = {}
            try:
                for name in sorted(shapes):
                    tensor = tensors.get_tensor(name)
                    values = tensor.float().numpy()
                    if not np.isfinite(values).all():
                        raise ValueError(f"non-finite checkpoint tensor: {name}")
                    # Keep all normalization and bias values in F32, including
                    # the rank-two RMS gamma tensors. Only linear matrices use F16.
                    use_half = storage == "f16" and name.endswith(".weight") and values.ndim == 2
                    with np.errstate(over="ignore"):
                        converted = values.astype(np.float16 if use_half else np.float32)
                    if not np.isfinite(converted).all():
                        raise ValueError(f"tensor overflows requested storage: {name}")
                    writer.add_tensor(name, converted)
                    records[name] = {"shape": list(converted.shape), "dtype": str(converted.dtype),
                                     "sha256": hashlib.sha256(converted.tobytes()).hexdigest()}
                writer.write_header_to_file()
                writer.write_kv_data_to_file()
                writer.write_tensors_to_file()
            finally:
                writer.close()
                if writer.temp_file is not None:
                    writer.temp_file.close()
            if digest(checkpoint) != original_hash or config_path.read_bytes() != raw_config:
                raise ValueError("source changed during conversion")
            manifest = {"schema_version": SCHEMA, "architecture": ARCHITECTURE, "stage": stage,
                        "storage": storage, "flow": spec, "source": provenance, "tensors": records,
                        "reference_revision": PIXAL_REVISION, "converter_sha256": digest(Path(__file__)),
                        "packages": {name: importlib.metadata.version(name)
                                     for name in ("gguf", "safetensors", "numpy", "torch")},
                        "output_sha256": digest(result), "output_bytes": result.stat().st_size,
                        "torch_gpu_initialized": torch.cuda.is_initialized(), "adopted": False}
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            directory.rename(output_dir)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=("ss", "shape", "texture"))
    parser.add_argument("--storage", choices=("f32", "f16"), default="f32")
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-kind", required=True, choices=("checkpoint", "synthetic"))
    args = parser.parse_args()
    report = convert(args.checkpoint, args.config, args.output_dir, stage=args.stage,
                     storage=args.storage, source_repository=args.source_repository,
                     source_revision=args.source_revision, source_kind=args.source_kind)
    print(json.dumps({key: report[key] for key in ("stage", "storage", "output_sha256", "output_bytes")}))


if __name__ == "__main__":
    main()
