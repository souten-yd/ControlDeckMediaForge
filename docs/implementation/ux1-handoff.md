# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-22
ブランチ    release/v0.2.0
PR          #21〜#26 マージ済み / release 記録は #27
状態        v0.2.0 を公開済み。次は PR-U4（状況と結果ステージ）
基準値      ./mf.sh test = 174 passed
リリース    v0.2.0 / sha256 ec7dd229…f97c6 / 29,121,065 bytes
```

## PR 進捗

| PR | 内容 | 状態 |
|---|---|---|
| — | 設計 + 実装計画 + 運用ルール | #21 マージ済み |
| — | G3 profiles backend | #22 マージ済み |
| PR-U0 | /ws 追加メソッドと保存基盤 | #23 マージ済み（転送量 -85.9%） |
| PR-U1 | シェル刷新（3ナビ・モード・モバイル IA） | #24 マージ済み |
| PR-U2 | 作成体験 | #25 マージ済み |
| PR-U3 | マスクエディタ・外側拡張 | #26 マージ済み |
| PR-U4 | 状況と結果ステージ | 次はここ |
| — | 実使用で見つかった不具合 6 件 | #28 #29 マージ済み |
| PR-U7 | 実機受け入れ | 一部完了（desktop / mobile を観測） |
| PR-U5 | ライブラリと書き出し | 未着手 |
| PR-U6 | 一貫性 UI（G3） | 未着手 |
| PR-U7 | 実機受け入れ | 未着手 |

## 次にやること（1 つだけ）

```text
PR-U4（状況と結果ステージ）を開始する。
  ブランチ    ux1/activity-stage（main から）
  最初の作業  失敗コードごとの「出口」を作る。frontend/app.js の failureText を
              {文言, 操作ラベル, 操作} の表に広げ、状況一覧と作る画面の両方から押せるようにする
  仕様        docs/implementation/ux1-workspace.md §6
  完了の目安  失敗表示に必ず実行可能な出口が 1 つあること、
              中止が 2 秒以内に反映されること、
              workspace 表示中に toast が出ないこと（visibility.changed を購読）

  注意        jobs.watch の push は U1 で入っている。polling へ戻さない。
              待機理由の日本語は host が所有する。MF 側で enum を訳し直さない
              （ControlDeck/docs/addon-ux-guidelines.md）。
```

## リリースの運用

```text
区切りごとに版を出す（利用者の指示 2026-08-22）
  1. ./mf.sh bundle build <version> /data1tb/mediaforge-release-bundles
  2. 展開して bin/mediaforge-core serve を起動し、配信 HTML が新 UI であることを確認
  3. そのバンドルに対して scripts/ux_standalone_e2e.py を回す
  4. gh release create v<version> --title ... で tar.gz と .sha256 を添付
     資産名は control-deck-media-forge-<version>-linux-x86_64.tar.gz(.sha256)
  5. docs/implementation-status.md に artifact / bytes / sha256 / 未確認事項を記録
  6. 配布するには ControlDeck の trusted-catalog.json を更新する別 PR が要る
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
     UI 実装のために必要な host 変更は 1 つも出ていない。
     ただし v0.2.0 を配布するには trusted-catalog.json の pin 更新が要る
     （これは Media 固有のコードではなく、カタログの版指定なので許容範囲）。
4. worker が core を import している（層の違反・未解決）
     worker_packs/image/adapters/diffusers_flux2.py が
     mediaforge.image_edit / mediaforge.outpaint を import している。
     AGENTS.md「worker は core から実装を import しない」に反する。
     v0.2.2 では bundle へ同梱して動作を戻したが、層の整理は未着手。
     image_edit / outpaint は PIL だけに依存するので worker pack 側へ寄せるのが筋。
     ただし strict edit の独立検証は core 側に残すこと（共有すると保証の意味が消える）。
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
