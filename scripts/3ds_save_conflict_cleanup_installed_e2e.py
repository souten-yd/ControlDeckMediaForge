"""Installed GUI failure: terminal cleanup and recovery fork.

Host diagnostic Python. Only an explicitly named retained mf-e2e material
conflict scene is advanced in save-conflict mode. Explicit blender-crash mode
signals only this run's verified Blender child through a PID fd. Autosave-crash
duplicates meshes, faults only its own working directory and verifies JA/EN
warnings via a browser-language input fixture. Explicit core-restart mode restarts
only the installed MediaForge unit after checking no other GUI or Job is active.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import sqlite3
import subprocess
import time
from typing import Any, Iterator

import httpx

ACTIVE = {"queued", "preparing", "starting", "ready", "saving", "stopping"}
DATA = Path("/data1tb/ControlDeck/data/feature-data/media-forge/data")


@contextmanager
def deny_owned_snapshot_write(candidate: Path, working_root: Path) -> Iterator[None]:
    """Fault only a validated diagnostic working directory; always restore mode."""
    assert not candidate.is_symlink() and candidate.is_file()
    parent = candidate.parent
    assert not parent.is_symlink()
    assert re.fullmatch(r"working_[0-9a-f]{32}", parent.name)
    assert parent.resolve(strict=True).parent == working_root.resolve(strict=True)
    mode = stat.S_IMODE(parent.stat().st_mode)
    try:
        parent.chmod(0o500)
        yield
    finally:
        parent.chmod(mode)


def await_autosave(page: Any, root: Path, session_id: str, wanted: bool) -> dict[str, Any]:
    """Observe the actual 120-second timer without replacing its clock."""
    began = time.monotonic()
    while time.monotonic() - began < 150:
        path = root / "autosave.json"
        if path.exists():
            assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024
            value = json.loads(path.read_text())
            assert value["session_id"] == session_id and value["schema_version"] == 1
            if value.get("ok") is wanted:
                return value
        print(json.dumps({"waiting_autosave": wanted, "elapsed_sec": round(time.monotonic()-began, 1)}), flush=True)
        page.wait_for_timeout(15000)
    raise AssertionError("default autosave did not report expected result")


def expire_owned_gateway(session_id: str, user_id: int) -> dict[str, Any]:
    """Use a real short-lived Host service identity, never an expiry override."""
    assert re.fullmatch(r"blendersession_[0-9a-f]{32}", session_id)
    assert isinstance(user_id, int) and not isinstance(user_id, bool) and user_id > 0
    from app.addons import tokens
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    bearer = tokens.issue("media-forge", subject=str(user_id), kind="service",
                          actor_user_id=user_id, ttl_seconds=20)
    began = time.monotonic()
    with connect(f"ws://127.0.0.1:9130/blender/sessions/{session_id}/rfb",
                 additional_headers={"Authorization": "Bearer " + bearer,
                                     "X-Control-Deck-Addon-ID": "media-forge"},
                 subprotocols=["binary"], open_timeout=10, close_timeout=5) as ws:
        banner = ws.recv(timeout=10)
        assert isinstance(banner, bytes) and banner.startswith(b"RFB ")
        # Keep the real RFB handshake open; send no edit or synthetic activity.
        try:
            while time.monotonic() - began < 45:
                ws.recv(timeout=45 - (time.monotonic() - began))
        except ConnectionClosed as closed:
            assert closed.rcvd and closed.rcvd.code == 4403
            assert closed.rcvd.reason == "host service token expired"
            elapsed = round(time.monotonic() - began, 3)
            assert elapsed >= 19
            return {"ttl_sec": 20, "elapsed_sec": elapsed, "close_code": closed.rcvd.code,
                    "reason": closed.rcvd.reason, "rfb_banner_received": True,
                    "route": "Host-signed identity to installed core RFB endpoint"}
    raise AssertionError("short-lived service identity did not expire")


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


def restart_installed_core(session_id: str) -> dict[str, Any]:
    """Bounded standard service restart; never restart the Host or another unit."""
    assert re.fullmatch(r"blendersession_[0-9a-f]{32}", session_id)
    with closing(sqlite3.connect(f"file:{DATA}/media-forge.sqlite3?mode=ro", uri=True)) as db:
        live = {row[0] for row in db.execute(
            "select id from blender_web_sessions where state in ('queued','preparing','starting','ready','saving','stopping')")}
        assert live == {session_id}, "Another GUI is active; do not restart"
        assert db.execute("select count(*) from jobs where status not in ('succeeded','failed','canceled')").fetchone()[0] == 0
    def pid(unit: str) -> int:
        return int(subprocess.check_output(["systemctl", "--user", "show", unit, "-p", "MainPID", "--value"],
                                          text=True, timeout=10))
    host = pid("control-deck-web.service")
    before = pid("cdapp-feature-media-forge.service")
    assert host > 0 and before > 0
    began = time.monotonic()
    subprocess.run(["systemctl", "--user", "restart", "cdapp-feature-media-forge.service"],
                   check=True, timeout=45, capture_output=True)
    after = pid("cdapp-feature-media-forge.service")
    assert after > 0 and after != before and pid("control-deck-web.service") == host
    with httpx.Client(timeout=2) as client:
        deadline = time.monotonic() + 30
        while True:
            try:
                response = client.get("http://127.0.0.1:9130/health")
                healthy = response.status_code == 200 and response.json().get("status") == "healthy"
            except httpx.HTTPError:
                healthy = False
            if healthy:
                break
            assert time.monotonic() < deadline, "MediaForge did not become healthy"
            time.sleep(.25)
    return {"old_core_pid": before, "new_core_pid": after, "host_pid_unchanged": host,
            "http_health": "healthy", "elapsed_sec": round(time.monotonic()-began, 3)}


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
    parser.add_argument("--failure-kind", choices=("save-conflict", "blender-crash", "disconnect-timeout", "autosave-crash", "auth-expiry", "core-restart"), default="save-conflict")
    parser.add_argument("--manual-edit", action="store_true", help="Duplicate meshes through RFB before a save conflict")
    args = parser.parse_args()
    if args.failure_kind in {"autosave-crash", "auth-expiry", "core-restart"}:
        args.manual_edit = True
    if args.manual_edit and args.failure_kind not in {"save-conflict", "autosave-crash", "auth-expiry", "core-restart"}:
        parser.error("--manual-edit requires save-conflict, autosave-crash, auth-expiry or core-restart")
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
    edit_spec = importlib.util.spec_from_file_location("edit_helpers", Path(__file__).with_name("3ds_background_return_installed_e2e.py"))
    assert edit_spec and edit_spec.loader
    edit_helpers = importlib.util.module_from_spec(edit_spec)
    edit_spec.loader.exec_module(edit_helpers)
    evidence: dict[str, Any] = {"version": args.expected_version, "scene_id": args.scene_id,
        "mode": "installed_real_gui_" + args.failure_kind, "page_errors": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        user_id = user.id
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
                original_hashes = edit_helpers.asset_hashes(before) if args.manual_edit else {}
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
                if args.manual_edit:
                    evidence["before"] = before
                    evidence["original_asset_hashes"] = original_hashes
                    working_id = owned["working_id"]
                    assert re.fullmatch(r"working_[0-9a-f]{32}", working_id)
                    working_path = (DATA / "scenes/working" / working_id / "scene.blend").resolve(strict=True)
                    assert working_path.is_relative_to((DATA / "scenes/working").resolve(strict=True))
                    original_working_hash = hashlib.sha256(working_path.read_bytes()).hexdigest()
                    frame.locator("#create-media-3d").click()
                    frame.evaluate("id => openScene(id)", args.scene_id)
                    frame.evaluate("s => openBlenderView(s)", ready)
                    frame.wait_for_function("state.blenderRfb?._rfbConnectionState === 'connected'", timeout=30000)
                    frame.wait_for_function("""() => {
                        const c=document.querySelector('#scene-blender-screen canvas');
                        if (!c || c.width<100 || c.height<100) return false;
                        const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
                        const colors=new Set();
                        for(let i=0;i<d.length;i+=160) colors.add(`${d[i]},${d[i+1]},${d[i+2]}`);
                        return colors.size>50;
                    }""", timeout=45000)
                    frame.locator("#scene-blender-screen canvas").click(position={"x":320,"y":240})
                    page.keyboard.press("a")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Shift+D")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                    page.screenshot(path=str(args.evidence_dir / "unsaved-edit.png"))
                    # No GUI save has occurred yet; edits exist only in Blender memory.
                    assert hashlib.sha256(working_path.read_bytes()).hexdigest() == original_working_hash
                    assert call("scenes.get", {"scene_id":args.scene_id}) == before
                    evidence["working_hash_before_save"] = original_working_hash
                if args.failure_kind == "core-restart":
                    # Trigger before the default autosave: prove in-memory edits
                    # survived in the same Blender process, not a recovered snapshot.
                    evidence["restart"] = restart_installed_core(session_id)
                    assert all(Path(f"/proc/{pid}").exists() for pid in pids)
                    assert cgroup.is_dir() and root.is_dir() and socket.is_socket()
                    assert hashlib.sha256(working_path.read_bytes()).hexdigest() == original_working_hash
                    evidence["working_hash_after_restart"] = original_working_hash
                    page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
                    frame = helpers.workspace_frame(page)
                    frame.wait_for_selector('#app[aria-busy="false"]')
                    assert frame.evaluate("self.origin") == "null"
                    resumed = wait({"ready"})
                    assert record(session_id)["unit_id"] == unit
                    frame.locator("#create-media-3d").click()
                    frame.evaluate("id => openScene(id)", args.scene_id)
                    frame.evaluate("s => openBlenderView(s)", resumed)
                    frame.wait_for_function("state.blenderRfb?._rfbConnectionState === 'connected'", timeout=30000)
                    frame.wait_for_function("""() => {
                        const c=document.querySelector('#scene-blender-screen canvas');
                        if (!c || c.width<100 || c.height<100) return false;
                        const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
                        const colors=new Set();
                        for(let i=0;i<d.length;i+=160) colors.add(`${d[i]},${d[i+1]},${d[i+2]}`);
                        return colors.size>50;
                    }""", timeout=45000)
                    frame.wait_for_function("['接続しました','Connected'].includes(document.querySelector('#scene-blender-connection').textContent)", timeout=30000)
                    assert call("scenes.get", {"scene_id": args.scene_id}) == before
                    page.screenshot(path=str(args.evidence_dir / "reconnected-after-restart.png"))
                    frame.locator("#scene-blender-screen canvas").click(position={"x":320,"y":240})
                    page.keyboard.press("a")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Shift+D")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                    page.screenshot(path=str(args.evidence_dir / "edited-after-restart.png"))
                    call("blender.sessions.save", {"session_id": session_id})
                    terminal = wait({"stopped", "failed", "interrupted"})
                    assert terminal["state"] == "stopped" and terminal["result"]["saved"] is True
                    after = call("scenes.get", {"scene_id": args.scene_id})
                    assert len(after["revisions"]) == len(before["revisions"]) + 1
                    assert edit_helpers.mesh_count(after) == 4 * edit_helpers.mesh_count(before)
                    assert edit_helpers.asset_hashes(before) == original_hashes
                    assert not root.exists() and not socket.exists() and not cgroup.exists()
                    assert all(not Path(f"/proc/{pid}").exists() for pid in pids)
                    assert not evidence["page_errors"]
                    evidence.update(passed=True, resumed=resumed, after=after, terminal=terminal,
                        same_gui_processes_survived_restart=True, unsaved_edit_saved=True,
                        reconnected_render_and_edit_tested=True,
                        process_cgroup_root_socket_reclaimed=True,
                        not_tested=["power failure", "core crash", "restart during save", "connected idle timeout", "GPU lease"])
                    print(json.dumps({"passed": True, "session_id": session_id, "restart": evidence["restart"]}), flush=True)
                    return
                if args.failure_kind == "autosave-crash":
                    assert owned["runtime_id"] == "blender-4.5.13-linux-x64"
                    autosave_began = time.monotonic()
                    with deny_owned_snapshot_write(working_path, DATA / "scenes/working"):
                        evidence["failed_autosave"] = await_autosave(page, root, session_id, False)
                        assert hashlib.sha256(working_path.read_bytes()).hexdigest() == original_working_hash
                        frame.evaluate("() => refreshSession(['blender_sessions'])")
                        warning = frame.locator("#scene-blender-autosave-warning")
                        warning.wait_for(state="visible")
                        evidence["warning_texts"] = {}
                        # Browser-language input fixture, delivered through the real Host bridge.
                        # Do not replace MediaForge strings/state or persistent user preferences.
                        for locale, message in (("ja", "自動復旧用の保存に失敗しました"),
                                                ("en", "Automatic recovery save failed")):
                            page.evaluate("""locale => {
                              Object.defineProperty(navigator, 'language', {configurable:true, get:()=>locale});
                              window.dispatchEvent(new Event('languagechange'));
                            }""", locale)
                            frame.wait_for_function("lang => document.documentElement.lang === lang", arg=locale)
                            frame.wait_for_function("text => document.querySelector('#scene-blender-autosave-warning').textContent.includes(text)", arg=message)
                            assert warning.is_visible()
                            evidence["warning_texts"][locale] = warning.inner_text()
                            page.screenshot(path=str(args.evidence_dir / f"autosave-failed-{locale}.png"))
                        evidence["failed_autosave_sec"] = round(time.monotonic()-autosave_began, 3)
                    evidence["successful_autosave"] = await_autosave(page, root, session_id, True)
                    autosave_hash = hashlib.sha256(working_path.read_bytes()).hexdigest()
                    assert autosave_hash != original_working_hash
                    assert call("scenes.get", {"scene_id": args.scene_id}) == before
                    frame.evaluate("() => refreshSession(['blender_sessions'])")
                    frame.locator("#scene-blender-autosave-warning").wait_for(state="hidden")
                    frame.wait_for_function("state.blenderRfb?._rfbConnectionState === 'connected'")
                    evidence["successful_autosave_sec"] = round(time.monotonic()-autosave_began, 3)
                    evidence["autosave_hash"] = autosave_hash
                    evidence["language_input"] = "navigator.language + browser languagechange fixture through Host bridge"
                    page.screenshot(path=str(args.evidence_dir / "autosave-retried.png"))
                if args.failure_kind == "auth-expiry":
                    assert owned["runtime_id"] == "blender-4.5.13-linux-x64"
                    evidence["successful_autosave"] = await_autosave(page, root, session_id, True)
                    autosave_hash = hashlib.sha256(working_path.read_bytes()).hexdigest()
                    assert autosave_hash != original_working_hash
                    evidence["autosave_hash"] = autosave_hash
                    assert call("scenes.get", {"scene_id": args.scene_id}) == before
                    frame.locator("#scene-blender-screen canvas").click(position={"x":320,"y":240})
                    page.keyboard.press("a")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Shift+D")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                    page.screenshot(path=str(args.evidence_dir / "post-autosave-edit.png"))
                    assert hashlib.sha256(working_path.read_bytes()).hexdigest() == autosave_hash
                    frame.locator("#scene-blender-close").click()
                    frame.wait_for_function("""async id => {
                      const s=(await call('blender.sessions.list',{})).items.find(s=>s.id===id);
                      return s?.connection_state==='disconnected';
                    }""", arg=session_id)
                if args.failure_kind == "save-conflict":
                    # Only this dedicated scene advances while its GUI owns the old base.
                    call("scenes.revisions.restore", {"scene_id": args.scene_id,
                        "base_revision_id": before["scene"]["current_revision_id"],
                        "target_revision_id": before["revisions"][0]["id"]})
                advanced = call("scenes.get", {"scene_id": args.scene_id})
                if args.manual_edit:
                    evidence["advanced"] = advanced
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
                elif args.failure_kind in {"blender-crash", "autosave-crash"}:
                    evidence["signaled_blender_pid"] = crash_owned_blender(cgroup, pids, owned["runtime_id"])
                elif args.failure_kind == "auth-expiry":
                    evidence["expired_gateway"] = expire_owned_gateway(session_id, user_id)
                failed = wait({"failed", "interrupted"}, 330 if args.failure_kind == "disconnect-timeout" else 90)
                evidence["terminal_sec"] = round(time.monotonic() - began, 3)
                expected_error = {"save-conflict": "scene_revision_conflict", "blender-crash": "blender_session_runner_lost",
                                  "autosave-crash": "blender_session_runner_lost",
                                  "auth-expiry": "blender_session_host_revoked",
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
                if args.failure_kind in {"autosave-crash", "auth-expiry"}:
                    assert digest == autosave_hash
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
                if args.manual_edit:
                    recovered_scene = call("scenes.get", {"scene_id": recovered["scene"]["id"]})
                    evidence["recovered_scene"] = recovered_scene
                    assert edit_helpers.mesh_count(recovered_scene) == 2 * edit_helpers.mesh_count(before)
                    assert edit_helpers.asset_hashes(before) == original_hashes
                    evidence["unsaved_edit_recovered"] = True
                    if args.failure_kind == "auth-expiry":
                        evidence["recovery_boundary"] = "Last autosave recovered; post-autosave input effect is not asserted"
                evidence.update(passed=True, ready=ready, failed=failed, recovered=recovered,
                    candidate_sha256=digest, candidate_bytes=candidate.stat().st_size,
                    process_cgroup_root_socket_reclaimed=True,
                    rfb_connection_tested=args.manual_edit or args.failure_kind == "disconnect-timeout",
                    not_tested=(["power failure", "crash during snapshot write", "post-autosave input effect"]
                        if args.failure_kind == "auth-expiry" else
                        ["power failure", "crash during snapshot write", "edits after last autosave"]
                        if args.failure_kind in {"autosave-crash", "auth-expiry"} else
                        (["manual GUI edit"] if not args.manual_edit else ["unsaved crash recovery", "autosave"])) +
                        ["GPU lease", "batch worker crash", "connected idle timeout"])
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
