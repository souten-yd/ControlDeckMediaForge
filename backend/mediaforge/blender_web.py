"""Pinned, separately managed browser-operation runtime for Web Blender."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from typing import Any, Callable

from .paths import contained


WEB_PACK_STATUS_SCHEMA = "media-forge.blender-web-pack-status@1"
MAX_WEB_PACK_MANIFEST_BYTES = 128 * 1024
MAX_WEB_PACK_MEMBERS = 4096
MAX_WEB_PACK_EXTRACTED_BYTES = 256 * 1024 * 1024
MAX_CLIENT_MODULE_BYTES = 512 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PACK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class BlenderWebPackError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WebPackComponent:
    id: str
    version: str
    archive_name: str
    archive_url: str
    archive_size_bytes: int
    archive_sha256: str
    top_level_directory: str
    license: str
    source_url: str


@dataclass(frozen=True)
class WebPackRequiredFile:
    path: str
    sha256: str
    executable: bool


@dataclass(frozen=True)
class BlenderWebPackSpec:
    pack_id: str
    version: str
    platform: str
    components: tuple[WebPackComponent, ...]
    required_files: tuple[WebPackRequiredFile, ...]

    @property
    def archive_size_bytes(self) -> int:
        return sum(item.archive_size_bytes for item in self.components)


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise BlenderWebPackError("blender_web_catalog_invalid", "web pack path is invalid")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise BlenderWebPackError("blender_web_catalog_invalid", "web pack path is invalid")
    return value


def load_web_pack_spec(path: Path) -> BlenderWebPackSpec:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_WEB_PACK_MANIFEST_BYTES:
        raise BlenderWebPackError("blender_web_catalog_invalid", "web pack catalog is unavailable")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlenderWebPackError("blender_web_catalog_invalid", "web pack catalog is invalid") from exc
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "pack_id", "version", "platform", "components", "required_files"
    }:
        raise BlenderWebPackError("blender_web_catalog_invalid", "web pack catalog fields are invalid")
    if (
        value["schema_version"] != 1
        or not isinstance(value["pack_id"], str)
        or not PACK_ID_PATTERN.fullmatch(value["pack_id"])
        or not isinstance(value["version"], str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["version"])
        or value["platform"] != "linux-x86_64"
        or not isinstance(value["components"], list)
        or not 1 <= len(value["components"]) <= 8
        or not isinstance(value["required_files"], list)
        or not 1 <= len(value["required_files"]) <= 128
    ):
        raise BlenderWebPackError("blender_web_catalog_invalid", "web pack catalog is invalid")
    components: list[WebPackComponent] = []
    seen_components: set[str] = set()
    for row in value["components"]:
        if not isinstance(row, dict) or set(row) != {
            "id", "version", "archive_name", "archive_url", "archive_size_bytes",
            "archive_sha256", "top_level_directory", "license", "source_url",
        }:
            raise BlenderWebPackError("blender_web_catalog_invalid", "web pack component is invalid")
        component_id = _safe_relative(row["id"])
        archive_name = _safe_relative(row["archive_name"])
        top_level = _safe_relative(row["top_level_directory"])
        if (
            "/" in component_id
            or "/" in archive_name
            or "/" in top_level
            or component_id in seen_components
            or not isinstance(row["version"], str)
            or not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", row["version"])
            or not isinstance(row["archive_url"], str)
            or not row["archive_url"].startswith("https://")
            or not isinstance(row["source_url"], str)
            or not row["source_url"].startswith("https://")
            or not isinstance(row["archive_size_bytes"], int)
            or not 1 <= row["archive_size_bytes"] <= 128 * 1024 * 1024
            or not isinstance(row["archive_sha256"], str)
            or not SHA256_PATTERN.fullmatch(row["archive_sha256"])
            or not isinstance(row["license"], str)
            or not 1 <= len(row["license"]) <= 64
        ):
            raise BlenderWebPackError("blender_web_catalog_invalid", "web pack component is invalid")
        seen_components.add(component_id)
        components.append(WebPackComponent(
            id=component_id,
            version=row["version"],
            archive_name=archive_name,
            archive_url=row["archive_url"],
            archive_size_bytes=row["archive_size_bytes"],
            archive_sha256=row["archive_sha256"],
            top_level_directory=top_level,
            license=row["license"],
            source_url=row["source_url"],
        ))
    required: list[WebPackRequiredFile] = []
    seen_files: set[str] = set()
    for row in value["required_files"]:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "executable"}:
            raise BlenderWebPackError("blender_web_catalog_invalid", "required web pack file is invalid")
        relative = _safe_relative(row["path"])
        if (
            relative in seen_files
            or relative.split("/", 1)[0] not in seen_components
            or not isinstance(row["sha256"], str)
            or not SHA256_PATTERN.fullmatch(row["sha256"])
            or not isinstance(row["executable"], bool)
        ):
            raise BlenderWebPackError("blender_web_catalog_invalid", "required web pack file is invalid")
        seen_files.add(relative)
        required.append(WebPackRequiredFile(relative, row["sha256"], row["executable"]))
    return BlenderWebPackSpec(
        pack_id=value["pack_id"], version=value["version"], platform=value["platform"],
        components=tuple(components), required_files=tuple(required),
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_web_pack_archive(path: Path, component: WebPackComponent) -> dict[str, int]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size != component.archive_size_bytes:
        raise BlenderWebPackError("blender_web_verify_failed", "web pack archive size differs")
    if _hash_file(path) != component.archive_sha256:
        raise BlenderWebPackError("blender_web_verify_failed", "web pack archive hash differs")
    names: set[str] = set()
    members = 0
    extracted = 0
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            for member in archive:
                members += 1
                if members > MAX_WEB_PACK_MEMBERS:
                    raise BlenderWebPackError("blender_web_verify_failed", "web pack has too many members")
                relative = _safe_relative(member.name.rstrip("/"))
                if relative in names or relative.split("/", 1)[0] != component.top_level_directory:
                    raise BlenderWebPackError("blender_web_verify_failed", "web pack member path is invalid")
                names.add(relative)
                if not (member.isdir() or member.isfile()):
                    raise BlenderWebPackError("blender_web_verify_failed", "web pack contains a link or device")
                if member.isfile():
                    extracted += member.size
                    if extracted > MAX_WEB_PACK_EXTRACTED_BYTES:
                        raise BlenderWebPackError("blender_web_verify_failed", "web pack expands beyond its limit")
    except BlenderWebPackError as exc:
        if exc.code == "blender_web_verify_failed":
            raise
        raise BlenderWebPackError(
            "blender_web_verify_failed", "web pack member path is invalid"
        ) from exc
    except (tarfile.TarError, OSError) as exc:
        raise BlenderWebPackError("blender_web_verify_failed", "web pack archive is unreadable") from exc
    if component.top_level_directory not in names:
        raise BlenderWebPackError("blender_web_verify_failed", "web pack root is missing")
    return {"members": members, "extracted_bytes": extracted}


def extract_web_pack_archive(
    path: Path,
    destination: Path,
    component: WebPackComponent,
    cancel_requested: Callable[[], bool],
) -> None:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            for member in archive:
                if cancel_requested():
                    raise BlenderWebPackError("blender_runtime_operation_canceled", "web pack install was canceled")
                archive.extract(member, destination, filter="data")
    except BlenderWebPackError:
        raise
    except (tarfile.TarError, OSError) as exc:
        raise BlenderWebPackError("blender_web_extract_failed", "web pack extraction failed") from exc
    extracted = contained(destination, destination / component.top_level_directory)
    if extracted.is_symlink() or not extracted.is_dir():
        raise BlenderWebPackError("blender_web_extract_failed", "web pack root was not extracted")


class BlenderWebPack:
    """Resolve and verify one immutable web-operation pack without returning paths."""

    def __init__(self, manifest_path: Path, managed_root: Path) -> None:
        self.manifest_path = Path(os.path.abspath(manifest_path))
        self.managed_root = managed_root.resolve()

    def spec(self) -> BlenderWebPackSpec:
        return load_web_pack_spec(self.manifest_path)

    def destination(self, spec: BlenderWebPackSpec | None = None) -> Path:
        selected = spec or self.spec()
        return contained(self.managed_root, self.managed_root / selected.pack_id)

    @staticmethod
    def _required_checks(root: Path, spec: BlenderWebPackSpec) -> dict[str, bool]:
        checks: dict[str, bool] = {}
        for item in spec.required_files:
            path = contained(root, root / "install" / item.path)
            checks[item.path] = (
                not path.is_symlink()
                and path.is_file()
                and _hash_file(path) == item.sha256
                and (not item.executable or os.access(path, os.X_OK))
            )
        return checks

    def status(self) -> dict[str, Any]:
        try:
            spec = self.spec()
            root = self.destination(spec)
            checks = self._required_checks(root, spec) if root.is_dir() and not root.is_symlink() else {}
            stamp_path = contained(root, root / ".web-runtime.json")
            expected_stamp = {
                "schema_version": 1,
                "pack_id": spec.pack_id,
                "version": spec.version,
                "components": {item.id: item.archive_sha256 for item in spec.components},
            }
            stamp_ok = False
            try:
                stamp_ok = (
                    not stamp_path.is_symlink()
                    and stamp_path.is_file()
                    and stamp_path.stat().st_size <= 64 * 1024
                    and json.loads(stamp_path.read_text(encoding="utf-8")) == expected_stamp
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
            ready = stamp_ok and len(checks) == len(spec.required_files) and all(checks.values())
            state = "ready" if ready else ("damaged" if root.exists() or root.is_symlink() else "missing")
            payload: dict[str, Any] = {
                "schema_version": WEB_PACK_STATUS_SCHEMA,
                "state": state,
                "pack_id": spec.pack_id,
                "version": spec.version,
                "archive_size_bytes": spec.archive_size_bytes,
                "install_available": state == "missing",
                "components": [
                    {"id": item.id, "version": item.version, "license": item.license,
                     "source": item.source_url}
                    for item in spec.components
                ],
                "checks": {"stamp": stamp_ok, "required_files": bool(checks) and all(checks.values())},
            }
        except (BlenderWebPackError, OSError, ValueError):
            payload = {
                "schema_version": WEB_PACK_STATUS_SCHEMA,
                "state": "invalid",
                "reason": "blender_web_catalog_invalid",
                "install_available": False,
                "components": [],
                "checks": {"stamp": False, "required_files": False},
            }
        identity = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**payload, "fingerprint": hashlib.sha256(identity).hexdigest()}

    def client_file(self, relative: str) -> Path:
        """Resolve one integrity-checked noVNC module without exposing pack paths."""
        try:
            safe = _safe_relative(relative)
            if not safe.endswith(".js") or not (
                safe.startswith("core/") or safe.startswith("vendor/pako/lib/")
            ):
                raise BlenderWebPackError(
                    "blender_web_client_unavailable", "browser client module is unavailable"
                )
            spec = self.spec()
            expected = next(
                (item for item in spec.required_files if item.path == f"novnc/{safe}"), None
            )
            if expected is None:
                raise BlenderWebPackError(
                    "blender_web_client_unavailable", "browser client module is unavailable"
                )
            root = self.destination(spec)
            path = contained(root, root / "install" / expected.path)
            if (
                path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size <= MAX_CLIENT_MODULE_BYTES
                or _hash_file(path) != expected.sha256
            ):
                raise BlenderWebPackError(
                    "blender_web_client_unavailable", "browser client module is unavailable"
                )
            return path
        except (BlenderWebPackError, OSError, ValueError) as exc:
            if isinstance(exc, BlenderWebPackError) and exc.code == "blender_web_client_unavailable":
                raise
            raise BlenderWebPackError(
                "blender_web_client_unavailable", "browser client module is unavailable"
            ) from exc

    def probe(self, root: Path, spec: BlenderWebPackSpec) -> dict[str, Any]:
        checks = self._required_checks(root, spec)
        if len(checks) != len(spec.required_files) or not all(checks.values()):
            raise BlenderWebPackError("blender_web_probe_failed", "web pack required file differs")
        install = contained(root, root / "install")
        xvnc = contained(install, install / "tigervnc/usr/bin/Xvnc")
        passwd = contained(install, install / "tigervnc/usr/bin/vncpasswd")
        environment = {
            "HOME": "/nonexistent", "LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin",
            "LD_LIBRARY_PATH": str(install / "tigervnc/usr/lib64"),
        }
        try:
            version = subprocess.run(
                [str(xvnc), "-version"], capture_output=True, text=True, timeout=15,
                check=False, env=environment,
            )
            password_help = subprocess.run(
                [str(passwd), "-h"], capture_output=True, text=True, timeout=15,
                check=False, env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BlenderWebPackError("blender_web_probe_failed", "web pack executable probe failed") from exc
        version_output = (version.stdout + version.stderr)[:8192]
        passwd_output = (password_help.stdout + password_help.stderr)[:8192]
        if "Xvnc TigerVNC 1.16.2" not in version_output or "vncpasswd" not in passwd_output:
            raise BlenderWebPackError("blender_web_probe_failed", "web pack executable identity differs")
        package_path = contained(install, install / "novnc/package.json")
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderWebPackError("blender_web_probe_failed", "noVNC package identity is invalid") from exc
        if package.get("name") != "@novnc/novnc" or package.get("version") != "1.7.0":
            raise BlenderWebPackError("blender_web_probe_failed", "noVNC package identity differs")
        return {"tigervnc": "1.16.2", "novnc": "1.7.0", "software_display": True}

    def write_stamp(self, root: Path, spec: BlenderWebPackSpec) -> None:
        stamp = {
            "schema_version": 1,
            "pack_id": spec.pack_id,
            "version": spec.version,
            "components": {item.id: item.archive_sha256 for item in spec.components},
        }
        path = contained(root, root / ".web-runtime.json")
        path.write_text(json.dumps(stamp, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        path.chmod(0o600)
