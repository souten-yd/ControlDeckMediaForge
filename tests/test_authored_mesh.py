from __future__ import annotations

import json
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import MeshCreate, SceneCreateRequest
from test_game_static_operations import ROOT, request, worker


def operation(**changes: Any) -> dict[str, Any]:
    return {"type": "mesh.create", "object_id": "cloth", "name": "Cloth panel",
            "vertices": [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]],
            "faces": [[0, 1, 2, 3]], **changes}


def test_authored_mesh_contracts() -> None:
    value = request(operation())
    parsed = SceneCreateRequest.model_validate(value)
    assert parsed.recipe.operations[0].smooth is True
    assert parsed.recipe.operations[0].require_closed is False
    for name, payload in (
        ("scene-create-request.json", value),
        ("scene-edit-request.json", {"scene_id": "scene_" + "a"*32,
         "base_revision_id": "revision_" + "b"*32, "recipe": value["recipe"]}),
        ("scene-workflow-request.json", {"action": "create", **value}),
    ):
        schema = json.loads((ROOT / "schemas" / name).read_text())
        assert schema["$defs"]["MeshCreate"] == MeshCreate.model_json_schema()
        jsonschema.validate(payload, schema)


@pytest.mark.parametrize("changes", [
    {"vertices": []}, {"vertices": [[0, 0, 0]] * 4097},
    {"vertices": [[0, 0, 0], [1, 0, 0], [2, 0, 0]], "faces": [[0, 1, 2]]},
    {"vertices": [[float("nan"), 0, 0], [1, 0, 0], [0, 1, 0]], "faces": [[0, 1, 2]]},
    {"faces": []}, {"faces": [[0, 1, 2]]*4097}, {"faces": [[0, 1, 4]]},
    {"faces": [[0, 1, 1]]}, {"faces": [[0, 1, 2, 3], [3, 2, 1, 0]]},
    {"faces": [[0, 1, 2]]}, {"faces": [[0, True, 2, 3]]},
    {"faces": [[0, 1.0, 2, 3]]}, {"faces": [[0, 1, 2, 3, 0]]}, {"smooth": "true"},
])
def test_invalid_topology_rejected_by_core_and_worker(monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]) -> None:
    value = operation(**changes)
    with pytest.raises(ValidationError):
        MeshCreate.model_validate(value)
    module = worker(monkeypatch)
    with pytest.raises((RuntimeError, ValueError, TypeError)):
        module.authored_mesh_data(value)


def test_open_surface_and_flat_shading_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    value = operation(smooth=False)
    parsed = MeshCreate.model_validate(value)
    vertices, faces = worker(monkeypatch).authored_mesh_data(parsed.model_dump(mode="json"))
    assert len(vertices) == 4 and faces == [[0, 1, 2, 3]]


def closed_operation() -> dict[str, Any]:
    return operation(require_closed=True, vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
                     faces=[[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])


@pytest.mark.parametrize("failure", [None, "open", "winding", "multiple", "string", "integer"])
def test_closed_requirement_independent_checks(monkeypatch: pytest.MonkeyPatch, failure: str | None) -> None:
    value = closed_operation()
    if failure == "open":
        value["faces"].pop()
    elif failure == "winding":
        value["faces"][0].reverse()
    elif failure == "multiple":
        value["vertices"].append([0, -1, 0])
        value["faces"].append([0, 1, 4])
    elif failure in {"string", "integer"}:
        value["require_closed"] = "true" if failure == "string" else 1
    module = worker(monkeypatch)
    if failure:
        with pytest.raises(ValidationError):
            MeshCreate.model_validate(value)
        with pytest.raises(RuntimeError, match="closed"):
            module.authored_mesh_data(value)
        # The stub has no Blender allocation API: closure must reject first.
        with pytest.raises(RuntimeError, match="closed"):
            module.apply_operation(value, {})
    else:
        parsed = MeshCreate.model_validate(value)
        vertices, faces = module.authored_mesh_data(parsed.model_dump(mode="json"))
        assert len(vertices) == 4 and len(faces) == 4


def test_open_cloth_explicit_false_remains_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    value = operation(require_closed=False)
    MeshCreate.model_validate(value)
    assert worker(monkeypatch).authored_mesh_data(value)[1] == [[0, 1, 2, 3]]


def test_r4_missing_caps_rejected_with_boundary_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # Observed real OpenCode shape: bottom and one top triangle were missing.
    value = operation(require_closed=True,
        vertices=[[x, y, z] for z in (0, .5) for x, y in
                  [(0, -.04), (.2, -.02), (.2, .04), (-.2, .04), (-.2, -.02)]],
        faces=[[0, 1, 6, 5], [1, 2, 7, 6], [2, 3, 8, 7], [3, 4, 9, 8], [4, 0, 5, 9],
               [5, 6, 7], [7, 8, 9]])
    with pytest.raises(ValidationError, match="boundary=8"):
        MeshCreate.model_validate(value)
    with pytest.raises(RuntimeError, match="boundary=8"):
        worker(monkeypatch).authored_mesh_data(value)


def test_new_mesh_reserves_id_and_budget_before_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="duplicate object_id"):
        SceneCreateRequest.model_validate(request(operation(), operation()))
    module = worker(monkeypatch)
    with pytest.raises(RuntimeError, match="already exists"):
        module.apply_operation(operation(), {"cloth": object()})
    module.MAX_GROWTH_GEOMETRY = 3
    with pytest.raises(RuntimeError, match="budget"):
        module.apply_operation(operation(), {})


def test_arbitrary_code_and_paths_are_not_mesh_inputs() -> None:
    for key in ("script", "operator", "path", "url"):
        with pytest.raises(ValidationError):
            MeshCreate.model_validate(operation(**{key: "untrusted"}))


def test_guidance_is_fresh_json_and_does_not_assert_vision() -> None:
    from mediaforge.scene_authoring_guidance import scene_authoring_guidance
    first = scene_authoring_guidance()
    json.dumps(first, allow_nan=False)
    first["workflow"].clear()
    second = scene_authoring_guidance()
    assert len(second["workflow"]) == 6
    assert "NOT TESTED" in second["visual_review"]["rule"]
    assert "rotations only" in second["operation_notes"]["pose.set"]


def test_character_fixture_is_valid_bounded_geometry() -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("character_fixture", ROOT / "scripts/3ds_authored_character_e2e.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parsed = SceneCreateRequest.model_validate(module.character_recipe())
    assert len(parsed.recipe.operations) == 56
    assert sum(isinstance(op, MeshCreate) for op in parsed.recipe.operations) == 28
