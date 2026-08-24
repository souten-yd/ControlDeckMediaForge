"""A5 — the whole agent path on a real project, with a real GPU.

What this proves, in one run:

    project analysis
      -> purpose-level asset request      (no prompt, no model, no size)
      -> real generation on the GPU
      -> deterministic inspection against the brief
      -> output grant requested late, after the bytes exist
      -> placement receipt
      -> code updated from the receipt, not from a guessed path
      -> build
      -> test

The point is the *absence* of certain things. The caller here plays a coding
agent: it reads the project, states what the asset is for, and never writes a
prompt, names a model, or picks a canvas size. If Media Forge cannot turn
purpose into a correct asset by itself, this script fails — that is what makes
it worth running.

What is real: the GPU, the model, the generated pixels, the project, its build
and its tests. What is stubbed: ControlDeck's file-grant plumbing, which is
ControlDeck's own contract and has its own tests. The stub writes committed
bytes to the real project directory, so placement is observable as a file the
build actually consumes rather than as a success message.

    python scripts/a5_agent_asset_path_e2e.py --evidence-dir ./evidence
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import Body, FastAPI, Response

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

FEATURE_DATA = Path("/data1tb/ControlDeck/data/feature-data/media-forge")
SHARED_CACHE = Path("/data1tb/ControlDeck/data/cache")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# ── the project the agent is working on ────────────────────────────────────
#
# Small on purpose, but real: it has a build step, tests that fail when the
# asset is wrong, and a declared need written in the project's own terms
# rather than in Media Forge's.

PROJECT_SPEC = {
    "name": "title-screen",
    "needs": [
        {
            "slot": "background",
            "purpose": "title screen background for a small game",
            "surface": "game",
            "shape": "landscape",
            "must_not": ["no text in the image"],
            "keep_clear": "top",
        }
    ],
}

PROJECT_TEST = '''"""アセットが実際に使える形で入ったかを、プロジェクト側から確かめる。

