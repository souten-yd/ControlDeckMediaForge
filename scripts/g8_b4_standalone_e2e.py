#!/usr/bin/env python3
"""Real-process/browser acceptance for the G8 B4 standalone workspace path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from playwright.sync_api import Page, sync_playwright


class Failure(AssertionError):
    pass


def check(value: bool, message: str) -> None:
    if not value:
        raise Failure(message)


def wait_terminal(page: Page, base_url: str, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        response = page.request.get(f"{base_url}/api/v1/jobs/{job_id}")
        check(response.ok, f"job poll failed: {response.status}")
        job = response.json()
        if job["status"] in {"succeeded", "failed", "canceled"}:
            return job
        page.wait_for_timeout(100)
    raise Failure("3D compile did not finish within 60 seconds")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--glb", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--chrome", type=Path, default=Path("/usr/bin/google-chrome"))
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    observations: dict[str, Any] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(args.chrome),
            headless=False,
            args=["--enable-webgl", "--ignore-gpu-blocklist"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        submitted: list[dict[str, Any]] = []
        page.on(
            "request",
            lambda request: submitted.append(json.loads(request.post_data or "{}"))
            if request.url.endswith("/api/v1/jobs") and request.method == "POST"
            else None,
        )

        page.goto(args.media_forge_url, wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        check(page.locator("#project-3d-section").is_visible(), "runtime-ready 3D section is hidden")
        check(not page.locator("#project-3d-submit").is_visible(), "3D action appeared before selecting an asset")
        check(not page.locator("#project-3d-options").is_visible(), "typed options leaked into Simple mode")

        page.set_input_files("#project-3d-file", str(args.glb))
        check(page.locator("#project-3d-submit").is_visible(), "3D action did not appear after GLB selection")
        page.set_viewport_size({"width": 320, "height": 640})
        observations["simple_overflow_320"] = page.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(observations["simple_overflow_320"] == 0, "3D Simple flow overflows at 320px")
        page.set_viewport_size({"width": 1280, "height": 900})
        page.click("#mode-advanced")
        check(page.locator("#project-3d-options").is_visible(), "typed options are unreachable in Advanced mode")
        page.check("#project-3d-repair-normals")
        page.check("#project-3d-remove-degenerate")
        page.fill("#project-3d-merge-distance", "0.000001")
        page.fill("#project-3d-triangle-budget", "12")
        page.select_option("#project-3d-collision", "box")
        page.select_option("#project-3d-materials", "basic_pbr")

        with page.expect_response(
            lambda response: response.url.endswith("/api/v1/jobs") and response.request.method == "POST",
            timeout=15_000,
        ) as accepted:
            page.click("#project-3d-submit")
        created = accepted.value.json()
        job = wait_terminal(page, args.media_forge_url.rstrip("/"), created["id"])
        check(job["status"] == "succeeded", f"3D job failed: {job.get('error')}")
        check(len(job["asset_ids"]) == 1, "3D job did not register exactly one ZIP")
        check(submitted, "browser job request was not observed")
        request = submitted[-1]
        check(request["operation"] == "asset.pack" and request["profile"] == "3d.project.glb",
              "workspace used a different public operation/profile")
        options = request["constraints"]["compile_options"]
        check(options == {
            "schema_version": "3d.compile-options@1",
            "apply_transforms": True,
            "repair_normals": True,
            "remove_degenerate": True,
            "merge_by_distance_m": 0.000001,
            "triangle_budget": 12,
            "lod_ratios": [],
            "collision": "box",
            "materials": "basic_pbr",
            "preview": "fixed_workbench",
        }, "browser did not send the exact typed options")

        page.click("#nav-library")
        page.wait_for_selector(f'[data-asset-id="{job["asset_ids"][0]}"]', timeout=10_000)
        card = page.locator(f'[data-asset-id="{job["asset_ids"][0]}"]')
        image = card.locator("img")
        check(image.is_visible(), "ZIP package card has no preview")
        check((image.get_attribute("src") or "").startswith("data:image/webp;base64,"),
              "ZIP preview is not the bounded WebP transport")
        card.click()
        page.wait_for_selector("#viewer[open]")
        page.wait_for_function(
            "id => document.querySelector('#viewer-3d-canvas')?.dataset.modelAssetId === id",
            arg=job["asset_ids"][0],
            timeout=10_000,
        )
        check(page.locator("#viewer-3d").is_visible(), "ZIP package did not open in the GLB viewer")
        check(page.locator("#viewer-caption").inner_text().startswith("3D ZIP ·"),
              "viewer did not identify the interactive package")
        check("三角形" in page.locator("#viewer-3d-stats").inner_text(),
              "interactive viewer did not report model geometry")
        page.screenshot(path=str(args.evidence_dir / "g8-b4-library-preview.png"), full_page=True)

        observations.update({
            "job_id": job["id"],
            "asset_id": job["asset_ids"][0],
            "request": request,
            "card_preview_prefix": (image.get_attribute("src") or "")[:28],
            "viewer_caption": page.locator("#viewer-caption").inner_text(),
            "viewer_stats": page.locator("#viewer-3d-stats").inner_text(),
            "console_errors": console_errors,
            "page_errors": page_errors,
        })
        check(
            not console_errors and not page_errors,
            f"browser emitted errors: console={console_errors!r}, page={page_errors!r}",
        )
        browser.close()

    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
