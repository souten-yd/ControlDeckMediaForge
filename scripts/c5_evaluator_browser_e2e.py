#!/usr/bin/env python3
"""Exercise C5 advisory ranking in an installed-host opaque workspace."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def check(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login", wait_until="domcontentloaded")
    if "/login" not in page.url:
        return
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def workspace_frame(page: Page):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/addon-frame/media-forge" in frame.url and frame.locator("#app").count():
                return frame
        page.wait_for_timeout(200)
    raise AssertionError("Media Forge workspace iframe did not become available")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--asset-id", action="append", required=True)
    parser.add_argument("--expected-first", required=True)
    parser.add_argument(
        "--intent",
        default="同じオレンジメッシュのボーイッシュなコンパニオンが端末を見せる",
    )
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    if len(args.asset_id) < 2:
        raise ValueError("at least two candidates are required")
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    browser_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            base_url=args.control_deck_url,
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: browser_errors.append(f"console:{message.type}:{message.text}")
            if message.type == "error" else None,
        )
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
        login(page, args.username, password)
        page.goto("/x/media-forge/workspace", wait_until="domcontentloaded")
        frame = workspace_frame(page)
        frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)
        frame.locator("#create-intent").fill(args.intent)
        jobs_before = frame.evaluate("() => call('jobs.list', {limit: 100})")
        frame.evaluate("assetIds => showResult(assetIds)", args.asset_id)
        frame.locator("#result-evaluate").wait_for(state="visible")
        started = time.perf_counter()
        frame.locator("#result-evaluate").click()
        frame.wait_for_function(
            "() => document.getElementById('result-evaluation').textContent.startsWith('おすすめ:')",
            timeout=180_000,
        )
        elapsed = time.perf_counter() - started
        ranked = frame.locator("#candidate-strip .thumb").evaluate_all(
            "nodes => nodes.map(node => node.dataset.assetId)"
        )
        jobs_after = frame.evaluate("() => call('jobs.list', {limit: 100})")
        note = frame.locator("#result-evaluation").inner_text()
        check(ranked[0] == args.expected_first, f"unexpected first candidate: {ranked}")
        check(
            len(jobs_before["items"]) == len(jobs_after["items"]),
            "advisory evaluation created a generation job",
        )
        page.screenshot(path=args.evidence_dir / "evaluator-ranked.png", full_page=True)

        page.set_viewport_size({"width": 320, "height": 700})
        page.wait_for_timeout(250)
        overflow = frame.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(overflow <= 0, f"workspace overflowed at 320px: {overflow}")
        page.screenshot(path=args.evidence_dir / "evaluator-ranked-320.png", full_page=True)
        browser.close()

    check(not browser_errors, f"browser errors: {browser_errors}")
    evidence = {
        "asset_ids": args.asset_id,
        "intent": args.intent,
        "ranked_asset_ids": ranked,
        "expected_first": args.expected_first,
        "elapsed_sec": round(elapsed, 3),
        "jobs_before": len(jobs_before["items"]),
        "jobs_after": len(jobs_after["items"]),
        "evaluation_note": note,
        "overflow_320px": overflow,
        "browser_errors": browser_errors,
    }
    (args.evidence_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
