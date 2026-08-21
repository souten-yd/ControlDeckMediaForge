#!/usr/bin/env python3
"""Run one real G1 generation through ControlDeck and record bounded evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import time
from pathlib import Path
from typing import Any

from mf0_host_runtime_e2e import AcceptanceError, JsonSession, loopback_origin


TERMINAL_EXECUTION_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "INTERRUPTED"}
TERMINAL_MEDIA_STATES = {"succeeded", "failed", "canceled"}


def image_device() -> Path:
    candidates: list[tuple[int, Path]] = []
    for device in Path("/sys/class/drm").glob("card[0-9]*/device"):
        total = device / "mem_info_vram_total"
        try:
            candidates.append((int(total.read_text(encoding="ascii").strip()), device))
        except (OSError, ValueError):
            continue
    if not candidates:
        raise AcceptanceError("no DRM VRAM counter is available")
    return max(candidates)[1]


def process_metrics() -> tuple[int, int]:
    peak_rss = 0
    peak_swap = 0
    for process in Path("/proc").glob("[0-9]*"):
        try:
            command = (process / "cmdline").read_bytes().replace(b"\0", b" ")
            if b"worker_packs.image.worker" not in command:
                continue
            fields = {}
            for line in (process / "status").read_text(encoding="utf-8").splitlines():
                if line.startswith(("VmRSS:", "VmSwap:")):
                    key, value = line.split(":", 1)
                    fields[key] = int(value.strip().split()[0]) * 1024
            peak_rss = max(peak_rss, fields.get("VmRSS", 0))
            peak_swap = max(peak_swap, fields.get("VmSwap", 0))
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return peak_rss, peak_swap


def worker_pids() -> list[int]:
    found: list[int] = []
    for process in Path("/proc").glob("[0-9]*"):
        try:
            if b"worker_packs.image.worker" in (process / "cmdline").read_bytes():
                found.append(int(process.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return found


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    parser.add_argument("--steps", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--evidence-json", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--cancel-after-sec", type=float)
    parser.add_argument("--kill-worker-after-sec", type=float)
    parser.add_argument("--timeout-sec", type=float, default=900)
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise AcceptanceError(f"password environment variable is unset: {args.password_env}")
    if not 256 <= args.width <= 1024 or not 256 <= args.height <= 1024:
        raise AcceptanceError("G1 measured run dimensions must be within 256..1024")
    if args.cancel_after_sec is not None and (
        args.cancel_after_sec <= 0 or args.expected_sha256 is not None
    ):
        raise AcceptanceError("cancel runs require a positive delay and no expected SHA-256")
    if args.kill_worker_after_sec is not None and (
        args.kill_worker_after_sec <= 0
        or args.expected_sha256 is not None
        or args.cancel_after_sec is not None
    ):
        raise AcceptanceError("worker crash runs require a positive delay and no cancel or expected SHA-256")

    host = JsonSession(loopback_origin(args.control_deck_url), cookies=True)
    media = JsonSession(loopback_origin(args.media_forge_url), cookies=False)
    host.request(
        "/api/v1/auth/login",
        method="POST",
        payload={"username": args.username, "password": password},
    )
    addons = host.request("/api/v1/addons")
    addon = next((item for item in addons if item.get("id") == "media-forge"), None)
    if addon is not None and addon.get("installed") is True and addon.get("enabled") is True:
        for _ in range(20):
            addon = host.request("/api/v1/addons/media-forge/recheck", method="POST")
            if addon.get("state") == "healthy":
                break
            time.sleep(0.25)
    if addon is None or addon.get("state") != "healthy":
        raise AcceptanceError("Media Forge must already be installed, enabled, and healthy")

    request = {
        "operation": "image.generate",
        "intent": args.prompt,
        "model_policy": "auto",
        "constraints": {
            "width": args.width,
            "height": args.height,
            "steps": args.steps,
            "seed": args.seed,
        },
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }
    definition = {
        "nodes": [
            {"id": "start", "type": "trigger", "config": {"mode": "manual"}},
            {
                "id": "generate",
                "type": "addon.workflow:media-forge:media.generate",
                "config": request,
            },
        ],
        "edges": [{"source": "start", "target": "generate"}],
    }
    workflow = host.request(
        "/api/v1/workflows",
        method="POST",
        payload={"name": f"G1 {args.width}x{args.height} measured generation", "definition": definition},
        expected=(201,),
    )
    workflow_id = workflow["id"]
    drm = image_device()
    idle_vram = int((drm / "mem_info_vram_used").read_text(encoding="ascii").strip())
    resources_before = host.request("/api/v1/resources")
    renew_before = int(resources_before.get("telemetry", {}).get("counters", {}).get("lease.renewed", 0))
    started_wall = time.time()
    started = time.monotonic()
    peak_vram = idle_vram
    peak_vram_at_sec = 0.0
    peak_worker_rss = 0
    peak_worker_rss_at_sec = 0.0
    peak_worker_swap = 0
    sample_count = 0
    observed_active_lease = False
    observed_lease_id: str | None = None
    canceled_host_job_id: str | None = None
    killed_worker_pid: int | None = None
    execution: dict[str, Any] = {}
    try:
        started_execution = host.request(
            f"/api/v1/workflows/{workflow_id}/test", method="POST", payload={"input": {}},
        )
        execution_id = started_execution["execution_id"]
        deadline = started + args.timeout_sec
        media_job_id: str | None = None
        while time.monotonic() < deadline:
            execution = host.request(f"/api/v1/workflow-executions/{execution_id}/live")
            current_vram = int((drm / "mem_info_vram_used").read_text(encoding="ascii").strip())
            rss, swap = process_metrics()
            sample_count += 1
            if current_vram > peak_vram:
                peak_vram = current_vram
                peak_vram_at_sec = time.monotonic() - started
            if rss > peak_worker_rss:
                peak_worker_rss = rss
                peak_worker_rss_at_sec = time.monotonic() - started
            peak_worker_swap = max(peak_worker_swap, swap)
            resources = host.request("/api/v1/resources")
            active_media_leases = [
                item for item in resources.get("leases", [])
                if item.get("owner") == "addon:media-forge" and item.get("state") == "active"
            ]
            if active_media_leases:
                observed_active_lease = True
                observed_lease_id = active_media_leases[-1].get("lease_id")
                if (
                    args.cancel_after_sec is not None
                    and canceled_host_job_id is None
                    and time.monotonic() - started >= args.cancel_after_sec
                ):
                    canceled_host_job_id = active_media_leases[-1].get("job_id")
                    if not isinstance(canceled_host_job_id, str):
                        raise AcceptanceError("active Media Forge lease had no Host job ID")
                    host.request(f"/api/v1/jobs/{canceled_host_job_id}/cancel", method="POST")
                if (
                    args.kill_worker_after_sec is not None
                    and killed_worker_pid is None
                    and time.monotonic() - started >= args.kill_worker_after_sec
                ):
                    pids = worker_pids()
                    if len(pids) == 1:
                        killed_worker_pid = pids[0]
                        os.kill(killed_worker_pid, signal.SIGKILL)
            if execution.get("status") in TERMINAL_EXECUTION_STATES:
                break
            time.sleep(0.2)
        else:
            raise AcceptanceError("workflow execution exceeded its bounded timeout")
        if execution.get("status") != "SUCCEEDED":
            raise AcceptanceError(f"workflow generation failed: {execution.get('status')}")
        output = execution.get("context", {}).get("generate", {}).get("output", {})
        media_job_id = output.get("job_id")
        if not isinstance(media_job_id, str):
            raise AcceptanceError("workflow output did not contain a Media Forge job_id")
        while time.monotonic() < deadline:
            media_job = media.request(f"/api/v1/jobs/{media_job_id}")
            current_vram = int((drm / "mem_info_vram_used").read_text(encoding="ascii").strip())
            rss, swap = process_metrics()
            sample_count += 1
            if current_vram > peak_vram:
                peak_vram = current_vram
                peak_vram_at_sec = time.monotonic() - started
            if rss > peak_worker_rss:
                peak_worker_rss = rss
                peak_worker_rss_at_sec = time.monotonic() - started
            peak_worker_swap = max(peak_worker_swap, swap)
            resources = host.request("/api/v1/resources")
            active_media_leases = [
                item for item in resources.get("leases", [])
                if item.get("owner") == "addon:media-forge" and item.get("state") == "active"
            ]
            if active_media_leases:
                observed_active_lease = True
                observed_lease_id = active_media_leases[-1].get("lease_id")
                if (
                    args.cancel_after_sec is not None
                    and canceled_host_job_id is None
                    and time.monotonic() - started >= args.cancel_after_sec
                ):
                    canceled_host_job_id = active_media_leases[-1].get("job_id")
                    if not isinstance(canceled_host_job_id, str):
                        raise AcceptanceError("active Media Forge lease had no Host job ID")
                    host.request(f"/api/v1/jobs/{canceled_host_job_id}/cancel", method="POST")
                if (
                    args.kill_worker_after_sec is not None
                    and killed_worker_pid is None
                    and time.monotonic() - started >= args.kill_worker_after_sec
                ):
                    pids = worker_pids()
                    if len(pids) == 1:
                        killed_worker_pid = pids[0]
                        os.kill(killed_worker_pid, signal.SIGKILL)
            if media_job.get("status") in TERMINAL_MEDIA_STATES:
                break
            time.sleep(0.2)
        else:
            raise AcceptanceError("Media Forge job exceeded its bounded timeout")
        if args.cancel_after_sec is not None:
            if canceled_host_job_id is None or media_job.get("status") != "canceled":
                raise AcceptanceError(f"Host cancellation did not cancel Media Forge: {media_job.get('status')}")
            release_deadline = time.monotonic() + 10
            while True:
                resources_after = host.request("/api/v1/resources")
                active_after = [
                    item for item in resources_after.get("leases", [])
                    if item.get("owner") == "addon:media-forge" and item.get("state") == "active"
                ]
                if not active_after:
                    break
                if time.monotonic() >= release_deadline:
                    raise AcceptanceError("Media Forge lease remained active after Host cancellation")
                time.sleep(0.1)
            media_leases = [
                item for item in resources_after.get("leases", []) if item.get("owner") == "addon:media-forge"
            ]
            latest_lease = next(
                (item for item in media_leases if item.get("lease_id") == observed_lease_id),
                None,
            )
            if latest_lease is None or latest_lease.get("state") != "released":
                raise AcceptanceError("canceled Media Forge lease was not released")
            evidence = {
                "started_at": started_wall,
                "elapsed_sec": time.monotonic() - started,
                "request": request,
                "workflow_execution_id": execution_id,
                "media_job_id": media_job_id,
                "media_job_status": media_job.get("status"),
                "canceled_host_job_id": canceled_host_job_id,
                "idle_vram_bytes": idle_vram,
                "peak_vram_bytes": peak_vram,
                "peak_worker_rss_bytes": peak_worker_rss,
                "peak_worker_swap_bytes": peak_worker_swap,
                "active_lease_observed": observed_active_lease,
                "lease": latest_lease,
                "active_leases_after": len(active_after),
            }
            args.evidence_json.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            args.evidence_json.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(evidence, sort_keys=True))
            return 0
        if args.kill_worker_after_sec is not None:
            resources_after = host.request("/api/v1/resources")
            active_after = [
                item for item in resources_after.get("leases", [])
                if item.get("owner") == "addon:media-forge" and item.get("state") == "active"
            ]
            if killed_worker_pid is None or media_job.get("status") != "failed":
                raise AcceptanceError(f"worker crash was not normalized: {media_job.get('status')}")
            if media_job.get("error", {}).get("code") != "worker_crash" or active_after:
                raise AcceptanceError("worker crash did not fail closed and release its lease")
            health = media.request("/health")
            if health.get("status") != "healthy":
                raise AcceptanceError("Media Forge core became unhealthy after worker crash")
            evidence = {
                "started_at": started_wall,
                "elapsed_sec": time.monotonic() - started,
                "request": request,
                "workflow_execution_id": execution_id,
                "media_job_id": media_job_id,
                "media_job_status": media_job.get("status"),
                "media_job_error": media_job.get("error"),
                "killed_worker_pid": killed_worker_pid,
                "active_lease_observed": observed_active_lease,
                "active_leases_after": len(active_after),
                "core_health_after": health.get("status"),
            }
            args.evidence_json.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            args.evidence_json.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(evidence, sort_keys=True))
            return 0
        if media_job.get("status") != "succeeded" or len(media_job.get("asset_ids", [])) != 1:
            raise AcceptanceError(f"Media Forge generation failed: {media_job.get('error')}")
        asset_id = media_job["asset_ids"][0]
        asset = media.request(f"/api/v1/assets/{asset_id}")
        provenance = media.request(f"/api/v1/assets/{asset_id}/provenance")
        content_request = media.opener.open(f"{media.origin}/api/v1/assets/{asset_id}/content", timeout=15)
        content = content_request.read(64 * 1024 * 1024 + 1)
        if len(content) > 64 * 1024 * 1024:
            raise AcceptanceError("generated asset exceeded the bounded evidence read")
        content_sha = sha256(content)
        if content_sha != asset.get("sha256") or content_sha != provenance.get("output_sha256"):
            raise AcceptanceError("asset bytes, catalog hash, and provenance hash differ")
        if args.expected_sha256 is not None and content_sha != args.expected_sha256:
            raise AcceptanceError("deterministic regeneration hash did not match")
        resources_after = host.request("/api/v1/resources")
        active_after = [
            item for item in resources_after.get("leases", [])
            if item.get("owner") == "addon:media-forge" and item.get("state") == "active"
        ]
        if active_after:
            raise AcceptanceError("Media Forge lease remained active after generation")
        media_leases = [
            item for item in resources_after.get("leases", []) if item.get("owner") == "addon:media-forge"
        ]
        latest_lease = next(
            (item for item in media_leases if item.get("lease_id") == observed_lease_id),
            media_leases[-1] if media_leases else None,
        )
        renew_after = int(resources_after.get("telemetry", {}).get("counters", {}).get("lease.renewed", 0))
        evidence = {
            "started_at": started_wall,
            "elapsed_sec": time.monotonic() - started,
            "request": request,
            "workflow_execution_id": execution_id,
            "media_job_id": media_job_id,
            "asset": asset,
            "provenance": provenance,
            "output_sha256": content_sha,
            "output_size_bytes": len(content),
            "idle_vram_bytes": idle_vram,
            "peak_vram_bytes": peak_vram,
            "peak_vram_delta_bytes": peak_vram - idle_vram,
            "peak_vram_at_sec": peak_vram_at_sec,
            "peak_worker_rss_bytes": peak_worker_rss,
            "peak_worker_rss_at_sec": peak_worker_rss_at_sec,
            "peak_worker_swap_bytes": peak_worker_swap,
            "monitor_sample_count": sample_count,
            "active_lease_observed": observed_active_lease,
            "lease": latest_lease,
            "lease_renew_delta": renew_after - renew_before,
            "active_leases_after": len(active_after),
        }
        args.evidence_json.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        args.evidence_json.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(evidence, sort_keys=True))
    finally:
        host.request(f"/api/v1/workflows/{workflow_id}", method="DELETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
