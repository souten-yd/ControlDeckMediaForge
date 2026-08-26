# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      ux1/wan21-vace-evaluation（origin/main 245a5e2 から作成）
slice       G7 V1g Wan 2.1 VACE 1.3B I2V evaluation
状態        exact snapshot/hashと初回Broker smoke完了、128-token最適化後smoke待ち
baseline    focused 32 passed / 1 warning、full 711 passed / 2 warnings / 49.27s
installed   一時停止中 / branch coreが127.0.0.1:9130でhealthy / contract 2.0
GPU         Qwen3.8-27Bを優先してresident保持中 / VACE worker 0
PR          Media Forge #125 merged / V1g PR未作成
```

G7 V1c は Media Forge #122、merge commit
`41eee86efc97db285c6717c3f482834604442816` で main へ入った。Hunyuan weight は取得していない。
G7 V1d は Media Forge #123、merge commit
`cfb6c74890e5c00257898e7a3169d9cb26826b65` で main へ入った。
G7 V1e は Media Forge #124、merge commit
`af15cd2eced1b3046b588eb9b663aaad4f106631` で main へ入った。
G7 V1f は Media Forge #125、merge commit
`245a5e2b8a17a4cac196db67cf70945083136624` で main へ入った。

## この slice の結果

```text
PASS       exact snapshot 27 files / 19,043,130,596 B / 8 LFS size+SHA-256
PASS       exact revision / local-only snapshot containment / offline runner boundary
PASS       fixed first-frame+mask conditioning / smoke/candidate/official presets
PASS       BF16 transformer + FP32 VAE / model CPU offload / VAE slicing+tiling
PASS       optional settings / complete-snapshot-only visibility / Broker envelope
PASS       real Host Job/Broker grant/activate/renew/release / H.264 artifact
PASS       R9700 smoke 256x256 / 5 frames / 1 step / process swap 0
PASS       LLM resident時のinsufficient_capacity / worker未起動 / direct競合なし
FAIL       smoke 260.206s / system swap in 2,890・out 24,510 pages
PASS       focused 32 tests / full 711 tests / diff check
NOT TESTED 128-token最適化後smoke / candidate quality / cancel / determinism
DEFERRED   production adoption / G7 V2 promotion
```

通常の video capability/routing state は変更していない。両 candidate は catalog で external /
`experimental` / `measurement_confidence=low` / recommended profile 0 のまま。

## 次にやること（1つだけ）

```text
1. 実LLMを止めずidle policyの自然解放を待ち、128-token smokeを再測定する
2. latency/system swap gateを満たした場合だけBroker経由candidate I2Vを実測する
3. adoption gate判定・docs/full test・PR merge後だけT2V 1.3Bへ進む
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの一般的な継続指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeck slice code/DB/manifest変更0。既存`frontend/tsconfig.tsbuildinfo`変更1件は保全。Hostはread-only。
installed v0.9.0 service は一時停止中。評価用branch coreは127.0.0.1:9130で起動中。
Cog runtime/snapshot/evidenceは `/data1tb/mediaforge-g7-cogvideox2b` に外部保持。
Hunyuan weight/snapshot/partial download は0。dedicated runtimeだけ外部構築済み。
Wan runtime/model は移動・削除しない。
Wan VACE downloadは `/data1tb/mediaforge-g7-wan21-vace/hf` に外部保持し、partialを消さない。
Wan T2V 1.3B weights/partial snapshotは0。runtimeはrepo内ignored `.venv`へ構築済み。
SonicForge は `sonicforge-acceptance.service` でactive。Qwen3.8-27B llama.cppも実利用後のresidencyを
保持中。どちらもMedia Forgeから停止せず、競合時は Broker を唯一の調停経路にする。
```

## 参照

```text
設計正          docs/base-plan.md / docs/controldeck-integration-plan.md
全体 roadmap    docs/implementation/goal-roadmap.md
G7 実装指示     docs/implementation/g7-video-runtime.md
実測            docs/implementation-status.md
model catalog   docs/models.md / worker_packs/image/models.json
```
