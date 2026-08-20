# Codex実装指示 — Media Forge MF0: Standalone Core + Add-on v2 接続

対象リポジトリ: `souten-yd/ControlDeckMediaForge`
現状: `README.md` / `docs/base-plan.md` / `docs/controldeck-integration-plan.md` のみ（実装ゼロ）
ホスト側前提: ControlDeck `8681eb7` で Add-on Platform v2 PR-0〜PR-E がマージ済み

設計の正:

- `docs/base-plan.md` §22 Phase 0
- `docs/controldeck-integration-plan.md` §15 MF0 / MF1
- ControlDeck `docs/design-addon-platform-v2.md`（Add-on contract 2.0）
- ControlDeck `docs/addon-ux-guidelines.md`
- ControlDeck `tools/fake-addon`（**実装の参照実装として読むこと**）
- [`mf0-0-environment.md`](mf0-0-environment.md)（MF0-0。**本書より先に実施する**）
- [`goal-roadmap.md`](goal-roadmap.md)（本書は G0 に相当）

---

## 0. MF0 の目的

**モデルを1つも動かさずに、Add-on として完全に成立させる。**

ControlDeck 側の汎用基盤は完成している。MF0 の役割は
「受け入れる側」ではなく「入る側」を作ること。
重い依存（PyTorch / Diffusers / FFmpeg / Blender）は MF0 に入れない。

MF0 完了時点で以下が成立していること。

```text
ControlDeck から install / enable でき、Media が sidebar に出る
embedded workspace が ControlDeck shell 内で動く
fake worker でジョブが走り、asset と provenance が残る
Workflow node / Agent tool / Context action が discovery に出て実行できる
GPU lease を取得し、estimated_runtime_sec を申告する
disable すると全部消え、データは残る
```

MF1 以降で fake worker を実 worker に差し替えても、
**上記の contract を一切変えずに済む**こと。ここが唯一の設計目標。

---

## 1. やってはいけないこと

```text
PyTorch / Diffusers / transformers / ComfyUI への依存追加
FFmpeg / Blender への依存追加
実モデルのダウンロードや推論
node graph エディタの実装
M5 / game2d / web profile の実装（MF2）
ControlDeck の内部モジュールを import すること
ControlDeck の session cookie を前提にした実装
manifest に任意コードを持たせること
ControlDeck へ path 文字列を要求すること（grant: ID のみ扱う）
remote 推論APIへの接続経路を実装すること（local_only を backend で強制）
prompt 文字列を shell へ渡すこと
```

---

## 2. リポジトリ構成

`docs/base-plan.md` §4.2 に従う。MF0 では以下だけを作る。

```text
ControlDeckMediaForge/
├─ addon.json                    Add-on v2 manifest
├─ pyproject.toml                依存は FastAPI / uvicorn / pydantic / httpx / Pillow のみ
├─ backend/
│  └─ mediaforge/
│     ├─ main.py                 ASGI entrypoint
│     ├─ config.py               data_dir / policy
│     ├─ api/
│     │  ├─ media.py             image.generate / image.edit / media.inspect
│     │  ├─ jobs.py
│     │  ├─ assets.py
│     │  ├─ capabilities.py
│     │  ├─ health.py
│     │  ├─ workflow.py          remote executor（schema / execute / cancel）
│     │  ├─ tools.py             agent tool（schema / invoke）
│     │  └─ context.py           context action
│     ├─ host/
│     │  ├─ client.py            ControlDeck host API client
│     │  ├─ token.py             service token 受領・検証
│     │  ├─ resources.py         lease acquire/renew/release
│     │  └─ jobs.py              remote job register/update
│     ├─ jobs/                   durable job store + runner
│     ├─ assets/                 asset library + provenance sidecar
│     ├─ routing/                capability router（fake registry のみ）
│     ├─ models/                 model registry（宣言のみ、実体なし）
│     ├─ workers/
│     │  ├─ base.py              worker interface
│     │  └─ fake.py              fake worker（唯一の実装）
│     └─ validators/             deterministic validators（Pillow のみ）
├─ frontend/                     embedded workspace（最小）
├─ schemas/                      公開JSON schema
├─ scripts/                      起動・開発スクリプト
├─ tests/
└─ docs/
```

Pillow は入れる。deterministic validator（寸法・mode・alpha）に必要で、
これが無いと MF2 の strict_edit の土台が作れない。

---

