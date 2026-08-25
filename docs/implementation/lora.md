# LoRA を使えるようにする

## LoRA は「モデル」ではない

選んだ checkpoint の上に載せるもので、単体では絵を作れない。だから routing が
これを「使えるモデル」として選んではいけない。

registry には別の capability（`image.lora`）で載せる。routing は
`capability in item.capabilities` で候補を絞るので、`image.text_to_image` を
求める経路には最初から現れない。旗を立てて後から除外する作りにすると、
除外を書き忘れた経路が 1 つでもあれば LoRA が本体として選ばれる。

別の入れ物を作らないのは、取得・再開・digest 照合・進捗・削除が既に
ModelOperationManager にあるためである。同じものを 2 つ持つと、片方だけ直る。

## 実測して分かっていること（2026-08-25）

```text
種別    types=LORA。Checkpoint と同じ /api/v1/models で引ける
大きさ  36 MB 〜 218 MB。checkpoint の 2GB とは桁が違う
系統    version.baseModel が "SD 1.5" / "SDXL 1.0" / "Pony" を名乗る
起動語  version.trainedWords。空の LoRA もある
digest  file.hashes.SHA256 が付く
```

## 系統が合わないものは載せない

SD 1.5 の LoRA を SDXL に載せると、次元が合わずに落ちるか、運が悪いと
形だけ通って絵が崩れる。checkpoint 側の系統と突き合わせて、合わないものは
その場で理由を付けて断る。

Pony と Illustrious は SDXL 派生だが、LoRA の互換は系統ごとに切れている。
同じ正規化（`normalize_base_model`）で見て、完全一致だけを通す。

## 起動語

起動語を持つ LoRA は、それを prompt に入れないと何も起きない。持っている
ものは自動で prompt に足し、何を足したかを画面に出す。黙って足さない。

## 作るもの

1. Civitai 検索に LoRA を足す。種別で絞れるようにする。
2. `image.lora` capability の registry entry として取り込む。起動語と系統を
   descriptor に持たせる。
3. 要求の `constraints.loras` = `[{model_id, weight}]`。系統の一致と枚数
   （4 まで）と強さ（0〜2）を core で検証する。
4. worker で `load_lora_weights` と `set_adapters`。前回と違う組み合わせなら
   先に外す。外さないと重なって効く。
5. VRAM の見積りに LoRA の分を足す。足さないと、載る判定で載らない。
6. UI に LoRA の選択と強さ。選んだ checkpoint に載せられるものだけ出す。

## 確かめ方

実機で LoRA を 1 つ落として、同じ seed で「無し」と「有り」を作り、絵が
変わることを見る。変わらなければ載っていない。

## やらないこと

* LoRA の学習。使うだけ。
* checkpoint 以外への適用（動画モデルなど）。経路が別で、実測もできていない。
