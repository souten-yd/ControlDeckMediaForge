#!/usr/bin/env python3
"""Real-process/browser acceptance for UX2 C3 intentional variation batches."""

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


def http_json(
    base_url: str, path: str, *, method: str = "GET", value: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = None if value is None else json.dumps(value).encode()
    request = urllib.request.Request(
        base_url + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def wait_batch(base_url: str, batch_id: str, predicate, timeout: float = 15) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = http_json(base_url, f"/workspace-api/creative/batches/{batch_id}")
        if predicate(last):
            return last
        time.sleep(0.05)
    raise AssertionError(f"batch condition timed out: {last}")


def request_payload(intent: str, *, delay: float = 0) -> dict[str, Any]:
    constraints: dict[str, Any] = {"width": 256, "height": 256, "seed": 700}
    if delay:
        constraints["_fake_delay_sec"] = delay
    return {
        "operation": "image.generate",
        "intent": intent,
        "inputs": [],
        "constraints": constraints,
        "output": {"format": "png", "count": 1},
        "qa": {},
        "local_only": True,
        "model_policy": "auto",
    }


def create_batch(base_url: str, axis: str, *, delay: float) -> dict[str, Any]:
    return http_json(base_url, "/workspace-api/creative/batches", method="POST", value={
        "request": request_payload(f"delayed {axis} batch", delay=delay),
        "creative_spec": {"variation": {"axis": axis}},
        "count": 4,
    })


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

        page.fill("#create-intent", "same companion in four deliberate poses")
        page.locator("#scene-framing summary").click()
        page.select_option("#creative-variation", "pose")
        page.click('#count-chips [data-count="4"]')
        page.click("#create-submit")
        page.wait_for_selector("#candidate-strip .thumb:nth-child(4)", timeout=20_000)
        pose_batch = http_json(args.media_forge_url, "/workspace-api/creative/batches")["items"][0]
        pose_ids = [plan["pose"]["id"] for plan in pose_batch["child_plans"]]
        pose_seeds = [plan["batch"]["seed"] for plan in pose_batch["child_plans"]]
        check(len(set(pose_ids)) == 4, "pose x4 did not create four explicit poses")
        check(len(set(pose_seeds)) == 4, "pose x4 did not create four explicit seeds")
        check(pose_batch["state"] == "succeeded" and len(pose_batch["asset_ids"]) == 4,
              "pose x4 did not preserve four outputs")
        observations["pose_x4"] = {"batch_id": pose_batch["id"], "poses": pose_ids, "seeds": pose_seeds}

        page.select_option("#creative-variation", "composition")
        page.fill("#create-intent", "same companion in four deliberate compositions")
        page.click("#create-submit")
        page.wait_for_function(
            """id => fetch('/workspace-api/creative/batches').then(r => r.json()).then(v =>
                v.items[0].id !== id && v.items[0].state === 'succeeded')""",
            arg=pose_batch["id"], timeout=20_000,
        )
        composition_batch = http_json(args.media_forge_url, "/workspace-api/creative/batches")["items"][0]
        composition_ids = [plan["composition"]["id"] for plan in composition_batch["child_plans"]]
        check(len(set(composition_ids)) == 4, "composition x4 did not create four explicit compositions")
        observations["composition_x4"] = {
            "batch_id": composition_batch["id"], "compositions": composition_ids,
        }

        delayed = create_batch(args.media_forge_url, "pose", delay=0.8)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('#app[aria-busy="false"]', timeout=15_000)
        page.wait_for_function(
            "() => !document.querySelector('#stage-progress').hidden"
            " && document.querySelector('#progress-phase').textContent.includes('差分を作っています')",
            timeout=5_000,
        )
        observations["reconnected_batch"] = {
            "batch_id": delayed["id"],
            "progress_text": page.locator("#progress-phase").inner_text(),
        }
        page.click("#progress-cancel")
        canceled = wait_batch(
            args.media_forge_url, delayed["id"],
            lambda item: item["state"] in {"canceled", "partial", "failed"},
        )
        check(not any(child["status"] in {"queued", "running"} for child in canceled["children"]),
              "logical cancel left a queued/running child")
        observations["cancel"] = {
            "state": canceled["state"],
            "child_statuses": [child["status"] for child in canceled["children"]],
        }

        partial = create_batch(args.media_forge_url, "composition", delay=0.18)
        partial = wait_batch(
            args.media_forge_url, partial["id"],
            lambda item: item["succeeded_count"] >= 1 and item["state"] == "running",
        )
        partial = http_json(
            args.media_forge_url,
            f"/workspace-api/creative/batches/{partial['id']}",
            method="DELETE",
        )
        partial = wait_batch(args.media_forge_url, partial["id"], lambda item: item["state"] == "partial")
        check(partial["asset_ids"], "partial batch discarded successful assets")
        observations["partial"] = {
            "state": partial["state"], "succeeded": partial["succeeded_count"],
            "assets_retained": len(partial["asset_ids"]),
            "child_statuses": [child["status"] for child in partial["children"]],
        }

        page.click("#mode-advanced")
        page.click("#nav-activity")
        page.wait_for_selector(f'[data-batch-id="{partial["id"]}"] details', timeout=5_000)
        row = page.locator(f'[data-batch-id="{partial["id"]}"]')
        row.locator("summary").click()
        child_text = row.locator("details .s").inner_text()
        check(all(job_id in child_text for job_id in partial["child_job_ids"]),
              "Advanced Activity did not drill down to every child")
        observations["advanced_activity_children"] = partial["child_job_ids"]
        page.screenshot(path=str(args.evidence_dir / "advanced-batch-activity.png"), full_page=True)

        page.set_viewport_size({"width": 320, "height": 640})
        observations["overflow_320"] = page.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(observations["overflow_320"] == 0, "320px viewport has horizontal overflow")
        page.screenshot(path=str(args.evidence_dir / "advanced-batch-activity-320.png"), full_page=True)
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
