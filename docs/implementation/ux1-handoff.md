# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-22
基準main    8f61d054d09735381a6c5224546b01c64fb1da26
作業        Creative Intelligence v2 計画統廃合（docs/creative-intelligence-unified-v2）
PR          v0.3.0 #48 / Creative Intelligence A0 #46 / protected-field fix #49 マージ済み
状態        UX2 M0〜C5は完了。A0基盤を残し、旧A1〜A7をCI-1〜CI-6へ統廃合中
基準値      ./mf.sh test = 269 passed（24.58秒、#49）
リリース    v0.3.0公開済み（artifact d8055331...aa48f）。installed host は v0.2.4
別作業      PR #50 video candidate catalog は open。Creative Intelligence と混ぜない
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
| UX2 M0〜C5 | model management / creative compiler / references / batches / Composer / evaluator | #35〜#43 マージ済み |
| Release | v0.3.0 creative workflow | #48 マージ済み |
| Creative Intelligence A0 | provider-neutral Host AI seam + typed planning models | #46 マージ済み |
| A0 fix | server-owned PromptPlan fields保護 | #49 マージ済み |
| Creative Intelligence v2 | Director / conditional vision / unified evaluator 計画 | 本docs PR |

## 次にやること（1 つだけ）

```text
Creative Intelligence v2 docsをmerge後、CI-1 provider-neutral AI cutoverへ進む。
  最優先      addon.jsonにai.inference grantを追加
  移行        semantic_review.py / evaluator.py のOllama直結をHostAIGateway vision.analyzeへ交換
  削除        config.py のprovider URL/model決め打ち
  維持        prompt-only生成、deterministic QA、C5 ranking、既存retry budget
  次          CI-2 Creative Director。新規text-only生成ではtext.generateを使い、pre-generation vision=0
  注意        PR #50 video catalogと混ぜない。保持済みFLUX modelとC5実画像を削除しない。hosted CIは使わない。
```

## Creative Intelligence v2 の要点

```text
新規画像（参照なし）
  intent -> text.generate Creative Director -> ActionState/Scene/Composition/Camera
         -> existing CreativeCompiler -> image Job
         -> vision.analyzeは生成後の任意評価だけ

参照画像あり
  reference -> deterministic VisualFacts + cached vision.analyze
  intent + accepted analysis -> text.generate Director -> generation

Pose preset
  削除しない。Advanced/shortcut/fallbackへ降格。
  主経路はActionStateSpec、既存compilerへはcustom pose detailsとして互換投影。

Evaluator
  C5 six-axis evaluatorとbinary semantic reviewを最終的に1本化。
  deterministic validationが常に優先、semantic retryは既存budget内だけ。
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
     Creative IntelligenceではControlDeck #224のgeneric ai.inferenceを使用する。
     Media固有provider/model routeは追加しない。
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
     PR #50はvideo候補catalogの別作業。Creative Intelligence planへ混ぜない。
     Directorは将来MotionSpecをtext.generateで作れる形にし、visionはstart/reference frameがある時だけ使う。
```

## リポジトリの状態で注意すること

```text
実ブラウザ試験には別 venv が要る
    playwright は core venv に入れない（AGENTS.md「core を軽く保つ」）。
    実行例: /data1tb/ControlDeck-release-bundle/.venv/bin/python \
              scripts/ux_standalone_e2e.py --media-forge-url http://127.0.0.1:9137 \
              --evidence-dir /tmp/ux1-evidence
    証跡: /data1tb/mediaforge-ux1-evidence/{light,dark}/

機能スライスは直前スライスをmainへmergeしてから切る。
Creative Intelligenceは docs/implementation/creative-intelligence.md の CI-1〜CI-6 を順に進める。
```

## 再開コマンド

```bash
cd /data1tb/ControlDeckMediaForge
cat docs/implementation/ux1-handoff.md
git fetch --all --prune && git log --oneline -8
gh pr list --state open
cat docs/design-creative-intelligence.md
cat docs/implementation/creative-intelligence.md
./mf.sh test
```

## 参照

```text
設計の正             docs/design-workspace-ux.md
UX2拡張設計           docs/design-model-scene-ux.md
Creative Intelligence docs/design-creative-intelligence.md
実装指示              docs/implementation/ux1-workspace.md
UX2実装指示            docs/implementation/ux2-model-scene.md
CI実装指示             docs/implementation/creative-intelligence.md
運用ルール             docs/implementation/ux1-workspace.md §14
進捗と実測             docs/implementation-status.md（実測値のみ。推測を書かない）
```
