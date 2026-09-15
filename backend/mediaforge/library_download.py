"""ライブラリから素材を手元の端末へ持ち出す。

これまで持ち出せるのは原寸表示を開いた 1 件だけだった。携帯から使うと、
選んで見る・開く・保存する、を件数ぶん繰り返すことになる。ここは選んだぶんを
1 つの zip にまとめ、**押した瞬間に落ち始める**経路を用意する。

押した瞬間に、というのが効く。iOS の Safari は、利用者の操作から離れた場所で
始まった遷移をダウンロードとして扱わないことがある。先に組み立ててから URL を
差し替える形にすると、組み立てを待つ間に操作との繋がりが切れる。だからこの
経路は **GET 一本** で、押した先がそのまま zip である。組み立ては要求を受けた
側でやる。

zip は要求のたびに作って、返し終えたら消す。素材は増減するので、作り置きを
持つと「古い zip が落ちてくる」ことになる。
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# 1 回に持ち出せる件数。
#
# 押した瞬間に落ち始めるようにするため、選んだ素材の id は URL に載る。上限が
# 無いと URL が伸びて、途中で切れても切れたことが分からない。100 件で id は
# 概ね 4KB に収まる。
MAX_ASSETS = 100

# 1 回に持ち出せる合計。
#
# 相手は携帯であることが多い。入り切らない大きさを黙って送り始めると、詰まった
# ことしか分からない形で失敗する。断って、選び直してもらうほうがよい。
MAX_TOTAL_BYTES = 2 * 1024**3

# zip の中の名前として許す文字。素材の提案名はこちらが付けているが、取り込んだ
# ものが混ざる経路があるので、ここで必ず通す。区切り文字を含む名前を書き込むと
# 展開した先で階層が生える。
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class DownloadRefused(Exception):
    """持ち出しを断る。code は画面がそのまま文言へ訳せるものにする。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Entry:
    asset_id: str
    path: Path
    name: str
    size_bytes: int


def safe_name(value: str, fallback: str) -> str:
    cleaned = _UNSAFE.sub("-", str(value or "")).strip("-.")
    return cleaned or fallback


def archive_name(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"media-forge-{stamp}.zip"


def plan(store, asset_ids: Iterable[str]) -> list[Entry]:
    """何を詰めるかを先に決める。詰めながら気づくのでは遅い。

    重複した id は 1 件に畳む。名前がぶつかったら連番を付ける——同じ名前で
    2 つ書き込むと、展開したとき片方が消える。
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for asset_id in asset_ids:
        value = str(asset_id or "")
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    if not ordered:
        raise DownloadRefused("download_empty", "持ち出す素材が選ばれていません")
    if len(ordered) > MAX_ASSETS:
        raise DownloadRefused(
            "download_too_many",
            f"一度に持ち出せるのは {MAX_ASSETS} 件までです（{len(ordered)} 件選ばれています）",
        )

    entries: list[Entry] = []
    used: set[str] = set()
    total = 0
    for index, asset_id in enumerate(ordered, 1):
        try:
            asset = store.get_asset(asset_id)
            path = store.asset_path(asset_id)
        except KeyError as exc:
            raise DownloadRefused("asset_not_found", f"{asset_id} が見つかりません") from exc
        if not path.is_file():
            raise DownloadRefused("asset_not_found", f"{asset_id} の中身がありません")
        name = safe_name(asset.suggested_filename, f"media-forge-{index:03d}")
        stem, dot, suffix = name.rpartition(".")
        if not dot:
            stem, suffix = name, ""
        candidate = name
        bump = 2
        while candidate.lower() in used:
            candidate = f"{stem}-{bump}{'.' + suffix if suffix else ''}"
            bump += 1
        used.add(candidate.lower())
        total += int(asset.size_bytes or 0)
        entries.append(Entry(asset_id, path, candidate, int(asset.size_bytes or 0)))

    if total > MAX_TOTAL_BYTES:
        raise DownloadRefused(
            "download_too_large",
            f"合計 {total // 1024 // 1024} MB は一度に持ち出せる大きさを超えています",
        )
    return entries


def build(entries: list[Entry], target: Path) -> Path:
    """zip を作る。

    圧縮はしない。中身は既に png / webp / mp4 / glb で、どれも圧縮済みである。
    かけ直しても縮まないうえ、待ち時間だけが伸びる——押した先で待たされる経路
    なので、そこは削る。
    """
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for entry in entries:
            archive.write(entry.path, arcname=entry.name)
    return target


# 返し終えた zip は消すが、途中で落ちたぶんは残る。残ったまま溜まると、置き場が
# 静かに膨らむ。作る前に古いものを掃く——掃除のためだけに別の仕掛けを増やさない。
STALE_AFTER_SEC = 3600


def sweep(directory: Path, now: float, max_age_sec: int = STALE_AFTER_SEC) -> int:
    """置き場に残った古い zip を消す。消した数を返す。"""
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.glob("*.zip"):
        try:
            if now - path.stat().st_mtime < max_age_sec:
                continue
            path.unlink()
        except OSError:
            continue
        removed += 1
    return removed
