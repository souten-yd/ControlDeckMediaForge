from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from mediaforge.domain import JobRequest, JobStatus
from mediaforge.store import Store, UnreadableJobRecord


def test_store_recovers_interrupted_running_job_as_failed(tmp_path: Path):
    store = Store(tmp_path / "state")
    store.initialize()
    job = store.create_job(JobRequest(operation="image.generate", intent="recover me"))
    store.update_job(job.id, status=JobStatus.RUNNING, phase="generating")

    restarted = Store(tmp_path / "state")
    restarted.initialize()
    recovered = restarted.get_job(job.id)
    assert recovered.status == JobStatus.FAILED
    assert recovered.error is not None and recovered.error.code == "service_restarted"


def test_store_does_not_resume_host_managed_job_without_short_lived_credential(tmp_path: Path):
    store = Store(tmp_path / "state")
    store.initialize()
    local_job = store.create_job(JobRequest(operation="image.generate", intent="resume locally"))
    hosted_job = store.create_job(
        JobRequest(operation="image.generate", intent="must retain host authority"),
        host_managed=True,
    )

    restarted = Store(tmp_path / "state")
    restarted.initialize()

    assert restarted.get_job(local_job.id).status == JobStatus.QUEUED
    recovered = restarted.get_job(hosted_job.id)
    assert recovered.status == JobStatus.FAILED
    assert recovered.error is not None and recovered.error.code == "host_context_lost"
    assert restarted.queued_job_ids() == [local_job.id]


def test_store_removes_only_stale_entries_inside_work_directory(tmp_path: Path):
    store = Store(tmp_path / "state")
    store.initialize()
    stale = store.work_dir / "job_stale"
    stale.mkdir()
    (stale / "partial.bin").write_bytes(b"partial")
    persistent = store.data_dir / "keep.txt"
    persistent.write_text("keep", encoding="utf-8")

    Store(store.data_dir).initialize()

    assert not stale.exists()
    assert persistent.read_text(encoding="utf-8") == "keep"


def _write_raw_request(store: Store, job_id: str, request_json: str) -> None:
    with store._connect() as connection:  # noqa: SLF001 - 前方互換の再現には生の行が要る
        connection.execute("UPDATE jobs SET request_json = ? WHERE id = ?", (request_json, job_id))


FUTURE_REQUEST_JSON = json.dumps({
    "operation": "video.generate",
    "intent": "written by a newer additive contract",
    "inputs": [{"asset_id": "asset_" + "0" * 32}] * 40,
    "profile": None,
    "model_policy": "auto",
    "model_id": None,
    "constraints": {},
    "output": {"format": "mp4", "count": 1},
    "qa": {"deterministic": True, "semantic": False, "max_regeneration_attempts": 0},
    "local_only": True,
    "future_field": 7,
})


def test_one_unreadable_row_does_not_break_the_job_list(tmp_path: Path):
    """実機で inputs 21 件 / output.format=zip の 1 行が jobs.list 全体を 500 にしていた。

    保存済み行の読み出しで契約境界を再検証しないこと、そして degraded 行を
    一覧から黙って消さないことを守る。
    """
    store = Store(tmp_path / "state")
    store.initialize()
    readable = store.create_job(JobRequest(operation="image.generate", intent="readable"))
    unreadable = store.create_job(JobRequest(operation="image.generate", intent="replace me"))
    _write_raw_request(store, unreadable.id, FUTURE_REQUEST_JSON)

    items = store.list_jobs(100)

    assert {item.id for item in items} == {readable.id, unreadable.id}
    states = {item.id: item.record_state for item in items}
    assert states[readable.id] == "ok"
    assert states[unreadable.id] == "degraded"


def test_degraded_row_keeps_its_stored_request_verbatim(tmp_path: Path):
    """未知フィールドを黙って落とさない。新しい版の記録を古い版が破壊しない。"""
    store = Store(tmp_path / "state")
    store.initialize()
    job = store.create_job(JobRequest(operation="image.generate", intent="replace me"))
    _write_raw_request(store, job.id, FUTURE_REQUEST_JSON)

    served = store.get_job(job.id).model_dump(mode="json")["request"]

    assert served["operation"] == "video.generate"
    assert served["output"]["format"] == "mp4"
    assert len(served["inputs"]) == 40
    assert served["future_field"] == 7


def test_degraded_row_is_not_executable(tmp_path: Path):
    """表示は続けるが実行は fail-closed。読めない指示を推測で実行しない。"""
    store = Store(tmp_path / "state")
    store.initialize()
    job = store.create_job(JobRequest(operation="image.generate", intent="replace me"))
    _write_raw_request(store, job.id, FUTURE_REQUEST_JSON)

    assert store.get_job(job.id).record_state == "degraded"
    with pytest.raises(UnreadableJobRecord):
        store.executable_job(job.id)


def test_one_unreadable_asset_row_does_not_break_the_library(tmp_path: Path):
    """欠陥は job 固有ではない。コレクション読み出し全体で行単位に落とす。"""
    store = Store(tmp_path / "state")
    store.initialize()
    job = store.create_job(JobRequest(operation="image.generate", intent="library"))
    with store._connect() as connection:  # noqa: SLF001 - 壊れた行の再現には生の INSERT が要る
        connection.execute(
            """INSERT INTO assets (id, job_id, metadata_json, provenance_json, storage_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "asset_" + "1" * 32,
                job.id,
                json.dumps({"id": "asset_" + "1" * 32, "unreadable": True}),
                "{}",
                "missing.png",
                "2026-08-24T00:00:00+00:00",
            ),
        )

    assert store.list_assets(100) == []
    assert store.list_asset_records(100) == []
