"""An upright character's dense hands must not become its knees."""
from __future__ import annotations

import importlib
import math
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def auto(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'worker_packs/blender'))
    return importlib.import_module('rig_auto')


def surface(*, arms: bool = True) -> list[tuple[float, float, float]]:
    points = []
    for step in range(101):
        z = step / 100
        circles = []
        if .01 <= z <= .50:
            circles.extend([(-.08, .045, .04), (.08, .045, .04)])
        if .35 <= z <= .80:
            circles.append((0, .12, .065))
        if .78 <= z <= 1:
            radius = math.sqrt(max(0., 1 - ((z - .89) / .11) ** 2))
            circles.append((0, .10 * radius, .085 * radius))
        if arms and .38 <= z <= .74:
            x = .12 + (.74 - z) * .36
            circles.extend([(-x, .028, .028), (x, .028, .028)])
        for x, rx, ry in circles:
            for angle in range(48):
                theta = angle * math.tau / 48
                points.append((x + rx * math.cos(theta), ry * math.sin(theta), z))
    return points


def measured(auto: ModuleType, monkeypatch: pytest.MonkeyPatch,
             points: list[tuple[float, float, float]]) -> dict[str, Any]:
    monkeypatch.setattr(auto, '_sampled_points', lambda obj: points)
    obj = SimpleNamespace(type='MESH', data=SimpleNamespace(vertices=[1]))
    return auto.measure(obj)


@pytest.mark.parametrize('scale,offset', [(1., (0., 0., 0.)), (3., (4., -2., 7.))])
def test_human_has_supported_arms_and_knees_below_the_hips(
    auto: ModuleType, monkeypatch: pytest.MonkeyPatch, scale: float, offset: tuple[float, float, float]
) -> None:
    points = [tuple(p[k] * scale + offset[k] for k in range(3)) for p in surface()]
    facts = measured(auto, monkeypatch, points)
    assert facts['body_plan'] == 'humanoid'
    assert len(facts['arms']) == len(facts['legs']) == 2
    for leg in facts['legs']:
        assert .22 < (leg['knee'][2] - offset[2]) / scale < .30
        assert leg['foot'][2] < leg['knee'][2] < leg['hip'][2]
    armature = auto.armature_operation(facts, 'rig', 'Character')
    names = {bone['bone_id'] for bone in armature['bones']}
    assert {'head', 'arm1_upper', 'arm1_lower', 'arm1_hand', 'arm2_hand'} <= names
    from mediaforge.scene_recipes import SceneRecipe
    SceneRecipe.model_validate({'operations': [armature, auto.walk_operation(facts, 'rig', 'walk', 24, 24)]})


def test_dense_hand_topology_does_not_move_the_knees_up(auto: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    points = surface()
    original = measured(auto, monkeypatch, points)
    dense_hands = [p for p in points if abs(p[0]) > .18 and .38 < p[2] < .49]
    dense = measured(auto, monkeypatch, points + dense_hands * 12)
    assert dense['body_plan'] == 'humanoid'
    for before, after in zip(original['legs'], dense['legs'], strict=True):
        assert after['knee'] == pytest.approx(before['knee'], abs=1e-6)


def test_missing_arms_are_not_claimed_as_a_humanoid(auto: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    facts = measured(auto, monkeypatch, surface(arms=False))
    assert facts.get('body_plan') != 'humanoid'
    assert len(facts['legs']) == 2


def test_simplified_flat_waist_does_not_lose_arm_support(
    auto: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A decimator retains cuffs but removes most vertices from flat waist faces.
    points = [p for p in surface() if not (.40 < p[2] < .50 and abs(p[0]) < .05)]
    facts = measured(auto, monkeypatch, points)
    assert facts['body_plan'] == 'humanoid'
    assert len(facts['arms']) == 2


def test_wide_shoes_do_not_become_hand_tips(auto: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    points = surface()
    shoes = [(x * 2.5, y, z) for x, y, z in points if z < .08]
    facts = measured(auto, monkeypatch, points + shoes)
    assert facts['body_plan'] == 'humanoid'
    assert all(arm['hand'][2] > .3 for arm in facts['arms'])


def test_humanoid_gait_is_sagittal_with_opposite_arms_and_closed_loop(
    auto: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts = measured(auto, monkeypatch, surface())
    tracks = auto.walk_operation(facts, 'rig', 'walk', 24, 24)['tracks']
    by_name = {track['bone_id']: track['keys'] for track in tracks}
    for keys in by_name.values():
        assert keys[0]['rotation_degrees'] == keys[-1]['rotation_degrees']
        assert all(key['rotation_degrees'][1:] == [0., 0.] for key in keys)
    assert by_name['leg1_upper'][1]['rotation_degrees'][0] < 0
    assert by_name['leg2_upper'][1]['rotation_degrees'][0] > 0
    assert by_name['arm1_upper'][1]['rotation_degrees'][0] > 0


@pytest.mark.parametrize('count', [4, 6])
def test_radial_creatures_keep_their_legs_and_alternating_gait(
    auto: ModuleType, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    points = []
    for level in range(101):
        z = level / 100
        for step in range(48):
            theta = step * math.tau / 48
            if z > .45:
                points.append((.32 * math.cos(theta), .32 * math.sin(theta), z))
            if z < .60:
                for leg in range(count):
                    bearing = leg * math.tau / count
                    points.append((.4 * math.cos(bearing) + .045 * math.cos(theta),
                                   .4 * math.sin(bearing) + .045 * math.sin(theta), z))
    facts = measured(auto, monkeypatch, points)
    assert facts.get('body_plan') != 'humanoid'
    assert len(facts['legs']) == count
    bones = auto.armature_operation(facts, 'rig', 'Creature')['bones']
    assert len([b for b in bones if b['bone_id'].endswith('_lower')]) == count
    clip = auto.walk_operation(facts, 'rig', 'walk', 24, 24)
    assert len(clip['tracks']) == count * 2
    upper = clip['tracks'][::2]
    for a, b in zip(upper, upper[1:]):
        assert a['keys'][1]['rotation_degrees'][2] == -b['keys'][1]['rotation_degrees'][2]
