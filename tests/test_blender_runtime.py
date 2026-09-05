from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from scripts import blender_runtime
from scripts.blender_runtime import (
    BlenderRuntimeError,
    RuntimeSpec,
    _safe_link_target,
    _safe_member_path,
    load_spec,
    runtime_status,
    validate_archive,
    validate_spec,
)


def spec_for(path: Path, *, size: int, digest: str) -> RuntimeSpec:
    return RuntimeSpec(
        schema_version=1,
        version="4.5.9",
        archive_name=path.name,
        archive_url=f"https://download.blender.org/release/Blender4.5/{path.name}",
        archive_size_bytes=size,
        archive_sha256=digest,
        top_level_directory=path.name.removesuffix(".tar.xz"),
        executable="blender",
        license="GPL-3.0-or-later",
        source_url="https://projects.blender.org/blender/blender",
    )


def write_archive(path: Path, members: list[tarfile.TarInfo]) -> None:
    with tarfile.open(path, "w:xz") as archive:
        for member in members:
            content = b"#!/bin/sh\n" if member.isfile() else b""
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content) if content else None)


def test_checked_in_manifest_is_exact_official_lts_archive() -> None:
    spec = load_spec(Path("config/blender-runtime.json"))
    assert spec.version == "4.5.9"
    assert spec.archive_size_bytes == 377_929_956
    assert spec.archive_sha256 == "dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d"
    assert spec.license == "GPL-3.0-or-later"


def test_runtime_catalog_pins_supported_and_recommended_lts_versions() -> None:
    value = json.loads(Path("config/blender-runtime-catalog.json").read_text(encoding="utf-8"))
    assert set(value) == {
        "schema_version", "base_runtime_id", "recommended_studio_runtime_id", "runtimes"
    }
    assert value["schema_version"] == 1
    entries = {row["runtime_id"]: validate_spec(row["spec"]) for row in value["runtimes"]}
    assert entries[value["base_runtime_id"]].version == "4.5.9"
    recommended = entries[value["recommended_studio_runtime_id"]]
    assert recommended.version == "4.5.13"
    assert recommended.archive_size_bytes == 378_033_952
    assert recommended.archive_sha256 == (
        "da4e69b06b75b9e642d106496c50e7e240218b411d2f6e18271c1d1d819cef91"
    )


def test_manifest_rejects_unpinned_host(tmp_path: Path) -> None:
    value = json.loads(Path("config/blender-runtime.json").read_text(encoding="utf-8"))
    value["archive_url"] = "https://example.invalid/blender-4.5.9-linux-x64.tar.xz"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(BlenderRuntimeError, match="pinned boundary"):
        load_spec(manifest)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "other/file"])
def test_archive_member_must_stay_in_pinned_root(name: str) -> None:
    with pytest.raises(BlenderRuntimeError, match="escapes"):
        _safe_member_path(name, "blender-4.5.9-linux-x64")


def test_archive_link_must_stay_in_pinned_root() -> None:
    safe = tarfile.TarInfo("blender-4.5.9-linux-x64/lib/current.so")
    safe.type = tarfile.SYMTYPE
    safe.linkname = "target.so"
    _safe_link_target(safe, "blender-4.5.9-linux-x64")

    escaped = tarfile.TarInfo("blender-4.5.9-linux-x64/lib/current.so")
    escaped.type = tarfile.SYMTYPE
    escaped.linkname = "../../outside"
    with pytest.raises(BlenderRuntimeError, match="escapes"):
        _safe_link_target(escaped, "blender-4.5.9-linux-x64")


def test_validate_archive_checks_members_size_and_hash(tmp_path: Path) -> None:
    archive = tmp_path / "blender-test-linux-x64.tar.xz"
    directory = tarfile.TarInfo("blender-test-linux-x64")
    directory.type = tarfile.DIRTYPE
    executable = tarfile.TarInfo("blender-test-linux-x64/blender")
    executable.mode = 0o755
    write_archive(archive, [directory, executable])
    content = archive.read_bytes()
    spec = RuntimeSpec(
        schema_version=1,
        version="4.5.9",
        archive_name=archive.name,
        archive_url=f"https://download.blender.org/release/Blender4.5/{archive.name}",
        archive_size_bytes=len(content),
        archive_sha256=hashlib.sha256(content).hexdigest(),
        top_level_directory="blender-test-linux-x64",
        executable="blender",
        license="GPL-3.0-or-later",
        source_url="https://projects.blender.org/blender/blender",
    )
    assert validate_archive(archive, spec) == {"member_count": 2, "extracted_bytes": 10}
    with pytest.raises(BlenderRuntimeError, match="size differs"):
        validate_archive(archive, replace(spec, archive_size_bytes=len(content) + 1))


def test_validate_archive_rejects_device_member(tmp_path: Path) -> None:
    archive = tmp_path / "blender-test-linux-x64.tar.xz"
    device = tarfile.TarInfo("blender-test-linux-x64/device")
    device.type = tarfile.CHRTYPE
    write_archive(archive, [device])
    content = archive.read_bytes()
    spec = spec_for(archive, size=len(content), digest=hashlib.sha256(content).hexdigest())
    with pytest.raises(BlenderRuntimeError, match="device or FIFO"):
        validate_archive(archive, spec)


def test_runtime_status_fails_closed_without_stamp(tmp_path: Path) -> None:
    spec = load_spec(Path("config/blender-runtime.json"))
    assert runtime_status(tmp_path, spec, Path("worker_packs/blender/preflight.py"))["state"] == "missing"


def test_build_reuses_a_preflighted_runtime_without_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = load_spec(Path("config/blender-runtime.json"))
    monkeypatch.setattr(
        blender_runtime,
        "runtime_status",
        lambda *_args: {"state": "ready", "version": spec.version, "preflight": {"background": True}},
    )
    monkeypatch.setattr(
        blender_runtime,
        "_download",
        lambda *_args: (_ for _ in ()).throw(AssertionError("ready runtime downloaded again")),
    )
    result = blender_runtime.build_runtime(tmp_path, spec, Path("worker_packs/blender/preflight.py"))
    assert result["state"] == "ready" and result["reused"] is True
