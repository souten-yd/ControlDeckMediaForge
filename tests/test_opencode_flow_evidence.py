"""Verifier negative tests; synthetic fixtures are not runtime acceptance."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import pytest

SPEC = importlib.util.spec_from_file_location(
    "opencode_flow_verifier", Path(__file__).parents[1] / "scripts/3ds_verify_opencode_flow.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def evidence(tmp_path: Path) -> tuple[Path, Path]:
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "sword.glb").write_bytes(b"synthetic-glb")
    (exports / "blade.png").write_bytes(b"synthetic-png")
    digest = lambda data: hashlib.sha256(data).hexdigest()
    manifest = {
        "profile": "3d.project.glb", "source": {"sha256": digest(b"synthetic-glb")},
        "asset": {"filename": "asset.glb", "size_bytes": 1, "sha256": digest(b"g")},
        "preview": {"filename": "preview.png", "size_bytes": 1, "sha256": digest(b"p")},
        "statistics": {"triangles": 12, "bounds_max": [0.1, 0.1, 1], "bounds_min": [0, 0, 0]},
        "compiler": {"blender_version": "fixture"},
    }
    with zipfile.ZipFile(exports / "sword-project.zip", "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("asset.glb", b"g")
        archive.writestr("preview.png", b"p")
    database = tmp_path / "fixture.db"
    db = sqlite3.connect(database)
    db.execute("CREATE TABLE assets (id TEXT, metadata_json TEXT, provenance_json TEXT)")
    db.execute("CREATE TABLE jobs (id TEXT, status TEXT)")
    for job in ("create", "material", "image", "zip"):
        db.execute("INSERT INTO jobs VALUES (?, 'succeeded')", (job,))
    receipts = []
    for name, asset_id in (("sword.glb", "glb"), ("blade.png", "image"), ("sword-project.zip", "zip")):
        data = (exports / name).read_bytes()
        metadata = {"sha256": digest(data), "size_bytes": len(data)}
        provenance = {"output_sha256": digest(data), "operation": "image.generate",
                      "weights_hash": "sha256:fixture", "runtime_adapter": "fixture",
                      "model_id": "fixture", "warnings": []}
        db.execute("INSERT INTO assets VALUES (?, ?, ?)", (asset_id, json.dumps(metadata), json.dumps(provenance)))
        receipts.append({"filename": name, "source_asset_id": asset_id, "committed": True,
                         "error": None, **metadata})
    image_hash = digest(b"synthetic-png")
    db.execute("INSERT INTO assets VALUES ('source', '{}', ?)", (json.dumps({
        "parent_asset_ids": ["image"], "reference_asset_hashes": {"image": image_hash}}),))
    db.commit()
    db.close()
    revision = {"id": "revision", "source_asset_id": "source",
                "dependencies": [{"asset_id": "image", "sha256": image_hash}]}
    events: list[dict[str, Any]] = []

    def call(name: str, output: dict[str, Any]) -> None:
        events.append({"type": "tool_use", "part": {"tool": "controldeck_addons_" + name,
            "state": {"status": "completed", "output": json.dumps({"output": output})}}})

    call("media_capabilities", {"capabilities": []})
    call("media_scene_create", {"job_id": "create"})
    call("media_scene_material", {"job_id": "material"})
    for job in ("create", "material"):
        call("media_job_status", {"job_id": job, "status": "succeeded", "result": {"revision": revision}})
    for job in ("image", "zip"):
        call("media_generate", {"job_id": job, "status": "succeeded"})
    call("media_scene_export", {"scene_id": "scene", "revision_id": "revision"})
    call("media_pack", {"committed_count": 3, "requested_count": 3, "partial": False, "receipts": receipts})
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(event) for event in events))
    (tmp_path / "observations.json").write_text(json.dumps({
        "exit_code": 0, "project_path": str(tmp_path), "elapsed_sec": 1}))
    return tmp_path, database


def test_complete_evidence(evidence: tuple[Path, Path]) -> None:
    assert MODULE.verify(*evidence)["verified"]


@pytest.mark.parametrize("failure", ["bytes", "job", "missing", "unexpected_tool"])
def test_false_success_rejected(evidence: tuple[Path, Path], failure: str) -> None:
    root, database = evidence
    if failure == "bytes":
        (root / "exports/blade.png").write_bytes(b"tampered")
    elif failure == "missing":
        (root / "exports/blade.png").unlink()
    elif failure == "job":
        with sqlite3.connect(database) as db:
            db.execute("UPDATE jobs SET status='failed' WHERE id='material'")
    else:
        path = root / "events.jsonl"
        path.write_text(path.read_text().replace("controldeck_addons_media_capabilities", "bash"))
    with pytest.raises(AssertionError):
        MODULE.verify(root, database)


@pytest.mark.parametrize("failure", [None, "absent", "other", "failed", "late", "missing_operation", "local_mirror"])
def test_director_requires_actual_read_and_operations(failure: str | None) -> None:
    calls = [
        {"tool": "skill", "state": {"status": "completed", "input": {"name": "blender-director"},
                                    "output": "Blender Director media.scene.create"}},
        {"tool": "controldeck_addons_media_scene_create", "state": {"status": "completed", "input": {
            "recipe": {"operations": [{"type": "object.duplicate"},
                {"type": "modifier.mirror", "reference_object_id": "handle", "axes": ["X"]}]}}}},
    ]
    if failure == "absent":
        calls.pop(0)
    elif failure == "other":
        calls[0]["state"]["input"]["name"] = "other-director"
    elif failure == "failed":
        calls[0]["state"]["status"] = "error"
    elif failure == "late":
        calls.reverse()
    elif failure == "missing_operation":
        calls[1]["state"]["input"]["recipe"]["operations"].pop()
    elif failure == "local_mirror":
        calls[1]["state"]["input"]["recipe"]["operations"][1].pop("reference_object_id")
    if failure:
        with pytest.raises(AssertionError):
            MODULE.verify_director_static(calls)
    else:
        MODULE.verify_director_static(calls)


@pytest.mark.parametrize("enabled", [False, True])
def test_private_director_tool_permission(enabled: bool) -> None:
    spec = importlib.util.spec_from_file_location(
        "opencode_flow_runner", Path(__file__).parents[1] / "scripts/3ds_opencode_flow_e2e.py")
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    payload: dict[str, Any] = {}
    runner.restrict_tools(payload, director_static=enabled)
    if enabled:
        assert "skill" not in payload["tools"], "Legacy tools entry would override named skill permission"
    else:
        assert payload["tools"]["skill"] is False
    assert all(not value for name, value in payload["tools"].items() if name != "skill")
    assert payload["permission"]["*"] == "deny"
    if enabled:
        assert payload["permission"]["skill"] == {"*": "deny", "blender-director": "allow"}
    else:
        assert "skill" not in payload["permission"]
