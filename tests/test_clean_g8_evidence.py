"""Synthetic negative checks for the clean packaged G8 evidence verifier."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import zipfile

from PIL import Image
import pytest


SPEC = importlib.util.spec_from_file_location(
    "clean_g8_evidence", Path(__file__).parents[1] / "scripts/3ds_clean_g8_package_e2e.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture() -> tuple[bytes, dict, dict, dict]:
    model_json = b'{"asset":{"version":"2.0"},"scenes":[{}],"scene":0}'
    model_json += b" " * (-len(model_json) % 4)
    glb = struct.pack("<4sIIII", b"glTF", 2, 20 + len(model_json), len(model_json), 0x4E4F534A) + model_json
    png = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(png, "PNG")
    source = {"id": "asset_source", "sha256": hashlib.sha256(glb).hexdigest(), "size_bytes": len(glb)}
    manifest = {"profile": "3d.project.glb", "source": {"sha256": source["sha256"], "size_bytes": len(glb)},
                "compiler": {"blender_version": "4.5.9"}}
    for key, name, content in (("asset", "asset.glb", glb), ("preview", "preview.png", png.getvalue())):
        manifest[key] = {"filename": name, "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("asset.glb", glb)
        archive.writestr("preview.png", png.getvalue())
    content = buffer.getvalue()
    asset = {"mime_type": "application/zip", "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
             "parent_asset_ids": [source["id"]]}
    provenance = {"runtime_adapter": "blender.project-compiler", "reference_asset_hashes": {source["id"]: source["sha256"]},
                  "parameters": {"manifest": manifest}}
    return content, asset, provenance, source


def test_clean_g8_verifier_accepts_consistent_fixture() -> None:
    assert MODULE.verify_package(*fixture())["profile"] == "3d.project.glb"


@pytest.mark.parametrize("fault", ["zip_bytes", "parent", "reference_hash", "manifest"])
def test_clean_g8_verifier_rejects_inconsistent_evidence(fault: str) -> None:
    content, asset, provenance, source = copy.deepcopy(fixture())
    if fault == "zip_bytes":
        content = content[:-1] + bytes([content[-1] ^ 1])
    elif fault == "parent":
        asset["parent_asset_ids"] = []
    elif fault == "reference_hash":
        provenance["reference_asset_hashes"][source["id"]] = "0" * 64
    else:
        provenance["parameters"]["manifest"]["profile"] = "wrong"
    with pytest.raises(AssertionError):
        MODULE.verify_package(content, asset, provenance, source)
