from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mediaforge.creative_intelligence import (
    ActionStateSpec,
    CreativeDirector,
    CreativeIntelligenceError,
    PromptPlanner,
    PromptPlan,
    SubjectSpec,
    prompt_plan_to_creative_details,
    project_plan_to_creative_spec,
)
from mediaforge.host.ai import HostAIGateway
from mediaforge.host.ai import HostAIError
from mediaforge.host.client import HostApiError, HostIdentity


ROOT = Path(__file__).parents[1]


IDENTITY = HostIdentity(
    authorization="Bearer test-token",
    addon_id="media-forge",
    subject="1",
    expires_at=2**31,
    granted_capabilities=frozenset({"ai.inference"}),
)


class FakeHost:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict | None, float | None]] = []

    async def _request(self, identity, method, path, *, json=None, content=None, timeout_sec=None):
        del identity, content
        self.calls.append((method, path, json, timeout_sec))
        return self.responses.pop(0)


def test_host_ai_gateway_uses_only_capability_and_ignores_host_identity_fields():
    host = FakeHost([{
        "content": '{"ok":true}',
        "capability": "vision.analyze",
        "provider": "must-be-ignored",
        "model": "must-be-ignored",
    }])
    gateway = HostAIGateway(host)  # type: ignore[arg-type]
    result = asyncio.run(gateway.complete(
        IDENTITY,
        "vision.analyze",
        [{"role": "user", "content": "bounded fixture"}],
        response_format={"type": "json_object"},
        max_tokens=128,
    ))
    assert result.content == '{"ok":true}'
    assert result.capability == "vision.analyze"
    assert host.calls == [(
        "POST",
        "/media-forge/ai/complete",
        {
            "capability": "vision.analyze",
            "messages": [{"role": "user", "content": "bounded fixture"}],
            "temperature": 0.0,
            "max_tokens": 128,
            "timeout_seconds": 120,
            "response_format": {"type": "json_object"},
        },
        125,
    )]


def test_host_ai_capabilities_are_normalized_without_provider_metadata():
    host = FakeHost([{
        "text.generate": {"available": True, "model": "ignored"},
        "vision.analyze": {"available": False, "provider": "ignored"},
    }])
    gateway = HostAIGateway(host)  # type: ignore[arg-type]
    assert asyncio.run(gateway.capabilities(IDENTITY)) == {
        "text.generate": True,
        "vision.analyze": False,
    }


def test_addon_grants_provider_neutral_ai_and_production_has_no_ollama_transport():
    manifest = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
    assert "ai.inference" in manifest["host_capabilities"]
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend" / "mediaforge").rglob("*.py")
    )
    for forbidden in (
        "/api/chat", "/api/tags", "11434", "OllamaSemanticReviewer",
        "OllamaCreativeEvaluator", "MEDIA_FORGE_SEMANTIC_REVIEWER_URL",
        "MEDIA_FORGE_SEMANTIC_REVIEWER_MODEL", "mediaforge_semantic_review",
        "identity_match", "obvious_visual_breakage",
    ):
        assert forbidden not in production
    assert not (ROOT / "backend" / "mediaforge" / "semantic_review.py").exists()


def test_host_ai_errors_use_the_ci1_normalized_codes():
    expected = {
        ("denied", 403): "host_ai_not_granted",
        ("unavailable", 503): "vision_analyzer_unavailable",
        ("host_unreachable", 502): "host_ai_unavailable",
        ("other", 502): "host_ai_unavailable",
    }
    for (code, status), normalized in expected.items():
        error = HostAIGateway._normalize_host_error(
            HostApiError(code, "failure", status_code=status), capability="vision.analyze"
        )
        assert isinstance(error, HostAIError)
        assert error.code == normalized


class FakeGateway:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    async def complete(self, identity, capability, messages, **kwargs):
        del identity
        self.calls.append((capability, messages, kwargs))
        return type("Result", (), {"content": self.content, "capability": capability})()


