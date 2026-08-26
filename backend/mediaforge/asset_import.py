from __future__ import annotations

import hashlib
import io
import shutil
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from . import __version__
from .domain import Asset, ErrorDetail, JobRequest, JobStatus, Provenance
from .glb import VALIDATION_VERSION as GLB_VALIDATION_VERSION
from .glb import GlbValidationError, validate_glb
from .paths import contained
from .store import Store, utc_now
from .validators import validate_png


MAX_IMPORT_BYTES = 64 * 1024 * 1024
MAX_IMPORT_PIXELS = 2048 * 2048


class AssetImportError(ValueError):
    pass


def import_asset_bytes(store: Store, content: bytes, *, purpose: str, media_type: str | None = None) -> Asset:
    if media_type == "model/gltf-binary":
        return import_glb_asset(store, content, purpose=purpose)
    return import_image_asset(store, content, purpose=purpose)


def import_image_asset(store: Store, content: bytes, *, purpose: str) -> Asset:
    if purpose not in {"source", "edit_mask"}:
        raise AssetImportError("image import purpose is unsupported")
    if not content or len(content) > MAX_IMPORT_BYTES:
        raise AssetImportError("image import must be between 1 byte and 64 MiB")
    try:
        with Image.open(io.BytesIO(content)) as opened:
            opened.load()
            if opened.format not in {"PNG", "JPEG"}:
                raise AssetImportError("image import supports PNG and JPEG only")
            if opened.width < 1 or opened.height < 1 or opened.width * opened.height > MAX_IMPORT_PIXELS:
                raise AssetImportError("image import dimensions exceed the 4,194,304 pixel bound")
            image = opened.convert("RGBA")
    except AssetImportError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise AssetImportError("image import is not decodable") from exc

    job = store.create_job(JobRequest(
        operation="media.inspect",
        intent=f"Import local {purpose.replace('_', ' ')} asset",
    ))
    work_root = contained(store.work_dir, store.work_dir / job.id)
    try:
        work_root.mkdir(mode=0o700)
        normalized = contained(work_root, work_root / "normalized.png")
        image.save(normalized, format="PNG")
        width, height, validation = validate_png(normalized)
        sha256 = hashlib.sha256(normalized.read_bytes()).hexdigest()
        now = utc_now()
        asset_id = f"asset_{uuid.uuid4().hex}"
        provenance_id = f"prov_{uuid.uuid4().hex}"
        asset = Asset(
            id=asset_id,
            job_id=job.id,
            parent_asset_ids=[],
            mime_type="image/png",
            width=width,
            height=height,
            size_bytes=normalized.stat().st_size,
            sha256=sha256,
            suggested_filename=f"media-forge-import-{asset_id[6:14]}.png",
            provenance_id=provenance_id,
            created_at=now,
        )
        provenance = Provenance(
            id=provenance_id,
            asset_id=asset_id,
            parent_asset_ids=[],
            operation="asset.import",
            intent=job.request.intent,
            model_id="media-forge/local-import",
            model_version="1.0.0",
            weights_hash="sha256:" + "0" * 64,
            license="user-provided",
            runtime_adapter="deterministic.image-import",
            runtime_version="1.0.0",
            tool_versions={"media-forge": __version__, "validator.png": "1.0.0"},
            seed=0,
            parameters={"purpose": purpose, "source_size_bytes": len(content)},
            reference_asset_hashes={},
            postprocessing=["pil.convert.rgba", "png.normalize"],
            validation=validation,
            warnings=[],
            output_sha256=sha256,
            created_at=now,
        )
        store.register_asset(asset, provenance, normalized)
        store.update_job(
            job.id,
            status=JobStatus.SUCCEEDED,
            progress=1,
            asset_ids=[asset.id],
        )
        return asset
    except Exception as exc:
        store.update_job(
            job.id,
            status=JobStatus.FAILED,
            error=ErrorDetail(code="asset_import_failed", message=str(exc)[:300]),
        )
        raise
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)


def import_glb_asset(store: Store, content: bytes, *, purpose: str) -> Asset:
    if purpose != "source":
        raise AssetImportError("GLB import purpose must be source")
    try:
        validation = validate_glb(content)
    except GlbValidationError as exc:
        raise AssetImportError(str(exc)) from exc

    job = store.create_job(JobRequest(operation="media.inspect", intent="Import local 3D source asset"))
    work_root = contained(store.work_dir, store.work_dir / job.id)
    try:
        work_root.mkdir(mode=0o700)
        original = contained(work_root, work_root / "original.glb")
        original.write_bytes(content)
        original.chmod(0o600)
        sha256 = hashlib.sha256(content).hexdigest()
        now = utc_now()
        asset_id = f"asset_{uuid.uuid4().hex}"
        provenance_id = f"prov_{uuid.uuid4().hex}"
        asset = Asset(
            id=asset_id,
            job_id=job.id,
            parent_asset_ids=[],
            mime_type="model/gltf-binary",
            size_bytes=len(content),
            sha256=sha256,
            suggested_filename=f"media-forge-import-{asset_id[6:14]}.glb",
            provenance_id=provenance_id,
            created_at=now,
        )
        provenance = Provenance(
            id=provenance_id,
            asset_id=asset_id,
            parent_asset_ids=[],
            operation="asset.import",
            intent=job.request.intent,
            model_id="media-forge/local-import",
            model_version="1.0.0",
            weights_hash="sha256:" + "0" * 64,
            license="user-provided",
            runtime_adapter="deterministic.glb-import",
            runtime_version="1.0.0",
            tool_versions={"media-forge": __version__, "validator.glb": GLB_VALIDATION_VERSION},
            seed=0,
            parameters={
                "purpose": purpose,
                "source_size_bytes": len(content),
                "structure": {
                    "counts": validation["counts"],
                    "required_extensions": validation["required_extensions"],
                },
            },
            reference_asset_hashes={},
            postprocessing=[],
            validation=[validation],
            warnings=[],
            output_sha256=sha256,
            created_at=now,
        )
        store.register_asset(asset, provenance, original)
        store.update_job(job.id, status=JobStatus.SUCCEEDED, progress=1, asset_ids=[asset.id])
        return asset
    except Exception as exc:
        store.update_job(
            job.id,
            status=JobStatus.FAILED,
            error=ErrorDetail(code="asset_import_failed", message=str(exc)[:300]),
        )
        raise
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)
