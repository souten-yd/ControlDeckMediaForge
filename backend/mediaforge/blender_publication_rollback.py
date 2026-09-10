"""Owned-worker rollback of a proven unpublished install/update or repair.

Never remove runtime data here. A promoted but unregistered candidate is moved
back to its operation staging directory before the failure outcome is committed.
Repair additionally matches the original directory identity before restoring it.
"""
from __future__ import annotations

import os
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.blender_runtime import RuntimeSpec

from .blender_publication import PublicationIdentity
from .blender_publication_generation import read_generation
from .blender_publication_recovery import BlenderPublicationRecovery
from .blender_runtime import BlenderRuntimeRegistryError, BlenderRuntimeResolver
from .paths import contained
from .store import Store


class BlenderPublicationRollback:
    def __init__(self, store: Store, resolver: BlenderRuntimeResolver) -> None:
        self.store = store
        self.resolver = resolver

    def rollback(self, operation_id: str) -> dict[str, Any]:
        publication = self.store.blender_publication(operation_id)
        if publication is None or publication.phase != "recovery_required":
            raise ValueError("Publication is not awaiting recovery")
        identity = publication.identity
        if identity.action == "repair":
            return self._rollback_repair(operation_id, identity)
        if (identity.action not in {"install", "update"} or identity.recovered_directory
                or identity.previous_registration_sha256 is not None or identity.generation is None):
            return {"status": "recovery_required", "reason": "rollback_identity_unproven"}
        with self.resolver.managed_publication_guard():
            try:
                registry = self.resolver._read_registry()
                if (any(row["runtime_id"] == identity.runtime_id for row in registry["runtimes"])
                        or registry["active_runtime_id"] != identity.previous_active_runtime_id):
                    return {"status": "recovery_required", "reason": "rollback_registry_changed"}
                if (self.resolver.live_reference_count(identity.runtime_id)
                        or self.store.scene_runtime_reference_count(identity.runtime_id)
                        or any(self.store.active_scene_runtime_references(identity.runtime_id).values())):
                    return {"status": "recovery_required", "reason": "rollback_runtime_in_use"}
                spec = self.resolver._catalog_specs()[identity.runtime_id]
                if spec.version != identity.version or spec.archive_sha256 != identity.archive_sha256:
                    return {"status": "recovery_required", "reason": "rollback_catalog_changed"}
                root = self.resolver.managed_root
                raw_destination = root / identity.runtime_id
                raw_candidate = root / ".staging" / operation_id / "candidate"
                if raw_destination.is_symlink() or raw_candidate.is_symlink():
                    return {"status": "recovery_required", "reason": "rollback_unsafe_path"}
                destination = contained(root, raw_destination)
                candidate = contained(root, raw_candidate)
                if destination != raw_destination or candidate != raw_candidate:
                    return {"status": "recovery_required", "reason": "rollback_unsafe_path"}
                if destination.exists() == candidate.exists():
                    return {"status": "recovery_required", "reason": "rollback_ambiguous_candidates"}
                source = destination if destination.exists() else candidate
                if (not source.is_dir() or read_generation(root, source) != identity.generation
                        or BlenderPublicationRecovery.executable_digest(source, source / "install" / spec.executable)
                        != identity.executable_sha256):
                    return {"status": "recovery_required", "reason": "rollback_candidate_mismatch"}
                if source == destination:
                    candidate.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    os.replace(destination, candidate)
                    for parent in (destination.parent, candidate.parent):
                        descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                        try:
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                # Check again after rename. On any ambiguity retain all bytes.
                if (destination.exists() or destination.is_symlink()
                        or read_generation(root, candidate) != identity.generation
                        or BlenderPublicationRecovery.executable_digest(candidate, candidate / "install" / spec.executable)
                        != identity.executable_sha256):
                    return {"status": "recovery_required", "reason": "rollback_candidate_changed"}
            except (BlenderRuntimeRegistryError, OSError, ValueError, KeyError):
                return {"status": "recovery_required", "reason": "rollback_verification_failed"}
            result = self.store.rollback_blender_publication(operation_id, identity)
            return {"status": "rolled_back", "operation_id": result.id}

    @staticmethod
    def previous_matches(identity: PublicationIdentity, root: Path, spec: RuntimeSpec) -> bool:
        """Match the original directory, including an explicitly missing exe."""
        if root.is_symlink() or not root.is_dir() or identity.previous_root_inode is None:
            return False
        info = root.stat()
        if (info.st_dev, info.st_ino) != (identity.previous_root_device, identity.previous_root_inode):
            return False
        if read_generation(root.parent, root) != identity.previous_generation:
            return False
        executable = contained(root, root / "install" / spec.executable)
        if identity.previous_executable_missing:
            return not executable.exists() and not (root / "install" / spec.executable).is_symlink()
        return BlenderPublicationRecovery.executable_digest(root, executable) == identity.previous_executable_sha256

    @staticmethod
    def _sync_parents(*paths: Path) -> None:
        for path in set(paths):
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _rollback_repair(self, operation_id: str, identity: PublicationIdentity) -> dict[str, Any]:
        if (identity.previous_root_inode is None or identity.previous_registration_sha256 is None
                or identity.generation is None):
            return {"status": "recovery_required", "reason": "repair_rollback_identity_unproven"}
        with self.resolver.managed_publication_guard():
            try:
                registry = self.resolver._read_registry()
                row = next((item for item in registry["runtimes"] if item["runtime_id"] == identity.runtime_id), None)
                digest = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                if digest != identity.previous_registration_sha256 or registry["active_runtime_id"] != identity.previous_active_runtime_id:
                    return {"status": "recovery_required", "reason": "repair_rollback_registry_changed"}
                if (self.resolver.live_reference_count(identity.runtime_id)
                        or any(self.store.active_scene_runtime_references(identity.runtime_id).values())):
                    return {"status": "recovery_required", "reason": "rollback_runtime_in_use"}
                spec = self.resolver._catalog_specs()[identity.runtime_id]
                if spec.version != identity.version or spec.archive_sha256 != identity.archive_sha256:
                    return {"status": "recovery_required", "reason": "rollback_catalog_changed"}
                root = self.resolver.managed_root
                destination = root / identity.runtime_id
                candidate = root / ".staging" / operation_id / "candidate"
                previous = root / ".staging" / f"previous-{operation_id}"
                for path in (destination, candidate, previous):
                    if path.is_symlink() or contained(root, path) != path:
                        return {"status": "recovery_required", "reason": "rollback_unsafe_path"}
                old = previous if previous.exists() else destination
                if not self.previous_matches(identity, old, spec):
                    return {"status": "recovery_required", "reason": "repair_previous_mismatch"}
                if old == previous and destination.exists() and candidate.exists():
                    return {"status": "recovery_required", "reason": "rollback_ambiguous_candidates"}
                new = candidate if candidate.exists() else destination
                if (new == old or read_generation(root, new) != identity.generation
                        or BlenderPublicationRecovery.executable_digest(new, new / "install" / spec.executable)
                        != identity.executable_sha256):
                    return {"status": "recovery_required", "reason": "rollback_candidate_mismatch"}
                if new == destination:
                    candidate.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    os.replace(destination, candidate)
                    self._sync_parents(destination.parent, candidate.parent)
                if old == previous:
                    if destination.exists() or destination.is_symlink():
                        return {"status": "recovery_required", "reason": "rollback_destination_changed"}
                    os.replace(previous, destination)
                    self._sync_parents(previous.parent, destination.parent)
                if (not self.previous_matches(identity, destination, spec)
                        or read_generation(root, candidate) != identity.generation
                        or BlenderPublicationRecovery.executable_digest(candidate, candidate / "install" / spec.executable)
                        != identity.executable_sha256):
                    return {"status": "recovery_required", "reason": "rollback_candidate_changed"}
            except (BlenderRuntimeRegistryError, OSError, ValueError, KeyError):
                return {"status": "recovery_required", "reason": "repair_rollback_verification_failed"}
            result = self.store.rollback_blender_publication(operation_id, identity)
            return {"status": "rolled_back", "operation_id": result.id}
