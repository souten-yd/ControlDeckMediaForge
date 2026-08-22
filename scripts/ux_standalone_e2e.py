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

import jsonschema
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


def submitted_payload(page: Page, evidence: Path) -> dict[str, Any] | None:
    """送信内容だけを捕まえ、実際の生成は起こさせない。

    この開発機には実モデルが入っているため、本当に投げると GPU を数分占有する。
    """
    captured: list[dict[str, Any]] = []

    def intercept(route, request):
        try:
            captured.append(json.loads(request.post_data or "{}"))
        except json.JSONDecodeError:
            captured.append({})
        route.fulfill(
            status=202,
            content_type="application/json",
            body=json.dumps({
                "id": "job_" + "0" * 32, "status": "queued", "phase": None, "progress": 0.0,
                "request": captured[-1], "asset_ids": [], "error": None,
                "created_at": "2026-08-22T00:00:00Z", "updated_at": "2026-08-22T00:00:00Z",
            }),
        )

    page.route("**/api/v1/jobs", intercept)
    page.click("#create-submit")
    # 画像の取り込みを挟むと送信までに時間がかかる。捕捉できるまで待つ。
    deadline = time.monotonic() + 8
    while not captured and time.monotonic() < deadline:
        page.wait_for_timeout(100)
    page.wait_for_timeout(200)
    page.unroute("**/api/v1/jobs")
    if captured:
        (evidence / "submitted-request.json").write_text(
            json.dumps(captured[-1], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return captured[-1] if captured else None


FAKE_JOB_ID = "job_" + "0" * 32


def canned_job(route, _request) -> None:
    """捕まえた送信の job は実在しない。polling が 404 を出さないよう応答を用意する。"""
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({
            "id": FAKE_JOB_ID, "status": "canceled", "phase": None, "progress": 0.0,
            "request": {"operation": "image.generate", "intent": "captured", "local_only": True},
            "asset_ids": [], "error": None,
            "created_at": "2026-08-22T00:00:00Z", "updated_at": "2026-08-22T00:00:00Z",
        }),
    )


def pre_submit_checks(page: Page, evidence: Path) -> dict[str, Any]:
    """受付前検証。落ちるべきものが落ち、通るべきものが schema に適合すること。"""
    result: dict[str, Any] = {}
    page.route(f"**/api/v1/jobs/{FAKE_JOB_ID}", canned_job)

    # 以降は「書いていない」以外の理由で止まることを見たいので、先に書いておく
    page.fill("#create-intent", "受付前検証のためのテスト入力")

    source = page.evaluate("() => document.querySelector('#attach-size').textContent").split(" → ", 1)[0]

    # 外側を広げるのに広がっていない指定（詳細モードで元画像と同じ寸法を入れる）
    page.click("#mode-advanced")
    page.wait_for_selector("#advanced-width")
    source_width, source_height = (int(value) for value in source.split("×"))
    page.fill("#advanced-width", str(source_width))
    page.fill("#advanced-height", str(source_height))
    check(submitted_payload(page, evidence) is None, "広がっていない outpaint が送信された")
    result["outpaint_not_expanding_blocked"] = page.locator("#create-error").inner_text()
    check(bool(result["outpaint_not_expanding_blocked"].strip()), "止めた理由が表示されていない")
    page.click("#mode-simple")

    # 詳細モード: 16 の倍数でない幅
    page.click('[data-edit-mode="reference"]')
    page.click("#attach-clear")
    page.click("#mode-advanced")
    page.wait_for_selector("#advanced-width")
    page.fill("#advanced-width", "1000")
    check(submitted_payload(page, evidence) is None, "16 の倍数でない幅が送信された")
    result["non_multiple_blocked"] = page.locator("#create-error").inner_text()
    check(bool(result["non_multiple_blocked"].strip()),
          "16 の倍数でない幅を止めたのに理由が表示されていない")

    # 詳細モード: manual を選んだらモデル指定が必ず載る
    page.fill("#advanced-width", "512")
    page.fill("#advanced-height", "512")
    page.select_option("#advanced-policy", "manual")
    page.wait_for_timeout(100)
    schema = json.loads((Path(__file__).parents[1] / "schemas" / "job-request.json").read_text(encoding="utf-8"))
    if page.locator("#advanced-model").input_value():
        manual = submitted_payload(page, evidence)
        check(manual is not None, "manual の送信が捕まえられなかった")
        check(manual["model_policy"] == "manual" and bool(manual.get("model_id")),
              "manual なのに model_id が載っていない")
        jsonschema.validate(manual, schema)
        result["manual_model_id"] = manual["model_id"]
    else:
        check(submitted_payload(page, evidence) is None, "モデル未指定の manual が送信された")
        result["manual_without_model_blocked"] = page.locator("#create-error").inner_text()
    page.select_option("#advanced-policy", "auto")

    # 既定の送信が job-request schema に適合する
    payload = submitted_payload(page, evidence)
    check(payload is not None, "正しい入力が送信されていない")
    result["payload"] = payload
    jsonschema.validate(payload, schema)
    result["schema"] = "valid"
    check(payload["local_only"] is True, "local_only が true ではない")
    check("model_id" not in payload, "auto なのに model_id が載っている")
    page.click("#mode-simple")
    page.unroute(f"**/api/v1/jobs/{FAKE_JOB_ID}")
    return result


def draw_on_mask(page: Page, strokes: int = 3) -> None:
    """実際のポインタ操作で塗る。canvas への直接描画は経路の検証にならない。"""
    box = page.locator("#mask-canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.35, box["y"] + box["height"] * 0.35)
    page.mouse.down()
    for index in range(strokes):
        page.mouse.move(
            box["x"] + box["width"] * (0.35 + 0.08 * index),
            box["y"] + box["height"] * (0.45 + 0.05 * index),
            steps=6,
        )
    page.mouse.up()


def mask_editor_checks(page: Page, evidence: Path) -> dict[str, Any]:
    """外部ツール無しで inpaint の範囲を指定できること。"""
    result: dict[str, Any] = {}
    page.fill("#create-intent", "口元を笑顔に変える")
    page.click('[data-edit-mode="inpaint"]')
    check(visible(page, "#mask-draw"), "塗る導線が出ていない")
    check(not page.locator("#advanced-mask-file").count(), "シンプルにファイル指定が出ている")

    page.click("#mask-draw")
    page.wait_for_selector("#mask-dialog[open]")

    # 何も塗らずに決定しても閉じない
    page.click("#mask-apply")
    check(page.locator("#mask-dialog").get_attribute("open") is not None, "空のまま決定できてしまった")
    result["empty_mask_blocked"] = page.locator("#mask-hint").inner_text()
    check("塗って" in result["empty_mask_blocked"], "空マスクの理由が出ていない")

    draw_on_mask(page)
    page.screenshot(path=str(evidence / "mask-editor.png"))

    # 取り消しと消しゴムが操作できる
    page.click("#mask-undo")
    draw_on_mask(page)
    page.click("#mask-eraser")
    check(page.locator("#mask-eraser").get_attribute("aria-pressed") == "true", "消しゴムに切り替わらない")
    page.click("#mask-brush")

    page.click("#mask-apply")
    # 閉じた dialog は不可視なので、可視性ではなく属性で待つ
    page.wait_for_function(
        "() => !document.getElementById('mask-dialog').hasAttribute('open')", timeout=5_000
    )
    check(visible(page, "#mask-preview"), "塗った範囲の見本が出ていない")
    result["mask_state"] = page.locator("#mask-state").inner_text()
    check("ピクセル" in result["mask_state"], "塗った量が示されていない")

    # 塗った範囲が実際にマスク資産として送られる
    payload = submitted_payload(page, evidence)
    check(payload is not None, "マスク付きの送信が捕まえられなかった")
    check(payload["operation"] == "image.edit", "operation が image.edit ではない")
    check(payload["constraints"].get("strict_edit") is True, "strict_edit が立っていない")
    mask_id = payload["constraints"].get("editable_mask_asset_id", "")
    check(mask_id.startswith("asset_"), f"マスク資産が載っていない: {mask_id!r}")
    result["mask_asset_id"] = mask_id
    result["mask_constraints"] = payload["constraints"]
    return result


def outpaint_checks(page: Page, evidence: Path) -> dict[str, Any]:
    """広げ方の選択だけで有効な寸法が決まること。"""
    result: dict[str, Any] = {}
    page.click('[data-edit-mode="outpaint"]')
    check(visible(page, "#outpaint-input"), "広げ方の選択が出ていない")
    check(not visible(page, "#size-block"), "シンプルで寸法欄が出ている")
    page.click('#outpaint-ratios [data-ratio="16:9"]')
    page.click('#outpaint-scales [data-scale="2"]')
    result["note"] = page.locator("#outpaint-note").inner_text()
    check("中央" in result["note"], "中央配置であることが書かれていない")
    page.screenshot(path=str(evidence / "outpaint.png"))

    payload = submitted_payload(page, evidence)
    check(payload is not None, "outpaint の送信が捕まえられなかった")
    constraints = payload["constraints"]
    source_label = page.locator("#attach-size").inner_text().split(" → ", 1)[0]
    source_width, source_height = (int(value) for value in source_label.split("×"))
    check(constraints["width"] % 16 == 0 and constraints["height"] % 16 == 0, "16 の倍数ではない")
    check(constraints["width"] >= source_width and constraints["height"] >= source_height,
          "元画像を含んでいない")
    check(constraints["width"] > source_width or constraints["height"] > source_height,
          "どちらの辺も広がっていない")
    check(constraints.get("strict_edit") is True, "strict_edit が立っていない")
    result["constraints"] = constraints
    return result


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

    # 出力寸法が元画像で決まる操作では、無視される値を選ばせない
    check(not visible(page, "#size-block"), "結果に影響しないサイズ欄が出ている")

    page.route(f"**/api/v1/jobs/{FAKE_JOB_ID}", canned_job)
    observations["mask"] = mask_editor_checks(page, evidence)
    observations["outpaint"] = outpaint_checks(page, evidence)
    page.unroute(f"**/api/v1/jobs/{FAKE_JOB_ID}")

    # 受付前に落とすべきものを落としているか（GPU を取りに行かせない）
    observations["pre_submit"] = pre_submit_checks(page, evidence)

    # pre_submit_checks の中で添付を外している
    check(not visible(page, "#edit-block"), "画像を外しても編集操作が残っている")
    check(visible(page, "#size-block"), "生成に戻ってもサイズ欄が出ない")

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
