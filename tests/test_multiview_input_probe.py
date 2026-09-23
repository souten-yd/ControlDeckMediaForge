from __future__ import annotations

import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
import pytest

from scripts.verify_multiview_inputs import InvalidViews, verify_directory


def views(root: Path) -> Path:
    root.mkdir()
    frames = []
    for index, rotation in enumerate((
        [[1, 0, 0, 0], [0, 0, -1, -3.1], [0, 1, 0, 0], [0, 0, 0, 1]],
        [[0, 0, 1, 3.1], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]],
    )):
        image = Image.new('RGBA', (64, 64))
        ImageDraw.Draw(image).rectangle((10 + index * 10, 5, 40, 50), fill=(255, 20, 5, 255))
        name = f'view-{index}.png'
        image.save(root / name)
        frames.append({'file_path': name, 'transform_matrix': rotation})
    (root / 'transforms.json').write_text(json.dumps({'frames': frames, 'camera_angle_x': .35, 'mesh_scale': 1}))
    return root


def test_distinct_views_audit_hashes_and_leave_source_unchanged(tmp_path: Path) -> None:
    root = views(tmp_path / 'views')
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    result = verify_directory(root)
    assert result['valid'] and result['selected_count'] == 2
    assert len({v['premultiplied_pixels_sha256'] for v in result['views']}) == 2
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
    assert not result['adoption_checked']


@pytest.mark.parametrize('different_encoding', [False, True])
def test_same_pixels_under_different_name_rejected(tmp_path: Path, different_encoding: bool) -> None:
    root = views(tmp_path / 'views')
    if different_encoding:
        with Image.open(root / 'view-0.png') as image:
            image.save(root / 'view-1.png', compress_level=0)
        assert (root / 'view-0.png').read_bytes() != (root / 'view-1.png').read_bytes()
    else:
        shutil.copyfile(root / 'view-0.png', root / 'view-1.png')
    with pytest.raises(InvalidViews, match='duplicate_image_content'):
        verify_directory(root)


def test_changed_invisible_pixels_cannot_disguise_a_duplicate(tmp_path: Path) -> None:
    root = views(tmp_path / 'views')
    with Image.open(root / 'view-0.png') as image:
        image.putpixel((0, 0), (255, 255, 255, 0))
        image.save(root / 'view-1.png')
    with pytest.raises(InvalidViews, match='duplicate_image_content'):
        verify_directory(root)


@pytest.mark.parametrize(('fault', 'reason'), [
    ('escape', 'image_path_escape'), ('traversal', 'image_path_invalid'),
    ('same_path', 'duplicate_image_path'), ('camera', 'duplicate_camera_pose'),
    ('singular', 'camera_rotation_not_orthonormal'), ('reflected', 'camera_rotation_reflected'),
    ('fov', 'camera_fov_out_of_bounds'), ('nonfinite', 'camera_number_invalid'),
    ('opaque', 'nonempty_matted_foreground_required'), ('empty', 'nonempty_matted_foreground_required'),
    ('size', 'view_canvas_mismatch'), ('count', 'view_count_invalid'),
])
def test_invalid_inputs_fail_before_native_generation(tmp_path: Path, fault: str, reason: str) -> None:
    root = views(tmp_path / 'views')
    metadata = json.loads((root / 'transforms.json').read_text())
    frame = metadata['frames'][1]
    if fault == 'escape':
        outside = tmp_path / 'outside.png'
        (root / 'view-1.png').rename(outside)
        (root / 'view-1.png').symlink_to(outside)
    elif fault == 'traversal':
        frame['file_path'] = '../outside.png'
    elif fault == 'same_path':
        frame['file_path'] = 'view-0.png'
    elif fault == 'camera':
        frame['transform_matrix'] = metadata['frames'][0]['transform_matrix']
    elif fault in {'singular', 'reflected'}:
        frame['transform_matrix'][0][2] = 0 if fault == 'singular' else -1
    elif fault in {'fov', 'nonfinite'}:
        metadata['camera_angle_x'] = 0 if fault == 'fov' else float('nan')
    elif fault in {'opaque', 'empty'}:
        Image.new('RGBA', (64, 64), (20, 30, 40, 255 if fault == 'opaque' else 0)).save(root / 'view-1.png')
    elif fault == 'size':
        with Image.open(root / 'view-1.png') as image:
            image.resize((128, 128)).save(root / 'view-1.png')
    (root / 'transforms.json').write_text(json.dumps(metadata))
    with pytest.raises(InvalidViews, match=reason):
        verify_directory(root, count=3 if fault == 'count' else None)


def test_duplicate_metadata_keys_rejected(tmp_path: Path) -> None:
    root = views(tmp_path / 'views')
    (root / 'transforms.json').write_text('{"frames":[],"frames":[]}')
    with pytest.raises(InvalidViews, match='duplicate_metadata_key'):
        verify_directory(root)
