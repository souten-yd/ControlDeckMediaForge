# Codex実装指示 — Media Forge 実行環境の分離と自動整備

対象リポジトリ: `souten-yd/ControlDeckMediaForge`
位置づけ: **MF0-0（[`mf0-addon-core.md`](mf0-addon-core.md) の MF0-1 より前）**
全体像: [`goal-roadmap.md`](goal-roadmap.md)
参照（読み取り専用）: `souten-yd/ControlDeck` の `deck.sh`

---

## 1. 動作確認の定義（全ゴール共通・最優先）

各指示書には実機E2Eを含めているが、**「確認した」の基準を先に固定する。**

### 1.1 証拠として認めるもの

```text
実際に実行したコマンドとその出力
実測した数値（秒・バイト・件数）
実プロセスに対する実HTTPリクエストとその応答
実ブラウザ（Chromium）での操作と、その結果のスクリーンショットまたは assertion
DBの実際の行数・revision
```

### 1.2 証拠として認めないもの

```text
lint 成功
型検査成功
build 成功
テスト成功（単体テストは「実装が仕様通り」の証拠であって「動く」証拠ではない）
「〜のはず」「〜と考えられる」という記述
実行していないコマンドの想定出力
```

### 1.3 記録の書き方

`docs/implementation-status.md` に、ゴール単位で次を書く。

```text
何を実行したか（コマンド・条件・ホスト構成）
何が観測されたか（数値をそのまま）
何を確認していないか（NOT TESTED を明示）
なぜ確認できなかったか
```

**未実施を「成功」と書かない。** NOT TESTED は正しい記録であり、失点ではない。
ControlDeck 側 `docs/implementation-status.md` が既にこの流儀で書かれているので、
それに揃えること。

### 1.4 環境構築そのものも動作確認の対象

本書で作る環境整備は「動いた」の土台なので、
**クリーンな状態からの構築を実際に1回通すこと**（§10）。
既に環境がある手元で試して終わりにしない。

---

## 2. 環境分離の方針

### 2.1 絶対に共有しないもの

```text
ControlDeck の .venv と Media Forge の Python 環境
```

理由は容量ではなく**設計**である。
`docs/controldeck-integration-plan.md` §2.3 が
「add-on モジュールを ControlDeck backend へ import しない」と決めている。
venv を共有すると依存解決が結合し、
Media Forge が torch を入れた瞬間 ControlDeck の依存グラフが変わる。
これは import 禁止のルールを迂回で破ることになる。

ControlDeck core の依存は 20 数個の軽量パッケージで、
Media Forge core と重複する分を二重に持っても代償は小さい。**分ける。**

### 2.2 共有してよいもの

**再取得可能で content-addressed なキャッシュのみ**共有する。

```text
pip キャッシュ
uv キャッシュ
HuggingFace キャッシュ（HF_HOME）
```

ControlDeck の `deck.sh` は既に `export_cache_paths()` でこれらを
`data_dir/cache/{pip,uv,huggingface}` へ寄せている。
Media Forge も**同じ場所を指す**こと。
巨大な wheel やモデルファイルの二重ダウンロードを避けられる。

共有しても安全な根拠:

```text
消えても再取得できる
片方が消しても他方は壊れず、次回に再取得するだけ
内容がハッシュで一意なので競合しない
```

### 2.3 共有してはいけないもの（削除事故になる）

```text
venv 本体
モデルの重み（実体）
生成した asset / provenance / DB
ジョブの作業ディレクトリ
```

これらを ControlDeck の `data_dir` 配下に置かないこと。
ControlDeck の add-on uninstall は
「manifest 外の service や data へ触れない」実装になっているので
現状は安全だが、**依存させない**。

Media Forge のデータは独立した data_dir を持つ。

---

## 3. ディレクトリ配置

```text
ControlDeckMediaForge/
├─ .venv/                          core 環境（軽量・自動構築）
├─ runtimes/
│  ├─ rocm-torch/                  重量 ML 環境（共有ベース）
│  │  ├─ .venv/
│  │  ├─ requirements.txt
│  │  └─ .refs                     参照している worker pack の一覧
│  └─ <他ランタイム>/               torch 版が衝突する場合のみ増やす
├─ worker_packs/
│  ├─ image/
│  │  └─ runtime.toml              使用する runtime を宣言
│  ├─ vision/
│  ├─ video/
│  └─ blender/
└─ mf.sh                           deck.sh 相当の運用スクリプト
```

data_dir（既定）:

```text
~/.local/share/control-deck-media-forge/
├─ mediaforge.db
├─ assets/
├─ tmp/                            job ごとの作業ディレクトリ
└─ logs/
```

`config/config.yaml` で変更可能にする。ControlDeck の `deck_data_dir()` と
同じ読み方（`data_dir:` 行を読む）に揃えると利用者が混乱しない。

モデルの重み:

```text
既定は data_dir/models ではなく、明示設定を要求する
NVMe 上のパスを利用者が指定する
複数ライブラリを持てるようにする（ControlDeck の model_libraries と同じ考え方）
venv の中に置かない
```

---

## 4. 環境レイヤ設計

