from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path

import jsonschema
import pytest
from PIL import Image, ImageDraw

from conftest import wait_terminal
from mediaforge.m5_companion import (
    CANVAS,
    EYE_SLOTS,
    MOUTH_SLOTS,
    M5CompanionError,
    profile_documents,
    validate_edit_mask,
    validate_image,
)


ROOT = Path(__file__).parents[1]


def png_bytes(layer: str, name: str) -> bytes:
    image = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if layer == "base":
        draw.ellipse((440, 80, 840, 700), fill=(224, 176, 144, 255))
    elif layer == "eyes":
        offset = EYE_SLOTS.index(name) % 3
        draw.ellipse((520 + offset, 432, 568 + offset, 464), fill=(42, 74, 110, 255))
        draw.ellipse((712 + offset, 432, 760 + offset, 464), fill=(42, 74, 110, 255))
    else:
        width = 32 + MOUTH_SLOTS.index(name) * 8
        draw.ellipse((640 - width, 560, 640 + width, 592), fill=(126, 42, 54, 255))
    value = io.BytesIO()
    image.save(value, format="PNG")
    return value.getvalue()


def import_pack_inputs(client) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    entries: list[dict[str, str]] = []
    inputs: list[dict[str, str]] = []
    for layer, names in (("base", ("front",)), ("eyes", EYE_SLOTS), ("mouth", MOUTH_SLOTS)):
        for name in names:
            response = client.post(
                "/api/v1/assets/import?purpose=source",
                content=png_bytes(layer, name),
                headers={"content-type": "image/png"},
            )
            assert response.status_code == 201
            asset_id = response.json()["id"]
            entries.append({"asset_id": asset_id, "layer": layer, "name": name})
            inputs.append({"asset_id": asset_id})
    return entries, inputs


def pack_request(entries: list[dict[str, str]], inputs: list[dict[str, str]]) -> dict:
    return {
        "operation": "asset.pack",
        "intent": "Build the Kizuna M5 companion runtime pack",
        "inputs": inputs,
        "profile": "m5.companion.pack",
        "constraints": {"pack_name": "kizuna", "entries": entries},
        "output": {"format": "zip", "count": 1},
        "local_only": True,
    }


def test_builtin_profile_catalog_is_complete_and_discoverable(client):
    documents = profile_documents()
    response = client.get("/api/v1/domain-profiles")
    assert response.status_code == 200
    assert response.json()["items"] == documents
    assert {item["id"] for item in documents} == {
        "m5.companion.base", "m5.companion.eyes", "m5.companion.mouth",
        "m5.companion.expression", "m5.companion.pose", "m5.companion.pack",
    }
    assert client.get("/api/v1/capabilities").json()["capabilities"]["asset.m5_companion_pack"] == {
        "state": "available"
    }


@pytest.mark.parametrize(
    ("layer", "name", "profile"),
    [("base", "front", "m5.companion.base"),
     ("eyes", "open_center", "m5.companion.eyes"),
     ("mouth", "rest", "m5.companion.mouth")],
)
def test_profile_validator_enforces_canvas_alpha_safe_region_and_anchors(
    tmp_path: Path, layer: str, name: str, profile: str
):
    path = tmp_path / f"{name}.png"
    path.write_bytes(png_bytes(layer, name))
    validation = validate_image(path, profile, require_pupil_anchors=layer == "eyes")[0]
    assert validation["canvas"] == [1280, 960]
    assert validation["transparent_background"] is True
    if layer == "eyes":
        assert validation["anchors"] == [[544, 448], [736, 448]]
        assert validation["measured_anchors"] == [[544.0, 448.0], [736.0, 448.0]]
    bad = Image.new("RGBA", (1280, 960), (255, 255, 255, 255))
    bad.save(path)
    with pytest.raises(M5CompanionError):
        validate_image(path, profile)


