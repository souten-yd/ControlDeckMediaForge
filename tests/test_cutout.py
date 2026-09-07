"""透過を求められた資産の背景を、決定的に抜く処理。

拡散モデルは alpha を出さない。抜かなければ sprite / icon / emblem は
`alpha_missing` で必ず落ちるが、抜けない画まで抜いたことにすると、被写体を
削った資産が「透過あり」として通る。ここで守るのはその両側である。
"""

from PIL import Image, ImageDraw

from mediaforge.cutout import cut_out_background


def _sprite(path, size=(512, 512), background=(18, 22, 30)):
    """単色背景に被写体 1 体。生成側へ頼んでいるのがこの形である。"""
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((128, 128, 384, 384), fill=(210, 60, 40))
    image.save(path)
    return path


def test_a_flat_background_becomes_transparent(tmp_path):
    path = _sprite(tmp_path / "sprite.png")
    assert cut_out_background(path) is True
    with Image.open(path) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((4, 4))[3] == 0
        assert image.getpixel((256, 256))[3] == 255


def test_an_enclosed_region_of_the_background_colour_survives(tmp_path):
    """閾値だけで消すと、被写体の中の同色の面が穴になる。縁から届く範囲に限る。"""
    path = tmp_path / "sprite.png"
    image = Image.new("RGB", (512, 512), (18, 22, 30))
    draw = ImageDraw.Draw(image)
    draw.ellipse((128, 128, 384, 384), fill=(210, 60, 40))
    draw.ellipse((240, 240, 272, 272), fill=(18, 22, 30))
    image.save(path)

    assert cut_out_background(path) is True
    with Image.open(path) as result:
        assert result.getpixel((256, 256))[3] == 255
        assert result.getpixel((4, 4))[3] == 0


def test_a_scene_background_is_left_alone(tmp_path):
    """平らでない背景は抜けない。抜いたことにせず、検査に理由を名指しさせる。"""
    path = tmp_path / "scene.png"
    image = Image.new("RGB", (256, 256))
    for y in range(256):
        for x in range(256):
            image.putpixel((x, y), (x, y, 120))
    image.save(path)
    before = path.read_bytes()

    assert cut_out_background(path) is False
    assert path.read_bytes() == before


def test_an_image_that_is_already_transparent_is_not_rebuilt(tmp_path):
    path = tmp_path / "clear.png"
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    image.paste((200, 30, 30, 255), (64, 64, 192, 192))
    image.save(path)
    before = path.read_bytes()

    assert cut_out_background(path) is False
    assert path.read_bytes() == before


def test_a_frame_filled_by_one_colour_is_not_erased(tmp_path):
    """全面が背景色なら、抜けば何も残らない。抜いたと名乗らない。"""
    path = tmp_path / "flat.png"
    Image.new("RGB", (256, 256), (200, 10, 10)).save(path)
    before = path.read_bytes()

    assert cut_out_background(path) is False
    assert path.read_bytes() == before


# ── 唐揚げダンジョンの実績から入れたもの ────────────────────────────────
#
# OpenCode が本アドオンで作った game では、agent が自前で chroma key を書いて
# 透過を作っていた（tools/prepare_assets.py）。そこで実際に起きた二つを、
# ここで固定する。勇者の足元には背景色が混ざった桃色の影が残り、閾値を広げて
# それを消すと今度は赤マントに穴が空いた。連結で追いながら、混ざり具合に
# 応じた半透明にするのはそのためである。


def test_a_falloff_of_the_background_becomes_partly_transparent(tmp_path):
    """背景が被写体へ falloff している部分。狭い閾値で切ると塊として残る。"""
    from PIL import ImageDraw

    path = tmp_path / "sprite.png"
    image = Image.new("RGB", (256, 256), (250, 25, 150))
    draw = ImageDraw.Draw(image)
    # 背景色と被写体の中間色。生成物では影がこの帯に入る。
    draw.ellipse((80, 150, 176, 200), fill=(200, 60, 120))
    draw.ellipse((96, 60, 160, 170), fill=(60, 70, 200))
    image.convert("RGBA").save(path)

    assert cut_out_background(path) is True
    with Image.open(path) as result:
        assert result.getpixel((128, 100))[3] == 255      # 被写体は残る
        assert result.getpixel((4, 4))[3] == 0            # 背景は消える
        assert 0 < result.getpixel((90, 180))[3] < 255    # 影は半透明になる


def test_the_background_colour_is_subtracted_from_a_blended_edge(tmp_path):
    """抜いただけでは縁が背景色に染まったまま残る。マゼンタなら桃色の輪郭になる。"""
    from PIL import ImageDraw

    path = tmp_path / "sprite.png"
    image = Image.new("RGB", (256, 256), (255, 0, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((64, 64, 192, 192), fill=(200, 0, 0))
    # 縁 1px ぶんの混色を模す。背景 3 : 被写体 1。
    draw.ellipse((60, 60, 196, 196), outline=(241, 0, 191), width=4)
    image.convert("RGBA").save(path)

    assert cut_out_background(path) is True
    with Image.open(path) as result:
        red, _green, blue, alpha = result.getpixel((128, 62))
        assert 0 < alpha < 255
        # 見えている色は背景 3 : 被写体 1 だった。青が抜けて被写体の赤へ戻る。
        assert blue < 100
        assert red > 150
