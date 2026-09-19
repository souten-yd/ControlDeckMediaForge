#!/usr/bin/env python3
"""Compare native pixels -> DINO -> projection -> sampled latent using synthetic weights."""
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
from typing import List, Optional, Tuple, Union

from convert_flow import PIXAL_REVISION, digest
from prepare_image import prepare_rgb


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixal-source",required=True,type=Path)
    parser.add_argument("--checkpoint-fixtures",required=True,type=Path)
    parser.add_argument("--binary",required=True,type=Path)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--backend",choices=("cpu","vulkan"),default="cpu")
    parser.add_argument("--device-index",type=int)
    args=parser.parse_args()
    if (args.backend=="vulkan") != (args.device_index is not None): parser.error("Vulkan requires an admitted explicit device index")
    source=args.pixal_source.resolve(strict=True)
    if subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()!=PIXAL_REVISION or \
            subprocess.check_output(["git","-C",str(source),"diff","HEAD","--"]):
        parser.error("reference source must be pinned without tracked changes")
    if args.output_dir.exists(): parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES":"-1","ROCR_VISIBLE_DEVICES":"-1","CUDA_VISIBLE_DEVICES":"-1",
                       "HF_HUB_OFFLINE":"1","ATTN_BACKEND":"sdpa","SPARSE_ATTN_BACKEND":"sdpa","SPARSE_CONV_BACKEND":"none"})
    sys.path.insert(0,str(source))
    import numpy as np
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from torchvision import transforms
    from transformers import DINOv3ViTConfig, DINOv3ViTModel
    from transformers.models.dinov3_vit import modeling_dinov3_vit
    from safetensors.torch import load_file
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler
    if importlib.metadata.version("transformers")!="4.57.3": raise ValueError("use the pinned worker dependency lock")
    torch.set_num_threads(2)
    reference=source/"pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"
    wanted={"project_points_to_image_batch","sample_features","ProjGrid","DinoV3ProjFeatureExtractor"}
    nodes=[n for n in ast.parse(reference.read_text()).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in wanted]
    assert len(nodes)==len(wanted)
    namespace={"torch":torch,"nn":torch.nn,"F":F,"np":np,"Image":Image,"transforms":transforms,
               "Tuple":Tuple,"Optional":Optional,"Union":Union,"List":List,"DINOv3ViTModel":DINOv3ViTModel}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(reference),"exec"),namespace)
    args.output_dir.mkdir(parents=True)
    reports=[]
    # All cases run real DINO layers. HR is a supplied synthetic feature map,
    # testing projection/concatenation only; it is NOT a NAF inference result.
    cases=[("ss_pixels",32,4,8,4,4,True,False), ("resized_rgb",32,4,12,4,4,True,False),
           ("no_attention_bias",32,4,8,4,2,False,False), ("larger_heads",64,4,16,4,4,True,False),
           ("single_patch",32,4,4,4,4,True,False), ("supplied_hr_features",32,4,12,4,4,True,True)]
    for case,dim,heads,size,patch,registers,bias,with_high in cases:
        directory=args.output_dir/case
        (directory/"weights").mkdir(parents=True)
        torch.manual_seed(9257)
        config=DINOv3ViTConfig(hidden_size=dim,intermediate_size=dim*2,num_hidden_layers=2,num_attention_heads=heads,
                              image_size=size,patch_size=patch,num_register_tokens=registers,query_bias=bias,
                              key_bias=False,value_bias=bias,proj_bias=True,mlp_bias=True,use_gated_mlp=False)
        config._attn_implementation="sdpa"
        model=DINOv3ViTModel(config).eval()
        with torch.no_grad():
            for name,parameter in model.named_parameters():
                if name.endswith("lambda1") or ("norm" in name and name.endswith("weight")):
                    parameter.normal_(1.,.04)
                elif parameter.ndim>=2:
                    parameter.normal_(0.,.5/math.sqrt(parameter[0].numel()))
                else: parameter.normal_(0.,.1)
        # Instantiate the actual extractor without its from_pretrained initializer.
        extractor=namespace["DinoV3ProjFeatureExtractor"].__new__(namespace["DinoV3ProjFeatureExtractor"])
        torch.nn.Module.__init__(extractor)
        extractor.model=model; extractor.image_size=size; extractor.patch_number=size//patch
        extractor.transform=transforms.Normalize([.485,.456,.406],[.229,.224,.225])
        extractor.use_naf_upsample=with_high
        grid=4 if with_high else 2
        extractor.proj_grid=namespace["ProjGrid"](grid,size)
        if with_high:
            high=torch.randn(1,dim,5,7)
            class SuppliedFeatures(torch.nn.Module):
                def forward(self,guide,low,target): return high
            extractor.naf_model=SuppliedFeatures()
            extractor.naf_target_size=(5,7)
            np.save(directory/"high.npy",high[0].permute(1,2,0).numpy())
        rng=np.random.default_rng(271)
        rgb=Image.fromarray(rng.integers(0,256,size=(11 if case=="resized_rgb" else size,17 if case=="resized_rgb" else size,3),dtype=np.uint8))
        rgb.save(directory/"input.png")
        prepared=prepare_rgb(rgb,size)
        raw_reference=np.array(rgb.resize((size,size),Image.Resampling.LANCZOS).convert("RGB")).astype(np.float32)/255
        resize_equal=bool(np.array_equal(prepared,raw_reference.transpose(2,0,1)))
        image=torch.from_numpy(prepared).unsqueeze(0)
        expected={"normalized":extractor.transform(image).numpy().reshape(-1)}
        def capture(name: str):
            def hook(_module,_inputs,value):
                if isinstance(value,tuple): value=value[0]
                expected[name]=value.detach().numpy().reshape(-1).copy()
            return hook
        model.embeddings.register_forward_hook(capture("embedding"))
        for i,block in enumerate(model.layer):
            block.attention.register_forward_hook(capture(f"blocks.{i}.attention"))
            block.mlp.register_forward_hook(capture(f"blocks.{i}.mlp"))
            block.register_forward_hook(capture(f"blocks.{i}.output"))
        camera=[torch.tensor([v]) for v in (.857556,2.,1.)]
        with torch.no_grad():
            global_features,projected=extractor(image,*camera)
            tokens=extractor.extract_features(extractor.transform(image))
        coords=torch.cartesian_prod(torch.arange(grid),torch.arange(grid),torch.arange(grid))
        if with_high:
            coords=torch.tensor([[3,1,0],[0,0,2],[2,3,1],[3,1,0],[1,1,2],[0,3,0],[2,2,2]])
            projected=projected.reshape(1,grid,grid,grid,-1)[:,coords[:,0],coords[:,1],coords[:,2]]
        expected.update({"tokens":tokens.numpy().reshape(-1),"global":global_features.numpy().reshape(-1),
                         "patches":tokens[:,1+registers:].numpy().reshape(-1),"projected":projected.numpy().reshape(-1),
                         "negative_global":np.zeros(global_features.numel(),np.float32),"negative_projected":np.zeros(projected.numel(),np.float32)})
        state={"patch_embed.proj.weight":model.embeddings.patch_embeddings.weight,"patch_embed.proj.bias":model.embeddings.patch_embeddings.bias,
               "cls_token":model.embeddings.cls_token,"reg_token":model.embeddings.register_tokens}
        for i,block in enumerate(model.layer):
            prefix=f"blocks.{i}"
            for norm in ("norm1","norm2"):
                for param in ("weight","bias"): state[f"{prefix}.{norm}.{param}"]=getattr(getattr(block,norm),param)
            attn=block.attention
            state[prefix+".attn.qkv.weight"]=torch.cat([attn.q_proj.weight,attn.k_proj.weight,attn.v_proj.weight])
            if bias: state[prefix+".attn.qkv.bias"]=torch.cat([attn.q_proj.bias,torch.zeros(dim),attn.v_proj.bias])
            for target,layer in (("attn.proj",attn.o_proj),("mlp.fc1",block.mlp.up_proj),("mlp.fc2",block.mlp.down_proj)):
                state[f"{prefix}.{target}.weight"]=layer.weight
                state[f"{prefix}.{target}.bias"]=layer.bias
            state[prefix+".gamma_1"]=block.layer_scale1.lambda1
            state[prefix+".gamma_2"]=block.layer_scale2.lambda1
        for name,value in state.items(): np.save(directory/"weights"/(name+".npy"),value.detach().numpy())
        (directory/"weights.txt").write_text("\n".join(state)+"\n")
        (directory/"params.txt").write_text(f"{dim} {heads} 2 {patch} {registers} {dim*2} {size}\n")
        np.save(directory/"rgb.npy",prepared)
        np.save(directory/"coordinates.npy",coords.numpy().astype(np.float32))
        np.save(directory/"camera.npy",np.array([.857556,2.,1.,grid],np.float32))
        command=[str(args.binary.resolve()),str(directory.resolve()),args.backend]
        if args.device_index is not None: command += ["--device",str(args.device_index)]
        if with_high: command += ["--with-high"]
        if dim==32:
            base=args.checkpoint_fixtures.resolve()/("shape_f32_f32" if with_high else "ss_f32_f32")
            manifest=json.loads((base/"converted/manifest.json").read_text())
            if manifest["source"]["source_kind"]!="synthetic" or digest(base/"converted/model.gguf")!=manifest["output_sha256"]:
                raise ValueError("use intact synthetic flow checkpoints")
            flow_config=json.loads((base/"config.json").read_text())
            flow=(ElasticSLatFlowModel if with_high else SparseStructureFlowModel)(**flow_config["args"]).eval()
            flow.load_state_dict(load_file(base/"source.safetensors"),strict=False)
            noise=torch.from_numpy(np.load(base/"input.npy",allow_pickle=False))
            np.save(directory/"noise.npy",noise.numpy())
            if with_high:
                sc=torch.cat([torch.zeros(len(coords),1,dtype=coords.dtype),coords],dim=1).int()
                xt=SparseTensor(noise,sc)
                pos={"global":global_features,"proj":SparseTensor(projected[0],sc)}
                neg={"global":torch.zeros_like(global_features),"proj":SparseTensor(torch.zeros_like(projected[0]),sc)}
            else:
                xt=noise.T.reshape(1,8,2,2,2)
                pos={"global":global_features,"proj":projected}
                neg={"global":torch.zeros_like(global_features),"proj":torch.zeros_like(projected)}
            samples=FlowEulerGuidanceIntervalSampler(1e-5).sample(flow,xt,pos,neg,steps=3,guidance_strength=2.5,
                        guidance_rescale=.3,guidance_interval=(0,1),verbose=False)
            for i,value in enumerate(samples.pred_x_t): expected["sample"+str(i)]=(value.feats if with_high else value[0].reshape(8,-1).T.contiguous()).numpy().reshape(-1)
            command += ["--flow-gguf",str(base/"converted/model.gguf")]
        for name,value in expected.items(): np.save(directory/("expected_"+name+".npy"),value)
        native=subprocess.run(command,capture_output=True,text=True,timeout=90)
        (directory/"native.log").write_text(native.stdout+native.stderr)
        record={"case":case,"returncode":native.returncode,"resize_equal":resize_equal,"tensors":{},"passed":False}
        if native.returncode==0:
            for name,reference_value in expected.items():
                actual=np.load(directory/("actual_"+name+".npy"),allow_pickle=False)
                record["tensors"][name]={"max_abs_error":float(np.max(np.abs(actual-reference_value))),
                                         "passed":actual.shape==reference_value.shape and bool(np.allclose(actual,reference_value,atol=5e-5,rtol=5e-5))}
            record["passed"]=resize_equal and all(v["passed"] for v in record["tensors"].values())
        reports.append(record)
    negatives={}
    for case in ("rgb_range","nan_rgb","missing_weight","wrong_weight_shape","bad_camera","bad_high_channels"):
        directory=args.output_dir/"negative"/case
        base=args.output_dir/("supplied_hr_features" if case=="bad_high_channels" else "ss_pixels")
        shutil.copytree(base,directory,ignore=shutil.ignore_patterns("actual_*","expected_*","native*"))
        if case in {"rgb_range","nan_rgb"}:
            values=np.load(directory/"rgb.npy"); values.flat[0]=2. if case=="rgb_range" else float("nan")
            np.save(directory/"rgb.npy",values)
        elif case=="missing_weight":
            p=directory/"weights.txt"; p.write_text(p.read_text().replace("blocks.0.norm1.weight\n",""))
        elif case=="wrong_weight_shape":
            p=directory/"weights/blocks.0.norm1.weight.npy"; np.save(p,np.load(p)[:-1])
        elif case=="bad_camera":
            p=directory/"camera.npy"; values=np.load(p); values[2]=0; np.save(p,values)
        else:
            p=directory/"high.npy"; np.save(p,np.load(p)[:,:,:-1])
        command=[str(args.binary.resolve()),str(directory.resolve()),"cpu"]+(["--with-high"] if case=="bad_high_channels" else [])
        native=subprocess.run(command,capture_output=True,text=True,timeout=20)
        negatives[case]={"returncode":native.returncode,"stderr":native.stderr.strip(),
                         "passed":native.returncode==1 and not list(directory.glob("actual_*"))}
    report={"passed":all(r["passed"] for r in reports) and all(r["passed"] for r in negatives.values()),
            "reference_revision":PIXAL_REVISION,"reference_sha256":digest(reference),
            "transformers_version":importlib.metadata.version("transformers"),"transformers_model_sha256":digest(Path(modeling_dinov3_vit.__file__)),
            "binary_sha256":digest(args.binary),"cases":reports,"negative_checks":negatives,
            "backend":args.backend,"device_index":args.device_index,"torch_gpu_initialized":torch.cuda.is_initialized(),
            "pretrained_weights":"NOT USED","naf_inference":"NOT TESTED; supplied synthetic HR features only",
            "background_removal_camera_and_glb":"NOT TESTED"}
    (args.output_dir/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"passed":report["passed"],"cases":len(reports),"negative_checks":len(negatives)}))
    return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
