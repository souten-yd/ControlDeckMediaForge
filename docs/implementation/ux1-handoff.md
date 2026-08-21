# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-22
ブランチ    ux1/design-and-workflow
PR          #21（作成済み・未マージ）
状態        設計と実装計画のみ完了。コードは 1 行も書いていない
```

## PR 進捗

| PR | 内容 | 状態 |
|---|---|---|
| — | 設計 + 実装計画 + 運用ルール | PR 作成済 |
| PR-U0 | /ws 追加メソッドと保存基盤 | 未着手 |
| PR-U1 | シェル刷新（3ナビ・モード・モバイル IA） | 未着手 |
| PR-U2 | 作成体験 | 未着手 |
| PR-U3 | マスクエディタ・外側拡張 | 未着手 |
| PR-U4 | 状況と結果ステージ | 未着手 |
| PR-U5 | ライブラリと書き出し | 未着手 |
| PR-U6 | 一貫性 UI（G3） | 未着手 |
| PR-U7 | 実機受け入れ | 未着手 |

## 次にやること（1 つだけ）

```text
PR-U0 を開始する。
  ブランチ    ux1/transport-foundation
  最初の作業  backend/mediaforge/thumbnails.py を新規作成し、
              Pillow で 256px / 64KiB 上限のサムネイルを生成する関数を書く
  仕様        docs/implementation/ux1-workspace.md §2.3
  完了の目安  tests/test_workspace_transport.py のサムネイル 3 ケースが通る
```

## 未解決の判断

```text
1. subresource 直接取得の可否（設計 §10.1 / 実装 §2.6）
     未実測。PR-U0 で 1 度だけ測る。測る前に前提にした実装を書かない。
2. addon.json の mobile: "companion" → "embedded"
     PR-U1（モバイル IA 実装）と同じ PR でのみ変更する。先行して変えない。
3. ControlDeck 側の変更
     利用者が許可済み（2026-08-22）。ただし汎用 host 機能に限る（§0 B1）。
     現時点で必要な host 変更は 1 つも特定されていない。
```

## リポジトリの状態で注意すること

```text
g3/profiles ブランチに利用者の未 commit 作業がある
    backend/mediaforge/{app,jobs,semantic_review,store}.py
    backend/mediaforge/profiles.py（新規）
    schemas/{profile,reference-collection}.json（新規）
    tests/test_profiles.py（新規）
    worker_packs/image/**
  → UX1 の作業でこれらを commit しない。触らない。
  → G3 backend が main へマージされるまで、PR-U6（一貫性 UI）は着手しない。
```

## 再開コマンド

```bash
cd /data1tb/ControlDeckMediaForge
cat docs/implementation/ux1-handoff.md          # このファイル
git fetch --all --prune && git log --oneline -5
gh pr list --state open
sed -n '/## 2\. PR-U0/,/## 3\. PR-U1/p' docs/implementation/ux1-workspace.md   # 次の仕様
./mf.sh test                                     # 現在の基準値を確認
```

## 参照

```text
設計の正        docs/design-workspace-ux.md
実装指示        docs/implementation/ux1-workspace.md
運用ルール      docs/implementation/ux1-workspace.md §14
進捗と実測      docs/implementation-status.md（実測値のみ。推測を書かない）
```
