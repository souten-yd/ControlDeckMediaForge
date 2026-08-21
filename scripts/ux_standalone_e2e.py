#!/usr/bin/env python3
"""Real-browser layout and disclosure checks for the PR-U1 workspace shell.

Runs against a standalone Media Forge (no ControlDeck), so it exercises the
`window.parent === window` transport path. Bridge, theme tokens, grants and
mobile embedding still need the installed host, which is PR-U7.

Playwright is deliberately absent from the Media Forge core venv (AGENTS.md
keeps core light), so run this with an interpreter that has it:

    /path/to/other/.venv/bin/python scripts/ux_standalone_e2e.py \
        --media-forge-url http://127.0.0.1:9130 \
        --evidence-dir /tmp/ux1-evidence
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

DESKTOP = {"width": 1280, "height": 800}
TABLET = {"width": 900, "height": 900}
PHONE = {"width": 390, "height": 844}
NARROW = {"width": 320, "height": 640}


class Failure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def horizontal_overflow(page: Page) -> int:
    return page.evaluate(
        "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
    )


def advanced_nodes(page: Page) -> int:
    return page.evaluate("() => document.querySelectorAll('[id^=\"advanced-\"]').length")


def visible(page: Page, selector: str) -> bool:
    return page.locator(selector).is_visible()


def ready(page: Page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)


def run(page: Page, url: str, evidence: Path) -> dict[str, Any]:
    observations: dict[str, Any] = {}

    # ── デスクトップ: 2 ペイン・3 ナビ・シンプルでは詳細要素が DOM に無い ──
    page.set_viewport_size(DESKTOP)
    started = time.perf_counter()
    ready(page, url)
    observations["desktop_ready_sec"] = round(time.perf_counter() - started, 3)

    check(advanced_nodes(page) == 0, "シンプルで advanced-* が DOM に存在する")
    check(page.locator("#shell-nav button").count() == 3, "ナビが 3 つではない")
    check(not visible(page, "#activity-badge"), "実行中が無いのに件数バッジが出ている")
    columns = page.evaluate("() => getComputedStyle(document.querySelector('#view-create')).gridTemplateColumns")
    check(len(columns.split()) == 2, f"デスクトップが 2 ペインではない: {columns}")
    check(horizontal_overflow(page) <= 0, "デスクトップで横スクロールが出ている")
    page.screenshot(path=str(evidence / "desktop-simple.png"), full_page=True)

    # ── 詳細モード: 要素が現れ、preferences に保存され、再読込後も残る ──
    page.click("#mode-advanced")
    page.wait_for_selector("#advanced-create", timeout=5_000)
    observations["advanced_nodes"] = advanced_nodes(page)
    check(observations["advanced_nodes"] >= 8, "詳細モードで advanced-* が足りない")
    check(page.locator("#advanced-policy option").count() == 6, "モデル方針が 6 種ではない")
    page.screenshot(path=str(evidence / "desktop-advanced.png"), full_page=True)

    page.click("#mode-simple")
    check(advanced_nodes(page) == 0, "シンプルへ戻しても advanced-* が残る")
    # 再読込をまたぐ復元は preferences の永続化が要る。standalone には host identity が
    # 無く /ws を張れないため、ここでは確認できない（PR-U7 の installed host で確認する）。
    observations["mode_persistence"] = "NOT TESTED (standalone)"

    # ── 可用性: 使えない操作はシンプルに出さない ──
    page.click("#nav-settings")
    page.wait_for_selector("#capability-list .row")
    states = page.evaluate(
        "() => Array.from(document.querySelectorAll('#capability-list .row'))"
        ".map(row => [row.dataset.capability, row.querySelector('.state').textContent])"
    )
    observations["capabilities"] = dict(states)
    check(any(value == "使えません" for _, value in states), "unavailable な capability が 1 つも無い")
    page.click("#nav-create")

    # ── 画像を添付すると編集操作が現れる ──
    sample = evidence / "sample.png"
    if not sample.exists():
        page.evaluate("() => {}")
    page.set_input_files("#source-file", str(sample))
    page.wait_for_selector("#edit-actions .edit-action", timeout=5_000)
    actions = page.evaluate(
        "() => Array.from(document.querySelectorAll('#edit-actions .edit-action'))"
        ".map(button => button.dataset.editMode)"
    )
    observations["edit_actions_simple"] = actions
    check(visible(page, "#guarantee-badge"), "保証の文言が出ていない")
    guarantee = page.locator("#guarantee-badge").inner_text()
    check(bool(guarantee.strip()), "保証の文言が空")
    observations["guarantee"] = guarantee

    # 選んだ操作に関係ない入力が出ていないこと（hidden がクラスに負ける崩れの検出）
    check(visible(page, "#mask-input"), "一部だけ直すのに変更場所の入力が出ていない")
    check(not visible(page, "#reference-input"), "選んでいない参照画像の入力が出ている")
    page.click('[data-edit-mode="multi_reference"]')
    check(visible(page, "#reference-input"), "参考を足して直すのに参照画像の入力が出ない")
    check(not visible(page, "#mask-input"), "参照編集なのに変更場所の入力が出ている")
    page.click('[data-edit-mode="inpaint"]')

    page.screenshot(path=str(evidence / "desktop-edit.png"), full_page=True)
    page.click("#attach-clear")
    check(not visible(page, "#edit-block"), "画像を外しても編集操作が残っている")

    # ── タブレット ──
    page.set_viewport_size(TABLET)
    page.wait_for_timeout(150)
    check(horizontal_overflow(page) <= 0, "900px で横スクロールが出ている")

    # ── モバイル: 下部タブ・単一列・横スクロールなし ──
    page.set_viewport_size(PHONE)
    page.wait_for_timeout(150)
    nav_position = page.evaluate("() => getComputedStyle(document.querySelector('#shell-nav')).position")
    check(nav_position == "fixed", f"モバイルで下部タブになっていない: {nav_position}")
    columns = page.evaluate("() => getComputedStyle(document.querySelector('#view-create')).gridTemplateColumns")
    check(len(columns.split()) == 1, f"モバイルが単一列ではない: {columns}")
    observations["phone_overflow_px"] = horizontal_overflow(page)
    check(observations["phone_overflow_px"] <= 0, "390px で横スクロールが出ている")

    tab_height = page.evaluate("() => document.querySelector('#nav-create').getBoundingClientRect().height")
    observations["tab_height_px"] = round(tab_height, 1)
    check(tab_height >= 44, f"タップ標的が 44px 未満: {tab_height}")
    page.screenshot(path=str(evidence / "phone-create.png"), full_page=True)

    page.click("#nav-library")
    page.wait_for_selector('#view-library:not([hidden])')
    grid_columns = page.evaluate("() => getComputedStyle(document.querySelector('#library-grid')).gridTemplateColumns")
    observations["phone_grid_columns"] = len(grid_columns.split())
    check(observations["phone_grid_columns"] == 2, f"モバイルの一覧が 2 列ではない: {grid_columns}")
    page.screenshot(path=str(evidence / "phone-library.png"), full_page=True)

    # ── 320px ──
    page.set_viewport_size(NARROW)
    page.wait_for_timeout(150)
    observations["narrow_overflow_px"] = horizontal_overflow(page)
    check(observations["narrow_overflow_px"] <= 0, "320px で横スクロールが出ている")
    page.screenshot(path=str(evidence / "narrow-library.png"), full_page=True)

    return observations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--dark", action="store_true", help="dark で描画して FOUC を確認する")
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            color_scheme="dark" if args.dark else "light",
            device_scale_factor=1,
        )
        page = context.new_page()
        page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}")
                if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(f"pageerror:{error}"))
        try:
            observations = run(page, args.media_forge_url, args.evidence_dir)
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
