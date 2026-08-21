from __future__ import annotations

import json

from mediaforge.config import Settings
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


def test_image_runtime_launcher_keeps_venv_path_instead_of_resolving_python_symlink(tmp_path):
    runtime = tmp_path / "runtime" / ".venv" / "bin"
    runtime.mkdir(parents=True)
    system_python = tmp_path / "system-python"
    system_python.write_text("placeholder", encoding="utf-8")
    launcher = runtime / "python"
    launcher.symlink_to(system_python)

    settings = Settings(data_dir=tmp_path / "data", image_runtime_python=launcher)

    assert settings.image_runtime_python == launcher.absolute()
    assert settings.image_runtime_python != launcher.resolve()
