#!/usr/bin/env python3
"""Installed-host CI-3 acceptance for real Vision, cache and Director context."""

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


def audit(page: Page) -> list[dict]:
    return page.evaluate(
        """async () => {
          const response = await fetch('/api/v1/audit?action=addon.runtime.ai.complete&limit=100', {
            headers: {'X-Requested-With': 'ControlDeck'},
          });
          if (!response.ok) throw new Error(`audit ${response.status}`);
          return response.json();
        }"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    if not args.reference.is_file():
        raise FileNotFoundError(args.reference)
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
        before = audit(page)
        page.goto("/x/media-forge/workspace", wait_until="domcontentloaded")
        frame = workspace_frame(page)
        frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)
        frame.locator("#source-file").set_input_files(str(args.reference))
        frame.locator("#reference-intelligence").wait_for(state="visible")

        started = time.perf_counter()
        frame.get_by_role("button", name="主役", exact=True).click()
        frame.wait_for_function("() => state.referenceAnalysis?.analysis != null", timeout=300_000)
        first_elapsed = time.perf_counter() - started
        first = frame.evaluate("() => structuredClone(state.referenceAnalysis)")
        first_summary = frame.locator("#reference-analysis-summary").inner_text()
        page.screenshot(path=args.evidence_dir / "reference-identity-1280.png", full_page=True)

        started = time.perf_counter()
        frame.get_by_role("button", name="動き", exact=True).click()
        frame.wait_for_function("() => state.referenceAnalysis?.analysis_cache_hit === true", timeout=20_000)
        cache_elapsed = time.perf_counter() - started
        cached = frame.evaluate("() => structuredClone(state.referenceAnalysis)")

        started = time.perf_counter()
        directed = frame.evaluate(
            """async () => call('creative.direct', {
              intent: '同じオレンジメッシュのボーイッシュな女の子が手を振る',
              director_mode: 'refine',
              creative_spec: {},
              reference_analysis: referenceAnalysisRequest(),
            })"""
        )
        director_elapsed = time.perf_counter() - started
        check(directed["assistance_used"] is True, f"Director was skipped: {directed}")
        check(len(directed["reference_context"]) == 1, "Director did not receive accepted analysis")
        check(
            set(directed["reference_context"][0])
            == {"asset_id", "asset_hash", "focus", "action_state"},
            f"pose focus leaked unrelated fields: {directed['reference_context']}",
        )

        original = frame.evaluate(
            """async () => call('creative.direct', {
              intent: 'この文をそのまま使う', director_mode: 'original', creative_spec: {},
            })"""
        )
        check(original["skipped_reason"] == "original_mode", "original route invoked assistance")

        after = audit(page)
        delta = after[: max(0, len(after) - len(before))]
        capabilities = [item.get("resource_id") for item in reversed(delta)]
        check(capabilities == ["vision.analyze", "text.generate"], f"unexpected AI audit delta: {capabilities}")
        check(first["asset_hash"] == cached["asset_hash"], "cache changed reference identity")
        check(cached["analysis_cache_hit"] is True, "second analysis did not use cache")

        page.set_viewport_size({"width": 320, "height": 700})
        page.wait_for_timeout(250)
        overflow = frame.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        offenders = frame.evaluate(
            """() => Array.from(document.querySelectorAll('body *')).map(element => {
              const rect = element.getBoundingClientRect();
              return {tag: element.tagName, id: element.id, className: String(element.className),
                      left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width)};
            }).filter(item => item.right > document.documentElement.clientWidth + 1).slice(0, 20)"""
        )
        page.screenshot(path=args.evidence_dir / "reference-pose-320.png", full_page=True)
        check(overflow <= 0, f"workspace overflowed at 320px: {overflow}; {offenders}")
        browser.close()

    check(not browser_errors, f"browser errors: {browser_errors}")
    evidence = {
        "reference": str(args.reference.resolve()),
        "asset_id": first["asset_id"],
        "asset_hash": first["asset_hash"],
        "facts": first["facts"],
        "subject": first["analysis"]["subject"],
        "action_state": first["analysis"]["action_state"],
        "identity_summary": first_summary,
        "vision_elapsed_sec": round(first_elapsed, 3),
        "cache_elapsed_sec": round(cache_elapsed, 3),
        "director_elapsed_sec": round(director_elapsed, 3),
        "audit_delta": capabilities,
        "original_assistance_used": original["assistance_used"],
        "overflow_320px": overflow,
        "overflow_offenders": offenders,
        "browser_errors": browser_errors,
    }
    (args.evidence_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
