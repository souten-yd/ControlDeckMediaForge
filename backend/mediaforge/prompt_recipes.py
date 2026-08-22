from __future__ import annotations

import json
import re
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .host.ai import HostAIError, HostAIGateway
from .host.client import HostIdentity


PromptRecipeMode = Literal["t2va", "i2va", "fl2va", "l2va", "ref2va"]
PromptReferenceKind = Literal["image", "video", "audio"]

H3_PROMPT_RECIPE_ID = "minimax-h3-prompt-writing"
H3_PROMPT_RECIPE_VERSION = "1"
H3_PROMPT_RECIPE_SOURCE_REVISION = "d21241f0a4b3acbb34c97dae47fa417b7065e438"
H3_PROMPT_RECIPE_SOURCE_HASHES = {
    "SKILL.md": "a7000443588ca3f145e3b3fd8900f14e0325dc460bd811268fac89a9dc8e56d0",
    "references/base-en.txt": "2cfebc096a6e08370f288d468d90b60f7f9bcb938f94bf090816e910e48e75fc",
    "references/ref-en.txt": "1e574f356716ad55612247ffb7bbccbcdb484ad96599d63c7dca1af186b1fab7",
}

_REFERENCE_LABEL = re.compile(r"<(Picture|Video|Audio) ([1-9][0-9]*)>")
_FENCED_JSON = re.compile(r"\A```(?:json)?\s*\r?\n(?P<body>.*)\r?\n```\Z", re.DOTALL)


class PromptRecipeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class PromptReference(BaseModel):
    """A bounded semantic summary; raw bytes and filesystem paths never enter text planning."""

    model_config = ConfigDict(extra="forbid")

    kind: PromptReferenceKind
    description: str = Field(min_length=1, max_length=2000)


class PromptRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = Field(min_length=1, max_length=8000)
    mode: PromptRecipeMode
    duration_seconds: float = Field(ge=4.0, le=15.0)
    references: list[PromptReference] = Field(default_factory=list, max_length=16)
    verbatim_text: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list, max_length=16
    )

    @model_validator(mode="after")
    def validate_mode_references(self) -> "PromptRecipeRequest":
        kinds = [item.kind for item in self.references]
        if self.mode == "t2va" and kinds:
            raise ValueError("t2va does not accept references")
        if self.mode in {"i2va", "l2va"} and kinds != ["image"]:
            raise ValueError(f"{self.mode} requires exactly one image reference")
        if self.mode == "fl2va" and kinds != ["image", "image"]:
            raise ValueError("fl2va requires exactly two image references")
        if self.mode == "ref2va" and not kinds:
            raise ValueError("ref2va requires at least one reference")
        return self


class BasePromptDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integrated_multimodal_description: str = Field(min_length=1, max_length=16000)
    overall_soundscape: str = Field(min_length=1, max_length=3000)
    non_diegetic_music: str = Field(min_length=1, max_length=2000)


class ReferencePromptDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_definitions: str = Field(min_length=1, max_length=5000)
    summary: str = Field(min_length=1, max_length=3000)
    retention_analysis: str = Field(min_length=1, max_length=5000)
    detailed_description: str = Field(min_length=1, max_length=16000)
    overall_soundscape: str = Field(min_length=1, max_length=3000)
    non_diegetic_music: str = Field(min_length=1, max_length=2000)


class ProjectedPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = "1"
    recipe_id: Literal["minimax-h3-prompt-writing"] = H3_PROMPT_RECIPE_ID
    recipe_version: Literal["1"] = H3_PROMPT_RECIPE_VERSION
    source_revision: Literal[H3_PROMPT_RECIPE_SOURCE_REVISION] = H3_PROMPT_RECIPE_SOURCE_REVISION
    capability: Literal["text.generate"] = "text.generate"
    mode: PromptRecipeMode
    duration_seconds: float
    reference_labels: list[str] = Field(default_factory=list, max_length=16)
    sections: dict[str, str]
    rendered_prompt: str = Field(min_length=1, max_length=32768)


class PromptRecipe(Protocol):
    async def project(self, identity: HostIdentity, request: PromptRecipeRequest) -> ProjectedPrompt: ...


def _provider_strict_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    properties = schema.get("properties")
    if isinstance(properties, dict):
        schema["required"] = list(properties)
    return schema


def _reference_labels(references: list[PromptReference]) -> list[str]:
    counts = {"image": 0, "video": 0, "audio": 0}
    names = {"image": "Picture", "video": "Video", "audio": "Audio"}
    labels: list[str] = []
    for reference in references:
        counts[reference.kind] += 1
        labels.append(f"<{names[reference.kind]} {counts[reference.kind]}>")
    return labels


def _validate_labels(sections: dict[str, str], expected: list[str]) -> None:
    text = "\n".join(sections.values())
    found = {f"<{kind} {index}>" for kind, index in _REFERENCE_LABEL.findall(text)}
    allowed = set(expected)
    if found - allowed:
        raise ValueError("prompt contains an unknown reference label")
    if allowed - found:
        raise ValueError("prompt omitted a required reference label")


def _validate_verbatim_text(sections: dict[str, str], expected: list[str]) -> None:
    text = "\n".join(sections.values())
    if any(value not in text for value in expected):
        raise ValueError("prompt omitted required verbatim text")


