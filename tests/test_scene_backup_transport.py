from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from mediaforge.scene_backup import MAX_BACKUP_ARCHIVE_BYTES
from mediaforge.scene_backup_transport import (
    BACKUP_TRANSFER_TTL_SEC,
    SCENE_BACKUP_CHUNK_BYTES,
    SceneBackupSession,
)
from mediaforge.scenes import SceneError
from test_host_execution import host_client
from test_scene_backup import scene_fixture
from test_scene_workspace import fake_scene_workspace
from test_workspace_transport import call


def _read_session_backup(
    session: SceneBackupSession, owner: str, opened: dict[str, object]
) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    total = int(opened["total_bytes"])
    while offset < total:
        result = session.read_download(owner, str(opened["handle"]), offset)
        chunk = base64.b64decode(result["base64"], validate=True)
        assert result["offset"] == offset and result["total_bytes"] == total
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def test_session_streams_exact_backup_and_restores_with_no_paths(tmp_path: Path) -> None:
    store, catalog, scene_id, _expected = scene_fixture(tmp_path)
    session = SceneBackupSession(store)
    session.initialize()

    opened = session.open_download("user:source", scene_id)
    assert opened["chunk_bytes"] == 512 * 1024
    with pytest.raises(SceneError) as limited:
        session.open_download("user:source", scene_id)
    assert limited.value.code == "scene_backup_transfer_limit"
    with pytest.raises(SceneError) as hidden:
        session.read_download("user:other", str(opened["handle"]), 0)
    assert hidden.value.code == "scene_backup_handle_invalid"

    content = _read_session_backup(session, "user:source", opened)
    assert len(content) == opened["total_bytes"]
    assert hashlib.sha256(content).hexdigest() == opened["sha256"]
    assert "path" not in json.dumps(opened)
    assert session.close_download("user:other", str(opened["handle"])) is False
    assert session.close_download("user:source", str(opened["handle"])) is True

    begun = session.begin_restore(
        "user:restored", size=len(content), sha256=hashlib.sha256(content).hexdigest()
    )
    assert begun["chunk_bytes"] == 512 * 1024
    offset = 0
    while offset < len(content):
        chunk = content[offset : offset + SCENE_BACKUP_CHUNK_BYTES]
        appended = session.append_restore(
            "user:restored",
            str(begun["upload_id"]),
            offset,
            chunk,
            hashlib.sha256(chunk).hexdigest(),
        )
        offset = int(appended["received"])
    restored = session.commit_restore("user:restored", str(begun["upload_id"]))

    restored_id = restored["scene"]["id"]
    document, revisions = catalog.get("user:restored", restored_id)
    assert document.revision_count == 2 and len(revisions) == 2
    assert restored_id != scene_id
    assert "path" not in json.dumps(restored)
    assert list(session.root.iterdir()) == []


