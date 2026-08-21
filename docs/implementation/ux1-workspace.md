# UX1 — workspace を「使える製品」にする（実装指示）

対象リポジトリ: **ControlDeckMediaForge のみ**
設計の正: `docs/design-workspace-ux.md`（先に読む。設計を変えるときは先にそちらを直す）
前提ゴール: G0〜G3 の機能が実装済みであること
位置づけ: G4 の前に入れる横断スライス。G1 の公開契約凍結を壊さない範囲で行う

```text
読む順
  1. docs/design-workspace-ux.md          何を作るか・なぜそう決めたか
  2. 本書                                  どの順で・何を確認して進めるか
  3. ControlDeck/docs/addon-ux-guidelines.md  状態表現・文言規約（読み取り専用）
  4. docs/api.md / schemas/                公開契約（変えない）
```

---

## 0. 絶対に守る境界

```text
B1 ControlDeck の変更は「汎用 host 機能」に限って許可（2026-08-22 利用者判断）
     既定は MF 側で解く。設計 §12 のとおり本スライスは MF だけで完成できる。
     それでも host を触る場合の条件:
       1. 「なぜ MF 側で解けないか」を 1 行で書いてから着手する
       2. 汎用 host 機能としてのみ変更する（例: theme token の safe_area 実値化、
          embedded view の高さ制約、bridge メソッドの不足）
       3. Media 固有のコード・ルート・依存・文言を host に入れない
          （goal-roadmap §4「完成の定義」は変わらない。ここが崩れたら未完成）
       4. ControlDeck 側は別リポジトリの別 PR にし、MF 側 PR の本文から参照する
       5. host PR が未マージの間、MF 側は host 変更なしで動く経路を残す
B2 公開契約を変えない
     /api/v1/* のパスと意味、schemas/*.json、workflow executor、agent tools、
     context actions、provenance/asset の必須フィールド、contract_version 1.0。
B3 /ws への追加は実装詳細として行う
     docs/api.md に「workspace のための実装詳細であり公開 operation ではない」と
     既に明記されている。追加時もこの位置づけを本文で維持する。
B4 addon.json の変更は 1 点だけ
     mobile: "companion" → "embedded"、version 0.1.2 → 0.2.0。
     他の contribution を触らない。理由・影響・移行を implementation-status に書く。
B5 storage を使わない
     localStorage / sessionStorage / document.cookie を 1 箇所も書かない（静的テストで担保）。
B6 path 文字列を扱わない
     file は grant ID のみ。reject_host_paths を新メソッドにも通す。
B7 UI で local_only を false にできる経路を作らない
B8 モデル名を既定経路に出さない（詳細モードの manual のみ）
```

---

## 1. PR 分割

小さく出す。各 PR は単独で動作し、前の PR のテストを壊さない。

```text
PR-U0  /ws 追加メソッドと保存基盤（capabilities / library / thumbnail / preferences）
PR-U1  シェル刷新（3ナビ + モード + モバイル IA + skeleton）
PR-U2  作成体験（シンプル入力・サイズプリセット・アクション選択・詳細パネル）
PR-U3  マスクエディタと外側拡張ハンドル
PR-U4  状況と結果ステージ（push 更新・中止・失敗文言・通知条件）
PR-U5  ライブラリと書き出し（サムネイル・ドロワー・比較・export）
PR-U6  一貫性 UI（reference collection / profile / このキャラを登録）
PR-U7  実機受け入れ（PC・モバイル）と実測記録
```

---

## 2. PR-U0 — /ws 追加メソッドと保存基盤

### 変更対象

```text
backend/mediaforge/store.py        preferences テーブル / thumbnail キャッシュ土台
backend/mediaforge/thumbnails.py   新規。Pillow で 256px サムネイル生成
backend/mediaforge/library.py      新規。asset + kind + 要約の組み立て
backend/mediaforge/app.py          /ws のメソッド追加
docs/api.md                        /ws 実装詳細の記述を更新（公開 operation ではない旨は維持）
tests/test_workspace_transport.py  新規
```

### 2.1 `capabilities.get`

```json
→ {"method": "capabilities.get", "params": {}}
← {
    "capabilities": { "image.text_to_image": {"state": "available"}, ... },
    "envelope": {
      "min_side": 256, "max_side": 1024, "multiple_of": 16,
      "max_count": 8, "max_reference_assets": 4
    },
    "presets": [
      {"id": "square",    "label_key": "size.square",    "width": 1024, "height": 1024},
      {"id": "landscape", "label_key": "size.landscape", "width": 1024, "height": 576},
      {"id": "portrait",  "label_key": "size.portrait",  "width": 576,  "height": 1024}
    ]
  }
```

