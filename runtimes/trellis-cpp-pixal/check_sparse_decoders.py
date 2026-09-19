#!/usr/bin/env python3
"""Actual Pixal sparse decoders / FlexGEMM Torch reference vs native GGUF.

All parameters are synthetic. This checks raw dual-grid/PBR fields, not a mesh.
"""
from __future__ import annotations
import argparse
import copy
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
from convert_sparse_decoder import convert, decoder_spec, tensor_shapes, PIXAL_REVISION, digest
from sparse_cpu_reference import FLEX_REVISION, install


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pixal-source", "flex-source", "ss-fixtures", "binary", "output-dir"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device-index", type=int)
    a = parser.parse_args()
    if (a.backend == "vulkan") != (a.device_index is not None): parser.error("Vulkan requires an admitted explicit device")
    for root, revision in ((a.pixal_source, PIXAL_REVISION), (a.flex_source, FLEX_REVISION)):
        if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != revision or subprocess.check_output(["git", "-C", str(root), "diff", "HEAD", "--"]):
            parser.error("reference sources must be pinned and tracked files unchanged")
    if a.output_dir.exists(): parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES":"-1", "ROCR_VISIBLE_DEVICES":"-1", "CUDA_VISIBLE_DEVICES":"-1", "HF_HUB_OFFLINE":"1",
                       "SPARSE_CONV_BACKEND":"none", "SPARSE_ATTN_BACKEND":"sdpa", "ATTN_BACKEND":"sdpa"})
    sys.path.insert(0, str(a.pixal_source.resolve()))
    import gguf
    import numpy as np
    import torch
    import torch.nn.functional as F
    from safetensors.torch import save_file, load_file
    from pixal3d.modules.sparse import SparseTensor
    reference = install(a.pixal_source, a.flex_source)
    from pixal3d.models.sc_vaes.sparse_unet_vae import SparseUnetVaeDecoder
    torch.set_num_threads(2)
    a.output_dir.mkdir(parents=True)
    provenance = {"source_repository":"mediaforge/synthetic-sparse-decoder", "source_revision":PIXAL_REVISION, "source_kind":"synthetic"}
    cases = []

    def run(directory: Path, paths: list[Path], extra: list[str] | None = None) -> Any:
        cmd = [str(a.binary.resolve()), str(directory.resolve()), a.backend, *map(str, paths)]
        if a.device_index is not None: cmd += ["--device", str(a.device_index)]
        cmd += extra or []
        started = time.monotonic(); result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        (directory / "native.log").write_text(result.stdout+result.stderr)
        (directory / "command.json").write_text(json.dumps({"argv":cmd, "seconds":time.monotonic()-started, "returncode":result.returncode}, indent=2)+"\n")
        return result

    # Sanity-check the unmodified FlexGEMM Torch path against dense Torch conv3d
    # at active coordinates, including borders and non-sorted sparse rows.
    torch.manual_seed(5321)
    cs = torch.tensor([[0,3,2,1],[0,0,0,0],[0,2,1,1],[0,3,3,3],[0,2,2,1]], dtype=torch.int32)
    feats = torch.randn(len(cs),8); w = torch.randn(12,3,3,3,8); bias = torch.randn(12)
    sparse, _ = reference["conv"](feats, cs, torch.Size([1,8,4,4,4]), w, bias, None, (1,1,1))
    dense = torch.zeros(1,8,4,4,4); dense[cs[:,0],:,cs[:,1],cs[:,2],cs[:,3]] = feats
    result = F.conv3d(dense,w.permute(0,4,1,2,3).contiguous(),bias,padding=1)[cs[:,0],:,cs[:,1],cs[:,2],cs[:,3]]
    reference_check = {"passed":bool(torch.allclose(sparse,result,atol=5e-5,rtol=5e-5)), "max_abs_error":float((sparse-result).abs().max())}

    configurations = [
        ("f32", [32,16,8], [1,1,1], "f32", "f32", False, "learned"),
        ("f16_explicit_f32", [64,32,16,8], [2,1,1,0], "f16", "f16", True, "learned"),
        ("bf16_f16_storage", [32,16], [1,2], "bf16", "f16", False, "learned"),
        ("deployed_depth_reduced_width", [16,8,8,8,8], [4,16,8,4,0], "f32", "f32", False, "two"),
        ("strict_subdivision_threshold", [8,8], [0,0], "f32", "f32", False, "boundary"),
        ("prior_image_shape_latent", [16,8], [1,1], "f32", "f32", False, "learned"),
    ]
    for case, channels, blocks, source_dtype, storage, fp16, mask in configurations:
        directory = a.output_dir / case; directory.mkdir(); torch.manual_seed(7721)
        coords = cs.clone(); latent = torch.randn(len(coords),8); texture = torch.randn(len(coords),8); grid=4
        if case == "prior_image_shape_latent":
            source = a.ss_fixtures / "connected_image"
            coords = torch.from_numpy(np.load(source / "actual_coords.npy", allow_pickle=False).astype(np.int32).reshape(-1,3))
            coords = torch.cat([torch.zeros(len(coords),1,dtype=torch.int32),coords],dim=1)
            latent = torch.from_numpy(np.load(source / "actual_shape.npy", allow_pickle=False).reshape(-1,8).copy())
            texture = torch.randn(len(coords),8)
            (directory / "input-provenance.json").write_text(json.dumps({"kind":"saved native image/SS/shape-flow output; not a rerun of those stages",
                "files":{str(source/n):digest(source/n) for n in ("actual_coords.npy","actual_shape.npy","command.json")}}, indent=2)+"\n")
        if mask == "two": coords=coords[:3]; latent=latent[:3]; texture=texture[:3]
        common = {"model_channels":channels,"latent_channels":8,"num_blocks":blocks,"block_type":["SparseConvNeXtBlock3d"]*len(channels),
                  "up_block_type":["SparseResBlockC2S3d"]*(len(channels)-1),"block_args":[{} for _ in channels],"use_fp16":fp16}
        if case == "bf16_f16_storage": common["block_args"][-1]={"mlp_ratio":2.5,"use_checkpoint":False}
        models={}; paths=[]; rounded={}; expected={}; hooks=[]
        for label in ("shape","texture"):
            target=directory/label; target.mkdir()
            cfg={"name":"FlexiDualGridVaeDecoder" if label=="shape" else "SparseUnetVaeDecoder", "args":common | ({"resolution":grid*2**(len(channels)-1)} if label=="shape" else {"out_channels":6,"pred_subdiv":False})}
            (target/"config.json").write_text(json.dumps(cfg,indent=2)+"\n")
            # FlexiDualGridVaeDecoder inherits this exact raw-field forward path;
            # its sigmoid/softplus and mesh conversion are outside this check.
            model=SparseUnetVaeDecoder(**(common | {"use_fp16":False}),out_channels=7 if label=="shape" else 6,pred_subdiv=label=="shape").eval()
            with torch.no_grad():
                for name,p in model.named_parameters():
                    if name.endswith("weight") and p.ndim==1: p.normal_(1.,.05)
                    elif p.ndim>1: p.normal_(0.,.4/math.sqrt(math.prod(p.shape[1:])))
                    else: p.normal_(0.,.08)
                    if ".to_subdiv." in name and mask in {"two","boundary"}:
                        p.zero_()
                        if name.endswith("bias"):
                            p.copy_(torch.tensor([.2,-.3,-.2,-.1,.3,-.4,-.5,-.6] if mask=="two" else [0.,-0.,.1,-.1,1e-8,-1e-8,0.,-.2]))
            dtype={"f32":torch.float32,"f16":torch.float16,"bf16":torch.bfloat16}[source_dtype]
            state={name:p.detach().to(dtype).contiguous() for name,p in model.named_parameters()}
            save_file(state,target/"source.safetensors",metadata={"source":"synthetic; no pretrained weights"})
            convert(target/"source.safetensors",target/"config.json",target/"converted",storage=storage,**provenance)
            path=target/"converted/model.gguf"; paths.append(path)
            rounded[label]={name:(v.float().half().float() if storage=="f16" and v.ndim>1 else v.float()) for name,v in state.items()}
            model.load_state_dict(rounded[label],strict=True); models[label]=model
            def capture(name: str) -> Any:
                def hook(_module: Any, _inputs: Any, value: Any) -> None:
                    value=value[0] if isinstance(value,tuple) else value
                    value=value.feats if isinstance(value,SparseTensor) else value
                    expected[name]=value.detach().numpy().copy()
                return hook
            hooks.append(model.from_latent.register_forward_hook(capture(label+".from_latent")))
            hooks.append(model.output_layer.register_forward_hook(capture(label+".output_layer")))
            def before_output(_module: Any, inputs: Any, name: str=label+".final_norm") -> None:
                expected[name]=inputs[0].feats.detach().numpy().copy()
            hooks.append(model.output_layer.register_forward_pre_hook(before_output))
            for i,stage in enumerate(model.blocks):
                for j,block in enumerate(stage):
                    name=f"{label}.blocks.{i}.{j}"; hooks.append(block.register_forward_hook(capture(name)))
                    if hasattr(block,"updown"):
                        # updown is invoked first on conv1 then on the raw skip.
                        def expanded(name: str) -> Any:
                            calls=0
                            def hook(_module: Any,_inputs: Any,value: Any) -> None:
                                nonlocal calls
                                if calls%2==0: expected[name]=value.feats.detach().numpy().copy()
                                calls+=1
                            return hook
                        hooks.append(block.updown.register_forward_hook(expanded(name+".expanded")))
        with torch.no_grad():
            s,subs=models["shape"](SparseTensor(latent,coords),return_subs=True)
            t=models["texture"](SparseTensor(texture,coords),guide_subs=subs)
        for hook in hooks: hook.remove()
        expected["shape.coords"]=s.coords[:,1:].numpy(); expected["texture.coords"]=t.coords[:,1:].numpy()
        expected["output_grid"]=np.array([grid*2**(len(channels)-1)],np.float32)
        expected["shape.progress"]=np.array([[i,len(channels)] for i in range(len(channels)+1)],np.float32)
        for i,sub in enumerate(subs):
            for label in ("shape","texture"): expected[f"{label}.blocks.{i}.{blocks[i]}.subdiv"]=sub.feats.numpy()
            expected[f"shape.guide{i}.coords"]=sub.coords[:,1:].numpy()
        with torch.no_grad():
            for i in range(len(channels)): expected[f"upsample{i}"]=models["shape"].upsample(SparseTensor(latent,coords),i)[:,1:].numpy()
        for name,value in {"shape":latent.numpy(),"texture":texture.numpy(),"coords":coords[:,1:].numpy(),"settings":np.array([grid],np.float32)}.items(): np.save(directory/(name+".npy"),np.ascontiguousarray(value,dtype=np.float32))
        result=run(directory,paths)
        record={"case":case,"returncode":result.returncode,"tensors":{},"weight_count":0,"weights_exact":True,"passed":False}
        for name,value in expected.items():
            np.save(directory/("expected_"+name+".npy"),value)
            if result.returncode: continue
            actual=np.load(directory/("actual_"+name+".npy"),allow_pickle=False); ref=np.asarray(value).reshape(-1)
            exact="coords" in name or name.startswith("upsample") or name in {"output_grid","shape.progress"}
            passed=actual.shape==ref.shape and bool(np.array_equal(actual,ref) if exact else np.allclose(actual,ref,atol=5e-5,rtol=5e-5))
            record["tensors"][name]={"passed":passed,"exact":exact,"max_abs_error":float(np.max(np.abs(actual-ref))) if actual.shape==ref.shape else None}
        if result.returncode==0:
            for label,path in zip(("shape","texture"),paths):
                for tensor in gguf.GGUFReader(path).tensors:
                    ref=rounded[label][tensor.name].numpy().reshape(-1)
                    actual=np.load(directory/(f"actual_{label}.weight.{tensor.name}.npy"),allow_pickle=False)
                    record["weights_exact"] &= bool(np.array_equal(tensor.data.astype(np.float32).reshape(-1),ref) and np.array_equal(actual,ref))
                    record["weight_count"]+=1
                repeated=np.load(directory/(f"actual_{label}.repeated.npy"),allow_pickle=False)
                original=np.load(directory/(f"actual_{label}.output_layer.npy"),allow_pickle=False)
                record["tensors"][label+".chunk_invariance"]={"passed":bool(np.allclose(repeated,original,atol=5e-5,rtol=5e-5)),"exact":bool(np.array_equal(repeated,original)),"max_abs_error":float(np.max(np.abs(repeated-original)))}
            record["passed"]=record["weights_exact"] and all(v["passed"] for v in record["tensors"].values())
        cases.append(record)

    baseline=a.output_dir/"f32"
    converter_checks={}; native_checks={}
    cfg=json.loads((baseline/"shape/config.json").read_text()); state=load_file(baseline/"shape/source.safetensors")
    for case in ("unknown_arg","block_type","stage_count","skip_channels","nonfinite","missing_tensor","unexpected_tensor","tensor_shape","overflow","mlp_arg","bad_bool","texture_subdiv"):
        directory=a.output_dir/"negative_converter"/case; directory.mkdir(parents=True)
        c=copy.deepcopy(cfg); weights={k:v.clone() for k,v in state.items()}; storage="f32"
        if case=="unknown_arg": c["args"]["unknown"]=True
        if case=="block_type": c["args"]["block_type"][0]="SparseResBlock3d"
        if case=="stage_count": c["args"]["num_blocks"].pop()
        if case=="skip_channels": c["args"]["model_channels"][0]=33
        if case=="mlp_arg": c["args"]["block_args"][0]["mlp_ratio"]=4.
        if case=="bad_bool": c["args"]["use_fp16"]=1
        if case=="texture_subdiv": c=json.loads((baseline/"texture/config.json").read_text()); c["args"]["pred_subdiv"]=True
        first=next(iter(weights))
        if case=="missing_tensor": weights.pop(first)
        if case=="unexpected_tensor": weights["unknown"]=torch.ones(1)
        if case=="tensor_shape": weights[first]=weights[first].reshape(-1)[:1]
        if case=="nonfinite": weights[first].flatten()[0]=float("nan")
        if case=="overflow": weights["from_latent.weight"][0,0]=1e8; storage="f16"
        cp=directory/"config.json"; cp.write_text(json.dumps(c)); save_file(weights,directory/"source.safetensors")
        try:
            convert(directory/"source.safetensors",cp,directory/"converted",storage=storage,**provenance)
            converter_checks[case]={"passed":False,"error":"unexpected success"}
        except ValueError as error:
            converter_checks[case]={"passed":not (directory/"converted").exists(),"error":str(error)}
    # Backend initialization must not precede malformed metadata/table rejection.
    for case in ("schema","kind","channels","tensor_name","tensor_shape","truncated","nan_weight"):
        directory=a.output_dir/"negative_native"/case; directory.mkdir(parents=True); path=directory/"bad.gguf"
        reader=gguf.GGUFReader(baseline/"shape/converted/model.gguf"); writer=gguf.GGUFWriter(path,None)
        for name,field in reader.fields.items():
            if name.startswith("GGUF."): continue
            value=field.contents()
            if case=="schema" and name=="pixal.schema_version": value=2
            if case=="kind" and name=="pixal.sparse_decoder.kind": value="other"
            if case=="channels" and name=="pixal.sparse_decoder.channels.0": value=33
            writer.add_key_value(name,value,field.types[0])
        for i,tensor in enumerate(reader.tensors):
            values=tensor.data.copy()
            if i==0 and case=="nan_weight": values.flat[0]=float("nan")
            if i==0 and case=="tensor_shape": values=values.reshape(-1)[:1]
            writer.add_tensor("unexpected" if i==0 and case=="tensor_name" else tensor.name,values)
        writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file(); writer.close()
        if case=="truncated":
            with path.open("r+b") as stream: stream.truncate(path.stat().st_size-128)
        for name in ("coords","settings","shape","texture"): shutil.copyfile(baseline/(name+".npy"),directory/(name+".npy"))
        result=run(directory,[path,baseline/"texture/converted/model.gguf"])
        native_checks[case]={"passed":result.returncode==1 and not list(directory.glob("actual_*")) and (case=="nan_weight" or "backend_initialized=" not in result.stdout),"error":result.stderr.strip()}
    for case in ("nan_latent","extent","channels","coordinate","duplicate","grid","chunk","budget","model_kind","guide_missing","guide_order","guide_grid","guide_extent","guide_nan","guide_empty","upsample_count","cancel_before","cancel_between","cancel_final","reference_precision"):
        directory=a.output_dir/"negative_native"/("fault_"+case); directory.mkdir(parents=True)
        base=a.output_dir/"f16_explicit_f32" if case=="reference_precision" else baseline
        for name in ("coords","settings","shape","texture"): shutil.copyfile(base/(name+".npy"),directory/(name+".npy"))
        result=run(directory,[base/"shape/converted/model.gguf",base/"texture/converted/model.gguf"],["--fault",case])
        messages={"nan_latent":"non-finite sparse", "extent":"invalid sparse decoder input extent", "channels":"invalid sparse decoder input extent", "coordinate":"coordinate outside grid", "duplicate":"duplicate sparse", "grid":"latent/guide/grid mismatch", "chunk":"invalid sparse decoder options", "budget":"exceeds explicit voxel budget", "model_kind":"latent/guide/grid mismatch", "guide_missing":"latent/guide/grid mismatch", "guide_order":"guide coordinate/order mismatch", "guide_grid":"guide coordinate/order mismatch", "guide_extent":"invalid subdivision logits extent", "guide_nan":"non-finite sparse", "guide_empty":"no active voxels", "upsample_count":"invalid shape upsample count", "cancel_before":"sparse decoder cancelled", "cancel_between":"sparse decoder cancelled", "cancel_final":"sparse decoder cancelled", "reference_precision":"missing explicit F32 evaluation"}
        native_checks["fault_"+case]={"passed":result.returncode==1 and messages[case] in result.stderr and not list(directory.glob("actual_*")),"error":result.stderr.strip()}
    sources=reference["sources"]+[a.pixal_source/"pixal3d/models/sc_vaes/sparse_unet_vae.py",a.pixal_source/"pixal3d/modules/sparse/spatial/spatial2channel.py"]
    report={"passed":reference_check["passed"] and all(r["passed"] for r in cases+list(converter_checks.values())+list(native_checks.values())),
            "cases":cases,"converter_checks":converter_checks,"native_checks":native_checks,"reference_dense_conv":reference_check,
            "reference_revision":PIXAL_REVISION,"flex_revision":FLEX_REVISION,"source_hashes":{str(p):digest(p) for p in sources},"binary_sha256":digest(a.binary),
            "backend":a.backend,"device_index":a.device_index,"torch_gpu_initialized":torch.cuda.is_initialized(),"trained_weights":"NOT USED",
            "reference":"actual Pixal decoder class and AST-extracted FlexGEMM Torch explicit GEMM; no GPU FlexGEMM kernels",
            "mixed_precision_mesh_glb_library":"NOT TESTED", "packages":{name:importlib.metadata.version(name) for name in ("torch","numpy","gguf","safetensors")}}
    (a.output_dir/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"passed":report["passed"],"cases":len(cases),"converter_checks":len(converter_checks),"native_checks":len(native_checks)}))
    return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
