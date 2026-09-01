#!/usr/bin/env python3
"""実ブラウザで、土台に選べるモデルが本当に絵を作れるものだけかを確かめる。

直すだけの道具（拡大・ブレ補正・消して埋める）は「無から絵を作る」ことができない。
土台の一覧に並ぶと、選んだ利用者のあらゆる「作る」が model_unavailable で落ちる。

実測（2026-09-01、model_policy=manual で生成を投げた）:
    tog/nafnet-models               failed model_unavailable
    AEmotionStudio/lama-inpainting  failed model_unavailable
    mikestealth/SwinIR              failed model_unavailable

    /path/to/other/.venv/bin/python scripts/ux_base_model_choices_e2e.py \\
        --media-forge-url http://127.0.0.1:9137
"""

from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright

DESKTOP = {"width": 1280, "height": 900}

# 直すだけの道具。宣言している capability がこれだけなら土台になれない。
REPAIR_ONLY = {"image.upscale", "image.deblur", "image.erase"}


class Failure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def run(url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=DESKTOP)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1200)

        state = page.evaluate(
            """() => ({
              catalog: (state.modelCatalog||[]).map(m => ({
                id: m.model_id, installed: m.installed, healthy: m.healthy,
                runtime: m.has_runtime, kind: m.kind,
                media: m.media_types || ['image'],
                caps: m.capabilities || [],
              })),
              base: imageBaseModels().map(m => m.model_id),
            })"""
        )
        base = set(state["base"])
        check(bool(base), "土台の一覧が空である")

        # 直すだけのものは並ばない。
        for item in state["catalog"]:
            repair_only = bool(item["caps"]) and set(item["caps"]) <= REPAIR_ONLY
            if repair_only:
                check(
                    item["id"] not in base,
                    f"直すだけの道具が土台に並んでいる: {item['id']} {item['caps']}",
                )

        # 絵を作れて、導入済みで、走らせる worker があるものは並ぶ。
        for item in state["catalog"]:
            makes_pictures = any(name not in REPAIR_ONLY for name in item["caps"])
            usable = (
                item["installed"] and item["healthy"] and item["runtime"] is not False
                and item["kind"] != "lora" and "image" in item["media"]
            )
            if makes_pictures and usable:
                check(
                    item["id"] in base,
                    f"作れるのに土台に並んでいない: {item['id']} {item['caps']}",
                )

        options = page.evaluate(
            "() => Array.from(document.querySelectorAll('#model-choice-model option'))"
            ".map(o => o.textContent.trim())"
        )
        check(len(options) == len(base) + 1, f"選択肢と一覧が食い違う: {options} / {base}")
        for name in ("NAFNet", "LaMa", "SwinIR"):
            check(
                not any(name in option for option in options),
                f"直すだけの道具が選択肢に出ている: {options}",
            )

        browser.close()
    print(f"ok: only models that can make a picture are offered as a base ({sorted(base)})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", default="http://127.0.0.1:9130")
    args = parser.parse_args()
    run(args.media_forge_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
