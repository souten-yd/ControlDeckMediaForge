"""Private Pixal adoption and isolated worker orchestration; no ML imports."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .glb import validate_glb_path
from .host.jobs import HostExecution
from .paths import contained
from .scene_generation import GenerationExecutionFacts, GenerationFacts, SceneFromImageRequest
from .scenes import SceneError
from .three_d_runtime_files import RuntimeFile, sha256_file

MODEL_ROLES = {'dino', 'naf', 'ss-flow', 'ss-decoder', 'shape-lr', 'shape-hr',
               'shape-decoder', 'texture-flow', 'texture-decoder'}
PREPARED_FILES = {'rgb_low.npy', 'rgb_high.npy', 'camera.npy', 'samplers.npy',
                  'shape_norm.npy', 'texture_norm.npy', 'framed.png', 'manifest.json'}


class PixalWorkerLaunch(BaseModel):
    """Private process locations/identity; provides no adoption or GPU authority."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    allowed_root: Path
    runtime_root: Path
    worker_entry: str = Field(min_length=1, max_length=256)
    python_launcher: str = Field(min_length=1, max_length=256)
    python_interpreter: Path
    interpreter_file: RuntimeFile
    descriptor_path: Path


class PixalRuntimeReceipt(PixalWorkerLaunch):
    """Operator-owned measurement, separate from a worker descriptor."""
    schema_version: Literal['media-forge.pixal3d-runtime@1'] = 'media-forge.pixal3d-runtime@1'
    engine: Literal['pixal3d']
    runtime_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    runtime_files: dict[str, RuntimeFile] = Field(min_length=1, max_length=65536)
    descriptor_file: RuntimeFile
    model_id: str = Field(min_length=1, max_length=128, pattern=r'^[a-zA-Z0-9_./-]+$')
    model_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    license: str = Field(min_length=1, max_length=1024)
    license_accepted: Literal[True]
    device_id: str = Field(pattern=r'^gpu[0-9]+$')
    native_device_index: int = Field(ge=0, le=31, strict=True)
    evaluated_resolution: Literal[1024]
    measured_peak_vram_bytes: int = Field(gt=0, le=256*1024**3, strict=True)
    measured_runtime_sec: float = Field(gt=0, le=86400)
    measured_preparation_sec: float = Field(gt=0, le=86400)
    evaluated_output_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    backend: Literal['vulkan']
    validation: Literal['passed']

    @model_validator(mode='after')
    def bounded_paths(self) -> PixalRuntimeReceipt:
        for path in (self.allowed_root, self.runtime_root, self.python_interpreter, self.descriptor_path):
            if not path.is_absolute():
                raise ValueError('Pixal roots must be absolute private configuration')
        for name in (self.worker_entry, self.python_launcher, *self.runtime_files):
            if not name or len(name) > 512 or Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('escaping Pixal runtime member')
        launcher = Path(self.python_launcher)
        config = str(launcher.parent.parent / 'pyvenv.cfg')
        if launcher.parent.name != 'bin' or config not in self.runtime_files:
            raise ValueError('Pixal requires its pinned isolated venv')
        if self.worker_entry not in self.runtime_files or self.python_launcher in self.runtime_files:
            raise ValueError('worker must be pinned; interpreter has its own identity')
        return self


@dataclass(frozen=True)
class PreparedPixalInput:
    root: Path
    directory: Path
    manifest_sha256: str
    receipt_sha256: str
    image_sha256: str
    seed: int
    resolution: int
    elapsed_sec: float


def read_json(path: Path, limit: int = 256 * 1024) -> dict[str, Any]:
    with path.open('rb') as stream:
        content = stream.read(limit + 1)
    if not content or len(content) > limit:
        raise ValueError('private Pixal JSON exceeds bound')
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate Pixal JSON field')
            result[key] = value
        return result
    def invalid(value: str) -> Any:
        raise ValueError('non-finite Pixal JSON value')
    def finite_number(text: str) -> float:
        value = float(text)
        if not math.isfinite(value):
            raise ValueError('non-finite Pixal JSON value')
        return value
    value = json.loads(content, object_pairs_hook=unique, parse_constant=invalid, parse_float=finite_number)
    if not isinstance(value, dict):
        raise ValueError('private Pixal JSON must be an object')
    return value


