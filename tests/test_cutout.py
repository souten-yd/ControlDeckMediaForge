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


def test_an_enclosed_region_of_the_background_colour_is_a_hole(tmp_path):
    """鍵の輪の中や UI 枠の内側は、囲まれていても背景である。実機の 8 件では
    鍵とパネルの 2 件がこれで、マゼンタの塊が残ったまま資産になっていた。"""
    path = tmp_path / "key.png"
    image = Image.new("RGB", (512, 512), (255, 31, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((160, 100, 352, 292), fill=(190, 190, 200))
    draw.ellipse((208, 148, 304, 244), fill=(255, 31, 255))
    image.convert("RGBA").save(path)

    assert cut_out_background(path) is True
    with Image.open(path) as result:
        assert result.getpixel((256, 196))[3] == 0    # 輪の中は抜ける
        assert result.getpixel((256, 120))[3] == 255  # 輪そのものは残る


def test_an_enclosed_region_that_merely_resembles_the_background_survives(tmp_path):
    """背景に近いだけの面までは抜かない。唐揚げダンジョンの gate は中央の渦が
    背景色に近く、閾値だけで消していたときは透けたまま game に入っていた。"""
    path = tmp_path / "gate.png"
    image = Image.new("RGB", (512, 512), (255, 31, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((128, 128, 384, 384), fill=(120, 110, 200))
    # 背景と 55 だけ違う面。厳しい閾値(40)の外、緩い帯(120)の内。
    draw.ellipse((208, 208, 304, 304), fill=(200, 60, 200))
    image.convert("RGBA").save(path)

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


def test_a_small_subject_on_a_large_canvas_is_not_mistaken_for_over_cutting(tmp_path):
    """実機で落ちた形。1024x1024 にスライムが小さく描かれ、背景が 96.1% だった。
    「消えた量」で抜きすぎを見ていたので、上限 95% に掛かって拒否していた。
    被写体が小さいことと、被写体を消したことは別である。"""
    from PIL import ImageDraw

    path = tmp_path / "sprite.png"
    image = Image.new("RGB", (1024, 1024), (255, 31, 255))
    ImageDraw.Draw(image).ellipse((420, 420, 620, 580), fill=(60, 170, 70))
    image.convert("RGBA").save(path)

    assert cut_out_background(path) is True
    with Image.open(path) as result:
        alpha = result.getchannel("A").tobytes()
        assert alpha.count(0) / len(alpha) > 0.95
        assert result.getpixel((512, 500))[3] == 255


def test_erasing_the_subject_is_still_refused(tmp_path):
    """残りが点になる画は「抜けた」と名乗らない。上限を外した代わりの守り。"""
    from PIL import ImageDraw

    path = tmp_path / "sprite.png"
    image = Image.new("RGB", (512, 512), (255, 31, 255))
    # 背景色に紛れる微差の被写体。抜けば何も残らない。
    ImageDraw.Draw(image).ellipse((240, 240, 250, 250), fill=(250, 28, 250))
    image.convert("RGBA").save(path)
    before = path.read_bytes()

    assert cut_out_background(path) is False
    assert path.read_bytes() == before


def test_an_isolated_faint_speck_does_not_stretch_the_bounding_box(tmp_path):
    """背景の揺らぎが 1 画素だけ閾値を超えることがある（実機: スライムの左上に
    alpha 38 が 1 点）。見た目には出ないが、外接矩形が画面全体になる。呼び出し
    側は矩形で切り出して縮めるので、点 1 つで使えない資産になる。"""
    path = tmp_path / "sprite.png"
    image = Image.new("RGB", (512, 512), (255, 31, 255))
    ImageDraw.Draw(image).ellipse((200, 200, 320, 320), fill=(60, 170, 70))
    # 背景でも被写体でもない、閾値をわずかに超えた 1 点。
    image.putpixel((5, 5), (200, 60, 210))
    image.convert("RGBA").save(path)

    assert cut_out_background(path) is True
    with Image.open(path) as result:
        box = result.getchannel("A").getbbox()
    assert box[0] > 100 and box[1] > 100


def test_a_one_pixel_wide_line_is_not_treated_as_a_speck(tmp_path):
    """細い線は開けば消えるが、被写体である。剣の刃や羽根の縁がこれに当たる。"""
    path = tmp_path / "sprite.png"
    image = Image.new("RGB", (512, 512), (255, 31, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((200, 260, 320, 380), fill=(60, 170, 70))
    draw.line((256, 60, 256, 260), fill=(230, 230, 240), width=1)
    image.convert("RGBA").save(path)

    assert cut_out_background(path) is True
    with Image.open(path) as result:
        assert result.getpixel((256, 150))[3] == 255


# ── 形を推定して抜く ────────────────────────────────────────────────────
#
# クロマキーは背景色が縁へ滲むぶんを残す。閾値では消えない性質のもので、実機で
# 残った画素の 3.5〜6.1% が桃色だった。形そのものを推定すれば背景色という前提
# ごと無くなる。合成と可否の判断は core が持つ——model は形を出すだけである。


def _subject_on(background, size=(256, 256), radius=70):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    centre = (size[0] // 2, size[1] // 2)
    draw.ellipse(
        (centre[0] - radius, centre[1] - radius, centre[0] + radius, centre[1] + radius),
        fill=(40, 170, 70),
    )
    return image.convert("RGBA")


def _mask_for(size=(256, 256), radius=70):
    from PIL import Image, ImageDraw

    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    centre = (size[0] // 2, size[1] // 2)
    draw.ellipse(
        (centre[0] - radius, centre[1] - radius, centre[0] + radius, centre[1] + radius),
        fill=255,
    )
    return mask


def test_a_matte_becomes_the_alpha(tmp_path):
    from PIL import Image

    from mediaforge.cutout import apply_matte

    path = tmp_path / "output.png"
    _subject_on((18, 22, 30)).save(path)
    mask_path = tmp_path / "matte.png"
    _mask_for().save(mask_path)

    assert apply_matte(path, mask_path) is True
    with Image.open(path) as opened:
        opened.load()
        result = opened.convert("RGBA")
    assert result.getpixel((4, 4))[3] == 0, "外は透明になっていない"
    assert result.getpixel((128, 128))[3] == 255, "被写体が半透明になっている"


def test_a_matte_over_a_flat_background_leaves_no_colour_cast(tmp_path):
    """model は形を当てるだけで、縁が背景色と混ざっている事実は変わらない。

    平らな背景なら差し引ける。単色背景で描かせた画を抜くと、差し引かないかぎり
    縁に背景色が残る（実機ではマゼンタの輪郭として出ていた）。
    """
    from PIL import Image

    from mediaforge.cutout import FLAT_BACKGROUND_RGB, apply_matte

    path = tmp_path / "output.png"
    image = _subject_on(FLAT_BACKGROUND_RGB)
    # 縁を 1 画素ぶん背景と混ぜる。生成物の縁はこうなっている。
    blurred = image.filter(__import__("PIL.ImageFilter", fromlist=["ImageFilter"]).GaussianBlur(2))
    blurred.save(path)
    mask_path = tmp_path / "matte.png"
    _mask_for().save(mask_path)

    assert apply_matte(path, mask_path) is True
    with Image.open(path) as opened:
        opened.load()
        result = opened.convert("RGBA")
    kept = [(p[:3], p[3]) for p in result.getdata() if p[3] > 0]
    pink = [c for c, _a in kept if c[0] > c[1] + 40 and c[2] > c[1] + 40]
    assert len(pink) * 100 / len(kept) < 1.0, f"桃色が {len(pink)}/{len(kept)} 残っている"


def test_a_matte_that_keeps_nothing_is_refused(tmp_path):
    """抜きすぎたものを「透過あり」として通さない。検査が理由を名指しできる
    ように、触らずに False を返す。"""
    from PIL import Image

    from mediaforge.cutout import apply_matte

    path = tmp_path / "output.png"
    _subject_on((18, 22, 30)).save(path)
    before = path.read_bytes()
    mask_path = tmp_path / "matte.png"
    Image.new("L", (256, 256), 0).save(mask_path)

    assert apply_matte(path, mask_path) is False
    assert path.read_bytes() == before


def test_a_matte_that_removes_nothing_is_refused(tmp_path):
    from PIL import Image

    from mediaforge.cutout import apply_matte

    path = tmp_path / "output.png"
    _subject_on((18, 22, 30)).save(path)
    before = path.read_bytes()
    mask_path = tmp_path / "matte.png"
    Image.new("L", (256, 256), 255).save(mask_path)

    assert apply_matte(path, mask_path) is False
    assert path.read_bytes() == before


def test_a_matte_of_the_wrong_size_is_refused(tmp_path):
    from PIL import Image

    from mediaforge.cutout import apply_matte

    path = tmp_path / "output.png"
    _subject_on((18, 22, 30)).save(path)
    mask_path = tmp_path / "matte.png"
    Image.new("L", (128, 128), 255).save(mask_path)

    assert apply_matte(path, mask_path) is False


def test_the_matting_path_says_when_it_cannot_run(tmp_path):
    """重みが無い環境では黙って従来の経路へ落ちる。壊れたことにしない。"""
    import pytest

    from mediaforge.matting import MattingUnavailable, matte_mask

    with pytest.raises(MattingUnavailable):
        matte_mask(
            tmp_path / "in.png", tmp_path / "out.png",
            runtime_python=None, model_path=None, repository_root=tmp_path,
        )
    with pytest.raises(MattingUnavailable):
        matte_mask(
            tmp_path / "in.png", tmp_path / "out.png",
            runtime_python=tmp_path / "python", model_path=tmp_path / "model.onnx",
            repository_root=tmp_path,
        )
