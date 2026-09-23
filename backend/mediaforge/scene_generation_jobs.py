"""Image generation inside the existing durable scene Job lifecycle."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
import uuid

from .host.client import HostApiError
from .host.jobs import HostExecution, HostJobReporter
from .paths import contained
from .scene_generation import GenerationFacts, SceneFromImageRequest
from .scene_generation_inputs import inspect_views
from .scenes import SceneError
from .three_d_runtime import RuntimeReceipt

if TYPE_CHECKING:
    from .scene_recipe_jobs import SceneRecipeJobManager


def receipt_digest(receipt: RuntimeReceipt) -> str:
    return hashlib.sha256(receipt.model_dump_json().encode()).hexdigest()


def stages_digest(receipts: list[RuntimeReceipt]) -> str:
    """One identity for the whole pinned chain, so a mid-job adoption change is caught.

    段を足したときに 1 段目だけを見ていると、2 段目の採用が入れ替わっても
    admission 後の検査を素通りする。順番も含めて 1 つの値にする。
    """
    return hashlib.sha256(json.dumps(
        [receipt_digest(item) for item in receipts], separators=(",", ":"),
    ).encode()).hexdigest()


async def generate_scene_from_image(
    manager: SceneRecipeJobManager, job_id: str, value: SceneFromImageRequest,
    execution: HostExecution, reporter: HostJobReporter,
) -> dict[str, Any]:
    """Run the pinned chain: trellis.cpp, then Pixal3D only when it was requested.

    1 段目までが既定の成果物である。2 段目は「もっと精度を上げる」ための追加で、
    そこが落ちても 1 段目の成果物は publish 済みのまま残し、理由を結果に書く。
    握り潰しではなく、`refine` に state と reason を必ず載せる。
    """
    generator = manager.generator
    if generator is None:
        raise SceneError('three_d_runtime_unavailable', '3D generator is unavailable')
    receipts = generator.resolve_request(value)
    constraints = manager.store.get_job(job_id).request.constraints
    if stages_digest(receipts) != constraints.get('generation_runtime_sha256'):
        raise SceneError('three_d_runtime_changed', '3D runtime changed after job admission')
    asset = manager.store.get_asset(value.input_asset_id)
    if asset.sha256 != constraints.get('generation_input_sha256'):
        raise SceneError('scene_generation_input_invalid', 'Generation input changed after admission')
    _, _, source = manager.workspace._verified_revision_asset(asset.id, asset.mime_type)
    view_sources: list[Path] = []
    if value.additional_views:
        views, view_sources = await asyncio.to_thread(inspect_views, manager.workspace, value)
        if [v.model_dump(mode='json') for v in views] != constraints.get('generation_views'):
            raise SceneError('scene_generation_input_invalid', 'Additional views changed after admission')
    root = contained(manager.workspace.recipe_root, manager.workspace.recipe_root / f'native_{uuid.uuid4().hex}')
    root.mkdir(mode=0o700)
    # 段ごとの進み。1 段だけなら今までと同じ 0.15〜0.75 を使う。
    spans = [(0.10, 0.70)] if len(receipts) == 1 else [(0.08, 0.42), (0.45, 0.88)]
    try:
        result: dict[str, Any] | None = None
        for index, receipt in enumerate(receipts):
            # 追加の段は自分の実測解像度で走らせる。記録する facts もその解像度になる。
            stage_value = value if index == 0 else value.model_copy(
                update={'resolution': receipt.evaluated_resolution})
            stage_root = contained(root, root / f'stage{index + 1}')
            stage_root.mkdir(mode=0o700)
            image = stage_root / ('input' + source.suffix)
            shutil.copyfile(source, image)
            image.chmod(0o600)
            if manager.workspace._sha256(image) != asset.sha256:
                raise SceneError('scene_generation_input_invalid', 'Generation input changed while staging')
            for view_index, view_source in enumerate(view_sources[1:], 1):
                staged_view = stage_root/f'view-source-{view_index}'
                shutil.copyfile(view_source, staged_view)
                staged_view.chmod(0o600)
                if manager.workspace._sha256(staged_view) != constraints['generation_views'][view_index]['sha256']:
                    raise SceneError('scene_generation_input_invalid', 'Additional view changed while staging')
            try:
                output, facts = await _run_stage(
                    manager, job_id, value, stage_value, execution, reporter, receipt,
                    image, stage_root, span=spans[index], stage_index=index,
                )
            except Exception as exc:
                if result is None:
                    raise
                # 1 段目は publish 済みである。落ちたのは追加の段だけなので、
                # 出来ているものを返し、何がどう落ちたかを結果へ残す。取り消しは
                # BaseException なのでここへ来ない（途中で止めたときは publish しない）。
                result['refine'] = {'state': 'failed', 'engine': receipt.engine,
                                    'reason': getattr(exc, 'code', 'three_d_refine_failed')}
                break
            task = manager.store.get_scene_recipe_task(job_id)
            if value.additional_views:
                current_views, _ = await asyncio.to_thread(inspect_views, manager.workspace, value)
                if [v.model_dump(mode='json') for v in current_views] != constraints.get('generation_views'):
                    raise SceneError('scene_generation_input_invalid', 'Additional view changed before publication')
            async with manager._execution_guard:
                if result is None:
                    result = await manager.workspace.import_generated_glb(
                        task.owner, job_id, stage_value, output, stage_root, facts,
                        runtime_id=task.runtime_id, runtime_version=task.runtime_version,
                    )
                    result['refine'] = {'state': 'not_requested' if len(receipts) == 1 else 'running',
                                        'engine': receipts[-1].engine if len(receipts) > 1 else None,
                                        'reason': None}
                else:
                    result = await manager.workspace.commit_generated_glb(
                        task.owner, job_id, stage_value, output, stage_root, facts,
                        scene_id=result['scene']['id'], base_revision_id=result['revision']['id'],
                        previous_asset_ids=result.get('asset_ids', []),
                        runtime_id=task.runtime_id, runtime_version=task.runtime_version,
                    )
                    result['refine'] = {'state': 'succeeded', 'engine': receipt.engine, 'reason': None}
        if result is None:
            raise SceneError('three_d_runtime_unavailable', 'No adopted 3D stage produced a scene')
        return result
    finally:
        manager.workspace._remove_tree(root, manager.workspace.recipe_root)


async def _run_stage(
    manager: SceneRecipeJobManager, job_id: str, value: SceneFromImageRequest,
    stage_value: SceneFromImageRequest, execution: HostExecution, reporter: HostJobReporter,
    receipt: RuntimeReceipt, image: Path, root: Path, *, span: tuple[float, float], stage_index: int,
) -> tuple[Path, GenerationFacts]:
    """One pinned engine: prepare, take a lease, generate, and give the lease back."""
    from .scene_recipe_jobs import _finish_cleanup

    generator = manager.generator
    assert generator is not None
    constraints = manager.store.get_job(job_id).request.constraints
    request_task: asyncio.Task[dict[str, Any]] | None = None
    start, end = span
    # 1 段目の phase 名は今までどおり。追加の段だけ別名にして、画面と記録で区別する。
    suffix = '' if stage_index == 0 else '_refine'

    def unchanged() -> None:
        if stages_digest(generator.resolve_request(value)) != constraints.get('generation_runtime_sha256'):
            raise SceneError('three_d_runtime_changed', '3D adoption changed during generation')

    def capture_status(status: dict[str, Any]) -> None:
        request_id = status.get('request_id')
        if not isinstance(request_id, str) or not request_id:
            raise HostApiError('invalid_host_response', 'Host resource request ID is missing')
        execution.request_id = request_id
        if status.get('state') == 'granted':
            lease_id = status.get('lease_id')
            if not isinstance(lease_id, str) or not lease_id:
                raise HostApiError('invalid_host_response', 'Host resource lease ID is missing')
            execution.lease_id = lease_id
            execution.device_id = status.get('device_id')
            granted = status.get('granted_bytes')
            execution.granted_bytes = granted if type(granted) is int else None

    async def release_resource() -> None:
        # A canceled HTTP caller must still collect its admission response so
        # that a grant created by that request cannot escape cleanup.
        try:
            if request_task is not None:
                capture_status(await request_task)
        finally:
            if execution.lease_id:
                await manager.host.lease_action(execution.identity, execution.lease_id, 'release')
            elif execution.request_id:
                await manager.host.cancel_resource(execution.identity, execution.request_id)
            execution.lease_id = None
            execution.request_id = None
            execution.device_id = None
            execution.granted_bytes = None

    async def renew_lease() -> None:
        while True:
            await asyncio.sleep(manager.lease_renew_sec)
            await manager.host.lease_action(execution.identity, execution.lease_id or '', 'renew')

    async def phase(name: str, progress: float) -> None:
        manager.store.update_job(job_id, phase=name, progress=progress)
        manager.store.update_scene_recipe_task(job_id, stage=name)
        await manager._report_progress(reporter, name, progress)

    try:
        if receipt.engine == 'pixal3d':
            await phase('prepare_3d_input' + suffix, start)
        prepared = await generator.prepare(receipt, stage_value, image, root)
        if value.additional_views:
            from .multiview_runtime import PreparedMultiview
            if not isinstance(prepared, PreparedMultiview) or [v.model_dump(mode='json') for v in prepared.facts] != constraints.get('generation_views'):
                raise SceneError('scene_generation_input_invalid', 'Prepared views differ from admitted inputs')
        unchanged()
        await phase('waiting_resource', start + (end - start) * .2)
        request_task = asyncio.create_task(manager.host.request_resource(
            execution.identity, generator.resource_request(receipt, execution),
        ))
        status = await asyncio.shield(request_task)
        capture_status(status)
        request_task = None
        deadline = asyncio.get_running_loop().time() + manager.resource_wait_sec
        while status.get('state') == 'waiting':
            if asyncio.get_running_loop().time() >= deadline:
                raise SceneError('resource_wait_timeout', '3D resource wait exceeded its time bound')
            await asyncio.sleep(manager.resource_poll_sec)
            status = await manager.host.resource_status(execution.identity, execution.request_id or '')
            capture_status(status)
        if status.get('state') != 'granted':
            raise SceneError('resource_unavailable', 'ControlDeck could not grant the 3D resource request')
        unchanged()
        if (execution.device_id != receipt.device_id or execution.granted_bytes is None
                or execution.granted_bytes < receipt.measured_peak_vram_bytes):
            raise SceneError('resource_grant_incompatible', 'Host grant cannot run the measured 3D runtime')
        await manager.host.lease_action(execution.identity, execution.lease_id or '', 'activate')
        await phase('generate_3d' + suffix, start + (end - start) * .35)
        renewal = asyncio.create_task(renew_lease())
        worker = asyncio.create_task(generator.generate(receipt, stage_value, image, root, execution, prepared=prepared))
        try:
            done, _ = await asyncio.wait({worker, renewal}, return_when=asyncio.FIRST_COMPLETED)
            if renewal in done:
                renewal.result()
                raise SceneError('host_lease_lost', '3D resource lease maintenance stopped')
            output, facts = worker.result()
        finally:
            worker.cancel()
            # Keep renewing while cancellation reaps a CPU wrapper/native group.
            # Releasing or abandoning the lease before drain could overlap jobs.
            try:
                await _finish_cleanup(asyncio.create_task(_drain(worker)))
            finally:
                renewal.cancel()
                await _finish_cleanup(asyncio.create_task(_drain(renewal)))
        # GPU process is reaped before releasing the lease. Blender validation
        # is CPU-only and does not retain the generation resource reservation.
        await release_resource()
        await phase('validate_generated_scene' + suffix, end)
        return output, facts
    finally:
        await _finish_cleanup(asyncio.create_task(release_resource()))


async def _drain(*tasks: asyncio.Task[Any]) -> None:
    await asyncio.gather(*tasks, return_exceptions=True)
