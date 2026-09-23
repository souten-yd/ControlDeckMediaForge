"""Read-only image and camera validation shared by native multiview and its probe.

Validation does not establish runtime adoption or infer camera calibration.
It never downloads models or edits images.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_SIDE = 2048


class InvalidViews(ValueError):
    """Stable diagnostic with no file content or private path in its message."""


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidViews('camera_number_invalid')
    try:
        number = float(value)
    except OverflowError as exc:
        raise InvalidViews('camera_number_invalid') from exc
    if not math.isfinite(number):
        raise InvalidViews('camera_number_invalid')
    return number


def _camera(frame: dict[str, Any], metadata: dict[str, Any]) -> tuple[list[list[float]], float]:
    raw = frame.get('transform_matrix')
    if not isinstance(raw, list) or len(raw) != 4 or any(not isinstance(row, list) or len(row) != 4 for row in raw):
        raise InvalidViews('camera_matrix_shape_invalid')
    matrix = [[_number(v) for v in row] for row in raw]
    if any(abs(a - b) > 1e-6 for a, b in zip(matrix[3], [0, 0, 0, 1], strict=True)):
        raise InvalidViews('camera_not_affine')
    rotation = [row[:3] for row in matrix[:3]]
    for i in range(3):
        for j in range(3):
            dot = sum(rotation[i][k] * rotation[j][k] for k in range(3))
            if abs(dot - (1 if i == j else 0)) > 1e-4:
                raise InvalidViews('camera_rotation_not_orthonormal')
    a, b, c = rotation
    determinant = a[0] * (b[1]*c[2]-b[2]*c[1]) - a[1] * (b[0]*c[2]-b[2]*c[0]) + a[2] * (b[0]*c[1]-b[1]*c[0])
    if abs(determinant - 1) > 1e-4:
        raise InvalidViews('camera_rotation_reflected')
    if any(abs(matrix[i][3]) > 100 for i in range(3)):
        raise InvalidViews('camera_distance_out_of_bounds')
    distance = math.sqrt(sum(matrix[i][3] ** 2 for i in range(3)))
    if not 0.01 <= distance <= 100:
        raise InvalidViews('camera_distance_out_of_bounds')
    fov = _number(frame.get('camera_angle_x', metadata.get('camera_angle_x')))
    if not math.radians(1) <= fov <= math.radians(160):
        raise InvalidViews('camera_fov_out_of_bounds')
    return matrix, fov


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InvalidViews('duplicate_metadata_key')
        value[key] = item
    return value


def _read_metadata(root: Path) -> dict[str, Any]:
    path = (root / 'transforms.json').resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise InvalidViews('metadata_path_escape')
    with path.open('rb') as stream:
        content = stream.read(64 * 1024 + 1)
    if not 1 <= len(content) <= 64 * 1024:
        raise InvalidViews('metadata_size_invalid')
    value = json.loads(content, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise InvalidViews('metadata_object_required')
    return value


def image_identity(path: Path, *, allow_webp: bool = False) -> dict[str, Any]:
    size = path.stat().st_size
    if not 1 <= size <= MAX_IMAGE_BYTES:
        raise InvalidViews('image_size_invalid')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        stream.seek(0)
        with Image.open(stream) as image:
            if image.format not in ({'PNG', 'WEBP'} if allow_webp else {'PNG'}) or image.mode != 'RGBA':
                raise InvalidViews('rgba_png_required')
            if not 64 <= image.width == image.height <= MAX_SIDE:
                raise InvalidViews('square_canvas_out_of_bounds')
            if image.getexif().get(274, 1) != 1:
                raise InvalidViews('unapplied_image_orientation')
            alpha = image.getchannel('A')
            low, high = alpha.getextrema()
            if low == 255 or high == 0:
                raise InvalidViews('nonempty_matted_foreground_required')
            channels = image.split()
            premult = Image.merge('RGBA', tuple(ImageChops.multiply(c, alpha) for c in channels[:3]) + (alpha,))
            pixel_hash = hashlib.sha256(
                f'{image.width}x{image.height}:premult8\0'.encode() + premult.tobytes(),
            ).hexdigest()
            return {'bytes': size, 'sha256': digest, 'size': list(image.size),
                    'foreground_bounds': list(alpha.getbbox()),
                    'premultiplied_pixels_sha256': pixel_hash}


def verify_directory(directory: Path, *, count: int | None = None) -> dict[str, Any]:
    """Audit every supplied frame, including frames outside a requested prefix."""
    root = directory.resolve(strict=True)
    metadata = _read_metadata(root)
    frames = metadata.get('frames')
    if not isinstance(frames, list) or not 2 <= len(frames) <= 4:
        raise InvalidViews('two_to_four_views_required')
    used = len(frames) if count is None else count
    if type(used) is not int or not 2 <= used <= len(frames):
        raise InvalidViews('view_count_invalid')
    mesh_scale = _number(metadata.get('mesh_scale', 1))
    if not .01 <= mesh_scale <= 100:
        raise InvalidViews('mesh_scale_out_of_bounds')
    seen_pixels: set[str] = set()
    seen_paths: set[Path] = set()
    seen_cameras: set[tuple[float, ...]] = set()
    canvas: tuple[int, int] | None = None
    records: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise InvalidViews('frame_object_required')
        relative = frame.get('file_path')
        if (not isinstance(relative, str) or not relative or len(relative) > 256
                or '\\' in relative or '\x00' in relative or Path(relative).is_absolute()
                or '..' in Path(relative).parts):
            raise InvalidViews('image_path_invalid')
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise InvalidViews('image_path_escape')
        if path in seen_paths:
            raise InvalidViews('duplicate_image_path')
        seen_paths.add(path)
        size = path.stat().st_size
        if not 1 <= size <= MAX_IMAGE_BYTES:
            raise InvalidViews('image_size_invalid')
        matrix, fov = _camera(frame, metadata)
        camera_key = tuple(round(v, 7) for row in matrix for v in row)
        if camera_key in seen_cameras:
            raise InvalidViews('duplicate_camera_pose')
        seen_cameras.add(camera_key)
        identity = image_identity(path)
        if canvas is not None and identity['size'] != list(canvas):
            raise InvalidViews('view_canvas_mismatch')
        canvas = tuple(identity['size'])
        pixel_hash = identity['premultiplied_pixels_sha256']
        if pixel_hash in seen_pixels:
            raise InvalidViews('duplicate_image_content')
        seen_pixels.add(pixel_hash)
        digest = identity['sha256']
        bounds = identity['foreground_bounds']
        records.append({'index': index, 'filename': relative, 'bytes': size,
                        'sha256': digest, 'premultiplied_pixels_sha256': pixel_hash,
                        'size': list(canvas), 'foreground_bounds': list(bounds),
                        'camera_angle_x': fov, 'camera_to_world': matrix,
                        'selected_for_generation': index < used})
    canonical = json.dumps({'mesh_scale': mesh_scale, 'views': records}, sort_keys=True, separators=(',', ':'))
    return {'valid': True, 'view_count': len(records), 'selected_count': used,
            'input_manifest_sha256': hashlib.sha256(canonical.encode()).hexdigest(),
            'mesh_scale': mesh_scale, 'views': records,
            'calibration': 'supplied metadata checked structurally; image correspondence not inferred',
            'content_check': 'exact premultiplied 8-bit pixels; not perceptual similarity',
            'adoption_checked': False}

