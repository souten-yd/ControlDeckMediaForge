"""ライブラリから手元の端末へ持ち出す経路。

携帯（iPhone）から使うことを前提にしている。確かめたいのは三つで、
「押した先がそのまま中身か」「まとめたものが開けるか」「入り切らない要求を
黙って始めないか」である。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from mediaforge import library_download
from mediaforge.store import Store
from test_host_execution import host_client
from test_scenes import _register


def test_one_asset_comes_back_as_a_file_to_keep(tmp_path: Path) -> None:
    """押した先がそのまま中身である。

    既にある /api/v1/assets/{id}/content は inline なので、押すとブラウザが
    開いてしまう。落とすための経路は disposition が attachment でなければ
    意味がない。
    """
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.store
        asset = _register(store, tmp_path, mime_type="image/png", content=b"one image")
        response = client.get(f"/workspace-api/assets/{asset.id}/download")
        assert response.status_code == 200, response.text
        assert response.content == b"one image"
        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment")
        assert asset.suggested_filename in disposition
        # 見るための経路は今までどおり開く側のままにしておく。
        inline = client.get(f"/api/v1/assets/{asset.id}/content")
        assert inline.headers["content-disposition"].startswith("inline")


def test_several_assets_come_back_as_one_archive(tmp_path: Path) -> None:
    """選んだぶんが 1 つの zip で落ちてくる。

    1 件ずつ開いて保存するのは、携帯で何十件も持ち出すときに現実的でない。
    """
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.store
        assets = [
            _register(store, tmp_path, mime_type="image/png", content=f"image {index}".encode())
            for index in range(3)
        ]
        query = "&".join(f"asset_id={item.id}" for item in assets)
        response = client.get(f"/workspace-api/library/download?{query}")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/zip"
        assert response.headers["content-disposition"].startswith("attachment")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            assert sorted(archive.namelist()) == sorted(item.suggested_filename for item in assets)
            for item in assets:
                stored = archive.read(item.suggested_filename)
                assert stored == (tmp_path / item.suggested_filename).read_bytes()


def test_the_archive_does_not_stay_behind(tmp_path: Path) -> None:
    """返し終えた zip を置き場に残さない。

    素材は増減するので、作り置きを持つと古い中身が落ちてくる。残しておく理由が
    無いうえ、残せば置き場が静かに膨らむ。
    """
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.store
        first = _register(store, tmp_path, mime_type="image/png", content=b"a")
        second = _register(store, tmp_path, mime_type="image/png", content=b"b")
        response = client.get(
            f"/workspace-api/library/download?asset_id={first.id}&asset_id={second.id}"
        )
        assert response.status_code == 200
        downloads = store.data_dir / "downloads"
        assert list(downloads.glob("*.zip")) == []


def test_a_missing_asset_is_named_instead_of_silently_skipped(tmp_path: Path) -> None:
    """欠けた素材を黙って抜かない。

    抜いて成功にすると、落とした側は全部あると思ったまま元を消してしまう。
    """
    client, _headers, _state = host_client(tmp_path, token="valid-user")
    with client:
        store = client.app.state.store
        asset = _register(store, tmp_path, mime_type="image/png", content=b"present")
        response = client.get(
            f"/workspace-api/library/download?asset_id={asset.id}&asset_id=asset_missing"
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "asset_not_found"


def test_too_many_or_too_large_is_refused_before_anything_is_built(tmp_path: Path) -> None:
    """入り切らない要求を始めない。

    相手は携帯であることが多い。送り始めてから詰まると、詰まったことしか
    分からない形で失敗する。
    """
    store = Store(tmp_path / "data")
    store.initialize()
    asset = _register(store, tmp_path, mime_type="image/png", content=b"x")
    with pytest.raises(library_download.DownloadRefused) as too_many:
        library_download.plan(store, [asset.id] * 1 + [f"asset_{index}" for index in range(200)])
    assert too_many.value.code == "download_too_many"
    with pytest.raises(library_download.DownloadRefused) as empty:
        library_download.plan(store, [])
    assert empty.value.code == "download_empty"


def test_a_huge_selection_is_refused_by_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    asset = _register(store, tmp_path, mime_type="image/png", content=b"x")
    monkeypatch.setattr(library_download, "MAX_TOTAL_BYTES", 0)
    with pytest.raises(library_download.DownloadRefused) as refused:
        library_download.plan(store, [asset.id])
    assert refused.value.code == "download_too_large"


class _Stub:
    """提案名だけを差し替えた store。同じ名前の素材は普通の経路では作れない。"""

    def __init__(self, entries: dict[str, tuple[str, Path]]) -> None:
        self._entries = entries

    def get_asset(self, asset_id: str):
        name, path = self._entries[asset_id]
        return type("A", (), {"suggested_filename": name, "size_bytes": path.stat().st_size})()

    def asset_path(self, asset_id: str) -> Path:
        return self._entries[asset_id][1]


def test_names_that_collide_do_not_overwrite_each_other(tmp_path: Path) -> None:
    """同じ名前の素材が 2 つあっても、両方が zip に残る。

    同じ arcname で 2 回書くと、展開したとき片方が消える。消えたことは
    展開するまで分からない。取り込んだ素材の名前は外から来るので、記号も落とす。
    """
    first = tmp_path / "first.bin"
    first.write_bytes(b"first")
    second = tmp_path / "second.bin"
    second.write_bytes(b"second")
    store = _Stub({
        "a": ("同じ 名前.png", first),
        "b": ("同じ 名前.png", second),
        "c": ("../../逃げ出す.png", first),
    })
    entries = library_download.plan(store, ["a", "b", "c"])
    names = [entry.name for entry in entries]
    assert len(set(names)) == 3, names
    assert all("/" not in name and "\\" not in name and not name.startswith(".") for name in names)
    target = tmp_path / "out.zip"
    library_download.build(entries, target)
    with zipfile.ZipFile(target) as archive:
        assert sorted(archive.namelist()) == sorted(names)
        assert archive.read(names[0]) == b"first"
        assert archive.read(names[1]) == b"second"


def test_stale_archives_are_swept_before_a_new_one_is_built(tmp_path: Path) -> None:
    """途中で落ちて残ったぶんを掃く。掃除のために別の仕掛けを増やさない。"""
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    old = downloads / "old.zip"
    old.write_bytes(b"stale")
    fresh = downloads / "fresh.zip"
    fresh.write_bytes(b"new")
    now = old.stat().st_mtime + library_download.STALE_AFTER_SEC + 1
    import os

    os.utime(fresh, (now, now))
    assert library_download.sweep(downloads, now) == 1
    assert not old.exists() and fresh.exists()
