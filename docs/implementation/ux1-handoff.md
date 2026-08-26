# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      g7/hunyuan15-probe（origin/main b528884 から作成）
slice       G7 V1c HunyuanVideo-1.5 weight-free R9700 preflight
状態        runtime/import/SDPA PASS、weight/inference は license acceptance 待ち
baseline    full 686 passed / 2 warnings / 51.28s、compile/diff PASS
installed   Media Forge v0.9.0 / 127.0.0.1:9130 / healthy
GPU         preflight 後 process 0。SonicForge は別管理
PR          未作成
```

G7 V1b は Media Forge #121、merge commit
`b528884d6799b3571799fae064f2ffaab3110308` で main へ入った。Wan practical profile を
production adapter へ昇格させない。

## この slice の結果

```text
PASS       Hunyuan 480p distilled を次候補に選定
PASS       dedicated ROCm runtime / pip check / gfx1201 enumeration
PASS       Diffusers pipeline / transformer / VAE / PyTorch SDPA import
PASS       custom CUDA kernel 0 / GPU process cleanup
PASS       installed v0.9.0 healthy / full 686 passed
NOT TESTED 53,367,753,676-byte weight download / hash
NOT TESTED generation / Broker / cancel / quality / installed browser
BLOCKED    Tencent Hunyuan Community License の明示同意待ち
```

主要実測は `docs/implementation-status.md` の G7 V1c 節を正とする。専用 runtime は
`/data1tb/mediaforge-g7-hunyuan15/runtime`（4,688,976,346 bytes）。weight は未取得。

## 次にやること（1つだけ）

```text
1. commit/push、V1c PR、exact head/mergeability、merge を完了する
2. 利用者へ exact license 条件と 53GB download の明示同意を求める
3. 同意後だけ pinned sequential download と hash verification を開始する
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの「計画を進める」という一般指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeck 変更 0。Host は read-only。
installed v0.9.0 service は healthy。評価用 branch core は起動していない。
Hunyuan weight/snapshot/partial download は 0。runtime だけ外部構築済み。
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
