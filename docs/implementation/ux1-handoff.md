# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      ux1/wan21-vace-prompt-lifecycle（origin/main bc30f53 から作成）
slice       G7 V1h Wan 2.1 VACE prompt/model lifecycle follow-up
状態        component直列化でprocess swap 0 / system swap-out 401 pages / DEFERRED維持
baseline    focused 32 passed / full 711 passed / compileall・diff check PASS
installed   v0.9.0復元 / 127.0.0.1:9130 / healthy / contract 2.0
GPU         VACE worker 0 / KFD process 0 / R9700 baseline 59,912,192 B
PR          Media Forge #127 merged / V1h PR未作成
```

G7 V1c は Media Forge #122、merge commit
`41eee86efc97db285c6717c3f482834604442816` で main へ入った。Hunyuan weight は取得していない。
G7 V1d は Media Forge #123、merge commit
`cfb6c74890e5c00257898e7a3169d9cb26826b65` で main へ入った。
G7 V1e は Media Forge #124、merge commit
`af15cd2eced1b3046b588eb9b663aaad4f106631` で main へ入った。
G7 V1f は Media Forge #125、merge commit
`245a5e2b8a17a4cac196db67cf70945083136624` で main へ入った。
G7 V1g は Media Forge #126、merge commit
`1bbfbd43d784a2d03a34eafdc9a189d1c28a5e6b` で main へ入った。

## この slice の結果

```text
PASS       prompt embedsをGPU生成後にUMT5/tokenizerを破棄
PASS       VAE/scheduler/tokenizer/text encoder/transformerのcomponent直列ロード
PASS       best smoke 110.622s / peak RSS 10,251,010,048 B / process swap 0
PASS       同一H.264 SHA-256 / determinism / Broker grant・renew・release
PASS       V1g比 latency約53%減 / peak RSS約51%減 / process swap 100%減
PASS       focused 32 tests / full 711 tests / compileall / diff check
FAIL       best smoke system swap in 70 / out 401 pages
NOT TESTED candidate quality / cancel / public Asset/provenance
DEFERRED   VACE production adoption / candidate profile / G7 V2 promotion
```

通常の video capability/routing state は変更していない。両 candidate は catalog で external /
`experimental` / `measurement_confidence=low` / recommended profile 0 のまま。

## 次にやること（1つだけ）

```text
1. V1h PRをexact headでmergeし、handoffをmerged stateへ更新する
2. VACEはsystem swap 0を実測できる追加改善までcandidate profileへ進めない
3. LTX/Hunyuan/SkyReels weightは明示license acceptanceなしに取得しない
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの一般的な継続指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeck slice code/DB/manifest変更0。既存`frontend/tsconfig.tsbuildinfo`変更1件は保全。Hostはread-only。
installed v0.9.0は復元済み。127.0.0.1:9130でhealthy / contract 2.0。
Cog runtime/snapshot/evidenceは `/data1tb/mediaforge-g7-cogvideox2b` に外部保持。
Hunyuan weight/snapshot/partial download は0。dedicated runtimeだけ外部構築済み。
Wan runtime/model は移動・削除しない。
Wan VACE downloadは `/data1tb/mediaforge-g7-wan21-vace/hf` に外部保持し、partialを消さない。
Wan T2V 1.3B weights/partial snapshotは0。runtimeはrepo内ignored `.venv`へ構築済み。
SonicForge は `sonicforge-acceptance.service` でactive。Qwen3.8-27B llama.cppは実利用を優先して
停止せず、ControlDeck idle policyにより12:53:19に自然解放された。競合時は Broker を唯一の調停
経路にする。
```

## 参照

```text
設計正          docs/base-plan.md / docs/controldeck-integration-plan.md
全体 roadmap    docs/implementation/goal-roadmap.md
G7 実装指示     docs/implementation/g7-video-runtime.md
実測            docs/implementation-status.md
model catalog   docs/models.md / worker_packs/image/models.json
```
