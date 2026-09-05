from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import struct
import uuid
import zipfile

from PIL import Image
import pytest

from mediaforge.asset_import import import_asset_bytes
from mediaforge.model_viewer import MODEL_CHUNK_BYTES, ModelViewerError, ModelViewerSession
from mediaforge.store import Store
from mediaforge import thumbnails
from test_glb_import import glb_bytes
from test_host_execution import host_client
from test_workspace_transport import call


def project_zip(content: bytes, *, declared_hash: str | None = None) -> bytes:
    preview = io.BytesIO()
    Image.new("RGB", (48, 48), (20, 80, 120)).save(preview, format="PNG")
    manifest = {
        "schema_version": "media-forge.3d-project@1",
        "profile": "3d.project.glb",
        "asset": {
            "filename": "asset.glb",
            "mime_type": "model/gltf-binary",
            "size_bytes": len(content),
            "sha256": declared_hash or hashlib.sha256(content).hexdigest(),
        },
    }
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("asset.glb", content)
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("preview.png", preview.getvalue())
    return result.getvalue()


def register_project(store: Store, content: bytes):
    imported = import_asset_bytes(store, glb_bytes(), purpose="source", media_type="model/gltf-binary")
    source = store.work_dir / "project.zip"
    source.write_bytes(content)
    provenance_id = f"prov_{uuid.uuid4().hex}"
    asset = imported.model_copy(update={
        "id": f"asset_{uuid.uuid4().hex}",
        "mime_type": "application/zip",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "suggested_filename": "project-ready.zip",
        "provenance_id": provenance_id,
    })
    provenance = store.get_provenance(imported.id).model_copy(update={
        "id": provenance_id,
        "asset_id": asset.id,
        "operation": "asset.pack",
        "parameters": {"profile": "3d.project.glb"},
        "output_sha256": asset.sha256,
    })
    return store.register_asset(asset, provenance, source)


def glb_with_texture(width: int, height: int) -> bytes:
    encoded = io.BytesIO()
    Image.new("RGB", (width, height), (40, 80, 120)).save(encoded, format="PNG")
    geometry = struct.pack("<9f3H", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 2)
    geometry += b"\0" * (-len(geometry) % 4)
    texture = encoded.getvalue()
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36},
            {"buffer": 0, "byteOffset": 36, "byteLength": 6},
            {"buffer": 0, "byteOffset": len(geometry), "byteLength": len(texture)},
        ],
        "buffers": [{"byteLength": len(geometry) + len(texture)}],
        "images": [{"bufferView": 2, "mimeType": "image/png"}],
    }
    return glb_bytes(document, geometry + texture)


