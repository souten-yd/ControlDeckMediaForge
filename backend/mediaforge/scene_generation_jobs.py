"""Image generation inside the existing durable scene Job lifecycle."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any
import uuid

from .host.client import HostApiError
from .host.jobs import HostExecution, HostJobReporter
from .paths import contained
from .scene_generation import SceneFromImageRequest
from .scenes import SceneError
from .three_d_runtime import RuntimeReceipt

if TYPE_CHECKING:
    from .scene_recipe_jobs import SceneRecipeJobManager


def receipt_digest(receipt: RuntimeReceipt) -> str:
    return hashlib.sha256(receipt.model_dump_json().encode()).hexdigest()


async def generate_scene_from_image(
    manager: SceneRecipeJobManager, job_id: str, value: SceneFromImageRequest,
    execution: HostExecution, reporter: HostJobReporter,
) -> dict[str, Any]:
    from .scene_recipe_jobs import _finish_cleanup

    generator = manager.generator
    if generator is None:
        raise SceneError('three_d_runtime_unavailable', '3D generator is unavailable')
    receipt = generator.resolve(value.engine, value.resolution)
    constraints = manager.store.get_job(job_id).request.constraints
    if receipt_digest(receipt) != constraints.get('generation_runtime_sha256'):
        raise SceneError('three_d_runtime_changed', '3D runtime changed after job admission')
    asset = manager.store.get_asset(value.input_asset_id)
    if asset.sha256 != constraints.get('generation_input_sha256'):
        raise SceneError('scene_generation_input_invalid', 'Generation input changed after admission')
    _, _, source = manager.workspace._verified_revision_asset(asset.id, asset.mime_type)
    root = contained(manager.workspace.recipe_root, manager.workspace.recipe_root / f'native_{uuid.uuid4().hex}')
    root.mkdir(mode=0o700)
    request_task: asyncio.Task[dict[str, Any]] | None = None

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
        image = root / ('input' + source.suffix)
        shutil.copyfile(source, image)
        image.chmod(0o600)
        if manager.workspace._sha256(image) != asset.sha256:
            raise SceneError('scene_generation_input_invalid', 'Generation input changed while staging')
        if receipt.engine == 'pixal3d':
            await phase('prepare_3d_input', 0.15)
        prepared = await generator.prepare(receipt, value, image, root)
        if receipt_digest(generator.resolve(value.engine, value.resolution)) != constraints.get('generation_runtime_sha256'):
            raise SceneError('three_d_runtime_changed', '3D adoption changed during input preparation')
        await phase('waiting_resource', 0.25)
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
        if receipt_digest(generator.resolve(value.engine, value.resolution)) != constraints.get('generation_runtime_sha256'):
            raise SceneError('three_d_runtime_changed', '3D adoption changed while waiting for GPU admission')
        if (execution.device_id != receipt.device_id or execution.granted_bytes is None
                or execution.granted_bytes < receipt.measured_peak_vram_bytes):
            raise SceneError('resource_grant_incompatible', 'Host grant cannot run the measured 3D runtime')
        await manager.host.lease_action(execution.identity, execution.lease_id or '', 'activate')
        await phase('generate_3d', 0.35)
        renewal = asyncio.create_task(renew_lease())
        worker = asyncio.create_task(generator.generate(receipt, value, image, root, execution, prepared=prepared))
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
        await phase('validate_generated_scene', 0.75)
        task = manager.store.get_scene_recipe_task(job_id)
        async with manager._execution_guard:
            return await manager.workspace.import_generated_glb(
                task.owner, job_id, value, output, root, facts,
                runtime_id=task.runtime_id, runtime_version=task.runtime_version,
            )
    finally:
        try:
            await _finish_cleanup(asyncio.create_task(release_resource()))
        finally:
            manager.workspace._remove_tree(root, manager.workspace.recipe_root)


async def _drain(*tasks: asyncio.Task[Any]) -> None:
    await asyncio.gather(*tasks, return_exceptions=True)
