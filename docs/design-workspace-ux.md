# Media Forge Workspace UX — 設計の正

Status: 設計確定 / 未実装（実装指示は `implementation/ux1-workspace.md`）
Date: 2026-08-22
対象: G0〜G3 で完成した機能を、利用者が実際に使える形にする workspace UI
実装対象リポジトリ: **ControlDeckMediaForge のみ**（ControlDeck 本体の変更は不要。§12）

本書は `base-plan.md` §16「UI」を具体化した設計の正である。
UI に関する設計判断を変えるときは、実装より先に本書を更新する。

---

## 1. なぜ作り直すか（現状の批判的評価）

現在の workspace（`frontend/index.html` + `app.js`）は G0 の足場であり、
G1〜G3 で実装された機能に対して以下の欠落がある。**機能不足ではなく到達不能**が問題である。

```text
致命的
  1. モバイルで何も見えない
       addon.json は mobile: "companion"。ControlDeck は 768px 未満で
       AddonCompanion（状態カードのみ）を描画する。Jobs も asset も進捗も出ない。
       「モバイルで完成物と作成状況を見る」は現状 0%。
  2. 生成物を取り出せない
       UI に書き出し導線が 1 つも無い。host.file.export と host files bridge は
       実装済み（/test/host-files/roundtrip で疎通実績あり）なのに UI が使っていない。
       作った画像が Media Forge の中から出られない。
  3. マスクを作れない
       image.edit の inpaint は「白=編集可 / 黒=保護」の PNG マスクを要求するが、
       UI はファイル選択しか提供しない。外部ペイントツールが事実上の必須依存。
       実装済みの最重要機能（ピクセル保護編集）が上級者専用になっている。

重い
  4. capability を UI が見ていない
       /api/v1/capabilities は available / unavailable / experimental を返すのに、
       UI は常に全モードを出す。outpaint や multi_reference が使えない構成でも
       選べてしまい、GPU 受付後ではなく受付時に落ちる（またはその逆に見える）。
  5. 進捗が Create 画面に閉じている
       pollJob は create-status の 1 ノードにしか書かない。タブを移ると進捗が消える。
       生成中であることを示す全体インジケータが存在しない。
  6. ライブラリが重い
       asset ごとに assets.content（フルサイズ base64、実測 1.4 MB 級）を
       直列取得している。50 枚で数十 MB。サムネイル経路が無い。
  7. 失敗が生の error code
       strict_edit_invariant_failed / semantic_review_exhausted / invalid_edit_mask を
       そのまま出す。次に何をすればよいかが無い（UX ガイドライン「出口のない error は禁止」違反）。
  8. G3 の UI が無い
       profile / reference collection の API は在るが、作成も選択も UI から不可能。
  9. 使わない物が常時見えている
       Models タブ（モデル ID・ライセンス・capability 名）は一般利用者に無意味で、
       かつ「public API にモデル名を必須で登場させない」原則と噛み合わない。
       Settings タブは静的な説明文で、操作対象が 1 つも無い。
```

**結論**: タブを足すのではなく、情報構造・開示段階・プレビュー面を作り直す。

---

## 2. 設計原則

```text
P1  1画面で終わる
      「作る」は 1 画面。ウィザードにしない。文脈が増えたときだけ画面が育つ。
P2  隠す ≠ 消す
      既定では見せない。ただし詳細モードで必ず全機能へ到達できる。
      機能削除で簡単さを買わない（上級者要件と衝突するため）。
P3  可用性は capability が決める
      UI の出し分けはハードコードせず capability document から導出する。
      使えないものは既定で出さない。詳細モードでは理由付きで無効表示する。
P4  保証を言葉にする
      「塗った所だけ変わります／全体が変わることがあります」を操作の隣に置く。
      backend の strict_edit 不変条件を UI の約束として正直に表示する。
P5  失敗には必ず出口を 1 つ
      error code を日本語 1 文 + 実行可能な操作 1 つに変換する。
      「マスクが空」なら「マスクを描き直す」ボタンで、入力を保ったまま戻す。
```

補助原則:

