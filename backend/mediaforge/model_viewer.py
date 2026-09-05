"""Connection-scoped, path-free delivery of validated GLB viewer bytes."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import threading
from typing import Any
import uuid
import zipfile

from PIL import Image, UnidentifiedImageError

from .glb import GlbValidationError, MAX_GLB_BYTES, validate_glb_path
from .paths import contained
from .store import Store


MODEL_CHUNK_BYTES = 512 * 1024
MAX_OPEN_MODELS = 2
PROJECT_ENTRIES = ["asset.glb", "manifest.json", "preview.png"]
PROJECT_MANIFEST_BYTES = 1024 * 1024
PROJECT_PREVIEW_BYTES = 16 * 1024 * 1024
MAX_TEXTURE_SIDE = 8_192
MAX_TEXTURE_PIXELS = 67_108_864


class ModelViewerError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class ModelViewerSession:
    """Prepare at most two immutable models and clean staging with the connection."""

    def __init__(self, store: Store):
        self.store = store
        self._models: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def open(self, asset_id: str) -> dict[str, Any]:
        with self._lock:
            return self._open(asset_id)

    def _open(self, asset_id: str) -> dict[str, Any]:
        try:
            asset = self.store.get_asset(asset_id)
        except KeyError as exc:
            raise ModelViewerError("model_viewer_not_found", "3D model asset is unavailable") from exc
        if asset.mime_type not in {"model/gltf-binary", "application/zip"}:
            raise ModelViewerError("model_viewer_unsupported", "asset is not a supported 3D model")
        if len(self._models) >= MAX_OPEN_MODELS:
            raise ModelViewerError("model_viewer_limit", "too many model viewer handles are open")

        root: Path | None = None
        source = self.store.asset_path(asset_id)
        try:
            if asset.mime_type == "application/zip":
                root = Path(tempfile.mkdtemp(prefix="workspace-model-", dir=self.store.work_dir))
                model = contained(root, root / "model.glb")
                self._extract_project(source, model)
                source_kind = "project_3d"
            else:
                model = source
                source_kind = "model_3d"
            validation = validate_glb_path(model, root or self.store.asset_dir)
            validation["viewer_memory"] = self._validate_browser_memory(model)
            digest = self._sha256(model)
        except ModelViewerError:
            if root is not None:
                shutil.rmtree(root, ignore_errors=True)
            raise
        except (OSError, zipfile.BadZipFile, GlbValidationError, UnicodeDecodeError,
                json.JSONDecodeError, KeyError) as exc:
            if root is not None:
                shutil.rmtree(root, ignore_errors=True)
            raise ModelViewerError("model_viewer_invalid", "3D model failed viewer validation") from exc

        handle = f"modelview_{uuid.uuid4().hex}"
        self._models[handle] = {
            "asset_id": asset_id,
            "path": model,
            "root": root,
            "total_bytes": model.stat().st_size,
            "sha256": digest,
        }
        return {
            "handle": handle,
            "asset_id": asset_id,
            "mime_type": "model/gltf-binary",
            "filename": "asset.glb" if source_kind == "project_3d" else asset.suggested_filename,
            "source_kind": source_kind,
            "total_bytes": model.stat().st_size,
            "sha256": digest,
            "validation": validation,
            "chunk_bytes": MODEL_CHUNK_BYTES,
        }

    def read(self, handle: str, offset: object, length: object = MODEL_CHUNK_BYTES) -> dict[str, Any]:
        with self._lock:
            return self._read(handle, offset, length)

    def _read(self, handle: str, offset: object, length: object) -> dict[str, Any]:
        prepared = self._models.get(handle)
        if prepared is None:
            raise ModelViewerError("model_viewer_handle_invalid", "viewer handle is unavailable")
        total = int(prepared["total_bytes"])
        if (
            isinstance(offset, bool) or not isinstance(offset, int)
            or isinstance(length, bool) or not isinstance(length, int)
            or offset < 0 or offset >= total or not 1 <= length <= MODEL_CHUNK_BYTES
        ):
            raise ModelViewerError("model_viewer_range_invalid", "viewer byte range is out of bounds")
        path = Path(prepared["path"])
        if path.is_symlink() or not path.is_file():
            raise ModelViewerError("model_viewer_handle_invalid", "prepared model is unavailable")
        with path.open("rb") as stream:
            stream.seek(offset)
            content = stream.read(length)
        return {
            "handle": handle,
            "offset": offset,
            "total_bytes": total,
            "base64": base64.b64encode(content).decode("ascii"),
        }

    def close(self, handle: str) -> bool:
        with self._lock:
            return self._close(handle)

    def _close(self, handle: str) -> bool:
        prepared = self._models.pop(handle, None)
        if prepared is None:
            return False
        root = prepared.get("root")
        if isinstance(root, Path) and root.exists():
            shutil.rmtree(root)
        return True

    def cleanup(self) -> None:
        with self._lock:
            for handle in tuple(self._models):
                self._close(handle)

    def _extract_project(self, source: Path, destination: Path) -> None:
        if source.is_symlink() or not source.is_file():
            raise ModelViewerError("model_viewer_invalid", "3D project package is unavailable")
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if [info.filename for info in infos] != PROJECT_ENTRIES:
                raise ModelViewerError("model_viewer_invalid", "3D project entries are invalid")
            if any(info.is_dir() or info.flag_bits & 0x1 for info in infos):
                raise ModelViewerError("model_viewer_invalid", "3D project entry is unsafe")
            by_name = {info.filename: info for info in infos}
            if (
                not 1 <= by_name["asset.glb"].file_size <= MAX_GLB_BYTES
                or by_name["manifest.json"].file_size > PROJECT_MANIFEST_BYTES
                or by_name["preview.png"].file_size > PROJECT_PREVIEW_BYTES
            ):
                raise ModelViewerError("model_viewer_invalid", "3D project exceeds viewer bounds")
            manifest_content = archive.read("manifest.json")
            manifest = json.loads(manifest_content.decode("utf-8"))
            if not isinstance(manifest, dict):
                raise ModelViewerError("model_viewer_invalid", "3D project manifest is invalid")
            record = manifest.get("asset")
            if (
                manifest.get("schema_version") != "media-forge.3d-project@1"
                or manifest.get("profile") != "3d.project.glb"
                or not isinstance(record, dict)
                or record.get("filename") != "asset.glb"
                or record.get("mime_type") != "model/gltf-binary"
                or record.get("size_bytes") != by_name["asset.glb"].file_size
            ):
                raise ModelViewerError("model_viewer_invalid", "3D project manifest is invalid")
            digest = hashlib.sha256()
            written = 0
            with archive.open("asset.glb") as incoming, destination.open("xb") as outgoing:
                while True:
                    chunk = incoming.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_GLB_BYTES:
                        raise ModelViewerError("model_viewer_invalid", "3D project GLB exceeds its bound")
                    digest.update(chunk)
                    outgoing.write(chunk)
            destination.chmod(0o600)
            if written != record["size_bytes"] or digest.hexdigest() != record.get("sha256"):
                raise ModelViewerError("model_viewer_invalid", "3D project GLB identity changed")

    @staticmethod
    def _validate_browser_memory(path: Path) -> dict[str, int]:
        content = path.read_bytes()
        json_length = struct.unpack_from("<I", content, 12)[0]
        document = json.loads(content[20 : 20 + json_length].decode("utf-8"))
        binary_offset = 20 + json_length + 8
        binary = content[binary_offset:] if binary_offset <= len(content) else b""
        views = document.get("bufferViews", [])
        pixels = 0
        maximum_side = 0
        for entry in document.get("images", []):
            mime_type = entry["mimeType"]
            if mime_type == "image/ktx2":
                raise ModelViewerError(
                    "model_viewer_extension_unsupported", "KTX2 viewer decoding is not installed"
                )
            view = views[entry["bufferView"]]
            start = view.get("byteOffset", 0)
            image_bytes = binary[start : start + view["byteLength"]]
            try:
                with Image.open(io.BytesIO(image_bytes)) as image:
                    width, height = image.size
                    expected = {
                        "image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP",
                    }[mime_type]
                    if image.format != expected:
                        raise ModelViewerError(
                            "model_viewer_invalid", "embedded texture type differs from its declaration"
                        )
            except (KeyError, OSError, UnidentifiedImageError) as exc:
                raise ModelViewerError(
                    "model_viewer_invalid", "embedded texture cannot be inspected"
                ) from exc
            maximum_side = max(maximum_side, width, height)
            pixels += width * height
            if maximum_side > MAX_TEXTURE_SIDE or pixels > MAX_TEXTURE_PIXELS:
                raise ModelViewerError(
                    "model_viewer_memory_bound", "embedded textures exceed the browser memory bound"
                )
        return {
            "texture_pixels": pixels,
            "maximum_texture_side": maximum_side,
            "estimated_gpu_bytes": len(content) + pixels * 4,
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
