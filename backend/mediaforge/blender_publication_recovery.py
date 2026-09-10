"""Verify an interrupted installed runtime before committing its journal outcome.

All methods are synchronous and must run in an owned worker thread. No runtime
files or registry entries are changed. Ambiguous identities remain quarantined.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import stat
from typing import Any

from scripts.blender_runtime import BlenderRuntimeError, preflight

from .blender_runtime import BlenderRuntimeRegistryError, BlenderRuntimeResolver
from .paths import contained
from .store import Store


class BlenderPublicationRecovery:
    def __init__(self, store: Store, resolver: BlenderRuntimeResolver, preflight_script: Path) -> None:
        self.store = store
        self.resolver = resolver
        self.preflight_script = preflight_script

    @staticmethod
    def executable_digest(root: Path, executable: Path) -> str:
        executable = contained(root, executable)
        descriptor = os.open(executable, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 2 * 1024**3:
                raise ValueError("Invalid executable file")
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def recover(self, operation_id: str) -> dict[str, Any]:
        publication = self.store.blender_publication(operation_id)
        if publication is None or publication.phase != "recovery_required":
            raise ValueError("Publication is not awaiting recovery")
        identity = publication.identity
        # A same-version repair can have identical old/new executable hashes.
        # Without generation evidence it is unsafe to claim the repair happened.
        if identity.action == "repair":
            return {"status": "recovery_required", "reason": "repair_generation_unproven"}
        with self.resolver.removal_guard():
            lock_path = self.resolver.registry_path.with_suffix(self.resolver.registry_path.suffix + ".lock")
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            with os.fdopen(descriptor, "r+") as lock:
                if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                    raise ValueError("Invalid registry lock")
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    registry = self.resolver._read_registry()
                    row = next((item for item in registry["runtimes"] if item["runtime_id"] == identity.runtime_id), None)
                    expected = {"runtime_id": identity.runtime_id, "version": identity.version,
                                "ownership": "managed", "location": identity.runtime_id,
                                "archive_sha256": identity.archive_sha256}
                    active = (identity.runtime_id if identity.action == "update"
                              else identity.previous_active_runtime_id or identity.runtime_id)
                    if row != expected or registry["active_runtime_id"] != active:
                        return {"status": "recovery_required", "reason": "registry_identity_mismatch"}
                    runtime = self.resolver._resolved(row)
                    # Validate intermediate directory links before readiness
                    # checks touch the executable, not only before hashing it.
                    contained(runtime.root, runtime.executable)
                    if not self.resolver._ready(runtime):
                        return {"status": "recovery_required", "reason": "runtime_not_verified"}
                    if self.executable_digest(runtime.root, runtime.executable) != identity.executable_sha256:
                        return {"status": "recovery_required", "reason": "executable_identity_mismatch"}
                    spec = self.resolver._catalog_specs()[identity.runtime_id]
                    facts = preflight(runtime.executable, self.preflight_script, spec)
                    if (not self.resolver._ready(runtime)
                            or self.executable_digest(runtime.root, runtime.executable) != identity.executable_sha256):
                        return {"status": "recovery_required", "reason": "executable_changed_during_probe"}
                except (BlenderRuntimeRegistryError, BlenderRuntimeError, OSError, ValueError, KeyError):
                    return {"status": "recovery_required", "reason": "verification_failed"}
                operation = self.store.recover_blender_publication(operation_id, identity, {
                    "runtime_id": identity.runtime_id, "version": identity.version,
                    "archive_sha256": identity.archive_sha256, "preflight": facts,
                    "publication_recovered": True,
                })
                return {"status": "committed", "operation_id": operation.id}
