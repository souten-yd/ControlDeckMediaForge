#!/usr/bin/env python3
"""Installed-ControlDeck CI-6 acceptance for Director and real image jobs."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


TERMINAL = {"succeeded", "failed", "canceled"}


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


def audit(page: Page) -> list[dict[str, Any]]:
    return page.evaluate(
        """async () => {
          const response = await fetch('/api/v1/audit?action=addon.runtime.ai.complete&limit=100', {
            headers: {'X-Requested-With': 'ControlDeck'},
          });
          if (!response.ok) throw new Error(`audit ${response.status}`);
          return response.json();
        }"""
    )


def request(intent: str, seed: int) -> dict[str, Any]:
    return {
        "operation": "image.generate",
        "intent": intent,
        "inputs": [],
        "model_policy": "auto",
        "constraints": {"width": 256, "height": 256, "seed": seed},
        "output": {"format": "png", "count": 1},
        "qa": {"semantic": False, "max_regeneration_attempts": 0},
        "local_only": True,
    }


def wait_job(frame, job_id: str, timeout: float = 600) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = frame.evaluate("id => call('jobs.get', {job_id: id})", job_id)
        if last.get("status") in TERMINAL:
            return last, time.perf_counter() - started
        frame.wait_for_timeout(1000)
    raise AssertionError(f"job did not finish: {last}")


def wait_batch(frame, batch_id: str, timeout: float = 900) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = frame.evaluate("id => call('creative.batches.get', {batch_id: id})", batch_id)
        if last.get("state") in TERMINAL | {"partial"}:
            return last, time.perf_counter() - started
        frame.wait_for_timeout(1000)
    raise AssertionError(f"batch did not finish: {last}")


def directed_job(frame, intent: str, seed: int) -> tuple[dict[str, Any], dict[str, Any], float]:
    directed = frame.evaluate(
        """intent => call('creative.direct', {
          intent, director_mode: 'refine', creative_spec: {},
        })""",
        intent,
    )
    compiled = frame.evaluate(
        """value => call('creative.validate', {
          request: value.request, creative_spec: value.directed.creative_spec,
          director_plan: value.directed.assistance_used ? value.directed.plan : null,
        })""",
        {"request": request(intent, seed), "directed": directed},
    )
    job = frame.evaluate("value => call('jobs.create', value)", compiled["request"])
    finished, elapsed = wait_job(frame, job["id"])
    return directed, finished, elapsed


def overflow(frame, width: int, page: Page) -> int:
    page.set_viewport_size({"width": width, "height": 700})
    page.wait_for_timeout(250)
    return frame.evaluate(
        "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--ai-unavailable", action="store_true")
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    browser_errors: list[str] = []
    observations: dict[str, Any] = {"ai_unavailable": args.ai_unavailable}
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
        capabilities = frame.evaluate("() => call('capabilities.get', {})")
        check(capabilities["capabilities"]["image.text_to_image"]["state"] == "available",
              "image.text_to_image is not available")

        if args.ai_unavailable:
            directed, job, elapsed = directed_job(
                frame, "an orange field robot unfolds its solar panels at sunrise", 8604
            )
            check(directed["assistance_used"] is False, "AI-unavailable route used assistance")
            check(directed["skipped_reason"] in {"host_ai_not_granted", "host_ai_unavailable"},
                  f"unexpected fallback reason: {directed}")
            check(job["status"] == "succeeded" and len(job["asset_ids"]) == 1,
                  f"prompt-only fallback did not generate: {job}")
            observations["fallback"] = {
                "skipped_reason": directed["skipped_reason"], "job_id": job["id"],
                "asset_id": job["asset_ids"][0], "elapsed_sec": round(elapsed, 3),
            }
        else:
            before = audit(page)
            human_intent = (
                "a martial artist performs a deep one-handed backbend while balancing "
                "a glowing orange lantern on the raised foot"
            )
            director_started = time.perf_counter()
            directed = frame.evaluate(
                "intent => call('creative.direct', {intent, director_mode: 'refine', creative_spec: {}})",
                human_intent,
            )
            director_elapsed = time.perf_counter() - director_started
            check(directed["assistance_used"] is True, f"Director was skipped: {directed}")
            pose = directed["creative_spec"]["pose"]
            check(pose["preset"] == "custom" and len(pose["details"].strip()) >= 20,
                  f"uncommon action did not become a custom pose: {pose}")
            after_director = audit(page)
            pre_generation = after_director[: max(0, len(after_director) - len(before))]
            pre_capabilities = [item.get("resource_id") for item in reversed(pre_generation)]
            check(pre_capabilities == ["text.generate"],
                  f"prompt-only Director made unexpected calls: {pre_capabilities}")
            compiled = frame.evaluate(
                """value => call('creative.validate', {
                  request: value.request, creative_spec: value.directed.creative_spec,
                  director_plan: value.directed.plan,
                })""",
                {"request": request(human_intent, 8601), "directed": directed},
            )
            human = frame.evaluate("value => call('jobs.create', value)", compiled["request"])
            human, human_elapsed = wait_job(frame, human["id"])
            check(human["status"] == "succeeded" and len(human["asset_ids"]) == 1,
                  f"directed image failed: {human}")

            original_before = audit(page)
            original = frame.evaluate(
                """() => call('creative.direct', {
                  intent: 'an orange inspection rover unfolds two solar panels in a dry canyon',
                  director_mode: 'original', creative_spec: {},
                })"""
            )
            check(original["skipped_reason"] == "original_mode", "original mode called Director")
            check(len(audit(page)) == len(original_before), "original mode emitted an AI audit event")
            original_job = frame.evaluate(
                "value => call('jobs.create', value)",
                request("an orange inspection rover unfolds two solar panels in a dry canyon", 8602),
            )
            original_job, original_elapsed = wait_job(frame, original_job["id"])
            check(original_job["status"] == "succeeded" and len(original_job["asset_ids"]) == 1,
                  f"original non-human image failed: {original_job}")

            batch_before = audit(page)
            batch = frame.evaluate(
                """value => call('creative.batches.create', {
                  request: value, creative_spec: {variation: {axis: 'pose'}}, count: 2,
                  director_mode: 'refine',
                })""",
                request("an orange service robot demonstrates two distinct emergency repair actions", 8603),
            )
            batch, batch_elapsed = wait_batch(frame, batch["id"])
            check(batch["state"] == "succeeded" and len(batch["asset_ids"]) == 2,
                  f"directed action batch failed: {batch}")
            details = [plan["pose"]["details"] for plan in batch["child_plans"]]
            check(len(set(details)) == 2 and all(len(item.strip()) >= 10 for item in details),
                  f"action children were not meaningful and distinct: {details}")
            batch_after = audit(page)
            batch_delta = batch_after[: max(0, len(batch_after) - len(batch_before))]
            batch_capabilities = [item.get("resource_id") for item in reversed(batch_delta)]
            check(batch_capabilities == ["text.generate"],
                  f"action batch did not use exactly one Director call: {batch_capabilities}")

            observations.update({
                "director": {"elapsed_sec": round(director_elapsed, 3), "pose": pose,
                             "pre_generation_ai_calls": pre_capabilities},
                "directed_job": {"job_id": human["id"], "asset_id": human["asset_ids"][0],
                                 "elapsed_sec": round(human_elapsed, 3)},
                "original_job": {"job_id": original_job["id"],
                                 "asset_id": original_job["asset_ids"][0],
                                 "elapsed_sec": round(original_elapsed, 3)},
                "action_batch": {"batch_id": batch["id"], "job_ids": batch["child_job_ids"],
                                 "asset_ids": batch["asset_ids"], "pose_details": details,
                                 "elapsed_sec": round(batch_elapsed, 3),
                                 "ai_calls": batch_capabilities},
            })

        page.set_viewport_size({"width": 1280, "height": 800})
        page.screenshot(path=args.evidence_dir / "installed-1280.png", full_page=True)
        overflow_390 = overflow(frame, 390, page)
        page.screenshot(path=args.evidence_dir / "installed-390.png", full_page=True)
        overflow_320 = overflow(frame, 320, page)
        page.screenshot(path=args.evidence_dir / "installed-320.png", full_page=True)
        check(overflow_390 <= 0 and overflow_320 <= 0,
              f"installed iframe overflow: 390={overflow_390}, 320={overflow_320}")
        browser.close()

    check(not browser_errors, f"browser errors: {browser_errors}")
    observations.update({
        "overflow_390px": overflow_390, "overflow_320px": overflow_320,
        "browser_errors": browser_errors,
    })
    (args.evidence_dir / "evidence.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