def test_m5_edit_mask_has_a_bounded_layer_and_change_area(tmp_path: Path):
    path = tmp_path / "mask.png"
    mask = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(mask).rectangle((500, 400, 800, 480), fill=(255, 255, 255, 255))
    mask.save(path)
    result = validate_edit_mask(path, "m5.companion.eyes")
    assert result["status"] == "passed" and result["change_fraction"] < 0.08
    ImageDraw.Draw(mask).rectangle((0, 0, 100, 100), fill=(255, 255, 255, 255))
    mask.save(path)
    with pytest.raises(M5CompanionError):
        validate_edit_mask(path, "m5.companion.eyes")


def test_pack_job_is_reproducible_and_contains_valid_atlas_manifest_and_fixed_names(client):
    entries, inputs = import_pack_inputs(client)
    hashes: list[str] = []
    first_content = b""
    for index in range(2):
        created = client.post("/api/v1/jobs", json=pack_request(entries, inputs))
        assert created.status_code == 202
        terminal = wait_terminal(client, created.json()["id"], timeout=15)
        assert terminal["status"] == "succeeded"
        asset_id = terminal["asset_ids"][0]
        asset = client.get(f"/api/v1/assets/{asset_id}").json()
        assert asset["mime_type"] == "application/zip" and asset["width"] is None
        hashes.append(asset["sha256"])
        content = client.get(f"/api/v1/assets/{asset_id}/content").content
        if index == 0:
            first_content = content
    assert hashes[0] == hashes[1]

    with zipfile.ZipFile(io.BytesIO(first_content)) as archive:
        names = archive.namelist()
        assert names[:2] == ["manifest.json", "atlas.png"]
        expected = {"manifest.json", "atlas.png", "base/front.png"}
        expected.update(f"eyes/{name}.png" for name in EYE_SLOTS)
        expected.update(f"mouths/{name}.png" for name in MOUTH_SLOTS)
        device_root = "companion/packs/kizuna"
        expected.update({
            f"{device_root}/manifest.json",
            f"{device_root}/base/neutral.m5a",
            f"{device_root}/eyes/neutral.m5a",
            f"{device_root}/mouth/neutral.m5a",
        })
        assert set(names) == expected
        manifest = json.loads(archive.read("manifest.json"))
        atlas = Image.open(io.BytesIO(archive.read("atlas.png")))
        assert atlas.size == (1280, 1440) and atlas.mode == "RGBA"
        device_manifest = json.loads(archive.read(f"{device_root}/manifest.json"))
        assert device_manifest["format"] == "rgb565be"
        assert device_manifest["expressions"]["neutral"] == {
            "base": "base/neutral.m5a", "eyes": "eyes/neutral.m5a",
            "mouth": "mouth/neutral.m5a", "sway": "",
        }
        expected_clips = {
            "base/neutral.m5a": (320, 240, 1),
            "eyes/neutral.m5a": (128, 44, 12),
            "mouth/neutral.m5a": (64, 40, 8),
        }
        for relative, geometry in expected_clips.items():
            content = archive.read(f"{device_root}/{relative}")
            header = struct.unpack("<IHHHHHHIB3sII", content[:32])
            assert header[0:2] == (0x3141354D, 1)
            assert (header[3], header[4], header[5]) == geometry
            assert header[7] == geometry[0] * geometry[1] * 2
            assert len(content) == 32 + header[7] * geometry[2]
    schema = json.loads((ROOT / "schemas/m5-companion-manifest.json").read_text())
    jsonschema.validate(manifest, schema)
    assert manifest["registration"]["pupil_centers"] == [[544, 448], [736, 448]]
    assert manifest["eye_slots"] == list(EYE_SLOTS)
    assert manifest["mouth_slots"] == list(MOUTH_SLOTS)
    assert manifest["device_pack"]["format"] == "m5a-rgb565be-v1"


def test_pack_fails_closed_on_missing_or_misnamed_runtime_slot(client):
    entries, inputs = import_pack_inputs(client)
    entries[-1]["name"] = "unexpected"
    created = client.post("/api/v1/jobs", json=pack_request(entries, inputs)).json()
    terminal = wait_terminal(client, created["id"])
    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "invalid_pack"
