from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from mediaforge.host.client import HostIdentity
from mediaforge.prompt_recipes import (
    H3_PROMPT_RECIPE_SOURCE_HASHES,
    H3_PROMPT_RECIPE_SOURCE_REVISION,
    H3PromptRecipe,
    PromptRecipeError,
    PromptRecipeMode,
    PromptRecipeRequest,
    PromptReference,
)


IDENTITY = HostIdentity(
    authorization="Bearer test-token",
    addon_id="media-forge",
    subject="1",
    expires_at=2**31,
    granted_capabilities=frozenset({"ai.inference"}),
)


class FakeGateway:
    def __init__(self, content: str):
        self.content = content
        self.calls: list[tuple[str, list[dict], dict]] = []

    async def complete(self, identity, capability, messages, **kwargs):
        del identity
        self.calls.append((capability, messages, kwargs))
        return type("Result", (), {"content": self.content, "capability": capability})()


def base_draft(*, description: str = "[Shot 1] A blue robot waves for six seconds.") -> str:
    return json.dumps({
        "integrated_multimodal_description": description,
        "overall_soundscape": "A quiet room with a soft mechanical movement.",
        "non_diegetic_music": "N/A",
    })


def test_t2va_recipe_uses_only_text_generate_and_renders_fixed_field_order():
    gateway = FakeGateway(base_draft())
    projected = asyncio.run(H3PromptRecipe(gateway).project(
        IDENTITY,
        PromptRecipeRequest(intent="青いロボットが手を振る", mode="t2va", duration_seconds=6),
    ))

    assert projected.source_revision == H3_PROMPT_RECIPE_SOURCE_REVISION
    assert projected.reference_labels == []
    assert projected.rendered_prompt.splitlines() == [
        "integrated_multimodal_description: [Shot 1] A blue robot waves for six seconds.",
        "overall_soundscape: A quiet room with a soft mechanical movement.",
        "non_diegetic_music: N/A",
    ]
    assert len(gateway.calls) == 1
    capability, messages, kwargs = gateway.calls[0]
    assert capability == "text.generate"
    assert "vision.analyze" not in json.dumps(gateway.calls)
    user_payload = json.loads(messages[1]["content"])
    assert user_payload == {
        "duration_seconds": 6.0,
        "intent": "青いロボットが手を振る",
        "references": [],
        "verbatim_text": [],
    }
    assert all(term not in messages[1]["content"] for term in (
        "MiniMax-AI/MiniMax-H3", "d21241f0", "skills/h3-prompt-writing", "/data1tb/",
    ))
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["schema"]["required"] == [
        "integrated_multimodal_description", "overall_soundscape", "non_diegetic_music",
    ]


@pytest.mark.parametrize(
    ("mode", "references", "expected_alignment"),
    (
        (
            "i2va",
            [PromptReference(kind="image", description="a blue robot facing front")],
            "reference_alignment: <Picture 1> is the target video's first frame at 0.00 seconds.",
        ),
        (
            "fl2va",
            [
                PromptReference(kind="image", description="robot at rest"),
                PromptReference(kind="image", description="robot waving"),
            ],
            "reference_alignment: <Picture 1> is the target video's first frame at 0.00 seconds; <Picture 2> is its last frame at 6.25 seconds.",
        ),
        (
            "l2va",
            [PromptReference(kind="image", description="robot waving")],
            "reference_alignment: <Picture 1> is the target video's last frame at 6.25 seconds.",
        ),
    ),
)
def test_keyframe_modes_render_media_forge_owned_alignment(
    mode: PromptRecipeMode, references: list[PromptReference], expected_alignment: str
):
    labels = " and ".join(
        f"<Picture {index}>" for index in range(1, len(references) + 1)
    )
    gateway = FakeGateway(base_draft(description=f"[Shot 1] Preserve {labels}."))
    projected = asyncio.run(H3PromptRecipe(gateway).project(
        IDENTITY,
        PromptRecipeRequest(
            intent="animate the supplied frame", mode=mode, duration_seconds=6.25,
            references=references,
        ),
    ))

    assert projected.rendered_prompt.startswith(expected_alignment + "\n\n")
    assert projected.reference_labels == [f"<Picture {i}>" for i in range(1, len(references) + 1)]


