"""Recovery verifier contracts, not substitutes for real delivery evidence."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SPEC = importlib.util.spec_from_file_location(
    "restored_delivery", Path(__file__).parents[1] / "scripts/3ds_verify_restored_delivery.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def call(status: str, *, asset_id: str = "asset_a") -> dict[str, Any]:
    return {"tool": "controldeck_addons_media_generate", "state": {
        "status": status, "input": {"operation": "asset.pack", "inputs": [{"asset_id": asset_id}]}}}


def test_exact_later_retry_retains_failure() -> None:
    failed = call("error")
    assert MODULE.recovered_failures([failed, call("completed")]) == [failed]


@pytest.mark.parametrize("calls", [
    [call("error")],
    [call("error"), call("completed", asset_id="asset_b")],
    [call("completed"), call("error")],
])
def test_unrecovered_error_is_rejected(calls: list[dict[str, Any]]) -> None:
    with pytest.raises(AssertionError):
        MODULE.recovered_failures(calls)
