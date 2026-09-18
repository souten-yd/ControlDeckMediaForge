"""Immutable, bounded reference images packaged through the existing Asset graph."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Annotated, Callable, Literal
import zipfile

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .store import Store
from .domain import Provenance

PROFILE = "3d.reference_set"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PACKAGE_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
AssetId = Annotated[str, Field(pattern=r"^asset_[0-9a-f]{32}$")]
PartId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
View = Literal["front", "side", "back", "three-quarter"]
Axis = Literal["+X", "-X", "+Y", "-Y", "+Z", "-Z"]
Unit = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0, le=1)]


class ReferenceSetError(ValueError):
    pass


class ReferenceSetCanceled(ReferenceSetError):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReferenceView(StrictModel):
    view: View
    asset_id: AssetId


class ReferencePart(StrictModel):
    id: PartId
    parent_id: PartId | None = None
    description: str = Field(min_length=1, max_length=256)


class ReferenceLandmark(StrictModel):
    view: View
    part_id: PartId
    name: PartId
    uv: tuple[Unit, Unit]


class ReferenceSetSpec(StrictModel):
    schema_version: Literal["media-forge.reference-set-spec@1"] = "media-forge.reference-set-spec@1"
    name: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f/\\]+$")
    canonical_asset_id: AssetId | None = None
    views: list[ReferenceView] = Field(min_length=2, max_length=4)
    scale_m: float = Field(strict=True, allow_inf_nan=False, gt=0, le=10000)
    scale_axis: Axis = "+Y"
    forward_axis: Axis = "-Y"
    up_axis: Axis = "+Z"
    parts: list[ReferencePart] = Field(default_factory=list, max_length=64)
    landmarks: list[ReferenceLandmark] = Field(default_factory=list, max_length=256)
    origin_notes: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def coherent(self) -> ReferenceSetSpec:
        labels = [item.view for item in self.views]
        ids = [item.asset_id for item in self.views]
        if len(set(labels)) != len(labels) or not {"front", "side"} <= set(labels):
            raise ValueError("unique front and side views are required")
        if len(set(ids)) != len(ids):
            raise ValueError("each view must name a distinct image Asset")
        if self.forward_axis[-1] == self.up_axis[-1]:
            raise ValueError("forward and up axes must be orthogonal")
        parts = {part.id: part for part in self.parts}
        if len(parts) != len(self.parts):
            raise ValueError("part IDs must be unique")
        for part in self.parts:
            visited = {part.id}
            parent = part.parent_id
            while parent is not None:
                if parent not in parts or parent in visited:
                    raise ValueError("part parents must exist and form an acyclic hierarchy")
                visited.add(parent)
                parent = parts[parent].parent_id
        landmarks = set()
        for item in self.landmarks:
            key = (item.view, item.part_id, item.name)
            if item.view not in labels or item.part_id not in parts or key in landmarks:
                raise ValueError("landmarks must uniquely reference declared views and parts")
            landmarks.add(key)
        return self

    def asset_ids(self) -> list[str]:
        return sorted({item.asset_id for item in self.views} | (
            {self.canonical_asset_id} if self.canonical_asset_id else set()
        ))


class ReferenceImage(StrictModel):
    asset_id: AssetId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    provenance_id: str = Field(min_length=1, max_length=128)
    source_operation: str = Field(min_length=1, max_length=128)
    license: str = Field(min_length=1, max_length=4096)
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: int = Field(strict=True, ge=1, le=4096)
    height: int = Field(strict=True, ge=1, le=4096)


class ReferenceManifest(StrictModel):
    schema_version: Literal["media-forge.reference-set@1"] = "media-forge.reference-set@1"
    spec: ReferenceSetSpec
    images: list[ReferenceImage] = Field(min_length=2, max_length=5)
    status: Literal["needs_review"] = "needs_review"
    visual_consistency: Literal["not_reviewed"] = "not_reviewed"
    projection: Literal["unverified"] = "unverified"

    @model_validator(mode="after")
    def mapped(self) -> ReferenceManifest:
        ids = [item.asset_id for item in self.images]
        if sorted(ids) != self.spec.asset_ids():
            raise ValueError("reference images must map all declared input assets exactly once")
        if any(item.filename != f"images/{item.asset_id}.png" for item in self.images):
            raise ValueError("reference image filenames must be fixed Asset names")
        return self


class ReferenceOrigin(StrictModel):
    """Historical image IDs inside exact ZIP bytes are not remapped by scene restore."""
    profile: Literal["3d.reference_set"] = PROFILE
    asset_id: AssetId
    provenance_id: str = Field(min_length=1, max_length=128)
    parent_asset_ids: list[AssetId] = Field(min_length=2, max_length=5)
    reference_asset_hashes: dict[AssetId, Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]] = Field(max_length=5)
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def reference_origin(provenance: Provenance) -> ReferenceOrigin:
    if provenance.operation == "asset.pack" and provenance.parameters.get("profile") == PROFILE:
        return ReferenceOrigin(asset_id=provenance.asset_id, provenance_id=provenance.id,
            parent_asset_ids=provenance.parent_asset_ids,
            reference_asset_hashes=provenance.reference_asset_hashes, output_sha256=provenance.output_sha256)
    if provenance.operation == "scene.restore":
        try:
            origin = ReferenceOrigin.model_validate(provenance.parameters.get("reference_set_origin"))
        except ValidationError as exc:
            raise ReferenceSetError("restored reference origin is invalid") from exc
        if origin.output_sha256 != provenance.output_sha256:
            raise ReferenceSetError("restored reference package hash changed")
        return origin
    raise ReferenceSetError("asset is not a reference set")


def parse_spec(value: object) -> ReferenceSetSpec:
    try:
        return ReferenceSetSpec.model_validate(value)
    except ValidationError as exc:
        raise ReferenceSetError("invalid reference-set specification") from exc


def _check_cancel(canceled: Callable[[], bool]) -> None:
    if canceled():
        raise ReferenceSetCanceled("reference packaging canceled")


def build_reference_set(
    store: Store, spec: ReferenceSetSpec, output: Path, *, canceled: Callable[[], bool]
) -> ReferenceManifest:
    images: list[ReferenceImage] = []
    payloads: dict[str, bytes] = {}
    for asset_id in spec.asset_ids():
        _check_cancel(canceled)
        try:
            asset = store.get_asset(asset_id)
            provenance = store.get_provenance(asset_id)
            path = store.asset_path(asset_id)
            if (asset.mime_type not in {"image/png", "image/jpeg", "image/webp"}
                    or not 0 < asset.size_bytes <= MAX_IMAGE_BYTES
                    or path.stat().st_size != asset.size_bytes):
                raise ReferenceSetError("reference image type or size is outside its bound")
            raw = path.read_bytes()
            if (hashlib.sha256(raw).hexdigest() != asset.sha256
                    or provenance.output_sha256 != asset.sha256
                    or provenance.asset_id != asset.id or provenance.id != asset.provenance_id):
                raise ReferenceSetError("reference image hash/provenance mismatch")
            with Image.open(io.BytesIO(raw)) as source:
                if (source.format != {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}[asset.mime_type]
                        or getattr(source, "n_frames", 1) != 1
                        or max(source.size) > 4096 or source.width * source.height > 16_777_216):
                    raise ReferenceSetError("reference image geometry is outside its bound")
                oriented = ImageOps.exif_transpose(source).convert("RGBA")
                # A new image preserves pixels and strips private metadata, EXIF and dates.
                clean = Image.frombytes("RGBA", oriented.size, oriented.tobytes())
                buffer = io.BytesIO()
                clean.save(buffer, format="PNG")
                data = buffer.getvalue()
            if len(data) > MAX_IMAGE_BYTES:
                raise ReferenceSetError("normalized reference image exceeds its byte bound")
            filename = f"images/{asset_id}.png"
            images.append(ReferenceImage(
                asset_id=asset.id, source_sha256=asset.sha256, source_mime_type=asset.mime_type,
                provenance_id=provenance.id, source_operation=provenance.operation,
                license=provenance.license, filename=filename, sha256=hashlib.sha256(data).hexdigest(),
                width=clean.width, height=clean.height,
            ))
            payloads[filename] = data
        except (KeyError, OSError, UnidentifiedImageError, Image.DecompressionBombError, ValidationError) as exc:
            raise ReferenceSetError("reference image is missing or invalid") from exc
    manifest = ReferenceManifest(spec=spec, images=images)
    manifest_bytes = json.dumps(manifest.model_dump(mode="json"), sort_keys=True,
                                ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ReferenceSetError("reference manifest exceeds its byte bound")
    _check_cancel(canceled)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for filename, data in [("manifest.json", manifest_bytes), *sorted(payloads.items())]:
            _check_cancel(canceled)
            info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, data)
    _check_cancel(canceled)
    if output.stat().st_size > MAX_PACKAGE_BYTES:
        raise ReferenceSetError("reference package exceeds its byte bound")
    return manifest


def read_reference_set(store: Store, asset_id: str) -> ReferenceManifest:
    """Verify a pinned package without extracting any archive paths."""
    try:
        asset = store.get_asset(asset_id)
        provenance = store.get_provenance(asset_id)
        origin = reference_origin(provenance)
        path = store.asset_path(asset_id)
        if (asset.mime_type != "application/zip" or not 0 < asset.size_bytes <= MAX_PACKAGE_BYTES
                or path.stat().st_size != asset.size_bytes
                or provenance.asset_id != asset.id or provenance.id != asset.provenance_id
                or provenance.output_sha256 != asset.sha256):
            raise ReferenceSetError("asset is not a verified reference set")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != asset.sha256:
            raise ReferenceSetError("reference package hash mismatch")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if (not 3 <= len(entries) <= 6 or len({item.filename for item in entries}) != len(entries)
                    or any(item.compress_type != zipfile.ZIP_STORED or item.flag_bits & 1
                           or item.file_size > MAX_IMAGE_BYTES for item in entries)
                    or archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES):
                raise ReferenceSetError("reference package entries exceed their bounds")
            manifest = ReferenceManifest.model_validate_json(archive.read("manifest.json"))
            if ({item.filename for item in entries} != {"manifest.json", *(i.filename for i in manifest.images)}
                    or sorted(origin.parent_asset_ids) != manifest.spec.asset_ids()
                    or provenance.parent_asset_ids != asset.parent_asset_ids
                    or origin.reference_asset_hashes != {i.asset_id: i.source_sha256 for i in manifest.images}):
                raise ReferenceSetError("reference package lineage mismatch")
            for item in manifest.images:
                data = archive.read(item.filename)
                if hashlib.sha256(data).hexdigest() != item.sha256:
                    raise ReferenceSetError("reference package image hash mismatch")
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != "PNG" or image.size != (item.width, item.height) or image.n_frames != 1:
                        raise ReferenceSetError("reference package image geometry mismatch")
                    image.verify()
        return manifest
    except (KeyError, OSError, ValueError, zipfile.BadZipFile, Image.DecompressionBombError) as exc:
        if isinstance(exc, ReferenceSetError):
            raise
        raise ReferenceSetError("reference package is missing or invalid") from exc
