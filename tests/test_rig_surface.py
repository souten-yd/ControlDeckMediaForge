"""Measure real faces even when simplification removes joint-band vertices."""
from __future__ import annotations

import importlib
import math
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def surface(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'worker_packs/blender'))
    return importlib.import_module('rig_surface')


PANEL = [(0., 0., 0.), (0., 1., 0.), (0., 1., 1.), (0., 0., 1.)]
TRIANGLES = [(0, 1, 2), (0, 2, 3)]


@pytest.mark.parametrize('scale,offset', [(1., (0., 0., 0.)), (3., (4., -2., 7.))])
def test_sections_lie_on_the_original_faces(surface: ModuleType, scale: float, offset: tuple) -> None:
    vertices = [tuple(p[i] * scale + offset[i] for i in range(3)) for p in PANEL]
    original = vertices.copy()
    points = surface.sample(vertices, TRIANGLES, .02 * scale)
    assert vertices == original
    assert min(p[2] for p in points) == offset[2]
    assert max(p[2] for p in points) == offset[2] + scale
    assert all(p[0] == offset[0] and offset[1] <= p[1] <= offset[1] + scale for p in points)
    assert len([p for p in points if .095 <= (p[2] - offset[2]) / scale <= .145]) > 24
    assert not any(.095 <= (p[2] - offset[2]) / scale <= .145 for p in vertices)


def test_duplicate_triangles_do_not_bias_measurements(surface: ModuleType) -> None:
    points = surface.sample(PANEL, TRIANGLES, .02)
    assert surface.sample(PANEL, TRIANGLES * 4, .02) == points


@pytest.mark.parametrize('spacing', [0., -1., math.inf, math.nan, 1e-300])
def test_invalid_or_unbounded_spacing_fails(surface: ModuleType, spacing: float) -> None:
    with pytest.raises(surface.SurfaceMeasurementError):
        surface.sample(PANEL, TRIANGLES, spacing)


@pytest.mark.parametrize('indices', [[(-1, 1, 2)], [(0, 1, 4)], [(0, 1)], [(True, 1, 2)]])
def test_invalid_triangle_indices_fail(surface: ModuleType, indices: list) -> None:
    with pytest.raises(surface.SurfaceMeasurementError):
        surface.sample(PANEL, indices, .02)


@pytest.mark.parametrize('limit', ['MAX_TRIANGLES', 'MAX_SEGMENTS', 'MAX_POINTS', 'MAX_SAMPLE_ATTEMPTS'])
def test_all_work_budgets_are_enforced(surface: ModuleType, monkeypatch: pytest.MonkeyPatch, limit: str) -> None:
    monkeypatch.setattr(surface, limit, 1)
    with pytest.raises(surface.SurfaceMeasurementError):
        surface.sample(PANEL, TRIANGLES, .02)


def test_nonfinite_or_flat_geometry_fails(surface: ModuleType) -> None:
    for vertices in [[], [(math.nan, 0., 0.)], [(0., 0., 0.)], [(0., 0., -1e308), (0., 0., 1e308)]]:
        with pytest.raises(surface.SurfaceMeasurementError):
            surface.sample(vertices, [], .02)
