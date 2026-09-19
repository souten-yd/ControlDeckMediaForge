#!/usr/bin/env python3
"""Actual MoGe CPU camera -> native Pixal GLB, synthetic model acceptance only."""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any

from camera import _validate_config, MOGE_REVISION, file_sha256, infer_camera, local_moge, moge_model_class
from convert_flow import PIXAL_REVISION
from prepare_camera import prepare_camera_input
from prepare_image import frame_foreground


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('moge-source', 'pixal-source', 'pipeline-fixtures', 'binary', 'core-python', 'blender', 'output-dir'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    if a.output_dir.exists(): p.error('fresh output directory required')
    for source, pin in ((a.moge_source, MOGE_REVISION), (a.pixal_source, PIXAL_REVISION)):
        if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=pin or subprocess.check_output(['git','-C',str(source),'diff','HEAD','--']):
            p.error('pinned unchanged sources required')
    previous=json.loads((a.pipeline_fixtures/'report.json').read_text())
    if not previous['passed'] or any(c['source_kind']!='synthetic' for c in previous['cases']): p.error('passing synthetic pipeline fixtures required')
    os.environ.update(HIP_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='-1',CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1')
    import numpy as np
    import torch
    from PIL import Image
    torch.set_num_threads(2);torch.manual_seed(919)
    a.output_dir.mkdir(parents=True)
    model_type=moge_model_class(a.moge_source)
    config=json.loads((a.moge_source/'configs/train/v2.json').read_text())['model']
    _validate_config(config)
    config['encoder'].update(backbone='dinov2_vits14',intermediate_layers=[2,5,8,11],dim_out=32)
    for name in ('neck','points_head','normal_head','mask_head'):
        config[name]['dim_res_blocks']=[32]*5
        config[name]['dim_in']=[34,2,2,2,2] if name=='neck' else [32]*5
    config['scale_head']['dims']=[384,32,32,1];config['num_tokens_range']=[9,16]
    model=model_type(**config).eval()
    # All actual neural classes run. Calibration makes synthetic UV correlation
    # and mask validity suitable for focal fitting; it is not learned geometry.
    with torch.no_grad():
        w=model.neck.input_blocks[4];w.weight.zero_();w.bias.zero_();w.weight[0,0]=1;w.weight[1,1]=1
        w=model.points_head.input_blocks[4];w.weight.zero_();w.bias.zero_();w.weight[0,0]=1;w.weight[1,1]=1;w.weight[2,2]=1
        w=model.points_head.output_blocks[4];w.weight.zero_();w.bias.zero_();w.weight[0,0]=1;w.weight[1,1]=1;w.weight[2,2]=.05
        model.mask_head.output_blocks[4].bias.fill_(4)
    checkpoint=a.output_dir/'moge-synthetic.pt'
    torch.save({'model_config':config,'model':model.state_dict()},checkpoint)
    checkpoint_hash=file_sha256(checkpoint)
    (a.output_dir/'model-config.json').write_text(json.dumps(config,indent=2)+'\n')
    source=a.pixal_source/'inference.py'
    names={'compute_f_pixels','distance_from_fov','get_camera_params_wild_moge'}
    nodes=[n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(nodes)==3
    ns={'torch':torch,'np':np,'math':math,'Image':Image}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
    cases=[];negatives=[]
    rng=np.random.default_rng(919)
    with local_moge(a.moge_source,checkpoint,checkpoint_hash,a.output_dir) as loaded:
        assert all(torch.equal(v,loaded.state_dict()[k]) for k,v in model.state_dict().items())
        for label,size,options in (
            ('square_default',(40,40),{}),('wide',(56,32),{'num_tokens':9}),
            ('tall',(30,54),{'num_tokens':25}),('scaled_extended',(48,40),{'mesh_scale':1.3,'extend_pixel':13,'image_resolution':768}),
        ):
            image=Image.fromarray(rng.integers(0,256,(size[1],size[0],3),dtype=np.uint8));path=a.output_dir/(label+'.png');image.save(path)
            calls=[]
            proxy=SimpleNamespace(infer=lambda tensor:loaded.infer(tensor,num_tokens=options.get('num_tokens'),resolution_level=9,use_fp16=False))
            expected=ns['get_camera_params_wild_moge'](path,proxy,device='cpu',**{k:v for k,v in options.items() if k!='num_tokens'})
            result=infer_camera(loaded,image,progress=lambda *v:calls.append(v),**options)
            repeated=infer_camera(loaded,image,**options)
            errors={k:abs(getattr(result,k)-value) for k,value in expected.items()}
            assert max(errors.values())==0 and result==repeated
            assert any(v[0]=='camera_encoder_block_11' for v in calls) and calls[-1][0]=='camera_complete'
            cases.append({'name':label,'camera':result.as_dict(),'reference':expected,'max_abs':max(errors.values()),'repeat_exact':True,'neural_stages':calls})
        original_infer=loaded.infer
        base=image.copy()
        def rejected(label: str, call: Any, message: str) -> None:
            try:call()
            except (ValueError,RuntimeError,InterruptedError) as e:
                assert message in str(e),(label,str(e));negatives.append({'case':label,'error':str(e)})
            else:raise AssertionError(label+' accepted')
        for label,kwargs,message in (
            ('scale',{'mesh_scale':0},'invalid Pixal camera'),('extension',{'extend_pixel':-1},'invalid Pixal camera'),
            ('resolution',{'image_resolution':True},'invalid Pixal camera'),('tokens',{'num_tokens':0},'token count'),
            ('cancel_before',{'cancelled':lambda:True},'cancelled'),
        ):rejected(label,lambda kwargs=kwargs:infer_camera(loaded,base,**kwargs),message)
        rejected('image_mode',lambda:infer_camera(loaded,base.convert('RGBA')),'framed RGB')
        loaded.train();rejected('training_model',lambda:infer_camera(loaded,base),'eval model');loaded.eval()
        for stage in ('camera_encoder','camera_encoder_block_5','camera_neck','camera_points_head','camera_mask_head','camera_scale_head','camera_complete'):
            stop=[False]
            def cancel_stage(name: str,_done: int,_total: int) -> None:
                if name==stage:stop[0]=True
            rejected('cancel_'+stage,lambda:infer_camera(loaded,base,cancelled=lambda:stop[0],progress=cancel_stage),'cancelled')
            assert not any(m._forward_pre_hooks for m in loaded.modules())
        # Boundary fault injection is separate from the actual-neural evidence.
        for name in ('missing_intrinsics','nan_intrinsics','negative_focal','principal_point','mask_empty','mask_shape'):
            output={'intrinsics':torch.eye(3),'mask':torch.ones(base.height,base.width,dtype=torch.bool)}
            output['intrinsics'][:2,2]=.5
            if name=='missing_intrinsics':output.pop('intrinsics')
            elif name=='nan_intrinsics':output['intrinsics'][0,0]=float('nan')
            elif name=='negative_focal':output['intrinsics'][0,0]=-1
            elif name=='principal_point':output['intrinsics'][0,2]=.4
            elif name=='mask_empty':output['mask'].zero_()
            else:output['mask']=output['mask'][:1]
            loaded.infer=lambda *_args,output=output,**_kw:output
            rejected(name,lambda:infer_camera(loaded,base),'MoGe camera')
        tiny_mask=torch.zeros(128,128,dtype=torch.bool);tiny_mask[1,1]=True;tiny_mask[3,3]=True
        matrix=torch.eye(3);matrix[:2,2]=.5
        loaded.infer=lambda *_args,**_kw:{'intrinsics':matrix,'mask':tiny_mask}
        rejected('undersampled_foreground',lambda:infer_camera(loaded,base.resize((128,128))),'insufficient valid foreground')
        loaded.infer=original_infer
        # Cancellation leaves the borrowed model reusable; image pixels affect
        # the actual inferred camera even with synthetic calibrated heads.
        original_camera=infer_camera(loaded,base)
        changed=Image.fromarray(np.asarray(base)[:,:,::-1].copy())
        changed_camera=infer_camera(loaded,changed)
        image_focal_delta=abs(changed_camera.focal_x_normalized-original_camera.focal_x_normalized)
        assert original_camera.foreground_pixels>1 and image_focal_delta>1e-7
    del loaded,model
    envelope=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
    original_config=envelope['model_config'];original_state=envelope['model']
    for label,error in (('unknown_config','configuration'),('bad_backbone','encoder'),('missing_tensor','tensor table mismatch'),
                        ('wrong_shape','tensor table mismatch'),('nan_tensor','non-finite'),('integer_tensor','unsupported')):
        config_copy=json.loads(json.dumps(original_config));state=original_state.copy()
        key='encoder.backbone.cls_token'
        if label=='unknown_config':config_copy['network_url']='forbidden'
        elif label=='bad_backbone':config_copy['encoder']['backbone']='guessed_model'
        elif label=='missing_tensor':state.pop(key)
        elif label=='wrong_shape':state[key]=state[key][...,:2]
        elif label=='nan_tensor':state[key]=state[key].clone();state[key].view(-1)[0]=float('nan')
        else:state[key]=state[key].to(torch.int64)
        bad=a.output_dir/('bad-'+label+'.pt');torch.save({'model_config':config_copy,'model':state},bad)
        def load_bad() -> None:
            with local_moge(a.moge_source,bad,file_sha256(bad),a.output_dir):
                pass
        rejected(label,load_bad,error)
    del envelope,original_state,state
    kwargs={'source':a.moge_source,'checkpoint':checkpoint,'checkpoint_sha256':checkpoint_hash,'allowed_root':a.output_dir,
            'source_kind':'synthetic','low_size':12,'high_size':16}
    source_image=a.output_dir/'input.png';shutil.copy2(a.pipeline_fixtures/'cascade1024-input/input.png',source_image)
    kwargs['image_path']=source_image
    output=a.output_dir/'prepared'
    # Real private CPU worker process must exit before native generation starts.
    command=[sys.executable,str(Path(__file__).with_name('prepare_camera.py')),'--source',str(a.moge_source),
             '--checkpoint',str(checkpoint),'--checkpoint-sha256',checkpoint_hash,'--allowed-root',str(a.output_dir),
             '--input',str(source_image),'--output-dir',str(output),'--source-kind','synthetic','--low-size','12','--high-size','16']
    start=time.monotonic();process=subprocess.run(command,text=True,capture_output=True,timeout=120)
    (a.output_dir/'prepare.log').write_text(process.stdout+process.stderr)
    assert process.returncode==0,process.stdout+process.stderr
    prepare_seconds=time.monotonic()-start
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['checkpoint_sha256']==checkpoint_hash and all(file_sha256(output/name)==value for name,value in manifest['files'].items())
    for name in ('rgb_low.npy','rgb_high.npy'):
        assert np.array_equal(np.load(output/name),np.load(a.pipeline_fixtures/'cascade1024-input'/name))
    for label,changes,error in (
        ('wrong_hash',{'checkpoint_sha256':'0'*64},'hash'),
        ('allowed_root_escape',{'allowed_root':output},'escapes'),
        ('cancel_preprocess',{'cancelled':lambda:True},'cancelled'),
        ('bad_kind',{'source_kind':'guessed'},'source_kind'),
    ):
        target=a.output_dir/('negative-'+label)
        rejected(label,lambda:prepare_camera_input(output_dir=target,**{**kwargs,**changes}),error)
        assert not target.exists()
    stop=[False]
    def stop_neck(name: str,_done: int,_total: int) -> None:
        if name=='camera_neck':stop[0]=True
    target=a.output_dir/'negative-cancel-staged'
    rejected('cancel_staged',lambda:prepare_camera_input(output_dir=target,**kwargs,cancelled=lambda:stop[0],progress=stop_neck),'cancelled')
    assert not target.exists()
    old_manifest=(output/'manifest.json').read_bytes()
    try:prepare_camera_input(output_dir=output,**kwargs)
    except FileExistsError:negatives.append({'case':'output_exists','error':'FileExistsError'})
    else:raise AssertionError('existing output overwritten')
    assert (output/'manifest.json').read_bytes()==old_manifest
    opaque=a.output_dir/'opaque.png';Image.new('RGB',(12,12)).save(opaque)
    rejected('opaque_requires_provider',lambda:prepare_camera_input(output_dir=a.output_dir/'opaque-output',**{**kwargs,'image_path':opaque}),'background-removal provider')
    # Signal a real owned preprocessing process in an actual encoder block.
    stopped=a.output_dir/'terminated';cmd=command.copy();cmd[cmd.index('--output-dir')+1]=str(stopped)
    child=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    observed=False;buffer=bytearray();start=time.monotonic()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout,selectors.EVENT_READ)
            while child.poll() is None and time.monotonic()-start<60:
                for key,_ in selector.select(.1):
                    buffer.extend(os.read(key.fileobj.fileno(),4096))
                    if b'camera_encoder_block_0' in buffer:
                        observed=True;break
                if observed:break
        assert observed,'no live encoder block observed'
        kill_time=time.monotonic();child.send_signal(signal.SIGTERM);tail,_=child.communicate(timeout=10)
        buffer.extend(tail);reap=time.monotonic()-kill_time
        assert child.returncode==1 and not stopped.exists()
    finally:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
    (a.output_dir/'termination.log').write_bytes(buffer)
    # All native models retain the exact prior verified synthetic identities.
    models={name:a.pipeline_fixtures/'models'/name/'converted/model.gguf' for name in previous['models']}
    if any(not path.exists() for path in models.values()):
        # Models reused by the pipeline checker carry their original paths in
        # the exact saved native command; do not guess alternate filenames.
        saved=json.loads((a.pipeline_fixtures/'cascade1024.command.json').read_text())['argv']
        models={name:Path(saved[saved.index('--'+name)+1]) for name in previous['models']}
    assert all(file_sha256(path)==previous['models'][name] for name,path in models.items())
    source_manifest=a.output_dir/'source-manifest.json'
    source_manifest.write_text(json.dumps({'native_models':previous['models'],'camera_model':checkpoint_hash,'camera_source':MOGE_REVISION},sort_keys=True,indent=2)+'\n')
    for name in ('settings.npy','samplers.npy','shape_norm.npy','texture_norm.npy'):
        shutil.copy2(a.pipeline_fixtures/'cascade1024-input'/name,output/name)
    input_manifest=output/'native-input-manifest.json'
    input_manifest.write_text(json.dumps({name:file_sha256(output/name) for name in ('manifest.json','settings.npy','samplers.npy','shape_norm.npy','texture_norm.npy')},sort_keys=True,indent=2)+'\n')
    exports=[]
    for label in ('connected','repeated'):
        target=a.output_dir/label
        cmd=[str(a.binary),str(output),str(target),'cpu',*[x for name,path in models.items() for x in ('--'+name,str(path))],
             '--source-sha',file_sha256(source_manifest),'--input-sha',file_sha256(input_manifest),'--native-noise','--diagnostics']
        start=time.monotonic();native=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        (a.output_dir/(label+'.log')).write_text(native.stdout+native.stderr);assert native.returncode==0,native.stderr
        result=json.loads((target/'report.json').read_text());result.update(seconds=time.monotonic()-start,output=str(target/'asset.glb'))
        exports.append(result)
    import struct
    def glb_payload(path: Path) -> tuple[Any,bytes]:
        raw=path.read_bytes();length=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+length])
        doc['asset']['extras'].pop('generated')
        assert doc['asset']['extras']['pixal']['source_sha256']==file_sha256(source_manifest)
        assert doc['asset']['extras']['pixal']['input_sha256']==file_sha256(input_manifest)
        return doc,raw[28+length:]
    assert glb_payload(a.output_dir/'connected/asset.glb')==glb_payload(a.output_dir/'repeated/asset.glb')
    for path in (a.output_dir/'connected').glob('actual_*.npy'):
        assert path.read_bytes()==(a.output_dir/'repeated'/path.name).read_bytes(),path.name
    manifest_path=a.output_dir/'outputs.json'
    manifest_path.write_text(json.dumps([entry['output'] for entry in exports],indent=2)+'\n')
    code='import json,sys; from pathlib import Path; from mediaforge.glb import validate_glb; print(json.dumps({p:validate_glb(Path(p).read_bytes()) for p in json.loads(Path(sys.argv[1]).read_text())}))'
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[2]/'backend'))
    validation=subprocess.run([str(a.core_python),'-c',code,str(manifest_path)],env=env,text=True,capture_output=True,timeout=120)
    (a.output_dir/'core.log').write_text(validation.stdout+validation.stderr);assert validation.returncode==0,validation.stderr
    core=json.loads(validation.stdout);assert len(core)==len(exports) and all(row['status']=='passed' for row in core.values())
    cmd=[str(a.blender),'--background','--factory-startup','--threads','4','--python',str(Path(__file__).with_name('check_surface_blender.py')),'--',str(manifest_path),str(a.output_dir/'blender-report.json')]
    checked=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    (a.output_dir/'blender.log').write_text(checked.stdout+checked.stderr);assert checked.returncode==0,checked.stderr
    report={'passed':True,'cases':cases,'negative_cases':negatives,'prepare_seconds':prepare_seconds,
            'connected':exports,'core':core,'blender':json.loads((a.output_dir/'blender-report.json').read_text()),
            'termination':{'observed_stage':'camera_encoder_block_0','exit':child.returncode,'seconds_to_reap':reap,'output_retained':False},
            'checkpoint_sha256':checkpoint_hash,'binary_sha256':file_sha256(a.binary),
            'source_sha256':{str(source):file_sha256(source),str(a.moge_source/'moge/model/v2.py'):file_sha256(a.moge_source/'moge/model/v2.py')},
            'packages':{name:importlib.metadata.version(name) for name in ('torch','numpy','pillow','scipy','utils3d','accelerate')},
            'image_focal_delta':image_focal_delta,'public_source_config_accepted':True,
            'torch_gpu_initialized':torch.cuda.is_initialized(),'pretrained_weights':'NOT USED',
            'fixture':'actual MoGe ViT-S/14 encoder, 32-channel five-level heads; UV/mask-calibrated synthetic parameters; full forward/infer runs',
            'not_tested':['trained camera/shape/quality','full-size MoGe and mixed precision','MoGe/Vulkan','opaque background model','Host lease and native Vulkan','installed Library and rigging']}
    assert not report['torch_gpu_initialized']
    (a.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'camera_cases':len(cases),'negative_cases':len(negatives),'connected_glbs':len(exports),'prepare_seconds':prepare_seconds}))
    return 0


if __name__=='__main__':raise SystemExit(main())