- 語彙は利用者の語彙にする（`multi_reference` ではなく「参考画像を足して直す」）
- 内部語（add-on / contribution / lease / worker / capability）を画面に出さない
- モバイルは PC の縮小ではない。IA から別に設計する（UX ガイドライン準拠）
- node graph を作らない（`base-plan.md` §3.1 / §16 を維持）

---

## 3. 情報アーキテクチャ

トップレベルを **5 タブ → 3 + 歯車** に減らす。

```text
before                      after
  Create                      作る        （作成 + 実行中 + 直近結果）
  Library                     ライブラリ  （完成物・取り込み・キャラ/画風）
  Jobs                        状況        （実行中と履歴。バッジで件数）
  Models        ──┐
  Settings      ──┴─────→     ⚙ 設定      （状態・保存先・モデル管理・詳細モード）
```

- **Models は独立タブをやめる**。導入・削除・進捗は設定内で両モードに現れ、
  model ID・hash・runtime・生 capability などの技術詳細だけを詳細モードに置く。
- **状況**は実行中があるときだけバッジが付く。空でもタブは消さない
  （UX ガイドライン「状態は消さずに説明する」）。
- route は host へ同期する（`host.route.sync`）:
  `/` `/library` `/activity` `/settings`。戻る/進む/共有 URL が壊れないこと。

### 3.1 モード（段階開示）

| モード | 既定 | 対象 | 切替 |
|---|---|---|---|
| シンプル | ON | 通常利用 | ヘッダのトグル |
| 詳細 | OFF | 上級者・検証・再現 | 同上。サーバ側に利用者ごとに保存 |

詳細モードの要素は **DOM に描画しない**（`hidden` にしない）。
理由: tab 順・スクリーンリーダー・誤操作の汚染を避け、
テストで「シンプルでは存在しない」を存在アサーションとして検証できるようにするため。

保存は localStorage 不可（opaque sandbox）。`preferences` を Media Forge の
サーバ側に host identity の subject 単位で置く（§11）。

---

## 4. 何を隠し、何を出すか（完全表）

`L1` = シンプルで常時表示 / `L2` = 文脈が満たされたときに出現 / `L3` = 詳細モードのみ

| 項目 | 段階 | 根拠 |
|---|---|---|
| 作りたいものの入力（intent） | L1 | 主操作 |
| ドメイン（自動/アニメ/イラスト/写真/2Dゲーム/ポスター） | L1 | モデル名ではなく意図で routing |
| シーンと見せ方（シーン/ポーズ/構図/カメラ/変化軸） | L1の閉じた展開 | 全て自動のまま使える |
| サイズプリセット（正方形/横長/縦長） | L1 | 数値を触らせない |
| 枚数（1〜4 のチップ、既定 1） | L1 | 8 まで要るのは上級者 |
| 「作る」ボタン + 目安時間 | L1 | 待ち時間の予告 |
| 画像を追加（ドロップ/選択） | L1 | 編集入口。ここが operation 切替を兼ねる |
| 編集アクション 5 種 | L2 | 画像が付いたときだけ。capability で絞る |
| マスク描画エディタ | L2 | 「一部だけ直す」選択時 |
| 広げ方の選択（比率・倍率） | L2 | 「外側を広げる」選択時 |
| 参考画像の追加（最大 3） | L2 | 「参考を足して直す」選択時 |
| キャラ / 画風の固定 | L2 | 既定は「使う」1 行に畳む。選択後にチップ表示 |
| 幅・高さの直接入力 | L3 | 16 の倍数・envelope 検証つき |
| 出力形式 png/webp/jpeg | L3 | 既定 png |
| 枚数 5〜8 | L3 | VRAM と待ち時間の実害 |
| model_policy 全 6 種 | L3 | 既定 auto |
| model_id 指定（manual） | L3 | **唯一モデル名が出る場所** |
| 意味レビュー（qa.semantic）とリトライ上限 | L3 | 既定 OFF。unavailable なら理由付き無効 |
| strict_edit / edit_mode の生指定 | L3 | 通常はアクション選択から導出 |
| domain/scene/pose/composition/camera の全 template と自由補足 | L3 | versioned CreativeSpec template から表示 |
| provenance 生 JSON | L3 | シンプルでは要約カード |
| job 生 JSON / phase 生名 | L3 | シンプルでは日本語フェーズ |
| モデル管理（容量・分類・導入・削除・進捗） | L1 | 設定内。通常利用に必要 |
| model ID / hash / runtime / capability 生値 | L3 | 設定内の展開詳細 |
| host 連携診断（host-integration） | L3 | 設定内 |
| edit_mask として取り込んだ asset | 非表示 | 作業中間物。ライブラリを汚す |
| 動画 / 3D | 非表示 | G7 / G9 未実装。空タブを作らない |

