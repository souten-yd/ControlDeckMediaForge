"""端末の写真をそのまま取り込めること。

iPhone の既定の形式は HEIC で、端末が JPEG へ直さずに添付してくることがある。
Pillow 単体は HEIF を読まないので、読める形式を `pillow-heif` で足してある。
向きも EXIF で持つため、当てずに預かると横倒しのまま 3D の入力になる。
"""

from __future__ import annotations

import io

from PIL import Image
import pytest

from mediaforge.asset_import import IMPORTABLE_FORMATS

pillow_heif = pytest.importorskip("pillow_heif", reason="HEIF decoder is optional")


def _post(client, content: bytes, media_type: str):
    return client.post(
        "/api/v1/assets/import?purpose=source", content=content,
        headers={"content-type": media_type},
    )


def test_heic_photo_is_imported_and_normalized_to_png(client):
    assert "HEIF" in IMPORTABLE_FORMATS
    source = Image.new("RGB", (320, 240), (180, 90, 40))
    encoded = io.BytesIO()
    pillow_heif.from_pillow(source).save(encoded, format="HEIF", quality=80)
    response = _post(client, encoded.getvalue(), "image/heic")
    assert response.status_code == 201, response.text
    asset = response.json()
    # 保管する形式は今までどおり PNG のまま。契約は増やしていない。
    assert asset["mime_type"] == "image/png"
    assert (asset["width"], asset["height"]) == (320, 240)
    content = client.get(f"/api/v1/assets/{asset['id']}/content")
    assert content.status_code == 200
    with Image.open(io.BytesIO(content.content)) as stored:
        assert stored.format == "PNG"


def test_rotated_photo_is_stored_as_it_is_seen(client):
    """EXIF で 90 度回した写真は、回した後の寸法で預かる。

    画面は復号時に向きを当てて寸法を測る。ここで当てないと、測った寸法と
    預かった寸法が食い違い、寸法一致を要求する経路が理由なく断る。
    """
    source = Image.new("RGB", (320, 240), (30, 120, 90))
    exif = Image.Exif()
    exif[274] = 6  # Orientation: 右へ90度回して表示する
    encoded = io.BytesIO()
    source.save(encoded, format="JPEG", exif=exif)
    response = _post(client, encoded.getvalue(), "image/jpeg")
    assert response.status_code == 201, response.text
    asset = response.json()
    assert (asset["width"], asset["height"]) == (240, 320)


def test_undecodable_photo_is_refused_with_a_reason(client):
    response = _post(client, b"not an image at all", "image/heic")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_image_import"
