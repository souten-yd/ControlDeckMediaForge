#!/usr/bin/env python3
"""CPU comparison of the authorized local trellis DINO GGUF with timm.

Uses all trained layers at 512 or 1024 square. The reference loads every original
tensor strictly, then applies Pixal's non-affine final normalization. This is
not a comparison against the unavailable original HF precision checkpoint.
"""
from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import time

from convert_flow import digest
from import_trellis_dino import CHECKPOINT_SHA256, REPOSITORY, REVISION


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint', 'converted', 'rgb', 'binary', 'output-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--image-size', type=int, choices=(512, 1024), default=512)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('use a fresh output directory')
    if digest(args.checkpoint) != CHECKPOINT_SHA256:
        parser.error('use the pinned authorized local checkpoint')
    manifest = json.loads((args.converted.parent / 'manifest.json').read_text())
    if (digest(args.converted) != manifest['output_sha256'] or
        manifest['source']['checkpoint_sha256'] != CHECKPOINT_SHA256 or
        manifest['source']['input_format'] != 'trellis-gguf'):
        parser.error('converted checkpoint provenance differs')
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1',
                      CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1')
    import gguf
    import numpy as np
    import torch
    import timm
    from accelerate import init_empty_weights
    from timm.models import eva
    if importlib.metadata.version('timm') != '1.0.22':
        raise ValueError('use timm 1.0.22 reference')
    torch.set_num_threads(2)
    rgb = np.load(args.rgb, allow_pickle=False)
    size = args.image_size
    if rgb.shape != (3, size, size) or rgb.dtype != np.float32 or not np.isfinite(rgb).all():
        raise ValueError('expected finite CHW float32 RGB at the selected size')
    args.output_dir.mkdir(parents=True)
    source = gguf.GGUFReader(args.checkpoint)
    converted = gguf.GGUFReader(args.converted)
    original = {t.name: t.data for t in source.tensors}
    if any(not np.array_equal(t.data.astype(np.float32), original[t.name].astype(np.float32))
           for t in converted.tensors):
        raise ValueError('converted values differ from original tensors')
    started = time.monotonic()
    with init_empty_weights(include_buffers=False):
        model = timm.create_model('vit_large_patch16_dinov3', pretrained=False, num_classes=0, img_size=size)
    # assign avoids allocating a second complete copy; mmap source is read only.
    state = {name: torch.from_numpy(values.astype(np.float32)) for name, values in original.items()}
    model.load_state_dict(state, strict=True, assign=True)
    model.norm = torch.nn.LayerNorm(1024, eps=1e-5, elementwise_affine=False)
    model.eval()
    with torch.inference_mode():
        image = torch.from_numpy(rgb)[None]
        normalized = (image - torch.tensor([.485, .456, .406])[None, :, None, None]) / torch.tensor([.229, .224, .225])[None, :, None, None]
        tokens = model.forward_features(normalized)[0].numpy().copy()
    reference_seconds = time.monotonic() - started
    expected = {'global': tokens[:5], 'patches': tokens[5:].reshape(size // 16, size // 16, 1024)}
    del model, state, source, converted, original
    gc.collect()
    for name, value in expected.items():
        np.save(args.output_dir / ('expected_' + name + '.npy'), value)
    native_dir = args.output_dir / 'native'
    started = time.monotonic()
    native = subprocess.run([str(args.binary.resolve()), str(args.converted.resolve()), str(args.rgb.resolve()), str(native_dir.resolve())],
                            capture_output=True, text=True, timeout=1200)
    native_seconds = time.monotonic() - started
    (args.output_dir / 'native.log').write_text(native.stdout + native.stderr)
    comparisons = {}
    if native.returncode == 0:
        for name, value in expected.items():
            actual = np.load(native_dir / (name + '.npy'), allow_pickle=False)
            same_shape = actual.shape == value.shape
            finite = bool(np.isfinite(actual).all())
            delta = actual - value if same_shape else np.array([np.inf])
            cosine = float(np.dot(actual.ravel(), value.ravel()) / (np.linalg.norm(actual) * np.linalg.norm(value))) if same_shape and finite else 0.
            comparisons[name] = {'shape': list(actual.shape), 'max_abs_error': float(np.abs(delta).max()),
                                 'rms_error': float(np.sqrt(np.mean(delta ** 2))), 'cosine': cosine,
                                 'passed': same_shape and finite and bool(np.allclose(actual, value, atol=1e-3, rtol=1e-3)) and cosine > .99999}
    report = {'passed': native.returncode == 0 and len(comparisons) == 2 and all(c['passed'] for c in comparisons.values()),
              'backend': 'cpu', 'arithmetic': 'float32', 'source_repository': REPOSITORY, 'source_revision': REVISION,
              'source_sha256': CHECKPOINT_SHA256, 'converted_sha256': digest(args.converted),
              'rgb_sha256': digest(args.rgb), 'binary_sha256': digest(args.binary),
              'reference_source_sha256': digest(Path(eva.__file__)), 'reference_package': 'timm 1.0.22',
              'image_size': size, 'layers': 24, 'channels': 1024, 'used_values_identical': True,
              'final_normalization': 'Pixal non-affine layer norm, epsilon 1e-5',
              'reference_seconds': reference_seconds, 'native_seconds': native_seconds,
              'native_returncode': native.returncode, 'comparisons': comparisons,
              'atol': 1e-3, 'rtol': 1e-3, 'torch_gpu_initialized': torch.cuda.is_initialized(),
              'original_hf_checkpoint_acquired': False, 'full_generation_tested': False, 'adopted': False}
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
