from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import time
import zipfile

import jsonschema
from PIL import Image

from conftest import wait_terminal
from mediaforge import blender_compile
from mediaforge.blender_compile import compile_project_package
from mediaforge.blender_compile import BlenderCompileCanceled, BlenderCompileError
from test_glb_import import glb_bytes


async def fake_blender(job_root: Path, _request: Path, _cancel) -> dict:
    source = job_root / "source.glb"
    output = job_root / "asset.glb"
    preview = job_root / "preview.png"
    output.write_bytes(source.read_bytes())
    Image.new("RGBA", (32, 32), (48, 96, 144, 255)).save(preview, format="PNG", compress_level=9)
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
        "constraints": {},
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
    assert hashes[0] == hashes[1]
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
    assert terminal["error"]["code"] == "unsupported_pack_profile"


def test_trusted_worker_contract_has_no_expression_shell_or_free_script_argument() -> None:
    core = Path("backend/mediaforge/blender_compile.py").read_text(encoding="utf-8")
    worker = Path("worker_packs/blender/compile_asset.py").read_text(encoding="utf-8")
    assert "--python-expr" not in core + worker
    assert "shell=True" not in core + worker
    assert 'choices=("request.json",)' in worker and 'choices=("result.json",)' in worker


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

    async def failed(_root: Path, _request: Path, _cancel) -> dict:
        raise BlenderCompileError("bounded worker failure")

    monkeypatch.setattr(blender_compile, "_run_blender", failed)
    failed_job = wait_terminal(client, client.post("/api/v1/jobs", json=request).json()["id"])
    assert failed_job["error"]["code"] == "blender_compile_failed"
    assert failed_job["asset_ids"] == []

    async def canceled(_root: Path, _request: Path, cancel_requested) -> dict:
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
