"""Synthetic accounting fixtures; not real OpenCode or asset acceptance."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from test_opencode_authored_mesh_evidence import calls
from test_opencode_flow_evidence import MODULE
from mediaforge.scene_drafts import SceneComposeRequest
from mediaforge.scene_recipes import SceneCreateRequest


def compose_calls() -> list[dict[str, Any]]:
    value = calls()
    request = SceneCreateRequest.model_validate(value[2]["state"]["input"])
    value[2]["tool"] = "controldeck_addons_media_scene_compose"
    value[2]["state"]["input"] = {"name": request.name, "intent": "A closed ridged chest plate", "vertex_budget": 10, "require_closed": True}
    capability = json.loads(value[1]["state"]["output"])
    capability["output"]["capabilities"]["3d.scene_compose"] = {"state": "available"}
    value[1]["state"]["output"] = json.dumps(capability)
    terminal = json.loads(value[3]["state"]["output"])
    terminal["output"]["result"].update({"prepared_request": request.model_dump(mode="json"), "preparation": {
        "schema_version": "media-forge.grouped-mesh-draft@1", "execution_status": "executed",
        "requested_thinking": True, "quality_status": "NOT TESTED",
        "execution_request_sha256": hashlib.sha256(request.model_dump_json().encode()).hexdigest(),
        "attempts": [{"response_kind": name, "valid": True} for name in ("layout", "faces")]}})
    terminal["output"]["result"]["revision"]["source_asset_id"] = "source"
    value[3]["state"]["output"] = json.dumps(terminal)
    return value


@pytest.mark.parametrize("failure", [None, "unavailable", "substitution", "hash", "not_executed", "quality_claim", "no_thinking", "extra_call", "missing_prepared"])
def test_compose_call_evidence(failure: str | None) -> None:
    value = compose_calls()
    terminal = json.loads(value[3]["state"]["output"])
    preparation = terminal["output"]["result"]["preparation"]
    if failure == "unavailable":
        cap = json.loads(value[1]["state"]["output"])
        cap["output"]["capabilities"]["3d.scene_compose"]["state"] = "unavailable"
        value[1]["state"]["output"] = json.dumps(cap)
    elif failure == "substitution":
        value[2]["tool"] = "controldeck_addons_media_scene_create"
    elif failure == "hash":
        preparation["execution_request_sha256"] = "0" * 64
    elif failure == "not_executed":
        preparation["execution_status"] = "not_executed"
    elif failure == "quality_claim":
        preparation["quality_status"] = "PASS"
    elif failure == "no_thinking":
        preparation["requested_thinking"] = False
    elif failure == "extra_call":
        preparation["attempts"] *= 2
    elif failure == "missing_prepared":
        del terminal["output"]["result"]["prepared_request"]
    value[3]["state"]["output"] = json.dumps(terminal)
    if failure:
        with pytest.raises((AssertionError, KeyError, ValueError)):
            MODULE.verify_authored_mesh_calls(value, compose=True)
    else:
        MODULE.verify_authored_mesh_calls(value, compose=True)


@pytest.mark.parametrize("failure", [None, "database_result", "database_request", "source_provenance", "delivery_bytes"])
def test_compose_delivery_cross_checks_database(tmp_path: Path, failure: str | None) -> None:
    value = compose_calls()
    def call(name: str, inputs: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        return {"tool": "controldeck_addons_" + name, "state": {
            "status": "completed", "input": inputs, "output": json.dumps(output)}}
    value[-1]["state"]["output"] = json.dumps({"scene_id": "scene", "revision_id": "revision", "asset": {"id": "glb"}})
    data = b"synthetic delivery bytes, not a real GLB"
    digest = hashlib.sha256(data).hexdigest()
    receipt = {"filename": "armor.glb", "source_asset_id": "glb", "sha256": digest,
               "size_bytes": len(data), "committed": True, "error": None}
    value += [call("control_deck_project_output_grant", {"addon_id": "media-forge", "relative_directory": "exports"}, {"grant_id": "grant:test"}),
              call("media_pack", {"output_grant_id": "grant:test"}, {"committed_count": 1, "requested_count": 1, "partial": False, "receipts": [receipt]})]
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports/armor.glb").write_bytes(data if failure != "delivery_bytes" else b"changed")
    (tmp_path / "observations.json").write_text(json.dumps({"director_compose": True, "exit_code": 0, "project_path": str(tmp_path), "elapsed_sec": 1}))
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps({"type": "tool_use", "part": c}) for c in value))
    result = json.loads(value[3]["state"]["output"])["output"]["result"]
    database = tmp_path / "fixture.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE jobs (id TEXT, status TEXT)")
        db.execute("INSERT INTO jobs VALUES ('job', 'succeeded')")
        db.execute("CREATE TABLE scene_recipe_tasks (job_id TEXT, operation TEXT, result_json TEXT, request_json TEXT)")
        request = SceneComposeRequest.model_validate(value[2]["state"]["input"]).model_dump(mode="json", exclude={"retry_job_id"})
        db.execute("INSERT INTO scene_recipe_tasks VALUES ('job','scene.compose',?,?)", (
            json.dumps({} if failure == "database_result" else result), json.dumps({} if failure == "database_request" else request)))
        db.execute("CREATE TABLE assets (id TEXT, metadata_json TEXT, provenance_json TEXT)")
        db.execute("INSERT INTO assets VALUES ('glb',?,?)", (json.dumps({"sha256": digest, "size_bytes": len(data)}), json.dumps({"output_sha256": digest})))
        db.execute("INSERT INTO assets VALUES ('source','{}',?)", (json.dumps({"parameters": {"preparation": {} if failure == "source_provenance" else result["preparation"]}}),))
    if failure:
        with pytest.raises(AssertionError):
            MODULE.verify(tmp_path, database)
    else:
        assert MODULE.verify(tmp_path, database)["verified"]
