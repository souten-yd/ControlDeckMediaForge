from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import stat
import uuid
import zipfile

import pytest

from mediaforge.domain import Asset, JobRequest, Provenance
import mediaforge.store as store_module
from mediaforge.scene_backup import SceneBackupCodec
from mediaforge.scenes import (
    SceneCatalog,
    SceneDependency,
    SceneError,
    SceneRevisionInput,
    SceneValidationCheck,
)
from mediaforge.store import Store, utc_now
from test_glb_import import glb_bytes


def register_asset(
    store: Store,
    root: Path,
    content: bytes,
    mime_type: str,
    *,
    parents: list[str] | None = None,
) -> Asset:
    asset_id = f"asset_{uuid.uuid4().hex}"
    provenance_id = f"prov_{uuid.uuid4().hex}"
    source = root / f"source-{uuid.uuid4().hex}"
    source.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    now = utc_now()
    parent_ids = parents or []
    job = store.create_job(JobRequest(operation="media.inspect", intent="backup fixture"))
    asset = Asset(
        id=asset_id,
        job_id=job.id,
        parent_asset_ids=parent_ids,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=digest,
        suggested_filename=f"fixture-{asset_id[6:14]}",
        provenance_id=provenance_id,
        created_at=now,
    )
    provenance = Provenance(
        id=provenance_id,
        asset_id=asset_id,
        parent_asset_ids=parent_ids,
        operation="scene.fixture",
        intent="backup fixture",
        model_id="none",
        model_version="0",
        weights_hash="none",
        license="CC0-1.0",
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


def scene_fixture(root: Path) -> tuple[Store, SceneCatalog, str, list[bytes]]:
    store = Store(root / "data")
    store.initialize()
    catalog = SceneCatalog(store)
    dependency_bytes = b"texture-exact-bytes"
    dependency = register_asset(store, root, dependency_bytes, "image/png")
    source1_bytes = b"BLENDER-scene-backup-v1"
    preview1_bytes = glb_bytes()
    source1 = register_asset(store, root, source1_bytes, "application/x-blender")
    preview1 = register_asset(
        store, root, preview1_bytes, "model/gltf-binary", parents=[source1.id]
    )

    def revision(source: Asset, preview: Asset) -> SceneRevisionInput:
        return SceneRevisionInput(
            source_asset_id=source.id,
            preview_asset_id=preview.id,
            dependencies=[
                SceneDependency(
                    role="texture.base_color",
                    asset_id=dependency.id,
                    sha256=dependency.sha256,
                )
            ],
            runtime_id="blender-4.5.9-linux-x64",
            runtime_version="4.5.9",
            validation=[
                SceneValidationCheck(
                    validator="blender.scene", status="passed", facts={"objects": 1}
                ),
                SceneValidationCheck(
                    validator="glb.structure", status="passed", facts={"meshes": 1}
                ),
            ],
        )

    document, first = catalog.create(
        "user:source",
        name="Backup scene",
        tags=["exact"],
        collection="Test",
        revision=revision(source1, preview1),
    )
    source2_bytes = b"BLENDER-scene-backup-v2"
    preview2_bytes = glb_bytes()
    source2 = register_asset(
        store, root, source2_bytes, "application/x-blender", parents=[source1.id]
    )
    preview2 = register_asset(
        store, root, preview2_bytes, "model/gltf-binary", parents=[source2.id]
    )
    document, _second = catalog.commit(
        "user:source", document.id, first.id, revision(source2, preview2)
    )
    return store, catalog, document.id, [
        source1_bytes,
        preview1_bytes,
        source2_bytes,
        preview2_bytes,
        dependency_bytes,
    ]


def database_counts(store: Store) -> tuple[int, int, int, int]:
    with sqlite3.connect(store.db_path) as connection:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("jobs", "assets", "scene_documents", "scene_revisions")
        )  # type: ignore[return-value]


def rewrite_archive(source: Path, target: Path, transform) -> None:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as changed:
        for info in original.infolist():
            name, content = transform(info.filename, original.read(info))
            if name is not None:
                changed.writestr(name, content)


