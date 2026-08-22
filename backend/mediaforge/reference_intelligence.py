from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, Any, Literal
import uuid

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .creative_intelligence import (
    ActionStateSpec,
    SemanticObservation,
    SubjectSpec,
    VisualAnalysis,
    VisualFacts,
    _provider_strict_schema,
)
from .host.ai import HostAIError, HostAIGateway
from .host.client import HostIdentity
from .vision import VisionInputError, vision_message


VISUAL_FACTS_VERSION = "visual-facts-v1"
VISUAL_ANALYSIS_VERSION = "visual-analysis-v1"
ReferenceFocus = Literal["overall", "identity", "pose", "palette", "composition", "style"]
REFERENCE_FOCUSES: tuple[ReferenceFocus, ...] = (
    "overall", "identity", "pose", "palette", "composition", "style",
)


class ReferenceIntelligenceError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class VisualAnalysisDraft(BaseModel):
    """Provider-authored semantic fields; measurable facts stay server-owned."""

    model_config = ConfigDict(extra="forbid")

    subject: SubjectSpec = Field(default_factory=SubjectSpec)
    action_state: ActionStateSpec = Field(default_factory=ActionStateSpec)
    scene: str = Field(default="", max_length=1000)
    composition: str = Field(default="", max_length=1000)
    style: list[str] = Field(default_factory=list, max_length=32)
    clothing_props: list[str] = Field(default_factory=list, max_length=32)
    text_regions: list[str] = Field(default_factory=list, max_length=32)
    observations: list[SemanticObservation] = Field(default_factory=list, max_length=64)
    inferences: list[SemanticObservation] = Field(default_factory=list, max_length=64)
    confidence_by_field: dict[
        Annotated[str, Field(min_length=1, max_length=80)],
        Annotated[float, Field(ge=0.0, le=1.0)],
    ] = Field(default_factory=dict, max_length=64)


class ReferenceAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(pattern=r"^asset_[0-9a-f]{32}$")
    asset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    facts_cache_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    facts_cache_hit: bool
    analysis_cache_hit: bool
    facts: VisualFacts
    analysis: VisualAnalysis | None = None
    skipped_reason: str | None = None


def facts_cache_key(asset_sha256: str) -> str:
    return hashlib.sha256(f"{asset_sha256}:{VISUAL_FACTS_VERSION}".encode()).hexdigest()


def analysis_cache_key(asset_sha256: str) -> str:
    return hashlib.sha256(
        f"{asset_sha256}:{VISUAL_FACTS_VERSION}:{VISUAL_ANALYSIS_VERSION}".encode()
    ).hexdigest()


def analyze_visual_facts(path: Path) -> VisualFacts:
    """Measure bounded image facts without changing or rewriting the source."""
    try:
        with Image.open(path) as opened:
            width, height = opened.size
            had_alpha = "A" in opened.getbands() or "transparency" in opened.info
            image = opened.convert("RGBA")
            alpha_histogram = image.getchannel("A").histogram()
            opaque_fraction = sum(alpha_histogram[250:]) / (width * height)
            image.thumbnail((256, 256), Image.Resampling.LANCZOS)
            pixels = list(image.get_flattened_data())
    except (OSError, UnidentifiedImageError) as exc:
        raise ReferenceIntelligenceError("reference_image_invalid", "Reference image is not decodable") from exc
    if width <= 0 or height <= 0 or not pixels:
        raise ReferenceIntelligenceError("reference_image_invalid", "Reference image is empty")

    visible = [(red, green, blue) for red, green, blue, alpha in pixels if alpha >= 32]
    entries: list[tuple[str, float, float]] = []
    if visible:
        strip = Image.new("RGB", (len(visible), 1))
        strip.putdata(visible)
        palette = strip.quantize(colors=min(8, len(set(visible))), method=Image.Quantize.MEDIANCUT)
        counts = palette.getcolors(maxcolors=len(visible)) or []
        raw_palette = palette.getpalette() or []
        for count, index in sorted(counts, key=lambda item: (-item[0], item[1])):
            offset = index * 3
            red, green, blue = raw_palette[offset:offset + 3]
            coverage = count / len(visible)
            maximum, minimum = max(red, green, blue), min(red, green, blue)
            saturation = 0.0 if maximum == 0 else (maximum - minimum) / maximum
            entries.append((f"#{red:02X}{green:02X}{blue:02X}", coverage, saturation))

    dominant = [
        {"hex": color, "coverage": round(coverage, 6)}
        for color, coverage, _saturation in entries[:6]
    ]
    accents = [
        {"hex": color, "coverage": round(coverage, 6)}
        for color, coverage, saturation in entries[1:]
        if coverage >= 0.01 and saturation >= 0.25
    ][:4]
    luminance = sum((0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255 for red, green, blue in visible)
    saturation = sum(
        0.0 if max(rgb) == 0 else (max(rgb) - min(rgb)) / max(rgb)
        for rgb in visible
    )
    return VisualFacts(
        version="1",
        width=width,
        height=height,
        aspect_ratio=round(width / height, 8),
        has_alpha=had_alpha,
        opaque_fraction=round(opaque_fraction, 8),
        dominant_colors=dominant,
        accent_colors=accents,
        mean_luminance=round(luminance / len(visible), 8) if visible else 0.0,
        mean_saturation=round(saturation / len(visible), 8) if visible else 0.0,
    )


class ReferenceAnalysisCache:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, kind: str, key: str) -> Path:
        return self.root / f"{kind}-{key}.json"

    def read_facts(self, asset_sha256: str) -> VisualFacts | None:
        return self._read(self._path("facts", facts_cache_key(asset_sha256)), VisualFacts)

    def write_facts(self, asset_sha256: str, value: VisualFacts) -> None:
        self._write(self._path("facts", facts_cache_key(asset_sha256)), value.model_dump(mode="json"))

    def read_analysis(self, asset_sha256: str) -> VisualAnalysis | None:
        return self._read(self._path("analysis", analysis_cache_key(asset_sha256)), VisualAnalysis)

    def write_analysis(self, asset_sha256: str, value: VisualAnalysis) -> None:
        self._write(self._path("analysis", analysis_cache_key(asset_sha256)), value.model_dump(mode="json"))

    @staticmethod
    def _read(path: Path, model: type[BaseModel]):
        try:
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValidationError, ValueError):
            return None

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


