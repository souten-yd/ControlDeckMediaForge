from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from conftest import wait_terminal
from mediaforge.domain import JobRequest


ROOT = Path(__file__).parents[1]


def _walk_dicts(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def test_public_schemas_are_valid_draft_2020_12():
    for path in sorted((ROOT / "schemas").glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)


def test_manifest_has_only_capability_driven_public_names():
    manifest = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
    assert manifest["api_version"] == "2"
    assert manifest["id"] == "media-forge"
    serialized = json.dumps(manifest).lower()
    assert "flux" not in serialized
    assert "qwen" not in serialized
    assert manifest["runtime"]["base_url"] == "http://127.0.0.1:9130"


def test_job_schema_does_not_require_model_id():
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))
    assert schema["required"] == ["operation", "intent"]
    jsonschema.validate({"operation": "image.generate", "intent": "a blue robot"}, schema)


def test_agent_tool_schemas_are_self_contained_for_model_decoders():
    manifest = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
    for contribution in manifest["contributions"]["agent_tools"]:
        schema = json.loads(
            (ROOT / contribution["schema_path"].removeprefix("/")).read_text(encoding="utf-8")
        )
        external_refs = [
            node["$ref"]
            for node in _walk_dicts(schema)
            if isinstance(node.get("$ref"), str) and not str(node["$ref"]).startswith("#/")
        ]
        assert external_refs == [], (
            contribution["id"],
            external_refs,
        )


def test_scene_texture_job_context_is_bounded_and_only_valid_for_image_generation(client):
    schema = json.loads((ROOT / "schemas/scene-texture-request.json").read_text(encoding="utf-8"))
    context = {
        "schema_version": "media-forge.scene-texture-request@1",
        "scene_id": "scene_" + "1" * 32,
        "source_revision_id": "revision_" + "2" * 32,
        "object_name": "Body",
        "material_slot": 0,
        "channel": "base_color",
        "uv_map": "UVMap",
    }
    jsonschema.validate(context, schema)
    job_schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))
    jsonschema.validate(
        {
            "operation": "image.generate",
            "intent": "seamless worn green painted metal",
            "constraints": {"scene_texture": context},
        },
        job_schema,
    )
    request = JobRequest(
        operation="image.generate",
        intent="seamless worn green painted metal",
        constraints={"scene_texture": context},
    )
    assert request.constraints["scene_texture"] == context
    response = client.post("/api/v1/jobs", json=request.model_dump(mode="json"))
    assert response.status_code == 202
    finished = wait_terminal(client, response.json()["id"])
    assert finished["status"] == "succeeded"
    assert finished["request"]["constraints"]["scene_texture"] == context
    assert len(finished["asset_ids"]) == 1
    with pytest.raises(ValidationError):
        JobRequest(
            operation="image.generate",
            intent="invalid",
            constraints={"scene_texture": {**context, "material_slot": -1}},
        )
    with pytest.raises(ValidationError):
        JobRequest(
            operation="media.inspect",
            intent="invalid",
            constraints={"scene_texture": context},
        )


def test_3ds7_scene_tools_are_additive_strict_and_keep_job_request_frozen():
    manifest = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
    agent_tools = manifest["contributions"]["agent_tools"]
    agent_ids = {item["id"] for item in agent_tools}
    assert {
        "media.scene.create",
        "media.scene.edit",
        "media.scene.material",
        "media.scene.snapshot",
        "media.scene.export",
        "media.job.status",
        "media.job.cancel",
    }.issubset(agent_ids)
    workflow_ids = {
        item["id"] for item in manifest["contributions"]["workflow_executors"]
    }
    assert "media.scene" in workflow_ids

    scene_schema_paths = {
        item["schema_path"]
        for item in agent_tools
        if item["id"] in {
            "media.scene.create",
            "media.scene.edit",
            "media.scene.material",
            "media.scene.snapshot",
            "media.scene.export",
            "media.job.status",
            "media.job.cancel",
        }
    }
    scene_schema_paths.add("/schemas/scene-workflow-request.json")
    assert len(scene_schema_paths) == 7
    for schema_path in scene_schema_paths:
        schema = json.loads((ROOT / schema_path.removeprefix("/")).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        references = [
            item["$ref"]
            for item in _walk_dicts(schema)
            if isinstance(item.get("$ref"), str)
        ]
        assert all(reference.startswith("#/") for reference in references)

    create_schema = json.loads(
        (ROOT / "schemas/scene-create-request.json").read_text(encoding="utf-8")
    )
    example = {
        "name": "Sword",
        "recipe": {"operations": [{
            "type": "primitive.add",
            "object_id": "blade",
            "primitive": "cube",
            "name": "Blade",
            "dimensions": [0.1, 0.02, 1.2],
        }]},
    }
    jsonschema.validate(example, create_schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"name": "unsafe", "recipe": {"operations": [{
                "type": "python.exec", "code": "import os",
            }]}},
            create_schema,
        )
    operation_properties = []
    for definition in create_schema["$defs"].values():
        if isinstance(definition, dict) and "properties" in definition:
            operation_properties.extend(definition["properties"])
    assert not {"code", "script", "operator", "path", "url"}.intersection(
        operation_properties
    )
    job_schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))
    assert not {"scene.create", "scene.edit", "scene.material"}.intersection(
        job_schema["properties"]["operation"]["enum"]
    )


