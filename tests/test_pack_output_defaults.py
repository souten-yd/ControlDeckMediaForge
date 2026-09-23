from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.domain import JobRequest, OutputOptions, StoredJobRequest


ROOT = Path(__file__).parents[1]
ASSET_ID = "asset_" + "1" * 32


def pack_request() -> dict:
    return {
        "operation": "asset.pack", "intent": "Package an existing model",
        "profile": "3d.project.glb", "inputs": [{"asset_id": ASSET_ID}],
    }


@pytest.mark.parametrize("profile", ["3d.project.glb", "3d.reference_set", "m5.companion.pack"])
def test_pack_defaults_do_not_mutate_shared_image_options(profile: str) -> None:
    shared = OutputOptions()
    request = JobRequest.model_validate({**pack_request(), "profile": profile, "output": shared})
    assert request.output.format == "zip"
    assert shared.format == "png"
    assert "format" not in shared.model_fields_set
    image = JobRequest(operation="image.generate", intent="An image", output=shared)
    assert image.output.format == "png"


@pytest.mark.parametrize("output", [{"format": "png"}, {"format": "webp"}, {"count": 2}])
def test_invalid_explicit_pack_output_is_rejected_before_job_creation(client, output: dict) -> None:
    request = {**pack_request(), "output": output}
    schema = json.loads((ROOT / "schemas/job-request.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(request, schema)
    with pytest.raises(ValidationError, match=r"asset.pack requires output\."):
        JobRequest.model_validate(request)
    response = client.post("/api/v1/jobs", json=request)
    assert response.status_code == 422
    assert "asset.pack requires output." in response.text
    assert client.get("/api/v1/jobs").json()["items"] == []


@pytest.mark.parametrize("output", [{"format": "png", "count": 1}, {"format": "zip", "count": 2}])
def test_historical_failed_pack_output_is_not_reinterpreted(output: dict) -> None:
    request = StoredJobRequest.model_validate({**pack_request(), "output": output})
    assert request.output.model_dump() == output


def test_historical_pack_with_omitted_output_keeps_legacy_default() -> None:
    request = StoredJobRequest.model_validate(pack_request())
    assert request.output.format == "png"


def test_explicit_typed_png_is_not_silently_converted_to_zip() -> None:
    with pytest.raises(ValidationError, match="output.format=zip"):
        JobRequest.model_validate({**pack_request(), "output": OutputOptions(format="png")})