def test_session_rejects_invalid_chunks_and_expires_all_staging(tmp_path: Path) -> None:
    store, _catalog, scene_id, _expected = scene_fixture(tmp_path)
    now = [100.0]
    session = SceneBackupSession(store, clock=lambda: now[0])
    session.initialize()
    opened = session.open_download("user:source", scene_id)
    now[0] += BACKUP_TRANSFER_TTL_SEC
    with pytest.raises(SceneError) as expired:
        session.read_download("user:source", str(opened["handle"]), 0)
    assert expired.value.code == "scene_backup_handle_invalid"

    with pytest.raises(SceneError) as oversized:
        session.begin_restore(
            "user:source", size=MAX_BACKUP_ARCHIVE_BYTES + 1, sha256="0" * 64
        )
    assert oversized.value.code == "scene_backup_upload_invalid"
    begun = session.begin_restore("user:source", size=8, sha256="0" * 64)
    with pytest.raises(SceneError) as concurrent:
        session.begin_restore("user:source", size=8, sha256="0" * 64)
    assert concurrent.value.code == "scene_backup_transfer_limit"
    with pytest.raises(SceneError) as other_owner:
        session.cancel_restore("user:other", str(begun["upload_id"]))
    assert other_owner.value.code == "scene_backup_upload_invalid"
    with pytest.raises(SceneError) as bad_chunk:
        session.append_restore(
            "user:source", str(begun["upload_id"]), 0, b"four", "0" * 64
        )
    assert bad_chunk.value.code == "scene_backup_chunk_invalid"
    with pytest.raises(SceneError) as incomplete:
        session.commit_restore("user:source", str(begun["upload_id"]))
    assert incomplete.value.code == "scene_backup_upload_incomplete"
    assert session.cancel_restore("user:source", str(begun["upload_id"])) is True

    content = b"not-a-zip"
    changed = session.begin_restore("user:source", size=len(content), sha256="0" * 64)
    session.append_restore(
        "user:source",
        str(changed["upload_id"]),
        0,
        content,
        hashlib.sha256(content).hexdigest(),
    )
    with pytest.raises(SceneError) as identity:
        session.commit_restore("user:source", str(changed["upload_id"]))
    assert identity.value.code == "scene_backup_hash_changed"

    expires = session.begin_restore("user:source", size=1, sha256="0" * 64)
    now[0] += BACKUP_TRANSFER_TTL_SEC
    with pytest.raises(SceneError) as expired_upload:
        session.append_restore(
            "user:source",
            str(expires["upload_id"]),
            0,
            b"x",
            hashlib.sha256(b"x").hexdigest(),
        )
    assert expired_upload.value.code == "scene_backup_upload_invalid"
    abandoned = session.begin_restore("user:source", size=1, sha256="0" * 64)
    session.append_restore(
        "user:source",
        str(abandoned["upload_id"]),
        0,
        b"x",
        hashlib.sha256(b"x").hexdigest(),
    )
    session.cleanup()
    assert list(session.root.iterdir()) == []


def test_authenticated_backup_transport_round_trips_and_cleans_on_shutdown(
    tmp_path: Path,
) -> None:
    _store, fixture_workspace, resolver = fake_scene_workspace(tmp_path / "fixture")
    client, headers, _state = host_client(tmp_path / "app", token="valid-user")
    source = b"BLENDER" + b"backup-transport-scene" * 20
    source_sha = hashlib.sha256(source).hexdigest()
    with client:
        workspace = client.app.state.scene_workspace
        workspace.resolver = resolver
        workspace.worker = fixture_workspace.worker
        with client.websocket_connect("/ws", headers=headers) as socket:
            begun = call(
                socket,
                "scenes.import.begin",
                {"size": len(source), "sha256": source_sha, "name": "Backup transport"},
            )["result"]
            call(
                socket,
                "scenes.import.chunk",
                {
                    "upload_id": begun["upload_id"],
                    "offset": 0,
                    "sha256": source_sha,
                    "base64": base64.b64encode(source).decode("ascii"),
                },
            )
            imported = call(
                socket, "scenes.import.commit", {"upload_id": begun["upload_id"]}
            )["result"]
            opened = call(
                socket, "scenes.backup.open", {"scene_id": imported["scene"]["id"]}
            )["result"]
            assert opened["chunk_bytes"] == 512 * 1024
            limited = call(
                socket, "scenes.backup.open", {"scene_id": imported["scene"]["id"]}
            )
            parts: list[bytes] = []
            offset = 0
            while offset < opened["total_bytes"]:
                read = call(
                    socket,
                    "scenes.backup.read",
                    {"handle": opened["handle"], "offset": offset},
                )["result"]
                chunk = base64.b64decode(read["base64"], validate=True)
                parts.append(chunk)
                offset += len(chunk)
            backup = b"".join(parts)
            restored_upload = call(
                socket,
                "scenes.restore.begin",
                {"size": len(backup), "sha256": hashlib.sha256(backup).hexdigest()},
            )["result"]
            assert restored_upload["chunk_bytes"] == 512 * 1024
            offset = 0
            while offset < len(backup):
                chunk = backup[offset : offset + SCENE_BACKUP_CHUNK_BYTES]
                call(
                    socket,
                    "scenes.restore.chunk",
                    {
                        "upload_id": restored_upload["upload_id"],
                        "offset": offset,
                        "sha256": hashlib.sha256(chunk).hexdigest(),
                        "base64": base64.b64encode(chunk).decode("ascii"),
                    },
                )
                offset += len(chunk)
            restored = call(
                socket,
                "scenes.restore.commit",
                {"upload_id": restored_upload["upload_id"]},
            )
            scene_list = call(socket, "scenes.list", {})
            assert call(
                socket, "scenes.backup.close", {"handle": opened["handle"]}
            )["result"] == {"closed": True}
            abandoned = call(
                socket,
                "scenes.restore.begin",
                {"size": len(backup), "sha256": hashlib.sha256(backup).hexdigest()},
            )["result"]
            call(
                socket,
                "scenes.restore.chunk",
                {
                    "upload_id": abandoned["upload_id"],
                    "offset": 0,
                    "sha256": hashlib.sha256(backup[:16]).hexdigest(),
                    "base64": base64.b64encode(backup[:16]).decode("ascii"),
                },
            )
        with client.websocket_connect("/ws", headers=headers) as resumed:
            unavailable = call(
                resumed,
                "scenes.backup.read",
                {"handle": opened["handle"], "offset": 0},
            )
        transfer_root = client.app.state.scene_backups.root

    assert list(transfer_root.iterdir()) == []

    assert limited["ok"] is False
    assert limited["error"]["code"] == "scene_backup_transfer_limit"
    assert restored["ok"] is True and "path" not in json.dumps(restored)
    assert len(scene_list["result"]["items"]) == 2
    assert unavailable["ok"] is False
    assert unavailable["error"]["code"] == "scene_backup_handle_invalid"