class ReferenceIntelligence:
    def __init__(self, gateway: HostAIGateway, cache: ReferenceAnalysisCache, *, timeout_sec: float = 120.0):
        self.gateway = gateway
        self.cache = cache
        self.timeout_sec = timeout_sec

    async def analyze(
        self,
        *,
        asset_id: str,
        asset_sha256: str,
        path: Path,
        identity: HostIdentity | None,
    ) -> ReferenceAnalysisResult:
        facts = self.cache.read_facts(asset_sha256)
        facts_hit = facts is not None
        if facts is None:
            facts = analyze_visual_facts(path)
            self.cache.write_facts(asset_sha256, facts)
        cached = self.cache.read_analysis(asset_sha256)
        if cached is not None and cached.asset_hash == asset_sha256 and cached.facts == facts:
            return ReferenceAnalysisResult(
                asset_id=asset_id, asset_hash=asset_sha256,
                facts_cache_key=facts_cache_key(asset_sha256), facts_cache_hit=facts_hit,
                analysis_cache_hit=True, facts=facts, analysis=cached,
            )
        if identity is None or "ai.inference" not in identity.granted_capabilities:
            return ReferenceAnalysisResult(
                asset_id=asset_id, asset_hash=asset_sha256,
                facts_cache_key=facts_cache_key(asset_sha256), facts_cache_hit=facts_hit,
                analysis_cache_hit=False, facts=facts, skipped_reason="vision_analyzer_unavailable",
            )
        try:
            if not await self.gateway.available(identity, "vision.analyze"):
                raise HostAIError("vision_analyzer_unavailable", "ControlDeck vision analyzer is unavailable")
            result = await self.gateway.complete(
                identity,
                "vision.analyze",
                [vision_message(
                    "Analyze this existing reference image into the requested JSON fields. Populate every field. "
                    "Use generic subject and action/state language for people, robots, vehicles, products, animals "
                    "and environments. Separate direct observations from inferences. Do not guess identity names, "
                    "copyright ownership, model/provider details, or measurable pixel/color facts.",
                    path,
                    (),
                )],
                response_format={
                    "type": "json_schema",
                    "name": "mediaforge_visual_analysis",
                    "schema": _provider_strict_schema(VisualAnalysisDraft.model_json_schema()),
                    "strict": True,
                },
                max_tokens=3072,
                timeout_seconds=max(1, min(300, int(self.timeout_sec))),
            )
            draft = VisualAnalysisDraft.model_validate_json(result.content)
            if any(not 0.0 <= value <= 1.0 for value in draft.confidence_by_field.values()):
                raise ValueError("analysis confidence is outside 0..1")
        except HostAIError as exc:
            return ReferenceAnalysisResult(
                asset_id=asset_id, asset_hash=asset_sha256,
                facts_cache_key=facts_cache_key(asset_sha256), facts_cache_hit=facts_hit,
                analysis_cache_hit=False, facts=facts, skipped_reason=exc.code,
            )
        except (VisionInputError, ValidationError, ValueError, json.JSONDecodeError) as exc:
            raise ReferenceIntelligenceError(
                "vision_result_invalid", "ControlDeck returned an invalid reference analysis"
            ) from exc
        analysis = VisualAnalysis(
            version="1", asset_hash=asset_sha256, facts=facts,
            **draft.model_dump(mode="python"),
        )
        self.cache.write_analysis(asset_sha256, analysis)
        return ReferenceAnalysisResult(
            asset_id=asset_id, asset_hash=asset_sha256,
            facts_cache_key=facts_cache_key(asset_sha256), facts_cache_hit=facts_hit,
            analysis_cache_hit=False, facts=facts, analysis=analysis,
        )


def analysis_summary(analysis: VisualAnalysis, focus: ReferenceFocus) -> dict[str, Any]:
    """Return only accepted role-relevant context; unrelated dimensions stay absent."""
    if focus == "identity":
        return {"focus": focus, "subject": analysis.subject.model_dump(mode="json")}
    if focus == "pose":
        return {"focus": focus, "action_state": analysis.action_state.model_dump(mode="json")}
    if focus == "palette":
        return {
            "focus": focus,
            "dominant_colors": [item.model_dump(mode="json") for item in analysis.facts.dominant_colors],
            "accent_colors": [item.model_dump(mode="json") for item in analysis.facts.accent_colors],
        }
    if focus == "composition":
        return {"focus": focus, "composition": analysis.composition}
    if focus == "style":
        return {"focus": focus, "style": analysis.style}
    return {
        "focus": focus,
        "subject": analysis.subject.model_dump(mode="json"),
        "action_state": analysis.action_state.model_dump(mode="json"),
        "scene": analysis.scene,
        "composition": analysis.composition,
        "style": analysis.style,
        "clothing_props": analysis.clothing_props,
        "dominant_colors": [item.model_dump(mode="json") for item in analysis.facts.dominant_colors],
    }
