from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..models import ModelDescriptor
from ..models.adapters import runs_on_cpu


MIB = 1024 * 1024

GPU_DEVICE = "gpu0"
HOST_DEVICE = "host"
# 順序が意味を持つ。「空いていれば VRAM、無ければ RAM」である
# （docs/design-ai-resource-broker.md §0）。host は opt-in で、挙げなければ
# 従来どおり VRAM だけが候補になる。
COEXISTING_PLACEMENT = [GPU_DEVICE, HOST_DEVICE]


@dataclass(frozen=True)
class LeaseEstimate:
    resident_bytes: int
    execution_peak_bytes: int
    cold_load_peak_bytes: int
    headroom_bytes: int
    estimated_runtime_sec: float

    def __post_init__(self) -> None:
        values = (
            self.resident_bytes,
            self.execution_peak_bytes,
            self.cold_load_peak_bytes,
            self.headroom_bytes,
        )
        if any(value < 0 for value in values) or self.estimated_runtime_sec <= 0:
            raise ValueError("lease estimates must be non-negative and runtime must be positive")


def fake_image_request(
    job_id: str,
    *,
    runtime_sec: float,
    workload_class: str = "interactive",
    vram_bytes: int = 256 * MIB,
) -> dict[str, Any]:
    """Build the Add-on Runtime request; ControlDeck forces the owner identity."""
    estimate = LeaseEstimate(
        resident_bytes=0,
        execution_peak_bytes=vram_bytes,
        cold_load_peak_bytes=vram_bytes,
        headroom_bytes=64 * MIB,
        estimated_runtime_sec=max(0.001, runtime_sec),
    )
    return {
        "job_id": job_id,
        "device": "auto",
        "preferred_devices": list(COEXISTING_PLACEMENT),
        "vram": {
            "resident_bytes": estimate.resident_bytes,
            "execution_peak_bytes": estimate.execution_peak_bytes,
            "cold_load_peak_bytes": estimate.cold_load_peak_bytes,
            "headroom_bytes": estimate.headroom_bytes,
            "confidence": "low",
        },
        "compute_mode": "shared-safe",
        "priority": {"interactive": 20, "agent-interactive": 20, "workflow": 10}.get(workload_class, 0),
        "class": workload_class,
        "residency_key": "mediaforge:fake-image-v1",
        "estimated_runtime_sec": estimate.estimated_runtime_sec,
        "max_wait_sec": 300,
        "on_insufficient": "queue",
    }


def image_model_request(
    job_id: str,
    model: ModelDescriptor,
    *,
    workload_class: str = "interactive",
    estimated_runtime_sec: float | None = None,
) -> dict[str, Any]:
    """Build a measured request without exposing model selection publicly.

    `estimated_runtime_sec` は、その要求の見積りが分かっているときだけ渡す。
    分かるのは費用が入力の面積に比例する直しの場合で、そこでは 1 枚ぶんの実測を
    渡すと broker に申告する占有時間が実際の数分の一になる。
    """
    values = (
        model.resident_vram_bytes,
        model.execution_peak_vram_bytes,
        model.cold_load_peak_vram_bytes,
        model.headroom_vram_bytes,
        model.measured_runtime_sec,
    )
    if any(value is None for value in values):
        raise ValueError("real image model requires complete measurements")
    estimate = LeaseEstimate(
        resident_bytes=int(model.resident_vram_bytes or 0),
        execution_peak_bytes=int(model.execution_peak_vram_bytes or 0),
        cold_load_peak_bytes=int(model.cold_load_peak_vram_bytes or 0),
        headroom_bytes=int(model.headroom_vram_bytes or 0),
        estimated_runtime_sec=(
            float(model.measured_runtime_sec or 0)
            if estimated_runtime_sec is None
            else max(float(estimated_runtime_sec), 0.0)
        ),
    )
    # CPU で走らせられる系統だけが host を候補にしてよい。VRAM を確保しない
    # ことが host 配置の条件で、守れない adapter が要求すると LLM の側から
    # 見えないまま VRAM を取ることになる。
    offers_ram = runs_on_cpu(model.runtime_adapter)
    return {
        "job_id": job_id,
        "device": "auto",
        "preferred_devices": list(COEXISTING_PLACEMENT) if offers_ram else [],
        # RAM に載せたときに要る量。vram の見積りは device_map で段階的に載せる
        # ときの GPU 側ピークで、RAM 配置の実態とは別物である。実測: FLUX.2
        # Klein 4B は vram 31.1GB の申告に対し CPU 実行の RSS が 18.8GB
        # （1024x1024/4歩）。VRAM の数字を RAM に当てると、30GB の機械では
        # host が永久に grant されない。測っていないモデルには送らない。
        **({"host_bytes": int(model.host_resident_bytes) + estimate.headroom_bytes}
           if offers_ram and model.host_resident_bytes else {}),
        "vram": {
            "resident_bytes": estimate.resident_bytes,
            "execution_peak_bytes": estimate.execution_peak_bytes,
            "cold_load_peak_bytes": estimate.cold_load_peak_bytes,
            "headroom_bytes": estimate.headroom_bytes,
            "confidence": model.measurement_confidence,
        },
        # LLM と場所を分け合う。exclusive だと、LLM が載っている間は VRAM の
        # 空きに関係なく断られ、共存にならない。
        "compute_mode": "shared-safe",
        "priority": {"interactive": 20, "agent-interactive": 20, "workflow": 10}.get(workload_class, 0),
        "class": workload_class,
        "residency_key": f"mediaforge:{model.model_id}:{model.revision}",
        "estimated_runtime_sec": estimate.estimated_runtime_sec,
        "max_wait_sec": 300,
        "on_insufficient": "queue",
    }


class ResourceLeaseBridge(Protocol):
    async def request_resource(self, request: dict[str, Any]) -> dict[str, Any]: ...
    async def resource_status(self, request_id: str) -> dict[str, Any]: ...
    async def cancel_resource(self, request_id: str) -> dict[str, Any]: ...
    async def activate(self, lease_id: str) -> dict[str, Any]: ...
    async def renew(self, lease_id: str) -> dict[str, Any]: ...
    async def release(self, lease_id: str) -> dict[str, Any]: ...
