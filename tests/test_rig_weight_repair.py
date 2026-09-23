"""Small heat-solver omissions may not become an unrestricted fallback rig."""
from __future__ import annotations

import copy
import importlib
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def repair(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'worker_packs/blender'))
    return importlib.import_module('rig_weight_repair')


def fixture(count: int = 1000) -> tuple[list[tuple[float, float, float]], list[dict[int, float]]]:
    points = [(0., 0., i / (count - 1)) for i in range(count)]
    return points, [{0: .25, 1: .75} for _ in points]


def test_tiny_island_interpolates_original_weights_without_mutation(repair: ModuleType) -> None:
    points, weights = fixture()
    weights[500] = weights[501] = {}
    weights[498] = {1: .5, 2: .5}
    before = copy.deepcopy(weights)
    result, report = repair.plan(points, [(500, 501)], weights,
                                 lambda p: [(498, .002), (502, .004)])
    assert weights == before
    assert set(result) == {500, 501} and report['components'] == 1
    assert report['repaired_vertices'] == 2
    assert result[500] == pytest.approx({0: .05, 1: .55, 2: .4})
    assert sum(result[501].values()) == pytest.approx(1)


def test_no_missing_weights_does_not_consult_donors(repair: ModuleType) -> None:
    points, weights = fixture()
    def forbidden(point: object) -> None:
        raise AssertionError('healthy binding must remain unchanged')
    result, report = repair.plan(points, [], weights, forbidden)
    assert result == {} and report['repaired_vertices'] == 0


@pytest.mark.parametrize('failure', ['fraction', 'total', 'island', 'span', 'far', 'chain', 'donor'])
def test_incomplete_or_unbounded_binding_is_rejected(repair: ModuleType, failure: str) -> None:
    count = 30000 if failure in {'total', 'island'} else 1000
    points, weights = fixture(count)
    missing = {'fraction': 6, 'total': 129, 'island': 65}.get(failure, 2)
    start = count // 2
    for i in range(start, start + missing):
        weights[i] = {}
    edges = [(i, i + 1) for i in range(start, start + missing - 1)]
    distance = .002
    donor = start - 1
    if failure == 'span':
        points[start + 1] = (.03, 0., points[start + 1][2])
    elif failure == 'far':
        distance = .006
    elif failure == 'chain':
        donor = start
    elif failure == 'donor':
        weights[donor] = {1: float('nan')}
    before = copy.deepcopy(weights)
    with pytest.raises(RuntimeError):
        repair.plan(points, edges, weights, lambda p: [(donor, distance)])
    # Missing vertices must remain missing even if another repair was planned.
    assert all(weights[i] == before[i] == {} for i in range(start, start + missing))
