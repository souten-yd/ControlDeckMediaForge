from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import struct

import jsonschema
import pytest
from PIL import Image

from mediaforge.glb import BIN_CHUNK, JSON_CHUNK, GlbValidationError, validate_glb, validate_glb_path
from test_host_execution import host_client
from test_workspace_transport import call


ROOT = Path(__file__).parents[1]


def glb_bytes(document: dict | None = None, binary: bytes | None = None) -> bytes:
    if document is None:
        document = {
            "asset": {"version": "2.0", "generator": "Media Forge generated test fixture"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": 5126,
                    "count": 3,
                    "type": "VEC3",
                    "min": [0.0, 0.0, 0.0],
                    "max": [1.0, 1.0, 0.0],
                },
                {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
            ],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962},
                {"buffer": 0, "byteOffset": 36, "byteLength": 6, "target": 34963},
            ],
            "buffers": [{"byteLength": 42}],
        }
    if binary is None:
        binary = struct.pack("<9f3H", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 2)
    json_content = json.dumps(document, separators=(",", ":"), allow_nan=False).encode("utf-8")
    json_content += b" " * (-len(json_content) % 4)
    binary += b"\0" * (-len(binary) % 4)
    chunks = struct.pack("<II", len(json_content), JSON_CHUNK) + json_content
    if binary:
        chunks += struct.pack("<II", len(binary), BIN_CHUNK) + binary
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def test_generated_triangle_glb_passes_bounded_independent_validation() -> None:
    content = glb_bytes()
    facts = validate_glb(content)

    assert facts["validation_version"] == "1.1.0"
    assert facts["counts"] == {
        "scenes": 1,
        "nodes": 1,
        "meshes": 1,
        "materials": 0,
        "images": 0,
        "textures": 0,
        "samplers": 0,
        "accessors": 2,
        "bufferViews": 2,
        "buffers": 1,
        "skins": 0,
        "animations": 0,
        "cameras": 0,
        "primitives": 1,
    }


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value[:11], "header is truncated"),
        (lambda value: value[:8] + struct.pack("<I", len(value) + 4) + value[12:], "declared length differs"),
        (lambda value: value[:12] + struct.pack("<I", len(value)) + value[16:], "chunk escapes"),
    ],
)
def test_glb_rejects_truncated_or_escaping_binary(mutate, message: str) -> None:
    with pytest.raises(GlbValidationError, match=message):
        validate_glb(mutate(glb_bytes()))


def test_glb_rejects_external_uri_unknown_required_extension_and_oversized_count() -> None:
    cases = [
        ({"buffers": [{"byteLength": 42, "uri": "outside.bin"}]}, "external buffer URI"),
        (
            {"extensionsUsed": ["VENDOR_unknown"], "extensionsRequired": ["VENDOR_unknown"]},
            "required extension is not allowed",
        ),
        ({"accessors": [{"bufferView": 0, "componentType": 5126, "count": 10_000_001, "type": "VEC3"}]},
         "count is outside"),
    ]
    base = json.loads(structural_document_json())
    for changes, message in cases:
        document = json.loads(json.dumps(base))
        document.update(changes)
        with pytest.raises(GlbValidationError, match=message):
            validate_glb(glb_bytes(document))


def structural_document_json() -> str:
    content = glb_bytes()
    json_length = struct.unpack_from("<I", content, 12)[0]
    return content[20 : 20 + json_length].decode("utf-8")


def json_only_glb(json_content: bytes) -> bytes:
    json_content += b" " * (-len(json_content) % 4)
    chunk = struct.pack("<II", len(json_content), JSON_CHUNK) + json_content
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk


def test_glb_path_rejects_symlink_even_when_target_is_inside_allowed_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "triangle.glb"
    target.write_bytes(glb_bytes())
    link = root / "link.glb"
    link.symlink_to(target)

    assert validate_glb_path(target, root)["counts"]["meshes"] == 1
    with pytest.raises(GlbValidationError, match="not a regular file"):
        validate_glb_path(link, root)


def test_glb_rejects_cyclic_node_hierarchy() -> None:
    document = {
        "asset": {"version": "2.0"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"children": [1]}, {"children": [0]}],
    }
    with pytest.raises(GlbValidationError, match="cycle"):
        validate_glb(glb_bytes(document, binary=b""))
    huge_integer = b'{"asset":{"version":"2.0"},"scene":' + b"9" * 5_000 + b"}"
    with pytest.raises(GlbValidationError, match="invalid UTF-8 JSON"):
        validate_glb(json_only_glb(huge_integer))


def webp_glb_parts() -> tuple[dict, bytes]:
    document = json.loads(structural_document_json())
    image = io.BytesIO()
    Image.new("RGBA", (2, 2), (40, 120, 200, 128)).save(image, format="WEBP", lossless=True)
    binary = struct.pack("<9f3H", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 2) + b"\0\0"
    document["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(image.getvalue())})
    binary += image.getvalue()
    document["buffers"][0]["byteLength"] = len(binary)
    document["images"] = [{"bufferView": 2, "mimeType": "image/webp"}]
    document["textures"] = [{"extensions": {"EXT_texture_webp": {"source": 0}}}]
    document["materials"] = [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}]
    document["meshes"][0]["primitives"][0]["material"] = 0
    document["extensionsUsed"] = ["EXT_texture_webp"]
    document["extensionsRequired"] = ["EXT_texture_webp"]
    return document, binary


