# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-22
ブランチ    ux1/create-experience
PR          #21 #22 #23 #24 マージ済み / PR-U2 は #25
状態        作成体験まで完了。受付前検証を実ブラウザで観測済み
基準値      ./mf.sh test = 172 passed
```

## PR 進捗

| PR | 内容 | 状態 |
|---|---|---|
| — | 設計 + 実装計画 + 運用ルール | #21 マージ済み |
| — | G3 profiles backend | #22 マージ済み |
| PR-U0 | /ws 追加メソッドと保存基盤 | #23 マージ済み（転送量 -85.9%） |
| PR-U1 | シェル刷新（3ナビ・モード・モバイル IA） | #24 マージ済み |
| PR-U2 | 作成体験 | PR #25 |
| PR-U3 | マスクエディタ・外側拡張 | 次はここ |
| PR-U4 | 状況と結果ステージ | 未着手 |
| PR-U5 | ライブラリと書き出し | 未着手 |
| PR-U6 | 一貫性 UI（G3） | 未着手 |
| PR-U7 | 実機受け入れ | 未着手 |

## 次にやること（1 つだけ）

```text
PR-U3（マスクエディタと外側拡張）を開始する。
  ブランチ    ux1/mask-editor（main から。#25 マージ後に切る）
  最初の作業  frontend に canvas のマスク描画を作る。元画像と同寸法の PNG を出力し、
              白=変更可 / 黒=保護へ変換して既存の import 経路（purpose=edit_mask）へ流す
  仕様        docs/implementation/ux1-workspace.md §5
  完了の目安  外部ツール無しで inpaint が完了すること、
              空マスク・全面マスクを送信前に止めること、
              タッチ（1 本指で描画・2 本指でパン/ズーム）で操作できること

  注意        マスクのファイル指定は詳細モードに残す（既存経路を消さない）。
              添付時の寸法計測（state.source）は U2 で入っているので再実装しない。
              outpaint の方向ハンドルも同じ PR。数値入力は詳細モードのみに残す。
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
実ブラウザ試験には別 venv が要る
    playwright は core venv に入れない（AGENTS.md「core を軽く保つ」）。
    実行例: /data1tb/ControlDeck-release-bundle/.venv/bin/python \
              scripts/ux_standalone_e2e.py --media-forge-url http://127.0.0.1:9137 \
              --evidence-dir /tmp/ux1-evidence
    証跡: /data1tb/mediaforge-ux1-evidence/{light,dark}/

main はクリーン。以降の UX1 ブランチは main から切る
    #21 #22 #23 はすべてマージ済み。積み重ねは解消した。
    PR-U6（一貫性 UI）の前提だった G3 backend も main に入っている。

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
