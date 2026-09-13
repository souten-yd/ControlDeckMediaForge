from __future__ import annotations

import asyncio
import copy
import json

import pytest
from pydantic import ValidationError

from mediaforge.host.ai import HostAIError, HostAIResult
from mediaforge.host.client import HostIdentity
from mediaforge.scene_drafts import (
    MAX_DRAFT_BYTES, MeshDraftError, MeshDraftPreparer, MeshDraftRequest,
    draft_schema, edge_feedback, validate_draft,
    topology_repair_hints,
    _TopologyCorrection, apply_topology_correction,
)


IDENTITY = HostIdentity("Bearer test", "media-forge", "user:1", 2**31, frozenset({"ai.inference"}))


def draft_data() -> dict:
    return {
        "name": "Draft", "mesh": {
            "type": "mesh.create", "object_id": "armor", "name": "Armor",
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "faces": [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]],
            "require_closed": True,
        }, "material": {
            "type": "material.set", "object_id": "armor", "base_color": [0, 0.5, 0.5, 1],
        },
    }


class Gateway:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    async def complete_streamed(self, identity, capability, messages, **kwargs):
        self.calls.append((identity, capability, copy.deepcopy(messages), kwargs))
        value = next(self.responses)
        if isinstance(value, BaseException):
            raise value
        return HostAIResult(value, capability)


def test_prepare_is_data_only_with_provenance_and_scoped_gateway():
    gateway = Gateway(json.dumps(draft_data()))
    result = asyncio.run(MeshDraftPreparer(gateway).prepare(IDENTITY, MeshDraftRequest(intent="armor")))
    assert len(result.request.recipe.operations) == 2
    assert result.request.recipe.operations[0].require_closed is True
    assert result.provenance["quality_status"] == "NOT TESTED"
    assert result.provenance["execution_status"] == "not_executed"
    assert len(result.provenance["attempts"]) == 1
    assert len(result.provenance["request_sha256"]) == 64
    identity, capability, messages, options = gateway.calls[0]
    assert identity is IDENTITY and capability == "text.generate"
    assert options["max_tokens"] == 4096 and options["timeout_seconds"] == 90
    assert "model" not in options and "tools" not in options
    assert options["response_format"]["type"] == "json_schema"
    assert json.loads(messages[1]["content"])["local_only"] is True


def test_one_feedback_repair_includes_specific_edges_without_changing_constraints():
    opened = draft_data()
    opened["mesh"]["faces"].pop()
    patch = {"append_faces": topology_repair_hints(opened)["candidate_cap_faces"], "reverse_face_indices": []}
    gateway = Gateway(json.dumps(opened), json.dumps(patch))
    result = asyncio.run(MeshDraftPreparer(gateway).prepare(IDENTITY, MeshDraftRequest(intent="armor")))
    assert [item["valid"] for item in result.provenance["attempts"]] == [False, True]
    feedback = json.loads(gateway.calls[1][2][-1]["content"])
    assert feedback["repair_hints"]["candidate_cap_faces"]
    issues = result.provenance["attempts"][0]["issues"]
    assert all("input" not in item and "ctx" not in item for item in issues)
    assert set(gateway.calls[1][3]["response_format"]["schema"]["properties"]) == {
        "append_faces", "reverse_face_indices",
    }
    assert gateway.calls[1][3]["max_tokens"] == 512
    assert result.provenance["attempts"][1]["response_kind"] == "topology_correction"


def test_validation_is_exhausted_after_exactly_two_repairs():
    gateway = Gateway("{}", "{}", "{}")
    with pytest.raises(MeshDraftError, match="draft_validation_exhausted") as caught:
        asyncio.run(MeshDraftPreparer(gateway).prepare(IDENTITY, MeshDraftRequest(intent="armor")))
    assert len(gateway.calls) == 3
    assert len(caught.value.details["attempts"]) == 3
    assert all("issues" in item for item in caught.value.details["attempts"])


@pytest.mark.parametrize("error", [HostAIError("host_ai_unavailable", "unavailable"), asyncio.CancelledError()])
def test_transport_failure_or_cancel_propagates_without_retry(error):
    gateway = Gateway(error)
    with pytest.raises(type(error)):
        asyncio.run(MeshDraftPreparer(gateway).prepare(IDENTITY, MeshDraftRequest(intent="armor")))
    assert len(gateway.calls) == 1


def test_oversize_output_is_terminal_and_not_echoed():
    gateway = Gateway("x" * (MAX_DRAFT_BYTES + 1))
    with pytest.raises(MeshDraftError, match="draft_output_too_large"):
        asyncio.run(MeshDraftPreparer(gateway).prepare(IDENTITY, MeshDraftRequest(intent="armor")))
    assert len(gateway.calls) == 1


def test_missing_grant_never_calls_gateway():
    gateway = Gateway()
    identity = HostIdentity("Bearer test", "media-forge", "user:1", 2**31, frozenset())
    with pytest.raises(MeshDraftError, match="host_ai_not_granted"):
        asyncio.run(MeshDraftPreparer(gateway).prepare(identity, MeshDraftRequest(intent="armor")))
    assert gateway.calls == []


