from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import fake_settings, wait_terminal
from mediaforge.app import create_app
from mediaforge.semantic_review import OllamaSemanticReviewer, SemanticReviewResult, loopback_origin


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

    async def available(self) -> bool:
        return self.is_available

    async def review(
        self,
        path: Path,
        intent: str,
        *,
        reference_paths: tuple[Path, ...] = (),
    ) -> SemanticReviewResult:
        self.calls.append(path)
        accepted = self.decisions.popleft()
        return SemanticReviewResult(accepted, "clear match" if accepted else "missing wave", "test-vlm")


@pytest.mark.parametrize("origin", ["https://example.com", "http://192.0.2.1:11434", "http://u:p@localhost"])
def test_reviewer_rejects_non_loopback_origin(origin: str):
    with pytest.raises(ValueError, match="loopback"):
        loopback_origin(origin)


def test_ollama_request_forces_cpu_only_and_bounded_context():
    reviewer = OllamaSemanticReviewer("http://127.0.0.1:11434", "qwen3-vl:2b")
    payload = reviewer.request_payload(["image"], "intent")
    assert payload["options"] == {"temperature": 0, "num_gpu": 0, "num_ctx": 4096}
    assert payload["stream"] is False
    assert payload["think"] is False


def test_semantic_disabled_never_calls_reviewer(tmp_path: Path):
    reviewer = Reviewer([])
    app = create_app(fake_settings(tmp_path), semantic_reviewer=reviewer)
    payload = request()
    payload["qa"]["semantic"] = False
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=payload).json()["id"])
    assert terminal["status"] == "succeeded"
    assert reviewer.calls == []


def test_default_rejection_is_advisory_without_retry(tmp_path: Path):
    reviewer = Reviewer([False])
    app = create_app(fake_settings(tmp_path), semantic_reviewer=reviewer)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request()).json()["id"])
        provenance = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}/provenance").json()
    assert terminal["status"] == "succeeded"
    assert len(reviewer.calls) == 1
    assert provenance["validation"][-1]["passed"] is False
    assert provenance["warnings"] == ["semantic review advisory: missing wave"]


def test_explicit_retry_selects_next_accepted_candidate(tmp_path: Path):
    reviewer = Reviewer([False, True])
    app = create_app(fake_settings(tmp_path), semantic_reviewer=reviewer)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request(retries=1)).json()["id"])
        provenance = client.get(f"/api/v1/assets/{terminal['asset_ids'][0]}/provenance").json()
    assert terminal["status"] == "succeeded"
    assert len(reviewer.calls) == 2
    assert provenance["seed"] == 42
    assert provenance["validation"][-1]["passed"] is True
    assert provenance["warnings"] == []


def test_retry_budget_exhaustion_fails_explicitly(tmp_path: Path):
    reviewer = Reviewer([False, False])
    app = create_app(fake_settings(tmp_path), semantic_reviewer=reviewer)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request(retries=1)).json()["id"])
    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "semantic_review_exhausted"
    assert len(reviewer.calls) == 2


def test_unavailable_reviewer_fails_without_review(tmp_path: Path):
    reviewer = Reviewer([], available=False)
    app = create_app(fake_settings(tmp_path), semantic_reviewer=reviewer)
    with TestClient(app) as client:
        capabilities = client.get("/api/v1/capabilities").json()["capabilities"]
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request()).json()["id"])
    assert capabilities["image.semantic_review"] == {
        "state": "unavailable",
        "reason": "local_vlm_not_installed",
    }
    assert terminal["error"]["code"] == "semantic_review_unavailable"
    assert reviewer.calls == []


def test_deterministic_failure_prevents_semantic_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reviewer = Reviewer([True])
    app = create_app(fake_settings(tmp_path), semantic_reviewer=reviewer)

    def fail_validation(_: Path):
        raise ValueError("deterministic failure")

    monkeypatch.setattr("mediaforge.jobs.validate_png", fail_validation)
    with TestClient(app) as client:
        terminal = wait_terminal(client, client.post("/api/v1/jobs", json=request()).json()["id"])
    assert terminal["status"] == "failed"
    assert terminal["error"]["code"] == "artifact_integrity_failed"
    assert reviewer.calls == []
