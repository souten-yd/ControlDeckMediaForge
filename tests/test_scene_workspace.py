from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import io
from pathlib import Path
from typing import Iterator
import uuid

import pytest
from PIL import Image

from mediaforge import library
from mediaforge.blender_runtime import ResolvedBlenderRuntime
from mediaforge.domain import Asset, JobRequest, Provenance
from mediaforge.material_binding import MaterialBinding
from mediaforge.scene_workspace import BLEND_CHUNK_BYTES, MAX_BLEND_BYTES, SceneWorkspace
from mediaforge.scenes import SceneError, SceneRevisionInput
from mediaforge.store import AssetInUse, Store, utc_now
from test_glb_import import glb_bytes


RUNTIME_ID = "blender-4.5.9-linux-x64"


class FakeResolver:
    def __init__(self, runtime: ResolvedBlenderRuntime):
        self.runtime = runtime
        self.references = 0

    @contextmanager
    def active_reference(self) -> Iterator[ResolvedBlenderRuntime]:
        self.references += 1
        try:
            yield self.runtime
        finally:
            self.references -= 1

    @contextmanager
    def runtime_reference(self, runtime_id: str) -> Iterator[ResolvedBlenderRuntime | None]:
        self.references += 1
        try:
            yield self.runtime if runtime_id == self.runtime.runtime_id else None
        finally:
            self.references -= 1

    def resolve_registered(self, runtime_id: str) -> ResolvedBlenderRuntime | None:
        return self.runtime if runtime_id == self.runtime.runtime_id else None


def fake_scene_workspace(
    tmp_path: Path, *, now: list[datetime] | None = None, delay: float = 0
) -> tuple[Store, SceneWorkspace, FakeResolver]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    preview = base64.b64encode(glb_bytes()).decode("ascii")
    executable = tmp_path / "fake-blender"
    executable.write_text(
        "#!/usr/bin/python3\n"
        "import base64,json,pathlib,shutil,sys,time\n"
        f"time.sleep({delay!r})\n"
        "if '--action' in sys.argv:\n"
        " action=sys.argv[sys.argv.index('--action')+1]\n"
        " result={'schema_version':'media-forge.material-operation-result@1',"
        "'blender_version':'4.5.9','background':True,'autoexec_disabled':True,'action':action}\n"
        " if action=='inspect':\n"
        "  result.update({'targets':[{'object_name':'Cube','material_slots':[{'index':0,'name':'Material'}],'uv_maps':['UVMap']}],'binding':None})\n"
        " else:\n"
        "  binding=json.loads(pathlib.Path('binding.json').read_text())\n"
        "  if binding['object_name']!='Cube' or binding['uv_map']!='UVMap': sys.exit(3)\n"
        "  shutil.copyfile('scene.blend','bound.blend')\n"
        "  with pathlib.Path('bound.blend').open('ab') as stream: stream.write(b'-material-bound')\n"
        "  result.update({'targets':None,'binding':{'object_name':binding['object_name'],"
        "'material_slot':binding['material_slot'],'material_name':'Material · MediaForge',"
        "'channel':binding['channel'],'uv_map':binding['uv_map'],'packed':True,"
        "'texture_sha256':binding['texture_sha256']}})\n"
        " pathlib.Path('result.json').write_text(json.dumps(result))\n"
        " sys.exit(0)\n"
        f"pathlib.Path('preview.glb').write_bytes(base64.b64decode({preview!r}))\n"
        "pathlib.Path('result.json').write_text(json.dumps({"
        "'schema_version':'media-forge.blender-scene-validation@1',"
        "'blender_version':'4.5.9','background':True,'autoexec_disabled':True,"
        "'objects':1,'meshes':1,'vertices':3,'triangles':1,'materials':0,"
        "'images':0,'animations':0,'text_blocks':0,'linked_libraries':0,"
        "'external_images':0,'unit_meters':1.0}))\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    worker = tmp_path / "trusted-worker.py"
    worker.write_text("# test fixture\n", encoding="utf-8")
    material_worker = tmp_path / "trusted-material-worker.py"
    material_worker.write_text("# test fixture\n", encoding="utf-8")
    runtime = ResolvedBlenderRuntime(
        runtime_id=RUNTIME_ID,
        version="4.5.9",
        ownership="managed",
        root=tmp_path,
        executable=executable,
        manifest_path=tmp_path / "manifest.json",
        trusted_worker=worker,
        archive_sha256="0" * 64,
    )
    resolver = FakeResolver(runtime)
    store = Store(tmp_path / "data")
    store.initialize()
    clock = now or [datetime(2026, 9, 5, 12, 0, tzinfo=UTC)]
    workspace = SceneWorkspace(
        store,
        resolver,  # type: ignore[arg-type]
        worker,
        material_worker=material_worker,
        now=lambda: clock[0],
        process_timeout_sec=0.2,
    )
    workspace.initialize()
    return store, workspace, resolver


def register_image(store: Store, root: Path, *, mime_type: str = "image/png") -> Asset:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (80, 140, 210)).save(buffer, format="PNG")
    content = buffer.getvalue()
    source = root / f"texture-{uuid.uuid4().hex}.png"
    source.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    asset_id = f"asset_{uuid.uuid4().hex}"
    provenance_id = f"prov_{uuid.uuid4().hex}"
    job = store.create_job(JobRequest(operation="media.inspect", intent="texture fixture"))
    now = utc_now()
    asset = Asset(
        id=asset_id,
        job_id=job.id,
        parent_asset_ids=[],
        mime_type=mime_type,
        width=8,
        height=6,
        size_bytes=len(content),
        sha256=digest,
        suggested_filename="texture.png",
        provenance_id=provenance_id,
        created_at=now,
    )
    provenance = Provenance(
        id=provenance_id,
        asset_id=asset_id,
        parent_asset_ids=[],
        operation="asset.import",
        intent="texture fixture",
        model_id="none",
        model_version="0",
        weights_hash="none",
        license="user-provided",
        runtime_adapter="test",
        runtime_version="1.0.0",
        tool_versions={},
        seed=0,
        parameters={},
        reference_asset_hashes={},
        postprocessing=[],
        validation=[],
        warnings=[],
        output_sha256=digest,
        created_at=now,
    )
    return store.register_asset(asset, provenance, source)


