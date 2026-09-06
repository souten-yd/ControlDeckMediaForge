"""Installed GUI failure: terminal cleanup and recovery fork.

Host diagnostic Python. Only an explicitly named retained mf-e2e material
conflict scene is advanced in save-conflict mode. Explicit blender-crash mode
signals only this run's verified Blender child through a PID fd. No core restart.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import time
from typing import Any

ACTIVE = {"queued", "preparing", "starting", "ready", "saving", "stopping"}
DATA = Path("/data1tb/ControlDeck/data/feature-data/media-forge/data")


def record(session_id: str) -> dict[str, Any]:
    with sqlite3.connect(f"file:{DATA}/media-forge.sqlite3?mode=ro", uri=True) as db:
        return json.loads(db.execute("select value_json from blender_web_sessions where id=?", (session_id,)).fetchone()[0])


def crash_owned_blender(cgroup: Path, pids: list[int], runtime_id: str) -> int:
    """Pin the process identity before rechecking executable and cgroup ownership."""
    targets = [pid for pid in pids if (Path(f"/proc/{pid}/exe").resolve().name == "blender")]
    assert len(targets) == 1
    pid = targets[0]
    fd = os.pidfd_open(pid)
    try:
        executable = Path(f"/proc/{pid}/exe").resolve(strict=True)
        runtime = DATA.parent / "runtimes/blender" / runtime_id
        assert executable.name == "blender" and executable.is_relative_to(runtime.resolve(strict=True))
        members = {int(value) for path in cgroup.rglob("cgroup.procs") for value in path.read_text().split()}
        assert pid in members
        signal.pidfd_send_signal(fd, signal.SIGKILL)
    finally:
        os.close(fd)
    return pid


def main() -> None:
    from playwright.sync_api import sync_playwright

    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--failure-kind", choices=("save-conflict", "blender-crash", "disconnect-timeout"), default="save-conflict")
    args = parser.parse_args()
    assert re.fullmatch(r"scene_[0-9a-f]{32}", args.scene_id)
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version and installed["health"] == "healthy"
    with sqlite3.connect(f"file:{DATA}/media-forge.sqlite3?mode=ro", uri=True) as db:
        assert not any(state in ACTIVE for (state,) in db.execute("select state from blender_web_sessions"))
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("helpers", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {"version": args.expected_version, "scene_id": args.scene_id,
        "mode": "installed_real_gui_" + args.failure_kind, "page_errors": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge GUI cleanup acceptance")
    session_id = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                         args=["--window-size=1280,1000"])
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", no_viewport=True)
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": "http://127.0.0.1:8765",
                    "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda e: evidence["page_errors"].append(str(e)))
                page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
                frame = helpers.workspace_frame(page)
                frame.wait_for_selector('#app[aria-busy="false"]')
                assert frame.evaluate("self.origin") == "null"

                def call(method: str, params: dict) -> dict:
                    return frame.evaluate("p => call(p.method,p.params)", {"method": method, "params": params})

                def wait(wanted: set[str], timeout: float = 90) -> dict:
                    started_at = time.monotonic()
                    deadline = started_at + timeout
                    report_at = started_at + 30
                    while time.monotonic() < deadline:
                        value = next(v for v in call("blender.sessions.list", {})["items"] if v["id"] == session_id)
                        if value["state"] in wanted:
                            return value
                        assert value["state"] in ACTIVE, value
                        if time.monotonic() >= report_at:
                            print(json.dumps({"session_id": session_id, "state": value["state"],
                                "waiting_sec": round(time.monotonic() - started_at, 1)}), flush=True)
                            report_at = time.monotonic() + 30
                        page.wait_for_timeout(250)
                    raise AssertionError("owned session did not reach requested state")

                before = call("scenes.get", {"scene_id": args.scene_id})
                assert before["scene"]["name"].startswith("mf-e2e material conflict ")
                assert len(before["revisions"]) >= 3
                started = call("blender.sessions.start", {"scene_id": args.scene_id})
                session_id = started["id"]
                evidence["session_id"] = session_id
                ready = wait({"ready"})
                owned = record(session_id)
                unit = owned["unit_id"]
                assert re.fullmatch(r"mediaforge-blender-[0-9a-f]{32}\.service", unit)
                assert unit == "mediaforge-blender-" + session_id.removeprefix("blendersession_") + ".service"
                result = subprocess.run(["systemctl", "--user", "show", unit, "--property=ControlGroup", "--value"],
                                        check=True, capture_output=True, text=True, timeout=10)
                cgroup = Path("/sys/fs/cgroup") / result.stdout.strip().lstrip("/")
                assert cgroup.resolve().is_relative_to(Path("/sys/fs/cgroup")) and cgroup.is_dir()
                pids = sorted({int(pid) for p in cgroup.rglob("cgroup.procs") for pid in p.read_text().split()})
                assert pids
                evidence["live_pids"] = pids
                evidence["unit_id"] = unit
                root = DATA / "sessions/blender" / session_id
                socket = Path("/run/user/1000/mediaforge-blender") / (session_id.removeprefix("blendersession_")[:16] + ".sock")
                assert root.is_dir() and socket.is_socket()
                if args.failure_kind == "save-conflict":
                    # Only this dedicated scene advances while its GUI owns the old base.
                    call("scenes.revisions.restore", {"scene_id": args.scene_id,
                        "base_revision_id": before["scene"]["current_revision_id"],
                        "target_revision_id": before["revisions"][0]["id"]})
                advanced = call("scenes.get", {"scene_id": args.scene_id})
                if args.failure_kind == "disconnect-timeout":
                    assert ready["disconnect_grace_sec"] == 300
                    frame.evaluate("s => openBlenderView(s)", ready)
                    frame.wait_for_function("['接続しました','Connected'].includes(document.querySelector('#scene-blender-connection').textContent)", timeout=30000)
                    evidence["connected_at"] = record(session_id)["connected_at"]
                    assert evidence["connected_at"] is not None
                    page.screenshot(path=str(args.evidence_dir / "connected.png"))
                    frame.locator("#scene-blender-close").click()
                    frame.wait_for_function("""async id => {
                        const s = (await call('blender.sessions.list', {})).items.find(s => s.id === id);
                        return s?.connection_state === 'disconnected' && s.disconnected_at && !s.connected_at;
                    }""", arg=session_id, timeout=30000)
                    evidence["disconnected_at"] = record(session_id)["disconnected_at"]
                    assert evidence["disconnected_at"]
                began = time.monotonic()
                if args.failure_kind == "save-conflict":
                    call("blender.sessions.save", {"session_id": session_id})
                elif args.failure_kind == "blender-crash":
                    evidence["signaled_blender_pid"] = crash_owned_blender(cgroup, pids, owned["runtime_id"])
                failed = wait({"failed", "interrupted"}, 330 if args.failure_kind == "disconnect-timeout" else 90)
                evidence["terminal_sec"] = round(time.monotonic() - began, 3)
                expected_error = {"save-conflict": "scene_revision_conflict", "blender-crash": "blender_session_runner_lost",
                                  "disconnect-timeout": "blender_session_disconnected_timeout"}[args.failure_kind]
                if args.failure_kind == "disconnect-timeout":
                    assert evidence["terminal_sec"] >= 299
                assert failed["error_code"] == expected_error, failed
                assert failed["result"]["saved"] is False
                working_id = failed["result"]["recovery"]["working_id"]
                assert re.fullmatch(r"working_[0-9a-f]{32}", working_id)
                candidate = DATA / "scenes/working" / working_id / "scene.blend"
                assert candidate.is_file() and not candidate.is_symlink()
                digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
                assert call("scenes.get", {"scene_id": args.scene_id}) == advanced
                assert not root.exists() and not socket.exists() and not cgroup.exists()
                assert all(not Path(f"/proc/{pid}").exists() for pid in pids)
                assert record(session_id)["state"] not in ACTIVE
                recovered = call("scenes.recovery.fork", {"scene_id": args.scene_id, "recovery_working_id": working_id})
                source_id = recovered["revision"]["source_asset_id"]
                source = DATA / "assets" / (source_id + ".blend")
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                assert hashlib.sha256(candidate.read_bytes()).hexdigest() == digest
                assert call("scenes.get", {"scene_id": args.scene_id}) == advanced
                assert not evidence["page_errors"]
                evidence.update(passed=True, ready=ready, failed=failed, recovered=recovered,
                    candidate_sha256=digest, candidate_bytes=candidate.stat().st_size,
                    process_cgroup_root_socket_reclaimed=True,
                    rfb_connection_tested=args.failure_kind == "disconnect-timeout",
                    not_tested=["manual GUI edit", "GPU lease", "batch worker crash", "connected idle timeout"])
            finally:
                if session_id and record(session_id)["state"] in ACTIVE:
                    call("blender.sessions.stop", {"session_id": session_id})
                    wait({"stopped", "failed", "interrupted"})
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k:evidence[k] for k in ("passed", "session_id", "terminal_sec", "candidate_bytes")}))


if __name__ == "__main__":
    main()
