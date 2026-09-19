#!/usr/bin/env python3
"""Check native dual-grid geometry against pinned Pixal/o_voxel on CPU.

GPU hashmap calls alone are adapted; no GPU execution or trained weights.
"""
from __future__ import annotations
import argparse
import ast
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any
import typing
from convert_flow import PIXAL_REVISION, digest
from sparse_cpu_reference import FLEX_REVISION, install
from convert_sparse_decoder import convert

TRELLIS2_REVISION="75fbf0183001ed9876c8dbb35de6b68552ee08bd"


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("pixal-source","trellis2-source","flex-source","sparse-fixtures","binary","output-dir"):
        parser.add_argument("--"+name,type=Path,required=True)
    a=parser.parse_args()
    for source,pin in ((a.pixal_source,PIXAL_REVISION),(a.trellis2_source,TRELLIS2_REVISION),(a.flex_source,FLEX_REVISION)):
        if subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()!=pin or subprocess.check_output(["git","-C",str(source),"diff","HEAD","--"]): parser.error("reference sources must be pinned with unchanged tracked files")
    if a.output_dir.exists(): parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES":"-1","ROCR_VISIBLE_DEVICES":"-1","CUDA_VISIBLE_DEVICES":"-1","HF_HUB_OFFLINE":"1","SPARSE_CONV_BACKEND":"none","SPARSE_ATTN_BACKEND":"sdpa","ATTN_BACKEND":"sdpa"})
    sys.path.insert(0,str(a.pixal_source.resolve()))
    import gguf
    import numpy as np
    import torch
    import torch.nn.functional as F
    from safetensors.torch import save_file
    from pixal3d.modules.sparse import SparseTensor
    install(a.pixal_source,a.flex_source)
    from pixal3d.models.sc_vaes.sparse_unet_vae import SparseUnetVaeDecoder
    torch.set_num_threads(2)
    a.output_dir.mkdir(parents=True)
    # The original hash lookup kernel explicitly rejects out-of-grid queries
    # before flattening; preserve that rule and its uint32 missing-row sentinel.
    class CpuHash:
        table: dict[int,int]
        def hashmap_insert_3d_idx_as_val_cuda(self,keys: Any,_values: Any,coords: Any,w: int,h: int,d: int) -> None:
            if coords.device.type!="cpu" or w*h*d>=2**32: raise ValueError("CPU reference covers grids below the uint32 volume limit")
            if keys.dtype!=torch.uint32: raise ValueError("unexpected reference hashmap width")
            self.table={((int(b)*w+int(x))*h+int(y))*d+int(z):i for i,(b,x,y,z) in enumerate(coords.tolist())}
        def hashmap_lookup_3d_cuda(self,_keys: Any,_values: Any,coords: Any,w: int,h: int,d: int) -> Any:
            values=[self.table.get(((int(b)*w+int(x))*h+int(y))*d+int(z),0xffffffff) if 0<=x<w and 0<=y<h and 0<=z<d else 0xffffffff for b,x,y,z in coords.tolist()]
            return torch.tensor(values,dtype=torch.uint32)
    geometry_source=a.trellis2_source/"o-voxel/o_voxel/convert/flexible_dual_grid.py"
    namespace={**vars(typing),"torch":torch,"np":np,"nn":torch.nn,"F":F,"_C":CpuHash()}
    names={"_init_hashmap","flexible_dual_grid_to_mesh"}
    nodes=[n for n in ast.parse(geometry_source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(nodes)==len(names)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(geometry_source),"exec"),namespace)
    geometry=namespace["flexible_dual_grid_to_mesh"]
    # Use the real Mesh constructor without importing cumesh. Its GPU-only
    # fill_holes/simplify methods are deliberately not called in this slice.
    mesh_source=a.pixal_source/"pixal3d/representations/mesh/base.py"
    nodes=[n for n in ast.parse(mesh_source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="Mesh"]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(mesh_source),"exec"),namespace)
    fdg_source=a.pixal_source/"pixal3d/models/sc_vaes/fdg_vae.py"
    namespace.update({"SparseUnetVaeDecoder":SparseUnetVaeDecoder,"sp":SimpleNamespace(SparseTensor=SparseTensor)})
    nodes=[n for n in ast.parse(fdg_source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="FlexiDualGridVaeDecoder"]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(fdg_source),"exec"),namespace)
    pipeline_source=a.pixal_source/"pixal3d/pipelines/pixal3d_image_to_3d.py"
    cls=next(n for n in ast.parse(pipeline_source.read_text()).body if isinstance(n,ast.ClassDef))
    namespace.update({"SparseTensor":SparseTensor})
    nodes=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="decode_tex_slat"]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(pipeline_source),"exec"),namespace)
    records=[]

    def run(directory: Path,extra: list[str] | None=None) -> Any:
        cmd=[str(a.binary.resolve()),str(directory.resolve()),*(extra or [])]
        started=time.monotonic(); r=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (directory/"native.log").write_text(r.stdout+r.stderr)
        (directory/"command.json").write_text(json.dumps({"argv":cmd,"seconds":time.monotonic()-started,"returncode":r.returncode},indent=2)+"\n")
        return r

    def save(directory: Path,coords: Any,shape: Any,texture: Any,grid: int,margin: float,require: bool=True) -> None:
        for name,value in {"coords":coords,"shape":shape,"texture":texture,"settings":[grid,margin,int(require)]}.items(): np.save(directory/(name+".npy"),np.ascontiguousarray(value,dtype=np.float32))

    def compare(directory: Path,expected: dict[str,Any],result: Any,legacy: bool=False) -> dict[str,Any]:
        record={"case":directory.name,"returncode":result.returncode,"tensors":{},"passed":False}
        for name,value in expected.items():
            ref=np.asarray(value).reshape(-1); np.save(directory/("expected_"+name+".npy"),value)
            if result.returncode: continue
            actual=np.load(directory/("actual_"+name+".npy"),allow_pickle=False)
            exact=name in {"faces","coords","grid","progress","pbr"}
            same=actual.shape==ref.shape
            record["tensors"][name]={"passed":same and bool(np.array_equal(actual,ref) if exact else np.allclose(actual,ref,atol=2e-6,rtol=2e-6)),"exact":exact,"max_abs_error":float(np.max(np.abs(actual-ref))) if same and len(ref) else 0. if same else None}
        if result.returncode==0 and legacy:
            for name in ("vertices","faces"):
                old=np.load(directory/("actual_legacy."+name+".npy"),allow_pickle=False)
                actual=np.load(directory/("actual_"+name+".npy"),allow_pickle=False)
                record["tensors"]["legacy."+name]={"passed":old.shape==actual.shape and bool(np.array_equal(old,actual) if name=="faces" else np.allclose(old,actual,atol=2e-6,rtol=2e-6)),"max_abs_error":float(np.max(np.abs(old-actual))) if len(actual) and old.shape==actual.shape else 0.}
        record["passed"]=result.returncode==0 and all(r["passed"] for r in record["tensors"].values())
        return record

    torch.manual_seed(9991)
    for name in ("dense_random","reordered","missing_neighbor","boundary_no_wrap","tie_split13","split02","margin_zero","margin_two","strict_intersection","extreme_logits","large_grid1536","empty_diagnostic"):
        directory=a.output_dir/name;directory.mkdir(); grid=4; margin=.5
        coords=torch.cartesian_prod(torch.arange(3),torch.arange(3),torch.arange(3)).int()
        shape=torch.randn(len(coords),7); shape[:,3:6]=1
        if name=="reordered": coords=coords[torch.randperm(len(coords))]
        if name=="missing_neighbor": coords=coords[1:];shape=shape[1:]
        if name=="boundary_no_wrap": coords=torch.cartesian_prod(torch.arange(4),torch.arange(4),torch.arange(4)).int();shape=torch.randn(len(coords),7);shape[:,3:6]=1
        if name=="tie_split13": shape[:,6]=0
        if name=="split02":
            coords=torch.tensor([[1,0,0],[1,0,1],[1,1,1],[1,1,0]],dtype=torch.int32); shape=torch.zeros(4,7);shape[0,3]=1;shape[:,6]=torch.tensor([2.,0.,2.,0.])
        if name=="margin_zero": margin=0.
        if name=="margin_two": margin=2.
        if name=="strict_intersection": shape[:,3:6]=torch.tensor([0.,-0.,1e-8]);shape[0,3]=-1e-8
        if name=="extreme_logits":
            shape[:,:3]=torch.tensor([-1000.,0.,1000.]);shape[:,6]=torch.tensor([-1000.,-100.,-20.,0.,20.,20.0001,1000.,1e30,3e38]*3)
        if name=="large_grid1536": grid=1536; coords=coords+1533
        if name=="empty_diagnostic": shape[:,3:6]=-1
        texture=torch.randn(len(coords),6)*3
        with torch.no_grad():
            verts,faces=geometry(coords,(1+2*margin)*torch.sigmoid(shape[:,:3])-margin,shape[:,3:6]>0,F.softplus(shape[:,6:7]),[[-.5]*3,[.5]*3],grid_size=grid,train=False)
        save(directory,coords.numpy(),shape.numpy(),texture.numpy(),grid,margin,name!="empty_diagnostic")
        expected={"vertices":verts.numpy(),"faces":faces.numpy(),"coords":coords.numpy(),"pbr":(texture*.5+.5).numpy(),"grid":[grid],"progress":[[0,2],[1,2],[2,2]]}
        records.append(compare(directory,expected,run(directory),margin==.5))

    # Execute the actual full FDG decoder class (including its geometry head),
    # not just saved raw fields. Reuse rounded synthetic learned parameters.
    for case in ("f32","f16_explicit_f32","deployed_depth_reduced_width","full_depth_planar","prior_image_shape_latent"):
        source=a.sparse_fixtures/("deployed_depth_reduced_width" if case=="full_depth_planar" else case); directory=a.output_dir/("connected_"+case);directory.mkdir()
        config={label:json.loads((source/label/"config.json").read_text()) for label in ("shape","texture")}
        config["shape"]["args"]["use_fp16"]=False; config["texture"]["args"]["use_fp16"]=False
        models={"shape":namespace["FlexiDualGridVaeDecoder"](**config["shape"]["args"]).eval(),"texture":SparseUnetVaeDecoder(**config["texture"]["args"]).eval()}
        for label,model in models.items():
            state={}
            for tensor in gguf.GGUFReader(source/label/"converted/model.gguf").tensors:
                state[tensor.name]=torch.from_numpy(tensor.data.astype(np.float32).copy()).reshape(model.state_dict()[tensor.name].shape)
            model.load_state_dict(state,strict=True)
        paths={label:source/label/"converted/model.gguf" for label in models}
        if case=="full_depth_planar":
            # The earlier two-child synthetic topology is a line and correctly
            # has no quads. This separate planar fixture exercises full-depth
            # successful connectivity; it is not an accepted generated asset.
            with torch.no_grad():
                for name,parameter in models["shape"].named_parameters():
                    if ".to_subdiv." in name:
                        parameter.zero_()
                        if name.endswith("bias"): parameter.copy_(torch.tensor([1.,1.,1.,1.,-1.,-1.,-1.,-1.]))
                models["shape"].output_layer.weight[5].zero_()
                models["shape"].output_layer.bias[5]=1.
            for label,model in models.items():
                target=directory/label;target.mkdir()
                cp=target/"config.json";cp.write_text(json.dumps(config[label],indent=2)+"\n")
                state={name:parameter.detach().contiguous() for name,parameter in model.named_parameters()}
                save_file(state,target/"source.safetensors",metadata={"source":"synthetic planar topology; no pretrained weights"})
                convert(target/"source.safetensors",cp,target/"converted",storage="f32",source_repository="mediaforge/synthetic-planar-decoder",source_revision=PIXAL_REVISION,source_kind="synthetic")
                paths[label]=target/"converted/model.gguf"
        coords=torch.from_numpy(np.load(source/"coords.npy",allow_pickle=False).astype(np.int32))
        cs=torch.cat([torch.zeros(len(coords),1,dtype=torch.int32),coords],dim=1)
        shape=torch.from_numpy(np.load(source/"shape.npy",allow_pickle=False).copy());texture=torch.from_numpy(np.load(source/"texture.npy",allow_pickle=False).copy())
        grid=int(np.load(source/"settings.npy",allow_pickle=False)[0]);resolution=grid*2**(len(config["shape"]["args"]["model_channels"])-1)
        models["shape"].set_resolution(resolution)
        pipeline=SimpleNamespace(low_vram=False,models={"tex_slat_decoder":models["texture"]})
        with torch.no_grad():
            meshes,subs=models["shape"](SparseTensor(shape,cs),return_subs=True)
            tex=namespace["decode_tex_slat"](pipeline,SparseTensor(texture,cs),subs)
        save(directory,coords.numpy(),shape.numpy(),texture.numpy(),grid,.5,True)
        extra=["--shape",str(paths["shape"].resolve()),"--texture",str(paths["texture"].resolve()),"--backend","cpu"]
        expected={"vertices":meshes[0].vertices.numpy(),"faces":meshes[0].faces.numpy(),"coords":tex.coords[:,1:].numpy(),"pbr":tex.feats.numpy(),"grid":[resolution],"progress":[[0,2],[1,2],[2,2]]}
        # Decoder arithmetic has the established 5e-5 tolerance; raw PBR affine
        # fixtures above are exact, whereas this path includes neural roundoff.
        result=run(directory,extra); rec=compare(directory,expected,result)
        if result.returncode==0:
            actual=np.load(directory/"actual_pbr.npy",allow_pickle=False);ref=tex.feats.numpy().reshape(-1)
            rec["tensors"]["pbr"]={"passed":actual.shape==ref.shape and bool(np.allclose(actual,ref,atol=5e-5,rtol=5e-5)),"exact":False,"max_abs_error":float(np.max(np.abs(actual-ref))) if actual.shape==ref.shape else None}
            rec["passed"]=all(r["passed"] for r in rec["tensors"].values())
        if len(meshes[0].faces)==0:
            rec["empty_surface_rejection"]={"passed":result.returncode==1 and "mesh contains no triangles" in result.stderr and not list(directory.glob("actual_*")),"reference_triangles":0}
            rec["passed"]=rec["empty_surface_rejection"]["passed"]
        rec["checkpoint_sha256"]={label:digest(paths[label]) for label in models}
        records.append(rec)

    checks={}; baseline=a.output_dir/"dense_random"
    expected_errors={"nan":"non-finite mesh field","extent":"invalid mesh field dimensions","channels":"invalid mesh field dimensions","coordinate":"mesh coordinate outside grid","duplicate":"duplicate mesh coordinate","grid":"invalid mesh field dimensions","margin":"invalid voxel margin","budget":"explicit triangle budget","voxel_budget":"invalid mesh field dimensions","invalid_budget":"invalid mesh decoding budget","empty_surface":"mesh contains no triangles","texture_nan":"non-finite mesh field","cancel_before":"mesh decoding cancelled","cancel_vertices":"mesh decoding cancelled","cancel_final":"mesh decoding cancelled"}
    for case,error in expected_errors.items():
        directory=a.output_dir/"negative"/case; directory.mkdir(parents=True)
        for name in ("coords","shape","texture","settings"): shutil.copyfile(baseline/(name+".npy"),directory/(name+".npy"))
        result=run(directory,["--fault",case]);checks[case]={"passed":result.returncode==1 and error in result.stderr and not list(directory.glob("actual_*")),"error":result.stderr.strip()}
    base=a.output_dir/"connected_f32";source=a.sparse_fixtures/"f32"
    extra=["--shape",str((source/"shape/converted/model.gguf").resolve()),"--texture",str((source/"texture/converted/model.gguf").resolve()),"--backend","cpu"]
    for case,error in {"latent_order":"surface decoder/model/coordinate/backend mismatch","model_kind":"surface decoder/model/coordinate/backend mismatch","decoder_cancel":"sparse decoder cancelled","cancel_vertices":"mesh decoding cancelled","cancel_final":"mesh decoding cancelled"}.items():
        directory=a.output_dir/"negative"/("connected_"+case);directory.mkdir(parents=True)
        for name in ("coords","shape","texture","settings"): shutil.copyfile(base/(name+".npy"),directory/(name+".npy"))
        result=run(directory,extra+["--fault",case]);checks["connected_"+case]={"passed":result.returncode==1 and error in result.stderr and not list(directory.glob("actual_*")),"error":result.stderr.strip()}
    sources=[geometry_source,fdg_source,mesh_source,pipeline_source,a.trellis2_source/"o-voxel/src/hash/hash.cu"]
    report={"passed":all(r["passed"] for r in records+list(checks.values())),"cases":records,"negative_checks":checks,
            "reference_revision":PIXAL_REVISION,"trellis2_revision":TRELLIS2_REVISION,"reference_hashes":{str(p):digest(p) for p in sources},"binary_sha256":digest(a.binary),
            "reference_adapter":"Unchanged o_voxel triangulation / Pixal FDG and texture methods; GPU hashmap replaced by CPU lookup with bounds and sentinel semantics",
            "torch_gpu_initialized":torch.cuda.is_initialized(),"trained_weights":"NOT USED","vulkan_hole_filling_uv_bake_glb_library":"NOT TESTED",
            "packages":{n:importlib.metadata.version(n) for n in ("torch","numpy","gguf")}}
    (a.output_dir/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"passed":report["passed"],"cases":len(records),"negative_checks":len(checks)}))
    return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
