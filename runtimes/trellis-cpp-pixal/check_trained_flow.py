#!/usr/bin/env python3
"""Full-width trained shape DiT CPU check on eight synthetic coordinates.

Explicit F32 arithmetic with declared F16 storage rounding on both sides.
This numerical test is not full-grid image generation or a quality evaluation.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from convert_flow import PIXAL_REVISION, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pixal-source', 'checkpoint', 'config', 'converted', 'binary', 'output-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    source = args.pixal_source.resolve(strict=True)
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != PIXAL_REVISION or subprocess.check_output(['git', '-C', str(source), 'diff', 'HEAD', '--']):
        parser.error('use the pinned clean Pixal reference')
    manifest = json.loads((args.converted.parent / 'manifest.json').read_text())
    origin = manifest['source']
    if (origin['source_kind'] != 'checkpoint' or origin['source_repository'] != 'TencentARC/Pixal3D' or
        origin['source_revision'] != 'b0cb2e1b794cab9aa0ac38a95d794a4d9337437f' or
        digest(args.checkpoint) != origin['checkpoint_sha256'] or digest(args.config) != origin['config_sha256'] or
        digest(args.converted) != manifest['output_sha256'] or manifest['storage'] != 'f16' or manifest['stage'] != 'shape'):
        parser.error('trained checkpoint identity differs')
    if args.output_dir.exists():
        parser.error('use a fresh output directory')
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1',
                      HF_HUB_OFFLINE='1', ATTN_BACKEND='sdpa', SPARSE_ATTN_BACKEND='sdpa', SPARSE_CONV_BACKEND='none')
    sys.path.insert(0, str(source))
    import numpy as np
    import torch
    from accelerate import init_empty_weights
    from safetensors.torch import load_file
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler
    torch.set_num_threads(2)
    config = json.loads(args.config.read_text())
    model_args = config['args'] | {'dtype': 'float32'}
    started = time.monotonic()
    with init_empty_weights(include_buffers=False):
        model = ElasticSLatFlowModel(**model_args).eval()
    state = load_file(args.checkpoint)
    for name in list(state):
        value = state[name].float()
        state[name] = value.half().float() if value.ndim == 2 and name.endswith('.weight') else value
    model.load_state_dict(state, strict=True, assign=True)
    del state
    torch.manual_seed(91231)
    n, channels = 8, model_args['out_channels']
    xyz = torch.tensor([[0,0,0],[1,3,5],[7,8,9],[16,4,32],[31,31,31],[40,10,22],[60,60,60],[63,63,63]], dtype=torch.int32)
    sc = torch.cat([torch.zeros(n,1,dtype=torch.int32), xyz], dim=1)
    latent = torch.randn(n, channels)
    global_cond = torch.randn(1,5,model_args['cond_channels'])
    projected = torch.randn(n,model_args['proj_in_channels'])
    positive = {'global': global_cond, 'proj': SparseTensor(projected,sc)}
    negative = {'global': torch.zeros_like(global_cond), 'proj': SparseTensor(torch.zeros_like(projected),sc)}
    velocities = []
    class RecordingSampler(FlowEulerGuidanceIntervalSampler):
        def _get_model_prediction(self, *values: Any, **kwargs: Any) -> Any:
            result = super()._get_model_prediction(*values, **kwargs)
            velocities.append(result[2].feats.detach().numpy().copy())
            return result
    with torch.inference_mode():
        result = RecordingSampler(1e-5).sample(model, SparseTensor(latent,sc), positive, negative,
            steps=2, rescale_t=3., guidance_strength=7.5, guidance_rescale=.5,
            guidance_interval=(0.,1.), verbose=False)
    expected = {}
    for i in range(2):
        expected[f'step{i}_velocity'] = velocities[i]
        expected[f'step{i}_clean'] = result.pred_x_0[i].feats.numpy().copy()
        expected[f'step{i}_sample'] = result.pred_x_t[i].feats.numpy().copy()
    reference_seconds = time.monotonic() - started
    del model, result
    gc.collect()
    args.output_dir.mkdir(parents=True)
    arrays = {'coordinates': xyz.numpy().astype(np.float32), 'noise': latent.numpy(),
              'global': global_cond[0].numpy(), 'projected': projected.numpy(),
              'negative_global': np.zeros_like(global_cond[0].numpy()), 'negative_projected': np.zeros_like(projected.numpy())}
    for name,value in (arrays | {'expected_'+k:v for k,v in expected.items()}).items():
        np.save(args.output_dir / (name+'.npy'),value)
    (args.output_dir/'sampler.txt').write_text('2 3 0.00001 7.5 0.5 0 1\n')
    started=time.monotonic()
    native=subprocess.run([str(args.binary.resolve()),str(args.output_dir.resolve()),str(args.converted.resolve()),'cpu','--trained-cpu'],capture_output=True,text=True,timeout=1200)
    native_seconds=time.monotonic()-started
    (args.output_dir/'native.log').write_text(native.stdout+native.stderr)
    comparisons={}
    if native.returncode==0:
        for name,expected_value in expected.items():
            actual=np.load(args.output_dir/('actual_'+name+'.npy'),allow_pickle=False)
            comparisons[name]={'max_abs_error':float(np.max(np.abs(actual-expected_value))),
                              'passed':actual.shape==expected_value.shape and bool(np.allclose(actual,expected_value,atol=1e-3,rtol=1e-3))}
    report={'passed':native.returncode==0 and len(comparisons)==6 and all(v['passed'] for v in comparisons.values()),
            'native_returncode':native.returncode,'comparisons':comparisons,'source':origin,
            'converted_sha256':digest(args.converted),'binary_sha256':digest(args.binary),
            'reference_revision':PIXAL_REVISION,'reference_seconds':reference_seconds,'native_seconds':native_seconds,
            'arithmetic':'float32','storage':'float16 matrices, float32 other tensors','source_dtype':config['args']['dtype'],
            'layers':30,'channels':1536,'coordinates':n,'steps':2,'conditioning':'synthetic, deterministic seed 91231',
            'atol':1e-3,'rtol':1e-3,'torch_gpu_initialized':torch.cuda.is_initialized(),
            'full_generation_tested':False,'quality_tested':False,'adopted':False}
    (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
