#!/usr/bin/env python3
"""Installed-Host acceptance for CI-5 directed multi-cut composition."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def get_json(base_url: str, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url + path, timeout=10) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise AssertionError(f"expected an object from {path}")
    return value


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login", wait_until="domcontentloaded")
    if "/login" not in page.url:
        return
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def workspace_frame(page: Page, timeout: float = 20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/addon-frame/media-forge" in frame.url and frame.locator("#app").count():
                return frame
        page.wait_for_timeout(200)
    return None


def wait_composition(base_url: str, timeout: float = 180.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        items = get_json(base_url, "/workspace-api/creative/compositions").get("items", [])
        last = items[0] if items else {}
        if last.get("state") in {"succeeded", "partial", "failed", "canceled"}:
            return last
        time.sleep(0.5)
    raise AssertionError(f"composition did not finish: {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise SystemExit(f"password environment variable is unset: {args.password_env}")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    console_errors: list[str] = []
    page_errors: list[str] = []
    started = time.perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        login(page, args.username, password)
        page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
        frame = workspace_frame(page)
        check(frame is not None, "installed Media Forge frame did not appear")
        frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)
        check(frame.evaluate("() => document.documentElement.dataset.bridge") == "ready", "Host bridge is not ready")
        frame.select_option("#director-mode", "refine")
        frame.click('#domain-chips [data-domain="poster"]')
        frame.click('#count-chips [data-count="3"]')
        frame.fill("#create-intent", "same orange robot repairs and presents a damaged terminal in three coherent shots")
        frame.fill("#composition-title", "CI5 EXACT TITLE")
        frame.fill("#composition-caption", "CI5 EXACT CAPTION")
        frame.click("#create-submit")
        result = wait_composition(args.media_forge_url)
        check(result.get("state") == "succeeded", f"composition did not succeed: {result}")
        check(result.get("director", {}).get("assistance_used") is True, "Director did not author shot briefs")
        plans = result.get("child_plans", [])
        check(len(plans) == 3 and len(result.get("child_job_ids", [])) == 3, "ordinary child jobs are missing")
        roles = [plan.get("director", {}).get("shot_brief", {}).get("role") for plan in plans]
        check(roles == ["main", "coding", "device"], f"shot roles are not server-owned: {roles}")
        encoded_plans = json.dumps(plans, ensure_ascii=False)
        check("CI5 EXACT TITLE" not in encoded_plans and "CI5 EXACT CAPTION" not in encoded_plans,
              "deterministic title or caption leaked into diffusion shot plans")
        check(len(result.get("shot_asset_ids", [])) == 3 and len(result.get("asset_ids", [])) == 1,
              "shot or final assets are missing")
        frame.wait_for_selector("#composition-text-edit", state="visible", timeout=20_000)
        page.screenshot(path=str(args.evidence_dir / "ci5-installed-directed-poster.png"), full_page=True)
        page.set_viewport_size({"width": 320, "height": 640})
        page.wait_for_timeout(500)
        overflow = frame.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(overflow == 0, f"320px workspace overflowed by {overflow}px")
        page.screenshot(path=str(args.evidence_dir / "ci5-installed-directed-poster-320.png"), full_page=True)
        context.close()
        browser.close()

    observations = {
        "wall_sec": round(time.perf_counter() - started, 3),
        "composition_id": result["id"],
        "child_job_ids": result["child_job_ids"],
        "shot_asset_ids": result["shot_asset_ids"],
        "final_asset_id": result["asset_ids"][0],
        "roles": roles,
        "director": result["director"],
        "overflow_320": overflow,
        "console_errors": console_errors,
        "page_errors": page_errors,
    }
    check(not console_errors and not page_errors, "browser emitted console or page errors")
    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    print("PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
