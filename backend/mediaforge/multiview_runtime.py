"""Measured native Vulkan multiview runtime; uses existing scene Job leases."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .glb import validate_glb_path
from .host.jobs import HostExecution
from .multiview_inputs import image_identity, verify_directory
from .paths import contained
from .scene_generation import (GenerationFacts, GenerationViewCamera, GenerationViewFacts,
                               MultiviewExecutionFacts, SceneFromImageRequest)
from .scene_generation_inputs import view_transforms
from .scenes import SceneError
from .three_d_runtime_files import RuntimeFile, sha256_file

MV_MODEL_FILES = frozenset({'dinov3.gguf', 'pixal3d_naf.gguf', 'ss_dec.gguf',
                          'shape_dec.gguf', 'tex_dec.gguf', 'pixal3d_ss_flow_mv.gguf',
                          'pixal3d_shape_flow_512_mv.gguf', 'pixal3d_shape_flow_1024_mv.gguf',
                          'pixal3d_tex_flow_1024_mv.gguf'})


class MultiviewRuntimeReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    schema_version: Literal['media-forge.pixal3d-multiview-runtime@1'] = 'media-forge.pixal3d-multiview-runtime@1'
    engine: Literal['pixal3d'] = 'pixal3d'
    backend: Literal['vulkan'] = 'vulkan'
    precision: Literal['q8_0_flows_f16_shared'] = 'q8_0_flows_f16_shared'
    runtime_root: Path
    executable: str = Field(min_length=1, max_length=256)
    runtime_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    runtime_files: dict[str, RuntimeFile] = Field(min_length=1, max_length=128)
    model_repository: Path
    model_snapshot: str = Field(min_length=1, max_length=512)
    model_files: dict[str, RuntimeFile] = Field(min_length=9, max_length=9)
    model_id: str = Field(min_length=1, max_length=128, pattern=r'^[a-zA-Z0-9_./-]+$')
    model_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    license: str = Field(min_length=1, max_length=256)
    license_accepted: Literal[True]
    device_id: str = Field(pattern=r'^gpu[0-9]+$')
    native_device_index: int = Field(ge=0, le=31, strict=True)
    evaluated_resolution: Literal[1024] = 1024
    evaluated_view_counts: list[Literal[2, 3, 4]] = Field(min_length=1, max_length=3)
    measured_peak_vram_bytes: int = Field(gt=0, le=256*1024**3, strict=True)
    measured_runtime_sec: float = Field(gt=0, le=86400)
    evaluated_output_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    validation: Literal['passed']

    @model_validator(mode='after')
    def bounds(self) -> MultiviewRuntimeReceipt:
        if not self.runtime_root.is_absolute() or not self.model_repository.is_absolute():
            raise ValueError('runtime roots must be private absolute paths')
        for name in (self.executable, self.model_snapshot, *self.runtime_files, *self.model_files):
            if not name or Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('runtime member escapes its root')
        if self.executable not in self.runtime_files or set(self.model_files) != MV_MODEL_FILES:
            raise ValueError('receipt must pin executable and all nine weights')
        if len(set(self.evaluated_view_counts)) != len(self.evaluated_view_counts):
            raise ValueError('repeated measured view count')
        return self


def verify_runtime(receipt: MultiviewRuntimeReceipt, *, hashes: bool) -> None:
    snapshot = contained(receipt.model_repository, receipt.model_repository / receipt.model_snapshot)
    files = [(contained(receipt.runtime_root, receipt.runtime_root/name), identity)
             for name, identity in receipt.runtime_files.items()]
    files += [(contained(receipt.model_repository, snapshot/name), identity)
              for name, identity in receipt.model_files.items()]
    for path, identity in files:
        if not path.is_file() or path.stat().st_size != identity.size_bytes:
            raise ValueError('multiview runtime file missing or size changed')
        if hashes and sha256_file(path) != identity.sha256:
            raise ValueError('multiview runtime digest changed')
    if not os.access(contained(receipt.runtime_root, receipt.runtime_root/receipt.executable), os.X_OK):
        raise ValueError('multiview executable is not executable')


@dataclass(frozen=True)
class PreparedMultiview:
    directory: Path
    receipt_sha256: str
    input_manifest_sha256: str
    facts: tuple[GenerationViewFacts, ...]


def _prepare(receipt: MultiviewRuntimeReceipt, value: SceneFromImageRequest,
             image: Path, root: Path) -> PreparedMultiview:
    directory = contained(root, root/'multiview-inputs')
    directory.mkdir(mode=0o700)
    views = []
    for index, (direction, asset_id) in enumerate(value.ordered_views()):
        source = contained(root, image if index == 0 else root/f'view-source-{index}')
        identity = image_identity(source, allow_webp=True)
        views.append(GenerationViewFacts(direction=direction, asset_id=asset_id,
                     sha256=identity['sha256'], pixels_sha256=identity['premultiplied_pixels_sha256']))
        with Image.open(source) as original:
            original.save(directory/f'view-{index}.png', format='PNG')
        (directory/f'view-{index}.png').chmod(0o600)
    metadata = directory/'transforms.json'
    metadata.write_text(json.dumps(view_transforms(value), sort_keys=True))
    metadata.chmod(0o600)
    audit = verify_directory(directory)
    for original, staged in zip(views, audit['views'], strict=True):
        if original.pixels_sha256 != staged['premultiplied_pixels_sha256']:
            raise ValueError('staged view pixels changed')
    return PreparedMultiview(directory, hashlib.sha256(receipt.model_dump_json().encode()).hexdigest(),
                             audit['input_manifest_sha256'], tuple(views))


async def prepare_multiview(receipt: MultiviewRuntimeReceipt, value: SceneFromImageRequest,
                            image: Path, root: Path) -> PreparedMultiview:
    from .scene_recipe_jobs import _finish_cleanup
    task = asyncio.create_task(asyncio.to_thread(_prepare, receipt, value, image, root))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await _finish_cleanup(task)
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise SceneError('scene_multiview_input_invalid', 'Multiview preparation failed without changing the source images') from exc


async def generate_multiview(receipt: MultiviewRuntimeReceipt, value: SceneFromImageRequest,
                             image: Path, root: Path, execution: HostExecution,
                             prepared: PreparedMultiview | None, *, timeout: float) -> tuple[Path, GenerationFacts]:
    from .scene_workspace import _bounded_read, _stop_process
    if not execution.lease_id or execution.device_id != receipt.device_id:
        raise SceneError('host_lease_required', 'Multiview generation requires its granted GPU lease')
    if len(value.ordered_views()) not in receipt.evaluated_view_counts or value.resolution != 1024:
        raise SceneError('three_d_multiview_not_evaluated', 'Requested multiview count has not been measured')
    receipt_sha = hashlib.sha256(receipt.model_dump_json().encode()).hexdigest()
    try:
        await asyncio.to_thread(verify_runtime, receipt, hashes=True)
        if prepared is None or prepared.receipt_sha256 != receipt_sha:
            raise ValueError('prepared runtime identity changed')
        directory = contained(root, prepared.directory)
        if directory != contained(root, root/'multiview-inputs'):
            raise ValueError('prepared directory changed')
        audit = await asyncio.to_thread(verify_directory, directory)
        if audit['input_manifest_sha256'] != prepared.input_manifest_sha256:
            raise ValueError('prepared view data changed')
        if len(prepared.facts) != len(value.ordered_views()):
            raise ValueError('prepared view count changed')
        expected_metadata = json.dumps(view_transforms(value), sort_keys=True)
        if (directory/'transforms.json').read_text() != expected_metadata:
            raise ValueError('prepared camera changed')
        for index, ((direction, asset_id), facts) in enumerate(zip(value.ordered_views(), prepared.facts, strict=True)):
            source = contained(root, image if index == 0 else root/f'view-source-{index}')
            if facts.direction != direction or facts.asset_id != asset_id or sha256_file(source) != facts.sha256:
                raise ValueError('prepared source identity changed')
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise SceneError('scene_multiview_input_changed', 'Multiview inputs or runtime changed after preparation') from exc
    output = contained(root, root/'generated.glb')
    if output.exists():
        raise SceneError('scene_generation_invalid', 'Generation output already exists')
    sandbox = root/'native-user'
    sandbox.mkdir(mode=0o700)
    environment = {'PATH': '/usr/bin:/bin', 'HOME': str(sandbox),
                   'XDG_CACHE_HOME': str(sandbox/'cache'), 'XDG_CONFIG_HOME': str(sandbox/'config'),
                   'LD_LIBRARY_PATH': str(receipt.runtime_root), 'OMP_NUM_THREADS': '4', 'OPENBLAS_NUM_THREADS': '1'}
    command = ['/usr/bin/prlimit', '--core=0', '--as=27917287424', '--',
               str(contained(receipt.runtime_root, receipt.runtime_root/receipt.executable)),
               '--views', str(directory), '--num-views', str(len(prepared.facts)),
               '--pixal3d-weights', 'mv', '--output', str(output),
               '--models', str(contained(receipt.model_repository, receipt.model_repository/receipt.model_snapshot)),
               '--res', '1024', '--seed', str(value.seed), '--gpu', str(receipt.native_device_index),
               '--require-gpu', '--threads', '4']
    started = time.monotonic()
    try:
        process = await asyncio.create_subprocess_exec(*command, cwd=root, env=environment,
                    start_new_session=True, stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except OSError as exc:
        raise SceneError('three_d_worker_unavailable', 'Multiview worker could not start') from exc
    readers = [asyncio.create_task(_bounded_read(process.stdout)), asyncio.create_task(_bounded_read(process.stderr))]
    try:
        _, _, code = await asyncio.wait_for(asyncio.gather(*readers, process.wait()), timeout)
        if code != 0:
            raise SceneError('three_d_generation_failed', 'Multiview worker failed; no Asset was published')
        validate_glb_path(output, root)
    except BaseException as exc:
        await _stop_process(process)
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        if isinstance(exc, TimeoutError):
            raise SceneError('three_d_generation_timeout', 'Multiview worker exceeded its time bound') from exc
        raise
    weights = hashlib.sha256(json.dumps({k: v.model_dump() for k, v in receipt.model_files.items()},
                                       sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return output, GenerationFacts(model_id=receipt.model_id, model_revision=receipt.model_revision,
        weights_sha256=weights, license=receipt.license, runtime_adapter='native.pixal3d-multiview',
        runtime_version=receipt.runtime_revision, seed=value.seed, resolution=value.resolution,
        elapsed_sec=time.monotonic()-started, output_sha256=await asyncio.to_thread(sha256_file, output),
        multiview=MultiviewExecutionFacts(receipt_sha256=receipt_sha, prepared_sha256=prepared.input_manifest_sha256,
                   camera=value.view_camera or GenerationViewCamera(), views=list(prepared.facts)))
