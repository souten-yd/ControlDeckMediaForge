from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import tarfile
import threading
from collections.abc import Callable
from typing import Any

import httpx

from scripts.blender_runtime import (
    BlenderRuntimeError,
    MAX_EXTRACTED_BYTES,
    RuntimeSpec,
    load_spec,
    preflight,
    validate_archive,
    validate_spec,
)

from .blender_operation import (
    TERMINAL_BLENDER_RUNTIME_OPERATION_STATES,
    BlenderRuntimeOperation,
    BlenderRuntimeOperationAction,
    BlenderRuntimeOperationError,
    BlenderRuntimeOperationState,
)
from .blender_runtime import (
    G8_RUNTIME_ID,
    RUNTIME_ID_PATTERN,
    BlenderRuntimeRegistryError,
    BlenderRuntimeResolver,
)
from .blender_web import (
    BlenderWebPack,
    BlenderWebPackError,
    WebPackComponent,
    extract_web_pack_archive,
    validate_web_pack_archive,
)
from .paths import contained
from .store import Store


MINIMUM_DISK_MARGIN_BYTES = 1024 * 1024 * 1024
DOWNLOAD_RETRIES = 3
RUNTIME_ID = "blender-4.5.9-linux-x64"
MAX_CATALOG_BYTES = 128 * 1024
USER_AGENT = "ControlDeck-Media-Forge/Blender-Runtime-Manager"
logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class BlenderRuntimeCatalog:
    base_runtime_id: str
    recommended_studio_runtime_id: str
    specs: dict[str, RuntimeSpec]