---

## 5. レイアウト

トークンは host の theme token（`bg` `surface` `text` `border` `muted` `accent`
`radius_*` `spacing_unit` `density` `safe_area`）のみを使う。自己申告の重大色を使わない。

### 5.1 PC（≥1100px）— 作る

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Media Forge                        ● ローカルのみ   [シンプル|詳細]  ⚙  │ 56px
├──────────────────────────────────────────────────────────────────────────┤
│  作る   ライブラリ   状況 ②                                              │ 44px
├────────────────────────┬─────────────────────────────────────────────────┤
│ 指示パネル  400px      │  ステージ  flex                                 │
│                        │                                                 │
│ 何を作りますか？       │   ┌───────────────────────────────────────┐     │
│ ┌────────────────────┐ │   │                                       │     │
│ │                    │ │   │        大きなプレビュー               │     │
│ │  （4行・自動拡張） │ │   │        （最新の結果 / 実行中の状態）  │     │
│ └────────────────────┘ │   │                                       │     │
│                        │   └───────────────────────────────────────┘     │
│ ＋ 画像を追加          │   [ 候補 1 ][ 候補 2 ][ 候補 3 ]  ← count>1     │
│                        │                                                 │
│ サイズ                 │   保存 / これを編集 / 参考に追加 / もう1枚      │
│ [1:1][16:9][9:16]      │   このキャラを登録 ▸                            │
│ 枚数 [1][2][3][4]      │                                                 │
│                        │   ── 最近作ったもの ────────────────────        │
│ ＋ キャラ・画風を使う  │   [ ][ ][ ][ ]  ← サムネイル 4 件              │
│                        │                                                 │
│ [        作る        ] │                                                 │
│  目安 15〜30秒         │                                                 │
└────────────────────────┴─────────────────────────────────────────────────┘
```

画像を追加した後（L2 展開、指示パネル内）:

```text
│ ┌────────────────────┐ │
│ │ [縮小した元画像] × │ │
│ └────────────────────┘ │
│ この画像を…           │
│ ( ● 一部だけ直す    ) │  ← ラジオカード。capability=unavailable は非表示
│ ( ○ 全体を直す      ) │
│ ( ○ 似た別案を作る  ) │
│ ( ○ 外側を広げる    ) │
│ ( ○ 参考を足して直す) │
│ 🛡 塗った所以外は     │  ← 保証バッジ（P4）
│    1px も変わりません │
│ [ マスクを描く ]      │
```

### 5.2 PC — 実行中のステージ

```text
   ┌───────────────────────────────────────┐
   │  ▓▓▓▓▓▓▓▓▓░░░░░░░░  62%               │
   │  生成しています                       │  ← phase の日本語
   │  経過 12 秒                           │
   │  [ 中止 ]                             │
   └───────────────────────────────────────┘
