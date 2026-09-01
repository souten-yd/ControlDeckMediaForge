from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
from fractions import Fraction
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
# 端末の写真を、撮ったままの解像度で預かれる大きさに置く。2048x2048 は strict edit を
# 入れたときの丸い数で、根拠は記録されていなかった。実際に何が縛るかを測った
# （合成 + 検証、原寸 RGBA を数枚持つ）。
#
#    3.1MP  合成 0.81s  検証 0.24s  PNG  4.6MiB  peak RSS  139MiB
#   12.2MP       2.90s       0.91s      13.6MiB           433MiB   ← 携帯の標準
#   24.4MP       5.22s       1.71s      22.2MiB           828MiB   ← 一眼の標準
#   48.0MP       9.16s       3.27s      35.6MiB          1607MiB
#
# VRAM は使わない。縛るのは core の RAM である。24MP までなら 1 枚あたり 0.8GB で
# 収まり、携帯の 12MP も一眼の 24MP もそのまま通る。48MP は 1.6GB を 1 ジョブが
# 抱えるので取らない。超える写真は画面が縮めて送る（今までと同じ）。
MAX_IMPORT_PIXELS = 24_000_000


class AssetImportError(ValueError):
    pass


VIDEO_MEDIA_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
# 動画の上限は画像と分ける。実測: 640x384 の 15 秒（360 フレーム）で 17.2 MB。
# 余裕を見て 4 倍に置く。artifact の 64 MiB とは別の理由で決まる値である。
MAX_VIDEO_IMPORT_BYTES = 96 * 1024 * 1024
# 画素の上限も分ける。画像は原寸で預かるために上げたが、動画は 1 フレームでは
# なく尺のぶんだけ復号する。同じ数を当てると桁が変わる。
MAX_VIDEO_IMPORT_PIXELS = 2048 * 2048
_VIDEO_TOOL_TIMEOUT_SEC = 600


def import_asset_bytes(store: Store, content: bytes, *, purpose: str, media_type: str | None = None) -> Asset:
    if media_type == "model/gltf-binary":
        return import_glb_asset(store, content, purpose=purpose)
    if media_type in VIDEO_MEDIA_TYPES:
        return import_video_asset(store, content, purpose=purpose, media_type=media_type)
    return import_image_asset(store, content, purpose=purpose)


def _probe_video(path: Path) -> dict[str, Any]:
    """中身が本当に動画かを確かめ、寸法と尺を読む。

    worker の FFmpeg 実装は import しない（AGENTS.md）。呼ぶのは system の
    binary で、配列引数・timeout 付きである。
    """
    completed = subprocess.run(
        [
            "/usr/bin/ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(path),
        ],
        check=False, capture_output=True, timeout=_VIDEO_TOOL_TIMEOUT_SEC,
    )
    if completed.returncode != 0:
        raise AssetImportError("video import is not decodable")
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssetImportError("video import is not decodable") from exc
    streams = [s for s in document.get("streams", []) if s.get("codec_type") == "video"]
    if len(streams) != 1:
        raise AssetImportError("video import must carry exactly one video stream")
    video = streams[0]
    try:
        width, height = int(video["width"]), int(video["height"])
        duration = float(document["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AssetImportError("video import has no usable dimensions or duration") from exc
    if width < 16 or height < 16 or width * height > MAX_VIDEO_IMPORT_PIXELS:
        raise AssetImportError("video import dimensions are out of bounds")
    if not 0 < duration <= 300:
        raise AssetImportError("video import must be between 0 and 300 seconds")
    rate = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
    try:
        frame_rate = float(Fraction(rate))
    except (ValueError, ZeroDivisionError):
        frame_rate = 0.0
    if not 0 < frame_rate <= 120:
        raise AssetImportError("video import frame rate is out of bounds")
    return {
        "width": width, "height": height,
        "duration_sec": duration, "frame_rate": frame_rate,
        "codec": str(video.get("codec_name") or ""),
        "audio": any(s.get("codec_type") == "audio" for s in document.get("streams", [])),
    }


def import_video_asset(
    store: Store, content: bytes, *, purpose: str, media_type: str | None = None
) -> Asset:
    """取り込んだ動画を、どの端末でも再生できる 1 つの形に揃えて登録する。

    駆動系は webm/vp8 を書くものもあるが、iOS はそれを再生しない。取り込んだ
    ものをそのまま置くと、作った端末でだけ見える asset ができる。h264/aac の
    mp4 へ揃えるのは、見られないものを library に置かないためである。
    """
    if purpose != "source":
        raise AssetImportError("video import purpose must be source")
    if not content or len(content) > MAX_VIDEO_IMPORT_BYTES:
        raise AssetImportError("video import must be between 1 byte and 96 MiB")

    job = store.create_job(JobRequest(
        operation="media.inspect", intent="Import local video asset",
    ))
    work_root = contained(store.work_dir, store.work_dir / job.id)
    try:
        work_root.mkdir(mode=0o700)
        source = contained(work_root, work_root / "source.bin")
        source.write_bytes(content)
        probed = _probe_video(source)
        normalized = contained(work_root, work_root / "normalized.mp4")
        completed = subprocess.run(
            [
                "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", str(source),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                *(("-c:a", "aac") if probed["audio"] else ("-an",)),
                str(normalized),
            ],
            check=False, capture_output=True, timeout=_VIDEO_TOOL_TIMEOUT_SEC,
        )
        if completed.returncode != 0 or not normalized.is_file() or normalized.stat().st_size <= 0:
            raise AssetImportError("video import could not be normalized")
        final = _probe_video(normalized)
        digest = hashlib.sha256(normalized.read_bytes()).hexdigest()
        now = utc_now()
        asset_id = f"asset_{uuid.uuid4().hex}"
        provenance_id = f"prov_{uuid.uuid4().hex}"
        asset = Asset(
            id=asset_id,
            job_id=job.id,
            parent_asset_ids=[],
            mime_type="video/mp4",
            width=final["width"],
            height=final["height"],
            duration_sec=final["duration_sec"],
            frame_rate=final["frame_rate"],
            size_bytes=normalized.stat().st_size,
            sha256=digest,
            suggested_filename=f"media-forge-import-{asset_id[6:14]}.mp4",
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
            runtime_adapter="deterministic.video-import",
            runtime_version="1.0.0",
            tool_versions={"media-forge": __version__, "ffmpeg.normalize": "1.0.0"},
            seed=0,
            parameters={
                "purpose": purpose,
                "source_size_bytes": len(content),
                "source_media_type": media_type or "",
                "source_codec": probed["codec"],
            },
            reference_asset_hashes={},
            postprocessing=["ffmpeg.normalize.mp4"],
            validation=[{
                "validator": "video.normalized",
                "status": "passed",
                "width": final["width"],
                "height": final["height"],
                "duration_sec": final["duration_sec"],
                "frame_rate": final["frame_rate"],
            }],
            warnings=[],
            output_sha256=digest,
            created_at=now,
        )
        store.register_asset(asset, provenance, normalized)
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
                raise AssetImportError(
                    f"image import dimensions exceed the {MAX_IMPORT_PIXELS:,} pixel bound"
                )
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
