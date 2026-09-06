"""Real CPU Blender retry after default-version change, isolated state only.

Host credential/control is an explicit fixture. The first attempt is canceled
while queued; the retry runs real Blender after manager recreation. No installed
service/registry changes, runtime download/deletion or global credentials.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import time
from typing import Any

from mediaforge.blender_runtime import BlenderRuntimeResolver
from mediaforge.config import REPOSITORY_ROOT
from mediaforge.host.client import HostIdentity
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_recipes import SceneCreateRequest
from mediaforge.scene_workspace import SceneWorkspace
from mediaforge.store import Store


async def execute(store: Store, workspace: SceneWorkspace, host: Any) -> dict:
    host.proceed.set()
    identity = HostIdentity(authorization="Bearer fixture-only", addon_id="media-forge",
        subject="job:retry-fixture-parent", actor_subject="user:7", expires_at=int(time.time()) + 600,
        granted_capabilities=frozenset({"jobs.write"}))
    request = SceneCreateRequest.model_validate({"name": "Retry pin acceptance cube", "recipe": {"operations": [
        {"type": "primitive.add", "object_id": "cube", "name": "Cube", "primitive": "cube", "dimensions": [1, 1, 1]}]}})
    manager = SceneRecipeJobManager(store, workspace, host)
    await manager._execution_guard.acquire()
    try:
        first, original = await manager.submit(request, identity)
        await manager.cancel(first.id, "user:7")
        await manager.wait_cleanup(first.id)
        canceled = await asyncio.to_thread(manager.projection, first.id, "user:7")
        assert canceled["status"] == "canceled" and not canceled["asset_ids"]
    finally:
        manager._execution_guard.release()
        await manager.stop()
    await asyncio.to_thread(workspace.resolver.activate, "blender-4.5.13-linux-x64")
    manager = SceneRecipeJobManager(store, workspace, host)
    try:
        retry, record = await manager.submit(request.model_copy(update={"retry_job_id": first.id}),
                                              identity, retry_of=first.id)
        await manager.wait_cleanup(retry.id, timeout=60)
        result = await asyncio.to_thread(manager.projection, retry.id, "user:7")
        assert result["status"] == "succeeded", result["error"]
        assert record.runtime_id == original.runtime_id == "blender-4.5.9-linux-x64"
        assert result["result"]["revision"]["runtime_version"] == "4.5.9"
        assert result["input_sha256"] == canceled["input_sha256"]
        assert result["retry_of"] == first.id
        assert workspace.resolver.live_reference_count(original.runtime_id) == 0
        return {"first": canceled, "retry": result, "retry_uses_original_version": True,
                "new_default_version": "4.5.13", "released_runtime_references": True}
    finally:
        await manager.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--managed-root", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    started = time.monotonic()
    resolver = BlenderRuntimeResolver(registry_path=args.evidence_dir / "registry/blender-runtimes.json",
        managed_root=args.managed_root, legacy_root=args.evidence_dir / "absent-legacy",
        manifest_path=REPOSITORY_ROOT / "config/blender-runtime.json",
        catalog_path=REPOSITORY_ROOT / "config/blender-runtime-catalog.json",
        trusted_worker=REPOSITORY_ROOT / "worker_packs/blender/compile_asset.py")
    catalog = json.loads((REPOSITORY_ROOT / "config/blender-runtime-catalog.json").read_text())
    for row in catalog["runtimes"]:
        resolver.register_managed(runtime_id=row["runtime_id"], version=row["spec"]["version"],
            location=row["runtime_id"], archive_sha256=row["spec"]["archive_sha256"])
    resolver.activate("blender-4.5.9-linux-x64")
    store = Store(args.evidence_dir / "data")
    store.initialize()
    workspace = SceneWorkspace(store, resolver, REPOSITORY_ROOT / "worker_packs/blender/scene_document.py",
                               recipe_worker=REPOSITORY_ROOT / "worker_packs/blender/scene_recipe.py")
    workspace.initialize()
    spec = importlib.util.spec_from_file_location("pin_fixture", Path(__file__).with_name("3ds_recipe_runtime_pin_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict = {"mode": "source_real_blender_host_fixture", "not_tested": [
        "installed Host", "HTTP/browser", "failed material reuse", "signed release"]}
    try:
        evidence.update(asyncio.run(execute(store, workspace, helpers.DelayedHost())))
        assets = []
        for asset_id in evidence["retry"]["asset_ids"]:
            metadata = store.get_asset(asset_id)
            path = store.asset_path(asset_id)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == metadata.sha256 and path.stat().st_size == metadata.size_bytes
            assets.append({"id": asset_id, "sha256": digest, "size_bytes": metadata.size_bytes})
        evidence.update(assets=assets, passed=True)
    finally:
        evidence["elapsed_sec"] = round(time.monotonic() - started, 3)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