```

待機中（Broker lease 待ち）は「GPU の空きを待っています」+
`[ ControlDeck の Jobs で詳細を見る ]`（`host.route.open` `/jobs`）。
**抑止理由 enum の日本語は host が所有する**ため Media Forge 側で再翻訳しない
（UX ガイドライン「Broker／provider は enum を返し、日本語文言は host が所有」）。

### 5.3 PC — ライブラリ

```text
├──────────────────────────────────────────────────────────────────────────┤
│ [ すべて ][ 作ったもの ][ 取り込み ][ キャラ・画風 ]        🔍 絞り込み  │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                          │
│  │ thumb│ │ thumb│ │ thumb│ │ thumb│ │ thumb│   grid minmax(200px,1fr)  │
│  │      │ │      │ │      │ │      │ │      │                          │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                          │
│   3分前     10分前    1時間前  昨日     昨日                            │
│   生成      編集      取り込み 生成     生成                            │
└──────────────────────────────────────────────────────────────────────────┘
```

カード選択で右からドロワー:

```text
   ┌──────────────────────────────┐
   │ [ 大きなプレビュー ]         │
   │                              │
   │ ◀ 元画像 | 結果 ▶            │ ← 親がある場合のみ比較スライダ
   │                              │
   │ 3分前・1024×1024・PNG        │
   │ 元: 「夜の机の青いロボット」 │
   │ 🛡 保護画素の変更 0           │ ← validation から
   │ ライセンス: …                │
   │                              │
   │ [保存][編集][参考に追加]     │
   │ ▸ 詳細（provenance）         │ ← L3 で生 JSON
   │ 系譜: 取り込み → 編集 → これ │
   └──────────────────────────────┘
```

### 5.4 モバイル（<768px）

`addon.json` の `mobile` を `companion` → `embedded` に変更する（§11）。
**PC の縮小ではなく別 IA** を実装するため、UX ガイドラインの意図（320px に
workspace を押し込まない）を満たす。

```text
┌──────────────────────────┐   ┌──────────────────────────┐
│ Media Forge        ⚙     │   │ ライブラリ               │
├──────────────────────────┤   ├──────────────────────────┤
│ 何を作りますか？         │   │ [すべて][作った][取込]   │
│ ┌──────────────────────┐ │   │ ┌────────┐ ┌────────┐   │
│ │                      │ │   │ │ thumb  │ │ thumb  │   │ 2列
│ └──────────────────────┘ │   │ └────────┘ └────────┘   │
│ ＋ 画像を追加            │   │ ┌────────┐ ┌────────┐   │
│ [1:1][16:9][9:16]        │   │ │ thumb  │ │ thumb  │   │
│ 枚数 [1][2]              │   │ └────────┘ └────────┘   │
│ [        作る          ] │   │      [ もっと見る ]      │
│                          │   │                          │
│ 最近作ったもの           │   │                          │
│ ┌──────┐┌──────┐┌──────┐ │   │                          │
│ └──────┘└──────┘└──────┘ │   │                          │
├──────────────────────────┤   ├──────────────────────────┤
│ ▓▓▓▓░░ 生成中 62%    ✕  │   │ （実行中のみ表示）       │ 40px sticky
├──────────────────────────┤   ├──────────────────────────┤
│   作る   ライブラリ  状況│   │   作る   ライブラリ  状況│ 56px + safe
└──────────────────────────┘   └──────────────────────────┘
```

規則:

```text
下部タブ 56px、タップ標的 44px 以上、safe_area token を padding へ加算
実行中ミニバーはタブに関係なく常時表示（要件「作成状況をモバイルで確認」）
結果は全画面プレビュー（ピンチズーム可）。ドロワーではなくシート
マスク描画はタッチ対応するが、モバイル既定のアクションは「全体を直す」
  （親指で細部を塗るのは苦痛。inpaint は選べるが押し付けない）
320px で横スクロールを発生させない。チップは折返す
詳細モードはモバイルでも使える（ボトムシート）。既定 OFF
```

### 5.5 ブレークポイント

| 幅 | 作る | ライブラリ |
|---|---|---|
| ≥1100px | 指示 400px + ステージ | minmax(200px,1fr) |
| 768–1099px | 指示 340px + ステージ | minmax(170px,1fr) |
| <768px | 単一列 + 下部タブ + ミニバー | 2 列固定 |
| <360px | 同上・チップ折返し | 2 列（gap 8px） |

---

## 6. 主要フロー

```text
F1 作る（初回）
   入力 → 作る → ステージが進捗 → 完成 → 保存 or 編集
   触る要素は 3 つ（文章・サイズ・作る）