def test_raw_glb_is_chunked_behind_an_opaque_handle_and_closed(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    content = glb_bytes()
    asset = import_asset_bytes(store, content, purpose="source", media_type="model/gltf-binary")
    session = ModelViewerSession(store)

    opened = session.open(asset.id)
    assert opened["handle"].startswith("modelview_")
    assert opened["total_bytes"] == len(content)
    assert opened["chunk_bytes"] == MODEL_CHUNK_BYTES
    assert opened["validation"]["counts"]["meshes"] == 1
    assert opened["validation"]["viewer_memory"] == {
        "texture_pixels": 0,
        "maximum_texture_side": 0,
        "estimated_gpu_bytes": len(content),
    }
    assert str(tmp_path) not in json.dumps(opened)
    piece = session.read(opened["handle"], 0, 64)
    assert base64.b64decode(piece["base64"]) == content[:64]
    assert session.close(opened["handle"]) is True
    with pytest.raises(ModelViewerError) as stale:
        session.read(opened["handle"], 0)
    assert stale.value.code == "model_viewer_handle_invalid"


def test_model_handle_count_ranges_and_texture_memory_are_bounded(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    content = glb_with_texture(32, 16)
    asset = import_asset_bytes(store, content, purpose="source", media_type="model/gltf-binary")
    session = ModelViewerSession(store)
    first = session.open(asset.id)
    second = session.open(asset.id)
    assert first["validation"]["viewer_memory"]["texture_pixels"] == 512
    with pytest.raises(ModelViewerError) as limited:
        session.open(asset.id)
    assert limited.value.code == "model_viewer_limit"
    for offset, length in ((len(content), 1), (-1, 1), (0, 0), (0, MODEL_CHUNK_BYTES + 1)):
        with pytest.raises(ModelViewerError) as ranged:
            session.read(first["handle"], offset, length)
        assert ranged.value.code == "model_viewer_range_invalid"
    session.close(second["handle"])
    session.close(first["handle"])

    oversized = glb_with_texture(8_193, 1)
    large = import_asset_bytes(store, oversized, purpose="source", media_type="model/gltf-binary")
    with pytest.raises(ModelViewerError) as memory:
        session.open(large.id)
    assert memory.value.code == "model_viewer_memory_bound"
    with pytest.raises(ModelViewerError) as missing:
        session.open("asset_" + "0" * 32)
    assert missing.value.code == "model_viewer_not_found"


def test_project_zip_is_hash_checked_staged_once_and_removed_on_cleanup(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    content = glb_bytes()
    asset = register_project(store, project_zip(content))
    session = ModelViewerSession(store)
    opened = session.open(asset.id)
    staged = list(store.work_dir.glob("workspace-model-*"))
    assert len(staged) == 1
    assert base64.b64decode(session.read(opened["handle"], 0)["base64"]) == content
    session.cleanup()
    assert not list(store.work_dir.glob("workspace-model-*"))

    bad = register_project(store, project_zip(content, declared_hash="0" * 64))
    with pytest.raises(ModelViewerError) as invalid:
        ModelViewerSession(store).open(bad.id)
    assert invalid.value.code == "model_viewer_invalid"
    assert not list(store.work_dir.glob("workspace-model-*"))


def test_browser_capture_is_bounded_and_becomes_a_grid_thumbnail(tmp_path: Path) -> None:
    cache = tmp_path / "thumbs"
    capture = io.BytesIO()
    Image.new("RGB", (320, 240), (30, 90, 140)).save(capture, format="WEBP", quality=80)
    saved = thumbnails.store_model_capture(cache, "asset_" + "3" * 32, capture.getvalue())
    assert (saved.width, saved.height) == (320, 240)
    grid = thumbnails.model_cached(cache, "asset_" + "3" * 32, 160)
    assert max(grid.width, grid.height) == 160
    assert len(grid.content) <= thumbnails.THUMBNAIL_BYTE_LIMIT
    with pytest.raises(thumbnails.ThumbnailError):
        thumbnails.store_model_capture(cache, "asset_" + "4" * 32, b"not webp")
    oversized = io.BytesIO()
    Image.new("RGB", (513, 1), (10, 20, 30)).save(oversized, format="WEBP")
    with pytest.raises(thumbnails.ThumbnailError):
        thumbnails.store_model_capture(cache, "asset_" + "5" * 32, oversized.getvalue())


def test_workspace_model_transport_filters_and_reclaims_staging(tmp_path: Path) -> None:
    client, headers, _state = host_client(tmp_path, token="valid-user")
    content = glb_bytes()
    with client:
        imported = client.post(
            "/api/v1/assets/import?purpose=source",
            content=content,
            headers={"content-type": "model/gltf-binary"},
        ).json()
        with client.websocket_connect("/ws", headers=headers) as socket:
            page = call(socket, "library.list", {"media_kind": "3d", "limit": 24})["result"]
            assert [item["asset_id"] for item in page["items"]] == [imported["id"]]
            assert page["items"][0]["preview_kind"] == "model_3d"
            opened = call(socket, "assets.model.open", {"asset_id": imported["id"]})["result"]
            received = call(socket, "assets.model.bytes", {
                "handle": opened["handle"], "offset": 0,
            })["result"]
            assert base64.b64decode(received["base64"]) == content
            assert call(socket, "assets.model.close", {"handle": opened["handle"]})["result"] == {
                "closed": True
            }
            refused = call(socket, "assets.model.bytes", {
                "handle": opened["handle"], "offset": 0,
            })
            assert refused["error"]["code"] == "model_viewer_handle_invalid"
        assert not list(client.app.state.store.work_dir.glob("workspace-model-*"))


def test_standalone_model_transport_and_opaque_module_are_served_from_the_bundle(tmp_path: Path) -> None:
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    content = glb_bytes()
    with client:
        imported = client.post(
            "/api/v1/assets/import?purpose=source",
            content=content,
            headers={"content-type": "model/gltf-binary"},
        ).json()
        module = client.get("/viewer-runtime.js?v=test", headers={"Origin": "null"})
        assert module.status_code == 200
        assert module.headers["access-control-allow-origin"] == "*"
        assert module.headers["cross-origin-resource-policy"] == "cross-origin"
        assert b"Three.js Authors" in module.content[:300]

        opened = client.post(f"/workspace-api/assets/{imported['id']}/model/open").json()
        piece = client.post(
            f"/workspace-api/models/{opened['handle']}/bytes", json={"offset": 0}
        ).json()
        assert base64.b64decode(piece["base64"]) == content
        closed = client.post(f"/workspace-api/models/{opened['handle']}/close").json()
        assert closed == {"closed": True}
        missing = client.post("/workspace-api/assets/asset_00000000000000000000000000000000/model/open")
        assert missing.status_code == 422
        assert missing.json()["detail"]["code"] == "model_viewer_not_found"
