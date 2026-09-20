"""Pinned native image-to-3D runtime; no ML libraries are loaded into core."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .glb import validate_glb_path
from .host.jobs import HostExecution
from .paths import contained
from .pixal_runtime import (PixalRuntimeReceipt, PreparedPixalInput, generate_pixal,
                            prepare_pixal, read_json, verify_pixal_files)
from .scene_generation import GenerationFacts, SceneFromImageRequest
from .scenes import SceneError
from .three_d_runtime_files import RuntimeFile, sha256_file

MODEL_FILES = frozenset({
    'dinov3.gguf', 'birefnet.gguf', 'ss_flow.gguf', 'ss_dec.gguf',
    'shape_flow_512.gguf', 'shape_flow_1024.gguf', 'shape_dec.gguf',
    'tex_flow_512.gguf', 'tex_flow_1024.gguf', 'tex_dec.gguf',
})


class ThreeDRuntimeReceipt(BaseModel):
    """Private operator receipt written only after adoption measurement."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    schema_version: Literal['media-forge.image-to-3d-runtime@1'] = 'media-forge.image-to-3d-runtime@1'
    engine: Literal['trellis_cpp']
    runtime_root: Path
    executable: str = Field(min_length=1, max_length=256)
    runtime_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    runtime_files: dict[str, RuntimeFile] = Field(min_length=1, max_length=64)
    model_repository: Path
    model_snapshot: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=128, pattern=r'^[a-zA-Z0-9_./-]+$')
    model_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    model_files: dict[str, RuntimeFile] = Field(min_length=1, max_length=64)
    license: str = Field(min_length=1, max_length=256)
    license_accepted: Literal[True]
    device_id: str = Field(pattern=r'^gpu[0-9]+$')
    native_device_index: int = Field(ge=0, le=31, strict=True)
    evaluated_resolution: Literal[512, 1024]
    # 採用は解像度ごとに測る。1 つしか持てないと、上の解像度へ上げた瞬間に下が
    # 選べなくなる。密な入力は上の解像度でホスト RAM を使い切るので、逃げ道を
    # 残せないと「選べるのに必ず落ちる」入力ができてしまう。
    # 省略時は evaluated_resolution 1 つだけを測ったものとして読む（既存 receipt 互換）。
    evaluated_resolutions: list[Literal[512, 1024]] | None = Field(default=None, min_length=1, max_length=2)
    measured_runtime_by_resolution: dict[str, float] | None = None
    measured_peak_vram_bytes: int = Field(gt=0, le=256*1024**3, strict=True)
    measured_runtime_sec: float = Field(gt=0, le=86400)
    evaluated_output_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    validation: Literal['passed']

    @model_validator(mode='after')
    def bounded_paths(self) -> ThreeDRuntimeReceipt:
        if not self.runtime_root.is_absolute() or not self.model_repository.is_absolute():
            raise ValueError('runtime roots must be absolute server configuration')
        for name in [self.executable, self.model_snapshot, *self.runtime_files, *self.model_files]:
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('runtime receipt contains an escaping relative path')
        if self.executable not in self.runtime_files or set(self.model_files) != MODEL_FILES:
            raise ValueError('runtime receipt does not cover executable and required models')
        declared = self.evaluated_resolutions
        if declared is not None and (
            self.evaluated_resolution not in declared or len(set(declared)) != len(declared)
        ):
            raise ValueError('runtime receipt default resolution is not among its measured ones')
        measured = self.measured_resolutions()
        timings = self.measured_runtime_by_resolution or {}
        if timings and (set(timings) != {str(value) for value in measured}
                        or any(not 0 < seconds <= 86400 for seconds in timings.values())):
            raise ValueError('runtime receipt timings do not cover its measured resolutions')
        return self

    def measured_resolutions(self) -> list[int]:
        """Every resolution this adoption measured, the default first.

        宣言した集合が正で、既定はその中に無ければならない（上の検証）。ここで
        既定を足してはいけない。足すと、どんな宣言でも既定が入ってしまい、
        検証が素通りする。
        """
        declared = self.evaluated_resolutions
        if declared is None:
            return [self.evaluated_resolution]
        return [self.evaluated_resolution,
                *(value for value in declared if value != self.evaluated_resolution)]

    def runtime_sec(self, resolution: int) -> float:
        return (self.measured_runtime_by_resolution or {}).get(str(resolution), self.measured_runtime_sec)


RuntimeReceipt = ThreeDRuntimeReceipt | PixalRuntimeReceipt


def measured_resolutions(receipt: RuntimeReceipt) -> list[int]:
    """Both adapters answer the same question; only trellis.cpp measures more than one."""
    if isinstance(receipt, ThreeDRuntimeReceipt):
        return receipt.measured_resolutions()
    return [receipt.evaluated_resolution]


def runtime_by_resolution(receipt: RuntimeReceipt) -> dict[str, float]:
    return {str(value): receipt.runtime_sec(value) if isinstance(receipt, ThreeDRuntimeReceipt)
            else receipt.measured_runtime_sec for value in measured_resolutions(receipt)}


