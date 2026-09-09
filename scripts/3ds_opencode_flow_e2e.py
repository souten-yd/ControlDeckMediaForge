"""Real OpenCode -> installed Host MCP -> MediaForge acceptance.

Host diagnostic venv only. Creates a dedicated project and private per-run
configuration, never edits global OpenCode settings. Built-in file/shell/web
tools and external plugins are disabled. Keeps output and redacted JSON events.
"""
from __future__ import annotations

import argparse
import hashlib
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

DIRECTOR_STATIC = """最初にskill toolでblender-directorを実際に読み込んでください。
スキルの説明を推測して進めず、読込に失敗したら停止してください。
以下はゲーム用静的アセットの複製・ミラー受入です。現在の公開schemaとcapabilitiesに
object.duplicateとmodifier.mirrorがあることを確認し、scene.createのrecipe内で両方を使います。
Guardを中心からX方向に離した片側部品として作り、中心のHandleをreferenceにXミラーして
左右対称の鍔にしてください。中心対称cubeをその場でミラーするだけでは不十分です。
object.duplicateで装飾部品を独立複製し、別位置へ配置してください。全体の最大寸法は約1mです。
スキルの古い7操作表にない追加操作も、現在の公開schemaに存在するものだけ使えます。
以下の制作依頼のtool制限には、今回だけblender-directorのskill読込を追加で許可します。
"""


DIRECTOR_MOTION = """最初にskill toolでblender-directorを実際に読み込んでください。
読込に失敗したら停止してください。MediaForgeで新しいボーン付きの小型ロボットを作り、
待機idle（2秒）と腕振りarm_swing（1秒）の2つのループアニメーションを付けてください。
これはBlenderの骨格です。Unreal Pawnではありません。既存sceneは変更しません。
scene名は MF3DS OpenCode motion acceptance。頭・胴・腕・脚を持ち、全高約1m、
3000 triangles以下。部品の接合に隙間を作らず、骨へ部品全体を剛体bindしてください。
既存skillの7操作表にない機能も、現在のMCP公開schemaとmedia.capabilitiesに
存在するものだけ利用可能です。armature.create / skin.bind / animation.clipを使います。
任意PythonやBlenderMCPの存在しないtoolは使いません。現在のschemaを実行の正とします。
骨の回転はrest-local XYZ、fps24、idleは48frames、arm_swingは24frames、
frame0と終点は同じ回転、中間は実際に部品が動く回転にしてください。
未指定boneの回転はrestになります。色はmaterial.setで設定し、画像は今回は生成しません。
Jobが終端になるまでmedia.job.statusで追跡し、成功後にsnapshotを確認しGLBへexportします。
scene.exportは同期でAssetを返します。asset.job_idは過去の履歴であり新Jobではありません。
現在projectのexports用output grantを取得し、media.packでrobot.glbを1件配置してください。
G8 ZIPへの加工は今回行いません。失敗は段階とJob IDを報告し、成功扱いしません。
最終応答にscene/revision/制作Job/GLB Asset IDと配置receiptを列挙してください。
skill読込とMediaForge tool、control_deck.project_output_grantだけを使い、shell/file/webは禁止です。
"""


