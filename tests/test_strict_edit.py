from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from conftest import wait_terminal
from mediaforge.domain import Asset, Provenance
from mediaforge.image_edit import (
    StrictEditError,
    compose_strict_edit,
    strict_edit_plan,
    validate_strict_edit,
)
from mediaforge.models import ModelDescriptor, ModelState
from mediaforge.store import Store, utc_now


def _source(path: Path, size: tuple[int, int]) -> None:
    image = Image.new("RGBA", size)
    for y in range(size[1]):
        for x in range(size[0]):
            image.putpixel((x, y), (x % 256, y % 256, (x + y) % 256, (x * 7 + y * 3) % 256))
    image.save(path, format="PNG")


def _mask(path: Path, size: tuple[int, int], box: tuple[int, int, int, int]) -> None:
    image = Image.new("RGBA", size, (0, 0, 0, 255))
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            image.putpixel((x, y), (255, 255, 255, 255))
    image.save(path, format="PNG")


@pytest.mark.parametrize("size", [(31, 23), (128, 80), (257, 193)])
def test_strict_composite_preserves_every_unmasked_rgba_pixel(tmp_path: Path, size):
    source = tmp_path / "source.png"
    mask = tmp_path / "mask.png"
    output = tmp_path / "output.png"
    box = (3, 4, min(19, size[0] - 1), min(17, size[1] - 1))
    _source(source, size)
    _mask(mask, size, box)

    patch = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (255, 80, 40, 127))
    plan = compose_strict_edit(source, mask, patch, output)
    result = validate_strict_edit(source, mask, output)

    assert plan.crop_box == box
    assert result["protected_pixel_difference"] == 0
    with Image.open(source) as original, Image.open(output) as edited, Image.open(mask) as edit_mask:
        for y in range(size[1]):
            for x in range(size[0]):
                if edit_mask.getpixel((x, y))[0] == 0:
                    assert edited.getpixel((x, y)) == original.getpixel((x, y))


@pytest.mark.parametrize("kind", ["empty", "full", "mismatch"])
def test_strict_edit_rejects_invalid_masks(tmp_path: Path, kind: str):
    source = tmp_path / "source.png"
    mask = tmp_path / "mask.png"
    _source(source, (40, 30))
    size = (41, 30) if kind == "mismatch" else (40, 30)
    color = (255, 255, 255, 255) if kind == "full" else (0, 0, 0, 255)
    Image.new("RGBA", size, color).save(mask, format="PNG")

    with pytest.raises(StrictEditError):
        strict_edit_plan(source, mask)


def _register_mask(store: Store, path: Path, asset_id: str, job_id: str) -> None:
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    now = utc_now()
    provenance_id = "prov_" + asset_id.removeprefix("asset_")
    width, height = Image.open(path).size
    asset = Asset(
        id=asset_id,
        job_id=job_id,
        parent_asset_ids=[],
        mime_type="image/png",
        width=width,
        height=height,
        size_bytes=path.stat().st_size,
        sha256=sha256,
        suggested_filename="mask.png",
        provenance_id=provenance_id,
        created_at=now,
    )
    provenance = Provenance(
        id=provenance_id,
        asset_id=asset_id,
        parent_asset_ids=[],
        operation="asset.import",
        intent="test edit mask",
        model_id="media-forge/test-fixture",
        model_version="1",
        weights_hash="sha256:" + "0" * 64,
        license="CC0-1.0",
        runtime_adapter="test-fixture",
        runtime_version="1",
        tool_versions={"media-forge": "test"},
        seed=0,
        parameters={},
        reference_asset_hashes={},
        postprocessing=[],
        validation=[],
        warnings=[],
        output_sha256=sha256,
        created_at=now,
    )
    store.register_asset(asset, provenance, path)


