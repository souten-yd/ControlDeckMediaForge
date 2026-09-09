"""Real Blender with a delayed Host fixture; isolated data/registry only.

This is domain/process acceptance, not installed Host, HTTP or Settings acceptance.
Existing runtime roots are read-only. No download, repair or runtime deletion.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any

from mediaforge.blender_runtime import BlenderRuntimeRegistryError, BlenderRuntimeResolver, G8_RUNTIME_ID
from mediaforge.config import REPOSITORY_ROOT
from mediaforge.host.client import HostIdentity
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_recipes import SceneCreateRequest
from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.store import Store
from scripts.blender_runtime import load_spec


class DelayedHost:
    """Explicit credential/control fixture; never connects to the installed Host."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.proceed = asyncio.Event()

    async def create_or_attach_job(self, identity: HostIdentity, **kwargs: Any) -> dict[str, Any]:
        self.entered.set()
        await self.proceed.wait()
        return {"created": True, "job": {"id": "pin-fixture-child"},
                "access_token": "fixture-only", "expires_at": int(time.time()) + 600}

    async def update_job(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}

    async def job_control(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"cancel_requested": False}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


async def execute(store: Store, workspace: SceneWorkspace) -> dict[str, Any]:
    host = DelayedHost()
    manager = SceneRecipeJobManager(store, workspace, host)  # type: ignore[arg-type]
    runtime_id = workspace.resolver.resolve_active().runtime_id
    identity = HostIdentity(authorization="Bearer fixture", addon_id="media-forge",
        subject="job:pin-fixture-parent", actor_subject="user:7",
        expires_at=int(time.time()) + 600, granted_capabilities=frozenset({"jobs.write"}))
    value = SceneCreateRequest.model_validate({"name": "Admission pin acceptance cube", "recipe": {
        "operations": [{"type": "primitive.add", "object_id": "cube", "primitive": "cube",
                        "name": "Cube", "dimensions": [1, 1, 1]}]}})
    # Explicit acquisition-delay fixture. The resolver/runtime are real; only
    # the return from acquisition is held while three cancellations arrive.
    acquired, release = threading.Event(), threading.Event()
    original_acquire = workspace.acquire_recipe_runtime

    def paused_acquire(*args: Any, **kwargs: Any) -> Any:
        held = original_acquire(*args, **kwargs)
        acquired.set()
        if not release.wait(10):
            held[0].close()
            raise TimeoutError("acquisition fixture was not released")
        return held

    workspace.acquire_recipe_runtime = paused_acquire
    canceled = asyncio.create_task(manager.submit(value, identity))
    try:
        assert await asyncio.to_thread(acquired.wait, 5)
        for _ in range(3):
            canceled.cancel()
            await asyncio.sleep(0.01)
        assert not canceled.done()
        assert workspace.resolver.live_reference_count(runtime_id) == 1
    except BaseException:
        canceled.cancel()
        raise
    finally:
        release.set()
        outcome = await asyncio.gather(canceled, return_exceptions=True)
        workspace.acquire_recipe_runtime = original_acquire
    assert isinstance(outcome[0], asyncio.CancelledError)
    assert workspace.resolver.live_reference_count(runtime_id) == 0
    assert not manager._admissions and not host.entered.is_set()
    await manager._execution_guard.acquire()
    submission = asyncio.create_task(manager.submit(value, identity))
    try:
        await asyncio.wait_for(host.entered.wait(), 5)
        await asyncio.to_thread(workspace.resolver.activate, G8_RUNTIME_ID)
        observations: dict[str, Any] = {"runtime_id": runtime_id,
            "repeated_admission_cancel": {"count": 3, "cleanup_references": 0, "host_called": False},
            "host_wait_references": workspace.resolver.live_reference_count(runtime_id)}
        assert observations["host_wait_references"] == 1
        try:
            await asyncio.to_thread(workspace.resolver.unregister_managed, runtime_id)
        except BlenderRuntimeRegistryError as exc:
            observations["admission_unregister_rejection"] = str(exc)
            assert "live references" in str(exc)
        else:
            raise AssertionError("admission pin did not reject unregistration")
        host.proceed.set()
        job, record = await asyncio.wait_for(submission, 5)
        assert record.runtime_id == runtime_id
        observations["queue_references"] = workspace.resolver.live_reference_count(runtime_id)
        assert observations["queue_references"] == 1
        manager._execution_guard.release()
        await manager.wait_cleanup(job.id, timeout=60)
        observations["job"] = manager.projection(job.id, "user:7")
        assert observations["job"]["status"] == "succeeded", observations["job"]
        observations["cleanup_references"] = workspace.resolver.live_reference_count(runtime_id)
        assert observations["cleanup_references"] == 0
        observations["assets"] = await asyncio.to_thread(lambda: [
            {"id": asset_id, "size_bytes": store.asset_path(asset_id).stat().st_size,
             "sha256": digest(store.asset_path(asset_id))}
            for asset_id in observations["job"]["asset_ids"]])
        assert len(observations["assets"]) == 2
        return observations
    finally:
        if not submission.done():
            submission.cancel()
        await asyncio.gather(submission, return_exceptions=True)
        await manager.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--managed-root", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    started = time.monotonic()
    spec = load_spec(REPOSITORY_ROOT / "config/blender-runtime.json")
    runtime_id = "blender-4.5.9-linux-x64"
    runtimes = BlenderRuntimeResolver(registry_path=args.evidence_dir / "registry/blender-runtimes.json",
        managed_root=args.managed_root, legacy_root=args.legacy_root,
        manifest_path=REPOSITORY_ROOT / "config/blender-runtime.json",
        trusted_worker=REPOSITORY_ROOT / "worker_packs/blender/compile_asset.py")
    assert runtimes.register_legacy()
    runtimes.register_managed(runtime_id=runtime_id, version=spec.version, location=runtime_id,
                              archive_sha256=spec.archive_sha256)
    runtimes.activate(runtime_id)
    executable = runtimes.resolve_active().executable
    before = digest(executable)
    store = Store(args.evidence_dir / "data")
    store.initialize()
    workspace = SceneWorkspace(store, runtimes, REPOSITORY_ROOT / "worker_packs/blender/scene_document.py",
        recipe_worker=REPOSITORY_ROOT / "worker_packs/blender/scene_recipe.py")
    workspace.initialize()
    evidence: dict[str, Any] = {"mode": "source_real_blender_delayed_host_fixture"}
    try:
        evidence.update(asyncio.run(execute(store, workspace)))
        assert digest(executable) == before
        evidence.update(passed=True, blender_executable_sha256=before,
            not_tested=["installed Host", "HTTP/Settings", "confirmed history removal", "GUI durable refs"])
    finally:
        evidence["elapsed_sec"] = round(time.monotonic() - started, 3)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