def restrict_tools(payload: dict[str, Any], *, director_static: bool, director_motion: bool = False) -> None:
    """Limit this diagnostic's private configuration, never global settings."""
    payload["permission"] = {"*": "deny", "controldeck_addons_*": "allow"}
    payload["tools"] = {name: False for name in (
        "bash", "read", "edit", "write", "glob", "grep", "webfetch", "websearch", "task", "skill", "question")}
    if director_static or director_motion:
        payload["permission"]["skill"] = {"*": "deny", "blender-director": "allow"}
        # Legacy tools entries become permissions before the global wildcard;
        # duplicating skill there changes insertion order and disables it again.
        payload["tools"].pop("skill")
    payload["enabled_providers"] = ["controldeck"]


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.integrations.opencode import provider
    from app.models import User

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--restored-ui-evidence", type=Path,
                        help="Export the verified restored scene into a new sibling output folder in its existing dedicated project")
    parser.add_argument("--retry-empty-output", action="store_true",
                        help="Reuse only an existing empty restored output directory after a terminal failed run")
    parser.add_argument("--director-static", action="store_true",
                        help="Require a real director skill read and duplicate/mirror in a new sword scene")
    parser.add_argument("--director-motion", action="store_true",
                        help="Require a real director read and a new rigged robot with idle/arm_swing GLB delivery")
    args = parser.parse_args()
    if args.director_static and args.director_motion:
        parser.error("Choose one director scenario")
    director_enabled = args.director_static or args.director_motion
    if director_enabled and (args.restored_ui_evidence or args.retry_empty_output):
        parser.error("Director acceptance requires a new project/scene")
    os.umask(0o077)
    args.evidence_dir.mkdir(exist_ok=False)
    project_names = {p["name"] for p in provider.list_projects()}
    prompt = DIRECTOR_STATIC + PROMPT if args.director_static else PROMPT
    if args.director_motion:
        prompt = DIRECTOR_MOTION
    output_directory = "exports"
    if args.restored_ui_evidence:
        assert args.project_name.startswith("MF3DS-") and args.project_name in project_names
        restored = json.loads(args.restored_ui_evidence.read_text())
        assert restored["success"] is True
        scene_id = restored["scene_id"]
        revision_id = restored["restored"]["scene"]["current_revision_id"]
        image_id = restored["generated_image_id"]
        output_directory = "restored-exports"
        prompt = f"""MediaForgeの制作受入の続きです。既存scene {scene_id} のsnapshotを確認し、
現在revisionが {revision_id} である場合だけ進めてください。異なる場合は変更せず停止します。
この復元済み版をGLBへexportし、GLBから既存asset.packの3d.project.glbでmanifest入りZIPを作ります。
scene.exportは同期で検証済みAssetを返す操作です。返されたasset.job_idは過去の作成履歴であり、
新しく開始したJobではありません。この過去Jobへmedia.job.statusを呼ぶ必要はありません。
asset.packの入力はexportしたGLBのAsset ID一つだけです。画像はZIP加工のinputsへ入れません。
ZIP生成はoperation=asset.pack、profile=3d.project.glb、inputs=[GLB一件]、output.format=zipです。
画像 {image_id} はすでに生成・材質採用済みなので再生成しません。scene編集・新規作成もしません。
新しく依頼したZIP加工は応答のsucceededとAsset IDを確認し、未成功なら停止して原因を報告してください。
最後に現在projectの restored-exports 用output grantを直前に取得し、media.packで
sword.glb、blade.png、sword-project.zipを配置してください。既存exportsには書き込みません。
MediaForge toolとcontrol_deck.project_output_grantだけを使い、shell/file/web/任意Pythonは禁止です。
最終応答にscene/revision/Job/Asset IDと3件のreceiptを列挙してください。"""
    else:
        assert args.project_name not in project_names, "Use a NEW dedicated project"
    project = provider.ensure_project(args.project_name)
    project_path = Path(project["path"])
    output_path = project_path / output_directory
    if args.retry_empty_output:
        assert args.restored_ui_evidence and output_path.is_dir() and not output_path.is_symlink()
        assert not list(output_path.iterdir()), "Never overwrite a previous delivery"
    else:
        output_path.mkdir(exist_ok=False)
    preserved = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in (project_path / "exports").iterdir() if path.is_file()} if args.restored_ui_evidence else {}
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
                                "correlation_id": correlation, "model": settings["model"], "events": 0,
                                "output_directory": output_directory, "preserved_exports": preserved,
                                "director_static": args.director_static, "director_motion": args.director_motion}
    process = None
    try:
        payload = json.loads(config.read_text())
        secrets = [payload["provider"]["controldeck"]["options"]["apiKey"],
                   payload["mcp"]["controldeck_addons"]["environment"]["CONTROL_DECK_ADDON_MCP_TOKEN"]]
        restrict_tools(payload, director_static=args.director_static, director_motion=args.director_motion)
        config.write_text(json.dumps(payload))
        if director_enabled:
            debug = subprocess.run([str(registry.executable("opencode")), "debug", "agent", "build", "--pure"],
                env=dict(os.environ, OPENCODE_CONFIG=str(config)), capture_output=True, text=True, timeout=30)
            assert debug.returncode == 0, "Agent permission preflight failed"
            resolved = json.loads(debug.stdout)
            assert resolved["tools"]["skill"] is True, "Director skill tool is disabled after config resolution"
            assert not any(resolved["tools"].get(name) for name in ("bash", "read", "edit", "write", "task", "webfetch"))
            evidence["director_tool_enabled"] = True
        bridge = payload["mcp"]["controldeck_addons"]
        preflight = subprocess.run(bridge["command"],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n",
            env=dict(os.environ, **bridge["environment"]), capture_output=True, text=True, timeout=30)
        assert preflight.returncode == 0, "MCP bridge preflight failed"
        listing = json.loads(preflight.stdout)["result"]["tools"]
        names = {tool["name"] for tool in listing}
        assert {"media.scene.snapshot", "media.scene.export", "media.pack", "control_deck.project_output_grant"} <= names
        if director_enabled:
            schema = json.dumps(next(tool["inputSchema"] for tool in listing if tool["name"] == "media.scene.create"))
            required = ("armature.create", "skin.bind", "animation.clip") if args.director_motion else ("object.duplicate", "modifier.mirror")
            assert all(operation in schema for operation in required)
        evidence["mcp_preflight_tool_count"] = len(names)
        env = dict(os.environ, OPENCODE_CONFIG=str(config))
        argv = [str(registry.executable("opencode")), "run", prompt, "--pure", "--auto", "--format", "json",
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
                if kind == "tool_use":
                    evidence["tool_calls"] = evidence.get("tool_calls", 0) + 1
                if kind in {"tool_use", "error", "step_finish"}:
                    print(json.dumps({"type": kind, "tool": part.get("tool"),
                                      "elapsed_sec": round(time.monotonic() - start, 3)}), flush=True)
                if part.get("sessionID"):
                    evidence["session_id"] = part["sessionID"]
        evidence["exit_code"] = process.wait()
        evidence["elapsed_sec"] = round(time.monotonic() - start, 3)
        evidence["output_files"] = [p.name for p in sorted((project_path / output_directory).iterdir())]
        assert all(hashlib.sha256((project_path / "exports" / name).read_bytes()).hexdigest() == digest
                   for name, digest in preserved.items()), "Original delivery was modified"
        print(json.dumps(evidence, indent=2), flush=True)
        assert evidence["exit_code"] == 0
        assert evidence.get("tool_calls", 0) > 0, "OpenCode emitted no actual tool calls"
        expected = {"robot.glb"} if args.director_motion else {"sword.glb", "blade.png", "sword-project.zip"}
        assert set(evidence["output_files"]) == expected
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=30)
        config.unlink(missing_ok=True)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
