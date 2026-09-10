from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

import mediaforge.scene_recipe_failure as failure_reader
from mediaforge.scene_recipe_failure import recipe_failure_message
from mediaforge.scene_recipes import SceneRecipe


RECIPE = SceneRecipe.model_validate({"operations": [
    {"type": "transform.set", "object_id": "target", "location": [0, 0, 0]},
]})
VALID = {"schema_version": "media-forge.scene-recipe-failure@1",
         "blender_version": "4.5.13", "operation_index": 0, "reason": "object_not_found"}
FALLBACK = "Blender rejected the typed scene recipe"


@pytest.fixture
def diagnostic_fds(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[list[int], set[int]]]:
    """Track this reader's actual descriptors, not unrelated process-wide cleanup."""
    opened: list[int] = []
    outstanding: set[int] = set()

    def open_fd(path: Path, flags: int) -> int:
        fd = os.open(path, flags)
        opened.append(fd)
        outstanding.add(fd)
        return fd

    def close_fd(fd: int) -> None:
        os.close(fd)
        outstanding.remove(fd)

    proxy = SimpleNamespace(**{name: getattr(os, name) for name in (
        "O_RDONLY", "O_NOFOLLOW", "O_NONBLOCK", "fstat", "read")},
        open=open_fd, close=close_fd)
    monkeypatch.setattr(failure_reader, "os", proxy)
    try:
        yield opened, outstanding
    finally:
        for fd in outstanding:
            os.close(fd)


def test_failure_context_uses_original_typed_input(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(VALID))
    assert recipe_failure_message(path, RECIPE, "4.5.13") == (
        "Operation 1/1 (transform.set, object_id=target) failed: "
        "target object does not exist; inspect stable object IDs"
    )


@pytest.mark.parametrize("changes", [
    {"operation_index": True}, {"operation_index": -1}, {"operation_index": 1},
    {"operation_index": 0.0}, {"operation_index": "0"},
    {"reason": []}, {"reason": "/private/secret"},
    {"blender_version": "4.5.9"}, {"schema_version": "unknown"},
    {"traceback": "/private/secret"},
])
def test_invalid_context_never_leaks_worker_data(tmp_path: Path, changes: dict) -> None:
    path = tmp_path / "result.json"
    path.write_text(json.dumps({**VALID, **changes}))
    assert recipe_failure_message(path, RECIPE, "4.5.13") == FALLBACK


@pytest.mark.parametrize("data", [b"", b"null", b"[]", b"{}", b"\xff", b"x" * 4097,
                                  b"[" * 1500 + b"]" * 1500])
def test_invalid_result_bytes(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "result.json"
    path.write_bytes(data)
    assert recipe_failure_message(path, RECIPE, "4.5.13") == FALLBACK


@pytest.mark.parametrize("kind", ["missing", "symlink", "fifo", "directory"])
def test_non_regular_diagnostics_do_not_block_or_follow(
    tmp_path: Path, kind: str, diagnostic_fds: tuple[list[int], set[int]],
) -> None:
    path = tmp_path / "result.json"
    if kind == "symlink":
        target = tmp_path / "secret"
        target.write_text(json.dumps(VALID))
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "directory":
        path.mkdir()
    opened, outstanding = diagnostic_fds
    for _ in range(10):
        assert recipe_failure_message(path, RECIPE, "4.5.13") == FALLBACK
        assert not outstanding
    assert len(opened) == (10 if kind in {"fifo", "directory"} else 0)


def test_descriptor_tracker_detects_missing_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, diagnostic_fds: tuple[list[int], set[int]],
) -> None:
    path = tmp_path / "directory"
    path.mkdir()
    monkeypatch.setattr(failure_reader.os, "close", lambda fd: None)
    assert recipe_failure_message(path, RECIPE, "4.5.13") == FALLBACK
    opened, outstanding = diagnostic_fds
    assert len(opened) == len(outstanding) == 1
    os.fstat(opened[0])  # Deliberately leaked descriptor is still real; fixture reclaims it.


def test_unrelated_descriptor_cleanup_does_not_mask_reader_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, diagnostic_fds: tuple[list[int], set[int]],
) -> None:
    path = tmp_path / "directory"
    path.mkdir()
    unrelated = os.open(path, os.O_RDONLY)

    def fstat_with_cleanup(fd: int) -> os.stat_result:
        nonlocal unrelated
        os.close(unrelated)
        unrelated = -1
        return os.fstat(fd)

    monkeypatch.setattr(failure_reader.os, "fstat", fstat_with_cleanup)
    try:
        assert recipe_failure_message(path, RECIPE, "4.5.13") == FALLBACK
        opened, outstanding = diagnostic_fds
        assert len(opened) == 1 and not outstanding and unrelated == -1
    finally:
        if unrelated != -1:
            os.close(unrelated)
