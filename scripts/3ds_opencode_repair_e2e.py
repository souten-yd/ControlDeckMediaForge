"""Real installed OpenCode repair of an isolated failed typed recipe.

Run with the Host diagnostic Python. Creates only its own scene and a private
runtime config; does not mutate existing projects' files or global settings.
The setup uses direct MCP; only the subsequent repair is attributed to the LLM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any
import uuid

import httpx


def verify_calls(calls: list[dict[str, Any]], created: str, failed: str,
                 scene: str, revision: str) -> str:
    """Require actual diagnosis before editing, bounded input, and terminal success."""
    statuses: dict[str, str] = {}
    snapshot = False
    edited: str | None = None
    allowed = {"media_job_status", "media_scene_snapshot", "media_scene_edit", "media_capabilities"}
    for call in calls:
        name = call["tool"].removeprefix("controldeck_addons_")
        assert name in allowed and call["state"]["status"] == "completed"
        state = call["state"]
        output = json.loads(state["output"])
        output = output.get("output", output)
        if name == "media_job_status":
            statuses[output["job_id"]] = output["status"]
        elif name == "media_scene_snapshot":
            assert state["input"]["scene_id"] == scene
            snapshot = True
        elif name == "media_scene_edit":
            assert edited is None and snapshot
            assert statuses.get(created) == "succeeded" and statuses.get(failed) == "failed"
            value = state["input"]
            assert value["scene_id"] == scene and value["base_revision_id"] == revision
            assert not value.get("retry_job_id"), "Changed input is not an unchanged-input retry"
            operations = value["recipe"]["operations"]
            assert 1 <= len(operations) <= 2
            assert all(op["type"] == "transform.set" and op["object_id"] == "target" for op in operations)
            assert operations[-1]["location"] == [2, 0, 0]
            assert all(set(op) <= {"type", "object_id", "location"} for op in operations)
            edited = output["job_id"]
    assert edited and statuses.get(edited) == "succeeded", "Repair was not observed completing"
    return edited


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.integrations.opencode import provider
    from app.models import User

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.evidence_dir.mkdir(exist_ok=False)
    assert args.project_name not in {p["name"] for p in provider.list_projects()}
    project = provider.ensure_project(args.project_name)
    assert registry.status("media-forge")["version"] == "0.28.49"
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        user_id = user.id
    settings = provider.get_settings()
    assert provider.is_gateway_url(settings["base_url"])
    config = provider._runtime_config("mf3ds-"+uuid.uuid4().hex[:16], settings["base_url"], settings["model"],
                                     owner_user_id=user_id, project_id=args.project_name)
    evidence: dict[str, Any] = {"mode": "real_opencode_failed_recipe_repair", "setup_calls": [],
                                "project": args.project_name, "project_path": project["path"]}
    process = None

    def record() -> None:
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2)+"\n")

    try:
        payload = json.loads(config.read_text())
        bridge = payload["mcp"]["controldeck_addons"]
        secrets = [payload["provider"]["controldeck"]["options"]["apiKey"],
                   bridge["environment"]["CONTROL_DECK_ADDON_MCP_TOKEN"]]
        payload["permission"] = {"*": "deny"}
        for name in ("media_job_status", "media_scene_snapshot", "media_scene_edit", "media_capabilities"):
            payload["permission"]["controldeck_addons_"+name] = "allow"
        payload["tools"] = {name: False for name in (
            "bash", "read", "edit", "write", "glob", "grep", "webfetch", "websearch", "task", "skill", "question")}
        payload["enabled_providers"] = ["controldeck"]
        config.write_text(json.dumps(payload))

        def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}}
            response = subprocess.run(bridge["command"], input=json.dumps(request)+"\n",
                env=dict(os.environ, **bridge["environment"]), capture_output=True, text=True, timeout=45, check=True)
            result = json.loads(response.stdout)["result"]
            assert not result.get("isError"), "Setup MCP request rejected"
            output = result["structuredContent"]["output"]
            evidence["setup_calls"].append({"name": name, "arguments": json.loads(json.dumps(arguments)), "output": output})
            record()
            return output

        def wait(job: dict[str, Any]) -> dict[str, Any]:
            for _ in range(40):
                value = call("media.job.status", {"job_id": job["job_id"]})
                if value["status"] in {"succeeded", "failed", "canceled"}:
                    return value
                time.sleep(.25)
            raise AssertionError("Inspect the existing setup Job; do not resubmit")

        created = wait(call("media.scene.create", {"name": "MF3DS OpenCode failure repair acceptance",
            "recipe": {"operations": [{"type": "primitive.add", "object_id": "target", "primitive": "cube",
                                        "name": "Target", "dimensions": [1, 1, 1]}]}}))
        assert created["status"] == "succeeded"
        scene, revision = created["result"]["scene"]["id"], created["result"]["revision"]["id"]
        failed_operations = [{"type": "transform.set", "object_id": "target", "location": [1, 0, 0]},
                             {"type": "transform.set", "object_id": "missing", "location": [2, 0, 0]}]
        failed = wait(call("media.scene.edit", {"scene_id": scene, "base_revision_id": revision,
                                               "recipe": {"operations": failed_operations}}))
        assert failed["status"] == "failed" and failed["error"]["code"] == "scene_recipe_failed"
        source_id = created["result"]["revision"]["source_asset_id"]
        def source_hash() -> str:
            response = httpx.get("http://127.0.0.1:9130/api/v1/assets/"+source_id+"/content", timeout=20)
            response.raise_for_status()
            return hashlib.sha256(response.content).hexdigest()
        old_hash = source_hash()
        evidence.update(scene_id=scene, base_revision_id=revision, created_job_id=created["job_id"],
                        failed_job_id=failed["job_id"], old_source_sha256=old_hash)
        record()
        prompt = f"""3D編集が失敗したので原因を調べて直してください。対象sceneは{scene}、
