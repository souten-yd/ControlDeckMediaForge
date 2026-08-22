#!/usr/bin/env python3
"""Real-process/browser acceptance for UX2 C4 multi-cut Composer."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def get_json(base_url: str, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url + path) as response:
        return json.loads(response.read())


def patch_json(base_url: str, path: str, value: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(value).encode(),
        method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def wait_latest(base_url: str, predicate, timeout: float = 20) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        items = get_json(base_url, "/workspace-api/creative/compositions")["items"]
        last = items[0] if items else {}
        if last and predicate(last):
            return last
        time.sleep(0.05)
    raise AssertionError(f"composition condition timed out: {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    observations: dict[str, Any] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(args.media_forge_url, wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)

        page.click('#domain-chips [data-domain="poster"]')
        check(page.locator("#composition-options").is_visible(), "poster did not reveal composition controls")
        page.click('#count-chips [data-count="3"]')
        page.fill("#create-intent", "same orange companion in three production shots")
        page.fill("#composition-title", "オレンジ・コンパニオン")
        page.fill("#composition-caption", "コーディング、端末紹介、メイン立ち絵")
        page.click("#create-submit")
        page.wait_for_selector("#composition-text-edit", state="visible", timeout=20_000)
        first = wait_latest(args.media_forge_url, lambda item: item["state"] == "succeeded")
        check(len(first["child_job_ids"]) == 3 and len(first["shot_asset_ids"]) == 3,
              "three ordinary child shots were not retained")
        check(len(first["asset_ids"]) == 1, "final composed asset is missing")
        first_asset_id = first["asset_ids"][0]
        first_asset = get_json(args.media_forge_url, f"/api/v1/assets/{first_asset_id}")
        provenance = get_json(args.media_forge_url, f"/api/v1/assets/{first_asset_id}/provenance")
        check(provenance["parent_asset_ids"] == first["shot_asset_ids"], "child lineage is incomplete")
        observations["initial"] = {
            "composition_id": first["id"], "child_job_ids": first["child_job_ids"],
            "shot_asset_ids": first["shot_asset_ids"], "final_asset_id": first_asset_id,
            "sha256": first_asset["sha256"], "size": [first_asset["width"], first_asset["height"]],
        }
        page.screenshot(path=str(args.evidence_dir / "poster-three-cut.png"), full_page=True)

        image_jobs_before = [
            job for job in get_json(args.media_forge_url, "/api/v1/jobs")["items"]
            if job["request"]["operation"] == "image.generate"
        ]
        page.fill("#composition-edit-title", "文字だけ更新")
        page.fill("#composition-edit-caption", "カットはそのまま")
        page.click("#composition-update-text")
        page.wait_for_function(
            "() => document.querySelector('#composition-edit-status').textContent.includes('文字だけ更新しました')",
            timeout=8_000,
        )
        second = wait_latest(args.media_forge_url, lambda item: len(item["final_asset_ids"]) == 2)
        second_asset = get_json(args.media_forge_url, f"/api/v1/assets/{second['asset_ids'][0]}")
        image_jobs_after = [
            job for job in get_json(args.media_forge_url, "/api/v1/jobs")["items"]
            if job["request"]["operation"] == "image.generate"
        ]
        check(second["child_job_ids"] == first["child_job_ids"], "text edit regenerated child jobs")
        check(len(image_jobs_after) == len(image_jobs_before) == 3, "text edit created an image-generation job")
        check(second_asset["sha256"] != first_asset["sha256"], "changed title did not change final pixels")

        reproduced = patch_json(
            args.media_forge_url,
            f"/workspace-api/creative/compositions/{first['id']}",
            {"title": first["layout"]["title"], "caption": first["layout"]["caption"]},
        )
        reproduced_asset = get_json(args.media_forge_url, f"/api/v1/assets/{reproduced['asset_ids'][0]}")
        check(reproduced_asset["sha256"] == first_asset["sha256"],
              "same layout text and child assets did not reproduce the final PNG")
        observations["text_only_update"] = {
            "child_job_delta": len(image_jobs_after) - len(image_jobs_before),
            "final_revisions": len(reproduced["final_asset_ids"]),
            "changed_sha256": second_asset["sha256"],
            "reproduced_sha256": reproduced_asset["sha256"],
        }

        page.set_viewport_size({"width": 320, "height": 640})
        page.locator("#result-image").click()
        page.wait_for_selector("#viewer[open] #viewer-image", timeout=5_000)
        page.wait_for_function("() => document.querySelector('#viewer-image').naturalWidth > 0", timeout=5_000)
        observations["mobile_viewer_size"] = page.evaluate(
            "() => [document.querySelector('#viewer-image').naturalWidth, document.querySelector('#viewer-image').naturalHeight]"
        )
        page.locator("#viewer-close").click()
        observations["overflow_320"] = page.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(observations["overflow_320"] == 0, "320px viewport has horizontal overflow")
        page.screenshot(path=str(args.evidence_dir / "poster-mobile-320.png"), full_page=True)
        observations["console_errors"] = console_errors
        observations["page_errors"] = page_errors
        check(not console_errors and not page_errors,
              f"browser emitted errors: console={console_errors!r}, page={page_errors!r}")
        browser.close()

    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
