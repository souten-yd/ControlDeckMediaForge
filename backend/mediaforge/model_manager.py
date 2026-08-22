from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import httpx

from .models import (
    ModelDescriptor,
    ModelOperation,
    ModelOperationAction,
    ModelOperationError,
    ModelOperationState,
    ModelOwnership,
    ModelRegistry,
    ModelRegistryError,
    ModelSource,
)
from .paths import contained
from .store import Store


CHUNK_BYTES = 4 * 1024 * 1024
PROGRESS_BYTES = 16 * 1024 * 1024
MINIMUM_DISK_MARGIN_BYTES = 1024 * 1024 * 1024
MAX_MANAGED_MODEL_DOWNLOAD_BYTES = 32_000_000_000
DOWNLOAD_RETRIES = 5
logger = logging.getLogger("uvicorn.error")


class ModelOperationManager:
    """Durable, catalog-only installer for Media-Forge-owned model snapshots."""

    def __init__(
        self,
        store: Store,
        *,
        model_manifest: Path,
        catalog_manifest: Path,
        model_store_root: Path,
        hf_home: Path,
        model_in_use: Callable[[str], bool] | None = None,
        download_origin: str = "https://huggingface.co",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.store = store
        self.model_manifest = model_manifest
        self.catalog_manifest = catalog_manifest
        self.model_store_root = model_store_root.resolve()
        self.hf_home = hf_home.resolve()
        self.model_in_use = model_in_use or (lambda _model_id: False)
        self.download_origin = download_origin.rstrip("/")
        self.transport = transport
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._guard = asyncio.Semaphore(1)

    async def start(self) -> None:
        self.model_store_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._download_root().mkdir(mode=0o700, parents=True, exist_ok=True)
        for operation_id in self.store.resumable_model_operation_ids():
            self._spawn(operation_id)

    async def stop(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def catalog(self) -> dict[str, object]:
        models = self._registry().all()
        return {
            "items": [self._catalog_item(model) for model in models],
            "storage": self.storage_summary(),
            "management_available": True,
        }

    def storage_summary(self) -> dict[str, int]:
        probe = self.model_store_root if self.model_store_root.exists() else self.model_store_root.parent
        usage = shutil.disk_usage(probe)
        return {
            "managed_bytes": self._directory_bytes(self.model_store_root / "hub"),
            "free_bytes": usage.free,
            "total_bytes": usage.total,
        }

    def install(self, model_id: str, *, license_acceptance: str | None = None) -> ModelOperation:
        active = self._active_operation(model_id, ModelOperationAction.INSTALL)
        if active is not None:
            return active
        model = self._model(model_id)
        if model.installed:
            code = "external_model_owned" if model.ownership == ModelOwnership.EXTERNAL else "model_already_installed"
            raise ModelOperationError(code, "model is already installed")
        if model.ownership != ModelOwnership.MANAGED:
            raise ModelOperationError(
                "external_model_owned", "external model must be installed by its runtime owner"
            )
        if model.source is None or model.source.kind != "huggingface":
            raise ModelOperationError("model_not_found", "model has no supported catalog source")
        if model.approx_download_bytes >= MAX_MANAGED_MODEL_DOWNLOAD_BYTES:
            raise ModelOperationError(
                "model_too_large", "managed model download must be smaller than 32 GB"
            )
        if model.gated and license_acceptance != model.license_acceptance_id:
            raise ModelOperationError(
                "model_gated", "the exact catalog license must be accepted before download"
            )
        operation = self.store.create_model_operation(
            model.model_id,
            ModelOperationAction.INSTALL,
            bytes_total=model.approx_download_bytes,
        )
        self._spawn(operation.id)
        return operation

    def remove(self, model_id: str) -> ModelOperation:
        active = self._active_operation(model_id, ModelOperationAction.REMOVE)
        if active is not None:
            return active
        model = self._model(model_id)
        if not model.installed:
            raise ModelOperationError("model_not_found", "model is not installed")
        if model.ownership != ModelOwnership.MANAGED or not model.removable:
            raise ModelOperationError("external_model_owned", "external model must be managed at its source")
        if self.model_in_use(model.model_id):
            raise ModelOperationError("model_in_use", "model is held by a running job")
        operation = self.store.create_model_operation(
            model.model_id,
            ModelOperationAction.REMOVE,
            bytes_total=self._directory_bytes(self._repo_root(model)),
        )
        self._spawn(operation.id)
        return operation

    def cancel(self, operation_id: str) -> ModelOperation:
        return self.store.request_model_operation_cancel(operation_id)

    def _spawn(self, operation_id: str) -> None:
        current = self._tasks.get(operation_id)
        if current is not None and not current.done():
            return
        task = asyncio.create_task(self._run(operation_id), name=f"model-operation-{operation_id}")
        self._tasks[operation_id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(operation_id, None))

    def _active_operation(
        self,
        model_id: str,
        action: ModelOperationAction,
    ) -> ModelOperation | None:
        return next(
            (
                item for item in self.store.list_model_operations()
                if item.model_id == model_id
                and item.action == action
                and item.state not in {
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                }
            ),
            None,
        )

    async def _run(self, operation_id: str) -> None:
        async with self._guard:
            operation = self.store.get_model_operation(operation_id)
            if self.store.model_operation_cancel_requested(operation_id):
                await self._finish_canceled(operation)
                return
            try:
                model = self._model(operation.model_id)
                self.store.update_model_operation(operation.id, state=ModelOperationState.PREFLIGHT)
                if operation.action == ModelOperationAction.INSTALL:
                    await self._install(operation, model)
                else:
                    await self._remove(operation, model)
            except asyncio.CancelledError:
                # Service shutdown preserves partial files and the durable state;
                # Store.initialize() returns it to queued on the next start.
                raise
            except ModelOperationError as exc:
                if exc.code == "model_operation_canceled":
                    await self._finish_canceled(operation)
                    return
                await self._clean_operation(operation.id)
                self.store.update_model_operation(
                    operation.id,
                    state=ModelOperationState.FAILED,
                    error_code=exc.code,
                    error_message=str(exc)[:300],
                )
            except (OSError, httpx.HTTPError, ModelRegistryError) as exc:
                await self._clean_operation(operation.id)
                self.store.update_model_operation(
                    operation.id,
                    state=ModelOperationState.FAILED,
                    error_code="model_download_failed" if operation.action == ModelOperationAction.INSTALL
                    else "model_remove_failed",
                    error_message=str(exc)[:300],
                )
            except Exception as exc:  # noqa: BLE001 - durable final isolation boundary
                logger.exception("model operation %s failed unexpectedly", operation.id)
                await self._clean_operation(operation.id)
                self.store.update_model_operation(
                    operation.id,
                    state=ModelOperationState.FAILED,
                    error_code="model_download_failed" if operation.action == ModelOperationAction.INSTALL
                    else "model_remove_failed",
                    error_message=str(exc)[:300],
                )

    async def _install(self, operation: ModelOperation, model: ModelDescriptor) -> None:
        required = model.approx_download_bytes + max(
            MINIMUM_DISK_MARGIN_BYTES, model.approx_download_bytes // 10
        )
        if self.storage_summary()["free_bytes"] < required:
            raise ModelOperationError("insufficient_disk", "managed model store has insufficient free space")
        if self._repo_root(model).exists() or self._repo_root(model).is_symlink():
            raise ModelOperationError("model_verify_failed", "managed destination already exists")

        operation_root = self._operation_root(operation.id)
        files_root = contained(operation_root, operation_root / "files")
        files_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        files = self._download_files(model)
        completed = sum(
            (files_root / relative).stat().st_size
            for relative, _size, _digest, _source in files
            if (files_root / relative).is_file()
        )
        self.store.update_model_operation(
            operation.id, state=ModelOperationState.DOWNLOADING, bytes_done=completed
        )
        headers = {"Accept-Encoding": "identity"}
        token = os.environ.get("HF_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(
            transport=self.transport,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=120.0),
            headers=headers,
        ) as client:
            # Probe one small catalog file first so authorization/gating fails
            # before any large weight transfer begins. Remaining files are
            # intentionally sequential to favor stable local installation.
            first, *remaining = files
            await self._download_with_retry(
                client, operation, model, files_root, first[0], first[1], first[3]
            )
            for entry in remaining:
                await self._download_with_retry(
                    client, operation, model, files_root, entry[0], entry[1], entry[3]
                )

        self._raise_if_canceled(operation.id)
        self.store.update_model_operation(operation.id, state=ModelOperationState.VERIFYING)
        repo_stage = contained(operation_root, operation_root / "repository")
        blobs = contained(repo_stage, repo_stage / "blobs")
        snapshot = contained(repo_stage, repo_stage / "snapshots" / model.revision)
        blobs.mkdir(mode=0o700, parents=True, exist_ok=True)
        snapshot.mkdir(mode=0o700, parents=True, exist_ok=True)
        for relative, expected_size, expected_digest, _source in files:
            source = contained(files_root, files_root / relative)
            if not source.is_file() or source.stat().st_size <= 0:
                raise ModelOperationError("model_verify_failed", f"download is incomplete: {relative}")
            if expected_size is not None and source.stat().st_size != expected_size:
                raise ModelOperationError("model_verify_failed", f"download size differs: {relative}")
            digest = await asyncio.to_thread(self._sha256, source)
            if expected_digest is not None and digest != expected_digest:
                raise ModelOperationError("model_verify_failed", f"download hash differs: {relative}")
            blob = contained(blobs, blobs / digest)
            if blob.exists():
                source.unlink()
            else:
                os.replace(source, blob)
            link = contained(snapshot, snapshot / relative)
            link.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            link.symlink_to(os.path.relpath(blob, link.parent))

        self._raise_if_canceled(operation.id)
        self.store.update_model_operation(operation.id, state=ModelOperationState.INSTALLING)
        destination = self._repo_root(model)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(repo_stage, destination)
        try:
            installed = self._registry().all()
            if not any(item.model_id == model.model_id and item.installed for item in installed):
                raise ModelOperationError(
                    "model_verify_failed", "installed snapshot did not pass registry verification"
                )
        except (ModelOperationError, ModelRegistryError):
            self._ensure_managed_directory(destination)
            await asyncio.to_thread(shutil.rmtree, destination)
            raise
        await self._clean_operation(operation.id)
        self.store.update_model_operation(
            operation.id,
            state=ModelOperationState.READY,
            bytes_done=operation.bytes_total,
        )

    async def _download_file(
        self,
        client: httpx.AsyncClient,
        operation: ModelOperation,
        model: ModelDescriptor,
        files_root: Path,
        relative: str,
        expected_size: int | None,
        source: ModelSource,
    ) -> None:
        target = contained(files_root, files_root / relative)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        existing = target.stat().st_size if target.is_file() else 0
        if expected_size is not None and existing == expected_size:
            return
        if expected_size is not None and existing > expected_size:
            target.unlink()
            existing = 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        url = (
            f"{self.download_origin}/{quote(source.repo_id, safe='/')}/resolve/"
            f"{source.revision}/{quote(relative, safe='/')}?download=true"
        )
        async with client.stream("GET", url, headers=headers) as response:
            if response.status_code in {401, 403}:
                raise ModelOperationError("model_gated", "model source requires authorization")
            if existing and response.status_code == 416:
                content_range = response.headers.get("content-range", "")
                match = re.fullmatch(r"bytes \*/([0-9]+)", content_range)
                if match is not None and int(match.group(1)) == existing:
                    self.store.update_model_operation(
                        operation.id, bytes_done=self._partial_bytes(files_root)
                    )
                    return
                target.unlink(missing_ok=True)
                return await self._download_file(
                    client, operation, model, files_root, relative, expected_size, source
                )
            if response.status_code not in ({206} if existing else {200}):
                if existing and response.status_code == 200:
                    target.unlink(missing_ok=True)
                    return await self._download_file(
                        client, operation, model, files_root, relative, expected_size, source
                    )
                raise ModelOperationError("model_download_failed", f"source returned HTTP {response.status_code}")
            mode = "ab" if existing else "wb"
            reported = existing
            with target.open(mode) as stream:
                async for chunk in response.aiter_bytes():
                    self._raise_if_canceled(operation.id)
                    stream.write(chunk)
                    stream.flush()
                    existing += len(chunk)
                    if existing - reported >= PROGRESS_BYTES:
                        reported = existing
                        self.store.update_model_operation(
                            operation.id,
                            bytes_done=self._partial_bytes(files_root),
                        )
                os.fsync(stream.fileno())
        self.store.update_model_operation(operation.id, bytes_done=self._partial_bytes(files_root))

    async def _download_with_retry(
        self,
        client: httpx.AsyncClient,
        operation: ModelOperation,
        model: ModelDescriptor,
        files_root: Path,
        relative: str,
        expected_size: int | None,
        source: ModelSource,
    ) -> None:
        for attempt in range(DOWNLOAD_RETRIES):
            try:
                await self._download_file(
                    client, operation, model, files_root, relative, expected_size, source
                )
                return
            except httpx.HTTPError as exc:
                self._raise_if_canceled(operation.id)
                if attempt + 1 == DOWNLOAD_RETRIES:
                    raise ModelOperationError(
                        "model_download_failed",
                        f"download connection failed after {DOWNLOAD_RETRIES} attempts: {relative}",
                    ) from exc
                await asyncio.sleep(min(2 ** attempt, 8))

    async def _remove(self, operation: ModelOperation, model: ModelDescriptor) -> None:
        if model.ownership != ModelOwnership.MANAGED or not model.removable:
            raise ModelOperationError("external_model_owned", "external model must be managed at its source")
        if self.model_in_use(model.model_id):
            raise ModelOperationError("model_in_use", "model is held by a running job")
        destination = self._repo_root(model)
        self._ensure_managed_directory(destination)
        self.store.update_model_operation(operation.id, state=ModelOperationState.INSTALLING)
        await asyncio.to_thread(shutil.rmtree, destination)
        if any(item.model_id == model.model_id and item.installed for item in self._registry().all()):
            raise ModelOperationError("model_remove_failed", "model remained installed after removal")
        self.store.update_model_operation(
            operation.id, state=ModelOperationState.READY, bytes_done=operation.bytes_total
        )

    async def _finish_canceled(self, operation: ModelOperation) -> None:
        await self._clean_operation(operation.id)
        self.store.update_model_operation(operation.id, state=ModelOperationState.CANCELED)

    def _raise_if_canceled(self, operation_id: str) -> None:
        if self.store.model_operation_cancel_requested(operation_id):
            raise ModelOperationError("model_operation_canceled", "model operation was canceled")

    async def _clean_operation(self, operation_id: str) -> None:
        root = self._operation_root(operation_id)
        if root.exists():
            self._ensure_managed_directory(root, within=self._download_root())
            await asyncio.to_thread(shutil.rmtree, root)

    def _registry(self) -> ModelRegistry:
        return ModelRegistry.load(
            self.model_manifest,
            catalog_manifest=self.catalog_manifest,
            hf_home=self.hf_home,
            model_store_root=self.model_store_root,
        )

    def _model(self, model_id: str) -> ModelDescriptor:
        try:
            return next(item for item in self._registry().all() if item.model_id == model_id)
        except StopIteration as exc:
            raise ModelOperationError("model_not_found", "model is not in the trusted catalog") from exc
        except ModelRegistryError as exc:
            raise ModelOperationError("model_not_found", "model registry is unavailable") from exc

    def _catalog_item(self, model: ModelDescriptor) -> dict[str, object]:
        source = model.source
        return {
            "model_id": model.model_id,
            "display_name": model.display_name,
            "domains": list(model.domains),
            "media_types": list(model.media_types),
            "description": model.description,
            "approx_download_bytes": model.approx_download_bytes,
            "reclaimable_bytes": self._directory_bytes(self._repo_root(model))
            if model.ownership == ModelOwnership.MANAGED and model.installed else 0,
            "profile_reference_count": 0,
            "source": {
                "kind": source.kind,
                "repo_id": source.repo_id,
                "revision": source.revision,
            } if source is not None else None,
            "ownership": model.ownership,
            "installed": model.installed,
            "healthy": model.healthy,
            "removable": model.removable,
            "state": model.state,
            "supports_lora": model.supports_lora,
            "max_references": model.max_references,
            "reference_roles": list(model.reference_roles),
            "supports_reference_strength": model.supports_reference_strength,
            "recommended_profiles": list(model.recommended_profiles),
            "gated": model.gated,
            "license_acceptance_id": model.license_acceptance_id,
            "license": model.license,
            "license_notice": model.license_notice,
            "runtime_adapter": model.runtime_adapter,
            "hardware_backends": list(model.hardware_backends),
            "capabilities": list(model.capabilities),
            "weights_hash": model.weights_hash,
            "measurement_confidence": model.measurement_confidence,
            "measured_vram_bytes": model.measured_vram_bytes,
            "measured_runtime_sec": model.measured_runtime_sec,
        }

    def _download_files(
        self, model: ModelDescriptor
    ) -> list[tuple[str, int | None, str | None, ModelSource]]:
        if model.source is None:
            raise ModelOperationError("model_not_found", "catalog source disappeared")
        weights = {
            item.path: (item.size_bytes, item.sha256, item.source or model.source)
            for item in model.weights
        }
        paths = list(dict.fromkeys((*model.required_files, *weights)))
        return [
            (path, *(weights.get(path, (None, None, model.source))))
            for path in paths
        ]

    def _download_root(self) -> Path:
        try:
            return contained(self.model_store_root, self.model_store_root / ".downloads")
        except ValueError as exc:
            raise ModelOperationError("model_verify_failed", "download root escapes the model store") from exc

    def _operation_root(self, operation_id: str) -> Path:
        if not operation_id.startswith("modelop_") or not operation_id.removeprefix("modelop_").isalnum():
            raise ModelOperationError("model_not_found", "model operation identity is invalid")
        try:
            return contained(self._download_root(), self._download_root() / operation_id)
        except ValueError as exc:
            raise ModelOperationError("model_verify_failed", "operation path escapes the download root") from exc

    def _repo_root(self, model: ModelDescriptor) -> Path:
        name = "models--" + model.model_id.replace("/", "--")
        try:
            return contained(self.model_store_root, self.model_store_root / "hub" / name)
        except ValueError as exc:
            raise ModelOperationError("model_verify_failed", "model repository escapes the managed root") from exc

    def _ensure_managed_directory(self, path: Path, *, within: Path | None = None) -> None:
        root = (within or self.model_store_root).resolve(strict=True)
        if path.is_symlink():
            raise ModelOperationError("model_verify_failed", "managed path is a symlink")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_dir():
            raise ModelOperationError("model_verify_failed", "managed path escapes its root")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _directory_bytes(path: Path) -> int:
        if not path.exists() or path.is_symlink():
            return 0
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink())

    @staticmethod
    def _partial_bytes(files_root: Path) -> int:
        if not files_root.exists():
            return 0
        return sum(item.stat().st_size for item in files_root.rglob("*") if item.is_file())
