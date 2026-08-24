from __future__ import annotations

import asyncio
from collections import deque
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import fake_settings, wait_terminal
from mediaforge.app import create_app
from PIL import Image

from mediaforge.creative_intelligence import EvaluationResult, EvaluationScores
from mediaforge.evaluator import EvaluatedCandidate, HostCreativeEvaluator
from mediaforge.host.client import HostIdentity


IDENTITY = HostIdentity(
    authorization="Bearer test-token", addon_id="media-forge", subject="1",
    expires_at=2**31, granted_capabilities=frozenset({"ai.inference"}),
)


def request(*, retries: int = 0) -> dict:
    return {
        "operation": "image.generate",
        "intent": "a small orange robot waving",
        "inputs": [],
        "model_policy": "auto",
        "constraints": {"width": 256, "height": 256, "seed": 42},
        "output": {"format": "png", "count": 1},
        "qa": {
            "deterministic": True,
            "semantic": True,
            "max_regeneration_attempts": retries,
        },
        "local_only": True,
    }


class Reviewer:
    def __init__(self, decisions: list[bool], *, available: bool = True):
        self.decisions = deque(decisions)
        self.is_available = available
        self.calls: list[Path] = []

    async def available(self, identity=None) -> bool:
        del identity
        return self.is_available

    async def evaluate(
        self,
        path: Path,
        intent: str,
        *,
        creative_plan: dict,
        reference_paths: tuple[Path, ...] = (),
        identity=None,
        brief=None,
        resolved_layout=None,
    ) -> EvaluatedCandidate:
        del identity, reference_paths, intent, creative_plan, brief, resolved_layout
        self.calls.append(path)
        accepted = self.decisions.popleft()
        return EvaluatedCandidate(
            result=EvaluationResult(
                accepted_for_requested_constraints=accepted,
                scores=EvaluationScores(
                    intent=0.9 if accepted else 0.2,
                    visual_integrity=0.9,
                ),
                issues=[] if accepted else ["missing wave"],
                strengths=["clear match"] if accepted else [],
                retry_suggestions=[] if accepted else ["show the wave clearly"],
                review_budget_used=1,
            ),
            evaluator="test-vlm",
            relevant_dimensions=("intent", "visual_integrity"),
        )


class Gateway:
    def __init__(self, content: dict):
        self.content = content
        self.calls = []

    async def available(self, identity, capability):
        self.calls.append(("available", identity, capability))
        return True

    async def complete(self, identity, capability, messages, **kwargs):
        self.calls.append(("complete", identity, capability, messages, kwargs))
        return type("Result", (), {"content": json.dumps(self.content), "capability": capability})()


def evaluation_body(*, references: bool = False) -> dict:
    scores = {name: None for name in (
        "intent", "subject_identity", "action_state", "palette", "composition",
        "style", "props_clothing", "visual_integrity",
    )}
    scores.update({"intent": 0.9, "visual_integrity": 0.9})
    if references:
        scores.update({"subject_identity": 0.8, "style": 0.8})
    return {"scores": scores, "issues": [], "strengths": ["clear match"], "retry_suggestions": []}


def test_host_evaluator_uses_bounded_vision_message_without_model_or_provider(tmp_path: Path):
    image = tmp_path / "candidate.png"
    Image.new("RGB", (32, 32), "orange").save(image)
    gateway = Gateway(evaluation_body())
    reviewer = HostCreativeEvaluator(gateway)  # type: ignore[arg-type]
    result = asyncio.run(reviewer.evaluate(image, "orange", creative_plan={}, identity=IDENTITY))
    assert result.result.accepted_for_requested_constraints is True
    assert result.evaluator == "control-deck:vision.analyze"
    call = gateway.calls[-1]
    assert call[2] == "vision.analyze"
    assert call[3][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "model" not in call[4] and "provider" not in call[4]


def test_four_references_are_bounded_into_one_host_image_part(tmp_path: Path):
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (32, 32), "orange").save(candidate)
    references = []
    for index in range(4):
        path = tmp_path / f"reference-{index}.png"
        Image.new("RGB", (32 + index, 32), (index * 40, 20, 10)).save(path)
        references.append(path)
    gateway = Gateway(evaluation_body(references=True))
    reviewer = HostCreativeEvaluator(gateway)  # type: ignore[arg-type]
    asyncio.run(reviewer.evaluate(
        candidate, "orange", creative_plan={}, reference_paths=tuple(references), identity=IDENTITY
    ))
    content = gateway.calls[-1][3][0]["content"]
    images = [part for part in content if part["type"] == "image_url"]
    assert len(images) == 2
    assert all(len(part["image_url"]["url"]) < 2 * 1024 * 1024 * 4 / 3 + 64 for part in images)


def test_semantic_disabled_never_calls_reviewer(tmp_path: Path):
    reviewer = Reviewer([])
    app = create_app(fake_settings(tmp_path), creative_evaluator=reviewer)
    payload = request()
    payload["qa"]["semantic"] = False
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=payload).json()["id"])
    assert terminal["status"] == "succeeded"
    assert reviewer.calls == []


def test_default_rejection_is_advisory_without_retry(tmp_path: Path):
    reviewer = Reviewer([False])
    app = create_app(fake_settings(tmp_path), creative_evaluator=reviewer)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request()).json()["id"])
        provenance = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}/provenance").json()
    assert terminal["status"] == "succeeded"
    assert len(reviewer.calls) == 1
    assert provenance["validation"][-1]["passed"] is False
    assert provenance["warnings"] == ["evaluation advisory: missing wave"]
    assert provenance["validation"][-1]["evaluation"]["scores"]["intent"] == 0.2


def test_explicit_retry_selects_next_accepted_candidate(tmp_path: Path):
    reviewer = Reviewer([False, True])
    app = create_app(fake_settings(tmp_path), creative_evaluator=reviewer)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request(retries=1)).json()["id"])
        provenance = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}/provenance").json()
    assert terminal["status"] == "succeeded"
    assert len(reviewer.calls) == 2
    assert provenance["seed"] == 42
    assert provenance["validation"][-1]["passed"] is True
    assert provenance["validation"][-1]["evaluation"]["review_budget_used"] == 2
    assert provenance["warnings"] == []


def test_retry_budget_exhaustion_fails_explicitly(tmp_path: Path):
    reviewer = Reviewer([False, False])
    app = create_app(fake_settings(tmp_path), creative_evaluator=reviewer)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request(retries=1)).json()["id"])
    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "semantic_review_exhausted"
    assert len(reviewer.calls) == 2


def test_unavailable_evaluator_preserves_deterministically_valid_asset(tmp_path: Path):
    reviewer = Reviewer([], available=False)
    app = create_app(fake_settings(tmp_path), creative_evaluator=reviewer)
    with TestClient(app) as client:
        capabilities = client.get("/api/v1/capabilities").json()["capabilities"]
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request()).json()["id"])
        provenance = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}/provenance").json()
    assert capabilities["image.semantic_review"] == {
        "state": "unavailable",
        "reason": "vision_analyzer_unavailable",
    }
    assert terminal["status"] == "succeeded"
    assert provenance["warnings"] == [
        "unified evaluator unavailable; deterministic validation passed"
    ]
    assert reviewer.calls == []


def test_deterministic_failure_prevents_semantic_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reviewer = Reviewer([True])
    app = create_app(fake_settings(tmp_path), creative_evaluator=reviewer)

    def fail_validation(_: Path):
        raise ValueError("deterministic failure")

    monkeypatch.setattr("mediaforge.jobs.validate_png", fail_validation)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request()).json()["id"])
    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "artifact_integrity_failed"
    assert reviewer.calls == []
