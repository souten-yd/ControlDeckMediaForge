from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
from typing import Iterator

import pytest

from mediaforge import library
from mediaforge.blender_runtime import ResolvedBlenderRuntime
from mediaforge.scene_workspace import BLEND_CHUNK_BYTES, MAX_BLEND_BYTES, SceneWorkspace
from mediaforge.scenes import SceneError, SceneRevisionInput
from mediaforge.store import Store
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
        "import base64,json,pathlib,time\n"
        f"time.sleep({delay!r})\n"
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
        now=lambda: clock[0],
        process_timeout_sec=0.2,
    )
    workspace.initialize()
    return store, workspace, resolver


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
