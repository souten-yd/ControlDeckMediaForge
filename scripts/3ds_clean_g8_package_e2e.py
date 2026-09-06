"""Compile the clean setup's existing scene GLB through real packaged G8 HTTP."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import time
from typing import Any
import zipfile

import httpx
from PIL import Image


def verify_package(content: bytes, asset: dict[str, Any], provenance: dict[str, Any],
                   source: dict[str, Any]) -> dict[str, Any]:
    assert asset["mime_type"] == "application/zip"
    assert len(content) == asset["size_bytes"]
    assert hashlib.sha256(content).hexdigest() == asset["sha256"]
    assert asset["parent_asset_ids"] == [source["id"]]
    assert provenance["runtime_adapter"] == "blender.project-compiler"
    assert provenance["reference_asset_hashes"] == {source["id"]: source["sha256"]}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert len(archive.infolist()) == 3 and archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest == provenance["parameters"]["manifest"]
        assert manifest["profile"] == "3d.project.glb"
        assert manifest["source"]["sha256"] == source["sha256"]
        assert manifest["source"]["size_bytes"] == source["size_bytes"]
        assert manifest["compiler"]["blender_version"] == "4.5.9"
        assert set(archive.namelist()) == {"manifest.json", manifest["asset"]["filename"], manifest["preview"]["filename"]}
        for key in ("asset", "preview"):
            item = manifest[key]
            data = archive.read(item["filename"])
            assert len(data) == item["size_bytes"]
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
        glb = archive.read(manifest["asset"]["filename"])
        assert glb[:4] == b"glTF" and int.from_bytes(glb[4:8], "little") == 2
        assert int.from_bytes(glb[8:12], "little") == len(glb)
        with Image.open(io.BytesIO(archive.read(manifest["preview"]["filename"]))) as preview:
            assert preview.format == "PNG" and min(preview.size) > 0
            preview.verify()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict[str, Any] = {"mode": "isolated_packaged_http", "events": []}
    started = time.monotonic()

    def record(stage: str, **values: Any) -> None:
        row = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        evidence["events"].append(row)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(row), flush=True)

    with httpx.Client(base_url="http://127.0.0.1:9161", timeout=10) as client:
        def get(path: str) -> Any:
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        source_id = "asset_d8548f7e2e3548359b4656b9dddc4781"
        scene_id = "scene_2642c93f480d427d920267ac790405e2"
        before = get(f"/workspace-api/scenes/{scene_id}")
        source = get(f"/api/v1/assets/{source_id}")
        response = client.get(f"/api/v1/assets/{source_id}/content")
        response.raise_for_status()
        original = response.content
        assert hashlib.sha256(original).hexdigest() == source["sha256"]
        request = {"operation": "asset.pack", "intent": "Compile the clean setup cube as a project ZIP",
                   "inputs": [{"asset_id": source_id}], "profile": "3d.project.glb",
                   "constraints": {"compile_options": {"schema_version": "3d.compile-options@1", "triangle_budget": 12}},
                   "output": {"format": "zip", "count": 1}, "local_only": True}
        response = client.post("/api/v1/jobs", json=request)
        response.raise_for_status()
        job_id = response.json()["id"]
        record("submitted", job_id=job_id, request=request)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            job = get(f"/api/v1/jobs/{job_id}")
            if job["status"] in {"succeeded", "failed", "canceled"}:
                record("terminal", job=job)
                assert job["status"] == "succeeded", job
                break
            time.sleep(0.5)
        else:
            raise AssertionError("G8 job observation deadline exceeded")
        assert len(job["asset_ids"]) == 1
        asset_id = job["asset_ids"][0]
        asset = get(f"/api/v1/assets/{asset_id}")
        provenance = get(f"/api/v1/assets/{asset_id}/provenance")
        response = client.get(f"/api/v1/assets/{asset_id}/content")
        response.raise_for_status()
        content = response.content
        manifest = verify_package(content, asset, provenance, source)
        assert manifest["statistics"]["triangles"] <= 12
        assert get(f"/workspace-api/scenes/{scene_id}") == before
        assert client.get(f"/api/v1/assets/{source_id}/content").content == original
        (args.evidence_dir / "cube-project.zip").write_bytes(content)
        record("passed", asset=asset, manifest=manifest, scene_unchanged=True, source_unchanged=True)


if __name__ == "__main__":
    main()
