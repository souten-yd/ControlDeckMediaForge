from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

import jsonschema
from PIL import Image

from conftest import wait_terminal


ROOT = Path(__file__).parents[1]


def png(color: str = "orange") -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (256, 256), color).save(buffer, format="PNG")
    return buffer.getvalue()


def job_request(**constraints) -> dict:
    return {
        "operation": "image.generate",
        "intent": "the same character waving",
        "inputs": [],
        "model_policy": "auto",
        "constraints": {"width": 256, "height": 256, "seed": 88, **constraints},
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


def create_character_profile(client, asset_ids: list[str]) -> tuple[dict, dict]:
    collection = client.post("/api/v1/reference-collections", json={
        "name": "Orange hero references",
        "description": "approved identity views",
        "asset_ids": asset_ids,
    })
    assert collection.status_code == 201
    profile = client.post("/api/v1/profiles", json={
        "kind": "character",
        "name": "Rin",
        "description": "tomboy companion",
        "reference_collection_id": collection.json()["id"],
        "character": {
            "appearance": "cute anime tomboy with short dark hair and an orange mesh streak",
            "clothing": "black hoodie with orange lining",
            "colors": ["orange", "black"],
            "distinguishing_features": ["orange mesh hair streak"],
            "negative_traits": ["long blonde hair"],
        },
        "style": None,
    })
    assert profile.status_code == 201
    return collection.json(), profile.json()


def test_collection_and_profile_match_public_schemas(client):
    imported = client.post("/api/v1/assets/import?purpose=source", content=png()).json()
    collection, profile = create_character_profile(client, [imported["id"]])
    collection_schema = json.loads((ROOT / "schemas/reference-collection.json").read_text())
    profile_schema = json.loads((ROOT / "schemas/profile.json").read_text())
    jsonschema.validate(collection, collection_schema)
    jsonschema.validate(profile, profile_schema)
    assert client.get("/api/v1/reference-collections").json()["items"] == [collection]
    assert client.get("/api/v1/profiles").json()["items"] == [profile]


def test_profile_is_snapshotted_and_hashed_in_provenance_after_deletion(client):
    imported = client.post("/api/v1/assets/import?purpose=source", content=png()).json()
    _collection, profile = create_character_profile(client, [imported["id"]])
    created = client.post(
        "/api/v1/jobs",
        json=job_request(character_profile_id=profile["id"]),
    ).json()
    terminal = wait_terminal(client, created["id"])
    assert terminal["status"] == "succeeded"
    assert client.delete(f"/api/v1/profiles/{profile['id']}").status_code == 204
    provenance = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}/provenance").json()
    snapshot = provenance["parameters"]["resolved_profiles"]["character"]
    assert snapshot["profile"]["character"]["appearance"].startswith("cute anime tomboy")
    assert snapshot["reference_collection"]["asset_ids"] == [imported["id"]]
    assert provenance["reference_asset_hashes"] == {imported["id"]: imported["sha256"]}


def test_profile_prompt_reaches_worker_but_profile_is_optional(client):
    imported = client.post("/api/v1/assets/import?purpose=source", content=png()).json()
    _collection, profile = create_character_profile(client, [imported["id"]])
    plain = wait_terminal(client, client.post("/api/v1/jobs", json=job_request()).json()["id"])
    profiled = wait_terminal(client, client.post(
        "/api/v1/jobs", json=job_request(character_profile_id=profile["id"])
    ).json()["id"])
    plain_asset = client.get(f"/api/v1/assets/{plain['asset_ids'][0]}").json()
    profiled_asset = client.get(f"/api/v1/assets/{profiled['asset_ids'][0]}").json()
    assert plain["status"] == profiled["status"] == "succeeded"
    assert plain_asset["sha256"] != profiled_asset["sha256"]


def test_profile_kind_and_reference_limits_fail_before_job_creation(client):
    asset_ids = [
        client.post("/api/v1/assets/import?purpose=source", content=png(color)).json()["id"]
        for color in ("red", "green", "blue", "orange")
    ]
    _collection, profile = create_character_profile(client, asset_ids)
    mismatch = client.post(
        "/api/v1/jobs",
        json=job_request(style_profile_id=profile["id"]),
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "profile_kind_mismatch"
    source = client.post("/api/v1/assets/import?purpose=source", content=png("purple")).json()
    limited = job_request(character_profile_id=profile["id"], edit_mode="reference", strict_edit=False)
    limited["operation"] = "image.edit"
    limited["inputs"] = [{"asset_id": source["id"]}]
    response = client.post("/api/v1/jobs", json=limited)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "profile_reference_limit"


def test_collection_cannot_be_deleted_while_profile_uses_it(client):
    imported = client.post("/api/v1/assets/import?purpose=source", content=png()).json()
    collection, _profile = create_character_profile(client, [imported["id"]])
    response = client.delete(f"/api/v1/reference-collections/{collection['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "reference_collection_in_use"


def test_collection_roles_are_additive_and_snapshotted_with_job_overrides(client):
    identity = client.post("/api/v1/assets/import?purpose=source", content=png("orange")).json()
    pose = client.post("/api/v1/assets/import?purpose=source", content=png("blue")).json()
    collection = client.post("/api/v1/reference-collections", json={
        "name": "Role-aware character", "description": "identity and pose",
        "asset_ids": [identity["id"], pose["id"]],
        "roles": {identity["id"]: "identity", pose["id"]: "pose"},
    })
    assert collection.status_code == 201
    profile = client.post("/api/v1/profiles", json={
        "kind": "character", "name": "Rin roles", "description": "",
        "reference_collection_id": collection.json()["id"],
        "character": {"appearance": "orange-haired tomboy", "clothing": "", "colors": [],
                      "distinguishing_features": [], "negative_traits": []},
        "style": None,
    }).json()
    request_value = job_request(character_profile_id=profile["id"])
    request_value["constraints"]["creative_plan"] = {
        "reference_roles": [
            {"asset_id": identity["id"], "role": "identity", "strength": 1.0},
            {"asset_id": pose["id"], "role": "composition", "strength": 1.0},
        ]
    }
    terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request_value).json()["id"])
    provenance = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}/provenance").json()
    snapshot = provenance["parameters"]["resolved_profiles"]["character"]
    assert snapshot["reference_collection"]["roles"] == {
        identity["id"]: "identity", pose["id"]: "pose",
    }
    assert provenance["parameters"]["constraints"]["creative_plan"]["reference_roles"][1]["role"] == "composition"
    assert provenance["reference_asset_hashes"] == {
        identity["id"]: identity["sha256"], pose["id"]: pose["sha256"],
    }


def test_collection_rejects_role_for_asset_outside_collection(client):
    first = client.post("/api/v1/assets/import?purpose=source", content=png("red")).json()
    second = client.post("/api/v1/assets/import?purpose=source", content=png("green")).json()
    response = client.post("/api/v1/reference-collections", json={
        "name": "invalid roles", "asset_ids": [first["id"]],
        "roles": {second["id"]: "pose"},
    })
    assert response.status_code == 422
