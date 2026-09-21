"""画像→3D→骨→書き出しを、順番だけ持って進める。

実行は既存の job をそのまま使うので、ここで確かめるのは順番・止まり方・
失敗したときに先へ進まないことである。Blender も GPU も要らない。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mediaforge.asset_pipeline import AssetPipeline, AssetPipelineRequest, PipelineStage
from mediaforge.asset_pipeline_runner import PipelineDeps, PipelineStalled, advance, approve, cancel

SCENE = "scene_" + "a" * 32
REVISION_MODEL = "revision_" + "b" * 32
REVISION_RIG = "revision_" + "c" * 32


class Fake:
    """段ごとに job を出したことにして、終わらせる時期をこちらで決める。"""

    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.submitted: list[str] = []
        self.exported: list[tuple[str, str]] = []
        self.clock = 0

    def now(self) -> str:
        self.clock += 1
        return f"2026-09-21T00:00:{self.clock:02d}+00:00"

    def _job(self, name: str) -> dict[str, Any]:
        job_id = "job_" + f"{len(self.jobs):032x}"
        self.jobs[job_id] = {"job_id": job_id, "id": job_id, "status": "running"}
        self.submitted.append(name)
        return {"job_id": job_id}

    def finish(self, job_id: str, **changes: Any) -> None:
        self.jobs[job_id].update({"status": "succeeded", **changes})

    def fail(self, job_id: str, code: str) -> None:
        self.jobs[job_id].update({"status": "failed", "error": {"code": code}})

    def deps(self) -> PipelineDeps:
        async def submit_image(prompt: str, width: int, height: int) -> dict[str, Any]:
            return self._job("image")

        async def submit_model(value: AssetPipelineRequest, asset_id: str) -> dict[str, Any]:
            return self._job("model")

        async def submit_rig(value: AssetPipelineRequest, scene: str, revision: str) -> dict[str, Any]:
            assert scene == SCENE and revision == REVISION_MODEL
            return self._job("rig")

        async def export_scene(scene: str, fmt: str) -> dict[str, Any]:
            self.exported.append((scene, fmt))
            return {"asset_id": "asset_" + "e" * 32}

        async def lookup(job_id: str) -> dict[str, Any]:
            return self.jobs[job_id]

        return PipelineDeps(submit_image=submit_image, submit_model=submit_model,
                            submit_rig=submit_rig, export_scene=export_scene,
                            media_job=lookup, scene_job=lookup, now=self.now)


def build(**changes: Any) -> tuple[AssetPipeline, AssetPipelineRequest]:
    payload: dict[str, Any] = {"name": "Robot", "prompt": "a six legged robot", "mode": "auto"}
    payload.update(changes)
    value = AssetPipelineRequest.model_validate(payload)
    pipeline = AssetPipeline(
        id="pipeline_" + "1" * 32, owner="tester", name=value.name, mode=value.mode,
        request=value.model_dump(mode="json"),
        stages=[PipelineStage(name=name) for name in value.planned_stages()],
        created_at="2026-09-21T00:00:00+00:00", updated_at="2026-09-21T00:00:00+00:00",
    )
    return pipeline, value


def run(pipeline: AssetPipeline, deps: PipelineDeps) -> AssetPipeline:
    return asyncio.run(advance(pipeline, deps))


def test_auto_runs_the_steps_in_order_and_carries_the_result_forward() -> None:
    pipeline, _ = build()
    fake = Fake()
    deps = fake.deps()
    assert [stage.name for stage in pipeline.stages] == ["image", "model", "rig", "export"]

    run(pipeline, deps)
    assert fake.submitted == ["image"] and pipeline.state == "running"
    # 走っている間は待たない。poll しても同じ所に居る。
    run(pipeline, deps)
    assert fake.submitted == ["image"]

    image_job = pipeline.stages[0].job_id
    fake.finish(image_job, asset_ids=["asset_" + "d" * 32])
    run(pipeline, deps)
    assert fake.submitted == ["image", "model"]
    assert pipeline.stages[0].asset_id == "asset_" + "d" * 32

    fake.finish(pipeline.stages[1].job_id,
                result={"revision": {"id": REVISION_MODEL, "scene_id": SCENE}})
    run(pipeline, deps)
    assert fake.submitted == ["image", "model", "rig"]
    assert pipeline.scene_id == SCENE

    fake.finish(pipeline.stages[2].job_id,
                result={"revision": {"id": REVISION_RIG, "scene_id": SCENE}})
    run(pipeline, deps)
    assert fake.exported == [(SCENE, "glb")]
    assert pipeline.state == "succeeded"
    assert [stage.state for stage in pipeline.stages] == ["succeeded"] * 4


def test_confirm_stops_before_every_step_after_the_first() -> None:
    pipeline, _ = build(mode="confirm")
    fake = Fake()
    deps = fake.deps()
    run(pipeline, deps)
    assert fake.submitted == ["image"]
    fake.finish(pipeline.stages[0].job_id, asset_ids=["asset_" + "d" * 32])
    run(pipeline, deps)
    # 2 段目は勝手に始まらない。何が出来たかを見てから進める。
    assert fake.submitted == ["image"] and pipeline.state == "awaiting_approval"
    assert pipeline.stages[1].state == "awaiting_approval"
    approve(pipeline, deps)
    run(pipeline, deps)
    assert fake.submitted == ["image", "model"]


def test_approving_when_nothing_waits_is_refused() -> None:
    pipeline, _ = build()
    fake = Fake()
    with pytest.raises(PipelineStalled):
        approve(pipeline, fake.deps())


def test_a_failed_step_stops_the_chain() -> None:
    """失敗した出力を次の段へ持ち込まない。"""
    pipeline, _ = build()
    fake = Fake()
    deps = fake.deps()
    run(pipeline, deps)
    fake.fail(pipeline.stages[0].job_id, "generation_failed")
    run(pipeline, deps)
    assert pipeline.state == "failed"
    assert pipeline.stages[0].error_code == "generation_failed"
    assert fake.submitted == ["image"]
    assert [stage.state for stage in pipeline.stages[1:]] == ["pending"] * 3


def test_a_succeeded_model_step_without_a_revision_is_a_failure() -> None:
    pipeline, _ = build(image_asset_id="asset_" + "d" * 32, prompt=None)
    fake = Fake()
    deps = fake.deps()
    run(pipeline, deps)
    fake.finish(pipeline.stages[0].job_id, result={})
    run(pipeline, deps)
    assert pipeline.state == "failed"
    assert pipeline.stages[0].error_code == "stage_produced_no_revision"


def test_steps_can_be_left_out() -> None:
    pipeline, _ = build(rig=False, export=False)
    assert [stage.name for stage in pipeline.stages] == ["image", "model"]
    pipeline, _ = build(image_asset_id="asset_" + "d" * 32, prompt=None)
    assert [stage.name for stage in pipeline.stages] == ["model", "rig", "export"]


def test_cancel_skips_what_has_not_started() -> None:
    pipeline, _ = build()
    fake = Fake()
    deps = fake.deps()
    run(pipeline, deps)
    cancel(pipeline, deps)
    assert pipeline.state == "canceled"
    # 走っている段はそのまま。始まっていない段だけ飛ばす。
    assert pipeline.stages[0].state == "running"
    assert [stage.state for stage in pipeline.stages[1:]] == ["skipped"] * 3
    with pytest.raises(PipelineStalled):
        cancel(pipeline, deps)


def test_stage_order_is_fixed() -> None:
    with pytest.raises(ValueError):
        AssetPipeline(
            id="pipeline_" + "1" * 32, owner="tester", name="Bad", mode="auto", request={},
            stages=[PipelineStage(name="rig"), PipelineStage(name="model")],
            created_at="2026-09-21T00:00:00+00:00", updated_at="2026-09-21T00:00:00+00:00",
        )
