from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import SceneCreateRequest
from test_game_static_operations import ROOT, mesh, request, worker


def operation(**changes: Any) -> dict[str, Any]:
    return {"type": "modifier.array", "object_id": "step", "count": 6,
            "local_offset": [1.5, 0, 1.5], **changes}


def test_array_matches_all_published_schemas() -> None:
    value = request(operation())
    SceneCreateRequest.model_validate(value)
    for name, payload in (
        ("scene-create-request.json", value),
        ("scene-edit-request.json", {"scene_id": "scene_" + "a"*32,
            "base_revision_id": "revision_" + "b"*32, "recipe": value["recipe"]}),
        ("scene-workflow-request.json", {"action": "create", **value}),
    ):
        jsonschema.validate(payload, json.loads((ROOT / "schemas" / name).read_text()))


@pytest.mark.parametrize("changes", [
    {"count": 1}, {"count": 65}, {"count": True}, {"count": 2.5},
    {"local_offset": [0, 0, 0]}, {"local_offset": [1, 2]},
    {"local_offset": [float("nan"), 0, 0]}, {"local_offset": [10001, 0, 0]},
    {"fit_type": "FIT_CURVE"}, {"python": "pass"},
])
def test_invalid_array_input_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SceneCreateRequest.model_validate(request(operation(**changes)))


def array() -> Any:
    return SimpleNamespace(type="ARRAY", fit_type="FIXED_COUNT", count=6,
        use_relative_offset=False, use_object_offset=False, use_constant_offset=True,
        offset_object=None, start_cap=None, end_cap=None)


def static_mesh(modifiers: list[Any] | None = None) -> Any:
    obj = mesh(modifiers)
    obj.parent, obj.constraints, obj.animation_data = None, [], None
    obj.data.shape_keys, obj.data.animation_data = None, None
    return obj


def test_array_growth_counts_duplicate_and_bevel_before_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    module = worker(monkeypatch)
    obj = static_mesh([array()])
    assert module.geometry_cost(obj) == 72
    module.check_growth({"step": obj}, 72)
    module.MAX_GROWTH_GEOMETRY = 100
    with pytest.raises(RuntimeError, match="budget"):
        module.check_growth({"step": obj}, 72)
    with pytest.raises(RuntimeError, match="budget"):
        module.apply_operation({"type": "modifier.bevel", "object_id": "step", "width": .01,
                                "segments": 8}, {"step": obj})
    assert len(obj.modifiers) == 1


@pytest.mark.parametrize("field,value", [("fit_type", "FIT_CURVE"), ("count", 65),
    ("use_relative_offset", True), ("use_object_offset", True), ("use_constant_offset", False),
    ("offset_object", object()), ("start_cap", object()), ("end_cap", object())])
def test_unsupported_gui_array_is_not_assumed_bounded(monkeypatch: pytest.MonkeyPatch, field: str, value: Any) -> None:
    module = worker(monkeypatch)
    modifier = array()
    setattr(modifier, field, value)
    with pytest.raises(RuntimeError, match="unsupported array"):
        module.geometry_cost(mesh([modifier]))


@pytest.mark.parametrize("case", ["count", "zero", "duplicate", "parent", "animation", "shape", "budget"])
def test_worker_rejects_array_before_allocating(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    module = worker(monkeypatch)
    obj = static_mesh()
    op = operation()
    if case == "count": op["count"] = True
    elif case == "zero": op["local_offset"] = [0, 0, 0]
    elif case == "duplicate": obj.modifiers = [array()]
    elif case == "parent": obj.parent = object()
    elif case == "animation": obj.animation_data = object()
    elif case == "shape": obj.data.shape_keys = object()
    elif case == "budget": module.MAX_GROWTH_GEOMETRY = 50
    before = list(obj.modifiers)
    with pytest.raises(RuntimeError):
        module.apply_operation(op, {"step": obj})
    assert obj.modifiers == before
