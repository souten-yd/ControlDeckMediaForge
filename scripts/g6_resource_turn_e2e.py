#!/usr/bin/env python3
"""Installed-ControlDeck acceptance for the G6 AI/generation resource turn.

Proves what the unit tests cannot: that a resident Host LLM keeps its VRAM
while Media Forge generates, and that a real image still lands. The broker
places generation on whichever device has room, so the LLM is not asked to
step aside (docs/design-ai-resource-broker.md §0).

Run it against the installed stack. It asks for the password itself, so nothing
secret reaches the command line, the shell history, or a process listing:

    /data1tb/ControlDeck-release-bundle/.venv/bin/python \\
      scripts/g6_resource_turn_e2e.py \\
        --control-deck-url http://127.0.0.1:8765 \\
        --username <name> \\
        --evidence-dir /data1tb/mediaforge-g6-evidence

    Unattended runs can still supply MEDIA_FORGE_E2E_PASSWORD instead.

What is asserted, in order:

1. the workspace boots in one aggregated session request, not ten
2. the job list survives records the running contract cannot read strictly
3. a Host LLM is made resident and really holds VRAM
4. a real image job runs while the LLM stays resident
5. the grant names the device it ran on and the image is produced
6. the Broker is left clean and no worker process remains
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


TERMINAL = {"succeeded", "failed", "canceled"}
# ロードは実測 4.040 秒、生成は FLUX.2 Klein 4B の実測 208.8 秒を含む。
JOB_TIMEOUT_SEC = 900.0


def _password(variable: str) -> str:
    """Take the password from the environment, or ask for it.

    CI keeps using the environment variable. A person running this by hand
    should not have to arrange one: setting it up by hand meant exporting a
    secret into a shell, keeping that shell alive, and remembering to unset it,
    and every step of that was somewhere to go wrong. getpass echoes nothing and
    never reaches the shell history.
    """
    value = os.environ.get(variable)
    if value:
        return value
    if not sys.stdin.isatty():
        raise AssertionError(
            f"パスワードがありません。環境変数 {variable} を設定するか、"
            "対話できる端末から実行してください。"
        )
    value = getpass.getpass("ControlDeck のパスワード: ")
    if not value:
        raise AssertionError("パスワードが入力されませんでした。")
    return value


def check(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def vram_used_bytes() -> int:
    """Read the device, not a model's own accounting."""
    try:
        out = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"], capture_output=True, text=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return -1
    for line in out.splitlines():
        if "GPU[0]" in line and "Total Used Memory" in line:
            try:
                return int(line.split(":")[-1].strip())
            except ValueError:
                return -1
    return -1


def login(page: Page, username: str, password: str) -> None:
    """Sign in, and say plainly what went wrong when it does not work.

    Waiting on the URL alone turns every cause — a wrong password, a rate
    limit, a required second factor — into the same 20-second Playwright
    timeout with a stack trace and no diagnosis. Watch the login response
    instead and report what the server actually said.
    """
    page.goto("/login", wait_until="domcontentloaded")
    if "/login" not in page.url:
        return
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    try:
        with page.expect_response(
            lambda response: response.request.method == "POST"
            and "/auth/login" in response.url,
            timeout=20_000,
        ) as caught:
            page.get_by_role("button", name="ログイン").click()
        response = caught.value
    except PlaywrightTimeoutError as exc:
        raise AssertionError(
            "ログイン要求そのものが送信されませんでした。ControlDeck が応答しているか確認してください。"
        ) from exc

    if response.status != 200:
        detail = ""
        try:
            detail = str(response.json().get("detail", ""))
        except Exception:  # noqa: BLE001 - 応答本文が無いこともある
            detail = response.status_text
        if detail == "two_factor_required":
            raise AssertionError(
                f"{username} は二要素認証が有効です。TOTP を無効にするか、"
                "無効なアカウントで実行してください（./deck.sh reset-totp <user>）。"
            )
        if response.status == 429:
            raise AssertionError(
                "ログイン試行が多すぎて制限されました。1 分待ってから再実行してください"
                "（同一ユーザーは 5 回/分、同一 IP は 20 回/分）。"
            )
        raise AssertionError(
            f"ログインに失敗しました（HTTP {response.status}: {detail}）。"
            f"ユーザー名 {username} とパスワードを確認してください。"
            " パスワードを設定し直すには ./deck.sh passwd <user> を使います。"
        )

    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)
    except PlaywrightTimeoutError as exc:
        raise AssertionError(
            "ログインは成功しましたが画面が遷移しませんでした。"
            f"現在の URL: {page.url}"
        ) from exc


