from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
import struct
import time
import zipfile

import jsonschema
from PIL import Image
import pytest

from conftest import wait_terminal
from mediaforge import blender_compile, thumbnails
from mediaforge.blender_compile import (
    BlenderCompileCanceled,
    BlenderCompileError,
    OPERATION_IDS,
    compile_project_package,
    parse_compile_options,
)
from mediaforge.thumbnails import ThumbnailError
from test_glb_import import glb_bytes
from test_host_execution import host_client


def generated_mesh_glb(
    positions: list[tuple[float, float, float]],
    indices: list[int],
    *,
    material: bool = False,
) -> bytes:
    position_bytes = struct.pack(f"<{len(positions) * 3}f", *(component for point in positions for component in point))
    index_component = 5123 if max(indices) <= 65_535 else 5125
    index_format = "H" if index_component == 5123 else "I"
    index_bytes = struct.pack(f"<{len(indices)}{index_format}", *indices)
    offset = len(position_bytes)
    binary = position_bytes + index_bytes
    primitive: dict = {"attributes": {"POSITION": 0}, "indices": 1}
    if material:
        primitive["material"] = 0
    document = {
        "asset": {"version": "2.0", "generator": "Media Forge generated test fixture"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [primitive]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3"},
            {"bufferView": 1, "componentType": index_component, "count": len(indices), "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": offset, "byteLength": len(index_bytes), "target": 34963},
        ],
        "buffers": [{"byteLength": len(binary)}],
    }
    if material:
        document["materials"] = [{"pbrMetallicRoughness": {"baseColorFactor": [0.2, 0.5, 0.8, 1.0]}}]
    return glb_bytes(document, binary)


def cube_glb_bytes() -> bytes:
    positions = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]
    indices = [
        0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7,
        0, 1, 5, 0, 5, 4, 2, 3, 7, 2, 7, 6,
        0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5,
    ]
    return generated_mesh_glb(positions, indices, material=True)


async def fake_blender(job_root: Path, _request: Path, _cancel, _timeout=180, **_kwargs) -> dict:
    source = job_root / "source.glb"
    output = job_root / "asset.glb"
    preview = job_root / "preview.png"
    output.write_bytes(source.read_bytes())
    Image.new("RGBA", (32, 32), (48, 96, 144, 255)).save(preview, format="PNG", compress_level=9)
    options = json.loads(_request.read_text(encoding="utf-8"))["options"]
    return {
        "schema_version": 1,
        "blender_version": "4.5.9",
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "preview_sha256": hashlib.sha256(preview.read_bytes()).hexdigest(),
        "statistics": {
            "objects": 1, "meshes": 1, "vertices": 3, "edges": 3, "triangles": 1,
            "materials": 0, "textures": 0, "bounds_min": [0, 0, 0], "bounds_max": [1, 1, 0],
        },
        "removed": {"camera_light_objects": 0, "text_blocks": 0, "drivers": 0, "custom_properties": 0},
        "warnings": [],
        "operations": [
            {"id": name, "parameters": options if name == "edit.mesh" else {}, "results": {}, "warnings": []}
            for name in OPERATION_IDS
        ],
    }


def test_compile_package_has_fixed_entries_metadata_and_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(blender_compile, "_run_blender", fake_blender)
    source = tmp_path / "source.glb"
    source.write_bytes(glb_bytes())
    packages: list[bytes] = []
    for name in ("first", "second"):
        root = tmp_path / name
        root.mkdir()
        package, manifest, validation = asyncio.run(compile_project_package(source, root))
        packages.append(package.read_bytes())
        assert manifest["schema_version"] == "media-forge.3d-project@1"
        assert manifest["statistics"]["triangles"] == 1
        assert manifest["options"]["schema_version"] == "3d.compile-options@1"
        assert {entry["validator"] for entry in validation} == {
            "glb.structure", "glb.output_structure", "image.non_empty", "image.dimensions",
            "image.mode", "image.alpha", "package.deterministic_zip",
        }
        with zipfile.ZipFile(package) as archive:
            assert archive.namelist() == ["asset.glb", "manifest.json", "preview.png"]
            assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
            assert all((info.external_attr >> 16) == 0o100600 for info in archive.infolist())
            assert json.loads(archive.read("manifest.json")) == manifest
    assert packages[0] == packages[1]


