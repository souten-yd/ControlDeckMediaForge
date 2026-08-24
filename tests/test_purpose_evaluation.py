"""G4H A3: evaluate suitability for a stated use, not generic beauty.

The Hanabi background was genuinely attractive and was composed exactly as its
prompt asked. It was unusable because the surface it had to fill was landscape.
Asking "is this a good image?" would have answered yes.
"""

from __future__ import annotations

import pytest

from mediaforge.asset_brief import (
    AssetBrief,
    brief_dimensions,
    brief_rubric,
    resolve_layout,
)
from mediaforge.evaluator import EVALUATION_DIMENSIONS, relevant_dimensions

ENVELOPE = {"min_side": 256, "max_side": 1024, "multiple_of": 16, "max_pixels": 1024 * 1024}


def brief_and_layout(**kwargs):
    brief = AssetBrief(**kwargs)
    return brief, resolve_layout(brief, envelope=ENVELOPE)


# ── 用途が観点を決める ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "role,expected",
    [
        ("background", {"composition", "palette"}),
        ("character_portrait", {"subject_identity", "composition"}),
        ("sprite", {"subject_identity"}),
        ("texture", {"style"}),
        ("general", set()),
    ],
)
def test_each_role_asks_for_the_dimensions_that_matter_to_it(role: str, expected: set):
    assert set(brief_dimensions(AssetBrief(role=role))) == expected


def test_a_declared_safe_area_makes_composition_relevant():
    """空けておくべき領域があるなら、それは構図の話である。"""
    brief = AssetBrief(role="general", safe_areas=[{"edge": "top", "fraction": 0.4}])

    assert "composition" in brief_dimensions(brief)


def test_every_brief_dimension_is_a_real_evaluation_dimension():
    """存在しない観点を評価器へ渡さない。"""
    for role in ("background", "key_visual", "character_portrait", "sprite",
                 "icon", "emblem", "texture", "ui_element", "general"):
        for name in brief_dimensions(AssetBrief(role=role)):
            assert name in EVALUATION_DIMENSIONS


def test_the_brief_widens_the_evaluated_dimensions():
    without = relevant_dimensions({}, has_references=False)
    with_brief = relevant_dimensions(
        {}, has_references=False, brief=AssetBrief(role="background")
    )

    assert set(without) < set(with_brief)
    assert "composition" in with_brief


def test_no_brief_leaves_the_existing_dimension_selection_alone():
    """brief を使わない既存の呼び出しの意味を変えない。"""
    assert relevant_dimensions({}, has_references=False, brief=None) == relevant_dimensions(
        {}, has_references=False
    )


# ── 評価器へ渡す文言 ────────────────────────────────────────────────────


def test_the_rubric_states_what_suitable_means_for_a_background():
    brief, resolved = brief_and_layout(role="background")

    rubric = brief_rubric(brief, resolved)

    assert "drawn on top of" in rubric
    assert "compete" in rubric


def test_the_rubric_asks_about_intrusion_into_a_declared_safe_area():
    brief, resolved = brief_and_layout(
        role="background",
        safe_areas=[{"edge": "top", "fraction": 0.4, "purpose": "title and menu"}],
    )

    rubric = brief_rubric(brief, resolved)

    assert "top 40%" in rubric
    assert "title and menu" in rubric
    assert "intrudes" in rubric


def test_the_rubric_forbids_the_evaluator_from_relitigating_settled_geometry():
    """寸法は決定的に解決済み。VLM に蒸し返させない。"""
    brief, resolved = brief_and_layout(role="background")

    rubric = brief_rubric(brief, resolved)

    assert "already fixed" in rubric
    assert "do not comment on dimensions" in rubric


def test_hard_constraints_reach_the_evaluator():
    brief, resolved = brief_and_layout(
        role="key_visual", hard_constraints=["no text in the image"]
    )

    assert "no text in the image" in brief_rubric(brief, resolved)


def test_an_emblem_is_judged_as_a_motif_not_a_scene():
    """Hanabi の花火キーアートは重ね用の紋章なのに完成シーンだった。"""
    brief, resolved = brief_and_layout(role="emblem")

    assert "isolated motif" in brief_rubric(brief, resolved)


def test_without_a_brief_no_rubric_is_added():
    assert brief_rubric(None, None) == ""


def test_the_rubric_stays_bounded():
    brief, resolved = brief_and_layout(
        role="background",
        target_surface="game",
        hard_constraints=["x" * 200] * 16,
        safe_areas=[{"edge": edge, "fraction": 0.3} for edge in ("top", "bottom", "left", "right")],
    )

    assert len(brief_rubric(brief, resolved)) <= 1500


# ── 予算は主観だけを縛る ────────────────────────────────────────────────


def test_the_default_request_asks_for_no_vision_call_at_all():
    """通常生成に VLM を必須にしない。1 回ごとに model swap を払うことになる。"""
    from mediaforge.domain import JobRequest

    request = JobRequest(operation="image.generate", intent="anything")

    assert request.qa.semantic is False
    assert request.qa.max_regeneration_attempts == 0


def test_an_objective_defect_is_not_charged_to_the_retry_budget(tmp_path):
    """予算切れが必要な修正を握り潰さないことを、経路の形で守る。

    defect の判定は QA 予算をまったく参照しない。参照させた瞬間に、
    予算を使い切った job が誤った資産を成功として返せるようになる。
    """
    import inspect

    from mediaforge.jobs import JobManager

    source = inspect.getsource(JobManager._brief_defects)

    assert "max_regeneration_attempts" not in source
    assert "qa" not in source.replace("request.constraints", "")