def upload_scene(workspace: SceneWorkspace, content: bytes, *, owner: str = "user:1") -> dict:
    upload = workspace.begin_upload(
        owner,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        name="Imported cube",
        tags=["test"],
    )
    for offset in range(0, len(content), BLEND_CHUNK_BYTES):
        chunk = content[offset : offset + BLEND_CHUNK_BYTES]
        workspace.append_upload(
            owner,
            upload["upload_id"],
            offset,
            chunk,
            hashlib.sha256(chunk).hexdigest(),
        )
    return asyncio.run(workspace.commit_upload(owner, upload["upload_id"]))


def test_bounded_upload_creates_scene_and_working_commit_preserves_old_revision(
    tmp_path: Path,
) -> None:
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    content = b"BLENDER" + b"scene-v1" * 100

    imported = upload_scene(workspace, content)
    scene_id = imported["scene"]["id"]
    first = imported["revision"]
    assert first["sequence"] == 1
    assert store.asset_path(first["source_asset_id"]).read_bytes() == content
    scene_records = store.list_asset_records(10)
    projected = library.page(
        scene_records, kind="all", include_masks=False, limit=10, media_kind="3d"
    )
    assert [item["asset_id"] for item in projected["items"]] == [first["preview_asset_id"]]
    assert resolver.references == 0
    assert not any(workspace.upload_root.iterdir())

    working = workspace.acquire_working_copy("user:1", scene_id)
    assert "path" not in working.model_dump_json()
    with pytest.raises(SceneError) as locked:
        workspace.acquire_working_copy("user:1", scene_id)
    assert locked.value.code == "scene_working_locked"
    with pytest.raises(SceneError) as hidden:
        workspace.renew_working_copy("user:2", working.id)
    assert hidden.value.code == "scene_working_not_found"

    working_path = workspace.working_path_for_runtime("user:1", working.id)
    working_path.write_bytes(b"BLENDER" + b"scene-v2" * 100)
    committed = asyncio.run(workspace.commit_working_copy("user:1", working.id))
    assert committed["revision"]["sequence"] == 2
    assert committed["revision"]["parent_revision_id"] == first["id"]
    document, revisions = workspace.catalog.get("user:1", scene_id)
    assert document.revision_count == 2
    assert [item.id for item in revisions] == [first["id"], committed["revision"]["id"]]
    assert store.get_scene_working_copy("user:1", working.id).state == "committed"
    assert not (workspace.working_root / working.id).exists()
    assert store.scene_runtime_reference_count(RUNTIME_ID) == 1

    released = workspace.acquire_working_copy("user:1", scene_id)
    assert workspace.release_working_copy("user:1", released.id).state == "released"
    assert not (workspace.working_root / released.id).exists()