def test_project_preview_never_extracts_archive_members(tmp_path: Path) -> None:
    archive_path = tmp_path / "hostile.zip"
    preview = BytesIO()
    Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(preview, format="PNG")
    content = preview.getvalue()
    manifest = {
        "schema_version": "media-forge.3d-project@1",
        "profile": "3d.project.glb",
        "preview": {
            "filename": "preview.png",
            "mime_type": "image/png",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("asset.glb", b"glTF")
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("preview.png", content)
        archive.writestr("../escaped", b"must not be written")
    with pytest.raises(ThumbnailError):
        thumbnails.render(archive_path, 256, "application/zip")
    assert not (tmp_path.parent / "escaped").exists()


def test_runtime_capability_requires_exact_stamp_and_trusted_files(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    executable = runtime / "install" / "blender"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"#!/bin/sh\n")
    executable.chmod(0o700)
    worker = tmp_path / "compile_asset.py"
    worker.write_text("# trusted\n", encoding="utf-8")
    manifest = tmp_path / "config" / "blender-runtime.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"archive_sha256": "a" * 64}), encoding="utf-8")
    monkeypatch.setattr(blender_compile, "RUNTIME_ROOT", runtime)
    monkeypatch.setattr(blender_compile, "BLENDER_EXECUTABLE", executable)
    monkeypatch.setattr(blender_compile, "TRUSTED_WORKER", worker)
    monkeypatch.setattr(blender_compile, "REPOSITORY_ROOT", tmp_path)

    assert blender_compile.runtime_available() is False
    (runtime / ".runtime.json").write_text(json.dumps({
        "schema_version": 1,
        "version": "4.5.9",
        "archive_sha256": "a" * 64,
        "executable": "blender",
    }), encoding="utf-8")
    assert blender_compile.runtime_available() is True
    worker.unlink()
    assert blender_compile.runtime_available() is False


def test_asset_pack_3d_profile_registers_deterministic_zip_and_provenance(client, monkeypatch) -> None:
    monkeypatch.setattr(blender_compile, "_run_blender", fake_blender)
    imported = client.post(
        "/api/v1/assets/import?purpose=source",
        content=glb_bytes(),
        headers={"content-type": "model/gltf-binary"},
    ).json()
    request = {
        "operation": "asset.pack",
        "intent": "Prepare this model as a project-ready GLB",
        "inputs": [{"asset_id": imported["id"]}],
        "profile": "3d.project.glb",
        "constraints": {"compile_options": {
            "schema_version": "3d.compile-options@1",
            "apply_transforms": True,
            "repair_normals": True,
            "remove_degenerate": True,
            "merge_by_distance_m": 0.000001,
            "triangle_budget": 12,
            "lod_ratios": [0.5],
            "collision": "box",
            "materials": "basic_pbr",
            "preview": "fixed_workbench",
        }},
        "output": {"format": "zip", "count": 1},
        "local_only": True,
    }
    schema = json.loads(Path("schemas/job-request.json").read_text(encoding="utf-8"))
    jsonschema.validate(request, schema)
    hashes: list[str] = []
    for _ in range(2):
        created = client.post("/api/v1/jobs", json=request)
        assert created.status_code == 202, created.text
        terminal = wait_terminal(client, created.json()["id"])
        assert terminal["status"] == "succeeded", terminal
        asset = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}").json()
        provenance = client.get(f"/api/v1/assets/{asset['id']}/provenance").json()
        hashes.append(asset["sha256"])
        assert asset["mime_type"] == "application/zip"
        assert asset["parent_asset_ids"] == [imported["id"]]
        assert provenance["runtime_adapter"] == "blender.project-compiler"
        assert provenance["reference_asset_hashes"] == {imported["id"]: imported["sha256"]}
        assert provenance["parameters"]["manifest"]["profile"] == "3d.project.glb"
        assert provenance["parameters"]["manifest"]["options"]["collision"] == "box"
        assert provenance["postprocessing"] == list(OPERATION_IDS)
    assert hashes[0] == hashes[1]
    assert list(client.app.state.store.work_dir.iterdir()) == []


def test_3d_package_crosses_agent_library_preview_and_pack_without_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(blender_compile, "_run_blender", fake_blender)
    client, headers, state = host_client(tmp_path, token="valid-job")
    with client:
        imported = client.post(
            "/api/v1/assets/import?purpose=source",
            content=glb_bytes(),
            headers={"content-type": "model/gltf-binary"},
        ).json()
        request = {
            "operation": "asset.pack",
            "intent": "Prepare agent GLB",
            "inputs": [{"asset_id": imported["id"]}],
            "profile": "3d.project.glb",
            "constraints": {"compile_options": {"schema_version": "3d.compile-options@1"}},
            "output": {"format": "zip", "count": 1},
            "local_only": True,
        }
        generated = client.post(
            "/addon/v1/agent/generate",
            json={"input": request, "correlation": {"job_id": "host-job"}},
            headers=headers,
        )
        assert generated.status_code == 200, generated.text
        asset_id = generated.json()["asset_id"]
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({"id": "library", "method": "library.list", "params": {"limit": 20}})
            while True:
                message = socket.receive_json()
                if message.get("id") == "library":
                    break
            item = next(value for value in message["result"]["items"] if value["asset_id"] == asset_id)
            assert item["mime_type"] == "application/zip"
            assert item["preview_kind"] == "project_3d"
            assert item["suggested_filename"].endswith(".zip")
            assert base64.b64decode(item["thumbnail"]["base64"]).startswith(b"RIFF")

        standalone = client.post(
            f"/workspace-api/assets/{asset_id}/thumbnail", json={"max_side": 512}
        )
        assert standalone.status_code == 200
        assert standalone.json()["mime_type"] == "image/webp"
        placed = client.post(
            "/addon/v1/agent/pack",
            json={
                "input": {
                    "asset_id": asset_id,
                    "output_grant_id": "grant:export-1",
                    "filename": "project-ready.zip",
                },
                "correlation": {"job_id": "host-agent"},
            },
            headers=headers,
        )
    assert placed.status_code == 200, placed.text
    receipt = placed.json()
    assert receipt["mime_type"] == "application/zip"
    assert receipt["name"] == "project-ready.zip"
    assert state["outputs"]["output-1"]["content"].startswith(b"PK")
    serialized = json.dumps({"generated": generated.json(), "receipt": receipt})
    assert str(tmp_path) not in serialized and "path" not in serialized


def test_workspace_imports_glb_from_opaque_host_read_grant(tmp_path: Path) -> None:
    client, headers, state = host_client(tmp_path, token="valid-user")
    state["grant_content"] = glb_bytes()
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        socket.send_json({
            "id": "import",
            "method": "assets.import_grant",
            "params": {
                "grant_id": "grant:read-1",
                "purpose": "source",
                "media_type": "model/gltf-binary",
            },
        })
        while True:
            message = socket.receive_json()
            if message.get("id") == "import":
                break

    assert message["ok"] is True
    imported = message["result"]
    assert imported["mime_type"] == "model/gltf-binary"
    assert imported["sha256"] == hashlib.sha256(state["grant_content"]).hexdigest()
    serialized = json.dumps(imported)
    assert str(tmp_path) not in serialized and "grant:read-1" not in serialized


def test_host_cancel_reaches_cpu_only_blender_without_gpu_lease(
    tmp_path: Path, monkeypatch
) -> None:
    async def cancellable(_root: Path, _request: Path, cancel_requested, _timeout=180, **_kwargs) -> dict:
        while not cancel_requested():
            await asyncio.sleep(0.01)
        raise BlenderCompileCanceled("canceled")

    monkeypatch.setattr(blender_compile, "_run_blender", cancellable)
    client, headers, state = host_client(tmp_path, token="valid-user")
    with client:
        imported = client.post(
            "/api/v1/assets/import?purpose=source",
            content=glb_bytes(),
            headers={"content-type": "model/gltf-binary"},
        ).json()
        with client.websocket_connect("/ws", headers=headers) as socket:
            socket.send_json({
                "id": "create",
                "method": "jobs.create",
                "params": {
                    "operation": "asset.pack",
                    "intent": "Cancel the CPU-only Blender compile",
                    "inputs": [{"asset_id": imported["id"]}],
                    "profile": "3d.project.glb",
                    "constraints": {},
                    "output": {"format": "zip", "count": 1},
                },
            })
            while True:
                message = socket.receive_json()
                if message.get("id") == "create":
                    break
            job_id = message["result"]["id"]
            deadline = time.monotonic() + 2
            while client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "queued":
                assert time.monotonic() < deadline
                time.sleep(0.01)
            state["jobs"]["host-created-1"]["status"] = "canceled"
            terminal = wait_terminal(client, job_id)

    assert terminal["status"] == "canceled"
    assert terminal["asset_ids"] == []
    assert state["resource_requests"] == []
    assert list(client.app.state.store.work_dir.iterdir()) == []


def test_3d_profile_rejects_options_and_non_glb_input(client) -> None:
    imported = client.post(
        "/api/v1/assets/import?purpose=source",
        content=glb_bytes(),
        headers={"content-type": "model/gltf-binary"},
    ).json()
    request = {
        "operation": "asset.pack",
        "intent": "Compile",
        "inputs": [{"asset_id": imported["id"]}],
        "profile": "3d.project.glb",
        "constraints": {"arbitrary_operator": "bpy.ops.wm.quit_blender"},
        "output": {"format": "zip", "count": 1},
    }
    terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request).json()["id"])
    assert terminal["error"]["code"] == "invalid_compile_options"


