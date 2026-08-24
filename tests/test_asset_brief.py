"""G4H A1: purpose-level briefs and deterministic output geometry.

The regression these lock down is real. A Hanabi OpenCode run asked for a "wide
landscape" game title background, reached the worker with ``constraints == {}``,
and got 1024x1024 from the worker's own fallback. The page then used
``object-fit: cover``, cropping away the open sky and crowd the prompt had
asked for.
"""

from __future__ import annotations

import pytest

from mediaforge.asset_brief import (
    AssetBrief,
    AssetBriefError,
    effective_alpha_intent,
    infer_brief_from_intent,
    inspect_against_brief,
    parse_brief,
    resolve_layout,
)

ENVELOPE = {"min_side": 256, "max_side": 1024, "multiple_of": 16, "max_pixels": 1024 * 1024}


def layout(**brief):
    return resolve_layout(AssetBrief(**brief), envelope=ENVELOPE)


# ── 用途から幾何が決まること ────────────────────────────────────────────


def test_a_background_resolves_to_a_landscape_canvas_without_any_prose():
    """実使用の欠陥そのもの。散文の「wide landscape」に頼らない。"""
    resolved = layout(role="background")

    assert resolved is not None
    assert resolved.width > resolved.height
    assert resolved.aspect_ratio == "16:9"
    assert resolved.source == "role_default"


@pytest.mark.parametrize(
    "role,expected",
    [("icon", "1:1"), ("emblem", "1:1"), ("character_portrait", "2:3"), ("key_visual", "16:9")],
)
def test_each_role_has_a_deterministic_default_ratio(role: str, expected: str):
    assert layout(role=role).aspect_ratio == expected


def test_a_role_without_a_geometric_opinion_keeps_todays_behavior():
    """既定を持たない用途にまで比を押し付けない。"""
    assert layout(role="general") is None


def test_no_brief_at_all_keeps_todays_behavior():
    assert resolve_layout(None, envelope=ENVELOPE) is None


# ── 優先順位 ────────────────────────────────────────────────────────────


def test_an_explicit_request_size_beats_an_inferred_landscape():
    """推論が明示指定を上書きしたら、利用者は制御を失う。"""
    resolved = resolve_layout(
        AssetBrief(role="background"),
        envelope=ENVELOPE,
        explicit_width=1024,
        explicit_height=1024,
    )

    assert (resolved.width, resolved.height) == (1024, 1024)
    assert resolved.source == "request.constraints"


def test_explicit_brief_dimensions_beat_the_role_default():
    resolved = layout(role="background", target_width=512, target_height=512)

    assert (resolved.width, resolved.height) == (512, 512)
    assert resolved.source == "brief.target_dimensions"


def test_an_explicit_aspect_intent_beats_the_role_default():
    resolved = layout(role="icon", aspect_intent="landscape")

    assert resolved.width > resolved.height
    assert resolved.source == "brief.aspect_intent"


def test_an_explicit_ratio_is_honoured_exactly():
    resolved = layout(role="general", aspect_intent="ratio", aspect_ratio="21:9")

    assert resolved.aspect_ratio == "21:9"
    assert resolved.width / resolved.height == pytest.approx(21 / 9, rel=0.05)


# ── envelope の範囲を出ないこと ─────────────────────────────────────────


@pytest.mark.parametrize("role", ["background", "icon", "character_portrait", "key_visual"])
def test_every_resolved_canvas_is_acceptable_to_the_worker(role: str):
    """worker が拒否する寸法を UI や agent へ返さない。"""
    resolved = layout(role=role)

    assert resolved.width % 16 == 0 and resolved.height % 16 == 0
    assert ENVELOPE["min_side"] <= resolved.width <= ENVELOPE["max_side"]
    assert ENVELOPE["min_side"] <= resolved.height <= ENVELOPE["max_side"]
    assert resolved.width * resolved.height <= ENVELOPE["max_pixels"]


def test_a_narrow_envelope_still_produces_an_acceptable_canvas():
    narrow = {"min_side": 256, "max_side": 512, "multiple_of": 16, "max_pixels": 512 * 288}
    resolved = resolve_layout(AssetBrief(role="background"), envelope=narrow)

    assert resolved.width * resolved.height <= narrow["max_pixels"]
    assert resolved.width % 16 == 0 and resolved.height % 16 == 0


# ── alpha ───────────────────────────────────────────────────────────────


def test_an_overlay_emblem_requires_alpha_by_default():
    """Hanabi の花火キーアートは重ね要素なのに不透明な完成シーンだった。"""
    assert layout(role="emblem").alpha is True


def test_a_background_forbids_alpha_by_default():
    assert layout(role="background").alpha is False


