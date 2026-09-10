from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import SceneCreateRequest
from test_game_static_operations import ROOT, request, worker


def operation(**changes: Any) -> dict[str, Any]:
    return {"type": "skin.bind_auto", "object_id": "rig", "mesh_object_ids": ["body"], **changes}


def test_auto_bind_published_contracts() -> None:
    value = request(operation())
    parsed = SceneCreateRequest.model_validate(value)
    assert parsed.recipe.operations[0].type == "skin.bind_auto"
    for filename, payload in (
        ("scene-create-request.json", value),
        ("scene-edit-request.json", {"scene_id": "scene_" + "a"*32,
          "base_revision_id": "revision_" + "b"*32, "recipe": value["recipe"]}),
        ("scene-workflow-request.json", {"action": "create", **value}),
    ):
        schema = json.loads((ROOT / "schemas" / filename).read_text())
        jsonschema.validate(payload, schema)
        assert "skin.bind_auto" in schema["$defs"]["SceneRecipe"]["properties"]["operations"]["items"]["discriminator"]["mapping"]


@pytest.mark.parametrize("changes", [
    {"mesh_object_ids": []}, {"mesh_object_ids": ["body"]*2}, {"mesh_object_ids": ["rig"]},
    {"mesh_object_ids": ["mesh"+str(i) for i in range(17)]},
    {"mesh_object_ids": ["../body"]}, {"mesh_object_ids": [None]},
    {"method": "ENVELOPE"}, {"max_influences": 8}, {"replace": True}, {"python": "pass"},
])
def test_auto_bind_invalid_inputs(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SceneCreateRequest.model_validate(request(operation(**changes)))


@pytest.mark.parametrize("groups", [[], [(0, 0)], [(0, -1), (1, 1)],
    [(0, float("nan")), (1, 1)], [(0, float("inf"))], [(0, 1.1)],
    [(9, 1)], [(0, .5), (0, .5)]])
def test_heat_missing_invalid_unknown_weights_fail(monkeypatch: pytest.MonkeyPatch, groups: list) -> None:
    with pytest.raises(RuntimeError, match="weights"):
        worker(monkeypatch).normalized_influences(groups, {0, 1})


def test_heat_explicit_top_four_and_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    module = worker(monkeypatch)
    raw = [(5, .1), (4, .1), (3, .1), (2, .1), (1, .1), (0, 0)]
    assert module.normalized_influences(raw, set(range(6))) == [(1, .25), (2, .25), (3, .25), (4, .25)]
    result = module.normalized_influences([(0, .48), (1, .5)], {0, 1})
    assert dict(result)[0] == pytest.approx(.48/.98)
    assert sum(weight for _, weight in result) == pytest.approx(1)


class Matrix(list):
    def determinant(self) -> float:
        return 1.0


@pytest.mark.parametrize("failure", ["parent", "groups", "modifier", "shared", "animation", "shape",
    "empty", "vertices", "polygons", "corners", "degenerate", "pairs", "nan", "posed", "rig_transform", "unknown", "duplicate"])
def test_auto_preflight_rejects_before_operator(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    module = worker(monkeypatch)
    monkeypatch.setattr(module, "rigid_armature", lambda _: None)
    identity = Matrix([[float(i == j) for j in range(4)] for i in range(4)])
    bone = SimpleNamespace(name="root", use_deform=True, length=1, matrix_local=identity)
    pose = SimpleNamespace(matrix_basis=identity)
    rig = SimpleNamespace(parent=None, matrix_world=identity, pose=SimpleNamespace(bones=[pose]),
                          data=SimpleNamespace(bones=[bone]))
    mesh = SimpleNamespace(type="MESH", parent=None, constraints=[], animation_data=None,
        vertex_groups=[], modifiers=[], matrix_world=identity,
        data=SimpleNamespace(users=1, shape_keys=None, animation_data=None,
            vertices=[SimpleNamespace(co=(0., 0., 0.))]*8,
            polygons=[SimpleNamespace(loop_total=4, area=1.)]*6))
    op = operation()
    if failure == "parent": mesh.parent = object()
    elif failure == "groups": mesh.vertex_groups = [object()]
    elif failure == "modifier": mesh.modifiers = [object()]
    elif failure == "shared": mesh.data.users = 2
    elif failure == "animation": mesh.animation_data = object()
    elif failure == "shape": mesh.data.shape_keys = object()
    elif failure == "empty": mesh.data.vertices = []
    elif failure == "vertices": mesh.data.vertices *= 6251
    elif failure == "polygons": mesh.data.polygons *= 16667
    elif failure == "corners": mesh.data.polygons[0].loop_total = 50001
    elif failure == "degenerate": mesh.data.polygons[0].area = 0
    elif failure == "pairs":
        mesh.data.vertices *= 1000
        rig.data.bones *= 128
    elif failure == "nan": mesh.data.vertices[0].co = (float("nan"), 0, 0)
    elif failure == "posed": pose.matrix_basis = Matrix([[float("nan")]*4]*4)
    elif failure == "rig_transform": rig.matrix_world = Matrix([[2.]*4]*4)
    elif failure == "unknown": op["mesh_object_ids"] = ["missing"]
    elif failure == "duplicate": op["mesh_object_ids"] *= 2
    # bpy has no operators in this test: accidental allocation would fail with
    # AttributeError, not the expected bounded preflight RuntimeError.
    with pytest.raises(RuntimeError):
        module.bind_skin_auto(rig, op, {"rig": rig, "body": mesh})
