#!/usr/bin/env python3
"""Installed-ControlDeck G5 acceptance with real M5Companion artwork and R9700 strict edit."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from playwright.sync_api import Page


CANVAS = (1280, 960)
EYE_RECT = (384, 328, 896, 504)
EYE_SLOTS = (
    "open_center", "open_left", "open_right", "open_up", "open_down",
    "soft_lower", "half", "almost_closed", "closed", "wide",
    "sleepy_half", "sleepy_closed",
)
MOUTH_SLOTS = (
    "rest", "tiny", "small", "medium", "wide", "rounded", "smile_closed", "smile_open",
)


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


def import_asset(frame, path: Path, purpose: str = "source") -> dict[str, Any]:
    return frame.evaluate(
        """async value => {
          const binary = atob(value.base64);
          const bytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
          return importFile(new File([bytes], value.name, {type: 'image/png'}), value.purpose);
        }""",
        {"base64": base64.b64encode(path.read_bytes()).decode("ascii"), "name": path.name, "purpose": purpose},
    )


def wait_job(frame, job_id: str, timeout: float = 600) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = frame.evaluate("id => call('jobs.get', {job_id: id})", job_id)
        if last.get("status") in {"succeeded", "failed", "canceled"}:
            return last, time.perf_counter() - started
        frame.wait_for_timeout(500)
    raise AssertionError(f"job did not finish: {last}")


def prepare_real_inputs(m5_root: Path, output: Path) -> dict[str, Path]:
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    source_eye = Image.open(m5_root / "assets/kizuna/eyes/open.normalised.png").convert("RGBA")
    check(source_eye.size == CANVAS, "real M5 eye template is no longer 1280x960")
    registered = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    # eye_anchor.json records the current human-measured pupil centers. Move
    # the two registered halves independently onto the new shared-canvas contract.
    registered.alpha_composite(source_eye.crop((384, 328, 640, 504)), (432, 341))
    registered.alpha_composite(source_eye.crop((640, 328, 896, 504)), (667, 357))
    eye_path = output / "open_center.png"
    registered.save(eye_path)

    source_base = Image.open(m5_root / "assets/kizuna/base/front.png").convert("RGBA")
    source_base.thumbnail((1200, 696), Image.Resampling.LANCZOS)
    base = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    base.alpha_composite(source_base, ((CANVAS[0] - source_base.width) // 2, 40))
    base_path = output / "front.png"
    base.save(base_path)

    source_mouth = Image.open(m5_root / "assets/kizuna/variants/master.png").convert("RGBA").resize(
        CANVAS, Image.Resampling.LANCZOS
    )
    mouth = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    mouth.alpha_composite(source_mouth.crop((512, 496, 768, 656)), (512, 496))
    mouth_path = output / "mouth.png"
    mouth.save(mouth_path)

    mask = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(mask).rectangle((EYE_RECT[0], EYE_RECT[1], EYE_RECT[2] - 1, EYE_RECT[3] - 1),
                                   fill=(255, 255, 255, 255))
    mask_path = output / "eyes-mask.png"
    mask.save(mask_path)
    return {"base": base_path, "eye": eye_path, "mouth": mouth_path, "mask": mask_path}


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--m5-root", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    inputs = prepare_real_inputs(args.m5_root, args.evidence_dir / "inputs")
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("console", lambda message: browser_errors.append(f"console:{message.type}:{message.text}")
                if message.type == "error" else None)
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
        login(page, args.username, password)
        page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
        frame = workspace_frame(page)
        frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)

        source = import_asset(frame, inputs["eye"])
        mask = import_asset(frame, inputs["mask"], "edit_mask")
        strict = frame.evaluate(
            """value => call('jobs.create', {
              operation: 'image.edit', intent: 'close both eyes gently while preserving every other pixel',
              inputs: [{asset_id: value.source}], profile: 'm5.companion.eyes', model_policy: 'auto',
              constraints: {width: 1280, height: 960, seed: 9501, strict_edit: true,
                            edit_mode: 'inpaint', editable_mask_asset_id: value.mask},
              output: {format: 'png', count: 1}, qa: {semantic: false, max_regeneration_attempts: 0},
              local_only: true,
            })""",
            {"source": source["id"], "mask": mask["id"]},
        )
        strict, strict_elapsed = wait_job(frame, strict["id"])
        check(strict["status"] == "succeeded", f"real M5 strict edit failed: {strict}")
        strict_provenance = frame.evaluate(
            "id => call('assets.provenance', {asset_id: id})", strict["asset_ids"][0]
        )

        entries: list[dict[str, str]] = []
        asset_inputs: list[dict[str, str]] = []

        def add(asset_id: str, layer: str, name: str) -> None:
            entries.append({"asset_id": asset_id, "layer": layer, "name": name})
            asset_inputs.append({"asset_id": asset_id})

        add(import_asset(frame, inputs["base"])["id"], "base", "front")
        for name in EYE_SLOTS:
            asset_id = strict["asset_ids"][0] if name == "closed" else import_asset(frame, inputs["eye"])["id"]
            add(asset_id, "eyes", name)
        for name in MOUTH_SLOTS:
            add(import_asset(frame, inputs["mouth"])["id"], "mouth", name)
        packed = frame.evaluate(
            """value => call('jobs.create', {
              operation: 'asset.pack', intent: 'Package the hardware companion assets',
              inputs: value.inputs, profile: 'm5.companion.pack',
              constraints: {pack_name: 'kizuna', entries: value.entries},
              output: {format: 'zip', count: 1}, local_only: true,
            })""",
            {"inputs": asset_inputs, "entries": entries},
        )
        packed, pack_elapsed = wait_job(frame, packed["id"], timeout=120)
        check(packed["status"] == "succeeded", f"real M5 pack failed: {packed}")
        pack_provenance = frame.evaluate(
            "id => call('assets.provenance', {asset_id: id})", packed["asset_ids"][0]
        )
        content = frame.evaluate("id => call('assets.content', {asset_id: id})", packed["asset_ids"][0])
        archive_bytes = base64.b64decode(content["base64"])
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read("manifest.json"))
        check(len(names) == 27, f"pack file count changed: {names}")
        check(
            f"companion/packs/kizuna/eyes/neutral.m5a" in names,
            "firmware-ready M5A eye clip is missing",
        )
        check(manifest["eye_slots"] == list(EYE_SLOTS), "eye slot order changed")
        check(manifest["mouth_slots"] == list(MOUTH_SLOTS), "mouth slot order changed")
        (args.evidence_dir / "kizuna-m5-companion.zip").write_bytes(archive_bytes)
        page.screenshot(path=args.evidence_dir / "g5-workspace.png", full_page=True)
        browser.close()

    check(not browser_errors, f"browser errors: {browser_errors}")
    strict_check = next(
        item for item in strict_provenance["validation"]
        if item["validator"] == "image.strict_edit.unmasked_pixel_diff"
    )
    evidence = {
        "strict": {"job_id": strict["id"], "asset_id": strict["asset_ids"][0],
                   "elapsed_sec": round(strict_elapsed, 3), "validator": strict_check},
        "pack": {"job_id": packed["id"], "asset_id": packed["asset_ids"][0],
                 "elapsed_sec": round(pack_elapsed, 3), "bytes": len(archive_bytes),
                 "sha256": pack_provenance["output_sha256"], "file_count": len(names)},
        "source_template": str(args.m5_root / "assets/kizuna/eyes/open.normalised.png"),
        "browser_errors": browser_errors,
    }
    (args.evidence_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