def test_prompt_planner_preserves_original_intent_and_marks_non_user_additions():
    value = PromptPlan(
        original_intent="model tried to replace this",
        mode="art_direct",
        subject=SubjectSpec(kind="vehicle", appearance_traits=["red sports car"]),
        primary_action=ActionStateSpec(action="drifting", orientation="front three-quarter"),
        scene="rainy mountain road at night",
        composition="vehicle low in frame",
        camera="low angle",
        hard_constraints=["red sports car", "rainy mountain road", "drifting"],
        optional_suggestions=["tire spray", "wet-road reflections"],
        assumptions=["night is inferred from mood"],
    )
    gateway = FakeGateway(json.dumps(value.model_dump(mode="json")))
    planner = PromptPlanner(gateway)  # type: ignore[arg-type]
    plan = asyncio.run(planner.plan(
        IDENTITY,
        "赤いスポーツカーが雨の峠をドリフトしている",
        mode="refine",
    ))
    assert plan.original_intent == "赤いスポーツカーが雨の峠をドリフトしている"
    assert plan.mode == "refine"
    assert plan.subject.kind == "vehicle"
    assert plan.primary_action.action == "drifting"
    assert plan.optional_suggestions == ["tire spray", "wet-road reflections"]
    assert gateway.calls[0][0] == "text.generate"
    assert gateway.calls[0][2]["response_format"]["type"] == "json_schema"
    response_schema = gateway.calls[0][2]["response_format"]["schema"]
    assert response_schema["required"] == list(response_schema["properties"])
    assert response_schema["$defs"]["ActionStateSpec"]["required"] == list(
        response_schema["$defs"]["ActionStateSpec"]["properties"]
    )


def test_prompt_planner_original_mode_never_calls_ai():
    gateway = FakeGateway("this must not be used")
    planner = PromptPlanner(gateway)  # type: ignore[arg-type]
    plan = asyncio.run(planner.plan(IDENTITY, "blue robot on a desk", mode="original"))
    assert plan.original_intent == "blue robot on a desk"
    assert plan.mode == "original"
    assert gateway.calls == []


def test_prompt_planner_rejects_malformed_host_json_without_changing_intent():
    planner = PromptPlanner(FakeGateway("not-json"))  # type: ignore[arg-type]
    with pytest.raises(CreativeIntelligenceError) as caught:
        asyncio.run(planner.plan(IDENTITY, "small orange robot", mode="refine"))
    assert caught.value.code == "prompt_plan_invalid"


def test_prompt_planner_still_rejects_unknown_ai_authored_fields():
    planner = PromptPlanner(FakeGateway(json.dumps({"provider_model": "must not pass"})))  # type: ignore[arg-type]
    with pytest.raises(CreativeIntelligenceError) as caught:
        asyncio.run(planner.plan(IDENTITY, "small orange robot", mode="refine"))
    assert caught.value.code == "prompt_plan_invalid"


def test_prompt_planner_rejects_content_free_default_object():
    planner = PromptPlanner(FakeGateway("{}"))  # type: ignore[arg-type]
    with pytest.raises(CreativeIntelligenceError) as caught:
        asyncio.run(planner.plan(IDENTITY, "small orange robot", mode="refine"))
    assert caught.value.code == "prompt_plan_invalid"


def test_non_person_action_state_projects_into_existing_pose_details_without_requiring_person_pose():
    plan = PromptPlan(
        original_intent="a robot opens its chest panel",
        subject=SubjectSpec(kind="robot"),
        primary_action=ActionStateSpec(
            action="opening chest panel",
            state="crouched",
            orientation="three-quarter view",
        ),
    )
    details = prompt_plan_to_creative_details(plan)
    assert details["pose_details"] == "opening chest panel; crouched; three-quarter view"
    assert details["scene_details"] == ""


