from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from conftest import wait_terminal
from mediaforge.image_edit import StrictEditError
from mediaforge.outpaint import compose_outpaint, outpaint_plan, validate_outpaint


def _source(path: Path, size: tuple[int, int] = (63, 47)) -> None:
    image = Image.new("RGBA", size)
    for y in range(size[1]):
        for x in range(size[0]):
            image.putpixel((x, y), (x % 256, y % 256, (x + y) % 256, (x * 3 + y * 7) % 256))
    image.save(path, format="PNG")


def _import_source(client, size: tuple[int, int] = (320, 256)) -> str:
    image = Image.new("RGBA", size, (30, 80, 120, 190))
    encoded = io.BytesIO()
    image.save(encoded, format="PNG")
    response = client.post(
        "/api/v1/assets/import?purpose=source",
        content=encoded.getvalue(),
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _request(source_id: str, **constraints):
    return {
        "operation": "image.edit",
        "intent": "extend the scene outside the source",
        "inputs": [{"asset_id": source_id}],
        "constraints": {
            "width": 512,
            "height": 384,
            "strict_edit": True,
            "edit_mode": "outpaint",
            **constraints,
        },
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


def test_outpaint_composite_preserves_source_rgba_bit_exact(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    _source(source)
    generated = Image.new("RGBA", (96, 80), (255, 100, 40, 128))

    plan = compose_outpaint(source, generated, output, width=96, height=80)
    result = validate_outpaint(source, output, width=96, height=80)

    assert plan.source_box == (16, 16, 79, 63)
    assert result["source_pixel_difference"] == 0
    assert result["generated_pixels"] == 96 * 80 - 63 * 47


@pytest.mark.parametrize("target", [(48, 80), (96, 40), (63, 47)])
def test_outpaint_rejects_crop_or_unchanged_canvas(tmp_path: Path, target):
    source = tmp_path / "source.png"
    _source(source)
    with pytest.raises(StrictEditError):
        outpaint_plan(source, *target)


def test_outpaint_job_records_lineage_and_source_validator(client):
    source_id = _import_source(client)
    terminal = wait_terminal(client, client.post("/api/v1/jobs", json=_request(source_id)).json()["id"])

    assert terminal["status"] == "succeeded"
    asset_id = terminal["asset_ids"][0]
    asset = client.get(f"/api/v1/assets/{asset_id}").json()
    provenance = client.get(f"/api/v1/assets/{asset_id}/provenance").json()
    assert asset["width"] == 512 and asset["height"] == 384
    assert asset["parent_asset_ids"] == [source_id]
    validator = next(item for item in provenance["validation"] if item["validator"] == "image.outpaint.source_pixel_diff")
    assert validator["source_pixel_difference"] == 0
    assert validator["source_box"] == [96, 64, 416, 320]
    validate_outpaint(
        client.app.state.store.asset_path(source_id),
        client.app.state.store.asset_path(asset_id),
        width=512,
        height=384,
    )


def test_outpaint_invariant_failure_never_registers_asset(client):
    source_id = _import_source(client)
    created = client.post(
        "/api/v1/jobs",
        json=_request(source_id, _fake_outpaint_violation=True),
    ).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "outpaint_invariant_failed"
    assert terminal["asset_ids"] == []


@pytest.mark.parametrize(
    "constraints",
    [
        {"strict_edit": False},
        {"editable_mask_asset_id": "asset_" + "f" * 32},
        {"width": 511},
        {"width": 256},
        {"height": 128},
    ],
)
def test_outpaint_invalid_constraints_fail_before_worker(client, constraints):
    source_id = _import_source(client)
    terminal = wait_terminal(
        client,
        client.post("/api/v1/jobs", json=_request(source_id, **constraints)).json()["id"],
    )

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] in {"invalid_constraint", "invalid_dimensions"}
    assert terminal["asset_ids"] == []
