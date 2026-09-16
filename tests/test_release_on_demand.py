"""場所が要ると言われたら、時計も linger も待たずに退く。

抱えるかどうかを時計で決めると、短くすれば連続生成のたびにモデルを読み直し、
長くすれば他（音楽生成・LLM）の枠を削る。どちらに振っても片方が痛む。実測
2026-09-11: batch のあとに画像 worker が 19.4GB を抱えたまま残り、音楽生成が
300 秒待って期限切れになった。

引き金を需要にすれば、その板挟みが消える。誰も欲しがらない間は抱えたままで良く、
欲しがられた瞬間に降りる。**走っている処理は切らない。**
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from conftest import fake_settings
from mediaforge.app import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(fake_settings(tmp_path)))


def test_nothing_held_is_declared_as_nothing(tmp_path: Path):
    """抱えていないのに空でない申告をすると、頼む相手を探す側が空回りする。"""
    with _client(tmp_path) as client:
        body = client.get("/addon/v1/resources/residency").json()
        assert body["device_id"] == "gpu0"
        assert body["reserved_bytes"] == 0
        assert body["engines"] == []
        assert body["estimated"] is True


def test_asking_an_empty_add_on_to_step_aside_is_answered_honestly(tmp_path: Path):
    """空けるものが無いなら、そう答える。頼んだ側は待ち直す。"""
    with _client(tmp_path) as client:
        body = client.post("/addon/v1/resources/step-aside").json()
        assert body["released"] is False
        assert body["reason"] == "in_use_or_empty"
        assert body["freed_bytes"] == 0


def test_a_held_model_is_declared_and_released(tmp_path: Path):
    with _client(tmp_path) as client:
        manager = client.app.state.jobs
        manager._warm_worker = (object(), ("flux2-klein-4b", "a", "b", "c"))
        try:
            body = client.get("/addon/v1/resources/residency").json()
            assert body["reserved_bytes"] > 0
            assert body["engines"][0]["engine_id"] == "flux2-klein-4b"
        finally:
            manager._warm_worker = None


def test_a_running_job_keeps_its_model(tmp_path: Path):
    """使用中のものを取り上げても、取り上げられた側が落ちるだけで取り合いは解決しない。"""
    with _client(tmp_path) as client:
        manager = client.app.state.jobs
        manager._warm_worker = (object(), ("flux2-klein-4b", "a", "b", "c"))
        manager._job_tasks["job_1"] = object()
        try:
            body = client.post("/addon/v1/resources/step-aside").json()
            assert body["released"] is False
            assert manager._warm_worker is not None
        finally:
            manager._job_tasks.pop("job_1", None)
            manager._warm_worker = None
