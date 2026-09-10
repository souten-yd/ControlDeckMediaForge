from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from mediaforge.blender_publication import PublicationIdentity
from mediaforge.blender_publication_generation import MARKER_NAME, create_generation, read_generation


def candidate(root: Path) -> Path:
    value = root / ".staging" / ("blenderop_" + "1" * 32) / "candidate"
    value.mkdir(parents=True)
    return value


def test_exclusive_generation_survives_publication_rename(tmp_path: Path) -> None:
    staged = candidate(tmp_path)
    generation = create_generation(tmp_path, staged)
    assert len(generation) == 32 and read_generation(tmp_path, staged) == generation
    assert (staged / MARKER_NAME).stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        create_generation(tmp_path, staged)
    destination = tmp_path / "blender-4.5.9-linux-x64"
    staged.rename(destination)
    assert read_generation(tmp_path, destination) == generation
    with pytest.raises(ValueError):
        create_generation(tmp_path, destination)


@pytest.mark.parametrize("kind", ["long", "invalid", "symlink", "fifo", "directory"])
def test_invalid_markers_are_bounded_and_rejected(tmp_path: Path, kind: str) -> None:
    staged = candidate(tmp_path)
    marker = staged / MARKER_NAME
    assert read_generation(tmp_path, staged) is None
    if kind == "long":
        marker.write_bytes(b"a" * 1000)
    elif kind == "invalid":
        marker.write_bytes(b"z" * 32 + b"\n")
    elif kind == "symlink":
        outside = tmp_path / "outside"
        outside.write_bytes(b"a" * 32 + b"\n")
        marker.symlink_to(outside)
    elif kind == "fifo":
        os.mkfifo(marker)
    else:
        marker.mkdir()
    with pytest.raises((ValueError, OSError)):
        read_generation(tmp_path, staged)
    with pytest.raises(FileExistsError):
        create_generation(tmp_path, staged)


def test_candidate_symlink_and_escape_are_rejected(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    managed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = managed / "linked"
    linked.symlink_to(outside)
    for target in (outside, linked):
        with pytest.raises(ValueError):
            create_generation(managed, target)
        with pytest.raises(ValueError):
            read_generation(managed, target)
    assert list(outside.iterdir()) == []


def test_repair_cannot_reuse_previous_generation() -> None:
    with pytest.raises(ValidationError, match="new generation"):
        PublicationIdentity(runtime_id="blender-test", version="4.5.9", action="repair",
            archive_sha256="a" * 64, executable_sha256="b" * 64, previous_active_runtime_id="blender-test",
            previous_registration_sha256="c" * 64, previous_executable_sha256="b" * 64,
            recovered_directory=False, generation="1" * 32, previous_generation="1" * 32)


def test_previous_journal_identity_without_generation_is_still_readable() -> None:
    legacy = {"runtime_id": "blender-test", "version": "4.5.9", "action": "repair",
        "archive_sha256": "a" * 64, "executable_sha256": "b" * 64,
        "previous_active_runtime_id": "blender-test", "previous_registration_sha256": "c" * 64,
        "previous_executable_sha256": "b" * 64, "recovered_directory": False}
    identity = PublicationIdentity.model_validate(legacy)
    assert identity.generation is None and identity.previous_generation is None
    assert {key: value for key, value in identity.model_dump().items() if key in legacy} == legacy
