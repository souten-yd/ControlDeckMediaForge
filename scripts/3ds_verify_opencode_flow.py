"""Read-only verification of one real OpenCode run and its installed artifacts.

No Host imports, API writes, archive extraction, or inference requests. Output is
a JSON report on stdout; input event logs and the installed DB remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Any


def verify_director_read(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Discovery and text promises are not evidence of skill/operation execution."""
    skills = [call for call in calls if call["tool"] == "skill"]
    assert skills, "No actual skill invocation"
    for call in skills:
        state = call["state"]
        assert state["status"] == "completed"
        assert state["input"] == {"name": "blender-director"}
        assert "Blender Director" in state["output"] and "media.scene" in state["output"]
    creates = [call for call in calls if call["tool"] == "controldeck_addons_media_scene_create"]
    assert len(creates) == 1, "Expected exactly one new scene"
    assert calls.index(skills[0]) < calls.index(creates[0]), "Skill must be read before creation"
    state = creates[0]["state"]
    assert state["status"] == "completed"
    return creates[0]


def verify_director_static(calls: list[dict[str, Any]]) -> None:
    state = verify_director_read(calls)["state"]
    operations = state["input"]["recipe"]["operations"]
    assert {"object.duplicate", "modifier.mirror"} <= {op["type"] for op in operations}
    assert any(op.get("reference_object_id") == "handle" and op.get("axes") == ["X"]
               for op in operations if op["type"] == "modifier.mirror"), "Guard must mirror about the handle"


def verify_array_recipe(operations: list[dict[str, Any]]) -> None:
    assert {op['type'] for op in operations} == {'primitive.add', 'material.set', 'modifier.array'}
    assert len(operations) == 3
    primitive, = [op for op in operations if op['type'] == 'primitive.add']
    array, = [op for op in operations if op['type'] == 'modifier.array']
    material, = [op for op in operations if op['type'] == 'material.set']
    assert primitive['object_id'] == array['object_id'] == material['object_id'] == 'step'
    assert primitive['primitive'] == 'cube' and primitive['dimensions'] == [.4, .8, .2]
    assert primitive.get('location', [0, 0, 0]) == [0, 0, 0]
    assert primitive.get('rotation_degrees', [0, 0, 0]) == [0, 0, 0]
    assert array['count'] == 6 and array['local_offset'] == [1.5, 0, 1.5]
    assert operations.index(primitive) < operations.index(array)
    assert operations.index(primitive) < operations.index(material)


