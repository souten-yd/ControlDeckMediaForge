#!/usr/bin/env python3
"""実ブラウザで、使うモデルの一覧が「いま頼む操作」に追随するかを確かめる。

モデルによってできることは違う。FLUX.2-dev は文章から作ることしかできず、編集は
宣言していない。それを編集のときにも並べると、選んだ利用者は押した瞬間に
model_unavailable を受け取る。実機（インストール版 0.21.0）で確認した:

    image.generate  manual=city96/FLUX.2-dev-gguf  -> routing 通過
    image.edit      manual=city96/FLUX.2-dev-gguf  -> model_unavailable
                                                      画面には「使えるモデルが
                                                      ありません。」と出る

    /path/to/other/.venv/bin/python scripts/ux_model_choice_follows_the_job_e2e.py \\
        --media-forge-url http://127.0.0.1:9137
"""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import Page, sync_playwright

PHONE = {"width": 390, "height": 844}


class Failure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def write_png(path: Path, width: int, height: int) -> None:
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


def offered(page: Page) -> list[str]:
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('#model-choice-model option'))"
        ".map(o => o.value).filter(Boolean)"
    )


def run(url: str) -> None:
    with TemporaryDirectory(prefix="model-choice-") as temporary:
        photo = Path(temporary) / "photo.png"
        write_png(photo, 640, 480)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport=PHONE)
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1200)

            installed = page.evaluate(
                "() => (state.modelCatalog||[]).filter(m => m.installed && m.healthy)"
                ".map(m => ({id: m.model_id, caps: m.capabilities || []}))"
            )
            generate_only = [
                item["id"] for item in installed
                if item["caps"] == ["image.text_to_image"]
            ]
            check(
                bool(generate_only),
                "文章からしか作れないモデルが導入されていない。この試験の前提が無い",
            )

            # 添付が無いときは、文章から作れるものが並ぶ。
            page.click("[data-create-media='image']")
            page.wait_for_timeout(400)
            listed = offered(page)
            for model_id in generate_only:
                check(model_id in listed, f"作れるのに並んでいない: {model_id} / {listed}")

            # 写真を付けて編集にすると、編集できないものは消える。
            page.set_input_files("#source-file", str(photo))
            page.wait_for_selector("#edit-actions .edit-action", timeout=10_000)
            page.click("#edit-actions .edit-action[data-edit-mode='reference']")
            page.wait_for_timeout(500)
            listed = offered(page)
            for model_id in generate_only:
                check(
                    model_id not in listed,
                    f"編集できないモデルが編集の一覧に並んでいる: {model_id} / {listed}",
                )
            check(bool(listed), f"編集できるモデルまで消えている: {listed}")
            chosen = page.evaluate("() => state.modelChoice")
            check(chosen == "auto", f"消えたモデルの指定が残っている: {chosen}")

            # 直すだけの操作は、使うモデルが capability で決まる。選ばせない。
            page.click("[data-create-media='photo']")
            page.wait_for_timeout(300)
            page.set_input_files("#source-file", str(photo))
            page.wait_for_selector("#edit-actions .edit-action", timeout=10_000)
            page.click("#edit-actions .edit-action[data-edit-mode='upscale']")
            page.wait_for_timeout(500)
            check(
                page.is_hidden("#model-choice"),
                "直すだけの操作で、使うモデルを選ばせている",
            )
            check(
                page.evaluate("() => state.modelChoice") == "auto",
                "直すだけの操作に、前の指定が残っている",
            )

            browser.close()
    print("ok: the model list follows what is being asked for")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", default="http://127.0.0.1:9130")
    args = parser.parse_args()
    run(args.media_forge_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
