from __future__ import annotations

import json
from pathlib import Path

import pytest

from mediaforge.creative import CreativeCompiler, CreativeSpec, CreativeValidationError
from mediaforge.domain import JobRequest


ROOT = Path(__file__).parents[1]
TEMPLATES = ROOT / "creative/templates.json"
AVAILABLE = {
    "image.text_to_image": {"state": "available"},
    "image.single_reference_edit": {"state": "available"},
    "image.multi_reference_edit": {"state": "available"},
}


def request(*, policy: str = "auto", model_id: str | None = None) -> JobRequest:
    return JobRequest(
        operation="image.generate",
        intent="A friendly character",
        constraints={"width": 512, "height": 512},
        model_policy=policy,
        model_id=model_id,
    )


def test_empty_creative_spec_preserves_the_exact_request():
    compiler = CreativeCompiler.load(TEMPLATES)
    original = request()
    result = compiler.compile(original, CreativeSpec(), capabilities=AVAILABLE)
    assert result.request.model_dump(mode="json") == original.model_dump(mode="json")
    assert result.plan["active"] is False
    assert "creative_plan" not in result.request.constraints


@pytest.mark.parametrize(
    ("field", "identifier"),
    [
        ("domain", "anime"),
        ("scene", "standing_intro"),
        ("pose", "wave"),
        ("composition", "full_body_center"),
        ("camera", "eye_level"),
        ("variation", "expression"),
    ],
)
def test_each_template_family_compiles_deterministically(field: str, identifier: str):
    compiler = CreativeCompiler.load(TEMPLATES)
    payload: dict[str, object]
    if field == "domain":
        payload = {field: identifier}
    elif field == "variation":
        payload = {field: {"axis": identifier}}
    else:
        payload = {field: {"preset": identifier}}
    spec = CreativeSpec.model_validate(payload)
    first = compiler.compile(request(), spec, capabilities=AVAILABLE, envelope={"max_side": 2048})
    second = compiler.compile(request(), spec, capabilities=AVAILABLE, envelope={"max_side": 2048})
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.plan[field]["id"] == identifier
    assert first.request.constraints["creative_plan"] == first.plan
    assert "sampler" not in first.request.intent.lower()


def test_invalid_scene_pose_combination_is_a_user_facing_problem():
    compiler = CreativeCompiler.load(TEMPLATES)
    spec = CreativeSpec.model_validate({
        "scene": {"preset": "coding_at_desk"},
        "pose": {"preset": "walking"},
    })
    with pytest.raises(CreativeValidationError, match="組み合わせられません") as error:
        compiler.compile(request(), spec, capabilities=AVAILABLE)
    assert (error.value.code, error.value.field) == ("creative_combination_invalid", "pose")


def test_unavailable_capability_is_not_compiled_as_available():
    compiler = CreativeCompiler.load(TEMPLATES)
    with pytest.raises(CreativeValidationError, match="いま使えません") as error:
        compiler.compile(
            request(),
            CreativeSpec.model_validate({"pose": {"preset": "wave"}}),
            capabilities={"image.text_to_image": {"state": "unavailable"}},
        )
    assert error.value.code == "creative_capability_unavailable"


def test_compiler_never_forces_model_id_and_preserves_manual_pin():
    compiler = CreativeCompiler.load(TEMPLATES)
    spec = CreativeSpec.model_validate({"composition": {"preset": "poster"}})
    automatic = compiler.compile(request(), spec, capabilities=AVAILABLE).request
    manual = compiler.compile(
        request(policy="manual", model_id="owner/model"), spec, capabilities=AVAILABLE
    ).request
    assert (automatic.model_policy, automatic.model_id) == ("auto", None)
    assert (manual.model_policy, manual.model_id) == ("manual", "owner/model")


def test_reference_roles_must_name_existing_request_inputs():
    compiler = CreativeCompiler.load(TEMPLATES)
    spec = CreativeSpec.model_validate({
        "reference_roles": [{"asset_id": "asset_" + "a" * 32, "role": "identity"}],
    })
    with pytest.raises(CreativeValidationError) as error:
        compiler.compile(request(), spec, capabilities=AVAILABLE)
    assert error.value.code == "creative_reference_not_in_request"


def test_profile_reference_roles_use_resolved_ids_and_envelope():
    compiler = CreativeCompiler.load(TEMPLATES)
    profile_asset = "asset_" + "b" * 32
    spec = CreativeSpec.model_validate({
        "reference_roles": [{"asset_id": profile_asset, "role": "pose", "strength": 1.0}],
    })
    envelope = {
        "max_reference_assets": 4,
        "reference_roles": ["identity", "style", "pose", "composition"],
        "supports_reference_strength": False,
    }
    result = compiler.compile(
        request(), spec, capabilities=AVAILABLE, envelope=envelope,
        available_reference_ids={profile_asset},
    )
    assert result.plan["reference_roles"] == [
        {"asset_id": profile_asset, "role": "pose", "strength": 1.0}
    ]

    unsupported = spec.model_copy(update={
        "reference_roles": [spec.reference_roles[0].model_copy(update={"strength": 0.5})]
    })
    with pytest.raises(CreativeValidationError) as error:
        compiler.compile(
            request(), unsupported, capabilities=AVAILABLE, envelope=envelope,
            available_reference_ids={profile_asset},
        )
    assert error.value.code == "creative_reference_strength_unsupported"


def test_template_catalog_rejects_unknown_fields(tmp_path: Path):
    value = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    value["shell_command"] = "echo unsafe"
    path = tmp_path / "templates.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(CreativeValidationError, match="fields"):
        CreativeCompiler.load(path)
