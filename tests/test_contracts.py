from __future__ import annotations

import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).parents[1]


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
