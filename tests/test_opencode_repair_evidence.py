from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("repair_evidence", Path(__file__).parents[1] / "scripts/3ds_opencode_repair_e2e.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def ledger() -> list[dict]:
    def call(name: str, value: dict, arguments: dict | None = None) -> dict:
        return {"tool": "controldeck_addons_"+name, "state": {"status": "completed",
                "input": arguments or {}, "output": json.dumps({"output": value})}}
    return [
        call("media_job_status", {"job_id": "created", "status": "succeeded"}),
        call("media_job_status", {"job_id": "failed", "status": "failed"}),
        call("media_scene_snapshot", {}, {"scene_id": "scene"}),
        call("media_scene_edit", {"job_id": "fixed"}, {"scene_id": "scene", "base_revision_id": "revision",
             "recipe": {"operations": [{"type": "transform.set", "object_id": "target", "location": [2,0,0]}]}}),
        call("media_job_status", {"job_id": "fixed", "status": "succeeded"}),
    ]


def test_actual_diagnosis_and_completed_repair_required() -> None:
    assert module.verify_calls(ledger(), "created", "failed", "scene", "revision") == "fixed"


@pytest.mark.parametrize("fault", ["missing_diagnosis", "late_diagnosis", "no_completion", "wrong_scene",
                                  "wrong_base", "retry", "wrong_id", "wrong_location", "extra_edit", "shell"])
def test_rejects_insufficient_or_out_of_scope_evidence(fault: str) -> None:
    calls = copy.deepcopy(ledger())
    value = calls[3]["state"]["input"]
    if fault == "missing_diagnosis":
        calls.pop(1)
    elif fault == "late_diagnosis":
        calls.append(calls.pop(1))
    elif fault == "no_completion":
        calls.pop()
    elif fault == "wrong_scene":
        value["scene_id"] = "other"
    elif fault == "wrong_base":
        value["base_revision_id"] = "other"
    elif fault == "retry":
        value["retry_job_id"] = "failed"
    elif fault == "wrong_id":
        value["recipe"]["operations"][0]["object_id"] = "missing"
    elif fault == "wrong_location":
        value["recipe"]["operations"][0]["location"] = [1,0,0]
    elif fault == "extra_edit":
        calls.append(calls[3])
    elif fault == "shell":
        calls[0]["tool"] = "bash"
    with pytest.raises(AssertionError):
        module.verify_calls(calls, "created", "failed", "scene", "revision")