class ThreeDGenerator:
    def __init__(self, receipt_path: Path, *, pixal_receipt_path: Path | None = None,
                 timeout_sec: float = 1800, preparation_timeout_sec: float = 900) -> None:
        self.receipt_path = receipt_path
        self.pixal_receipt_path = pixal_receipt_path or receipt_path.with_name('pixal3d-runtime.json')
        self.timeout_sec = timeout_sec
        self.preparation_timeout_sec = preparation_timeout_sec

    def resolve(self, engine: str = 'auto', resolution: int | None = None) -> RuntimeReceipt:
        if engine not in {'auto', 'trellis_cpp', 'pixal3d'}:
            raise SceneError('three_d_runtime_not_adopted', 'Requested 3D engine has not been adopted')
        if engine == 'auto':
            engine = 'trellis_cpp' if self.receipt_path.exists() or self.receipt_path.is_symlink() else 'pixal3d'
        path = self.pixal_receipt_path if engine == 'pixal3d' else self.receipt_path
        try:
            if path.is_symlink():
                raise ValueError('invalid runtime receipt')
            receipt: RuntimeReceipt
            if engine == 'pixal3d':
                receipt = PixalRuntimeReceipt.model_validate(read_json(path, 16*1024**2))
            else:
                receipt = ThreeDRuntimeReceipt.model_validate(read_json(path, 128*1024))
            if resolution is not None and resolution not in measured_resolutions(receipt):
                raise SceneError('three_d_resolution_not_evaluated', 'Requested resolution has not been measured')
            self.verify_files(receipt, hashes=False)
            return receipt
        except (OSError, ValueError, ValidationError, KeyError, TypeError, AttributeError) as exc:
            if isinstance(exc, SceneError):
                raise
            raise SceneError('three_d_runtime_unavailable', 'Verified 3D runtime is unavailable') from exc

    def resolve_stages(self, engine: str = 'auto', resolution: int | None = None,
                       refine_with_pixal3d: bool = False) -> list[RuntimeReceipt]:
        """The pinned chain for one request, in the order it will run.

        既定は 1 段（trellis.cpp）。`refine_with_pixal3d` のときだけ Pixal3D を
        後ろへ足す。すでに Pixal3D を名指ししている場合は段を増やさない。
        足す段が採用されていなければ、黙って 1 段へ落とさずに理由を返す。
        """
        primary = self.resolve(engine, resolution)
        if not refine_with_pixal3d or primary.engine == 'pixal3d':
            return [primary]
        # 追加の段は自分が測られた解像度で走る。1 段目の解像度を押し付けると、
        # 512 で採用した trellis.cpp と 1024 で採用した Pixal3D が噛み合わず、
        # 画面では選べるのに受付で必ず落ちる組み合わせになる。
        return [primary, self.resolve('pixal3d')]

    @staticmethod
    def verify_files(receipt: RuntimeReceipt, *, hashes: bool) -> None:
        if isinstance(receipt, PixalRuntimeReceipt):
            verify_pixal_files(receipt, hashes=hashes)
            return
        snapshot = contained(receipt.model_repository, receipt.model_repository / receipt.model_snapshot)
        if snapshot.name != receipt.model_revision:
            raise ValueError('model snapshot does not match its pinned revision')
        paths = [(contained(receipt.runtime_root, receipt.runtime_root / name), item)
                 for name, item in receipt.runtime_files.items()]
        paths += [(contained(receipt.model_repository, snapshot / name), item)
                  for name, item in receipt.model_files.items()]
        for path, item in paths:
            if not path.is_file() or path.stat().st_size != item.size_bytes:
                raise ValueError('runtime file missing or size changed')
            if hashes and sha256_file(path) != item.sha256:
                raise ValueError('runtime file digest changed')
        executable = contained(receipt.runtime_root, receipt.runtime_root / receipt.executable)
        if not os.access(executable, os.X_OK):
            raise ValueError('runtime executable is not executable')

    def status(self) -> dict[str, object]:
        engines: dict[str, object] = {}
        for engine in ('trellis_cpp', 'pixal3d'):
            try:
                adopted = self.resolve(engine)
                engines[engine] = {'state':'experimental', 'resolutions':measured_resolutions(adopted),
                                  'estimated_runtime_sec':adopted.measured_runtime_sec,
                                  'estimated_runtime_by_resolution':runtime_by_resolution(adopted)}
            except SceneError as exc:
                engines[engine] = {'state':'unavailable', 'reason':exc.code}
        refine = engines.get('pixal3d', {})
        try:
            receipt = self.resolve()
        except SceneError as exc:
            return {'state':'unavailable', 'reason':exc.code, 'engines':engines, 'refine':refine}
        return {'state':'experimental', 'implementation':receipt.engine, 'engines':engines,
                'input':'image', 'resolutions':measured_resolutions(receipt),
                'estimated_runtime_by_resolution':runtime_by_resolution(receipt),
                # 画面のチェックボックスはここだけを見る。既定の段と、足せる段を分ける。
                'refine':refine, 'refine_engine':'pixal3d',
                'estimated_runtime_sec':receipt.measured_runtime_sec}

    @staticmethod
    def resource_request(receipt: RuntimeReceipt, execution: HostExecution) -> dict[str, object]:
        return {
            'job_id':execution.host_job_id, 'device':'auto', 'preferred_devices':[receipt.device_id],
            'vram':{'resident_bytes':0, 'execution_peak_bytes':receipt.measured_peak_vram_bytes,
                    'cold_load_peak_bytes':receipt.measured_peak_vram_bytes, 'headroom_bytes':512*1024**2,
                    'confidence':'measured'},
            'compute_mode':'shared-safe', 'priority':0, 'class':execution.workload_class,
            'residency_key':f'mediaforge:{"trellis-cpp" if receipt.engine == "trellis_cpp" else "pixal3d"}:{receipt.model_revision}',
            'estimated_runtime_sec':receipt.measured_runtime_sec, 'max_wait_sec':300, 'on_insufficient':'queue',
        }

    async def prepare(
        self, receipt: RuntimeReceipt, value: SceneFromImageRequest, image: Path, root: Path,
    ) -> PreparedPixalInput | None:
        if isinstance(receipt, PixalRuntimeReceipt):
            return await prepare_pixal(receipt, value, image, root, timeout=self.preparation_timeout_sec)
        return None

    async def generate(
        self, receipt: RuntimeReceipt, value: SceneFromImageRequest,
        image: Path, root: Path, execution: HostExecution,
        *, prepared: PreparedPixalInput | None = None,
    ) -> tuple[Path, GenerationFacts]:
        from .scene_workspace import _bounded_read, _stop_process

        if isinstance(receipt, PixalRuntimeReceipt):
            return await generate_pixal(receipt, value, image, root, execution, prepared, timeout=self.timeout_sec)
        if not execution.lease_id or execution.device_id != receipt.device_id:
            raise SceneError('host_lease_required', 'Image-to-3D generation requires its granted GPU lease')
        if value.resolution not in measured_resolutions(receipt):
            raise SceneError('three_d_resolution_not_evaluated', 'Requested resolution has not been measured')
        try:
            await asyncio.to_thread(self.verify_files, receipt, hashes=True)
        except (ValueError, OSError) as exc:
            raise SceneError('three_d_runtime_changed', '3D runtime changed after adoption') from exc
        image = contained(root, image)
        if not image.is_file():
            raise SceneError('scene_generation_input_invalid', 'Staged input image is missing')
        output = contained(root, root / 'generated.glb')
        if output.exists():
            raise SceneError('scene_generation_invalid', 'Generation output already exists')
        executable = contained(receipt.runtime_root, receipt.runtime_root / receipt.executable)
        snapshot = contained(receipt.model_repository, receipt.model_repository / receipt.model_snapshot)
        sandbox = contained(root, root/'native-user')
        sandbox.mkdir(mode=0o700)
        environment = {'PATH':'/usr/bin:/bin', 'HOME':str(sandbox),
                       'XDG_CACHE_HOME':str(sandbox/'cache'), 'XDG_CONFIG_HOME':str(sandbox/'config')}
        command = [str(executable), '--image', str(image), '--output', str(output),
                   '--models', str(snapshot), '--gpu', str(receipt.native_device_index),
                   '--seed', str(value.seed), '--res', str(value.resolution),
                   '--require-gpu', '--webp', 'on']
        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                *command, cwd=root, env=environment, start_new_session=True,
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise SceneError('three_d_worker_unavailable', '3D worker could not start') from exc
        readers = [asyncio.create_task(_bounded_read(process.stdout)), asyncio.create_task(_bounded_read(process.stderr))]
        try:
            _, _, code = await asyncio.wait_for(asyncio.gather(*readers, process.wait()), self.timeout_sec)
            if code != 0:
                raise SceneError('three_d_generation_failed', '3D worker failed; no asset was published')
            validate_glb_path(output, root)
            digest = await asyncio.to_thread(sha256_file, output)
        except BaseException as exc:
            await _stop_process(process)
            for reader in readers:
                reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
            if isinstance(exc, TimeoutError):
                raise SceneError('three_d_generation_timeout', '3D worker exceeded its time bound') from exc
            raise
        weights = hashlib.sha256(json.dumps(
            {name:item.model_dump() for name,item in receipt.model_files.items()},
            sort_keys=True, separators=(',',':'),
        ).encode()).hexdigest()
        return output, GenerationFacts(
            model_id=receipt.model_id, model_revision=receipt.model_revision, weights_sha256=weights,
            license=receipt.license, runtime_adapter='native.trellis-cpp', runtime_version=receipt.runtime_revision,
            seed=value.seed, resolution=value.resolution, elapsed_sec=time.monotonic()-started, output_sha256=digest,
        )
