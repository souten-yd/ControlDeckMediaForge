from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_geometry import validate_geometry_facts
from mediaforge.scene_recipes import SceneCreateRequest, MeshLoft, MeshSweep
from test_game_static_operations import ROOT, request, worker


def curve(**changes: Any) -> dict[str, Any]:
    return {"type":"mesh.loft","object_id":"body","name":"Body",
            "sections":[{"center":[0,0,0],"radii":[.2,.3]},
                        {"center":[0,0,1],"radii":[.4,.3]},
                        {"center":[.3,0,2],"radii":[.1,.1]}], **changes}


def module() -> Any:
    spec = importlib.util.spec_from_file_location("curve_geometry_test", ROOT/"worker_packs/blender/scene_curves.py")
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def test_published_curve_contracts() -> None:
    operations = [curve(), {"type":"mesh.sweep","object_id":"tube","name":"Tube","path_points":[[0,0,0],[1,0,0]],"radii":[.2,.2]},
                  {"type":"mesh.sections.set","object_id":"body","expected_geometry_sha256":"a"*64,"sections":curve()["sections"]},
                  {"type":"modifier.subdivision","object_id":"body","levels":2},
                  {"type":"mesh.bridge_loops","object_id":"body","other_object_id":"tube","expected_geometry_sha256":"a"*64,
                   "other_geometry_sha256":"b"*64,"boundary":[0,1,2],"other_boundary":[2,1,0]}]
    payload=request(*operations); SceneCreateRequest.model_validate(payload)
    for name,value in (("scene-create-request",payload),("scene-edit-request",{"scene_id":"scene_"+"a"*32,"base_revision_id":"revision_"+"b"*32,"recipe":payload["recipe"]}),
                       ("scene-workflow-request",{"action":"create",**payload})):
        jsonschema.validate(value,json.loads((ROOT/f"schemas/{name}.json").read_text()))


@pytest.mark.parametrize("changes",[
    {"radial_segments":7},{"radial_segments":33},{"radial_segments":True},{"samples_per_segment":9},
    {"up":[0,0,0]}, {"caps":"closed"}, {"smooth":"yes"}, {"sections":[]},
    {"sections":[{"center":[0,0,0],"radii":[.1,.1]}]*2},
    {"sections":[{"center":[0,0,0],"radii":[.1,.1]},{"center":[0,0,1],"radii":[0,.1]}]},
    {"sections":[{"center":[0,0,0],"radii":[.1,.1]},{"center":[0,0,float('nan')],"radii":[.1,.1]}]},
])
def test_core_and_worker_independently_reject_bad_curve(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError): MeshLoft.model_validate(curve(**changes))
    with pytest.raises(RuntimeError): module().geometry(curve(**changes))


@pytest.mark.parametrize("caps,boundary",[("both",0),("start",16),("end",16),("none",32)])
def test_real_generated_topology_closure_winding_and_area(caps: str,boundary: int) -> None:
    m=module();vertices,faces,spec=m.geometry(curve(caps=caps))
    mesh=SimpleNamespace(polygons=[SimpleNamespace(vertices=f) for f in faces])
    edges=m.edge_uses(mesh)
    assert sum(len(u)==1 for u in edges.values()) == boundary
    assert all(len(u)<=2 and (len(u)!=2 or u[0]==u[1][::-1]) for u in edges.values())
    assert len(vertices)<=8000
    m.validate_faces(vertices,faces)
    if not boundary:
        volume=sum(m.dot(vertices[f[0]],m.cross(vertices[f[i]],vertices[f[i+1]]))/6 for f in faces for i in range(1,len(f)-1))
        assert volume>0


def test_constant_sweep_matches_loft_and_expansion_is_bounded() -> None:
    m=module();value={"type":"mesh.sweep","object_id":"tube","name":"Tube","path_points":[[i,0,0] for i in range(32)],
                      "radii":[.2,.3],"radial_segments":32,"samples_per_segment":8}
    MeshSweep.model_validate(value)
    vertices,faces,spec=m.geometry(value)
    assert len(vertices)==7970 and len(faces)==8000
    assert m.geometry(spec)[:2] == (vertices,faces)


def test_stale_sections_fail_before_edit_and_growth_before_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    m=worker(monkeypatch);m.MAX_GROWTH_GEOMETRY=10
    with pytest.raises(RuntimeError,match="budget"):m.apply_operation(curve(),{})
    mesh=SimpleNamespace(vertices=[SimpleNamespace(co=(0,0,0))],polygons=[])
    obj=SimpleNamespace(type="MESH",data=SimpleNamespace(users=1,shape_keys=None,animation_data=None,vertices=mesh.vertices,polygons=[]))
    with pytest.raises(RuntimeError,match="stale"):
        m.scene_curves.set_sections(obj,{"expected_geometry_sha256":"0"*64})


def test_subdivision_budget_counts_triangles_conservatively(monkeypatch: pytest.MonkeyPatch) -> None:
    m=worker(monkeypatch)
    obj=SimpleNamespace(type="MESH",data=SimpleNamespace(vertices=range(3),polygons=[SimpleNamespace(loop_total=3)]),
                        modifiers=[SimpleNamespace(type="SUBSURF",subdivision_type="CATMULL_CLARK",levels=2,render_levels=2)])
    assert m.geometry_cost(obj)==72
    obj.modifiers[0].render_levels=3
    with pytest.raises(RuntimeError,match="subdivision"):m.geometry_cost(obj)


def test_geometry_projection_rejects_unbounded_or_foreign_selectors() -> None:
    fact={"object_id":"body","geometry_sha256":"a"*64,"vertices":3,"triangles":1,"boundary_edges":3,
          "nonmanifold_edges":0,"inconsistent_edges":0,"boundary_loops":[[0,1,2]]}
    assert validate_geometry_facts([fact],["body"])==[fact]
    for bad in ([{**fact,"boundary_loops":[[0,1,3]]}],[fact,fact],[{**fact,"vertices":16385}]):
        with pytest.raises(ValueError):validate_geometry_facts(bad,["body"])
    with pytest.raises(ValueError):validate_geometry_facts([fact],["other"])


def test_code_paths_and_duplicate_creations_rejected() -> None:
    with pytest.raises(ValidationError):SceneCreateRequest.model_validate(request(curve(script="bad")))
    with pytest.raises(ValidationError):SceneCreateRequest.model_validate(request(curve(),curve()))
