"""Fixture contract tests; real mesh contact/render checks run in Blender."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from mediaforge.scene_recipes import SceneCreateRequest


def test_robot_uses_public_bounded_recipe() -> None:
    spec = importlib.util.spec_from_file_location("robot_fixture", Path(__file__).parents[1] / "scripts/robot_fixture.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    operations = module.recipe()
    request = SceneCreateRequest.model_validate({"name": "Robot", "recipe": {"operations": operations}})
    assert len(request.recipe.operations) <= 64
    ids = {op["object_id"] for op in operations if op["type"] in ("primitive.add", "object.duplicate")}
    pairs = module.contact_pairs()
    assert len(pairs) == 24
    assert all(a in ids and b in ids and a != b for a, b in pairs)
    assert len(ids) == 25