## 3. addon.json（Add-on contract 2.0）

ControlDeck の `./deck.sh ext lint addon.json` を通すこと。
**まずこのコマンドを実行して schema を確認してから書く。** 推測で書かない。

宣言する contribution:

```text
navigation        Media（route /media、permission media.view）
embedded_views    workspace
commands          create-media
quick_actions     create-media
settings          media-settings
workflow_executors  media.generate
agent_tools       media.generate / media.capabilities / media.inspect
context_actions   edit-image（contexts: file、accepts: image/png, image/jpeg）
```

要求する host_capabilities:

```text
files.scoped
projects.read
jobs.bridge
notifications.publish
workflow.remote_executor
agent.remote_tools
ai.resource_lease
```

`runtime.kind = "external-service"`、`health_url` は loopback。
ControlDeck 側は HTTPS か loopback のみ許可する実装になっているので、
開発時も loopback で揃えること。

---

## 4. health エンドポイント

ControlDeck の health polling は15秒間隔、3秒 timeout、64KiB 上限、
3回失敗で unavailable、degraded→healthy は2回成功。
**この制約下で必ず3秒以内に返すこと。** worker の疎通確認を同期で行わない。

4状態すべてを返せること。開発用に手動切替エンドポイントを持たせる
（`tools/fake-addon` と同じ方式。本番では無効化できるようにする）。

```json
{
  "status": "degraded",
  "contract_version": "2.0",
  "contributions": {
    "navigation:media": "available",
    "embedded_view:workspace": "available",
    "workflow_executor:media.generate": "available",
    "agent_tool:media.inspect": {
      "state": "unavailable",
      "reason_code": "worker_not_installed",
      "message": "Vision worker is not installed",
      "action": { "kind": "open_route", "route": "/media/settings#workers" }
    }
  },
  "setup": [
    { "id": "service", "label": "サービス起動", "state": "ok" },
    { "id": "data_dir", "label": "データ領域", "state": "ok" },
    { "id": "image_model", "label": "画像モデル", "state": "missing",
      "message": "MF0 は fake worker のみを提供します",
      "action": { "kind": "open_route", "route": "/media/settings#workers" } }
  ]
}
```

MF0 では実モデルが無いので、既定で `setup_required` を返してよい。
ただし fake worker だけで全機能が動くことを設定で選べるようにし、
E2E では `healthy` にできること。

---

## 5. ジョブと asset

### 5.1 内部実行プラン

`docs/base-plan.md` §17 の内部DAGを MF0 から実装する。
後付けは困難で、retry / trace / cancel の土台になる。

```text
NormalizeRequest
  -> SelectModel        （fake registry から選択）
  -> AcquireGpuLease    （ControlDeck broker へ要求）
  -> Generate           （fake worker）
  -> DeterministicPostprocess
  -> Validate
  -> Package
  -> RegisterAsset
```

各ノードは phase 名を持ち、進捗として ControlDeck へ報告する。
**内部DAGを公開workflow形式として露出しないこと。**

### 5.2 job store

```text
SQLite（data_dir/mediaforge.db）
プロセス再起動後も job が復元される
cancel は待機中・実行中の両方で機能する
timeout を持つ
job ごとに一時ディレクトリを作り、終了時に消す
```

### 5.3 asset + provenance

生成物には必ず sidecar manifest を出す（`docs/base-plan.md` §2.7）。
MF0 では fake でも全フィールドを埋める。埋められない項目は
`null` ではなく `"unavailable_in_mf0"` のような明示値にし、
後で実 worker が入ったときに埋め忘れが検出できるようにする。

```text
asset_id / parent_asset_ids
operation / intent
model_id / version / weights_hash / license
runtime_adapter / runtime_version
prompt / constraints
reference_asset_hashes
seed / generation_params
postprocess_ops
tool_versions
output_hashes
validation_results / warnings
```

lineage（親子関係）を MF0 から持つこと。MF2 の variant 機能の土台になる。

---

## 6. ControlDeck 連携

### 6.1 service token

ControlDeck の proxy が audience 束縛・10分TTL の service token を注入する。
Media Forge は **Cookie を受け取らない前提**で実装する。

```text
token の audience / addon_id / 有効期限を検証する
token 無しのリクエストは 401
loopback 直アクセス（proxy を経由しない）でも token 検証を行う
token を log に出さない
```

### 6.2 GPU lease

`host.resources.acquire / renew / release` を使う。