def verify_file(path: Path, identity: RuntimeFile, *, hashes: bool) -> None:
    if not path.is_file() or path.stat().st_size != identity.size_bytes:
        raise ValueError('Pixal file missing or size changed')
    if hashes and sha256_file(path) != identity.sha256:
        raise ValueError('Pixal file digest changed')


def python_launcher(receipt: PixalWorkerLaunch) -> Path:
    # Resolve the directory, but deliberately retain the venv executable name.
    relative = Path(receipt.python_launcher)
    launcher = contained(receipt.runtime_root, receipt.runtime_root / relative.parent) / relative.name
    target = receipt.python_interpreter.resolve(strict=True)
    if launcher.resolve(strict=True) != target or not os.access(launcher, os.X_OK):
        raise ValueError('Pixal interpreter target changed')
    if launcher.parent.parent.resolve() == Path(sys.prefix).resolve():
        raise ValueError('Pixal must not use the core venv')
    config = contained(receipt.runtime_root, launcher.parent.parent / 'pyvenv.cfg')
    isolation = [line.split('=', 1)[1].strip().lower() for line in config.read_text().splitlines()
                 if '=' in line and line.split('=', 1)[0].strip().lower() == 'include-system-site-packages']
    if isolation != ['false']:
        raise ValueError('Pixal venv must exclude system site packages')
    verify_file(target, receipt.interpreter_file, hashes=False)
    return launcher


def verify_pixal_files(receipt: PixalRuntimeReceipt, *, hashes: bool) -> dict[str, Any]:
    contained(receipt.allowed_root, receipt.runtime_root)
    descriptor_path = contained(receipt.allowed_root, receipt.descriptor_path)
    verify_file(descriptor_path, receipt.descriptor_file, hashes=True)
    descriptor = read_json(descriptor_path)
    if set(descriptor) != {'schema_version', 'source_kind', 'native', 'models', 'camera', 'background', 'options'}:
        raise ValueError('invalid Pixal descriptor fields')
    if descriptor['schema_version'] != 'media-forge.pixal-worker@1' or descriptor['source_kind'] != 'checkpoint':
        raise ValueError('adopted Pixal requires checkpoint source kind')
    if any(not isinstance(descriptor[key], dict) for key in ('options', 'models', 'camera', 'background')):
        raise ValueError('invalid Pixal descriptor objects')
    if descriptor['options'].get('resolution') != receipt.evaluated_resolution:
        raise ValueError('Pixal descriptor resolution differs from measurement')
    if set(descriptor['models']) != MODEL_ROLES:
        raise ValueError('Pixal model roles differ')
    launcher = python_launcher(receipt)
    verify_file(launcher.resolve(), receipt.interpreter_file, hashes=hashes)
    for name, identity in receipt.runtime_files.items():
        verify_file(contained(receipt.runtime_root, receipt.runtime_root / name), identity, hashes=hashes)
    records = [descriptor['native'], *descriptor['models'].values(),
               descriptor['camera']['checkpoint'], descriptor['background']['checkpoint']]
    for record in records:
        if not isinstance(record, dict) or set(record) != {'path', 'sha256', 'size_bytes'}:
            raise ValueError('invalid Pixal descriptor file record')
        if not isinstance(record['path'], str) or not Path(record['path']).is_absolute():
            raise ValueError('invalid Pixal descriptor file path')
        identity = RuntimeFile.model_validate({k: record[k] for k in ('sha256', 'size_bytes')})
        verify_file(contained(receipt.allowed_root, Path(record['path'])), identity, hashes=hashes)
    native = contained(receipt.runtime_root, Path(descriptor['native']['path']))
    relative = str(native.relative_to(receipt.runtime_root.resolve()))
    if relative not in receipt.runtime_files or receipt.runtime_files[relative].model_dump() != {
        k: descriptor['native'][k] for k in ('sha256', 'size_bytes')
    } or not os.access(native, os.X_OK):
        raise ValueError('native identity is not covered by adoption')
    for stage in ('camera', 'background'):
        if not isinstance(descriptor[stage]['source'], str) or not Path(descriptor[stage]['source']).is_absolute():
            raise ValueError('invalid Pixal preprocessing source path')
        source = contained(receipt.allowed_root, Path(descriptor[stage]['source']))
        if not source.is_dir():
            raise ValueError('Pixal preprocessing source missing')
    return descriptor


