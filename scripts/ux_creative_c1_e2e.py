#!/usr/bin/env python3
"""Real-browser acceptance for UX2 C1 against a standalone Media Forge core."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


class Failure(AssertionError):
    pass


def check(value: bool, message: str) -> None:
    if not value:
        raise Failure(message)


def wait_for_count(items: list[dict[str, Any]], count: int, page: Page) -> None:
    deadline = time.monotonic() + 8
    while len(items) < count and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    check(len(items) >= count, f"job request {count} was not observed")


def capture_jobs(page: Page) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def intercept(route, request) -> None:
        payload = json.loads(request.post_data or "{}")
        captured.append(payload)
        route.fulfill(
            status=202,
            content_type="application/json",
            body=json.dumps({
                "id": "job_" + f"{len(captured):032x}",
                "status": "queued", "phase": None, "progress": 0.0,
                "request": payload, "asset_ids": [], "error": None,
                "created_at": "2026-08-22T00:00:00Z", "updated_at": "2026-08-22T00:00:00Z",
            }),
        )

    page.route("**/api/v1/jobs", intercept)
    page.route("**/api/v1/jobs/job_*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({
            "id": route.request.url.rsplit("/", 1)[-1],
            "status": "canceled", "phase": None, "progress": 0.0,
            "request": {"operation": "image.generate", "intent": "captured", "local_only": True},
            "asset_ids": [], "error": None,
            "created_at": "2026-08-22T00:00:00Z", "updated_at": "2026-08-22T00:00:00Z",
        }),
    ))
    return captured


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
        captured = capture_jobs(page)

        page.goto(args.media_forge_url, wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        observations["simple_advanced_nodes"] = page.locator('[id^="advanced-"]').count()
        check(observations["simple_advanced_nodes"] == 0, "advanced controls leaked into Simple DOM")
        check(not page.locator("#scene-framing").get_attribute("open"), "scene accordion is open by default")
        observations["domain_labels"] = page.locator("#domain-chips button").all_text_contents()
        check(observations["domain_labels"] == ["自動", "アニメ", "イラスト", "写真", "2Dゲーム", "ポスター"],
              "domain labels do not come from the expected catalog")

        page.fill("#create-intent", "prompt only baseline")
        page.click("#create-submit")
        wait_for_count(captured, 1, page)
        baseline = captured[0]
        observations["baseline_constraints"] = baseline["constraints"]
        check("creative_plan" not in baseline["constraints"], "Auto added a creative plan")
        check("model_id" not in baseline, "Auto added model_id")

        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        page.click('#domain-chips [data-domain="anime"]')
        page.locator("#scene-framing summary").click()
        page.select_option("#creative-scene", "presenting_device")
        page.select_option("#creative-pose", "holding_item")
        page.select_option("#creative-composition", "full_body_off_center")
        page.select_option("#creative-camera", "eye_level")
        page.select_option("#creative-variation", "expression")
        observations["independent_values"] = {
            key: page.locator(f"#creative-{key}").input_value()
            for key in ("scene", "pose", "composition", "camera", "variation")
        }
        page.fill("#create-intent", "device companion")
        page.click("#create-submit")
        wait_for_count(captured, 2, page)
        directed = captured[1]
        plan = directed["constraints"]["creative_plan"]
        observations["directed_plan"] = plan
        check(plan["domain"]["id"] == "anime", "domain did not compile to a routing hint")
        check(plan["scene"]["id"] == "presenting_device" and plan["pose"]["id"] == "holding_item",
              "scene and pose were not compiled independently")
        check(directed.get("model_id") is None, "creative routing forced a model")

        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        page.locator("#scene-framing summary").click()
        page.select_option("#creative-scene", "coding_at_desk")
        page.select_option("#creative-pose", "wave")
        page.fill("#create-intent", "invalid combination")
        before = len(captured)
        page.click("#create-submit")
        page.wait_for_timeout(300)
        check(len(captured) == before, "invalid combination reached job admission")
        observations["invalid_error"] = page.locator("#create-error").inner_text()
        check("組み合わせ" in observations["invalid_error"], "invalid combination has no inline reason")

        page.click("#mode-advanced")
        page.wait_for_selector("#advanced-domain")
        page.select_option("#advanced-scene", "presenting_device")
        page.select_option("#advanced-pose", "holding_item")
        page.fill("#advanced-scene-details", "orange-lit workbench")
        page.fill("#advanced-camera-details", "50mm natural perspective")
        observations["advanced_nodes"] = page.locator('[id^="advanced-"]').count()
        check(observations["advanced_nodes"] > 0, "Advanced template did not mount")

        page.set_viewport_size({"width": 320, "height": 640})
        page.click("#mode-simple")
        page.wait_for_timeout(100)
        observations["overflow_320"] = page.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(observations["overflow_320"] == 0, "320px viewport has horizontal overflow")
        tabbable = page.locator(
            'button:visible, textarea:visible, select:visible, input:not([type="file"]):visible, summary:visible'
        ).evaluate_all("nodes => nodes.map(node => node.id).filter(Boolean)")
        observations["tabbable_ids"] = tabbable
        check(tabbable.index("create-intent") < tabbable.index("creative-scene") < tabbable.index("create-submit"),
              "Create tab order is not logical")
        page.screenshot(path=str(args.evidence_dir / "creative-simple-320.png"), full_page=True)

        observations["console_errors"] = console_errors
        observations["page_errors"] = page_errors
        check(not console_errors and not page_errors, "browser emitted console/page errors")
        browser.close()

    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
