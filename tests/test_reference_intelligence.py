from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import struct
import time

from PIL import Image
import pytest

from mediaforge.creative_intelligence import (
    ActionStateSpec,
    SubjectSpec,
    VisualAnalysis,
)
from mediaforge.host.ai import HostAIError, HostAIResult
from mediaforge.host.client import HostIdentity
from mediaforge.reference_intelligence import (
    ReferenceAnalysisCache,
    ReferenceIntelligence,
    ReferenceIntelligenceError,
    analysis_summary,
    analyze_visual_facts,
    facts_cache_key,
)


class FakeVisionGateway:
    def __init__(self, response: dict | None, *, available: bool = True):
        self.response = response
        self.is_available = available
        self.calls: list[dict] = []

    async def available(self, identity: HostIdentity, capability: str) -> bool:
        assert capability == "vision.analyze"
        return self.is_available

    async def complete(self, identity: HostIdentity, capability: str, messages: list[dict], **kwargs):
        self.calls.append({"capability": capability, "messages": messages, **kwargs})
        if self.response is None:
            raise HostAIError("vision_analyzer_unavailable", "unavailable")
        return HostAIResult(content=json.dumps(self.response), capability="vision.analyze")


def identity() -> HostIdentity:
    return HostIdentity(
        authorization="Bearer test",
        addon_id="media-forge",
        subject="7",
        expires_at=int(time.time()) + 600,
        granted_capabilities=frozenset({"ai.inference"}),
    )


def reference_image(path: Path) -> bytes:
    image = Image.new("RGBA", (100, 40), (0, 0, 0, 0))
    for x in range(25):
        for y in range(40):
            image.putpixel((x, y), (255, 0, 0, 255))
    image.save(path)
    return path.read_bytes()


def semantic_response(kind: str = "robot") -> dict:
    return {
        "subject": {
            "kind": kind,
            "count": 1,
            "identity_traits": ["round amber eyes"],
            "appearance_traits": ["orange shell"],
            "materials": ["painted metal"],
        },
        "action_state": {
            "action": "waving",
            "state": "cheerful",
            "orientation": "front three-quarter",
            "gesture": "right arm raised",
            "gaze": "toward viewer",
            "motion_hint": "small wave",
            "body_or_part_relations": ["right hand above shoulder"],
            "confidence": 0.9,
        },
        "scene": "compact workshop",
        "composition": "full body centered",
        "style": ["anime illustration"],
        "clothing_props": ["tool belt"],
        "text_regions": [],
        "observations": [{"field": "pose", "value": "arm raised", "source": "observed", "confidence": 0.9}],
        "inferences": [{"field": "mood", "value": "cheerful", "source": "inferred", "confidence": 0.6}],
        "confidence_by_field": {"subject": 0.9, "action_state": 0.9},
    }


def test_visual_facts_ignore_transparent_background_and_never_mutate_source(tmp_path: Path):
    path = tmp_path / "reference.png"
    original = reference_image(path)

    first = analyze_visual_facts(path)
    second = analyze_visual_facts(path)

    assert path.read_bytes() == original
    assert first == second
    assert first.width == 100 and first.height == 40
    assert first.has_alpha is True and first.opaque_fraction == 0.25
    assert first.dominant_colors[0].hex == "#FF0000"
    assert first.dominant_colors[0].coverage == 1.0
    assert facts_cache_key(hashlib.sha256(original).hexdigest()) == facts_cache_key(
        hashlib.sha256(original).hexdigest()
    )


def test_fully_transparent_image_has_no_invented_black_palette(tmp_path: Path):
    path = tmp_path / "transparent.png"
    Image.new("RGBA", (12, 8), (0, 0, 0, 0)).save(path)

    facts = analyze_visual_facts(path)

    assert facts.opaque_fraction == 0.0
    assert facts.dominant_colors == [] and facts.accent_colors == []
    assert facts.mean_luminance == 0.0 and facts.mean_saturation == 0.0


