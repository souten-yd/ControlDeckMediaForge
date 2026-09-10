"""Read-only source DB backup and isolated setup-journal migration/restart acceptance.

This does not exercise Host authentication or install the new core.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from mediaforge.blender_operation import BlenderRuntimeOperationAction as Action
from mediaforge.blender_operation import BlenderRuntimeOperationState as State
from mediaforge.store import Store


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def fingerprints(connection: sqlite3.Connection, columns: dict[str, list[str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for table, names in columns.items():
        # Identifiers come only from SQLite's own schema, never from a public request.
        rows = connection.execute(
            f"SELECT {','.join(quote_identifier(name) for name in names)} FROM {quote_identifier(table)}"
        ).fetchall()
        encoded = sorted(repr(tuple(row)) for row in rows)
        result[table] = {"rows": len(rows), "sha256": hashlib.sha256(
            json.dumps(encoded, ensure_ascii=True).encode()).hexdigest()}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    source_path = args.source_db.resolve(strict=True)
    evidence = args.evidence_dir.resolve()
    evidence.mkdir(mode=0o700, parents=True, exist_ok=False)
    store = Store(evidence)
    with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(store.db_path) as target:
            source.backup(target)
    with sqlite3.connect(store.db_path) as connection:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        columns = {table: [row[1] for row in connection.execute(
            'PRAGMA table_info("' + table.replace('"', '""') + '")')] for table in tables}
        before = fingerprints(connection, columns)
    store.initialize()
    with sqlite3.connect(store.db_path) as connection:
        after = fingerprints(connection, columns)
    assert before == after, "Migration/restart changed existing records in the isolated copy"

    owned = store.create_blender_runtime_operation(
        "journal-acceptance-owned", "4.5.13", Action.INSTALL, bytes_total=100,
        host_owner="user:journal-acceptance", result={"retained": True})
    local = store.create_blender_runtime_operation(
        "journal-acceptance-local", "4.5.13", Action.INSTALL, bytes_total=100)
    store.bind_blender_runtime_host_job(owned.id, "user:journal-acceptance", "journal_child")
    store.update_blender_runtime_operation(owned.id, state=State.DOWNLOADING, bytes_done=42)
    restarted = Store(evidence)
    restarted.initialize()
    record = restarted.get_blender_runtime_operation(owned.id)
    assert record.state == State.FAILED and record.error_code == "host_context_lost"
    assert record.bytes_done == 42 and record.result == {"retained": True}
    assert owned.id not in restarted.resumable_blender_runtime_operation_ids()
    assert local.id in restarted.resumable_blender_runtime_operation_ids()
    journal = restarted.blender_runtime_host_journal(owned.id, "user:journal-acceptance")
    assert journal["terminal"]["status"] == "failed" and not journal["sent"]
    observations = {"passed": True, "scope": "isolated copy; not Host authentication",
                    "existing_tables": before, "owned_operation": owned.id,
                    "local_operation": local.id, "host_journal": journal}
    (evidence / "observations.json").write_text(
        json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "tables_preserved": len(before),
                      "rows_preserved": sum(value["rows"] for value in before.values()),
                      "owned_state": record.state, "local_resumable": True,
                      "evidence_dir": str(evidence)}))


if __name__ == "__main__":
    main()
