"""Fixed Blender subprocess and deterministic G8 project package."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import logging
import os
from pathlib import Path
import shutil
import signal
import tempfile
from collections.abc import Callable
from typing import Annotated, Any, Literal
import zipfile

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import __version__
from .config import REPOSITORY_ROOT
from .glb import VALIDATION_VERSION as GLB_VALIDATION_VERSION
from .glb import GlbValidationError, validate_glb
from .paths import contained
from .validators import validate_png


BLENDER_VERSION = "4.5.9"
RUNTIME_ROOT = REPOSITORY_ROOT / "runtimes" / "blender-4.5.9"
BLENDER_EXECUTABLE = RUNTIME_ROOT / "install" / "blender"
TRUSTED_WORKER = REPOSITORY_ROOT / "worker_packs" / "blender" / "compile_asset.py"
REQUEST_NAME = "request.json"
RESULT_NAME = "result.json"
SOURCE_NAME = "source.glb"
GLB_NAME = "asset.glb"
PREVIEW_NAME = "preview.png"
MANIFEST_NAME = "manifest.json"
PACKAGE_NAME = "project-ready-glb.zip"
MAX_PROCESS_OUTPUT_BYTES = 256 * 1024
PROCESS_TIMEOUT_SEC = 180
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
COMPILER_VERSION = "1.1.0"
logger = logging.getLogger("uvicorn.error")
OPERATION_IDS = (
    "sanitize.scene",
    "normalize.unit-meters",
    "edit.mesh",
    "budget.triangles",
    "materials.normalize",
    "lod.generate",
    "collision.generate",
    "validate.normals",
    "export.glb-embedded-y-up",
    "preview.fixed-workbench",
)


class BlenderCompileError(RuntimeError):
    pass


class BlenderCompileCanceled(BlenderCompileError):
    pass


class CompileOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["3d.compile-options@1"]
    apply_transforms: Literal[True] = True
    repair_normals: Annotated[bool, Field(strict=True)] = False
    remove_degenerate: Annotated[bool, Field(strict=True)] = False
    merge_by_distance_m: Annotated[float, Field(strict=True, ge=0.000_000_1, le=1.0)] | None = None
    triangle_budget: Annotated[int, Field(strict=True, ge=12, le=200_000)] | None = None
    lod_ratios: list[Annotated[float, Field(strict=True)]] = Field(default_factory=list, max_length=3)
    collision: Literal["none", "box", "convex_hull"] = "none"
    materials: Literal["preserve", "basic_pbr"] = "preserve"
    preview: Literal["fixed_workbench"] = "fixed_workbench"

    @field_validator("apply_transforms")
    @classmethod
    def transforms_are_fixed(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("apply_transforms must remain true")
        return value

    @field_validator("lod_ratios")
    @classmethod
    def bounded_descending_lods(cls, value: list[float]) -> list[float]:
        if any(isinstance(item, bool) or not 0.05 <= item <= 0.95 for item in value):
            raise ValueError("lod ratios must be between 0.05 and 0.95")
        if any(left <= right for left, right in zip(value, value[1:], strict=False)):
            raise ValueError("lod ratios must be strictly descending")
        return value


def parse_compile_options(constraints: dict[str, Any]) -> CompileOptions:
    value: object = {"schema_version": "3d.compile-options@1"}
    if constraints:
        if set(constraints) != {"compile_options"}:
            raise BlenderCompileError("3D constraints accept compile_options only")
        value = constraints["compile_options"]
    try:
        return CompileOptions.model_validate(value)
    except ValidationError as exc:
        raise BlenderCompileError("3d.compile-options@1 is invalid") from exc


async def _read_bounded(stream: asyncio.StreamReader | None, label: str) -> bytes:
    if stream is None:
        return b""
    value = bytearray()
    while True:
        chunk = await stream.read(16 * 1024)
        if not chunk:
            return bytes(value)
        value.extend(chunk)
        if len(value) > MAX_PROCESS_OUTPUT_BYTES:
            raise BlenderCompileError(f"Blender {label} exceeds the output bound")


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()


def _fixed_request(job_root: Path, source_sha256: str, options: CompileOptions) -> Path:
    request = {
        "schema_version": 1,
        "expected_blender_version": BLENDER_VERSION,
        "source": SOURCE_NAME,
        "output": GLB_NAME,
        "preview": PREVIEW_NAME,
        "source_sha256": source_sha256,
        "options": options.model_dump(mode="json"),
    }
    path = contained(job_root, job_root / REQUEST_NAME)
    path.write_text(json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


async def _wait_process(
    process: asyncio.subprocess.Process,
    cancel_requested: Callable[[], bool] | None,
) -> int:
    while process.returncode is None:
        if cancel_requested is not None and cancel_requested():
            raise BlenderCompileCanceled("Blender compiler was canceled")
        await asyncio.sleep(0.05)
    return await process.wait()


async def _run_blender(
    job_root: Path,
    request_path: Path,
    cancel_requested: Callable[[], bool] | None,
) -> dict[str, Any]:
    executable = BLENDER_EXECUTABLE.resolve()
    worker = TRUSTED_WORKER.resolve()
    if (
        not BLENDER_EXECUTABLE.is_file()
        or BLENDER_EXECUTABLE.is_symlink()
        or not os.access(executable, os.X_OK)
        or not TRUSTED_WORKER.is_file()
        or TRUSTED_WORKER.is_symlink()
    ):
        raise BlenderCompileError("pinned Blender runtime or trusted compiler is unavailable")
    result_path = contained(job_root, job_root / RESULT_NAME)
    sandbox = contained(job_root, job_root / "blender-user")
    sandbox.mkdir(mode=0o700)
    environment = {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "HOME": str(sandbox),
        "XDG_CACHE_HOME": str(sandbox / "cache"),
        "XDG_CONFIG_HOME": str(sandbox / "config"),
        "XDG_DATA_HOME": str(sandbox / "data"),
        "BLENDER_USER_CONFIG": str(sandbox / "blender-config"),
        "BLENDER_USER_SCRIPTS": str(sandbox / "blender-scripts"),
        "BLENDER_USER_DATAFILES": str(sandbox / "blender-data"),
        "LIBGL_ALWAYS_SOFTWARE": "1",
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
    }
    command = [
        str(executable),
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--python",
        str(worker),
        "--",
        "--request",
        request_path.name,
        "--result",
        result_path.name,
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=job_root,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
    except OSError as exc:
        raise BlenderCompileError("Blender compiler failed to start") from exc
    try:
        stdout_task = asyncio.create_task(_read_bounded(process.stdout, "stdout"))
        stderr_task = asyncio.create_task(_read_bounded(process.stderr, "stderr"))
        try:
            stdout, stderr, returncode = await asyncio.wait_for(
                asyncio.gather(stdout_task, stderr_task, _wait_process(process, cancel_requested)),
                timeout=PROCESS_TIMEOUT_SEC,
            )
        except BaseException:
            await _stop_process(process)
            for task in (stdout_task, stderr_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise
        if returncode != 0:
            detail = (stderr or stdout).decode("utf-8", errors="replace").strip()[-1200:]
            detail = detail.replace(str(job_root), "<job-root>").replace(str(REPOSITORY_ROOT), "<repository>")
            logger.warning("Blender compiler returned %s: %s", returncode, detail)
            raise BlenderCompileError("Blender compiler failed; inspect the bounded service log")
        if not result_path.is_file() or result_path.is_symlink():
            detail = (stderr + stdout).decode("utf-8", errors="replace").strip()[-1200:]
            detail = detail.replace(str(job_root), "<job-root>").replace(str(REPOSITORY_ROOT), "<repository>")
            logger.warning("Blender compiler result is missing: %s", detail)
            raise BlenderCompileError("Blender compiler did not produce its result; inspect the bounded service log")
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderCompileError("Blender compiler result is unreadable") from exc
        if not isinstance(result, dict):
            raise BlenderCompileError("Blender compiler result is not an object")
        return result
    except TimeoutError as exc:
        raise BlenderCompileError("Blender compiler exceeded the 180 second timeout") from exc
    finally:
        if sandbox.exists():
            shutil.rmtree(sandbox)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_entry(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.create_system = 3
    info.external_attr = 0o100600 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _validated_result(result: dict[str, Any], *, source_sha256: str, glb_sha256: str, preview_sha256: str) -> dict[str, Any]:
    expected_fields = {
        "schema_version", "blender_version", "input_sha256", "output_sha256", "preview_sha256",
        "statistics", "removed", "warnings", "operations",
    }
    if set(result) != expected_fields or result.get("schema_version") != 1:
        raise BlenderCompileError("Blender compiler result fields differ")
    if result.get("blender_version") != BLENDER_VERSION:
        raise BlenderCompileError("Blender compiler version differs")
    if (
        result.get("input_sha256") != source_sha256
        or result.get("output_sha256") != glb_sha256
        or result.get("preview_sha256") != preview_sha256
    ):
        raise BlenderCompileError("Blender compiler hashes differ")
    statistics = result.get("statistics")
    removed = result.get("removed")
    warnings = result.get("warnings")
    operations = result.get("operations")
    if (
        not isinstance(statistics, dict)
        or not isinstance(removed, dict)
        or not isinstance(warnings, list)
        or not isinstance(operations, list)
    ):
        raise BlenderCompileError("Blender compiler facts are invalid")
    count_fields = {"objects", "meshes", "vertices", "edges", "triangles", "materials", "textures"}
    if set(statistics) != {*count_fields, "bounds_min", "bounds_max"}:
        raise BlenderCompileError("Blender compiler statistic fields differ")
    if any(
        isinstance(statistics[name], bool)
        or not isinstance(statistics[name], int)
        or not 0 <= statistics[name] <= 100_000_000
        for name in count_fields
    ):
        raise BlenderCompileError("Blender compiler counts exceed their bound")
    for name in ("bounds_min", "bounds_max"):
        bounds = statistics[name]
        if (
            not isinstance(bounds, list)
            or len(bounds) != 3
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in bounds)
        ):
            raise BlenderCompileError("Blender compiler bounds are invalid")
    removed_fields = {"camera_light_objects", "text_blocks", "drivers", "custom_properties"}
    if set(removed) != removed_fields or any(
        isinstance(removed[name], bool) or not isinstance(removed[name], int) or not 0 <= removed[name] <= 1_000_000
        for name in removed_fields
    ):
        raise BlenderCompileError("Blender compiler removal counts are invalid")
    if (
        len(warnings) > 256
        or any(not isinstance(item, str) or len(item) > 300 for item in warnings)
    ):
        raise BlenderCompileError("Blender compiler warnings are invalid")
    if (
        len(operations) != len(OPERATION_IDS)
        or any(not isinstance(item, dict) for item in operations)
        or tuple(item.get("id") for item in operations) != OPERATION_IDS
        or any(set(item) != {"id", "parameters", "results", "warnings"} for item in operations)
        or any(
            not isinstance(item["parameters"], dict)
            or not isinstance(item["results"], dict)
            or not isinstance(item["warnings"], list)
            or any(not isinstance(warning, str) or len(warning) > 300 for warning in item["warnings"])
            for item in operations
        )
    ):
        raise BlenderCompileError("Blender compiler operations are invalid")
    serialized = json.dumps(
        {"statistics": statistics, "removed": removed, "warnings": warnings, "operations": operations},
        allow_nan=False,
    )
    if len(serialized.encode()) > 64 * 1024:
        raise BlenderCompileError("Blender compiler facts exceed their bound")
    return {"statistics": statistics, "removed": removed, "warnings": warnings, "operations": operations}


async def compile_project_package(
    source: Path,
    job_root: Path,
    *,
    options: CompileOptions | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    job_root = job_root.resolve()
    source_content = source.read_bytes()
    try:
        input_validation = validate_glb(source_content)
    except GlbValidationError as exc:
        raise BlenderCompileError(str(exc)) from exc
    source_copy = contained(job_root, job_root / SOURCE_NAME)
    source_copy.write_bytes(source_content)
    source_copy.chmod(0o600)
    source_sha256 = hashlib.sha256(source_content).hexdigest()
    options = options or CompileOptions(schema_version="3d.compile-options@1")
    request_path = _fixed_request(job_root, source_sha256, options)
    result = await _run_blender(job_root, request_path, cancel_requested)

    glb_path = contained(job_root, job_root / GLB_NAME)
    preview_path = contained(job_root, job_root / PREVIEW_NAME)
    if glb_path.is_symlink() or not glb_path.is_file() or preview_path.is_symlink() or not preview_path.is_file():
        raise BlenderCompileError("Blender compiler output is missing or unsafe")
    try:
        output_validation = validate_glb(glb_path.read_bytes())
        _, _, preview_validation = validate_png(preview_path)
    except (GlbValidationError, ValueError) as exc:
        raise BlenderCompileError(str(exc)) from exc
    glb_sha256 = _sha256(glb_path)
    preview_sha256 = _sha256(preview_path)
    facts = _validated_result(
        result,
        source_sha256=source_sha256,
        glb_sha256=glb_sha256,
        preview_sha256=preview_sha256,
    )
    manifest = {
        "schema_version": "media-forge.3d-project@1",
        "profile": "3d.project.glb",
        "source": {"mime_type": "model/gltf-binary", "size_bytes": len(source_content), "sha256": source_sha256},
        "asset": {
            "filename": GLB_NAME,
            "mime_type": "model/gltf-binary",
            "size_bytes": glb_path.stat().st_size,
            "sha256": glb_sha256,
            "validation_version": GLB_VALIDATION_VERSION,
        },
        "preview": {
            "filename": PREVIEW_NAME,
            "mime_type": "image/png",
            "size_bytes": preview_path.stat().st_size,
            "sha256": preview_sha256,
        },
        "compiler": {"blender_version": BLENDER_VERSION, "compiler_version": COMPILER_VERSION},
        "options": options.model_dump(mode="json"),
        **facts,
    }
    manifest_content = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode() + b"\n"
    package = contained(job_root, job_root / PACKAGE_NAME)
    with zipfile.ZipFile(package, "w") as archive:
        _zip_entry(archive, GLB_NAME, glb_path.read_bytes())
        _zip_entry(archive, MANIFEST_NAME, manifest_content)
        _zip_entry(archive, PREVIEW_NAME, preview_path.read_bytes())
    package.chmod(0o600)
    validation = [
        input_validation,
        {**output_validation, "validator": "glb.output_structure"},
        *preview_validation,
        {"validator": "package.deterministic_zip", "status": "passed", "entries": 3},
    ]
    return package, manifest, validation