def test_restore_revision_clones_validated_assets_and_preserves_linear_history(
    tmp_path: Path,
) -> None:
    store, workspace, _resolver = fake_scene_workspace(tmp_path)
    first_bytes = b"BLENDER" + b"first-version" * 100
    imported = upload_scene(workspace, first_bytes)
    scene_id = imported["scene"]["id"]
    first = imported["revision"]
    working = workspace.acquire_working_copy("user:1", scene_id)
    second_bytes = b"BLENDER" + b"second-version" * 100
    workspace.working_path_for_runtime("user:1", working.id).write_bytes(second_bytes)
    second = asyncio.run(workspace.commit_working_copy("user:1", working.id))["revision"]

    restored = workspace.restore_revision("user:1", scene_id, second["id"], first["id"])
    third = restored["revision"]
    assert restored["restored_from_revision_id"] == first["id"]
    assert third["sequence"] == 3 and third["parent_revision_id"] == second["id"]
    assert third["source_asset_id"] not in {first["source_asset_id"], second["source_asset_id"]}
    assert third["preview_asset_id"] not in {first["preview_asset_id"], second["preview_asset_id"]}
    assert store.asset_path(third["source_asset_id"]).read_bytes() == first_bytes
    assert store.asset_path(second["source_asset_id"]).read_bytes() == second_bytes
    provenance = store.get_provenance(third["source_asset_id"])
    assert provenance.operation == "scene.revision.restore"
    assert provenance.parameters == {
        "scene_id": scene_id,
        "base_revision_id": second["id"],
        "restored_revision_id": first["id"],
    }
    assert first["source_asset_id"] in provenance.parent_asset_ids
    assert second["source_asset_id"] in provenance.parent_asset_ids
    document, revisions = workspace.catalog.get("user:1", scene_id)
    assert document.current_revision_id == third["id"]
    assert [item.sequence for item in revisions] == [1, 2, 3]

    with pytest.raises(SceneError) as stale:
        workspace.restore_revision("user:1", scene_id, second["id"], first["id"])
    assert stale.value.code == "scene_revision_conflict"
    with pytest.raises(SceneError) as current:
        workspace.restore_revision("user:1", scene_id, third["id"], third["id"])
    assert current.value.code == "scene_revision_restore_invalid"


def test_restore_revision_rejects_changed_immutable_asset_without_advancing(
    tmp_path: Path,
) -> None:
    store, workspace, _resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER" + b"first" * 100)
    scene_id = imported["scene"]["id"]
    first = imported["revision"]
    working = workspace.acquire_working_copy("user:1", scene_id)
    workspace.working_path_for_runtime("user:1", working.id).write_bytes(
        b"BLENDER" + b"second" * 100
    )
    second = asyncio.run(workspace.commit_working_copy("user:1", working.id))["revision"]
    store.asset_path(first["preview_asset_id"]).write_bytes(b"changed")

    with pytest.raises(SceneError) as changed:
        workspace.restore_revision("user:1", scene_id, second["id"], first["id"])
    assert changed.value.code == "scene_revision_restore_changed"
    document, revisions = workspace.catalog.get("user:1", scene_id)
    assert document.current_revision_id == second["id"]
    assert len(revisions) == 2


