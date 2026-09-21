"""動いている姿を見られるようにする。

書いた動きが意図どおりかを書いた側が確かめられないと、直しようがない。
観察は `frame_set(0)` 固定で、どのフレームを頼んでもレスト姿勢しか返さなかった。
クリップを名指せばその姿勢で描く。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mediaforge.scene_observation import ObservationSpec

ROOT = Path(__file__).parents[1]


def spec(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {"center": [0.0, 0.0, 0.0], "span_m": 1.0, "views": ["front"]}
    value.update(changes)
    return value


def test_the_rest_pose_stays_the_default() -> None:
    value = ObservationSpec.model_validate(spec())
    assert value.clip_id is None and value.frames is None
    assert value.rendered_frames() == [0]


def test_naming_a_clip_renders_the_frames_asked_for() -> None:
    value = ObservationSpec.model_validate(spec(clip_id="walk", frames=[0, 6, 12, 18]))
    assert value.rendered_frames() == [0, 6, 12, 18]


def test_frames_without_a_clip_are_refused() -> None:
    """フレームだけ動かしても姿勢は変わらない。「動いて見えない」を探させない。"""
    with pytest.raises(ValidationError):
        ObservationSpec.model_validate(spec(frames=[0, 6]))


def test_a_clip_without_frames_is_refused() -> None:
    with pytest.raises(ValidationError):
        ObservationSpec.model_validate(spec(clip_id="walk"))


@pytest.mark.parametrize("frames", [[6, 0], [0, 0], list(range(9))])
def test_frames_must_be_unique_increasing_and_bounded(frames: list[int]) -> None:
    with pytest.raises(ValidationError):
        ObservationSpec.model_validate(spec(clip_id="walk", frames=frames))


def test_the_render_budget_counts_views_times_frames() -> None:
    """CPU のパストレースなので、1 回の観察で描く枚数に歯止めが要る。"""
    ObservationSpec.model_validate(
        spec(views=["front", "side"], clip_id="walk", frames=[0, 6, 12, 18]))
    with pytest.raises(ValidationError):
        ObservationSpec.model_validate(
            spec(views=["front", "side", "back"], clip_id="walk", frames=[0, 6, 12]))


def test_the_published_schema_carries_the_pose_fields() -> None:
    schema = json.loads((ROOT / "schemas/scene-observe-request.json").read_text())
    properties = schema["$defs"]["ObservationSpec"]["properties"]
    assert "clip_id" in properties and "frames" in properties
    # 埋め込んでいる側も同じ定義でなければ、片方だけ古くなる。
    refine = json.loads((ROOT / "schemas/scene-refine-request.json").read_text())
    assert refine["$defs"]["ObservationSpec"] == schema["$defs"]["ObservationSpec"]
