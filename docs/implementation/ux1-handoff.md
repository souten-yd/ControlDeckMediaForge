# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-24
ブランチ    g6/workspace-turn-and-catalog
PR          MediaForge #72(G5) / #73(G6)、ControlDeck #238。いずれも作成済み
状態        G6 実装完了。installed v0.6.0 導入済み。残りは resource turn の実機通し 1 件
基準値      full = 412 passed（38.76 秒、warning 1）
リリース    v0.6.0 をローカルビルドして installed 差し替え済み
            artifact 30,640,703 bytes
            sha256 ef57f26f78bb5816f967c9256dfce07ae9a135d64602f4137f09004b9bfed73d
            GitHub Release と trusted-catalog の更新はまだ行っていない
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
| PR-U6 | 一貫性 UI（G3） | #73 で実装（キャラ・画風の作成/削除） |
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
| — | worker/core image composition boundary | #70 マージ済み（2b3114d） |
| — | v0.5.1 release/install evidence | #71 マージ済み（9482e38） |
| — | G5 M5 companion pack | #72 作成済み（実機 E2E 未実施） |
| — | G6 workspace turn / resource turn / catalog | #73 作成済み |
| — | ControlDeck 汎用 ai/release contract | ControlDeck #238 作成済み |

## 次にやること（1 つだけ）

```text
残っているのは resource turn の実機通し 1 件だけ。ログインが要るので利用者が実行する。

  MEDIA_FORGE_E2E_PASSWORD=... \
    /data1tb/ControlDeck-release-bundle/.venv/bin/python \
    scripts/g6_resource_turn_e2e.py \
      --control-deck-url http://127.0.0.1:8765 \
      --username <name> \
      --evidence-dir /data1tb/mediaforge-g6-evidence

  検証すること
    boot が workspace.session 1 往復で終わる
    状況タブが記録を読める
    Host LLM を gateway 経由で常駐させ実際に VRAM を握らせる
    phase 列に release_ai が現れ generating より前にある
    VRAM が生成前に返る / 実画像が 1 枚できる
    Broker が空で残り worker プロセスが残らない

  完了        G6 S1〜S6 実装 + 412 passed + installed v0.6.0
  完了        ❸ installed で解消（GET /api/v1/jobs 500 -> 200 / 90 件）
  完了        ❶❹ boot 2.609 -> 0.264 秒 / 要求 104 -> 14 件（実データ実測）
  完了        ❷ VRAM 実測。LLM 常駐 +31,495,229,440 / 解放 0.356 秒 / 全量返却
  完了        ❽ OpenCode 活動中でも解放が成立するよう修正し実測
  完了        ❺ 到達できなかった機能に入口を追加（実ブラウザで往復確認）
  完了        ❻ custom HF model（実 HF で解決 -> 承諾 -> 追加 -> 削除まで実測）
  完了        ❼ domain 対応 routing と 2 段のモデル選択 + 選択根拠の表示
  未実施      上記の resource turn 通し
  未実施      G5 の実機 installed E2E（scripts/g5_m5_e2e.py）
  保留        SD/SDXL/SD3 共通 adapter。実測していない adapter を available にしない
  注意        保持済み FLUX model と C5 実画像を削除しない。hosted CI は使わない
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
     2026-08-24 に 1 件だけ必要になった（ControlDeck #238）。
     LLM プロセスの寿命は ControlDeck が所有し add-on には HTTP 契約しか無いため、
     「AI ターン終了」を伝える口が公開契約に存在しなかった。足したのは
     `POST /{addon_id}/ai/release` という汎用宣言 1 個と、`/ai/complete` への
     `ensure_ready` 追加だけで、media 固有の語彙は入れていない。
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
