"""Installed exact-runtime retry using an existing dedicated canceled Job.

Temporarily switch the managed default, retry once through authenticated Agent
HTTP, and restore the default in finally through the real Host workspace bridge.
Never mutate the old Job, delete runtimes, or inject production worker faults.
Run in the existing Host diagnostic Python. Retain the new acceptance scene.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import time

import httpx
from playwright.sync_api import sync_playwright


def main() -> None:
    from app.addons import tokens
    from app.config import data_dir
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version and installed["health"] == "healthy"
    root = data_dir() / "feature-data/media-forge/data"
    db = sqlite3.connect(f"file:{root / 'media-forge.sqlite3'}?mode=ro", uri=True)
    row = db.execute("SELECT owner,runtime_id,runtime_version,request_json FROM scene_recipe_tasks WHERE job_id=? AND operation='scene.create'", (args.job_id,)).fetchone()
    assert row
    request = json.loads(row[3])
    assert request["name"].startswith("Credential acceptance ")
    assert len(request["recipe"]["operations"]) == 1
    old_job = db.execute("SELECT * FROM jobs WHERE id=?", (args.job_id,)).fetchone()
    assert db.execute("SELECT status FROM jobs WHERE id=?", (args.job_id,)).fetchone()[0] == "canceled"
    old_scenes = dict(db.execute("SELECT id,value_json FROM scene_documents"))
    old_revisions = dict(db.execute("SELECT id,value_json FROM scene_revisions"))
    registry_path = root / "runtime-state/blender-runtimes.json"
    registry_before = registry_path.read_bytes()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict = {"version": args.expected_version, "retry_of": args.job_id,
                      "mode": "installed_agent_http_real_host_workspace_switch", "switches": []}
    started = time.monotonic()

    def record() -> None:
        evidence["elapsed_sec"] = round(time.monotonic() - started, 3)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")

    with SessionLocal() as host_db:
        user = host_db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active and row[0] == f"user:{user.id}"
        user_id = user.id
        session = create_session(host_db, user, "127.0.0.1", "Installed runtime retry acceptance")
    helper_spec = importlib.util.spec_from_file_location("browser_helpers", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert helper_spec and helper_spec.loader
    helpers = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helpers)
    try:
        with sync_playwright() as pw, httpx.Client(base_url="http://127.0.0.1:9130", timeout=25) as client:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", viewport={"width": 1280, "height": 800})
                context.add_cookies([{"name": SESSION_COOKIE, "value": session, "url": "http://127.0.0.1:8765", "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.goto("/x/media-forge/workspace/create")
                frame = helpers.workspace_frame(page)
                frame.locator('#app[aria-busy="false"]').wait_for()
                assert frame.evaluate("self.origin") == "null"

                def runtime_status() -> dict:
                    return frame.evaluate("() => call('blender.runtime.status', {})")

                def switch(runtime_id: str) -> None:
                    operation = frame.evaluate("id => call('blender.runtime.switch', {runtime_id:id})", runtime_id)
                    evidence["switches"].append(operation)
                    record()
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        status = runtime_status()
                        current = next(o for o in status["operations"] if o["id"] == operation["id"])
                        if current["state"] in {"ready", "failed", "canceled"}:
                            assert current["state"] == "ready", current
                            assert status["active_runtime_id"] == runtime_id
                            evidence["switches"][-1] = current
                            record()
                            return
                        page.wait_for_timeout(100)
                    raise TimeoutError("Inspect the recorded live switch; do not resubmit")

                def agent(method: str, value: dict) -> dict:
                    bearer = tokens.issue("media-forge", subject=str(user_id), kind="service", actor_user_id=user_id)
                    response = client.post(f"/addon/v1/agent/{method}", json={"input": value}, headers={
                        "Authorization": f"Bearer {bearer}", "X-Control-Deck-Addon-ID": "media-forge"})
                    assert response.status_code == 200, (method, response.status_code)
                    return response.json()

                before = runtime_status()
                original = before["active_runtime_id"]
                alternate = "blender-4.5.9-linux-x64"
                assert original == row[1] == "blender-4.5.13-linux-x64"
                assert not db.execute("SELECT id FROM jobs WHERE status IN ('queued','running')").fetchall()
                assert not db.execute("SELECT id FROM blender_web_sessions WHERE state IN ('queued','preparing','starting','ready','saving','stopping')").fetchall()
                assert not db.execute("SELECT id FROM scene_working_copies WHERE state='active'").fetchall()
                try:
                    switch(alternate)
                    accepted = agent("scene/create", {**request, "retry_job_id": args.job_id})
                    evidence["accepted"] = accepted
                    record()
                    deadline = time.monotonic() + 240
                    while time.monotonic() < deadline:
                        result = agent("job/status", {"job_id": accepted["job_id"]})
                        if result["status"] in {"succeeded", "failed", "canceled"}:
                            evidence["result"] = result
                            record()
                            break
                        page.wait_for_timeout(250)
                    else:
                        raise TimeoutError("Inspect recorded Job; do not resubmit")
                    assert result["status"] == "succeeded", result["error"]
                    assert result["runtime_id"] == row[1] and result["runtime_version"] == row[2]
                    assert result["result"]["recipe"]["blender_version"] == row[2]
                    assert result["retry_of"] == args.job_id
                    assert runtime_status()["active_runtime_id"] == alternate
                finally:
                    if runtime_status()["active_runtime_id"] == alternate:
                        switch(original)
                    assert runtime_status()["active_runtime_id"] == original
            finally:
                browser.close()
        assert registry_path.read_bytes() == registry_before
        assert db.execute("SELECT * FROM jobs WHERE id=?", (args.job_id,)).fetchone() == old_job
        for table, before_rows in (("scene_documents", old_scenes), ("scene_revisions", old_revisions)):
            after_rows = dict(db.execute(f"SELECT id,value_json FROM {table}"))
            assert all(after_rows[key] == value for key, value in before_rows.items())
            assert len(after_rows) == len(before_rows) + 1
        for aid in result["asset_ids"]:
            metadata_json, storage_name = db.execute("SELECT metadata_json,storage_name FROM assets WHERE id=?", (aid,)).fetchone()
            metadata = json.loads(metadata_json)
            path = (root / "assets" / storage_name).resolve()
            assert path.is_relative_to((root / "assets").resolve())
            assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
            assert path.stat().st_size == metadata["size_bytes"]
        evidence.update(passed=True, original_job_unchanged=True, previous_scenes_revisions_unchanged=True,
                        runtime_registry_restored=True, new_scene_retained=True, asset_hashes_verified=True)
    finally:
        with SessionLocal() as host_db:
            revoke_session(host_db, session)
        db.close()
        record()
    print(json.dumps({"passed": True, "elapsed_sec": evidence["elapsed_sec"], "job_id": evidence["accepted"]["job_id"]}))


if __name__ == "__main__":
    main()