@pytest.mark.parametrize("webp", [False, True])
def test_public_glb_import_preserves_exact_bytes_and_records_bounded_provenance(client, webp: bool) -> None:
    content = glb_bytes(*webp_glb_parts()) if webp else glb_bytes()
    response = client.post(
        "/api/v1/assets/import?purpose=source",
        content=content,
        headers={"content-type": "model/gltf-binary"},
    )

    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset["mime_type"] == "model/gltf-binary"
    assert asset["width"] is None and asset["height"] is None
    assert asset["size_bytes"] == len(content)
    assert asset["sha256"] == hashlib.sha256(content).hexdigest()
    assert client.get(f"/api/v1/assets/{asset['id']}/content").content == content
    provenance = client.get(f"/api/v1/assets/{asset['id']}/provenance").json()
    assert provenance["operation"] == "asset.import"
    assert provenance["license"] == "user-provided"
    assert provenance["tool_versions"]["validator.glb"] == "1.1.0"
    assert provenance["validation"][0]["counts"]["meshes"] == 1
    assert provenance["validation"][0]["required_extensions"] == (["EXT_texture_webp"] if webp else [])
    assert "filename" not in json.dumps(provenance).lower()
    jsonschema.validate(asset, json.loads((ROOT / "schemas/asset.json").read_text(encoding="utf-8")))


def test_invalid_glb_and_edit_mask_fail_without_registering_assets(client) -> None:
    before = len(client.get("/api/v1/assets").json()["items"])
    invalid = client.post(
        "/api/v1/assets/import?purpose=source",
        content=b"not a glb",
        headers={"content-type": "model/gltf-binary"},
    )
    mask = client.post(
        "/api/v1/assets/import?purpose=edit_mask",
        content=glb_bytes(),
        headers={"content-type": "model/gltf-binary"},
    )

    assert invalid.status_code == 422 and invalid.json()["detail"]["code"] == "invalid_glb_import"
    assert mask.status_code == 422 and mask.json()["detail"]["code"] == "invalid_glb_import"
    assert len(client.get("/api/v1/assets").json()["items"]) == before


@pytest.mark.parametrize("webp", [False, True])
def test_workspace_chunk_transport_declares_glb_media_type(tmp_path: Path, webp: bool) -> None:
    client, headers, _state = host_client(tmp_path, token="valid-user")
    content = glb_bytes(*webp_glb_parts()) if webp else glb_bytes()
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        rejected = call(socket, "assets.import.begin", {
            "purpose": "source", "media_type": ["model/gltf-binary"], "size": len(content),
        })
        assert rejected["ok"] is False
        begun = call(socket, "assets.import.begin", {
            "purpose": "source", "media_type": "model/gltf-binary", "size": len(content),
        })["result"]
        encoded = base64.b64encode(content).decode("ascii")
        assert call(socket, "assets.import.chunk", {
            "upload_id": begun["upload_id"], "offset": 0, "base64": encoded,
        })["result"]["received"] == len(content)
        imported = call(socket, "assets.import.commit", {"upload_id": begun["upload_id"]})

    assert imported["ok"] is True
    assert imported["result"]["mime_type"] == "model/gltf-binary"
    assert imported["result"]["sha256"] == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("source", [None, True, -1, 1, "0"])
def test_webp_extension_rejects_invalid_image_reference(source: object) -> None:
    document, binary = webp_glb_parts()
    document["textures"][0]["extensions"]["EXT_texture_webp"]["source"] = source
    with pytest.raises(GlbValidationError, match="EXT_texture_webp.source"):
        validate_glb(glb_bytes(document, binary))


def test_webp_extension_rejects_wrong_mime_and_missing_declarations() -> None:
    for mutation, message in [
        (lambda doc: doc["images"][0].update(mimeType="image/png"), "must reference image/webp"),
        (lambda doc: doc.update(extensionsRequired=[]), "without fallback must be required"),
        (lambda doc: doc.update(extensionsRequired=[], extensionsUsed=[]), "must be declared"),
        (lambda doc: doc["textures"][0]["extensions"].update(EXT_texture_webp=None), "must be an object"),
        (lambda doc: doc["images"][0].update(uri="https://example.invalid/texture.webp"), "external image URI"),
        (lambda doc: doc["bufferViews"][2].update(byteLength=1000000), "escapes its buffer"),
    ]:
        document, binary = webp_glb_parts()
        mutation(document)
        with pytest.raises(GlbValidationError, match=message):
            validate_glb(glb_bytes(document, binary))


def test_optional_webp_with_embedded_png_fallback() -> None:
    document, binary = webp_glb_parts()
    png = io.BytesIO()
    Image.new("RGB", (2, 2), (40, 120, 200)).save(png, format="PNG")
    binary += b"\0" * (-len(binary) % 4)
    document["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(png.getvalue())})
    binary += png.getvalue()
    document["buffers"][0]["byteLength"] = len(binary)
    document["images"].append({"bufferView": 3, "mimeType": "image/png"})
    document["textures"][0]["source"] = 1
    document["extensionsRequired"] = []
    assert validate_glb(glb_bytes(document, binary))["required_extensions"] == []
