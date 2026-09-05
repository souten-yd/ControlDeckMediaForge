#!/usr/bin/env python3
"""Standalone browser acceptance for durable 3D texture generation and adoption."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from playwright.sync_api import Page, Route, sync_playwright


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def wait_job(page: Page, base_url: str, job_id: str, status: str, timeout: float = 30) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = page.request.get(f"{base_url}/api/v1/jobs/{job_id}")
        check(response.ok, f"job poll failed: {response.status}")
        job = response.json()
        if job["status"] == status:
            return job
        if job["status"] in {"succeeded", "failed", "canceled"} and job["status"] != status:
            raise AssertionError(f"job reached {job['status']} instead of {status}: {job.get('error')}")
        page.wait_for_timeout(100)
    raise AssertionError(f"job {job_id} did not reach {status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--chrome", type=Path, default=Path("/usr/bin/google-chrome"))
    args = parser.parse_args()
    base_url = args.media_forge_url.rstrip("/")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    observations: dict[str, Any] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(args.chrome), headless=False,
            args=["--enable-webgl", "--ignore-gpu-blocklist"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors: list[str] = []
        page_errors: list[str] = []
        submitted: list[dict[str, Any]] = []
        delay_next = True
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        def route_job(route: Route) -> None:
            nonlocal delay_next
            request = route.request
            if request.method != "POST":
                route.continue_()
                return
            payload = json.loads(request.post_data or "{}")
            submitted.append(payload)
            if delay_next:
                payload.setdefault("constraints", {})["_fake_delay_sec"] = 3
                delay_next = False
            route.continue_(post_data=json.dumps(payload))

        page.route("**/api/v1/jobs", route_job)
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        page.click('[data-create-media="3d"]')
        page.set_input_files("#scene-import-file", str(args.blend))
        page.fill("#scene-import-name", "3DS-6 texture acceptance")
        page.click("#scene-import-submit")
        page.wait_for_selector("#scene-list [data-scene-id]", timeout=30_000)
        page.locator("#scene-list [data-scene-id]").first.click()
        page.wait_for_selector(
            "#scene-material-object option:not([value=''])", state="attached", timeout=30_000
        )
        page.locator("#scene-material-title").click()
        page.wait_for_function("() => !document.querySelector('#scene-material-object')?.disabled")
        page.locator("#scene-material-object").select_option(index=1)
        page.fill("#scene-texture-prompt", "seamless worn green painted metal, no text")
        page.click("#scene-texture-generate")
        page.wait_for_function("() => document.querySelector('#scene-texture-cancel')?.hidden === false")
        first_id = page.request.get(f"{base_url}/api/v1/jobs").json()["items"][0]["id"]

        # A full page reload discards all in-memory UI state. The durable job context must
        # still route this job back to the selected scene without adopting it as Create work.
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        page.click('[data-create-media="3d"]')
        page.locator("#scene-list [data-scene-id]").first.click()
        page.locator("#scene-material-title").click()
        page.wait_for_function("() => document.querySelector('#scene-texture-cancel')?.hidden === false")
        check(page.locator("#mini-progress").is_hidden(), "texture job took over the global Create progress")
        page.click("#scene-texture-cancel")
        canceled = wait_job(page, base_url, first_id, "canceled")
        page.wait_for_function("() => document.querySelector('#scene-texture-retry')?.hidden === false")
        page.click("#scene-texture-retry")
        page.wait_for_function("() => document.querySelector('#scene-texture-preview')?.naturalWidth > 0", timeout=30_000)
        second_id = page.request.get(f"{base_url}/api/v1/jobs").json()["items"][0]["id"]
        succeeded = wait_job(page, base_url, second_id, "succeeded")
        page.click("#scene-texture-use")
        page.wait_for_function(
            "id => document.querySelector('#scene-material-image')?.value === id",
            arg=succeeded["asset_ids"][0],
        )
        revisions_before = page.locator("#scene-revisions .row").count()
        page.click("#scene-material-apply")
        page.wait_for_function(
            "count => document.querySelectorAll('#scene-revisions .row').length === count + 1",
            arg=revisions_before, timeout=30_000,
        )
        check(page.locator("#scene-material-status").inner_text() != "", "material adoption has no result status")

        request = succeeded["request"]
        context = request["constraints"]["scene_texture"]
        check(request["constraints"]["asset_brief"] == {"role": "texture", "target_surface": "3d"},
              "texture purpose was not sent to the image job")
        check(context["schema_version"] == "media-forge.scene-texture-request@1", "context schema differs")
        check(context["scene_id"].startswith("scene_") and context["source_revision_id"].startswith("revision_"),
              "durable scene identities are missing")
        check(context["object_name"] and context["uv_map"] and context["material_slot"] == 0,
              "material target context is incomplete")

        page.evaluate("document.documentElement.lang = 'en'; renderSceneText();")
        check(page.locator("#scene-texture-generate").inner_text() == "Create image", "English text did not update")
        page.set_viewport_size({"width": 390, "height": 844})
        overflow = page.evaluate("document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth")
        check(overflow == 0, "material generation UI overflows at 390px")
        page.screenshot(path=str(args.evidence_dir / "3ds6-texture-adopted.png"), full_page=True)

        observations = {
            "canceled_job_id": canceled["id"],
            "succeeded_job_id": succeeded["id"],
            "generated_asset_id": succeeded["asset_ids"][0],
            "scene_texture": context,
            "revision_count_before_adopt": revisions_before,
            "revision_count_after_adopt": page.locator("#scene-revisions .row").count(),
            "mobile_overflow_390": overflow,
            "submitted_requests": len(submitted),
            "console_errors": console_errors,
            "page_errors": page_errors,
        }
        check(not console_errors and not page_errors,
              f"browser errors: console={console_errors!r}, page={page_errors!r}")
        browser.close()

    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
