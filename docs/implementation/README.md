# Media Forge 実装指示

実装エージェント（Codex 等）へ渡す指示書。設計文書とは役割が違う。

```text
docs/base-plan.md                    設計の正（何を作るか・なぜそう決めたか）
docs/controldeck-integration-plan.md 統合の正（ホストとの境界）
docs/design-workspace-ux.md          UI/UX の正（画面構成・段階開示・レイアウト）
docs/design-model-scene-ux.md        既存UXを流用するモデル管理・シーン/ポーズ/構図拡張
docs/design-creative-intelligence.md Creative Director / Reference Intelligence / Evaluator の正
docs/implementation/                 実装の指示（どの順で・何を確認して進めるか）
```

設計判断を変えるときは `base-plan.md` / `controldeck-integration-plan.md` と該当する設計文書を先に更新する。
指示書だけを書き換えて設計を変えないこと。
`design-model-scene-ux.md` は既存 `design-workspace-ux.md` の情報構造と Simple/Advanced 方針を維持したまま、モデル管理とクリエイティブ制御を追加する拡張設計である。
`design-creative-intelligence.md` は UX2 M0〜C5 を作り直さず、自然文Creative Director、条件付き画像理解、既存Evaluatorの統合を追加する設計である。

---

## 読む順序

| # | 文書 | 対象リポジトリ | 内容 |
|---|---|---|---|
| 1 | [goal-roadmap.md](goal-roadmap.md) | MediaForge | 全体像。G0〜G10 のゴール機能と進め方の原則 |
| 2 | [mf0-0-environment.md](mf0-0-environment.md) | MediaForge | 実行環境の分離・自動整備・削除安全性。**最初に実施** |
| 3 | [mf0-addon-core.md](mf0-addon-core.md) | MediaForge | G0。Add-on として成立させる（fake worker） |
| 4 | [ux1-workspace.md](ux1-workspace.md) | MediaForge | G0〜G3 の機能を使える形にする workspace UI。設計は `../design-workspace-ux.md` |
| 5 | [ux2-model-scene.md](ux2-model-scene.md) | MediaForge | **UX1を作り直さず**、モデルDL/削除、領域、シーン、ポーズ、構図、意図的な差分生成、Composerを追加。設計は `../design-model-scene-ux.md` |
| 6 | [creative-intelligence.md](creative-intelligence.md) | MediaForge | **UX2 C0〜C5を再利用**して、Creative Director / Reference Intelligence / Unified Evaluator を追加。設計は `../design-creative-intelligence.md` |
| 7 | [g5-m5-companion.md](g5-m5-companion.md) | MediaForge | G5。shared-canvas profile、deterministic validator、atlas/manifest pack |
| 8 | [g6-workspace-turn-and-catalog.md](g6-workspace-turn-and-catalog.md) | MediaForge (+ControlDeck 1 スライス) | G6。永続化の前方互換、workspace session、AI/画像の resource turn 分割、到達性、domain routing、custom HF model |
| — | [host-load-profile-fix.md](host-load-profile-fix.md) | **ControlDeck** | ホスト側の LLM 退避コスト計測の修正。G7 の前提 |

`host-load-profile-fix.md` だけ作業対象が ControlDeck リポジトリ。
Creative Intelligence は ControlDeck の generic `ai.inference` を利用するが、Media固有の provider/model route は追加しない。
Media Forge G7（動画）で LLM 退避が実際に必要になるため、依存関係の記録として `host-load-profile-fix.md` をここに置く。

---

## ゴール一覧

```text
G0   Add-onとして成立する          mf0-addon-core.md
G1   ローカルで画像が作れる
G2   画像を壊さずに直せる
G3   同じキャラ・同じ絵柄で作れる
UX2  既存UXのままモデル管理・シーン/ポーズ/構図を使いこなせる  ux2-model-scene.md
CI   自然文Director・参照理解・評価を既存UXへ統合               creative-intelligence.md
G4   コーディングエージェントが素材を置ける
G5   M5Stack companion が実運用できる
G6   2Dゲーム素材一式が出せる
G7   動かせる（動画・アニメーション）    ← host-load-profile-fix.md が前提
G8   3D素材がプロジェクトに載る
G9   3Dを生成できる（実験的）
G10  手持ち資料を参照源にできる
```

G0〜G4 で local media service として実用成立する。
UX2 は G1〜G3 の既存能力を利用者が使い分けるための横断スライス。
Creative Intelligence は UX2 の Pose/Scene/Composer/Evaluator を捨てず、自然文のActionStateとControlDeck AI gatewayを上に載せる横断スライス。
G5 以降は用途別の上積みで、順序を入れ替えてよい。

---

## 進行中に必ず守ること

```text
契約凍結        G1 完了時点の public API / schemas / JobRequest を破壊しない
動作確認        lint / build / 単体テストの成功を「動く」と記録しない
                （基準は mf0-0-environment.md §1）
記録            docs/implementation-status.md に実測値と NOT TESTED を書く
環境            ControlDeck の .venv を共有しない。キャッシュのみ共有する
境界            ControlDeck 本体に Media 固有のコードを 1 行も入れない
UX再利用         Create/Library/Activity/Settings と Simple/Advanced を作り直さない
AI境界           Media Forgeは provider/model/port を選ばず、ControlDeck ai.inference を通す
AI役割           text-only Director = text.generate。画像が存在する時だけ vision.analyze
新規画像          prompt-only first image の前に vision.analyze を要求しない
Pose              presetを増殖させず、ActionStateSpecを主経路、presetはfallback/Advanced
モデル削除       Media Forge 管理下の重みだけ削除し、共有HF/ComfyUI/外部モデルを勝手に消さない
```

---

## Codex へ渡すときの注意

指示書は ControlDeck 側のファイルを繰り返し参照する。

```text
ControlDeck/docs/design-addon-platform-v2.md   Add-on contract 2.0
ControlDeck/docs/addon-ux-guidelines.md        状態表現・文言規約
ControlDeck/backend/app/addon_runtime/ai.py    generic ai.inference contract
ControlDeck/backend/app/models_mgmt/ai_gateway.py capability-based target policy
ControlDeck/tools/fake-addon/                  contract 2.0 準拠の動く参照実装
ControlDeck/deck.sh                            venv 管理・キャッシュ配置の作法
```

両リポジトリを並べた親ディレクトリから起動し、
**ControlDeck は読み取り専用の参照**であることを明示すること
（ControlDeck側を変更する専用スライスを除く）。

```text
~/dev/
├── ControlDeck/            参照用（通常は読み取り専用）
└── ControlDeckMediaForge/  実装対象
```