def verify_motion(evidence_dir: Path, database: Path, *, array: bool = False) -> dict[str, Any]:
    """Check actual tool execution and delivered bytes; deformation needs Blender inspection."""
    observations = json.loads((evidence_dir / "observations.json").read_text())
    assert observations.get("director_array" if array else "director_motion") is True and observations["exit_code"] == 0
    filename = "stairs.glb" if array else "robot.glb"
    events = [json.loads(line) for line in (evidence_dir / "events.jsonl").read_text().splitlines()]
    assert not any(event.get("type") == "error" for event in events)
    calls = [event["part"] for event in events if event.get("type") == "tool_use"]
    allowed = {"skill"} | {"controldeck_addons_" + name for name in (
        "media_capabilities", "media_inspect", "media_scene_create", "media_scene_snapshot",
        "media_scene_export", "media_job_status", "media_pack", "control_deck_project_output_grant")}
    assert all(call["tool"] in allowed and call["state"]["status"] == "completed" for call in calls)
    create_call = verify_director_read(calls)
    operations = create_call["state"]["input"]["recipe"]["operations"]
    if array:
        verify_array_recipe(operations)
    else:
        assert {"armature.create", "skin.bind", "animation.clip"} <= {op["type"] for op in operations}
        clips = [op for op in operations if op["type"] == "animation.clip"]
        assert len(clips) == 2 and {op["clip_id"] for op in clips} == {"idle", "arm_swing"}
        for op in clips:
            assert op.get("fps", 24) == 24 and op["frame_count"] == (48 if op["clip_id"] == "idle" else 24)
            assert op.get("loop", False) is True, "Clip must explicitly enable loop endpoint validation"

    def outputs(name: str) -> list[dict[str, Any]]:
        result = []
        for call in calls:
            if call["tool"] == "controldeck_addons_" + name:
                value = json.loads(call["state"]["output"])
                result.append(value.get("output", value))
        return result

    assert outputs("media_capabilities") and outputs("media_scene_snapshot")
    created = outputs("media_scene_create")[0]
    terminal = next(row for row in outputs("media_job_status")
                    if row["job_id"] == created["job_id"] and row["status"] == "succeeded")
    revision = terminal["result"]["revision"]
    exported, = outputs("media_scene_export")
    assert exported["revision_id"] == revision["id"]
    placed, = outputs("media_pack")
    if "receipt" in placed:
        receipt = placed["receipt"]
        assert placed["media_asset_id"] == receipt["source_asset_id"]
        assert placed["name"] == receipt["filename"]
        assert placed["sha256"] == receipt["sha256"] and placed["size"] == receipt["size_bytes"]
    else:
        assert placed["committed_count"] == placed["requested_count"] == 1 and placed["partial"] is False
        receipt, = placed["receipts"]
    assert receipt["filename"] == filename and receipt["committed"] and receipt["error"] is None
    assert receipt["source_asset_id"] == exported["asset"]["id"]
    root = (Path(observations["project_path"]) / "exports").resolve(strict=True)
    assert {p.name for p in root.iterdir()} == {filename}
    path = (root / filename).resolve(strict=True)
    assert path.parent == root and path.is_file()
    data = path.read_bytes()
    with closing(sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as db:
        assert db.execute("SELECT status FROM jobs WHERE id=?", (created["job_id"],)).fetchone() == ("succeeded",)
        row = db.execute("SELECT metadata_json, provenance_json FROM assets WHERE id=?",
                         (receipt["source_asset_id"],)).fetchone()
        assert row is not None
        metadata, provenance = map(json.loads, row)
        assert hashlib.sha256(data).hexdigest() == receipt["sha256"] == metadata["sha256"] == provenance["output_sha256"]
        assert len(data) == receipt["size_bytes"] == metadata["size_bytes"]
    return {"verified": True, "scope": "actual director read, typed array creation and GLB delivery" if array else "actual director read, typed clip creation and GLB delivery",
            "scene_id": exported["scene_id"], "revision_id": revision["id"], "job_id": created["job_id"],
            "source_asset_id": revision["source_asset_id"], "receipt": receipt,
            "elapsed_sec": observations["elapsed_sec"],
            "not_tested": ["actual GLB deformation (run Blender inspector)", "artistic quality",
                           "walking/root motion", "engine playback", "image generation"]}


def verify(evidence_dir: Path, database: Path) -> dict[str, Any]:
    observations = json.loads((evidence_dir / "observations.json").read_text())
    if observations.get("director_array"):
        return verify_motion(evidence_dir, database, array=True)
    if observations.get("director_motion"):
        return verify_motion(evidence_dir, database)
    assert observations["exit_code"] == 0
    events = [json.loads(line) for line in (evidence_dir / "events.jsonl").read_text().splitlines()]
    assert not any(event.get("type") == "error" for event in events)
    calls = [event["part"] for event in events if event.get("type") == "tool_use"]
    allowed = {
        "media_capabilities", "media_inspect", "media_scene_create", "media_generate", "media_job_status",
        "media_scene_snapshot", "media_scene_material", "media_scene_export", "media_pack",
        "control_deck_project_output_grant",
    }
    allowed_tools = {"controldeck_addons_" + name for name in allowed}
    if observations.get("director_static"):
        verify_director_static(calls)
        allowed_tools.add("skill")
    assert all(call["tool"] in allowed_tools for call in calls)
    assert all(call["state"]["status"] == "completed" for call in calls)

    def outputs(name: str) -> list[dict[str, Any]]:
        result = []
        for call in calls:
            if call["tool"] == "controldeck_addons_" + name:
                value = json.loads(call["state"]["output"])
                result.append(value.get("output", value))
        return result

    assert outputs("media_capabilities")
    create = outputs("media_scene_create")[0]
    material = outputs("media_scene_material")[0]
    generation = outputs("media_generate")
    statuses = outputs("media_job_status") + generation
    jobs = [create["job_id"], material["job_id"]] + [item["job_id"] for item in generation]
    assert len(jobs) == len(set(jobs)) == 4
    assert all(any(row["job_id"] == job and row["status"] == "succeeded" for row in statuses) for job in jobs)
    revision = next(row["result"]["revision"] for row in statuses
                    if row["job_id"] == material["job_id"] and row["status"] == "succeeded")
    exported = outputs("media_scene_export")[0]
    assert exported["revision_id"] == revision["id"]
    placement = outputs("media_pack")[0]
    assert placement["committed_count"] == placement["requested_count"] == 3
    assert placement["partial"] is False
    receipts = {item["filename"]: item for item in placement["receipts"]}
    assert set(receipts) == {"sword.glb", "blade.png", "sword-project.zip"}
    export_root = (Path(observations["project_path"]) / "exports").resolve(strict=True)
    assert {path.name for path in export_root.iterdir()} == set(receipts)
    connection = sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    try:
        def asset(asset_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
            row = connection.execute("SELECT metadata_json, provenance_json FROM assets WHERE id=?", (asset_id,)).fetchone()
            assert row is not None, asset_id
            return json.loads(row[0]), json.loads(row[1])

        for job in jobs:
            row = connection.execute("SELECT status FROM jobs WHERE id=?", (job,)).fetchone()
            assert row == ("succeeded",), (job, row)
        for filename, receipt in receipts.items():
            path = (export_root / filename).resolve(strict=True)
            assert path.parent == export_root and path.is_file()
            data = path.read_bytes()
            metadata, provenance = asset(receipt["source_asset_id"])
            assert receipt["committed"] and receipt["error"] is None
            assert hashlib.sha256(data).hexdigest() == receipt["sha256"] == metadata["sha256"] == provenance["output_sha256"]
            assert len(data) == receipt["size_bytes"] == metadata["size_bytes"]
        image_id = receipts["blade.png"]["source_asset_id"]
        image_metadata, image_provenance = asset(image_id)
        assert image_provenance["operation"] == "image.generate"
        assert image_provenance["weights_hash"].startswith("sha256:")
        assert "fake" not in image_provenance["runtime_adapter"].lower()
        _, source_provenance = asset(revision["source_asset_id"])
        assert image_id in source_provenance["parent_asset_ids"]
        assert source_provenance["reference_asset_hashes"][image_id] == image_metadata["sha256"]
        assert any(dep["asset_id"] == image_id and dep["sha256"] == image_metadata["sha256"] for dep in revision["dependencies"])
        with zipfile.ZipFile(export_root / "sword-project.zip") as archive:
            assert sorted(archive.namelist()) == ["asset.glb", "manifest.json", "preview.png"]
            assert all(info.file_size < 64 * 1024 * 1024 for info in archive.infolist())
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["profile"] == "3d.project.glb"
            assert manifest["source"]["sha256"] == receipts["sword.glb"]["sha256"]
            for key in ("asset", "preview"):
                item = manifest[key]
                data = archive.read(item["filename"])
                assert len(data) == item["size_bytes"]
                assert hashlib.sha256(data).hexdigest() == item["sha256"]
        stats = manifest["statistics"]
        dimensions = [hi - lo for hi, lo in zip(stats["bounds_max"], stats["bounds_min"], strict=True)]
        assert stats["triangles"] <= 2000 and 0.9 <= max(dimensions) <= 1.1
        return {"scene_id": exported["scene_id"], "revision_id": revision["id"], "jobs": jobs,
                "elapsed_sec": observations["elapsed_sec"], "receipts": list(receipts.values()),
                "dimensions_m": dimensions, "compiled_triangles": stats["triangles"],
                "compiler": manifest["compiler"], "image_model": image_provenance["model_id"],
                "image_warnings": image_provenance["warnings"], "verified": True,
                "director_static": observations.get("director_static", False),
                "not_tested": ["same-scene existing-image comparison/adoption and GUI/restore flow",
                               "image semantic constraints", "long credential refresh"]}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence_dir, args.database), ensure_ascii=False, indent=2))
