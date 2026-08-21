# Media Forge 実装指示

実装エージェント（Codex 等）へ渡す指示書。設計文書とは役割が違う。

```text
docs/base-plan.md                    設計の正（何を作るか・なぜそう決めたか）
docs/controldeck-integration-plan.md 統合の正（ホストとの境界）
docs/design-workspace-ux.md          UI/UX の正（画面構成・段階開示・レイアウト）
docs/implementation/                 実装の指示（どの順で・何を確認して進めるか）
```

設計判断を変えるときは `base-plan.md` / `controldeck-integration-plan.md` を先に更新する。
指示書だけを書き換えて設計を変えないこと。

---

## 読む順序

| # | 文書 | 対象リポジトリ | 内容 |
|---|---|---|---|
| 1 | [goal-roadmap.md](goal-roadmap.md) | MediaForge | 全体像。G0〜G10 のゴール機能と進め方の原則 |
| 2 | [mf0-0-environment.md](mf0-0-environment.md) | MediaForge | 実行環境の分離・自動整備・削除安全性。**最初に実施** |
| 3 | [mf0-addon-core.md](mf0-addon-core.md) | MediaForge | G0。Add-on として成立させる（fake worker） |
| 4 | [ux1-workspace.md](ux1-workspace.md) | MediaForge | G0〜G3 の機能を使える形にする workspace UI。設計は `../design-workspace-ux.md` |
| — | [host-load-profile-fix.md](host-load-profile-fix.md) | **ControlDeck** | ホスト側の LLM 退避コスト計測の修正。G7 の前提 |

`host-load-profile-fix.md` だけ作業対象が ControlDeck リポジトリ。
Media Forge G7（動画）で LLM 退避が実際に必要になるため、依存関係の記録としてここに置く。

---

## ゴール一覧

```text
G0   Add-onとして成立する          mf0-addon-core.md
G1   ローカルで画像が作れる
G2   画像を壊さずに直せる
G3   同じキャラ・同じ絵柄で作れる
G4   コーディングエージェントが素材を置ける
G5   M5Stack companion が実運用できる
G6   2Dゲーム素材一式が出せる
G7   動かせる（動画・アニメーション）    ← host-load-profile-fix.md が前提
G8   3D素材がプロジェクトに載る
G9   3Dを生成できる（実験的）
G10  手持ち資料を参照源にできる
```

G0〜G4 で local media service として実用成立する。
G5 以降は用途別の上積みで、順序を入れ替えてよい。
**G7 以降を先に着手しない**（理由は goal-roadmap.md §0.4）。

---

## 進行中に必ず守ること

```text
契約凍結        G1 完了時点で public API / schemas / addon.json を凍結する
動作確認        lint / build / 単体テストの成功を「動く」と記録しない
                （基準は mf0-0-environment.md §1）
記録            docs/implementation-status.md に実測値と NOT TESTED を書く
環境            ControlDeck の .venv を共有しない。キャッシュのみ共有する
境界            ControlDeck 本体に Media 固有のコードを 1 行も入れない
```

---

## Codex へ渡すときの注意

指示書は ControlDeck 側のファイルを繰り返し参照する。

```text
ControlDeck/docs/design-addon-platform-v2.md   Add-on contract 2.0
ControlDeck/docs/addon-ux-guidelines.md        状態表現・文言規約
ControlDeck/tools/fake-addon/                  contract 2.0 準拠の動く参照実装
ControlDeck/deck.sh                            venv 管理・キャッシュ配置の作法
```

両リポジトリを並べた親ディレクトリから起動し、
**ControlDeck は読み取り専用の参照**であることを明示すること
（`host-load-profile-fix.md` の作業時を除く）。

```text
~/dev/
├── ControlDeck/            参照用（読み取り専用）
└── ControlDeckMediaForge/  実装対象
```
