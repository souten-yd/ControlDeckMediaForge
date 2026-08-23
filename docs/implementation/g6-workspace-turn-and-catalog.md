# G6 workspace turn / resource turn / model catalog 実装計画

利用者報告 7 件（❶〜❼）への対応計画。実装前に本書を確定する。
設計の正を変える差分は `base-plan.md` / `controldeck-integration-plan.md` へ先に入れる。

---

## 0. 観測した事実（推測を書かない）

```text
2026-08-24 実測
  ControlDeck        /data1tb/ControlDeck/app  pid 818393  :8765  ok
  Media Forge        installed feature 0.5.1   pid 705506  :9130
  GPU                R9700 34,208,743,424 B / 使用 59,912,192 B（測定時アイドル）
  LLM 設定           llama.cpp / vulkan / Qwen3.8-27B-UD-Q4_K_M + mmproj-BF16
                     ctx_size 262144 / n_gpu_layers 999
  runtime policy     supervision="observed"  gateway_only=true  yield_max_level=4
                     idle_unload_enabled=true / 30 分
  core test          359 passed（G5 込み。従来基準 352 + G5 7）
```

### ❸ 状況タブが読めない — 根本原因を特定した

`GET /api/v1/jobs` が 500。実プロセスの traceback:

```text
mediaforge/app.py:1092 list_jobs -> store.py:292 list_jobs -> store.py:720 _job
  -> pydantic ValidationError: 2 errors for JobRequest
     inputs        List should have at most 16 items after validation, not 21
     output.format Input should be 'png','webp' or 'jpeg', input_value='zip'
```

`Store._job()` は保存済み行を **その時点の `JobRequest` で再検証**する。G5 で
`inputs` 上限と `output.format` を加法的に広げた結果、新形式で書かれた 1 行を
旧 core が読めず、`list_jobs` が行単位ではなく**コレクション全体**で落ちる。
UI 側は `jobs.list` の失敗を `catch` して「状況を読み込めませんでした。」と出すだけなので、
1 行の不整合で状況タブ全体が死ぬ。

これは G5 固有の事故ではなく**永続化読み出し全体の欠陥クラス**である。
`list_creative_compositions` も同じく `model_validate_json` を直に呼んでいる。

### ❷ VLM が VRAM を返さない — 根本原因を特定した

```text
ControlDeck/app/backend/app/models_mgmt/resource_provider.py
  LlamaCapacityProvider._managed() は policy.supervision == "managed" を要求する
  実機は "observed" -> _managed() False -> reservations() の yield_level = NONE
  -> broker は llama を退避対象に一切しない
```

つまり現状の ControlDeck は**設計上 LLM を降ろさない**。Qwen3.8-27B Q4_K_M +
ctx 262144 は 32GB 級 VRAM の大半を占有し、FLUX.2 Klein 4B の実行 peak が入らない。
Media Forge 側は既に生成 lease を vision 前に解放している（jobs.py の release_resource）が、
**逆方向（LLM -> 画像）を解決する手段が公開契約に存在しない**。

加えて `ControlDeck/app/backend/app/addon_runtime/ai.py::ai_complete` は
`/api/v1/llm` の `gateway_chat` と違い `llama.ensure_ready(alias)` を呼ばない。
停止中インスタンスへ add-on の AI 要求が飛ぶと死んだ port を叩く。
「降ろす」機能を入れるなら「必要時に上げ直す」も同時に要る。

### ❶❹ GUI が重い — 計測に基づく内訳

```text
frontend/app.js 139,281 B / 3,329 行（単一ファイル・分割なし）
boot() は直列 await が 10 段
  preferences.get -> capabilities.get -> creative.templates -> loadProfiles
  -> loadModelManagement -> refreshAttachment -> loadEstimate -> loadRecent
  -> restoreCreativeComposition -> restoreCreativeBatch -> jobs.watch
そのうえ 1 秒間隔の polling が 3 本（pollJob / pollBatch / pollComposition）。
job.changed / model.operation.changed の push は既にあるので polling は純粋な重複。
状態の正がクライアントの `state`（40 フィールド）にある。
```

### ❺ 実装済みだが GUI から到達できない機能

backend の /ws method 48 件と frontend の呼び出しを突き合わせた差分:

```text
profiles.create / profiles.delete                 G3 一貫性プロファイル（PR-U6 未着手）
reference_collections.create / .delete            参照コレクション
creative.prompt_recipe                            H3 版固定 prompt recipe
assets.list
jobs.unwatch / models.operations.unwatch          内部用。UI 機能ではない
```

加えて operation 単位:

```text
media.inspect    agent tool と REST にはあるが GUI から起動できない
asset.pack       G5。GUI から起動できない
```

---

## 1. 方針と却下した案

