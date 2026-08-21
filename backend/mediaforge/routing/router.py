from __future__ import annotations

from dataclasses import replace

from mediaforge.models import ModelDescriptor, ModelState


class ModelRouteError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def route_model(
    models: tuple[ModelDescriptor, ...],
    *,
    capability: str,
    policy: str,
    hardware_backend: str,
    free_vram_bytes: int,
    model_id: str | None = None,
) -> ModelDescriptor:
    if free_vram_bytes < 0:
        raise ValueError("free_vram_bytes must not be negative")
    candidates = [
        item for item in models
        if capability in item.capabilities
        and hardware_backend in item.hardware_backends
        and item.installed
        and item.local_path is not None
    ]
    if policy == "manual":
        if model_id is None:
            raise ModelRouteError("manual_model_required", "manual routing requires a model ID")
        candidates = [
            item for item in candidates
            if item.model_id == model_id
            and item.state == ModelState.AVAILABLE
            and item.healthy
            and item.measured_vram_bytes is not None
            and item.measured_vram_bytes <= free_vram_bytes
        ]
        if not candidates:
            raise ModelRouteError("model_unavailable", "the requested local model is unavailable")
        selected = candidates[0]
    else:
        if policy not in {"auto", "fast", "balanced", "quality", "low_vram"}:
            raise ModelRouteError("invalid_model_policy", "the model policy is unsupported")
        candidates = [item for item in candidates if item.state == ModelState.AVAILABLE and item.healthy]
        candidates = [
            item for item in candidates
            if item.measured_vram_bytes is not None and item.measured_vram_bytes <= free_vram_bytes
        ]
        if not candidates:
            raise ModelRouteError("capability_unavailable", "no measured local model satisfies the capability")
        candidates.sort(key=lambda item: (item.policy_rank.get(policy, 1_000_000), item.model_id))
        selected = candidates[0]
    return replace(selected)
