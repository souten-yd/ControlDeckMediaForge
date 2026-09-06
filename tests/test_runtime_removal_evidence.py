"""Evidence verifier tests, not real runtime-deletion acceptance."""
import importlib
from pathlib import Path

import pytest

asset_hashes = importlib.import_module("scripts.3ds_runtime_removal_e2e").asset_hashes


def test_asset_hashes_detects_content_and_provenance_changes(tmp_path: Path) -> None:
    (tmp_path / "scene.blend").write_bytes(b"blend")
    (tmp_path / "preview.glb").write_bytes(b"glb")
    provenance = tmp_path / "scene.provenance.json"
    provenance.write_bytes(b"{}")
    before = asset_hashes(tmp_path)
    assert len(before) == 3
    assert before["scene.blend"]["size"] == 5
    provenance.write_bytes(b"[]")
    assert asset_hashes(tmp_path) != before


def test_asset_hashes_rejects_symlink(tmp_path: Path) -> None:
    (tmp_path / "scene.blend").write_bytes(b"blend")
    (tmp_path / "preview.glb").write_bytes(b"glb")
    (tmp_path / "link").symlink_to(tmp_path / "scene.blend")
    with pytest.raises(AssertionError):
        asset_hashes(tmp_path)


def test_asset_hashes_rejects_empty_baseline(tmp_path: Path) -> None:
    with pytest.raises(AssertionError):
        asset_hashes(tmp_path)