### 4.1 2層に分ける

```text
core 環境（.venv）
    fastapi / uvicorn / pydantic / httpx / sqlalchemy / alembic /
    pillow / pytest / jsonschema
    数百MB。起動時に自動構築してよい
    torch を絶対に入れない

runtime 環境（runtimes/*/.venv）
    torch(ROCm) / diffusers / transformers / accelerate など
    数GB規模。worker プロセスだけが使う
    core からは import しない。subprocess / HTTP 越しにのみ触る
```

**core が torch を import できてしまう構成にしないこと。**
できてしまうと、いずれ誰かが import する。

### 4.2 runtime の共有と分岐

torch(ROCm) は非常に大きいため、worker pack ごとに別 venv を作ると
すぐに二桁GBになる。既定では **1つの `rocm-torch` を image / vision / video で共有**する。

分岐してよいのは次の場合のみ。

```text
モデルが要求する torch のメジャー/マイナー版が既存 runtime と衝突する
カスタムカーネルが他 worker を壊す
ROCm ビルドが異なる
```

分岐するときは新しい `runtimes/<name>/` を作り、
`worker_packs/*/runtime.toml` の宣言を変える。
**既存 runtime を破壊的に更新して合わせにいかない。**

`runtime.toml` の例:

```toml
[runtime]
name = "rocm-torch"
min_version = "1"
```

### 4.3 参照カウント（削除事故の防止）

`runtimes/<name>/.refs` に、その runtime を使う worker pack を列挙する。

```text
image
vision
```

規則:

```text
worker pack を有効化したら .refs へ追加
無効化・削除したら .refs から除去
.refs が空になっても自動削除しない
削除は `mf.sh env prune` の明示実行のみ
prune は .refs が空の runtime だけを対象にする
prune は必ず対象・サイズを表示し、確認を取る
core 環境（.venv）は prune の対象外
```

利用者が数GBの再ダウンロードを不意に強いられないようにする。

---

## 5. `mf.sh` の要件

ControlDeck の `deck.sh` の作法に合わせる。**別物の流儀を持ち込まない。**

### 5.1 起動時チェック（`ensure_env`）

`deck.sh:70` の `ensure_venv()` と同じ方式を採る。

```text
venv が無ければ作る
requirements.txt の sha256 を .venv/.req-stamp と比較
不一致なら pip install -r を実行し、stamp を更新
一致なら何もしない（毎回 pip を叩かない）
```

これを **core と各 runtime の両方**に適用する。
stamp は各 venv の中に置く。venv を消せば stamp も消えるので整合が崩れない。

### 5.2 キャッシュパス

`deck.sh:264` の `export_cache_paths()` と**同じ場所**を指す。

```bash
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$shared_cache/pip}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$shared_cache/uv}"
export HF_HOME="${HF_HOME:-$shared_cache/huggingface}"
```

`$shared_cache` は ControlDeck の data_dir を読めるならそこ、
読めなければ Media Forge 自身の data_dir 配下。
**利用者が明示設定している環境変数を上書きしない**（deck.sh と同じ配慮）。

ControlDeck の data_dir を読む方法は `config/config.yaml` の `data_dir:` 行のみ。
ControlDeck の Python を実行して聞き出さないこと（環境結合になる）。
読めなかった場合は自前 data_dir へ fallback し、警告を出す。

### 5.3 重量環境の扱い

core 環境は起動時に自動構築してよい（軽量・短時間）。

runtime 環境は数GBのダウンロードを伴うため、**無言で始めない**。

```text
既定 auto_provision = true（自動で構築する）
ただし開始前に
    何を入れるか
    概算ダウンロード量
    ディスク空き容量の確認結果
をログと ControlDeck の setup_checklist に出す
空き容量が「必要量 + 余裕」を下回るときは開始せず、明示エラーにする
構築中は setup checklist の state を in_progress にし、進捗を出す
中断されても次回に再開できること（途中の壊れた venv を検出して作り直す）
```

`auto_provision = false` の場合は `setup_required` のまま
「画像ワーカー環境を構築」アクションを出す。

### 5.4 コマンド

```text
mf.sh serve            起動（ensure_env 込み）
mf.sh doctor           環境診断。何が足りないかを一覧表示。変更はしない
mf.sh env build <name> runtime を明示構築
mf.sh env list         core / runtime の一覧、サイズ、.refs、stamp 状態
mf.sh env prune        参照ゼロの runtime を確認付きで削除
mf.sh test             テスト実行
```

`doctor` は**何も変更しない**こと。診断と実行を分ける。

---

## 6. ROCm / ハードウェアの検証

runtime 構築後、実際に確認する。インストール成功を動作確認としない。

```text
torch が import できる
torch から GPU が見える（デバイス数・名前）
gfx1201 が認識されている
小さなテンソル演算が GPU 上で実行できる
VRAM 総量・空き容量が取得できる
```

失敗した場合:

```text
worker を unavailable にする
health の contribution availability に reason_code を出す
Media Forge 全体を落とさない（画像が使えなくても core は動く）
ControlDeck の setup checklist に原因と対処を出す
```

