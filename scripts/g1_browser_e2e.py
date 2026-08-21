#!/usr/bin/env python3
"""Exercise G1 through an installed ControlDeck workspace in a real browser."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect, sync_playwright


def media_request(base_url: str, path: str) -> Any:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=15) as response:
        return json.load(response)


def host_request(page: Page, path: str) -> dict[str, Any]:
    return page.evaluate(
        """async (path) => {
          const response = await fetch(`/api/v1${path}`, {
            credentials: "same-origin",
            headers: {"X-Requested-With": "ControlDeck"},
          });
          return {status: response.status, body: await response.json()};
        }""",
        path,
    )


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login")
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    expect(page).not_to_have_url("/login")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--timeout-sec", type=float, default=180)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    observations: dict[str, Any] = {"started_at": time.time(), "checks": {}}
    browser_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.on(
            "console",
            lambda message: browser_errors.append(f"console:{message.type}:{message.text}")
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
        try:
            login(page, args.username, password)
            page.goto("/x/media-forge/workspace")
            frame_selector = 'iframe[title="Media Forge — workspace"]'
            expect(page.locator(frame_selector)).to_have_count(1)
            embedded = page.frame_locator(frame_selector)
            expect(embedded.locator("html")).to_have_attribute("data-bridge", "ready")

            embedded.get_by_role("button", name="Models", exact=True).click()
            model_card = embedded.locator(".info-card").filter(has_text="black-forest-labs/FLUX.2-klein-4B")
            expect(model_card).to_contain_text("available · installed · Apache-2.0")
            observations["checks"]["model_available_installed"] = True

            assets_before = media_request(args.media_forge_url, "/api/v1/assets")["items"]
            host_jobs_before = host_request(page, "/jobs?limit=100")
            assert host_jobs_before["status"] == 200, host_jobs_before
            host_job_ids_before = {item["id"] for item in host_jobs_before["body"]}

            embedded.get_by_role("button", name="Create", exact=True).click()
            embedded.get_by_label("作りたい画像").fill(args.prompt)
            embedded.get_by_role("button", name="生成する").click()
            expect(embedded.get_by_text("running", exact=False)).to_be_visible(timeout=30_000)
            deadline = time.monotonic() + args.timeout_sec
            current_assets = assets_before
            while time.monotonic() < deadline:
                current_assets = media_request(args.media_forge_url, "/api/v1/assets")["items"]
                if len(current_assets) == len(assets_before) + 1:
                    break
                page.wait_for_timeout(250)
            else:
                raise AssertionError("Create did not produce exactly one asset before the bounded timeout")
            newest = current_assets[0]
            embedded.get_by_role("button", name="Library", exact=True).click()
            card = embedded.locator(".asset-card").filter(has_text=newest["id"])
            expect(card.locator("img")).to_be_visible(timeout=30_000)
            card.get_by_role("button", name="Provenance").click()
            provenance_text = embedded.locator("#provenance")
            expect(provenance_text).to_contain_text("black-forest-labs/FLUX.2-klein-4B")
            expect(provenance_text).to_contain_text("Apache-2.0")
            provenance = json.loads(provenance_text.text_content())
            page.screenshot(path=args.evidence_dir / "library-provenance.png", full_page=True)

            host_jobs_after = host_request(page, "/jobs?limit=100")
            assert host_jobs_after["status"] == 200, host_jobs_after
            created = [
                item
                for item in host_jobs_after["body"]
                if item["id"] not in host_job_ids_before
                and item.get("kind") == "addon.runtime.media-forge"
            ]
            assert len(created) == 1 and created[0]["status"] == "succeeded", created
            observations["checks"]["create_jobs_library_provenance"] = {
                "host_job_id": created[0]["id"],
                "host_job_status": created[0]["status"],
                "asset_id": newest["id"],
                "asset_dimensions": [newest["width"], newest["height"]],
                "model_id": provenance["model_id"],
                "weights_hash": provenance["weights_hash"],
                "license": provenance["license"],
            }
        finally:
            context.close()
            browser.close()

    observations["finished_at"] = time.time()
    observations["elapsed_sec"] = observations["finished_at"] - observations["started_at"]
    observations["browser_errors"] = browser_errors
    assert not browser_errors, browser_errors
    result_path = args.evidence_dir / "result.json"
    result_path.write_text(json.dumps(observations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(observations, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