def test_visual_facts_reject_oversized_dimensions_before_decoding_pixels(tmp_path: Path):
    path = tmp_path / "oversized.bmp"
    width = height = 9000
    header = (
        b"BM" + struct.pack("<IHHI", 54, 0, 0, 54)
        + struct.pack("<IIIHHIIIIII", 40, width, height, 1, 24, 0, 0, 2835, 2835, 0, 0)
    )
    path.write_bytes(header)

    with pytest.raises(ReferenceIntelligenceError) as error:
        analyze_visual_facts(path)

    assert error.value.code == "reference_image_invalid"


@pytest.mark.parametrize("kind", ["person", "robot", "vehicle", "product"])
def test_semantic_analysis_is_generic_cached_and_contains_no_model_identity(tmp_path: Path, kind: str):
    path = tmp_path / f"{kind}.png"
    content = reference_image(path)
    digest = hashlib.sha256(content).hexdigest()
    gateway = FakeVisionGateway(semantic_response(kind))
    intelligence = ReferenceIntelligence(gateway, ReferenceAnalysisCache(tmp_path / "cache"))

    first = asyncio.run(intelligence.analyze(
        asset_id="asset_" + "1" * 32,
        asset_sha256=digest,
        path=path,
        identity=identity(),
    ))
    second = asyncio.run(intelligence.analyze(
        asset_id="asset_" + "2" * 32,
        asset_sha256=digest,
        path=path,
        identity=identity(),
    ))

    assert first.analysis is not None and first.analysis.subject.kind == kind
    assert first.analysis.asset_hash == digest
    assert first.analysis_cache_hit is False and second.analysis_cache_hit is True
    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert set(call) == {
        "capability", "messages", "response_format", "max_tokens", "timeout_seconds"
    }
    schema_properties = call["response_format"]["schema"]["properties"]
    assert "model_id" not in schema_properties and "provider" not in schema_properties
    encoded = json.dumps(call)
    assert "data:image/jpeg;base64," in encoded


def test_unavailable_semantic_analysis_returns_deterministic_facts(tmp_path: Path):
    path = tmp_path / "reference.png"
    content = reference_image(path)
    gateway = FakeVisionGateway(semantic_response(), available=False)
    result = asyncio.run(ReferenceIntelligence(
        gateway, ReferenceAnalysisCache(tmp_path / "cache")
    ).analyze(
        asset_id="asset_" + "1" * 32,
        asset_sha256=hashlib.sha256(content).hexdigest(),
        path=path,
        identity=identity(),
    ))

    assert result.analysis is None
    assert result.skipped_reason == "vision_analyzer_unavailable"
    assert result.facts.width == 100
    assert gateway.calls == []


def test_role_specific_summaries_do_not_leak_unrequested_dimensions(tmp_path: Path):
    path = tmp_path / "reference.png"
    content = reference_image(path)
    facts = analyze_visual_facts(path)
    response = semantic_response()
    analysis = VisualAnalysis(
        asset_hash=hashlib.sha256(content).hexdigest(),
        facts=facts,
        subject=SubjectSpec.model_validate(response["subject"]),
        action_state=ActionStateSpec.model_validate(response["action_state"]),
        scene=response["scene"], composition=response["composition"], style=response["style"],
    )

    identity_value = analysis_summary(analysis, "identity")
    pose = analysis_summary(analysis, "pose")
    palette = analysis_summary(analysis, "palette")
    style = analysis_summary(analysis, "style")

    assert set(identity_value) == {"focus", "subject"}
    assert set(pose) == {"focus", "action_state"}
    assert set(palette) == {"focus", "dominant_colors", "accent_colors"}
    assert set(style) == {"focus", "style"}


def test_invalid_provider_result_is_fail_closed_and_not_cached(tmp_path: Path):
    path = tmp_path / "reference.png"
    content = reference_image(path)
    response = semantic_response()
    response["confidence_by_field"] = {"subject": 1.5}
    cache = ReferenceAnalysisCache(tmp_path / "cache")
    intelligence = ReferenceIntelligence(FakeVisionGateway(response), cache)

    with pytest.raises(ReferenceIntelligenceError) as error:
        asyncio.run(intelligence.analyze(
            asset_id="asset_" + "1" * 32,
            asset_sha256=hashlib.sha256(content).hexdigest(),
            path=path,
            identity=identity(),
        ))

    assert error.value.code == "vision_result_invalid"
    assert cache.read_analysis(hashlib.sha256(content).hexdigest()) is None
