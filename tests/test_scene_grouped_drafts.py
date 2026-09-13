from __future__ import annotations

import asyncio
import copy
import json

import pytest
from pydantic import ValidationError

from mediaforge.host.ai import HostAIResult
from mediaforge.host.client import HostIdentity
from mediaforge.scene_drafts import MeshDraftError, MeshDraftRequest
from mediaforge.scene_grouped_drafts import GroupedLayout, GroupedMeshDraftPreparer, faces_schema, layout_schema, parse_faces


IDENTITY = HostIdentity("Bearer test", "media-forge", "user:1", 2**31, frozenset({"ai.inference"}))


def layout_data():
    return {"name": "Prism", "object_id": "prism",
        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1]],
        "vertex_groups": [{"name": "lower", "indices": [0, 1, 2]}, {"name": "upper", "indices": [3, 4, 5]}],
        "face_groups": [
            {"name": "sides", "vertex_groups": ["lower", "upper"], "face_size": 4, "face_count": 3, "role": "surface"},
            {"name": "bottom", "vertex_groups": ["lower"], "face_size": 3, "face_count": 1, "role": "cap"},
            {"name": "top", "vertex_groups": ["upper"], "face_size": 3, "face_count": 1, "role": "cap"}],
        "material": {"type": "material.set", "object_id": "prism", "base_color": [.2, .4, .5, 1]}}


def valid_faces():
    return {"sides": [[0, 1, 4, 3], [1, 2, 5, 4], [2, 0, 3, 5]], "bottom": [[0, 2, 1]], "top": [[3, 4, 5]]}


class Gateway:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    async def complete_streamed(self, identity, capability, messages, **options):
        self.calls.append((identity, capability, messages, options))
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return HostAIResult(response if isinstance(response, str) else json.dumps(response), capability)


def prepare(gateway, request=None, **options):
    return asyncio.run(GroupedMeshDraftPreparer(gateway).prepare(IDENTITY, request or MeshDraftRequest(intent="A prism"), **options))


def test_grouped_prism_is_model_authored_data_with_provenance_and_no_execution():
    gateway = Gateway(layout_data(), valid_faces())
    result = prepare(gateway)
    assert len(gateway.calls) == 2
    mesh, material = result.request.recipe.operations
    assert mesh.object_id == material.object_id == "prism"
    assert len(mesh.vertices) == 6 and len(mesh.faces) == 5
    assert mesh.require_closed
    assert result.provenance["quality_status"] == "NOT TESTED"
    assert result.provenance["execution_status"] == "not_executed"
    assert result.provenance["requested_thinking"] is True
    assert len(result.provenance["layout_sha256"]) == 64
    for _, capability, messages, options in gateway.calls:
        assert capability == "text.generate" and len(messages) == 2
        assert options["max_output_bytes"] == 8192 and options["timeout_seconds"] == 90
        assert options["thinking"] is True
        assert "model" not in options and options["response_format"]["strict"]


def test_cap_only_correction_preserves_coordinates_and_surfaces():
    faces = valid_faces()
    faces["bottom"] = [[0, 1, 2]]
    before = copy.deepcopy(faces)
    gateway = Gateway(layout_data(), faces, {"bottom": [[0, 2, 1]], "top": [[3, 4, 5]]})
    result = prepare(gateway)
    assert len(gateway.calls) == 3 and faces == before
    schema = gateway.calls[-1][3]["response_format"]["schema"]
    assert set(schema["properties"]) == {"bottom", "top"}
    assert result.request.recipe.operations[0].faces[:3] == valid_faces()["sides"]
    assert [a["valid"] for a in result.provenance["attempts"]] == [True, False, True]


def test_invalid_surface_requires_all_groups_not_cap_only():
    faces = valid_faces()
    faces["sides"][0] = [0, 0, 4, 3]
    gateway = Gateway(layout_data(), faces, valid_faces())
    prepare(gateway)
    assert set(gateway.calls[-1][3]["response_format"]["schema"]["properties"]) == set(valid_faces())


def test_surface_to_surface_winding_fault_cannot_be_hidden_by_cap_repair():
    faces = valid_faces()
    faces["sides"][0].reverse()
    gateway = Gateway(layout_data(), faces, valid_faces())
    prepare(gateway)
    assert set(gateway.calls[-1][3]["response_format"]["schema"]["properties"]) == set(valid_faces())


def test_malformed_first_face_response_can_only_be_replaced_explicitly():
    gateway = Gateway(layout_data(), "not JSON", valid_faces())
    result = prepare(gateway)
    assert [a["valid"] for a in result.provenance["attempts"]] == [True, False, True]
    assert set(gateway.calls[-1][3]["response_format"]["schema"]["properties"]) == set(valid_faces())


def test_open_panel_does_not_need_cap_or_closed_guard():
    data = layout_data()
    data["vertex_groups"] = [data["vertex_groups"][0]]
    data["vertices"] = data["vertices"][:3]
    data["face_groups"] = [{"name": "panel", "vertex_groups": ["lower"], "face_size": 3, "face_count": 1, "role": "surface"}]
    result = prepare(Gateway(data, {"panel": [[0, 1, 2]]}), MeshDraftRequest(intent="Open cloth", require_closed=False))
    assert result.request.recipe.operations[0].require_closed is False