### ❷ LLM のアンロードをどこが持つか

| 案 | 内容 | 判断 |
|---|---|---|
| A | broker の既存 yield に委ねる | **単独採用しない**。`supervision=observed` では発火せず、`managed` にしても load-cost / thrash / min-uptime で抑止される。決定的でない |
| B | Host に汎用 `ai` 明示解放 primitive を足し、順序制御は Media Forge が持つ | **採用** |
| C | Media Forge が llama プロセスを止める | **却下**。AGENTS.md 1 / 8 違反 |
| D | lease 要求に「排他 VRAM 必須」を足す | **却下**。broker の受理判断を add-on 側へ二重化する |

B が「主要機能は Media Forge が持つ」と両立する理由: Host へ足すのは
**「この add-on の AI ターンは終わった」という 1 個の宣言**だけで、
いつ解析し・いつ解放を要求し・解放できなかったらどう失敗するかという
**順序と方針はすべて Media Forge が持つ**。Host は最終判断権を保持し拒否できる。

Media Forge の 1 ジョブを 4 ステージへ分割する。

```text
stage 1  analyze     Host AI（text.generate / vision.analyze）だけを実施
                     この間 Media Forge は GPU lease を一切持たない
stage 2  ai_release  AI ターン終了を Host へ宣言し、解放結果を受け取る
stage 3  generate    broker lease を estimated_runtime_sec 付きで取得 -> 画像 worker
stage 4  review      画像 lease を解放してから vision 評価（既存挙動を維持）
```

stage 2 -> 3 の順序が ControlDeck の queue と競合しない理由: Media Forge は
**先に AI 常駐を落としてから lease を申請する**。以後の LLM 再ロードは
broker の受理を通るため、二重予約も deadlock も起きない。

Host 側変更（別リポジトリ・別 PR。汎用機能に限る）:

```text
なぜ Media Forge 側で解けないか
  LLM プロセスの寿命は ControlDeck が所有し、add-on には HTTP 契約しか無い。
  「AI ターン終了」を伝える口が公開契約に存在しないため add-on 側だけでは解けない。

1. POST /api/v1/addon-runtime/{addon_id}/ai/release
     ai.inference grant を持つ任意の add-on が使える。media 固有語彙を持たない。
     応答 {"released": bool, "reason": str, "resident_bytes": int}
     Host は拒否できる（他の consumer が実行中など）。
2. ai_complete に llama.ensure_ready を追加し gateway_chat と同じ on-demand 起動にする。
```

Media Forge は解放できなかった場合に `host_ai_residency_retained` として
**理由付きで fail-closed** する。無言の OOM にしない。
`supervision=observed` は診断として利用者へそのまま提示する。

### ❶❹ 状態管理をサーバ側へ

| 案 | 内容 | 判断 |
|---|---|---|
| A | サーバ生成 HTML 断片で UI を丸ごと駆動 | **却下**。opaque sandbox と段階開示の既存設計を壊す割に得が小さい |
| B | フレームワーク導入で再実装 | **却下**。core を軽く保つ方針と、実測済み UI 受入証跡を捨てる |
| C | 1 回の session snapshot + server push delta | **採用** |

```text
identity 非依存      既存の HTML 埋め込みを拡張（envelope / presets / templates）
                     -> 初回描画に round trip 0
identity 依存        workspace.session 1 メソッドへ集約
                     preferences / capabilities / profiles / reference collections
                     / model catalog / recent library / 実行中 job・batch・composition
                     -> 直列 10 -> 1
更新                 既存の job.changed / model.operation.changed に
                     session.changed を追加。polling 3 本を削除する
```

状態の正はサーバの session snapshot に置き、クライアントは受け取った snapshot を
描画するだけにする。localStorage / sessionStorage / Cookie は引き続き使わない。

### ❻ HuggingFace カタログ

既存実装: `worker_packs/image/catalog.json` に revision pin 付き HF エントリ、
`models.install` が SHA-256 検証・再開・32GB 上限付きで取得する。**取得系は既にある。**
不足しているのは「利用者が任意の HF モデルを足せない」ことだけ。

| 案 | 内容 | 判断 |
|---|---|---|
| A | GUI から HF Hub を検索して任意 repo を導入 | **既定にはしない**。revision 非固定・実測 VRAM 無し・license gate・任意コード実行の risk。local-first の検証可能性が壊れる |
| B | curated pinned catalog を信頼経路として維持し、明示的な custom model 追加を別扱いで足す | **採用** |

```text
B の流れ
  repo_id + revision を利用者が明示入力
  -> HF API で file 一覧 / 総 bytes / license を解決して提示
  -> license を明示同意
  -> 既存 installer で pinned 取得 + SHA-256
  -> experimental / unmeasured / unroutable として登録
  -> models.evaluate が実機実測に成功して初めて routing 対象へ昇格
```