def test_an_explicit_alpha_intent_beats_the_role_default():
    assert layout(role="background", alpha_intent="required").alpha is True
    assert layout(role="emblem", alpha_intent="forbidden").alpha is False


# ── 受理と拒否 ──────────────────────────────────────────────────────────


def test_a_brief_carries_no_provider_or_model_field():
    """agent に model/provider を選ばせない境界を型で守る。"""
    for field in ("model", "model_id", "provider", "sampler", "steps", "prompt"):
        assert field not in AssetBrief.model_fields


def test_an_unusable_ratio_is_rejected_before_generation():
    with pytest.raises(ValueError):
        AssetBrief(role="background", aspect_intent="ratio", aspect_ratio="wide")


def test_a_ratio_intent_without_a_ratio_is_rejected():
    with pytest.raises(ValueError):
        AssetBrief(role="background", aspect_intent="ratio")


def test_half_a_dimension_pair_is_rejected():
    with pytest.raises(ValueError):
        AssetBrief(role="background", target_width=512)


def test_repeated_safe_area_edges_are_rejected():
    with pytest.raises(ValueError):
        AssetBrief(role="background", safe_areas=[
            {"edge": "top", "fraction": 0.3}, {"edge": "top", "fraction": 0.4},
        ])


def test_safe_areas_survive_resolution_for_the_director_to_use():
    resolved = layout(role="background", safe_areas=[
        {"edge": "top", "fraction": 0.4, "purpose": "title UI"},
    ])

    assert resolved.safe_areas[0]["edge"] == "top"
    assert resolved.safe_areas[0]["purpose"] == "title UI"


def test_a_non_object_brief_is_rejected_with_a_code():
    with pytest.raises(AssetBriefError) as exc:
        parse_brief(["not", "an", "object"])

    assert exc.value.code == "asset_brief_invalid"


def test_an_unknown_brief_field_is_rejected_rather_than_ignored():
    """黙って無視すると、agent は効いていない指定を効いたと誤解する。"""
    with pytest.raises(AssetBriefError):
        parse_brief({"role": "background", "aspekt_intent": "landscape"})


def test_absent_brief_parses_to_nothing():
    assert parse_brief(None) is None


# ── ジョブ経路に効くこと ────────────────────────────────────────────────


def test_a_brief_actually_changes_the_submitted_canvas(client):
    """resolver が単体で正しくても、経路に繋がっていなければ実使用は直らない。"""
    response = client.post("/api/v1/jobs", json={
        "operation": "image.generate",
        "intent": "game title background for a fireworks festival",
        "constraints": {"asset_brief": {"role": "background"}},
        "local_only": True,
    })

    assert response.status_code == 202, response.text
    constraints = response.json()["request"]["constraints"]
    assert constraints["width"] > constraints["height"]
    assert constraints["resolved_layout"]["aspect_ratio"] == "16:9"
    assert constraints["resolved_layout"]["source"] == "role_default"


def test_an_explicit_size_in_the_request_still_wins_end_to_end(client):
    response = client.post("/api/v1/jobs", json={
        "operation": "image.generate",
        "intent": "square background on purpose",
        "constraints": {"width": 512, "height": 512, "asset_brief": {"role": "background"}},
        "local_only": True,
    })

    assert response.status_code == 202, response.text
    constraints = response.json()["request"]["constraints"]
    assert (constraints["width"], constraints["height"]) == (512, 512)
    assert constraints["resolved_layout"]["source"] == "request.constraints"


def test_a_request_without_a_brief_is_untouched(client):
    """既存の呼び出しの意味を変えない。"""
    response = client.post("/api/v1/jobs", json={
        "operation": "image.generate",
        "intent": "legacy request",
        "constraints": {"width": 256, "height": 256},
        "local_only": True,
    })

    assert response.status_code == 202, response.text
    constraints = response.json()["request"]["constraints"]
    assert constraints == {"width": 256, "height": 256}


def test_an_invalid_brief_fails_before_any_gpu_admission(client):
    response = client.post("/api/v1/jobs", json={
        "operation": "image.generate",
        "intent": "bad brief",
        "constraints": {"asset_brief": {"role": "background", "aspect_intent": "ratio"}},
        "local_only": True,
    })

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "asset_brief_invalid"


# ── 既存の散文からの決定的な抽出（AI 呼び出し 0 回） ────────────────────

