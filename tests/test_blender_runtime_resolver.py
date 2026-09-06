from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mediaforge.blender_runtime import (
    G8_RUNTIME_ID,
    BlenderRuntimeRegistryError,
    BlenderRuntimeResolver,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "config/blender-runtime.json").read_text(encoding="utf-8"))


def ready_runtime(root: Path) -> None:
    executable = root / "install/blender"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    executable.chmod(0o700)
    (root / ".runtime.json").write_text(
        json.dumps({
            "schema_version": 1,
            "version": MANIFEST["version"],
            "archive_sha256": MANIFEST["archive_sha256"],
            "executable": "blender",
        }),
        encoding="utf-8",
    )


def resolver(tmp_path: Path, legacy: Path) -> BlenderRuntimeResolver:
    return BlenderRuntimeResolver(
        registry_path=tmp_path / "data/runtime-state/blender-runtimes.json",
        managed_root=tmp_path / "managed",
        legacy_root=legacy,
        manifest_path=ROOT / "config/blender-runtime.json",
        trusted_worker=ROOT / "worker_packs/blender/compile_asset.py",
    )


def test_ready_legacy_runtime_is_registered_without_persisting_its_path(tmp_path: Path) -> None:
    legacy = tmp_path / "outside-managed/legacy"
    ready_runtime(legacy)
    runtimes = resolver(tmp_path, legacy)

    assert runtimes.register_legacy() is True
    selected = runtimes.resolve_g8()
    assert selected is not None
    assert selected.runtime_id == G8_RUNTIME_ID
    assert selected.root == legacy.resolve()
    registry = runtimes.registry_path
    serialized = registry.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized
    assert json.loads(serialized)["active_runtime_id"] == G8_RUNTIME_ID
    assert os.stat(registry).st_mode & 0o777 == 0o600

    status = runtimes.status()
    assert status["state"] == "ready"
    assert status["g8_runtime_id"] == G8_RUNTIME_ID
    assert status["runtimes"][0]["ownership"] == "legacy"
    assert all(status["runtimes"][0]["checks"].values())
    assert str(tmp_path) not in json.dumps(status)


