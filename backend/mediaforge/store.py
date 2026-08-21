from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .domain import Asset, ErrorDetail, Job, JobRequest, JobStatus, Provenance
from .paths import contained


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()
        self.db_path = self.data_dir / "media-forge.sqlite3"
        self.asset_dir = self.data_dir / "assets"
        self.work_dir = self.data_dir / "work"
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.asset_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.work_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
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
                """
            )
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(jobs)")}
            if "host_managed" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN host_managed INTEGER NOT NULL DEFAULT 0")
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

    def create_job(self, request: JobRequest, *, host_managed: bool = False) -> Job:
        now = utc_now()
        job_id = f"job_{uuid.uuid4().hex}"
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO jobs
                   (id, status, phase, progress, request_json, asset_ids_json, error_json,
                    cancel_requested, host_managed, created_at, updated_at)
                   VALUES (?, ?, NULL, 0, ?, '[]', NULL, 0, ?, ?, ?)""",
                (job_id, JobStatus.QUEUED, request.model_dump_json(), int(host_managed), now, now),
            )
        return self.get_job(job_id)

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
        return self.get_job(job_id)

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
        return self.get_job(job_id)

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