**`estimated_runtime_sec` を必ず申告すること。**
ControlDeck 側の thrash guard はこの値が無いと退避判断ができず、
`runtime_unknown` で常に抑止される。MF0 の fake worker は
実行時間を指定して起動するので、その値をそのまま申告すればよい。

```json
{
  "owner": "addon:media-forge",
  "job_id": "...",
  "device": "auto",
  "vram": {
    "resident_bytes": ...,
    "execution_peak_bytes": ...,
    "cold_load_peak_bytes": ...,
    "headroom_bytes": ...,
    "confidence": "low"
  },
  "compute_mode": "exclusive-preferred",
  "priority": 20,
  "class": "interactive",
  "residency_key": "mediaforge:fake-image-v1",
  "estimated_runtime_sec": 12.0,
  "max_wait_sec": 300,
  "on_insufficient": "queue"
}
```

`confidence` は MF0 では `"low"` 固定。実測が入る MF1 以降で上げる。
lease は renew を怠らないこと。TTL 切れで強制回収される。

### 6.3 Jobs bridge

Media Forge 内部の job と ControlDeck の Job を対応付ける。
高頻度の内部進捗を**そのまま流さない**。

```text
ControlDeck への進捗は 2Hz 上限、単調増加、phase 必須
内部の細かいステップ進捗は Media Forge 側に留める
terminal（成功・失敗・キャンセル）は必ず通知する
```

### 6.4 file / project

**ControlDeck から path 文字列を受け取らない。** `grant:` ID のみを扱う。
書き込みは `host.files.commit_write` を通す。
自前で任意パスへ書かない。data_dir 配下のみ自由に扱ってよい。

---

## 7. embedded workspace（frontend）

### 7.1 制約

ControlDeck の iframe は `allow-same-origin` **なし**の opaque sandbox。

```text
localStorage / sessionStorage / Cookie は使えない
document.cookie は読めない
親frame の DOM に触れない
WebSocket は Bridge nonce を専用 subprotocol で渡す方式（ControlDeck 実装を確認すること）
```

状態は in-memory + サーバ側に置く。**ブラウザストレージ前提の実装をしない。**

### 7.2 Host Bridge

handshake を最初に行い、theme token を受け取ってから描画する。

```text
handshake 完了前に自前の背景色で描画しない（FOUC 禁止）
theme.changed / locale.changed / safe_area.changed を購読し、reload せずに反映
route.sync で内部ルートを ControlDeck の URL に反映（戻る/進む/共有が壊れる）
title.set でヘッダを更新
busy.set で未保存変更を通知
disable.pending を受けたら2秒以内に保存・中断処理を行う
```

### 7.3 画面（MF0 最小）

```text
Create      prompt + 参照ドロップ + 出力数 + Auto/Fast/Balanced/Quality
Library     生成物一覧 + provenance 表示 + lineage
Jobs        進行中・履歴（ControlDeck Jobs への deep link）
Models      fake registry の表示（インストール機能は MF1）
Settings    policy（local_only）表示、worker 状態
```

node graph は作らない。
`Create` は chat/prompt 指向にし、profile は後から差し込める形にしておく。

### 7.4 mobile

`addon.json` の embedded_view に `"mobile": "companion"` を宣言する。
MF0 の workspace を 320px に押し込まない。
ControlDeck が host 側で簡易画面を出す。

---

## 8. Workflow / Agent / Context

### 8.1 workflow executor

```text
GET  /addon/v1/workflow/media.generate/schema    input/output schema
POST /addon/v1/workflow/media.generate/execute
POST /addon/v1/workflow/media.generate/cancel
```

ControlDeck の dry-run は cache 済み schema だけで検証し、
**Media Forge を呼ばない**。したがって schema は安定して返せること。

### 8.2 agent tool

```text
media.capabilities    利用可能な capability を返す（モデル名を返さない）
media.generate
media.inspect
```

capability の返し方は `docs/controldeck-integration-plan.md` §11 に従う。

```text
image.text_to_image       = available   （fake）
image.strict_edit         = unavailable （MF2）
video.image_to_video      = unavailable
3d.image_to_3d            = unavailable
```

**モデル名（FLUX / Qwen 等）を返さない。** agent が pin するのはユーザ明示時のみ。

### 8.3 context action

`edit-image` を1つだけ実装する。
ControlDeck から `grant:` ID と context 種別と短命 token が渡る。
path は渡ってこない。渡ってくる実装になっていたら ControlDeck 側のバグとして報告する。

