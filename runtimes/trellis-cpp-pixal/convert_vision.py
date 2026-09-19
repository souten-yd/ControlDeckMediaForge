#!/usr/bin/env python3
"""Convert authorized local DINOv3/NAF weights to strict native vision GGUF.

Worker environment only. No download, hub entrypoint, model instantiation or
GPU use. NAF torch archives require explicit weights-only format selection;
there is no unsafe pickle fallback. Conversion is not runtime adoption.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterator

from convert_flow import PIXAL_REVISION, digest, unique_object

ARCHITECTURE="pixal3d-vision"
NAF_REVISION="37f2dfc180f2de53d98bd601109c0da0dd6b0f43"
REFERENCE={"dino":"transformers-4.57.3","naf":NAF_REVISION}


def integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"invalid {name}")
    return value


def real(value: Any, name: str, minimum: float, maximum: float) -> float:
    if type(value) not in (int,float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"invalid {name}")
    return float(value)


def vision_spec(config: dict[str, Any], kind: str) -> dict[str, Any]:
    if not isinstance(config,dict) or kind not in REFERENCE:
        raise ValueError("invalid vision configuration/kind")
    if kind=="dino":
        if importlib.metadata.version("transformers")!="4.57.3":
            raise ValueError("use the pinned transformers config definition")
        from transformers import DINOv3ViTConfig
        # Config construction only: does not instantiate a model or resolve a URL.
        defaults=DINOv3ViTConfig().to_dict()
        if set(config)-set(defaults)-{"torch_dtype","_name_or_path"}:
            raise ValueError("unknown DINO configuration fields")
        c=defaults | config
        if c["model_type"]!="dinov3_vit" or c["hidden_act"]!="gelu" or type(c["num_channels"]) is not int or c["num_channels"]!=3 or c["use_gated_mlp"] is not False:
            raise ValueError("native DINO requires RGB/plain GELU ViT")
        fields={"channels":("hidden_size",8,4096),"heads":("num_attention_heads",1,128),
                "layers":("num_hidden_layers",1,48),"patch_size":("patch_size",1,32),
                "registers":("num_register_tokens",1,16),"mlp_channels":("intermediate_size",8,16384)}
        spec={key:integer(c[name],name,lo,hi) for key,(name,lo,hi) in fields.items()}
        if spec["channels"]%spec["heads"] or (spec["channels"]//spec["heads"])%4 or spec["mlp_channels"]<spec["channels"]:
            raise ValueError("invalid DINO head/MLP dimensions")
        for key in ("query_bias","key_bias","value_bias","proj_bias","mlp_bias"):
            if type(c[key]) is not bool: raise ValueError(f"invalid {key}")
            spec[key]=c[key]
        spec["qkv_bias"]=any(spec[key] for key in ("query_bias","key_bias","value_bias"))
        spec["norm_epsilon"]=real(c["layer_norm_eps"],"layer_norm_eps",1e-12,1.)
        spec["rope_theta"]=real(c["rope_theta"],"rope_theta",1e-6,1e6)
        return spec
    if set(config)-{"name","args"} or config.get("name")!="NAF" or not isinstance(config.get("args"),dict):
        raise ValueError("NAF expects an explicit {name: NAF, args: {...}} inference config")
    c={"dim":256,"heads_attn":4,"heads_rope":4,"kernel_size":9,"use_encoder":True,
       "rope_base":100.,"rope_rescale":2.,"img_layers":2} | config["args"]
    if set(c)-{"dim","heads_attn","heads_rope","kernel_size","use_encoder","rope_base","rope_rescale","img_layers"} or c["use_encoder"] is not True:
        raise ValueError("unsupported NAF arguments/encoder-disabled variant")
    real(c["rope_base"],"rope_base",1e-6,1e6)
    if c["rope_rescale"] is not None: real(c["rope_rescale"],"rope_rescale",1e-6,1e6)
    fields={"channels":("dim",16,512),"heads":("heads_attn",1,16),"rope_heads":("heads_rope",1,16),
            "layers":("img_layers",0,4),"kernel":("kernel_size",3,15)}
    spec={key:integer(c[name],name,lo,hi) for key,(name,lo,hi) in fields.items()}
    if spec["channels"]%16 or spec["channels"]%spec["heads"] or spec["channels"]%(4*spec["rope_heads"]) or spec["kernel"]%2==0:
        raise ValueError("invalid NAF head/group/kernel dimensions")
    return spec


def tensor_plan(kind: str, s: dict[str, Any]) -> tuple[dict[str, tuple[int,...]],dict[str, list[str | None]],dict[str,str]]:
    """Exact source shapes, native-to-source mapping and intentionally unused tensors."""
    shapes: dict[str,tuple[int,...]]={}; mapping: dict[str,list[str|None]]={}; unused: dict[str,str]={}
    def direct(source: str, target: str, shape: tuple[int,...]) -> None:
        shapes[source]=shape; mapping[target]=[source]
    D=s["channels"]
    if kind=="dino":
        direct("embeddings.patch_embeddings.weight","patch_embed.proj.weight",(D,3,s["patch_size"],s["patch_size"]))
        direct("embeddings.patch_embeddings.bias","patch_embed.proj.bias",(D,))
        direct("embeddings.cls_token","cls_token",(1,1,D))
        direct("embeddings.register_tokens","reg_token",(1,s["registers"],D))
        for name,shape,reason in (("embeddings.mask_token",(1,1,D),"Pixal does not mask input patches"),
                                  ("norm.weight",(D,),"Pixal uses non-affine final F.layer_norm"),
                                  ("norm.bias",(D,),"Pixal uses non-affine final F.layer_norm")):
            shapes[name]=shape; unused[name]=reason
        for i in range(s["layers"]):
            src=f"layer.{i}"; dst=f"blocks.{i}"
            for norm in ("norm1","norm2"):
                for part in ("weight","bias"): direct(f"{src}.{norm}.{part}",f"{dst}.{norm}.{part}",(D,))
            for part in ("weight","bias"):
                names=[]
                for label,key in (("q","query_bias"),("k","key_bias"),("v","value_bias")):
                    name=f"{src}.attention.{label}_proj.{part}"
                    if part=="bias" and not s[key]: names.append(None)
                    else:
                        shapes[name]=(D,D) if part=="weight" else (D,)
                        names.append(name)
                if part=="weight" or s["qkv_bias"]: mapping[f"{dst}.attn.qkv.{part}"]=names
            for source,target,out,inp,bias in (("attention.o_proj","attn.proj",D,D,s["proj_bias"]),
                    ("mlp.up_proj","mlp.fc1",s["mlp_channels"],D,s["mlp_bias"]),
                    ("mlp.down_proj","mlp.fc2",D,s["mlp_channels"],s["mlp_bias"])):
                direct(f"{src}.{source}.weight",f"{dst}.{target}.weight",(out,inp))
                if bias: direct(f"{src}.{source}.bias",f"{dst}.{target}.bias",(out,))
            for j in (1,2): direct(f"{src}.layer_scale{j}.lambda1",f"{dst}.gamma_{j}",(D,))
    else:
        for branch,kernel in (("encoder",1),("sem_encoder",3)):
            prefix="image_encoder."+branch
            for name,shape in ((prefix+".0.weight",(D//2,3,kernel,kernel)),(prefix+".0.bias",(D//2,))): direct(name,name,shape)
            for i in range(1,s["layers"]+1):
                for j in (1,2):
                    for part in ("weight","bias"):
                        name=f"{prefix}.{i}.norm{j}.{part}"; direct(name,name,(D//2,))
                        name=f"{prefix}.{i}.conv{j}.{part}"
                        direct(name,name,(D//2,D//2,kernel,kernel) if part=="weight" else (D//2,))
        name="image_encoder.rope.periods"; direct(name,name,(D//s["rope_heads"]//4,))
    return shapes,mapping,unused


@contextmanager
def tensor_source(path: Path, fmt: str) -> Iterator[Any]:
    import torch
    from safetensors import safe_open
    if fmt=="safetensors":
        with safe_open(path,framework="pt",device="cpu") as values: yield values
        return
    if fmt!="torch-weights-only" or not torch.__version__.startswith("2.10.0"):
        raise ValueError("NAF torch archives require the pinned torch2.10.0 weights-only reader")
    state=torch.load(path,map_location="cpu",weights_only=True,mmap=True)
    if type(state) not in (dict,OrderedDict) or not all(isinstance(k,str) and type(v) is torch.Tensor for k,v in state.items()):
        raise ValueError("NAF archive must contain a plain tensor state_dict without wrapper objects")
    class View:
        def __init__(self, tensor: Any): self.tensor=tensor
        def get_shape(self) -> list[int]: return list(self.tensor.shape)
        def get_dtype(self) -> str:
            return {torch.float32:"F32",torch.float16:"F16",torch.bfloat16:"BF16"}.get(self.tensor.dtype,"unsupported")
    class State:
        def keys(self) -> Any: return state.keys()
        def get_slice(self, name: str) -> View: return View(state[name])
        def get_tensor(self, name: str) -> Any: return state[name]
    yield State()


def convert(checkpoint: Path, config_path: Path, output_dir: Path, *, kind: str, storage: str,
            source_repository: str, source_revision: str, source_kind: str, input_format: str="safetensors") -> dict[str,Any]:
    if kind not in REFERENCE or storage not in {"f32","f16"} or source_kind not in {"synthetic","checkpoint"} or \
            input_format not in ({"safetensors","torch-weights-only"} if kind=="naf" else {"safetensors"}):
        raise ValueError("invalid vision conversion kind/storage/format/source")
    if not re.fullmatch(r"[0-9a-f]{40}",source_revision) or not re.fullmatch(r"[\w./-]{1,200}",source_repository):
        raise ValueError("source repository and full revision required")
    checkpoint=checkpoint.resolve(strict=True); config_path=config_path.resolve(strict=True); output_dir=output_dir.resolve()
    if output_dir.exists(): raise ValueError("output directory already exists; refusing overwrite")
    if not checkpoint.is_file() or not 8<=checkpoint.stat().st_size<=(32 if kind=="dino" else 1)*1024**3:
        raise ValueError("invalid checkpoint size/type")
    if not config_path.is_file() or config_path.stat().st_size>65536: raise ValueError("invalid config size/type")
    raw_config=config_path.read_bytes(); config=json.loads(raw_config,object_pairs_hook=unique_object)
    os.environ.update({"HIP_VISIBLE_DEVICES":"-1","ROCR_VISIBLE_DEVICES":"-1","CUDA_VISIBLE_DEVICES":"-1","HF_HUB_OFFLINE":"1"})
    spec=vision_spec(config,kind); shapes,mapping,unused=tensor_plan(kind,spec)
    source_hash=digest(checkpoint)
    import gguf
    import numpy as np
    import torch
    if importlib.metadata.version("gguf")!="0.19.0": raise ValueError("use pinned gguf-lock.txt")
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tensor_source(checkpoint,input_format) as tensors:
        if set(tensors.keys())!=set(shapes):
            raise ValueError(f"vision tensor set mismatch: missing={sorted(set(shapes)-set(tensors.keys()))}, extra={sorted(set(tensors.keys())-set(shapes))}")
        for name,shape in shapes.items():
            view=tensors.get_slice(name)
            if tuple(view.get_shape())!=shape or view.get_dtype() not in {"F32","F16","BF16"}:
                raise ValueError(f"vision tensor shape/dtype mismatch: {name}")
        records={}; unused_records={}
        def read(name: str) -> Any:
            values=tensors.get_tensor(name).detach().float().numpy()
            if not np.isfinite(values).all(): raise ValueError(f"non-finite vision tensor: {name}")
            if name=="image_encoder.rope.periods" and not (values>0).all(): raise ValueError("NAF periods must be positive")
            return values
        with tempfile.TemporaryDirectory(prefix=".pixal-vision-",dir=output_dir.parent) as temporary:
            directory=Path(temporary)/"result"; directory.mkdir(); result=directory/"model.gguf"
            writer=gguf.GGUFWriter(result,ARCHITECTURE,use_temp_file=True)
            writer.add_name("Pixal3D "+kind+" image features")
            writer.add_uint32("pixal.schema_version",1); writer.add_string("pixal.vision.kind",kind)
            writer.add_string("pixal.storage",storage); writer.add_string("pixal.reference_revision",PIXAL_REVISION)
            writer.add_string("pixal.vision.reference_revision",REFERENCE[kind]); writer.add_string("pixal.vision.config_json",raw_config.decode())
            for name,value in spec.items():
                method=writer.add_bool if type(value) is bool else writer.add_uint32 if type(value) is int else writer.add_float32
                method("pixal.vision."+name,value)
            provenance={"checkpoint_sha256":source_hash,"config_sha256":hashlib.sha256(raw_config).hexdigest(),
                        "source_repository":source_repository,"source_revision":source_revision,"source_kind":source_kind,"input_format":input_format}
            for name,value in provenance.items(): writer.add_string("pixal."+name,value)
            try:
                for name,reason in unused.items():
                    values=read(name)
                    unused_records[name]={"reason":reason,"shape":list(values.shape),"f32_sha256":hashlib.sha256(values.tobytes()).hexdigest()}
                for name,sources in sorted(mapping.items()):
                    if len(name.encode())>=64: raise ValueError("vision tensor name exceeds GGML capacity")
                    parts=[read(source) if source else np.zeros(spec["channels"],np.float32) for source in sources]
                    values=parts[0] if len(parts)==1 else np.concatenate(parts,axis=0)
                    half=storage=="f16" and name.endswith(".weight") and values.ndim in {2,4}
                    with np.errstate(over="ignore"): values=values.astype(np.float16 if half else np.float32)
                    if not np.isfinite(values).all(): raise ValueError(f"vision tensor overflows storage: {name}")
                    writer.add_tensor(name,values)
                    records[name]={"shape":list(values.shape),"dtype":str(values.dtype),"sha256":hashlib.sha256(values.tobytes()).hexdigest(),"sources":sources}
                writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file()
            finally:
                writer.close()
                if writer.temp_file is not None: writer.temp_file.close()
            if digest(checkpoint)!=source_hash or config_path.read_bytes()!=raw_config:
                raise ValueError("vision source changed during conversion")
            manifest={"schema_version":1,"architecture":ARCHITECTURE,"kind":kind,"storage":storage,"vision":spec,
                      "source":provenance,"tensors":records,"unused_source_tensors":unused_records,
                      "reference_revision":REFERENCE[kind],"pixal_revision":PIXAL_REVISION,"converter_sha256":digest(Path(__file__)),
                      "packages":{name:importlib.metadata.version(name) for name in ("gguf","safetensors","numpy","torch","transformers")},
                      "output_sha256":digest(result),"output_bytes":result.stat().st_size,"torch_gpu_initialized":torch.cuda.is_initialized(),"adopted":False}
            (directory/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
            if output_dir.exists(): raise ValueError("output directory appeared during conversion")
            directory.rename(output_dir)
    return manifest


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ("checkpoint","config","output-dir"): parser.add_argument("--"+flag,required=True,type=Path)
    parser.add_argument("--kind",required=True,choices=("dino","naf"))
    parser.add_argument("--storage",choices=("f32","f16"),default="f32")
    parser.add_argument("--input-format",choices=("safetensors","torch-weights-only"),default="safetensors")
    parser.add_argument("--source-repository",required=True); parser.add_argument("--source-revision",required=True)
    parser.add_argument("--source-kind",required=True,choices=("synthetic","checkpoint"))
    args=parser.parse_args()
    report=convert(args.checkpoint,args.config,args.output_dir,kind=args.kind,storage=args.storage,input_format=args.input_format,
                   source_repository=args.source_repository,source_revision=args.source_revision,source_kind=args.source_kind)
    print(json.dumps({k:report[k] for k in ("kind","storage","output_sha256","output_bytes")}))


if __name__=="__main__": main()
