"""Advance a pipeline by one step when it is polled.

裏で走り続ける番人は置かない。置くと再起動やクラッシュのたびに「誰が続きを
やるのか」を決めることになり、job の所有者が二重になる。呼ばれたときに 1 歩
進める形なら、状態は表 1 つで足りるし、進んだ理由も呼んだ人に説明できる。

実行は既存の job をそのまま使う。ここが足すのは順番と、その順番を覚えておく
ことだけである。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from weakref import WeakValueDictionary

from .asset_pipeline import AssetPipeline, AssetPipelineRequest, PipelineStage

TERMINAL = {"succeeded", "failed", "canceled"}


@dataclass(frozen=True)
class PipelineDeps:
    """既存の経路を渡してもらう。ここでは job を作らない。"""

    submit_image: Callable[[str, int, int], Awaitable[dict[str, Any]]]
    submit_model: Callable[[AssetPipelineRequest, str], Awaitable[dict[str, Any]]]
    submit_rig: Callable[[AssetPipelineRequest, str, str], Awaitable[dict[str, Any]]]
    export_scene: Callable[[str, str], Awaitable[dict[str, Any]]]
    media_job: Callable[[str], Awaitable[dict[str, Any]]]
    scene_job: Callable[[str], Awaitable[dict[str, Any]]]
    now: Callable[[], str]


class PipelineStalled(RuntimeError):
    """A step failed; the pipeline stops rather than carrying a bad input forward."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _finish(stage: PipelineStage, state: str, deps: PipelineDeps, code: str | None = None) -> None:
    stage.state = state  # type: ignore[assignment]
    stage.error_code = code
    stage.finished_at = deps.now()


async def _poll_running(pipeline: AssetPipeline, stage: PipelineStage, deps: PipelineDeps) -> bool:
    """Returns True when the step is done and the pipeline may move on."""
    if stage.job_id is None:
        _finish(stage, "failed", deps, "pipeline_stage_lost_its_job")
        return False
    job = await (deps.media_job if stage.name == "image" else deps.scene_job)(stage.job_id)
    status = str(job.get("status", ""))
    if status not in TERMINAL:
        return False
    if status != "succeeded":
        error = job.get("error") or {}
        _finish(stage, "failed", deps, str(error.get("code") or f"stage_{status}"))
        return False
    if stage.name == "image":
        assets = job.get("asset_ids") or []
        if not assets:
            _finish(stage, "failed", deps, "image_stage_produced_no_asset")
            return False
        stage.asset_id = str(assets[0])
    else:
        result = job.get("result") or {}
        revision = result.get("revision") or {}
        if revision.get("id"):
            stage.revision_id = str(revision["id"])
            pipeline.scene_id = str(revision.get("scene_id") or pipeline.scene_id or "") or None
        elif stage.name in {"model", "rig"}:
            _finish(stage, "failed", deps, "stage_produced_no_revision")
            return False
    _finish(stage, "succeeded", deps)
    return True


def _input_asset(pipeline: AssetPipeline, value: AssetPipelineRequest) -> str | None:
    if value.image_asset_id is not None:
        return value.image_asset_id
    for stage in pipeline.stages:
        if stage.name == "image":
            return stage.asset_id
    return None


def _base_revision(pipeline: AssetPipeline) -> str | None:
    """The newest revision any earlier step produced."""
    found = None
    for stage in pipeline.stages:
        if stage.revision_id is not None and stage.state == "succeeded":
            found = stage.revision_id
    return found


async def _start(pipeline: AssetPipeline, stage: PipelineStage, value: AssetPipelineRequest,
                 deps: PipelineDeps) -> None:
    stage.started_at = deps.now()
    if stage.name == "image":
        submitted = await deps.submit_image(str(value.prompt), value.width, value.height)
    elif stage.name == "model":
        asset_id = _input_asset(pipeline, value)
        if asset_id is None:
            _finish(stage, "failed", deps, "model_stage_has_no_input_image")
            return
        submitted = await deps.submit_model(value, asset_id)
    elif stage.name == "rig":
        revision = _base_revision(pipeline)
        if pipeline.scene_id is None or revision is None:
            _finish(stage, "failed", deps, "rig_stage_has_no_scene")
            return
        submitted = await deps.submit_rig(value, pipeline.scene_id, revision)
    else:
        if pipeline.scene_id is None:
            _finish(stage, "failed", deps, "export_stage_has_no_scene")
            return
        # 書き出しは job にならず、その場で資産が返る。
        exported = await deps.export_scene(pipeline.scene_id, value.export_format)
        stage.asset_id = str(exported.get("asset_id") or "") or None
        _finish(stage, "succeeded" if stage.asset_id else "failed", deps,
                None if stage.asset_id else "export_stage_produced_no_asset")
        return
    stage.job_id = str(submitted.get("job_id") or "") or None
    stage.state = "running" if stage.job_id else "failed"
    if stage.job_id is None:
        _finish(stage, "failed", deps, "stage_was_not_accepted")