class BlenderRuntimeManager:
    """Durable installer for the exact trusted Blender catalog entry."""

    def __init__(
        self,
        store: Store,
        resolver: BlenderRuntimeResolver,
        *,
        manifest_path: Path,
        preflight_script: Path,
        download_root: Path,
        catalog_path: Path | None = None,
        web_pack: BlenderWebPack | None = None,
        web_download_root: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.store = store
        self.resolver = resolver
        self.manifest_path = manifest_path.resolve()
        self.preflight_script = preflight_script.resolve()
        self.download_root = download_root.resolve()
        self.catalog_path = Path(os.path.abspath(catalog_path)) if catalog_path is not None else None
        self.web_pack = web_pack
        self.web_download_root = web_download_root.resolve() if web_download_root is not None else None
        self.transport = transport
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._removal_admissions: set[asyncio.Task[BlenderRuntimeOperation]] = set()
        self._request_admissions: set[asyncio.Task[BlenderRuntimeOperation]] = set()
        self._admission_guard = threading.Lock()
        self._guard = asyncio.Semaphore(1)
        self._stopping: asyncio.Task[None] | None = None

    @property
    def spec(self) -> RuntimeSpec:
        catalog = self._catalog()
        return catalog.specs[catalog.base_runtime_id]

    async def start(self) -> None:
        for operation_id in await self._runtime_io(self._startup_sync):
            self._spawn(operation_id)

    def _startup_sync(self) -> list[str]:
        self.resolver.managed_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.download_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.web_pack is not None:
            self.web_pack.managed_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.web_download_root is not None:
            self.web_download_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        return self.store.resumable_blender_runtime_operation_ids()

    async def stop(self) -> None:
        if self._stopping is None or self._stopping.done():
            self._stopping = asyncio.create_task(self._stop_workers())
        await self._await_owned(self._stopping)

    async def _stop_workers(self) -> None:
        await asyncio.gather(*list(self._request_admissions), return_exceptions=True)
        await asyncio.gather(*list(self._removal_admissions), return_exceptions=True)
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def catalog(self) -> dict[str, Any]:
        catalog = self._catalog()
        base = catalog.specs[catalog.base_runtime_id]
        active = self.resolver.resolve_active()
        status = self.resolver.status()
        ready_ids = {
            str(row["runtime_id"])
            for row in status.get("runtimes", [])
            if row.get("state") == "ready"
        }
        return {
            # Keep the 3DS-2a read-only fields additive for older workspaces.
            "version": base.version,
            "archive_size_bytes": base.archive_size_bytes,
            "license": base.license,
            "source": "blender.org",
            "base_runtime_id": catalog.base_runtime_id,
            "recommended_studio_runtime_id": catalog.recommended_studio_runtime_id,
            "active_runtime_id": active.runtime_id if active is not None else None,
            "update_available": (
                active is not None
                and active.runtime_id != catalog.recommended_studio_runtime_id
            ),
            "items": [
                {
                    "runtime_id": runtime_id,
                    "version": spec.version,
                    "archive_size_bytes": spec.archive_size_bytes,
                    "license": spec.license,
                    "source": "blender.org",
                }
                for runtime_id, spec in catalog.specs.items()
            ],
            "install_available": catalog.base_runtime_id not in ready_ids,
            "exact_install_available": True,
        }

    def _catalog(self) -> BlenderRuntimeCatalog:
        try:
            base_spec = load_spec(self.manifest_path)
        except BlenderRuntimeError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_catalog_invalid", "trusted Blender manifest is invalid"
            ) from exc
        if self.catalog_path is None:
            return BlenderRuntimeCatalog(RUNTIME_ID, RUNTIME_ID, {RUNTIME_ID: base_spec})
        path = self.catalog_path
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CATALOG_BYTES:
            raise BlenderRuntimeOperationError(
                "blender_runtime_catalog_invalid", "trusted Blender catalog is unavailable"
            )
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_catalog_invalid", "trusted Blender catalog is invalid"
            ) from exc
        if (
            not isinstance(value, dict)
            or set(value) != {
                "schema_version", "base_runtime_id", "recommended_studio_runtime_id", "runtimes"
            }
            or value["schema_version"] != 1
            or not isinstance(value["runtimes"], list)
            or not 1 <= len(value["runtimes"]) <= 16
        ):
            raise BlenderRuntimeOperationError(
                "blender_runtime_catalog_invalid", "trusted Blender catalog is invalid"
            )
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
                    raise BlenderRuntimeOperationError(
                        "blender_runtime_catalog_invalid", "trusted Blender catalog is invalid"
                    )
                specs[row["runtime_id"]] = validate_spec(row["spec"])
        except BlenderRuntimeError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_catalog_invalid", "trusted Blender catalog is invalid"
            ) from exc
        base_id = value["base_runtime_id"]
        recommended_id = value["recommended_studio_runtime_id"]
        if (
            not isinstance(base_id, str)
            or not isinstance(recommended_id, str)
            or base_id not in specs
            or recommended_id not in specs
            or specs[base_id] != base_spec
        ):
            raise BlenderRuntimeOperationError(
                "blender_runtime_catalog_invalid", "trusted Blender catalog is invalid"
            )
        return BlenderRuntimeCatalog(base_id, recommended_id, specs)

    def install(self) -> BlenderRuntimeOperation:
        return self._launch(self._prepare_install())

    def _prepare_install(self) -> BlenderRuntimeOperation:
        return self._prepare_start(self._catalog().base_runtime_id, BlenderRuntimeOperationAction.INSTALL)

    async def request(self, action: str, identifier: str = "") -> BlenderRuntimeOperation:
        """Own admission I/O through disconnect; spawn workers only on the loop.

        The synchronous helpers remain compatibility entrypoints for local
        callers. Async HTTP/WS callers must use this method instead.
        """
        callbacks: dict[str, Callable[[], BlenderRuntimeOperation]] = {
            "install": self._prepare_install,
            "web_install": self._prepare_web,
            "update": self._prepare_update,
            "repair": lambda: self._prepare_repair(identifier),
            "switch": lambda: self._prepare_switch(identifier),
            "cancel": lambda: self.cancel(identifier),
        }
        if action not in callbacks:
            raise BlenderRuntimeOperationError("invalid_blender_runtime_action", "unknown setup action")

        def prepare() -> BlenderRuntimeOperation:
            # Preserve the formerly serialized duplicate-request lookup/insert.
            # Acquire this lock in the worker, never on the event-loop thread.
            with self._admission_guard:
                return callbacks[action]()

        async def admit() -> BlenderRuntimeOperation:
            operation = await asyncio.to_thread(prepare)
            if action != "cancel":
                self._launch(operation)
            return operation

        task = asyncio.create_task(admit())
        self._request_admissions.add(task)
        canceled = False
        try:
            while True:
                try:
                    operation = await asyncio.shield(task)
                    break
                except asyncio.CancelledError:
                    if task.cancelled():
                        raise
                    canceled = True
            if canceled:
                raise asyncio.CancelledError
            return operation
        finally:
            self._request_admissions.discard(task)

    def _launch(self, operation: BlenderRuntimeOperation) -> BlenderRuntimeOperation:
        self._spawn(operation.id)
        return operation

    def web_status(self) -> dict[str, Any]:
        if self.web_pack is None:
            return {
                "schema_version": "media-forge.blender-web-pack-status@1",
                "state": "missing",
                "reason": "web_runtime_not_configured",
                "install_available": False,
                "components": [],
                "checks": {"stamp": False, "required_files": False},
            }
        return self.web_pack.status()

    def install_web(self) -> BlenderRuntimeOperation:
        return self._launch(self._prepare_web())

    def _prepare_web(self) -> BlenderRuntimeOperation:
        if self.web_pack is None or self.web_download_root is None:
            raise BlenderRuntimeOperationError(
                "blender_web_not_configured", "Blender browser-operation pack is not configured"
            )
        try:
            spec = self.web_pack.spec()
        except BlenderWebPackError as exc:
            raise BlenderRuntimeOperationError(exc.code, str(exc)) from exc
        if self.web_pack.status().get("state") == "ready":
            raise BlenderRuntimeOperationError(
                "blender_web_already_installed", "Blender browser-operation pack is already installed"
            )
        active = next((
            item for item in self.store.list_blender_runtime_operations()
            if item.runtime_id == spec.pack_id
            and item.state not in TERMINAL_BLENDER_RUNTIME_OPERATION_STATES
        ), None)
        if active is not None:
            return active
        try:
            operation = self.store.create_blender_runtime_operation(
                spec.pack_id,
                spec.version,
                BlenderRuntimeOperationAction.INSTALL,
                bytes_total=spec.archive_size_bytes,
            )
        except ValueError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_operation_active", "another Blender web pack operation is active"
            ) from exc
        return operation

    def update(self) -> BlenderRuntimeOperation:
        return self._launch(self._prepare_update())

    def _prepare_update(self) -> BlenderRuntimeOperation:
        catalog = self._catalog()
        active = self.resolver.resolve_active()
        if active is None:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_installed", "install the base Blender runtime first"
            )
        if active.runtime_id == catalog.recommended_studio_runtime_id:
            raise BlenderRuntimeOperationError(
                "blender_runtime_already_current", "Blender Studio runtime is already current"
            )
        return self._prepare_start(
            catalog.recommended_studio_runtime_id, BlenderRuntimeOperationAction.UPDATE
        )

    def repair(self, runtime_id: str) -> BlenderRuntimeOperation:
        return self._launch(self._prepare_repair(runtime_id))

    def _prepare_repair(self, runtime_id: str) -> BlenderRuntimeOperation:
        if runtime_id not in self._catalog().specs:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_found", "Blender runtime is not in the trusted catalog"
            )
        row = next((
            item for item in self.resolver.status().get("runtimes", [])
            if item.get("runtime_id") == runtime_id and item.get("ownership") == "managed"
        ), None)
        if row is None:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_found", "managed Blender runtime was not found"
            )
        return self._prepare_start(runtime_id, BlenderRuntimeOperationAction.REPAIR)

    def switch(self, runtime_id: str) -> BlenderRuntimeOperation:
        return self._launch(self._prepare_switch(runtime_id))

    def _prepare_switch(self, runtime_id: str) -> BlenderRuntimeOperation:
        if runtime_id not in self._catalog().specs:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_found", "Blender runtime is not in the trusted catalog"
            )
        return self._prepare_start(runtime_id, BlenderRuntimeOperationAction.SWITCH)

    async def install_exact(self, runtime_id: str) -> BlenderRuntimeOperation:
        """Explicit exact-catalog installation, without changing an existing active pin."""
        task = asyncio.create_task(self._admit_exact_async(runtime_id))
        self._removal_admissions.add(task)
        try:
            return await task
        finally:
            self._removal_admissions.discard(task)

    async def _admit_exact_async(self, runtime_id: str) -> BlenderRuntimeOperation:
        task = asyncio.create_task(asyncio.to_thread(self._admit_exact, runtime_id))
        try:
            operation = await asyncio.shield(task)
        except asyncio.CancelledError:
            operation = await task
            self._spawn(operation.id)
            raise
        self._spawn(operation.id)
        return operation

    def _admit_exact(self, runtime_id: str) -> BlenderRuntimeOperation:
        spec = self._catalog().specs.get(runtime_id)
        if spec is None:
            raise BlenderRuntimeOperationError("blender_runtime_not_found", "runtime is not in the trusted catalog")
        identity = self._exact_identity(runtime_id, spec)
        for operation in self.store.list_blender_runtime_operations():
            if operation.runtime_id == runtime_id and operation.state not in TERMINAL_BLENDER_RUNTIME_OPERATION_STATES:
                if operation.action == BlenderRuntimeOperationAction.INSTALL and (operation.result or {}).get("exact_install") == identity:
                    return operation
                raise BlenderRuntimeOperationError("blender_runtime_operation_active", "another runtime operation is active")
        if self.resolver.resolve_registered(runtime_id) is not None:
            raise BlenderRuntimeOperationError("blender_runtime_already_installed", "Blender runtime is already installed")
        try:
            return self.store.create_blender_runtime_operation(runtime_id, spec.version,
                BlenderRuntimeOperationAction.INSTALL, bytes_total=spec.archive_size_bytes,
                result={"exact_install": identity})
        except ValueError as exc:
            raise BlenderRuntimeOperationError("blender_runtime_operation_active", "another runtime operation is active") from exc

    @staticmethod
    def _exact_identity(runtime_id: str, spec: RuntimeSpec) -> dict[str, Any]:
        return {"runtime_id": runtime_id, "version": spec.version,
                "archive_sha256": spec.archive_sha256, "archive_size_bytes": spec.archive_size_bytes}

    @staticmethod
    def _removal_allowed(preview: dict[str, Any], acknowledge_history: bool) -> bool:
        if type(acknowledge_history) is not bool:
            raise BlenderRuntimeOperationError("blender_runtime_confirmation_invalid", "history acknowledgement must be a boolean")
        return bool(preview["can_remove"] or (acknowledge_history and preview.get("can_remove_with_history")))

    async def removal_preview(self, runtime_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._removal_preview, runtime_id)

    def _removal_preview(self, runtime_id: str) -> dict[str, Any]:
        spec = self._catalog().specs.get(runtime_id)
        if spec is None:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_found", "Blender runtime is not in the trusted catalog"
            )
        row = next((
            item for item in self.resolver.status().get("runtimes", [])
            if item.get("runtime_id") == runtime_id
        ), None)
        if row is None:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_found", "Blender runtime was not found"
            )
        if row.get("ownership") != "managed":
            raise BlenderRuntimeOperationError(
                "blender_runtime_external", "external Blender runtime cannot be removed"
            )
        destination = contained(
            self.resolver.managed_root, self.resolver.managed_root / runtime_id
        )
        reclaimable = self._directory_bytes(destination)
        in_process = self.resolver.live_reference_count(runtime_id)
        durable = self.store.active_scene_runtime_references(runtime_id)
        live_references = in_process + sum(durable.values())
        project_references = self.store.scene_runtime_reference_count(runtime_id)
        blocked: list[str] = []
        if row.get("active") is True:
            blocked.append("active_runtime")
        if live_references:
            blocked.append("live_reference")
        if project_references:
            blocked.append("project_reference")
        exact_reinstall = (self._exact_identity(runtime_id, spec)
            if row["version"] == spec.version and row.get("archive_sha256") == spec.archive_sha256 else None)
        identity = {
            "runtime_id": runtime_id,
            "version": str(row["version"]),
            "active": row.get("active") is True,
            "state": str(row["state"]),
            "reclaimable_bytes": reclaimable,
            "live_reference_count": live_references,
            "in_process_reference_count": in_process,
            "durable_reference_counts": durable,
            "project_reference_count": project_references,
            "exact_reinstall": exact_reinstall,
            "blocked_reasons": blocked,
        }
        fingerprint = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            **identity,
            "can_remove": not blocked,
            "can_remove_with_history": blocked == ["project_reference"] and exact_reinstall is not None,
            "confirmation_fingerprint": fingerprint,
        }

    def _external_removal_preview(self, runtime_id: str) -> dict[str, Any]:
        if runtime_id != G8_RUNTIME_ID:
            raise BlenderRuntimeOperationError("blender_runtime_external_invalid", "unknown external runtime")
        status = self.resolver.status()
        row = next((r for r in status["runtimes"] if r["runtime_id"] == runtime_id), None)
        if row is None or row["ownership"] != "legacy":
            raise BlenderRuntimeOperationError("blender_runtime_not_found", "external runtime is not registered")
        in_process = self.resolver.live_reference_count(runtime_id)
        durable = self.store.active_scene_runtime_references(runtime_id)
        live = in_process + sum(durable.values())
        projects = self.store.scene_runtime_reference_count(runtime_id)
        blocked = (["active_runtime"] if row["active"] else [])
        blocked += ["live_reference"] if live else []
        blocked += ["project_reference"] if projects else []
        identity = {"operation": "unregister", "runtime_id": runtime_id, "version": row["version"],
                    "active": row["active"], "state": row["state"], "reclaimable_bytes": 0,
                    "live_reference_count": live, "project_reference_count": projects,
                    "in_process_reference_count": in_process, "durable_reference_counts": durable,
                    "blocked_reasons": blocked}
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {**identity, "can_remove": not blocked, "confirmation_fingerprint": fingerprint}

    async def external_removal_preview(self, runtime_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._external_removal_preview, runtime_id)

    async def external_registration(
        self, *, register: bool, runtime_id: str = G8_RUNTIME_ID, confirmation_fingerprint: str = ""
    ) -> dict[str, Any]:
        """Short atomic registration change; never delete external files.

        Do not abandon a registry-writing thread when its request disconnects.
        The registry remains authoritative after response loss or restart.
        """
        if runtime_id != G8_RUNTIME_ID:
            raise BlenderRuntimeOperationError("blender_runtime_external_invalid", "unknown external runtime")

        def change() -> dict[str, Any]:
            with self.resolver.removal_guard():
                if register:
                    if not self.resolver.register_legacy(explicit=True):
                        raise BlenderRuntimeOperationError(
                            "blender_runtime_external_unavailable", "configured external runtime failed verification")
                    return {"registered": True, "runtime_id": runtime_id}
                preview = self._external_removal_preview(runtime_id)
                if confirmation_fingerprint != preview["confirmation_fingerprint"]:
                    raise BlenderRuntimeOperationError("blender_runtime_remove_changed", "external runtime preview changed")
                if not preview["can_remove"]:
                    raise BlenderRuntimeOperationError("blender_runtime_in_use", "external runtime is still in use")
                self.resolver.unregister_legacy()
                return {"unregistered": True, "runtime_id": runtime_id, "removed_bytes": 0}

        if self._guard.locked():
            raise BlenderRuntimeOperationError("blender_runtime_operation_active", "another runtime operation is active")
        async with self._guard:
            task = asyncio.create_task(asyncio.to_thread(change))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise

    async def remove(
        self, runtime_id: str, confirmation_fingerprint: str, *, acknowledge_history: bool = False
    ) -> BlenderRuntimeOperation:
        task = asyncio.create_task(self._admit_removal_async(runtime_id, confirmation_fingerprint, acknowledge_history))
        self._removal_admissions.add(task)
        try:
            return await task
        finally:
            self._removal_admissions.discard(task)

    async def _admit_removal_async(
        self, runtime_id: str, confirmation_fingerprint: str, acknowledge_history: bool = False
    ) -> BlenderRuntimeOperation:
        task = asyncio.create_task(asyncio.to_thread(self._admit_removal, runtime_id, confirmation_fingerprint, acknowledge_history))
        try:
            operation = await asyncio.shield(task)
        except asyncio.CancelledError:
            operation = await task
            self._spawn(operation.id)
            raise
        self._spawn(operation.id)
        return operation

    def _admit_removal(
        self, runtime_id: str, confirmation_fingerprint: str, acknowledge_history: bool = False
    ) -> BlenderRuntimeOperation:
        preview = self._removal_preview(runtime_id)
        if confirmation_fingerprint != preview["confirmation_fingerprint"]:
            raise BlenderRuntimeOperationError(
                "blender_runtime_remove_changed", "Blender runtime removal preview changed"
            )
        if not self._removal_allowed(preview, acknowledge_history):
            raise BlenderRuntimeOperationError(
                "blender_runtime_in_use", "Blender runtime is still in use"
            )
        try:
            operation = self.store.create_blender_runtime_operation(
                runtime_id,
                str(preview["version"]),
                BlenderRuntimeOperationAction.REMOVE,
                bytes_total=int(preview["reclaimable_bytes"]),
                result={"removal_preview": preview, "acknowledge_history": acknowledge_history},
            )
        except ValueError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_operation_active", "another Blender runtime operation is active"
            ) from exc
        return operation

    def _prepare_start(
        self, runtime_id: str, action: BlenderRuntimeOperationAction
    ) -> BlenderRuntimeOperation:
        active = next((
            item for item in self.store.list_blender_runtime_operations()
            if item.runtime_id == runtime_id
            and item.action == action
            and item.state not in TERMINAL_BLENDER_RUNTIME_OPERATION_STATES
        ), None)
        if active is not None:
            return active
        if action == BlenderRuntimeOperationAction.INSTALL and any(
            row.get("runtime_id") == runtime_id and row.get("state") == "ready"
            for row in self.resolver.status().get("runtimes", [])
        ):
            raise BlenderRuntimeOperationError(
                "blender_runtime_already_installed", "Blender runtime is already installed"
            )
        try:
            spec = self._catalog().specs[runtime_id]
            operation = self.store.create_blender_runtime_operation(
                runtime_id,
                spec.version,
                action,
                bytes_total=0 if action == BlenderRuntimeOperationAction.SWITCH else spec.archive_size_bytes,
            )
        except ValueError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_operation_active", "another Blender runtime operation is active"
            ) from exc
        return operation

    def cancel(self, operation_id: str) -> BlenderRuntimeOperation:
        try:
            operation = self.store.get_blender_runtime_operation(operation_id)
        except KeyError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_operation_not_found", "Blender runtime operation was not found"
            ) from exc
        web_pack_id = None
        if self.web_pack is not None:
            try:
                web_pack_id = self.web_pack.spec().pack_id
            except BlenderWebPackError:
                pass
        if operation.runtime_id not in self._catalog().specs and operation.runtime_id != web_pack_id:
            raise BlenderRuntimeOperationError(
                "blender_runtime_operation_not_found", "Blender runtime operation was not found"
            )
        return self.store.request_blender_runtime_operation_cancel(operation_id)

    def _spawn(self, operation_id: str) -> None:
        current = self._tasks.get(operation_id)
        if current is not None and not current.done():
            return
        task = asyncio.create_task(self._run(operation_id), name=f"blender-runtime-{operation_id}")
        self._tasks[operation_id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(operation_id, None))

    async def _run(self, operation_id: str) -> None:
        async with self._guard:
            operation = await self._runtime_io(self.store.get_blender_runtime_operation, operation_id)
            if await self._runtime_io(self.store.blender_runtime_operation_cancel_requested, operation_id):
                await self._finish_canceled(operation)
                return
            try:
                web_pack_id = (await self._runtime_io(self.web_pack.spec)).pack_id if self.web_pack is not None else None
                if operation.runtime_id == web_pack_id:
                    await self._install_web(operation)
                elif operation.action == BlenderRuntimeOperationAction.SWITCH:
                    await self._switch(operation)
                elif operation.action == BlenderRuntimeOperationAction.REMOVE:
                    await self._remove(operation)
                else:
                    await self._install(operation)
            except asyncio.CancelledError:
                # Store.initialize() queues the journal again. Partial bytes stay
                # in the trusted download cache and must pass ETag/hash checks.
                raise
            except (BlenderRuntimeOperationError, BlenderWebPackError) as exc:
                if exc.code == "blender_runtime_operation_canceled":
                    await self._finish_canceled(operation)
                    return
                await self._runtime_io(self._fail_sync, operation.id, exc.code, str(exc)[:300])
            except (BlenderRuntimeError, BlenderRuntimeRegistryError, OSError, httpx.HTTPError) as exc:
                await self._runtime_io(self._fail_sync, operation.id, "blender_runtime_install_failed", str(exc)[:300])
            except Exception as exc:  # noqa: BLE001 - durable isolation boundary
                logger.exception("Blender runtime operation %s failed", operation.id)
                await self._runtime_io(self._fail_sync, operation.id, "blender_runtime_install_failed", str(exc)[:300])

    def _fail_sync(self, operation_id: str, code: str, message: str) -> None:
        self._clean_stage_sync(operation_id)
        self.store.update_blender_runtime_operation(
            operation_id, state=BlenderRuntimeOperationState.FAILED,
            error_code=code, error_message=message,
        )

    async def _install_web(self, operation: BlenderRuntimeOperation) -> None:
        if self.web_pack is None or self.web_download_root is None:
            raise BlenderWebPackError("blender_web_not_configured", "web pack is not configured")
        spec = self.web_pack.spec()
        if operation.runtime_id != spec.pack_id or operation.version != spec.version:
            raise BlenderWebPackError("blender_web_catalog_changed", "web pack catalog changed")
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.PREFLIGHT
        )
        required = spec.archive_size_bytes + MINIMUM_DISK_MARGIN_BYTES
        if shutil.disk_usage(self.web_pack.managed_root).free < required:
            raise BlenderWebPackError("insufficient_disk", "web pack store has insufficient free space")
        destination = self.web_pack.destination(spec)
        if destination.is_symlink():
            raise BlenderWebPackError("blender_web_destination_unsafe", "web pack destination is unsafe")
        if destination.is_dir():
            status = self.web_pack.status()
            if status.get("state") != "ready":
                raise BlenderWebPackError("blender_web_destination_exists", "damaged web pack must be repaired")
            self.store.update_blender_runtime_operation(
                operation.id,
                state=BlenderRuntimeOperationState.READY,
                bytes_done=spec.archive_size_bytes,
                result={"pack_id": spec.pack_id, "version": spec.version, "recovered": True},
            )
            return
        if destination.exists():
            raise BlenderWebPackError("blender_web_destination_unsafe", "web pack destination is unsafe")

        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.DOWNLOADING
        )
        archives: list[tuple[WebPackComponent, Path]] = []
        downloaded = 0
        for component in spec.components:
            archive = await self._download(
                operation, component, download_root=self.web_download_root,
                progress_base=downloaded,
            )
            downloaded += component.archive_size_bytes
            self.store.update_blender_runtime_operation(operation.id, bytes_done=downloaded)
            archives.append((component, archive))
        self._raise_if_canceled(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id,
            state=BlenderRuntimeOperationState.VERIFYING,
            bytes_done=spec.archive_size_bytes,
        )
        archive_facts: dict[str, dict[str, int]] = {}
        for component, archive in archives:
            try:
                archive_facts[component.id] = await asyncio.to_thread(
                    validate_web_pack_archive, archive, component
                )
            except BlenderWebPackError:
                archive.unlink(missing_ok=True)
                raise
        extracted_bytes = sum(item["extracted_bytes"] for item in archive_facts.values())
        if shutil.disk_usage(self.web_pack.managed_root).free < (
            extracted_bytes + MINIMUM_DISK_MARGIN_BYTES
        ):
            raise BlenderWebPackError("insufficient_disk", "web pack cannot be safely extracted")
        self._raise_if_canceled(operation.id)

        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.INSTALLING
        )
        stage = self._web_stage_root(operation.id)
        await self._clean_stage(operation.id)
        extract_root = contained(stage, stage / "extract")
        install_root = contained(stage, stage / "candidate/install")
        extract_root.mkdir(mode=0o700, parents=True)
        install_root.mkdir(mode=0o700, parents=True)
        for component, archive in archives:
            component_extract = contained(extract_root, extract_root / component.id)
            component_extract.mkdir(mode=0o700)
            await asyncio.to_thread(
                extract_web_pack_archive,
                archive,
                component_extract,
                component,
                lambda: self.store.blender_runtime_operation_cancel_requested(operation.id),
            )
            extracted = contained(
                component_extract, component_extract / component.top_level_directory
            )
            os.replace(extracted, contained(install_root, install_root / component.id))
        candidate = contained(stage, stage / "candidate")
        self.web_pack.write_stamp(candidate, spec)
        self._raise_if_canceled(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.PROBING
        )
        probe = await asyncio.to_thread(self.web_pack.probe, candidate, spec)
        self._raise_if_canceled(operation.id)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise BlenderWebPackError("blender_web_destination_exists", "web pack destination appeared")
        os.replace(candidate, destination)
        if self.web_pack.status().get("state") != "ready":
            await asyncio.to_thread(shutil.rmtree, destination)
            raise BlenderWebPackError("blender_web_probe_failed", "installed web pack did not verify")
        await self._clean_stage(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id,
            state=BlenderRuntimeOperationState.READY,
            bytes_done=spec.archive_size_bytes,
            result={
                "pack_id": spec.pack_id,
                "version": spec.version,
                "components": {item.id: item.archive_sha256 for item in spec.components},
                "archives": archive_facts,
                "probe": probe,
            },
        )
    async def _switch(self, operation: BlenderRuntimeOperation) -> None:
        # Keep activation and its terminal journal owned as one started unit.
        await self._runtime_io(self._switch_sync, operation)

    def _switch_sync(self, operation: BlenderRuntimeOperation) -> None:
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.PREFLIGHT
        )
        self._raise_if_canceled(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.PROBING
        )
        runtime = self.resolver.activate(operation.runtime_id)
        self._raise_if_canceled(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id,
            state=BlenderRuntimeOperationState.READY,
            result={"runtime_id": runtime.runtime_id, "version": runtime.version},
        )

    async def _remove(self, operation: BlenderRuntimeOperation) -> None:
        await self._runtime_io(self._remove_sync, operation)

    def _remove_sync(self, operation: BlenderRuntimeOperation) -> None:
        preview = (operation.result or {}).get("removal_preview")
        acknowledge_history = (operation.result or {}).get("acknowledge_history", False)
        if type(acknowledge_history) is not bool:
            raise BlenderRuntimeOperationError("blender_runtime_confirmation_invalid", "stored history acknowledgement is invalid")
        if not isinstance(preview, dict) or not isinstance(
            preview.get("confirmation_fingerprint"), str
        ):
            raise BlenderRuntimeOperationError(
                "blender_runtime_remove_changed", "Blender runtime removal preview is unavailable"
            )
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.PREFLIGHT
        )
        self._raise_if_canceled(operation.id)
        destination = contained(
            self.resolver.managed_root,
            self.resolver.managed_root / operation.runtime_id,
        )
        removing = contained(
            self.resolver.managed_root,
            self.resolver.managed_root / ".removing" / operation.id,
        )
        removed_bytes = int(preview.get("reclaimable_bytes", 0))
        with self.resolver.removal_guard():
            registered = any(
                row.get("runtime_id") == operation.runtime_id
                for row in self.resolver.status().get("runtimes", [])
            )
            if not registered:
                if removing.exists():
                    if removing.is_symlink() or not removing.is_dir():
                        raise BlenderRuntimeOperationError(
                            "blender_runtime_remove_unsafe", "Blender removal staging is unsafe"
                        )
                    shutil.rmtree(removing)
                self.store.update_blender_runtime_operation(
                    operation.id,
                    state=BlenderRuntimeOperationState.READY,
                    bytes_done=removed_bytes,
                    result={
                        "runtime_id": operation.runtime_id,
                        "version": operation.version,
                        "removed_bytes": removed_bytes,
                        "recovered": True,
                        "acknowledge_history": acknowledge_history,
                        "removal_preview": preview,
                    },
                )
                return
            if removing.exists():
                if removing.is_symlink() or not removing.is_dir():
                    raise BlenderRuntimeOperationError(
                        "blender_runtime_remove_unsafe", "Blender removal staging is unsafe"
                    )
                if registered:
                    if destination.exists() or destination.is_symlink():
                        raise BlenderRuntimeOperationError(
                            "blender_runtime_remove_unsafe", "Blender removal state conflicts"
                        )
                    os.replace(removing, destination)
            current = self._removal_preview(operation.runtime_id)
            if current["confirmation_fingerprint"] != preview["confirmation_fingerprint"]:
                raise BlenderRuntimeOperationError(
                    "blender_runtime_remove_changed", "Blender runtime removal preview changed"
                )
            if not self._removal_allowed(current, acknowledge_history):
                raise BlenderRuntimeOperationError(
                    "blender_runtime_in_use", "Blender runtime is still in use"
                )
            self.store.update_blender_runtime_operation(
                operation.id, state=BlenderRuntimeOperationState.DELETING
            )
            removing.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            moved = False
            if destination.exists() or destination.is_symlink():
                self._ensure_managed_destination(destination)
                os.replace(destination, removing)
                moved = True
            try:
                if not self.resolver.unregister_managed(operation.runtime_id):
                    raise BlenderRuntimeOperationError(
                        "blender_runtime_not_found", "Blender runtime was not found"
                    )
                if moved:
                    shutil.rmtree(removing)
            except Exception:
                if moved and removing.exists() and not destination.exists():
                    os.replace(removing, destination)
                    self.resolver.register_managed(
                        runtime_id=operation.runtime_id,
                        version=operation.version,
                        location=operation.runtime_id,
                        archive_sha256=self._catalog().specs[
                            operation.runtime_id
                        ].archive_sha256,
                    )
                raise
        self.store.update_blender_runtime_operation(
            operation.id,
            state=BlenderRuntimeOperationState.READY,
            bytes_done=removed_bytes,
            result={
                "runtime_id": operation.runtime_id,
                "version": operation.version,
                "removed_bytes": removed_bytes,
                "acknowledge_history": acknowledge_history,
                "removal_preview": preview,
            },
        )

    async def _install(self, operation: BlenderRuntimeOperation) -> None:
        try:
            spec = self._catalog().specs[operation.runtime_id]
        except KeyError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_found", "Blender runtime is not in the trusted catalog"
            ) from exc
        if spec.version != operation.version:
            raise BlenderRuntimeOperationError(
                "blender_runtime_catalog_changed", "Blender runtime catalog changed"
            )
        exact_install = (operation.result or {}).get("exact_install")
        if exact_install is not None and exact_install != self._exact_identity(operation.runtime_id, spec):
            raise BlenderRuntimeOperationError("blender_runtime_catalog_changed", "exact Blender archive identity changed")
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.PREFLIGHT
        )
        required = spec.archive_size_bytes + max(
            MINIMUM_DISK_MARGIN_BYTES, spec.archive_size_bytes // 10
        )
        if shutil.disk_usage(self.resolver.managed_root).free < required:
            raise BlenderRuntimeOperationError(
                "insufficient_disk", "Blender runtime store has insufficient free space"
            )
        destination = contained(
            self.resolver.managed_root,
            self.resolver.managed_root / operation.runtime_id,
        )
        if destination.is_symlink():
            raise BlenderRuntimeOperationError(
                "blender_runtime_destination_exists", "managed Blender destination already exists"
            )
        if destination.is_dir() and operation.action != BlenderRuntimeOperationAction.REPAIR:
            self.store.update_blender_runtime_operation(
                operation.id, state=BlenderRuntimeOperationState.PROBING,
                bytes_done=spec.archive_size_bytes,
            )
            facts = await asyncio.to_thread(
                preflight, destination / "install" / spec.executable,
                self.preflight_script, spec,
            )
            self.resolver.register_managed(
                runtime_id=operation.runtime_id,
                version=spec.version,
                location=operation.runtime_id,
                archive_sha256=spec.archive_sha256,
            )
            if operation.action == BlenderRuntimeOperationAction.UPDATE:
                self.resolver.activate(operation.runtime_id)
            await self._clean_stage(operation.id)
            self.store.update_blender_runtime_operation(
                operation.id,
                state=BlenderRuntimeOperationState.READY,
                bytes_done=spec.archive_size_bytes,
                result={
                    "runtime_id": operation.runtime_id,
                    "version": spec.version,
                    "archive_sha256": spec.archive_sha256,
                    "preflight": facts,
                    "recovered": True,
                },
            )
            return
        if destination.exists() and operation.action != BlenderRuntimeOperationAction.REPAIR:
            raise BlenderRuntimeOperationError(
                "blender_runtime_destination_exists", "managed Blender destination already exists"
            )

        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.DOWNLOADING
        )
        archive = await self._download(operation, spec)
        self._raise_if_canceled(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.VERIFYING,
            bytes_done=spec.archive_size_bytes,
        )
        try:
            archive_facts = await asyncio.to_thread(validate_archive, archive, spec)
        except BlenderRuntimeError:
            archive.unlink(missing_ok=True)
            raise
        extracted_bytes = int(archive_facts["extracted_bytes"])
        if shutil.disk_usage(self.resolver.managed_root).free < (
            extracted_bytes + MINIMUM_DISK_MARGIN_BYTES
        ):
            raise BlenderRuntimeOperationError(
                "insufficient_disk", "Blender runtime store cannot safely extract the archive"
            )
        self._raise_if_canceled(operation.id)

        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.INSTALLING
        )
        stage = self._stage_root(operation.id)
        await self._clean_stage(operation.id)
        extract_root = contained(stage, stage / "extract")
        extract_root.mkdir(mode=0o700, parents=True)
        await asyncio.to_thread(
            self._extract,
            archive,
            extract_root,
            spec,
            lambda: self.store.blender_runtime_operation_cancel_requested(operation.id),
        )
        extracted = contained(extract_root, extract_root / spec.top_level_directory)
        if not extracted.is_dir() or extracted.is_symlink():
            raise BlenderRuntimeOperationError(
                "blender_runtime_verify_failed", "archive did not produce the trusted root"
            )
        candidate = contained(stage, stage / "candidate")
        candidate.mkdir(mode=0o700)
        os.replace(extracted, candidate / "install")
        stamp = {
            "schema_version": 1,
            "version": spec.version,
            "archive_sha256": spec.archive_sha256,
            "executable": spec.executable,
        }
        stamp_path = candidate / ".runtime.json"
        stamp_path.write_text(json.dumps(stamp, sort_keys=True) + "\n", encoding="utf-8")
        stamp_path.chmod(0o600)
        self._raise_if_canceled(operation.id)

        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.PROBING
        )
        facts = await asyncio.to_thread(
            preflight, candidate / "install" / spec.executable, self.preflight_script, spec
        )
        self._raise_if_canceled(operation.id)
        if operation.action == BlenderRuntimeOperationAction.REPAIR:
            # Admission may have happened while downloading/probing. Keep its
            # guard, all synchronous persistence and filesystem work off-loop.
            await self._runtime_io(
                self._publish_repair, operation, spec, candidate, destination,
                archive_facts, facts,
            )
            return
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(candidate, destination)
        try:
            self.resolver.register_managed(
                runtime_id=operation.runtime_id,
                version=spec.version,
                location=operation.runtime_id,
                archive_sha256=spec.archive_sha256,
            )
            if operation.action == BlenderRuntimeOperationAction.UPDATE:
                self.resolver.activate(operation.runtime_id)
        except Exception:
            self._ensure_managed_destination(destination)
            await asyncio.to_thread(shutil.rmtree, destination)
            raise
        await self._clean_stage(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id,
            state=BlenderRuntimeOperationState.READY,
            bytes_done=spec.archive_size_bytes,
            result={
                "runtime_id": operation.runtime_id,
                "version": spec.version,
                "archive_sha256": spec.archive_sha256,
                "archive": archive_facts,
                "preflight": facts,
            },
        )

    def _publish_repair(
        self, operation: BlenderRuntimeOperation, spec: RuntimeSpec,
        candidate: Path, destination: Path,
        archive_facts: dict[str, Any], facts: dict[str, Any],
    ) -> None:
        """Publish or roll back a repair atomically against runtime admission."""
        with self.resolver.removal_guard():
            self._raise_if_canceled(operation.id)
            durable = self.store.active_scene_runtime_references(operation.runtime_id)
            if self.resolver.live_reference_count(operation.runtime_id) or any(durable.values()):
                raise BlenderRuntimeOperationError(
                    "blender_runtime_in_use", "Stop Blender jobs and sessions before repairing this runtime"
                )
            self._ensure_managed_destination(destination)
            previous = contained(self.resolver.managed_root,
                self.resolver.managed_root / ".staging" / f"previous-{operation.id}")
            if previous.exists() or previous.is_symlink():
                raise BlenderRuntimeOperationError(
                    "blender_runtime_staging_unsafe", "Blender repair rollback destination already exists"
                )
            os.replace(destination, previous)
            promoted = False
            try:
                os.replace(candidate, destination)
                promoted = True
                self.resolver.register_managed(runtime_id=operation.runtime_id,
                    version=spec.version, location=operation.runtime_id,
                    archive_sha256=spec.archive_sha256)
            except Exception:
                if promoted:
                    self._ensure_managed_destination(destination)
                    shutil.rmtree(destination)
                os.replace(previous, destination)
                raise
            shutil.rmtree(previous)
            stage = self._stage_root(operation.id)
            if stage.exists():
                if stage.is_symlink():
                    raise BlenderRuntimeOperationError("blender_runtime_staging_unsafe", "Blender staging root is unsafe")
                shutil.rmtree(stage)
            self.store.update_blender_runtime_operation(operation.id,
                state=BlenderRuntimeOperationState.READY, bytes_done=spec.archive_size_bytes,
                result={"runtime_id": operation.runtime_id, "version": spec.version,
                    "archive_sha256": spec.archive_sha256, "archive": archive_facts, "preflight": facts})

    async def _download(
        self,
        operation: BlenderRuntimeOperation,
        spec: RuntimeSpec | WebPackComponent,
        *,
        download_root: Path | None = None,
        progress_base: int = 0,
    ) -> Path:
        selected_root = download_root or self.download_root
        archive = contained(selected_root, selected_root / spec.archive_name)
        if archive.is_file() and not archive.is_symlink():
            return archive
        if archive.exists() or archive.is_symlink():
            raise BlenderRuntimeOperationError(
                "blender_runtime_download_unsafe", "Blender archive cache is unsafe"
            )
        partial = archive.with_suffix(archive.suffix + ".partial")
        metadata = archive.with_suffix(archive.suffix + ".partial.json")
        for attempt in range(DOWNLOAD_RETRIES):
            try:
                await self._download_attempt(
                    operation, spec, partial, metadata, progress_base=progress_base
                )
                os.replace(partial, archive)
                metadata.unlink(missing_ok=True)
                return archive
            except httpx.HTTPError:
                self._raise_if_canceled(operation.id)
                if attempt + 1 == DOWNLOAD_RETRIES:
                    raise
                await asyncio.sleep(min(2 ** attempt, 4))
        raise AssertionError("download retry loop ended unexpectedly")

    async def _download_attempt(
        self,
        operation: BlenderRuntimeOperation,
        spec: RuntimeSpec | WebPackComponent,
        partial: Path,
        metadata: Path,
        *,
        progress_base: int = 0,
    ) -> None:
        existing = partial.stat().st_size if partial.is_file() and not partial.is_symlink() else 0
        etag: str | None = None
        if existing:
            if metadata.is_symlink() or (
                metadata.exists() and (not metadata.is_file() or metadata.stat().st_size > 4096)
            ):
                partial.unlink(missing_ok=True)
                metadata.unlink(missing_ok=True)
                existing = 0
            try:
                value = json.loads(metadata.read_text(encoding="utf-8"))
                etag = value["etag"] if set(value) == {"etag"} else None
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
                etag = None
            if not etag or existing > spec.archive_size_bytes:
                partial.unlink(missing_ok=True)
                metadata.unlink(missing_ok=True)
                existing = 0
        headers = {"Accept-Encoding": "identity", "User-Agent": USER_AGENT}
        if existing:
            headers.update({"Range": f"bytes={existing}-", "If-Range": etag or ""})
        async with httpx.AsyncClient(
            transport=self.transport,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=120.0),
            headers=headers,
        ) as client:
            async with client.stream("GET", spec.archive_url) as response:
                if response.status_code not in ({206} if existing else {200}):
                    if existing:
                        partial.unlink(missing_ok=True)
                        metadata.unlink(missing_ok=True)
                    response.raise_for_status()
                    raise BlenderRuntimeOperationError(
                        "blender_runtime_resume_rejected", "download resume response differed"
                    )
                response_etag = response.headers.get("ETag")
                if existing and (
                    response.headers.get("Content-Range", "").split("/", 1)[0]
                    != f"bytes {existing}-{spec.archive_size_bytes - 1}"
                    or response_etag != etag
                ):
                    partial.unlink(missing_ok=True)
                    metadata.unlink(missing_ok=True)
                    raise BlenderRuntimeOperationError(
                        "blender_runtime_resume_rejected", "download resume identity differed"
                    )
                length = response.headers.get("Content-Length")
                expected_length = spec.archive_size_bytes - existing
                if length is not None and int(length) != expected_length:
                    raise BlenderRuntimeOperationError(
                        "blender_runtime_download_size", "download Content-Length differed"
                    )
                if not existing:
                    partial.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    if partial.exists() or partial.is_symlink():
                        raise BlenderRuntimeOperationError(
                            "blender_runtime_download_unsafe", "download partial is unsafe"
                        )
                    partial.touch(mode=0o600)
                    metadata.write_text(
                        json.dumps({"etag": response_etag}) + "\n", encoding="utf-8"
                    )
                    metadata.chmod(0o600)
                written = existing
                async for chunk in response.aiter_bytes():
                    written += len(chunk)
                    if written > spec.archive_size_bytes:
                        raise BlenderRuntimeOperationError(
                            "blender_runtime_download_size", "download exceeded trusted size"
                        )
                    await self._download_io(self._append_download_chunk, operation.id, partial,
                                            chunk, written, progress_base)
                await self._download_io(self._sync_download, partial)
                if written != spec.archive_size_bytes:
                    raise httpx.RemoteProtocolError("download ended before the trusted size")

    @staticmethod
    async def _download_io(callback: Callable[..., Any], *args: Any) -> Any:
        return await BlenderRuntimeManager._runtime_io(callback, *args)

    @staticmethod
    async def _runtime_io(callback: Callable[..., Any], *args: Any) -> Any:
        """Own started disk work through repeated cancellation before returning."""
        task = asyncio.create_task(asyncio.to_thread(callback, *args))
        return await BlenderRuntimeManager._await_owned(task)

    @staticmethod
    async def _await_owned(task: asyncio.Task[Any]) -> Any:
        """Drain an owned task even when the caller is canceled repeatedly."""
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            task.result()
            raise

    def _append_download_chunk(
        self, operation_id: str, partial: Path, chunk: bytes, written: int, progress_base: int,
    ) -> None:
        self._raise_if_canceled(operation_id)
        # Reopening must not follow a replaced symlink or create a missing file.
        fd = os.open(partial, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "ab") as output:
            facts = os.fstat(output.fileno())
            if not stat.S_ISREG(facts.st_mode) or facts.st_size != written - len(chunk):
                raise BlenderRuntimeOperationError(
                    "blender_runtime_download_unsafe", "download partial changed during transfer"
                )
            output.write(chunk)
            output.flush()
            # Publish progress only after bytes have reached the partial file.
            self.store.update_blender_runtime_operation(operation_id, bytes_done=progress_base + written)

    @staticmethod
    def _sync_download(partial: Path) -> None:
        fd = os.open(partial, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise BlenderRuntimeOperationError(
                    "blender_runtime_download_unsafe", "download partial is not a regular file"
                )
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _extract(
        archive_path: Path,
        destination: Path,
        spec: RuntimeSpec,
        cancel_requested: Callable[[], bool],
    ) -> None:
        try:
            with tarfile.open(archive_path, mode="r:xz") as archive:
                for member in archive:
                    if cancel_requested():
                        raise BlenderRuntimeOperationError(
                            "blender_runtime_operation_canceled",
                            "Blender runtime operation was canceled",
                        )
                    archive.extract(member, destination, filter="data")
        except (tarfile.TarError, OSError) as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_extract_failed", "Blender archive extraction failed"
            ) from exc

    def _raise_if_canceled(self, operation_id: str) -> None:
        if self.store.blender_runtime_operation_cancel_requested(operation_id):
            raise BlenderRuntimeOperationError(
                "blender_runtime_operation_canceled", "Blender runtime operation was canceled"
            )

    def _stage_root(self, operation_id: str) -> Path:
        return contained(
            self.resolver.managed_root,
            self.resolver.managed_root / ".staging" / operation_id,
        )

    def _web_stage_root(self, operation_id: str) -> Path:
        if self.web_pack is None:
            return self._stage_root(operation_id)
        return contained(
            self.web_pack.managed_root,
            self.web_pack.managed_root / ".staging" / operation_id,
        )

    async def _clean_stage(self, operation_id: str) -> None:
        await self._runtime_io(self._clean_stage_sync, operation_id)

    def _clean_stage_sync(self, operation_id: str) -> None:
        stages = {self._stage_root(operation_id), self._web_stage_root(operation_id)}
        for stage in stages:
            if stage.exists():
                if stage.is_symlink():
                    raise BlenderRuntimeOperationError(
                        "blender_runtime_staging_unsafe", "Blender staging root is unsafe"
                    )
                shutil.rmtree(stage)

    async def _finish_canceled(self, operation: BlenderRuntimeOperation) -> None:
        await self._runtime_io(self._finish_canceled_sync, operation)

    def _finish_canceled_sync(self, operation: BlenderRuntimeOperation) -> None:
        self._clean_stage_sync(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.CANCELED
        )

    def _ensure_managed_destination(self, destination: Path) -> None:
        if destination.is_symlink() or not destination.is_dir():
            raise BlenderRuntimeOperationError(
                "blender_runtime_destination_unsafe", "managed Blender destination is unsafe"
            )
        destination.resolve().relative_to(self.resolver.managed_root)

    @staticmethod
    def _directory_bytes(root: Path) -> int:
        if root.is_symlink() or not root.is_dir():
            return 0
        total = 0
        for directory, names, files in os.walk(root, followlinks=False):
            current = Path(directory)
            names[:] = [name for name in names if not (current / name).is_symlink()]
            for name in files:
                path = current / name
                try:
                    if not path.is_symlink() and path.is_file():
                        total += path.stat().st_size
                except OSError:
                    continue
        return total