ROCm のバージョン不一致は環境要因であり、**コードで握り潰さない**。
`docs/implementation-status.md` に観測した組み合わせを記録する。

---

## 7. ControlDeck への見せ方

環境状態を health の `setup` へそのまま反映する。
ControlDeck 側は既にチェックリストを host 描画する実装になっている。

```json
{
  "status": "setup_required",
  "setup": [
    { "id": "core_env", "label": "基本環境", "state": "ok" },
    { "id": "rocm_runtime", "label": "画像ワーカー環境", "state": "missing",
      "message": "約 N GB のダウンロードが必要です",
      "action": { "kind": "open_route", "route": "/media/settings#workers" } },
    { "id": "gpu", "label": "GPU 検出", "state": "unknown" },
    { "id": "model_library", "label": "モデル保存先", "state": "missing",
      "message": "NVMe 上のパスを指定してください" },
    { "id": "disk", "label": "空き容量", "state": "ok", "detail": "..." }
  ]
}
```

`N GB` は**実測または実際のインデックス取得値**を使う。決め打ちの数字を書かない。

health は3秒以内に返す制約があるので、
容量計算やGPU検査を health ハンドラ内で同期実行しないこと。
背景で更新した結果を返す。

---

## 8. アンインストール時の挙動

```text
ControlDeck から uninstall されても、Media Forge は自分の data_dir を消さない
消すのは利用者の明示操作のみ
mf.sh に破壊的コマンドを作る場合は、対象と容量を表示して確認を取る
共有キャッシュ（pip / HF）を消さない（ControlDeck が使っている）
runtime venv は .refs を確認してから
```

「アンインストールしたら生成物が全部消えた」を起こさないこと。

---

## 9. テスト

```text
ensure_env: stamp 不一致で再インストール、一致でスキップ
ensure_env: 壊れた venv（python 実行不可）を検出して作り直す
.refs: worker 有効化で追加、無効化で除去
prune: .refs 非空の runtime を削除しない
prune: core 環境を削除しない
prune: 確認なしで削除しない
容量不足時に構築を開始しない
キャッシュパスが既存の環境変数を上書きしない
ControlDeck config が読めない場合に fallback して警告を出す
GPU 検出失敗時に worker だけ unavailable になり core は healthy
health が3秒以内に返る（重い検査を同期実行していない）
data_dir が ControlDeck の data_dir 配下を既定にしていない
```

---

## 10. 実機確認（MF0-0 の完了条件）

**クリーンな状態から実際に1回通すこと。** 手元の既存環境で試して終わりにしない。

```text
1. リポジトリを clean clone（または .venv / runtimes を退避）
2. mf.sh doctor -> 不足が正しく列挙される。何も変更されていないことを確認
3. mf.sh serve -> core 環境が自動構築され、サービスが起動する
   所要時間と .venv の実サイズを記録
4. health が setup_required を返し、rocm_runtime が missing になる
5. mf.sh env build rocm-torch -> 実際にダウンロード・構築
   所要時間、ダウンロード量、実ディスク使用量を記録
6. §6 の GPU 検証をすべて実行し、結果を記録
   （torch から見えたデバイス名、gfx1201 認識、VRAM 総量）
7. 2回目の mf.sh serve が pip を叩かずに即起動することを確認
8. requirements.txt を1行変更 -> 次回起動で再インストールが走ることを確認
9. mf.sh env list -> サイズと .refs が正しい
10. mf.sh env prune -> .refs 非空のため削除されないことを確認
11. ControlDeck 側の共有キャッシュが使われ、二重ダウンロードが起きていないことを
    PIP_CACHE_DIR / HF_HOME の実パスと更新時刻で確認
12. ControlDeck の data_dir を消しても Media Forge の asset / DB が残ることを確認
    （実際に消さず、パスが独立していることをコマンドで示す）
```

記録先は `docs/implementation-status.md`。
実測値をそのまま書き、推定を混ぜない。

---

## 11. 禁止事項

```text
ControlDeck の .venv を共有・流用すること
ControlDeck の Python を実行して設定を取得すること
core 環境に torch / diffusers / transformers を入れること
モデルの重みを venv 内に置くこと
Media Forge の data_dir を ControlDeck の data_dir 配下に既定で置くこと
共有キャッシュを削除するコマンドを Media Forge 側に作ること
数GBのダウンロードを無言で開始すること
容量不足のまま構築を開始すること
GPU 検出失敗を握り潰して healthy を返すこと
health ハンドラ内で容量計算や GPU 検査を同期実行すること
インストール成功を動作確認として記録すること
runtime venv を .refs 確認なしに削除すること
```

---

## 12. 完了条件

```text
ControlDeck と Media Forge が独立した Python 環境で動く
巨大な torch 環境は runtime として1つに集約され、worker pack が共有している
pip / HF キャッシュは共有され、二重ダウンロードが起きない
起動時に不足を検出して自動で埋める。重量環境は可視化してから構築する
削除は参照カウントと明示確認を経る
片方を消してももう片方のデータが消えない
§10 をクリーンな状態から実際に1回通し、実測値を記録した
```

最後の項目が本体。構築スクリプトを書いただけでは未完了とする。
