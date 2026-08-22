#!/usr/bin/env python3
"""Real-browser acceptance for UX2 C2 profile and role-aware references."""

from __future__ import annotations

import argparse
import json
import struct
import time
import urllib.request
import zlib
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def png(red: int, green: int, blue: int) -> bytes:
    width = height = 2
    raw = b"".join(b"\x00" + bytes((red, green, blue)) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def request(url: str, path: str, value: dict[str, Any] | None = None, raw: bytes | None = None) -> dict[str, Any]:
    body = raw if raw is not None else json.dumps(value or {}).encode()
    content_type = "application/octet-stream" if raw is not None else "application/json"
    req = urllib.request.Request(url + path, data=body, headers={"Content-Type": content_type}, method="POST")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


def seed(url: str) -> dict[str, Any]:
    assets = [
        request(url, "/api/v1/assets/import?purpose=source", raw=png(*color))
        for color in [(240, 120, 30), (20, 80, 200), (40, 180, 90), (180, 40, 180), (210, 180, 30), (40, 180, 180)]
    ]
    character_collection = request(url, "/api/v1/reference-collections", {
        "name": "Rin reference roles", "description": "identity plus pose alternatives",
        "asset_ids": [item["id"] for item in assets[:3]],
        "roles": {assets[0]["id"]: "identity", assets[1]["id"]: "pose", assets[2]["id"]: "prop"},
    })
    style_collection = request(url, "/api/v1/reference-collections", {
        "name": "Orange anime style", "description": "style plus compositions",
        "asset_ids": [item["id"] for item in assets[3:]],
        "roles": {assets[3]["id"]: "style", assets[4]["id"]: "composition", assets[5]["id"]: "prop"},
    })
    character = request(url, "/api/v1/profiles", {
        "kind": "character", "name": "Rin", "description": "tomboy companion",
        "reference_collection_id": character_collection["id"],
        "character": {"appearance": "cute anime tomboy with an orange hair streak", "clothing": "black hoodie",
                      "colors": ["orange", "black"], "distinguishing_features": ["orange streak"],
                      "negative_traits": []}, "style": None,
    })
    style = request(url, "/api/v1/profiles", {
        "kind": "style", "name": "Orange anime", "description": "clean cel shading",
        "reference_collection_id": style_collection["id"], "character": None,
        "style": {"art_style": "clean anime", "linework": "crisp", "coloring": "orange accents",
                  "texture": "flat", "negative_traits": []},
    })
    return {"assets": assets, "character": character, "style": style}


def capture_jobs(page: Page) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def intercept(route, request_value) -> None:
        payload = json.loads(request_value.post_data or "{}")
        captured.append(payload)
        route.fulfill(status=202, content_type="application/json", body=json.dumps({
            "id": "job_" + f"{len(captured):032x}", "status": "canceled", "phase": None, "progress": 0,
            "request": payload, "asset_ids": [], "error": None,
            "created_at": "2026-08-22T00:00:00Z", "updated_at": "2026-08-22T00:00:00Z",
        }))

    page.route("**/api/v1/jobs", intercept)
    page.route("**/api/v1/jobs/job_*", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps({
            "id": route.request.url.rsplit("/", 1)[-1], "status": "canceled", "phase": None, "progress": 0,
            "request": {"operation": "image.generate", "intent": "captured", "local_only": True},
            "asset_ids": [], "error": None,
            "created_at": "2026-08-22T00:00:00Z", "updated_at": "2026-08-22T00:00:00Z",
        })
    ))
    return captured