# 実際に Hanabi の OpenCode 実行が送った intent。これらが 1024x1024 になった。
HANABI_BACKGROUND = (
    "Key visual background for a Japanese fireworks festival game, wide landscape "
    "composition. A calm river at night reflecting lights, a silhouetted crowd of "
    "spectators on the riverbank at the bottom, a full moon and a deep indigo night "
    "sky with stars. Leave the upper two-thirds of the sky mostly open and dark for "
    "fireworks to be overlaid."
)
HANABI_FIREWORKS = (
    "Key visual for a Japanese fireworks festival mobile game title screen. A single "
    "massive golden chrysanthemum firework bursting at the center of a deep night sky. "
    "Cinematic, luminous"
)


@pytest.mark.parametrize("intent", [HANABI_BACKGROUND, HANABI_FIREWORKS])
def test_the_real_failing_requests_now_resolve_to_landscape(intent: str):
    """実使用で 1024x1024 になった要求そのもの。AI を一度も呼ばずに直る。"""
    inferred = infer_brief_from_intent(intent)
    resolved = resolve_layout(inferred, envelope=ENVELOPE)

    assert resolved is not None
    assert resolved.width > resolved.height
    assert resolved.aspect_ratio == "16:9"


def test_a_background_is_recognised_as_a_background_not_a_key_visual():
    """実際に置かれる面を名指す語のほうが用途を正確に表す。"""
    assert infer_brief_from_intent(HANABI_BACKGROUND).role == "background"


def test_an_explicit_ratio_in_prose_is_taken_literally():
    inferred = infer_brief_from_intent("a 21:9 cinematic banner")

    assert inferred.aspect_intent == "ratio"
    assert inferred.aspect_ratio == "21:9"


def test_a_transparent_background_request_is_recognised():
    assert infer_brief_from_intent("a sprite with a transparent background").alpha_intent == "required"


def test_prose_with_no_structural_signal_infers_nothing():
    """確信が持てないときに推論すると、黙って他人の出力を変えてしまう。"""
    assert infer_brief_from_intent("a beautiful painting of a mountain at dawn") is None
    assert infer_brief_from_intent("") is None


def test_inference_never_outranks_an_explicit_request_size():
    inferred = infer_brief_from_intent(HANABI_BACKGROUND)
    resolved = resolve_layout(
        inferred, envelope=ENVELOPE, explicit_width=1024, explicit_height=1024
    )

    assert (resolved.width, resolved.height) == (1024, 1024)


# ── 予算に縛られない側（defect） ────────────────────────────────────────


def resolved_for(**brief):
    value = AssetBrief(**brief)
    return value, resolve_layout(value, envelope=ENVELOPE)


def test_a_correct_asset_reports_no_defect():
    brief, resolved = resolved_for(role="background")

    assert inspect_against_brief(
        brief, resolved, width=resolved.width, height=resolved.height, has_alpha=False
    ) == []


def test_a_wrong_canvas_is_a_defect_not_a_matter_of_taste():
    brief, resolved = resolved_for(role="background")

    defects = inspect_against_brief(brief, resolved, width=1024, height=1024, has_alpha=False)

    assert [item.code for item in defects] == ["canvas_mismatch"]
    assert defects[0].expected == f"{resolved.width}x{resolved.height}"
    assert defects[0].actual == "1024x1024"


def test_an_opaque_overlay_is_a_defect():
    """Hanabi の花火キーアートそのもの。重ね要素なのに完全不透明だった。"""
    brief, resolved = resolved_for(role="emblem")

    defects = inspect_against_brief(
        brief, resolved, width=resolved.width, height=resolved.height, has_alpha=False
    )

    assert [item.code for item in defects] == ["alpha_missing"]


def test_unexpected_transparency_is_also_reported():
    brief, resolved = resolved_for(role="background")

    defects = inspect_against_brief(
        brief, resolved, width=resolved.width, height=resolved.height, has_alpha=True
    )

    assert [item.code for item in defects] == ["alpha_unexpected"]


def test_without_a_brief_nothing_is_claimed():
    """brief が無い呼び出しに新しい失敗理由を持ち込まない。"""
    assert inspect_against_brief(None, None, width=1, height=1, has_alpha=False) == []


def test_alpha_keeps_three_states_not_two():
    """「不要」と「禁止」を混同すると、片方が誤って defect になる。"""
    assert effective_alpha_intent(AssetBrief(role="emblem")) == "required"
    assert effective_alpha_intent(AssetBrief(role="background")) == "forbidden"
    assert effective_alpha_intent(AssetBrief(role="general")) == "auto"


def test_a_dont_care_role_accepts_either_transparency():
    brief, resolved = resolved_for(role="general", aspect_intent="square")

    for has_alpha in (True, False):
        assert inspect_against_brief(
            brief, resolved, width=resolved.width, height=resolved.height, has_alpha=has_alpha
        ) == []
