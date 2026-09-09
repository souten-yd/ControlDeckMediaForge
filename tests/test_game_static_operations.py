from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import jsonschema
from pydantic import ValidationError
import pytest

from mediaforge.scene_recipes import SceneCreateRequest, scene_operation_types

ROOT = Path(__file__).resolve().parents[1]


def request(*operations: dict[str, Any]) -> dict[str, Any]:
    return {"name": "Gate", "recipe": {"operations": list(operations)}}


def test_new_static_operations_match_published_schemas() -> None:
    value = request(
        {"type": "object.duplicate", "source_object_id": "post", "object_id": "copy", "name": "Copy"},
        {"type": "modifier.mirror", "object_id": "copy", "axes": ["X", "Z"], "reference_object_id": "origin"},
    )
    SceneCreateRequest.model_validate(value)
    jsonschema.validate(value, json.loads((ROOT / "schemas/scene-create-request.json").read_text()))
    for filename, extended in (
        ("scene-edit-request.json", {"scene_id": "scene_" + "a"*32, "base_revision_id": "revision_" + "b"*32,
                                    "recipe": value["recipe"]}),
        ("scene-workflow-request.json", {"action": "create", **value}),
    ):
        jsonschema.validate(extended, json.loads((ROOT / "schemas" / filename).read_text()))
    assert set(scene_operation_types()) == {
        "primitive.add", "transform.set", "modifier.bevel", "material.set", "uv.smart_project",
        "light.add", "camera.add", "object.duplicate", "modifier.mirror",
        "armature.create", "skin.bind", "pose.set",
        "animation.clip",
    }


@pytest.mark.parametrize("operation", [
    {"type": "object.duplicate", "source_object_id": "same", "object_id": "same", "name": "Invalid"},
    {"type": "object.duplicate", "source_object_id": "old", "object_id": "../new", "name": "Invalid"},
    {"type": "object.duplicate", "source_object_id": "old", "object_id": "new", "name": "New", "location": [float("inf"),0,0]},
    {"type": "modifier.mirror", "object_id": "mesh", "axes": []},
    {"type": "modifier.mirror", "object_id": "mesh", "axes": ["X","X"]},
    {"type": "modifier.mirror", "object_id": "mesh", "axes": ["Q"]},
    {"type": "modifier.mirror", "object_id": "mesh", "reference_object_id": "mesh"},
    {"type": "modifier.mirror", "object_id": "mesh", "merge_threshold": 0.2},
    {"type": "modifier.mirror", "object_id": "mesh", "python": "print(1)"},
])
def test_static_operations_reject_invalid_input(operation: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SceneCreateRequest.model_validate(request(operation))


def test_duplicate_reserves_new_stable_id() -> None:
    operation = {"type": "object.duplicate", "source_object_id": "old", "object_id": "copy", "name": "Copy"}
    with pytest.raises(ValidationError, match="duplicate object_id"):
        SceneCreateRequest.model_validate(request(operation, operation))


def test_capability_operations_only_advertised_with_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient
    from conftest import fake_settings
    from mediaforge.app import create_app

    app = create_app(fake_settings(tmp_path))
    with TestClient(app) as client:
        monkeypatch.setattr(app.state.blender_runtimes, "resolve_g8", lambda: None)
        unavailable = client.get("/api/v1/capabilities").json()["capabilities"]["3d.scene_recipe"]
        assert unavailable["state"] == "unavailable"
        assert "supported_operations" not in unavailable
        monkeypatch.setattr(app.state.blender_runtimes, "resolve_g8", lambda: object())
        available = client.get("/api/v1/capabilities").json()["capabilities"]["3d.scene_recipe"]
        assert available["supported_operations"] == scene_operation_types()


def worker(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setitem(sys.modules, "bpy", SimpleNamespace())
    spec = importlib.util.spec_from_file_location("static_worker", ROOT / "worker_packs/blender/scene_recipe.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mesh(modifiers: list[Any] | None = None) -> Any:
    return SimpleNamespace(type="MESH", data=SimpleNamespace(vertices=range(8),
        polygons=[SimpleNamespace(loop_total=4)]*6), modifiers=modifiers or [])


def test_growth_budget_prevents_exponential_mirror_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    module = worker(monkeypatch)
    obj = mesh([SimpleNamespace(type="MIRROR", use_axis=(True, True, True))])
    assert module.geometry_cost(obj) == 96
    module.check_growth({"mesh": obj}, 96)
    with pytest.raises(RuntimeError, match="budget"):
        module.check_growth({"mesh": obj}, module.MAX_GROWTH_GEOMETRY)
    with pytest.raises(RuntimeError, match="unsupported modifiers"):
        module.geometry_cost(mesh([SimpleNamespace(type="NODES")]))


def test_worker_rejects_missing_source_and_second_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    module = worker(monkeypatch)
    with pytest.raises(RuntimeError, match="known mesh"):
        module.apply_operation({"type":"object.duplicate","object_id":"copy","source_object_id":"missing"}, {})
    obj = mesh([SimpleNamespace(type="MIRROR")])
    with pytest.raises(RuntimeError, match="one mirror"):
        module.apply_operation({"type":"modifier.mirror","object_id":"mesh","axes":["X"]}, {"mesh":obj})
