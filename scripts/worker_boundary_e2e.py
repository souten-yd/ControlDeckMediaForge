#!/usr/bin/env python3
"""Installed-Host acceptance for worker-owned strict-edit/outpaint composition."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


def check(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login", wait_until="domcontentloaded")
    if "/login" not in page.url:
        return
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def workspace_frame(page: Page):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/addon-frame/media-forge" in frame.url and frame.locator("#app").count():
                return frame
        page.wait_for_timeout(200)
    raise AssertionError("Media Forge workspace iframe did not become available")


def import_asset(frame, path: Path, purpose: str) -> dict[str, Any]:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return frame.evaluate(
        """async value => {
          const binary = atob(value.base64);
          const bytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
          }
          const file = new File([bytes], value.name, {type: 'image/png'});
          return importFile(file, value.purpose);
        }""",
        {"base64": encoded, "name": path.name, "purpose": purpose},
    )


def wait_job(frame, job_id: str, timeout: float = 600) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = frame.evaluate("id => call('jobs.get', {job_id: id})", job_id)
        if last.get("status") in {"succeeded", "failed", "canceled"}:
            return last, time.perf_counter() - started
        frame.wait_for_timeout(1000)
    raise AssertionError(f"job did not finish: {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--strict-source", required=True, type=Path)
    parser.add_argument("--strict-mask", required=True, type=Path)
    parser.add_argument("--outpaint-source", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    for path in (args.strict_source, args.strict_mask, args.outpaint_source):
        if not path.is_file():
            raise FileNotFoundError(path)
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    browser_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            base_url=args.control_deck_url, viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: browser_errors.append(f"console:{message.type}:{message.text}")
            if message.type == "error" else None,
        )
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
        login(page, args.username, password)
        page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
        frame = workspace_frame(page)
        frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)

        strict_source = import_asset(frame, args.strict_source, "source")
        strict_mask = import_asset(frame, args.strict_mask, "edit_mask")
        strict_job = frame.evaluate(
            """value => call('jobs.create', {
              operation: 'image.edit', intent: 'close the mouth into a gentle smile',
              inputs: [{asset_id: value.source}], model_policy: 'auto',
              constraints: {width: 1024, height: 1024, seed: 8701, strict_edit: true,
                            edit_mode: 'inpaint', editable_mask_asset_id: value.mask},
              output: {format: 'png', count: 1},
              qa: {semantic: false, max_regeneration_attempts: 0}, local_only: true,
            })""",
            {"source": strict_source["id"], "mask": strict_mask["id"]},
        )
        strict_job, strict_elapsed = wait_job(frame, strict_job["id"])
        check(strict_job["status"] == "succeeded", f"strict edit failed: {strict_job}")
        strict_provenance = frame.evaluate(
            "id => call('assets.provenance', {asset_id: id})", strict_job["asset_ids"][0]
        )
        strict_validator = next(
            item for item in strict_provenance["validation"]
            if item["validator"] == "image.strict_edit.unmasked_pixel_diff"
        )
        check(strict_validator["protected_pixel_difference"] == 0,
              f"strict validator failed: {strict_validator}")

        outpaint_source = import_asset(frame, args.outpaint_source, "source")
        outpaint_job = frame.evaluate(
            """source => call('jobs.create', {
              operation: 'image.edit', intent: 'extend the background naturally',
              inputs: [{asset_id: source}], model_policy: 'auto',
              constraints: {width: 768, height: 512, seed: 8702, strict_edit: true,
                            edit_mode: 'outpaint'},
              output: {format: 'png', count: 1},
              qa: {semantic: false, max_regeneration_attempts: 0}, local_only: true,
            })""",
            outpaint_source["id"],
        )
        outpaint_job, outpaint_elapsed = wait_job(frame, outpaint_job["id"])
        check(outpaint_job["status"] == "succeeded", f"outpaint failed: {outpaint_job}")
        outpaint_provenance = frame.evaluate(
            "id => call('assets.provenance', {asset_id: id})", outpaint_job["asset_ids"][0]
        )
        outpaint_validator = next(
            item for item in outpaint_provenance["validation"]
            if item["validator"] == "image.outpaint.source_pixel_diff"
        )
        check(outpaint_validator["source_pixel_difference"] == 0,
              f"outpaint validator failed: {outpaint_validator}")
        frame.evaluate("ids => showResult(ids)", [strict_job["asset_ids"][0], outpaint_job["asset_ids"][0]])
        page.screenshot(path=args.evidence_dir / "worker-boundary-results.png", full_page=True)
        browser.close()

    check(not browser_errors, f"browser errors: {browser_errors}")
    evidence = {
        "strict": {
            "job_id": strict_job["id"], "asset_id": strict_job["asset_ids"][0],
            "elapsed_sec": round(strict_elapsed, 3), "validator": strict_validator,
        },
        "outpaint": {
            "job_id": outpaint_job["id"], "asset_id": outpaint_job["asset_ids"][0],
            "elapsed_sec": round(outpaint_elapsed, 3), "validator": outpaint_validator,
        },
        "browser_errors": browser_errors,
    }
    (args.evidence_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
