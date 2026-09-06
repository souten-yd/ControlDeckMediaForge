"""Reconcile explicitly selected prior E2E failures on the installed service.

Run in the Host diagnostic environment. Only mf-e2e-owned terminal fixtures
whose Host record is already interrupted are accepted. No token is written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import time

import httpx


def main() -> None:
    from app.addons import tokens
    from app.config import data_dir
    from app.features import registry

    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", action="append", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=False)
    data = data_dir()
    with sqlite3.connect(f"file:{data}/control-deck.db?mode=ro", uri=True) as host_db, sqlite3.connect(
        f"file:{data}/feature-data/media-forge/data/media-forge.sqlite3?mode=ro", uri=True
    ) as core_db:
        user = host_db.execute("SELECT id,is_active FROM users WHERE username='mf-e2e'").fetchone()
        assert user and user[1]
        installed = registry.status("media-forge")
        assert installed["version"] == "0.28.17" and installed["health"] == "healthy"
        # Other users may run jobs: only the explicitly checked terminal IDs
        # below are touched. Concurrent count changes make this smoke fail.
        before_counts = {table: core_db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                         for table in ("jobs", "assets", "scene_documents", "scene_revisions")}
        host_ids = []
        for job_id in args.job_id:
            row = core_db.execute("SELECT owner,host_job_id FROM scene_recipe_tasks WHERE job_id=?", (job_id,)).fetchone()
            assert row and row[0] == f"user:{user[0]}"
            assert core_db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone() == ("failed",)
            assert host_db.execute("SELECT status FROM jobs WHERE id=?", (row[1],)).fetchone() == ("interrupted",)
            host_ids.append(row[1])
        events = []
        start = time.monotonic()
        with httpx.Client(base_url="http://127.0.0.1:9130", timeout=20) as client:
            for operation in ("status", "cancel", "status"):
                for job_id, host_id in zip(args.job_id, host_ids, strict=True):
                    bearer = tokens.issue("media-forge", subject=str(user[0]), kind="service", actor_user_id=user[0])
                    response = client.post(f"/addon/v1/agent/job/{operation}", json={"input": {"job_id": job_id}}, headers={
                        "Authorization": f"Bearer {bearer}", "X-Control-Deck-Addon-ID": "media-forge"})
                    assert response.status_code == 200, response.status_code
                    value = response.json()
                    assert value["status"] == "failed" and value["host_terminal_sent"] is False
                    assert value["host_terminal_reconciliation"] == {
                        "host_job_id": host_id, "status": "interrupted", "disposition": "already_terminal", "terminal_matches": False}
                    events.append({"operation": operation, **value})
        after_counts = {table: core_db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in before_counts}
        assert after_counts == before_counts
        assert all(host_db.execute("SELECT status FROM jobs WHERE id=?", (host_id,)).fetchone() == ("interrupted",)
                   for host_id in host_ids)
        observed = {"version": installed["version"], "elapsed_sec": round(time.monotonic() - start, 3),
                    "counts": after_counts, "events": events}
        (args.evidence_dir / "observations.json").write_text(json.dumps(observed, indent=2) + "\n")
        print(json.dumps({"version": installed["version"], "elapsed_sec": observed["elapsed_sec"],
                          "requests": len(events), "counts_unchanged": True}))


if __name__ == "__main__":
    main()
