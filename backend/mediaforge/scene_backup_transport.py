"""Connection-scoped, path-free scene backup upload and download."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Callable
import uuid

from .paths import contained
from .scene_backup import (
    MAX_BACKUP_ARCHIVE_BYTES,
    SceneBackupCodec,
)
from .scenes import SceneError, validate_scene_owner
from .store import Store


BACKUP_TRANSFER_TTL_SEC = 10 * 60
BACKUP_TRANSFER_ROOT = "transfers"
SCENE_BACKUP_CHUNK_BYTES = 512 * 1024


@dataclass
class _Download:
    owner: str
    root: Path
    path: Path
    total_bytes: int
    sha256: str
    expires_at: float


@dataclass
class _Upload:
    owner: str
    root: Path
    path: Path
    total_bytes: int
    sha256: str
    received: int
    expires_at: float


class SceneBackupSession:
    """Own at most one ephemeral download and restore upload per connection."""

    def __init__(self, store: Store, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.codec = SceneBackupCodec(store)
        self.root = contained(self.codec.root, self.codec.root / BACKUP_TRANSFER_ROOT)
        self.clock = clock
        self._downloads: dict[str, _Download] = {}
        self._upload: tuple[str, _Upload] | None = None
        self._lock = threading.RLock()

    def initialize(self) -> None:
        """Remove only abandoned ephemeral transfers after a service restart."""
        self.codec.initialize()
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(mode=0o700)

    def open_download(self, owner: str, scene_id: str) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        with self._lock:
            self._expire()
            if self._downloads:
                raise SceneError(
                    "scene_backup_transfer_limit", "a scene backup download is already open"
                )
            handle = f"backup_{uuid.uuid4().hex}"
            root = self._new_root()
            path = contained(root, root / "scene-backup.zip")
            try:
                exported = self.codec.export(owner, scene_id, path)
            except Exception:
                shutil.rmtree(root, ignore_errors=True)
                raise
            transfer = _Download(
                owner=owner,
                root=root,
                path=path,
                total_bytes=int(exported["size_bytes"]),
                sha256=str(exported["sha256"]),
                expires_at=self.clock() + BACKUP_TRANSFER_TTL_SEC,
            )
            self._downloads[handle] = transfer
            return {
                "handle": handle,
                "filename": "media-forge-scene-backup.zip",
                "mime_type": "application/zip",
                "total_bytes": transfer.total_bytes,
                "sha256": transfer.sha256,
                "content_sha256": exported["content_sha256"],
                "revision_count": exported["revision_count"],
                "chunk_bytes": SCENE_BACKUP_CHUNK_BYTES,
                "expires_in_sec": BACKUP_TRANSFER_TTL_SEC,
            }

    def read_download(
        self,
        owner: str,
        handle: str,
        offset: object,
        length: object = SCENE_BACKUP_CHUNK_BYTES,
    ) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        with self._lock:
            self._expire()
            transfer = self._downloads.get(handle)
            if transfer is None or transfer.owner != owner:
                raise SceneError(
                    "scene_backup_handle_invalid", "scene backup download is unavailable"
                )
            if (
                isinstance(offset, bool)
                or not isinstance(offset, int)
                or isinstance(length, bool)
                or not isinstance(length, int)
                or offset < 0
                or offset >= transfer.total_bytes
                or not 1 <= length <= SCENE_BACKUP_CHUNK_BYTES
            ):
                raise SceneError(
                    "scene_backup_range_invalid", "scene backup byte range is out of bounds"
                )
            if transfer.path.is_symlink() or not transfer.path.is_file():
                raise SceneError(
                    "scene_backup_handle_invalid", "scene backup download is unavailable"
                )
            with transfer.path.open("rb") as stream:
                stream.seek(offset)
                content = stream.read(length)
            transfer.expires_at = self.clock() + BACKUP_TRANSFER_TTL_SEC
            return {
                "handle": handle,
                "offset": offset,
                "total_bytes": transfer.total_bytes,
                "base64": base64.b64encode(content).decode("ascii"),
            }

    def close_download(self, owner: str, handle: str) -> bool:
        owner = validate_scene_owner(owner)
        with self._lock:
            transfer = self._downloads.get(handle)
            if transfer is None or transfer.owner != owner:
                return False
            self._remove_download(handle, transfer)
            return True

    def begin_restore(self, owner: str, *, size: object, sha256: object) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or not 1 <= size <= MAX_BACKUP_ARCHIVE_BYTES
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(char not in "0123456789abcdef" for char in sha256)
        ):
            raise SceneError("scene_backup_upload_invalid", "scene backup declaration is invalid")
        with self._lock:
            self._expire()
            if self._upload is not None:
                raise SceneError(
                    "scene_backup_transfer_limit", "a scene backup restore is already active"
                )
            upload_id = f"backup_upload_{uuid.uuid4().hex}"
            root = self._new_root()
            path = contained(root, root / "incoming.zip")
            path.touch(mode=0o600)
            self._upload = (
                upload_id,
                _Upload(
                    owner=owner,
                    root=root,
                    path=path,
                    total_bytes=size,
                    sha256=sha256,
                    received=0,
                    expires_at=self.clock() + BACKUP_TRANSFER_TTL_SEC,
                ),
            )
            return {
                "upload_id": upload_id,
                "chunk_bytes": SCENE_BACKUP_CHUNK_BYTES,
                "expires_in_sec": BACKUP_TRANSFER_TTL_SEC,
            }

    def append_restore(
        self,
        owner: str,
        upload_id: str,
        offset: object,
        content: bytes,
        sha256: object,
    ) -> dict[str, int]:
        owner = validate_scene_owner(owner)
        with self._lock:
            self._expire()
            upload = self._require_upload(owner, upload_id)
            if (
                isinstance(offset, bool)
                or not isinstance(offset, int)
                or offset != upload.received
                or not content
                or len(content) > SCENE_BACKUP_CHUNK_BYTES
                or upload.received + len(content) > upload.total_bytes
                or not isinstance(sha256, str)
                or hashlib.sha256(content).hexdigest() != sha256
            ):
                raise SceneError(
                    "scene_backup_chunk_invalid", "scene backup upload chunk is invalid"
                )
            with upload.path.open("ab") as stream:
                stream.write(content)
            upload.received += len(content)
            upload.expires_at = self.clock() + BACKUP_TRANSFER_TTL_SEC
            return {"received": upload.received}

    def commit_restore(self, owner: str, upload_id: str) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        with self._lock:
            self._expire()
            upload = self._require_upload(owner, upload_id)
            if upload.received != upload.total_bytes:
                raise SceneError(
                    "scene_backup_upload_incomplete", "scene backup upload is incomplete"
                )
            digest = self._sha256(upload.path)
            if digest != upload.sha256:
                self._remove_upload(upload)
                raise SceneError(
                    "scene_backup_hash_changed", "scene backup upload identity changed"
                )
            try:
                return self.codec.restore(owner, upload.path)
            finally:
                self._remove_upload(upload)

    def cancel_restore(self, owner: str, upload_id: str) -> bool:
        owner = validate_scene_owner(owner)
        with self._lock:
            self._expire()
            upload = self._require_upload(owner, upload_id)
            self._remove_upload(upload)
            return True

    def cleanup(self) -> None:
        with self._lock:
            for handle, transfer in tuple(self._downloads.items()):
                self._remove_download(handle, transfer)
            if self._upload is not None:
                self._remove_upload(self._upload[1])

    def shutdown_cleanup(self) -> None:
        """Remove this session and any orphan left by a terminated connection."""
        self.cleanup()
        with self._lock:
            if not self.root.exists():
                return
            for entry in self.root.iterdir():
                if entry.is_symlink():
                    entry.unlink()
                    continue
                bounded = contained(self.root, entry)
                if bounded.is_dir():
                    shutil.rmtree(bounded)
                else:
                    bounded.unlink()

    def _expire(self) -> None:
        now = self.clock()
        for handle, transfer in tuple(self._downloads.items()):
            if transfer.expires_at <= now:
                self._remove_download(handle, transfer)
        if self._upload is not None and self._upload[1].expires_at <= now:
            self._remove_upload(self._upload[1])

    def _require_upload(self, owner: str, upload_id: str) -> _Upload:
        if (
            self._upload is None
            or self._upload[0] != upload_id
            or self._upload[1].owner != owner
        ):
            raise SceneError(
                "scene_backup_upload_invalid", "scene backup upload is unavailable"
            )
        return self._upload[1]

    def _remove_download(self, handle: str, transfer: _Download) -> None:
        self._downloads.pop(handle, None)
        shutil.rmtree(transfer.root, ignore_errors=True)

    def _remove_upload(self, upload: _Upload) -> None:
        self._upload = None
        shutil.rmtree(upload.root, ignore_errors=True)

    def _new_root(self) -> Path:
        root = contained(self.root, self.root / f"transfer_{uuid.uuid4().hex}")
        root.mkdir(mode=0o700)
        return root

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(SCENE_BACKUP_CHUNK_BYTES), b""):
                digest.update(chunk)
        return digest.hexdigest()
