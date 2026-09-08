"""透過を求められた資産から、平らな背景を決定的に抜く。

sprite / icon / emblem / ui_element は重ねて使うので brief の alpha は既定で
`required` である。ところが拡散モデルは透過を出力しない。adapter はどれも
`convert("RGBA")` するだけで、alpha は全画素 255 のままになる。結果として
`inspect_against_brief` の `alpha_missing` が必ず立ち、これらの用途は成功
しうる道が一つも無い状態だった（実機ログでは `alpha_intent: required` の
依頼がすべて 502 で返っていた）。

作れないものを検査で咎めても資産は出てこないので、canvas と同じ形にする。
`conform_to_layout` が「学習寸法のバケットで生成し、後で要求の画面へ揃える」
のと同じく、ここは「単色背景で生成し、後でその背景を抜く」を受け持つ。
どちらも決定的な後処理で、検査より前に完結する。

抜き方は、唐揚げダンジョン（OpenCode が実際に本アドオンを使って作った game）
で agent が自前で書いた `tools/prepare_assets.py` の実績を土台にしている。
そこで分かったことが三つある。

  1. 生成されたのは頼んだ色そのものではない。純マゼンタ (255,0,255) を
     指定しても届いたのは (250,25,150) 付近で、画面内でも数値が揺れていた。
     指定色を鍵にはできない。縁を測って実際の色を鍵にする。
  2. 閾値だけで消すと被写体に穴が空く。あの gate スプライトは中央の渦が
     背景色に近く、透けたまま game に入っていた。届く範囲に限れば残る。
  3. 逆に閾値が狭すぎると、背景が被写体へ falloff している部分が残る。
     勇者の足元の影は背景色に混ざった桃色の塊として残っていた。狭い閾値で
     切るのではなく、混ざり具合に応じた半透明として抜く必要がある。

そこで二段にする。確実に背景である範囲は完全に透明にし、その外側の「背景が
混ざっている」範囲は距離に応じた半透明にする。連結は緩いほうの範囲で追う
ので、影のような falloff も背景から地続きに抜ける。最後に、混ざった画素から
背景の寄与を差し引く（縁に残る色被りを消す）。

平らでない背景は抜かない。抜けないものを無理に抜くと、直したつもりで被写体
を削った資産が「透過あり」として通ってしまう。抜けなければ False を返し、
`alpha_missing` が理由をそのまま名指しする。
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from statistics import median

from PIL import Image, ImageChops, ImageFilter, ImageMath


# 完全に背景とみなす色差（チャンネルごとの差の最大）。生成物の背景は単色を
# 頼んでも一様ではなく、実測では画面内で 10 前後は揺れていた。
TOLERANCE = 40

# ここまでは「背景が混ざっている」とみなし、混ざり具合に応じて半透明にする。
# 勇者の足元の桃色の影がこの帯に入る。広げすぎると被写体側の暗部を削るので、
# 背景色が被写体に現れない前提（生成側へそう頼んでいる）で決めている。
SPILL_TOLERANCE = 120

# ほとんど抜けないなら、そもそも抜ける背景が無い。「抜けた」と名乗らない。
MIN_REMOVED = 0.05

# 抜きすぎの検出は、消えた量ではなく残ったもので行う。上限を面積で置いていた
# ときは、1024x1024 に小さく描かれたスプライトが抜きすぎと区別できなかった
# （実機: スライムは背景 96.1% で、上限 95% に掛かって拒否された）。被写体が
# 小さいことと、被写体を消したことは別である。
#
# 残った不透明の面積と、その外接矩形の辺で見る。被写体を削った画は、残りが
# 散った点になるか、矩形が潰れる。
MIN_SUBJECT_PIXELS = 1024
MIN_SUBJECT_SIDE = 16

# 縁のうち背景色に収まっている割合の下限。これを割るなら、そもそも単色背景
# ではない（風景や光源が縁まで来ている）。
BORDER_FLATNESS = 0.9

# 生成側への予防。抜ける背景で描かせておくほうが、抜けない背景を後から
# どうにかするより確実である。色を名指しするのは唐揚げダンジョンの実績に
# 倣ったもので、マゼンタは被写体の色と衝突しにくい。そのとおりの色は返って
# こないが、被写体から遠い色が返ってくれば鍵としては十分である。
# 背景に頼む色。指示文と、参照画像を平らにするときで同じものを使う。
FLAT_BACKGROUND_RGB = (255, 0, 255)

FLAT_BACKGROUND_DIRECTIVE = (
    "Place the single subject alone on a completely flat, uniform pure magenta "
    "(RGB 255, 0, 255) background. The magenta must not appear anywhere in the "
    "subject itself. No scenery, no gradient, no vignette, no glow, no cast "
    "shadow, no ground plane, no frame or border. The subject must not touch "
    "the edges of the image."
)

# 呼び出し側が書いた背景の注文。透過を求められている限り、背景はこちらが
# 決めるものなので、この語を含む節は worker へ渡す複製から落とす。
#
# 落とさないと、一つのプロンプトに矛盾した二つの指示が入る。実際の依頼は
# "golden coin game icon, dark background" や "……、背景なし" であり、そこへ
# 上のマゼンタ指示が続く。モデルは間を取った絵を返し、抜けない背景になる。
# 契約（schemas/job-request.json）にも「背景に触れるな」と書いてあるが、
# 説明文は助言にすぎない。守られなかったときに壊れない側に倒す。
#
# 語彙は狭く保つ。asset_brief の役割推定と同じで、確信が持てないものまで
# 削ると呼び出し側の意図を静かに失う。
_BACKGROUND_WORDS: tuple[str, ...] = ("background", "backdrop", "背景")

# 節の切れ目。英語の読点と句点、日本語の読点と句点、改行。
_CLAUSE_MARKS = ",.;\n、。"


def without_background_clauses(intent: str) -> str:
    """背景を注文している節を落とす。落とすものが無ければそのまま返す。

    節ごとに見るのは、背景の語だけを抜くと "on a dark" のような残骸が
    残るからである。全部が背景の話だったときは元の文を返す——何も言わない
    プロンプトを worker へ渡すより、矛盾したまま渡すほうがまだ絵になる。
    """
    clauses: list[str] = []
    current: list[str] = []
    for character in intent:
        current.append(character)
        if character in _CLAUSE_MARKS:
            clauses.append("".join(current))
            current = []
    if current:
        clauses.append("".join(current))
    kept = [
        clause for clause in clauses
        if not any(word in clause.lower() for word in _BACKGROUND_WORDS)
    ]
    if not kept:
        return intent
    remaining = "".join(kept).strip().strip(",.;、。").strip()
    return remaining or intent

_REACHED = bytes([0, 255]) + bytes(254)


def _border(image: Image.Image) -> list[tuple[int, int, int]]:
    """縁 1px の画素。背景は縁にあり、被写体は縁に無い前提で見る。"""
    width, height = image.size
    edges = (
        image.crop((0, 0, width, 1)),
        image.crop((0, height - 1, width, height)),
        image.crop((0, 0, 1, height)),
        image.crop((width - 1, 0, width, height)),
    )
    raw = b"".join(edge.tobytes() for edge in edges)
    return [(raw[index], raw[index + 1], raw[index + 2]) for index in range(0, len(raw), 3)]


def _background_colour(border: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    """縁の代表色。平均だと被写体が縁に掛かった分だけ色が動くので中央値を使う。"""
    return (
        int(median(pixel[0] for pixel in border)),
        int(median(pixel[1] for pixel in border)),
        int(median(pixel[2] for pixel in border)),
    )


def _flatness(border: list[tuple[int, int, int]], colour: tuple[int, int, int]) -> float:
    within = sum(
        1 for pixel in border
        if max(abs(pixel[index] - colour[index]) for index in range(3)) <= TOLERANCE
    )
    return within / len(border) if border else 0.0


def _distance(image: Image.Image, colour: tuple[int, int, int]) -> Image.Image:
    """背景色からの色差。

    チャンネルごとの差の最大を見る。輝度に落とすと、明るさの近い別の色
    （同じ明度の青と緑）が同じ色として通ってしまう。
    """
    difference = ImageChops.difference(image, Image.new("RGB", image.size, colour))
    red, green, blue = difference.split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


def _ramp(value: int) -> int:
    """色差から不透明度へ。背景そのものは 0、混ざりは距離なりの半透明。"""
    if value <= TOLERANCE:
        return 0
    if value >= SPILL_TOLERANCE:
        return 255
    return round((value - TOLERANCE) * 255 / (SPILL_TOLERANCE - TOLERANCE))


def _reachable_from_border(near: bytearray, width: int, height: int) -> bytearray:
    """縁から届く背景画素に 1 を立てる。

    走査線ごとに埋め、隣の行へは連続区間の先頭だけを積む。1 画素ずつ積むと
    1024x1024 の大半が背景のとき積む回数が百万単位になる。区間の切れ目は
    bytearray の find に探させる。
    """
    reached = bytearray(width * height)
    stack: deque[tuple[int, int]] = deque()
    for x in range(width):
        stack.append((x, 0))
        stack.append((x, height - 1))
    for y in range(height):
        stack.append((0, y))
        stack.append((width - 1, y))
    while stack:
        x, y = stack.pop()
        row = y * width
        if not near[row + x]:
            continue
        opened = near.rfind(0, row, row + x)
        left = 0 if opened == -1 else opened - row + 1
        closed = near.find(0, row + x, row + width)
        right = width - 1 if closed == -1 else closed - row - 1
        span = right - left + 1
        # 埋めた区間は候補から外す。外さないと同じ区間を何度も積み直す。
        near[row + left:row + right + 1] = bytes(span)
        reached[row + left:row + right + 1] = b"\x01" * span
        for neighbour in (y - 1, y + 1):
            if not 0 <= neighbour < height:
                continue
            base = neighbour * width
            stop = base + right + 1
            index = near.find(255, base + left, stop)
            while index != -1:
                stack.append((index - base, neighbour))
                end = near.find(0, index + 1, stop)
                if end == -1:
                    break
                index = near.find(255, end + 1, stop)
    return reached


def _without_spill(
    image: Image.Image, alpha: Image.Image, colour: tuple[int, int, int]
) -> Image.Image:
    """半透明になった画素から背景の寄与を差し引く。

    見えている色は c = a*f + (1-a)*b である。b（背景色）と a は分かって
    いるので f を戻せる。戻さないと、縁が背景色に染まったまま別の背景へ
    重なる（マゼンタで抜けば桃色の輪郭が残る）。

    完全に透明な画素は触らない。見えない画素の色を作り替えても意味が無く、
    a が 0 に近いところでは復元が暴れるだけである。
    """
    clear = alpha.point(lambda value: 255 if value == 0 else 0)
    bands = []
    for band, level in zip(image.split(), colour):
        restored = ImageMath.lambda_eval(
            lambda args: args["convert"](
                args["min"](
                    args["max"](
                        (args["c"] * 255 - (255 - args["a"]) * args["b"])
                        / args["max"](args["a"], 1),
                        0,
                    ),
                    255,
                ),
                "L",
            ),
            c=band,
            a=alpha,
            b=level,
        )
        bands.append(Image.composite(band, restored, clear))
    return Image.merge("RGB", bands)


# 孤立した薄い点をノイズとみなす境目。濃い点は残す——1 画素の線（剣の刃や
# 羽根の縁）はここを通しても消えない。
SPECK_ALPHA = 128


def _without_specks(alpha: Image.Image) -> Image.Image:
    """周りが完全に透明な、薄い 1 点を落とす。

    背景の揺らぎが 1 画素だけ閾値を超えることがある（実機のスライムは左上に
    alpha 38 が 1 点だけ残った）。見た目には出ないが、外接矩形が画面全体に
    なる。呼び出し側は矩形で切り出して縮めるので（唐揚げダンジョンの
    prepare_assets がそうしている）、点 1 つで使えない資産になる。

    落とすのは薄いものだけに限る。濃い画素は、たとえ 1 画素幅でも被写体の線で
    ある。開いた（収縮→膨張）結果が空になるのは細い線も同じなので、そこだけで
    判断すると剣の刃が消える。
    """
    opened = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    isolated = opened.point(lambda value: 255 if value == 0 else 0)
    faint = alpha.point(lambda value: 255 if value < SPECK_ALPHA else 0)
    return Image.composite(
        Image.new("L", alpha.size, 0), alpha, ImageChops.darker(isolated, faint)
    )


def _subject_survives(alpha: Image.Image, opaque_pixels: int) -> bool:
    """抜いた後に、被写体と呼べるものが残っているか。"""
    if opaque_pixels < MIN_SUBJECT_PIXELS:
        return False
    box = alpha.getbbox()
    if box is None:
        return False
    left, top, right, bottom = box
    return right - left >= MIN_SUBJECT_SIDE and bottom - top >= MIN_SUBJECT_SIDE


def flatten_onto_flat_background(path: Path) -> bool:
    """透過を持つ画を、頼むのと同じ単色の上へ置き直す。置き換えたときだけ True。

    編集は元画像を参照として model へ渡す。透過を持つ資産をそのまま渡すと、
    透明だった所は model に届くまでに黒へ潰れる（実測: 唐揚げダンジョンの
    slime.png を参照にした編集が、真っ黒な背景で返ってきた）。透明は「無い」
    であって「黒」ではないので、こちらで意味のある色を置く。

    置く色は、透過を作るときに model へ頼むのと同じ単色である。参照も指示も
    同じ背景を指すことになり、返ってきた画は後段の `cut_out_background` が
    そのまま抜ける。

    透過が無い画は触らない。触る理由が無い。
    """
    with Image.open(path) as opened:
        opened.load()
        image = opened.convert("RGBA")
    if image.getchannel("A").getextrema()[0] == 255:
        return False
    flat = Image.new("RGBA", image.size, (*FLAT_BACKGROUND_RGB, 255))
    Image.alpha_composite(flat, image).save(path, format="PNG")
    return True


def cut_out_background(path: Path) -> bool:
    """`path` の平らな背景を透明にする。抜いたときだけ True。

    抜けない画は触らない。触らなければ検査がそのまま理由を名指しする。
    """
    with Image.open(path) as opened:
        opened.load()
        image = opened.convert("RGBA")
    if image.getchannel("A").getextrema()[0] < 255:
        # すでに透過がある。作り直す理由が無い。
        return False
    width, height = image.size
    if width < 3 or height < 3:
        return False
    rgb = image.convert("RGB")
    border = _border(rgb)
    colour = _background_colour(border)
    if _flatness(border, colour) < BORDER_FLATNESS:
        return False
    distance = _distance(rgb, colour)
    candidates = bytearray(
        distance.point(lambda value: 255 if value <= SPILL_TOLERANCE else 0).tobytes()
    )
    reached = _reachable_from_border(candidates, width, height)
    alpha = Image.composite(
        distance.point(_ramp),
        Image.new("L", (width, height), 255),
        Image.frombytes("L", (width, height), bytes(reached).translate(_REACHED)),
    )
    # 背景色そのものは、縁から届かなくても背景である。鍵の輪の中や UI 枠の内側
    # は囲まれているので連結では届かないが、そこは穴であって被写体ではない
    # （実機の 8 件では鍵とパネルの 2 件がこれで、マゼンタの塊が残っていた）。
    #
    # 抜くのは厳しいほうの閾値に収まるものだけに限る。緩い帯（背景が混ざって
    # いる範囲）まで連結を無視すると、被写体の中の似た色に穴が空く。唐揚げ
    # ダンジョンの gate がその形で、中央の渦が透けたまま game に入っていた。
    alpha = ImageChops.darker(alpha, distance.point(lambda value: 0 if value <= TOLERANCE else 255))
    alpha = _without_specks(alpha)
    raw = alpha.tobytes()
    if raw.count(0) / (width * height) < MIN_REMOVED:
        return False
    if not _subject_survives(alpha, len(raw) - raw.count(0)):
        return False
    cleaned = _without_spill(rgb, alpha, colour)
    cleaned.putalpha(alpha)
    cleaned.save(path, format="PNG")
    return True
