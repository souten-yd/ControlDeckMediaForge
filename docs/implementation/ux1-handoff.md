# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-23
ブランチ    infra/worker-core-boundary
PR          #63〜#69 merge済み。worker境界 PR作成前
状態        G0〜G4 / CI-1〜CI-6完了。worker境界解消・実機受入済み。次はG5
基準値      worker focused = 48 passed。full = 352 passed（37.33秒、warning 1）
リリース    v0.5.0公開・ControlDeck導入済み（artifact 9e24c3bf...fa0be、Host PR #236）
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
| — | H3 bounded evaluator hardening | #60 マージ済み（676f8cc） |
| — | v0.3.2 release/install evidence | #61 マージ済み（4c310cb） |
| — | H3 version-pinned prompt recipe | #63 マージ済み（6730bb7） |
| — | CI-4 Unified Evaluator | #64 マージ済み（3a2d6eb） |
| — | G4 prerequisite design correction | #65 マージ済み（43aa08c） |
| — | G4 coding-agent asset placement | #66 マージ済み（5a340ac） |
| — | v0.4.0 release/install evidence | #67 マージ済み（f30c1de） |
| — | CI-5 C4 shot direction | #68 マージ済み（8e82287） |
| — | v0.5.0 + CI-6 installed/R9700 evidence | #69 マージ済み（2f8e917） |
| — | worker/core image composition boundary | PR作成前（実装・実機受入済み） |

## 次にやること（1 つだけ）

```text
G4、CI-1〜CI-6、v0.5.0、worker境界解消は完了。次はG5 M5 companion profile/validator/pack。
  完了        26.98GB GGUF、pinned HIP runtime、Host lease/cancel、R9700 smoke実測
  延期        H3 quality route（Host watchdog/swap/output gate失敗。条件改善まで再実行しない）
  完了        版固定recipe、構造化projection、実Gateway text.generate、原文保持/fail-closed
  完了        CI-4 canonical EvaluationResult、advisory rank、bounded retry、旧binary reviewer削除
  完了        ControlDeck汎用 current-project output grant（PR #232）/ long MCP timeout（PR #233）
  完了        media.pack / atomic asset placement / OpenCode inspect・参照更新・build・test実機E2E
  完了        v0.4.0 exact-head bundle、extracted light/dark、installed Host light/dark、Broker cleanup
  完了        CI-5 one text.generate / 2〜4 shot brief / existing child Job + C4 Composer再利用
  実測        installed Host fake 3-shot構造受入。64.452秒、vision 0、lease最終0、320px overflow 0
  注意        fakeの1秒estimateはBroker thrash-cost未満。operator stopを使用。自動handoffはCI-6で実画像実測
  完了        v0.5.0 exact-head bundle、extracted light/dark、installed update、Host catalog PR #236
  完了        CI-6 real Director/original/C3/evaluator/reference/fail-soft、320/390px、Broker cleanup
  実測        FLUX 4 assets + fail-soft 1 asset。Director 15.218秒、C3 x2 37.504秒、GPU最大98%
  完了        workerのcore import/PYTHONPATH/source同梱を除去。core validatorは独立維持
  実測        strict 20.106秒 / protected差分0、outpaint 107.367秒 / source差分0
  次          G5 M5 companion profiles + deterministic validator + atlas/manifest pack
  保留        video public API/runtime実装（G5/G6の安定用途を先に完了する）
  注意        保持済みFLUX modelとC5実画像を削除しない。hosted CIは使わない。
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
4. worker/core image composition boundary（2026-08-23 解決）
     worker側のPIL compositionをworker_packsへ移し、core implementation import、
     backend PYTHONPATH、bundleのcore source同梱を除去した。coreのstrict/outpaint
     validatorは別実装のままworker出力を自己検証せずに検査する。
5. 動画モデル管理の将来互換（利用者指示 2026-08-22）
     M1 installer は image 専用にせず capability-driven のまま維持した。
     M2 では検証済み `media_types`（image / video / audio_video）を分類表示に追加し、
     routing の正は capability のままにする。両者が矛盾した catalog は fail-closed。
     Wan 2.2 TI2V-5B / Animate-14B / LTX 系は G7 の評価候補としてのみ記録する。
     利用者がM0〜M2を先行指定し、候補の実download確認も明示したため、boundedなmanaged
     snapshot取得までは先行する。R9700 worker実行、available/default昇格、G7 APIには進まない。
     C0 は CameraSpec を共通化し、MotionSpec を後から加法的に載せられる形にする。
6. 次回release時のControlDeck trusted catalog
     `ai.inference`は汎用allowlistへ追加済み。v0.3.2はPR #230でartifact SHAのみ更新し、
     PR #231で実update証跡を記録した。次版も同じくgeneric catalog dataだけを更新し、
     Media固有code、route、依存を追加しない。
7. MiniMax H3（利用者指示 2026-08-22）
     公式BF16 FL2VA 144.05GBは上限超過。1.865GBでcancelしpartial削除済み。
     第1候補をunsloth FL2VA UD-Q2 GGUF composite 26.98GBへ変更した。
     operation `modelop_0dfc422e9d9d480a996e02ba552d6b89` は49分00秒でready。
     独立SHAは4ファイル全一致（17.49秒）、snapshot 26,978,361,344 bytes、
     pinned stable-diffusion.cpp `97d2990`をROCm 7.2.1/gfx1201でbuild済み（539.64秒）。
     `sd-cli --list-devices`はR9700をROCm0/32,624MiBとして列挙（0.06秒）。
     lease acquire/renew/cancel/releaseを備えたprivate evaluatorを現在branchで実装した。
     実NVMe上のmodel/runtime preflightと5-frame/1-step smokeは成功。
     smokeは160.86秒、peak RSS 26.35GB、VRAM delta 14.55GB、process swap 0。
     出力frameは破綻しておりquality証拠ではない。
     25-frame/4-step probeはRAM/swap圧でHost watchdogが再起動し、outputなし。
     H3はexperimental/healthy=no/unroutableを維持する。
     token偽造やlease流用はしない。実測後も`experimental / healthy=no`を維持する。
     公式prompt-writing skillはMarkdownと参照guideだけで外部APIを呼ばない。版固定recipeを
     Media Forgeのprivate projectionとして実装済み。任意skill実行経路はなく、Hostへは
     構造化messageを`text.generate`として渡す。prompt-onlyではvisionを要求しない。
     32GB VRAM超のworking memoryをbounded RAM offloadで試すことは
     許容するが、wall time/RAM headroom/swap/Host watchdog/output qualityを全て実測する。
     今回のH3 quality routeはこのgateに失敗したため採用しない。
```

## リポジトリの状態で注意すること

```text
実ブラウザ試験には別 venv が要る
    playwright は core venv に入れない（AGENTS.md「core を軽く保つ」）。
    実行例: /data1tb/ControlDeck-release-bundle/.venv/bin/python \
              scripts/ux_standalone_e2e.py --media-forge-url http://127.0.0.1:9137 \
              --evidence-dir /tmp/ux1-evidence
    証跡: /data1tb/mediaforge-ux1-evidence/{light,dark}/

機能スライスは直前PRをmainへmergeしてから切る。
Creative Intelligenceは docs/implementation/creative-intelligence.md の CI-1〜CI-6 を順に進める。
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
