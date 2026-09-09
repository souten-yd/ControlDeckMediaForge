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
from pathlib import Path
from typing import Any


def verify_director_static(calls: list[dict[str, Any]]) -> None:
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
    operations = state["input"]["recipe"]["operations"]
    assert {"object.duplicate", "modifier.mirror"} <= {op["type"] for op in operations}
    assert any(op.get("reference_object_id") == "handle" and op.get("axes") == ["X"]
               for op in operations if op["type"] == "modifier.mirror"), "Guard must mirror about the handle"


def verify(evidence_dir: Path, database: Path) -> dict[str, Any]:
    observations = json.loads((evidence_dir / "observations.json").read_text())
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
