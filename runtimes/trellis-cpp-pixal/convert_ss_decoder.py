#!/usr/bin/env python3
"""Convert an authorized local Pixal SS decoder to strict GGUF, without a GPU."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from convert_flow import PIXAL_REVISION, digest, unique_object
from convert_vision import integer

ARCHITECTURE = "pixal3d-ss-decoder"


def decoder_spec(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict) or set(config) != {"name", "args"} or config["name"] != "SparseStructureDecoder" or not isinstance(config["args"], dict):
        raise ValueError("SS decoder requires an explicit SparseStructureDecoder config")
    fields = {"out_channels", "latent_channels", "num_res_blocks", "channels", "num_res_blocks_middle", "norm_type", "use_fp16"}
    c = {"num_res_blocks_middle": 2, "norm_type": "layer", "use_fp16": False} | config["args"]
    if set(c) != fields:
        raise ValueError("unknown or missing SS decoder arguments")
    result = {k: integer(c[k], k, lo, hi) for k, lo, hi in (("out_channels", 1, 1), ("latent_channels", 1, 64), ("num_res_blocks", 0, 8), ("num_res_blocks_middle", 0, 8))}
    if not isinstance(c["channels"], list) or not 1 <= len(c["channels"]) <= 5:
        raise ValueError("invalid SS decoder channel stages")
    result["channels"] = [integer(ch, "channels", 2, 1024) for ch in c["channels"]]
    if c["norm_type"] not in {"layer", "group"} or type(c["use_fp16"]) is not bool:
        raise ValueError("invalid SS decoder normalization/precision")
    if c["norm_type"] == "group" and result["channels"][-1] % 32:
        raise ValueError("SS output GroupNorm requires 32 groups")
    result["norm_type"] = c["norm_type"]
    result["reference_fp16"] = c["use_fp16"]
    return result


def tensor_shapes(s: dict[str, Any]) -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}
    def conv(name: str, ic: int, oc: int) -> None:
        result[name + ".weight"] = (oc, ic, 3, 3, 3)
        result[name + ".bias"] = (oc,)
    def norm(name: str, channels: int) -> None:
        result[name + ".weight"] = (channels,)
        result[name + ".bias"] = (channels,)
    def block(name: str, channels: int) -> None:
        for i in (1, 2):
            norm(f"{name}.norm{i}", channels)
            conv(f"{name}.conv{i}", channels, channels)
    conv("input_layer", s["latent_channels"], s["channels"][0])
    for i in range(s["num_res_blocks_middle"]):
        block(f"middle_block.{i}", s["channels"][0])
    index = 0
    for stage, channels in enumerate(s["channels"]):
        for _ in range(s["num_res_blocks"]):
            block(f"blocks.{index}", channels); index += 1
        if stage + 1 < len(s["channels"]):
            conv(f"blocks.{index}.conv", channels, s["channels"][stage + 1] * 8); index += 1
    norm("out_layer.0", s["channels"][-1])
    conv("out_layer.2", s["channels"][-1], s["out_channels"])
    return result


def convert(checkpoint: Path, config_path: Path, output_dir: Path, *, storage: str,
            source_repository: str, source_revision: str, source_kind: str) -> dict[str, Any]:
    if storage not in {"f32", "f16"} or source_kind not in {"synthetic", "checkpoint"} or not re.fullmatch(r"[0-9a-f]{40}", source_revision) or not re.fullmatch(r"[\w./-]{1,200}", source_repository):
        raise ValueError("invalid SS decoder storage/provenance")
    checkpoint = checkpoint.resolve(strict=True); config_path = config_path.resolve(strict=True); output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ValueError("output directory already exists; refusing overwrite")
    if not checkpoint.is_file() or not 8 <= checkpoint.stat().st_size <= 8 * 1024**3 or not config_path.is_file() or config_path.stat().st_size > 65536:
        raise ValueError("invalid local decoder checkpoint/config size")
    raw = config_path.read_bytes(); spec = decoder_spec(json.loads(raw, object_pairs_hook=unique_object))
    shapes = tensor_shapes(spec); source_hash = digest(checkpoint)
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1", "CUDA_VISIBLE_DEVICES": "-1", "HF_HUB_OFFLINE": "1"})
    import gguf
    import numpy as np
    import torch
    from safetensors import safe_open
    if importlib.metadata.version("gguf") != "0.19.0":
        raise ValueError("use pinned gguf-lock.txt")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with safe_open(checkpoint, framework="pt", device="cpu") as source:
        if set(source.keys()) != set(shapes):
            raise ValueError("SS decoder checkpoint tensor set mismatch")
        for name, shape in shapes.items():
            view = source.get_slice(name)
            if tuple(view.get_shape()) != shape or view.get_dtype() not in {"F32", "F16", "BF16"}:
                raise ValueError("SS decoder shape/dtype mismatch: " + name)
        with tempfile.TemporaryDirectory(prefix=".pixal-ss-decoder-", dir=output_dir.parent) as temporary:
            directory = Path(temporary) / "result"; directory.mkdir()
            output = directory / "model.gguf"; writer = gguf.GGUFWriter(output, ARCHITECTURE, use_temp_file=True)
            writer.add_name("Pixal3D sparse structure decoder")
            writer.add_uint32("pixal.schema_version", 1); writer.add_string("pixal.reference_revision", PIXAL_REVISION)
            writer.add_string("pixal.storage", storage); writer.add_string("pixal.ss_decoder.config_json", raw.decode())
            for name, value in spec.items():
                if name == "channels":
                    writer.add_uint32("pixal.ss_decoder.stages", len(value))
                    for i, ch in enumerate(value): writer.add_uint32(f"pixal.ss_decoder.channels.{i}", ch)
                else:
                    method = writer.add_bool if type(value) is bool else writer.add_uint32 if type(value) is int else writer.add_string
                    method("pixal.ss_decoder." + name, value)
            provenance = {"checkpoint_sha256": source_hash, "config_sha256": hashlib.sha256(raw).hexdigest(),
                          "source_repository": source_repository, "source_revision": source_revision, "source_kind": source_kind}
            for name, value in provenance.items(): writer.add_string("pixal." + name, value)
            records = {}
            try:
                for name, shape in sorted(shapes.items()):
                    values = source.get_tensor(name).float().numpy()
                    if not np.isfinite(values).all(): raise ValueError("non-finite SS decoder tensor: " + name)
                    # GGML has four dimensions: pack OC*IC without changing any
                    # element order. Original Torch layout is [OC,IC,KX,KY,KZ].
                    native_shape = (shape[0] * shape[1], *shape[2:]) if len(shape) == 5 else shape
                    with np.errstate(over="ignore"):
                        values = values.reshape(native_shape).astype(np.float16 if storage == "f16" and len(shape) == 5 else np.float32)
                    if not np.isfinite(values).all(): raise ValueError("SS decoder storage overflow: " + name)
                    writer.add_tensor(name, values)
                    records[name] = {"source_shape": shape, "stored_shape": values.shape, "dtype": str(values.dtype), "sha256": hashlib.sha256(values.tobytes()).hexdigest()}
                writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file()
            finally:
                writer.close()
                if writer.temp_file is not None: writer.temp_file.close()
            if digest(checkpoint) != source_hash or config_path.read_bytes() != raw:
                raise ValueError("SS decoder source changed during conversion")
            manifest = {"schema_version": 1, "architecture": ARCHITECTURE, "decoder": spec, "storage": storage, "source": provenance, "tensors": records,
                        "reference_revision": PIXAL_REVISION, "converter_sha256": digest(Path(__file__)), "output_sha256": digest(output), "output_bytes": output.stat().st_size,
                        "packages": {n: importlib.metadata.version(n) for n in ("gguf", "safetensors", "numpy", "torch")},
                        "torch_gpu_initialized": torch.cuda.is_initialized(), "adopted": False}
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            if output_dir.exists(): raise ValueError("SS decoder output appeared during conversion")
            directory.rename(output_dir)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkpoint", "config", "output-dir"): parser.add_argument("--" + name, type=Path, required=True)
    for name in ("source-repository", "source-revision"): parser.add_argument("--" + name, required=True)
    parser.add_argument("--source-kind", choices=("synthetic", "checkpoint"), required=True)
    parser.add_argument("--storage", choices=("f32", "f16"), default="f32")
    args = parser.parse_args()
    result = convert(args.checkpoint, args.config, args.output_dir, storage=args.storage, source_repository=args.source_repository, source_revision=args.source_revision, source_kind=args.source_kind)
    print(json.dumps({k: result[k] for k in ("output_sha256", "output_bytes", "storage")}))


if __name__ == "__main__": main()
