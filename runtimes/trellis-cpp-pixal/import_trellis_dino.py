#!/usr/bin/env python3
"""Import the operator's existing, authorized DINOv3 GGUF without downloading.

Only the recorded ilintar ViT-L/16 checkpoint is supported. Its timm no-QKV-bias
architecture is explicit; this is not the gated HF original. Used tensor values
are preserved exactly as F32 numbers, including promotion of prefix tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from convert_flow import PIXAL_REVISION, digest
from convert_vision import ARCHITECTURE, REFERENCE, tensor_plan, vision_spec

REPOSITORY = 'ilintar/trellis2-gguf'
REVISION = 'a57397bd3d351599d9729fc144b3f87c3f87d65b'
CHECKPOINT_SHA256 = 'b2e84087aebeb06440da4f5970413153f7f27f71ede7bab993e82accd839d936'
CHECKPOINT_BYTES = 606773440
# timm 1.0.22 eva.vit_large_patch16_dinov3 and the pinned trellis.cpp graph.
CONFIG = {
    'model_type': 'dinov3_vit', 'hidden_size': 1024, 'intermediate_size': 4096,
    'num_hidden_layers': 24, 'num_attention_heads': 16, 'patch_size': 16,
    'num_register_tokens': 4, 'query_bias': False, 'key_bias': False,
    'value_bias': False, 'proj_bias': True, 'mlp_bias': True,
    'layer_norm_eps': 1e-5, 'rope_theta': 100., 'use_gated_mlp': False,
}


def convert(checkpoint: Path, output_dir: Path) -> dict[str, Any]:
    checkpoint = checkpoint.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ValueError('output already exists; refusing overwrite')
    if not checkpoint.is_file() or checkpoint.stat().st_size != CHECKPOINT_BYTES:
        raise ValueError('expected the pinned local DINOv3 GGUF')
    if digest(checkpoint) != CHECKPOINT_SHA256:
        raise ValueError('local DINOv3 GGUF digest differs from the pinned source')
    os.environ.update({'HIP_VISIBLE_DEVICES': '-1', 'ROCR_VISIBLE_DEVICES': '-1',
                       'CUDA_VISIBLE_DEVICES': '-1', 'HF_HUB_OFFLINE': '1'})
    import gguf
    import numpy as np
    import torch

    if importlib.metadata.version('gguf') != '0.19.0':
        raise ValueError('use the pinned gguf-lock.txt')
    reader = gguf.GGUFReader(checkpoint)
    if reader.fields['general.architecture'].contents() != 'dinov3-vitl16':
        raise ValueError('unexpected source GGUF architecture')
    original_config = reader.fields['trellis.config_json'].contents()
    config = json.loads(original_config)
    if config['architecture'] != 'vit_large_patch16_dinov3' or config['pretrained_cfg']['tag'] != 'lvd1689m':
        raise ValueError('unexpected source DINOv3 variant')
    spec = vision_spec(CONFIG, 'dino')
    shapes, mapping, _ = tensor_plan('dino', spec)
    expected = {}
    for name, sources in mapping.items():
        parts = [shapes[source] for source in sources]
        expected[name] = parts[0] if len(parts) == 1 else (sum(p[0] for p in parts), *parts[0][1:])
    unused = {'norm.weight': (1024,), 'norm.bias': (1024,)}
    tensors = {tensor.name: tensor for tensor in reader.tensors}
    if len(tensors) != len(reader.tensors) or set(tensors) != set(expected) | set(unused):
        raise ValueError('local DINOv3 tensor table differs')
    for name, shape in (expected | unused).items():
        tensor = tensors[name]
        if tuple(tensor.data.shape) != shape or tensor.tensor_type not in (
            gguf.GGMLQuantizationType.F16, gguf.GGMLQuantizationType.F32,
        ) or not np.isfinite(tensor.data).all():
            raise ValueError('unsupported local DINOv3 tensor: ' + name)
    raw_config = json.dumps(CONFIG, sort_keys=True, separators=(',', ':'))
    source = {'checkpoint_sha256': CHECKPOINT_SHA256,
              'config_sha256': hashlib.sha256(raw_config.encode()).hexdigest(),
              'source_repository': REPOSITORY, 'source_revision': REVISION,
              'source_kind': 'checkpoint', 'input_format': 'trellis-gguf'}
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pixal-local-dino-', dir=output_dir.parent) as temporary:
        directory = Path(temporary) / 'result'
        directory.mkdir()
        result = directory / 'model.gguf'
        writer = gguf.GGUFWriter(result, ARCHITECTURE, use_temp_file=True)
        writer.add_name('Pixal3D DINOv3 from existing trellis.cpp GGUF')
        writer.add_uint32('pixal.schema_version', 1)
        writer.add_string('pixal.vision.kind', 'dino')
        writer.add_string('pixal.storage', 'f16')
        writer.add_string('pixal.reference_revision', PIXAL_REVISION)
        writer.add_string('pixal.vision.reference_revision', REFERENCE['dino'])
        writer.add_string('pixal.vision.config_json', raw_config)
        for name, value in spec.items():
            method = writer.add_bool if type(value) is bool else writer.add_uint32 if type(value) is int else writer.add_float32
            method('pixal.vision.' + name, value)
        for name, value in source.items():
            writer.add_string('pixal.' + name, value)
        records = {}
        try:
            for name in sorted(expected):
                values = tensors[name].data
                half = name.endswith('.weight') and values.ndim in {2, 4}
                converted = values.astype(np.float16 if half else np.float32)
                if not np.array_equal(converted.astype(np.float32), values.astype(np.float32)):
                    raise ValueError('local DINOv3 tensor conversion would lose values: ' + name)
                writer.add_tensor(name, converted)
                records[name] = {'shape': list(converted.shape), 'dtype': str(converted.dtype),
                                 'sha256': hashlib.sha256(converted.tobytes()).hexdigest(),
                                 'source_name': name, 'f32_values_identical': True}
            writer.write_header_to_file()
            writer.write_kv_data_to_file()
            writer.write_tensors_to_file()
        finally:
            writer.close()
            if writer.temp_file is not None:
                writer.temp_file.close()
        if digest(checkpoint) != CHECKPOINT_SHA256:
            raise ValueError('source changed during local import')
        manifest = {
            'schema_version': 1, 'architecture': ARCHITECTURE, 'kind': 'dino',
            'storage': 'f16', 'vision': spec, 'source': source, 'tensors': records,
            'source_config_json': config,
            'source_config_sha256': hashlib.sha256(original_config.encode()).hexdigest(),
            'unused_source_tensors': {name: {
                'reason': 'Pixal applies non-affine final layer normalization',
                'shape': list(tensors[name].data.shape),
                'f32_sha256': hashlib.sha256(tensors[name].data.astype(np.float32).tobytes()).hexdigest(),
            } for name in unused},
            'reference_revision': PIXAL_REVISION, 'converter_sha256': digest(Path(__file__)),
            'packages': {name: importlib.metadata.version(name) for name in ('gguf', 'numpy', 'torch', 'transformers')},
            'output_sha256': digest(result), 'output_bytes': result.stat().st_size,
            'torch_gpu_initialized': torch.cuda.is_initialized(), 'adopted': False,
            'original_hf_checkpoint_acquired': False,
        }
        (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        if output_dir.exists():
            raise ValueError('output appeared during local import')
        directory.rename(output_dir)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = convert(args.checkpoint, args.output_dir)
    print(json.dumps({key: report[key] for key in ('output_sha256', 'output_bytes', 'torch_gpu_initialized')}))


if __name__ == '__main__':
    main()