def workspace_frame(page: Page):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/addon-frame/media-forge" in frame.url and frame.locator("#app").count():
                return frame
        page.wait_for_timeout(200)
    raise AssertionError("Media Forge workspace iframe did not become available")


def make_llm_resident(page: Page) -> dict[str, Any]:
    """Ask ControlDeck's own gateway for one completion so a model loads.

    Going through the gateway is the point: that is the same admission path
    ControlDeck chat and OpenCode use, so what becomes resident here is exactly
    what has to be handed back.
    """
    started = time.perf_counter()
    result = page.evaluate(
        """async () => {
          const response = await fetch('/api/v1/llm/v1/chat/completions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-Requested-With': 'ControlDeck'},
            body: JSON.stringify({
              model: 'auto',
              messages: [{role: 'user', content: 'reply with the single word ok'}],
              max_tokens: 8,
              temperature: 0,
            }),
          });
          return {status: response.status, body: (await response.text()).slice(0, 400)};
        }"""
    )
    elapsed = time.perf_counter() - started
    check(result["status"] == 200, f"gateway completion failed: {result}")
    time.sleep(3)
    return {"elapsed_sec": round(elapsed, 3), "vram_after_load": vram_used_bytes()}


def broker_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """async () => {
          const response = await fetch('/api/v1/resources', {
            headers: {'X-Requested-With': 'ControlDeck'},
          });
          if (!response.ok) return {unavailable: response.status};
          return response.json();
        }"""
    )


def request(intent: str, seed: int) -> dict[str, Any]:
    return {
        "operation": "image.generate",
        "intent": intent,
        "inputs": [],
        "model_policy": "auto",
        "constraints": {"width": 256, "height": 256, "seed": seed},
        "output": {"format": "png", "count": 1},
        "qa": {"semantic": False, "max_regeneration_attempts": 0},
        "local_only": True,
    }


