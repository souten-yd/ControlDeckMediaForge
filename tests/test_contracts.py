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
