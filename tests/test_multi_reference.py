from __future__ import annotations

import io

import pytest
from PIL import Image

from conftest import wait_terminal


def _import(client, color: tuple[int, int, int, int]) -> str:
    image = Image.new("RGBA", (320, 256), color)
    encoded = io.BytesIO()
    image.save(encoded, format="PNG")
    response = client.post(
        "/api/v1/assets/import?purpose=source",
        content=encoded.getvalue(),
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _request(asset_ids: list[str], **constraints):
    return {
        "operation": "image.edit",
        "intent": "use the clothing and color references while editing the primary image",
        "inputs": [{"asset_id": asset_id} for asset_id in asset_ids],
        "constraints": {
            "width": 320,
            "height": 256,
            "strict_edit": False,
            "edit_mode": "multi_reference",
            **constraints,
        },
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


def test_multi_reference_job_keeps_primary_lineage_and_hashes_all_references(client):
    ids = [
        _import(client, (40, 80, 120, 255)),
        _import(client, (220, 90, 30, 255)),
        _import(client, (30, 180, 90, 200)),
    ]
    created = client.post("/api/v1/jobs", json=_request(ids)).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "succeeded"
    asset_id = terminal["asset_ids"][0]
    asset = client.get(f"/api/v1/assets/{asset_id}").json()
    provenance = client.get(f"/api/v1/assets/{asset_id}/provenance").json()
    assert asset["parent_asset_ids"] == [ids[0]]
    assert provenance["parent_asset_ids"] == [ids[0]]
    assert set(provenance["reference_asset_hashes"]) == set(ids)


@pytest.mark.parametrize("count", [1, 5])
def test_multi_reference_rejects_out_of_range_input_count(client, count: int):
    ids = [_import(client, (index * 20, 40, 80, 255)) for index in range(count)]
    created = client.post("/api/v1/jobs", json=_request(ids)).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "invalid_reference_count"
    assert terminal["asset_ids"] == []


def test_multi_reference_rejects_strict_combination(client):
    ids = [_import(client, (30, 60, 90, 255)), _import(client, (90, 60, 30, 255))]
    created = client.post("/api/v1/jobs", json=_request(ids, strict_edit=True)).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "invalid_constraint"
