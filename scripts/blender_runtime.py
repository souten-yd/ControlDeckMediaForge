#!/usr/bin/env python3
"""Provision and verify the exact Blender runtime used by G8."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.request import Request, urlopen
import uuid


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "config" / "blender-runtime.json"
DEFAULT_RUNTIME_ROOT = REPOSITORY_ROOT / "runtimes" / "blender-4.5.9"
DEFAULT_PREFLIGHT = REPOSITORY_ROOT / "worker_packs" / "blender" / "preflight.py"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100_000
MAX_EXTRACTED_BYTES = 4 * 1024 * 1024 * 1024
MAX_PROCESS_OUTPUT_BYTES = 64 * 1024
PREFLIGHT_PREFIX = "MEDIA_FORGE_BLENDER_PREFLIGHT="


class BlenderRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSpec:
    schema_version: int
    version: str
    archive_name: str
    archive_url: str
    archive_size_bytes: int
    archive_sha256: str
    top_level_directory: str
    executable: str
    license: str
    source_url: str


def validate_spec(value: object) -> RuntimeSpec:
    if not isinstance(value, dict) or set(value) != set(RuntimeSpec.__dataclass_fields__):
        raise BlenderRuntimeError("Blender runtime manifest fields differ")
    try:
        spec = RuntimeSpec(**value)
    except TypeError as exc:
        raise BlenderRuntimeError("Blender runtime manifest is invalid") from exc
    if (
        spec.schema_version != 1
        or not re.fullmatch(r"4\.5\.[0-9]+", spec.version)
        or spec.archive_url != (
            f"https://download.blender.org/release/Blender4.5/{spec.archive_name}"
        )
        or spec.archive_name != f"blender-{spec.version}-linux-x64.tar.xz"
        or spec.top_level_directory != spec.archive_name.removesuffix(".tar.xz")
        or spec.executable != "blender"
        or spec.license != "GPL-3.0-or-later"
        or spec.source_url != "https://projects.blender.org/blender/blender"
        or not isinstance(spec.archive_size_bytes, int)
        or isinstance(spec.archive_size_bytes, bool)
        or spec.archive_size_bytes <= 0
        or len(spec.archive_sha256) != 64
        or any(character not in "0123456789abcdef" for character in spec.archive_sha256)
    ):
        raise BlenderRuntimeError("Blender runtime manifest violates the pinned boundary")
    return spec


def load_spec(path: Path) -> RuntimeSpec:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlenderRuntimeError("Blender runtime manifest is unreadable") from exc
    return validate_spec(value)


def _safe_member_path(name: str, top_level: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or path.parts[0] != top_level:
        raise BlenderRuntimeError(f"archive member escapes the pinned root: {name[:200]}")
    return path


def _safe_link_target(member: tarfile.TarInfo, top_level: str) -> None:
    if not member.issym() and not member.islnk():
        return
    target = PurePosixPath(member.linkname)
    if target.is_absolute():
        raise BlenderRuntimeError(f"archive link is absolute: {member.name[:200]}")
    base = PurePosixPath(member.name).parent if member.issym() else PurePosixPath()
    parts: list[str] = []
    for part in (base / target).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise BlenderRuntimeError(f"archive link escapes its root: {member.name[:200]}")
            parts.pop()
        else:
            parts.append(part)
    if not parts or parts[0] != top_level:
        raise BlenderRuntimeError(f"archive link escapes the pinned root: {member.name[:200]}")


def validate_archive(path: Path, spec: RuntimeSpec) -> dict[str, int]:
    if not path.is_file() or path.is_symlink():
        raise BlenderRuntimeError("Blender archive is not a regular file")
    if path.stat().st_size != spec.archive_size_bytes:
        raise BlenderRuntimeError("Blender archive size differs")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    if digest.hexdigest() != spec.archive_sha256:
        raise BlenderRuntimeError("Blender archive SHA-256 differs")
    count = 0
    total = 0
    try:
        with tarfile.open(path, mode="r:xz") as archive:
            for member in archive:
                count += 1
                if count > MAX_ARCHIVE_MEMBERS:
                    raise BlenderRuntimeError("Blender archive has too many members")
                _safe_member_path(member.name, spec.top_level_directory)
                if member.isdev() or member.isfifo():
                    raise BlenderRuntimeError("Blender archive contains a device or FIFO")
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise BlenderRuntimeError("Blender archive contains an unsupported member type")
                _safe_link_target(member, spec.top_level_directory)
                if member.isfile():
                    total += member.size
                    if total > MAX_EXTRACTED_BYTES:
                        raise BlenderRuntimeError("Blender archive exceeds the extracted-size bound")
    except (tarfile.TarError, OSError) as exc:
        raise BlenderRuntimeError("Blender archive is not a readable xz tar") from exc
    if count == 0:
        raise BlenderRuntimeError("Blender archive is empty")
    return {"member_count": count, "extracted_bytes": total}


def _download(spec: RuntimeSpec, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    partial.unlink(missing_ok=True)
    request = Request(spec.archive_url, headers={"User-Agent": "ControlDeck-Media-Forge/Blender-Provisioner"})
    written = 0
    try:
        with urlopen(request, timeout=60) as response, partial.open("xb") as output:  # noqa: S310 - pinned HTTPS host
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != spec.archive_size_bytes:
                raise BlenderRuntimeError("Blender download Content-Length differs")
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > spec.archive_size_bytes:
                    raise BlenderRuntimeError("Blender download exceeds the exact size")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if written != spec.archive_size_bytes:
            raise BlenderRuntimeError("Blender download ended before the exact size")
        partial.replace(destination)
    except BlenderRuntimeError:
        partial.unlink(missing_ok=True)
        raise
    except (OSError, ValueError) as exc:
        partial.unlink(missing_ok=True)
        raise BlenderRuntimeError("Blender download failed") from exc


def _bounded_process(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="mediaforge-blender-preflight-") as sandbox:
        sandbox_path = Path(sandbox)
        environment = {
            **os.environ,
            "PYTHONNOUSERSITE": "1",
            "HOME": sandbox,
            "XDG_CACHE_HOME": str(sandbox_path / "cache"),
            "XDG_CONFIG_HOME": str(sandbox_path / "config"),
            "XDG_DATA_HOME": str(sandbox_path / "data"),
            "BLENDER_USER_CONFIG": str(sandbox_path / "blender-config"),
            "BLENDER_USER_SCRIPTS": str(sandbox_path / "blender-scripts"),
            "BLENDER_USER_DATAFILES": str(sandbox_path / "blender-data"),
        }
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BlenderRuntimeError("Blender preflight process failed to execute") from exc
    output_bytes = len(completed.stdout.encode()) + len(completed.stderr.encode())
    if output_bytes > MAX_PROCESS_OUTPUT_BYTES:
        raise BlenderRuntimeError("Blender preflight output exceeds the bound")
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()[-1000:]
        raise BlenderRuntimeError(f"Blender preflight failed: {message}")
    return completed


def preflight(executable: Path, script: Path, spec: RuntimeSpec) -> dict[str, object]:
    if not executable.is_file() or executable.is_symlink() or not os.access(executable, os.X_OK):
        raise BlenderRuntimeError("Blender executable is missing or unsafe")
    if not script.is_file() or script.is_symlink():
        raise BlenderRuntimeError("trusted Blender preflight script is missing or unsafe")
    completed = _bounded_process(
        [
            str(executable),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python",
            str(script),
            "--",
            "--expected-version",
            spec.version,
        ],
        timeout=60,
    )
    line = next((line for line in completed.stdout.splitlines() if line.startswith(PREFLIGHT_PREFIX)), None)
    if line is None:
        raise BlenderRuntimeError("Blender preflight did not return bounded JSON")
    try:
        value = json.loads(line.removeprefix(PREFLIGHT_PREFIX))
    except json.JSONDecodeError as exc:
        raise BlenderRuntimeError("Blender preflight JSON is invalid") from exc
    if not isinstance(value, dict) or value.get("version") != spec.version or value.get("background") is not True:
        raise BlenderRuntimeError("Blender preflight result differs")
    return value


def runtime_status(runtime_root: Path, spec: RuntimeSpec, preflight_script: Path) -> dict[str, object]:
    install = runtime_root / "install"
    executable = install / spec.executable
    stamp_path = runtime_root / ".runtime.json"
    if not stamp_path.is_file() or stamp_path.is_symlink():
        return {"state": "missing", "version": spec.version, "executable": str(executable)}
    try:
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"state": "invalid", "version": spec.version, "reason": "runtime stamp is unreadable"}
    if stamp != {
        "schema_version": 1,
        "version": spec.version,
        "archive_sha256": spec.archive_sha256,
        "executable": spec.executable,
    }:
        return {"state": "invalid", "version": spec.version, "reason": "runtime stamp differs"}
    try:
        facts = preflight(executable, preflight_script, spec)
    except BlenderRuntimeError as exc:
        return {"state": "invalid", "version": spec.version, "reason": str(exc)}
    return {"state": "ready", "version": spec.version, "executable": str(executable), "preflight": facts}


def build_runtime(runtime_root: Path, spec: RuntimeSpec, preflight_script: Path) -> dict[str, object]:
    runtime_root.mkdir(parents=True, exist_ok=True)
    current = runtime_status(runtime_root, spec, preflight_script)
    if current.get("state") == "ready":
        return {**current, "reused": True}
    archive_path = runtime_root / "downloads" / spec.archive_name
    if not archive_path.exists():
        _download(spec, archive_path)
    archive_facts = validate_archive(archive_path, spec)
    staging = Path(tempfile.mkdtemp(prefix=".extract-", dir=runtime_root))
    candidate = staging / spec.top_level_directory
    try:
        with tarfile.open(archive_path, mode="r:xz") as archive:
            archive.extractall(staging, filter="data")
        if not candidate.is_dir() or candidate.is_symlink():
            raise BlenderRuntimeError("Blender archive did not produce the pinned root")
        facts = preflight(candidate / spec.executable, preflight_script, spec)
        install = runtime_root / "install"
        previous = runtime_root / f".previous-{uuid.uuid4().hex}"
        if install.exists() or install.is_symlink():
            install.replace(previous)
        try:
            candidate.replace(install)
        except Exception:
            if previous.exists() and not install.exists():
                previous.replace(install)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        stamp = {
            "schema_version": 1,
            "version": spec.version,
            "archive_sha256": spec.archive_sha256,
            "executable": spec.executable,
        }
        temporary_stamp = runtime_root / ".runtime.json.tmp"
        temporary_stamp.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        temporary_stamp.replace(runtime_root / ".runtime.json")
        return {
            "state": "ready",
            "version": spec.version,
            "executable": str(install / spec.executable),
            "archive": archive_facts,
            "preflight": facts,
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "status"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = load_spec(args.manifest.resolve())
    runtime_root = args.runtime_root.resolve()
    preflight_script = DEFAULT_PREFLIGHT.resolve()
    allowed_root = (REPOSITORY_ROOT / "runtimes").resolve()
    if runtime_root == allowed_root or not runtime_root.is_relative_to(allowed_root):
        print(json.dumps({"state": "error", "version": spec.version, "reason": "runtime root escapes runtimes"}))
        return 1
    try:
        result = (
            build_runtime(runtime_root, spec, preflight_script)
            if args.action == "build"
            else runtime_status(runtime_root, spec, preflight_script)
        )
    except BlenderRuntimeError as exc:
        print(json.dumps({"state": "error", "version": spec.version, "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("state") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
