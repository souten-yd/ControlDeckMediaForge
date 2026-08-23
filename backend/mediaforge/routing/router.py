from __future__ import annotations

from dataclasses import dataclass, replace

from mediaforge.models import ModelDescriptor, ModelState


class ModelRouteError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ModelRoute:
    """The selected model and why it was selected.

    The reason is shown to the user. Routing that cannot explain itself forces
    people to guess, and guessing is what "auto" is supposed to remove.
    """

    model: ModelDescriptor
    policy: str
    capability: str
    domain: str
    domain_matched: bool
    candidate_count: int


def route_model(
    models: tuple[ModelDescriptor, ...],
    *,
    capability: str,
    policy: str,
    hardware_backend: str,
    free_vram_bytes: int,
    model_id: str | None = None,
    domain: str | None = None,
) -> ModelDescriptor:
    return route(
        models,
        capability=capability,
        policy=policy,
        hardware_backend=hardware_backend,
        free_vram_bytes=free_vram_bytes,
        model_id=model_id,
        domain=domain,
    ).model


def route(
    models: tuple[ModelDescriptor, ...],
    *,
    capability: str,
    policy: str,
    hardware_backend: str,
    free_vram_bytes: int,
    model_id: str | None = None,
    domain: str | None = None,
) -> ModelRoute:
    if free_vram_bytes < 0:
        raise ValueError("free_vram_bytes must not be negative")
    # "auto" と未指定は同じ意味。catalog の domains は general を持つので、
    # 指定が無いときの既定は general になる。
    requested_domain = domain if domain and domain != "auto" else "general"
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
        return ModelRoute(
            model=replace(candidates[0]),
            policy=policy,
            capability=capability,
            domain=requested_domain,
            domain_matched=requested_domain in candidates[0].domains,
            candidate_count=1,
        )
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
        # シーン（domain）に合うものを先に絞る。合うものが 1 件も無ければ
        # 全候補へ落とす。fail-soft にしないと、domain を選んだだけで
        # 使えるモデルが消える。
        preferred = [item for item in candidates if requested_domain in item.domains]
        domain_matched = bool(preferred)
        candidates = preferred or candidates
        candidates.sort(key=lambda item: (item.policy_rank.get(policy, 1_000_000), item.model_id))
        return ModelRoute(
            model=replace(candidates[0]),
            policy=policy,
            capability=capability,
            domain=requested_domain,
            domain_matched=domain_matched,
            candidate_count=len(candidates),
        )
