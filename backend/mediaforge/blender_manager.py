from __future__ import annotations

import asyncio
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
)

from .blender_operation import (
    TERMINAL_BLENDER_RUNTIME_OPERATION_STATES,
    BlenderRuntimeOperation,
    BlenderRuntimeOperationAction,
    BlenderRuntimeOperationError,
    BlenderRuntimeOperationState,
)
from .blender_runtime import BlenderRuntimeRegistryError, BlenderRuntimeResolver
from .paths import contained
from .store import Store


MINIMUM_DISK_MARGIN_BYTES = 1024 * 1024 * 1024
DOWNLOAD_RETRIES = 3
RUNTIME_ID = "blender-4.5.9-linux-x64"
RUNTIME_LOCATION = RUNTIME_ID
USER_AGENT = "ControlDeck-Media-Forge/Blender-Runtime-Manager"
logger = logging.getLogger("uvicorn.error")


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
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.store = store
        self.resolver = resolver
        self.manifest_path = manifest_path.resolve()
        self.preflight_script = preflight_script.resolve()
        self.download_root = download_root.resolve()
        self.transport = transport
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._guard = asyncio.Semaphore(1)

    @property
    def spec(self) -> RuntimeSpec:
        return load_spec(self.manifest_path)

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
        spec = self.spec
        return {
            "runtime_id": RUNTIME_ID,
            "version": spec.version,
            "archive_size_bytes": spec.archive_size_bytes,
            "license": spec.license,
            "source": "blender.org",
            "install_available": True,
        }

    def install(self) -> BlenderRuntimeOperation:
        active = next((
            item for item in self.store.list_blender_runtime_operations()
            if item.runtime_id == RUNTIME_ID
            and item.action == BlenderRuntimeOperationAction.INSTALL
            and item.state not in TERMINAL_BLENDER_RUNTIME_OPERATION_STATES
        ), None)
        if active is not None:
            return active
        if any(
            row.get("runtime_id") == RUNTIME_ID and row.get("state") == "ready"
            for row in self.resolver.status().get("runtimes", [])
        ):
            raise BlenderRuntimeOperationError(
                "blender_runtime_already_installed", "Blender runtime is already installed"
            )
        try:
            operation = self.store.create_blender_runtime_operation(
                RUNTIME_ID,
                self.spec.version,
                BlenderRuntimeOperationAction.INSTALL,
                bytes_total=self.spec.archive_size_bytes,
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
        if operation.runtime_id != RUNTIME_ID:
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

    async def _install(self, operation: BlenderRuntimeOperation) -> None:
        spec = self.spec
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
            self.resolver.managed_root / RUNTIME_LOCATION,
        )
        if destination.is_symlink():
            raise BlenderRuntimeOperationError(
                "blender_runtime_destination_exists", "managed Blender destination already exists"
            )
        if destination.is_dir():
            self.store.update_blender_runtime_operation(
                operation.id, state=BlenderRuntimeOperationState.PROBING,
                bytes_done=spec.archive_size_bytes,
            )
            facts = await asyncio.to_thread(
                preflight, destination / "install" / spec.executable,
                self.preflight_script, spec,
            )
            self.resolver.register_managed(
                runtime_id=RUNTIME_ID,
                version=spec.version,
                location=RUNTIME_LOCATION,
                archive_sha256=spec.archive_sha256,
            )
            await self._clean_stage(operation.id)
            self.store.update_blender_runtime_operation(
                operation.id,
                state=BlenderRuntimeOperationState.READY,
                bytes_done=spec.archive_size_bytes,
                result={
                    "runtime_id": RUNTIME_ID,
                    "version": spec.version,
                    "archive_sha256": spec.archive_sha256,
                    "preflight": facts,
                    "recovered": True,
                },
            )
            return
        if destination.exists():
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
        os.replace(candidate, destination)
        try:
            self.resolver.register_managed(
                runtime_id=RUNTIME_ID,
                version=spec.version,
                location=RUNTIME_LOCATION,
                archive_sha256=spec.archive_sha256,
            )
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
                "runtime_id": RUNTIME_ID,
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
