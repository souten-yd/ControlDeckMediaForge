"""Owned-worker rollback of a proven unpublished fresh install/update.

Never remove runtime data here. A promoted but unregistered candidate is moved
back to its operation staging directory before the failure outcome is committed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

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
