#!/usr/bin/env python3
"""Full BiRefNet CPU -> MoGe -> native GLB acceptance with synthetic tensors."""
from __future__ import annotations

import argparse
import ast
import gc
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
from types import SimpleNamespace
from typing import Any

from background import BackgroundSpec, BIREFNET_REVISION, empty_birefnet, infer_background, local_birefnet
from camera import file_sha256
from convert_flow import PIXAL_REVISION
from prepare_camera import prepare_camera_input


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'pixal-source', 'moge-source', 'camera-fixtures', 'pipeline-fixtures',
                 'binary', 'core-python', 'blender', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True)  # Never replace an earlier report.
    os.environ.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1', HF_HUB_OFFLINE='1')
    import numpy as np
    import torch
    from PIL import Image
    from safetensors.torch import save_file
    from torchvision import transforms

    torch.set_num_threads(2)
    torch.manual_seed(919)
    assert subprocess.check_output(['git', '-C', str(args.pixal_source), 'rev-parse', 'HEAD'], text=True).strip() == PIXAL_REVISION
    previous = json.loads((args.camera_fixtures / 'report.json').read_text())
    assert previous['passed'] and previous['pretrained_weights'] == 'NOT USED'
    checkpoint = root / 'birefnet-synthetic.safetensors'
    meta = empty_birefnet(args.source)
    parameters = sum(v.numel() for v in meta.parameters())
    assert parameters == 220176498 and meta.config.bb == 'swin_v1_l'
    state = {}
    for key, template in meta.state_dict().items():
        if not template.is_floating_point():
            value = template.clone()
        elif template.ndim >= 2:
            value = torch.randn(template.shape) * .002
        elif key.endswith('weight') or key.endswith('running_var'):
            value = torch.ones(template.shape)
        else:
            value = torch.zeros(template.shape)
        state[key] = value.half() if value.is_floating_point() else value
    # Synthetic calibration of the actual input-skip convolutions. All Swin-L,
    # dual-scale encoders and deformable decoder layers still execute. This is
    # an artificial red foreground mask, never trained segmentation quality.
    state['decoder.ipt_blk1.conv1.weight'].zero_()
    state['decoder.ipt_blk1.conv1.weight'][0, 0, 1, 1] = 1
    state['decoder.ipt_blk1.conv_out.weight'].zero_()
    state['decoder.ipt_blk1.conv_out.weight'][0, 0, 1, 1] = 1
    state['decoder.conv_out1.0.weight'][0, 192, 0, 0] = 3
    save_file(state, checkpoint, metadata={'source_kind': 'synthetic', 'fixture': 'full-swin-l-red-input-skip'})
    del state, meta
    gc.collect()
    spec = BackgroundSpec(args.source, checkpoint, file_sha256(checkpoint), 'synthetic')
    print(json.dumps({'stage': 'checkpoint_ready', 'bytes': checkpoint.stat().st_size, 'parameters': parameters}), flush=True)
    pixels = np.zeros((48, 64, 3), np.uint8)
    pixels[:, :, 2] = 100
    pixels[8:40, 12:52, 0] = 220
    pixels[:, :, 1] = np.arange(64, dtype=np.uint8)[None, :] * 3
    image = Image.fromarray(pixels)
    source_image = root / 'opaque.png'
    image.save(source_image)
    negatives = []

    def rejected(name: str, call: Any, message: str) -> None:
        try:
            call()
        except (ValueError, RuntimeError, InterruptedError, FileNotFoundError, FileExistsError) as error:
            assert message in str(error), (name, str(error))
            negatives.append({'case': name, 'error': str(error)})
        else:
            raise AssertionError(name + ' accepted')

    with local_birefnet(spec, root) as model:
        events = []
        start = time.monotonic()
        masked = infer_background(model, image, progress=lambda *event: events.append(event))
        inference_seconds = time.monotonic() - start
        assert image.mode == 'RGB' and np.array_equal(pixels, np.asarray(image))
        masked.save(root / 'masked.png')
        alpha = np.asarray(masked)[:, :, 3]
        assert alpha.min() < 50 and alpha.max() > 204 and np.unique(alpha).size > 2
        assert sum(e[0] == 'background_encoder_layer_2_block_17' for e in events) == 2
        assert any(e[0] == 'background_decoder_conv_out1' for e in events)
        print(json.dumps({'stage': 'full_forward_done', 'seconds': inference_seconds}), flush=True)
        upstream = args.pixal_source / 'pixal3d/pipelines/rembg/BiRefNet.py'
        tree = ast.parse(upstream.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BiRefNet')
        init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
        transform = next(n for n in init.body if isinstance(n, ast.Assign)
                         and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == 'transform_image')
        call = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__call__')
        # The only inference-body adaptation is explicit CPU device selection.
        changed = 0
        for node in ast.walk(call):
            if isinstance(node, ast.Constant) and node.value == 'cuda':
                node.value = 'cpu'
                changed += 1
        assert changed == 1
        proxy = SimpleNamespace(model=model)
        scope = {'torch': torch, 'transforms': transforms, 'Image': Image, 'self': proxy}
        exec(compile(ast.Module(body=[transform, call], type_ignores=[]), str(upstream), 'exec'), scope)
        reference_start = time.monotonic()
        reference = scope['__call__'](proxy, image.copy())
        reference_seconds = time.monotonic() - reference_start
        assert np.array_equal(np.asarray(reference), np.asarray(masked))
        rejected('cancel_before', lambda: infer_background(model, image, cancelled=lambda: True), 'cancelled')
        rejected('rgba_input', lambda: infer_background(model, masked), 'resized RGB')
        rejected('too_large', lambda: infer_background(model, image.resize((1025, 2))), 'resized RGB')
        model.train()
        rejected('training', lambda: infer_background(model, image), 'eval CPU')
        model.eval()
        stop = [False]
        def cancel_stage(name: str, _done: int, _total: int) -> None:
            if name == 'background_encoder_layer_0_block_0':
                stop[0] = True
        rejected('encoder_cancel', lambda: infer_background(model, image, cancelled=lambda: stop[0], progress=cancel_stage), 'cancelled')
        assert not any(m._forward_pre_hooks for m in model.modules())
        forward = model.forward
        for label, output in [('empty', []), ('wrong_extent', [torch.zeros(1, 1, 4, 4)]),
                              ('nonfinite', [torch.full((1, 1, 1024, 1024), float('nan'))])]:
            model.forward = lambda _tensor, output=output: output
            rejected(label, lambda: infer_background(model, image), 'produced invalid')
        model.forward = forward
    del model, proxy, scope, reference
    gc.collect()
    wrong_hash = BackgroundSpec(args.source, checkpoint, '0' * 64, 'synthetic')
    def load(specification: BackgroundSpec, allowed: Path = root) -> None:
        with local_birefnet(specification, allowed):
            pass
    rejected('hash', lambda: load(wrong_hash), 'hash')
    rejected('scope', lambda: load(spec, root / 'missing'), 'No such file')
    short = root / 'short.safetensors'
    save_file({'bb.patch_embed.proj.weight': torch.zeros(1)}, short)
    rejected('tensor_table', lambda: load(BackgroundSpec(args.source, short, file_sha256(short), 'synthetic')), 'tensor table')
    short.unlink()
    # A same-sized integer dtype substitution reaches value/type validation
    # after the full tensor-name/shape table has passed.
    bad = root / 'integer.safetensors'
    shutil.copyfile(checkpoint, bad)
    with bad.open('r+b') as stream:
        length = struct.unpack('<Q', stream.read(8))[0]
        header = stream.read(length)
        modified = header.replace(b'"dtype":"F16"', b'"dtype":"I16"', 1)
        assert modified != header
        stream.seek(8)
        stream.write(modified)
    rejected('integer_parameter', lambda: load(BackgroundSpec(args.source, bad, file_sha256(bad), 'synthetic')), 'unsupported')
    bad.unlink()
    changed_source = root / 'changed-source'
    changed_source.mkdir()
    for filename in ('birefnet.py', 'BiRefNet_config.py', 'config.json'):
        shutil.copy2(args.source / filename, changed_source / filename)
    with (changed_source / 'birefnet.py').open('a') as stream:
        stream.write('\n# changed\n')
    rejected('changed_source', lambda: load(BackgroundSpec(changed_source, checkpoint, spec.checkpoint_sha256, 'synthetic')), 'source hash')
    shutil.rmtree(changed_source)
    # A real isolated process must release background weights before camera
    # estimation and before the native generator starts.
    camera_checkpoint = args.camera_fixtures / 'moge-synthetic.pt'
    assert file_sha256(camera_checkpoint) == previous['checkpoint_sha256']
    allowed = Path(os.path.commonpath([str(root), str(camera_checkpoint.resolve())]))
    prepared = root / 'prepared'
    command = [sys.executable, str(Path(__file__).with_name('prepare_camera.py')),
        '--source', str(args.moge_source), '--checkpoint', str(camera_checkpoint),
        '--checkpoint-sha256', previous['checkpoint_sha256'], '--allowed-root', str(allowed),
        '--input', str(source_image), '--output-dir', str(prepared), '--source-kind', 'synthetic',
        '--low-size', '12', '--high-size', '16', '--background-source', str(args.source),
        '--background-checkpoint', str(checkpoint), '--background-checkpoint-sha256', spec.checkpoint_sha256,
        '--background-source-kind', 'synthetic']
    start = time.monotonic()
    child = subprocess.run(command, capture_output=True, text=True, timeout=600)
    (root / 'prepare.log').write_text(child.stdout + child.stderr)
    assert child.returncode == 0, child.stdout + child.stderr
    prepare_seconds = time.monotonic() - start
    manifest = json.loads((prepared / 'manifest.json').read_text())
    assert manifest['background'] == spec.descriptor() and not manifest['framing']['used_input_alpha']
    assert all(file_sha256(prepared / k) == v for k, v in manifest['files'].items())
    print(json.dumps({'stage': 'opaque_prepare_done', 'seconds': prepare_seconds}), flush=True)
    kwargs = dict(source=args.moge_source, checkpoint=camera_checkpoint,
        checkpoint_sha256=previous['checkpoint_sha256'], allowed_root=allowed,
        source_kind='synthetic', low_size=12, high_size=16)
    transparent = args.camera_fixtures / 'input.png'
    skipped = prepare_camera_input(**kwargs, image_path=transparent, output_dir=root / 'alpha-skip', background_spec=wrong_hash)
    assert skipped['background'] == {'method': 'input-alpha', 'provider_used': False}
    for name in ('framed.png', 'rgb_low.npy', 'rgb_high.npy', 'camera.npy'):
        assert (root / 'alpha-skip' / name).read_bytes() == (args.camera_fixtures / 'prepared' / name).read_bytes()
    rejected('opaque_no_provider', lambda: prepare_camera_input(**kwargs, image_path=source_image, output_dir=root / 'no-provider'), 'requires an explicit')
    rejected('two_providers', lambda: prepare_camera_input(**kwargs, image_path=source_image, output_dir=root / 'two-providers',
        background_spec=spec, remove_background=lambda image: image), 'only one')
    original_manifest_sha = file_sha256(prepared / 'manifest.json')
    rejected('existing_output', lambda: prepare_camera_input(**kwargs, image_path=source_image, output_dir=prepared, background_spec=spec), str(prepared))
    assert file_sha256(prepared / 'manifest.json') == original_manifest_sha
    partial = subprocess.run(command[:-2], capture_output=True, text=True, timeout=30)
    assert partial.returncode == 2 and 'all four background' in partial.stderr
    negatives.append({'case': 'partial_cli_provider', 'exit': partial.returncode})
    stopped = root / 'cancelled'
    terminate_command = [str(stopped) if s == str(prepared) else s for s in command]
    process = subprocess.Popen(terminate_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    buffer = bytearray()
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 60
            observed = False
            while time.monotonic() < deadline and process.poll() is None:
                for key, _ in selector.select(.1):
                    buffer.extend(os.read(key.fileobj.fileno(), 8192))
                    if b'background_encoder_layer_0_block_0' in buffer:
                        observed = True
                        break
                if observed:
                    break
        assert observed, 'background encoder not observed'
        start = time.monotonic()
        process.send_signal(signal.SIGTERM)
        tail, _ = process.communicate(timeout=15)
        buffer.extend(tail)
        reap_seconds = time.monotonic() - start
        assert process.returncode == 1 and not stopped.exists()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        (root / 'termination.log').write_bytes(buffer)
    # Reuse exactly the verified native models; opaque framing/camera are the
    # new inputs. Bind the complete preprocessing manifest into GLB provenance.
    pipeline = json.loads((args.pipeline_fixtures / 'report.json').read_text())
    saved = json.loads((args.pipeline_fixtures / 'cascade1024.command.json').read_text())['argv']
    models = {name: Path(saved[saved.index('--' + name) + 1]) for name in pipeline['models']}
    assert all(file_sha256(path) == pipeline['models'][name] for name, path in models.items())
    source_manifest = root / 'source-manifest.json'
    source_manifest.write_text(json.dumps({'native_models': pipeline['models'], 'camera_model': previous['checkpoint_sha256'],
        'background': spec.descriptor()}, sort_keys=True, indent=2) + '\n')
    for name in ('settings.npy', 'samplers.npy', 'shape_norm.npy', 'texture_norm.npy'):
        shutil.copy2(args.pipeline_fixtures / 'cascade1024-input' / name, prepared / name)
    input_manifest = prepared / 'native-input-manifest.json'
    input_manifest.write_text(json.dumps({name: file_sha256(prepared / name) for name in
        ('manifest.json', 'settings.npy', 'samplers.npy', 'shape_norm.npy', 'texture_norm.npy')}, sort_keys=True) + '\n')
    target = root / 'connected'
    native_command = [str(args.binary), str(prepared), str(target), 'cpu',
        *[s for name, path in models.items() for s in ('--' + name, str(path))],
        '--source-sha', file_sha256(source_manifest), '--input-sha', file_sha256(input_manifest), '--native-noise', '--diagnostics']
    start = time.monotonic()
    native = subprocess.run(native_command, capture_output=True, text=True, timeout=120)
    (root / 'native.log').write_text(native.stdout + native.stderr)
    assert native.returncode == 0, native.stderr
    native_seconds = time.monotonic() - start
    outputs = root / 'outputs.json'
    outputs.write_text(json.dumps([str(target / 'asset.glb')]) + '\n')
    code = 'import json,sys; from pathlib import Path; from mediaforge.glb import validate_glb; print(json.dumps({p:validate_glb(Path(p).read_bytes()) for p in json.loads(Path(sys.argv[1]).read_text())}))'
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / 'backend'))
    result = subprocess.run([str(args.core_python), '-c', code, str(outputs)], env=env, capture_output=True, text=True, timeout=120)
    (root / 'core.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(args.blender), '--background', '--factory-startup', '--threads', '4', '--python',
        str(Path(__file__).with_name('check_surface_blender.py')), '--', str(outputs), str(root / 'blender-report.json')],
        capture_output=True, text=True, timeout=120)
    (root / 'blender.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    report = {'passed': True, 'full_parameters': parameters, 'input_size': 1024,
        'checkpoint_sha256': spec.checkpoint_sha256, 'checkpoint_bytes': checkpoint.stat().st_size,
        'source_revision': BIREFNET_REVISION, 'reference_sha256': file_sha256(upstream),
        'reference_cpu_device_substitutions': changed, 'reference_mask_byte_identical': True,
        'alpha_min_max': [int(alpha.min()), int(alpha.max())], 'alpha_distinct': int(np.unique(alpha).size),
        'inference_seconds': inference_seconds, 'reference_seconds': reference_seconds,
        'prepare_seconds': prepare_seconds, 'native_seconds': native_seconds,
        'alpha_skip_previous_arrays_identical': True, 'negative_cases': negatives, 'neural_stages': events,
        'termination': {'exit': process.returncode, 'seconds_to_reap': reap_seconds, 'output_retained': False},
        'connected': json.loads((target / 'report.json').read_text()),
        'blender': json.loads((root / 'blender-report.json').read_text()),
        'torch_gpu_initialized': torch.cuda.is_initialized(), 'pretrained_weights': 'NOT USED',
        'fixture': 'full Swin-L 220176498 parameters, synthetic F16 storage/F32 inference, calibrated input skip',
        'not_tested': ['trained segmentation/camera/3D quality', 'official distributed checkpoint tensor table',
                       'Host lease and Vulkan', 'production worker/adoption/installed', 'new Library asset']}
    assert not report['torch_gpu_initialized']
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'negative_cases': len(negatives), 'full_parameters': parameters,
        'inference_seconds': inference_seconds, 'prepare_seconds': prepare_seconds}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