- `capabilities` は既存 `/api/v1/capabilities` と同じ生成関数を再利用する（二重実装禁止）。
- `envelope` は model registry の実測 envelope から導出する。取得できない場合は
  256/1024/16 の保守値にフォールバックし、`"envelope_source": "fallback"` を付ける。
- preset は envelope を超えないよう clamp してから返す。

### 2.2 `library.list`

```json
→ {"method": "library.list", "params": {"kind": "all|generated|imported|edited", "limit": 60, "before": "<created_at>"}}
← {"items": [{
      "asset_id": "asset_...", "width": 1024, "height": 1024, "mime_type": "image/png",
      "created_at": "...", "kind": "generated|edited|imported",
      "summary": "夜の机に置かれた小さな青いロボット",   ← intent 先頭 80 文字
      "parent_asset_ids": ["asset_..."],
      "protected_pixel_diff": 0,                          ← validation にある場合のみ
      "size_bytes": 1447679
    }], "next_before": "..." }
```

- `kind` は provenance の `operation` と `parent_asset_ids` から **サーバ側で**決める。
  `asset.import` → imported、`image.edit` → edited、それ以外 → generated。
- `parameters.purpose == "edit_mask"` の asset は既定で **除外**する
  （`include_masks: true` を渡したときのみ含める。詳細モード用）。
- provenance の N+1 取得を UI 側で起こさないため、必要な要約はここで組む。

### 2.3 `assets.thumbnail`

```json
→ {"method": "assets.thumbnail", "params": {"asset_id": "asset_...", "max_side": 256}}
← {"mime_type": "image/png", "base64": "...", "width": 256, "height": 256}
```

- `max_side` は 64..512 に丸める。既定 256。
- 生成物は `data_dir/thumbnails/<asset_id>_<max_side>.png`（mode 0o600、`contained()` 検証）。
  存在すれば再利用。asset 削除機能は現状無いので無効化処理は不要。
- 出力が 64 KiB を超える場合は品質ではなくサイズを下げて再試行し、
  それでも超えるなら `thumbnail_unavailable` を返す（握り潰さない）。
- 元 asset が画像でない場合も `thumbnail_unavailable`。将来の video 用に
  `mime_type` 判定を 1 箇所へ集約する。

### 2.4 `preferences.get` / `preferences.set`

```json
→ {"method": "preferences.set", "params": {"values": {"mode": "advanced", "last_preset": "landscape", "last_count": 2}}}
← {"values": {...}}
```

- 保存単位は host identity の `subject`。standalone（host なし）は `"local"` 固定。
- 許可キーの allowlist を backend に持ち、未知キーは拒否（`invalid_preference_key`）。
- 値は JSON で 4 KiB 上限。秘密値・path・token を保存しない。
- テーブル:

```sql
CREATE TABLE IF NOT EXISTS preferences (
    subject TEXT PRIMARY KEY,
    values_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 2.5 `jobs.watch` / `jobs.unwatch`

```json
→ {"method": "jobs.watch", "params": {"job_ids": ["job_..."]}}   ← 空配列 = 実行中すべて
← {"watching": ["job_..."]}
push  {"type": "event", "event": "job.changed", "data": {<Job の JSON>}}
```

- JobManager の状態更新点（`store.update_job` 呼び出し側）から
  in-process の非同期キューへ通知し、接続中の workspace socket へ push する。
- push は接続ごとに最大 10 job まで。終端に達した job は自動 unwatch。
- push 失敗で job 実行が壊れないこと（例外を握らず、送信失敗はログのみで job は継続）。
- 送信間隔は最短 200ms に間引く（進捗の細かい変化で溢れさせない）。

### 受け入れ条件

```text
新メソッドが host service identity を要求し、未認証で拒否される
reject_host_paths が新 params にも適用される
1 MiB 超の request が既存どおり拒否される
未知メソッドが従来どおり workspace_method_unsupported で落ちる
既存 /api/v1 と /ws の既存メソッドの応答が 1 バイトも変わらない
```

### テスト（pytest）

```text
tests/test_workspace_transport.py
  capabilities.get が /api/v1/capabilities と同じ capability 状態を返す
  envelope が fallback のとき envelope_source を明示する
  library.list が kind を正しく分類する（generate / edit / import の 3 パターン）
  library.list が edit_mask asset を既定で除外し、include_masks で含める
  library.list のページングが created_at 降順で重複・欠落しない
  assets.thumbnail が 256px 以内・64KiB 以内・PNG を返す
  assets.thumbnail が同一 asset で 2 回目にキャッシュを使う（ファイル mtime 不変）
  assets.thumbnail が非画像 asset で thumbnail_unavailable を返す
  preferences が subject ごとに分離される
  preferences が未知キーを拒否し、4KiB 超を拒否する
  jobs.watch が状態変化のたびに push し、終端で自動解除する
  jobs.watch の push 先が落ちても job が完了する
  新 params に path 文字列を入れると unscoped_host_path で落ちる
