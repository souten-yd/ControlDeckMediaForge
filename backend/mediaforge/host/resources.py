from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..models import ModelDescriptor


MIB = 1024 * 1024


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
        "vram": {
            "resident_bytes": estimate.resident_bytes,
            "execution_peak_bytes": estimate.execution_peak_bytes,
            "cold_load_peak_bytes": estimate.cold_load_peak_bytes,
            "headroom_bytes": estimate.headroom_bytes,
            "confidence": "low",
        },
        "compute_mode": "exclusive-preferred",
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
) -> dict[str, Any]:
    """Build a measured request without exposing model selection publicly."""
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
        estimated_runtime_sec=float(model.measured_runtime_sec or 0),
    )
    return {
        "job_id": job_id,
        "device": "auto",
        "vram": {
            "resident_bytes": estimate.resident_bytes,
            "execution_peak_bytes": estimate.execution_peak_bytes,
            "cold_load_peak_bytes": estimate.cold_load_peak_bytes,
            "headroom_bytes": estimate.headroom_bytes,
            "confidence": "measured",
        },
        "compute_mode": "exclusive-preferred",
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
