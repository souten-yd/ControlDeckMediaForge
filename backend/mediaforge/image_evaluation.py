"""Measure a diffusers image model on this machine, so it can be routed.

A model added from the Hub lands as ``experimental``: nobody has run it here,
so nothing is known about what it costs. Routing refuses experimental models,
which is right — picking one would mean guessing its VRAM and then discovering
the answer as an out-of-memory in the middle of someone's work.

The way out is to actually run it once. This does the same thing that was done
by hand to promote SSD-1B: load the model through the ordinary image worker,
generate one small picture, watch the device while it happens, and write down
what was observed. After that the numbers are measurements rather than
estimates, and routing can use them.

Deliberately not a smoke test that records a result and leaves the model
unusable. The point is the promotion; a run that does not change what the model
is allowed to do would not be worth its own GPU turn.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ModelDescriptor

# そのモデル本来の設定で回す。小さく短く済ませると測るのは速いが、測った値が
# 実使用と違うものになる。実測: SDXL を 512x512 / 8 歩で測ると 8.45GB / 6.07 秒
# と記録され、その数字で routing が VRAM を確保する。本来の 1024x1024 / 30 歩で
# 回すと実際にはもっと要るので、確保が足りない。
#
# 絵そのものも別物になる。同じ SDXL が 512x512 / 8 歩では指示した被写体を
# 描かず、1024x1024 / 30 歩では描く。前者で「通った」と記録すると、動かない
# 設定を動くものとして登録することになる。
EVALUATION_SEED = 7
# そのモデルが寸法も歩数も名乗らなかったときだけ使う。
FALLBACK_WIDTH = 1024
FALLBACK_HEIGHT = 1024
FALLBACK_STEPS = 30
EVALUATION_PROMPT = "a small blue robot on a wooden desk, soft light"
# 実測より上振れする分の余裕。FLUX の catalog と同じ値を使う。
HEADROOM_BYTES = 1024 * 1024 * 1024


class ImageEvaluationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ImageMeasurement:
    """What one real run cost, in the terms the catalog records."""

    execution_peak_vram_bytes: int
    cold_load_peak_vram_bytes: int
    measured_runtime_sec: float
    width: int
    height: int
    output_bytes: int

    def catalog_measurements(self) -> dict[str, Any]:
        return {
            "resident_vram_bytes": 0,
            "execution_peak_vram_bytes": self.execution_peak_vram_bytes,
            "cold_load_peak_vram_bytes": self.cold_load_peak_vram_bytes,
            "headroom_vram_bytes": HEADROOM_BYTES,
            "measured_runtime_sec": round(self.measured_runtime_sec, 2),
        }


def device_used_bytes() -> int:
    """Read the device, never a model's own accounting.

    Returns -1 when the device cannot be read, which the caller must treat as
    "unknown" rather than as zero: recording a peak of 0 would promote a model
    as costing nothing.
    """
    try:
        output = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"], capture_output=True, text=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return -1
    for line in output.splitlines():
        if "GPU[0]" in line and "Total Used Memory" in line:
            try:
                return int(line.split(":")[-1].strip())
            except ValueError:
                return -1
    return -1


class DeviceSampler:
    """Sample the device on its own thread while the worker runs.

    Sampling only at the start and the end reads the idle baseline: the model
    is loaded and freed inside the worker, so the interesting numbers exist
    only while it is running.
    """

    def __init__(self, interval_sec: float = 0.25):
        self.interval_sec = interval_sec
        self.samples: list[int] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            value = device_used_bytes()
            if value >= 0:
                self.samples.append(value)
            self._stop.wait(self.interval_sec)

    def __enter__(self) -> "DeviceSampler":
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def peak(self) -> int:
        """カード全体の使用量の最大。診断用で、必要量の申告には使わない。"""
        return max(self.samples) if self.samples else -1

    def increment(self, baseline: int) -> int:
        """測り始めからの増分。これが worker の要る量である。

        絶対値を申告すると、測ったときに同時に載っていた LLM のぶんまで
        「このモデルに要る量」として記録される。実際それで FLUX.2 Klein 4B
        （重み 15GB）に 30.1GB が記録され、32GB のカードに載らないモデルとして
        扱われていた。同じファイルの GpuMemoryMonitor は増分を持っている。
        """
        top = self.peak()
        if top < 0 or baseline < 0:
            return -1
        return max(0, top - baseline)


def worker_payload(model: ModelDescriptor, output_dir: Path) -> dict[str, Any]:
    """The same envelope an ordinary generation sends.

    Evaluating through a different path would measure that path instead of the
    one real work uses.
    """
    assert model.local_path is not None
    runtime_options: dict[str, Any] = {
        "device_mode": model.device_mode,
        "disable_mmap": model.disable_mmap,
    }
    if model.negative_prompt:
        runtime_options["negative_prompt"] = model.negative_prompt
    if model.guidance_scale is not None:
        runtime_options["guidance_scale"] = model.guidance_scale
    return {
        "model": {
            "id": model.model_id,
            "path": str(model.local_path),
            "version": model.version,
            "weights_hash": model.weights_hash,
            "license": model.license,
            "runtime_adapter": model.runtime_adapter,
            "runtime_options": runtime_options,
        },
        "request": {
            "operation": "image.generate",
            "intent": EVALUATION_PROMPT,
            "constraints": {
                "width": model.native_width or FALLBACK_WIDTH,
                "height": model.native_height or FALLBACK_HEIGHT,
                "steps": model.default_steps or FALLBACK_STEPS,
                "seed": EVALUATION_SEED,
            },
            "output": {"format": "png", "count": 1},
        },
        "worker_output_dir": str(output_dir),
    }


async def measure_image_model(
    model: ModelDescriptor,
    *,
    runtime_python: Path,
    work_root: Path,
    repository_root: Path,
    timeout_sec: float = 1800.0,
) -> ImageMeasurement:
    """Run the model once and report what it cost."""
    if not model.runtime_adapter.startswith("diffusers."):
        raise ImageEvaluationError(
            "model_evaluation_unsupported",
            f"{model.runtime_adapter} は画像ワーカーの経路ではありません",
        )
    if not model.installed or model.local_path is None:
        raise ImageEvaluationError("model_not_found", "評価の前に導入されている必要があります")
    if not runtime_python.is_file():
        raise ImageEvaluationError("model_runtime_unavailable", "画像ランタイムが導入されていません")

    output_dir = work_root / f"evaluate_{model.model_id.replace('/', '_')[:80]}"
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", str(work_root)),
        "PYTHONPATH": str(repository_root),
        "MEDIA_FORGE_MODEL_ROOT": str(model.local_path.parents[1]),
        "MEDIA_FORGE_WORK_ROOT": str(work_root.resolve()),
    }
    payload = json.dumps(worker_payload(model, output_dir)).encode("utf-8") + b"\n"

    baseline = device_used_bytes()
    started = time.perf_counter()
    with DeviceSampler() as sampler:
        process = await asyncio.create_subprocess_exec(
            str(runtime_python), "-m", "worker_packs.image.worker",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(payload), timeout=timeout_sec
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise ImageEvaluationError(
                "model_evaluation_timeout", "評価が時間内に終わりませんでした"
            ) from None
    elapsed = time.perf_counter() - started

    if process.returncode != 0:
        detail = (stderr or b"").decode("utf-8", errors="replace")[-300:]
        raise ImageEvaluationError("model_evaluation_failed", detail or "画像ワーカーが失敗しました")
    try:
        envelope = json.loads((stdout or b"").decode("utf-8", errors="replace").splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise ImageEvaluationError(
            "model_evaluation_invalid_output", "ワーカーの応答を読み取れませんでした"
        ) from exc
    # ワーカーは {"ok": ..., "result"|"error": ...} で包む。exit code 0 でも
    # 中で失敗していることがあるので、包みの中を見る。
    if envelope.get("ok") is not True:
        error = envelope.get("error") or {}
        raise ImageEvaluationError(
            str(error.get("code") or "model_evaluation_failed"),
            str(error.get("message") or "画像ワーカーが失敗しました")[:300],
        )
    result = envelope.get("result") or {}
    outputs = result.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ImageEvaluationError("model_evaluation_invalid_output", "画像が返りませんでした")
    produced = Path(str(outputs[0].get("path") or ""))
    if not produced.is_file():
        raise ImageEvaluationError("model_evaluation_invalid_output", "返された画像が見つかりません")

    # 確保した本人の申告を優先する。外から見た増分は、測っている間に他の
    # process が伸びた分まで拾ってしまう。申告が無いときだけ増分に落とす。
    metrics = result.get("runtime_metrics") or {}
    reported = metrics.get("peak_vram_bytes")
    peak = (
        int(reported)
        if isinstance(reported, int) and not isinstance(reported, bool) and reported > 0
        else sampler.increment(baseline)
    )
    if peak < 0 or baseline < 0:
        # 読めなかったものを 0 として記録すると、「何も使わないモデル」として
        # routing に採用される。測れなかったなら昇格させない。
        raise ImageEvaluationError(
            "model_evaluation_unmeasured", "実行中の VRAM を読み取れませんでした"
        )
    return ImageMeasurement(
        execution_peak_vram_bytes=peak,
        # 読み込みと生成を 1 本の run で見ているので、両方の上限は同じ観測になる。
        # 別々に測るには worker を 2 度走らせることになり、確かめるためだけに
        # GPU を倍使う。同じ値を入れて、それが同じ観測だと分かるようにする。
        cold_load_peak_vram_bytes=peak,
        measured_runtime_sec=elapsed,
        width=int(outputs[0].get("width") or model.native_width or FALLBACK_WIDTH),
        height=int(outputs[0].get("height") or model.native_height or FALLBACK_HEIGHT),
        output_bytes=produced.stat().st_size,
    )