```

### 2.6 実測タスク: subresource 直接取得の可否（設計 §10.1）

実装ではなく**測定**。PR-U0 の成果物は結論と証跡のみ。

```text
手順
  1. installed host で workspace を開く
  2. frame 内から
       fetch("/addon-frame/media-forge/api/v1/assets/<id>/content", {credentials: "include"})
     を実行し、status と Content-Length を記録する
  3. <img src="/addon-frame/media-forge/api/v1/assets/<id>/content"> の
     naturalWidth を記録する
  4. ControlDeck 側のアクセスログ／audit で 401/403 と 200 のどちらかを確認する
結論の使い道
  成立   → 原寸プレビューを直接取得へ移す設計変更を design-workspace-ux.md へ反映してから実装
  不成立 → /ws base64 のまま。design §10.1 に「不成立」と実測日を追記
どちらでも
  サムネイルは /ws のまま（64KB 上限で十分に軽く、standalone でも同じ経路で動くため）
```

### 記録

```text
asset 50 件での library.list + thumbnail 一括取得の転送量と所要時間
既存 assets.content 方式との比較（before / after を両方実測）
subresource 直接取得の可否（status / naturalWidth / 実測日）
```

---

## 3. PR-U1 — シェル刷新

### 変更対象

```text
frontend/index.html      3 ナビ・ヘッダ・モードトグル・モバイル下部タブ・skeleton
frontend/styles.css      レイアウト全面（desktop 2 ペイン / mobile 単一列）
frontend/app.js          ルーティング・モード制御・handshake・theme 適用
addon.json               mobile: "embedded" / version 0.2.0
backend/mediaforge/app.py  workspace ルート追加（/activity）
```

### DOM 契約（テストが依存する。勝手に変えない）

```text
#app                      data-mode="simple|advanced" data-bridge="waiting|ready|error|standalone"
                          data-view="create|library|activity|settings"
#nav-create #nav-library #nav-activity        ナビ。DOM は 1 組だけ置き、
                          PC 上部 / モバイル下部の切替は CSS で行う（id 重複を作らない）
#nav-activity .badge                          実行中件数
#mode-toggle                                  aria-pressed でモード状態
#create-intent                                主入力
#create-submit                                主ボタン
#size-presets [data-preset]                   サイズチップ
#count-chips [data-count]                     枚数チップ
#attach-image                                 画像追加
#edit-actions [data-edit-mode]                アクション選択（capability で出し分け）
#guarantee-badge                              保証文言
#stage                                        ステージ（プレビュー / 進捗）
#stage-progress                               進捗カード
#stage-result                                 結果
#candidate-strip [data-asset-id]              候補
#mini-progress                                モバイル常時バー
#library-grid [data-asset-id]                 グリッド
#asset-drawer                                 詳細
#activity-list [data-job-id]                  状況一覧
#advanced-*                                   詳細モードでのみ DOM に存在する要素の接頭辞
```

**規則**: `#advanced-*` はモード OFF のとき DOM に存在してはならない。
テストは `document.querySelectorAll('[id^="advanced-"]').length === 0` を検証する。

### 実装規則

```text
handshake 前は theme 背景の skeleton を描く。visibility:hidden をやめる
theme.changed / locale.changed / safe_area.changed で再描画せず反映（現行踏襲）
route.sync は /, /library, /activity, /settings の 4 値のみ送る
route.changed 受信で対応 view へ切り替える（sync は送り返さない。ループ防止）
モバイル判定は matchMedia("(max-width: 767px)")。JS で分岐せず CSS で切り替える
  （host 側の再マウントなしで回転・分割画面に追従するため）
下部タブは safe_area token を padding-bottom に加算する
```