@pytest.mark.parametrize("failure", ["extra", "duplicate", "reference", "material", "budget", "cap_reference", "nan", "unused", "impossible"])
def test_invalid_layout_never_reaches_face_generation(failure):
    data = layout_data()
    if failure == "extra": data["script"] = "forbidden"
    elif failure == "duplicate": data["vertex_groups"][1]["name"] = "lower"
    elif failure == "reference": data["face_groups"][0]["vertex_groups"] = ["missing"]
    elif failure == "material": data["material"]["object_id"] = "other"
    elif failure == "budget": data["face_groups"][0]["face_count"] = 64
    elif failure == "cap_reference": data["face_groups"][1]["vertex_groups"] = ["lower", "upper"]
    elif failure == "unused":
        data["vertex_groups"].append({"name": "unused", "indices": [6]})
        data["vertices"].append([2, 2, 2])
    elif failure == "impossible": data["face_groups"][1]["face_size"] = 4
    else: data["vertices"][0][0] = float("nan")
    gateway = Gateway(data)
    with pytest.raises(MeshDraftError): prepare(gateway)
    assert len(gateway.calls) == 1


def test_request_vertex_budget_precedes_next_inference():
    gateway = Gateway(layout_data())
    with pytest.raises(MeshDraftError, match="budget"):
        prepare(gateway, MeshDraftRequest(intent="prism", vertex_budget=4))
    assert len(gateway.calls) == 1
    schema = layout_schema(MeshDraftRequest(intent="prism", vertex_budget=4))
    assert schema["properties"]["vertices"]["maxItems"] == 4
    assert schema["$defs"]["VertexGroup"]["properties"]["indices"]["items"]["maximum"] == 3


@pytest.mark.parametrize("indices", [[0, 1, 2], [3, 4, 6], [3, 4], [3, 4, True]])
def test_groups_must_partition_actual_vertices(indices):
    data = layout_data()
    data["vertex_groups"][1]["indices"] = indices
    with pytest.raises(ValidationError): GroupedLayout.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("failure", ["cross_group", "bool", "float", "count", "extra", "missing"])
def test_face_constraints_enforced_locally_not_only_in_ai_schema(failure):
    layout = GroupedLayout.model_validate_json(json.dumps(layout_data()))
    schema = faces_schema(layout, ["bottom"])
    assert schema["properties"]["bottom"]["items"]["items"]["enum"] == [0, 1, 2]
    faces = {"bottom": [[0, 2, 1]]}
    if failure == "cross_group": faces["bottom"][0][0] = 3
    elif failure == "bool": faces["bottom"][0][0] = False
    elif failure == "float": faces["bottom"][0][0] = 0.0
    elif failure == "count": faces["bottom"].append([0, 2, 1])
    elif failure == "extra": faces["vertices"] = []
    else: faces.clear()
    with pytest.raises(MeshDraftError): parse_faces(json.dumps(faces), layout, ["bottom"])


def test_no_implicit_repair_and_three_calls_maximum():
    faces = valid_faces()
    faces["bottom"] = [[0, 1, 2]]
    gateway = Gateway(layout_data(), faces, {"bottom": [[0, 1, 2]], "top": [[3, 4, 5]]})
    with pytest.raises(MeshDraftError, match="exhausted") as exc:
        prepare(gateway)
    assert len(gateway.calls) == len(exc.value.details["attempts"]) == 3


def test_cancellation_propagates_without_another_request():
    gateway = Gateway(layout_data(), asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError): prepare(gateway)
    assert len(gateway.calls) == 2


def test_total_deadline_cancels_a_stalled_layout(monkeypatch):
    original = asyncio.timeout
    monkeypatch.setattr("mediaforge.scene_grouped_drafts.asyncio.timeout", lambda _: original(.01))
    class Stalled:
        canceled = False
        async def complete_streamed(self, *args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                self.canceled = True
    gateway = Stalled()
    with pytest.raises(TimeoutError): prepare(gateway)
    assert gateway.canceled


def test_fresh_child_identity_used_for_each_stage():
    ids = [HostIdentity("Bearer first", "media-forge", "user:1", 2**31, frozenset({"ai.inference"})),
           HostIdentity("Bearer second", "media-forge", "user:1", 2**31, frozenset({"ai.inference"}))]
    gateway = Gateway(layout_data(), valid_faces())
    prepare(gateway, identity_provider=iter(ids).__next__)
    assert [call[0] for call in gateway.calls] == ids


def test_oversized_or_missing_permission_stops_immediately():
    gateway = Gateway(" " * 8193)
    with pytest.raises(MeshDraftError, match="too_large"): prepare(gateway)
    identity = HostIdentity("Bearer none", "media-forge", "user:1", 2**31, frozenset())
    with pytest.raises(MeshDraftError, match="not_granted"):
        asyncio.run(GroupedMeshDraftPreparer(gateway).prepare(identity, MeshDraftRequest(intent="prism")))
    assert len(gateway.calls) == 1
