from __future__ import annotations

import json

from mediaforge.environment import setup_snapshot


def test_setup_snapshot_reads_precomputed_status(monkeypatch, tmp_path):
    status = tmp_path / "environment-status.json"
    expected = {
        "status": "setup_required",
        "setup": [{"id": "gpu", "label": "GPU verification", "state": "checking"}],
    }
    status.write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setenv("MEDIA_FORGE_ENV_STATUS_FILE", str(status))

    assert setup_snapshot() == expected


def test_setup_snapshot_fails_closed_when_file_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIA_FORGE_ENV_STATUS_FILE", str(tmp_path / "missing.json"))

    snapshot = setup_snapshot()

    assert snapshot is not None
    assert snapshot["status"] == "setup_required"
    assert snapshot["setup"][0]["state"] == "error"
