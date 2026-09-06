"""Installed CPU child-credential acceptance with bounded queue fault injection.

Run in the Host diagnostic environment (PYTHONPATH=Host/backend). No product
code, timeout, token TTL, service config or existing job is changed. Four
dedicated Blender children are paused for 160 seconds each, below the normal
180-second worker timeout. Two later jobs remain queued beyond the original
600-second credential expiry. One is canceled and the other completes.

This verifies real queue/refresh/control/terminal behavior, not natural compute
duration or OpenCode's language-driven authoring. Tokens remain in memory.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import threading
import time
import uuid

import httpx


def main() -> None:
    from app.addons import tokens
    from app.config import data_dir
    from app.features import registry

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--core-url", default="http://127.0.0.1:9130")
    parser.add_argument("--expected-version", default="0.28.16")
    args = parser.parse_args()
    host_data = data_dir()
    core_data = host_data / "feature-data/media-forge/data"
    host_db = sqlite3.connect(f"file:{host_data / 'control-deck.db'}?mode=ro", uri=True)
    core_db = sqlite3.connect(f"file:{core_data / 'media-forge.sqlite3'}?mode=ro", uri=True)
    user = host_db.execute("SELECT id,is_active FROM users WHERE username=?", ("mf-e2e",)).fetchone()
    assert user and user[1], "dedicated E2E user must exist and be active"
    assert tokens.TOKEN_TTL_SECONDS == 600
    assert not core_db.execute("SELECT id FROM jobs WHERE status IN ('queued','running')").fetchall()
    assert not core_db.execute("SELECT id FROM blender_web_sessions WHERE state IN ('queued','preparing','starting','ready','saving','stopping')").fetchall()
    installed = registry.status("media-forge")
    assert installed["health"] == "healthy" and installed["version"] == args.expected_version, installed["version"]
    service_pid = int(subprocess.check_output([
        "systemctl", "--user", "show", "cdapp-feature-media-forge.service", "--property=MainPID", "--value",
    ], text=True).strip())
    args.evidence_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    events: list[dict[str, object]] = []
    jobs: list[dict[str, str]] = []
    held: dict[int, threading.Timer] = {}
    run_id = uuid.uuid4().hex[:12]

    def event(kind: str, **values: object) -> None:
        item = {"elapsed_sec": round(time.monotonic() - started, 3), "event": kind, **values}
        events.append(item)
        (args.evidence_dir / "events.json").write_text(json.dumps(events, indent=2) + "\n")
        print(json.dumps(item), flush=True)

    client = httpx.Client(base_url=args.core_url, timeout=20)

    def call(method: str, value: dict[str, object]) -> dict:
        # A fresh normal caller identity is not a refresh of the child's token.
        bearer = tokens.issue("media-forge", subject=str(user[0]), kind="service", actor_user_id=user[0])
        for attempt in range(3):
            try:
                response = client.post(f"/addon/v1/agent/{method}", json={"input": value}, headers={
                    "Authorization": f"Bearer {bearer}", "X-Control-Deck-Addon-ID": "media-forge",
                })
            except httpx.TransportError as exc:
                if method != "job/status" or attempt == 2:
                    raise
                event("observation_retry", job_id=value.get("job_id"), error_type=type(exc).__name__)
                time.sleep(1)
                continue
            if method == "job/status" and response.status_code in {502, 503, 504} and attempt < 2:
                event("observation_retry", job_id=value.get("job_id"), status_code=response.status_code)
                time.sleep(1)
                continue
            break
        assert response.status_code == 200, (method, response.status_code, response.text[:300])
        return response.json()

    def submit(label: str) -> dict[str, str]:
        marker = f"cred_{run_id}_{label}"
        value = call("scene/create", {"name": f"Credential acceptance {run_id} {label}", "recipe": {
            "operations": [{"type": "primitive.add", "object_id": marker, "primitive": "uv_sphere",
                            "name": "Credential fixture", "dimensions": [1, 1, 1], "vertices": 128}],
        }})
        assert value["detached"] is True
        job = {"job_id": value["job_id"], "host_job_id": value["host_job_id"], "marker": marker}
        jobs.append(job)
        event("submitted", **job)
        return job

    def status(job: dict[str, str]) -> dict:
        return call("job/status", {"job_id": job["job_id"]})

    def resume(fd: int) -> None:
        try:
            signal.pidfd_send_signal(fd, signal.SIGCONT)
        except (OSError, ProcessLookupError):
            pass

    def pause_child(job: dict[str, str]) -> int:
        deadline = time.monotonic() + 15
        recipe_root = (core_data / "scenes/recipes").resolve()
        while time.monotonic() < deadline:
            # The onefile bootloader is systemd's main PID; Uvicorn is its child.
            children: list[str] = []
            pending = [str(service_pid)]
            while pending and len(children) < 64:
                parent = pending.pop()
                try:
                    descendants = Path(f"/proc/{parent}/task/{parent}/children").read_text().split()
                except OSError:
                    continue
                children.extend(descendants)
                pending.extend(descendants)
            for child in children:
                process = Path("/proc") / child
                try:
                    argv = (process / "cmdline").read_bytes().split(b"\0")
                    if not any(arg.endswith(b"/scene_recipe.py") for arg in argv):
                        continue
                    cwd = (process / "cwd").resolve(strict=True)
                    if not cwd.is_relative_to(recipe_root):
                        continue
                    recipe = json.loads((cwd / "recipe.json").read_text())
                    if recipe["operations"][0]["object_id"] != job["marker"]:
                        continue
                    fd = os.pidfd_open(int(child))
                    signal.pidfd_send_signal(fd, signal.SIGSTOP)
                    timer = threading.Timer(167, resume, args=(fd,))
                    timer.daemon = True
                    timer.start()
                    held[fd] = timer
                    event("child_paused", job_id=job["job_id"], pid=int(child))
                    return fd
                except (OSError, ValueError, KeyError):
                    continue
            time.sleep(0.01)
        raise AssertionError(f"owned recipe child not found for {job['job_id']}")

    def refresh_rows(job: dict[str, str]) -> list:
        return host_db.execute(
            "SELECT timestamp,result FROM audit_logs WHERE username=? AND action=? AND resource_id=? ORDER BY timestamp",
            ("addon:media-forge", "addon.runtime.job.credential.refresh", job["host_job_id"]),
        ).fetchall()

    completed = False
    try:
        event("preflight", version=installed["version"], service_pid=service_pid, ttl_seconds=600,
              worker_timeout_seconds=180, pause_seconds=160, injection="SIGSTOP on exact owned children via pidfd")
        first = submit("blocker0")
        fd = pause_child(first)
        blockers = [first, *(submit(f"blocker{index}") for index in range(1, 4))]
        success = submit("success")
        canceled = submit("cancel")
        canceled_result = None
        for index, blocker in enumerate(blockers):
            if index:
                fd = pause_child(blocker)
            hold_started = time.monotonic()
            next_log = 0.0
            while time.monotonic() - hold_started < 160:
                elapsed = time.monotonic() - started
                if elapsed >= next_log:
                    projection = status(success)
                    assert projection["status"] in {"queued", "running"}, projection
                    event("waiting", blocker=index, success_status=projection["status"], refresh_events=refresh_rows(success))
                    next_log = elapsed + 30
                if elapsed > 615 and canceled_result is None:
                    assert refresh_rows(canceled), "no audited refresh before post-expiry cancel"
                    canceled_result = call("job/cancel", {"job_id": canceled["job_id"]})
                    assert canceled_result["status"] == "canceled", canceled_result
                    event("canceled_after_original_expiry", result=canceled_result, refresh_events=refresh_rows(canceled))
                time.sleep(1)
            held[fd].cancel()
            resume(fd)
            event("child_resumed", job_id=blocker["job_id"], held_seconds=time.monotonic() - hold_started)
            del held[fd]
            os.close(fd)
        assert canceled_result is not None
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            value = status(success)
            if value["status"] in {"succeeded", "failed", "canceled"}:
                break
            time.sleep(1)
        assert value["status"] == "succeeded" and value["host_terminal_sent"] is True, value
        assert refresh_rows(success), "successful job has no audited credential refresh"
        finals = [status(job) for job in jobs]
        assert [item["status"] for item in finals] == ["succeeded"] * 5 + ["canceled"], finals
        assert all(item["host_terminal_sent"] for item in finals)
        host_finals = [host_db.execute("SELECT status FROM jobs WHERE id=?", (job["host_job_id"],)).fetchone() for job in jobs]
        assert host_finals == [("succeeded",)] * 5 + [("canceled",)], host_finals
        event("complete", final_jobs=finals, host_statuses=host_finals, refresh_events=refresh_rows(success))
        completed = True
    except Exception as exc:
        observed = [core_db.execute("SELECT status,error_json FROM jobs WHERE id=?", (job["job_id"],)).fetchone() for job in jobs]
        event("failed", error_type=type(exc).__name__, local_statuses=observed)
        raise
    finally:
        for fd, timer in held.items():
            timer.cancel()
            resume(fd)
            os.close(fd)
        if not completed:
            for job in jobs:
                try:
                    call("job/cancel", {"job_id": job["job_id"]})
                except Exception as exc:
                    event("cleanup_failed", job_id=job["job_id"], error_type=type(exc).__name__)
        client.close()
        host_db.close()
        core_db.close()


if __name__ == "__main__":
    main()