async def checked_thread(function: Any, *args: Any, **kwargs: Any) -> Any:
    """A started hash/read operation must finish before its staging is removed."""
    from .scene_recipe_jobs import _finish_cleanup
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await _finish_cleanup(task)
        raise


async def stop_worker_group(process: asyncio.subprocess.Process) -> None:
    """The wrapper has five seconds to reap its native child before group kill."""
    def send(sig: int) -> None:
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
    send(signal.SIGTERM)
    try:
        await asyncio.wait_for(asyncio.shield(process.wait()), 8)
    except TimeoutError:
        send(signal.SIGKILL)
        await process.wait()
    # Also terminate a child left behind by an unexpectedly exited wrapper.
    send(signal.SIGKILL)
    def live_members() -> bool:
        for stat in Path('/proc').glob('[0-9]*/stat'):
            try:
                fields = stat.read_text().rsplit(')', 1)[1].split()
                if int(fields[2]) == process.pid and fields[0] not in {'Z', 'X'}:
                    return True
            except (OSError, ValueError, IndexError):
                continue
        return False
    # Never return a GPU reservation while an orphan in our group is still live.
    while await asyncio.to_thread(live_members):
        send(signal.SIGKILL)
        await asyncio.sleep(.05)


async def run_worker(receipt: PixalWorkerLaunch, root: Path, mode: str,
                     arguments: list[str], timeout: float) -> None:
    from .scene_recipe_jobs import _finish_cleanup
    from .scene_workspace import _bounded_read

    root = contained(receipt.allowed_root, root)
    user = contained(root, root / (mode + '-user'))
    user.mkdir(mode=0o700)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(user), 'XDG_CACHE_HOME': str(user / 'cache'),
           'XDG_CONFIG_HOME': str(user / 'config'), 'HF_HUB_OFFLINE': '1', 'PYTHONNOUSERSITE': '1'}
    if mode == 'prepare':
        env.update(HIP_VISIBLE_DEVICES='-1', ROCR_VISIBLE_DEVICES='-1', CUDA_VISIBLE_DEVICES='-1')
    command = [str(python_launcher(receipt)), '-E', '-s', '-B', '-u',
        '-X', 'pycache_prefix=' + str(user / 'pycache'),
        str(contained(receipt.runtime_root, receipt.runtime_root / receipt.worker_entry)), mode,
        '--job', str(receipt.descriptor_path), '--allowed-root', str(receipt.allowed_root),
        '--binary-root', str(receipt.runtime_root), *arguments]
    starting = asyncio.create_task(asyncio.create_subprocess_exec(
        *command, cwd=root, env=env, start_new_session=True, stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE))
    async def cleanup(process: asyncio.subprocess.Process, readers: list[asyncio.Task[bytes]]) -> None:
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        async def discard(stream: asyncio.StreamReader | None) -> None:
            if stream is not None:
                while await stream.read(65536):
                    pass
        # A full pipe must not prevent wait()/reaping after an output-bound error
        # or cancellation arriving while process creation is still in progress.
        drains = [asyncio.create_task(discard(process.stdout)), asyncio.create_task(discard(process.stderr))]
        try:
            await stop_worker_group(process)
            await asyncio.gather(*drains)
        finally:
            for drain in drains:
                drain.cancel()
            await asyncio.gather(*drains, return_exceptions=True)
    try:
        process = await asyncio.shield(starting)
    except asyncio.CancelledError:
        async def finish_start() -> None:
            await cleanup(await starting, [])
        await _finish_cleanup(asyncio.create_task(finish_start()))
        raise
    except OSError as exc:
        raise SceneError('three_d_worker_unavailable', 'Pixal worker could not start') from exc
    readers = [asyncio.create_task(_bounded_read(process.stdout)), asyncio.create_task(_bounded_read(process.stderr))]
    try:
        _, _, code = await asyncio.wait_for(asyncio.gather(*readers, process.wait()), timeout)
        if code != 0:
            raise SceneError('three_d_preparation_failed' if mode == 'prepare' else 'three_d_generation_failed',
                             'Pixal worker failed; no asset was published')
    except TimeoutError as exc:
        raise SceneError('three_d_preparation_timeout' if mode == 'prepare' else 'three_d_generation_timeout',
                         'Pixal worker exceeded its time bound') from exc
    except SceneError as exc:
        if exc.code == 'scene_worker_output_bound':
            raise SceneError('three_d_worker_output_bound', 'Pixal worker output exceeded its bound') from exc
        raise
    finally:
        await _finish_cleanup(asyncio.create_task(cleanup(process, readers)))