### 受け入れ条件

```text
768px 未満で下部タブ・単一列になり、横スクロールが出ない（320px でも）
1100px 以上で 2 ペインになる
モードトグルが preferences に保存され、再読込後も維持される
シンプルで #advanced-* が 0 件
dark / light どちらでも handshake 直後に白背景が出ない
戻る / 進む / 共有 URL が host 側で維持される
```

### テスト

```text
tests/test_frontend_contract.py（静的・pytest）
  frontend/*.js に localStorage|sessionStorage|document\.cookie が 0 件
  DOM 契約の id がすべて index.html か app.js の生成コードに存在する
  UI の error 文言表に載る code が backend の実在 code 集合の部分集合である
  UI が参照する capability 名が /api/v1/capabilities の keys の部分集合である
  addon.json の mobile が "embedded" で version が 0.2.0

scripts/ux_standalone_e2e.py（Playwright / standalone）
  1280×800: 2 ペイン・3 ナビ・#advanced-* 0 件
  390×844: 下部タブ・ミニバー領域・横スクロール 0
  320×640: 崩れなし
  モード切替後の再読込で advanced が復元
```

---

## 4. PR-U2 — 作成体験

### 実装

```text
シンプル
  intent（autofocus・4 行・自動拡張・8000 文字上限を UI でも表示）
  サイズプリセット（capabilities.get の presets から生成）
  枚数チップ 1..4（詳細で 8 まで）
  作る（実行中は disabled + ラベル「実行中…」）
  目安時間は models の実測がある場合のみ表示し、無ければ出さない（推測を出さない）

画像添付（L2）
  ドロップ / クリック選択 / モバイルはファイル選択
  添付で operation を image.edit に切替（select を廃止。ユーザーは operation を知らない）
  アクション 5 種を capability で絞って描画:
    inpaint          一部だけ直す
    reference        全体を直す
    variation        似た別案を作る
    outpaint         外側を広げる
    multi_reference  参考を足して直す
  保証バッジを選択と同時に更新（P4）
    inpaint / outpaint : 「塗っていない場所は 1px も変わりません」
    その他             : 「画像全体が変わることがあります」

詳細パネル（#advanced-*）
  width / height（16 の倍数・envelope 検証・違反は送信前に inline error）
  output.format / count 5..8
  model_policy 6 種 / manual 時に model_id セレクト（models.list から）
  qa.semantic + max_regeneration_attempts 0..3
    capability unavailable のときは無効表示 + 理由（設計 §7.1）
  edit_mode / strict_edit / editable_mask_asset_id の生指定
  constraints の実キー名を併記（API と UI の対応を上級者に見せる）

preferences
  last_preset / last_count / mode を保存し次回復元する
```

### 受け入れ条件

```text
シンプルで触る要素が 3 つ以内で 1 枚生成できる
capability unavailable のアクションがシンプルで出ない
詳細で job-request のすべてのフィールドへ到達できる（設計 §9 の一覧を満たす）
送信前検証で invalid_dimensions / invalid_reference_count 相当を未然に止める
local_only を false にする UI 経路が存在しない
```

### テスト

```text
pytest（静的）
  UI が組み立てる request が schemas/job-request.json に適合する
    （app.js の組み立て関数を Node ではなく Python 側で再現しないこと。
      代わりに Playwright で実際に送信された payload を捕捉して schema 検証する）
Playwright（standalone）
  シンプル → 生成 → 成功（fake worker 構成で可）
  画像添付でアクションが現れ、capability を落とした構成では該当アクションが消える
  詳細 ON で幅 1000（16 の倍数でない）を入力すると送信されず inline error
  詳細 ON で manual を選ぶと model_id が必須になる
  最後に使ったサイズ・枚数が再読込後に復元される
```

---

## 5. PR-U3 — マスクエディタと外側拡張

### マスクエディタ

```text
canvas 2 枚（表示用の元画像 + マスク）。出力は元画像と同一寸法の PNG
ブラシ（サイズ 8..256、既定は短辺の 4%）／消しゴム／全消去／取り消し（8 段）
表示は「塗った所 = 半透明の色」。出力時に白（編集可）/ 黒（保護）へ変換
タッチ対応: 1 本指で描画、2 本指でパン・ズーム（pointer events）
出力は既存 assets.import.begin/chunk/commit（purpose=edit_mask）へ流す
空マスク・全面マスクは送信前に UI で止める（backend も従来どおり fail-closed）
詳細モードでは「マスク画像を読み込む」も残す（既存経路を消さない）
```