def test_ref2va_assigns_labels_and_preserves_six_section_order():
    gateway = FakeGateway(json.dumps({
        "subject_definitions": "<Picture 1> defines the robot; <Audio 1> defines its voice.",
        "summary": "The robot greets the viewer.",
        "retention_analysis": "Retain the shell from <Picture 1> and voice from <Audio 1>.",
        "detailed_description": "[Shot 1] <Picture 1> waves while <Audio 1> plays.",
        "overall_soundscape": "A quiet room.",
        "non_diegetic_music": "N/A",
    }))
    projected = asyncio.run(H3PromptRecipe(gateway).project(
        IDENTITY,
        PromptRecipeRequest(
            intent="make the robot greet the viewer",
            mode="ref2va",
            duration_seconds=8,
            references=[
                PromptReference(kind="image", description="blue service robot"),
                PromptReference(kind="audio", description="calm synthetic greeting voice"),
            ],
        ),
    ))

    assert projected.reference_labels == ["<Picture 1>", "<Audio 1>"]
    assert list(projected.sections) == [
        "subject_definitions", "summary", "retention_analysis", "detailed_description",
        "overall_soundscape", "non_diegetic_music",
    ]
    assert projected.rendered_prompt.splitlines()[0].startswith("subject_definitions:")


@pytest.mark.parametrize(
    "request_value",
    (
        {"intent": "x", "mode": "t2va", "duration_seconds": 3.99},
        {
            "intent": "x", "mode": "t2va", "duration_seconds": 6,
            "references": [{"kind": "image", "description": "unexpected"}],
        },
        {"intent": "x", "mode": "fl2va", "duration_seconds": 6, "references": []},
        {"intent": "x", "mode": "ref2va", "duration_seconds": 6, "references": []},
    ),
)
def test_recipe_request_is_bounded_and_mode_specific(request_value: dict):
    with pytest.raises(ValidationError):
        PromptRecipeRequest.model_validate(request_value)


def test_projection_rejects_unknown_or_missing_reference_labels():
    unknown = FakeGateway(base_draft(description="Use <Picture 2>."))
    missing = FakeGateway(base_draft(description="No reference label here."))
    request = PromptRecipeRequest(
        intent="animate", mode="i2va", duration_seconds=6,
        references=[PromptReference(kind="image", description="robot")],
    )
    for gateway in (unknown, missing):
        with pytest.raises(PromptRecipeError) as caught:
            asyncio.run(H3PromptRecipe(gateway).project(IDENTITY, request))
        assert caught.value.code == "prompt_recipe_invalid"


def test_provider_json_may_use_one_bounded_fence_but_not_surrounding_prose():
    fenced = FakeGateway(f"```json\n{base_draft()}\n```")
    projected = asyncio.run(H3PromptRecipe(fenced).project(
        IDENTITY,
        PromptRecipeRequest(intent="blue robot", mode="t2va", duration_seconds=6),
    ))
    assert projected.sections["overall_soundscape"].startswith("A quiet room")

    prose = FakeGateway(f"Here is JSON:\n```json\n{base_draft()}\n```")
    with pytest.raises(PromptRecipeError) as caught:
        asyncio.run(H3PromptRecipe(prose).project(
            IDENTITY,
            PromptRecipeRequest(intent="blue robot", mode="t2va", duration_seconds=6),
        ))
    assert caught.value.code == "prompt_recipe_invalid"


def test_verbatim_text_is_required_in_the_projected_sections():
    gateway = FakeGateway(base_draft(description="[Shot 1] The robot waves silently."))
    with pytest.raises(PromptRecipeError) as caught:
        asyncio.run(H3PromptRecipe(gateway).project(
            IDENTITY,
            PromptRecipeRequest(
                intent="robot says hello", mode="t2va", duration_seconds=6,
                verbatim_text=["こんにちは。"],
            ),
        ))
    assert caught.value.code == "prompt_recipe_invalid"


def test_pinned_recipe_hashes_cover_only_the_non_vendored_upstream_sources():
    assert H3_PROMPT_RECIPE_SOURCE_HASHES == {
        "SKILL.md": "a7000443588ca3f145e3b3fd8900f14e0325dc460bd811268fac89a9dc8e56d0",
        "references/base-en.txt": "2cfebc096a6e08370f288d468d90b60f7f9bcb938f94bf090816e910e48e75fc",
        "references/ref-en.txt": "1e574f356716ad55612247ffb7bbccbcdb484ad96599d63c7dca1af186b1fab7",
    }