def test_backup_has_fixed_order_and_restores_every_revision_as_a_new_scene(tmp_path: Path) -> None:
    store, catalog, scene_id, expected_bytes = scene_fixture(tmp_path)
    codec = SceneBackupCodec(store)
    codec.initialize()
    backup = codec.root / "scene.zip"

    exported = codec.export("user:source", scene_id, backup)
    with zipfile.ZipFile(backup) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
    revisions = manifest["revisions"]
    dependency_id = revisions[0]["dependencies"][0]["asset_id"]
    assert names == [
        "manifest.json",
        f"revisions/{revisions[0]['id']}/scene.blend",
        f"revisions/{revisions[0]['id']}/preview.glb",
        f"revisions/{revisions[1]['id']}/scene.blend",
        f"revisions/{revisions[1]['id']}/preview.glb",
        f"dependencies/{dependency_id}/asset",
    ]
    assert exported["schema_version"] == "media-forge.scene-backup@1"
    assert exported["sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()
    assert "owner" not in json.dumps(manifest)

    restored = codec.restore("user:restored", backup)
    restored_id = restored["scene"]["id"]
    document, restored_revisions = catalog.get("user:restored", restored_id)
    assert restored_id != scene_id
    assert document.name == "Backup scene" and document.revision_count == 2
    assert [item.sequence for item in restored_revisions] == [1, 2]
    assert restored_revisions[1].parent_revision_id == restored_revisions[0].id
    restored_paths = [
        store.asset_path(restored_revisions[0].source_asset_id),
        store.asset_path(restored_revisions[0].preview_asset_id),
        store.asset_path(restored_revisions[1].source_asset_id),
        store.asset_path(restored_revisions[1].preview_asset_id),
        store.asset_path(restored_revisions[0].dependencies[0].asset_id),
    ]
    assert [path.read_bytes() for path in restored_paths] == expected_bytes
    assert (
        restored_revisions[0].dependencies[0].asset_id
        == restored_revisions[1].dependencies[0].asset_id
    )
    assert restored_revisions[0].dependencies[0].asset_id != dependency_id
    assert all(
        store.get_provenance(asset_id).operation == "scene.restore"
        for revision in restored_revisions
        for asset_id in (revision.source_asset_id, revision.preview_asset_id)
    )
    with pytest.raises(SceneError) as hidden:
        catalog.get("user:other", restored_id)
    assert hidden.value.code == "scene_not_found"
    assert catalog.get("user:source", scene_id)[0].revision_count == 2


@pytest.mark.parametrize(
    "failure", ["missing", "tampered", "manifest", "traversal", "duplicate"]
)
def test_restore_rejects_missing_tampered_and_unsafe_members_without_partial_rows(
    tmp_path: Path, failure: str
) -> None:
    store, _catalog, scene_id, _expected = scene_fixture(tmp_path)
    codec = SceneBackupCodec(store)
    codec.initialize()
    backup = codec.root / "scene.zip"
    codec.export("user:source", scene_id, backup)
    broken = codec.root / f"{failure}.zip"
    before = database_counts(store)
    before_files = sorted(path.name for path in store.asset_dir.iterdir())

    if failure == "missing":
        rewrite_archive(
            backup,
            broken,
            lambda name, content: (None, content)
            if name.endswith("/asset")
            else (name, content),
        )
    elif failure == "tampered":
        changed = [False]

        def tamper(name: str, content: bytes):
            if name.endswith("preview.glb") and not changed[0]:
                changed[0] = True
                return name, content[:-1] + bytes([content[-1] ^ 0xFF])
            return name, content

        rewrite_archive(backup, broken, tamper)
    elif failure == "manifest":
        def tamper_manifest(name: str, content: bytes):
            if name == "manifest.json":
                value = json.loads(content)
                value["document"]["name"] = "Tampered"
                return name, json.dumps(value).encode()
            return name, content

        rewrite_archive(backup, broken, tamper_manifest)
    elif failure == "traversal":
        rewrite_archive(
            backup,
            broken,
            lambda name, content: ("../escape", content)
            if name.endswith("/asset")
            else (name, content),
        )
    else:
        rewrite_archive(backup, broken, lambda name, content: (name, content))
        with pytest.warns(UserWarning, match="Duplicate name"):
            with zipfile.ZipFile(broken, "a") as archive:
                archive.writestr("manifest.json", b"{}")

    with pytest.raises(SceneError):
        codec.restore("user:restored", broken)
    assert database_counts(store) == before
    assert sorted(path.name for path in store.asset_dir.iterdir()) == before_files
    assert not any(codec.root.glob("restore_*"))


def test_restore_rolls_back_files_and_rows_if_revision_insert_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _catalog, scene_id, _expected = scene_fixture(tmp_path)
    codec = SceneBackupCodec(store)
    codec.initialize()
    backup = codec.root / "scene.zip"
    codec.export("user:source", scene_id, backup)
    before = database_counts(store)
    before_files = sorted(path.name for path in store.asset_dir.iterdir())
    original = Store._insert_scene_revision
    inserted = [0]

    def fail_second(connection, revision):
        inserted[0] += 1
        original(connection, revision)
        if inserted[0] == 2:
            raise RuntimeError("injected restore failure")

    monkeypatch.setattr(Store, "_insert_scene_revision", staticmethod(fail_second))
    with pytest.raises(SceneError) as failed:
        codec.restore("user:restored", backup)
    assert failed.value.code == "scene_backup_restore_failed"
    assert database_counts(store) == before
    assert sorted(path.name for path in store.asset_dir.iterdir()) == before_files


def test_restore_rejects_member_count_before_extraction(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    codec = SceneBackupCodec(store)
    codec.initialize()
    excessive = codec.root / "excessive.zip"
    with zipfile.ZipFile(excessive, "w") as archive:
        archive.writestr("manifest.json", b"{}")
        for index in range(1025):
            archive.writestr(f"entry-{index}", b"x")
    with pytest.raises(SceneError) as limited:
        codec.restore("user:restored", excessive)
    assert limited.value.code == "scene_backup_invalid"


@pytest.mark.parametrize("file_type", [stat.S_IFLNK, stat.S_IFCHR])
def test_restore_rejects_link_and_device_members_before_extraction(
    tmp_path: Path, file_type: int
) -> None:
    store, _catalog, scene_id, _expected = scene_fixture(tmp_path)
    codec = SceneBackupCodec(store)
    codec.initialize()
    backup = codec.root / "scene.zip"
    codec.export("user:source", scene_id, backup)
    broken = codec.root / f"type-{file_type}.zip"
    with zipfile.ZipFile(backup) as original, zipfile.ZipFile(broken, "w") as changed:
        for index, original_info in enumerate(original.infolist()):
            content = original.read(original_info)
            if index == 1:
                info = zipfile.ZipInfo(original_info.filename)
                info.create_system = 3
                info.external_attr = (file_type | 0o600) << 16
                changed.writestr(info, content)
            else:
                changed.writestr(original_info.filename, content)

    before = database_counts(store)
    with pytest.raises(SceneError) as invalid:
        codec.restore("user:restored", broken)
    assert invalid.value.code == "scene_backup_invalid"
    assert database_counts(store) == before
    assert not any(codec.root.glob("restore_*"))


def test_backup_paths_are_private_and_export_detects_changed_asset(tmp_path: Path) -> None:
    store, _catalog, scene_id, _expected = scene_fixture(tmp_path)
    codec = SceneBackupCodec(store)
    codec.initialize()
    outside = tmp_path / "outside.zip"

    with pytest.raises(SceneError) as export_path:
        codec.export("user:source", scene_id, outside)
    assert export_path.value.code == "scene_backup_invalid"
    outside.write_bytes(b"not a zip")
    with pytest.raises(SceneError) as restore_path:
        codec.restore("user:restored", outside)
    assert restore_path.value.code == "scene_backup_invalid"

    source_asset = store.list_scene_revisions(scene_id, "user:source")[0].source_asset_id
    store.asset_path(source_asset).write_bytes(b"BLENDER-changed")
    with pytest.raises(SceneError) as changed:
        codec.export("user:source", scene_id, codec.root / "changed.zip")
    assert changed.value.code == "scene_backup_hash_changed"
    assert not (codec.root / "changed.zip").exists()


def test_restore_preserves_file_that_appears_during_atomic_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _catalog, scene_id, _expected = scene_fixture(tmp_path)
    codec = SceneBackupCodec(store)
    codec.initialize()
    backup = codec.root / "scene.zip"
    codec.export("user:source", scene_id, backup)
    before = database_counts(store)
    collision: list[Path] = []

    def collide(_source: Path, destination: Path) -> None:
        target = Path(destination)
        target.write_bytes(b"existing-concurrent-asset")
        collision.append(target)
        raise FileExistsError(target)

    monkeypatch.setattr(store_module.os, "link", collide)
    with pytest.raises(SceneError) as failed:
        codec.restore("user:restored", backup)
    assert failed.value.code == "scene_backup_conflict"
    assert database_counts(store) == before
    assert len(collision) == 1
    assert collision[0].read_bytes() == b"existing-concurrent-asset"
    assert not any(path.name.endswith(".restore") for path in store.asset_dir.iterdir())
