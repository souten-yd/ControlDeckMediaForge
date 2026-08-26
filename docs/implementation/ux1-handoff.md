# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      ux1/cogvideox2b-probe（origin/main cfb6c74 から作成）
slice       G7 V1e CogVideoX-2B Apache fallback evaluation
状態        R9700/Broker/quality実測完了、production adoptionはDEFERRED
baseline    focused 33 passed、full 700 passed / 1 warning / 49.15s
installed   Media Forge v0.9.0 / 127.0.0.1:9130 / healthy
GPU         quality run後 KFD process 0 / R9700 baseline 59,912,192 B
PR          Media Forge #124 open / exact head・CI・mergeability確認中
```

G7 V1c は Media Forge #122、merge commit
`41eee86efc97db285c6717c3f482834604442816` で main へ入った。Hunyuan weight は取得していない。
G7 V1d は Media Forge #123、merge commit
`cfb6c74890e5c00257898e7a3169d9cb26826b65` で main へ入った。

## この slice の結果

```text
PASS       Apache-2.0 exact revision / 19 files / 5 LFS SHA-256
PASS       exact local snapshot / offline-only FP16 runner boundary
PASS       fixed 720x480 smoke/official presets / H.264 validation
PASS       optional core configuration / complete-snapshot-only visibility
PASS       R9700/gfx1201 / PyTorch SDPA / custom kernel 0
PASS       Host Job / Broker grant-activate-renew-refresh-release
PASS       official 49-frame artifact / subject and composition coherence
PASS       process swap 0 / process cleanup / installed service restoration
FAIL       requested panel-folding action was not clear
FAIL       930.861 sec latency / system swap in-out 29,888-29,985 pages
NOT TESTED deterministic repeat / Cog-specific cancel / active Sonic coexistence
NOT TESTED public Asset/provenance / I2V（candidate is T2V-only）
DEFERRED   CogVideoX-2B production adoption / G7 V2 promotion
```

通常の video capability/routing state は変更していない。catalog は Cog の実 R9700 backendを
記録したが `experimental` / `measurement_confidence=low` / recommended profile 0 のまま。

## 次にやること（1つだけ）

```text
1. V1e PR #124 の exact head/CI/mergeabilityを確認してmergeする
2. action adherence / zero system-swap / shorter latency を満たす次の Apache系 T2V候補を選ぶ
3. T2Vとは別にI2V候補を固定し、両方のadoption gate通過後だけG7 V2へ進む
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの一般的な継続指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeck slice code/DB/manifest変更0。既存`frontend/tsconfig.tsbuildinfo`変更1件は保全。Hostはread-only。
installed v0.9.0 service は healthy。評価用branch coreは停止済み。
Cog runtime/snapshot/evidenceは `/data1tb/mediaforge-g7-cogvideox2b` に外部保持。
Hunyuan weight/snapshot/partial download は0。dedicated runtimeだけ外部構築済み。
Wan runtime/model は移動・削除しない。
SonicForge は独立 service。競合時は Broker を唯一の調停経路にする。
```

## 参照

```text
設計正          docs/base-plan.md / docs/controldeck-integration-plan.md
全体 roadmap    docs/implementation/goal-roadmap.md
G7 実装指示     docs/implementation/g7-video-runtime.md
実測            docs/implementation-status.md
model catalog   docs/models.md / worker_packs/image/models.json
```