F2 直す
   ライブラリで選ぶ or 画像を追加 → 「この画像を…」→ 5 択
   → 一部だけ直す: マスクを描く → 作る
   → 外側を広げる: 広げ方（比率・倍率）を選ぶ → 作る（幅高さは自動計算）
     上下左右を個別に指定する UI は作らない。backend の outpaint_plan は
     left = (width - source.width) // 2 で元画像を必ず中央へ置くため、
     非対称な拡張は現行契約では表現できない（実測確認 2026-08-22）。
     できるかのように見せない。必要になったら契約の追加として設計へ戻る。
   保証バッジは選択と同時に切り替わる

F3 一貫性（G3）
   結果ステージ「このキャラを登録」→ 名前のみ入力
     → reference collection（その asset 1 枚）+ character profile を作成
   以降 作る画面のチップで [キャラ: ロビン] を選ぶだけ
   構造化フィールド（外見・服装・色・NG）は詳細モードで編集

F4 見る・出す
   ライブラリ → カード → ドロワー → 保存
     保存A: ControlDeck のフォルダ選択（host.file.export の grant）→ 実ファイル書き出し
     保存B: ブラウザ保存（blob）。sandbox で失敗し得るため補助扱い
   ※ プロジェクトへ直接置くのは G4。ここでは実装しない

F5 失敗から戻る
   失敗行 → 日本語 1 文 + 出口 1 つ → 入力を保持したまま作る画面へ復帰
   例: マスクが空 → 「マスクを描き直す」でエディタを再オープン
```

---

## 7. 状態表現

### 7.1 capability → UI

`capabilities.get`（§11）の state を唯一の真実とする。

| state | シンプル | 詳細 |
|---|---|---|
| available | 表示 | 表示 |
| experimental | 表示 + 「試験中」ラベル | 同左 |
| unavailable | **非表示** | 無効表示 + 理由（`local_vlm_not_installed` 等の平易訳） |

`video.image_to_video` / `3d.image_to_3d` は現在 unavailable のため、
シンプルでは存在しない。詳細では「G7 で対応予定」と読める形にする。
**空のタブやダミー画面を作らない。**

### 7.2 phase → 日本語

backend の phase 名（実在するもののみ）:

| phase | 表示 |
|---|---|
| `starting` / `normalize_request` / `validate_request` | 準備しています |
| `select_model` | 使うモデルを選んでいます |
| `waiting_resource` | GPU の空きを待っています |
| `generating` | 生成しています |
| `postprocess` | 仕上げています |
| `semantic_review` | 内容を確認しています |
| `validate` | 保証を検証しています |
| `package` / `register_asset` | 保存しています |

### 7.3 error code → 日本語 + 出口

| code | 表示 | 出口 |
|---|---|---|
| `invalid_edit_mask` | 変更する場所が指定されていません | マスクを描き直す |
| `strict_edit_invariant_failed` | 守るはずの部分が変わってしまったため破棄しました | もう一度試す |
| `outpaint_invariant_failed` | 元画像を保ったまま広げられませんでした | 広げる量を減らす |
| `semantic_review_exhausted` | 指示どおりの結果になりませんでした | 指示を書き直す |
| `semantic_review_unavailable` | 内容チェックは今使えません | チェックなしで作る |
| `capability_unavailable` / `model_unavailable` | この操作は今使えません | 設定を開く |
| `resource_unavailable` / `host_lease_required` | GPU の空きを確保できませんでした | 時間をおいて再実行 |
| `worker_timeout` | 時間内に終わりませんでした | サイズか枚数を下げて再実行 |
| `invalid_dimensions` / `invalid_constraint` | 指定したサイズが使えません | プリセットに戻す |
| `invalid_reference_count` | 参考画像は 1〜3 枚です | 参考画像を選び直す |
| `asset_import_too_large` / `invalid_image_import` | この画像は取り込めません | 別の画像を選ぶ |
| `profile_not_found` / `reference_asset_not_found` | 指定したキャラ／画風が見つかりません | 選び直す |
| `unscoped_host_path` | 内部エラー（報告対象） | 設定を開く |
| 未知 | うまくいきませんでした | 状況を開く |

規則: token・path・外部レスポンス本文を表示しない。code は詳細モードのみ併記。

### 7.4 通知

UX ガイドライン「表示中 workspace の job は toast しない」に合わせる。
`visibility.changed` を購読し、**非表示のときだけ** `host.notification.show` を出す。
進捗は toast にしない。dedupe key は job id（現行踏襲）。

### 7.5 待機・接続

```text
handshake 前   theme 背景の skeleton を描く（白い FOUC を出さない）
               現行の visibility:hidden は「白を防ぐ」だけなので置き換える
