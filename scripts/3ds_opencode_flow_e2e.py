"""Real OpenCode -> installed Host MCP -> MediaForge acceptance.

Host diagnostic venv only. Creates a dedicated project and private per-run
configuration, never edits global OpenCode settings. Built-in file/shell/web
tools and external plugins are disabled. Keeps output and redacted JSON events.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


PROMPT = """MediaForgeの統合3D Studio受入として、新しいローポリの剣を1本制作してください。
既存sceneは変更しません。剣にはBlade、Guard、Handle、Pommelという部品を付け、全長約1m、
triangle budgetは2000以下。scene名は MF3DS OpenCode sword acceptance としてください。
形状作成後、青い鋼の模様をMediaForgeの画像生成で新規に1枚作り、Bladeのbase_color材質へ適用してください。
画像の生成前にcapabilitiesを確認し、導入済みの利用可能なローカルモデルをautoで使用してください。
画像が生成できない場合は偽物や外部画像で置き換えず、失敗段階とJob IDを報告してください。
sceneのsnapshotで対象object/material slot/UVを確認し、正しい現在revisionを指定して適用します。
各制作Jobが終端になるまでstatusで追跡し、成功を確認してから次へ進んでください。
完成したsceneをGLBへexportし、そのGLBを既存asset.packの3d.project.glb profileでZIPにもしてください。
公開toolのschemaを使い、任意Python、shell、ファイル直書き、別サービスは使用しません。
最後に現在のControlDeck projectの exports ディレクトリ用output grantを直前に取得し、
GLBをsword.glb、生成画像をblade.png、manifestを含む加工ZIPをsword-project.zipとしてmedia.packで配置します。
grantが期限切れなら新規取得して一度だけ再試行してください。未成功の工程は成功と書かず停止してください。
最終応答にscene ID、最終revision ID、全制作Job ID、生成画像/GLB/ZIPのAsset ID、
配置receiptを列挙してください。MediaForge toolとcontrol_deck.project_output_grantだけを使ってください。
"""


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.integrations.opencode import provider
    from app.models import User

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    args.evidence_dir.mkdir(exist_ok=False)
    assert args.project_name not in {p["name"] for p in provider.list_projects()}, "Use a NEW dedicated project"
    project = provider.ensure_project(args.project_name)
    project_path = Path(project["path"])
    (project_path / "exports").mkdir(exist_ok=False)
    settings = provider.get_settings()
    assert provider.is_gateway_url(settings["base_url"]), "Use the existing local Host gateway"
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        user_id = user.id
    correlation = "mf3ds-" + uuid.uuid4().hex[:16]
    config = provider._runtime_config(correlation, settings["base_url"], settings["model"],
                                      owner_user_id=user_id, project_id=args.project_name)
    evidence: dict[str, Any] = {"project": args.project_name, "project_path": str(project_path),
                                "correlation_id": correlation, "model": settings["model"], "events": 0}
    process = None
    try:
        payload = json.loads(config.read_text())
        secrets = [payload["provider"]["controldeck"]["options"]["apiKey"],
                   payload["mcp"]["controldeck_addons"]["environment"]["CONTROL_DECK_ADDON_MCP_TOKEN"]]
        payload["permission"] = {"*": "deny", "controldeck_addons_*": "allow"}
        payload["tools"] = {name: False for name in ("bash", "read", "edit", "write", "glob", "grep", "webfetch", "websearch", "task", "skill", "question")}
        payload["enabled_providers"] = ["controldeck"]
        config.write_text(json.dumps(payload))
        env = dict(os.environ, OPENCODE_CONFIG=str(config))
        argv = [str(registry.executable("opencode")), "run", PROMPT, "--pure", "--auto", "--format", "json",
                "--model", "controldeck/" + settings["model"], "--dir", str(project_path)]
        start = time.monotonic()
        process = subprocess.Popen(argv, env=env, cwd=project_path, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        evidence["pid"] = process.pid
        print(json.dumps({"pid": process.pid, "project": args.project_name}), flush=True)
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
                evidence["events"] += 1
                kind = event.get("type")
                part = event.get("part") or {}
                if kind in {"tool_use", "error", "step_finish"}:
                    print(json.dumps({"type": kind, "tool": part.get("tool"),
                                      "elapsed_sec": round(time.monotonic() - start, 3)}), flush=True)
                if part.get("sessionID"):
                    evidence["session_id"] = part["sessionID"]
        evidence["exit_code"] = process.wait()
        evidence["elapsed_sec"] = round(time.monotonic() - start, 3)
        evidence["output_files"] = [p.name for p in sorted((project_path / "exports").iterdir())]
        print(json.dumps(evidence, indent=2), flush=True)
        assert evidence["exit_code"] == 0
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=30)
        config.unlink(missing_ok=True)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
