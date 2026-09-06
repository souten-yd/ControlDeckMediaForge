"""Create one retained acceptance scene through installed production APIs.

Run in the existing Host diagnostic Python. This deliberately creates real CPU
Blender jobs and 61 immutable restores, not synthetic Store rows. Never retry
mutation requests automatically. Retain the labeled scene/history for repeat
read-only browser acceptance; do not bypass scene/Asset deletion protections.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3
import time
import uuid

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
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version
    assert installed["health"] == "healthy" and installed["enabled"]
    core_data = data_dir() / "feature-data/media-forge/data"
    db = sqlite3.connect(f"file:{core_data / 'media-forge.sqlite3'}?mode=ro", uri=True)
    before_scenes = dict(db.execute("SELECT id, value_json FROM scene_documents"))
    before_revisions = dict(db.execute("SELECT id, value_json FROM scene_revisions"))
    assert not db.execute("SELECT id FROM jobs WHERE status IN ('queued','running')").fetchall()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict = {"mode": "installed_real_recipe_and_revision_restore", "version": args.expected_version,
        "retained_acceptance_scene": True, "jobs": [], "restores": []}
    started = time.monotonic()

    def record() -> None:
        evidence["elapsed_sec"] = round(time.monotonic() - started, 3)
        (args.evidence_dir / "fixture.json").write_text(json.dumps(evidence, indent=2) + "\n")

    with SessionLocal() as host_db:
        user = host_db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        user_id = user.id
        session = create_session(host_db, user, "127.0.0.1", "MediaForge retained paging acceptance")
    try:
        with httpx.Client(base_url="http://127.0.0.1:9130", timeout=25) as client:
            def call(method: str, value: dict) -> dict:
                bearer = tokens.issue("media-forge", subject=str(user_id), kind="service", actor_user_id=user_id)
                response = client.post(f"/addon/v1/agent/{method}", json={"input": value}, headers={
                    "Authorization": f"Bearer {bearer}", "X-Control-Deck-Addon-ID": "media-forge"})
                assert response.status_code == 200, (method, response.status_code)
                return response.json()

            def produce(method: str, value: dict) -> dict:
                job = call(method, value)
                evidence["jobs"].append(job)
                record()
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    result = call("job/status", {"job_id": job["job_id"]})
                    if result["status"] in {"succeeded", "failed", "canceled"}:
                        job["terminal"] = result
                        record()
                        assert result["status"] == "succeeded", result.get("error")
                        print(json.dumps({"job_id": job["job_id"], "status": result["status"]}), flush=True)
                        return result["result"]
                    time.sleep(0.5)
                raise TimeoutError("Observation expired; inspect recorded job, do not resubmit")

            name = f"Library paging acceptance {uuid.uuid4().hex[:12]} (retained)"
            initial = produce("scene/create", {"name": name, "recipe": {"operations": [
                {"type": "primitive.add", "object_id": "paging_cube", "primitive": "cube",
                 "name": "Paging acceptance cube", "dimensions": [1, 1, 1]}]}})
            scene_id = initial["scene"]["id"]
            first = initial["revision"]
            evidence.update({"scene_id": scene_id, "name": name, "initial": initial,
                             "source": first["source_asset_id"]})
            record()
            edited = produce("scene/edit", {"scene_id": scene_id, "base_revision_id": first["id"],
                "recipe": {"operations": [{"type": "transform.set", "object_id": "paging_cube",
                                            "location": [0.1, 0, 0]}]}})

        spec = importlib.util.spec_from_file_location("installed_browser", Path(__file__).with_name(
            "3ds8_installed_browser_e2e.py"))
        assert spec and spec.loader
        helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helpers)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", viewport={"width": 1280, "height": 800})
                context.add_cookies([{"name": SESSION_COOKIE, "value": session, "url": "http://127.0.0.1:8765",
                                     "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                frame = helpers.open_scene(page, scene_id)
                assert frame.evaluate("self.origin") == "null"
                current = edited["revision"]["id"]
                children = [first["preview_asset_id"], edited["revision"]["source_asset_id"]]
                for index in range(61):
                    result = frame.evaluate("params => call('scenes.revisions.restore', params)", {
                        "scene_id": scene_id, "base_revision_id": current, "target_revision_id": first["id"]})
                    current = result["revision"]["id"]
                    children.append(result["revision"]["source_asset_id"])
                    evidence["restores"].append(result)
                    record()
                    if (index + 1) % 10 == 0:
                        print(json.dumps({"restores": index + 1}), flush=True)
                scene = frame.evaluate("id => call('scenes.get', {scene_id:id})", scene_id)
                assert len(scene["revisions"]) == 63
                assert scene["revisions"][:2] == [first, edited["revision"]]
                actual: list[str] = []
                for offset in (0, 60):
                    relations = frame.evaluate("params => call('assets.relations', params)",
                                               {"asset_id": first["source_asset_id"], "offset": offset})
                    actual.extend(item["id"] for item in relations["children"])
                    assert not relations["parents"]
                assert len(actual) == len(set(actual)) == 63
                assert set(actual) == set(children)
                evidence.update({"children": children, "parents": [], "revision_count": 63})
            finally:
                browser.close()
        after_scenes = dict(db.execute("SELECT id, value_json FROM scene_documents"))
        after_revisions = dict(db.execute("SELECT id, value_json FROM scene_revisions"))
        assert all(after_scenes[key] == value for key, value in before_scenes.items())
        assert all(after_revisions[key] == value for key, value in before_revisions.items())
        assert set(after_scenes) - set(before_scenes) == {scene_id}
        evidence.update({"previous_scene_revision_metadata_unchanged": True, "passed": True})
    except Exception as error:
        evidence["failure_type"] = type(error).__name__
        raise
    finally:
        with SessionLocal() as host_db:
            revoke_session(host_db, session)
        db.close()
        record()
    print(json.dumps({"scene_id": evidence["scene_id"], "children": len(evidence["children"]),
                      "elapsed_sec": evidence["elapsed_sec"], "passed": True}))


if __name__ == "__main__":
    main()
