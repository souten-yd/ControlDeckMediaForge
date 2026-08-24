from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from mediaforge.domain import JobRequest, JobStatus
from mediaforge.store import AssetInUse, Store, UnreadableJobRecord


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


def _register_test_asset(
    store: Store, tmp_path: Path, asset_id: str, *, parents: list[str] | None = None
) -> Path:
    from mediaforge.domain import Asset, Provenance
    from mediaforge.store import utc_now

    path = tmp_path / f"{asset_id}.png"
    Image.new("RGBA", (8, 8), (10, 20, 30, 255)).save(path, format="PNG")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    now = utc_now()
    provenance_id = "prov_" + asset_id.removeprefix("asset_")
    job = store.create_job(JobRequest(operation="image.generate", intent="delete me"))
    common = dict(
        id=asset_id,
        job_id=job.id,
        parent_asset_ids=parents or [],
        created_at=now,
    )
    store.register_asset(
        Asset(
            **common,
            mime_type="image/png",
            width=8,
            height=8,
            size_bytes=path.stat().st_size,
            sha256=digest,
            suggested_filename=f"{asset_id}.png",
            provenance_id=provenance_id,
        ),
        Provenance(
            **{**common, "id": provenance_id, "asset_id": asset_id},
            operation="image.generate",
            intent="delete me",
            model_id="media-forge/test-fixture",
            model_version="1",
            weights_hash="sha256:" + "0" * 64,
            license="CC0-1.0",
            runtime_adapter="test-fixture",
            runtime_version="1",
            tool_versions={"media-forge": "test"},
            seed=0,
            parameters={},
            reference_asset_hashes={},
            postprocessing=[],
            validation=[],
            warnings=[],
            output_sha256=digest,
        ),
        path,
    )
    return path


def test_delete_asset_removes_the_row_the_bytes_and_the_sidecar(tmp_path: Path):
    """一覧から消えても中身が残っていれば、消したことにならない。"""
    store = Store(tmp_path / "state")
    store.initialize()
    asset_id = "asset_" + "a" * 32
    _register_test_asset(store, tmp_path, asset_id)
    stored = store.asset_path(asset_id)
    sidecar = store.asset_dir / f"{asset_id}.provenance.json"
    assert stored.exists() and sidecar.exists()

    store.delete_asset(asset_id)

    with pytest.raises(KeyError):
        store.get_asset(asset_id)
    assert not stored.exists()
    assert not sidecar.exists()


def test_delete_asset_refuses_while_another_asset_descends_from_it(tmp_path: Path):
    """編集元を消すと、子の来歴が存在しない親を指す。それは証拠として壊れている。"""
    store = Store(tmp_path / "state")
    store.initialize()
    parent_id = "asset_" + "b" * 32
    child_id = "asset_" + "c" * 32
    _register_test_asset(store, tmp_path, parent_id)
    _register_test_asset(store, tmp_path, child_id, parents=[parent_id])

    with pytest.raises(AssetInUse):
        store.delete_asset(parent_id)
    assert store.get_asset(parent_id).id == parent_id

    store.delete_asset(child_id)
    store.delete_asset(parent_id)


def test_clear_finished_model_operations_keeps_the_running_ones(tmp_path: Path):
    """走っているものまで忘れると、中止できないダウンロードが残る。"""
    from mediaforge.models.operations import ModelOperationState

    store = Store(tmp_path / "state")
    store.initialize()
    running = store.create_model_operation("m/one", "install", bytes_total=10)
    done = store.create_model_operation("m/two", "install", bytes_total=10)
    failed = store.create_model_operation("m/three", "install", bytes_total=10)
    store.update_model_operation(done.id, state=ModelOperationState.READY)
    store.update_model_operation(
        failed.id, state=ModelOperationState.FAILED, error_code="model_download_failed"
    )

    assert store.clear_finished_model_operations() == 2
    assert [item.id for item in store.list_model_operations()] == [running.id]