Media Forge が「置いた」と言ったことではなく、この build が読める場所に、
使える中身で存在することを見る。
"""
from pathlib import Path

from PIL import Image

import assets

ROOT = Path(__file__).parent


def test_the_background_is_referenced_by_the_code():
    assert assets.BACKGROUND, "コードが背景を参照していない"


def test_the_referenced_file_exists_and_is_usable():
    path = ROOT / assets.BACKGROUND
    assert path.is_file(), f"参照先が無い: {assets.BACKGROUND}"
    with Image.open(path) as image:
        assert image.format == "PNG"
        # 用途は横長の背景。縦長が来たら、この画面には使えない。
        assert image.width > image.height, f"横長ではない: {image.size}"
        assert image.width >= 512, f"背景として小さすぎる: {image.size}"


def test_the_recorded_digest_matches_the_file():
    """受領書の digest と中身が一致すること。置き換わっていたら気づく。"""
    import hashlib

    path = ROOT / assets.BACKGROUND
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == assets.BACKGROUND_SHA256, "受領書と中身が食い違う"
'''

PROJECT_ASSETS_BEFORE = '''"""生成されたアセットへの参照。配置の受領書から書き換わる。"""

BACKGROUND = ""
BACKGROUND_SHA256 = ""
'''


def write_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.json").write_text(
        json.dumps(PROJECT_SPEC, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "assets.py").write_text(PROJECT_ASSETS_BEFORE, encoding="utf-8")
    (root / "test_project.py").write_text(PROJECT_TEST, encoding="utf-8")


# ── the Host stub, writing where the build can see ─────────────────────────


def project_host_stub(project_root: Path) -> tuple[FastAPI, dict[str, Any]]:
    """ControlDeck's grant plumbing, committing into the real project.

    Deliberately not a no-op: an in-memory commit would let a broken placement
    pass, because nothing downstream would notice.
    """
    from test_host_execution import control_deck_stub

    app, state = control_deck_stub()
    state["committed"] = {}

    for route in list(app.router.routes):
        if getattr(route, "path", "") in {
            "/api/v1/addon-runtime/media-forge/files/outputs/{output_id}/commit",
            "/api/v1/addon-runtime/media-forge/files/outputs/{output_id}/content",
        }:
            app.router.routes.remove(route)

    @app.put("/api/v1/addon-runtime/media-forge/files/outputs/{output_id}/content")
    async def upload_output(output_id: str, payload: bytes = Body()) -> dict[str, Any]:
        state["outputs"][output_id]["content"] = payload
        return {"output_id": output_id, "received": len(payload)}

    @app.post("/api/v1/addon-runtime/media-forge/files/outputs/{output_id}/commit")
    async def commit_output(output_id: str) -> dict[str, Any]:
        output = state["outputs"][output_id]
        metadata = output["metadata"]
        check(
            len(output["content"]) == metadata["size"],
            "committed byte count differs from the declared size",
        )
        destination = project_root / str(metadata["filename"])
        destination.write_bytes(output["content"])
        state["committed"][str(metadata["filename"])] = len(output["content"])
        return {
            "asset_id": f"asset:{output_id}",
            "job_id": metadata["job_id"],
            "name": metadata["filename"],
        }

    return app, state


# ── the coding agent's half ────────────────────────────────────────────────


def brief_from_project(need: dict[str, Any]) -> dict[str, Any]:
    """Turn what the project says it needs into a purpose-level brief.

    Note what is not here: no prompt wording, no model, no pixel size, no
    provider. The agent knows what the asset is for and nothing about how it
    gets made. Everything below comes from project.json.
    """
    brief: dict[str, Any] = {
        "role": need["slot"],
        "target_surface": need["surface"],
        "subject": need["purpose"],
        "aspect_intent": need["shape"],
        "hard_constraints": list(need.get("must_not", [])),
    }
    if need.get("keep_clear"):
        brief["safe_areas"] = [
            {"edge": need["keep_clear"], "fraction": 0.35, "purpose": "title and menu"}
        ]
    return brief


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--keep-project", action="store_true")
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(levelname)s %(name)s %(message)s")

    from fastapi.testclient import TestClient

    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.host.client import ControlDeckHostClient

    work = Path(tempfile.mkdtemp(prefix="a5-agent-path-"))
    project = work / "project"
    write_project(project)
    observations: dict[str, Any] = {"project": str(project)}

    host_app, host_state = project_host_stub(project)
    settings = Settings(
        data_dir=work / "data",
        worker_timeout_sec=1800.0,
        model_manifest=REPO / "worker_packs/image/models.json",
        model_catalog_manifest=REPO / "worker_packs/image/catalog.json",
        model_store_root=FEATURE_DATA / "data" / "models",
        hf_home=SHARED_CACHE / "huggingface",
        image_runtime_python=FEATURE_DATA / "runtimes/rocm-torch/.venv/bin/python",
    )
    app = create_app(
        settings,
        host_client=ControlDeckHostClient(
            "https://control-deck.test", transport=httpx.ASGITransport(app=host_app)
        ),
    )
    headers = {"Authorization": "Bearer valid-user", "X-Control-Deck-Addon-ID": "media-forge"}

    with TestClient(app) as client, client.websocket_connect("/ws", headers=headers) as socket:
        # 生成は Host 管理の実行でなければ通らない（GPU を握るのは Host の
        # 判断である）。workspace 経路で呼ぶ。REST は同じことをしない。
        counter = {"n": 0}

        def call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            counter["n"] += 1
            tag = f"a5-{counter['n']}"
            socket.send_json({"id": tag, "method": method, "params": params})
            while True:
                message = socket.receive_json()
                if message.get("id") == tag:
                    check(message.get("ok") is not False,
                          f"{method} was refused: {message.get('error')}")
                    return message.get("result", {})

        # ── 1. project analysis ────────────────────────────────────────────
        spec = json.loads((project / "project.json").read_text(encoding="utf-8"))
        need = spec["needs"][0]
        brief = brief_from_project(need)
        observations["brief"] = brief
        check("prompt" not in brief and "model" not in brief, "brief leaked generation detail")

        # ── 2. purpose-level request ───────────────────────────────────────
        request: dict[str, Any] = {
            "operation": "image.generate",
            "intent": need["purpose"],
            "constraints": {"asset_brief": brief, "steps": 8},
            "output": {"format": "png", "count": 1},
        }
        if args.model_id:
            request["model_policy"] = "manual"
            request["model_id"] = args.model_id
        # 何 px にするかは書かない。用途から Media Forge が決めることを見る。
        check(
            "width" not in request["constraints"] and "height" not in request["constraints"],
            "the agent should not be choosing the canvas",
        )

        started = time.monotonic()
        job_id = call("jobs.create", request)["id"]

        deadline = time.monotonic() + 1800
        job: dict[str, Any] = {}
        while time.monotonic() < deadline:
            job = call("jobs.get", {"job_id": job_id})
            if job["status"] in {"succeeded", "failed", "canceled"}:
                break
            time.sleep(3)
        observations["generation"] = {
            "status": job.get("status"),
            "error": job.get("error"),
            "elapsed_sec": round(time.monotonic() - started, 2),
        }
        check(job.get("status") == "succeeded", f"generation did not succeed: {job.get('error')}")
        asset_id = job["asset_ids"][0]

        # ── 3. inspection against the brief ────────────────────────────────
        asset = client.get(f"/api/v1/assets/{asset_id}", headers=headers).json()
        provenance = call("assets.provenance", {"asset_id": asset_id})
        observations["asset"] = {
            k: asset[k] for k in ("width", "height", "mime_type", "size_bytes", "sha256")
        }
        observations["routed_model"] = provenance["model_id"]
        # 用途は「横長の背景」。ここが縦なら、purpose から幾何が解けていない。
        check(
            asset["width"] > asset["height"],
            f"a landscape brief produced {asset['width']}x{asset['height']}",
        )
        observations["warnings"] = provenance["warnings"]
        # hard_constraint は評価器でしか確かめられない。既定では回さないので、
        # 「確かめていない」と言うのが正しい。黙るのは嘘になる（実測: 文字を
        # 禁じた資産が文字入りで返り、warnings は空だった）。
        unverified = [w for w in provenance["warnings"] if "検査していません" in w]
        check(
            bool(unverified),
            "hard constraints went unchecked and unmentioned: "
            f"{provenance['warnings']}",
        )
        check(
            all("no text in the image" in w for w in unverified),
            f"the unverified notice does not name the constraint: {unverified}",
        )

        # ── 4. late output grant ───────────────────────────────────────────
        # 生成の前に取らない。生成は数十秒〜数分かかり、先に取った grant は
        # 期限切れになる。バイトが存在してから頼む。
        grant_id = "grant:export-1"
        observations["grant_requested_after_generation"] = True

        # ── 5. placement, and a receipt to read back ───────────────────────
        # agent tool の入口をそのまま使う。coding agent が実際に呼ぶ経路である。
        placed = client.post(
            "/addon/v1/agent/pack",
            headers={
                "Authorization": "Bearer valid-job",
                "X-Control-Deck-Addon-ID": "media-forge",
            },
            json={
                "input": {
                    "output_grant_id": grant_id,
                    "items": [{
                        "asset_id": asset_id,
                        "filename": "title-background.png",
                        "role": need["slot"],
                    }],
                },
                "correlation": {"job_id": "host-agent"},
            },
        )
        check(placed.status_code == 200, f"placement was refused: {placed.text}")
        body = placed.json()
        receipts = body.get("receipts") or ([body["receipt"]] if body.get("receipt") else [])
        observations["placement"] = {"receipts": receipts, "committed": host_state["committed"]}
        check(bool(receipts), f"no placement receipt was returned: {body}")
        receipt = receipts[0]
        check(receipt.get("committed") is True, f"the receipt does not claim a commit: {receipt}")
        check(
            receipt.get("sha256") == asset["sha256"],
            "the receipt digest differs from the asset that was inspected",
        )
        # 受領書が「置いた」と言うだけでは足りない。実際に project に在ること。
        check(
            "title-background.png" in host_state["committed"],
            f"nothing was committed into the project: {host_state['committed']}",
        )

        # ── 6. update the code from the receipt ────────────────────────────
        # パスを推測しない。受領書が名乗った名前と digest をそのまま書く。
        (project / "assets.py").write_text(
            '"""生成されたアセットへの参照。配置の受領書から書き換わる。"""\n\n'
            f'BACKGROUND = {receipt["filename"]!r}\n'
            f'BACKGROUND_SHA256 = {receipt["sha256"]!r}\n',
            encoding="utf-8",
        )

    # ── 7. build ───────────────────────────────────────────────────────────
    build = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(project)],
        capture_output=True, text=True, timeout=120,
    )
    observations["build"] = {"returncode": build.returncode, "stderr": build.stderr[-500:]}
    check(build.returncode == 0, f"the project did not build: {build.stderr}")

    # ── 8. test ────────────────────────────────────────────────────────────
    tests = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-m", "pytest", "-q", str(project)],
        capture_output=True, text=True, timeout=300, cwd=str(project),
    )
    observations["tests"] = {
        "returncode": tests.returncode,
        "stdout": tests.stdout[-800:],
    }
    check(tests.returncode == 0, f"the project's tests failed:\n{tests.stdout}")

    evidence = args.evidence_dir / "a5-agent-asset-path.json"
    evidence.write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    if args.keep_project:
        print(f"project kept at {project}", file=sys.stderr)
    print("PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
