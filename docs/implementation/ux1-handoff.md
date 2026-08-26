# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      ux1/hunyuan-evaluator-prep（origin/main 41eee86 から作成）
slice       G7 V1d Hunyuan license-gated evaluator preparation
状態        runner/core admission PASS、weight/model load は license acceptance 待ち
baseline    focused 20 passed、full 693 passed / 1 warning / 46.96s
installed   Media Forge v0.9.0 / 127.0.0.1:9130 / healthy
GPU         weight-free preflight 後 KFD process 0。SonicForge は別管理
PR          Media Forge #123 open / exact head・mergeability 確認待ち
```

G7 V1c は Media Forge #122、merge commit
`41eee86efc97db285c6717c3f482834604442816` で main へ入った。Hunyuan weight は取得していない。

## この slice の結果

```text
PASS       exact local snapshot / offline-only runner boundary
PASS       fixed smoke/candidate/official presets and deterministic seed
PASS       H.264 output bounds / temporary and partial cleanup tests
PASS       optional core configuration / hidden-until-configured behavior
PASS       Host Job + conservative Broker request + metrics/validator wiring
PASS       dedicated runtime CLI / weight-free R9700 preflight / KFD cleanup
PASS       branch core real HTTP / hidden evaluation / capability unavailable
NOT TESTED 53,367,753,676-byte weight download / hash / model load
NOT TESTED real Broker lease/cancel / VRAM/RSS/swap / video quality
BLOCKED    Tencent Hunyuan Community License の明示同意待ち
```

通常の video capability/routing/catalog state は変更していない。実測前 envelope は
`confidence=low` であり採用値ではない。

## 次にやること（1つだけ）

```text
1. full gate、commit/push、V1d PR、exact head/mergeability、merge を完了する
2. 利用者の明示同意後だけ pinned sequential download と hash verification を開始する
3. smoke → candidate clip の順に Broker/metrics/cancel/quality を実測する
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの一般的な継続指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeck 変更 0。Host は read-only。
installed v0.9.0 service は healthy。評価用 branch core は起動していない。
Hunyuan weight/snapshot/partial download は 0。dedicated runtime だけ外部構築済み。
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