### 外側拡張（outpaint）

```text
上下左右のハンドルをドラッグ、または比率プリセット（16:9 / 1:1 / 9:16）
入力から目標 width / height を計算し、以下を UI で保証してから送信する
  16 の倍数
  元画像を完全に含む
  少なくとも 1 辺が拡大
  envelope 内
数値は詳細モードでのみ表示・編集可能
```

### 受け入れ条件

```text
外部ツールなしで inpaint が完了する（設計 A4）
マスクは元画像と同寸法で、無変更領域が黒であることをテストで確認
モバイル（タッチ）で描画・消去・取り消しができる
```

### テスト

```text
pytest
  UI が作ったマスクと同等の PNG が既存 strict edit 検証を通る（合成マスクで代替可）
Playwright
  ブラシで塗る → 送信 → job の constraints に editable_mask_asset_id が入る
  何も塗らずに送信すると送信されず「変更する場所を塗ってください」
  全面を塗ると送信されず注意が出る
  outpaint ハンドル操作で width/height が 16 の倍数かつ元画像以上になる
```

---

## 6. PR-U4 — 状況と結果ステージ

### 実装

```text
jobs.watch を接続時に開始し、進行中 job を push で追う（polling を廃止）
ステージ
  実行中: 進捗バー / 日本語 phase / 経過秒 / [中止]
  待機中: 「GPU の空きを待っています」+ [ControlDeck の Jobs で詳細を見る]
          ※ 抑止理由 enum の日本語訳を MF 側で持たない（host 所有）
  完了  : 大プレビュー + 候補ストリップ + 次アクション
モバイルはミニ進捗バーを全 view で表示（sticky・タブの上）
状況タブ
  実行中を上に固定、履歴は新しい順
  行: 種別（作成 / 一部だけ直す 等）/ 進捗 or 結果 / 相対時刻 / 操作
  失敗行に日本語 1 文 + 出口 1 つ（設計 §7.3 の表を実装）
  「同じ設定でもう一度」で request を復元して作る画面へ戻す
通知
  visibility.changed を購読し、非表示のときだけ toast する
  進捗を toast しない。dedupe key は job id
```

### 受け入れ条件

```text
タブを移動しても進捗が失われない（設計 A9）
中止が 2 秒以内に反映される
失敗表示に必ず操作可能な出口が 1 つある
workspace 表示中は toast が出ない
```

### テスト

```text
pytest
  error code → 文言表に backend の全 code が網羅されている（未知は既定文へ）
Playwright
  実行中にタブ移動 → 進捗が継続表示
  中止ボタンで canceled になる
  失敗 job（無効マスク等を意図的に投入）で出口ボタンが現れ、押すと入力が復元される
  workspace 可視時に notification.show が呼ばれない（bridge をスタブして観測）
```

---

## 7. PR-U5 — ライブラリと書き出し

### 実装

```text
library.list + assets.thumbnail でグリッドを描く（assets.content の一括取得を廃止）
セグメント: すべて / 作ったもの / 取り込み / キャラ・画風
ドロワー
  原寸プレビュー（12 MiB 超は「原寸は書き出しで確認してください」）
  親がある場合は before/after 比較
  provenance 要約（いつ・何から・保証・ライセンス）／詳細で生 JSON
  系譜チェーン表示
  操作: 保存 / これを編集 / 参考に追加
書き出し（assets.export）
  1. host.file.export で書き出し先 grant を得る
  2. /ws assets.export {asset_id, grant_id, filename} を呼ぶ
  3. backend は producing host job があればそれへ attach、無ければ
     「Media Forge 書き出し」ジョブを作り、create_output → upload → commit
  4. 結果の sha256 を UI で照合し、一致を成功条件にする
  補助: ブラウザ保存（blob）。sandbox で失敗し得るため主経路にしない
  ※ プロジェクトへ直接置くのは G4。ここでは実装しない
```

### 受け入れ条件

```text
生成物を Media Forge の外へ出せる（設計 A2 / 現状不能の解消）
書き出したファイルの sha256 が asset の sha256 と一致する
ライブラリ初期表示の転送量が現行方式より明確に小さい（実測を記録）
```

