from __future__ import annotations

from pathlib import Path

import pytest

from conftest import wait_terminal
from mediaforge.creative import CreativeCompiler, CreativeSpec, CreativeValidationError
from mediaforge.creative_batches import CreativeBatchPlanner, CreativeBatchRecord, project_batch
from mediaforge.domain import AssetInput, Job, JobRequest, JobStatus, OutputOptions
from mediaforge.store import Store, utc_now


ROOT = Path(__file__).parents[1]
CAPABILITIES = {"image.text_to_image": {"state": "available"}}
ENVELOPE = {"max_reference_assets": 4, "reference_roles": [], "supports_reference_strength": False}


def base_request(*, delay: float = 0) -> JobRequest:
    constraints = {"width": 256, "height": 256, "seed": 100}
    if delay:
        constraints["_fake_delay_sec"] = delay
    return JobRequest(operation="image.generate", intent="batch companion", constraints=constraints)


@pytest.mark.parametrize(("axis", "field"), [("pose", "pose"), ("composition", "composition")])
def test_planner_creates_four_explicit_child_specs_and_seeds(axis: str, field: str):
    planner = CreativeBatchPlanner(CreativeCompiler.load(ROOT / "creative/templates.json"))
    spec = CreativeSpec.model_validate({"variation": {"axis": axis}})
    batch_id, requests, plans = planner.plan(
        base_request(), spec, 4, capabilities=CAPABILITIES, envelope=ENVELOPE,
    )
    assert batch_id.startswith("batch_")
    assert len({plan[field]["id"] for plan in plans}) == 4
    assert [item.constraints["seed"] for item in requests] == [100, 101, 102, 103]
    assert all(item.output.count == 1 for item in requests)
    assert [plan["batch"]["index"] for plan in plans] == [0, 1, 2, 3]
    assert all(plan["batch"]["total"] == 4 for plan in plans)


def test_planner_rejects_unavailable_number_of_scene_variants():
    planner = CreativeBatchPlanner(CreativeCompiler.load(ROOT / "creative/templates.json"))
    spec = CreativeSpec.model_validate({
        "pose": {"preset": "typing"}, "variation": {"axis": "scene"},
    })
    with pytest.raises(CreativeValidationError) as error:
        planner.plan(base_request(), spec, 4, capabilities=CAPABILITIES, envelope=ENVELOPE)
    assert error.value.code == "creative_batch_variants_unavailable"


def test_standalone_batch_is_durable_and_collects_child_assets(client):
    created = client.post("/workspace-api/creative/batches", json={
        "request": base_request().model_dump(mode="json"),
        "creative_spec": {"variation": {"axis": "pose"}},
        "count": 4,
    })
    assert created.status_code == 200
    batch = created.json()
    assert len(batch["child_job_ids"]) == 4
    for job_id in batch["child_job_ids"]:
        assert wait_terminal(client, job_id)["status"] == "succeeded"
    restored = client.get(f"/workspace-api/creative/batches/{batch['id']}").json()
    assert restored["state"] == "succeeded"
    assert restored["succeeded_count"] == 4
    assert len(restored["asset_ids"]) == 4
    assert len({child["request"]["constraints"]["creative_plan"]["pose"]["id"]
                for child in restored["children"]}) == 4
    assert client.get("/workspace-api/creative/batches").json()["items"][0]["id"] == batch["id"]
    assert "/workspace-api/creative/batches" not in client.get("/openapi.json").json()["paths"]


def test_cancel_batch_cancels_queued_and_running_children(client):
    created = client.post("/workspace-api/creative/batches", json={
        "request": base_request(delay=0.5).model_dump(mode="json"),
        "creative_spec": {"variation": {"axis": "composition"}},
        "count": 4,
    }).json()
    canceled = client.delete(f"/workspace-api/creative/batches/{created['id']}")
    assert canceled.status_code == 200
    terminal = canceled.json()
    assert terminal["state"] in {"canceled", "running"}
    for job_id in created["child_job_ids"]:
        assert wait_terminal(client, job_id)["status"] == "canceled"
    final = client.get(f"/workspace-api/creative/batches/{created['id']}").json()
    assert final["state"] == "canceled" and final["canceled_count"] == 4


def test_partial_projection_keeps_successful_assets(tmp_path: Path):
    now = utc_now()
    request = base_request()
    succeeded = Job(
        id="job_" + "1" * 32, status=JobStatus.SUCCEEDED, progress=1, request=request,
        asset_ids=["asset_" + "a" * 32], created_at=now, updated_at=now,
    )
    failed = Job(
        id="job_" + "2" * 32, status=JobStatus.FAILED, progress=1, request=request,
        created_at=now, updated_at=now,
    )
    record = CreativeBatchRecord(
        id="batch_" + "3" * 32, axis="pose", requested_count=2,
        child_plans=[{}, {}], child_job_ids=[succeeded.id, failed.id], created_at=now, updated_at=now,
    )
    projected = project_batch(record, [succeeded, failed])
    assert projected["state"] == "partial"
    assert projected["asset_ids"] == succeeded.asset_ids

    store = Store(tmp_path / "durable")
    store.initialize()
    store.create_creative_batch(record)
    assert store.get_creative_batch(record.id) == record
