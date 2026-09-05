from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .composer import CreativeCompositionRecord
from .creative_batches import CreativeBatchRecord
from .blender_operation import (
    TERMINAL_BLENDER_RUNTIME_OPERATION_STATES,
    BlenderRuntimeOperation,
    BlenderRuntimeOperationAction,
    BlenderRuntimeOperationState,
)
from .domain import Asset, ErrorDetail, Job, JobRequest, JobStatus, Provenance, StoredJobRequest
from .models.operations import (
    TERMINAL_MODEL_OPERATION_STATES,
    ModelOperation,
    ModelOperationAction,
    ModelOperationState,
)
from .paths import contained
from .profiles import Profile, ProfileInput, ReferenceCollection, ReferenceCollectionInput


logger = logging.getLogger("uvicorn.error")


class AssetInUse(RuntimeError):
    """Another asset still records this one as its parent."""

    def __init__(self, asset_id: str, child_id: str):
        super().__init__(f"{asset_id} is the parent of {child_id}")
        self.asset_id = asset_id
        self.child_id = child_id
        self.code = "asset_in_use"


class UnreadableJobRecord(RuntimeError):
    """現在の契約で厳格に読めない job 行を実行しようとした。"""

    def __init__(self, job_id: str):
        super().__init__(f"job {job_id} is not readable by the current contract")
        self.job_id = job_id


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def readable_rows(
    rows: Iterable[sqlite3.Row], model: type[_ModelT], column: str, *, kind: str
) -> list[_ModelT]:
    """行単位で読めるものだけ返す。1 行の不整合で一覧全体を落とさない。

    保存済み記録の読み出しは常に fail-soft にする。厳格な境界検査は書き込み側
    （API ingress）の責務であり、読み出しで再検証すると、契約を加法的に広げた
    版が書いた行を古い版が読めなくなる。
    """
    values: list[_ModelT] = []
    unreadable = 0
    for row in rows:
        try:
            values.append(model.model_validate_json(row[column]))
        except ValidationError:
            unreadable += 1
    if unreadable:
        logger.warning(
            "skipped %d unreadable %s record(s); the collection is still served", unreadable, kind
        )
    return values


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()
        self.db_path = self.data_dir / "media-forge.sqlite3"
        self.asset_dir = self.data_dir / "assets"
        self.work_dir = self.data_dir / "work"
        self.thumbnail_dir = self.data_dir / "thumbnails"
        self._lock = threading.RLock()
        self._listeners: list[Callable[[Job], None]] = []
        self._model_operation_listeners: list[Callable[[ModelOperation], None]] = []
        self._session_listeners: list[Callable[[str], None]] = []

    def observe(self, listener: Callable[[Job], None]) -> None:
        """Register a job-change listener. Listener failures never reach callers."""
        self._listeners.append(listener)

    def _notify(self, job: Job) -> Job:
        for listener in list(self._listeners):
            try:
                listener(job)
            except Exception:  # noqa: BLE001 - observation must not break job execution
                continue
        return job

    def observe_model_operations(self, listener: Callable[[ModelOperation], None]) -> None:
        self._model_operation_listeners.append(listener)

    def observe_session(self, listener: Callable[[str], None]) -> None:
        """Register a session-part invalidation listener.

        状態の正はサーバ側の session snapshot に置く。変わった部分の名前だけを
        通知し、workspace は必要な部分だけ読み直す。
        """
        self._session_listeners.append(listener)

    def _notify_session(self, part: str) -> None:
        for listener in list(self._session_listeners):
            try:
                listener(part)
            except Exception:  # noqa: BLE001 - observation must not break the mutation
                continue

    def _notify_model_operation(self, operation: ModelOperation) -> ModelOperation:
        for listener in list(self._model_operation_listeners):
            try:
                listener(operation)
            except Exception:  # noqa: BLE001 - observation must not break installation
                continue
        return operation

    def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.asset_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.work_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.thumbnail_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    phase TEXT,
                    progress REAL NOT NULL,
                    request_json TEXT NOT NULL,
                    asset_ids_json TEXT NOT NULL,
                    error_json TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    host_managed INTEGER NOT NULL DEFAULT 0,
                    profile_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    metadata_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    storage_name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at DESC);
                CREATE TABLE IF NOT EXISTS reference_collections (
                    id TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    subject TEXT PRIMARY KEY,
                    values_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_operations (
                    id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    state TEXT NOT NULL,
                    bytes_total INTEGER NOT NULL,
                    bytes_done INTEGER NOT NULL,
                    error_code TEXT,
                    error_message TEXT,
                    host_job_id TEXT,
                    result_json TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_model_operations_created
                    ON model_operations(created_at DESC);
                CREATE TABLE IF NOT EXISTS blender_runtime_operations (
                    id TEXT PRIMARY KEY,
                    runtime_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    action TEXT NOT NULL,
                    state TEXT NOT NULL,
                    bytes_total INTEGER NOT NULL,
                    bytes_done INTEGER NOT NULL,
                    error_code TEXT,
                    error_message TEXT,
                    result_json TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_blender_runtime_operations_created
                    ON blender_runtime_operations(created_at DESC);
                CREATE TABLE IF NOT EXISTS creative_batches (
                    id TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_creative_batches_created
                    ON creative_batches(created_at DESC);
                CREATE TABLE IF NOT EXISTS creative_compositions (
                    id TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_creative_compositions_created
                    ON creative_compositions(created_at DESC);
                """
            )
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(jobs)")}
            if "host_managed" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN host_managed INTEGER NOT NULL DEFAULT 0")
            if "profile_snapshot_json" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN profile_snapshot_json TEXT NOT NULL DEFAULT '{}'")
            if "cleared_at" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN cleared_at TEXT")
            model_operation_columns = {
                str(row["name"]) for row in connection.execute("PRAGMA table_info(model_operations)")
            }
            if "host_job_id" not in model_operation_columns:
                connection.execute("ALTER TABLE model_operations ADD COLUMN host_job_id TEXT")
            if "result_json" not in model_operation_columns:
                connection.execute("ALTER TABLE model_operations ADD COLUMN result_json TEXT")
            connection.execute(
                """UPDATE jobs SET status = ?, phase = NULL,
                   error_json = ?, updated_at = ? WHERE status = ?""",
                (
                    JobStatus.FAILED,
                    json.dumps({"code": "service_restarted", "message": "Service restarted while the worker was running"}),
                    utc_now(),
                    JobStatus.RUNNING,
                ),
            )
            blender_terminal = tuple(
                state.value for state in TERMINAL_BLENDER_RUNTIME_OPERATION_STATES
            )
            connection.execute(
                f"""UPDATE blender_runtime_operations SET state = ?, error_code = NULL,
                    error_message = NULL, updated_at = ?
                    WHERE cancel_requested = 0 AND state NOT IN ({','.join('?' * len(blender_terminal))})""",
                (BlenderRuntimeOperationState.QUEUED, utc_now(), *blender_terminal),
            )
            connection.execute(
                f"""UPDATE blender_runtime_operations SET state = ?, updated_at = ?
                    WHERE cancel_requested = 1 AND state NOT IN ({','.join('?' * len(blender_terminal))})""",
                (BlenderRuntimeOperationState.CANCELED, utc_now(), *blender_terminal),
            )
            connection.execute(
                """UPDATE model_operations SET state = ?, error_code = ?,
                   error_message = ?, updated_at = ?
                   WHERE action = ? AND cancel_requested = 0
                   AND state NOT IN (?, ?, ?)""",
                (
                    ModelOperationState.FAILED,
                    "host_context_lost",
                    "Service restarted after the short-lived ControlDeck evaluation credential was lost",
                    utc_now(),
                    ModelOperationAction.EVALUATE,
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                ),
            )
            connection.execute(
                """UPDATE model_operations SET state = ?, updated_at = ?
                   WHERE action = ? AND cancel_requested = 1
                   AND state NOT IN (?, ?, ?)""",
                (
                    ModelOperationState.CANCELED,
                    utc_now(),
                    ModelOperationAction.EVALUATE,
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                ),
            )
            connection.execute(
                """UPDATE model_operations SET state = ?, error_code = NULL,
                   error_message = NULL, updated_at = ?
                   WHERE action != ? AND state NOT IN (?, ?, ?) AND cancel_requested = 0""",
                (
                    ModelOperationState.QUEUED,
                    utc_now(),
                    ModelOperationAction.EVALUATE,
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                ),
            )
            connection.execute(
                """UPDATE model_operations SET state = ?, updated_at = ?
                   WHERE action != ? AND state NOT IN (?, ?, ?) AND cancel_requested = 1""",
                (
                    ModelOperationState.CANCELED,
                    utc_now(),
                    ModelOperationAction.EVALUATE,
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                ),
            )
            connection.execute(
                """UPDATE jobs SET status = ?, phase = NULL,
                   error_json = ?, updated_at = ?
                   WHERE status = ? AND host_managed = 1""",
                (
                    JobStatus.FAILED,
                    json.dumps({
                        "code": "host_context_lost",
                        "message": "Service restarted after the short-lived ControlDeck job credential was lost",
                    }),
                    utc_now(),
                    JobStatus.QUEUED,
                ),
            )
        for entry in self.work_dir.iterdir():
            bounded = contained(self.work_dir, entry)
            if bounded.is_dir():
                shutil.rmtree(bounded)
            else:
                bounded.unlink()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def create_job(
        self,
        request: JobRequest,
        *,
        host_managed: bool = False,
        profile_snapshot: dict[str, Any] | None = None,
        initial_status: JobStatus = JobStatus.QUEUED,
        initial_phase: str | None = None,
    ) -> Job:
        now = utc_now()
        job_id = f"job_{uuid.uuid4().hex}"
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO jobs
                   (id, status, phase, progress, request_json, asset_ids_json, error_json,
                    cancel_requested, host_managed, profile_snapshot_json, created_at, updated_at)
                   VALUES (?, ?, ?, 0, ?, '[]', NULL, 0, ?, ?, ?, ?)""",
                (
                    job_id,
                    initial_status,
                    initial_phase,
                    request.model_dump_json(),
                    int(host_managed),
                    json.dumps(profile_snapshot or {}, separators=(",", ":")),
                    now,
                    now,
                ),
            )
        return self._notify(self.get_job(job_id))

    def get_job(self, job_id: str) -> Job:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._job(row)

    def executable_job(self, job_id: str) -> Job:
        """実行経路用。現在の契約で読めない行は実行させない。

        表示は degraded で続けられるが、実行は fail-closed にする。
        """
        job = self.get_job(job_id)
        if job.record_state != "ok":
            raise UnreadableJobRecord(job_id)
        return job

    def list_jobs(self, limit: int = 100, *, include_cleared: bool = False) -> list[Job]:
        query = "SELECT * FROM jobs"
        if not include_cleared:
            query += " WHERE cleared_at IS NULL"
        query += " ORDER BY created_at DESC LIMIT ?"
        with self._connect() as connection:
            rows = connection.execute(query, (limit,)).fetchall()
        return [self._job(row) for row in rows]

    def clear_finished_jobs(self) -> int:
        """Drop settled runs from the activity list without destroying anything.

        The rows are marked, not deleted. Assets reference their job by foreign
        key, so removing the row would break the library's link back to how a
        picture was made — and that link is the whole point of keeping
        provenance. Running jobs are never cleared: hiding one would leave work
        in progress with nothing pointing at it.
        """
        settled = (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"""UPDATE jobs SET cleared_at = ?
                    WHERE cleared_at IS NULL AND status IN ({','.join('?' * len(settled))})""",
                (utc_now(), *settled),
            )
        removed = int(cursor.rowcount or 0)
        if removed:
            self._notify_session("jobs")
        return removed

    def queued_job_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM jobs WHERE status = ? AND cancel_requested = 0 ORDER BY created_at", (JobStatus.QUEUED,)
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def job_profile_snapshot(self, job_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT profile_snapshot_json FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        value = json.loads(row["profile_snapshot_json"])
        if not isinstance(value, dict):
            raise ValueError("stored profile snapshot is invalid")
        return value

    def replace_job_request(self, job_id: str, request: JobRequest) -> Job:
        """Persist the request the job will actually run.

        Direction and validation rewrite the request before generation. Keeping
        the rewritten version is what lets the record answer "what was actually
        asked for" later — and it is why closing the browser no longer loses
        the work, since the durable row now carries it.
        """
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET request_json = ?, updated_at = ? WHERE id = ?",
                (request.model_dump_json(), utc_now(), job_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(job_id)
        return self._notify(self.get_job(job_id))

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        phase: str | None = None,
        progress: float | None = None,
        asset_ids: list[str] | None = None,
        error: ErrorDetail | None = None,
    ) -> Job:
        values: dict[str, Any] = {"updated_at": utc_now()}
        if status is not None:
            values["status"] = status
        values["phase"] = phase
        if progress is not None:
            values["progress"] = progress
        if asset_ids is not None:
            values["asset_ids_json"] = json.dumps(asset_ids)
        values["error_json"] = error.model_dump_json() if error else None
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?", (*values.values(), job_id)  # noqa: S608 - fixed column names
            )
            if cursor.rowcount != 1:
                raise KeyError(job_id)
        return self._notify(self.get_job(job_id))

    def request_cancel(self, job_id: str) -> Job:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["status"] in {JobStatus.QUEUED, JobStatus.RUNNING}:
                connection.execute(
                    "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE id = ?", (utc_now(), job_id)
                )
                if row["status"] == JobStatus.QUEUED:
                    connection.execute(
                        "UPDATE jobs SET status = ?, phase = NULL, updated_at = ? WHERE id = ?",
                        (JobStatus.CANCELED, utc_now(), job_id),
                    )
        return self._notify(self.get_job(job_id))

    def cancel_requested(self, job_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT cancel_requested FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return bool(row["cancel_requested"])

    def register_asset(self, metadata: Asset, provenance: Provenance, source: Path) -> Asset:
        suffix = {
            "image/png": ".png", "image/webp": ".webp", "image/jpeg": ".jpg",
            "video/mp4": ".mp4", "video/webm": ".webm",
            "application/zip": ".zip",
            "model/gltf-binary": ".glb",
        }[metadata.mime_type]
        storage_name = f"{metadata.id}{suffix}"
        destination = contained(self.asset_dir, self.asset_dir / storage_name)
        source = source.resolve()
        destination.write_bytes(source.read_bytes())
        destination.chmod(0o600)
        sidecar = contained(self.asset_dir, self.asset_dir / f"{metadata.id}.provenance.json")
        sidecar.write_text(provenance.model_dump_json(indent=2), encoding="utf-8")
        sidecar.chmod(0o600)
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO assets (id, job_id, metadata_json, provenance_json, storage_name, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    metadata.id,
                    metadata.job_id,
                    metadata.model_dump_json(),
                    provenance.model_dump_json(),
                    storage_name,
                    metadata.created_at,
                ),
            )
        self._notify_session("library")
        return metadata

    def get_asset(self, asset_id: str) -> Asset:
        row = self._asset_row(asset_id)
        return Asset.model_validate_json(row["metadata_json"])

    def get_provenance(self, asset_id: str) -> Provenance:
        row = self._asset_row(asset_id)
        return Provenance.model_validate_json(row["provenance_json"])

    def asset_path(self, asset_id: str) -> Path:
        row = self._asset_row(asset_id)
        return contained(self.asset_dir, self.asset_dir / str(row["storage_name"]))

    def list_assets(self, limit: int = 100) -> list[Asset]:
        with self._connect() as connection:
            rows = connection.execute("SELECT metadata_json FROM assets ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return readable_rows(rows, Asset, "metadata_json", kind="asset")

    def list_asset_records(self, limit: int, before: str | None = None) -> list[tuple[Asset, Provenance]]:
        """Return asset+provenance pairs so the workspace never issues N+1 lookups."""
        query = "SELECT metadata_json, provenance_json FROM assets"
        parameters: list[object] = []
        if before:
            query += " WHERE created_at < ?"
            parameters.append(before)
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        pairs: list[tuple[Asset, Provenance]] = []
        unreadable = 0
        for row in rows:
            try:
                pairs.append((
                    Asset.model_validate_json(row["metadata_json"]),
                    Provenance.model_validate_json(row["provenance_json"]),
                ))
            except ValidationError:
                unreadable += 1
        if unreadable:
            logger.warning(
                "skipped %d unreadable asset record(s); the library page is still served", unreadable
            )
        return pairs

    def delete_asset(self, asset_id: str) -> None:
        """Remove one asset, its provenance sidecar, and its cached thumbnails.

        Refused while another asset still lists it as a parent: deleting the
        source of an edit would leave a lineage that points at nothing, and
        provenance is the thing that makes a generated file trustworthy.
        """
        row = self._asset_row(asset_id)
        with self._connect() as connection:
            # LIKE で候補を絞ってから検証する。全行を Pydantic に通すと、
            # 複数選択削除が蔵書数に比例して重くなる。
            children = connection.execute(
                "SELECT metadata_json FROM assets WHERE id != ? AND metadata_json LIKE ?",
                (asset_id, f"%{asset_id}%"),
            ).fetchall()
        for child in children:
            try:
                metadata = Asset.model_validate_json(child["metadata_json"])
            except ValidationError:
                continue
            if asset_id in metadata.parent_asset_ids:
                raise AssetInUse(asset_id, metadata.id)

        storage = contained(self.asset_dir, self.asset_dir / str(row["storage_name"]))
        sidecar = contained(self.asset_dir, self.asset_dir / f"{asset_id}.provenance.json")
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            if cursor.rowcount != 1:
                raise KeyError(asset_id)
        for path in (storage, sidecar):
            try:
                path.unlink()
            except OSError:
                # 行は消えている。孤児ファイルで一覧を壊さない。
                logger.warning("could not remove %s for deleted asset %s", path.name, asset_id)
        for thumbnail in self.thumbnail_dir.glob(f"{asset_id}*"):
            try:
                thumbnail.unlink()
            except OSError:
                continue
        self._notify_session("library")

    def get_preferences(self, subject: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT values_json FROM preferences WHERE subject = ?", (subject,)
            ).fetchone()
        return json.loads(row["values_json"]) if row else {}

    def set_preferences(self, subject: str, values: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(values, ensure_ascii=False)
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO preferences (subject, values_json, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(subject) DO UPDATE SET values_json = excluded.values_json,
                   updated_at = excluded.updated_at""",
                (subject, payload, utc_now()),
            )
        self._notify_session("preferences")
        return values

    def create_model_operation(
        self,
        model_id: str,
        action: ModelOperationAction,
        *,
        bytes_total: int,
    ) -> ModelOperation:
        now = utc_now()
        operation_id = f"modelop_{uuid.uuid4().hex}"
        with self._lock, self._connect() as connection:
            active = connection.execute(
                """SELECT id FROM model_operations WHERE model_id = ?
                   AND state NOT IN (?, ?, ?) LIMIT 1""",
                (
                    model_id,
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                ),
            ).fetchone()
            if active is not None:
                raise ValueError("a model operation is already active")
            connection.execute(
                """INSERT INTO model_operations
                   (id, model_id, action, state, bytes_total, bytes_done, error_code,
                    error_message, host_job_id, result_json, cancel_requested, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, 0, ?, ?)""",
                (operation_id, model_id, action, ModelOperationState.QUEUED, bytes_total, now, now),
            )
        return self._notify_model_operation(self.get_model_operation(operation_id))

    def create_blender_runtime_operation(
        self,
        runtime_id: str,
        version: str,
        action: BlenderRuntimeOperationAction,
        *,
        bytes_total: int,
    ) -> BlenderRuntimeOperation:
        now = utc_now()
        operation_id = f"blenderop_{uuid.uuid4().hex}"
        terminal = tuple(state.value for state in TERMINAL_BLENDER_RUNTIME_OPERATION_STATES)
        with self._lock, self._connect() as connection:
            active = connection.execute(
                f"""SELECT id FROM blender_runtime_operations WHERE runtime_id = ?
                    AND state NOT IN ({','.join('?' * len(terminal))}) LIMIT 1""",
                (runtime_id, *terminal),
            ).fetchone()
            if active is not None:
                raise ValueError("a Blender runtime operation is already active")
            connection.execute(
                """INSERT INTO blender_runtime_operations
                   (id, runtime_id, version, action, state, bytes_total, bytes_done,
                    error_code, error_message, result_json, cancel_requested, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, NULL, NULL, NULL, 0, ?, ?)""",
                (
                    operation_id, runtime_id, version, action,
                    BlenderRuntimeOperationState.QUEUED, bytes_total, now, now,
                ),
            )
        operation = self.get_blender_runtime_operation(operation_id)
        self._notify_session("blender_runtime")
        return operation

    def get_blender_runtime_operation(self, operation_id: str) -> BlenderRuntimeOperation:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM blender_runtime_operations WHERE id = ?", (operation_id,)
            ).fetchone()
        if row is None:
            raise KeyError(operation_id)
        return self._blender_runtime_operation(row)

    def list_blender_runtime_operations(self, limit: int = 50) -> list[BlenderRuntimeOperation]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM blender_runtime_operations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._blender_runtime_operation(row) for row in rows]

    def resumable_blender_runtime_operation_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id FROM blender_runtime_operations
                   WHERE state = ? AND cancel_requested = 0 ORDER BY created_at""",
                (BlenderRuntimeOperationState.QUEUED,),
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def update_blender_runtime_operation(
        self,
        operation_id: str,
        *,
        state: BlenderRuntimeOperationState | None = None,
        bytes_done: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> BlenderRuntimeOperation:
        values: dict[str, Any] = {"updated_at": utc_now()}
        if state is not None:
            values["state"] = state
        if bytes_done is not None:
            values["bytes_done"] = bytes_done
        values["error_code"] = error_code
        values["error_message"] = error_message
        if result is not None:
            values["result_json"] = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE blender_runtime_operations SET {assignments} WHERE id = ?",  # noqa: S608
                (*values.values(), operation_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(operation_id)
        operation = self.get_blender_runtime_operation(operation_id)
        self._notify_session("blender_runtime")
        return operation

    def request_blender_runtime_operation_cancel(
        self, operation_id: str
    ) -> BlenderRuntimeOperation:
        terminal = {state.value for state in TERMINAL_BLENDER_RUNTIME_OPERATION_STATES}
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM blender_runtime_operations WHERE id = ?", (operation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            if row["state"] not in terminal:
                if row["state"] == BlenderRuntimeOperationState.QUEUED:
                    connection.execute(
                        """UPDATE blender_runtime_operations
                           SET cancel_requested = 1, state = ?, updated_at = ? WHERE id = ?""",
                        (BlenderRuntimeOperationState.CANCELED, utc_now(), operation_id),
                    )
                else:
                    connection.execute(
                        """UPDATE blender_runtime_operations
                           SET cancel_requested = 1, updated_at = ? WHERE id = ?""",
                        (utc_now(), operation_id),
                    )
        operation = self.get_blender_runtime_operation(operation_id)
        self._notify_session("blender_runtime")
        return operation

    def blender_runtime_operation_cancel_requested(self, operation_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM blender_runtime_operations WHERE id = ?",
                (operation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(operation_id)
        return bool(row["cancel_requested"])

    def get_model_operation(self, operation_id: str) -> ModelOperation:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_operations WHERE id = ?", (operation_id,)
            ).fetchone()
        if row is None:
            raise KeyError(operation_id)
        return self._model_operation(row)

    def list_model_operations(self, limit: int = 100) -> list[ModelOperation]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_operations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._model_operation(row) for row in rows]

    def clear_finished_model_operations(self) -> int:
        """Drop the settled rows so the download list is only what still matters.

        Running rows are kept whatever the caller asks: forgetting an operation
        that is still writing to disk would leave a download nobody can cancel.
        """
        with self._lock, self._connect() as connection:
            settled = sorted(state.value for state in TERMINAL_MODEL_OPERATION_STATES)
            cursor = connection.execute(
                f"DELETE FROM model_operations WHERE state IN ({','.join('?' * len(settled))})",
                settled,
            )
        return int(cursor.rowcount or 0)

    def resumable_model_operation_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id FROM model_operations WHERE state = ? AND action != ?
                   AND cancel_requested = 0
                   ORDER BY created_at""",
                (ModelOperationState.QUEUED, ModelOperationAction.EVALUATE),
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def update_model_operation(
        self,
        operation_id: str,
        *,
        state: ModelOperationState | None = None,
        bytes_done: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        host_job_id: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> ModelOperation:
        values: dict[str, Any] = {"updated_at": utc_now()}
        if state is not None:
            values["state"] = state
        if bytes_done is not None:
            values["bytes_done"] = bytes_done
        values["error_code"] = error_code
        values["error_message"] = error_message
        if host_job_id is not None:
            values["host_job_id"] = host_job_id
        if result is not None:
            values["result_json"] = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE model_operations SET {assignments} WHERE id = ?",  # noqa: S608 - fixed columns
                (*values.values(), operation_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(operation_id)
        return self._notify_model_operation(self.get_model_operation(operation_id))

    def request_model_operation_cancel(self, operation_id: str) -> ModelOperation:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM model_operations WHERE id = ?", (operation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            if row["state"] not in {state.value for state in TERMINAL_MODEL_OPERATION_STATES}:
                # まだ順番を待っているだけなら、止めるものが無い。旗を立てても
                # 走り出すまで誰も見ないので、押しても何も起きないように見える
                # （実測: cancel_requested=1 のまま queued で止まっていた）。
                # 走っていないものは、その場で終わらせる。
                if row["state"] == ModelOperationState.QUEUED:
                    connection.execute(
                        """UPDATE model_operations SET cancel_requested = 1, state = ?,
                           updated_at = ? WHERE id = ?""",
                        (ModelOperationState.CANCELED, utc_now(), operation_id),
                    )
                else:
                    connection.execute(
                        "UPDATE model_operations SET cancel_requested = 1, updated_at = ? WHERE id = ?",
                        (utc_now(), operation_id),
                    )
        return self._notify_model_operation(self.get_model_operation(operation_id))

    def model_operation_cancel_requested(self, operation_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM model_operations WHERE id = ?", (operation_id,)
            ).fetchone()
        if row is None:
            raise KeyError(operation_id)
        return bool(row["cancel_requested"])

    def create_reference_collection(self, value: ReferenceCollectionInput) -> ReferenceCollection:
        for asset_id in value.asset_ids:
            self.get_asset(asset_id)
        now = utc_now()
        result = ReferenceCollection(
            id=f"refs_{uuid.uuid4().hex}",
            created_at=now,
            updated_at=now,
            **value.model_dump(),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO reference_collections (id, value_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (result.id, result.model_dump_json(), now, now),
            )
        self._notify_session("reference_collections")
        return result

    def get_reference_collection(self, collection_id: str) -> ReferenceCollection:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM reference_collections WHERE id = ?", (collection_id,)
            ).fetchone()
        if row is None:
            raise KeyError(collection_id)
        return ReferenceCollection.model_validate_json(row["value_json"])

    def list_reference_collections(self) -> list[ReferenceCollection]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT value_json FROM reference_collections ORDER BY created_at DESC"
            ).fetchall()
        return readable_rows(rows, ReferenceCollection, "value_json", kind="reference collection")

    def delete_reference_collection(self, collection_id: str) -> None:
        if any(item.reference_collection_id == collection_id for item in self.list_profiles()):
            raise ValueError("reference collection is used by a profile")
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM reference_collections WHERE id = ?", (collection_id,))
            if cursor.rowcount != 1:
                raise KeyError(collection_id)
        self._notify_session("reference_collections")

    def create_profile(self, value: ProfileInput) -> Profile:
        if value.reference_collection_id is not None:
            self.get_reference_collection(value.reference_collection_id)
        now = utc_now()
        result = Profile(
            id=f"{value.kind}_{uuid.uuid4().hex}",
            created_at=now,
            updated_at=now,
            **value.model_dump(),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO profiles (id, value_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (result.id, result.model_dump_json(), now, now),
            )
        self._notify_session("profiles")
        return result

    def get_profile(self, profile_id: str) -> Profile:
        with self._connect() as connection:
            row = connection.execute("SELECT value_json FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            raise KeyError(profile_id)
        return Profile.model_validate_json(row["value_json"])

    def list_profiles(self) -> list[Profile]:
        with self._connect() as connection:
            rows = connection.execute("SELECT value_json FROM profiles ORDER BY created_at DESC").fetchall()
        return readable_rows(rows, Profile, "value_json", kind="profile")

    def delete_profile(self, profile_id: str) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            if cursor.rowcount != 1:
                raise KeyError(profile_id)
        self._notify_session("profiles")

    def create_creative_batch(self, value: CreativeBatchRecord) -> CreativeBatchRecord:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO creative_batches (id, value_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (value.id, value.model_dump_json(), value.created_at, value.updated_at),
            )
        self._notify_session("creative_batches")
        return value

    def update_creative_batch(self, value: CreativeBatchRecord) -> CreativeBatchRecord:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE creative_batches SET value_json = ?, updated_at = ? WHERE id = ?",
                (value.model_dump_json(), value.updated_at, value.id),
            )
            if cursor.rowcount != 1:
                raise KeyError(value.id)
        self._notify_session("creative_batches")
        return value

    def get_creative_batch(self, batch_id: str) -> CreativeBatchRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM creative_batches WHERE id = ?", (batch_id,)
            ).fetchone()
        if row is None:
            raise KeyError(batch_id)
        return CreativeBatchRecord.model_validate_json(row["value_json"])

    def list_creative_batches(self, limit: int = 100) -> list[CreativeBatchRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT value_json FROM creative_batches ORDER BY created_at DESC LIMIT ?",
                (max(1, min(100, limit)),),
            ).fetchall()
        return readable_rows(rows, CreativeBatchRecord, "value_json", kind="creative batch")

    def create_creative_composition(
        self, value: CreativeCompositionRecord
    ) -> CreativeCompositionRecord:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO creative_compositions (id, value_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (value.id, value.model_dump_json(), value.created_at, value.updated_at),
            )
        self._notify_session("creative_compositions")
        return value

    def update_creative_composition(
        self, value: CreativeCompositionRecord
    ) -> CreativeCompositionRecord:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE creative_compositions SET value_json = ?, updated_at = ? WHERE id = ?",
                (value.model_dump_json(), value.updated_at, value.id),
            )
            if cursor.rowcount != 1:
                raise KeyError(value.id)
        self._notify_session("creative_compositions")
        return value

    def get_creative_composition(self, composition_id: str) -> CreativeCompositionRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM creative_compositions WHERE id = ?", (composition_id,)
            ).fetchone()
        if row is None:
            raise KeyError(composition_id)
        return CreativeCompositionRecord.model_validate_json(row["value_json"])

    def list_creative_compositions(self, limit: int = 100) -> list[CreativeCompositionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT value_json FROM creative_compositions ORDER BY created_at DESC LIMIT ?",
                (max(1, min(100, limit)),),
            ).fetchall()
        return readable_rows(rows, CreativeCompositionRecord, "value_json", kind="creative composition")

    def _asset_row(self, asset_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if row is None:
            raise KeyError(asset_id)
        return row

    @staticmethod
    def _job(row: sqlite3.Row) -> Job:
        error = ErrorDetail.model_validate_json(row["error_json"]) if row["error_json"] else None
        request, record_state = Store._job_request(row["request_json"], job_id=str(row["id"]))
        return Job(
            id=row["id"],
            status=row["status"],
            phase=row["phase"],
            progress=row["progress"],
            request=request,
            asset_ids=json.loads(row["asset_ids_json"]),
            error=error,
            record_state=record_state,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _job_request(request_json: str, *, job_id: str) -> tuple[JobRequest, str]:
        """保存済み request を読む。厳格版で読めなければ寛容版へ落とす。

        読み出しで契約境界を再検証すると、加法的に広げた版が書いた行を
        古い版が読めず、1 行の不整合が一覧全体を落とす。行単位で degraded
        にして残し、コレクションごと失わせない。
        """
        try:
            return JobRequest.model_validate_json(request_json), "ok"
        except ValidationError as exc:
            logger.warning(
                "job %s request is not readable by the current contract; "
                "serving it as degraded (%d validation errors)",
                job_id,
                exc.error_count(),
            )
        try:
            return StoredJobRequest.model_validate_json(request_json), "degraded"
        except ValidationError:
            logger.exception("job %s request is unreadable even leniently", job_id)
            return StoredJobRequest(), "degraded"

    @staticmethod
    def _model_operation(row: sqlite3.Row) -> ModelOperation:
        return ModelOperation(
            id=row["id"], model_id=row["model_id"], action=row["action"], state=row["state"],
            bytes_total=row["bytes_total"], bytes_done=row["bytes_done"],
            error_code=row["error_code"], error_message=row["error_message"],
            host_job_id=row["host_job_id"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            cancel_requested=bool(row["cancel_requested"]), created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _blender_runtime_operation(row: sqlite3.Row) -> BlenderRuntimeOperation:
        return BlenderRuntimeOperation(
            id=row["id"], runtime_id=row["runtime_id"], version=row["version"],
            action=row["action"], state=row["state"], bytes_total=row["bytes_total"],
            bytes_done=row["bytes_done"], error_code=row["error_code"],
            error_message=row["error_message"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            cancel_requested=bool(row["cancel_requested"]), created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
