#!/usr/bin/env python3
"""Real-browser acceptance for the mobile image/video Create switch."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def check(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:9165/create")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    observations: dict[str, Any] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)

        check(page.locator("#create-media-switch").is_visible(), "media switch is not visible")
        page.locator("#create-media-video").click()
        check(page.locator("#video-create-fields").is_visible(), "video form did not open")
        check(page.locator("#create-submit").is_disabled(), "unavailable video submission is enabled")
        check(page.locator("#video-create-settings").is_visible(), "video settings exit is missing")
        unavailable_note = page.locator("#video-create-note").inner_text()
        check(unavailable_note, "unavailable video reason is empty")

        sizes = page.locator("#create-media-switch button").evaluate_all(
            "buttons => buttons.map(button => ({width: button.getBoundingClientRect().width, "
            "height: button.getBoundingClientRect().height}))"
        )
        check(all(item["height"] >= 44 for item in sizes), f"switch touch target is too small: {sizes}")

        overflows: dict[str, int] = {}
        for width, height in ((390, 844), (320, 640)):
            page.set_viewport_size({"width": width, "height": height})
            overflows[str(width)] = page.evaluate(
                "() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)"
            )
            check(overflows[str(width)] == 0, f"{width}px viewport overflows")
        page.screenshot(path=str(args.evidence_dir / "mobile-video-switch-unavailable-320.png"), full_page=True)

        page.evaluate(
            """() => {
              state.capabilities['video.text_to_video'] = {state: 'experimental'};
              renderCreateMedia();
              const originalCall = call;
              window.__videoRequest = null;
              call = async (method, params = {}) => {
                if (method === 'jobs.create') {
                  window.__videoRequest = params;
                  return {id: 'job_mobile_video', status: 'queued', phase: null, progress: 0,
                    request: params, asset_ids: [], error: null, created_at: new Date().toISOString()};
                }
                if (method === 'jobs.watch') return {watching: ['job_mobile_video']};
                if (method === 'assets.import') return {id: 'asset_00000000000000000000000000000000',
                  mime_type: 'image/png', width: 256, height: 256};
                if (method === 'jobs.get') return {id: 'job_mobile_video', status: 'canceled',
                  phase: 'canceled', progress: 1, request: window.__videoRequest,
                  asset_ids: [], error: null, created_at: new Date().toISOString()};
                return originalCall(method, params);
              };
            }"""
        )
        check(not page.locator("#create-submit").is_disabled(), "experimental video submission stayed disabled")
        check(page.locator("#create-media-video-badge").is_visible(), "experimental label is missing")
        page.locator("#create-intent").fill("A small robot waves once")
        page.locator("#create-submit").click()
        page.wait_for_function("() => window.__videoRequest !== null")
        request = page.evaluate("() => window.__videoRequest")
        check(request["operation"] == "video.generate", f"unexpected operation: {request}")
        check(request["inputs"] == [], f"text-to-video has unexpected inputs: {request}")
        check(request["output"] == {"format": "mp4", "count": 1}, f"unexpected output: {request}")
        check(request["local_only"] is True, "local_only is not enforced")
        page.wait_for_function("() => state.activeJob === ''")

        page.evaluate(
            """() => {
              state.capabilities['video.text_to_video'] = {
                state: 'unavailable', reason: 'video_runtime_not_adopted'};
              state.capabilities['video.image_to_video'] = {state: 'experimental'};
              window.__videoRequest = null;
              renderCreateMedia();
            }"""
        )
        page.locator("#source-file").set_input_files({
            "name": "first-frame.png",
            "mimeType": "image/png",
            "buffer": base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            ),
        })
        page.wait_for_function("() => state.source !== null")
        check(not page.locator("#create-submit").is_disabled(), "image-to-video submission stayed disabled")
        page.locator("#create-intent").fill("The first frame moves gently")
        page.locator("#create-submit").click()
        page.wait_for_function("() => window.__videoRequest !== null")
        image_request = page.evaluate("() => window.__videoRequest")
        check(image_request["operation"] == "video.generate", f"unexpected I2V operation: {image_request}")
        check(image_request["inputs"] == [{"asset_id": "asset_00000000000000000000000000000000"}],
              f"image-to-video input differs: {image_request}")
        browser.close()

    check(not errors, f"browser errors: {errors}")
    observations.update({
        "unavailable_note": unavailable_note,
        "touch_targets": sizes,
        "overflow_px": overflows,
        "experimental_request": request,
        "experimental_image_request": image_request,
        "browser_errors": errors,
    })
    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