def test_standalone_backup_transport_uses_the_same_bounded_session(tmp_path: Path) -> None:
    _store, fixture_workspace, resolver = fake_scene_workspace(tmp_path / "fixture")
    client, _headers, _state = host_client(tmp_path / "app")
    source = b"BLENDER-standalone-backup"
    source_sha = hashlib.sha256(source).hexdigest()
    with client:
        workspace = client.app.state.scene_workspace
        workspace.resolver = resolver
        workspace.worker = fixture_workspace.worker
        begun = client.post(
            "/workspace-api/scenes/import/begin",
            json={"size": len(source), "sha256": source_sha, "name": "Standalone backup"},
        ).json()
        client.post(
            "/workspace-api/scenes/import/chunk",
            json={
                "upload_id": begun["upload_id"],
                "offset": 0,
                "sha256": source_sha,
                "base64": base64.b64encode(source).decode("ascii"),
            },
        )
        scene = client.post(
            "/workspace-api/scenes/import/commit", json={"upload_id": begun["upload_id"]}
        ).json()["scene"]
        opened_response = client.post(
            f"/workspace-api/scenes/{scene['id']}/backup/open", json={}
        )
        opened = opened_response.json()
        assert opened["chunk_bytes"] == 512 * 1024
        read = client.post(
            f"/workspace-api/scenes/backups/{opened['handle']}/read",
            json={"offset": 0, "length": opened["total_bytes"]},
        )
        backup = base64.b64decode(read.json()["base64"], validate=True)
        closed = client.post(
            f"/workspace-api/scenes/backups/{opened['handle']}/close", json={}
        )
        upload = client.post(
            "/workspace-api/scenes/restore/begin",
            json={"size": len(backup), "sha256": hashlib.sha256(backup).hexdigest()},
        ).json()
        chunked = client.post(
            "/workspace-api/scenes/restore/chunk",
            json={
                "upload_id": upload["upload_id"],
                "offset": 0,
                "sha256": hashlib.sha256(backup).hexdigest(),
                "base64": base64.b64encode(backup).decode("ascii"),
            },
        )
        restored = client.post(
            "/workspace-api/scenes/restore/commit", json={"upload_id": upload["upload_id"]}
        )
        injected = client.post(
            "/workspace-api/scenes/restore/begin",
            json={"size": len(backup), "sha256": hashlib.sha256(backup).hexdigest(), "path": "/tmp/x"},
        )

    assert opened_response.status_code == 200 and "path" not in opened_response.text
    assert read.status_code == 200 and len(backup) == opened["total_bytes"]
    assert closed.json() == {"closed": True}
    assert chunked.status_code == 200 and chunked.json()["received"] == len(backup)
    assert restored.status_code == 200 and "path" not in restored.text
    assert injected.status_code == 422
    assert injected.json()["detail"]["code"] == "unscoped_host_path"
