"""Real HTTP terminal recovery with separate Host/core venvs and isolated data.

Coordinator/serve run in the Host diagnostic venv. Core modes run only in the
MediaForge core venv. Bearers cross an anonymous stdin pipe, never argv/files.
No installed service, scene, runtime, or Job is modified.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import uuid


async def core(mode: str) -> None:
    from mediaforge.domain import JobRequest, JobStatus
    from mediaforge.host.client import ControlDeckHostClient
    from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
    from mediaforge.store import Store

    value = json.load(sys.stdin)
    store = Store(Path(value["core_data"]))
    store.initialize()
    host = ControlDeckHostClient(value["host_url"])
    try:
        identity = await host.authenticate({"Authorization": value["authorization"], "X-Control-Deck-Addon-ID": "media-forge"})
        owner = identity.actor_subject
        assert owner
        if mode == "seed":
            local_ids = []
            for target in value["targets"]:
                job = store.create_job(JobRequest(operation="media.inspect", intent="terminal HTTP fixture"), host_managed=True)
                store.create_scene_recipe_task(job.id, owner=owner, host_job_id=target["id"], operation="scene.create",
                    runtime_id="fixture", runtime_version="4.5.9", base_revision_id=None,
                    input_sha256="1" * 64, idempotency_key="2" * 64, request={})
                store.update_job(job.id, status=JobStatus(target["payload"]["status"]))
                store.update_scene_recipe_task(job.id, stage="fixture_terminal")
                store.queue_scene_recipe_terminal(job.id, target["payload"])
                local_ids.append(job.id)
            print(json.dumps({"local_ids": local_ids}))
        else:
            manager = SceneRecipeJobManager(store, object(), host)
            for job_id in value["local_ids"]:
                await manager.reconcile_terminal(job_id, identity)
            output = [manager.projection(job_id, owner) for job_id in value["local_ids"]]
            assert [item["host_terminal_sent"] for item in output] == [False, True]
            assert output[0]["host_terminal_reconciliation"]["status"] == "interrupted"
            assert output[1]["host_terminal_reconciliation"]["terminal_matches"] is True
            assert len(store.list_jobs()) == 2
            assert not manager._tasks and not manager._executions
            print(json.dumps({"projections": output}))
    finally:
        await host.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-repo", type=Path)
    parser.add_argument("--core-python", type=Path)
    parser.add_argument("--package-executable", type=Path)
    parser.add_argument("--serve", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--core-mode", choices=["seed", "consume"])
    args = parser.parse_args()
    if args.core_mode:
        asyncio.run(core(args.core_mode))
        return
    root = args.serve or Path(tempfile.mkdtemp(prefix="mf-terminal-http-"))
    config = root / "config.yaml"
    if not args.serve:
        config.write_text(f"data_dir: {root}/host-data\n")
    os.environ["CONTROL_DECK_CONFIG"] = str(config)
    os.environ["CONTROL_DECK_DB_URL"] = f"sqlite:///{root}/host.db"
    from app.jobs import service as jobs
    if args.serve:
        from fastapi import FastAPI
        import uvicorn
        from app.addon_runtime.router import router
        assert not jobs._jobs and jobs.recover_on_startup() == 1
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")
        return
    assert args.host_repo and args.core_python
    import httpx
    from app.addons import registry, tokens
    from app.addons.schema import parse_manifest
    from app.bootstrap import init_db, seed_roles, create_admin
    from app.database import SessionLocal
    init_db()
    with SessionLocal() as db:
        seed_roles(db)
        owner = create_admin(db, "terminal-e2e", uuid.uuid4().hex).id
    repo = Path(__file__).resolve().parents[1]
    registry.install(parse_manifest(json.loads((repo / "addon.json").read_text())))
    registry.set_enabled("media-forge", True, grants=["jobs.write"])
    old = jobs.create_external("media-forge", "interrupted fixture", owner_user_id=owner)
    bearer = tokens.issue("media-forge", subject=str(owner), kind="service", actor_user_id=owner)
    headers = {"Authorization": f"Bearer {bearer}", "X-Control-Deck-Addon-ID": "media-forge"}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    unit = f"mf-terminal-http-{uuid.uuid4().hex[:10]}"
    package_unit: str | None = None
    subprocess.run(["systemd-run", "--user", "--collect", f"--unit={unit}", "--property=RuntimeMaxSec=90",
        f"--working-directory={args.host_repo}/backend", f"--setenv=PYTHONPATH={args.host_repo}/backend",
        sys.executable, str(Path(__file__).resolve()), "--serve", str(root), "--port", str(port)], check=True)
    try:
        host_url = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=host_url, timeout=5) as client:
            deadline = time.monotonic() + 25
            while True:
                try:
                    ready = client.get(f"/api/v1/addon-runtime/media-forge/jobs/{old.id}/control", headers=headers)
                    assert ready.status_code == 200 and ready.json()["status"] == "interrupted"
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            caller = client.post("/api/v1/addon-runtime/media-forge/jobs", json={"title": "fresh caller"}, headers=headers)
            active = client.post("/api/v1/addon-runtime/media-forge/jobs", json={"title": "active target"}, headers=headers)
            assert caller.status_code == active.status_code == 201
            value = {"core_data": str(root / "core"), "host_url": host_url,
                "authorization": f"Bearer {caller.json()['access_token']}", "targets": [
                    {"id": old.id, "payload": {"status": "failed", "error": "service_restarted"}},
                    {"id": active.json()["job"]["id"], "payload": {"status": "succeeded", "result": {"fixture": True}}}]}
            observations = []
            for mode in ("seed", "consume", "consume"):
                result = subprocess.run([str(args.core_python), str(Path(__file__).resolve()), "--core-mode", mode],
                    input=json.dumps(value), text=True, capture_output=True, timeout=30,
                    env={**os.environ, "PYTHONPATH": os.pathsep.join((str(repo / "backend"), str(repo)))})
                if result.returncode:
                    detail = result.stderr.replace(value["authorization"], "[redacted]").replace(
                        value["authorization"].removeprefix("Bearer "), "[redacted]")
                    raise RuntimeError(f"core {mode} failed: {detail[-3000:]}")
                observed = json.loads(result.stdout)
                observations.append({"mode": mode, **observed})
                if mode == "seed":
                    value.update(observed)
                    if args.package_executable:
                        with socket.socket() as sock:
                            sock.bind(("127.0.0.1", 0))
                            package_port = sock.getsockname()[1]
                        package_unit = f"{unit}-core"
                        subprocess.run(["systemd-run", "--user", "--collect", f"--unit={package_unit}",
                            "--property=RuntimeMaxSec=60",
                            f"--setenv=CONTROL_DECK_FEATURE_DATA_DIR={root}/feature",
                            f"--setenv=CONTROL_DECK_SHARED_CACHE_DIR={root}/cache",
                            f"--setenv=MEDIA_FORGE_DATA_DIR={root}/core",
                            f"--setenv=MEDIA_FORGE_CONTROLDECK_URL={host_url}",
                            f"--setenv=MEDIA_FORGE_PORT={package_port}",
                            str(args.package_executable.resolve(strict=True)), "serve"], check=True)
                        package_url = f"http://127.0.0.1:{package_port}"
                        deadline = time.monotonic() + 25
                        while True:
                            try:
                                health = client.get(f"{package_url}/health")
                                assert health.status_code == 200
                                break
                            except httpx.ConnectError:
                                if time.monotonic() >= deadline:
                                    raise
                                time.sleep(0.1)
                        package_headers = {"Authorization": value["authorization"], "X-Control-Deck-Addon-ID": "media-forge"}
                        projections = []
                        for job_id in value["local_ids"]:
                            response = client.post(f"{package_url}/addon/v1/agent/job/status",
                                json={"input": {"job_id": job_id}}, headers=package_headers)
                            assert response.status_code == 200, response.status_code
                            projections.append(response.json())
                        assert [item["host_terminal_sent"] for item in projections] == [False, True]
                        cancel = client.post(f"{package_url}/addon/v1/agent/job/cancel",
                            json={"input": {"job_id": value["local_ids"][0]}}, headers=package_headers)
                        assert cancel.status_code == 200 and cancel.json()["status"] == "failed"
                        observations.append({"mode": "packaged_agent_http", "projections": projections,
                                             "terminal_cancel": cancel.json(), "health": health.json()})
                        subprocess.run(["systemctl", "--user", "stop", package_unit], check=True)
                        package_unit = None
            assert jobs._db_get(old.id)["status"] == "interrupted"
            assert jobs._db_get(active.json()["job"]["id"])["status"] == "succeeded"
            (root / "observations.json").write_text(json.dumps(observations, indent=2) + "\n")
            print(json.dumps({"evidence": str(root / "observations.json"), "core_processes": 3,
                "terminal_sent": [False, True], "host_states": ["interrupted", "succeeded"], "local_jobs": 2}))
    finally:
        if package_unit is not None:
            subprocess.run(["systemctl", "--user", "stop", package_unit], check=True)
        subprocess.run(["systemctl", "--user", "stop", unit], check=True)


if __name__ == "__main__":
    main()
