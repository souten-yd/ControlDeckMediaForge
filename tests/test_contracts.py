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