def test_g7_video_contract_is_additive_and_does_not_claim_a_runtime(client):
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))
    request = {
        "operation": "video.generate",
        "intent": "a blue robot turns toward the camera",
        "output": {"format": "mp4", "count": 1},
    }
    jsonschema.validate(request, schema)
    response = client.post("/api/v1/jobs", json=request)
    assert response.status_code == 202
    job = wait_terminal(client, response.json()["id"])
    assert job["error"] == {
        "code": "capability_unavailable",
        "message": "video.generate has no measured local runtime",
    }


def test_model_catalog_matches_public_schema_without_local_path(client):
    schema = json.loads((ROOT / "schemas/model.json").read_text(encoding="utf-8"))
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    for model in response.json()["items"]:
        jsonschema.validate(model, schema)
        assert "path" not in model


def test_no_contribution_duplicates_the_navigation_entry():
    """ナビがあるのに quick action で同じ場所を出さない。

    実機の Quick Actions で「Media」と「メディアを作成」が並び、
    どちらも workspace を開くだけだった。ホストが導線を持つものを
    プラグイン側で二重に宣言しない。
    """
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).parents[1] / "addon.json").read_text(encoding="utf-8"))
    contributions = manifest["contributions"]
    assert "quick_actions" not in contributions, "navigation と重複する quick action を宣言しない"
    assert contributions["navigation"], "ナビゲーションは残す"
    # command palette から呼ぶ command は残す（別の導線であり重複ではない）
    assert contributions["commands"], "command は残す"


# ── G4H A2: agent へ届く指針 ────────────────────────────────────────────

# 指針が届く経路は JSON Schema の description である。どの agent harness でも
# 提示されるので、OpenCode 専用の分岐を作らずに済む。


def test_the_request_schema_tells_agents_to_describe_purpose_not_craft_prompts():
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))

    assert "asset_brief" in schema["properties"]["constraints"]["properties"]
    assert "assetBrief" in schema["$defs"]
    top = schema["description"].lower()
    assert "for" in top and "model" in top


def test_the_request_schema_warns_that_adjectives_do_not_set_geometry():
    """実使用の失敗そのものを、契約の説明文に残す。"""
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))

    assert "square" in schema["properties"]["intent"]["description"]


def test_the_request_schema_steers_agents_to_automatic_model_selection():
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))

    assert "auto" in schema["properties"]["model_policy"]["description"]


def test_the_brief_explains_when_transparency_is_required():
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))
    alpha = schema["$defs"]["assetBrief"]["properties"]["alpha_intent"]["description"]

    assert "over something else" in alpha


def test_the_qa_description_separates_budget_from_correctness():
    """予算が必要な修正まで縛ると誤解させない。"""
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))
    qa = schema["$defs"]["qa"]["description"]

    assert "regardless of this budget" in qa


def test_the_placement_schema_tells_agents_to_request_the_grant_late():
    schema = json.loads((ROOT / "schemas/project-asset-placement.json").read_text(encoding="utf-8"))

    assert "immediately before placing" in schema["description"]
    assert "expire" in schema["description"]
    assert {"asset_id", "output_grant_id", "filename", "items"}.issubset(
        schema["properties"]
    )


def test_placement_schema_keeps_single_and_batch_inputs_exclusive():
    schema = json.loads((ROOT / "schemas/project-asset-placement.json").read_text(encoding="utf-8"))
    asset_id = "asset_" + "1" * 32
    grant_id = "grant:acceptance"
    jsonschema.validate(
        {"asset_id": asset_id, "output_grant_id": grant_id, "filename": "asset.glb"},
        schema,
    )
    jsonschema.validate(
        {"output_grant_id": grant_id, "items": [{"asset_id": asset_id}]},
        schema,
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"asset_id": asset_id, "output_grant_id": grant_id, "items": [{"asset_id": asset_id}]},
            schema,
        )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"output_grant_id": grant_id, "filename": "asset.glb", "items": [{"asset_id": asset_id}]},
            schema,
        )


def test_every_schema_example_validates_against_its_own_schema():
    """例が古びて嘘になるのを防ぐ。"""
    import jsonschema

    for name in ("job-request.json", "project-asset-placement.json"):
        schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        for example in schema.get("examples", []):
            jsonschema.Draft202012Validator(schema).validate(example)


def test_the_brief_examples_are_accepted_by_the_running_service(client):
    """説明文だけ正しくても、実サービスが受理しなければ意味がない。"""
    schema = json.loads((ROOT / "schemas/job-request.json").read_text(encoding="utf-8"))

    for example in schema["examples"]:
        response = client.post("/api/v1/jobs", json=example)
        assert response.status_code == 202, response.text