def test_upload_hash_offset_size_owner_and_timeout_fail_closed(tmp_path: Path) -> None:
    _store, workspace, _resolver = fake_scene_workspace(tmp_path)
    content = b"BLENDER-scene"
    digest = hashlib.sha256(content).hexdigest()
    upload = workspace.begin_upload(
        "user:1", size=len(content), sha256=digest, name="Bounded scene"
    )
    with pytest.raises(SceneError) as busy:
        workspace.begin_upload(
            "user:1", size=len(content), sha256=digest, name="Another scene"
        )
    assert busy.value.code == "scene_upload_busy"
    with pytest.raises(SceneError) as owner:
        workspace.append_upload("user:2", upload["upload_id"], 0, content, digest)
    assert owner.value.code == "scene_upload_not_found"
    with pytest.raises(SceneError) as offset:
        workspace.append_upload("user:1", upload["upload_id"], 1, content, digest)
    assert offset.value.code == "scene_upload_offset_conflict"
    with pytest.raises(SceneError) as chunk_hash:
        workspace.append_upload("user:1", upload["upload_id"], 0, content, "0" * 64)
    assert chunk_hash.value.code == "scene_upload_chunk_invalid"
    assert workspace.cancel_upload("user:1", upload["upload_id"]) is True
    with pytest.raises(SceneError):
        workspace.begin_upload(
            "user:1", size=MAX_BLEND_BYTES + 1, sha256=digest, name="Too large"
        )

    _store, slow, _resolver = fake_scene_workspace(tmp_path / "slow", delay=1)
    slow_upload = slow.begin_upload(
        "user:1", size=len(content), sha256=digest, name="Slow scene"
    )
    slow.append_upload("user:1", slow_upload["upload_id"], 0, content, digest)
    with pytest.raises(SceneError) as timeout:
        asyncio.run(slow.commit_upload("user:1", slow_upload["upload_id"]))
    assert timeout.value.code == "scene_worker_timeout"
    assert slow.catalog.list("user:1") == []
    assert not any(slow.upload_root.iterdir())


def test_expired_writer_becomes_recovery_and_does_not_block_new_writer(tmp_path: Path) -> None:
    clock = [datetime(2026, 9, 5, 12, 0, tzinfo=UTC)]
    store, workspace, _resolver = fake_scene_workspace(tmp_path, now=clock)
    imported = upload_scene(workspace, b"BLENDER-scene")
    first = workspace.acquire_working_copy("user:1", imported["scene"]["id"])
    first_path = workspace.working_path_for_runtime("user:1", first.id)
    clock[0] += timedelta(minutes=11)

    second = workspace.acquire_working_copy("user:1", imported["scene"]["id"])

    records = {item.id: item for item in store.list_scene_working_copies("user:1")}
    assert records[first.id].state == "expired"
    assert records[second.id].state == "active"
    assert first_path.exists(), "expired bytes are retained as recovery evidence"
    assert workspace.release_working_copy("user:1", second.id).state == "released"


def test_recovery_open_copies_bytes_and_retires_only_after_explicit_success(tmp_path: Path) -> None:
    store, workspace, _resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER-recovery-source")
    scene_id = imported["scene"]["id"]
    original = workspace.acquire_working_copy("user:1", scene_id)
    source = workspace.working_path_for_runtime("user:1", original.id)
    source.write_bytes(b"BLENDER-unsaved-change")
    workspace.retain_working_copy_for_recovery("user:1", original.id)

    reopened = workspace.acquire_recovery_working_copy("user:1", scene_id, original.id)
    reopened_path = workspace.working_path_for_runtime("user:1", reopened.id)
    assert reopened_path.read_bytes() == source.read_bytes()
    reopened_path.write_bytes(b"BLENDER-new-session-change")
    assert source.read_bytes() == b"BLENDER-unsaved-change"
    assert store.get_scene_working_copy("user:1", original.id).state == "recovery"

    workspace.release_working_copy("user:1", reopened.id)
    workspace.retire_recovery_working_copy("user:1", original.id)
    assert store.get_scene_working_copy("user:1", original.id).state == "released"
    assert not source.parent.exists()


def test_recovery_open_rejects_wrong_owner_and_missing_bytes(tmp_path: Path) -> None:
    _store, workspace, _resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER-recovery-negative")
    scene_id = imported["scene"]["id"]
    candidate = workspace.acquire_working_copy("user:1", scene_id)
    workspace.retain_working_copy_for_recovery("user:1", candidate.id)

    with pytest.raises(SceneError) as hidden:
        workspace.acquire_recovery_working_copy("user:2", scene_id, candidate.id)
    assert hidden.value.code == "scene_working_not_found"

    source = workspace.working_root / candidate.id / "scene.blend"
    source.unlink()
    with pytest.raises(SceneError) as missing:
        workspace.acquire_recovery_working_copy("user:1", scene_id, candidate.id)
    assert missing.value.code == "scene_recovery_missing"


