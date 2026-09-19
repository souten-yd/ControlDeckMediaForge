#!/usr/bin/env python3
"""Private CPU image/camera preprocessing entry; no GPU or runtime adoption.

Opaque inputs need a separately admitted background provider. This entry accepts
transparent inputs, preserving upstream framing. It publishes a manifest only
after local MoGe inference and all arrays complete. The parent owns timeout,
termination/reaping and cleanup after forced process death.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import signal
from typing import Any, Callable

from camera import MOGE_REVISION, check_cancel, contained_file, file_sha256, infer_camera, local_moge
from prepare_image import frame_foreground, prepare_rgb


def prepare_camera_input(*, source: Path, checkpoint: Path, checkpoint_sha256: str,
                         allowed_root: Path, image_path: Path, output_dir: Path,
                         source_kind: str, low_size: int = 512, high_size: int = 1024,
                         num_tokens: int | None = None, mesh_scale: float = 1.,
                         extend_pixel: int = 0, image_resolution: int = 512,
                         cancelled: Callable[[], bool] | None = None,
                         progress: Callable[[str, int, int], None] | None = None,
                         remove_background: Callable[[Any], Any] | None = None) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    check_cancel(cancelled)
    if source_kind not in {'synthetic', 'checkpoint'}:
        raise ValueError('explicit camera source_kind is required')
    root = allowed_root.resolve(strict=True)
    image_path = contained_file(image_path, root)
    output = output_dir.absolute()
    parent = output.parent.resolve(strict=True)
    if not parent.is_relative_to(root) or output.name in {'', '.', '..'}:
        raise ValueError('camera output escapes the allowed root')
    # Always anchor output creation to the checked real parent.
    output = parent / output.name
    input_hash = file_sha256(image_path)
    with Image.open(image_path) as image:
        if min(image.size) < 2 or max(image.size) > 8192 or image.width * image.height > 32_000_000:
            raise ValueError('camera source image exceeds extent bound')
        image.load()
        frame = frame_foreground(image, remove_background=remove_background)
    check_cancel(cancelled)
    if file_sha256(image_path) != input_hash:
        raise ValueError('camera source image changed during decoding')
    low, high = prepare_rgb(frame.image, low_size), prepare_rgb(frame.image, high_size)
    output.mkdir(mode=0o700)  # Existing outputs are never replaced or removed.
    try:
        if progress:
            progress('camera_load', 0, 1)
        def estimate() -> Any:
            with local_moge(source, checkpoint, checkpoint_sha256, root, cancelled=cancelled) as model:
                return infer_camera(model, frame.image, num_tokens=num_tokens, mesh_scale=mesh_scale,
                                    extend_pixel=extend_pixel, image_resolution=image_resolution,
                                    cancelled=cancelled, progress=progress)
        camera = estimate()
        gc.collect()  # No model/point-map references survive into native generation.
        check_cancel(cancelled)
        frame.image.save(output / 'framed.png')
        np.save(output / 'rgb_low.npy', low)
        np.save(output / 'rgb_high.npy', high)
        np.save(output / 'camera.npy', np.array([camera.camera_angle_x, camera.distance, camera.mesh_scale], np.float32))
        manifest = {'schema_version': 1, 'kind': 'pixal-camera-input', 'source_kind': source_kind,
                    'input_sha256': input_hash, 'checkpoint_sha256': checkpoint_sha256,
                    'moge_source_revision': MOGE_REVISION, 'camera': camera.as_dict(),
                    'num_tokens': num_tokens, 'resolution_level': 9, 'extend_pixel': extend_pixel,
                    'framing': {'original_size': frame.original_size, 'resized_size': frame.resized_size,
                                'used_input_alpha': frame.used_input_alpha, 'crop_box': frame.crop_box},
                    'low_size': low_size, 'high_size': high_size,
                    'files': {name: file_sha256(output / name) for name in ('framed.png', 'rgb_low.npy', 'rgb_high.npy', 'camera.npy')}}
        check_cancel(cancelled)
        staged = output / 'manifest.partial'
        staged.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        check_cancel(cancelled)
        staged.replace(output / 'manifest.json')
        # No cancellable callback after manifest publication.
        return manifest
    except BaseException:
        shutil.rmtree(output)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'checkpoint', 'allowed-root', 'input', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--source-kind', choices=('synthetic', 'checkpoint'), required=True)
    parser.add_argument('--low-size', type=int, default=512)
    parser.add_argument('--high-size', type=int, default=1024)
    parser.add_argument('--num-tokens', type=int)
    parser.add_argument('--mesh-scale', type=float, default=1.)
    parser.add_argument('--extend-pixel', type=int, default=0)
    parser.add_argument('--image-resolution', type=int, default=512)
    args = parser.parse_args()
    # This process explicitly owns CPU preprocessing, irrespective of whether
    # the installed Torch wheel also supports GPUs.
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1')
    import torch
    torch.set_num_threads(2)
    stop = False
    def request_stop(_signal: int, _frame: Any) -> None:
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    def progress(stage: str, done: int, total: int) -> None:
        print(json.dumps({'stage': stage, 'done': done, 'total': total}), flush=True)
    try:
        result = prepare_camera_input(source=args.source, checkpoint=args.checkpoint,
                                      checkpoint_sha256=args.checkpoint_sha256, allowed_root=args.allowed_root,
                                      image_path=args.input, output_dir=args.output_dir, source_kind=args.source_kind,
                                      low_size=args.low_size, high_size=args.high_size, num_tokens=args.num_tokens,
                                      mesh_scale=args.mesh_scale, extend_pixel=args.extend_pixel,
                                      image_resolution=args.image_resolution, cancelled=lambda: stop, progress=progress)
        print(json.dumps({'completed': True, 'camera': result['camera']}), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({'completed': False, 'error': str(error)}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
