"""道具の説明の書き方を縛る。

規約は ControlDeck の docs/addon-agent-tool-writing.md にある。ここでは
機械で見られるところだけを検査する。

なぜ要るか: 2026-09-11 に数えたとき、MediaForge と SonicForge の 22 個のうち
11 個は label 一行だけで、用途の説明が無かった。ローカルモデル（Qwen3.8-27B）で
測ると、誤って選ばれた道具は全部その側だった。3D の場面へ照明を足す依頼で、
モデルは media.scene.snapshot を三回呼んで media.scene.export へ流れ、
media.scene.edit に辿り着けなかった。snapshot に「場面を変えるためには使わない
——media.scene.edit を呼ぶこと」を足すと通った。

Haiku では同じ題が全部通る。書いていないことを名前から補えるかどうかの差で、
補えないモデルのほうが多い。
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]

# 呼ぶ側の語ではない。書くと、用途を書くべき場所が埋まる。
IMPLEMENTATION_WORDS = (
    "typed", "durable", "bounded", "owner-scoped", "immutable", "recipe", "detached",
)
# 読むだけの道具。名詞が依頼と一致しやすく、行動する道具に勝ってしまう。
READ_ONLY_TOOLS = {
    "media.capabilities", "media.inspect", "media.scene.snapshot",
    "media.job.status", "media.scene.export",
}
LABEL_LIMIT = 80
# 用途・前提・使わない場面まで書けば、どうしてもこれくらいにはなる。
DESCRIPTION_MINIMUM = 120


def agent_tools():
    manifest = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
    return manifest["contributions"]["agent_tools"]


def schema_of(tool):
    path = ROOT / str(tool["schema_path"]).lstrip("/")
    return json.loads(path.read_text(encoding="utf-8"))


def label_of(tool):
    label = tool["label"]
    if isinstance(label, dict):
        return label.get("en") or label.get("ja") or tool["id"]
    return label


@pytest.mark.parametrize("tool", agent_tools(), ids=lambda t: t["id"])
def test_the_label_says_what_the_tool_does_without_implementation_words(tool):
    label = label_of(tool)
    assert len(label) <= LABEL_LIMIT, f"{tool['id']}: labelが長い（{len(label)}文字）"
    lowered = label.lower()
    leaked = [word for word in IMPLEMENTATION_WORDS if word in lowered]
    assert not leaked, f"{tool['id']}: 呼ぶ側の語ではない: {leaked}"


@pytest.mark.parametrize("tool", agent_tools(), ids=lambda t: t["id"])
def test_every_agent_tool_says_what_it_is_for(tool):
    """label だけでは、一覧から選ぶ側に用途が届かない。"""
    description = schema_of(tool).get("description")
    assert isinstance(description, str) and description.strip(), (
        f"{tool['id']}: 入力schemaにtop-level descriptionが無い。"
        "一覧に出る説明がlabel一行だけになる"
    )
    assert len(description) >= DESCRIPTION_MINIMUM, (
        f"{tool['id']}: 説明が{len(description)}文字しかない。"
        "何のためか・いつ呼ぶか・何に使わないかを書く"
    )


@pytest.mark.parametrize(
    "tool", [t for t in agent_tools() if t["id"] in READ_ONLY_TOOLS], ids=lambda t: t["id"]
)
def test_a_read_only_tool_says_what_it_is_not_for(tool):
    """読むだけの道具は、行動する道具の代わりに選ばれる。名指しで断る。"""
    description = schema_of(tool)["description"]
    assert any(phrase in description for phrase in
               ("does not", "not how", "changes nothing", "makes nothing", "starts nothing",
                "cannot be", "It is not")), (
        f"{tool['id']}: 「何をしない道具か」が書かれていない"
    )
    assert any(other["id"] in description for other in agent_tools()
               if other["id"] != tool["id"]), (
        f"{tool['id']}: 代わりに呼ぶべき道具を名指ししていない"
    )


def test_two_tools_never_share_one_input_schema():
    """top-level descriptionは道具ごとの用途を書く場所である。共有すると
    どちらの用途も書けない。形が同じでもファイルを分ける。"""
    seen: dict[str, str] = {}
    for tool in agent_tools():
        path = str(tool["schema_path"])
        assert path not in seen, (
            f"{tool['id']} と {seen[path]} が {path} を共有している。分けること"
        )
        seen[path] = tool["id"]
