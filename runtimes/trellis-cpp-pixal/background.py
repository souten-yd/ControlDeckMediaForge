"""Pinned full BiRefNet background removal, explicitly CPU/F32.

The caller owns checkpoint consent/adoption. Hashes prove integrity, not model
adoption. No network loader, Lite substitution, GPU use or automatic fallback.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any, Iterator

from camera import Cancel, Progress, contained_file, file_sha256

BIREFNET_REVISION = 'e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4'
SOURCE_HASHES = {
    'BiRefNet_config.py': 'e7b8c2a74f6cea6a59553d517f71d47f2c1d90e670a13416af17c25fe2f3dc52',
    'birefnet.py': '208771ae626f653d64128fbf2d6ac9f8e645c5cc5e286258a73ec3322bbfe5ef',
    'config.json': 'c97ea21569daf66b205491a4635147dd3bc42c7c168b89d7d75b53f67ef548ae',
}
INPUT_SIZE = 1024


def check_cancel(cancelled: Cancel | None) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError('Pixal background cancelled')


@dataclass(frozen=True)
class BackgroundSpec:
    source: Path
    checkpoint: Path
    checkpoint_sha256: str
    source_kind: str

    def __post_init__(self) -> None:
        if self.source_kind not in {'synthetic', 'checkpoint'}:
            raise ValueError('explicit background source_kind is required')
        if not re.fullmatch(r'[0-9a-f]{64}', self.checkpoint_sha256):
            raise ValueError('invalid background checkpoint hash')

    def descriptor(self) -> dict[str, Any]:
        return {'method': 'birefnet', 'variant': 'full-swin-l', 'provider_used': True,
                'source_revision': BIREFNET_REVISION, 'source_kind': self.source_kind,
                'checkpoint_sha256': self.checkpoint_sha256, 'backend': 'cpu',
                'precision': 'float32', 'input_size': INPUT_SIZE}


def birefnet_model_class(source: Path) -> type:
    """Execute only the verified local source bytes, never cached bytecode."""
    import hashlib

    root = source.resolve(strict=True)
    contents = {}
    for filename, expected in SOURCE_HASHES.items():
        path = contained_file(root / filename, root)
        value = path.read_bytes()
        if hashlib.sha256(value).hexdigest() != expected:
            raise ValueError('BiRefNet source hash mismatch: ' + filename)
        contents[filename] = value
    name = '_mediaforge_pixal_birefnet_' + BIREFNET_REVISION
    if name in sys.modules:
        module = sys.modules.get(name + '.birefnet')
        package = sys.modules[name]
        if getattr(package, '__path__', None) != [str(root)] or module is None:
            raise ValueError('BiRefNet module was imported from a different source')
        return module.BiRefNet
    package = ModuleType(name)
    package.__path__ = [str(root)]
    sys.modules[name] = package
    try:
        for filename in ('BiRefNet_config.py', 'birefnet.py'):
            fullname = name + '.' + filename[:-3]
            module = ModuleType(fullname)
            module.__file__ = str(root / filename)
            module.__package__ = name
            sys.modules[fullname] = module
            exec(compile(contents[filename], module.__file__, 'exec'), module.__dict__)
        return module.BiRefNet
    except BaseException:
        for key in (name, name + '.BiRefNet_config', name + '.birefnet'):
            sys.modules.pop(key, None)
        raise


def empty_birefnet(source: Path) -> Any:
    """Full upstream architecture, metadata parameters and real CPU constants."""
    from accelerate import init_empty_weights
    import torch

    model_type = birefnet_model_class(source)
    with init_empty_weights(include_buffers=False):
        model = model_type(config=model_type.config_class(bb_pretrained=False)).to(dtype=torch.float32)
    return model.eval()


@contextmanager
def local_birefnet(spec: BackgroundSpec, allowed_root: Path, *,
                   cancelled: Cancel | None = None) -> Iterator[Any]:
    """Validate a complete local safetensors checkpoint before CPU allocation."""
    from safetensors import safe_open
    import torch

    check_cancel(cancelled)
    checkpoint = contained_file(spec.checkpoint, allowed_root)
    if not 1 <= checkpoint.stat().st_size <= 2 * 1024**3 or file_sha256(checkpoint) != spec.checkpoint_sha256:
        raise ValueError('BiRefNet checkpoint hash or file-size mismatch')
    model = empty_birefnet(spec.source)
    expected = model.state_dict()
    if sum(v.numel() for v in expected.values()) > 230_000_000:
        raise ValueError('BiRefNet architecture tensor budget exceeded')
    with safe_open(checkpoint, framework='pt', device='cpu') as incoming:
        if set(incoming.keys()) != set(expected) or any(
            tuple(incoming.get_slice(k).get_shape()) != tuple(v.shape) for k, v in expected.items()
        ):
            raise ValueError('BiRefNet checkpoint tensor table mismatch')
        state = {}
        for key, template in expected.items():
            check_cancel(cancelled)
            value = incoming.get_tensor(key)
            if template.is_floating_point():
                if value.dtype not in (torch.float16, torch.float32, torch.bfloat16) or not torch.isfinite(value).all():
                    raise ValueError('unsupported or non-finite BiRefNet tensor: ' + key)
            elif value.dtype != template.dtype:
                raise ValueError('BiRefNet integer tensor type mismatch: ' + key)
            elif key.endswith('relative_position_index') and not torch.equal(template, value):
                raise ValueError('BiRefNet position index mismatch: ' + key)
            elif key.endswith('num_batches_tracked') and bool((value < 0).any()):
                raise ValueError('invalid BiRefNet batch counter: ' + key)
            state[key] = value
        check_cancel(cancelled)
        model.to_empty(device='cpu')
        model.load_state_dict(state, strict=True)
        del state, expected
    model.eval()
    if file_sha256(checkpoint) != spec.checkpoint_sha256:
        raise ValueError('BiRefNet checkpoint changed during loading')
    try:
        check_cancel(cancelled)
        yield model
    finally:
        del model


def infer_background(model: Any, image: Any, *, cancelled: Cancel | None = None,
                     progress: Progress | None = None) -> Any:
    """Pixal's exact PIL/torchvision transform, sigmoid and uint8 mask path."""
    from PIL import Image
    import torch
    from torchvision import transforms

    check_cancel(cancelled)
    if not isinstance(image, Image.Image) or image.mode != 'RGB' or min(image.size) < 1 or max(image.size) > 1024:
        raise ValueError('BiRefNet requires resized RGB input of size 1..1024')
    if model.training:
        raise ValueError('BiRefNet requires an eval CPU float32 model')
    for value in (*model.parameters(), *model.buffers()):
        if value.device.type != 'cpu' or (value.is_floating_point() and value.dtype != torch.float32):
            raise ValueError('BiRefNet requires an eval CPU float32 model')
    transform = transforms.Compose([
        transforms.Resize((INPUT_SIZE, INPUT_SIZE)), transforms.ToTensor(),
        transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
    ])
    tensor = transform(image).unsqueeze(0)
    modules = [('encoder', model.bb), ('squeeze', model.squeeze_module), ('decoder', model.decoder)]
    modules += [(f'encoder_layer_{i}_block_{j}', block)
                for i, layer in enumerate(model.bb.layers) for j, block in enumerate(layer.blocks)]
    modules += [('decoder_' + name, child) for name, child in model.decoder.named_children()]
    hooks = []

    def before(name: str) -> Any:
        def hook(_module: Any, _inputs: Any) -> None:
            check_cancel(cancelled)
            if progress:
                progress('background_' + name, 0, 1)
            check_cancel(cancelled)
        return hook

    try:
        for name, module in modules:
            hooks.append(module.register_forward_pre_hook(before(name)))
        with torch.inference_mode():
            output = model(tensor)
    finally:
        for hook in hooks:
            hook.remove()
    check_cancel(cancelled)
    if not isinstance(output, (list, tuple)) or not output:
        raise ValueError('BiRefNet produced invalid output')
    logits = output[-1]
    if not isinstance(logits, torch.Tensor) or logits.shape != (1, 1, INPUT_SIZE, INPUT_SIZE) or logits.device.type != 'cpu' or logits.dtype != torch.float32 or not torch.isfinite(logits).all():
        raise ValueError('BiRefNet produced invalid mask logits')
    # ToPILImage deliberately truncates floats to uint8. PIL's default resize
    # for an L image is bicubic; rounding/bilinear would change Pixal's mask.
    mask = transforms.ToPILImage()(logits.sigmoid()[0].squeeze()).resize(image.size)
    result = image.copy()
    result.putalpha(mask)
    if progress:
        progress('background_complete', 1, 1)
    check_cancel(cancelled)
    return result
