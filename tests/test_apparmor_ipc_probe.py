"""Diagnostic assertions do not stand in for a loaded kernel policy test."""
from __future__ import annotations

from copy import deepcopy
import errno
from importlib import import_module
from pathlib import Path
import tempfile

import pytest

probe = import_module("scripts.3ds_apparmor_ipc_probe")


def positive() -> dict:
    return {
        "mode": "profile", "returncode": 0,
        "child": {"profile": f"{probe.PROFILE} (enforce)",
                  "allowed": {"connected": True},
                  "outside": {"connected": False, "errno": errno.EACCES}},
        "received": {"allowed": "mf-owned-canary", "outside": None},
    }


def test_accepts_only_complete_positive_evidence() -> None:
    assert probe.accepted(positive())
    assert not probe.accepted({})
    for key in positive():
        record = positive()
        del record[key]
        assert not probe.accepted(record)


@pytest.mark.parametrize("key,value", [
    ("mode", "baseline"), ("returncode", 1),
    ("profile", "unconfined"), ("profile", f"{probe.PROFILE} (complain)"),
    ("allowed", {"connected": False, "errno": errno.EACCES}),
    ("outside", {"connected": True}),
    ("outside", {"connected": False, "errno": errno.ENOENT}),
    ("outside", {"connected": False, "errno": None}),
    ("received", {"allowed": None, "outside": None}),
    ("received", {"allowed": "mf-owned-canary", "outside": "mf-owned-canary"}),
])
def test_rejects_false_positive_evidence(key: str, value: object) -> None:
    record = deepcopy(positive())
    target = record if key in record else record["child"]
    target[key] = value
    assert not probe.accepted(record)


def test_real_unconfined_canary_is_failure_and_removes_only_owned_peers() -> None:
    # Short task-owned path avoids the UNIX socket address length limit.
    with tempfile.TemporaryDirectory(prefix="mf-ipc-") as directory:
        root = Path(directory)
        retained = root / "retained.txt"
        retained.write_text("keep")
        result = probe.observe(root, baseline=True)
        assert result["returncode"] == 0
        assert result["received"] == {"allowed": "mf-owned-canary", "outside": "mf-owned-canary"}
        assert result["passed"] is False
        assert result["temporary_peers_removed"] is True
        assert list(root.iterdir()) == [retained]
        assert retained.read_text() == "keep"
