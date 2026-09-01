#!/usr/bin/env python3
"""実ブラウザで、高画質化の「出す大きさ」を確かめる。

倍率がモデルの宣言から出ていること、その写真で出せない倍率が並ばないこと、
そして選び直すと案内の寸法が付いてくることを見る。画面が倍率を決め打ちして
いないか（別の倍率の重みを足したとき黙って外れないか）はここでしか出ない。

Playwright は core venv に入れない（AGENTS.md）。持っている interpreter で回す:

    /path/to/other/.venv/bin/python scripts/ux_upscale_scale_e2e.py \\
        --media-forge-url http://127.0.0.1:9137 \\
        --evidence-dir /tmp/upscale-scale-evidence
"""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DESKTOP = {"width": 1280, "height": 900}


class Failure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def write_png(path: Path, width: int, height: int) -> None:
    """依存を足さずに、狙った寸法の PNG を書く。寸法だけが要る。"""
    rows = b"".join(
        b"\x00" + bytes(
            value
            for x in range(width)
            for value in ((x * 7 + y * 3) % 256, (y * 5) % 256, 90)
        )
        for y in range(height)
    )

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def chips(page: Page) -> list[tuple[str, bool]]:
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('#upscale-scales .chip'))"
        ".map((chip) => [chip.textContent.trim(), chip.getAttribute('aria-checked') === 'true'])"
    )


def attach(page: Page, path: Path, mode: str = "upscale") -> None:
    page.set_input_files("#source-file", str(path))
    page.wait_for_selector("#edit-actions .edit-action", timeout=10_000)
    page.click(f"#edit-actions .edit-action[data-edit-mode='{mode}']")
    page.wait_for_timeout(200)


def run(url: str, evidence: Path) -> None:
    evidence.mkdir(parents=True, exist_ok=True)
    square = evidence / "source-1024.png"
    middling = evidence / "source-2000x1500.png"
    large = evidence / "source-4032x3024.png"
    write_png(square, 1024, 1024)
    write_png(middling, 2000, 1500)
    write_png(large, 4032, 3024)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=DESKTOP)
        page.goto(url, wait_until="networkidle")
        page.click("[data-create-media='photo']")
        page.wait_for_timeout(200)

        # 1.05MP。4 倍でも 16.8MP なので、3 つとも出せる。
        attach(page, square)
        found = chips(page)
        check(
            [label for label, _ in found] == ["原寸のまま", "2倍", "4倍"],
            f"選べる倍率がモデルの宣言と合わない: {found}",
        )
        check(
            found[-1][1] is True,
            f"入る中でいちばん大きいものが既定になっていない: {found}",
        )
        note = page.inner_text("#upscale-note")
        check("1024×1024 → 4096×4096" in note, f"案内が 4 倍の寸法を書いていない: {note}")
        page.screenshot(path=str(evidence / "1-square-x4.png"))

        # 選び直すと、案内の寸法が付いてくる。
        page.click("#upscale-scales .chip[data-upscale-scale='1']")
        page.wait_for_timeout(150)
        note = page.inner_text("#upscale-note")
        check("1024×1024 のまま" in note, f"原寸を選んでも案内が変わらない: {note}")
        check("→" not in note, f"寸法が変わらないのに矢印が出ている: {note}")
        page.screenshot(path=str(evidence / "2-square-x1.png"))

        # 3.0MP。4 倍は 48MP で上限を超えるので出さない。
        attach(page, middling)
        found = chips(page)
        check(
            [label for label, _ in found] == ["原寸のまま", "2倍"],
            f"出せない 4 倍が並んでいる: {found}",
        )
        check(found[-1][1] is True, f"既定が入る中の最大でない: {found}")
        note = page.inner_text("#upscale-note")
        check("4倍は" in note and "24,000,000" in note, f"消えた倍率の理由が無い: {note}")
        page.screenshot(path=str(evidence / "3-middling-x2.png"))

        # 12.2MP のスマホ写真。原寸だけが出せる。前は写真ごと断られていた。
        attach(page, large)
        check(
            page.is_hidden("#upscale-scale-field"),
            "選べるものが 1 つしか無いのに選択肢を出している",
        )
        note = page.inner_text("#upscale-note")
        check("4032×3024 のまま" in note, f"原寸で通ることが書かれていない: {note}")
        check("大きすぎます" not in note, f"通るのに断っている: {note}")
        check("2倍・4倍は" in note, f"消えた倍率の理由が無い: {note}")
        page.screenshot(path=str(evidence / "4-large-x1.png"))

        # 送るときに倍率が付く。画面が出した寸法と核が使う倍率を一致させる。
        sent = page.evaluate(
            "() => ({targets: upscaleTargets(), chosen: upscaleScale(),"
            " source: state.source})"
        )
        check(sent["chosen"] == 1, f"送る倍率が原寸になっていない: {sent}")
        check(sent["targets"] == [1], f"出せる倍率が原寸だけになっていない: {sent}")

        # 直し方ごとに別のモデルである。ブレ補正で拡大の倍率と単価が出ないこと。
        attach(page, square, mode="deblur")
        check(
            page.is_hidden("#upscale-scale-field"),
            "寸法の変わらない直しに、出す大きさの選択肢を出している",
        )
        note = page.inner_text("#upscale-note")
        check("1024×1024 のまま" in note, f"ブレ補正の案内が寸法を変えている: {note}")
        check("4096" not in note, f"ブレ補正に拡大の寸法が出ている: {note}")
        # NAFNet は 1.02 秒 / メガピクセル、SwinIR は 21.5。取り違えるとここで出る。
        check("およそ 1 秒" in note, f"ブレ補正の単価が拡大のものになっている: {note}")
        page.screenshot(path=str(evidence / "5-deblur.png"))

        browser.close()
    print(f"ok: upscale scale chooser verified in a real browser ({evidence})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", default="http://127.0.0.1:9130")
    parser.add_argument("--evidence-dir", default="/tmp/upscale-scale-evidence")
    args = parser.parse_args()
    run(args.media_forge_url, Path(args.evidence_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