def receipt_digest(receipt: PixalRuntimeReceipt) -> str:
    return hashlib.sha256(receipt.model_dump_json().encode()).hexdigest()


def verify_prepared(receipt: PixalRuntimeReceipt, value: SceneFromImageRequest, image: Path,
                    root: Path, prepared: PreparedPixalInput) -> dict[str, Any]:
    if (prepared.root != root.resolve() or prepared.directory != root.resolve() / 'pixal-prepared'
            or prepared.receipt_sha256 != receipt_digest(receipt) or prepared.seed != value.seed
            or prepared.resolution != value.resolution or sha256_file(image) != prepared.image_sha256):
        raise ValueError('Pixal preparation belongs to a different request')
    directory = contained(root, prepared.directory)
    ready = contained(directory, directory / 'ready.json')
    if ready.stat().st_size > 256*1024:
        raise ValueError('Pixal prepared manifest exceeds bound')
    if sha256_file(ready) != prepared.manifest_sha256:
        raise ValueError('Pixal prepared manifest changed')
    manifest = read_json(ready)
    if set(manifest) != {'schema_version', 'job_sha256', 'input_image_sha256', 'source_kind', 'seed', 'preprocessing', 'files'}:
        raise ValueError('invalid Pixal prepared manifest fields')
    for key, expected in {'schema_version': 'media-forge.pixal-prepared@1', 'source_kind': 'checkpoint',
        'job_sha256': receipt.descriptor_file.sha256, 'input_image_sha256': prepared.image_sha256, 'seed': value.seed}.items():
        if manifest[key] != expected:
            raise ValueError('Pixal prepared identity differs')
    if type(manifest['seed']) is not int or set(manifest['files']) != PREPARED_FILES:
        raise ValueError('invalid Pixal prepared file table or seed')
    for name, record in manifest['files'].items():
        verify_file(contained(directory, directory / 'inputs' / name), RuntimeFile.model_validate(record), hashes=True)
    preparation = manifest['preprocessing']
    if not isinstance(preparation, dict) or any(not isinstance(preparation.get(k), dict) for k in ('camera', 'background')):
        raise ValueError('invalid Pixal preprocessing facts')
    if set(preparation) != {'camera', 'background'}:
        raise ValueError('invalid Pixal preprocessing facts')
    for stage in ('camera', 'background'):
        facts = preparation[stage]
        if stage == 'camera' or facts.get('provider_used'):
            if facts.get('backend') != 'cpu' or facts.get('precision') != 'float32':
                raise ValueError('Pixal CPU preprocessing facts differ')
    return manifest


async def prepare_pixal(receipt: PixalRuntimeReceipt, value: SceneFromImageRequest,
                        image: Path, root: Path, *, timeout: float) -> PreparedPixalInput:
    started = time.monotonic()
    try:
        if value.resolution != receipt.evaluated_resolution:
            raise ValueError('Pixal preparation resolution was not measured')
        root = contained(receipt.allowed_root, root)
        image = contained(root, image)
        await checked_thread(verify_pixal_files, receipt, hashes=True)
        image_sha = await checked_thread(sha256_file, image)
        directory = root / 'pixal-prepared'
        await run_worker(receipt, root, 'prepare', ['--input', str(image), '--seed', str(value.seed),
            '--output', str(directory)], timeout)
        ready_path = contained(root, directory / 'ready.json')
        await checked_thread(read_json, ready_path)
        manifest_sha = await checked_thread(sha256_file, ready_path)
        prepared = PreparedPixalInput(root, directory, manifest_sha, receipt_digest(receipt),
            image_sha, value.seed, value.resolution, time.monotonic() - started)
        await checked_thread(verify_prepared, receipt, value, image, root, prepared)
        await checked_thread(verify_pixal_files, receipt, hashes=True)
        return prepared
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        if isinstance(exc, SceneError):
            raise
        raise SceneError('three_d_preparation_invalid', 'Pixal preparation or its pinned runtime changed') from exc


