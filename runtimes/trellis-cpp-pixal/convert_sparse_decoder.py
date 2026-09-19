#!/usr/bin/env python3
"""Local Pixal shape/texture sparse decoder safetensors -> validated GGUF."""
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
from convert_vision import integer, real

ARCHITECTURE = "pixal3d-sparse-decoder"


def decoder_spec(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict) or set(config) != {"name", "args"} or not isinstance(config["args"], dict):
        raise ValueError("sparse decoder requires explicit name/args config")
    shape = config["name"] == "FlexiDualGridVaeDecoder"
    if not shape and config["name"] != "SparseUnetVaeDecoder": raise ValueError("unsupported sparse decoder class")
    c = {"use_fp16": False, **({"voxel_margin": .5} if shape else {"pred_subdiv": True})} | config["args"]
    fields = {"model_channels", "latent_channels", "num_blocks", "block_type", "up_block_type", "block_args", "use_fp16"}
    fields |= {"resolution", "voxel_margin"} if shape else {"out_channels", "pred_subdiv"}
    if set(c) != fields: raise ValueError("unknown/missing sparse decoder arguments")
    if not isinstance(c["model_channels"], list) or not 2 <= len(c["model_channels"]) <= 5: raise ValueError("invalid sparse decoder stages")
    channels = [integer(v, "model_channels", 8, 2048) for v in c["model_channels"]]; stages = len(channels)
    for name, count in (("num_blocks", stages), ("block_type", stages), ("block_args", stages), ("up_block_type", stages-1)):
        if not isinstance(c[name], list) or len(c[name]) != count: raise ValueError("invalid stage list: " + name)
    if any(v != "SparseConvNeXtBlock3d" for v in c["block_type"]) or any(v != "SparseResBlockC2S3d" for v in c["up_block_type"]):
        raise ValueError("unsupported sparse decoder block architecture")
    blocks = [integer(v, "num_blocks", 0, 32) for v in c["num_blocks"]]
    mlp = []
    for i, block in enumerate(c["block_args"]):
        if not isinstance(block, dict) or set(block)-{"mlp_ratio", "use_checkpoint"}: raise ValueError("unsupported sparse block arguments")
        # A stage's arguments are also passed to C2S, whose signature has no mlp_ratio.
        if i < stages-1 and "mlp_ratio" in block: raise ValueError("mlp_ratio is not a C2S argument")
        if type(block.get("use_checkpoint", False)) is not bool: raise ValueError("invalid use_checkpoint")
        mlp.append(int(channels[i] * real(block.get("mlp_ratio", 4.), "mlp_ratio", .5, 16.)))
    for a, b in zip(channels, channels[1:]):
        if a % 8 or b % (a//8): raise ValueError("C2S channels do not support repeat_interleave skip")
    if type(c["use_fp16"]) is not bool: raise ValueError("invalid sparse decoder precision")
    if not shape and (c["out_channels"] != 6 or type(c["out_channels"]) is not int or c["pred_subdiv"] is not False):
        raise ValueError("texture decoder must output six channels with guided subdivision")
    return {"kind": "shape" if shape else "texture", "latent_channels": integer(c["latent_channels"], "latent_channels", 1, 64),
            "out_channels": 7 if shape else 6, "channels": channels, "blocks": blocks, "mlp_channels": mlp,
            "reference_fp16": c["use_fp16"], "resolution": integer(c["resolution"], "resolution", 2, 4096) if shape else 0,
            "voxel_margin": real(c["voxel_margin"], "voxel_margin", 0., 4.) if shape else 0.}


def tensor_shapes(s: dict[str, Any]) -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}
    def linear(name: str, ci: int, co: int) -> None:
        result[name+".weight"] = (co, ci); result[name+".bias"] = (co,)
    def conv(name: str, ci: int, co: int) -> None:
        result[name+".weight"] = (co, 3, 3, 3, ci); result[name+".bias"] = (co,)
    def norm(name: str, channels: int) -> None:
        result[name+".weight"] = (channels,); result[name+".bias"] = (channels,)
    linear("from_latent", s["latent_channels"], s["channels"][0]); linear("output_layer", s["channels"][-1], s["out_channels"])
    for i, ch in enumerate(s["channels"]):
        for j in range(s["blocks"][i]):
            p = f"blocks.{i}.{j}"
            conv(p+".conv", ch, ch); norm(p+".norm", ch)
            linear(p+".mlp.0", ch, s["mlp_channels"][i]); linear(p+".mlp.2", s["mlp_channels"][i], ch)
        if i+1 < len(s["channels"]):
            p = f"blocks.{i}.{s['blocks'][i]}"; out = s["channels"][i+1]
            norm(p+".norm1", ch); conv(p+".conv1", ch, out*8); conv(p+".conv2", out, out)
            if s["kind"] == "shape": linear(p+".to_subdiv", ch, 8)
    return result


