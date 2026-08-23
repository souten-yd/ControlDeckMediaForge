#!/usr/bin/env python3
"""Installed-host acceptance for the UX1 workspace.

standalone では確認できないものだけを見る: host bridge、theme token、
opaque iframe 越しの transport、preferences の永続化、そして
`mobile: "embedded"` にしたことでモバイル幅に状態カードではなく
workspace が出ること。

playwright は Media Forge の core venv に入れない（AGENTS.md）。

    /path/to/other/.venv/bin/python scripts/ux_control_deck_e2e.py \
        --control-deck-url http://127.0.0.1:8765 \
        --username mf-e2e --password-env MEDIA_FORGE_E2E_PASSWORD \
        --evidence-dir /tmp/ux7-evidence
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}
WORKSPACE = "/x/media-forge/workspace"


class Failure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login", wait_until="domcontentloaded")
    if "/login" not in page.url:
        return
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def workspace_frame(page: Page, timeout: float = 20.0):
    """host が描く iframe の中身を掴む。8 秒で状態画面へ切り替わる仕様なので待つ。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/addon-frame/media-forge" in frame.url:
                try:
                    if frame.locator("#app").count():
                        return frame
                except Exception:  # noqa: BLE001 - frame が入れ替わる瞬間がある
                    pass
        page.wait_for_timeout(200)
    return None


def theme_tokens(frame) -> dict[str, str]:
    return frame.evaluate(
        "() => Object.fromEntries(['bg','surface','text','border','muted','accent']"
        ".map(name => [name, getComputedStyle(document.documentElement)"
        ".getPropertyValue('--' + name).trim()]))"
    )


def desktop_checks(page: Page, evidence: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    page.set_viewport_size(DESKTOP)
    started = time.perf_counter()
    page.goto(WORKSPACE, wait_until="domcontentloaded")
    frame = workspace_frame(page)
    check(frame is not None, "workspace の iframe が現れない")
    frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)
    result["ready_sec"] = round(time.perf_counter() - started, 3)

    # host bridge が繋がっている（standalone ではなく ready）
    bridge = frame.evaluate("() => document.documentElement.dataset.bridge")
    check(bridge == "ready", f"host bridge に繋がっていない: {bridge}")
    result["bridge"] = bridge

    # theme token が host から届いて適用されている
    result["theme"] = theme_tokens(frame)
    check(all(result["theme"].values()), f"theme token が空: {result['theme']}")

    # capability と envelope が実値で届く
    result["envelope"] = frame.evaluate(
        "() => { const raw = document.getElementById('advanced-size-hint'); return raw ? raw.textContent : ''; }"
    )
    presets = frame.evaluate(
        "() => Array.from(document.querySelectorAll('#size-presets [data-preset]'))"
        ".map(chip => [chip.dataset.preset, chip.dataset.width || null, chip.dataset.height || null])"
    )
    result["presets"] = presets
    check(
        [item[0] for item in presets] == [
            "square", "landscape", "portrait", "wide", "tall", "cinema", "custom",
        ],
        f"サイズ preset が現行設計と一致しない: {presets}",
    )
    for _name, raw_width, raw_height in presets[:-1]:
        width, height = int(raw_width), int(raw_height)
        check(width % 16 == 0 and height % 16 == 0, f"preset が 16 の倍数ではない: {presets}")
    check(presets[-1][1:] == [None, None], f"custom preset が固定寸法を持っている: {presets}")

    check(frame.evaluate("() => document.querySelectorAll('[id^=\"advanced-\"]').length") == 0,
          "シンプルで advanced-* が DOM にある")
    page.screenshot(path=str(evidence / "host-desktop-simple.png"))

    # 詳細モードが preferences に保存され、再読込後も残る（standalone では確認できない）
    frame.click("#mode-advanced")
    frame.wait_for_selector("#advanced-create", timeout=10_000)
    page.reload(wait_until="domcontentloaded")
    frame = workspace_frame(page)
    check(frame is not None, "再読込後に workspace が現れない")
    frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)
    result["mode_after_reload"] = frame.evaluate(
        "() => document.getElementById('mode-advanced').getAttribute('aria-pressed')"
    )
    check(result["mode_after_reload"] == "true", "詳細モードが再読込後に復元されない")
    page.screenshot(path=str(evidence / "host-desktop-advanced.png"))
    frame.click("#mode-simple")

    # route が host の URL へ同期する
    frame.click("#nav-library")
    page.wait_for_timeout(800)
    result["route_after_library"] = page.url
    check(page.url.rstrip("/").endswith("/library"), f"route が同期していない: {page.url}")
    page.screenshot(path=str(evidence / "host-desktop-library.png"))
    return result


def mobile_checks(page: Page, evidence: Path) -> dict[str, Any]:
    """mobile: "embedded" の唯一の目的。状態カードではなく workspace が出ること。"""
    result: dict[str, Any] = {}
    page.set_viewport_size(PHONE)
    page.goto(WORKSPACE, wait_until="domcontentloaded")
    page.wait_for_timeout(1_000)

    body = page.inner_text("body")
    result["companion_card_shown"] = "この拡張機能の作業画面はデスクトップ向けです" in body
    check(not result["companion_card_shown"],
          "モバイルで状態カードが出ている（embedded 宣言が効いていない）")

    frame = workspace_frame(page)
    check(frame is not None, "モバイルで workspace の iframe が現れない")
    frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)

    nav_position = frame.evaluate(
        "() => getComputedStyle(document.querySelector('#shell-nav')).position"
    )
    check(nav_position == "fixed", f"モバイルで下部タブになっていない: {nav_position}")
    columns = frame.evaluate(
        "() => getComputedStyle(document.querySelector('#view-create')).gridTemplateColumns"
    )
    check(len(columns.split()) == 1, f"モバイルが単一列ではない: {columns}")

    result["overflow_px"] = frame.evaluate(
        "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
    )
    check(result["overflow_px"] <= 0, f"モバイルで横スクロールが出ている: {result['overflow_px']}")
    result["tab_height_px"] = round(frame.evaluate(
        "() => document.querySelector('#nav-create').getBoundingClientRect().height"
    ), 1)
    check(result["tab_height_px"] >= 44, f"タップ標的が 44px 未満: {result['tab_height_px']}")
    page.screenshot(path=str(evidence / "host-phone-create.png"))

    frame.click("#nav-library")
    page.wait_for_timeout(600)
    grid = frame.evaluate(
        "() => getComputedStyle(document.querySelector('#library-grid')).gridTemplateColumns"
    )
    result["grid_columns"] = len(grid.split())
    check(result["grid_columns"] == 2, f"モバイルの一覧が 2 列ではない: {grid}")
    page.screenshot(path=str(evidence / "host-phone-library.png"))

    frame.click("#nav-create")
    page.wait_for_timeout(300)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise SystemExit(f"password environment variable is unset: {args.password_env}")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    observations: dict[str, Any] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            base_url=args.control_deck_url,
            color_scheme="dark" if args.dark else "light",
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.on("console", lambda message: errors.append(f"console:{message.text}")
                if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(f"pageerror:{error}"))
        try:
            login(page, args.username, password)
            observations["desktop"] = desktop_checks(page, args.evidence_dir)
            observations["mobile"] = mobile_checks(page, args.evidence_dir)
        finally:
            context.close()
            browser.close()

    observations["console_errors"] = errors
    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    if errors:
        print(f"FAILED: browser reported {len(errors)} error(s)")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