async def generate_pixal(receipt: PixalRuntimeReceipt, value: SceneFromImageRequest,
                         image: Path, root: Path, execution: HostExecution,
                         prepared: PreparedPixalInput | None, *, timeout: float) -> tuple[Path, GenerationFacts]:
    if not execution.lease_id or execution.device_id != receipt.device_id:
        raise SceneError('host_lease_required', 'Pixal generation requires its granted GPU lease')
    if value.resolution != receipt.evaluated_resolution:
        raise SceneError('three_d_resolution_not_evaluated', 'Requested resolution has not been measured')
    if prepared is None:
        raise SceneError('three_d_preparation_required', 'Pixal requires completed CPU preparation')
    started = time.monotonic()
    try:
        root = contained(receipt.allowed_root, root)
        image = contained(root, image)
        descriptor = await checked_thread(verify_pixal_files, receipt, hashes=True)
        ready = await checked_thread(verify_prepared, receipt, value, image, root, prepared)
        output = root / 'pixal-generated'
        await run_worker(receipt, root, 'generate', ['--prepared', str(prepared.directory),
            '--prepared-sha256', prepared.manifest_sha256, '--backend', 'vulkan',
            '--device', str(receipt.native_device_index), '--timeout', str(timeout), '--output', str(output)], timeout + 8)
        complete = await checked_thread(read_json, contained(root, output / 'complete.json'))
        if set(complete) != {'schema_version', 'job_sha256', 'prepared_sha256', 'input_image_sha256', 'asset', 'native', 'preprocessing'}:
            raise ValueError('invalid Pixal completion fields')
        for key, expected in {'schema_version': 'media-forge.pixal-complete@1',
            'job_sha256': receipt.descriptor_file.sha256, 'prepared_sha256': prepared.manifest_sha256,
            'input_image_sha256': prepared.image_sha256, 'preprocessing': ready['preprocessing']}.items():
            if complete[key] != expected:
                raise ValueError('Pixal completion identity differs')
        native = complete['native']
        for key, expected in {'source_kind': 'checkpoint', 'backend': 'vulkan', 'precision': 'float32',
            'device_index': receipt.native_device_index, 'seed': value.seed, 'source_sha256': receipt.descriptor_file.sha256,
            'input_sha256': prepared.manifest_sha256, 'actual_resolution': value.resolution,
            'rng_algorithm': 'mt19937-box-muller-f32-v1'}.items():
            if native.get(key) != expected:
                raise ValueError('Pixal native execution facts differ')
        asset = dict(complete['asset'])
        if asset.pop('filename') != 'native/asset.glb':
            raise ValueError('invalid Pixal output filename')
        identity = RuntimeFile.model_validate(asset)
        path = contained(root, output / 'native/asset.glb')
        if identity.size_bytes > 64 * 1024**2 or native.get('glb_bytes') != identity.size_bytes:
            raise ValueError('Pixal output size differs')
        await checked_thread(verify_file, path, identity, hashes=True)
        await checked_thread(validate_glb_path, path, root)
        await checked_thread(verify_prepared, receipt, value, image, root, prepared)
        await checked_thread(verify_pixal_files, receipt, hashes=True)
        weights = {name: {k: record[k] for k in ('sha256', 'size_bytes')}
                   for name, record in descriptor['models'].items()}
        for stage in ('camera', 'background'):
            weights[stage] = {k: descriptor[stage]['checkpoint'][k] for k in ('sha256', 'size_bytes')}
        digest = hashlib.sha256(json.dumps(weights, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return path, GenerationFacts(model_id=receipt.model_id, model_revision=receipt.model_revision,
            weights_sha256=digest, license=receipt.license, runtime_adapter='pixal3d',
            runtime_version=receipt.runtime_revision, seed=value.seed, resolution=value.resolution,
            elapsed_sec=prepared.elapsed_sec + time.monotonic() - started, output_sha256=identity.sha256,
            execution=GenerationExecutionFacts(backend='vulkan', precision='float32',
                descriptor_sha256=receipt.descriptor_file.sha256, prepared_sha256=prepared.manifest_sha256,
                input_image_sha256=prepared.image_sha256, preprocessing_backend='cpu',
                preprocessing_precision='float32', preprocessing_elapsed_sec=prepared.elapsed_sec))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        if isinstance(exc, SceneError):
            raise
        raise SceneError('three_d_generation_invalid', 'Pixal output or its pinned inputs failed verification') from exc
