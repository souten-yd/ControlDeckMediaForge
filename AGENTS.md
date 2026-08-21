# AGENTS.md — 開発エージェント向けガイド

このリポジトリで作業する AI エージェント / 開発者向けの規約。

## プロジェクト概要

ControlDeck Media Forge — ローカル完結の汎用メディア生成サービス。ControlDeck の Add-on
として動作しつつ、単体の API としても使える。ComfyUI の簡易版を作るプロジェクトではない。

```text
docs/base-plan.md                     設計の正（何を作るか・なぜそう決めたか）
docs/controldeck-integration-plan.md  統合の正（ホストとの境界。add-on 統合は本書が優先）
docs/design-workspace-ux.md           UI/UX の正（画面構成・段階開示・レイアウト）
docs/implementation/                  実装の指示（どの順で・何を確認して進めるか）
docs/implementation/ux1-handoff.md    UX1 の引き継ぎ状態。**再開時に最初に読む**
docs/implementation-status.md         現在の進捗。必ず確認・更新する
```

設計判断を変えるときは `base-plan.md` / `controldeck-integration-plan.md` を先に更新する。
実装指示だけを書き換えて設計を変えないこと。`base-plan.md` §3（却下した案）は消さない。

## 現在地

MF0-0〜MF0-3（分離環境、health、durable job、fake worker、asset/provenance）まで実装済み。
MF0-4のtoken introspection / Jobs / resource lease / scoped files bridgeは、Hostが受理する
identity経路で実装・実機確認済み。workflow:* と context:* subjectをHost Runtime側が受理しない
2件はfail-closedのまま未完了。MF0-5/6のworkspaceと実行endpointも、host契約が許す範囲で
installed-host browser実測済み。次は `docs/implementation-status.md` の2件のHost blockerを
再検証してMF0-4を完了させる。
各段階を飛ばさず、実機証跡を `docs/implementation-status.md` に追記する。
全体像は `docs/implementation/goal-roadmap.md`（G0〜G10）。

## 作業の進め方（context が切れる前提）

```text
再開時    docs/implementation/ux1-handoff.md を最初に読む
1 PR      1 スライス。跨がない。ブランチは ux1/<slug>
commit    ./mf.sh test 全通過 + 引き継ぎファイル更新をしてから
push      git push -u origin <branch> → gh pr create
記録      実測値のみ docs/implementation-status.md へ。推測を書かない
```

未 commit の状態は引き継げない。作業を止めるときは必ず commit と push を済ませる。
詳細は `docs/implementation/ux1-workspace.md` §14。

## ControlDeck との関係

ホスト側の Add-on Platform v2 / AI Resource Broker は実装済み。
Media Forge は「入る側」を作る。

```text
ControlDeck/docs/design-addon-platform-v2.md   Add-on contract 2.0 の仕様
ControlDeck/docs/addon-ux-guidelines.md        状態表現・文言規約
ControlDeck/tools/fake-addon/                  contract 2.0 準拠の動く参照実装
ControlDeck/deck.sh                            venv 管理・キャッシュ配置の作法
```

**ControlDeck リポジトリは原則として読み取り専用の参照。**
2026-08-22 に利用者が host 変更を許可したが、**汎用 host 機能に限る**。
Media 固有のコード・ルート・依存・文言を ControlDeck へ入れない
（`goal-roadmap.md` §4「完成の定義」は変わらない）。
host を触る前に「なぜ Media Forge 側で解けないか」を 1 行で書き、別リポジトリの
別 PR にする。条件は `docs/implementation/ux1-workspace.md` §0 B1。
manifest や API を推測で書かず、上記を読んでから書く。

## 技術スタック

- core: Python 3.11+ / FastAPI / Uvicorn / Pydantic v2 / SQLAlchemy / Pillow / httpx
- worker: PyTorch(ROCm) / Diffusers ほか。**core とは別の venv**
- frontend: 埋め込み workspace（opaque sandbox iframe 内で動作）
- 対象ハード: Linux + AMD GPU / ROCm。ただし公開 API に ROCm 前提を持ち込まない

## 環境

```bash
./mf.sh serve            # 環境チェック + 起動
./mf.sh doctor           # 環境診断（何も変更しない）
./mf.sh env build <name> # 重量 runtime の明示構築
./mf.sh env list         # core / runtime の一覧・サイズ・参照
./mf.sh env prune        # 参照ゼロの runtime を確認付き削除
./mf.sh test             # テスト
```

