"""Server-private Pixal worker descriptor; integrity is not GPU admission."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any, Callable

from camera import contained_file, file_sha256

ROLES = ('dino', 'naf', 'ss-flow', 'ss-decoder', 'shape-lr', 'shape-hr',
         'shape-decoder', 'texture-flow', 'texture-decoder')
ARRAY_FILES = ('rgb_low.npy', 'rgb_high.npy', 'camera.npy', 'samplers.npy', 'shape_norm.npy', 'texture_norm.npy')
PREPARED_FILES = (*ARRAY_FILES, 'framed.png', 'manifest.json')
INTEGER_OPTIONS = {
    'low_size': (1, 1024), 'high_size': (1, 1024), 'resolution': (1024, 1536),
    'max_tokens': (1, 1048576), 'naf_lr': (1, 1024), 'naf_hr': (1, 1024), 'naf_texture': (1, 1024),
    'texture_size': (32, 4096), 'target_faces': (4, 5000000), 'decoder_chunk': (1, 65536),
    'max_voxels': (1, 64 * 1024**2), 'max_triangles': (1, 256 * 1024**2),
}


def keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(label + ' fields differ')
    return value


def integer(value: Any, minimum: int, maximum: int, label: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('invalid ' + label)
    return value


def scalar(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e12:
        raise ValueError('invalid ' + label)
    return float(value)


def hash_string(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid worker SHA-256')
    return value


def read_json(path: Path, bound: int = 256 * 1024) -> dict[str, Any]:
    if not 1 <= path.stat().st_size <= bound:
        raise ValueError('worker JSON exceeds bound')
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate worker JSON field')
            result[key] = value
        return result
    def invalid(value: str) -> Any:
        raise ValueError('non-finite worker JSON: ' + value)
    value = json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError('worker JSON must be an object')
    return value


def file_record(path: Path) -> dict[str, Any]:
    return {'sha256': file_sha256(path), 'size_bytes': path.stat().st_size}


def verified_file(value: Any, root: Path, *, with_path: bool = True, path: Path | None = None) -> Path:
    keys(value, {'path', 'sha256', 'size_bytes'} if with_path else {'sha256', 'size_bytes'}, 'worker file')
    hash_string(value['sha256'])
    integer(value['size_bytes'], 1, 64 * 1024**3, 'worker file size')
    if with_path:
        if not isinstance(value['path'], str) or not Path(value['path']).is_absolute():
            raise ValueError('worker file path must be private and absolute')
        path = Path(value['path'])
    if path is None:
        raise ValueError('missing worker file path')
    path = contained_file(path, root)
    if path.stat().st_size != value['size_bytes'] or file_sha256(path) != value['sha256']:
        raise ValueError('worker file identity changed')
    return path


def directory(value: Any, root: Path) -> Path:
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError('worker directory must be private and absolute')
    path = Path(value).resolve(strict=True)
    if not path.is_dir() or not path.is_relative_to(root.resolve(strict=True)):
        raise ValueError('worker directory escapes allowed root')
    return path


def load_spec(path: Path, allowed_root: Path, binary_root: Path,
              cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
    from camera import check_cancel

    check_cancel(cancelled)
    path = contained_file(path, allowed_root)
    spec = read_json(path)
    keys(spec, {'schema_version', 'source_kind', 'native', 'models', 'camera', 'background', 'options'}, 'worker descriptor')
    if spec['schema_version'] != 'media-forge.pixal-worker@1' or spec['source_kind'] not in {'synthetic', 'checkpoint'}:
        raise ValueError('invalid worker descriptor identity')
    spec['native']['path'] = str(verified_file(spec['native'], binary_root))
    keys(spec['models'], set(ROLES), 'native models')
    for record in spec['models'].values():
        check_cancel(cancelled)
        record['path'] = str(verified_file(record, allowed_root))
    keys(spec['camera'], {'source', 'checkpoint', 'num_tokens', 'mesh_scale', 'extend_pixel', 'image_resolution'}, 'camera')
    keys(spec['background'], {'source', 'checkpoint'}, 'background')
    for stage in ('camera', 'background'):
        check_cancel(cancelled)
        spec[stage]['source'] = str(directory(spec[stage]['source'], allowed_root))
        spec[stage]['checkpoint']['path'] = str(verified_file(spec[stage]['checkpoint'], allowed_root))
    cam = spec['camera']
    if cam['num_tokens'] is not None:
        integer(cam['num_tokens'], 4, 4096, 'camera token count')
    if scalar(cam['mesh_scale'], 'camera scale') <= 0:
        raise ValueError('invalid camera scale')
    integer(cam['extend_pixel'], 0, 2048, 'camera extension')
    integer(cam['image_resolution'], 2, 2048, 'camera resolution')
    options = keys(spec['options'], set(INTEGER_OPTIONS) | {'samplers', 'shape_norm', 'texture_norm'}, 'worker options')
    for key, (minimum, maximum) in INTEGER_OPTIONS.items():
        integer(options[key], minimum, maximum, key)
    if options['resolution'] not in (1024, 1536) or options['texture_size'] & (options['texture_size'] - 1):
        raise ValueError('unsupported worker resolution or texture size')
    samplers = options['samplers']
    if not isinstance(samplers, list) or len(samplers) != 3:
        raise ValueError('invalid worker samplers')
    for sampler in samplers:
        if not isinstance(sampler, list) or len(sampler) != 7:
            raise ValueError('invalid worker sampler row')
        integer(sampler[0], 1, 1000, 'sampler steps')
        _, rescale, guidance, strength, lo, hi, sigma = [scalar(v, 'sampler value') for v in sampler]
        if rescale <= 0 or not 0 <= strength <= 1 or not 0 <= lo <= hi <= 1 or not 0 <= sigma < 1:
            raise ValueError('invalid worker sampler range')
    for name in ('shape_norm', 'texture_norm'):
        rows = options[name]
        if not isinstance(rows, list) or len(rows) != 2 or any(not isinstance(row, list) for row in rows) or not 1 <= len(rows[0]) <= 4096 or len(rows[1]) != len(rows[0]):
            raise ValueError('invalid worker normalization extent')
        for value in rows[0]:
            scalar(value, 'normalization mean')
        if any(scalar(value, 'normalization std') <= 0 for value in rows[1]):
            raise ValueError('invalid worker normalization std')
    check_cancel(cancelled)
    return spec