async def advance(pipeline: AssetPipeline, deps: PipelineDeps) -> AssetPipeline:
    """Move the pipeline as far as it can go right now, then return it.

    1 回の呼び出しで、終わった段は次へ進め、始められる段は 1 つだけ始める。
    走っている段が終わるまで待たない（待つと poll が返らない）。
    """
    if pipeline.state in TERMINAL:
        return pipeline
    value = AssetPipelineRequest.model_validate(pipeline.request)
    for _ in range(len(pipeline.stages) + 1):
        stage = pipeline.current()
        if stage is None:
            break
        if stage.state == "running":
            if not await _poll_running(pipeline, stage, deps):
                break
            continue
        if stage.state == "awaiting_approval":
            break
        # confirm では、最初の段以外は承認を待つ。何が出来たかを見てから進める。
        if (pipeline.mode == "confirm" and not stage.approved
                and pipeline.previous_of(stage) is not None):
            stage.state = "awaiting_approval"
            break
        await _start(pipeline, stage, value, deps)
        if stage.state == "failed":
            break
        if stage.state == "running":
            break
    failed = [stage for stage in pipeline.stages if stage.state == "failed"]
    remaining = pipeline.current()
    if failed:
        pipeline.state = "failed"
    elif remaining is None:
        pipeline.state = "succeeded"
    elif remaining.state == "awaiting_approval":
        pipeline.state = "awaiting_approval"
    else:
        pipeline.state = "running"
    pipeline.updated_at = deps.now()
    return pipeline


def approve(pipeline: AssetPipeline, deps: PipelineDeps) -> AssetPipeline:
    """Let the step the pipeline is waiting on start on the next poll."""
    if pipeline.state in TERMINAL:
        raise PipelineStalled("pipeline_already_finished")
    stage = pipeline.current()
    if stage is None or stage.state != "awaiting_approval":
        raise PipelineStalled("pipeline_is_not_awaiting_approval")
    stage.state = "pending"
    stage.approved = True
    pipeline.state = "running"
    pipeline.updated_at = deps.now()
    return pipeline


class PipelineCoordinator:
    """Serialize a pipeline's read/advance/write in the single core process.

    Different pipelines keep independent request-bound dependencies. Weak locks
    are retained by all callers while waiting, then reclaimed after use.
    """

    def __init__(self, load: Callable[[str, str], AssetPipeline],
                 save: Callable[[AssetPipeline], None]) -> None:
        self.load = load
        self.save = save
        self.locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()

    async def start(self, pipeline: AssetPipeline, deps: PipelineDeps) -> AssetPipeline:
        # The identifier is private until this request returns.
        result = await advance(pipeline, deps)
        await asyncio.to_thread(self.save, result)
        return result

    async def action(self, pipeline_id: str, owner: str, action: str,
                     deps: PipelineDeps) -> AssetPipeline:
        lock = self.locks.setdefault(pipeline_id, asyncio.Lock())
        async with lock:
            pipeline = await asyncio.to_thread(self.load, pipeline_id, owner)
            if action == "approve":
                approve(pipeline, deps)
            elif action == "cancel":
                cancel(pipeline, deps)
            elif action != "status":
                raise PipelineStalled("invalid_pipeline_action")
            result = await advance(pipeline, deps)
            await asyncio.to_thread(self.save, result)
            return result


def cancel(pipeline: AssetPipeline, deps: PipelineDeps) -> AssetPipeline:
    """Stop before the next step. 走っている job はそのまま終わらせる。"""
    if pipeline.state in {"succeeded", "failed", "canceled"}:
        raise PipelineStalled("pipeline_already_finished")
    for stage in pipeline.stages:
        if stage.state in {"pending", "awaiting_approval"}:
            _finish(stage, "skipped", deps)
    pipeline.state = "canceled"
    pipeline.updated_at = deps.now()
    return pipeline
