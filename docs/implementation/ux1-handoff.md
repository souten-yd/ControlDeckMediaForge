# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-22
ブランチ    ux1/transport-foundation（g3/profiles + ux1/design-and-workflow の上）
PR          #21 設計 / #22 G3 profiles / #23 PR-U0（いずれも未マージ）
状態        PR-U0 実装済み・実測済み。UI はまだ 1 行も書いていない
```

## PR 進捗

| PR | 内容 | 状態 |
|---|---|---|
| — | 設計 + 実装計画 + 運用ルール | PR #21 |
| PR-U0 | /ws 追加メソッドと保存基盤 | PR #23（転送量 -85.9% 実測済み） |
| PR-U1 | シェル刷新（3ナビ・モード・モバイル IA） | 次はここ |
| PR-U2 | 作成体験 | 未着手 |
| PR-U3 | マスクエディタ・外側拡張 | 未着手 |
| PR-U4 | 状況と結果ステージ | 未着手 |
| PR-U5 | ライブラリと書き出し | 未着手 |
| PR-U6 | 一貫性 UI（G3） | 未着手 |
| PR-U7 | 実機受け入れ | 未着手 |

## 次にやること（1 つだけ）

```text
PR-U1（シェル刷新）を開始する。
  ブランチ    ux1/workspace-shell（#22 の上に積む）
  最初の作業  frontend/index.html を 3 ナビ + ヘッダのモードトグル + モバイル下部タブ
              の構造へ書き直す。DOM 契約の id は §3 の表どおりに付ける
  仕様        docs/implementation/ux1-workspace.md §3
  完了の目安  tests/test_frontend_contract.py（新規）が通り、
              standalone の Playwright で 320px / 390×844 / 1280×800 が崩れない

  注意        addon.json の mobile: "embedded" 変更はこの PR で同時に行う。
              モバイル IA が動く状態になるまで宣言を変えない。
              preferences.get/set は PR-U0 で入っているので、モード保存はそれを使う。
```

## 未解決の判断

```text
1. subresource 直接取得の可否（設計 §10.1 / 実装 §2.6）
     未実測のまま。installed host とログイン資格情報が要るため PR-U0 では行えなかった。
     PR-U5 の着手前までに 1 度だけ測る。サムネイルは結論に依存しないので U1〜U4 は先行可。
2. addon.json の mobile: "companion" → "embedded"
     PR-U1（モバイル IA 実装）と同じ PR でのみ変更する。先行して変えない。
3. ControlDeck 側の変更
     利用者が許可済み（2026-08-22）。ただし汎用 host 機能に限る（§0 B1）。
     現時点で必要な host 変更は 1 つも特定されていない。
```

## リポジトリの状態で注意すること

```text
PR が 3 本積み重なっている（いずれも未マージ）
    main
     ├─ #21 ux1/design-and-workflow   設計・実装計画・運用
     └─ #22 g3/profiles               G3 backend（旧・未 commit 作業を独立させたもの）
          └─ #23 ux1/transport-foundation  PR-U0（#21 を merge 済み）
  → #23 は #22 と #21 の両方を含む。マージ順は #21 → #22 → #23。
  → 以降の UX1 ブランチは ux1/transport-foundation から切る。
  → PR-U6（一貫性 UI）は #22 がマージされてから着手する。

docs/README-updated.md / docs/README-updated 2.md は untracked のまま
    UX1 とは無関係の残置ファイル。触らない。
```

## 再開コマンド

```bash
cd /data1tb/ControlDeckMediaForge
cat docs/implementation/ux1-handoff.md          # このファイル
git fetch --all --prune && git log --oneline -5
gh pr list --state open
sed -n '/## 3\. PR-U1/,/## 4\. PR-U2/p' docs/implementation/ux1-workspace.md   # 次の仕様
./mf.sh test                                     # 基準値: 155 passed
```

## 参照

```text
設計の正        docs/design-workspace-ux.md
実装指示        docs/implementation/ux1-workspace.md
運用ルール      docs/implementation/ux1-workspace.md §14
進捗と実測      docs/implementation-status.md（実測値のみ。推測を書かない）
```
