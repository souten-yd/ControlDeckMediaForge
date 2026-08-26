# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      ux1/wan21-1.3b-candidate-preflight（origin/main af15cd2 から作成）
slice       G7 V1f Wan 2.1 1.3B T2V/I2V candidate preflight
状態        exact source/bundle/runtime/R9700 import PASS、weights/inference NOT TESTED
baseline    focused 9 passed / 1 warning、full 702 passed / 2 warnings / 48.88s
installed   Media Forge v0.9.0 / 127.0.0.1:9130 / healthy / contract 2.0
GPU         preflight後 KFD process 0 / R9700 baseline 59,912,192 B
PR          Media Forge #125 open / exact head・CI・mergeability確認中
```

G7 V1c は Media Forge #122、merge commit
`41eee86efc97db285c6717c3f482834604442816` で main へ入った。Hunyuan weight は取得していない。
G7 V1d は Media Forge #123、merge commit
`cfb6c74890e5c00257898e7a3169d9cb26826b65` で main へ入った。
G7 V1e は Media Forge #124、merge commit
`af15cd2eced1b3046b588eb9b663aaad4f106631` で main へ入った。

## この slice の結果

```text
PASS       public/non-gated/Apache-2.0 official identities and exact revisions
PASS       T2V 31 files / 28,935,653,511 B / 10 inference LFS hashes
PASS       VACE 27 files / 19,043,130,596 B / 8 inference LFS hashes
PASS       dedicated 4,686,651,246 B runtime / pip check 0
PASS       R9700/gfx1201 / both pipelines and transformers / PyTorch SDPA
PASS       preflight 2.15 sec / max RSS 959,360 KiB / swaps 0 / KFD process 0
CAUTION    exact snapshots contain no LICENSE/LICENSE.txt/NOTICE
NOT TESTED weights / load / generation / Broker / quality / cancel / coexistence
DEFERRED   production adoption / G7 V2 promotion
```

通常の video capability/routing state は変更していない。両 candidate は catalog で external /
`experimental` / `measurement_confidence=low` / recommended profile 0 のまま。

## 次にやること（1つだけ）

```text
1. V1f を focused/full/evidence確認し、PR作成・exact-head確認・mergeする
2. VACE exact snapshotを外部NVMeへbounded download/hashし、private I2V evaluatorを作る
3. Broker経由I2V gateがPASSした場合だけT2V 1.3B download/evaluationへ進む
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの一般的な継続指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeck slice code/DB/manifest変更0。既存`frontend/tsconfig.tsbuildinfo`変更1件は保全。Hostはread-only。
installed v0.9.0 service は healthy。評価用branch coreは起動していない。
Cog runtime/snapshot/evidenceは `/data1tb/mediaforge-g7-cogvideox2b` に外部保持。
Hunyuan weight/snapshot/partial download は0。dedicated runtimeだけ外部構築済み。
Wan runtime/model は移動・削除しない。
Wan 2.1 1.3B weights/partial snapshotは0。runtimeだけrepo内ignored `.venv`へ構築済み。
SonicForge は `sonicforge-acceptance.service` でactive。競合時は Broker を唯一の調停経路にする。
```

## 参照

```text
設計正          docs/base-plan.md / docs/controldeck-integration-plan.md
全体 roadmap    docs/implementation/goal-roadmap.md
G7 実装指示     docs/implementation/g7-video-runtime.md
実測            docs/implementation-status.md
model catalog   docs/models.md / worker_packs/image/models.json
```
