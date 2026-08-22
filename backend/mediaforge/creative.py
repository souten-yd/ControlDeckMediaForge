from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import JobRequest


class CreativeValidationError(ValueError):
    def __init__(self, code: str, message: str, *, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.field = field


class SceneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: str = Field(default="auto", min_length=1, max_length=64)
    details: str = Field(default="", max_length=500)


class PoseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: str = Field(default="auto", min_length=1, max_length=64)
    details: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def custom_requires_details(self) -> "PoseSpec":
        if self.preset == "custom" and not self.details.strip():
            raise ValueError("custom pose requires details")
        if self.preset != "custom" and self.details:
            raise ValueError("pose details are accepted only for custom pose")
        return self


class CompositionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: str = Field(default="auto", min_length=1, max_length=64)
    details: str = Field(default="", max_length=500)


class CameraSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: str = Field(default="auto", min_length=1, max_length=64)
    details: str = Field(default="", max_length=500)


class VariationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: str = Field(default="auto", min_length=1, max_length=64)


class ReferenceRole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    role: Literal["identity", "style", "pose", "composition", "content"]
    strength: float = Field(default=1.0, ge=0.0, le=1.0)


class CreativeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = Field(default="auto", min_length=1, max_length=64)
    scene: SceneSpec = Field(default_factory=SceneSpec)
    pose: PoseSpec = Field(default_factory=PoseSpec)
    composition: CompositionSpec = Field(default_factory=CompositionSpec)
    camera: CameraSpec = Field(default_factory=CameraSpec)
    variation: VariationSpec = Field(default_factory=VariationSpec)
    reference_roles: list[ReferenceRole] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def unique_reference_assets(self) -> "CreativeSpec":
        identifiers = [item.asset_id for item in self.reference_roles]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("reference role asset IDs must be unique")
        return self

    @property
    def active(self) -> bool:
        return bool(
            self.domain != "auto"
            or self.scene.preset != "auto"
            or self.scene.details
            or self.pose.preset != "auto"
            or self.composition.preset != "auto"
            or self.composition.details
            or self.camera.preset != "auto"
            or self.camera.details
            or self.variation.axis != "auto"
            or self.reference_roles
        )


class CreativeCompileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: JobRequest
    plan: dict[str, Any]


class CreativeTemplateCatalog:
    SECTIONS = ("domains", "scenes", "poses", "compositions", "cameras", "variations")

    def __init__(self, value: dict[str, Any]):
        if set(value) != {"schema_version", "catalog_version", *self.SECTIONS, "reference_roles"}:
            raise CreativeValidationError("creative_template_invalid", "template catalog fields are invalid")
        if value.get("schema_version") != "1.0" or not isinstance(value.get("catalog_version"), str):
            raise CreativeValidationError("creative_template_invalid", "template catalog version is invalid")
        self.value = value
        self.catalog_version = value["catalog_version"]
        self.entries: dict[str, dict[str, dict[str, Any]]] = {}
        for section in (*self.SECTIONS, "reference_roles"):
            entries = value.get(section)
            if not isinstance(entries, list) or not entries:
                raise CreativeValidationError("creative_template_invalid", f"{section} must be a non-empty array")
            parsed: dict[str, dict[str, Any]] = {}
            for entry in entries:
                allowed = {"id", "version", "label"} if section == "reference_roles" else {
                    "id", "version", "label", "prompt"
                }
                if section == "scenes":
                    allowed.add("compatible_poses")
                if not isinstance(entry, dict) or set(entry) != allowed:
                    raise CreativeValidationError("creative_template_invalid", f"{section} entry is invalid")
                if any(not isinstance(entry.get(key), str) or not entry[key] for key in ("id", "version", "label")):
                    raise CreativeValidationError("creative_template_invalid", f"{section} entry identity is invalid")
                if section != "reference_roles" and not isinstance(entry.get("prompt"), str):
                    raise CreativeValidationError("creative_template_invalid", f"{section} prompt is invalid")
                if section == "scenes" and (
                    not isinstance(entry.get("compatible_poses"), list)
                    or not all(isinstance(item, str) for item in entry["compatible_poses"])
                ):
                    raise CreativeValidationError("creative_template_invalid", "scene compatibility is invalid")
                if entry["id"] in parsed:
                    raise CreativeValidationError("creative_template_invalid", f"duplicate {section} template")
                parsed[entry["id"]] = entry
            if section != "reference_roles" and "auto" not in parsed:
                raise CreativeValidationError("creative_template_invalid", f"{section} has no auto template")
            self.entries[section] = parsed
        pose_ids = set(self.entries["poses"])
        if any(
            set(scene["compatible_poses"]) - pose_ids
            for scene in self.entries["scenes"].values()
        ):
            raise CreativeValidationError("creative_template_invalid", "scene references an unknown pose")

    @classmethod
    def load(cls, path: Path) -> "CreativeTemplateCatalog":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CreativeValidationError("creative_template_invalid", "template catalog could not be read") from exc
        if not isinstance(value, dict):
            raise CreativeValidationError("creative_template_invalid", "template catalog must be an object")
        return cls(value)

    def public_document(self) -> dict[str, Any]:
        return deepcopy(self.value)

    def resolve(self, section: str, identifier: str) -> dict[str, Any]:
        try:
            return self.entries[section][identifier]
        except KeyError as exc:
            raise CreativeValidationError(
                "creative_template_not_found",
                f"unknown {section} template: {identifier}",
                field=section,
            ) from exc


class CreativeCompiler:
    def __init__(self, catalog: CreativeTemplateCatalog):
        self.catalog = catalog

    @classmethod
    def load(cls, path: Path) -> "CreativeCompiler":
        return cls(CreativeTemplateCatalog.load(path))

    def compile(
        self,
        request: JobRequest,
        creative: CreativeSpec,
        *,
        capabilities: Mapping[str, Mapping[str, Any]],
        envelope: Mapping[str, Any] | None = None,
    ) -> CreativeCompileResult:
        resolved = {
            "domain": self.catalog.resolve("domains", creative.domain),
            "scene": self.catalog.resolve("scenes", creative.scene.preset),
            "pose": self.catalog.resolve("poses", creative.pose.preset),
            "composition": self.catalog.resolve("compositions", creative.composition.preset),
            "camera": self.catalog.resolve("cameras", creative.camera.preset),
            "variation": self.catalog.resolve("variations", creative.variation.axis),
        }
        if creative.pose.preset not in resolved["scene"]["compatible_poses"]:
            raise CreativeValidationError(
                "creative_combination_invalid",
                "選んだシーンとポーズは組み合わせられません。",
                field="pose",
            )
        input_ids = {item.asset_id for item in request.inputs}
        if any(item.asset_id not in input_ids for item in creative.reference_roles):
            raise CreativeValidationError(
                "creative_reference_not_in_request",
                "参照役割の画像が入力に含まれていません。",
                field="reference_roles",
            )
        if creative.active:
            required = (
                "image.text_to_image"
                if request.operation == "image.generate"
                else "image.single_reference_edit"
                if request.operation == "image.edit"
                else None
            )
            if required is None or capabilities.get(required, {}).get("state") != "available":
                raise CreativeValidationError(
                    "creative_capability_unavailable",
                    "この見せ方に必要な機能はいま使えません。",
                )

        plan = {
            "schema_version": "1.0",
            "catalog_version": self.catalog.catalog_version,
            "active": creative.active,
            "domain": self._snapshot(resolved["domain"]),
            "scene": {**self._snapshot(resolved["scene"]), "details": creative.scene.details},
            "pose": {**self._snapshot(resolved["pose"]), "details": creative.pose.details},
            "composition": {
                **self._snapshot(resolved["composition"]), "details": creative.composition.details,
            },
            "camera": {**self._snapshot(resolved["camera"]), "details": creative.camera.details},
            "variation": self._snapshot(resolved["variation"]),
            "reference_roles": [item.model_dump(mode="json") for item in creative.reference_roles],
            "envelope": dict(envelope or {}),
        }
        if not creative.active:
            return CreativeCompileResult(request=request, plan=plan)

        phrases = [request.intent.rstrip()]
        for name in ("domain", "scene", "pose", "composition", "camera", "variation"):
            prompt = resolved[name].get("prompt", "")
            if prompt:
                phrases.append(prompt)
        for details in (
            creative.scene.details,
            creative.pose.details,
            creative.composition.details,
            creative.camera.details,
        ):
            if details.strip():
                phrases.append(details.strip())
        intent = ". ".join(phrase.rstrip(". ") for phrase in phrases if phrase) + "."
        if len(intent) > 8000:
            raise CreativeValidationError(
                "creative_intent_too_long", "シーン指定を含めると指示が長すぎます。", field="intent"
            )
        value = request.model_dump(mode="python")
        value["intent"] = intent
        value["constraints"] = {**value["constraints"], "creative_plan": plan}
        compiled = JobRequest.model_validate(value)
        return CreativeCompileResult(request=compiled, plan=plan)

    @staticmethod
    def _snapshot(entry: Mapping[str, Any]) -> dict[str, str]:
        return {key: str(entry[key]) for key in ("id", "version", "label")}
