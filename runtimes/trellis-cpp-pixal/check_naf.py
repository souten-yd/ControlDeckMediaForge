#!/usr/bin/env python3
"""CPU reference for native NAF -> projected shape conditioning -> sampled latent.

Uses pinned NAF with synthetic parameters and NATTEN's real flex-fna backend.
The hard-coded cutlass backend is redirected to CPU flex-fna, with independent
V-channel chunks/padding to meet its head-width constraint. The checker does
not implement a replacement attention formula or neighborhood mask.
"""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Tuple

from convert_flow import PIXAL_REVISION, digest

NAF_REVISION="37f2dfc180f2de53d98bd601109c0da0dd6b0f43"


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--naf-source",required=True,type=Path)
    parser.add_argument("--pixal-source",required=True,type=Path)
    parser.add_argument("--checkpoint-fixtures",required=True,type=Path)
    parser.add_argument("--binary",required=True,type=Path)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--backend",choices=("cpu","vulkan"),default="cpu")
    parser.add_argument("--device-index",type=int)
    args=parser.parse_args()
    if (args.backend=="vulkan")!=(args.device_index is not None): parser.error("Vulkan requires an admitted explicit device index")
    for source,revision in ((args.naf_source,NAF_REVISION),(args.pixal_source,PIXAL_REVISION)):
        if subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()!=revision or \
                subprocess.check_output(["git","-C",str(source),"diff","HEAD","--"]):
            parser.error("reference source must be pinned without tracked changes")
    if args.output_dir.exists(): parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES":"-1","ROCR_VISIBLE_DEVICES":"-1","CUDA_VISIBLE_DEVICES":"-1",
                       "HF_HUB_OFFLINE":"1","ATTN_BACKEND":"sdpa","SPARSE_ATTN_BACKEND":"sdpa","SPARSE_CONV_BACKEND":"none"})
    sys.path[:0]=[str(args.naf_source.resolve()),str(args.pixal_source.resolve())]
    import numpy as np
    import torch
    import torch.nn.functional as F
    from natten import na2d
    from natten.backends import flex
    from src.model.naf import NAF
    from src.layers import attentions
    from safetensors.torch import load_file
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler
    if importlib.metadata.version("natten")!="0.21.0" or not attentions.NATTEN_RECENT:
        raise ValueError("use the pinned NATTEN dependency")
    torch.set_num_threads(2)
    backend_calls=[]
    def cpu_na2d(*values,**kwargs):
        assert kwargs.pop("backend")=="cutlass-fna"
        backend_calls.append({"query":list(values[0].shape),"value":list(values[2].shape),"dilation":list(kwargs["dilation"])})
        q,k,v=values
        # CPU flex-fna requires equal QK/V head widths; cutlass supports the
        # differing widths used by NAF. Split/pad ONLY independent V channels,
        # keeping Q, K, scale and the official NATTEN neighborhood unchanged.
        width=q.shape[-1]
        outputs=[]
        for start in range(0,v.shape[-1],width):
            part=v[...,start:start+width]; count=part.shape[-1]
            part=F.pad(part,(0,width-count))
            outputs.append(na2d(q,k,part,**kwargs,backend="flex-fna",torch_compile=False)[...,:count])
        return torch.cat(outputs,dim=-1)
    attentions.na2d=cpu_na2d
    reference=args.pixal_source/"pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"
    names={"project_points_to_image_batch","sample_features","ProjGrid"}
    nodes=[n for n in ast.parse(reference.read_text()).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    assert len(nodes)==len(names)
    namespace={"torch":torch,"nn":torch.nn,"F":F,"np":np,"Tuple":Tuple}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(reference),"exec"),namespace)
    args.output_dir.mkdir(parents=True)
    # name,D,attentionHeads,ropeHeads,layers,kernel,tile,guideW,H,outW,H,lowW,H,valueChannels,half
    cases=[
        ("regular",32,4,2,2,3,7,16,16,8,8,4,4,32,False),
        ("uneven",32,4,4,1,3,11,17,13,11,9,5,4,32,False),
        ("resize_guide",32,2,2,2,3,16,65,49,8,6,4,3,32,False),
        ("pool_up",32,4,1,0,3,128,5,4,9,9,3,3,64,False),
        ("same_extent",16,2,1,1,3,1,8,8,5,5,5,5,16,False),
        ("default_encoder",256,4,4,2,9,128,18,18,18,18,9,9,64,False),
        ("f16_storage",32,4,2,2,3,7,16,16,8,8,4,4,32,True),
        ("unequal_dilation",32,4,2,2,3,7,16,12,12,9,3,3,32,False),
        ("regular_one_tile",32,4,2,2,3,128,16,16,8,8,4,4,32,False),
    ]
    reports=[]
    for case,D,heads,rope_heads,layers,kernel,tile,iw,ih,ow,oh,lw,lh,C,half in cases:
        directory=args.output_dir/case; (directory/"weights").mkdir(parents=True)
        torch.manual_seed(63371)
        model=NAF(dim=D,heads_attn=heads,heads_rope=rope_heads,img_layers=layers,kernel_size=kernel).eval()
        with torch.no_grad():
            for name,param in model.named_parameters():
                if "norm" in name and name.endswith("weight"): param.normal_(1.,.05)
                elif param.ndim>=2: param.normal_(0.,.5/math.sqrt(param[0].numel()))
                else: param.normal_(0.,.1)
            if half:
                for param in model.state_dict().values(): param.copy_(param.half().float())
        rgb=torch.rand(1,3,ih,iw); low=torch.randn(1,C,lh,lw)
        expected={}
        def capture(name: str,hwc: bool=False):
            def hook(_module,_inputs,value):
                if hwc: value=value.permute(0,2,3,1)
                expected[name]=value.detach().contiguous().numpy().reshape(-1).copy()
            return hook
        for branch in ("encoder","sem_encoder"):
            for i,layer in enumerate(getattr(model.image_encoder,branch)):
                layer.register_forward_hook(capture(f"{branch}.{i}"))
        def capture_guide(_module,inputs): expected["guide"]=inputs[0].detach().numpy().reshape(-1).copy()
        model.image_encoder.encoder.register_forward_pre_hook(capture_guide)
        def capture_pooled(_module,inputs): expected["pooled"]=inputs[0].detach().numpy().reshape(-1).copy()
        model.image_encoder.rope.register_forward_pre_hook(capture_pooled)
        model.query_encoder.register_forward_hook(capture("query",True))
        model.key_encoder.register_forward_hook(capture("key",True))
        with torch.no_grad():
            high=model(rgb,low,(oh,ow))
        expected["high"]=high.permute(0,2,3,1).contiguous().numpy().reshape(-1)
        for name,value in model.state_dict().items(): np.save(directory/"weights"/(name+".npy"),value.detach().numpy())
        (directory/"weights.txt").write_text("\n".join(model.state_dict())+"\n")
        (directory/"params.txt").write_text(f"{D} {heads} {rope_heads} {layers} {kernel} {tile} {iw} {ih} {ow} {oh}\n")
        np.save(directory/"rgb.npy",rgb[0].numpy()); np.save(directory/"low.npy",low[0].permute(1,2,0).numpy())
        coords=torch.tensor([[3,1,0],[0,0,2],[2,3,1],[3,1,0],[1,1,2],[0,3,0],[2,2,2]])
        np.save(directory/"coordinates.npy",coords.numpy().astype(np.float32))
        for i,cam in enumerate(((.857556,2.,1.),(.1,.2,1.),(1.7,.1,.3))):
            projected_high=namespace["ProjGrid"](4,iw)(high,*[torch.tensor([v]) for v in cam],BHWC=False)
            expected["sparse"+str(i)]=projected_high.reshape(1,4,4,4,-1)[:,coords[:,0],coords[:,1],coords[:,2]].numpy().reshape(-1)
        command=[str(args.binary.resolve()),str(directory.resolve()),args.backend]
        if args.device_index is not None: command += ["--device",str(args.device_index)]
        if half: command += ["--f16-storage"]
        if C==32:
            base=args.checkpoint_fixtures/"shape_f32_f32"
            manifest=json.loads((base/"converted/manifest.json").read_text())
            if manifest["source"]["source_kind"]!="synthetic" or digest(base/"converted/model.gguf")!=manifest["output_sha256"]:
                raise ValueError("use intact synthetic shape checkpoint")
            config=json.loads((base/"config.json").read_text())
            flow=ElasticSLatFlowModel(**config["args"]).eval()
            flow.load_state_dict(load_file(base/"source.safetensors"),strict=False)
            coords=torch.tensor([[3,1,0],[0,0,2],[2,3,1],[3,1,0],[1,1,2],[0,3,0],[2,2,2]])
            global_features=torch.randn(1,5,C)
            camera=[torch.tensor([v]) for v in (.857556,2.,1.)]
            grid=namespace["ProjGrid"](4,iw)
            projected=torch.cat([grid(low,*camera,BHWC=False),grid(high,*camera,BHWC=False)],dim=-1)
            projected=projected.reshape(1,4,4,4,-1)[:,coords[:,0],coords[:,1],coords[:,2]]
            expected["projected"]=projected.numpy().reshape(-1)
            sc=torch.cat([torch.zeros(len(coords),1,dtype=coords.dtype),coords],dim=1).int()
            noise=torch.from_numpy(np.load(base/"input.npy",allow_pickle=False))
            positive={"global":global_features,"proj":SparseTensor(projected[0],sc)}
            negative={"global":torch.zeros_like(global_features),"proj":SparseTensor(torch.zeros_like(projected[0]),sc)}
            samples=FlowEulerGuidanceIntervalSampler(1e-5).sample(flow,SparseTensor(noise,sc),positive,negative,steps=3,
                        guidance_strength=2.5,guidance_rescale=.3,guidance_interval=(0,1),verbose=False)
            for i,value in enumerate(samples.pred_x_t): expected["sample"+str(i)]=value.feats.numpy().reshape(-1)
            np.save(directory/"global.npy",global_features[0].numpy()); np.save(directory/"noise.npy",noise.numpy())
            np.save(directory/"coordinates.npy",coords.numpy().astype(np.float32))
            command += ["--flow-gguf",str((base/"converted/model.gguf").resolve())]
        for name,value in expected.items(): np.save(directory/("expected_"+name+".npy"),value)
        start=time.monotonic(); native=subprocess.run(command,capture_output=True,text=True,timeout=180)
        (directory/"native.log").write_text(native.stdout+native.stderr)
        record={"case":case,"returncode":native.returncode,"native_seconds":time.monotonic()-start,"tensors":{},"passed":False}
        if native.returncode==0:
            record["stats"]=json.loads((directory/"stats.json").read_text())
            for name,value in expected.items():
                actual=np.load(directory/("actual_"+name+".npy"),allow_pickle=False)
                record["tensors"][name]={"max_abs_error":float(np.max(np.abs(actual-value))),
                                         "passed":actual.shape==value.shape and bool(np.allclose(actual,value,atol=5e-5,rtol=5e-5))}
            record["passed"]=all(v["passed"] for v in record["tensors"].values())
        reports.append(record)
        print(json.dumps(record),flush=True)
    tiled_equal=False
    if (args.output_dir/"regular/actual_high.npy").exists() and (args.output_dir/"regular_one_tile/actual_high.npy").exists():
        tiled_equal=bool(np.array_equal(np.load(args.output_dir/"regular/actual_high.npy"),np.load(args.output_dir/"regular_one_tile/actual_high.npy")))
    negatives={}
    for case in ("rgb_range","nan_features","missing_weight","weight_shape","bad_period","bad_extent","bad_heads","cancel_before","cancel_between_tiles","cancel_final"):
        directory=args.output_dir/"negative"/case
        shutil.copytree(args.output_dir/"regular",directory,ignore=shutil.ignore_patterns("actual_*","expected_*","native*","stats.json"))
        flags=[]
        if case=="rgb_range":
            p=directory/"rgb.npy"; v=np.load(p); v.flat[0]=2.; np.save(p,v)
        elif case=="nan_features":
            p=directory/"low.npy"; v=np.load(p); v.flat[0]=float("nan"); np.save(p,v)
        elif case=="missing_weight":
            p=directory/"weights.txt"; p.write_text(p.read_text().replace("image_encoder.encoder.1.norm1.weight\n",""))
        elif case=="weight_shape":
            p=directory/"weights/image_encoder.encoder.0.weight.npy"; np.save(p,np.load(p)[:-1])
        elif case=="bad_period":
            p=directory/"weights/image_encoder.rope.periods.npy"; v=np.load(p); v[0]=0; np.save(p,v)
        elif case in {"bad_extent","bad_heads"}:
            p=directory/"params.txt"; v=p.read_text().split(); v[4 if case=="bad_extent" else 1]="9" if case=="bad_extent" else "3"; p.write_text(" ".join(v)+"\n")
        elif case=="cancel_before": flags=["--cancel-at","1"]
        elif case=="cancel_between_tiles": flags=["--cancel-at","7"]
        else:
            flags=["--cancel-at",str(3+3*math.ceil(64/7))]
        command=[str(args.binary.resolve()),str(directory.resolve()),"cpu",*flags]
        native=subprocess.run(command,capture_output=True,text=True,timeout=30)
        expected_message="cancelled" if case.startswith("cancel") else None
        negatives[case]={"returncode":native.returncode,"stderr":native.stderr.strip(),
                         "passed":native.returncode==1 and not list(directory.glob("actual_*")) and
                         (expected_message is None or expected_message in native.stderr)}
    for case,flags,error in (("projected_cancel_before",["--cancel-at","1"],"cancelled"),
                             ("projected_cancel_tiles",["--cancel-at","8"],"cancelled"),
                             ("projected_cancel_final",["--cancel-at","25"],"cancelled"),
                             ("projected_bad_coord",[],"coordinate")):
        directory=args.output_dir/"negative"/case
        shutil.copytree(args.output_dir/"regular",directory,ignore=shutil.ignore_patterns("actual_*","expected_*","native*","stats.json"))
        if case=="projected_bad_coord":
            v=np.load(directory/"coordinates.npy");v[0,0]=4;np.save(directory/"coordinates.npy",v)
        native=subprocess.run([str(args.binary.resolve()),str(directory.resolve()),"cpu","--projected-only",*flags],capture_output=True,text=True,timeout=30)
        negatives[case]={"returncode":native.returncode,"stderr":native.stderr.strip(),
                         "passed":native.returncode==1 and error in native.stderr and not list(directory.glob("actual_*"))}
    references=["src/model/naf.py","src/layers/attentions.py","src/layers/convolutions.py","src/layers/rope.py"]
    report={"passed":all(r["passed"] for r in reports) and all(r["passed"] for r in negatives.values()) and tiled_equal,
            "naf_revision":NAF_REVISION,"reference_sha256":{p:digest(args.naf_source/p) for p in references},
            "pixal_revision":PIXAL_REVISION,"pixal_projection_sha256":digest(reference),
            "natten_version":importlib.metadata.version("natten"),"natten_flex_sha256":digest(Path(flex.__file__)),
            "attention_reference":"NAF original forward; cutlass-fna -> CPU NATTEN flex-fna, torch_compile=False; V channels chunked/padded to QK head width",
            "attention_calls":backend_calls,"tile_size_bitwise_equal":tiled_equal,"cases":reports,"negative_checks":negatives,
            "binary_sha256":digest(args.binary),"backend":args.backend,"device_index":args.device_index,
            "torch_gpu_initialized":torch.cuda.is_initialized(),"pretrained_weights":"NOT USED",
            "vulkan_acceptance":"NOT TESTED" if args.backend=="cpu" else "synthetic numeric checks only",
            "pipeline_glb_adoption_library":"NOT TESTED"}
    (args.output_dir/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"passed":report["passed"],"cases":len(reports),"tile_size_bitwise_equal":tiled_equal,"negative_checks":negatives}),flush=True)
    return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
