#!/usr/bin/env python3
"""Connected native RGB-to-GLB CPU acceptance; synthetic checkpoints only.

Runs the pinned run() control flow and actual neural decoders on CPU. CPU-only
adapters cover image input, NATTEN, FlexGEMM hash/conv and the unrepaired-mesh
boundary. Does not claim GPU postprocessing, trained quality, or Torch RNG parity.
"""
from __future__ import annotations
import argparse
import ast
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import struct
import subprocess
import sys
import time
from types import MethodType, SimpleNamespace
from typing import Any
import typing
from convert_flow import PIXAL_REVISION, convert as convert_flow, digest
from convert_ss_decoder import convert as convert_ss
from convert_sparse_decoder import convert as convert_sparse
from convert_vision import NAF_REVISION
from sparse_cpu_reference import FLEX_REVISION, install
from prepare_image import frame_foreground, prepare_rgb


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('pixal-source', 'naf-source', 'flex-source', 'trellis2-source', 'vision-fixtures', 'flow-fixtures', 'ss-fixtures', 'mesh-fixtures', 'binary', 'core-python', 'blender', 'output-dir'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    pins = [(a.pixal_source, PIXAL_REVISION), (a.naf_source, NAF_REVISION), (a.flex_source, FLEX_REVISION), (a.trellis2_source, '75fbf0183001ed9876c8dbb35de6b68552ee08bd')]
    for root, pin in pins:
        if subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() != pin or subprocess.check_output(['git', '-C', str(root), 'diff', 'HEAD', '--']): p.error('pinned, unchanged references required')
    if a.output_dir.exists(): p.error('new output directory required')
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1', ATTN_BACKEND='sdpa', SPARSE_ATTN_BACKEND='sdpa', SPARSE_CONV_BACKEND='none')
    sys.path[:0] = [str(a.pixal_source), str(a.naf_source)]
    import numpy as np
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from safetensors.torch import load_file, save_file
    from torchvision import transforms
    from transformers import DINOv3ViTConfig, DINOv3ViTModel
    from natten import na2d
    from src.model.naf import NAF
    from src.layers import attentions
    from pixal3d.models.sparse_structure_vae import SparseStructureDecoder
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler
    install(a.pixal_source, a.flex_source)
    from pixal3d.models.sc_vaes.sparse_unet_vae import SparseUnetVaeDecoder
    if importlib.metadata.version('transformers') != '4.57.3' or importlib.metadata.version('natten') != '0.21.0': raise ValueError('pinned reference packages required')
    torch.set_num_threads(2)
    def cpu_attention(q: Any, k: Any, v: Any, **kw: Any) -> Any:
        assert kw.pop('backend') == 'cutlass-fna'
        width = q.shape[-1]; parts = []
        for start in range(0, v.shape[-1], width):
            part = v[..., start:start+width]
            parts.append(na2d(q, k, F.pad(part, (0, width-part.shape[-1])), **kw, backend='flex-fna', torch_compile=False)[..., :part.shape[-1]])
        return torch.cat(parts, dim=-1)
    attentions.na2d = cpu_attention
    class CpuHash:
        def hashmap_insert_3d_idx_as_val_cuda(self, keys: Any, vals: Any, coords: Any, w: int, h: int, d: int) -> None:
            assert coords.device.type == 'cpu' and w*h*d < 2**32
            self.table = {tuple(row): i for i, row in enumerate(coords.tolist())}
        def hashmap_lookup_3d_cuda(self, keys: Any, vals: Any, coords: Any, w: int, h: int, d: int) -> Any:
            return torch.tensor([self.table.get(tuple(row), 0xffffffff) if all(0 <= v < n for v, n in zip(row[1:], (w,h,d))) else 0xffffffff for row in coords.tolist()], dtype=torch.uint32)
    ns = {**vars(typing), 'torch': torch, 'nn': torch.nn, 'F': F, 'np': np, 'Image': Image, 'transforms': transforms, 'DINOv3ViTModel': DINOv3ViTModel, 'SparseTensor': SparseTensor, 'SparseUnetVaeDecoder': SparseUnetVaeDecoder, 'sp': SimpleNamespace(SparseTensor=SparseTensor), '_C': CpuHash()}
    sources = []
    def extract(path: Path, names: set[str], cls: bool = False) -> None:
        sources.append(path); body = ast.parse(path.read_text()).body
        if cls: body = next(n for n in body if isinstance(n, ast.ClassDef)).body
        nodes = [n for n in body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
        assert len(nodes) == len(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    extract(a.trellis2_source/'o-voxel/o_voxel/convert/flexible_dual_grid.py', {'_init_hashmap', 'flexible_dual_grid_to_mesh'})
    extract(a.pixal_source/'pixal3d/representations/mesh/base.py', {'Mesh'})
    extract(a.pixal_source/'pixal3d/models/sc_vaes/fdg_vae.py', {'FlexiDualGridVaeDecoder'})
    extract(a.pixal_source/'pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py', {'project_points_to_image_batch', 'sample_features', 'ProjGrid', 'DinoV3ProjFeatureExtractor'})
    extract(a.pixal_source/'pixal3d/pipelines/pixal3d_image_to_3d.py', {'preprocess_image', 'get_proj_cond_ss', 'get_proj_cond_shape', 'sample_sparse_structure', 'sample_shape_slat', 'sample_tex_slat', 'decode_shape_slat', 'decode_tex_slat', 'run'}, True)
    a.output_dir.mkdir(parents=True)
    fixture_root = a.output_dir/'models'; fixture_root.mkdir()
    model_paths: dict[str, Path] = {}; models: dict[str, Any] = {}; configs: dict[str, Any] = {}; reused: dict[str, Any] = {}
    provenance = dict(source_repository='mediaforge/synthetic-native-pipeline', source_revision=PIXAL_REVISION, source_kind='synthetic')
    def original(part: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = json.loads((part/'converted/manifest.json').read_text())
        assert manifest['source']['source_kind'] == 'synthetic' and manifest['storage'] == 'f32'
        assert digest(part/'source.safetensors') == manifest['source']['checkpoint_sha256'] and digest(part/'config.json') == manifest['source']['config_sha256'] and digest(part/'converted/model.gguf') == manifest['output_sha256']
        reused[str(part)] = manifest['output_sha256']
        return json.loads((part/'config.json').read_text()), load_file(part/'source.safetensors')
    def store(label: str, config: dict[str, Any], model: Any, converter: Any, **kw: Any) -> None:
        out = fixture_root/label; out.mkdir()
        (out/'config.json').write_text(json.dumps(config, indent=2)+'\n')
        save_file({name: value.detach().contiguous() for name, value in model.named_parameters()}, out/'source.safetensors', metadata={'source': 'synthetic pipeline evaluation; no pretrained weights'})
        converter(out/'source.safetensors', out/'config.json', out/'converted', storage='f32', **provenance, **kw)
        model_paths[label] = out/'converted/model.gguf'; models[label] = model.eval(); configs[label] = config
    for label in ('dino', 'naf'):
        part = a.vision_fixtures/'f32_full'/label; cfg, state = original(part)
        if label == 'dino':
            config = DINOv3ViTConfig.from_dict(cfg); config._attn_implementation = 'sdpa'; model = DINOv3ViTModel(config)
        else: model = NAF(**cfg['args'])
        model.load_state_dict(state, strict=True);models[label] = model.eval();model_paths[label] = part/'converted/model.gguf'
    for label, stage, resolution in (('ss-flow','ss',8), ('shape-lr','shape',32), ('shape-hr','shape',64), ('texture-flow','texture',64)):
        cfg, state = original(a.flow_fixtures/(stage+'_f32_f32')); cfg['args']['resolution'] = resolution
        model = (SparseStructureFlowModel if stage == 'ss' else ElasticSLatFlowModel)(**cfg['args'])
        if stage == 'ss': state['rope_phases'] = model.state_dict()['rope_phases']
        model.load_state_dict(state, strict=True)
        if stage == 'ss':
            # A deterministic synthetic zero velocity leaves the true SS noise
            # unchanged, allowing a bounded occupancy calibration. All graph
            # operators still execute; this is not trained conditional quality.
            with torch.no_grad(): model.out_layer.weight.zero_(); model.out_layer.bias.zero_()
        store(label, cfg, model, convert_flow, stage=stage)
    cfg, state = original(a.ss_fixtures/'connected_image'); ss = SparseStructureDecoder(**cfg['args']).eval(); ss.load_state_dict(state, strict=True)
    with torch.no_grad():
        torch.manual_seed(42); logits = ss(torch.randn(1, 8, 8, 8, 8)).flatten()
        top = torch.topk(logits, 5).values; threshold = (top[3]+top[4])/2
        assert float(top[3]-top[4]) > 2e-5, 'synthetic occupancy needs a robust strict-threshold margin'
        ss.out_layer[2].bias.sub_(threshold)
    store('ss-decoder', cfg, ss, convert_ss)
    for label, part_name in (('shape-decoder', 'shape'), ('texture-decoder', 'texture')):
        cfg, state = original(a.mesh_fixtures/'connected_full_depth_planar'/part_name)
        model = (ns['FlexiDualGridVaeDecoder'] if part_name == 'shape' else SparseUnetVaeDecoder)(**cfg['args']).eval();model.load_state_dict(state, strict=True)
        if part_name == 'shape':
            with torch.no_grad():
                model.output_layer.weight[3:6].zero_();model.output_layer.bias[3:6] = torch.tensor([-1.,-1.,1.])
        store(label, cfg, model, convert_sparse)
    norm_shape = {'mean': np.linspace(-.7,.8,8,dtype=np.float32).tolist(), 'std': np.linspace(.2,1.7,8,dtype=np.float32).tolist()}
    norm_texture = {'mean': np.linspace(.5,-.3,8,dtype=np.float32).tolist(), 'std': np.linspace(1.8,.7,8,dtype=np.float32).tolist()}
    (fixture_root/'bundle.json').write_text(json.dumps({name:digest(path) for name,path in model_paths.items()},sort_keys=True,indent=2)+'\n')
    model_digest = digest(fixture_root/'bundle.json')
    results: list[dict[str, Any]] = []; comparisons: list[dict[str, Any]] = []; negatives: list[dict[str, Any]] = []
    expected: dict[str, Any] = {}; noises: dict[str, Any] = {}; current = ''
    def record(name: str, value: Any) -> None:
        expected[name] = value.detach().cpu().numpy().copy() if torch.is_tensor(value) else np.asarray(value).copy()
    def make_extractor(size: int, grid: int, target: int) -> Any:
        ex = ns['DinoV3ProjFeatureExtractor'].__new__(ns['DinoV3ProjFeatureExtractor']);torch.nn.Module.__init__(ex)
        ex.model=models['dino'];ex.image_size=size;ex.patch_number=size//4;ex.transform=transforms.Normalize([.485,.456,.406],[.229,.224,.225]);ex.grid_resolution=grid;ex.proj_grid=ns['ProjGrid'](grid,size);ex.use_naf_upsample=bool(target);ex.naf_model=models['naf'];ex.naf_target_size=(target,target)
        return ex
    class RecordingSampler(FlowEulerGuidanceIntervalSampler):
        @torch.no_grad()
        def sample(self, model: Any, noise: Any, **kw: Any) -> Any:
            label = next(label for label in ('ss-flow','shape-lr','shape-hr','texture-flow') if model is models[label]);label = {'ss-flow':'ss','shape-lr':'lr','shape-hr':'hr','texture-flow':'texture'}[label]
            noises[label] = noise.feats.detach().clone() if isinstance(noise,SparseTensor) else noise[0].reshape(8,-1).T.contiguous().clone()
            kw['verbose']=False;result=super().sample(model,noise,**kw)
            for i, value in enumerate(result.pred_x_t): record(label+'.sample'+str(i),value.feats if isinstance(value,SparseTensor) else value[0].reshape(8,-1).T)
            if label=='ss': record('ss_latent',result.samples)
            return result
    def run_reference(raw: Any, resolution: int, budget: int) -> tuple[Any, int]:
        nonlocal expected, noises
        expected={};noises={};sampler=RecordingSampler(1e-5)
        params={'steps':3,'guidance_strength':2.5,'guidance_rescale':.3,'guidance_interval':(0,1)}
        # SS zero velocity makes rescale=0/0 undefined; disable only its CFG rescale.
        ss_params={**params,'guidance_rescale':0.}
        pipeline=SimpleNamespace(device='cpu',low_vram=False,default_pipeline_type='1024_cascade',
            models={'sparse_structure_flow_model':models['ss-flow'],'sparse_structure_decoder':models['ss-decoder'],'shape_slat_flow_model_512':models['shape-lr'],'shape_slat_flow_model_1024':models['shape-hr'],'tex_slat_flow_model_1024':models['texture-flow'],'shape_slat_decoder':models['shape-decoder'],'tex_slat_decoder':models['texture-decoder']},
            sparse_structure_sampler=sampler,shape_slat_sampler=sampler,tex_slat_sampler=sampler,sparse_structure_sampler_params=ss_params,shape_slat_sampler_params=params,tex_slat_sampler_params=params,
            shape_slat_normalization=norm_shape,tex_slat_normalization=norm_texture)
        extractors={'ss_image':make_extractor(12,8,0),'lr_image':make_extractor(12,32,8),'hr_image':make_extractor(16,64,8),'texture_image':make_extractor(16,64,12)}
        pipeline.image_cond_model_ss=extractors['ss_image'];pipeline.image_cond_model_shape_512=extractors['lr_image'];pipeline.image_cond_model_shape_1024=extractors['hr_image'];pipeline.image_cond_model_tex_1024=extractors['texture_image']
        def image_condition(self: Any, *args: Any, **kw: Any) -> Any:
            if isinstance(args[0], list): ex=extractors['ss_image']; images=args[0]; rest=args[1:]; method='get_proj_cond_ss'
            else: ex=args[0];images=args[1];rest=args[2:];method='get_proj_cond_shape'
            label=next(name for name,obj in extractors.items() if obj is ex)
            # CPU adapter for upstream's list-of-PIL branch, which hardcodes cuda.
            resized=images[0].resize((ex.image_size,ex.image_size),Image.Resampling.LANCZOS).convert('RGB')
            pixels=np.asarray(resized,dtype=np.float32).transpose(2,0,1).copy()/255
            rgb=torch.from_numpy(pixels)[None]
            tokens=ex.extract_features(ex.transform(rgb));record(label+'.global',tokens[:,:5]);record(label+'.patches',tokens[:,5:])
            pair=ns[method](self,rgb,*rest,**kw) if method=='get_proj_cond_ss' else ns[method](self,ex,rgb,*rest,**kw)
            if ex.use_naf_upsample:
                record(label+'.projected',pair['cond']['proj'].feats)
            return pair
        for name in ('preprocess_image','sample_sparse_structure','sample_shape_slat','sample_tex_slat','decode_shape_slat','decode_tex_slat'):
            setattr(pipeline,name,MethodType(ns[name],pipeline))
        pipeline.get_proj_cond_ss=MethodType(image_condition,pipeline);pipeline.get_proj_cond_shape=MethodType(image_condition,pipeline)
        def decode_boundary(self: Any, shape: Any, texture: Any, resolution: int) -> Any:
            record('hr',shape.feats);record('texture',texture.feats);record('hr_coords',shape.coords[:,1:])
            meshes,subs=self.decode_shape_slat(shape,resolution);tex=self.decode_tex_slat(texture,subs)
            record('vertices',meshes[0].vertices);record('faces',meshes[0].faces);record('pbr',tex.feats);record('decoded_coords',tex.coords[:,1:])
            return meshes
        pipeline.decode_latent=MethodType(decode_boundary,pipeline)
        hooks=[models['ss-decoder'].register_forward_hook(lambda _m,_i,v:record('ss_logits',v)),
               models['shape-decoder'].output_layer.register_forward_hook(lambda _m,_i,v:record('shape_fields',v.feats)),
               models['texture-decoder'].output_layer.register_forward_hook(lambda _m,_i,v:record('texture_fields',v.feats))]
        # Wrap the real method only to retain its actual output; do not supply coordinates.
        real_upsample=models['shape-decoder'].upsample
        def capture_upsample(slat: Any, **kw: Any) -> Any:
            record('lr',slat.feats);record('ss_coords',slat.coords[:,1:]);out=real_upsample(slat,**kw);record('upsampled_coords',out[:,1:]);return out
        models['shape-decoder'].upsample=capture_upsample
        try:
            with torch.no_grad(): result=ns['run'](pipeline,raw,camera_params={'camera_angle_x':.8575560450553894,'distance':2.,'mesh_scale':1.},seed=42,return_latent=True,pipeline_type=str(resolution)+'_cascade',max_num_tokens=budget)
        finally:
            models['shape-decoder'].upsample=real_upsample
            for h in hooks:h.remove()
        return result[0],result[1][2]
    def save(directory: Path, name: str, values: Any) -> None:
        np.save(directory/(name+'.npy'),np.ascontiguousarray(values,dtype=np.float32))
    def input_digest(src: Path, native_noise: bool) -> str:
        names=['input.png','rgb_low.npy','rgb_high.npy','settings.npy','samplers.npy','camera.npy','shape_norm.npy','texture_norm.npy']
        if not native_noise:names += [stage+'_noise.npy' for stage in ('ss','lr','hr','texture')]
        manifest=src/('input-manifest-native.json' if native_noise else 'input-manifest-provided.json')
        manifest.write_text(json.dumps({name:digest(src/name) for name in names},sort_keys=True,indent=2)+'\n')
        return digest(manifest)
    def argv(src: Path, out: Path, extra: list[str] | None = None) -> list[str]:
        return [str(a.binary),str(src),str(out),'cpu',*[x for name,path in model_paths.items() for x in ('--'+name,str(path))],'--source-sha',model_digest,'--input-sha',input_digest(src,'--native-noise' in (extra or [])),'--diagnostics',*(extra or [])]
    def native(src: Path,name: str,extra: list[str] | None=None,error: str | None=None) -> Path:
        out=a.output_dir/name;cmd=argv(src,out,extra);start=time.monotonic()
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (a.output_dir/(name+'.log')).write_text(r.stdout+r.stderr);(a.output_dir/(name+'.command.json')).write_text(json.dumps({'argv':cmd,'seconds':time.monotonic()-start,'exit':r.returncode},indent=2)+'\n')
        if error:
            assert r.returncode==1 and error in r.stderr and not out.exists(),(name,r.stderr)
            negatives.append({'name':name,'error':error,'exit':r.returncode,'published_output':False})
        else:
            assert r.returncode==0,(name,r.stderr)
            report=json.loads((out/'report.json').read_text());report.update(name=name,seconds=time.monotonic()-start,sha256=digest(out/'asset.glb'));results.append(report)
        return out
    yy,xx=np.mgrid[:26,:34];raw=np.stack(((xx*7)%256,(yy*9)%256,((xx+yy)*5)%256,np.where((xx>4)&(xx<29)&(yy>3)&(yy<22),255,0)),axis=-1).astype(np.uint8)
    raw=Image.fromarray(raw,'RGBA');exports=[]
    for label,resolution,budget in (('cascade1024',1024,49152),('cascade1536',1536,49152),('backoff1024',1536,1)):
        src=a.output_dir/(label+'-input');src.mkdir();raw.save(src/'input.png')
        meshes,actual_res=run_reference(raw,resolution,budget);assert len(meshes[0].faces)>0
        framed=frame_foreground(raw).image
        # Separate source preprocessing call confirms actual pixel framing.
        source_framed=ns['preprocess_image'](SimpleNamespace(),raw)
        assert np.array_equal(np.asarray(framed),np.asarray(source_framed))
        for name,value in {'rgb_low':prepare_rgb(framed,12),'rgb_high':prepare_rgb(framed,16),'camera':[.8575560450553894,2.,1.], 'settings':[resolution,budget,8,8,12,128,600,42],
            'samplers':[[3,1,2.5,0,0,1,1e-5],[3,1,2.5,.3,0,1,1e-5],[3,1,2.5,.3,0,1,1e-5]], 'shape_norm':[norm_shape['mean'],norm_shape['std']],'texture_norm':[norm_texture['mean'],norm_texture['std']],**{name+'_noise':v.numpy() for name,v in noises.items()}}.items():save(src,name,value)
        out=native(src,label);exports.append(out);assert results[-1]['actual_resolution']==actual_res
        for name,value in expected.items():
            ref=np.asarray(value).reshape(-1);save(src,'expected_'+name,ref);actual=np.load(out/('actual_'+name+'.npy'))
            exact=name.endswith('coords') or name=='faces';atol=2e-6 if name=='vertices' else 5e-5
            assert actual.shape==ref.shape,(name,actual.shape,ref.shape)
            if exact:np.testing.assert_array_equal(actual,ref,err_msg=label+'/'+name)
            else:np.testing.assert_allclose(actual,ref,atol=atol,rtol=atol,err_msg=label+'/'+name)
            comparisons.append({'case':label,'name':name,'exact':exact,'atol':0 if exact else atol,'max_abs':float(np.max(np.abs(actual-ref),initial=0))})
        assert results[-1]['token_budget_met']==(len(expected['hr_coords'])<budget)
    src=a.output_dir/'cascade1024-input'
    repeat=native(src,'repeated1024')
    for path in exports[0].glob('actual_*.npy'):assert path.read_bytes()==(repeat/path.name).read_bytes(),path.name
    def semantic_glb(path: Path) -> tuple[Any,bytes]:
        content=path.read_bytes();length=struct.unpack_from('<I',content,12)[0]
        doc=json.loads(content[20:20+length]);doc['asset']['extras'].pop('generated')
        assert doc['asset']['extras']['pixal']['source_sha256']==model_digest
        return doc,content[28+length:]
    assert semantic_glb(exports[0]/'asset.glb')==semantic_glb(repeat/'asset.glb')
    # Default native RNG is repeatable, separately from exact-noise Torch parity.
    seeded=native(src,'native-seed42',['--native-noise']);seeded_again=native(src,'native-seed42-repeat',['--native-noise'])
    for path in seeded.glob('actual_*.npy'):assert path.read_bytes()==(seeded_again/path.name).read_bytes(),path.name
    assert semantic_glb(seeded/'asset.glb')==semantic_glb(seeded_again/'asset.glb')
    assert semantic_glb(seeded/'asset.glb')[0]['asset']['extras']['pixal']['rng_algorithm']=='mt19937-box-muller-f32-v1'
    exports.append(seeded)
    changed=a.output_dir/'changed-image-input';shutil.copytree(src,changed)
    pixels=np.asarray(raw).copy();pixels[:,:,:3]=pixels[:,:,:3][:,:,::-1];different=Image.fromarray(pixels)
    different.save(changed/'input.png');frame=frame_foreground(different).image
    save(changed,'rgb_low',prepare_rgb(frame,12));save(changed,'rgb_high',prepare_rgb(frame,16))
    altered=native(changed,'changed-image');exports.append(altered)
    image_delta=float(np.max(np.abs(np.load(altered/'actual_hr.npy')-np.load(exports[0]/'actual_hr.npy'))))
    assert image_delta>1e-6,'image conditioning must affect the sampled shape'
    assert semantic_glb(altered/'asset.glb')[1]!=semantic_glb(exports[0]/'asset.glb')[1]
    for phase in ('inspect','ss_image','ss_flow','ss_decode','lr_image','lr_flow','upsample','cascade','hr_image','hr_flow','texture_image','texture_flow','shape_decode','texture_decode','mesh','surface_holes','surface_uv','surface_publish'):
        native(src,'negative-cancel-'+phase,['--fault','cancel_'+phase],error='Pixal pipeline cancelled')
    for fault,error in {'cancel_before':'Pixal pipeline cancelled','nan_rgb':'non-finite pipeline input','camera':'invalid pipeline camera','resolution':'invalid pipeline backend/resolution/budget/export mode','budget':'invalid pipeline backend/resolution/budget/export mode','norm':'pipeline normalization std must be positive','provenance':'pipeline output provenance mismatch','no_remesh':'invalid pipeline backend/resolution/budget/export mode','empty_allowed':'invalid pipeline backend/resolution/budget/export mode','target':'invalid pipeline NAF target','sampler':'invalid flow sampler parameters','output_exists':'pipeline output exists','noise_extent':'pipeline noise extent mismatch','noise_nan':'non-finite pipeline input'}.items():native(src,'negative-'+fault,['--fault',fault],error)
    for label,replacement,error in [('shape-lr','texture-flow','pipeline model role/dimension/cascade mismatch'),('dino','naf','pipeline model role/dimension/cascade mismatch')]:
        original_path=model_paths[label];model_paths[label]=model_paths[replacement]
        try:native(src,'negative-model-'+label,error=error)
        finally:model_paths[label]=original_path
    # A real owned-process termination, beyond cooperative callback exceptions.
    stopped=a.output_dir/'terminated-output';cmd=argv(src,stopped)
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    stream=bytearray();ready=False;started=time.monotonic()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout,selectors.EVENT_READ)
            while proc.poll() is None and time.monotonic()-started<30:
                for key,_ in selector.select(.1):
                    stream.extend(os.read(key.fileobj.fileno(),4096))
                    if b'stage=ss_flow 0/' in stream:ready=True;break
                if ready:break
        assert ready and proc.poll() is None and not (stopped/'asset.glb').exists()
        kill_start=time.monotonic();os.killpg(proc.pid,signal.SIGTERM);code=proc.wait(timeout=5)
        assert code==-signal.SIGTERM and not (stopped/'asset.glb').exists()
        termination={'observed_stage':'ss_flow','exit':code,'seconds_to_reap':time.monotonic()-kill_start,'published_glb':False}
    finally:
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
        if proc.stdout:stream.extend(proc.stdout.read());proc.stdout.close()
        if stopped.exists():shutil.rmtree(stopped)
        (a.output_dir/'termination.log').write_bytes(stream)
    manifest=a.output_dir/'glb-manifest.json';manifest.write_text(json.dumps([str(out/'asset.glb') for out in exports],indent=2)+'\n')
    code='import json,sys; from pathlib import Path; from mediaforge.glb import validate_glb; print(json.dumps({p:validate_glb(Path(p).read_bytes()) for p in json.loads(Path(sys.argv[1]).read_text())}))'
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[2]/'backend'))
    check=subprocess.run([str(a.core_python),'-c',code,str(manifest)],env=env,text=True,capture_output=True,timeout=120);(a.output_dir/'core.log').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stderr
    core=json.loads(check.stdout);assert all(row['status']=='passed' for row in core.values())
    cmd=[str(a.blender),'--background','--factory-startup','--threads','4','--python',str(Path(__file__).with_name('check_surface_blender.py')),'--',str(manifest),str(a.output_dir/'blender-report.json')]
    check=subprocess.run(cmd,text=True,capture_output=True,timeout=180);(a.output_dir/'blender.log').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stderr
    assert (a.output_dir/'blender-report.json').exists() and not torch.cuda.is_initialized()
    report={'passed':True,'gpu_initialized':False,'cases':results,'comparisons':comparisons,'negative_cases':negatives,'core':core,'blender':json.loads((a.output_dir/'blender-report.json').read_text()),'references':{str(path):digest(path) for path in sources},'reused_synthetic_models':reused,'models':{name:digest(path) for name,path in model_paths.items()},'binary_sha256':digest(a.binary),'image_change_max_shape_delta':image_delta,'process_termination':termination,'semantic_glb_repeat_equal':True,'not_tested':['trained/full-width quality','Vulkan and Host lease','full DINO/NAF image extents','MoGe/background removal inference','installed Library and rigging','Torch RNG seed equivalence','CuMesh/nvdiffrast/OpenCV postprocessing parity']}
    (a.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(results),'comparisons':len(comparisons),'negative_cases':len(negatives),'blender_imports':len(exports)}))
    return 0


if __name__=='__main__':raise SystemExit(main())
