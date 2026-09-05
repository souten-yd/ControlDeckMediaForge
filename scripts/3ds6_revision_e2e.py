#!/usr/bin/env python3
"""Standalone browser acceptance for side-by-side scene revision restore."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from playwright.sync_api import sync_playwright


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--chrome", type=Path, default=Path("/usr/bin/google-chrome"))
    args = parser.parse_args()
    base_url = args.media_forge_url.rstrip("/")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(args.chrome),
            headless=False,
            args=["--enable-webgl", "--ignore-gpu-blocklist"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        page.click('[data-create-media="3d"]')
        scene_button = page.locator("#scene-list [data-scene-id]").first
        scene_button.wait_for(timeout=15_000)
        scene_id = scene_button.get_attribute("data-scene-id") or ""
        scene_button.click()
        page.wait_for_function(
            "() => document.querySelectorAll('#scene-revisions .row').length >= 2",
            timeout=15_000,
        )
        before: dict[str, Any] = page.request.get(
            f"{base_url}/workspace-api/scenes/{scene_id}"
        ).json()
        current = next(
            item
            for item in before["revisions"]
            if item["id"] == before["scene"]["current_revision_id"]
        )
        older = [item for item in before["revisions"] if item["id"] != current["id"]]
        target = next(
            (item for item in older if item.get("dependencies")),
            min(older, key=lambda item: item["sequence"]),
        )
        target_source = page.request.get(
            f"{base_url}/api/v1/assets/{target['source_asset_id']}/content"
        ).body()

        compare_started = time.monotonic()
        page.locator(f'[data-scene-compare="{target["id"]}"]').click()
        page.wait_for_selector("#scene-compare-dialog[open]")
        page.wait_for_function(
            "() => document.querySelector('#scene-compare-restore')?.disabled === false",
            timeout=30_000,
        )
        compare_elapsed_sec = time.monotonic() - compare_started
        check(
            "triangle" in page.locator("#scene-compare-old-status").inner_text().lower()
            or "三角形" in page.locator("#scene-compare-old-status").inner_text(),
            "older preview did not expose measured model facts",
        )
        check(
            "triangle" in page.locator("#scene-compare-current-status").inner_text().lower()
            or "三角形" in page.locator("#scene-compare-current-status").inner_text(),
            "current preview did not expose measured model facts",
        )
        page.screenshot(
            path=str(args.evidence_dir / "3ds6-revision-compare.png"), full_page=True
        )
        restore_started = time.monotonic()
        page.click("#scene-compare-restore")
        page.wait_for_function(
            "count => document.querySelectorAll('#scene-revisions .row').length === count + 1",
            arg=len(before["revisions"]),
            timeout=30_000,
        )
        restore_elapsed_sec = time.monotonic() - restore_started
        after: dict[str, Any] = page.request.get(
            f"{base_url}/workspace-api/scenes/{scene_id}"
        ).json()
        restored = next(
            item
            for item in after["revisions"]
            if item["id"] == after["scene"]["current_revision_id"]
        )
        restored_source = page.request.get(
            f"{base_url}/api/v1/assets/{restored['source_asset_id']}/content"
        ).body()
        provenance = page.request.get(
            f"{base_url}/api/v1/assets/{restored['source_asset_id']}/provenance"
        ).json()
        check(restored["sequence"] == current["sequence"] + 1, "sequence did not advance")
        check(restored["parent_revision_id"] == current["id"], "history was not linear")
        check(restored["source_asset_id"] != target["source_asset_id"], "source was aliased")
        check(restored["preview_asset_id"] != target["preview_asset_id"], "preview was aliased")
        check(restored_source == target_source, "restored Blender bytes differ")
        check(provenance["operation"] == "scene.revision.restore", "restore provenance differs")
        check(
            provenance["parameters"]["restored_revision_id"] == target["id"],
            "restore source revision is absent",
        )

        page.evaluate("document.documentElement.lang = 'en'; renderSceneText();")
        page.wait_for_function(
            "() => document.querySelector('#scene-revisions [data-scene-compare]')?.textContent === 'Compare with current'",
            timeout=15_000,
        )
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#scene-revisions [data-scene-compare]").first.click()
        page.wait_for_function(
            "() => document.querySelector('#scene-compare-restore')?.disabled === false",
            timeout=30_000,
        )
        overflow = page.evaluate(
            "document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(overflow == 0, "revision UI overflows at 390px")
        page.screenshot(
            path=str(args.evidence_dir / "3ds6-revision-mobile-compare.png"), full_page=True
        )
        page.click("#scene-compare-cancel")
        page.wait_for_selector("#scene-compare-dialog", state="hidden")
        observations = {
            "scene_id": scene_id,
            "target_revision_id": target["id"],
            "previous_current_revision_id": current["id"],
            "restored_revision_id": restored["id"],
            "revision_count_before": len(before["revisions"]),
            "revision_count_after": len(after["revisions"]),
            "restored_source_bytes": len(restored_source),
            "restored_source_sha256": hashlib.sha256(restored_source).hexdigest(),
            "dependencies": len(restored["dependencies"]),
            "compare_elapsed_sec": compare_elapsed_sec,
            "restore_elapsed_sec": restore_elapsed_sec,
            "mobile_overflow_390": overflow,
            "console_errors": console_errors,
            "page_errors": page_errors,
        }
        check(
            not console_errors and not page_errors,
            f"browser errors: console={console_errors!r}, page={page_errors!r}",
        )
        browser.close()

    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
