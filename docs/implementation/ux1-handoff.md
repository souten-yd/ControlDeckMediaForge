# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      g7/wan-practical-profile（origin/main d883702 から作成）
slice       G7 V1b Wan evaluator host-memory lifecycle / practical profile comparison
状態        512x320 quality PASS / zero-swap FAIL、adoption DEFERRED
baseline    focused 17 passed、full 686 passed / 1 warning / 51.30s
installed   Media Forge v0.9.0 / 127.0.0.1:9130 / healthy に復元済み
GPU         Wan process 0、Media Forge lease 0。SonicForge は別管理
PR          Media Forge #121 open / mergeable確認待ち
```

G7 V1 は Media Forge #120、merge commit
`d8837026b4563cf3b94168629725d158ff3753bb` で main へ入った。V1 の probe を
production adapter へ昇格させない。

## この slice の結果

```text
PASS       meta-discard smoke / process swap 0
PASS       384x256 / 33-frame process swap 0
FAIL       384x256 / 33-frame prompt coherence
PASS       512x320 / 33-frame prompt coherence / deterministic SHA
FAIL       512x320 process swap 2,501,005,312 / 346,812,416 bytes
PASS       SonicForge hold 中 fail-closed、自然 release 後 admission
PASS       installed v0.9.0 復元 / healthy / worker・lease cleanup
DEFERRED   Wan production adapter/default/available への採用
```

主要実測は `docs/implementation-status.md` の G7 V1b 節を正とする。外部証跡は
`/data1tb/mediaforge-g7-v1/`、operation artifact/log は installed data directory の
`model-evaluations/<operation_id>/` にある。512x320/33-frame 2回は同じ SHA-256 と品質を
再現したが、process swap が0にならず operational gate を落とした。

## 次にやること（1つだけ）

```text
1. Media Forge #121 の exact head / diff / mergeability を確認して merge する
2. origin/main から別候補比較 slice を開始する
3. prompt coherence と zero-process-swap を同時に満たすまで V2 へ進まない
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
