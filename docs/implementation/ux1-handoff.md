# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      ux1/g8-b4-handoff（origin/main c06ec86 から作成）
slice       G8 B4 handoff close / B5 preparation
状態        B0-B4 merged / B5未着手
baseline    focused B4 200 passed / full 746 passed / 1 warning / 48.51s
installed   v0.9.0復元 / 127.0.0.1:9130 / healthy / contract 2.0
GPU         VACE worker 0 / KFD process 0 / R9700 baseline 59,912,192 B
PR          Media Forge #141 merged / handoff PR未作成
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
G7 V1h は Media Forge #128、exact head
`e5a527c4c7e8c903627d1acbcb74e2b6ff3f72b3`、merge commit
`9d486d86986fdbf06d29830432f835d2aacac679` で main へ入った。
G7 V1i は Media Forge #130、exact head
`77b15513981e0d8a6f06b65b6d0fa25cdf36858d`、merge commit
`7e8d2313d2543ee0b0df444eacc5c2d2f92f619f` で main へ入った。
G8 B0 は Media Forge #133、exact head
`17e7b2f1842928676101806f828bb91c911714c5`、merge commit
`9dc903445721abfacc2342a5c916dc88647826f0` で main へ入った。
G8 B1 は Media Forge #135、exact head
`e3e1d5e9f6c2fb5c9859eb5f57f942ca5bd9f05f`、merge commit
`f0bf8a3d4a2d23db931b1539ed970de59e606319` で main へ入った。
G8 B2 は Media Forge #137、exact head
`cc554a50f7df2f5508fa536fff58b1fcd7ea2b53`、merge commit
`84a231eaae4a69855580d204dbe6220897a514e0` で main へ入った。
G8 B3 は Media Forge #139、exact head
`aa322ea0e03e64c72f22fdc93d9ae30ade91df1d`、merge commit
`dd94ab13388ab8f5aa6b3855d8d89054383ab504` で main へ入った。
G8 B3 handoff は Media Forge #140、exact head
`96feb1938825c4455f978a11bf637a393ecb2d42`、merge commit
`bdf6a770203ad6d069847d9eb0e814d9515005f9` で main へ入った。
G8 B4 は Media Forge #141、exact head
`123db996d90a34dbc6933ded3ce943bf2348a91c`、merge commit
`c06ec865778f3d81a9102340ab3725bf6d3f3a76` で main へ入った。

## この slice の結果

```text
PASS       runtime-derived asset.3d_project_pack capability / Blender起動なし
PASS       Simple selected-asset gate / Advanced exact typed options
PASS       real standalone Chromium + Blender / ZIP card + viewer preview / browser errors 0
PASS       ZIP no-extract exact entry/manifest/hash bounds / hostile traversal reject
PASS       Agent generate → embedded Library preview → Agent pack grant contract
PASS       focused 200 / full 746 / node check / compileall / diff check
NOT TESTED installed Host browser/identity/real grant / reconnect / real cancel/timeout / rig+animation / B5
```

通常の video capability/routing state は変更していない。両 candidate は catalog で external /
`experimental` / `measurement_confidence=low` / recommended profile 0 のまま。

## 次にやること（1つだけ）

```text
1. G8 B5 installed ControlDeck browser / Agent / grant / cancel / recoveryを実測する
2. 実Blender別process 2回hash、reconnect、queued recovery、running restartを閉じる
3. G7は明示license acceptanceまたは別の実用候補が現れるまでDEFERREDを維持する
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
`sonicforge-acceptance.service` はexternal操作で14:52:03にsuccess停止・transient unit削除済み。
127.0.0.1:9140のexternal SonicForge acceptanceは現在healthy / contract 2.0、Speech Essentials/Music
ok、Game Audio missing。Qwen/llama process 0。B4はsoftware rendering + GPU visibility空でこの
external環境を変更していない。競合時は Broker を
唯一の調停経路にする。
```

## 参照

```text
設計正          docs/base-plan.md / docs/controldeck-integration-plan.md
全体 roadmap    docs/implementation/goal-roadmap.md
G7 実装指示     docs/implementation/g7-video-runtime.md
実測            docs/implementation-status.md
model catalog   docs/models.md / worker_packs/image/models.json
G8実装指示      docs/implementation/g8-blender-production.md
```