8 秒無応答     host が状態画面へ切替える（host 実装済み）。MF は半端な状態を描かない
disable.pending 2 秒以内に実行中 job を cancel し、busy を落とす（現行踏襲）
```

---

## 8. プレビューと作成状況（要件の中核）

「PC・モバイルともに完成物と作成状況を確認できる」を満たす具体条件:

```text
C1 完成物のプレビュー
     PC     : ステージ大表示 + ライブラリのサムネイルグリッド + ドロワー拡大
     モバイル: 最近作ったもの帯 + 2列グリッド + 全画面シート
C2 作成状況
     PC     : ステージの進捗カード + 状況タブ
     モバイル: 常時表示のミニ進捗バー（タブ非依存）+ 状況タブ
C3 どちらもリロード不要で更新される（jobs.watch の push）
C4 タブを移動しても進捗を失わない
C5 複数枚生成時は候補ストリップで全候補を見比べられる
C6 編集結果は元画像と比較できる（lineage 親が存在する場合）
C7 動画は G7 まで存在しない。プレビュー面は media_type 分岐で拡張可能に作るが、
   未実装のタブ・ダミー再生面を先に作らない
```

サムネイルは backend 生成（256px 長辺・**WebP**・上限 64KB）とする。
フロントで縮小しても転送量が減らないため却下（§13-6）。

形式は実測で決めた（2026-08-22、PR-U0）。ノイズの多い 1024×1024 を 256px へ
縮小すると PNG は 220,714 バイトで上限に収まらず、解像度を 128px まで落とす必要が
あった。WebP q80 は同じ 256px を 41,392 バイトで保持する。**画質を先に譲り、
解像度は最後まで守る**（`_QUALITY_LADDER` → `_FALLBACK_SIDES` の順）。

---

## 9. 上級者の全機能アクセス

詳細モード ON で以下すべてに UI から到達できること。これは受け入れ条件である。

```text
job request の全フィールド
    operation / intent / inputs / model_policy / model_id / constraints
    output.format / output.count / qa.deterministic / qa.semantic
    qa.max_regeneration_attempts
    （local_only は常に true。UI から false にできない = backend 強制と一致）
constraints の実キー
    width / height / edit_mode / strict_edit / editable_mask_asset_id
    character_profile_id / style_profile_id
参照系
    reference collection の作成・削除・所属 asset
    profile（character / style）の全構造化フィールド編集
観測系
    job 生 JSON / phase 生名 / error code / provenance 生 JSON
    capability 一覧と reason / models カタログ（ID・ライセンス・実測値）
    host 連携診断（/api/v1/host-integration の内容）
```

原則との整合: 「public API にモデル名を必須で登場させない」は保たれる。
モデル名は **opt-in の詳細モードでのみ** 現れ、既定経路は capability routing のまま。

---

## 10. 技術制約と対応

```text
opaque sandbox（allow-same-origin なし）
    JS からの localStorage / sessionStorage / document.cookie は使用不可
      → preferences をサーバ側に置く（確定事項）
/ws の上限
    request 1 MiB / asset preview 12 MiB
      → サムネイルは 64KB 上限、原寸プレビューは 12 MiB 上限を UI 側でも守る
      → 12 MiB 超の asset は「原寸は書き出しで確認してください」と案内する
proxy の上限
    request 16 MiB / response 32 MiB（host 側）
アップロード
    既存の assets.import.begin/chunk/commit（512 KiB チャンク）を使う
    同時アップロードは 2 件まで（backend 既存制限）
path 文字列
    UI から path を送らない・受け取らない。file は grant ID のみ
