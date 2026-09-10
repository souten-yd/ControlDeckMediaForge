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


@pytest.mark.parametrize("failure", [None, "single", "no_skill", "late_skill", "no_bind", "missing_clip", "duration", "loop_default",
                                     "bytes", "job", "wrong_asset", "wrong_revision", "unexpected_tool"])
def test_motion_evidence(evidence: tuple[Path, Path], failure: str | None) -> None:
    root, database = evidence
    # These fixture bytes test evidence accounting only, never Blender validity.
    for path in (root / "exports").iterdir():
        path.unlink()
    data = b"synthetic-glb"
    (root / "exports/robot.glb").write_bytes(data)
    observations = {"exit_code": 0, "director_motion": True, "project_path": str(root), "elapsed_sec": 1}
    (root / "observations.json").write_text(json.dumps(observations))
    events: list[dict[str, Any]] = []

    def call(name: str, output: dict[str, Any], inputs: dict[str, Any] | None = None) -> None:
        events.append({"type": "tool_use", "part": {"tool": "controldeck_addons_" + name,
            "state": {"status": "completed", "input": inputs or {}, "output": json.dumps({"output": output})}}})

    events.append({"type": "tool_use", "part": {"tool": "skill", "state": {
        "status": "completed", "input": {"name": "blender-director"}, "output": "Blender Director media.scene"}}})
    call("media_capabilities", {"capabilities": []})
    operations = [{"type": "armature.create"}, {"type": "skin.bind"}] + [
        {"type": "animation.clip", "clip_id": name, "fps": 24, "frame_count": frames, "loop": True}
        for name, frames in (("idle", 48), ("arm_swing", 24))]
    call("media_scene_create", {"job_id": "create"}, {"recipe": {"operations": operations}})
    call("media_job_status", {"job_id": "create", "status": "succeeded", "result": {
        "revision": {"id": "revision", "source_asset_id": "source"}}})
    call("media_scene_snapshot", {"scene_id": "scene"})
    call("media_scene_export", {"scene_id": "scene", "revision_id": "revision", "asset": {"id": "glb"}})
    receipt = {"filename": "robot.glb", "source_asset_id": "glb", "committed": True, "error": None,
               "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    call("media_pack", {"committed_count": 1, "requested_count": 1, "partial": False, "receipts": [receipt]})
    if failure == "single":
        events[-1]["part"]["state"]["output"] = json.dumps({"receipt": receipt, "media_asset_id": "glb",
            "name": "robot.glb", "sha256": receipt["sha256"], "size": receipt["size_bytes"]})
        operations[-1].pop("fps")  # Current public default is valid.
    elif failure == "no_skill":
        events.pop(0)
    elif failure == "late_skill":
        events.append(events.pop(0))
    elif failure == "no_bind":
        operations.pop(1)
    elif failure == "missing_clip":
        operations.pop()
    elif failure == "duration":
        operations[-1]["frame_count"] = 48
    elif failure == "loop_default":
        operations[-1].pop("loop")
    elif failure == "bytes":
        (root / "exports/robot.glb").write_bytes(b"tampered")
    elif failure == "job":
        with sqlite3.connect(database) as db:
            db.execute("UPDATE jobs SET status='failed' WHERE id='create'")
    elif failure == "wrong_asset":
        receipt["source_asset_id"] = "image"
        events[-1]["part"]["state"]["output"] = json.dumps({"committed_count": 1, "requested_count": 1,
            "partial": False, "receipts": [receipt]})
    elif failure == "wrong_revision":
        events[-2]["part"]["state"]["output"] = json.dumps({
            "scene_id": "scene", "revision_id": "other", "asset": {"id": "glb"}})
    elif failure == "unexpected_tool":
        call("bash", {})
    (root / "events.jsonl").write_text("\n".join(json.dumps(event) for event in events))
    if failure not in (None, "single"):
        with pytest.raises(AssertionError):
            MODULE.verify(root, database)
    else:
        assert MODULE.verify(root, database)["verified"]


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


@pytest.mark.parametrize("static,motion,array", [(False, False, False), (True, False, False), (False, True, False), (False, False, True)])
def test_private_director_tool_permission(static: bool, motion: bool, array: bool) -> None:
    spec = importlib.util.spec_from_file_location(
        "opencode_flow_runner", Path(__file__).parents[1] / "scripts/3ds_opencode_flow_e2e.py")
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    payload: dict[str, Any] = {}
    runner.restrict_tools(payload, director_static=static, director_motion=motion, director_array=array)
    enabled = static or motion or array
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


@pytest.mark.parametrize("failure", [None, "world_offset", "count", "extra_object", "no_skill", "wrong_file",
                                    "material_target", "material_before_primitive"])
def test_array_delivery_evidence(evidence: tuple[Path, Path], failure: str | None) -> None:
    test_motion_evidence(evidence, None)
    root, database = evidence
    observations = json.loads((root / "observations.json").read_text())
    observations.update(director_motion=False, director_array=True)
    (root / "observations.json").write_text(json.dumps(observations))
    (root / "exports/robot.glb").rename(root / "exports/stairs.glb")
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    operations = [
        {"type": "primitive.add", "object_id": "step", "primitive": "cube", "dimensions": [.4, .8, .2]},
        {"type": "material.set", "object_id": "step"},
        {"type": "modifier.array", "object_id": "step", "count": 6, "local_offset": [1.5, 0, 1.5]},
    ]
    if failure == "world_offset": operations[-1]['local_offset'] = [.3, 0, .15]
    elif failure == "count": operations[-1]['count'] = 5
    elif failure == "extra_object": operations.append(dict(operations[0]))
    elif failure == "material_target": operations[1]['object_id'] = 'other'
    elif failure == "material_before_primitive": operations[0], operations[1] = operations[1], operations[0]
    elif failure == "no_skill": events = [event for event in events if event['part']['tool'] != 'skill']
    for event in events:
        state = event['part']['state']
        if event['part']['tool'] == 'controldeck_addons_media_scene_create':
            state['input']['recipe']['operations'] = operations
        if event['part']['tool'] == 'controldeck_addons_media_pack':
            output = json.loads(state['output'])
            output['output']['receipts'][0]['filename'] = 'robot.glb' if failure == 'wrong_file' else 'stairs.glb'
            state['output'] = json.dumps(output)
    (root / 'events.jsonl').write_text('\n'.join(json.dumps(event) for event in events) + '\n')
    if failure:
        with pytest.raises(AssertionError):
            MODULE.verify(root, database)
    else:
        assert MODULE.verify(root, database)['verified']
