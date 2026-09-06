"""Real Blender material candidate acceptance in a NEW isolated data directory.

Run with MediaForge core Python and PYTHONPATH=backend:. No Host credentials,
installed database/service, or public scene are used. The runtime is read-only.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time

from PIL import Image

from mediaforge.app import create_app
from mediaforge.asset_import import import_image_asset
from mediaforge.config import Settings
from mediaforge.material_binding import MaterialBinding
from mediaforge.scene_material_preview import MaterialPreviewManager
from mediaforge.scene_workspace import BLEND_CHUNK_BYTES


async def run(args: argparse.Namespace) -> dict:
    args.data_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    app = create_app(Settings(data_dir=args.data_dir, blender_legacy_runtime_root=args.legacy_runtime_root))
    store = app.state.store
    store.initialize()
    workspace = app.state.scene_workspace
    workspace.initialize()
    assert workspace.resolver.register_legacy()
    runtime = workspace.resolver.resolve_g8()
    assert runtime is not None
    source = args.data_dir / "original.blend"
    expression = (
        "import bpy; "
        "obj=bpy.data.objects['Cube']; "
        "mat=bpy.data.materials.new('Preview material'); mat.use_nodes=True; "
        "obj.data.materials.clear(); obj.data.materials.append(mat); "
        f"bpy.ops.wm.save_as_mainfile(filepath={str(source)!r})"
    )
    subprocess.run([str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
                    "--python-expr", expression], check=True, timeout=60, capture_output=True)
    content = source.read_bytes()
    upload = workspace.begin_upload("local", size=len(content), sha256=hashlib.sha256(content).hexdigest(), name="Material preview acceptance")
    for offset in range(0, len(content), BLEND_CHUNK_BYTES):
        chunk = content[offset:offset + BLEND_CHUNK_BYTES]
        workspace.append_upload("local", upload["upload_id"], offset, chunk, hashlib.sha256(chunk).hexdigest())
    imported = await workspace.commit_upload("local", upload["upload_id"])
    image = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 80, 200)).save(image, format="PNG")
    texture = import_image_asset(store, image.getvalue(), purpose="source")
    scene_id = imported["scene"]["id"]
    binding = MaterialBinding(source_revision_id=imported["revision"]["id"], image_asset_id=texture.id,
                              object_name="Cube", material_slot=0, channel="base_color", uv_map="UVMap")
    manager = MaterialPreviewManager(workspace)
    manager.initialize()
    before = workspace.catalog.get("local", scene_id)
    assets_before = [item.id for item in store.list_assets()]
    started = time.monotonic()
    try:
        first = await manager.prepare("local", "acceptance", scene_id, binding)
        prepare_sec = time.monotonic() - started
        assert before == workspace.catalog.get("local", scene_id)
        assert assets_before == [item.id for item in store.list_assets()]
        await manager.discard("local", "acceptance", first["candidate_id"])
        assert before == workspace.catalog.get("local", scene_id)
        assert assets_before == [item.id for item in store.list_assets()]
        second = await manager.prepare("local", "acceptance", scene_id, binding)
        preview = await manager.read("local", "acceptance", second["candidate_id"], 0)
        assert preview["total_bytes"] == second["total_bytes"]
        started = time.monotonic()
        result = await manager.adopt("local", "acceptance", second["candidate_id"])
        adopt_sec = time.monotonic() - started
        assert result == await manager.adopt("local", "acceptance", second["candidate_id"])
        assert len(workspace.catalog.get("local", scene_id)[1]) == 2
        revision = result["revision"]
        assert revision["parent_revision_id"] == imported["revision"]["id"]
        assert store.asset_path(imported["revision"]["source_asset_id"]).read_bytes() == content
        provenance = store.get_provenance(revision["source_asset_id"])
        assert provenance.parameters["preview_source_sha256"] == store.get_asset(revision["source_asset_id"]).sha256
        assert revision["dependencies"][0]["sha256"] == texture.sha256
        assert not list(manager.root.iterdir())
        return {"runtime_version": runtime.version, "runtime_id": runtime.runtime_id,
                "scene_id": scene_id, "prepare_sec": prepare_sec, "adopt_sec": adopt_sec,
                "preview_bytes": second["total_bytes"], "preview_sha256": second["sha256"],
                "prepared_and_discarded_head_unchanged": True, "prepared_assets_unchanged": True,
                "original_blend_unchanged": True, "adopted_source_matches_candidate": True,
                "adopt_retry_revision_count": 2, "candidate_directories_remaining": 0,
                "revision": revision, "not_tested": ["transport", "browser", "installed release"]}
    finally:
        await manager.cleanup("local", "acceptance")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--legacy-runtime-root", type=Path, required=True)
    args = parser.parse_args()
    evidence = asyncio.run(run(args))
    (args.data_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