### テスト

```text
pytest
  assets.export が grant_id 無しを拒否する
  assets.export が path 文字列を拒否する（unscoped_host_path）
  export の filename が basename のみであることを検証する
  host bridge 失敗時に 502 相当を返し、job を壊さない
Playwright（installed host）
  書き出し → host のフォルダ選択 → 実ファイルが増える → sha256 一致
```

---

## 8. PR-U6 — 一貫性 UI（G3）

```text
ライブラリ「キャラ・画風」セグメント
  一覧（名前・参照サムネイル・作成日）／作成／削除
  削除しても過去 asset の provenance snapshot は消えないことを UI で明記
作る画面
  シンプル: 「＋ キャラ・画風を使う」1 行 → 選ぶとチップ表示
  詳細    : character / style の全構造化フィールド編集
            （appearance / clothing / colors / distinguishing_features /
              negative_traits / art_style / linework / coloring / texture）
結果ステージ
  「このキャラを登録」→ 名前のみで
    reference collection（その asset）+ character profile を作成
  参照は最大 4 枚制約を UI で強制（job 側 reference と合算）
```

### 受け入れ条件

```text
学習なしで同じキャラを続けて作れる（G3 の完了条件と一致）
profile 無しでも生成が動く（必須化しない）
profile 削除後も過去 asset の provenance から内容を辿れる
```

### テスト

```text
pytest（既存 tests/test_profiles.py を拡張）
  UI 経路（/ws）から profile / collection を作成・削除できる
  参照合計 4 枚超が拒否される
Playwright
  結果から「このキャラを登録」→ チップ選択 → 2 枚目生成の request に
  constraints.character_profile_id が入る
```

---

## 9. PR-U7 — 実機受け入れ

`AGENTS.md`「完了の定義」に従い、**実機の観測のみを証拠にする**。

```text
scripts/ux_control_deck_e2e.py（新規・既存 g2 スクリプトの作法を踏襲）
  --control-deck-url / --media-forge-url / --username / --password-env
  --viewport desktop|mobile / --evidence-dir

desktop（1440×900）
  ログイン → /x/media-forge/workspace
  作る（512×512・1 枚）→ 進捗が push で更新される → 結果表示
  ライブラリ → サムネイル表示 → ドロワー → 書き出し → sha256 一致
  console error 0 / page error 0

mobile（390×844）
  同一 URL で **状態カードではなく workspace が出る**ことを assert
  作る → ミニ進捗バーがタブ移動後も見える → 結果を全画面で確認
  ライブラリ 2 列グリッド → 拡大
  横スクロール量 0 を assert（document.scrollingElement.scrollWidth <= clientWidth）
  console error 0 / page error 0
```

記録する実測値（`docs/implementation-status.md`）:

```text
生成 1 件の browser 総時間 / load / generation
ライブラリ初期表示の転送量・時間（PR-U0 の before と対比）
job 状態反映の遅延（push 後の DOM 更新まで）
モバイル初期表示時間、横スクロール有無、320px 崩れ有無
書き出し所要時間と sha256 一致
Broker lease の後始末（active 0 / waiting 0）
NOT TESTED の列挙
```

---

## 10. テスト戦略（4 層）

```text
層 1  静的契約テスト（pytest・高速）
        storage 不使用、DOM 契約 id、error code 網羅、capability 名、addon.json
        → 文言とコードの乖離を CI で止める
層 2  backend 単体・トランスポート（pytest）
        新 /ws メソッドの境界・認証・上限・fail-closed
層 3  standalone ブラウザ（Playwright・ControlDeck 不要）
        レイアウト、段階開示、モード、マスク描画、送信 payload の schema 適合
        window.parent === window の既存 standaloneCall 経路を使う
層 4  installed-host ブラウザ（Playwright・実機）
        bridge / theme / grant / 書き出し / モバイル埋め込み
        **これだけが「動く」証拠**
```

層 1〜3 は回帰証拠であり、完了の根拠にしない（AGENTS.md）。

Playwright は core venv に入れない（core を軽く保つ）。
`scripts/` 用の別 venv かシステム環境で実行し、実行手順を
`docs/implementation-status.md` に残す（既存 g1/g2 スクリプトと同じ扱い）。

---

## 11. 実装順の理由

