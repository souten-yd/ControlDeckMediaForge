"""Validate and freeze all view Assets without changing camera framing."""
from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from .multiview_inputs import InvalidViews, image_identity
from .scene_generation import GenerationViewCamera, GenerationViewFacts, SceneFromImageRequest
from .scenes import SceneError

if TYPE_CHECKING:
    from .scene_workspace import SceneWorkspace


def inspect_views(workspace: SceneWorkspace, value: SceneFromImageRequest) -> tuple[list[GenerationViewFacts], list[Path]]:
    facts, paths = [], []
    seen: set[str] = set()
    canvas: list[int] | None = None
    for direction, asset_id in value.ordered_views():
        asset = workspace.store.get_asset(asset_id)
        if asset_id in workspace.store.trashed_asset_ids():
            raise SceneError('scene_generation_input_invalid', 'Restore the input image from Trash first')
        _, _, path = workspace._verified_revision_asset(asset_id, asset.mime_type)
        try:
            identity = image_identity(path, allow_webp=True)
        except (InvalidViews, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise SceneError('scene_multiview_input_invalid', 'Views require transparent square RGBA PNG or WebP images, 64 to 2048 pixels, with unchanged framing') from exc
        if identity['sha256'] != asset.sha256:
            raise SceneError('scene_generation_input_invalid', 'View image changed while validating')
        if canvas is not None and identity['size'] != canvas:
            raise SceneError('scene_multiview_canvas_mismatch', 'All views must have the same square canvas size')
        canvas = identity['size']
        pixels = identity['premultiplied_pixels_sha256']
        if pixels in seen:
            raise SceneError('scene_multiview_duplicate_image', 'Choose a different image for each direction')
        seen.add(pixels)
        facts.append(GenerationViewFacts(direction=direction, asset_id=asset_id,
                                        sha256=asset.sha256, pixels_sha256=pixels))
        paths.append(path)
    return facts, paths


def view_transforms(value: SceneFromImageRequest) -> dict[str, object]:
    camera = value.view_camera or GenerationViewCamera()
    elevation = math.radians(camera.elevation_degrees)
    ce, se = math.cos(elevation), math.sin(elevation)
    frames = []
    for index, (direction, _) in enumerate(value.ordered_views()):
        azimuth = math.radians({'front': 0, 'right': 90, 'back': 180, 'left': 270}[direction])
        ca, sa = math.cos(azimuth), math.sin(azimuth)
        matrix = [[ca, -sa*se, sa*ce, camera.distance*sa*ce],
                  [sa, ca*se, -ca*ce, -camera.distance*ca*ce],
                  [0, ce, se, camera.distance*se], [0, 0, 0, 1]]
        frames.append({'file_path': f'view-{index}.png', 'name': direction, 'transform_matrix': matrix})
    return {'camera_angle_x': math.radians(camera.fov_degrees), 'mesh_scale': camera.mesh_scale, 'frames': frames}
