from __future__ import annotations

import json
from pathlib import Path

from mediaforge import blender_compile


ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads(
    (ROOT / "tests/fixtures/3ds-baseline-contract.json").read_text(encoding="utf-8")
)


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_3d_studio_keeps_existing_addon_identity_and_contributions() -> None:
    expected = BASELINE["addon"]
    addon = _json("addon.json")

    assert addon["api_version"] == expected["api_version"]
    assert addon["id"] == expected["id"]
    assert addon["requires"]["addon_contract"] == expected["requires_addon_contract"]
    view = next(
        item for item in addon["contributions"]["embedded_views"]
        if item["id"] == expected["embedded_view_id"]
    )
    assert view["mobile"] == expected["mobile"]
    assert set(expected["workflow_executors"]).issubset(
        {item["id"] for item in addon["contributions"]["workflow_executors"]}
    )
    assert set(expected["agent_tools"]).issubset(
        {item["id"] for item in addon["contributions"]["agent_tools"]}
    )


def test_3d_studio_public_extensions_remain_additive_to_frozen_contract() -> None:
    expected = BASELINE["public_contract"]
    jobs = _json("schemas/job-request.json")
    assets = _json("schemas/asset.json")

    assert set(expected["job_operations"]).issubset(jobs["properties"]["operation"]["enum"])
    assert set(expected["asset_mime_types"]).issubset(assets["properties"]["mime_type"]["enum"])
    assert expected["g8_profile"] == "3d.project.glb"
    assert expected["g8_compile_options_schema"] == "3d.compile-options@1"
    assert [
        blender_compile.GLB_NAME,
        blender_compile.MANIFEST_NAME,
        blender_compile.PREVIEW_NAME,
    ] == expected["g8_package_entries"]


def test_3d_studio_registers_legacy_g8_runtime_without_changing_it() -> None:
    expected = BASELINE["legacy_blender_runtime"]
    manifest = _json(expected["manifest"])

    assert manifest["version"] == expected["version"] == blender_compile.BLENDER_VERSION
    assert manifest["archive_sha256"] == expected["archive_sha256"]
    assert manifest["license"] == expected["license"]
    assert blender_compile.RUNTIME_ROOT == ROOT / expected["relative_root"]
    assert blender_compile.BLENDER_EXECUTABLE == blender_compile.RUNTIME_ROOT / "install/blender"