def test_working_commit_checks_lease_and_base_in_the_same_transaction(tmp_path: Path) -> None:
    store, workspace, _resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER-conflict")
    scene_id = imported["scene"]["id"]
    first = imported["revision"]
    working = workspace.acquire_working_copy("user:1", scene_id)
    workspace.catalog.commit(
        "user:1",
        scene_id,
        first["id"],
        SceneRevisionInput(
            source_asset_id=first["source_asset_id"],
            preview_asset_id=first["preview_asset_id"],
            dependencies=first["dependencies"],
            runtime_id=first["runtime_id"],
            runtime_version=first["runtime_version"],
            validation=first["validation"],
        ),
    )
    before_assets = {item.id for item in store.list_assets()}

    with pytest.raises(SceneError) as conflict:
        asyncio.run(workspace.commit_working_copy("user:1", working.id))

    assert conflict.value.code == "scene_revision_conflict"
    assert store.get_scene_working_copy("user:1", working.id).state == "recovery"
    assert (workspace.working_root / working.id / "scene.blend").is_file()
    assert {item.id for item in store.list_assets()} == before_assets


def test_material_binding_contract_rejects_channel_mismatches() -> None:
    valid = {
        "source_revision_id": "revision_" + "b" * 32,
        "image_asset_id": "asset_" + "a" * 32,
        "object_name": "Cube",
        "material_slot": 0,
        "channel": "base_color",
        "uv_map": "UVMap",
        "wrap": "repeat",
        "color_space": "srgb",
        "normal_convention": "open_gl",
    }
    assert MaterialBinding.model_validate(valid).dependency_role().startswith(
        "material.base_color."
    )
    with pytest.raises(ValueError):
        MaterialBinding.model_validate({**valid, "color_space": "non_color"})
    with pytest.raises(ValueError):
        MaterialBinding.model_validate({**valid, "normal_convention": "direct_x"})
    assert MaterialBinding.model_validate({
        **valid,
        "channel": "normal",
        "color_space": "non_color",
        "normal_convention": "direct_x",
    }).normal_convention == "direct_x"


def test_material_targets_and_apply_create_validated_revision_with_lineage(
    tmp_path: Path,
) -> None:
    store, workspace, resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER-material-source")
    scene_id = imported["scene"]["id"]
    texture = register_image(store, tmp_path)

    inspected = asyncio.run(workspace.material_targets("user:1", scene_id))
    assert inspected == {
        "schema_version": "media-forge.material-operation-result@1",
        "scene_id": scene_id,
        "revision_id": imported["revision"]["id"],
        "targets": [{
            "object_name": "Cube",
            "material_slots": [{"index": 0, "name": "Material"}],
            "uv_maps": ["UVMap"],
        }],
    }

    binding = MaterialBinding(
        source_revision_id=imported["revision"]["id"],
        image_asset_id=texture.id,
        object_name="Cube",
        material_slot=0,
        channel="base_color",
        uv_map="UVMap",
    )
    committed = asyncio.run(
        workspace.apply_material_binding("user:1", scene_id, binding)
    )

    revision = committed["revision"]
    assert revision["sequence"] == 2
    assert revision["parent_revision_id"] == imported["revision"]["id"]
    assert revision["dependencies"] == [{
        "role": binding.dependency_role(),
        "asset_id": texture.id,
        "sha256": texture.sha256,
    }]
    assert committed["binding"] == {
        "object_name": "Cube",
        "material_slot": 0,
        "material_name": "Material · MediaForge",
        "channel": "base_color",
        "uv_map": "UVMap",
        "packed": True,
        "texture_sha256": committed["binding"]["texture_sha256"],
    }
    assert store.asset_path(revision["source_asset_id"]).read_bytes().endswith(
        b"-material-bound"
    )
    provenance = store.get_provenance(revision["source_asset_id"])
    assert provenance.operation == "scene.material.bind"
    assert provenance.parent_asset_ids == [
        imported["revision"]["source_asset_id"], texture.id
    ]
    assert provenance.reference_asset_hashes == {
        imported["revision"]["source_asset_id"]: store.get_asset(
            imported["revision"]["source_asset_id"]
        ).sha256,
        texture.id: texture.sha256,
    }
    assert provenance.parameters["binding"]["image_asset_id"] == texture.id
    with pytest.raises(AssetInUse):
        store.delete_asset(texture.id)
    assert store.get_scene_working_copy(
        "user:1", next(item.id for item in store.list_scene_working_copies("user:1"))
    ).state == "committed"
    assert not any(workspace.material_root.iterdir())
    assert not any(workspace.working_root.iterdir())
    assert resolver.references == 0