既存の「実測しないと使わせない」gate を custom model にもそのまま適用する。

**個別ローダーは要るのか（利用者質問への回答）**

要る。ただし「モデルごとに 1 から書く」ではなく**系統ごとの薄い adapter**である。

```text
worker_packs/image/adapters/  が既にその境界
  base.py            ImageAdapter Protocol（generate / edit）
  diffusers_flux2.py FLUX.2 用。pipeline class と参照編集の意味論が固有
  native.py          Diffusers を使えない runtime 用の口（未実装）

SD1.5 / SDXL / SD3 系は Diffusers の AutoPipelineForText2Image /
AutoPipelineForImage2Image / Inpaint で **1 個の共通 adapter に相乗りできる**。
新規に要るのは pipeline class の選択、dtype と offload 方針、
inpaint / img2img / reference の引数対応表、negative prompt や scheduler の有無だけ。

別 adapter が要るのは次の場合に限る
  Diffusers に pipeline が無い（stable-diffusion.cpp / GGUF 単一ファイル等）
  参照編集の意味論が固有（FLUX.2 の multi-reference がこれ）
  trust_remote_code を要求する（原則入れない）
```

本 PR では **`diffusers_sd.py`（SD/SDXL/SD3 共通 adapter）は設計と境界だけ確定し、
実装と実測は別スライスへ送る**。実測していない adapter を available にしない。

### ❼ モデル選択

既存: `model_policy` に auto/fast/balanced/quality/low_vram/manual、`model_id`、
advanced モードに `advanced-model` select。**明示選択はすでに動く。**
不足は 2 点。

```text
1. simple モードから到達できず、選んだ理由も見えない
2. auto が policy_rank だけで決まり、シーン（domain）を見ていない
   catalog には既に domains[] があるのに routing が使っていない
```

対応:

```text
route_model に domain を渡し、domain 一致を policy_rank より前段の候補絞りに使う
  一致 0 件なら従来どおり全候補へ落とす（fail-soft。使えるモデルを消さない）
選択結果と根拠（capability / domain / policy / 実測 VRAM）を job と UI に出す
UI は「おまかせ」と「モデルを指定」の 2 段で出し、詳細モードで全モデルへ到達させる
```

---

## 2. スライス

```text
S1  永続化の前方互換                 ❸
      Store の読み出しを行単位 fail-soft にする
      保存行は寛容に読み、厳格な境界検査は API ingress でだけ行う
      degraded 行は状態を明示して一覧に残す（黙って消さない）
      既存 DB の壊れた行を復旧する
S2  workspace session snapshot        ❶❹
      workspace.session 追加 / boot 直列 10 -> 1
      session.changed push 追加 / polling 3 本削除
S3  resource turn                     ❷
      4 ステージ化 / ai_release / fail-closed な理由付き失敗
      ControlDeck 側 PR（ai/release と ensure_ready）は別リポジトリ別 PR
S4  到達性                            ❺❼
      profiles / reference collections の作成・削除 UI
      prompt recipe / media.inspect / asset.pack の入口
      モデル選択の 2 段 UI と選択根拠の表示
S5  domain 対応 routing               ❼
      route_model の domain 候補絞り
S6  custom HF model                   ❻
      repo_id + revision 明示追加 / license 同意 / unmeasured 登録
      SD 系共通 adapter は境界だけ確定し実装は別スライス
```

1 PR = 1 スライスの原則に対する逸脱: 利用者が「PR を作成し適宜プッシュし
完成後にマージ」と明示したため、**1 ブランチ 1 PR / スライス単位の commit** とする。
スライス境界は commit で保つ。

## 3. 契約への影響

```text
加法のみ。破壊的変更を行わない。
  追加  /ws workspace.session
  追加  /ws session.changed イベント
  追加  job の stage 表現と host_ai_residency_retained エラーコード
  追加  model catalog の custom エントリ種別
  変更なし  operation 名 / agent tool / asset・provenance 必須フィールド / Host grant 境界
```

## 4. 受け入れ

```text
❸  壊れた行を含む DB で jobs.list が 200 を返し、状況タブが描画されること（実 HTTP）
❷  実機で LLM 常駐 -> analyze -> ai_release -> 画像生成成功まで通ること
    解放できない構成では OOM ではなく理由付きエラーで停止すること
    rocm-smi の VRAM 推移を実測値として記録すること
❶❹ boot の workspace 往復回数と初回描画までの実測時間を before/after で記録すること
❺❼ 追加した入口を実ブラウザで操作し、assertion で到達を確認すること
❻  custom model 追加が pinned 取得と unmeasured 登録まで実機で通ること
```

実機で動かすまで COMPLETE と記録しない。NOT TESTED は正しい記録である。
