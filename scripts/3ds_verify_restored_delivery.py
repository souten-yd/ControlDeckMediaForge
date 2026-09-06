"""Read-only join of restored UI revision, OpenCode MCP delivery, and real bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any


def recovered_failures(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Require a later success for the exact same failed pack request."""
    failed = []
    for index, call in enumerate(calls):
        if call["state"]["status"] == "completed":
            continue
        assert call["tool"] == "controldeck_addons_media_generate"
        assert call["state"]["input"].get("operation") == "asset.pack"
        assert any(other["state"]["status"] == "completed" and other["tool"] == call["tool"]
                   and other["state"]["input"] == call["state"]["input"] for other in calls[index + 1:])
        failed.append(call)
    return failed


def verify(evidence_dir: Path, database: Path, ui: dict[str, Any]) -> dict[str, Any]:
    assert ui["success"] is True
    observation = json.loads((evidence_dir / "observations.json").read_text())
    assert observation["exit_code"] == 0
    assert observation["output_directory"] == "restored-exports"
    events = [json.loads(line) for line in (evidence_dir / "events.jsonl").read_text().splitlines()]
    assert not any(event.get("type") == "error" for event in events)
    calls = [event["part"] for event in events if event.get("type") == "tool_use"]
    allowed = {"media_capabilities", "media_scene_snapshot", "media_scene_export", "media_generate",
               "media_job_status", "media_inspect", "media_pack", "control_deck_project_output_grant"}
    assert all(call["tool"] in {"controldeck_addons_" + name for name in allowed} for call in calls)
    failed = recovered_failures(calls)
    successful = [call for call in calls if call["state"]["status"] == "completed"]
    # A retry is evidence only when the exact same bounded operation later
    # succeeds. Preserve the error in the report; do not label it a clean run.

    def outputs(name: str) -> list[dict[str, Any]]:
        values = [json.loads(call["state"]["output"]) for call in successful if call["tool"] == "controldeck_addons_" + name]
        return [value.get("output", value) for value in values]

    expected = ui["restored"]
    scene_id = ui["scene_id"]
    revision_id = expected["scene"]["current_revision_id"]
    assert outputs("media_scene_snapshot")[0]["scene"]["current_revision_id"] == revision_id
    exported = outputs("media_scene_export")[0]
    assert (exported["scene_id"], exported["revision_id"]) == (scene_id, revision_id)
    generated_calls = [call for call in successful if call["tool"] == "controldeck_addons_media_generate"]
    assert len(generated_calls) == 1
    assert generated_calls[0]["state"]["input"]["operation"] == "asset.pack"
    assert generated_calls[0]["state"]["input"]["profile"] == "3d.project.glb"
    pack_job = outputs("media_generate")[0]["job_id"]
    assert any(value.get("job_id") == pack_job and value.get("status") == "succeeded"
               for value in outputs("media_generate") + outputs("media_job_status"))
    placement = outputs("media_pack")[0]
    assert placement["committed_count"] == placement["requested_count"] == 3 and placement["partial"] is False
    receipts = {item["filename"]: item for item in placement["receipts"]}
    assert len(placement["receipts"]) == len(receipts) == 3
    assert set(receipts) == {"sword.glb", "blade.png", "sword-project.zip"}
    assert receipts["blade.png"]["source_asset_id"] == ui["generated_image_id"]
    assert receipts["sword.glb"]["source_asset_id"] == exported["asset"]["id"]
    project = Path(observation["project_path"]).resolve(strict=True)
    root = (project / "restored-exports").resolve(strict=True)
    assert root.parent == project
    assert {path.name for path in root.iterdir()} == set(receipts)
    for name, digest in observation["preserved_exports"].items():
        assert Path(name).name == name
        path = (project / "exports" / name).resolve(strict=True)
        assert path.parent == (project / "exports").resolve(strict=True)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    connection = sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    try:
        current = connection.execute("SELECT current_revision_id FROM scene_documents WHERE id=?", (scene_id,)).fetchone()
        assert current == (revision_id,)
        rows = connection.execute("SELECT value_json FROM scene_revisions WHERE scene_id=? ORDER BY sequence", (scene_id,)).fetchall()
        assert [json.loads(row[0]) for row in rows] == expected["revisions"], "Export changed saved revisions"
        assert connection.execute("SELECT status FROM jobs WHERE id=?", (pack_job,)).fetchone() == ("succeeded",)
        for name, receipt in receipts.items():
            assert receipt["committed"] is True and receipt["error"] is None
            path = (root / name).resolve(strict=True)
            assert path.parent == root
            row = connection.execute("SELECT metadata_json,provenance_json FROM assets WHERE id=?", (receipt["source_asset_id"],)).fetchone()
            assert row is not None
            metadata, provenance = (json.loads(item) for item in row)
            data = path.read_bytes()
            assert len(data) == receipt["size_bytes"] == metadata["size_bytes"]
            assert hashlib.sha256(data).hexdigest() == receipt["sha256"] == metadata["sha256"] == provenance["output_sha256"]
        with zipfile.ZipFile(root / "sword-project.zip") as archive:
            assert sorted(archive.namelist()) == ["asset.glb", "manifest.json", "preview.png"]
            assert all(item.file_size < 64 * 1024 * 1024 for item in archive.infolist())
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["source"]["sha256"] == receipts["sword.glb"]["sha256"]
            for key in ("asset", "preview"):
                item = manifest[key]
                data = archive.read(item["filename"])
                assert len(data) == item["size_bytes"]
                assert hashlib.sha256(data).hexdigest() == item["sha256"]
        return {"verified": True, "scene_id": scene_id, "revision_id": revision_id,
                "elapsed_sec": observation["elapsed_sec"], "job_id": pack_job,
                "receipts": list(receipts.values()), "revisions_unchanged": len(rows),
                "original_exports_preserved": len(observation["preserved_exports"]),
                "recovered_tool_errors": [{"tool": call["tool"], "error": call["state"].get("error")} for call in failed],
                "manifest_statistics": manifest["statistics"]}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--ui-evidence", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence_dir, args.database, json.loads(args.ui_evidence.read_text())), indent=2))