def test_material_cancel_releases_the_scene_writer(tmp_path: Path) -> None:
    store, workspace, resolver = fake_scene_workspace(tmp_path, delay=0.1)
    imported = upload_scene(workspace, b"BLENDER-material-cancel")
    texture = register_image(store, tmp_path)

    async def scenario() -> None:
        task = asyncio.create_task(
            workspace.apply_material_binding(
                "user:1",
                imported["scene"]["id"],
                MaterialBinding(
                    source_revision_id=imported["revision"]["id"],
                    image_asset_id=texture.id,
                    object_name="Cube",
                    material_slot=0,
                    channel="base_color",
                    uv_map="UVMap",
                ),
            )
        )
        for _ in range(100):
            if any(
                item.state == "active"
                for item in store.list_scene_working_copies("user:1")
            ):
                break
            await asyncio.sleep(0.001)
        else:
            raise AssertionError("material worker did not acquire its scene writer")
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not any(
            item.state == "active"
            for item in store.list_scene_working_copies("user:1")
        )
        assert not any(workspace.material_root.iterdir())
        assert not any(workspace.working_root.iterdir())
        assert resolver.references == 0

    asyncio.run(scenario())


def test_material_replaces_same_target_channel_and_failures_release_writer(
    tmp_path: Path,
) -> None:
    store, workspace, _resolver = fake_scene_workspace(tmp_path)
    imported = upload_scene(workspace, b"BLENDER-material-replace")
    scene_id = imported["scene"]["id"]
    first = register_image(store, tmp_path)
    second = register_image(store, tmp_path)

    def value(
        asset_id: str,
        object_name: str = "Cube",
        source_revision_id: str | None = None,
    ) -> dict[str, object]:
        document, _ = workspace.catalog.get("user:1", scene_id)
        return {
            "source_revision_id": source_revision_id or document.current_revision_id,
            "image_asset_id": asset_id,
            "object_name": object_name,
            "material_slot": 0,
            "channel": "roughness",
            "uv_map": "UVMap",
            "wrap": "extend",
            "color_space": "non_color",
            "normal_convention": "open_gl",
        }

    asyncio.run(workspace.apply_material_binding("user:1", scene_id, value(first.id)))
    with pytest.raises(SceneError) as stale:
        asyncio.run(
            workspace.apply_material_binding(
                "user:1",
                scene_id,
                value(
                    second.id,
                    source_revision_id=imported["revision"]["id"],
                ),
            )
        )
    assert stale.value.code == "scene_revision_conflict"
    assert not any(
        item.state == "active" for item in store.list_scene_working_copies("user:1")
    )
    replaced = asyncio.run(
        workspace.apply_material_binding("user:1", scene_id, value(second.id))
    )
    assert replaced["revision"]["sequence"] == 3
    assert [item["asset_id"] for item in replaced["revision"]["dependencies"]] == [
        second.id
    ]

    with pytest.raises(SceneError) as rejected:
        asyncio.run(
            workspace.apply_material_binding(
                "user:1", scene_id, value(second.id, "Missing")
            )
        )
    assert rejected.value.code == "scene_material_rejected"
    assert not any(
        item.state == "active" for item in store.list_scene_working_copies("user:1")
    )
    assert not any(workspace.material_root.iterdir())
    assert not any(workspace.working_root.iterdir())

    archive = register_image(store, tmp_path, mime_type="application/zip")
    with pytest.raises(SceneError) as wrong_type:
        asyncio.run(
            workspace.apply_material_binding("user:1", scene_id, value(archive.id))
        )
    assert wrong_type.value.code == "scene_material_asset_invalid"
    assert not any(
        item.state == "active" for item in store.list_scene_working_copies("user:1")
    )

    changed = register_image(store, tmp_path)
    store.asset_path(changed.id).write_bytes(b"changed after registration")
    with pytest.raises(SceneError) as identity:
        asyncio.run(
            workspace.apply_material_binding("user:1", scene_id, value(changed.id))
        )
    assert identity.value.code == "scene_dependency_changed"
    assert not any(
        item.state == "active" for item in store.list_scene_working_copies("user:1")
    )
