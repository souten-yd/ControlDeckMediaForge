"""Pinned MoGe 2 camera inference in the isolated worker, explicitly CPU/F32.

No network loader, backend discovery, GPU fallback or model adoption. The caller
owns the admitted checkpoint, process lifetime and later native GPU admission.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import importlib
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Iterator

MOGE_REVISION = '07444410f1e33f402353b99d6ccd26bd31e469e8'
Cancel = Callable[[], bool]
Progress = Callable[[str, int, int], None]


@dataclass(frozen=True)
class CameraEstimate:
    camera_angle_x: float
    distance: float
    mesh_scale: float
    image_resolution: int
    focal_x_normalized: float
    foreground_pixels: int
    valid_downsampled_pixels: int
    backend: str = 'cpu'
    precision: str = 'float32'
    method: str = 'moge-2'

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_cancel(cancelled: Cancel | None) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError('Pixal camera cancelled')


def contained_file(path: Path, allowed_root: Path) -> Path:
    root = allowed_root.resolve(strict=True)
    result = path.resolve(strict=True)
    if not root.is_dir() or not result.is_relative_to(root) or not result.is_file():
        raise ValueError('camera input escapes the allowed root or is not a file')
    return result


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def moge_model_class(source: Path) -> type:
    """Only import the fixed, unchanged external source; never resolve a repo ID."""
    source = source.resolve(strict=True)
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all', '--', 'moge'])
    if head != MOGE_REVISION or dirty:
        raise ValueError('MoGe source must be pinned and unchanged')
    # An earlier import must not redirect inference to another installed package.
    for name, module in tuple(sys.modules.items()):
        if name == 'moge' or name.startswith('moge.'):
            filename = getattr(module, '__file__', None)
            if filename and not Path(filename).resolve().is_relative_to(source / 'moge'):
                raise ValueError('MoGe module was imported from a different source')
    sys.path.insert(0, str(source))
    try:
        module = importlib.import_module('moge.model.v2')
    finally:
        sys.path.remove(str(source))
    if not Path(module.__file__).resolve().is_relative_to(source / 'moge'):
        raise ValueError('MoGe import provenance mismatch')
    return module.MoGeModel


def _validate_config(config: Any) -> None:
    if not isinstance(config, dict) or set(config) - {'encoder', 'neck', 'points_head', 'mask_head', 'normal_head', 'scale_head', 'remap_output', 'num_tokens_range'}:
        raise ValueError('unsupported MoGe configuration')
    if not all(isinstance(config.get(name), dict) for name in ('encoder', 'neck', 'points_head', 'mask_head')):
        raise ValueError('MoGe camera requires encoder, neck, point and mask heads')
    encoder = config['encoder']
    if set(encoder) != {'backbone', 'intermediate_layers', 'dim_out'} or encoder['backbone'] not in {'dinov2_vits14', 'dinov2_vitb14', 'dinov2_vitl14'}:
        raise ValueError('unsupported MoGe encoder configuration')
    depth = 24 if encoder['backbone'] == 'dinov2_vitl14' else 12
    layers = encoder['intermediate_layers']
    if type(layers) is int:
        valid = 1 <= layers <= depth
    else:
        valid = isinstance(layers, list) and 1 <= len(layers) <= depth and all(type(v) is int and 0 <= v < depth for v in layers) and layers == sorted(set(layers))
    if not valid or type(encoder['dim_out']) is not int or not 16 <= encoder['dim_out'] <= 1024:
        raise ValueError('unsupported MoGe encoder extent')
    tokens = config.get('num_tokens_range', [1200, 3600])
    if not isinstance(tokens, list) or len(tokens) != 2 or any(type(x) is not int or not 4 <= x <= 4096 for x in tokens) or tokens[0] > tokens[1]:
        raise ValueError('invalid MoGe token range')
    if config.get('remap_output', 'linear') not in {'linear', 'sinh', 'exp', 'sinh_exp'}:
        raise ValueError('unsupported MoGe point remapping')
    allowed = {'dim_in', 'dim_res_blocks', 'dim_out', 'resamplers', 'dim_times_res_block_hidden', 'num_res_blocks', 'res_block_in_norm', 'res_block_hidden_norm', 'activation'}
    for name in ('neck', 'points_head', 'mask_head', 'normal_head'):
        stack = config.get(name)
        if stack is None:
            continue
        if not isinstance(stack, dict) or set(stack) - allowed:
            raise ValueError('unsupported MoGe convolution configuration')
        widths = stack.get('dim_res_blocks')
        if not isinstance(widths, list) or len(widths) != 5 or any(type(x) is not int or not 8 <= x <= 1024 for x in widths):
            raise ValueError('invalid MoGe convolution width')
        for key in ('dim_in', 'dim_out'):
            values = stack.get(key)
            values = values if isinstance(values, list) else [values] * 5
            if len(values) != 5 or any(v is not None and (type(v) is not int or not 1 <= v <= 1026) for v in values):
                raise ValueError('invalid MoGe convolution input/output')
        blocks = stack.get('num_res_blocks', 1)
        blocks = blocks if isinstance(blocks, list) else [blocks] * 5
        if len(blocks) != 5 or any(type(x) is not int or not 0 <= x <= 4 for x in blocks):
            raise ValueError('invalid MoGe residual block count')
        resamplers = stack.get('resamplers')
        if not isinstance(resamplers, list) or len(resamplers) != 4 or any(x not in {'pixel_shuffle', 'nearest', 'bilinear', 'conv_transpose'} for x in resamplers):
            raise ValueError('invalid MoGe resampling configuration')
        multiple = stack.get('dim_times_res_block_hidden', 1)
        if type(multiple) is not int or not 1 <= multiple <= 4:
            raise ValueError('invalid MoGe hidden width multiplier')
        for key, default in (('res_block_in_norm', 'layer_norm'), ('res_block_hidden_norm', 'group_norm')):
            if stack.get(key, default) not in {'layer_norm', 'group_norm', 'instance_norm', 'none'}:
                raise ValueError('unsupported MoGe normalization')
        if stack.get('activation', 'relu') not in {'relu', 'leaky_relu', 'silu', 'elu'}:
            raise ValueError('unsupported MoGe activation')
    if config.get('scale_head') is not None:
        scale = config['scale_head']
        dims = scale.get('dims') if isinstance(scale, dict) else None
        if not isinstance(scale, dict) or set(scale) != {'dims'} or not isinstance(dims, list) or not 2 <= len(dims) <= 5 or any(type(x) is not int or not 1 <= x <= 1024 for x in dims):
            raise ValueError('invalid MoGe scale head')


@contextmanager
def local_moge(source: Path, checkpoint: Path, expected_sha256: str, allowed_root: Path,
               *, cancelled: Cancel | None = None) -> Iterator[Any]:
    """Load caller-admitted local tensor/config bytes strictly on CPU.

    Hash checking is integrity checking, not license consent or an adoption
    receipt. Both synthetic and trained artifacts require caller provenance.
    """
    import torch

    check_cancel(cancelled)
    path = contained_file(checkpoint, allowed_root)
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256) or path.stat().st_size > 4 * 1024**3 or file_sha256(path) != expected_sha256:
        raise ValueError('MoGe checkpoint hash or file-size mismatch')
    model_type = moge_model_class(source)
    check_cancel(cancelled)
    loaded = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    if not isinstance(loaded, dict) or set(loaded) != {'model_config', 'model'}:
        raise ValueError('invalid local MoGe checkpoint envelope')
    _validate_config(loaded['model_config'])
    state = loaded['model']
    if not isinstance(state, dict) or not state or any(not isinstance(k, str) or not isinstance(v, torch.Tensor) for k, v in state.items()):
        raise ValueError('invalid MoGe tensor table')
    if sum(v.numel() for v in state.values()) > 800_000_000:
        raise ValueError('MoGe tensor budget exceeded')
    for value in state.values():
        check_cancel(cancelled)
        if value.device.type != 'cpu' or value.layout != torch.strided or value.dtype not in (torch.float32, torch.float16, torch.bfloat16) or not torch.isfinite(value).all():
            raise ValueError('unsupported or non-finite MoGe tensor')
    # Validate the complete architecture/tensor table on metadata-only tensors
    # before allocating CPU model storage. DINO uses pretrained=False.
    from accelerate import init_empty_weights
    # Keep constructor constants on CPU: upstream DINO reads linspace().item().
    # Parameters stay metadata-only until the complete table is validated.
    with init_empty_weights(include_buffers=False):
        model = model_type(**loaded['model_config']).to(dtype=torch.float32)
    expected = model.state_dict()
    if sum(v.numel() for v in expected.values()) > 800_000_000:
        raise ValueError('MoGe architecture tensor budget exceeded')
    if set(expected) != set(state) or any(expected[k].shape != state[k].shape for k in expected):
        raise ValueError('MoGe checkpoint tensor table mismatch')
    check_cancel(cancelled)
    model.to_empty(device='cpu')
    model.load_state_dict(state, strict=True)
    model.eval()
    del loaded, state
    if file_sha256(path) != expected_sha256:
        raise ValueError('MoGe checkpoint changed during loading')
    try:
        check_cancel(cancelled)
        yield model
    finally:
        del model


def infer_camera(model: Any, image: Any, *, mesh_scale: float = 1., extend_pixel: int = 0,
                 image_resolution: int = 512, num_tokens: int | None = None,
                 cancelled: Cancel | None = None, progress: Progress | None = None) -> CameraEstimate:
    """Actual pinned MoGe infer + Pixal camera formula; no fixed-FOV fallback."""
    import numpy as np
    from PIL import Image
    import torch

    check_cancel(cancelled)
    if not isinstance(image, Image.Image) or image.mode != 'RGB' or min(image.size) < 2 or max(image.size) > 2048:
        raise ValueError('MoGe camera requires a framed RGB image of size 2..2048')
    if not math.isfinite(mesh_scale) or mesh_scale <= 0 or type(extend_pixel) is not int or not 0 <= extend_pixel <= 2048 or type(image_resolution) is not int or not 2 <= image_resolution <= 2048:
        raise ValueError('invalid Pixal camera scale, extension or resolution')
    if num_tokens is not None and (type(num_tokens) is not int or not 4 <= num_tokens <= 4096):
        raise ValueError('invalid MoGe camera token count')
    if model.device.type != 'cpu' or model.dtype != torch.float32 or model.training:
        raise ValueError('MoGe camera requires an eval model on CPU in float32')
    for value in (*model.parameters(), *model.buffers()):
        if value.device.type != 'cpu':
            raise ValueError('MoGe camera contains a non-CPU tensor')
    pixels = np.array(image).astype(np.float32) / 255.
    tensor = torch.from_numpy(pixels).permute(2, 0, 1)
    modules = [('encoder', model.encoder), ('neck', model.neck)]
    modules += [(name, getattr(model, name)) for name in ('points_head', 'normal_head', 'mask_head', 'scale_head') if hasattr(model, name)]
    modules += [('encoder_block_' + str(i), block) for i, block in enumerate(model.encoder.backbone.blocks)]
    hooks = []
    def before(name: str) -> Callable[..., None]:
        def hook(_module: Any, _inputs: Any) -> None:
            check_cancel(cancelled)
            if progress:
                progress('camera_' + name, 0, 1)
            check_cancel(cancelled)
        return hook
    try:
        for name, module in modules:
            hooks.append(module.register_forward_pre_hook(before(name)))
        with torch.inference_mode():
            output = model.infer(tensor, num_tokens=num_tokens, resolution_level=9, use_fp16=False)
    finally:
        for hook in hooks:
            hook.remove()
    check_cancel(cancelled)
    intrinsics = output.get('intrinsics')
    mask = output.get('mask')
    if not isinstance(intrinsics, torch.Tensor) or intrinsics.device.type != 'cpu' or intrinsics.shape != (3, 3) or not torch.isfinite(intrinsics).all():
        raise ValueError('MoGe camera produced invalid intrinsics')
    if not isinstance(mask, torch.Tensor) or mask.device.type != 'cpu' or mask.dtype != torch.bool or mask.shape != (image.height, image.width):
        raise ValueError('MoGe camera produced invalid foreground mask')
    valid_pixels = int(mask.sum())
    fit_pixels = int(torch.nn.functional.interpolate(mask[None,None].float(), (64,64), mode='nearest').sum())
    if valid_pixels < 2 or fit_pixels < 2:
        raise ValueError('MoGe camera has insufficient valid foreground')
    matrix = intrinsics.float().detach().numpy()
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0 or not np.array_equal(matrix[[0,1,2,2,2],[1,0,0,1,2]], np.array([0,0,0,0,1], np.float32)) or not np.allclose(matrix[:2,2], .5, atol=1e-6, rtol=0):
        raise ValueError('MoGe camera produced unsupported intrinsics')
    # Preserve the upstream numpy-F32 and Torch-F32 steps, including rounding.
    fx_normalized = matrix[0, 0]
    fx = fx_normalized * image.width
    angle = 2 * math.atan(image.width / (2 * fx))
    f_pixels = float((16. / torch.tan(torch.tensor(angle / 2.)) * image_resolution / 32.).item())
    xw = float((torch.tensor(-1., dtype=torch.float32) / mesh_scale / 2).item())
    distance = f_pixels * xw / (-extend_pixel - image_resolution / 2.)
    if not math.isfinite(angle) or not 0 < angle < math.pi or not math.isfinite(distance) or distance <= 0:
        raise ValueError('MoGe camera produced invalid FOV or distance')
    check_cancel(cancelled)
    if progress:
        progress('camera_complete', 1, 1)
    check_cancel(cancelled)
    return CameraEstimate(angle, distance, mesh_scale, image_resolution, float(fx_normalized), valid_pixels, fit_pixels)
