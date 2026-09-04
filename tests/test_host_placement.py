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
