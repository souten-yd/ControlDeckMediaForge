"""Fault injection must preserve permissions and stay in one working copy."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import stat
import sqlite3
from types import ModuleType

import pytest


def diagnostic() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/3ds_save_conflict_cleanup_installed_e2e.py"
    spec = importlib.util.spec_from_file_location("autosave_diagnostic", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("fail", [False, True])
def test_owned_write_fault_restores_permissions(tmp_path: Path, fail: bool) -> None:
    parent = tmp_path / ("working_" + "a" * 32)
    parent.mkdir(mode=0o700)
    candidate = parent / "scene.blend"
    candidate.write_bytes(b"BLENDERprevious")
    try:
        with diagnostic().deny_owned_snapshot_write(candidate, tmp_path):
            assert stat.S_IMODE(parent.stat().st_mode) == 0o500
            if fail:
                raise ValueError("test")
    except ValueError:
        assert fail
    assert stat.S_IMODE(parent.stat().st_mode) == 0o700
    assert candidate.read_bytes() == b"BLENDERprevious"


def test_fault_rejects_symlink_and_foreign_root(tmp_path: Path) -> None:
    module = diagnostic()
    parent = tmp_path / ("working_" + "a" * 32)
    parent.mkdir(mode=0o700)
    candidate = parent / "scene.blend"
    target = tmp_path / "foreign.blend"
    target.write_bytes(b"BLENDERprevious")
    candidate.symlink_to(target)
    with pytest.raises(AssertionError):
        with module.deny_owned_snapshot_write(candidate, tmp_path):
            pytest.fail("symlink accepted")
    candidate.unlink()
    candidate.write_bytes(b"BLENDERprevious")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    with pytest.raises(AssertionError):
        with module.deny_owned_snapshot_write(candidate, foreign):
            pytest.fail("foreign root accepted")
    assert stat.S_IMODE(parent.stat().st_mode) == 0o700


@pytest.mark.parametrize("session_id,user_id", [
    ("../foreign", 16), ("blendersession_" + "a" * 32, 0),
    ("blendersession_" + "a" * 32, True),
])
def test_expiry_identity_validation_precedes_host_import(session_id: str, user_id: int) -> None:
    with pytest.raises(AssertionError):
        diagnostic().expire_owned_gateway(session_id, user_id)


@pytest.mark.parametrize("case", ["invalid_id", "other_gui", "no_owned_gui", "active_job"])
def test_core_restart_refuses_unscoped_or_busy_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    module = diagnostic()
    monkeypatch.setattr(module, "DATA", tmp_path)
    session = "blendersession_" + "a" * 32
    with sqlite3.connect(tmp_path / "media-forge.sqlite3") as db:
        db.execute("create table blender_web_sessions(id text,state text)")
        db.execute("create table jobs(status text)")
        if case != "no_owned_gui":
            db.execute("insert into blender_web_sessions values (?, 'ready')", (session,))
        if case == "other_gui":
            db.execute("insert into blender_web_sessions values ('other','ready')")
        if case == "active_job":
            db.execute("insert into jobs values ('running')")
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("No service command may run before the idle/ownership gate")
    monkeypatch.setattr(module.subprocess, "check_output", forbidden)
    monkeypatch.setattr(module.subprocess, "run", forbidden)
    with pytest.raises(AssertionError):
        module.restart_installed_core("../foreign" if case == "invalid_id" else session)