def _strict_request(source_id: str, mask_id: str, **extra_constraints):
    return {
        "operation": "image.edit",
        "intent": "change only the selected pixels to orange",
        "inputs": [{"asset_id": source_id}],
        "constraints": {
            "width": 96,
            "height": 64,
            "seed": 11,
            "strict_edit": True,
            "editable_mask_asset_id": mask_id,
            **extra_constraints,
        },
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


def test_strict_edit_job_records_validator_mask_hash_and_lineage(client, tmp_path: Path):
    generated = client.post("/api/v1/jobs", json={
        "operation": "image.generate",
        "intent": "strict edit base",
        "constraints": {"width": 96, "height": 64, "seed": 5},
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }).json()
    source_id = wait_terminal(client, generated["id"])["asset_ids"][0]
    mask_path = tmp_path / "mask.png"
    _mask(mask_path, (96, 64), (20, 15, 44, 38))
    mask_id = "asset_" + "a" * 32
    _register_mask(
        client.app.state.store,
        mask_path,
        mask_id,
        client.app.state.store.get_asset(source_id).job_id,
    )

    created = client.post("/api/v1/jobs", json=_strict_request(source_id, mask_id)).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "succeeded"
    edited_id = terminal["asset_ids"][0]
    asset = client.get(f"/api/v1/assets/{edited_id}").json()
    provenance = client.get(f"/api/v1/assets/{edited_id}/provenance").json()
    assert asset["parent_asset_ids"] == [source_id]
    assert provenance["parent_asset_ids"] == [source_id]
    assert set(provenance["reference_asset_hashes"]) == {source_id, mask_id}
    strict_result = next(
        item for item in provenance["validation"]
        if item["validator"] == "image.strict_edit.unmasked_pixel_diff"
    )
    assert strict_result["protected_pixel_difference"] == 0
    validate_strict_edit(
        client.app.state.store.asset_path(source_id),
        client.app.state.store.asset_path(mask_id),
        client.app.state.store.asset_path(edited_id),
    )
    second = client.post("/api/v1/jobs", json=_strict_request(edited_id, mask_id)).json()
    second_terminal = wait_terminal(client, second["id"])
    assert second_terminal["status"] == "succeeded"
    second_id = second_terminal["asset_ids"][0]
    assert client.app.state.store.get_asset(second_id).parent_asset_ids == [edited_id]
    assert client.app.state.store.get_asset(edited_id).parent_asset_ids == [source_id]


def test_strict_edit_invariant_failure_never_registers_success(client, tmp_path: Path):
    generated = client.post("/api/v1/jobs", json={
        "operation": "image.generate",
        "intent": "strict failure base",
        "constraints": {"width": 96, "height": 64},
        "output": {"format": "png", "count": 1},
    }).json()
    source_id = wait_terminal(client, generated["id"])["asset_ids"][0]
    mask_path = tmp_path / "mask.png"
    _mask(mask_path, (96, 64), (20, 15, 44, 38))
    mask_id = "asset_" + "b" * 32
    _register_mask(
        client.app.state.store,
        mask_path,
        mask_id,
        client.app.state.store.get_asset(source_id).job_id,
    )

    created = client.post(
        "/api/v1/jobs",
        json=_strict_request(source_id, mask_id, _fake_strict_violation=True),
    ).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "strict_edit_invariant_failed"
    assert terminal["asset_ids"] == []


def test_public_import_api_feeds_strict_edit_without_accepting_paths(client):
    source = Image.new("RGBA", (96, 64), (20, 40, 80, 255))
    source_bytes = io.BytesIO()
    source.save(source_bytes, format="PNG")
    imported_source = client.post(
        "/api/v1/assets/import?purpose=source",
        content=source_bytes.getvalue(),
        headers={"content-type": "image/png"},
    )
    mask = Image.new("RGBA", (96, 64), (0, 0, 0, 255))
    for y in range(20, 40):
        for x in range(30, 60):
            mask.putpixel((x, y), (255, 255, 255, 255))
    mask_bytes = io.BytesIO()
    mask.save(mask_bytes, format="PNG")
    imported_mask = client.post(
        "/api/v1/assets/import?purpose=edit_mask",
        content=mask_bytes.getvalue(),
        headers={"content-type": "image/png"},
    )

    assert imported_source.status_code == 201 and imported_mask.status_code == 201
    source_asset = imported_source.json()
    mask_asset = imported_mask.json()
    assert source_asset["mime_type"] == "image/png"
    assert mask_asset["mime_type"] == "image/png"
    provenance = client.get(f"/api/v1/assets/{source_asset['id']}/provenance").json()
    assert provenance["operation"] == "asset.import"
    assert provenance["license"] == "user-provided"
    assert "path" not in str(provenance).lower()

    created = client.post(
        "/api/v1/jobs",
        json=_strict_request(source_asset["id"], mask_asset["id"]),
    ).json()
    terminal = wait_terminal(client, created["id"])
    assert terminal["status"] == "succeeded"
    result_id = terminal["asset_ids"][0]
    validate_strict_edit(
        client.app.state.store.asset_path(source_asset["id"]),
        client.app.state.store.asset_path(mask_asset["id"]),
        client.app.state.store.asset_path(result_id),
    )


def test_import_api_rejects_non_image_without_persisting_asset(client):
    before = len(client.get("/api/v1/assets").json()["items"])
    response = client.post(
        "/api/v1/assets/import?purpose=source",
        content=b"not an image",
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_image_import"
    assert len(client.get("/api/v1/assets").json()["items"]) == before


def test_installed_model_without_edit_capability_fails_instead_of_using_fake(client, monkeypatch):
    source = Image.new("RGBA", (96, 64), (20, 40, 80, 255))
    encoded = io.BytesIO()
    source.save(encoded, format="PNG")
    source_id = client.post(
        "/api/v1/assets/import?purpose=source",
        content=encoded.getvalue(),
        headers={"content-type": "image/png"},
    ).json()["id"]
    installed = ModelDescriptor(
        model_id="owner/text-only",
        family="test",
        version="1",
        revision="d" * 40,
        weights_hash="sha256:" + "e" * 64,
        license="Apache-2.0",
        runtime_adapter="test",
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm",),
        state=ModelState.AVAILABLE,
        policy_rank={"auto": 1},
        required_files=("config.json",),
        weights=(),
        installed=True,
        healthy=True,
    )

    class Registry:
        @staticmethod
        def all():
            return [installed]

    monkeypatch.setattr("mediaforge.jobs.ModelRegistry.load", lambda *_args, **_kwargs: Registry())
    created = client.post("/api/v1/jobs", json={
        "operation": "image.edit",
        "intent": "edit without an installed editing capability",
        "inputs": [{"asset_id": source_id}],
        "constraints": {"width": 96, "height": 64},
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "capability_unavailable"
    assert terminal["asset_ids"] == []


@pytest.mark.parametrize(
    "constraints",
    [
        {"edit_mode": "unknown"},
        {"edit_mode": "variation", "strict_edit": True},
        {"edit_mode": "inpaint", "strict_edit": False},
        {"strict_edit": False, "editable_mask_asset_id": "asset_" + "f" * 32},
    ],
)
def test_edit_mode_combinations_fail_explicitly(client, constraints):
    source = Image.new("RGBA", (96, 64), (20, 40, 80, 255))
    encoded = io.BytesIO()
    source.save(encoded, format="PNG")
    source_id = client.post(
        "/api/v1/assets/import?purpose=source",
        content=encoded.getvalue(),
        headers={"content-type": "image/png"},
    ).json()["id"]
    created = client.post("/api/v1/jobs", json={
        "operation": "image.edit",
        "intent": "reject inconsistent edit constraints",
        "inputs": [{"asset_id": source_id}],
        "constraints": {"width": 96, "height": 64, **constraints},
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "invalid_constraint"
    assert terminal["asset_ids"] == []


@pytest.mark.parametrize(
    ("suffix", "size", "color"),
    [
        ("c", (96, 64), (0, 0, 0, 255)),
        ("d", (96, 64), (255, 255, 255, 255)),
        ("e", (95, 64), (0, 0, 0, 255)),
    ],
)
def test_strict_edit_job_rejects_empty_full_and_mismatched_masks(
    client, tmp_path: Path, suffix: str, size: tuple[int, int], color: tuple[int, int, int, int]
):
    generated = client.post("/api/v1/jobs", json={
        "operation": "image.generate",
        "intent": "invalid mask base",
        "constraints": {"width": 96, "height": 64},
        "output": {"format": "png", "count": 1},
    }).json()
    source_id = wait_terminal(client, generated["id"])["asset_ids"][0]
    mask_path = tmp_path / f"mask-{suffix}.png"
    Image.new("RGBA", size, color).save(mask_path, format="PNG")
    mask_id = "asset_" + suffix * 32
    _register_mask(
        client.app.state.store,
        mask_path,
        mask_id,
        client.app.state.store.get_asset(source_id).job_id,
    )

    created = client.post("/api/v1/jobs", json=_strict_request(source_id, mask_id)).json()
    terminal = wait_terminal(client, created["id"])

    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "invalid_edit_mask"
    assert terminal["asset_ids"] == []
