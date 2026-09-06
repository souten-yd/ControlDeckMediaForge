"""Isolated registry / real Blender acceptance; no HTTP or Settings acceptance.

Only evidence-dir is written. Both existing acceptance-runtime roots are read
only here: no install, repair, removal, global settings or live registry writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from mediaforge.blender_runtime import BlenderRuntimeResolver, G8_RUNTIME_ID
from mediaforge.config import REPOSITORY_ROOT
from scripts.blender_runtime import load_spec, preflight


def inventory(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(root.rglob("*")):
        name = str(path.relative_to(root))
        if path.is_symlink():
            result[name] = {"link": str(path.readlink())}
        elif path.is_file():
            with path.open("rb") as stream:
                result[name] = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                                "size": path.stat().st_size, "mode": path.stat().st_mode}
        else:
            assert path.is_dir(), path
            result[name] = {"directory": True}
    assert "install/blender" in result and ".runtime.json" in result
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    started = time.monotonic()
    legacy = Path("/data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/runtimes/blender/blender-4.5.9-linux-x64")
    managed = Path("/data1tb/mf-long-setup-source-20260906/runtimes/blender")
    manifest = REPOSITORY_ROOT / "config/blender-runtime.json"
    spec = load_spec(manifest)
    before = inventory(legacy)
    evidence: dict[str, Any] = {"mode": "isolated_registry_real_blender", "external_before": before}

    def resolver() -> BlenderRuntimeResolver:
        return BlenderRuntimeResolver(registry_path=args.evidence_dir / "registry/blender-runtimes.json",
            managed_root=managed, legacy_root=legacy, manifest_path=manifest,
            trusted_worker=REPOSITORY_ROOT / "worker_packs/blender/compile_asset.py")

    try:
        runtimes = resolver()
        assert runtimes.register_legacy()
        registered = runtimes.resolve_registered(G8_RUNTIME_ID)
        assert registered is not None
        evidence["probe_before"] = preflight(registered.executable,
            REPOSITORY_ROOT / "worker_packs/blender/preflight.py", spec)
        managed_id = "blender-4.5.9-linux-x64"
        runtimes.register_managed(runtime_id=managed_id, version=spec.version,
            location=managed_id, archive_sha256=spec.archive_sha256)
        runtimes.activate(managed_id)
        assert runtimes.unregister_legacy()
        detached = resolver()
        evidence["detached_status"] = detached.status()
        assert evidence["detached_status"]["legacy_registration_disabled"]
        assert detached.resolve_registered(G8_RUNTIME_ID) is None
        assert not detached.register_legacy()
        assert detached.resolve_active().runtime_id == managed_id
        assert inventory(legacy) == before
        assert detached.register_legacy(explicit=True)
        evidence["reattached_status"] = resolver().status()
        assert not evidence["reattached_status"]["legacy_registration_disabled"]
        evidence["probe_after"] = preflight(legacy / "install/blender",
            REPOSITORY_ROOT / "worker_packs/blender/preflight.py", spec)
        assert inventory(legacy) == before
        evidence.update(passed=True, external_unchanged=True,
            not_tested=["Settings UI", "HTTP management", "project reference guard", "arbitrary external versions"])
    except Exception as exc:
        evidence.update(passed=False, error_type=type(exc).__name__, message=str(exc)[:300])
        raise
    finally:
        evidence["elapsed_sec"] = round(time.monotonic() - started, 3)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({key: value for key, value in evidence.items() if key != "external_before"}), flush=True)


if __name__ == "__main__":
    main()