---

## 9. セキュリティ（MF0 から守る）

`docs/base-plan.md` §18 の最小規則を MF0 から実装する。後付けは高コスト。

```text
非root で動作
data_dir 外へ書かない（grant 経由を除く）
subprocess は引数配列。shell=True 禁止（MF0 では subprocess 自体不要）
prompt を shell / path / SQL に渡さない
job ごとの一時ディレクトリと確実な後始末
timeout / cancel / 出力サイズ上限
local_only=true を backend で強制（UI のトグルだけにしない）
remote provider 経路を「実装しない」ことで担保する
token を log に出さない
```

---

## 10. テスト

```text
manifest が ./deck.sh ext lint を通る
health の4状態すべてを返せる
contribution 単位の availability が返る
job: 作成 -> lease -> fake実行 -> asset 登録
job: プロセス再起動後の復元
job: 待機中 cancel / 実行中 cancel / timeout
lease: renew を怠ると TTL で回収される
lease: estimated_runtime_sec が必ず含まれる          ★
asset: provenance 全フィールドが埋まる
asset: lineage の親子が引ける
validator: 寸法 / mode / alpha
local_only: remote 指定が backend で拒否される
token: 無し -> 401 / audience 不一致 -> 401
path: grant 外への書き込みが拒否される
capabilities: モデル名が応答に含まれない            ★
workflow: schema が安定して返る（dry-run が呼ばない前提）
```

★ の2件は境界の本体なので必ず含めること。

---

## 11. 実機E2E（MF0 完了条件）

ControlDeck を実起動し、Media Forge を別プロセスで loopback 起動して確認する。

```text
A  install -> disabled。ControlDeck に Media が一切出ない
B  enable -> setup_required。host 描画のチェックリストが出る
C  fake worker のみ構成へ切替 -> healthy。sidebar に Media が出る
D  /media を開く -> ControlDeck shell 内に workspace。theme 一致、FOUC なし
E  Create から生成 -> ControlDeck Jobs に出る -> 完了 toast -> asset が Library に出る
F  theme 切替 -> iframe reload なしに追従
G  戻る/進む/reload/URL共有 が workspace 内で成立
H  Files で画像を選び Open with -> edit-image が出て起動する
I  Workflow に media.generate node が出る。dry-run が Media Forge を呼ばない
J  OpenCode から media.capabilities が見える。モデル名が含まれない
K  fake GPU job 2件で 1件が waiting_resource。runner slot を占有しない
L  disable -> 全 contribution 消滅。開いていた view が状態ページへ置換
M  再 enable -> 過去の asset / job 履歴が残っている
N  320px -> companion 画面が出る（workspace を押し込まない）
```

各 run 後に一時 Add-on を uninstall し、fake プロセスを停止すること。

---

## 12. 段階

1本のPRにしない。以下の順で分ける。

```text
MF0-1  service skeleton + health + addon.json + ext lint 通過
MF0-2  job store + fake worker + 内部実行プラン + cancel/timeout
MF0-3  asset library + provenance + lineage + validators
MF0-4  host 連携（token / lease / jobs bridge / files grant）
MF0-5  embedded workspace + Host Bridge + theme
MF0-6  workflow / agent / context contribution
MF0-7  E2E（§11 A〜N）+ docs
```

各段階で tests を通してから次へ進む。

---

## 13. ドキュメント

```text
docs/implementation-status.md   新規。各段階の実測検証を記録する
docs/api.md                     公開API（schemas/ と同期）
docs/base-plan.md               MF0 完了状況を反映
README.md                       起動手順・ControlDeck への install 手順
```

`docs/implementation-status.md` は ControlDeck 側と同じ流儀にする。
「何を実測し、何が NOT TESTED か」を明記し、
lint 成功を利用可能状態として扱わないこと。

---

## 14. 完了条件

```text
実モデル・重量依存ゼロで §11 A〜N がすべて通る
lease に estimated_runtime_sec が入り、ControlDeck の broker が判断できる
provenance と lineage が MF0 の fake 生成物にも完全に付く
public API に一度もモデル名が現れない
fake worker を実 worker に差し替えるとき、
  api/ ・ schemas/ ・ addon.json を変更しなくてよい構造になっている
```

最後の項目が MF0 の本質。ここが崩れていれば、他が全部通っても未完了とする。
