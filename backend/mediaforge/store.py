from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any

from .domain import Asset, ErrorDetail, Job, JobRequest, JobStatus, Provenance
from .paths import contained
from .profiles import Profile, ProfileInput, ReferenceCollection, ReferenceCollectionInput
from .models.operations import (
    ModelOperation,
    ModelOperationAction,
    ModelOperationState,
    TERMINAL_MODEL_OPERATION_STATES,
)


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
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_model_operations_created
                    ON model_operations(created_at DESC);
                """
            )
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(jobs)")}
            if "host_managed" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN host_managed INTEGER NOT NULL DEFAULT 0")
            if "profile_snapshot_json" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN profile_snapshot_json TEXT NOT NULL DEFAULT '{}'")
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
            connection.execute(
                """UPDATE model_operations SET state = ?, error_code = NULL,
                   error_message = NULL, updated_at = ?
                   WHERE state NOT IN (?, ?, ?) AND cancel_requested = 0""",
                (
                    ModelOperationState.QUEUED,
                    utc_now(),
                    ModelOperationState.READY,
                    ModelOperationState.FAILED,
                    ModelOperationState.CANCELED,
                ),
            )
            connection.execute(
                """UPDATE model_operations SET state = ?, updated_at = ?
                   WHERE state NOT IN (?, ?, ?) AND cancel_requested = 1""",
                (
                    ModelOperationState.CANCELED,
                    utc_now(),
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
    ) -> Job:
        now = utc_now()
        job_id = f"job_{uuid.uuid4().hex}"
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO jobs
                   (id, status, phase, progress, request_json, asset_ids_json, error_json,
                    cancel_requested, host_managed, profile_snapshot_json, created_at, updated_at)
                   VALUES (?, ?, NULL, 0, ?, '[]', NULL, 0, ?, ?, ?, ?)""",
                (
                    job_id,
                    JobStatus.QUEUED,
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

    def list_jobs(self, limit: int = 100) -> list[Job]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._job(row) for row in rows]

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
        suffix = {"image/png": ".png", "image/webp": ".webp", "image/jpeg": ".jpg"}[metadata.mime_type]
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
        return [Asset.model_validate_json(row["metadata_json"]) for row in rows]

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
        return [
            (
                Asset.model_validate_json(row["metadata_json"]),
                Provenance.model_validate_json(row["provenance_json"]),
            )
            for row in rows
        ]

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
                    error_message, cancel_requested, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 0, NULL, NULL, 0, ?, ?)""",
                (operation_id, model_id, action, ModelOperationState.QUEUED, bytes_total, now, now),
            )
        return self._notify_model_operation(self.get_model_operation(operation_id))

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

    def resumable_model_operation_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id FROM model_operations WHERE state = ? AND cancel_requested = 0
                   ORDER BY created_at""",
                (ModelOperationState.QUEUED,),
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
    ) -> ModelOperation:
        values: dict[str, Any] = {"updated_at": utc_now()}
        if state is not None:
            values["state"] = state
        if bytes_done is not None:
            values["bytes_done"] = bytes_done
        values["error_code"] = error_code
        values["error_message"] = error_message
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
        return [ReferenceCollection.model_validate_json(row["value_json"]) for row in rows]

    def delete_reference_collection(self, collection_id: str) -> None:
        if any(item.reference_collection_id == collection_id for item in self.list_profiles()):
            raise ValueError("reference collection is used by a profile")
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM reference_collections WHERE id = ?", (collection_id,))
            if cursor.rowcount != 1:
                raise KeyError(collection_id)

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
        return [Profile.model_validate_json(row["value_json"]) for row in rows]

    def delete_profile(self, profile_id: str) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            if cursor.rowcount != 1:
                raise KeyError(profile_id)

    def _asset_row(self, asset_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if row is None:
            raise KeyError(asset_id)
        return row

    @staticmethod
    def _job(row: sqlite3.Row) -> Job:
        error = ErrorDetail.model_validate_json(row["error_json"]) if row["error_json"] else None
        return Job(
            id=row["id"],
            status=row["status"],
            phase=row["phase"],
            progress=row["progress"],
            request=JobRequest.model_validate_json(row["request_json"]),
            asset_ids=json.loads(row["asset_ids_json"]),
            error=error,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _model_operation(row: sqlite3.Row) -> ModelOperation:
        return ModelOperation(
            id=row["id"], model_id=row["model_id"], action=row["action"], state=row["state"],
            bytes_total=row["bytes_total"], bytes_done=row["bytes_done"],
            error_code=row["error_code"], error_message=row["error_message"],
            cancel_requested=bool(row["cancel_requested"]), created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