def test_missing_or_damaged_legacy_runtime_fails_closed(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    runtimes = resolver(tmp_path, legacy)
    assert runtimes.register_legacy() is False
    assert runtimes.status()["state"] == "missing"
    assert runtimes.resolve_g8() is None

    ready_runtime(legacy)
    assert runtimes.register_legacy() is True
    (legacy / ".runtime.json").write_text("{}", encoding="utf-8")
    status = runtimes.status()
    assert status["state"] == "damaged"
    assert status["runtimes"][0]["state"] == "damaged"
    assert status["runtimes"][0]["checks"]["stamp"] is False


def test_registry_rejects_managed_path_escape_and_symlink(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    runtimes = resolver(tmp_path, legacy)
    runtimes.registry_path.parent.mkdir(parents=True)
    runtimes.registry_path.write_text(json.dumps({
        "schema_version": 1,
        "active_runtime_id": "managed-blender",
        "runtimes": [{
            "runtime_id": "managed-blender",
            "version": "4.5.9",
            "ownership": "managed",
            "location": "../escape",
            "archive_sha256": MANIFEST["archive_sha256"],
        }],
    }), encoding="utf-8")
    assert runtimes.status()["state"] == "invalid"
    assert runtimes.resolve_g8() is None

    runtimes.registry_path.unlink()
    target = tmp_path / "registry-target.json"
    target.write_text("{}", encoding="utf-8")
    runtimes.registry_path.symlink_to(target)
    assert runtimes.status()["state"] == "invalid"


def test_managed_runtime_is_resolved_inside_the_managed_root(tmp_path: Path) -> None:
    legacy = tmp_path / "missing-legacy"
    runtimes = resolver(tmp_path, legacy)
    managed = runtimes.managed_root / "blender-4.5.9-linux-x86_64"
    ready_runtime(managed)
    runtimes.registry_path.parent.mkdir(parents=True)
    runtimes.registry_path.write_text(json.dumps({
        "schema_version": 1,
        "active_runtime_id": "managed-blender-4.5.9",
        "runtimes": [{
            "runtime_id": "managed-blender-4.5.9",
            "version": "4.5.9",
            "ownership": "managed",
            "location": "blender-4.5.9-linux-x86_64",
            "archive_sha256": MANIFEST["archive_sha256"],
        }],
    }), encoding="utf-8")

    selected = runtimes.resolve_g8()
    assert selected is not None
    assert selected.ownership == "managed"
    assert selected.root == managed.resolve()
    assert runtimes.status()["runtimes"][0]["removable"] is True


def test_managed_runtime_symlink_fails_closed_without_breaking_capability(tmp_path: Path) -> None:
    runtimes = resolver(tmp_path, tmp_path / "missing-legacy")
    outside = tmp_path / "outside"
    ready_runtime(outside)
    runtimes.managed_root.mkdir(parents=True)
    (runtimes.managed_root / "blender-4.5.9-linux-x86_64").symlink_to(outside)
    runtimes.registry_path.parent.mkdir(parents=True)
    runtimes.registry_path.write_text(json.dumps({
        "schema_version": 1,
        "active_runtime_id": "managed-blender-4.5.9",
        "runtimes": [{
            "runtime_id": "managed-blender-4.5.9",
            "version": "4.5.9",
            "ownership": "managed",
            "location": "blender-4.5.9-linux-x86_64",
            "archive_sha256": MANIFEST["archive_sha256"],
        }],
    }), encoding="utf-8")

    assert runtimes.resolve_g8() is None
    assert runtimes.status()["state"] == "invalid"


def test_workspace_status_is_read_only_and_never_returns_server_paths(client) -> None:
    response = client.get("/workspace-api/blender/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "media-forge.blender-runtime-status@1"
    assert payload["state"] == "ready"
    assert len(payload["fingerprint"]) == 64
    serialized = json.dumps(payload)
    assert "/tmp" not in serialized and "/home" not in serialized and "path" not in serialized


def test_unregister_never_deletes_or_detaches_the_external_legacy_runtime(tmp_path: Path) -> None:
    legacy = tmp_path / "external-blender"
    ready_runtime(legacy)
    runtimes = resolver(tmp_path, legacy)
    assert runtimes.register_legacy() is True
    with pytest.raises(BlenderRuntimeRegistryError, match="external"):
        runtimes.unregister_managed(G8_RUNTIME_ID)
    assert (legacy / "install/blender").is_file()
    assert runtimes.resolve_g8() is not None


def legacy_and_managed(tmp_path: Path) -> tuple[BlenderRuntimeResolver, Path]:
    legacy = tmp_path / "external-blender"
    ready_runtime(legacy)
    runtimes = resolver(tmp_path, legacy)
    assert runtimes.register_legacy()
    managed_id = "blender-4.5.9-linux-x64"
    ready_runtime(runtimes.managed_root / managed_id)
    runtimes.register_managed(runtime_id=managed_id, version="4.5.9", location=managed_id,
        archive_sha256=MANIFEST["archive_sha256"])
    runtimes.activate(managed_id)
    return runtimes, legacy


def test_external_detach_survives_status_and_restart_and_can_be_explicitly_reversed(tmp_path: Path) -> None:
    runtimes, legacy = legacy_and_managed(tmp_path)
    before = {str(p.relative_to(legacy)): p.read_bytes() for p in legacy.rglob("*") if p.is_file()}
    assert runtimes.unregister_legacy()
    assert not runtimes.unregister_legacy()
    registry_before = runtimes.registry_path.read_bytes()
    restarted = resolver(tmp_path, legacy)
    for _ in range(3):
        status = restarted.status()
        assert status["legacy_registration_disabled"] is True
        assert all(r["runtime_id"] != G8_RUNTIME_ID for r in status["runtimes"])
        assert restarted.resolve_registered(G8_RUNTIME_ID) is None
        assert restarted.resolve_g8().ownership == "managed"
        assert not restarted.register_legacy()
    assert runtimes.registry_path.read_bytes() == registry_before
    assert restarted.register_legacy(explicit=True)
    assert restarted.status()["legacy_registration_disabled"] is False
    assert restarted.resolve_registered(G8_RUNTIME_ID) is not None
    assert restarted.resolve_active().ownership == "managed"
    assert before == {str(p.relative_to(legacy)): p.read_bytes() for p in legacy.rglob("*") if p.is_file()}


def test_external_detach_rejects_active_and_live_references(tmp_path: Path) -> None:
    runtimes, _ = legacy_and_managed(tmp_path)
    with runtimes.runtime_reference(G8_RUNTIME_ID):
        before = runtimes.registry_path.read_bytes()
        with pytest.raises(BlenderRuntimeRegistryError, match="live references"):
            runtimes.unregister_legacy()
        assert runtimes.registry_path.read_bytes() == before
    runtimes.activate(G8_RUNTIME_ID)
    with pytest.raises(BlenderRuntimeRegistryError, match="active"):
        runtimes.unregister_legacy()
    assert not runtimes.status()["legacy_registration_disabled"]


def test_external_reattach_failure_preserves_suppression(tmp_path: Path) -> None:
    runtimes, legacy = legacy_and_managed(tmp_path)
    runtimes.unregister_legacy()
    before = runtimes.registry_path.read_bytes()
    (legacy / ".runtime.json").write_text("{}", encoding="utf-8")
    assert not runtimes.register_legacy(explicit=True)
    assert runtimes.registry_path.read_bytes() == before
    assert runtimes.status()["legacy_registration_disabled"]


def test_external_detach_atomic_write_failure_preserves_old_registration(tmp_path: Path, monkeypatch) -> None:
    runtimes, _ = legacy_and_managed(tmp_path)
    before = runtimes.registry_path.read_bytes()
    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("injected registry replacement failure")
    monkeypatch.setattr("mediaforge.blender_runtime.os.replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        runtimes.unregister_legacy()
    assert runtimes.registry_path.read_bytes() == before
    assert runtimes.resolve_registered(G8_RUNTIME_ID) is not None
    assert not list(runtimes.registry_path.parent.glob(".blender-runtimes-*.tmp"))


@pytest.mark.parametrize("policy", [1, "true", [], None])
def test_external_policy_rejects_non_boolean_values(tmp_path: Path, policy: object) -> None:
    runtimes, _ = legacy_and_managed(tmp_path)
    value = json.loads(runtimes.registry_path.read_text())
    value["legacy_registration_disabled"] = policy
    runtimes.registry_path.write_text(json.dumps(value))
    assert runtimes.status()["state"] == "invalid"


def test_external_detach_does_not_follow_registry_lock_symlink(tmp_path: Path) -> None:
    runtimes, _ = legacy_and_managed(tmp_path)
    lock = runtimes.registry_path.with_suffix(".json.lock")
    lock.unlink()
    outside = tmp_path / "untouched"
    outside.write_text("do not change")
    lock.symlink_to(outside)
    with pytest.raises(BlenderRuntimeRegistryError, match="symlink"):
        runtimes.unregister_legacy()
    assert outside.read_text() == "do not change"
