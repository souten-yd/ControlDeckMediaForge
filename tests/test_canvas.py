"""生成した画を brief の画面へ揃える処理。"""

from PIL import Image

from mediaforge.canvas import conform_to_layout


def _write(tmp_path, size, mode="RGB"):
    path = tmp_path / "out.png"
    Image.new(mode, size, "white").save(path)
    return path


def test_snapped_bucket_becomes_the_resolved_canvas(tmp_path):
    """16:9 を頼むと 1024x576 に決まり、生成は 1344x768 のバケットで行われる。"""
    path = _write(tmp_path, (1344, 768))
    assert conform_to_layout(path, 1024, 576) is True
    with Image.open(path) as image:
        assert image.size == (1024, 576)


def test_matching_canvas_is_left_alone(tmp_path):
    path = _write(tmp_path, (1024, 576))
    before = path.read_bytes()
    assert conform_to_layout(path, 1024, 576) is False
    assert path.read_bytes() == before


def test_transparency_survives(tmp_path):
    """alpha の有無は brief の別の条件なので、揃える過程で失ってはいけない。"""
    path = tmp_path / "out.png"
    Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)).save(path)
    assert conform_to_layout(path, 512, 512) is True
    with Image.open(path) as image:
        assert image.mode == "RGBA"
        assert image.getextrema()[3] == (0, 0)


def test_ratio_is_reached_by_cropping_the_centre(tmp_path):
    """比がバケットと厳密に一致しなくても、引き伸ばさずに揃える。"""
    path = tmp_path / "out.png"
    image = Image.new("RGB", (1000, 500), "black")
    for x in range(400, 600):
        for y in range(200, 300):
            image.putpixel((x, y), (255, 255, 255))
    image.save(path)
    assert conform_to_layout(path, 500, 500) is True
    with Image.open(path) as result:
        assert result.size == (500, 500)
        # 中央の目印は中央に残る。端から切っていれば寄る。
        assert result.getpixel((250, 250)) == (255, 255, 255)