def test_director_projects_uncommon_non_person_action_but_preserves_manual_controls():
    authored = PromptPlan(
        original_intent="provider-owned value",
        mode="art_direct",
        subject=SubjectSpec(kind="robot", appearance_traits=["orange shell"]),
        primary_action=ActionStateSpec(
            action="opens its chest panel",
            gesture="holds a diagnostic cable in the left gripper",
            gaze="optical sensor aimed at the panel",
        ),
        scene="repair bay",
        composition="subject on the right third",
        camera="low angle",
        optional_suggestions=["soft rim light"],
    )
    gateway = FakeGateway(json.dumps(authored.model_dump(mode="json")))
    director = CreativeDirector(PromptPlanner(gateway))  # type: ignore[arg-type]
    directed = asyncio.run(director.direct(
        IDENTITY,
        "orange robot opens its chest panel",
        {
            "domain": "auto",
            "scene": {"preset": "coding_at_desk", "details": "user scene"},
            "pose": {"preset": "auto", "details": ""},
            "composition": {"preset": "full_body_center", "details": ""},
            "camera": {"preset": "auto", "details": ""},
            "variation": {"axis": "auto"},
            "reference_roles": [],
        },
        mode="refine",
    ))

    assert directed.assistance_used is True
    assert directed.plan.original_intent == "orange robot opens its chest panel"
    assert directed.creative_spec["scene"] == {"preset": "coding_at_desk", "details": "user scene"}
    assert directed.creative_spec["composition"] == {"preset": "full_body_center", "details": ""}
    assert directed.creative_spec["pose"]["preset"] == "custom"
    assert "chest panel" in directed.creative_spec["pose"]["details"]
    assert directed.creative_spec["camera"]["details"] == "low angle"
    assert gateway.calls[0][0] == "text.generate"
    assert all(call[0] != "vision.analyze" for call in gateway.calls)


class RaisingGateway:
    async def complete(self, *args, **kwargs):
        del args, kwargs
        raise HostAIError("host_ai_unavailable", "offline")


def test_director_failure_is_fail_soft_and_keeps_the_original_spec():
    director = CreativeDirector(PromptPlanner(RaisingGateway()))  # type: ignore[arg-type]
    creative = {
        "scene": {"preset": "auto", "details": ""},
        "pose": {"preset": "auto", "details": ""},
        "composition": {"preset": "auto", "details": ""},
        "camera": {"preset": "auto", "details": ""},
    }
    directed = asyncio.run(director.direct(
        IDENTITY, "a vehicle unfolds its solar panels", creative, mode="refine"
    ))
    assert directed.assistance_used is False
    assert directed.skipped_reason == "host_ai_unavailable"
    assert directed.plan.original_intent == "a vehicle unfolds its solar panels"
    assert directed.creative_spec == creative


def test_action_variations_use_one_text_request_and_exact_bounded_count():
    authored = {
        "plan": {
            "version": "provider-value",
            "original_intent": "provider-value",
            "mode": "art_direct",
            "subject": {"kind": "product"},
            "primary_action": {"action": "displaying status"},
        },
        "actions": [
            {"action": "tilted toward the viewer", "orientation": "front three-quarter"},
            {"action": "rotated to expose the rear ports", "orientation": "rear three-quarter"},
            {"action": "resting flat while the lid opens", "motion_hint": "hinge opening"},
        ],
    }
    gateway = FakeGateway(json.dumps(authored))
    director = CreativeDirector(PromptPlanner(gateway))  # type: ignore[arg-type]
    directed = asyncio.run(director.action_variations(
        IDENTITY, "show three useful views of the orange device", mode="refine", count=3,
    ))

    assert directed.assistance_used is True
    assert len(directed.actions) == 3
    assert directed.plan.original_intent == "show three useful views of the orange device"
    assert directed.plan.mode == "refine"
    assert len(gateway.calls) == 1 and gateway.calls[0][0] == "text.generate"


def test_projection_bounds_pose_compatibility_text_to_existing_schema_limit():
    plan = PromptPlan(
        original_intent="bounded",
        primary_action=ActionStateSpec(
            action="a" * 500,
            body_or_part_relations=["b" * 500],
        ),
    )
    projected, applied = project_plan_to_creative_spec(plan, {})
    assert applied == ["action_state"]
    assert projected["pose"]["preset"] == "custom"
    assert len(projected["pose"]["details"]) == 500