def test_closed_guard_and_geometry_budget_cannot_be_relaxed_by_response():
    value = draft_data()
    value["mesh"]["require_closed"] = False
    with pytest.raises(MeshDraftError, match="draft_closed_requirement_changed"):
        validate_draft(json.dumps(value), MeshDraftRequest(intent="armor"))
    del value["mesh"]["require_closed"]
    with pytest.raises(MeshDraftError, match="draft_closed_requirement_changed"):
        validate_draft(json.dumps(value), MeshDraftRequest(intent="armor"))
    value = draft_data()
    value["material"]["object_id"] = "different"
    with pytest.raises(ValidationError, match="must target"):
        validate_draft(json.dumps(value), MeshDraftRequest(intent="armor"))
    schema = draft_schema(MeshDraftRequest(intent="armor", vertex_budget=8))
    assert schema["$defs"]["MeshCreate"]["properties"]["vertices"]["maxItems"] == 8
    assert schema["$defs"]["MeshCreate"]["properties"]["faces"]["items"]["items"]["maximum"] == 7
    assert schema["$defs"]["MeshCreate"]["properties"]["require_closed"]["const"] is True


def test_open_cloth_is_only_allowed_when_explicitly_requested():
    value = draft_data()
    value["mesh"]["faces"].pop()
    value["mesh"]["require_closed"] = False
    result = validate_draft(json.dumps(value), MeshDraftRequest(intent="cloth", require_closed=False))
    assert result.mesh.require_closed is False


@pytest.mark.parametrize("changes", [{"local_only": False}, {"vertex_budget": 33}, {"require_closed": "false"}, {"intent": ""}])
def test_request_boundaries(changes):
    with pytest.raises(ValidationError):
        MeshDraftRequest.model_validate({"intent": "armor", **changes})


@pytest.mark.parametrize("value", [None, [], {"mesh": []}, {"mesh": {"faces": [[0, True, 2]]}},
                                  {"mesh": {"faces": [[0, 1, 32]]}}])
def test_malformed_edge_feedback_is_bounded(value):
    assert edge_feedback(value) == []


def test_cap_hint_is_data_only_and_resubmission_still_requires_validation():
    value = draft_data()
    value["mesh"]["faces"].pop()
    before = copy.deepcopy(value)
    hints = topology_repair_hints(value)
    assert value == before
    assert len(hints["candidate_cap_faces"]) == 1
    with pytest.raises(ValidationError):
        validate_draft(json.dumps(value), MeshDraftRequest(intent="armor"))
    # Simulate a caller applying the suggestion; the production helper does not.
    value["mesh"]["faces"] += hints["candidate_cap_faces"]
    validate_draft(json.dumps(value), MeshDraftRequest(intent="armor"))
    assert value["mesh"]["vertices"] == before["mesh"]["vertices"]


def test_closed_graph_hint_identifies_only_inconsistent_face_winding():
    value = draft_data()
    value["mesh"]["faces"][0].reverse()
    before = copy.deepcopy(value)
    hints = topology_repair_hints(value)
    assert value == before and hints["reverse_face_indices"] == [0]
    for index in hints["reverse_face_indices"]:
        value["mesh"]["faces"][index].reverse()
    validate_draft(json.dumps(value), MeshDraftRequest(intent="armor"))
    assert topology_repair_hints(value) == {}


@pytest.mark.parametrize("faces", [
    [[0, 1, 2], [0, 3, 4]],  # branched boundary at vertex 0
    [[0, 1, 2], [0, 1, 3], [0, 1, 4]],  # three uses
    [[0, 1, 2], [2, 1, 0]],  # duplicate face identity
    [[0, True, 2]], [[0, 1, 32]], [[0, 0, 1]],
])
def test_ambiguous_or_malformed_topology_gets_no_repair_hint(faces):
    assert topology_repair_hints({"mesh": {"vertices": [[i, 0, 0] for i in range(5)], "faces": faces}}) == {}


def test_hint_does_not_reference_a_phantom_vertex_below_global_budget():
    value = draft_data()
    value["mesh"]["faces"] = [[0, 1, 4]]
    assert topology_repair_hints(value) == {}


@pytest.mark.parametrize("patch", [
    {"append_faces": [], "reverse_face_indices": [True]},
    {"append_faces": [[0, 1.0, 2]], "reverse_face_indices": []},
    {"append_faces": [], "reverse_face_indices": [], "vertices": []},
])
def test_correction_cannot_smuggle_coordinates_or_noninteger_indices(patch):
    with pytest.raises(ValidationError):
        _TopologyCorrection.model_validate(patch)


@pytest.mark.parametrize("indices", [[0, 0], [5]])
def test_correction_rejects_duplicate_or_missing_faces(indices):
    with pytest.raises(MeshDraftError, match="draft_invalid_topology_correction"):
        apply_topology_correction(draft_data(), _TopologyCorrection(append_faces=[], reverse_face_indices=indices))


def test_a_submitted_empty_patch_is_not_implicitly_fixed():
    value = draft_data()
    value["mesh"]["faces"].pop()
    gateway = Gateway(json.dumps(value), json.dumps({"append_faces": [], "reverse_face_indices": []}),
                      json.dumps({"append_faces": [], "reverse_face_indices": []}))
    with pytest.raises(MeshDraftError, match="draft_validation_exhausted"):
        asyncio.run(MeshDraftPreparer(gateway).prepare(IDENTITY, MeshDraftRequest(intent="armor")))
    assert len(gateway.calls) == 3
