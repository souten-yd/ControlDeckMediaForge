#!/usr/bin/env python3
"""実ブラウザで、端末が持っている形式の写真が投入できることを確かめる。

iPhone の写真は既定で HEIC である。画面には HEIC を canvas で PNG へ直す経路が
あったのに、ファイル選択の `accept` が PNG と JPEG だけを並べていたので、写真が
そこまで届いていなかった。**選んでも何も起きない**、という形で表に出る。

Chromium は HEIC を復号しないので、ここで測れるのは「PNG / JPEG 以外の形式が
選択を通り、変換されて原寸のまま載るか」までである。実際の HEIC 復号は端末側の
仕事で、そこは iPhone でしか確かめられない。

    /path/to/other/.venv/bin/python scripts/ux_phone_photo_e2e.py \\
        --media-forge-url http://127.0.0.1:9137 \\
        --evidence-dir /tmp/phone-photo-evidence
"""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DESKTOP = {"width": 1280, "height": 900}
PHONE = {"width": 390, "height": 844}


class Failure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def png_bytes(width: int, height: int) -> bytes:
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

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def attach(page: Page, name: str, mime: str, payload: bytes) -> dict:
    page.set_input_files(
        "#source-file", {"name": name, "mimeType": mime, "buffer": payload}
    )
    page.wait_for_selector("#edit-actions .edit-action", timeout=10_000)
    page.wait_for_timeout(600)
    return page.evaluate(
        """() => ({
          source: state.source,
          measured: state.measured,
          uploadType: state.upload ? state.upload.type : null,
          label: (document.querySelector('#attach-size')||{}).textContent || '',
          error: (document.querySelector('#create-error')||{}).textContent || '',
        })"""
    )


def run(url: str, evidence: Path) -> None:
    evidence.mkdir(parents=True, exist_ok=True)
    # 「任意のサイズに切り取った」写真。16 の倍数でも、決まった並びの寸法でもない。
    cropped = png_bytes(1007, 661)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=PHONE)
        page.goto(url, wait_until="networkidle")

        # 選択の絞り込みが端末の写真を弾かない。
        accept = page.get_attribute("#source-file", "accept")
        check(accept == "image/*", f"選択が形式で絞られている: {accept}")
        references = page.get_attribute("#reference-files", "accept")
        check(references == "image/*", f"参考画像の選択が絞られている: {references}")

        page.click("[data-create-media='photo']")
        page.wait_for_timeout(200)

        # 端末が名乗る形式が PNG / JPEG でなくても、変換して載る。
        state = attach(page, "IMG_0001.HEIC", "image/heic", cropped)
        check(state["measured"] == {"width": 1007, "height": 661},
              f"端末の写真を測れていない: {state}")
        check(state["source"] == {"width": 1007, "height": 661},
              f"切り取った寸法が変えられている: {state}")
        check(state["uploadType"] == "image/png",
              f"取り込みが受ける形へ直していない: {state}")
        check("読み込めませんでした" not in state["error"],
              f"読み込めたのに断っている: {state}")
        page.screenshot(path=str(evidence / "1-heic-name.png"))

        # 形式を名乗らない端末もある。空の type でも同じ経路を通る。
        state = attach(page, "IMG_0002", "", cropped)
        check(state["source"] == {"width": 1007, "height": 661},
              f"形式を名乗らない写真が載っていない: {state}")
        check(state["uploadType"] == "image/png", f"変換されていない: {state}")

        # PNG と JPEG はそのまま送る。余分な canvas を通さない。
        state = attach(page, "shot.png", "image/png", cropped)
        check(state["uploadType"] == "image/png", f"PNG の扱いが変わった: {state}")
        check(state["source"] == {"width": 1007, "height": 661},
              f"PNG の寸法が変えられている: {state}")

        # 画像として読めないものは、読めないと言う。黙って「選んでいない」に
        # 見せない。
        state = attach(page, "notes.txt", "text/plain", b"not an image at all")
        check(state["source"] is None, f"読めないものを載せている: {state}")
        check("読み込めませんでした" in state["error"],
              f"読めない理由が出ていない: {state}")
        check("PNG か JPEG" not in state["error"],
              f"形式を変えて選び直せ、と案内している: {state}")
        page.screenshot(path=str(evidence / "2-undecodable.png"))

        browser.close()
    print(f"ok: the phone's own photo formats reach the workspace ({evidence})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", default="http://127.0.0.1:9130")
    parser.add_argument("--evidence-dir", default="/tmp/phone-photo-evidence")
    args = parser.parse_args()
    run(args.media_forge_url, Path(args.evidence_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
