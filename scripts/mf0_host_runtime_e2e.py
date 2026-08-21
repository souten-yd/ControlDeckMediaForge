#!/usr/bin/env python3
"""Real MF0 Host-runtime acceptance through public HTTP APIs only.

The caller supplies disposable ControlDeck and Media Forge processes. This
driver installs and always uninstalls the Add-on, exercises Jobs/Broker/files,
and writes a path-free JSON evidence document. It imports neither repository's
backend modules.
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit


TERMINAL_JOB_STATES = {"succeeded", "failed", "canceled", "interrupted"}


class AcceptanceError(RuntimeError):
    pass


def loopback_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("E2E origins must be plain-HTTP loopback origins")
    return value.rstrip("/")


class JsonSession:
    def __init__(self, origin: str, *, cookies: bool, timeout_sec: float = 15.0):
        self.origin = loopback_origin(origin)
        self.timeout_sec = timeout_sec
        handlers: list[Any] = []
        if cookies:
            handlers.append(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener = urllib.request.build_opener(*handlers)

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: object | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        if not path.startswith("/"):
            raise ValueError("request path must be absolute within the configured origin")
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {"Accept": "application/json", "X-Requested-With": "ControlDeck"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.origin}{path}", data=body, method=method, headers=headers,
        )
        try:
            with self.opener.open(request, timeout=self.timeout_sec) as response:
                status = response.status
                content = response.read(4 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            status = exc.code
            content = exc.read(64 * 1024)
        except urllib.error.URLError as exc:
            raise AcceptanceError(f"request failed: {method} {path}: host unavailable") from exc
        if status not in expected:
            detail = content.decode("utf-8", errors="replace")[:500]
            raise AcceptanceError(f"unexpected HTTP {status}: {method} {path}: {detail}")
        if len(content) > 4 * 1024 * 1024:
            raise AcceptanceError(f"response too large: {method} {path}")
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise AcceptanceError(f"non-JSON response: {method} {path}") from exc


def wait_until(
    description: str,
    probe: Callable[[], Any],
    accept: Callable[[Any], bool],
    *,
    timeout_sec: float = 20.0,
    interval_sec: float = 0.05,
) -> Any:
    deadline = time.monotonic() + timeout_sec
    latest: Any = None
    while time.monotonic() < deadline:
        latest = probe()
        if accept(latest):
            return latest
        time.sleep(interval_sec)
    raise AcceptanceError(f"timed out waiting for {description}; last observation={latest!r}")


def generation_input(intent: str, *, delay_sec: float = 0.0) -> dict[str, Any]:
    constraints: dict[str, Any] = {"width": 64, "height": 48}
    if delay_sec:
        constraints["_fake_delay_sec"] = delay_sec
    return {
        "operation": "image.generate",
        "intent": intent,
        "model_policy": "auto",
        "constraints": constraints,
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


def counter(snapshot: dict[str, Any], name: str) -> int:
    return int(snapshot.get("telemetry", {}).get("counters", {}).get(name, 0))


def job_by_id(host: JsonSession, job_id: str) -> dict[str, Any]:
    value = host.request(f"/api/v1/jobs/{job_id}")
    if not isinstance(value, dict):
        raise AcceptanceError("ControlDeck Job response is not an object")
    return value


def wait_job(host: JsonSession, job_id: str, *, timeout_sec: float = 25.0) -> dict[str, Any]:
    return wait_until(
        f"Job {job_id} terminal state",
        lambda: job_by_id(host, job_id),
        lambda value: value.get("status") in TERMINAL_JOB_STATES,
        timeout_sec=timeout_sec,
    )


def invoke_agent(
    host: JsonSession,
    contribution: str,
    arguments: dict[str, Any],
    *,
    wait: bool,
) -> dict[str, Any]:
    value = host.request(
        f"/api/v1/addons/media-forge/agent-tools/{contribution}/invoke",
        method="POST",
        payload={"arguments": arguments, "wait": wait},
        expected=(200,) if wait else (202,),
    )
    if not isinstance(value, dict) or not isinstance(value.get("job_id"), str):
        raise AcceptanceError("agent invocation did not return a structured job_id")
    return value


def resource_snapshot(host: JsonSession) -> dict[str, Any]:
    value = host.request("/api/v1/resources")
    if not isinstance(value, dict):
        raise AcceptanceError("resource snapshot is not an object")
    return value


def lease_for_job(snapshot: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in snapshot.get("leases", []) if item.get("job_id") == job_id),
        None,
    )


@dataclass
class AcceptanceRun:
    host: JsonSession
    media: JsonSession
    manifest: dict[str, Any]
    input_file: Path
    export_dir: Path

    def install(self) -> None:
        self.media.request("/test/health", method="POST", payload={"status": "setup_required"})
        self.host.request("/api/v1/addons", method="POST", payload=self.manifest, expected=(201,))
        enabled = self.host.request(
            "/api/v1/addons/media-forge/enable",
            method="POST",
            payload={"granted_capabilities": self.manifest["host_capabilities"]},
        )
        if enabled.get("state") != "setup_required":
            raise AcceptanceError("enabled Add-on did not expose setup_required")
        self.media.request("/test/health", method="POST", payload={"status": "healthy"})
        healthy = self.host.request("/api/v1/addons/media-forge/recheck", method="POST")
        if healthy.get("state") != "healthy":
            raise AcceptanceError("Add-on did not become healthy")

    def uninstall(self) -> None:
        values = self.host.request("/api/v1/addons")
        if any(item.get("id") == "media-forge" and item.get("installed") for item in values):
            self.host.request("/api/v1/addons/media-forge", method="DELETE")

    def discovery(self) -> dict[str, Any]:
        catalog = self.host.request("/api/v1/addons/execution-contributions")["contributions"]
        workflows = [item for item in catalog["workflow_executors"] if item["addon_id"] == "media-forge"]
        contexts = [item for item in catalog["context_actions"] if item["addon_id"] == "media-forge"]
        if len(workflows) != 1 or len(contexts) != 1:
            raise AcceptanceError("workflow/context contribution was not available exactly once")
        capabilities = invoke_agent(self.host, "media.capabilities", {}, wait=True)
        serialized = json.dumps(capabilities, sort_keys=True).lower()
        if any(value in serialized for value in ("model_id", "fake-image", "flux", "qwen")):
            raise AcceptanceError("capability discovery exposed a model identity")
        return {"capability_job_id": capabilities["job_id"], "workflow_count": 1, "context_count": 1}

    def workflow(self) -> dict[str, Any]:
        definition = {
            "nodes": [
                {"id": "start", "type": "trigger", "config": {"mode": "manual"}},
                {
                    "id": "generate",
                    "type": "addon.workflow:media-forge:media.generate",
                    "config": generation_input("MF0 real workflow delegation"),
                },
            ],
            "edges": [{"source": "start", "target": "generate"}],
        }
        before = len(self.media.request("/api/v1/jobs")["items"])
        created = self.host.request(
            "/api/v1/workflows",
            method="POST",
            payload={"name": "MF0 delegated runtime acceptance", "definition": definition},
            expected=(201,),
        )
        workflow_id = created["id"]
        try:
            self.host.request(f"/api/v1/workflows/{workflow_id}/dry-run", method="POST", payload={"input": {}})
            after_dry_run = len(self.media.request("/api/v1/jobs")["items"])
            if after_dry_run != before:
                raise AcceptanceError("workflow dry-run called Media Forge")
            started = self.host.request(
                f"/api/v1/workflows/{workflow_id}/test", method="POST", payload={"input": {}},
            )
            execution_id = started["execution_id"]
            execution = wait_until(
                "delegated workflow execution",
                lambda: self.host.request(f"/api/v1/workflow-executions/{execution_id}/live"),
                lambda value: value.get("status") not in {"RUNNING", "QUEUED", "WAITING"},
                timeout_sec=25,
            )
            if execution.get("status") != "SUCCEEDED":
                raise AcceptanceError(f"delegated workflow failed: {execution.get('status')}")
            output = execution.get("context", {}).get("generate", {}).get("output", {})
            media_job_id = output.get("job_id")
            if not isinstance(media_job_id, str):
                raise AcceptanceError("workflow output did not contain a Media Forge job_id")
            media_job = wait_until(
                "workflow Media Forge job",
                lambda: self.media.request(f"/api/v1/jobs/{media_job_id}"),
                lambda value: value.get("status") in TERMINAL_JOB_STATES,
                timeout_sec=25,
            )
            if media_job.get("status") != "succeeded":
                raise AcceptanceError("workflow Media Forge job did not succeed")
            return {
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                "execution_state": execution["status"],
                "media_job_id": media_job_id,
                "media_job_state": media_job["status"],
                "dry_run_media_job_delta": after_dry_run - before,
            }
        finally:
            self.host.request(f"/api/v1/workflows/{workflow_id}", method="DELETE")

    def context_action(self) -> dict[str, Any]:
        value = self.host.request(
            "/api/v1/addons/media-forge/context-actions/edit-image/invoke",
            method="POST",
            payload={"context_type": "file", "resource_id": str(self.input_file), "input": {}},
        )
        serialized = json.dumps(value, sort_keys=True)
        if str(self.input_file) in serialized or "grant_id" in serialized or "grant:" in serialized:
            raise AcceptanceError("context action reflected a Host path or scoped grant")
        source = value.get("context", {}).get("source", {})
        if source.get("size") != self.input_file.stat().st_size:
            raise AcceptanceError("context action did not read the selected scoped file")
        if (
            not isinstance(source.get("width"), int)
            or source["width"] <= 0
            or not isinstance(source.get("height"), int)
            or source["height"] <= 0
            or not isinstance(source.get("mode"), str)
        ):
            raise AcceptanceError("context action did not validate image geometry and mode")
        return {
            "action": value.get("action"),
            "route": value.get("route"),
            "source_name": source.get("name"),
            "source_size": source.get("size"),
            "source_width": source.get("width"),
            "source_height": source.get("height"),
            "source_mode": source.get("mode"),
            "path_or_grant_reflected": False,
        }

    def normal_generation(self) -> dict[str, Any]:
        started = time.monotonic()
        result = invoke_agent(
            self.host,
            "media.generate",
            generation_input("MF0 repeatable Host runtime acceptance"),
            wait=True,
        )
        elapsed = time.monotonic() - started
        job = job_by_id(self.host, result["job_id"])
        progress = job.get("progress", {})
        if job.get("status") != "succeeded" or progress.get("completed") != progress.get("total"):
            raise AcceptanceError("normal generation did not finish at complete progress")
        snapshot = resource_snapshot(self.host)
        lease = lease_for_job(snapshot, result["job_id"])
        if lease is None or lease.get("owner") != "addon:media-forge" or lease.get("state") != "released":
            raise AcceptanceError("normal generation lease was not released by the Add-on owner")
        return {
            "elapsed_sec": round(elapsed, 6),
            "job_id": result["job_id"],
            "phase": job.get("phase"),
            "progress": progress,
            "lease_id": lease["lease_id"],
            "device_id": lease["device_id"],
            "reserved_bytes": lease["reserved_bytes"],
            "lease_state": lease["state"],
        }

    def serialized_jobs(self) -> dict[str, Any]:
        first = invoke_agent(
            self.host, "media.generate", generation_input("MF0 serialized first", delay_sec=1.5), wait=False,
        )
        first_active = wait_until(
            "first active lease",
            lambda: resource_snapshot(self.host),
            lambda value: (lease_for_job(value, first["job_id"]) or {}).get("state") == "active",
        )
        second = invoke_agent(
            self.host, "media.generate", generation_input("MF0 serialized second", delay_sec=0.2), wait=False,
        )
        waiting = wait_until(
            "second resource wait",
            lambda: resource_snapshot(self.host),
            lambda value: any(
                item.get("job_id") == second["job_id"] and item.get("state") == "waiting"
                for item in value.get("requests", [])
            ),
        )
        waiting_request = next(
            item for item in waiting["requests"]
            if item.get("job_id") == second["job_id"] and item.get("state") == "waiting"
        )
        first_job = wait_job(self.host, first["job_id"])
        second_job = wait_job(self.host, second["job_id"])
        final = resource_snapshot(self.host)
        leases = [lease_for_job(final, item["job_id"]) for item in (first, second)]
        if any(job.get("status") != "succeeded" for job in (first_job, second_job)):
            raise AcceptanceError("serialized jobs did not both succeed")
        if any(lease is None or lease.get("state") != "released" for lease in leases):
            raise AcceptanceError("serialized job lease remained active")
        return {
            "first_job_id": first["job_id"],
            "second_job_id": second["job_id"],
            "waiting_reason": waiting_request.get("reason"),
            "queue_position": waiting_request.get("queue_position"),
            "first_active_device": lease_for_job(first_active, first["job_id"])["device_id"],
            "lease_states": [lease["state"] for lease in leases],
        }

    def cancel(self) -> dict[str, Any]:
        result = invoke_agent(
            self.host, "media.generate", generation_input("MF0 Host cancel", delay_sec=3), wait=False,
        )
        active = wait_until(
            "cancel target active lease",
            lambda: resource_snapshot(self.host),
            lambda value: (lease_for_job(value, result["job_id"]) or {}).get("state") == "active",
        )
        self.host.request(f"/api/v1/jobs/{result['job_id']}/cancel", method="POST")
        job = wait_job(self.host, result["job_id"])
        released = wait_until(
            "canceled lease release",
            lambda: resource_snapshot(self.host),
            lambda value: (lease_for_job(value, result["job_id"]) or {}).get("state") == "released",
        )
        if job.get("status") != "canceled":
            raise AcceptanceError("Host-canceled job did not become canceled")
        return {
            "job_id": result["job_id"],
            "lease_id": lease_for_job(active, result["job_id"])["lease_id"],
            "job_state": job["status"],
            "lease_state": lease_for_job(released, result["job_id"])["state"],
        }

    def renew(self) -> dict[str, Any]:
        before = resource_snapshot(self.host)
        result = invoke_agent(
            self.host, "media.generate", generation_input("MF0 Host renew", delay_sec=10), wait=False,
        )
        started = time.monotonic()
        job = wait_job(self.host, result["job_id"], timeout_sec=20)
        elapsed = time.monotonic() - started
        after = resource_snapshot(self.host)
        delta = counter(after, "lease.renewed") - counter(before, "lease.renewed")
        lease = lease_for_job(after, result["job_id"])
        if job.get("status") != "succeeded" or delta < 1 or lease is None or lease.get("state") != "released":
            raise AcceptanceError("long job did not renew and release its lease")
        return {"job_id": result["job_id"], "elapsed_sec": round(elapsed, 6), "renew_delta": delta}

    def scoped_file_roundtrip(self) -> dict[str, Any]:
        read_grant = self.host.request(
            "/api/v1/addons/media-forge/file-grants",
            method="POST",
            payload={"path": str(self.input_file), "kind": "read"},
            expected=(201,),
        )
        export_grant = self.host.request(
            "/api/v1/addons/media-forge/file-grants",
            method="POST",
            payload={"path": str(self.export_dir), "kind": "export"},
            expected=(201,),
        )
        output_name = "mf0-roundtrip.bin"
        result = self.host.request(
            "/addon-frame/media-forge/test/host-files/roundtrip",
            method="POST",
            payload={
                "read_grant_id": read_grant["grant_id"],
                "export_grant_id": export_grant["grant_id"],
                "filename": output_name,
            },
        )
        output = self.export_dir / output_name
        source_bytes = self.input_file.read_bytes()
        output_bytes = output.read_bytes()
        if source_bytes != output_bytes:
            raise AcceptanceError("scoped file roundtrip changed the content")
        serialized = json.dumps(result, sort_keys=True).lower()
        if "path" in serialized or str(self.input_file.parent).lower() in serialized:
            raise AcceptanceError("Host path leaked into the Media Forge response")
        return {
            "source_grant_id": read_grant["grant_id"],
            "export_grant_id": export_grant["grant_id"],
            "asset_id": result["output"]["asset_id"],
            "size_bytes": len(output_bytes),
            "sha256": hashlib.sha256(output_bytes).hexdigest(),
            "content_identical": True,
        }

    def disable_active(self) -> dict[str, Any]:
        result = invoke_agent(
            self.host, "media.generate", generation_input("MF0 disable active", delay_sec=3), wait=False,
        )
        active = wait_until(
            "disable target active lease",
            lambda: resource_snapshot(self.host),
            lambda value: (lease_for_job(value, result["job_id"]) or {}).get("state") == "active",
        )
        disabled = self.host.request("/api/v1/addons/media-forge/disable", method="POST")
        job = wait_job(self.host, result["job_id"])
        released = wait_until(
            "disable target lease release",
            lambda: resource_snapshot(self.host),
            lambda value: (lease_for_job(value, result["job_id"]) or {}).get("state") == "released",
        )
        if job.get("status") != "canceled" or disabled.get("enabled") is not False:
            raise AcceptanceError("disable did not cancel the active Add-on Job")
        reenabled = self.host.request(
            "/api/v1/addons/media-forge/enable",
            method="POST",
            payload={"granted_capabilities": self.manifest["host_capabilities"]},
        )
        if reenabled.get("state") != "healthy":
            raise AcceptanceError("Add-on did not return healthy after re-enable")
        return {
            "job_id": result["job_id"],
            "lease_id": lease_for_job(active, result["job_id"])["lease_id"],
            "job_state": job["status"],
            "lease_state": lease_for_job(released, result["job_id"])["state"],
            "reenabled_state": reenabled["state"],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--media-forge-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, required=True)
    args = parser.parse_args()

    password = os.environ.get(args.password_env)
    if not password:
        raise AcceptanceError(f"password environment variable is unset: {args.password_env}")

    host = JsonSession(args.control_deck_url, cookies=True)
    media = JsonSession(args.media_forge_url, cookies=False)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest["runtime"]["base_url"] = loopback_origin(args.media_forge_url)
    if not args.input_file.is_file() or not args.export_dir.is_dir():
        raise AcceptanceError("input file and export directory must already exist")

    host.request(
        "/api/v1/auth/login",
        method="POST",
        payload={"username": args.username, "password": password},
    )
    run = AcceptanceRun(host, media, manifest, args.input_file.resolve(), args.export_dir.resolve())
    evidence: dict[str, Any] = {"started_at": time.time(), "checks": {}}
    try:
        run.uninstall()
        run.install()
        evidence["checks"]["discovery"] = run.discovery()
        evidence["checks"]["workflow"] = run.workflow()
        evidence["checks"]["context_action"] = run.context_action()
        evidence["checks"]["normal_generation"] = run.normal_generation()
        evidence["checks"]["serialized_jobs"] = run.serialized_jobs()
        evidence["checks"]["host_cancel"] = run.cancel()
        evidence["checks"]["lease_renew"] = run.renew()
        evidence["checks"]["scoped_file_roundtrip"] = run.scoped_file_roundtrip()
        evidence["checks"]["disable_active"] = run.disable_active()
    finally:
        run.uninstall()
    evidence["finished_at"] = time.time()
    evidence["elapsed_sec"] = round(evidence["finished_at"] - evidence["started_at"], 6)
    args.evidence_json.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_json.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
