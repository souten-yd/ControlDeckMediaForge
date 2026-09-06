"""生成した画を、brief が決めた画面へ揃える。

生成と契約は別々の都合で寸法を決める。生成側 (`snap_to_native`) は「そのモデルが
学習した面積・比」へ寄せる。比を守ったまま学習寸法に近づけないと、同じ被写体が
2 つ並ぶような崩れ方をするからである。一方 brief 側は「16:9 の 1024x576」という
使い道そのものを決めており、受け取る側はその画面でしか使えない。

この二つは両方とも正しいので、どちらかを捨てるのではなく順番に満たす。学習寸法の
バケットで生成し、その後で要求どおりの画面へ揃える。揃えないと、比を守って
きちんと描けた画が canvas_mismatch として毎回捨てられる（16:9 を頼むと 1024x576 と
決まり、生成は 1344x768 のバケットで行われ、検査がその差を見て落としていた）。

比がバケットと厳密に一致しないこともある（1344/768 = 1.75、16:9 = 1.7778）。
足りないぶんは中央を残して切る。brief の safe_area は割合で書かれているので、
中央基準で切っても意味は保たれる。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

# 拡大は画を作らない。バケットのほうが小さいときだけ起きるが、落とすよりは
# 要求どおりの画面で返すほうが使える。
RESAMPLE = Image.Resampling.LANCZOS


def _center_crop(image: Image.Image, ratio: float) -> Image.Image:
    """求められた比になるまで、中央を残して切る。"""
    width, height = image.size
    if height and abs(width / height - ratio) < 1e-6:
        return image
    if width / height > ratio:
        cropped = max(1, round(height * ratio))
        left = (width - cropped) // 2
        return image.crop((left, 0, left + cropped, height))
    cropped = max(1, round(width / ratio))
    top = (height - cropped) // 2
    return image.crop((0, top, width, top + cropped))


def conform_to_layout(path: Path, width: int, height: int) -> bool:
    """`path` の画を width x height へ揃える。揃え直したときだけ True。

    透過は保つ。alpha の有無は brief の別の条件として検査されるので、ここで
    落とすと直したつもりで別の defect を作ることになる。
    """
    if width <= 0 or height <= 0:
        return False
    with Image.open(path) as image:
        image.load()
        if image.size == (width, height):
            return False
        conformed = _center_crop(image, width / height).resize((width, height), RESAMPLE)
        conformed.save(path, format="PNG")
    return True