- core venv はリポジトリ直下 `.venv/`。`mf.sh` が自動構築する
- 重量 ML 環境は `runtimes/<name>/.venv/`。worker pack が共有する
- **ControlDeck の `.venv` を共有・流用しない**（依存が結合し import 禁止規則を破る）
- pip / uv / HuggingFace キャッシュは ControlDeck と同じ場所を指す（再取得可能なので安全）
- モデルの重みを venv 内に置かない
- 詳細は `docs/implementation/mf0-0-environment.md`

## 絶対に守るルール

1. **ControlDeck の内部モジュールを import しない**。連携は HTTP / declarative contract のみ。
2. **core 環境に torch / diffusers / transformers を入れない**。worker は別プロセス・別 venv。
3. **`shell=True` 禁止**。subprocess は配列引数。prompt を shell / path / SQL へ連結しない。
4. **ControlDeck から path 文字列を受け取らない**。`grant:` ID のみ扱う。届いたらホスト側のバグとして報告する。
5. **パスは realpath 正規化**し、許可ルート配下か検証してから使う。symlink 脱出を防ぐ。
6. **`local_only` を backend で強制**する。UI トグルだけにしない。remote 推論の経路を実装しない。
7. **public API にモデル名を必須で登場させない**。capability 名で routing する。
8. **GPU を使う job は ControlDeck broker から lease を取り、`estimated_runtime_sec` を申告**する。独自のグローバル GPU スケジューラを作らない。
9. **生成物には必ず provenance と lineage を付ける**。fake worker 由来でも省略しない。
10. **worker の失敗が本体を巻き込まない**。一部 worker が不在でも core は healthy を返せる。
11. **秘密値（service token 等）をログへ出力しない**。
12. **エラーを握り潰さない**。GPU 検出失敗を healthy として返さない。

## 契約凍結

**G1 完了時点で public 契約を凍結する。**

```text
schemas/ 配下の公開 JSON schema
addon.json の contribution 定義
agent tool 名と引数
workflow executor の type と schema
asset / provenance の必須フィールド
```

以降は追加のみ。破壊的変更が必要なら、なぜ追加で足りないか・既存資産への影響・
移行手順・version bump を先に書く。書かずに変更しない。

## UI ルール

埋め込み iframe は `allow-same-origin` なしの opaque sandbox。

- **localStorage / sessionStorage / Cookie を使わない**。状態は in-memory + サーバ側
- handshake で theme token を受け取ってから描画する（dark mode で白背景を一瞬出さない）
- `theme.changed` / `locale.changed` / `safe_area.changed` を購読し、reload せず反映
- `route.sync` で内部ルートをホスト URL へ反映（戻る/進む/共有が壊れる）
- `disable.pending` を受けたら 2 秒以内に保存・中断処理
- mobile は `companion` 宣言。320px に workspace を押し込まない
- node graph を作らない。`Create` は chat/prompt 指向
- 機能の出し分けは capability document から導出する。使えないものを既定で出さない
- 簡単さは段階開示で作る。機能削除で作らない。詳細モードから全機能へ到達できること
- 画面構成・レイアウト・文言表の正は `docs/design-workspace-ux.md`
- 詳細は `ControlDeck/docs/addon-ux-guidelines.md`

## コード規約

- 型ヒント必須。公開スキーマは `schemas/` に置き `docs/api.md` と同期する
- worker は `workers/base.py` の interface に従う。core から実装を import しない
- コミットは段階 / 機能単位で簡潔に

## 完了の定義

コードを書くだけでは完了ではない。

```text
証拠として認めるもの
    実行したコマンドとその出力
    実測値（秒・バイト・件数）
    実プロセスへの実 HTTP リクエストと応答
    実ブラウザでの操作と assertion

証拠として認めないもの
    lint 成功 / 型検査成功 / build 成功
    テスト成功（仕様通りの証拠であって「動く」証拠ではない）
    「〜のはず」という記述
    実行していないコマンドの想定出力
```

実機で動かし、`docs/implementation-status.md` に
**何を実行し、何を観測し、何が NOT TESTED か**を記録してから完了とする。
未実施を「成功」と書かない。NOT TESTED は正しい記録であり、失点ではない。

## 止める判断

以下に当たったら、無理に完成させずに延期して記録する。

```text
モデルが gfx1201 / ROCm で安定動作しない   -> 代替を探す。カーネル自作へ踏み込まない
VRAM が実測で収まらない                    -> 量子化・解像度制限。駄目なら延期
public 契約を壊さないと実装できない        -> 設計へ戻る。契約を曲げない
依存が ControlDeck 側へ漏れそうになる      -> 境界が誤り。実装を止める
```

延期理由と再開条件を `docs/implementation-status.md` に書けば、正しい進行である。