def test_trusted_worker_contract_has_no_expression_shell_or_free_script_argument() -> None:
    core = Path("backend/mediaforge/blender_compile.py").read_text(encoding="utf-8")
    worker = Path("worker_packs/blender/compile_asset.py").read_text(encoding="utf-8")
    assert "--python-expr" not in core + worker
    assert "shell=True" not in core + worker
    assert 'choices=("request.json",)' in worker and 'choices=("result.json",)' in worker


def test_agent_placement_schema_declares_an_object_root_for_host_discovery() -> None:
    schema = json.loads(Path("schemas/project-asset-placement.json").read_text(encoding="utf-8"))
    assert schema["type"] == "object"
    assert all(branch["type"] == "object" for branch in schema["oneOf"])


@pytest.mark.parametrize(
    "value",
    [
        {"schema_version": "3d.compile-options@1", "apply_transforms": False},
        {"schema_version": "3d.compile-options@1", "lod_ratios": [0.5, 0.75]},
        {"schema_version": "3d.compile-options@1", "triangle_budget": 11},
        {"schema_version": "3d.compile-options@1", "operator": "bpy.ops.wm.quit_blender"},
    ],
)
def test_compile_options_fail_closed(value: dict) -> None:
    with pytest.raises(BlenderCompileError, match="invalid"):
        parse_compile_options({"compile_options": value})


