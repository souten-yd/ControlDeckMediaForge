"""Exact, bounded backups for owner-scoped immutable scenes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
from typing import Annotated, Any, BinaryIO, Literal
import uuid
import zipfile

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from . import __version__
from .domain import Asset, Job, JobRequest, JobStatus, Provenance
from .glb import GlbValidationError, validate_glb_path
from .paths import contained
from .scenes import SceneDependency, SceneDocument, SceneError, SceneRevision, validate_scene_owner
from .store import Store, utc_now


BACKUP_SCHEMA = "media-forge.scene-backup@1"
BACKUP_CHUNK_BYTES = 1024 * 1024
MAX_BACKUP_MANIFEST_BYTES = 1024 * 1024
MAX_BACKUP_MEMBERS = 1025
MAX_BACKUP_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_BACKUP_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_BLEND_BYTES = 256 * 1024 * 1024
MAX_GLB_BYTES = 64 * 1024 * 1024


BackupPath = Annotated[str, Field(min_length=1, max_length=256)]


class SceneBackupEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: BackupPath
    kind: Literal["source", "preview", "dependency"]
    asset: Asset
    provenance: Provenance
    revision_ids: list[str] = Field(min_length=1, max_length=1000)
    size_bytes: int = Field(ge=1, le=MAX_BACKUP_UNCOMPRESSED_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_asset_identity(self) -> "SceneBackupEntry":
        if (
            self.asset.id != self.provenance.asset_id
            or self.asset.provenance_id != self.provenance.id
            or self.asset.parent_asset_ids != self.provenance.parent_asset_ids
            or self.asset.size_bytes != self.size_bytes
            or self.asset.sha256 != self.sha256
            or self.provenance.output_sha256 != self.sha256
        ):
            raise ValueError("backup entry metadata differs")
        _safe_member(self.path)
        return self


class SceneBackupManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["media-forge.scene-backup@1"] = BACKUP_SCHEMA
    created_at: str
    document: SceneDocument
    revisions: list[SceneRevision] = Field(min_length=1, max_length=1000)
    entries: list[SceneBackupEntry] = Field(min_length=2, max_length=MAX_BACKUP_MEMBERS - 1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_snapshot(self) -> "SceneBackupManifest":
        if len({entry.path for entry in self.entries}) != len(self.entries):
            raise ValueError("backup entry names are not unique")
        if self.document.revision_count != len(self.revisions):
            raise ValueError("backup revision count differs")
        previous: str | None = None
        expected_paths: list[str] = []
        dependency_revisions: dict[str, list[str]] = {}
        for sequence, revision in enumerate(self.revisions, 1):
            if (
                revision.scene_id != self.document.id
                or revision.sequence != sequence
                or revision.parent_revision_id != previous
            ):
                raise ValueError("backup revision chain differs")
            previous = revision.id
            expected_paths.extend(
                [
                    f"revisions/{revision.id}/scene.blend",
                    f"revisions/{revision.id}/preview.glb",
                ]
            )
            for dependency in revision.dependencies:
                dependency_revisions.setdefault(dependency.asset_id, []).append(revision.id)
        if self.document.current_revision_id != self.revisions[-1].id:
            raise ValueError("backup current revision differs")
        expected_paths.extend(
            f"dependencies/{asset_id}/asset" for asset_id in sorted(dependency_revisions)
        )
        if [entry.path for entry in self.entries] != expected_paths:
            raise ValueError("backup entry order differs")

        by_path = {entry.path: entry for entry in self.entries}
        for revision in self.revisions:
            source = by_path[f"revisions/{revision.id}/scene.blend"]
            preview = by_path[f"revisions/{revision.id}/preview.glb"]
            if (
                source.kind != "source"
                or source.asset.id != revision.source_asset_id
                or source.asset.mime_type != "application/x-blender"
                or source.revision_ids != [revision.id]
                or preview.kind != "preview"
                or preview.asset.id != revision.preview_asset_id
                or preview.asset.mime_type != "model/gltf-binary"
                or preview.revision_ids != [revision.id]
            ):
                raise ValueError("backup revision entry differs")
        for asset_id, revision_ids in dependency_revisions.items():
            dependency = by_path[f"dependencies/{asset_id}/asset"]
            if (
                dependency.kind != "dependency"
                or dependency.asset.id != asset_id
                or dependency.revision_ids != revision_ids
            ):
                raise ValueError("backup dependency entry differs")
            expected_hashes = {
                item.sha256
                for revision in self.revisions
                for item in revision.dependencies
                if item.asset_id == asset_id
            }
            if expected_hashes != {dependency.sha256}:
                raise ValueError("backup dependency hash differs")
        return self


def _safe_member(value: str) -> PurePosixPath:
    if "\\" in value or value.startswith("/") or "\x00" in value:
        raise ValueError("backup member path is unsafe")
    path = PurePosixPath(value)
    if not value or str(path) != value or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("backup member path is unsafe")
    return path


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BACKUP_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_verified(source: BinaryIO, output: BinaryIO, entry: SceneBackupEntry) -> None:
    digest = hashlib.sha256()
    written = 0
    while True:
        chunk = source.read(BACKUP_CHUNK_BYTES)
        if not chunk:
            break
        written += len(chunk)
        if written > entry.size_bytes:
            raise SceneError("scene_backup_hash_changed", "scene backup asset size changed")
        digest.update(chunk)
        output.write(chunk)
    if written != entry.size_bytes or digest.hexdigest() != entry.sha256:
        raise SceneError("scene_backup_hash_changed", "scene backup asset identity changed")


def _manifest_fingerprint(value: SceneBackupManifest) -> str:
    payload = value.model_dump(mode="json", exclude={"content_sha256"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    info.create_system = 3
    return info


class SceneBackupCodec:
    """Write and restore scene backups without publishing filesystem paths."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.root = contained(store.data_dir, store.data_dir / "scenes/backups")

    def initialize(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def export(self, owner: str, scene_id: str, destination: Path) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        document = self.store.get_scene(scene_id, owner)
        revisions = self.store.list_scene_revisions(scene_id, owner)
        entries: list[SceneBackupEntry] = []
        sources: dict[str, Path] = {}
        dependency_revisions: dict[str, list[str]] = {}

        def append_entry(
            path: str,
            kind: Literal["source", "preview", "dependency"],
            asset_id: str,
            revision_ids: list[str],
        ) -> None:
            asset = self.store.get_asset(asset_id)
            provenance = self.store.get_provenance(asset_id)
            source = self.store.asset_path(asset_id)
            if source.is_symlink() or not source.is_file():
                raise SceneError("scene_backup_missing", "scene backup asset is unavailable")
            if source.stat().st_size != asset.size_bytes or _hash_path(source) != asset.sha256:
                raise SceneError("scene_backup_hash_changed", "scene backup asset identity changed")
            sources[path] = source
            entries.append(
                SceneBackupEntry(
                    path=path,
                    kind=kind,
                    asset=asset,
                    provenance=provenance,
                    revision_ids=revision_ids,
                    size_bytes=asset.size_bytes,
                    sha256=asset.sha256,
                )
            )

        for revision in revisions:
            append_entry(
                f"revisions/{revision.id}/scene.blend",
                "source",
                revision.source_asset_id,
                [revision.id],
            )
            append_entry(
                f"revisions/{revision.id}/preview.glb",
                "preview",
                revision.preview_asset_id,
                [revision.id],
            )
            for dependency in revision.dependencies:
                dependency_revisions.setdefault(dependency.asset_id, []).append(revision.id)
        for asset_id in sorted(dependency_revisions):
            append_entry(
                f"dependencies/{asset_id}/asset",
                "dependency",
                asset_id,
                dependency_revisions[asset_id],
            )

        try:
            manifest = SceneBackupManifest(
                created_at=utc_now(),
                document=document,
                revisions=revisions,
                entries=entries,
                content_sha256="0" * 64,
            )
            manifest = manifest.model_copy(
                update={"content_sha256": _manifest_fingerprint(manifest)}
            )
        except ValidationError as exc:
            raise SceneError("scene_backup_invalid", "scene backup metadata is invalid") from exc
        manifest_bytes = (
            json.dumps(
                manifest.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
        )
        if len(manifest_bytes) > MAX_BACKUP_MANIFEST_BYTES:
            raise SceneError("scene_backup_limit", "scene backup manifest exceeds its bound")
        total = len(manifest_bytes) + sum(entry.size_bytes for entry in entries)
        if len(entries) + 1 > MAX_BACKUP_MEMBERS or total > MAX_BACKUP_UNCOMPRESSED_BYTES:
            raise SceneError("scene_backup_limit", "scene backup exceeds its extraction bound")

        try:
            destination = contained(self.root, destination)
        except ValueError as exc:
            raise SceneError(
                "scene_backup_invalid", "scene backup destination is outside private storage"
            ) from exc
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
            ) as archive:
                archive.writestr(_zip_info("manifest.json"), manifest_bytes)
                for entry in entries:
                    with sources[entry.path].open("rb") as source, archive.open(
                        _zip_info(entry.path), "w", force_zip64=True
                    ) as output:
                        _copy_verified(source, output, entry)
            if temporary.stat().st_size > MAX_BACKUP_ARCHIVE_BYTES:
                raise SceneError("scene_backup_limit", "scene backup archive exceeds its bound")
            temporary.replace(destination)
            destination.chmod(0o600)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return {
            "schema_version": BACKUP_SCHEMA,
            "scene_id": scene_id,
            "revision_count": len(revisions),
            "size_bytes": destination.stat().st_size,
            "sha256": _hash_path(destination),
            "content_sha256": manifest.content_sha256,
        }

    def restore(self, owner: str, source: Path) -> dict[str, Any]:
        owner = validate_scene_owner(owner)
        original = source
        if original.is_symlink() or not original.is_file():
            raise SceneError("scene_backup_invalid", "scene backup archive is unavailable")
        try:
            source = contained(self.root, original)
        except ValueError as exc:
            raise SceneError(
                "scene_backup_invalid", "scene backup source is outside private storage"
            ) from exc
        if source.stat().st_size < 1 or source.stat().st_size > MAX_BACKUP_ARCHIVE_BYTES:
            raise SceneError("scene_backup_limit", "scene backup archive size is invalid")
        archive_sha256 = _hash_path(source)
        staging = contained(self.root, self.root / f"restore_{uuid.uuid4().hex}")
        staging.mkdir(mode=0o700)
        try:
            manifest, extracted = self._read_archive(source, staging)
            result = self._restore_snapshot(owner, manifest, extracted, archive_sha256)
            return {
                "schema_version": BACKUP_SCHEMA,
                "scene": result.model_dump(mode="json"),
                "archive_sha256": archive_sha256,
                "content_sha256": manifest.content_sha256,
            }
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _read_archive(
        self, source: Path, staging: Path
    ) -> tuple[SceneBackupManifest, dict[str, Path]]:
        try:
            archive = zipfile.ZipFile(source, "r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise SceneError("scene_backup_invalid", "scene backup archive is invalid") from exc
        try:
            with archive:
                members = archive.infolist()
                names = [item.filename for item in members]
                if (
                    not members
                    or len(members) > MAX_BACKUP_MEMBERS
                    or len(names) != len(set(names))
                    or names[0] != "manifest.json"
                ):
                    raise SceneError("scene_backup_invalid", "scene backup member list is invalid")
                total = 0
                for item in members:
                    try:
                        _safe_member(item.filename)
                    except ValueError as exc:
                        raise SceneError(
                            "scene_backup_invalid", "scene backup member path is unsafe"
                        ) from exc
                    mode = item.external_attr >> 16
                    file_type = stat.S_IFMT(mode)
                    if item.is_dir() or file_type not in {0, stat.S_IFREG} or item.flag_bits & 0x1:
                        raise SceneError(
                            "scene_backup_invalid", "scene backup member type is invalid"
                        )
                    total += item.file_size
                    if total > MAX_BACKUP_UNCOMPRESSED_BYTES:
                        raise SceneError(
                            "scene_backup_limit", "scene backup extraction exceeds its bound"
                        )
                manifest_info = members[0]
                if manifest_info.file_size > MAX_BACKUP_MANIFEST_BYTES:
                    raise SceneError(
                        "scene_backup_limit", "scene backup manifest exceeds its bound"
                    )
                try:
                    manifest = SceneBackupManifest.model_validate_json(archive.read(manifest_info))
                except (ValidationError, ValueError) as exc:
                    raise SceneError(
                        "scene_backup_invalid", "scene backup manifest is invalid"
                    ) from exc
                if manifest.content_sha256 != _manifest_fingerprint(manifest):
                    raise SceneError(
                        "scene_backup_hash_changed", "scene backup manifest identity changed"
                    )
                expected = ["manifest.json", *(entry.path for entry in manifest.entries)]
                if names != expected:
                    raise SceneError(
                        "scene_backup_invalid", "scene backup members differ from manifest"
                    )
                extracted: dict[str, Path] = {}
                for index, entry in enumerate(manifest.entries):
                    info = members[index + 1]
                    if info.file_size != entry.size_bytes:
                        raise SceneError(
                            "scene_backup_hash_changed", "scene backup member size changed"
                        )
                    target = contained(staging, staging / f"asset-{index:04d}")
                    digest = hashlib.sha256()
                    written = 0
                    with archive.open(info, "r") as input_stream, target.open("xb") as output:
                        while True:
                            chunk = input_stream.read(BACKUP_CHUNK_BYTES)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > entry.size_bytes:
                                raise SceneError(
                                    "scene_backup_limit", "scene backup member exceeds its bound"
                                )
                            digest.update(chunk)
                            output.write(chunk)
                    target.chmod(0o600)
                    if written != entry.size_bytes or digest.hexdigest() != entry.sha256:
                        raise SceneError(
                            "scene_backup_hash_changed", "scene backup member identity changed"
                        )
                    if entry.kind == "source":
                        with target.open("rb") as stream:
                            header = stream.read(7)
                        if written > MAX_BLEND_BYTES or header != b"BLENDER":
                            raise SceneError(
                                "scene_backup_invalid", "scene backup Blender source is invalid"
                            )
                    elif entry.kind == "preview":
                        if written > MAX_GLB_BYTES:
                            raise SceneError(
                                "scene_backup_limit", "scene backup preview exceeds its bound"
                            )
                        try:
                            validate_glb_path(target, staging)
                        except GlbValidationError as exc:
                            raise SceneError(
                                "scene_backup_invalid", "scene backup preview is invalid"
                            ) from exc
                    extracted[entry.path] = target
                return manifest, extracted
        except SceneError:
            raise
        except (OSError, EOFError, RuntimeError, zipfile.BadZipFile) as exc:
            raise SceneError("scene_backup_invalid", "scene backup archive is invalid") from exc

    def _restore_snapshot(
        self,
        owner: str,
        manifest: SceneBackupManifest,
        extracted: dict[str, Path],
        archive_sha256: str,
    ) -> SceneDocument:
        now = utc_now()
        scene_id = f"scene_{uuid.uuid4().hex}"
        revision_ids = {
            revision.id: f"revision_{uuid.uuid4().hex}" for revision in manifest.revisions
        }
        unique_entries: dict[str, SceneBackupEntry] = {}
        unique_paths: dict[str, Path] = {}
        for entry in manifest.entries:
            previous = unique_entries.get(entry.asset.id)
            if previous is not None and (
                previous.sha256 != entry.sha256
                or previous.asset != entry.asset
                or previous.provenance != entry.provenance
            ):
                raise SceneError("scene_backup_invalid", "repeated backup asset metadata differs")
            unique_entries.setdefault(entry.asset.id, entry)
            unique_paths.setdefault(entry.asset.id, extracted[entry.path])
        asset_ids = {asset_id: f"asset_{uuid.uuid4().hex}" for asset_id in unique_entries}
        job_id = f"job_{uuid.uuid4().hex}"
        restored_assets: list[tuple[Asset, Provenance, Path]] = []
        for original_id, entry in unique_entries.items():
            asset_id = asset_ids[original_id]
            provenance_id = f"prov_{uuid.uuid4().hex}"
            parents = [
                asset_ids[value]
                for value in entry.asset.parent_asset_ids
                if value in asset_ids
            ]
            asset = entry.asset.model_copy(
                update={
                    "id": asset_id,
                    "job_id": job_id,
                    "parent_asset_ids": parents,
                    "provenance_id": provenance_id,
                    "created_at": now,
                }
            )
            provenance = Provenance(
                id=provenance_id,
                asset_id=asset_id,
                parent_asset_ids=parents,
                operation="scene.restore",
                intent="Restore exact scene backup",
                model_id=entry.provenance.model_id,
                model_version=entry.provenance.model_version,
                weights_hash=entry.provenance.weights_hash,
                license=entry.provenance.license,
                runtime_adapter="scene.backup",
                runtime_version=__version__,
                tool_versions={**entry.provenance.tool_versions, "media-forge": __version__},
                seed=entry.provenance.seed,
                parameters={
                    "backup_sha256": archive_sha256,
                    "source_asset_id": original_id,
                    "source_provenance_id": entry.provenance.id,
                },
                reference_asset_hashes={
                    asset_ids[value]: digest
                    for value, digest in entry.provenance.reference_asset_hashes.items()
                    if value in asset_ids
                },
                postprocessing=[*entry.provenance.postprocessing, "scene-backup-restore"],
                validation=[
                    *entry.provenance.validation,
                    {"validator": "scene.backup", "status": "passed", "sha256": archive_sha256},
                ],
                warnings=entry.provenance.warnings,
                output_sha256=entry.sha256,
                created_at=now,
            )
            restored_assets.append((asset, provenance, unique_paths[original_id]))

        revisions: list[SceneRevision] = []
        for original in manifest.revisions:
            revisions.append(
                original.model_copy(
                    update={
                        "id": revision_ids[original.id],
                        "scene_id": scene_id,
                        "parent_revision_id": revision_ids.get(original.parent_revision_id),
                        "source_asset_id": asset_ids[original.source_asset_id],
                        "preview_asset_id": asset_ids[original.preview_asset_id],
                        "dependencies": [
                            SceneDependency(
                                role=item.role,
                                asset_id=asset_ids[item.asset_id],
                                sha256=item.sha256,
                            )
                            for item in original.dependencies
                        ],
                    }
                )
            )
        document = manifest.document.model_copy(
            update={
                "id": scene_id,
                "current_revision_id": revisions[-1].id,
                "created_at": now,
                "updated_at": now,
            }
        )
        job = Job(
            id=job_id,
            status=JobStatus.SUCCEEDED,
            progress=1,
            request=JobRequest(operation="media.inspect", intent="Restore scene backup"),
            asset_ids=[asset.id for asset, _provenance, _source in restored_assets],
            created_at=now,
            updated_at=now,
        )
        return self.store.restore_scene_snapshot(
            owner, job, document, revisions, restored_assets
        )
