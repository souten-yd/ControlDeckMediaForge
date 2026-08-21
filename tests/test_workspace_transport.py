"""PR-U0: bounded workspace transport additions.

These are regression evidence for the /ws implementation detail, not evidence
that the workspace UI works. Real browser observation belongs to PR-U7.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conftest import wait_terminal
from mediaforge import library, preferences, thumbnails
from mediaforge.thumbnails import THUMBNAIL_BYTE_LIMIT
from test_host_execution import generate_input, host_client


def png_bytes(size: tuple[int, int] = (64, 48), color: tuple[int, int, int, int] = (12, 90, 80, 255)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def import_asset(client: TestClient, purpose: str = "source", size: tuple[int, int] = (64, 48)) -> dict:
    response = client.post(
        f"/api/v1/assets/import?purpose={purpose}",
        content=png_bytes(size),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def call(socket, method: str, params: dict | None = None) -> dict:
    """Send one request and skip any pushed events that arrive first."""
    socket.send_json({"id": method, "method": method, "params": params or {}})
    while True:
        message = socket.receive_json()
        if message.get("id") == method:
            return message


# ── capabilities.get ────────────────────────────────────────────────────────


def test_capabilities_get_matches_the_public_document_and_bounds_presets(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        public = client.get("/api/v1/capabilities").json()
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "capabilities.get")

    assert answer["ok"] is True
    result = answer["result"]
    assert result["capabilities"] == public["capabilities"]
    assert result["contract_version"] == public["contract_version"]

    envelope = result["envelope"]
    assert envelope["multiple_of"] == 16
    assert envelope["min_side"] <= envelope["max_side"]
    # The fake test manifest installs nothing, so the envelope must say so
    # rather than inventing measured bounds.
    assert envelope["envelope_source"] == "fallback"

    ids = [preset["id"] for preset in result["presets"]]
    assert ids == ["square", "landscape", "portrait"]
    for preset in result["presets"]:
        assert preset["width"] % 16 == 0 and preset["height"] % 16 == 0
        assert max(preset["width"], preset["height"]) <= envelope["max_side"]


# ── library.list ────────────────────────────────────────────────────────────


def test_library_list_classifies_origin_and_hides_masks(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        import_asset(client, "source")
        import_asset(client, "edit_mask")
        created = client.post("/api/v1/jobs", json=generate_input("library robot")).json()
        wait_terminal(client, created["id"])

        with client.websocket_connect("/ws", headers=headers) as socket:
            default = call(socket, "library.list")["result"]
            masks = call(socket, "library.list", {"include_masks": True})["result"]
            generated = call(socket, "library.list", {"kind": "generated"})["result"]

    kinds = {item["kind"] for item in default["items"]}
    assert "generated" in kinds and "imported" in kinds
    assert len(masks["items"]) == len(default["items"]) + 1
    assert all(item["kind"] == "generated" for item in generated["items"])

    produced = next(item for item in default["items"] if item["kind"] == "generated")
    assert produced["summary"] == "library robot"
    assert produced["width"] and produced["height"]
    assert "asset_id" in produced and produced["asset_id"].startswith("asset_")


def test_library_list_rejects_unknown_kind_and_pages_without_gaps(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        for _ in range(3):
            import_asset(client, "source")
        with client.websocket_connect("/ws", headers=headers) as socket:
            rejected = call(socket, "library.list", {"kind": "nope"})
            first = call(socket, "library.list", {"limit": 2})["result"]
            socket.send_json({
                "id": "page2",
                "method": "library.list",
                "params": {"limit": 2, "before": first["next_before"]},
            })
            while True:
                message = socket.receive_json()
                if message.get("id") == "page2":
                    second = message["result"]
                    break

    assert rejected["ok"] is False
    assert rejected["error"]["code"] == "workspace_request_rejected"
    assert len(first["items"]) == 2 and first["next_before"]
    seen = [item["asset_id"] for item in first["items"] + second["items"]]
    assert len(seen) == len(set(seen)) == 3
    assert second["next_before"] is None


def test_library_page_advances_when_every_row_is_filtered_out():
    from mediaforge.domain import Asset, Provenance

    def record(index: int, purpose: str) -> tuple[Asset, Provenance]:
        asset = Asset(
            id=f"asset_{index:032x}",
            job_id="job_1",
            parent_asset_ids=[],
            mime_type="image/png",
            size_bytes=1,
            sha256="0" * 64,
            suggested_filename="a.png",
            provenance_id=f"prov_{index}",
            created_at=f"2026-08-22T00:00:0{index}Z",
        )
        provenance = Provenance(
            id=f"prov_{index}",
            asset_id=asset.id,
            parent_asset_ids=[],
            operation="asset.import",
            intent="Import local edit mask asset",
            model_id="none",
            model_version="0",
            weights_hash="none",
            license="user-provided",
            runtime_adapter="import",
            runtime_version="0",
            tool_versions={},
            seed=0,
            parameters={"purpose": purpose},
            reference_asset_hashes={},
            postprocessing=[],
            validation=[],
            warnings=[],
            output_sha256="0" * 64,
            created_at=asset.created_at,
        )
        return asset, provenance

    records = [record(1, "edit_mask"), record(2, "edit_mask")]
    result = library.page(records, kind="all", include_masks=False, limit=2)
    assert result["items"] == []
    assert result["next_before"] == records[-1][0].created_at


# ── assets.thumbnail ────────────────────────────────────────────────────────


def test_thumbnail_is_bounded_cached_and_webp(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        asset = import_asset(client, "source", size=(900, 600))
        with client.websocket_connect("/ws", headers=headers) as socket:
            first = call(socket, "assets.thumbnail", {"asset_id": asset["id"]})["result"]
            cached_dir = client.app.state.store.thumbnail_dir
            files = sorted(cached_dir.iterdir())
            stamp = files[0].stat().st_mtime_ns
            second = call(socket, "assets.thumbnail", {"asset_id": asset["id"]})["result"]
            assert sorted(cached_dir.iterdir())[0].stat().st_mtime_ns == stamp

    assert first["mime_type"] == "image/webp"
    assert max(first["width"], first["height"]) == thumbnails.DEFAULT_MAX_SIDE
    assert len(base64.b64decode(first["base64"])) <= THUMBNAIL_BYTE_LIMIT
    assert second == first
    assert len(files) == 1


def test_thumbnail_clamps_requested_size_and_reports_unsupported_media(tmp_path: Path):
    assert thumbnails.clamp_max_side(9999) == thumbnails.MAX_MAX_SIDE
    assert thumbnails.clamp_max_side(1) == thumbnails.MIN_MAX_SIDE
    assert thumbnails.clamp_max_side("256") == thumbnails.DEFAULT_MAX_SIDE
    assert thumbnails.clamp_max_side(True) == thumbnails.DEFAULT_MAX_SIDE
    assert not thumbnails.is_thumbnailable("video/mp4")

    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        asset = import_asset(client, "source")
        store = client.app.state.store
        store.asset_path(asset["id"]).write_bytes(b"not an image")
        with client.websocket_connect("/ws", headers=headers) as socket:
            answer = call(socket, "assets.thumbnail", {"asset_id": asset["id"]})

    assert answer["ok"] is False
    assert answer["error"]["code"] == "thumbnail_unavailable"


# ── preferences ─────────────────────────────────────────────────────────────


def test_preferences_round_trip_and_reject_unknown_keys(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        defaults = call(socket, "preferences.get")["result"]["values"]
        stored = call(socket, "preferences.set", {"values": {"mode": "advanced", "last_count": 4}})
        reloaded = call(socket, "preferences.get")["result"]["values"]
        unknown = call(socket, "preferences.set", {"values": {"api_token": "secret"}})
        bad_value = call(socket, "preferences.set", {"values": {"mode": "expert"}})
        oversized = call(socket, "preferences.set", {"values": {"mode": "x" * 5000}})

    assert defaults == preferences.DEFAULTS
    assert stored["ok"] is True
    assert reloaded["mode"] == "advanced" and reloaded["last_count"] == 4
    assert reloaded["last_preset"] == preferences.DEFAULTS["last_preset"]
    assert unknown["ok"] is False and unknown["error"]["code"] == "invalid_preference_key"
    assert bad_value["ok"] is False and bad_value["error"]["code"] == "invalid_preference_value"
    assert oversized["ok"] is False and oversized["error"]["code"] == "preferences_too_large"
    # A rejected write never leaks its value into an error message.
    assert "secret" not in unknown["error"]["message"]


def test_preferences_are_isolated_per_subject(tmp_path: Path):
    from mediaforge.store import Store

    store = Store(tmp_path / "prefs")
    store.initialize()
    store.set_preferences("7", {"mode": "advanced"})
    assert store.get_preferences("7") == {"mode": "advanced"}
    assert store.get_preferences("8") == {}
    assert preferences.merged(store.get_preferences("8"))["mode"] == "simple"
    # Values written by an older build are not handed back to the workspace.
    store.set_preferences("9", {"mode": "simple", "removed_key": 1})
    assert "removed_key" not in preferences.merged(store.get_preferences("9"))


# ── jobs.watch ──────────────────────────────────────────────────────────────


def test_jobs_watch_pushes_changes_and_releases_terminal_jobs(tmp_path: Path):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        created = client.post("/api/v1/jobs", json=generate_input("watched robot")).json()
        watching = call(socket, "jobs.watch", {"job_ids": [created["id"]]})
        assert watching["result"]["watching"] == [created["id"]]

        statuses: list[str] = []
        for _ in range(40):
            message = socket.receive_json()
            if message.get("event") != "job.changed":
                continue
            assert message["data"]["id"] == created["id"]
            statuses.append(message["data"]["status"])
            if message["data"]["status"] in {"succeeded", "failed", "canceled"}:
                break
        assert statuses, "no job.changed event was pushed"
        assert statuses[-1] in {"succeeded", "failed", "canceled"}

        # The terminal job is released, so a later watch of nothing stays empty.
        still = call(socket, "jobs.unwatch", {"job_ids": [created["id"]]})
        assert still["result"]["watching"] == []


def test_jobs_watch_rejects_malformed_ids_and_bounds_the_watch_set(tmp_path: Path):
    from mediaforge.events import MAX_WATCHED_JOBS, JobEventBus
    import asyncio

    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        rejected = call(socket, "jobs.watch", {"job_ids": [1, 2]})
    assert rejected["ok"] is False
    assert rejected["error"]["code"] == "workspace_request_rejected"

    async def bounded() -> list[str]:
        bus = JobEventBus()
        subscription = bus.subscribe(asyncio.get_running_loop())
        return subscription.watch([f"job_{index}" for index in range(MAX_WATCHED_JOBS + 5)])

    assert len(asyncio.run(bounded())) == MAX_WATCHED_JOBS


def test_job_publication_survives_a_failing_listener(tmp_path: Path):
    from mediaforge.domain import JobRequest
    from mediaforge.store import Store

    store = Store(tmp_path / "listener")
    store.initialize()
    seen: list[str] = []
    store.observe(lambda job: (_ for _ in ()).throw(RuntimeError("subscriber exploded")))
    store.observe(lambda job: seen.append(job.status.value))

    request = JobRequest.model_validate(generate_input("listener robot"))
    job = store.create_job(request)
    store.update_job(job.id, phase="generating", progress=0.5)

    assert seen == ["queued", "queued"]


@pytest.mark.parametrize(
    "method",
    ["capabilities.get", "library.list", "assets.thumbnail", "preferences.get", "jobs.watch"],
)
def test_new_methods_reject_host_path_strings(tmp_path: Path, method: str):
    client, headers, _state = host_client(tmp_path, token="valid-user")
    with client, client.websocket_connect("/ws", headers=headers) as socket:
        socket.send_json({"id": "path", "method": method, "params": {"hint": "/etc/passwd"}})
        while True:
            message = socket.receive_json()
            if message.get("id") == "path":
                break
    assert message["ok"] is False
    assert message["error"]["code"] == "unscoped_host_path"


def test_new_methods_require_the_host_service_identity(tmp_path: Path):
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        try:
            with client.websocket_connect("/ws"):
                pass
        except Exception:
            return
    raise AssertionError("workspace WebSocket accepted a request without a host token")
