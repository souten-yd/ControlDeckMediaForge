#!/usr/bin/env python3
"""Installed ControlDeck opaque-iframe acceptance for a 3D Studio scene.

Run with ControlDeck's virtualenv. The script temporarily changes only the
dedicated E2E user's password, restores it in ``finally``, and revokes only the
Host sessions created by this run.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any, Iterator

from argon2 import PasswordHasher
from playwright.sync_api import Frame, Page, sync_playwright


ACTIVE = {"queued", "preparing", "starting", "ready", "saving", "stopping"}


def check(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


@contextmanager
def fixture_login(db_path: Path, username: str) -> Iterator[str]:
    if db_path.is_symlink() or not db_path.is_file():
        raise RuntimeError("ControlDeck database is missing or unsafe")
    connection = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT id, password_hash, updated_at, last_login_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        connection.close()
        raise RuntimeError("ControlDeck E2E user is missing")
    user_id = int(row["id"])
    original = (row["password_hash"], row["updated_at"], row["last_login_at"])
    session_floor = int(connection.execute("SELECT COALESCE(MAX(id), 0) FROM sessions").fetchone()[0])
    password = secrets.token_urlsafe(32)
    connection.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        (PasswordHasher().hash(password), datetime.now(UTC).isoformat(), user_id),
    )
    connection.commit()
    try:
        yield password
    finally:
        now = datetime.now(UTC).isoformat()
        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = ?, last_login_at = ? WHERE id = ?",
            (*original, user_id),
        )
        connection.execute(
            "UPDATE sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id = ? AND id > ?",
            (now, user_id, session_floor),
        )
        connection.commit()
        connection.close()


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login", wait_until="domcontentloaded")
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def workspace_frame(page: Page) -> Frame:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/addon-frame/media-forge" in frame.url and frame.locator("#app").count():
                return frame
        page.wait_for_timeout(200)
    raise AssertionError("Media Forge workspace iframe did not become ready")


def open_scene(page: Page, scene_id: str) -> Frame:
    page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
    frame = workspace_frame(page)
    frame.wait_for_selector('#app[aria-busy="false"]', timeout=30_000)
    frame.locator("#create-media-3d").click()
    listed = frame.evaluate("() => call('scenes.list', {})")
    scene_ids = [str(item.get("id")) for item in listed.get("items", [])]
    check(scene_id in scene_ids, f"scene is not visible to browser owner: {scene_ids}")
    frame.evaluate("() => loadScenes()")
    selector = f'[data-scene-id="{scene_id}"]'
    frame.wait_for_selector(selector, timeout=30_000)
    frame.locator(selector).click()
    frame.wait_for_function(
        "id => !document.querySelector('#scene-detail').hidden && state.selectedSceneId === id",
        arg=scene_id,
        timeout=30_000,
    )
    return frame


def session_projection(frame: Frame, scene_id: str) -> dict[str, Any] | None:
    value = frame.evaluate(
        """async id => {
          const result = await call('blender.sessions.list', {});
          return (result.items || []).find(item => item.scene_id === id &&
            ['queued','preparing','starting','ready','saving','stopping'].includes(item.state)) || null;
        }""",
        scene_id,
    )
    return value


def wait_session(
    frame: Frame, scene_id: str, wanted: set[str], timeout: float = 60
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last = session_projection(frame, scene_id)
        if last and last.get("state") in wanted:
            return last
        frame.wait_for_timeout(250)
    raise AssertionError(f"Blender session did not reach {wanted}: {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", default="http://127.0.0.1:8765")
    parser.add_argument("--control-deck-db", type=Path, required=True)
    parser.add_argument("--username", default="mf-e2e")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--hold-sec", type=int, default=0)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    observations: dict[str, Any] = {"scene_id": args.scene_id, "hold_sec": args.hold_sec}
    browser_errors: list[str] = []

    with fixture_login(args.control_deck_db, args.username) as password, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            desktop = browser.new_context(
                base_url=args.control_deck_url, viewport={"width": 1280, "height": 900}
            )
            page = desktop.new_page()
            page.on(
                "console",
                lambda message: browser_errors.append(f"console:{message.text}")
                if message.type == "error" else None,
            )
            page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
            login(page, args.username, password)
            frame = open_scene(page, args.scene_id)
            observations["opaque_origin"] = frame.evaluate("() => self.origin")
            observations["desktop_width"] = frame.evaluate(
                "() => ({inner: innerWidth, client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
            )
            check(observations["opaque_origin"] == "null", "iframe origin is not opaque")
            check(
                observations["desktop_width"]["scroll"] <= observations["desktop_width"]["inner"],
                "desktop scene view overflows horizontally",
            )
            revision_before = int(frame.evaluate("() => state.sceneDocument.revision_count"))
            check(not frame.locator("#scene-blender-open").is_disabled(), "Blender button is disabled")
            frame.locator("#scene-blender-open").click()
            started = wait_session(frame, args.scene_id, {"ready"}, timeout=90)
            observations["session_id"] = started["id"]

            # Reload crosses the opaque Host bridge again while the server-owned session remains alive.
            frame = open_scene(page, args.scene_id)
            check(session_projection(frame, args.scene_id)["id"] == started["id"], "reload lost session")
            frame.locator("#scene-blender-open").click()
            frame.locator("#scene-blender-dialog[open]").wait_for(timeout=30_000)
            frame.wait_for_function(
                "() => ['接続しました', 'Connected'].includes(document.querySelector('#scene-blender-connection').textContent)",
                timeout=30_000,
            )

            # Close only the display, then reconnect to the same session.
            frame.locator("#scene-blender-close").click()
            check(session_projection(frame, args.scene_id)["id"] == started["id"], "display close stopped session")
            frame.locator("#scene-blender-open").click()
            frame.wait_for_function(
                "() => ['接続しました', 'Connected'].includes(document.querySelector('#scene-blender-connection').textContent)",
                timeout=30_000,
            )
            observations["reconnected"] = True

            # A second authenticated browser cannot create another writer.
            second = browser.new_context(
                base_url=args.control_deck_url, viewport={"width": 1280, "height": 900}
            )
            second_page = second.new_page()
            login(second_page, args.username, password)
            second_frame = open_scene(second_page, args.scene_id)
            conflict = second_frame.evaluate(
                """async id => {
                  try { return {ok: true, value: await call('blender.sessions.start', {scene_id: id})}; }
                  catch (error) { return {ok: false, code: error?.code || '', message: error?.message || ''}; }
                }""",
                args.scene_id,
            )
            check(not conflict["ok"], f"second writer was accepted: {conflict}")
            observations["second_writer"] = conflict
            second.close()

            # Exercise real noVNC input and keep the credentialed bridge active when requested.
            screen = frame.locator("#scene-blender-screen")
            screen.click(position={"x": 320, "y": 240})
            screen.press("F3")
            screen.type("Add Cube")
            screen.press("Enter")
            hold_started = time.monotonic()
            while time.monotonic() - hold_started < args.hold_sec:
                frame.wait_for_timeout(min(20_000, max(1, args.hold_sec) * 1000))
                screen.press("Shift")
                current = session_projection(frame, args.scene_id)
                check(current and current["id"] == started["id"], "long-lived session stopped")
            observations["held_actual_sec"] = round(time.monotonic() - hold_started, 3)

            frame.locator("#scene-blender-save").click()
            deadline = time.monotonic() + 90
            revision_after = revision_before
            while time.monotonic() < deadline:
                scene = frame.evaluate("id => call('scenes.get', {scene_id: id})", args.scene_id)
                revision_after = int(scene["scene"]["revision_count"])
                active = session_projection(frame, args.scene_id)
                if revision_after == revision_before + 1 and active is None:
                    break
                frame.wait_for_timeout(250)
            check(revision_after == revision_before + 1, "GUI save did not create one revision")
            observations["revision_before"] = revision_before
            observations["revision_after"] = revision_after

            mobile = browser.new_context(
                base_url=args.control_deck_url, viewport={"width": 390, "height": 844},
                is_mobile=True, device_scale_factor=1,
            )
            mobile_page = mobile.new_page()
            login(mobile_page, args.username, password)
            mobile_frame = open_scene(mobile_page, args.scene_id)
            mobile_width = mobile_frame.evaluate(
                "() => ({inner: innerWidth, client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
            )
            check(mobile_width["scroll"] <= mobile_width["inner"], "mobile scene view overflows")
            check(mobile_frame.locator("#scene-blender-open").is_disabled(), "mobile Blender button is enabled")
            check(
                any(
                    word in mobile_frame.locator("#scene-blender-status").inner_text()
                    for word in ("デスクトップ", "desktop", "Desktop")
                ),
                "mobile desktop guidance is missing",
            )
            observations["mobile_width"] = mobile_width
            mobile.close()
            desktop.close()
        finally:
            browser.close()

    observations["browser_errors"] = browser_errors
    check(browser_errors == [], f"browser errors observed: {browser_errors}")
    output = args.evidence_dir / "observations.json"
    output.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(observations, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
