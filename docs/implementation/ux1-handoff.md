# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      g7/wan-ti2v-probe（origin/main d58ec9e から作成）
slice       G7 V1 revision-pinned Wan2.2 TI2V-5B adoption probe
状態        実装・実 R9700/ControlDeck/Broker probe 完了、adoption DEFERRED
baseline    focused 17 passed、full 686 passed / 1 warning / 48.38s
installed   Media Forge v0.9.0 / 127.0.0.1:9130 / healthy に復元済み
GPU         Wan process 0、Media Forge lease 0。SonicForge の通常 process は別管理
PR          未作成
```

G7 V0 は Media Forge #119、merge commit
`d58ec9e3565b7e5d9e7f203deb55d8f79cb707e1` で main へ入った。V0 の完了作業を
繰り返さない。

## この slice の結果

```text
PASS       pinned Wan source/model/runtime preflight
PASS       R9700 512x320 / 17-frame cold + 3 warm deterministic samples
PASS       real installed browser identity / Host Job / Broker lease / cancel
PASS       SonicForge/LLM hold 中の fail-closed と release 後の admission
PASS       cancel 1.007 sec、lease/worker/partial cleanup
FAIL       256x256 / 49-frame 実用 clip の prompt coherence
FAIL       同 clip の process swap 1,754,775,552 bytes
NOT TESTED I2V / native 720p / 121 frames / 50 steps / public asset path
DEFERRED   Wan production adapter/default/available への採用
```

主要実測は `docs/implementation-status.md` の G7 V1 節を正とする。外部証跡は
`/data1tb/mediaforge-g7-v1/`、operation artifact/log は installed data directory の
`model-evaluations/<operation_id>/` にある。固定 17-frame warm 3 回は 75.955 / 71.972 /
71.221 秒、peak VRAM 約 30.612 GB、process swap 0、同じ SHA-256。49-frame は
235.053 秒で完走したが品質と swap gate を落とした。

## 次にやること（1つだけ）

```text
1. current diff と docs を最終確認する
2. commit、push、Media Forge V1 PR を作成し CI/exact head を確認して merge する
3. origin/main から候補比較 branch を切り、V1 の再開条件を満たす profile/別候補を評価する
```

V2 production execution へ直接進まない。V1 adoption gate が deferred なので、次は Wan の
品質 profile 改善または LTX-2.x 等との bounded 比較である。カーネル自作、ControlDeck への
動画固有依存、public contract の変更は行わない。

## 境界と外部状態

```text
ControlDeck 変更 0。Host は read-only のまま。
評価用 branch core は停止済み。installed v0.9.0 service を再起動済み。
Wan runtime/source は /data1tb/mediaforge-g7-v1/ の外部評価環境。
モデル snapshot は installed NVMe model store。移動・削除しない。
テスト account password hash は exact 元値へ復元済み。秘密値は記録しない。
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
