"""Diagnostic input guards; real Blender execution is a separate acceptance."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


def runner():
    path = Path(__file__).parents[1] / "scripts/3ds_prepared_mesh_e2e.py"
    spec = importlib.util.spec_from_file_location("prepared_mesh_diagnostic", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_evidence_is_not_overwritten(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    marker = evidence / "observations.json"
    marker.write_text("previous result")
    with pytest.raises(AssertionError, match="empty owned"):
        runner().run(argparse.Namespace(evidence_dir=evidence))
    assert marker.read_text() == "previous result"
    assert list(evidence.iterdir()) == [marker]


def test_oversized_recipe_is_rejected_before_runtime_copy(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    recipe = tmp_path / "recipe.json"
    recipe.write_bytes(b" " * 8193)
    with pytest.raises(AssertionError):
        runner().run(argparse.Namespace(evidence_dir=evidence, recipe=recipe))
    assert not list(evidence.iterdir())
