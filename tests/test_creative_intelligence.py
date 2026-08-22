from __future__ import annotations

import asyncio
import json

import pytest

from mediaforge.creative_intelligence import (
    ActionStateSpec,
    CreativeIntelligenceError,
    PromptPlanner,
    PromptPlan,
    SubjectSpec,
    prompt_plan_to_creative_details,
)
from mediaforge.host.ai import HostAIGateway
from mediaforge.host.client import HostIdentity


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
        self.calls: list[tuple[str, str, dict | None]] = []

    async def _request(self, identity, method, path, *, json=None, content=None):
        del identity, content
        self.calls.append((method, path, json))
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