def test_blender_failure_and_cancel_register_no_partial_package(client, monkeypatch) -> None:
    imported = client.post(
        "/api/v1/assets/import?purpose=source",
        content=glb_bytes(),
        headers={"content-type": "model/gltf-binary"},
    ).json()
    request = {
        "operation": "asset.pack",
        "intent": "Compile safely",
        "inputs": [{"asset_id": imported["id"]}],
        "profile": "3d.project.glb",
        "constraints": {},
        "output": {"format": "zip", "count": 1},
    }

    async def failed(_root: Path, _request: Path, _cancel, _timeout=180, **_kwargs) -> dict:
        raise BlenderCompileError("bounded worker failure")

    monkeypatch.setattr(blender_compile, "_run_blender", failed)
    failed_job = wait_terminal(client, client.post("/api/v1/jobs", json=request).json()["id"])
    assert failed_job["error"]["code"] == "blender_compile_failed"
    assert failed_job["asset_ids"] == []

    async def canceled(_root: Path, _request: Path, cancel_requested, _timeout=180, **_kwargs) -> dict:
        while not cancel_requested():
            await asyncio.sleep(0.01)
        raise BlenderCompileCanceled("canceled")

    monkeypatch.setattr(blender_compile, "_run_blender", canceled)
    created = client.post("/api/v1/jobs", json=request).json()
    for _ in range(100):
        if client.get(f"/api/v1/jobs/{created['id']}").json()["status"] == "running":
            break
        time.sleep(0.01)
    assert client.delete(f"/api/v1/jobs/{created['id']}").status_code == 200
    canceled_job = wait_terminal(client, created["id"])
    assert canceled_job["status"] == "canceled" and canceled_job["asset_ids"] == []
    assert list(client.app.state.store.work_dir.iterdir()) == []