```text
U0 を先にする      UI から先に作ると転送量の問題を UI に埋め込んでしまう
U1 を 2 番目       IA が決まらないと以降の置き場所が決まらない
U3 を U2 の後      添付とアクション選択が無いとマスクの入口が無い
U5 を U4 の後      結果ステージの「保存」がライブラリ書き出しと同じ実装を使う
U6 を最後から 2 番目  G3 backend が固まってから UI を載せる
U7 は必ず最後      実機証拠は全部入りでのみ意味がある
```

---

## 12. やらないこと（このスライスの範囲外）

```text
プロジェクトへの直接配置（G4）
M5 / 2D ゲームのプロファイル UI（G5 / G6）
動画・3D の画面（G7 / G9）
ライブラリの検索・タグ・コレクション（設計 §13-11 で延期）
LoRA / 学習の UI（base-plan §3.6）
node graph（base-plan §3.1）
Media 固有のコードを ControlDeck へ入れること（host 変更は汎用機能に限る。§0 B1）
```

---

## 13. 完了条件

```text
1. 設計 §14 の A1〜A9 を実機で満たす（desktop と mobile 両方）
2. 公開 API / schemas / workflow / agent tools が変わっていない
3. addon.json の変更が mobile と version の 2 行のみで、理由と影響が記録されている
4. ControlDeck の差分が 0 行、または汎用 host 機能に限定された別 PR として
   マージ済みで、Media 固有のコード・ルート・依存・文言が host に入っていない
5. 既存テストが 1 件も壊れていない（./mf.sh test 全通過）
6. docs/implementation-status.md に実測値と NOT TESTED を記録した
7. 「使えない機能が並んでいない」ことと「詳細モードで全機能に到達できる」ことを
   同時に満たしている（片方だけでは未完了）
```

---

## 14. 開発運用（PR・push・記録・引き継ぎ）

**このスライスは context が途中で切れる前提で進める。**
切れても次のセッションが `docs/implementation/ux1-handoff.md` だけを読めば再開できること。

### 14.1 1 PR の手順

```text
1. 引き継ぎファイルを読む      docs/implementation/ux1-handoff.md
2. ブランチを作る              MF:  ux1/<slug>       例 ux1/transport-foundation
                               CD:  addon/<slug>     （host 変更が要るときだけ）
3. 実装する（1 PR = §1 の 1 スライス。跨がない）
4. テスト                      ./mf.sh test          全通過を確認
5. 引き継ぎファイルを更新      §14.3 の全項目を書き換える
6. commit                      §14.2 の形式
7. push                        git push -u origin <branch>
8. PR 作成                     gh pr create（§14.4 のテンプレ）
9. 実測値があれば              docs/implementation-status.md へ追記
                               （実行したコマンドと観測値のみ。推測を書かない）
```

**commit しないまま次の作業に進まない。** 未 commit の状態は引き継げない。

### 14.2 commit の形式

```text
ux1(U0): add workspace transport methods

<何を追加/変更したか 3 行以内>
<実測値があれば 1 行>

Refs: docs/implementation/ux1-workspace.md §2
```

### 14.3 引き継ぎファイルの更新義務

`docs/implementation/ux1-handoff.md` を **commit のたびに** 更新する。
更新せずに commit した場合、その PR は未完了として扱う。

書く項目:

```text
最終更新（日付）／現在のブランチ／PR 番号と状態
PR-U0〜U7 の状態（未着手 / 実装中 / PR 作成済 / マージ済）
いま実装中のファイルと、途中なら「どこまで書いたか」
次にやること（1 つだけ。曖昧語を使わない）
未解決の判断・ブロッカー
再開コマンド（そのまま貼れる形）
```

### 14.4 PR 本文テンプレ

```text
## 何を変えたか
<箇条書き 3〜5 行>

## 設計上の根拠
docs/design-workspace-ux.md §<番号>

## 契約への影響
公開 API / schemas / workflow / agent tools: 変更なし
/ws: <追加メソッド or なし>
addon.json: <変更 or なし>
ControlDeck: <差分 0 行 or 別 PR へのリンク + MF 側で解けない理由>

## 確認したこと
./mf.sh test : <N> passed
<実機で観測したこと。無ければ「実機未確認」と書く>

## NOT TESTED
<列挙。無い場合も「なし」と明記>
```

### 14.5 やってはいけない記録

```text
テスト成功を「動く」と書く（AGENTS.md 完了の定義）
実行していないコマンドの想定出力を書く
NOT TESTED を省略する
引き継ぎファイルを更新せずに context を終える
```
