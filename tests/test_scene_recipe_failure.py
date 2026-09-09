from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mediaforge.scene_recipe_failure import recipe_failure_message
from mediaforge.scene_recipes import SceneRecipe


RECIPE = SceneRecipe.model_validate({"operations": [
    {"type": "transform.set", "object_id": "target", "location": [0, 0, 0]},
]})
VALID = {"schema_version": "media-forge.scene-recipe-failure@1",
         "blender_version": "4.5.13", "operation_index": 0, "reason": "object_not_found"}
FALLBACK = "Blender rejected the typed scene recipe"


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
def test_non_regular_diagnostics_do_not_block_or_follow(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "result.json"
    if kind == "symlink":
        target = tmp_path / "secret"
        target.write_text(json.dumps(VALID))
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "directory":
        path.mkdir()
    before = len(list(Path("/proc/self/fd").iterdir()))
    for _ in range(10):
        assert recipe_failure_message(path, RECIPE, "4.5.13") == FALLBACK
    assert len(list(Path("/proc/self/fd").iterdir())) == before
