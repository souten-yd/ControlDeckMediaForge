"""broker が返した置き場所に従う。

契約は docs/design-ai-resource-broker.md §0「Add-on 側の契約」である。

1. CPU オフロードに対応した Add-on は `preferred_devices: ["gpu0", "host"]` を送る
2. grant の `RequestStatus.device_id` が実際の配置を返す
3. `device_id == "host"` を受け取ったら、VRAM を確保せず RAM で実行する
"""

from __future__ import annotations

from pathlib import Path

from conftest import fake_settings
from mediaforge.host.jobs import HostExecution
from mediaforge.jobs import JobManager
from mediaforge.models import ModelDescriptor, ModelState
from mediaforge.store import Store


def descriptor() -> ModelDescriptor:
    return ModelDescriptor(
        model_id="owner/model",
        family="test",
        version="1",
        revision="a" * 40,
        weights_hash="sha256:" + "b" * 64,
        license="Apache-2.0",
        runtime_adapter="diffusers.flux2-klein",
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm",),
        state=ModelState.AVAILABLE,
        policy_rank={"auto": 1},
        required_files=("config.json",),
        weights=(),
        installed=True,
        healthy=True,
        local_path=Path("/model"),
        device_mode="direct_device_map",
    )


def execution(device_id: str | None) -> HostExecution:
    value = HostExecution(
        identity=None,  # type: ignore[arg-type]
        host_job_id="job_1",
        workload_class="interactive",
        owns_terminal=False,
    )
    value.device_id = device_id
    return value


def test_ram_placement_runs_without_reserving_vram():
    assert JobManager._device_mode(descriptor(), execution("host")) == "cpu"


def test_vram_placement_keeps_the_catalog_route():
    """カタログの device_mode は GPU 前提の値である。gpu0 なら変えない。"""
    assert JobManager._device_mode(descriptor(), execution("gpu0")) == "direct_device_map"


def test_a_job_without_a_lease_keeps_the_catalog_route():
    assert JobManager._device_mode(descriptor(), None) == "direct_device_map"


def test_a_warm_worker_is_not_reused_across_placements(tmp_path: Path):
    """VRAM に載せたままのプロセスを host 配置の job へ渡さない。

    渡すと、broker が「VRAM を取らない」と見なした要求が、前の job の
    pipeline を抱えたまま走る。
    """
    import asyncio
    import os
    import sys

    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    backend_root = str(Path(__file__).parents[1] / "backend")
    environment = dict(os.environ, PYTHONPATH=backend_root)
    module = "mediaforge.workers.fake"

    async def spawn(placement: str) -> int:
        signature = (sys.executable, module, placement, placement)
        process = await manager._reuse_or_spawn_worker(
            signature, Path(sys.executable), module, environment
        )
        return process.pid

    async def scenario() -> tuple[int, int, int]:
        first = await spawn("gpu0")
        again = await spawn("gpu0")
        moved = await spawn("host")
        await manager._retire_warm_worker()
        return first, again, moved

    first, again, moved = asyncio.run(scenario())

    assert first == again
    assert moved != first


def test_the_worker_is_gone_before_the_host_is_asked_for_its_vlm(tmp_path: Path):
    """lease を返す前に worker を終わらせる。

    生成の lease を持ったまま Host に VLM を載せさせると単一 GPU で deadlock
    する。そのため lease は評価の前に返す。ところが worker を残す作りにした
    ぶん（差分の 4 枚で載せ直さないため）、lease を返しただけでは VRAM は
    空かない。broker から見て「空いた」のに物理的には埋まったままになる。
    """
    import inspect

    source = inspect.getsource(JobManager._execute_worker)
    release = source.index("_release_host_resource")
    retire = source.rindex("_retire_warm_worker", 0, release)
    between = source[retire:release]

    # 直前が qa.semantic の条件つき retire であること。
    assert "job.request.qa.semantic" in source[:retire]
    assert "_release_host_resource" not in between


def _granted(device_id: str, granted_bytes: int | None) -> HostExecution:
    value = execution(device_id)
    value.granted_bytes = granted_bytes
    return value


def _measured() -> ModelDescriptor:
    """FLUX.2 Klein 4B の実測値（2026-09-05）。"""
    import dataclasses

    return dataclasses.replace(
        descriptor(),
        resident_vram_bytes=0,
        execution_peak_vram_bytes=22_397_755_392,
        cold_load_peak_vram_bytes=15_965_057_843,
        headroom_vram_bytes=3_650_722_201,
        minimum_vram_bytes=8_589_934_592,
    )


def test_a_full_budget_keeps_the_fast_route():
    """全常駐ぶんを貸してもらえたなら、そのまま VRAM に載せる。"""
    model = _measured()
    full = 22_397_755_392 + 3_650_722_201

    assert JobManager._device_mode(model, _granted("gpu0", full)) == "direct_device_map"


def test_a_partial_budget_switches_to_streaming():
    """残りしか無いなら、重みを RAM に置いて実行するモジュールだけ VRAM へ送る。

    実測（FLUX.2 Klein 4B / 1024²）: 全常駐 2.98秒、枠 8GiB で 6.7秒、
    RAM のみ 113秒。枠を使えないと 113秒側に落ちる。
    """
    model = _measured()

    assert JobManager._device_mode(model, _granted("gpu0", 8_589_934_592)) == "cpu_offload"


def test_ram_placement_still_wins_over_the_budget():
    """host を割り当てられたなら VRAM は取らない。枠の話ではない。"""
    model = _measured()

    assert JobManager._device_mode(model, _granted("host", 8_589_934_592)) == "cpu"


def test_no_budget_keeps_the_catalog_route():
    """枠を返さない Host（旧版）では、従来どおりカタログの値で動く。"""
    model = _measured()

    assert JobManager._device_mode(model, _granted("gpu0", None)) == "direct_device_map"


def test_the_worker_binds_itself_to_the_budget(monkeypatch, tmp_path: Path):
    """枠を渡されたら torch を縛る。縛らないと、はみ出したときに LLM を巻き込む。"""
    import sys
    from types import SimpleNamespace

    from worker_packs.image import worker as image_worker

    calls: list[tuple[float, int]] = []
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: True,
            get_device_properties=lambda _index: SimpleNamespace(total_memory=32 * 1024**3),
            set_per_process_memory_fraction=lambda fraction, index: calls.append((fraction, index)),
        )
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setenv("MEDIA_FORGE_VRAM_BUDGET_BYTES", str(8 * 1024**3))

    assert image_worker._apply_vram_budget() == 8 * 1024**3
    assert calls == [(0.25, 0)]


def test_a_worker_without_a_budget_binds_nothing(monkeypatch):
    """枠が無いときに勝手に縛らない。カード全部を使ってよい場合がある。"""
    from worker_packs.image import worker as image_worker

    monkeypatch.delenv("MEDIA_FORGE_VRAM_BUDGET_BYTES", raising=False)

    assert image_worker._apply_vram_budget() == 0