def _load_provider_json(content: str) -> object:
    """Accept raw JSON or one bounded Markdown JSON fence, but no surrounding prose."""

    normalized = content.strip()
    fenced = _FENCED_JSON.fullmatch(normalized)
    if fenced is not None:
        normalized = fenced.group("body")
    return json.loads(normalized)


def _alignment(mode: PromptRecipeMode, duration_seconds: float) -> str | None:
    duration = f"{duration_seconds:.2f}"
    if mode == "i2va":
        return (
            "reference_alignment: <Picture 1> is the target video's first frame "
            "at 0.00 seconds."
        )
    if mode == "fl2va":
        return (
            "reference_alignment: <Picture 1> is the target video's first frame at 0.00 seconds; "
            f"<Picture 2> is its last frame at {duration} seconds."
        )
    if mode == "l2va":
        return (
            "reference_alignment: <Picture 1> is the target video's last frame "
            f"at {duration} seconds."
        )
    return None


def _render_base(mode: PromptRecipeMode, duration_seconds: float, draft: BasePromptDraft) -> str:
    values = draft.model_dump(mode="python")
    body = "\n".join(f"{name}: {values[name]}" for name in (
        "integrated_multimodal_description",
        "overall_soundscape",
        "non_diegetic_music",
    ))
    alignment = _alignment(mode, duration_seconds)
    return f"{alignment}\n\n{body}" if alignment else body


def _render_reference(draft: ReferencePromptDraft) -> str:
    values = draft.model_dump(mode="python")
    return "\n".join(f"{name}: {values[name]}" for name in (
        "subject_definitions",
        "summary",
        "retention_analysis",
        "detailed_description",
        "overall_soundscape",
        "non_diegetic_music",
    ))


class H3PromptRecipe:
    """Version-pinned H3 prompt projection over ControlDeck's generic text gateway.

    This is data projection, not arbitrary skill execution. No repository, path,
    command, provider, model, or port is sent to ControlDeck.
    """

    def __init__(self, gateway: HostAIGateway):
        self.gateway = gateway

    async def project(self, identity: HostIdentity, request: PromptRecipeRequest) -> ProjectedPrompt:
        labels = _reference_labels(request.references)
        if request.mode == "ref2va":
            draft_type: type[BaseModel] = ReferencePromptDraft
            field_order = (
                "subject_definitions, summary, retention_analysis, detailed_description, "
                "overall_soundscape, non_diegetic_music"
            )
        else:
            draft_type = BasePromptDraft
            field_order = (
                "integrated_multimodal_description, overall_soundscape, non_diegetic_music"
            )
        instruction = (
            "Project the user's request into the supplied strict JSON schema for a short audiovisual clip. "
            f"The requested mode is {request.mode}; duration is {request.duration_seconds:.2f} seconds. "
            f"Populate the fields in this semantic order: {field_order}. "
            "Write the structured sections in English, but preserve dialogue, lyrics, and visible scene text "
            "verbatim in their original language. Describe concrete composition, subjects, environment, "
            "actions, camera behavior, synchronized sound, and timing. The described timeline must fit the "
            "requested duration. Preserve explicit user facts. Do not output provider, model, port, repository, "
            "path, command, or skill-execution instructions. Do not add fields outside the schema."
        )
        if labels:
            instruction += " Use only these exact reference labels and include every one: " + ", ".join(labels) + "."
        if request.verbatim_text:
            instruction += (
                " Preserve every string in verbatim_text exactly, including its language and punctuation."
            )
        references = [
            {"label": label, "kind": item.kind, "description": item.description}
            for label, item in zip(labels, request.references, strict=True)
        ]
        user_content = json.dumps(
            {
                "intent": request.intent,
                "duration_seconds": request.duration_seconds,
                "references": references,
                "verbatim_text": request.verbatim_text,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        response_format = {
            "type": "json_schema",
            "name": "mediaforge_h3_prompt_recipe",
            "schema": _provider_strict_schema(draft_type),
            "strict": True,
        }
        try:
            result = await self.gateway.complete(
                identity,
                "text.generate",
                [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user_content},
                ],
                response_format=response_format,
                temperature=0.1,
                max_tokens=6144,
                timeout_seconds=120,
            )
        except HostAIError as exc:
            raise PromptRecipeError(exc.code, str(exc)) from exc
        try:
            authored = _load_provider_json(result.content)
            if request.mode == "ref2va":
                draft = ReferencePromptDraft.model_validate(authored)
                sections = draft.model_dump(mode="python")
                rendered = _render_reference(draft)
            else:
                draft = BasePromptDraft.model_validate(authored)
                sections = draft.model_dump(mode="python")
                rendered = _render_base(request.mode, request.duration_seconds, draft)
            _validate_labels(sections, labels)
            _validate_verbatim_text(sections, request.verbatim_text)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            raise PromptRecipeError(
                "prompt_recipe_invalid", "ControlDeck returned an invalid prompt recipe projection"
            ) from exc
        if len(rendered) > 32768:
            raise PromptRecipeError("prompt_recipe_invalid", "Rendered prompt exceeds the bounded size")
        return ProjectedPrompt(
            mode=request.mode,
            duration_seconds=request.duration_seconds,
            reference_labels=labels,
            sections=sections,
            rendered_prompt=rendered,
        )