def submit(page: Page, captured: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(captured) + 1
    page.click("#create-submit")
    deadline = time.monotonic() + 8
    while len(captured) < count and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    error = page.locator("#create-error").inner_text() if page.locator("#create-error").is_visible() else ""
    check(len(captured) == count, f"job request was not observed; inline_error={error!r}")
    return captured[-1]


def set_roles(page: Page, mapping: dict[str, str]) -> None:
    for asset_id, role in mapping.items():
        page.select_option(f'[data-reference-role="{asset_id}"]', role)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    seeded = seed(args.media_forge_url)
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
        page.fill("#create-intent", "same companion in deliberate pose")
        page.select_option("#character-profile", seeded["character"]["id"])
        observations["simple_reference_note"] = page.locator("#profile-choice-note").inner_text()
        check("参照 3 枚" in observations["simple_reference_note"], "Simple did not infer profile references")
        check(page.locator("#advanced-reference-roles").count() == 0, "role matrix leaked into Simple")

        pose_requests = []
        for pose in ("wave", "peace", "holding_item"):
            if page.locator("#scene-framing").get_attribute("open") is None:
                page.locator("#scene-framing summary").click()
            page.select_option("#creative-pose", pose)
            payload = submit(page, captured)
            pose_requests.append({
                "pose": payload["constraints"]["creative_plan"]["pose"]["id"],
                "profile": payload["constraints"]["character_profile_id"],
                "identity": next(item["asset_id"] for item in payload["constraints"]["creative_plan"]["reference_roles"]
                                 if item["role"] == "identity"),
            })
        observations["pose_variants"] = pose_requests
        check(len({item["pose"] for item in pose_requests}) == 3, "three pose variants were not deliberate")
        check(len({item["profile"] for item in pose_requests}) == 1, "character profile changed between poses")
        check(len({item["identity"] for item in pose_requests}) == 1, "identity reference changed between poses")

        page.click("#mode-advanced")
        page.wait_for_selector("#advanced-reference-roles .reference-role-row")
        char_assets = [item["id"] for item in seeded["assets"][:3]]
        check(page.locator("[data-reference-strength]").count() == 3, "strength controls are missing")
        check(page.locator("[data-reference-strength]:disabled").count() == 3,
              "unsupported strength controls are not disabled")
        set_roles(page, {char_assets[0]: "identity", char_assets[1]: "pose", char_assets[2]: "prop"})
        first_pose_ref = submit(page, captured)
        set_roles(page, {char_assets[0]: "identity", char_assets[1]: "prop", char_assets[2]: "pose"})
        second_pose_ref = submit(page, captured)
        observations["pose_reference_swap"] = [
            item["reference_roles"] for item in [first_pose_ref["constraints"]["creative_plan"],
                                                  second_pose_ref["constraints"]["creative_plan"]]
        ]

        page.select_option("#character-profile", "")
        page.select_option("#style-profile", seeded["style"]["id"])
        style_assets = [item["id"] for item in seeded["assets"][3:]]
        set_roles(page, {style_assets[0]: "style", style_assets[1]: "composition", style_assets[2]: "prop"})
        first_composition = submit(page, captured)
        set_roles(page, {style_assets[0]: "style", style_assets[1]: "prop", style_assets[2]: "composition"})
        second_composition = submit(page, captured)
        observations["composition_reference_swap"] = [
            item["reference_roles"] for item in [first_composition["constraints"]["creative_plan"],
                                                  second_composition["constraints"]["creative_plan"]]
        ]
        check(first_composition["constraints"]["style_profile_id"] == second_composition["constraints"]["style_profile_id"],
              "style profile changed while composition reference changed")

        page.click("#mode-simple")
        page.select_option("#character-profile", seeded["character"]["id"])
        before = len(captured)
        page.click("#create-submit")
        page.wait_for_timeout(300)
        check(len(captured) == before, "six profile references exceeded admission limit")
        observations["limit_error"] = page.locator("#create-error").inner_text()
        check("合計 4 枚" in observations["limit_error"], "reference limit has no inline reason")

        page.set_viewport_size({"width": 320, "height": 640})
        observations["overflow_320"] = page.evaluate(
            "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
        )
        check(observations["overflow_320"] == 0, "320px viewport has horizontal overflow")
        page.screenshot(path=str(args.evidence_dir / "profiles-simple-320.png"), full_page=True)
        observations["console_errors"] = console_errors
        observations["page_errors"] = page_errors
        check(not console_errors and not page_errors,
              f"browser emitted console/page errors: console={console_errors!r} page={page_errors!r}")
        browser.close()

    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
