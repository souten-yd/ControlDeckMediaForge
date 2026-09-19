#!/usr/bin/env python3
"""Synthetic source checkpoint -> GGUF -> native RGB/DINO/NAF -> sampled-latent parity."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple, Union

from convert_vision import NAF_REVISION, PIXAL_REVISION, convert, digest


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("naf-source","pixal-source","checkpoint-fixtures","binary","output-dir"):
        parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--backend",choices=("cpu","vulkan"),default="cpu")
    parser.add_argument("--device-index",type=int)
    args=parser.parse_args()
    if (args.backend=="vulkan")!=(args.device_index is not None): parser.error("Vulkan requires an admitted explicit device index")
    for source,revision in ((args.naf_source,NAF_REVISION),(args.pixal_source,PIXAL_REVISION)):
        if subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()!=revision or subprocess.check_output(["git","-C",str(source),"diff","HEAD","--"]):
            parser.error("reference source must be pinned with no tracked changes")
    if args.output_dir.exists(): parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES":"-1","ROCR_VISIBLE_DEVICES":"-1","CUDA_VISIBLE_DEVICES":"-1",
                       "HF_HUB_OFFLINE":"1","ATTN_BACKEND":"sdpa","SPARSE_ATTN_BACKEND":"sdpa","SPARSE_CONV_BACKEND":"none"})
    sys.path[:0]=[str(args.naf_source.resolve()),str(args.pixal_source.resolve())]
    import gguf
    import numpy as np
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from torchvision import transforms
    from transformers import DINOv3ViTConfig,DINOv3ViTModel
    from transformers.models.dinov3_vit import modeling_dinov3_vit
    from safetensors.torch import load_file,save_file
    from natten import na2d
    from natten.backends import flex
    from src.model.naf import NAF
    from src.layers import attentions
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler
    if importlib.metadata.version("transformers")!="4.57.3" or importlib.metadata.version("natten")!="0.21.0" or not attentions.NATTEN_RECENT:
        raise ValueError("use pinned reference packages")
    torch.set_num_threads(2)
    def cpu_attention(q,k,v,**kwargs):
        assert kwargs.pop("backend")=="cutlass-fna"
        width=q.shape[-1]; result=[]
        for start in range(0,v.shape[-1],width):
            part=v[...,start:start+width]; n=part.shape[-1]
            result.append(na2d(q,k,F.pad(part,(0,width-n)),**kwargs,backend="flex-fna",torch_compile=False)[...,:n])
        return torch.cat(result,dim=-1)
    attentions.na2d=cpu_attention
    reference=args.pixal_source/"pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"
    names={"project_points_to_image_batch","sample_features","ProjGrid","DinoV3ProjFeatureExtractor"}
    nodes=[n for n in ast.parse(reference.read_text()).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    assert len(nodes)==len(names)
    namespace={"torch":torch,"nn":torch.nn,"F":F,"np":np,"Image":Image,"transforms":transforms,
               "Tuple":Tuple,"Optional":Optional,"Union":Union,"List":List,"DINOv3ViTModel":DINOv3ViTModel}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(reference),"exec"),namespace)
    args.output_dir.mkdir(parents=True)
    provenance={"source_repository":"mediaforge/synthetic-vision-check","source_revision":PIXAL_REVISION,"source_kind":"synthetic"}
    reports=[]
    for case in ("f32_full","bf16_f16_storage","no_bias","qk_bias","naf_torch_archive","ss_lr_only","f16_source"):
        directory=args.output_dir/case; directory.mkdir()
        torch.manual_seed(62971)
        with_high=case!="ss_lr_only"; storage="f16" if case=="bf16_f16_storage" else "f32"
        dtype={"bf16_f16_storage":torch.bfloat16,"f16_source":torch.float16}.get(case,torch.float32)
        size=12; out_w,out_h=(9,7) if case=="no_bias" else (8,8)
        config=DINOv3ViTConfig(hidden_size=32,intermediate_size=64,num_hidden_layers=2,num_attention_heads=4,patch_size=4,
            image_size=size,num_register_tokens=4,query_bias=case!="no_bias",key_bias=case=="qk_bias",
            value_bias=case not in {"no_bias","qk_bias"},proj_bias=case!="no_bias",mlp_bias=case!="no_bias",
            layer_norm_eps=2e-5 if case=="qk_bias" else 1e-5,rope_theta=123. if case=="qk_bias" else 100.)
        config._attn_implementation="sdpa"
        dino=DINOv3ViTModel(config).eval()
        naf_args={"dim":64 if case=="qk_bias" else 32,"heads_attn":4,"heads_rope":2,"kernel_size":3,
                  "use_encoder":True,"rope_base":100.,"rope_rescale":2.,"img_layers":0 if case=="no_bias" else 2}
        naf=NAF(**naf_args).eval()
        conversions={}; serialized={}
        for kind,model,cfg in (("dino",dino,config.to_dict()),("naf",naf,{"name":"NAF","args":naf_args})):
            if kind=="naf" and not with_high: continue
            with torch.no_grad():
                for name,param in model.named_parameters():
                    if name.endswith("lambda1") or ("norm" in name and name.endswith("weight")): param.normal_(1.,.04)
                    elif param.ndim>=2: param.normal_(0.,.5/math.sqrt(param[0].numel()))
                    else: param.normal_(0.,.1)
                if kind=="naf" and case=="qk_bias": model.image_encoder.rope.periods.mul_(1.3)
            part=directory/kind; part.mkdir()
            state={name:value.detach().to(dtype).contiguous() for name,value in model.state_dict().items()}
            fmt="torch-weights-only" if kind=="naf" and case=="naf_torch_archive" else "safetensors"
            checkpoint=part/("source.pth" if fmt=="torch-weights-only" else "source.safetensors")
            if fmt=="torch-weights-only": torch.save(state,checkpoint)
            else: save_file(state,checkpoint,metadata={"source":"synthetic; no pretrained weights"})
            (part/"config.json").write_text(json.dumps(cfg,indent=2)+"\n")
            conversions[kind]=convert(checkpoint,part/"config.json",part/"converted",kind=kind,storage=storage,input_format=fmt,**provenance)
            # Reference applies only declared storage rounding to original source
            # tensors, independently of the converter's canonical name mapping.
            rounded={}
            for name,value in state.items():
                v=value.float()
                if storage=="f16" and name.endswith(".weight") and v.ndim in (2,4): v=v.half().float()
                rounded[name]=v
            model.load_state_dict(rounded,strict=True)
            serialized[kind]=gguf.GGUFReader(part/"converted/model.gguf")
        extractor=namespace["DinoV3ProjFeatureExtractor"].__new__(namespace["DinoV3ProjFeatureExtractor"])
        torch.nn.Module.__init__(extractor)
        extractor.model=dino; extractor.image_size=size; extractor.patch_number=3
        extractor.transform=transforms.Normalize([.485,.456,.406],[.229,.224,.225])
        extractor.use_naf_upsample=with_high; extractor.naf_model=naf; extractor.naf_target_size=(out_h,out_w)
        grid=4 if with_high else 2; extractor.proj_grid=namespace["ProjGrid"](grid,size)
        expected={}
        def capture(label: str,hwc: bool=False):
            def hook(_module,_inputs,value):
                if isinstance(value,tuple): value=value[0]
                if hwc: value=value.permute(0,2,3,1)
                expected[label]=value.detach().contiguous().numpy().reshape(-1).copy()
            return hook
        dino.embeddings.register_forward_hook(capture("dino.embedding"))
        for i,block in enumerate(dino.layer):
            block.attention.register_forward_hook(capture(f"dino.blocks.{i}.attention"))
            block.mlp.register_forward_hook(capture(f"dino.blocks.{i}.mlp"))
            block.register_forward_hook(capture(f"dino.blocks.{i}.output"))
        for branch in ("encoder","sem_encoder"):
            for i,block in enumerate(getattr(naf.image_encoder,branch)): block.register_forward_hook(capture(f"naf.{branch}.{i}"))
        naf.query_encoder.register_forward_hook(capture("naf.query",True)); naf.key_encoder.register_forward_hook(capture("naf.key",True))
        naf.register_forward_hook(capture("high",True))
        def guide_hook(_module,values): expected["naf.guide"]=values[0].detach().numpy().reshape(-1).copy()
        def pooled_hook(_module,values): expected["naf.pooled"]=values[0].detach().numpy().reshape(-1).copy()
        naf.image_encoder.encoder.register_forward_pre_hook(guide_hook); naf.image_encoder.rope.register_forward_pre_hook(pooled_hook)
        rgb=torch.rand(1,3,size,size); camera=[torch.tensor([v]) for v in (.857556,2.,1.)]
        with torch.no_grad():
            global_features,projected=extractor(rgb,*camera)
            tokens=extractor.extract_features(extractor.transform(rgb))
        coords=torch.tensor([[3,1,0],[0,0,2],[2,3,1],[3,1,0],[1,1,2],[0,3,0],[2,2,2]]) if with_high else torch.cartesian_prod(torch.arange(2),torch.arange(2),torch.arange(2))
        if with_high: projected=projected.reshape(1,4,4,4,-1)[:,coords[:,0],coords[:,1],coords[:,2]]
        expected.update({"dino.normalized":extractor.transform(rgb).numpy().reshape(-1),"dino.tokens":tokens.numpy().reshape(-1),
                         "global":global_features.numpy().reshape(-1),"patches":tokens[:,5:].numpy().reshape(-1),
                         "projected":projected.numpy().reshape(-1),"negative_projected":np.zeros(projected.numel(),np.float32)})
        base=args.checkpoint_fixtures/("shape_f32_f32" if with_high else "ss_f32_f32")
        manifest=json.loads((base/"converted/manifest.json").read_text())
        if manifest["source"]["source_kind"]!="synthetic" or digest(base/"converted/model.gguf")!=manifest["output_sha256"]: raise ValueError("use intact synthetic flow checkpoints")
        flow_cfg=json.loads((base/"config.json").read_text())
        flow=(ElasticSLatFlowModel if with_high else SparseStructureFlowModel)(**flow_cfg["args"]).eval()
        flow.load_state_dict(load_file(base/"source.safetensors"),strict=False)
        noise=torch.from_numpy(np.load(base/"input.npy",allow_pickle=False))
        if with_high:
            sc=torch.cat([torch.zeros(len(coords),1,dtype=coords.dtype),coords],dim=1).int()
            xt=SparseTensor(noise,sc); pos={"global":global_features,"proj":SparseTensor(projected[0],sc)}
            neg={"global":torch.zeros_like(global_features),"proj":SparseTensor(torch.zeros_like(projected[0]),sc)}
        else:
            xt=noise.T.reshape(1,8,2,2,2); pos={"global":global_features,"proj":projected}
            neg={"global":torch.zeros_like(global_features),"proj":torch.zeros_like(projected)}
        samples=FlowEulerGuidanceIntervalSampler(1e-5).sample(flow,xt,pos,neg,steps=3,guidance_strength=2.5,guidance_rescale=.3,guidance_interval=(0,1),verbose=False)
        for i,value in enumerate(samples.pred_x_t): expected["sample"+str(i)]=(value.feats if with_high else value[0].reshape(8,-1).T.contiguous()).numpy().reshape(-1)
        for name,value in expected.items(): np.save(directory/("expected_"+name+".npy"),value)
        np.save(directory/"rgb.npy",rgb[0].numpy()); np.save(directory/"coordinates.npy",coords.numpy().astype(np.float32))
        np.save(directory/"camera.npy",np.array([.857556,2.,1.,grid],np.float32)); np.save(directory/"target.npy",np.array([out_w,out_h],np.float32))
        np.save(directory/"noise.npy",noise.numpy())
        command=[str(args.binary.resolve()),str(directory.resolve()),args.backend,"--dino",str((directory/"dino/converted/model.gguf").resolve()),"--flow",str((base/"converted/model.gguf").resolve())]
        if with_high: command += ["--naf",str((directory/"naf/converted/model.gguf").resolve())]
        if args.device_index is not None: command += ["--device",str(args.device_index)]
        native=subprocess.run(command,capture_output=True,text=True,timeout=120)
        (directory/"native.log").write_text(native.stdout+native.stderr)
        record={"case":case,"returncode":native.returncode,"passed":False,"tensors":{},"serialized_values_equal":False}
        if native.returncode==0:
            for name,value in expected.items():
                actual=np.load(directory/("actual_"+name+".npy"),allow_pickle=False)
                record["tensors"][name]={"passed":actual.shape==value.shape and bool(np.allclose(actual,value,atol=5e-5,rtol=5e-5)),"max_abs_error":float(np.max(np.abs(actual-value)))}
            weights_equal=True; tensor_count=0
            for kind,reader in serialized.items():
                for tensor in reader.tensors:
                    array=np.asarray(tensor.data); entry=conversions[kind]["tensors"][tensor.name]
                    actual=np.load(directory/("actual_weight."+kind+"."+tensor.name+".npy"),allow_pickle=False)
                    weights_equal &= bool(np.array_equal(actual,array.astype(np.float32).reshape(-1))) and \
                        list(array.shape)==entry["shape"] and hashlib.sha256(array.tobytes()).hexdigest()==entry["sha256"]
                    tensor_count+=1
            record["serialized_values_equal"]=weights_equal; record["serialized_tensors"]=tensor_count
            record["passed"]=weights_equal and all(t["passed"] for t in record["tensors"].values()) and "borrowed_backend_retained=true" in native.stdout
        reports.append(record); print(json.dumps(record),flush=True)
    # Conversion failures must leave no converted artifact. An unsupported
    # object is rejected by weights_only; never retry with unsafe unpickling.
    baseline=args.output_dir/"f32_full"; negative=args.output_dir/"negative"; negative.mkdir()
    converter_checks={}
    for case in ("unknown_config","gated_mlp","bad_heads","missing_tensor","extra_tensor","wrong_shape","integer_dtype","nonfinite","overflow","invalid_period","wrapped_pth","unsafe_pth","duplicate_json","existing_output"):
        kind="naf" if case in {"invalid_period","wrapped_pth","unsafe_pth"} else "dino"
        cfg=json.loads((baseline/kind/"config.json").read_text()); state=load_file(baseline/kind/"source.safetensors")
        directory=negative/case; directory.mkdir(); fmt="safetensors"; storage="f32"
        if case=="unknown_config": cfg["unimplemented_switch"]=True
        elif case=="gated_mlp": cfg["use_gated_mlp"]=True
        elif case=="bad_heads": cfg["num_attention_heads"]=3
        elif case=="missing_tensor": state.pop("embeddings.cls_token")
        elif case=="extra_tensor": state["extra"]=torch.zeros(1)
        elif case=="wrong_shape": state["embeddings.cls_token"]=state["embeddings.cls_token"][...,:-1].contiguous()
        elif case=="integer_dtype": state["embeddings.cls_token"]=state["embeddings.cls_token"].int()
        elif case=="nonfinite": state["norm.bias"][0]=float("nan") # unused still validated
        elif case=="overflow": state["embeddings.patch_embeddings.weight"].flatten()[0]=1e6; storage="f16"
        elif case=="invalid_period": state["image_encoder.rope.periods"][0]=0
        elif case in {"wrapped_pth","unsafe_pth"}: fmt="torch-weights-only"
        checkpoint=directory/("source.pth" if fmt!="safetensors" else "source.safetensors")
        if fmt=="safetensors": save_file(state,checkpoint)
        else: torch.save({"state_dict":state} if case=="wrapped_pth" else {"object":Path("not-a-tensor")},checkpoint)
        cp=directory/"config.json"; cp.write_text(json.dumps(cfg))
        if case=="duplicate_json": cp.write_text('{"hidden_size":32,"hidden_size":64}')
        output=directory/"converted"
        if case=="existing_output": output.mkdir(); (output/"sentinel").write_text("keep")
        try:
            convert(checkpoint,cp,output,kind=kind,storage=storage,input_format=fmt,**provenance)
            converter_checks[case]={"passed":False}
        except (ValueError,pickle.UnpicklingError) as exc:
            converter_checks[case]={"passed":not (output/"model.gguf").exists() and (not output.exists() or (case=="existing_output" and (output/"sentinel").read_text()=="keep")),"error":str(exc)}
    deterministic={}
    for kind in ("dino","naf"):
        part=baseline/kind
        repeated=convert(part/"source.safetensors",part/"config.json",part/"repeated",kind=kind,storage="f32",**provenance)
        deterministic[kind]=repeated["output_sha256"]==digest(part/"converted/model.gguf")
    native_checks={}
    mutations={"schema":("pixal.schema_version",99),"kind":("pixal.vision.kind","bad"),"reference":("pixal.vision.reference_revision","bad"),
               "missing_metadata":("pixal.vision.channels",None),"heads":("pixal.vision.heads",3),"source_hash":("pixal.checkpoint_sha256","bad"),
               "tensor_name":(None,None),"tensor_shape":(None,None),"tensor_type":(None,None),"truncated":(None,None),"nan_weight":(None,None),
               "naf_heads":("pixal.vision.heads",3),"naf_kernel":("pixal.vision.kernel",4),
               "naf_missing_period":(None,None),"naf_invalid_period":(None,None)}
    for case,(changed_key,changed_value) in mutations.items():
        is_naf=case.startswith("naf_")
        reader=gguf.GGUFReader(baseline/("naf" if is_naf else "dino")/"converted/model.gguf"); path=negative/("native_"+case+".gguf")
        writer=gguf.GGUFWriter(path,"pixal3d-vision")
        for key,field in reader.fields.items():
            if key.startswith("GGUF.") or key=="general.architecture" or (key==changed_key and changed_value is None): continue
            writer.add_key_value(key,changed_value if key==changed_key else field.contents(),field.types[0])
        for i,tensor in enumerate(reader.tensors):
            name="unexpected" if (case=="tensor_name" and i==0) or (case=="naf_missing_period" and tensor.name=="image_encoder.rope.periods") else tensor.name
            value=np.asarray(tensor.data).copy()
            if case=="tensor_shape" and i==0: value=value.reshape(-1)[:-1]
            if case=="tensor_type" and i==0: value=value.astype(np.float16)
            if case=="nan_weight" and i==0: value.flat[0]=float("nan")
            if case=="naf_invalid_period" and tensor.name=="image_encoder.rope.periods": value.flat[0]=0.
            writer.add_tensor(name,value)
        writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file(); writer.close()
        if case=="truncated":
            with path.open("r+b") as f: f.truncate(path.stat().st_size-128)
        fixture=negative/("fixture_"+case); fixture.mkdir()
        flags=["--dino",str(baseline/"dino/converted/model.gguf"),"--naf",str(path)] if is_naf else ["--dino",str(path)]
        result=subprocess.run([str(args.binary.resolve()),str(fixture),"cpu",*flags],capture_output=True,text=True,timeout=30)
        preallocation=case not in {"nan_weight","naf_invalid_period"}
        native_checks[case]={"passed":result.returncode==1 and not list(fixture.glob("actual_*")) and
                            (not preallocation or "backend_initialized=" not in result.stdout),"preallocation":preallocation,
                            "returncode":result.returncode,"stderr":result.stderr.strip()}
    for case,flags in (("wrong_component",["--dino",str(baseline/"naf/converted/model.gguf")]),
                       ("cancel_before",["--dino",str(baseline/"dino/converted/model.gguf"),"--cancel-at","1"]),
                       ("cancel_after_dino",["--dino",str(baseline/"dino/converted/model.gguf"),"--cancel-at","2"]),
                       ("missing_target",["--dino",str(baseline/"dino/converted/model.gguf"),"--naf",str(baseline/"naf/converted/model.gguf")])):
        fixture=negative/case; fixture.mkdir()
        for name in ("rgb","target"): shutil.copyfile(baseline/(name+".npy"),fixture/(name+".npy"))
        if case=="missing_target": np.save(fixture/"target.npy",np.zeros(2,np.float32))
        result=subprocess.run([str(args.binary.resolve()),str(fixture),"cpu",*flags],capture_output=True,text=True,timeout=30)
        marker="target size" if case=="missing_target" else "wrong component" if case=="wrong_component" else "cancelled"
        native_checks[case]={"passed":result.returncode==1 and not list(fixture.glob("actual_*")) and marker in result.stderr,"stderr":result.stderr.strip()}
    report={"passed":all(c["passed"] for c in reports) and all(c["passed"] for c in converter_checks.values()) and all(c["passed"] for c in native_checks.values()) and all(deterministic.values()),
            "cases":reports,"converter_negative_checks":converter_checks,"native_negative_checks":native_checks,"deterministic_gguf_bytes":deterministic,
            "pixal_revision":PIXAL_REVISION,"naf_revision":NAF_REVISION,"pixal_reference_sha256":digest(reference),
            "transformers_reference_sha256":digest(Path(modeling_dinov3_vit.__file__)),"natten_flex_sha256":digest(Path(flex.__file__)),
            "attention_reference":"original NAF forward, cutlass backend replaced by CPU NATTEN flex-fna with independent V channel chunks/padding",
            "backend":args.backend,"device_index":args.device_index,"binary_sha256":digest(args.binary),"torch_gpu_initialized":torch.cuda.is_initialized(),
            "pretrained_weights":"NOT USED","arithmetic":"F32 including converted F16 storage","full_generation_adoption_library":"NOT TESTED"}
    (args.output_dir/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"passed":report["passed"],"cases":len(reports),"converter_negatives":len(converter_checks),"native_negatives":len(native_checks)}),flush=True)
    return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
