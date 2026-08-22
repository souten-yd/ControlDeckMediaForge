from __future__ import annotations

from collections import deque
from pathlib import Path

from fastapi.testclient import TestClient

from conftest import fake_settings, wait_terminal
from mediaforge.app import create_app
from mediaforge.evaluator import CreativeScore, OllamaCreativeEvaluator


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

    async def available(self) -> bool:
        return self.is_available

    async def evaluate(
        self,
        path: Path,
        intent: str,
        *,
        creative_plan: dict,
        reference_paths: tuple[Path, ...] = (),
    ) -> CreativeScore:
        self.calls.append(path)
        value = self.values.popleft()
        return CreativeScore(
            scores={
                "identity_match": value,
                "style_match": value,
                "pose_action_match": value,
                "scene_match": value,
                "composition_match": value,
                "obvious_visual_breakage": 100 - value,
            },
            summary=f"score {value}",
            evaluator="test-vlm",
        )


def test_ollama_evaluator_is_cpu_only_bounded_and_advisory():
    evaluator = OllamaCreativeEvaluator("http://127.0.0.1:11434", "qwen3-vl:2b")
    payload = evaluator.request_payload(["candidate", "reference"], "wave", {"pose": "wave"})
    assert payload["options"] == {
        "temperature": 0,
        "num_gpu": 0,
        "num_ctx": 4096,
        "num_predict": 512,
    }
    assert payload["think"] is False and payload["stream"] is False
    assert payload["format"]["properties"]["obvious_visual_breakage"]["maximum"] == 100
    assert "advisory ranking only" in payload["messages"][0]["content"]
    assert payload["messages"][0]["content"].startswith("/no_think\n")


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
    assert response.json()["detail"]["code"] == "creative_evaluation_unavailable"


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
