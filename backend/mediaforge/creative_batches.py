from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .creative import CreativeCompiler, CreativeSpec, CreativeValidationError
from .creative_intelligence import ActionStateSpec, PromptPlan, action_state_to_pose_details
from .domain import Job, JobRequest


class CreativeBatchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^batch_[0-9a-f]{32}$")
    axis: str
    requested_count: int = Field(ge=2, le=8)
    child_plans: list[dict[str, Any]]
    child_job_ids: list[str] = Field(default_factory=list)
    submission_errors: list[dict[str, str]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CreativeBatchPlanner:
    AXES = {"pose", "scene", "composition"}

    def __init__(self, compiler: CreativeCompiler):
        self.compiler = compiler

    def plan(
        self,
        request: JobRequest,
        creative: CreativeSpec,
        count: int,
        *,
        capabilities: Mapping[str, Mapping[str, Any]],
        envelope: Mapping[str, Any],
        available_reference_ids: set[str] | None = None,
        batch_id: str | None = None,
    ) -> tuple[str, list[JobRequest], list[dict[str, Any]]]:
        axis = creative.variation.axis
        if axis not in self.AXES:
            raise CreativeValidationError(
                "creative_batch_axis_invalid",
                "複数差分はポーズ、シーン、構図のいずれかを選んでください。",
                field="variation",
            )
        if not isinstance(count, int) or isinstance(count, bool) or not 2 <= count <= 8:
            raise CreativeValidationError(
                "creative_batch_count_invalid", "差分は2〜8枚で指定してください。", field="count"
            )
        identifiers = self._candidate_ids(axis, creative)
        if len(identifiers) < count:
            raise CreativeValidationError(
                "creative_batch_variants_unavailable",
                f"選んだ条件では {count} 種類の差分を作れません。",
                field="variation",
            )
        identifier = batch_id or f"batch_{uuid.uuid4().hex}"
        seed = self._base_seed(request, creative)
        requests: list[JobRequest] = []
        plans: list[dict[str, Any]] = []
        for index, variant_id in enumerate(identifiers[:count]):
            child = creative.model_copy(deep=True)
            if axis == "pose":
                child.pose = child.pose.model_copy(update={"preset": variant_id, "details": ""})
            elif axis == "scene":
                child.scene = child.scene.model_copy(update={"preset": variant_id, "details": ""})
            else:
                child.composition = child.composition.model_copy(update={"preset": variant_id, "details": ""})
            compiled = self.compiler.compile(
                request.model_copy(update={"output": request.output.model_copy(update={"count": 1})}),
                child,
                capabilities=capabilities,
                envelope=envelope,
                available_reference_ids=available_reference_ids,
            )
            plan = compiled.plan
            plan["batch"] = {
                "id": identifier, "axis": axis, "index": index, "total": count, "seed": seed + index,
            }
            value = compiled.request.model_dump(mode="json")
            value["constraints"] = {
                **value["constraints"], "seed": seed + index, "creative_plan": plan,
            }
            value["output"]["count"] = 1
            requests.append(JobRequest.model_validate(value))
            plans.append(plan)
        return identifier, requests, plans

    def plan_action_variations(
        self,
        request: JobRequest,
        creative: CreativeSpec,
        actions: list[ActionStateSpec],
        director_plan: PromptPlan,
        *,
        reference_context: list[dict[str, Any]] | None = None,
        capabilities: Mapping[str, Mapping[str, Any]],
        envelope: Mapping[str, Any],
        available_reference_ids: set[str] | None = None,
        batch_id: str | None = None,
    ) -> tuple[str, list[JobRequest], list[dict[str, Any]]]:
        if not 2 <= len(actions) <= 4:
            raise CreativeValidationError(
                "creative_batch_count_invalid", "演出による動きの差分は2〜4枚です。", field="count"
            )
        identifier = batch_id or f"batch_{uuid.uuid4().hex}"
        seed = self._base_seed(request, creative)
        requests: list[JobRequest] = []
        plans: list[dict[str, Any]] = []
        for index, action in enumerate(actions):
            details = action_state_to_pose_details(action)
            if not details:
                raise CreativeValidationError(
                    "creative_batch_variants_unavailable",
                    "動きの差分に使える内容がありません。",
                    field="variation",
                )
            child = creative.model_copy(deep=True)
            child.pose = child.pose.model_copy(update={"preset": "custom", "details": details})
            compiled = self.compiler.compile(
                request.model_copy(update={"output": request.output.model_copy(update={"count": 1})}),
                child,
                capabilities=capabilities,
                envelope=envelope,
                available_reference_ids=available_reference_ids,
            )
            plan = compiled.plan
            plan["director"] = {
                **director_plan.model_dump(mode="json"),
                "child_action_state": action.model_dump(mode="json"),
                "source": "control-deck:text.generate",
                "reference_context": reference_context or [],
            }
            plan["batch"] = {
                "id": identifier,
                "axis": "pose",
                "index": index,
                "total": len(actions),
                "seed": seed + index,
            }
            value = compiled.request.model_dump(mode="json")
            value["constraints"] = {
                **value["constraints"], "seed": seed + index, "creative_plan": plan,
            }
            value["output"]["count"] = 1
            requests.append(JobRequest.model_validate(value))
            plans.append(plan)
        return identifier, requests, plans

    def _candidate_ids(self, axis: str, creative: CreativeSpec) -> list[str]:
        catalog = self.compiler.catalog.entries
        if axis == "pose":
            compatible = catalog["scenes"][creative.scene.preset]["compatible_poses"]
            values = [item for item in compatible if item not in {"auto", "custom"}]
            current = creative.pose.preset
        elif axis == "scene":
            values = [
                item for item, entry in catalog["scenes"].items()
                if item != "auto" and creative.pose.preset in entry["compatible_poses"]
            ]
            current = creative.scene.preset
        else:
            values = [item for item in catalog["compositions"] if item != "auto"]
            current = creative.composition.preset
        return ([current] if current in values else []) + [item for item in values if item != current]

    @staticmethod
    def _base_seed(request: JobRequest, creative: CreativeSpec) -> int:
        requested = request.constraints.get("seed")
        if isinstance(requested, int) and not isinstance(requested, bool) and requested >= 0:
            return requested
        canonical = json.dumps(
            {"request": request.model_dump(mode="json"), "creative": creative.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return int.from_bytes(hashlib.sha256(canonical).digest()[:4], "big")


def project_batch(record: CreativeBatchRecord, jobs: list[Job]) -> dict[str, Any]:
    statuses = [job.status.value for job in jobs]
    succeeded = sum(value == "succeeded" for value in statuses)
    failed = sum(value == "failed" for value in statuses) + len(record.submission_errors)
    canceled = sum(value == "canceled" for value in statuses)
    active = sum(value in {"queued", "running"} for value in statuses)
    completed = succeeded + failed + canceled
    if active:
        state = "running"
    elif succeeded == record.requested_count:
        state = "succeeded"
    elif succeeded:
        state = "partial"
    elif canceled and not failed:
        state = "canceled"
    else:
        state = "failed"
    return {
        **record.model_dump(mode="json"),
        "state": state,
        "completed_count": completed,
        "succeeded_count": succeeded,
        "failed_count": failed,
        "canceled_count": canceled,
        "progress": completed / record.requested_count,
        "asset_ids": [asset_id for job in jobs for asset_id in job.asset_ids],
        "children": [job.model_dump(mode="json") for job in jobs],
    }
