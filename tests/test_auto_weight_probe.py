from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "auto_weight_probe", Path(__file__).parents[1] / "scripts/auto_weight_probe.py")
assert SPEC and SPEC.loader
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


@pytest.mark.parametrize("other,expected", [
    ([(0., 0., 0.), (1., 0., 0.)], 0.),
    ([(1., 0., 0.), (0., 0., 0.), (1., 0., 0.)], 0.),
    ([(0., 0., 0.)], 1.),
    ([(0., .00002, 0.), (1., .00002, 0.)], .00002),
])
def test_world_distance_preserves_missing_geometry_detection(other: list, expected: float) -> None:
    assert PROBE.point_error([(0., 0., 0.), (1., 0., 0.)], other) == pytest.approx(expected)


@pytest.mark.parametrize("first,second", [([], [(0., 0., 0.)]), ([(0., 0., 0.)], [])])
def test_empty_geometry_is_not_a_success(first: list, second: list) -> None:
    with pytest.raises(AssertionError):
        PROBE.point_error(first, second)


@pytest.mark.parametrize("weights,valid", [([.5, .5], True), ([.25, .25], False),
                                         ([1.], False), ([float('nan'), .5], False),
                                         ([float('nan'), .5, .5], False),
                                         ([-.1, .5, .5], False), ([0., .5, .5], True)])
def test_mixed_normalized_weight_gate(weights: list[float], valid: bool) -> None:
    obj = SimpleNamespace(data=SimpleNamespace(vertices=[SimpleNamespace(
        groups=[SimpleNamespace(weight=value) for value in weights])]))
    if valid:
        assert PROBE.weight_stats(obj)['mixed_vertices'] == 1
    else:
        with pytest.raises(AssertionError):
            PROBE.weight_stats(obj)