def convert(checkpoint: Path, config_path: Path, output_dir: Path, *, storage: str, source_repository: str, source_revision: str, source_kind: str) -> dict[str, Any]:
    if storage not in {"f32", "f16"} or source_kind not in {"synthetic", "checkpoint"} or not re.fullmatch(r"[0-9a-f]{40}", source_revision) or not re.fullmatch(r"[\w./-]{1,200}", source_repository):
        raise ValueError("invalid sparse decoder storage/provenance")
    checkpoint=checkpoint.resolve(strict=True); config_path=config_path.resolve(strict=True); output_dir=output_dir.resolve()
    if output_dir.exists(): raise ValueError("output directory exists; refusing overwrite")
    if not checkpoint.is_file() or not 8<=checkpoint.stat().st_size<=32*1024**3 or not config_path.is_file() or config_path.stat().st_size>65536:
        raise ValueError("invalid sparse decoder input files")
    raw=config_path.read_bytes(); spec=decoder_spec(json.loads(raw, object_pairs_hook=unique_object)); shapes=tensor_shapes(spec); source_hash=digest(checkpoint)
    os.environ.update({"HIP_VISIBLE_DEVICES":"-1", "ROCR_VISIBLE_DEVICES":"-1", "CUDA_VISIBLE_DEVICES":"-1", "HF_HUB_OFFLINE":"1"})
    import gguf
    import numpy as np
    import torch
    from safetensors import safe_open
    if importlib.metadata.version("gguf")!="0.19.0": raise ValueError("use pinned GGUF converter")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with safe_open(checkpoint, framework="pt", device="cpu") as tensors:
        if set(tensors.keys())!=set(shapes): raise ValueError("sparse decoder tensor set mismatch")
        for name, shape in shapes.items():
            view=tensors.get_slice(name)
            if tuple(view.get_shape())!=shape or view.get_dtype() not in {"F32","F16","BF16"}: raise ValueError("sparse decoder tensor shape/dtype mismatch: "+name)
        with tempfile.TemporaryDirectory(prefix=".pixal-sparse-decoder-", dir=output_dir.parent) as tmp:
            directory=Path(tmp)/"result"; directory.mkdir(); output=directory/"model.gguf"
            writer=gguf.GGUFWriter(output, ARCHITECTURE, use_temp_file=True)
            writer.add_name("Pixal3D "+spec["kind"]+" sparse decoder"); writer.add_uint32("pixal.schema_version",1)
            writer.add_string("pixal.reference_revision",PIXAL_REVISION); writer.add_string("pixal.storage",storage)
            writer.add_string("pixal.sparse_decoder.config_json",raw.decode()); writer.add_uint32("pixal.sparse_decoder.stages",len(spec["channels"]))
            for name, value in spec.items():
                if isinstance(value,list):
                    for i,v in enumerate(value): writer.add_uint32(f"pixal.sparse_decoder.{name}.{i}",v)
                else:
                    method=writer.add_bool if type(value) is bool else writer.add_uint32 if type(value) is int else writer.add_float32 if type(value) is float else writer.add_string
                    method("pixal.sparse_decoder."+name,value)
            provenance={"checkpoint_sha256":source_hash,"config_sha256":hashlib.sha256(raw).hexdigest(),"source_repository":source_repository,"source_revision":source_revision,"source_kind":source_kind}
            for name,value in provenance.items(): writer.add_string("pixal."+name,value)
            records={}
            try:
                for name,shape in sorted(shapes.items()):
                    values=tensors.get_tensor(name).float().numpy()
                    if not np.isfinite(values).all(): raise ValueError("non-finite sparse decoder tensor: "+name)
                    packed=(shape[0],27,shape[-1]) if len(shape)==5 else shape
                    with np.errstate(over="ignore"): values=values.reshape(packed).astype(np.float16 if storage=="f16" and len(shape)>1 else np.float32)
                    if not np.isfinite(values).all(): raise ValueError("sparse decoder storage overflow: "+name)
                    writer.add_tensor(name,values)
                    records[name]={"source_shape":shape,"stored_shape":values.shape,"dtype":str(values.dtype),"sha256":hashlib.sha256(values.tobytes()).hexdigest()}
                writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file()
            finally:
                writer.close()
                if writer.temp_file is not None: writer.temp_file.close()
            if digest(checkpoint)!=source_hash or config_path.read_bytes()!=raw: raise ValueError("sparse decoder source changed during conversion")
            report={"schema_version":1,"architecture":ARCHITECTURE,"decoder":spec,"storage":storage,"source":provenance,"tensors":records,"reference_revision":PIXAL_REVISION,
                    "converter_sha256":digest(Path(__file__)),"output_sha256":digest(output),"output_bytes":output.stat().st_size,"adopted":False,
                    "torch_gpu_initialized":torch.cuda.is_initialized(),"packages":{n:importlib.metadata.version(n) for n in ("torch","gguf","numpy","safetensors")}}
            (directory/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
            if output_dir.exists(): raise ValueError("sparse decoder output appeared during conversion")
            directory.rename(output_dir)
    return report


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("checkpoint","config","output-dir"): p.add_argument("--"+n,type=Path,required=True)
    for n in ("source-repository","source-revision"): p.add_argument("--"+n,required=True)
    p.add_argument("--storage",choices=("f32","f16"),default="f32"); p.add_argument("--source-kind",choices=("synthetic","checkpoint"),required=True)
    a=p.parse_args(); r=convert(a.checkpoint,a.config,a.output_dir,storage=a.storage,source_repository=a.source_repository,source_revision=a.source_revision,source_kind=a.source_kind)
    print(json.dumps({k:r[k] for k in ("output_sha256","output_bytes","storage")}))


if __name__=="__main__": main()