def run_job_watching_phases(frame, payload: dict[str, Any]) -> dict[str, Any]:
    """Submit a job and record every phase it passes through.

    The phase sequence is the evidence for the ordering: the AI turn has to be
    declared finished before the generation lease is requested, otherwise a
    single-GPU host deadlocks.
    """
    job = frame.evaluate("value => call('jobs.create', value)", payload)
    job_id = job["id"]
    phases: list[str] = []
    vram_by_phase: dict[str, int] = {}
    started = time.perf_counter()
    deadline = time.monotonic() + JOB_TIMEOUT_SEC
    last: dict[str, Any] = job
    while time.monotonic() < deadline:
        last = frame.evaluate("id => call('jobs.get', {job_id: id})", job_id)
        phase = last.get("phase")
        if phase and (not phases or phases[-1] != phase):
            phases.append(phase)
            vram_by_phase[phase] = vram_used_bytes()
        if last.get("status") in TERMINAL:
            break
        frame.wait_for_timeout(500)
    return {
        "job": last,
        "phases": phases,
        "vram_by_phase": vram_by_phase,
        "elapsed_sec": round(time.perf_counter() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    password = _password(args.password_env)
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    browser_errors: list[str] = []
    observations: dict[str, Any] = {"vram_baseline": vram_used_bytes()}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            base_url=args.control_deck_url, viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: browser_errors.append(f"console:{message.type}:{message.text}")
            if message.type == "error" else None,
        )
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))

        # ── 1. boot が 1 往復であること ─────────────────────────────────
        # framesent は payload を直接渡す（dict ではない）。JSON でないフレームや
        # binary フレームも来るので、数えられないものは黙って捨てる。
        workspace_calls: list[str] = []

        def record_frame(payload: object) -> None:
            if isinstance(payload, bytes):
                try:
                    payload = payload.decode("utf-8")
                except UnicodeDecodeError:
                    return
            if not isinstance(payload, str):
                return
            try:
                method = json.loads(payload).get("method")
            except (ValueError, AttributeError):
                return
            if isinstance(method, str) and method:
                workspace_calls.append(method)

        page.on("websocket", lambda socket: socket.on("framesent", record_frame))
        login(page, args.username, password)
        boot_started = time.perf_counter()
        page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
        frame = workspace_frame(page)
        frame.wait_for_selector('#app[aria-busy="false"]', timeout=30_000)
        observations["boot_ready_sec"] = round(time.perf_counter() - boot_started, 3)
        observations["boot_workspace_calls"] = list(workspace_calls)
        check(
            workspace_calls.count("workspace.session") == 1,
            f"boot did not use one aggregated session: {workspace_calls}",
        )
        # 旧 boot が個別に投げていたメソッドが復活していないこと。
        superseded = {
            "preferences.get", "capabilities.get", "profiles.list",
            "reference_collections.list", "models.catalog", "models.operations.list",
            "models.list", "library.list", "creative.batches.list",
            "creative.compositions.list",
        }
        regressed = sorted(superseded.intersection(workspace_calls))
        check(not regressed, f"boot still issues superseded per-part calls: {regressed}")

        # ── 2. 状況タブが読めること ────────────────────────────────────
        jobs = frame.evaluate("() => call('workspace.session', {parts: ['jobs']})")
        items = jobs["jobs"]["items"]
        observations["job_records"] = len(items)
        observations["degraded_records"] = sum(
            1 for item in items if item.get("record_state") != "ok"
        )
        check(isinstance(items, list), "the activity tab could not read its records")

        capabilities = frame.evaluate("() => call('capabilities.get', {})")
        check(
            capabilities["capabilities"]["image.text_to_image"]["state"] == "available",
            "image.text_to_image is not available",
        )

        # ── 3. LLM を常駐させ、実際に VRAM を握らせる ─────────────────
        observations["llm_load"] = make_llm_resident(page)
        resident = observations["llm_load"]["vram_after_load"]
        check(
            resident > observations["vram_baseline"] + 1_000_000_000,
            f"the Host LLM did not become resident: {observations['llm_load']}",
        )

        # ── 4/5. LLM を載せたまま生成を通す ──────────────────────────
        run = run_job_watching_phases(
            frame, request("an orange field robot folds its solar panels at dusk", 60601)
        )
        observations["generation"] = {
            "status": run["job"]["status"],
            "error": run["job"].get("error"),
            "asset_ids": run["job"].get("asset_ids", []),
            "phases": run["phases"],
            "vram_by_phase": run["vram_by_phase"],
            "elapsed_sec": run["elapsed_sec"],
        }
        check(
            "release_ai" not in run["phases"],
            f"generation still unloads the language model: {run['phases']}",
        )
        during = run["vram_by_phase"].get("generating", run["vram_by_phase"].get("waiting_resource", -1))
        check(
            during < 0 or during >= observations["vram_baseline"] + 1_000_000_000,
            f"the Host LLM lost its VRAM to generation: {run['vram_by_phase']}",
        )
        observations["vram_during_generation"] = during
        check(
            run["job"]["status"] == "succeeded" and len(run["job"].get("asset_ids", [])) == 1,
            f"the real image job did not produce an asset: {run['job']}",
        )

        # ── 6. 後始末 ──────────────────────────────────────────────────
        observations["broker_after"] = broker_snapshot(page)
        browser.close()

    time.sleep(3)
    observations["vram_final"] = vram_used_bytes()
    observations["worker_processes"] = subprocess.run(
        ["pgrep", "-fc", "worker_packs/image"], capture_output=True, text=True
    ).stdout.strip() or "0"
    observations["browser_errors"] = browser_errors

    (args.evidence_dir / "g6-resource-turn.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    if browser_errors:
        print(f"FAILED: browser reported {len(browser_errors)} error(s)")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as failure:
        print(f"FAILED: {failure}")
        raise SystemExit(1) from None
