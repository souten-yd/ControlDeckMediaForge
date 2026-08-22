# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-22
ブランチ    ux1/creative-batches-c3
PR          UX1 #21〜#33 / UX2 M0 #35 / M1 #36 / M2 #37 / C0 #38 / C1 #39 / C2 #40 マージ済み
状態        UX2 C3 実装・実process/browser受け入れ・local full gate済み。PR作成前
基準値      ./mf.sh test = 240 passed
リリース    installed host は v0.2.4（M0 はまだ未収録）
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
| PR-U4 | 状況と結果ステージ | #32 マージ済み |
| — | 実使用で見つかった不具合 6 件 | #28 #29 マージ済み |
| PR-U7 | 実機受け入れ | 一部完了（desktop / mobile を観測） |
| PR-U5 | ライブラリ viewer | #33 マージ済み |
| PR-U6 | 一貫性 UI（G3） | 未着手 |
| PR-U7 | 実機受け入れ | 未着手 |

## 次にやること（1 つだけ）

```text
UX2 PR-C3 のfull gateを通し、commit / push / PR / mergeする。
  ブランチ    ux1/creative-batches-c3
  実装        deterministic child planner、durable parent batch、logical cancel、
              reconnect、partial asset保持、候補strip、Advanced child drilldown
  実測        pose/composition各4差分、全child cancel、partial 1 asset保持、
              reload復元、320px overflow 0、console/page error 0。
  次          merge 後に PR-C4（multi-cut planner + deterministic Composer）
  注意        実モデルは C5 まで保持し、大容量 remove は NOT TESTED のままにする。
              hosted CI は使わずローカル gate を記録する。
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
5. 動画モデル管理の将来互換（利用者指示 2026-08-22）
     M1 installer は image 専用にせず capability-driven のまま維持した。
     M2 では検証済み `media_types`（image / video / audio_video）を分類表示に追加し、
     routing の正は capability のままにする。両者が矛盾した catalog は fail-closed。
     Wan 2.2 TI2V-5B / Animate-14B / LTX 系は G7 の評価候補としてのみ記録し、
     G1〜G4 とモデル採用ゲートを終える前に download/default/worker 実装へ進まない。
     C0 は CameraSpec を共通化し、MotionSpec を後から加法的に載せられる形にする。
```

## リポジトリの状態で注意すること

```text
実ブラウザ試験には別 venv が要る
    playwright は core venv に入れない（AGENTS.md「core を軽く保つ」）。
    実行例: /data1tb/ControlDeck-release-bundle/.venv/bin/python \
              scripts/ux_standalone_e2e.py --media-forge-url http://127.0.0.1:9137 \
              --evidence-dir /tmp/ux1-evidence
    証跡: /data1tb/mediaforge-ux1-evidence/{light,dark}/

UX2 の各ブランチは直前スライスを main へ merge してから切る
    PR-C0 は ux1/creative-spec-c0。C0 と C1 を同一 PR に混ぜない。
```

## 再開コマンド

```bash
cd /data1tb/ControlDeckMediaForge
cat docs/implementation/ux1-handoff.md          # このファイル
git fetch --all --prune && git log --oneline -5
gh pr list --state open
sed -n '/## 9\. PR-C3/,/## 10\. PR-C4/p' docs/implementation/ux2-model-scene.md
./mf.sh test                                     # C1の最終基準値はstatusを確認
```

## 参照

```text
設計の正        docs/design-workspace-ux.md
実装指示        docs/implementation/ux1-workspace.md
UX2 実装指示    docs/implementation/ux2-model-scene.md
運用ルール      docs/implementation/ux1-workspace.md §14
進捗と実測      docs/implementation-status.md（実測値のみ。推測を書かない）
```
