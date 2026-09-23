from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import pytest

from mediaforge.asset_pipeline import AssetPipelineActionRequest
from mediaforge.asset_pipeline_runner import PipelineCoordinator, PipelineStalled, approve
from test_asset_pipeline import Fake, REVISION_MODEL, SCENE, build, run


def failed_rig() -> tuple[Any, Fake, PipelineCoordinator, dict[str, Any]]:
    pipeline, _ = build(image_asset_id="asset_" + "d" * 32, prompt=None, mode="confirm")
    fake = Fake()
    deps = fake.deps()
    run(pipeline, deps)
    fake.finish(pipeline.stages[0].job_id,
                result={"revision": {"id": REVISION_MODEL, "scene_id": SCENE}})
    run(pipeline, deps)
    approve(pipeline, deps)
    run(pipeline, deps)
    fake.fail(pipeline.stages[1].job_id, "scene_recipe_failed")
    run(pipeline, deps)
    stored = {pipeline.id: pipeline.model_copy(deep=True)}
    def load(key: str, owner: str) -> Any:
        if stored[key].owner != owner:
            raise KeyError(key)
        return stored[key].model_copy(deep=True)
    def save(value: Any) -> None:
        stored[value.id] = value.model_copy(deep=True)
    return pipeline, fake, PipelineCoordinator(load, save), stored


def test_retry_keeps_successful_model_and_history_and_later_approval() -> None:
    p, fake, coordinator, stored = failed_rig()
    old = p.stages[1].job_id
    result = asyncio.run(coordinator.action(p.id, p.owner, "retry", fake.deps(), expected_job_id=old))
    assert fake.submitted == ["model", "rig", "rig"]
    assert result.stages[0] == p.stages[0] and result.scene_id == SCENE
    assert result.stages[1].failed_attempts[0].job_id == old
    assert result.stages[1].failed_attempts[0].error_code == "scene_recipe_failed"
    assert result.stages[1].job_id != old
    fake.finish(result.stages[1].job_id,
                result={"revision": {"id": "revision_" + "e" * 32, "scene_id": SCENE}})
    result = asyncio.run(coordinator.action(p.id, p.owner, "status", fake.deps()))
    assert result.state == "awaiting_approval" and result.stages[2].state == "awaiting_approval"
    assert fake.exported == []


def test_concurrent_and_stale_retries_submit_only_once() -> None:
    p, fake, coordinator, _ = failed_rig()
    async def scenario() -> None:
        old = p.stages[1].job_id
        args = (p.id, p.owner, "retry", fake.deps())
        results = await asyncio.gather(*(coordinator.action(*args, expected_job_id=old) for _ in range(2)),
                                       return_exceptions=True)
        assert sum(isinstance(r, PipelineStalled) for r in results) == 1
        assert fake.submitted == ["model", "rig", "rig"]
        current = next(r for r in results if not isinstance(r, Exception))
        fake.fail(current.stages[1].job_id, "still_failed")
        await coordinator.action(p.id, p.owner, "status", fake.deps())
        with pytest.raises(PipelineStalled, match="pipeline_retry_job_changed"):
            await coordinator.action(*args, expected_job_id=old)
        assert fake.submitted == ["model", "rig", "rig"]
    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["running", "succeeded"])
def test_actual_job_must_be_confirmed_failed(status: str) -> None:
    p, fake, coordinator, stored = failed_rig()
    old = p.stages[1].job_id
    fake.jobs[old]["status"] = status
    with pytest.raises(PipelineStalled, match="reconciliation"):
        asyncio.run(coordinator.action(p.id, p.owner, "retry", fake.deps(), expected_job_id=old))
    assert stored[p.id] == p and fake.submitted == ["model", "rig"]


def test_retry_owner_and_expected_job_required() -> None:
    p, fake, coordinator, stored = failed_rig()
    with pytest.raises(KeyError):
        asyncio.run(coordinator.action(p.id, "other", "retry", fake.deps(), expected_job_id=p.stages[1].job_id))
    with pytest.raises(ValueError):
        AssetPipelineActionRequest(pipeline_id=p.id, action="retry")
    with pytest.raises(ValueError):
        AssetPipelineActionRequest(pipeline_id=p.id, expected_job_id=p.stages[1].job_id)
    assert stored[p.id] == p


@pytest.mark.parametrize("failure", ["exception", "cancel", "lost_job", "restart"])
def test_unknown_dispatch_is_persisted_and_never_resubmitted(failure: str) -> None:
    p, fake, coordinator, stored = failed_rig()
    async def scenario() -> None:
        old = p.stages[1].job_id
        saved = None
        async def submit(*args: Any) -> dict[str, Any]:
            nonlocal saved
            saved = stored[p.id].model_copy(deep=True)
            assert saved.stages[1].job_id is None
            if failure == "cancel":
                raise asyncio.CancelledError()
            if failure in {"exception", "restart"}:
                raise RuntimeError("connection lost after possible acceptance")
            return {}
        deps = replace(fake.deps(), submit_rig=submit)
        if failure == "lost_job":
            result = await coordinator.action(p.id, p.owner, "retry", deps, expected_job_id=old)
            assert result.state == "failed"
        else:
            with pytest.raises((RuntimeError, asyncio.CancelledError)):
                await coordinator.action(p.id, p.owner, "retry", deps, expected_job_id=old)
        if failure == "restart":
            stored[p.id] = saved
        result = await coordinator.action(p.id, p.owner, "status", deps)
        assert result.state == "failed" and result.stages[1].job_id is None
        with pytest.raises(PipelineStalled):
            await coordinator.action(p.id, p.owner, "retry", deps, expected_job_id=old)
        assert fake.submitted == ["model", "rig"]
        assert fake.exported == []
    asyncio.run(scenario())


def test_retry_budget_is_bounded() -> None:
    initial, fake, coordinator, _ = failed_rig()
    async def scenario() -> None:
        p = initial
        for _ in range(8):
            p = await coordinator.action(p.id, p.owner, "retry", fake.deps(), expected_job_id=p.stages[1].job_id)
            fake.fail(p.stages[1].job_id, "failed_again")
            p = await coordinator.action(p.id, p.owner, "status", fake.deps())
        assert len(p.stages[1].failed_attempts) == 8
        with pytest.raises(PipelineStalled, match="pipeline_retry_limit"):
            await coordinator.action(p.id, p.owner, "retry", fake.deps(), expected_job_id=p.stages[1].job_id)
    asyncio.run(scenario())
