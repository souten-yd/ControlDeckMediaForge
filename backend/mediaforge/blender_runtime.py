"""Resolve versioned Blender runtimes without exposing server paths."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any

from scripts.blender_runtime import BlenderRuntimeError, RuntimeSpec, load_spec, validate_spec


REGISTRY_SCHEMA_VERSION = 1
STATUS_SCHEMA_VERSION = "media-forge.blender-runtime-status@1"
G8_RUNTIME_ID = "legacy-blender-4.5.9"
G8_MANAGED_RUNTIME_ID = "blender-4.5.9-linux-x64"
G8_VERSION = "4.5.9"
G8_PROFILE = "3d.project.glb"
RUNTIME_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BlenderRuntimeRegistryError(RuntimeError):
    code = "blender_runtime_registry_invalid"


@dataclass(frozen=True)
class ResolvedBlenderRuntime:
    runtime_id: str
    version: str
    ownership: str
    root: Path
    executable: Path
    manifest_path: Path
    trusted_worker: Path
    archive_sha256: str


class BlenderRuntimeResolver:
    """Read a bounded registry and select the fixed runtime required by G8."""

    def __init__(
        self,
        *,
        registry_path: Path,
        managed_root: Path,
        legacy_root: Path,
        manifest_path: Path,
        trusted_worker: Path,
        catalog_path: Path | None = None,
    ) -> None:
        self.registry_path = Path(os.path.abspath(registry_path))
        self.managed_root = managed_root.resolve()
        self.legacy_root = legacy_root.resolve()
        self.manifest_path = Path(os.path.abspath(manifest_path))
        self.trusted_worker = Path(os.path.abspath(trusted_worker))
        self.catalog_path = Path(os.path.abspath(catalog_path)) if catalog_path else None
        self._reference_guard = threading.RLock()
        self._live_references: dict[str, int] = {}

    def _manifest(self) -> dict[str, Any]:
        if self.manifest_path.is_symlink() or not self.manifest_path.is_file():
            raise BlenderRuntimeRegistryError("trusted Blender manifest is unavailable")
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderRuntimeRegistryError("trusted Blender manifest is invalid") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 1
            or value.get("version") != G8_VERSION
            or not isinstance(value.get("archive_sha256"), str)
            or not SHA256_PATTERN.fullmatch(value["archive_sha256"])
            or value.get("executable") != "blender"
        ):
            raise BlenderRuntimeRegistryError("trusted Blender manifest is invalid")
        return value

    def _catalog_specs(self) -> dict[str, RuntimeSpec]:
        legacy = self._manifest()
        try:
            fallback = load_spec(self.manifest_path)
        except BlenderRuntimeError as exc:
            raise BlenderRuntimeRegistryError("trusted Blender manifest is invalid") from exc
        if self.catalog_path is None:
            return {G8_RUNTIME_ID: fallback, G8_MANAGED_RUNTIME_ID: fallback}
        if (
            self.catalog_path.is_symlink()
            or not self.catalog_path.is_file()
            or self.catalog_path.stat().st_size > 128 * 1024
        ):
            raise BlenderRuntimeRegistryError("trusted Blender catalog is unavailable")
        try:
            value = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderRuntimeRegistryError("trusted Blender catalog is invalid") from exc
        if not isinstance(value, dict) or set(value) != {
            "schema_version", "base_runtime_id", "recommended_studio_runtime_id", "runtimes"
        } or value["schema_version"] != 1 or not isinstance(value["runtimes"], list):
            raise BlenderRuntimeRegistryError("trusted Blender catalog is invalid")
        if not 1 <= len(value["runtimes"]) <= 16:
            raise BlenderRuntimeRegistryError("trusted Blender catalog is invalid")
        specs: dict[str, RuntimeSpec] = {}
        try:
            for row in value["runtimes"]:
                if (
                    not isinstance(row, dict)
                    or set(row) != {"runtime_id", "spec"}
                    or not isinstance(row["runtime_id"], str)
                    or not RUNTIME_ID_PATTERN.fullmatch(row["runtime_id"])
                    or row["runtime_id"] in specs
                ):
                    raise BlenderRuntimeRegistryError("trusted Blender catalog is invalid")
                specs[row["runtime_id"]] = validate_spec(row["spec"])
        except BlenderRuntimeError as exc:
            raise BlenderRuntimeRegistryError("trusted Blender catalog is invalid") from exc
        base = value["base_runtime_id"]
        recommended = value["recommended_studio_runtime_id"]
        if (
            base not in specs
            or recommended not in specs
            or specs[base] != fallback
            or specs[base].archive_sha256 != legacy["archive_sha256"]
        ):
            raise BlenderRuntimeRegistryError("trusted Blender catalog is invalid")
        return specs

    @staticmethod
    def _empty_registry() -> dict[str, Any]:
        return {"schema_version": REGISTRY_SCHEMA_VERSION, "active_runtime_id": None, "runtimes": []}

    def _validated_registry(self, value: object) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {
            "schema_version", "active_runtime_id", "runtimes"
        }:
            raise BlenderRuntimeRegistryError("Blender runtime registry fields are invalid")
        if value["schema_version"] != REGISTRY_SCHEMA_VERSION:
            raise BlenderRuntimeRegistryError("Blender runtime registry version is unsupported")
        rows = value["runtimes"]
        if not isinstance(rows, list) or len(rows) > 32:
            raise BlenderRuntimeRegistryError("Blender runtime registry size is invalid")
        seen: set[str] = set()
        validated: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "runtime_id", "version", "ownership", "location", "archive_sha256"
            }:
                raise BlenderRuntimeRegistryError("Blender runtime record fields are invalid")
            runtime_id = row["runtime_id"]
            version = row["version"]
            ownership = row["ownership"]
            location = row["location"]
            archive_sha256 = row["archive_sha256"]
            if (
                not isinstance(runtime_id, str)
                or not RUNTIME_ID_PATTERN.fullmatch(runtime_id)
                or runtime_id in seen
                or not isinstance(version, str)
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
                or ownership not in {"legacy", "managed"}
                or not isinstance(location, str)
                or not isinstance(archive_sha256, str)
                or not SHA256_PATTERN.fullmatch(archive_sha256)
            ):
                raise BlenderRuntimeRegistryError("Blender runtime record is invalid")
            if ownership == "legacy":
                if runtime_id != G8_RUNTIME_ID or location != "legacy" or version != G8_VERSION:
                    raise BlenderRuntimeRegistryError("legacy Blender runtime record is invalid")
            elif not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", location):
                raise BlenderRuntimeRegistryError("managed Blender runtime location is invalid")
            seen.add(runtime_id)
            validated.append({key: str(row[key]) for key in row})
        active = value["active_runtime_id"]
        if active is not None and (not isinstance(active, str) or active not in seen):
            raise BlenderRuntimeRegistryError("active Blender runtime is not registered")
        return {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "active_runtime_id": active,
            "runtimes": validated,
        }

    def _read_registry(self) -> dict[str, Any]:
        if self.registry_path.is_symlink():
            raise BlenderRuntimeRegistryError("Blender runtime registry must not be a symlink")
        if not self.registry_path.exists():
            return self._empty_registry()
        if not self.registry_path.is_file() or self.registry_path.stat().st_size > 256 * 1024:
            raise BlenderRuntimeRegistryError("Blender runtime registry file is invalid")
        try:
            value = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderRuntimeRegistryError("Blender runtime registry JSON is invalid") from exc
        return self._validated_registry(value)

    def _write_registry(self, value: dict[str, Any]) -> None:
        validated = self._validated_registry(value)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(validated, sort_keys=True, separators=(",", ":")) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".blender-runtimes-", suffix=".tmp", dir=self.registry_path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.registry_path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _runtime_root(self, row: dict[str, str]) -> Path:
        if row["ownership"] == "legacy":
            return self.legacy_root
        candidate = self.managed_root / row["location"]
        if candidate.is_symlink():
            raise BlenderRuntimeRegistryError("managed Blender runtime must not be a symlink")
        root = candidate.resolve()
        try:
            root.relative_to(self.managed_root)
        except ValueError as exc:  # defensive; location validation already excludes separators
            raise BlenderRuntimeRegistryError("managed Blender runtime escapes its root") from exc
        return root

    def _resolved(self, row: dict[str, str]) -> ResolvedBlenderRuntime:
        root = self._runtime_root(row)
        return ResolvedBlenderRuntime(
            runtime_id=row["runtime_id"],
            version=row["version"],
            ownership=row["ownership"],
            root=root,
            executable=root / "install/blender",
            manifest_path=self.manifest_path,
            trusted_worker=self.trusted_worker,
            archive_sha256=row["archive_sha256"],
        )

    def _checks(self, runtime: ResolvedBlenderRuntime) -> dict[str, bool]:
        expected = {
            "schema_version": 1,
            "version": runtime.version,
            "archive_sha256": runtime.archive_sha256,
            "executable": "blender",
        }
        stamp_path = runtime.root / ".runtime.json"
        stamp_ok = False
        try:
            stamp_ok = (
                not stamp_path.is_symlink()
                and stamp_path.is_file()
                and stamp_path.stat().st_size <= 64 * 1024
                and json.loads(stamp_path.read_text(encoding="utf-8")) == expected
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            stamp_ok = False
        executable_ok = (
            runtime.executable.is_file()
            and not runtime.executable.is_symlink()
            and os.access(runtime.executable, os.X_OK)
        )
        worker_ok = runtime.trusted_worker.is_file() and not runtime.trusted_worker.is_symlink()
        manifest_ok = False
        try:
            if runtime.ownership == "legacy":
                manifest = self._manifest()
                manifest_ok = (
                    runtime.version == manifest["version"]
                    and runtime.archive_sha256 == manifest["archive_sha256"]
                )
            else:
                specs = self._catalog_specs()
                spec = specs.get(runtime.runtime_id)
                if spec is None and self.catalog_path is None and runtime.version == G8_VERSION:
                    # Compatibility for registries created before the catalog existed.
                    spec = specs[G8_MANAGED_RUNTIME_ID]
                manifest_ok = spec is not None and (
                    runtime.version == spec.version
                    and runtime.archive_sha256 == spec.archive_sha256
                )
        except BlenderRuntimeRegistryError:
            pass
        return {
            "manifest": manifest_ok,
            "stamp": stamp_ok,
            "executable": executable_ok,
            "trusted_worker": worker_ok,
        }

    def _ready(self, runtime: ResolvedBlenderRuntime) -> bool:
        return all(self._checks(runtime).values())

    def register_legacy(self) -> bool:
        manifest = self._manifest()
        candidate = {
            "runtime_id": G8_RUNTIME_ID,
            "version": G8_VERSION,
            "ownership": "legacy",
            "location": "legacy",
            "archive_sha256": manifest["archive_sha256"],
        }
        if not self._ready(self._resolved(candidate)):
            return False
        self.registry_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.registry_path.with_suffix(self.registry_path.suffix + ".lock")
        if lock_path.is_symlink():
            raise BlenderRuntimeRegistryError("Blender runtime registry lock must not be a symlink")
        with lock_path.open("a", encoding="ascii") as lock:
            lock_path.chmod(0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            registry = self._read_registry()
            existing = next(
                (row for row in registry["runtimes"] if row["runtime_id"] == G8_RUNTIME_ID), None
            )
            if existing is not None and existing != candidate:
                raise BlenderRuntimeRegistryError("legacy Blender runtime registration conflicts")
            changed = existing is None or registry["active_runtime_id"] is None
            if existing is None:
                registry["runtimes"].append(candidate)
            if registry["active_runtime_id"] is None:
                registry["active_runtime_id"] = G8_RUNTIME_ID
            if changed:
                self._write_registry(registry)
        return True

    def register_managed(
        self,
        *,
        runtime_id: str,
        version: str,
        location: str,
        archive_sha256: str,
    ) -> ResolvedBlenderRuntime:
        """Register an already staged and probed runtime without accepting a path."""
        candidate = {
            "runtime_id": runtime_id,
            "version": version,
            "ownership": "managed",
            "location": location,
            "archive_sha256": archive_sha256,
        }
        self._validated_registry({
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "active_runtime_id": runtime_id,
            "runtimes": [candidate],
        })
        resolved = self._resolved(candidate)
        if not self._ready(resolved):
            raise BlenderRuntimeRegistryError("managed Blender runtime did not pass verification")
        self.registry_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.registry_path.with_suffix(self.registry_path.suffix + ".lock")
        if lock_path.is_symlink():
            raise BlenderRuntimeRegistryError("Blender runtime registry lock must not be a symlink")
        with lock_path.open("a", encoding="ascii") as lock:
            lock_path.chmod(0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            registry = self._read_registry()
            existing = next(
                (row for row in registry["runtimes"] if row["runtime_id"] == runtime_id), None
            )
            if existing is not None and existing != candidate:
                raise BlenderRuntimeRegistryError("managed Blender runtime registration conflicts")
            changed = existing is None or registry["active_runtime_id"] is None
            if existing is None:
                registry["runtimes"].append(candidate)
            if registry["active_runtime_id"] is None:
                registry["active_runtime_id"] = runtime_id
            if changed:
                self._write_registry(registry)
        return resolved

    def activate(self, runtime_id: str) -> ResolvedBlenderRuntime:
        with self._reference_guard:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            lock_path = self.registry_path.with_suffix(self.registry_path.suffix + ".lock")
            if lock_path.is_symlink():
                raise BlenderRuntimeRegistryError(
                    "Blender runtime registry lock must not be a symlink"
                )
            with lock_path.open("a", encoding="ascii") as lock:
                lock_path.chmod(0o600)
                fcntl.flock(lock, fcntl.LOCK_EX)
                registry = self._read_registry()
                try:
                    record = next(
                        row for row in registry["runtimes"] if row["runtime_id"] == runtime_id
                    )
                except StopIteration as exc:
                    raise BlenderRuntimeRegistryError("Blender runtime is not registered") from exc
                runtime = self._resolved(record)
                if not self._ready(runtime):
                    raise BlenderRuntimeRegistryError("Blender runtime is not ready")
                if registry["active_runtime_id"] != runtime_id:
                    registry["active_runtime_id"] = runtime_id
                    self._write_registry(registry)
        return runtime

    @contextmanager
    def g8_reference(self) -> Iterator[ResolvedBlenderRuntime | None]:
        """Pin the resolved G8 runtime until its child process has finished."""
        runtime: ResolvedBlenderRuntime | None
        with self._reference_guard:
            runtime = self.resolve_g8()
            if runtime is not None:
                self._live_references[runtime.runtime_id] = (
                    self._live_references.get(runtime.runtime_id, 0) + 1
                )
        try:
            yield runtime
        finally:
            if runtime is not None:
                with self._reference_guard:
                    remaining = self._live_references.get(runtime.runtime_id, 0) - 1
                    if remaining > 0:
                        self._live_references[runtime.runtime_id] = remaining
                    else:
                        self._live_references.pop(runtime.runtime_id, None)

    @contextmanager
    def active_reference(self) -> Iterator[ResolvedBlenderRuntime | None]:
        """Pin the active Studio runtime while a trusted scene worker is running."""
        runtime: ResolvedBlenderRuntime | None
        with self._reference_guard:
            runtime = self.resolve_active()
            if runtime is not None:
                self._live_references[runtime.runtime_id] = (
                    self._live_references.get(runtime.runtime_id, 0) + 1
                )
        try:
            yield runtime
        finally:
            if runtime is not None:
                with self._reference_guard:
                    remaining = self._live_references.get(runtime.runtime_id, 0) - 1
                    if remaining > 0:
                        self._live_references[runtime.runtime_id] = remaining
                    else:
                        self._live_references.pop(runtime.runtime_id, None)

    @contextmanager
    def runtime_reference(self, runtime_id: str) -> Iterator[ResolvedBlenderRuntime | None]:
        """Pin one exact registered runtime for a versioned working copy."""
        runtime: ResolvedBlenderRuntime | None
        with self._reference_guard:
            runtime = self.resolve_registered(runtime_id)
            if runtime is not None:
                self._live_references[runtime.runtime_id] = (
                    self._live_references.get(runtime.runtime_id, 0) + 1
                )
        try:
            yield runtime
        finally:
            if runtime is not None:
                with self._reference_guard:
                    remaining = self._live_references.get(runtime.runtime_id, 0) - 1
                    if remaining > 0:
                        self._live_references[runtime.runtime_id] = remaining
                    else:
                        self._live_references.pop(runtime.runtime_id, None)

    @contextmanager
    def removal_guard(self) -> Iterator[None]:
        """Serialize reference acquisition with remove revalidation and rename."""
        with self._reference_guard:
            yield

    def live_reference_count(self, runtime_id: str) -> int:
        with self._reference_guard:
            return self._live_references.get(runtime_id, 0)

    def unregister_managed(self, runtime_id: str) -> bool:
        """Remove only a non-active managed registry record; never delete files."""
        with self._reference_guard:
            if self._live_references.get(runtime_id, 0):
                raise BlenderRuntimeRegistryError("Blender runtime has live references")
            self.registry_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            lock_path = self.registry_path.with_suffix(self.registry_path.suffix + ".lock")
            if lock_path.is_symlink():
                raise BlenderRuntimeRegistryError(
                    "Blender runtime registry lock must not be a symlink"
                )
            with lock_path.open("a", encoding="ascii") as lock:
                lock_path.chmod(0o600)
                fcntl.flock(lock, fcntl.LOCK_EX)
                registry = self._read_registry()
                record = next(
                    (row for row in registry["runtimes"] if row["runtime_id"] == runtime_id),
                    None,
                )
                if record is None:
                    return False
                if record["ownership"] != "managed":
                    raise BlenderRuntimeRegistryError("external Blender runtime cannot be removed")
                if registry["active_runtime_id"] == runtime_id:
                    raise BlenderRuntimeRegistryError("active Blender runtime cannot be removed")
                registry["runtimes"] = [
                    row for row in registry["runtimes"] if row["runtime_id"] != runtime_id
                ]
                self._write_registry(registry)
        return True

    def resolve_g8(self) -> ResolvedBlenderRuntime | None:
        try:
            registry = self._read_registry()
            runtimes = [self._resolved(row) for row in registry["runtimes"]]
            compatible = [
                runtime for runtime in runtimes
                if runtime.version == G8_VERSION and self._ready(runtime)
            ]
        except BlenderRuntimeRegistryError:
            return None
        active = registry["active_runtime_id"]
        return next((runtime for runtime in compatible if runtime.runtime_id == active), None) or (
            compatible[0] if compatible else None
        )

    def resolve_active(self) -> ResolvedBlenderRuntime | None:
        try:
            registry = self._read_registry()
            active = registry["active_runtime_id"]
            record = next(row for row in registry["runtimes"] if row["runtime_id"] == active)
            runtime = self._resolved(record)
            return runtime if self._ready(runtime) else None
        except (BlenderRuntimeRegistryError, StopIteration):
            return None

    def resolve_registered(self, runtime_id: str) -> ResolvedBlenderRuntime | None:
        try:
            registry = self._read_registry()
            record = next(
                row for row in registry["runtimes"] if row["runtime_id"] == runtime_id
            )
            runtime = self._resolved(record)
            return runtime if self._ready(runtime) else None
        except (BlenderRuntimeRegistryError, StopIteration):
            return None

    def status(self) -> dict[str, Any]:
        try:
            # A legacy runtime may be built while the service is running. A status
            # refresh records only its fixed, verified identity and never moves it.
            self.register_legacy()
            registry = self._read_registry()
            rows = []
            for record in registry["runtimes"]:
                runtime = self._resolved(record)
                checks = self._checks(runtime)
                supported = checks["manifest"]
                g8_compatible = runtime.version == G8_VERSION and supported
                rows.append({
                    "runtime_id": runtime.runtime_id,
                    "version": runtime.version,
                    "ownership": runtime.ownership,
                    "state": "ready" if all(checks.values()) else (
                        "unsupported" if not supported else "damaged"
                    ),
                    "active": runtime.runtime_id == registry["active_runtime_id"],
                    "removable": runtime.ownership == "managed",
                    "compatible_profiles": [G8_PROFILE] if g8_compatible else [],
                    "checks": checks,
                })
            selected = self.resolve_g8()
            aggregate_state = "ready" if selected is not None else next(
                (state for state in ("damaged", "unsupported")
                 if any(row["state"] == state for row in rows)),
                "missing",
            )
            return {
                "schema_version": STATUS_SCHEMA_VERSION,
                "state": aggregate_state,
                "required_version": G8_VERSION,
                "active_runtime_id": registry["active_runtime_id"],
                "g8_runtime_id": selected.runtime_id if selected is not None else None,
                "management_available": False,
                "web_pack": {"state": "missing", "reason": "web_runtime_not_installed"},
                "runtimes": rows,
            }
        except BlenderRuntimeRegistryError as exc:
            return {
                "schema_version": STATUS_SCHEMA_VERSION,
                "state": "invalid",
                "reason": exc.code,
                "required_version": G8_VERSION,
                "active_runtime_id": None,
                "g8_runtime_id": None,
                "management_available": False,
                "web_pack": {"state": "missing", "reason": "web_runtime_not_installed"},
                "runtimes": [],
            }

    def fingerprint(self) -> str:
        """Stable diagnostic fingerprint; never serialize the registry or runtime path."""
        payload = json.dumps(self.status(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
