"""Synthetic verifier checks, not actual OpenCode/Blender acceptance."""
from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from test_opencode_flow_evidence import MODULE


def calls() -> list[dict[str, Any]]:
    def call(tool: str, inputs: dict[str, Any], output: dict[str, Any] | str) -> dict[str, Any]:
        return {"tool": tool, "state": {"status": "completed", "input": inputs,
                "output": output if isinstance(output, str) else json.dumps({"output": output})}}
    revision = {"id": "revision", "validation": [
        {"validator": name, "status": "passed"} for name in ("blender.scene", "glb.structure")]}
    return [
        call("skill", {"name": "blender-director"}, "Blender Director media.scene"),
        call("controldeck_addons_media_capabilities", {}, {"capabilities": {"3d.scene_recipe": {
            "state": "available", "supported_operations": ["mesh.create"],
            "authoring_guidance": {"version": "media-forge.scene-authoring-guidance@1"}}}}),
        call("controldeck_addons_media_scene_create", {"name": "Armor acceptance", "recipe": {"operations": [
            {"type": "mesh.create", "object_id": "armor", "name": "Armor", "require_closed": True, "vertices": [
                [-.2, 0, 0], [0, -.04, 0], [.2, 0, 0], [.2, .04, 0], [-.2, .04, 0],
                [-.2, 0, .5], [0, -.04, .5], [.2, 0, .5], [.2, .04, .5], [-.2, .04, .5]],
             "faces": [[0, 1, 6, 5], [1, 2, 7, 6], [2, 3, 8, 7], [3, 4, 9, 8], [4, 0, 5, 9],
                       [0, 2, 1], [0, 3, 2], [0, 4, 3], [5, 6, 7], [5, 7, 8], [5, 8, 9]]},
            {"type": "material.set", "object_id": "armor", "base_color": [0, .5, .5, 1]}]}}, {"job_id": "job"}),
        call("controldeck_addons_media_job_status", {}, {"job_id": "job", "status": "succeeded", "result": {"revision": revision}}),
        call("controldeck_addons_media_scene_snapshot", {}, {"revision": revision}),
        call("controldeck_addons_media_scene_export", {}, {"revision_id": "revision"}),
    ]


@pytest.mark.parametrize("failure", [None, "no_guide", "late_discovery", "open_shell", "primitive", "wrong_revision", "failed_validation", "complexity", "guard_bypass"])
def test_authored_mesh_evidence(failure: str | None) -> None:
    value = copy.deepcopy(calls())
    if failure == "no_guide":
        output = json.loads(value[1]["state"]["output"])
        del output["output"]["capabilities"]["3d.scene_recipe"]["authoring_guidance"]
        value[1]["state"]["output"] = json.dumps(output)
    elif failure == "late_discovery":
        value.append(value.pop(1))
    elif failure == "open_shell":
        value[2]["state"]["input"]["recipe"]["operations"][0]["faces"].pop()
    elif failure == "guard_bypass":
        value[2]["state"]["input"]["recipe"]["operations"][0]["require_closed"] = False
    elif failure == "complexity":
        mesh = value[2]["state"]["input"]["recipe"]["operations"][0]
        vertices, faces = copy.deepcopy(mesh["vertices"]), copy.deepcopy(mesh["faces"])
        # Additional closed shells exceed this diagnostic's budget.
        for offset in (1, 2):
            mesh["vertices"].extend([[x + offset, y, z] for x, y, z in vertices])
            mesh["faces"].extend([[index + offset * len(vertices) for index in face] for face in faces])
    elif failure == "primitive":
        value[2]["state"]["input"]["recipe"]["operations"][0] = {
            "type": "primitive.add", "object_id": "armor", "name": "Armor", "primitive": "cube"}
    elif failure == "wrong_revision":
        value[-1]["state"]["output"] = json.dumps({"revision_id": "other"})
    elif failure == "failed_validation":
        output = json.loads(value[4]["state"]["output"])
        output["output"]["revision"]["validation"][0]["status"] = "failed"
        value[4]["state"]["output"] = json.dumps(output)
    if failure:
        with pytest.raises((AssertionError, KeyError, ValueError)):
            MODULE.verify_authored_mesh_calls(value)
    else:
        MODULE.verify_authored_mesh_calls(value)


@pytest.mark.parametrize("failure", ["wrong_depth", "tetrahedron", "flat_subdivided_box"])
def test_closed_structural_success_is_not_armor_shape_acceptance(failure: str) -> None:
    value = calls()
    mesh = value[2]["state"]["input"]["recipe"]["operations"][0]
    if failure == "wrong_depth":
        for point in mesh["vertices"]:
            point[1] *= 1.5
    elif failure == "tetrahedron":
        mesh["vertices"] = [[0, 0, 0], [.4, 0, 0], [0, .08, 0], [0, 0, .5]]
        mesh["faces"] = [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]]
    else:
        for index in (0, 2, 5, 7):
            mesh["vertices"][index][1] = -.04
        # Triangulate the collinear five-corner box caps without zero-area faces.
        mesh["faces"][5:] = [[0, 4, 1], [1, 4, 3], [1, 3, 2],
                              [5, 6, 9], [6, 8, 9], [6, 7, 8]]
    from mediaforge.scene_recipes import MeshCreate
    MeshCreate.model_validate(mesh)  # These failures must pass the closed-edge guard first.
    with pytest.raises(AssertionError, match="dimensions|ridge"):
        MODULE.verify_authored_mesh_calls(value)


def test_authored_mesh_private_permissions_remove_delegation_mask() -> None:
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("runner", Path(__file__).parents[1] / "scripts/3ds_opencode_flow_e2e.py")
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    payload = {"agent": {"build": {"tools": {"controldeck_addons_media_scene_*": False}}}}
    runner.restrict_tools(payload, director_static=False, director_authored_mesh=True)
    assert payload["agent"] == {"build": {"tools": {"controldeck_addons_*": True}}}
    assert payload["tools"]["task"] is False and payload["tools"]["bash"] is False
    assert payload["permission"]["skill"] == {"*": "deny", "blender-director": "allow"}
    resolved = {"tools": {}, "permission": [
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "controldeck_addons_*", "pattern": "*", "action": "allow"}]}
    runner.assert_direct_mcp_permissions(resolved)
    resolved["permission"].append({"permission": "controldeck_addons_media_scene_*", "pattern": "*", "action": "deny"})
    with pytest.raises(AssertionError, match="media_scene_create"):
        runner.assert_direct_mcp_permissions(resolved)