元の制作Jobは{created['job_id']}、失敗した編集Jobは{failed['job_id']}です。
まず両Jobのstatusを実際に取得してエラーと作成済みstable IDを確認し、snapshotで現在版を確認してください。
現在版が{revision}以外なら変更せず停止してください。目的は作成済みの1つの立方体を
ワールド座標[2,0,0]メートルへ移すことです。失敗入力は{json.dumps(failed_operations)}。
失敗したrecipeは途中もcommitされません。新しいedit試行で必要な入力だけ直し、成功までstatusを追跡してください。
同入力retryではなく修正した新試行です。別sceneや新objectは作らず、材質/寸法/画像は変更しません。
MediaForgeのstatus/snapshot/edit/capabilitiesだけを使い、shell/file/web/任意Pythonは禁止です。
最終応答では実際のエラーと原因、修正内容、新Jobとrevision IDを報告してください。"""
        (args.evidence_dir / "prompt.txt").write_text(prompt)
        started = time.monotonic()
        process = subprocess.Popen([str(registry.executable("opencode")), "run", prompt, "--pure", "--auto",
            "--format", "json", "--model", "controldeck/"+settings["model"], "--dir", project["path"]],
            cwd=project["path"], env=dict(os.environ, OPENCODE_CONFIG=str(config)),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        evidence["pid"] = process.pid
        record()
        print(json.dumps({"pid": process.pid, "scene_id": scene}), flush=True)
        calls = []
        assert process.stdout
        with (args.evidence_dir / "events.jsonl").open("x") as output:
            for raw in process.stdout:
                for secret in secrets:
                    if secret:
                        raw = raw.replace(secret, "[REDACTED]")
                output.write(raw)
                output.flush()
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "tool_use":
                    calls.append(event["part"])
                    print(json.dumps({"tool": event["part"]["tool"],
                                      "elapsed_sec": round(time.monotonic()-started, 3)}), flush=True)
        evidence.update(exit_code=process.wait(), elapsed_sec=round(time.monotonic()-started, 3))
        assert evidence["exit_code"] == 0
        evidence["repaired_job_id"] = verify_calls(calls, created["job_id"], failed["job_id"], scene, revision)
        final = call("media.scene.snapshot", {"scene_id": scene})
        assert final["scene"]["revision_count"] == 2 and final["revision"]["parent_revision_id"] == revision
        assert source_hash() == old_hash
        evidence.update(passed=True, old_source_preserved=True,
                        not_tested=["artistic quality", "rig/animation repair", "whole 3DS/GA completion"])
    finally:
        try:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=30)
        finally:
            config.unlink(missing_ok=True)
            record()


if __name__ == "__main__":
    main()
