#!/usr/bin/env python3
"""Installed-host browser acceptance for the G2 strict-edit vertical slice."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def media_json(base_url: str, path: str) -> Any:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=10) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--cookie-file", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--mask", type=Path)
    parser.add_argument("--mode", choices=("strict", "reference", "variation", "outpaint"), default="strict")
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password and args.cookie_file is None:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    if not args.source.is_file() or (args.mode == "strict" and (args.mask is None or not args.mask.is_file())):
        raise RuntimeError("source and required mask fixtures must exist")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    before = len(media_json(args.media_forge_url, "/api/v1/assets")["items"])
    errors: list[str] = []
    started = time.perf_counter()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(f"pageerror:{error}"))
        if args.cookie_file is not None:
            cookie_fields = next(
                line.split("\t")
                for line in args.cookie_file.read_text(encoding="utf-8").splitlines()
                if line.startswith("#HttpOnly_") or (line and not line.startswith("#"))
            )
            context.add_cookies([{
                "name": cookie_fields[5],
                "value": cookie_fields[6],
                "domain": urlsplit(args.control_deck_url).hostname,
                "path": cookie_fields[2],
                "httpOnly": cookie_fields[0].startswith("#HttpOnly_"),
                "secure": cookie_fields[3] == "TRUE",
            }])
        else:
            page.goto("/login")
            page.get_by_label("ユーザー名").fill(args.username)
            page.get_by_label("パスワード").fill(password)
            page.get_by_role("button", name="ログイン").click()
            expect(page).not_to_have_url("/login")
        page.goto("/x/media-forge/workspace/create")
        frame = page.frame_locator('iframe[title="Media Forge — workspace"]')
        expect(frame.locator("html")).to_have_attribute("data-bridge", "ready")
        frame.get_by_label("操作").select_option("image.edit")
        frame.get_by_label("編集方法").select_option(args.mode)
        frame.get_by_label("元画像").set_input_files(str(args.source))
        if args.mode == "outpaint":
            frame.get_by_label("幅").fill(str(args.width))
            frame.get_by_label("高さ").fill(str(args.height))
        if args.mode == "strict":
            expect(frame.get_by_text("白い部分だけを変更するマスクを指定します。黒い部分は1ピクセルも変更しません。")).to_be_visible()
            frame.get_by_label("編集マスク").set_input_files(str(args.mask))
        frame.get_by_label("作りたい画像").fill(
            "Close her mouth into a small gentle smile, preserve the same character and art style"
            if args.mode == "strict"
            else "Extend the scene naturally beyond the original canvas, preserve the complete centered source"
            if args.mode == "outpaint"
            else "Create a cheerful waving pose of the same character, preserve the orange mesh hair and anime style"
        )
        frame.get_by_role("button", name="生成する").click()
        expect(frame.get_by_text(
            "元画像とマスクをローカルへ取り込み中…"
            if args.mode == "strict" else "元画像をローカルへ取り込み中…"
        )).to_be_visible(timeout=10_000)
        expect(frame.get_by_role("heading", name="Library", exact=True)).to_be_visible(timeout=180_000)
        deadline = time.monotonic() + 10
        items: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            items = media_json(args.media_forge_url, "/api/v1/assets")["items"]
            if len(items) >= before + (3 if args.mode == "strict" else 2):
                break
            time.sleep(0.1)
        expected_delta = 3 if args.mode == "strict" else 2
        if len(items) < before + expected_delta:
            raise AssertionError({"before": before, "after": len(items)})
        result = items[0]
        provenance = media_json(args.media_forge_url, f"/api/v1/assets/{result['id']}/provenance")
        strict = next((
            item for item in provenance["validation"]
            if item["validator"] == "image.strict_edit.unmasked_pixel_diff"
        ), None)
        assert (strict is not None) == (args.mode == "strict")
        if strict is not None:
            assert strict["protected_pixel_difference"] == 0
        outpaint = next((
            item for item in provenance["validation"]
            if item["validator"] == "image.outpaint.source_pixel_diff"
        ), None)
        assert (outpaint is not None) == (args.mode == "outpaint")
        if outpaint is not None:
            assert outpaint["source_pixel_difference"] == 0
        assert len(result["parent_asset_ids"]) == 1
        assert len(provenance["reference_asset_hashes"]) == (2 if args.mode == "strict" else 1)
        assert provenance["parameters"]["constraints"]["edit_mode"] == (
            "inpaint" if args.mode == "strict" else args.mode
        )
        page.screenshot(path=args.evidence_dir / f"{args.mode}-edit-library.png", full_page=True)
        browser.close()

    observations = {
        "elapsed_sec": time.perf_counter() - started,
        "asset_count_before": before,
        "asset_count_after": len(items),
        "result_asset_id": result["id"],
        "mode": args.mode,
        "parent_asset_ids": result["parent_asset_ids"],
        "protected_pixel_difference": strict["protected_pixel_difference"] if strict else None,
        "editable_pixels": strict["editable_pixels"] if strict else None,
        "source_pixel_difference": outpaint["source_pixel_difference"] if outpaint else None,
        "generated_pixels": outpaint["generated_pixels"] if outpaint else None,
        "browser_errors": errors,
    }
    (args.evidence_dir / "evidence.json").write_text(
        json.dumps(observations, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(observations, ensure_ascii=False))
    if errors:
        raise AssertionError(errors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
