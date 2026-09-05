from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import uuid

import pytest
from pydantic import ValidationError

from mediaforge.domain import Asset, JobRequest, Provenance
from mediaforge.scenes import (
    SceneCatalog,
    SceneDependency,
    SceneError,
    SceneRevision,
    SceneRevisionInput,
    SceneValidationCheck,
)
from mediaforge.store import AssetInUse, Store, utc_now
from test_host_execution import host_client
from test_workspace_transport import call


RUNTIME_ID = "blender-4.5.9-linux-x64"


def _register(
    store: Store,
    tmp_path: Path,
    *,
    mime_type: str,
    content: bytes,
    parents: list[str] | None = None,
) -> Asset:
    asset_id = f"asset_{uuid.uuid4().hex}"
    provenance_id = f"prov_{uuid.uuid4().hex}"
    suffix = {
        "application/x-blender": ".blend",
        "model/gltf-binary": ".glb",
        "image/png": ".png",
    }[mime_type]
    source = tmp_path / f"{asset_id}{suffix}"
    source.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    now = utc_now()
    parent_ids = parents or []
    job = store.create_job(JobRequest(operation="image.generate", intent="scene fixture"))
    asset = Asset(
        id=asset_id,
        job_id=job.id,
        parent_asset_ids=parent_ids,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=digest,
        suggested_filename=source.name,
        provenance_id=provenance_id,
        created_at=now,
    )
    provenance = Provenance(
        id=provenance_id,
        asset_id=asset.id,
        parent_asset_ids=parent_ids,
        operation="scene.fixture",
        intent="scene fixture",
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


def _revision_input(
    source: Asset, preview: Asset, dependency: Asset | None = None
) -> SceneRevisionInput:
    dependencies = []
    if dependency is not None:
        dependencies.append(
            SceneDependency(role="texture.base_color", asset_id=dependency.id, sha256=dependency.sha256)
        )
    return SceneRevisionInput(
        source_asset_id=source.id,
        preview_asset_id=preview.id,
        dependencies=dependencies,
        runtime_id=RUNTIME_ID,
        runtime_version="4.5.9",
        validation=[
            SceneValidationCheck(
                validator="blender.scene", status="passed", facts={"objects": 2}
            ),
            SceneValidationCheck(
                validator="glb.structure", status="passed", facts={"meshes": 1}
            ),
        ],
    )


def _revision_assets(store: Store, tmp_path: Path) -> tuple[Asset, Asset, Asset]:
    source = _register(
        store, tmp_path, mime_type="application/x-blender", content=b"BLENDER-v300"
    )
    preview = _register(
        store,
        tmp_path,
        mime_type="model/gltf-binary",
        content=b"glTF-preview",
        parents=[source.id],
    )
    dependency = _register(store, tmp_path, mime_type="image/png", content=b"png-texture")
    return source, preview, dependency


def test_scene_schema_migrates_and_create_is_owner_scoped_and_immutable(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    store.initialize()
    with sqlite3.connect(store.db_path) as connection:
        connection.executescript(
            """DROP TABLE scene_revision_dependencies;
            DROP TABLE scene_revisions;
            DROP TABLE scene_documents;"""
        )
    store = Store(tmp_path / "state")
    store.initialize()
    source, preview, dependency = _revision_assets(store, tmp_path)
    catalog = SceneCatalog(store)

    document, revision = catalog.create(
        "user:alpha",
        name=" Product shot ",
        tags=["product", "draft"],
        collection="Campaign A",
        revision=_revision_input(source, preview, dependency),
    )

    assert document.name == "Product shot"
    assert document.current_revision_id == revision.id
    assert revision.sequence == 1 and revision.parent_revision_id is None
    assert catalog.list("user:alpha") == [document]
    assert catalog.get("user:alpha", document.id) == (document, [revision])
    assert catalog.list("user:other") == []
    with pytest.raises(SceneError) as hidden:
        catalog.get("user:other", document.id)
    assert hidden.value.code == "scene_not_found"
    assert store.scene_runtime_reference_count(RUNTIME_ID) == 1

    with sqlite3.connect(store.db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'scene_%'"
            )
        }
    assert tables == {
        "scene_documents",
        "scene_revisions",
        "scene_revision_dependencies",
        "scene_working_copies",
        "scene_recipe_tasks",
    }

    for asset in (source, preview, dependency):
        with pytest.raises(AssetInUse) as referenced:
            store.delete_asset(asset.id)
        expected = {revision.id, preview.id} if asset.id == source.id else {revision.id}
        assert referenced.value.child_id in expected


def test_scene_commit_is_optimistic_and_preserves_every_revision(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    store.initialize()
    catalog = SceneCatalog(store)
    source1, preview1, dependency = _revision_assets(store, tmp_path)
    document1, revision1 = catalog.create(
        "user:alpha",
        name="Character turntable",
        revision=_revision_input(source1, preview1, dependency),
    )
    source2, preview2, _ = _revision_assets(store, tmp_path)

    document2, revision2 = catalog.commit(
        "user:alpha",
        document1.id,
        revision1.id,
        _revision_input(source2, preview2, dependency),
    )

    assert document2.current_revision_id == revision2.id
    assert document2.revision_count == revision2.sequence == 2
    assert revision2.parent_revision_id == revision1.id
    assert catalog.get("user:alpha", document1.id) == (
        document2,
        [revision1, revision2],
    )

    source3, preview3, _ = _revision_assets(store, tmp_path)
    with pytest.raises(SceneError) as conflict:
        catalog.commit(
            "user:alpha",
            document1.id,
            revision1.id,
            _revision_input(source3, preview3, dependency),
        )
    assert conflict.value.code == "scene_revision_conflict"
    assert catalog.get("user:alpha", document1.id) == (
        document2,
        [revision1, revision2],
    )


def test_invalid_scene_assets_roll_back_the_document_and_revision(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    store.initialize()
    source = _register(store, tmp_path, mime_type="image/png", content=b"not-blend")
    preview = _register(
        store,
        tmp_path,
        mime_type="model/gltf-binary",
        content=b"preview",
        parents=[source.id],
    )
    catalog = SceneCatalog(store)

    with pytest.raises(SceneError) as invalid:
        catalog.create(
            "user:alpha",
            name="Invalid scene",
            revision=_revision_input(source, preview),
        )
    assert invalid.value.code == "scene_source_invalid"
    assert catalog.list("user:alpha") == []
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM scene_revisions").fetchone()[0] == 0


def test_dependency_hash_and_required_validation_are_fail_closed(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    store.initialize()
    source, preview, dependency = _revision_assets(store, tmp_path)
    invalid_hash = _revision_input(source, preview, dependency).model_copy(deep=True)
    invalid_hash.dependencies[0].sha256 = "0" * 64

    with pytest.raises(SceneError) as changed:
        SceneCatalog(store).create(
            "user:alpha", name="Changed dependency", revision=invalid_hash
        )
    assert changed.value.code == "scene_dependency_changed"
    assert SceneCatalog(store).list("user:alpha") == []

    values = _revision_input(source, preview).model_dump()
    values["validation"][1]["status"] = "not_checked"
    with pytest.raises(ValidationError):
        SceneRevision(
            id=f"revision_{uuid.uuid4().hex}",
            scene_id=f"scene_{uuid.uuid4().hex}",
            sequence=1,
            created_at=utc_now(),
            **values,
        )


def test_private_scene_reads_use_the_stable_actor_and_standalone_owner(
    tmp_path: Path,
) -> None:
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.store
        source, preview, dependency = _revision_assets(store, tmp_path)
        document, revision = client.app.state.scenes.create(
            "user:7",
            name="Authenticated scene",
            revision=_revision_input(source, preview, dependency),
        )
        with client.websocket_connect("/ws", headers=headers) as socket:
            listed = call(socket, "scenes.list")
            fetched = call(socket, "scenes.get", {"scene_id": document.id})
            session = call(socket, "workspace.session", {"parts": ["scenes"]})
        with client.websocket_connect(
            "/ws",
            headers={
                "Authorization": "Bearer valid-job",
                "X-Control-Deck-Addon-ID": "media-forge",
            },
        ) as other_socket:
            shared = call(other_socket, "scenes.get", {"scene_id": document.id})
        with client.websocket_connect(
            "/ws",
            headers={
                "Authorization": "Bearer valid-other",
                "X-Control-Deck-Addon-ID": "media-forge",
            },
        ) as other_actor_socket:
            hidden = call(other_actor_socket, "scenes.get", {"scene_id": document.id})

        assert listed["result"]["items"] == [document.model_dump(mode="json")]
        assert fetched["result"] == {
            "scene": document.model_dump(mode="json"),
            "revisions": [revision.model_dump(mode="json")],
        }
        assert session["result"]["scenes"]["items"] == [document.model_dump(mode="json")]
        assert shared["result"] == fetched["result"]
        assert hidden["ok"] is False and hidden["error"]["code"] == "scene_not_found"

        standalone_source, standalone_preview, standalone_dependency = _revision_assets(
            store, tmp_path
        )
        standalone, _ = client.app.state.scenes.create(
            "local",
            name="Standalone scene",
            revision=_revision_input(
                standalone_source, standalone_preview, standalone_dependency
            ),
        )
        standalone_list = client.get("/workspace-api/scenes")
        standalone_get = client.get(f"/workspace-api/scenes/{standalone.id}")

    assert standalone_list.status_code == 200
    assert standalone_list.json()["items"] == [standalone.model_dump(mode="json")]
    assert standalone_get.status_code == 200
    assert standalone_get.json()["scene"] == standalone.model_dump(mode="json")
