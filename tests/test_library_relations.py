from pathlib import Path

import pytest

from mediaforge import library
from mediaforge.store import Store
from test_host_execution import host_client
from test_scenes import _register
from test_workspace_transport import call


def test_relation_pagination_and_format_filters(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    image = _register(store, tmp_path, mime_type="image/png", content=b"test image")
    blend = _register(store, tmp_path, mime_type="application/x-blender", content=b"test source", parents=[image.id])
    children = [_register(store, tmp_path, mime_type="model/gltf-binary", content=b"test glb", parents=[blend.id]) for _ in range(3)]
    records = store.list_asset_records(20)
    assert [item["asset_id"] for item in library.page(records, kind="all", include_masks=False, limit=20, media_kind="blend")["items"]] == [blend.id]
    glbs = library.page(records, kind="all", include_masks=False, limit=20, media_kind="glb")["items"]
    assert {item["asset_id"] for item in glbs} == {item.id for item in children}
    assert library.entry(blend, store.get_provenance(blend.id))["preview_kind"] is None
    first = store.asset_relations(blend.id, limit=2)
    second = store.asset_relations(blend.id, limit=2, offset=first["next_offset"])
    assert first["parents"][0]["id"] == image.id
    assert second["next_offset"] is None
    assert {item["id"] for item in first["children"] + second["children"]} == {item.id for item in children}
    assert store.asset_relations(children[0].id)["parents"][0]["id"] == blend.id
    assert store.asset_relations(image.id)["children"][0]["id"] == blend.id
    for offset in (-1, True, "0", 1_000_001):
        with pytest.raises(ValueError):
            store.asset_relations(blend.id, offset=offset)


def test_relations_private_transports_and_metadata_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, headers, _ = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.store
        source = _register(store, tmp_path, mime_type="application/x-blender", content=b"not decoded")
        child = _register(store, tmp_path, mime_type="model/gltf-binary", content=b"not decoded", parents=[source.id])
        def no_asset_reads(*args: object, **kwargs: object) -> None:
            raise AssertionError("metadata navigation must not read full asset bytes")
        monkeypatch.setattr(store, "asset_path", no_asset_reads)
        with client.websocket_connect("/ws", headers=headers) as socket:
            result = call(socket, "assets.relations", {"asset_id": source.id})
            assert result["ok"] and result["result"]["children"][0]["id"] == child.id
            assert not call(socket, "assets.relations", {"asset_id": source.id, "offset": -1})["ok"]
            assert not call(socket, "assets.relations", {"asset_id": source.id, "path": "/tmp"})["ok"]
        response = client.get(f"/workspace-api/assets/{source.id}/relations")
        assert response.status_code == 200
        assert response.json() == result["result"]
        assert client.get(f"/workspace-api/assets/{source.id}/relations?offset=-1").status_code == 422
        assert client.get("/workspace-api/assets/asset_missing/relations").status_code == 404
