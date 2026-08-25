# 配布元として Civitai を選べるようにする

## なぜ

Hugging Face には diffusers 形式の基盤モデルが並ぶが、実際に絵を作るときに
使われている調整済みモデルの多くは Civitai にある。検索できないものは
存在しないのと同じなので、切り替えられるようにし、既定を Civitai にする。

## 実測して分かっていること（2026-08-25）

```text
検索    GET /api/v1/models        認証不要。件数・作者・stats・version・file を返す
形式    1 version = 1 .safetensors。SD 1.5 の pruned fp16 でおよそ 2.0 GB
系統    version.baseModel が "SD 1.5" / "SDXL 1.0" / "Flux.1 D" などを名乗る
digest  file.hashes.SHA256 が付く
取得    /api/download/models/{versionId} が署名付き URL へ転送する
```

curl の既定 UA では 403 が返る。ブラウザの UA を付けると通る。認証の問題では
ないので、API key を要求しない。ただし early access のモデルは 401 を返すので、
その場合だけ利用者に鍵を求める。

## 何が足りないか

**Civitai のモデルは今の Media Forge では動かない。** 配布されるのは単一の
safetensors で、画像ワーカーの `diffusers.sdxl` は `from_pretrained` で
ディレクトリを読む。`diffusers.sdxl-single-file` は models.json に名前だけ
あって実装が無い。

検索だけ足すと「見つかるが動かない」ものが既定で並ぶことになる。それは
検索を足さないより悪い。単一ファイルの読み込みまで含めて 1 つの作業とする。

系統は safetensors の中身から判定しない。判定には UNet の次元を読む必要が
あり、Pony や Illustrious のような派生で外す。配布元が `baseModel` として
名乗っているものを使い、名乗っていなければ取り込まない。

## 作るもの

1. `sources.py` — 配布元 1 つを表す interface。`search()` と `resolve()` を持つ。
   Hugging Face は既存の実装をそのまま移す。
2. `CivitaiSource` — 上の実測に沿った実装。UA を付ける。nsfw は既定で外す。
3. `ModelSource.kind` に `civitai` を足す。`repo_id` は `civitai/{modelId}`、
   `revision` は version id。どちらも既存の pattern に収まる。
4. `model_manager` の取得 URL を kind ごとに分ける。今は Hugging Face の
   `resolve/` 形式が直書きされている。
5. `diffusers.sdxl-single-file` を worker に実装する。`from_single_file` を
   使い、pipeline クラスは宣言された baseModel から選ぶ。
6. UI に配布元の切り替えを置く。既定は Civitai。選択は preferences に残す。

## 確かめ方

* 実機で Civitai から 1 つ落として、評価を通し、実際に生成して絵を見る
* Hugging Face 側が壊れていないことを、既存の検索と取り込みで確かめる

## やらないこと

* LoRA。Civitai の多くは LoRA だが、Media Forge に LoRA の経路がまだ無い。
  検索では Checkpoint に絞る。LoRA を並べても取り込めない。
* NSFW の閲覧。既定で外す。
