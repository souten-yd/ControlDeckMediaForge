from __future__ import annotations

import asyncio
from collections import deque
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import fake_settings, wait_terminal
from mediaforge.app import create_app
from mediaforge.creative_intelligence import EvaluationResult, EvaluationScores
from PIL import Image

from mediaforge.evaluator import (
    CreativeEvaluationError,
    EvaluatedCandidate,
    HostCreativeEvaluator,
    relevant_dimensions,
)
from mediaforge.host.client import HostIdentity


IDENTITY = HostIdentity(
    authorization="Bearer test-token", addon_id="media-forge", subject="1",
    expires_at=2**31, granted_capabilities=frozenset({"ai.inference"}),
)


def generation(intent: str, seed: int) -> dict:
    return {
        "operation": "image.generate",
        "intent": intent,
        "constraints": {"width": 256, "height": 256, "seed": seed},
        "output": {"format": "png", "count": 1},
        "local_only": True,
    }


class Evaluator:
    def __init__(self, values: list[int], *, available: bool = True):
        self.values = deque(values)
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
        del identity, creative_plan, reference_paths, intent
        self.calls.append(path)
        value = self.values.popleft()
        score = value / 100
        return EvaluatedCandidate(
            result=EvaluationResult(
                accepted_for_requested_constraints=score >= 0.55,
                scores=EvaluationScores(intent=score, visual_integrity=score),
                issues=[] if score >= 0.55 else [f"score {value}"],
                strengths=[f"score {value}"] if score >= 0.55 else [],
                retry_suggestions=[],
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
        return True

    async def complete(self, identity, capability, messages, **kwargs):
        self.calls.append((identity, capability, messages, kwargs))
        return type("Result", (), {"content": json.dumps(self.content), "capability": capability})()


def test_host_evaluator_is_provider_neutral_bounded_and_advisory(tmp_path: Path):
    image = tmp_path / "candidate.png"
    Image.new("RGB", (32, 32), "orange").save(image)
    body = {
        "scores": {
            "intent": 0.8,
            "subject_identity": None,
            "action_state": 0.8,
            "palette": None,
            "composition": None,
            "style": None,
            "props_clothing": None,
            "visual_integrity": 0.95,
        },
        "issues": [],
        "strengths": ["good"],
        "retry_suggestions": [],
    }
    gateway = Gateway(body)
    evaluator = HostCreativeEvaluator(gateway)  # type: ignore[arg-type]
    score = asyncio.run(evaluator.evaluate(
        image, "wave", creative_plan={"pose": "wave"}, identity=IDENTITY
    ))
    assert score.evaluator == "control-deck:vision.analyze"
    assert score.result.accepted_for_requested_constraints is True
    _, capability, messages, kwargs = gateway.calls[0]
    assert capability == "vision.analyze"
    assert "Deterministic file and edit validators already ran" in messages[0]["content"][0]["text"]
    score_schema = kwargs["response_format"]["schema"]["properties"]["scores"]
    assert score_schema["properties"]["visual_integrity"]["anyOf"][0]["maximum"] == 1
    assert "model" not in kwargs and "provider" not in kwargs


def test_palette_only_reference_does_not_score_or_penalize_action(tmp_path: Path):
    image = tmp_path / "candidate.png"
    reference = tmp_path / "palette.png"
    Image.new("RGB", (32, 32), "orange").save(image)
    Image.new("RGB", (32, 32), "blue").save(reference)
    body = {
        "scores": {
            "intent": 0.9,
            "subject_identity": None,
            "action_state": None,
            "palette": 0.8,
            "composition": None,
            "style": None,
            "props_clothing": None,
            "visual_integrity": 0.9,
        },
        "issues": [],
        "strengths": ["palette matches"],
        "retry_suggestions": [],
    }
    evaluator = HostCreativeEvaluator(Gateway(body))  # type: ignore[arg-type]
    evaluated = asyncio.run(evaluator.evaluate(
        image,
        "use the reference palette",
        creative_plan={"reference_roles": [{"role": "palette"}]},
        reference_paths=(reference,),
        identity=IDENTITY,
    ))

    assert evaluated.relevant_dimensions == ("intent", "palette", "visual_integrity")
    assert evaluated.result.scores.action_state is None
    assert evaluated.result.accepted_for_requested_constraints is True


def test_evaluator_rejects_scores_for_irrelevant_dimensions(tmp_path: Path):
    image = tmp_path / "candidate.png"
    Image.new("RGB", (32, 32), "orange").save(image)
    body = {
        "scores": {
            "intent": 0.9,
            "subject_identity": None,
            "action_state": 0.9,
            "palette": None,
            "composition": None,
            "style": None,
            "props_clothing": None,
            "visual_integrity": 0.9,
        },
        "issues": [],
        "strengths": ["good"],
        "retry_suggestions": [],
    }
    evaluator = HostCreativeEvaluator(Gateway(body))  # type: ignore[arg-type]

    with pytest.raises(CreativeEvaluationError) as caught:
        asyncio.run(evaluator.evaluate(image, "orange", creative_plan={}, identity=IDENTITY))
    assert caught.value.code == "vision_result_invalid"


def test_relevant_dimensions_follow_reference_roles_and_explicit_controls():
    assert relevant_dimensions(
        {
            "reference_roles": [{"role": "pose"}, {"role": "clothing"}],
            "composition": {"id": "centered"},
        },
        has_references=True,
    ) == ("intent", "action_state", "composition", "props_clothing", "visual_integrity")


def test_candidate_evaluation_ranks_without_regeneration(tmp_path: Path):
    evaluator = Evaluator([40, 90])
    app = create_app(fake_settings(tmp_path), creative_evaluator=evaluator)
    with TestClient(app) as client:
        first_job = wait_terminal(client, client.post("/api/v1/jobs", json=generation("first", 1)).json()["id"])
        second_job = wait_terminal(client, client.post("/api/v1/jobs", json=generation("second", 2)).json()["id"])
        jobs_before = len(client.get("/api/v1/jobs").json()["items"])
        response = client.post("/workspace-api/creative/evaluate", json={
            "asset_ids": [first_job["asset_ids"][0], second_job["asset_ids"][0]],
            "reference_asset_ids": [],
            "intent": "best orange companion",
            "creative_plan": {"pose": {"id": "wave"}},
        })
        jobs_after = len(client.get("/api/v1/jobs").json()["items"])

    assert response.status_code == 200
    result = response.json()
    assert result["ranked_asset_ids"] == [second_job["asset_ids"][0], first_job["asset_ids"][0]]
    assert result["advisory"] is True and result["regeneration_requested"] is False
    assert jobs_after == jobs_before
    assert len(evaluator.calls) == 2


def test_candidate_evaluation_fails_closed_when_evaluator_is_unavailable(tmp_path: Path):
    evaluator = Evaluator([], available=False)
    app = create_app(fake_settings(tmp_path), creative_evaluator=evaluator)
    with TestClient(app) as client:
        job = wait_terminal(client, client.post("/api/v1/jobs", json=generation("candidate", 3)).json()["id"])
        response = client.post("/workspace-api/creative/evaluate", json={
            "asset_ids": job["asset_ids"], "intent": "candidate",
        })
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "vision_analyzer_unavailable"


def test_candidate_evaluation_rejects_host_paths_before_lookup(tmp_path: Path):
    app = create_app(fake_settings(tmp_path), creative_evaluator=Evaluator([], available=False))
    with TestClient(app) as client:
        response = client.post("/workspace-api/creative/evaluate", json={
            "asset_ids": ["asset_" + "a" * 32], "intent": "candidate", "hint": "/etc/passwd",
        })
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unscoped_host_path"


def test_candidate_evaluation_rejects_oversized_plan(tmp_path: Path):
    app = create_app(fake_settings(tmp_path), creative_evaluator=Evaluator([], available=False))
    with TestClient(app) as client:
        response = client.post("/workspace-api/creative/evaluate", json={
            "asset_ids": ["asset_" + "a" * 32],
            "intent": "rank these candidates",
            "creative_plan": {"notes": "x" * (16 * 1024)},
        })
    assert response.status_code == 422
