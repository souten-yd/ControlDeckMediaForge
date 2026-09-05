from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import shutil
import tarfile
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
    RUNTIME_ID_PATTERN,
    BlenderRuntimeRegistryError,
    BlenderRuntimeResolver,
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
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.store = store
        self.resolver = resolver
        self.manifest_path = manifest_path.resolve()
        self.preflight_script = preflight_script.resolve()
        self.download_root = download_root.resolve()
        self.catalog_path = Path(os.path.abspath(catalog_path)) if catalog_path is not None else None
        self.transport = transport
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._guard = asyncio.Semaphore(1)

    @property
    def spec(self) -> RuntimeSpec:
        catalog = self._catalog()
        return catalog.specs[catalog.base_runtime_id]

    async def start(self) -> None:
        self.resolver.managed_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.download_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for operation_id in self.store.resumable_blender_runtime_operation_ids():
            self._spawn(operation_id)

    async def stop(self) -> None:
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
        return self._start(self._catalog().base_runtime_id, BlenderRuntimeOperationAction.INSTALL)

    def update(self) -> BlenderRuntimeOperation:
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
        return self._start(
            catalog.recommended_studio_runtime_id, BlenderRuntimeOperationAction.UPDATE
        )

    def repair(self, runtime_id: str) -> BlenderRuntimeOperation:
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
        return self._start(runtime_id, BlenderRuntimeOperationAction.REPAIR)

    def switch(self, runtime_id: str) -> BlenderRuntimeOperation:
        if runtime_id not in self._catalog().specs:
            raise BlenderRuntimeOperationError(
                "blender_runtime_not_found", "Blender runtime is not in the trusted catalog"
            )
        return self._start(runtime_id, BlenderRuntimeOperationAction.SWITCH)

    def _start(
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
        self._spawn(operation.id)
        return operation

    def cancel(self, operation_id: str) -> BlenderRuntimeOperation:
        try:
            operation = self.store.get_blender_runtime_operation(operation_id)
        except KeyError as exc:
            raise BlenderRuntimeOperationError(
                "blender_runtime_operation_not_found", "Blender runtime operation was not found"
            ) from exc
        if operation.runtime_id not in self._catalog().specs:
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
            operation = self.store.get_blender_runtime_operation(operation_id)
            if self.store.blender_runtime_operation_cancel_requested(operation_id):
                await self._finish_canceled(operation)
                return
            try:
                if operation.action == BlenderRuntimeOperationAction.SWITCH:
                    await self._switch(operation)
                else:
                    await self._install(operation)
            except asyncio.CancelledError:
                # Store.initialize() queues the journal again. Partial bytes stay
                # in the trusted download cache and must pass ETag/hash checks.
                raise
            except BlenderRuntimeOperationError as exc:
                if exc.code == "blender_runtime_operation_canceled":
                    await self._finish_canceled(operation)
                    return
                await self._clean_stage(operation.id)
                self.store.update_blender_runtime_operation(
                    operation.id,
                    state=BlenderRuntimeOperationState.FAILED,
                    error_code=exc.code,
                    error_message=str(exc)[:300],
                )
            except (BlenderRuntimeError, BlenderRuntimeRegistryError, OSError, httpx.HTTPError) as exc:
                await self._clean_stage(operation.id)
                self.store.update_blender_runtime_operation(
                    operation.id,
                    state=BlenderRuntimeOperationState.FAILED,
                    error_code="blender_runtime_install_failed",
                    error_message=str(exc)[:300],
                )
            except Exception as exc:  # noqa: BLE001 - durable isolation boundary
                logger.exception("Blender runtime operation %s failed", operation.id)
                await self._clean_stage(operation.id)
                self.store.update_blender_runtime_operation(
                    operation.id,
                    state=BlenderRuntimeOperationState.FAILED,
                    error_code="blender_runtime_install_failed",
                    error_message=str(exc)[:300],
                )

    async def _switch(self, operation: BlenderRuntimeOperation) -> None:
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
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        previous = contained(
            self.resolver.managed_root,
            self.resolver.managed_root / ".staging" / f"previous-{operation.id}",
        )
        replacing = operation.action == BlenderRuntimeOperationAction.REPAIR
        if replacing:
            self._ensure_managed_destination(destination)
            try:
                os.replace(destination, previous)
                os.replace(candidate, destination)
            except Exception:
                if previous.exists() and not destination.exists():
                    os.replace(previous, destination)
                raise
        else:
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
            if replacing and previous.exists():
                os.replace(previous, destination)
            raise
        if previous.exists():
            await asyncio.to_thread(shutil.rmtree, previous)
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

    async def _download(
        self, operation: BlenderRuntimeOperation, spec: RuntimeSpec
    ) -> Path:
        archive = contained(self.download_root, self.download_root / spec.archive_name)
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
                await self._download_attempt(operation, spec, partial, metadata)
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
        spec: RuntimeSpec,
        partial: Path,
        metadata: Path,
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
                with partial.open("ab") as output:
                    async for chunk in response.aiter_bytes():
                        self._raise_if_canceled(operation.id)
                        written += len(chunk)
                        if written > spec.archive_size_bytes:
                            raise BlenderRuntimeOperationError(
                                "blender_runtime_download_size", "download exceeded trusted size"
                            )
                        output.write(chunk)
                        # Progress and restart evidence must describe bytes that
                        # have reached the partial file, not Python's buffer.
                        output.flush()
                        self.store.update_blender_runtime_operation(
                            operation.id, bytes_done=written
                        )
                    output.flush()
                    os.fsync(output.fileno())
                if written != spec.archive_size_bytes:
                    raise httpx.RemoteProtocolError("download ended before the trusted size")

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

    async def _clean_stage(self, operation_id: str) -> None:
        stage = self._stage_root(operation_id)
        if stage.exists():
            if stage.is_symlink():
                raise BlenderRuntimeOperationError(
                    "blender_runtime_staging_unsafe", "Blender staging root is unsafe"
                )
            await asyncio.to_thread(shutil.rmtree, stage)

    async def _finish_canceled(self, operation: BlenderRuntimeOperation) -> None:
        await self._clean_stage(operation.id)
        self.store.update_blender_runtime_operation(
            operation.id, state=BlenderRuntimeOperationState.CANCELED
        )

    def _ensure_managed_destination(self, destination: Path) -> None:
        if destination.is_symlink() or not destination.is_dir():
            raise BlenderRuntimeOperationError(
                "blender_runtime_destination_unsafe", "managed Blender destination is unsafe"
            )
        destination.resolve().relative_to(self.resolver.managed_root)