```

### 10.1 画像を直接 subresource で取れるか（未検証・実測してから決める）

埋め込み frame の文書 URL は `/addon-frame/media-forge/...` である。したがって
`<img src="/addon-frame/media-forge/api/v1/assets/<id>/content">` という形は
**経路としては存在する**（proxy は任意 path を upstream へ転送する）。
成立するかは、sandbox された opaque origin の subresource 要求に
ControlDeck の session cookie（`SameSite=Lax`）が付くかどうかで決まる。

```text
ControlDeck 側の記述
    design-addon-platform-v2.md §7.2.3
    「opaque origin であっても /addon-frame/* へのリクエストには Cookie が付く。
      送信可否は URL 基準であり JS の origin 基準ではない」
    （proxy 層で Cookie/Authorization を削除する根拠として書かれている）
反対の可能性
    Chromium は opaque origin 文書の site-for-cookies を null として扱うため、
    Lax cookie が subresource に付かない可能性がある。
    frame 本体のナビゲーションは親から開始されるため cookie が付き、
    workspace HTML 自体は現に読み込めている。この 2 つは別の話である。
```

**判断**: 既定は `/ws` の base64（実績あり・§11 のサムネイルで転送量も解決する）。
その上で PR-U0 で 1 度だけ実測し、直接 subresource が成立するなら
原寸プレビューと将来の video（Range 要求）をそちらへ移す価値がある。
**測る前にどちらかを前提にした実装を書かない。**

---

## 11. 契約への影響

### 11.1 変更しないもの

```text
public API（/api/v1/*）のパスと意味
schemas/*.json
workflow executor / agent tools / context actions の定義
provenance / asset の必須フィールド
contract_version 1.0
```

### 11.2 追加するもの（workspace 内部トランスポート）

`/ws` は `docs/api.md` に「workspace のための実装詳細であり、
公開 operation ではない」と明記されている。よって **追加は契約変更に当たらない**。

| method | 目的 |
|---|---|
| `capabilities.get` | capability + サイズ envelope を 1 往復で取得 |
| `library.list` | asset に kind（生成/編集/取り込み）・要約・親数を付けて返す。mask は除外 |
| `assets.thumbnail` | 256px・64KB 上限のサムネイル（サーバ生成・キャッシュ） |
| `assets.export` | grant ID 指定で host files bridge へ書き出し |
| `preferences.get` / `preferences.set` | 利用者ごとの UI 設定（モード・最後のサイズ等） |
| `jobs.watch` / `jobs.unwatch` | job 変化の push（id なしイベントメッセージ） |

`jobs.watch` は既存の request/response に加えて、サーバ発の
`{"type":"event","event":"job.changed","data":{...}}` を流す。
フロントは `id` を持たないメッセージをイベントとして扱う（後方互換）。

### 11.3 変更する contribution（記録が必要）

```text
addon.json
  embedded_views[0].mobile : "companion" → "embedded"
  version                  : 0.1.2 → 0.2.0
```

- **影響**: 768px 未満で host が状態カードではなく workspace を描く。
- **理由**: companion のままでは要件（モバイルでのプレビュー・進捗）が
  ControlDeck 側の実装に依存し、Media Forge 側で満たせない。
- **移行**: 既存データ・API・agent 経路に影響なし。ロールバックは値を戻すだけ。
- **前提条件**: モバイル専用 IA（§5.4）が実装済みであること。
  未実装のまま `embedded` にしてはならない（縮小 workspace は規約違反）。

---

## 12. ControlDeck 側の変更要否

**結論: 不要。** 本設計は Media Forge のみで実装できる。

検討した依存点と結論:

```text
モバイル描画          host は mobile: "embedded" を既に受理する（AddonHost.tsx）
                      → MF 側の宣言変更のみで解決
安全領域              host のシェルが env(safe-area-inset-*) を処理済み。
                      theme token の safe_area は現在 0 で届くが、
                      iframe 内では inset が 0 に解決されるのが仕様どおり。
                      MF は自前の余白 + safe_area token 加算で足りる
書き出し              host.file.export（grant 発行）と host files bridge は実装済み。
                      /test/host-files/roundtrip で疎通実績あり
進捗 push             MF 内の /ws で完結。host.job.subscribe に依存しない
通知                  host.notification.show 実装済み
route 同期            host.route.sync 実装済み
```

将来 host 変更が必要になり得る唯一の点（今回は使わない）:

```text
theme token の safe_area が常に 0 であること自体を修正したい場合
  → その時点で ControlDeck 側の 1 箇所（useThemeTokens）変更を相談する。
     本設計はそれ無しで成立するため、今回は変更しない。
```

---

## 13. 却下した案

同じ議論に戻らないための記録（`base-plan.md` §3 と同じ扱い）。

```text
13-1 ノードグラフ / パイプライン編集を主 UI にする
     却下。base-plan §3.1・§16 を維持。内部実行計画は将来 read-only 可視化から。

13-2 ControlDeck 側にモバイル用 Media 画面を作る
     却下。AGENTS.md 規則 1 と roadmap §4「ControlDeck に Media 固有コードを 1 行も入れない」
     に反する。companion → embedded で MF 側に閉じる。

13-3 シンプルさを「上級機能の削除」で実現する
     却下。上級者の全機能アクセス要件と直接衝突する。隠す ≠ 消す（P2）。

13-4 作成をウィザード（複数ステップ）にする
     却下。1 枚作るまでの手数が増え、再実行が遅くなる。
     単一画面 + 文脈展開（L2）で同じ導線を作れる。

13-5 UI 設定を localStorage に保存する
     却下（不可能）。opaque sandbox。サーバ側 preferences にする。

13-6 サムネイルをフロントで縮小する
     却下。フルサイズ base64 の転送量（実測 1.4 MB/枚）が減らない。
     backend でサムネイルを作りキャッシュする。

13-7 満足するまで自動再生成する
     却下。base-plan §3.5 の判断を維持。qa.max_regeneration_attempts は
     明示 opt-in・上限つきのまま。既定 0（advisory）を変えない。

13-8 モデル選択を主要 UI に出す
     却下。capability routing 原則に反する。詳細モードの manual 経路のみ。

13-9 画像取得を frame からの直接 subresource に置き換える
     既定としては却下（保留）。§10.1 のとおり成立可否が未検証であり、
     /ws は実績がある。実測で成立が確認できた場合のみ、原寸プレビューと
     将来の video を移す。なお相対 URL は `/api/v1/...` ではなく
     `/addon-frame/media-forge/api/v1/...` でなければ届かない。

13-10 動画タブを今から置く（disabled 表示）
     却下。G7 未実装。「存在しないものを見せない」（§7.1）。
     プレビュー面だけ media_type 分岐で拡張可能にしておく。

13-11 検索・タグ・コレクションなど大きなライブラリ機能を今入れる
     却下（延期）。現時点の資産数では過剰。並び替えと種別セグメントで足りる。
     必要になった時点で再検討する。
```

---

## 14. 受け入れ条件（利用者の言葉）

```text
A1 初めて開いた人が、文章を 1 つ書いて「作る」を押すだけで画像を得られる
A2 できた画像がその場に大きく表示され、保存できる
A3 スマートフォンでも、作れて・進み具合が見えて・できた物が見られる
A4 一部だけ直したいとき、外部ツールなしで塗って指定できる
A5 同じキャラを続けて作れる（名前を付けるだけで固定できる）
A6 失敗したとき、何が起きたか日本語で分かり、次の一手が画面にある
A7 使えない機能が並んでいない
A8 上級者は詳細モードで、API で送れる値すべてに UI から到達できる
A9 タブを移動しても、生成中であることを見失わない
```

---

## 15. 測定項目（実装時に実測を記録する）

```text
ライブラリ初期表示の転送量と時間（asset 50 件、サムネイル導入前後）
最初の生成までの操作数（クリック/タップ回数）とキーストローク
job 状態が UI に反映されるまでの遅延（polling 1s → push）
モバイル実機（390×844 相当）での初期表示時間と横スクロール有無
320px 幅での崩れの有無
dark/light 両方での handshake 直後の白フラッシュ有無
書き出し 1 件の所要時間と生成ファイルの sha256 一致
```

計測なしの「改善した」は記録として認めない（AGENTS.md「完了の定義」）。
