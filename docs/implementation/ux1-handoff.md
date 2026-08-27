# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-27
branch      ux1/video-model-management-clarity（origin/main 02f1ac1 から作成）
slice       v0.9.2 video model add/remove management and runtime-gate clarity
状態        実装・source browser評価完了 / PR・release・installed acceptance前
baseline    focused 211 + 155 passed / full 751 passed / 1 warning / 51.73s
installed   v0.9.1 / PID 9724,9728 / 127.0.0.1:9130 / healthy / contract 2.0
GPU         生成再評価0。既存G7不採用証跡を維持
PR          ControlDeck変更0 / Media Forge PR前
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
G8 B4 handoff は Media Forge #142、exact head
`36314efa61c4dd1c32ef43fd4cc8efa02167b485`、merge commit
`48d7caf02eec59c72a44cfb4811ce1f15d437ba6` で main へ入った。
G8 B5 は Media Forge #143、exact head
`f20f9517c7c79574c0980c0019ea52b288e40dc2`、merge commit
`a6c37e28bcc5471102a9e13fe7b4e1cc9b47e552` で main へ入った。
G8 B5 handoff は Media Forge #144、exact head
`0ec084951e32576622ff7a4eb79bb961a105c49e`、merge commit
`b9a8878a2a4b51076a32546ce49632ca34db295e` で main へ入った。
Mobile Create media switch は Media Forge #145、exact head
`bd9a06517d2dbbd678a9ed48391f4bfaa4c092b3`、merge commit
`cc64bd32b6d7d27718bbef21771acafd13a191d7` で main へ入った。
そのhandoffはMedia Forge #146、exact head
`0d6d22b12aa58037f92e960926b77bc421d24225`、merge commit
`5810f7fdcccd2eb7c8208a98e037ac8437fb8917`。v0.9.1 releaseはMedia Forge #147、exact head
`f7f42c7af6e34420d2dba4017f733a6f4d58c8c7`、merge commit/tag
`cc3f342d77a20e98d95fcc43d276e1aafdcd8d94`。

## この slice の結果

```text
PASS       実ControlDeck v0.9.1で現象再現。動画候補12／追加可能0／削除可能2
PASS       モデル管理入口、管理件数、常時表示の操作不能理由
PASS       license acceptanceとruntime採用gateの分離表示
PASS       CogVideoX-2Bをbounded managed checkpointへ変更。追加可能1
PASS       standalone 1280px/320px、horizontal overflow 0、browser errors 0
PASS       focused tests / full 751 / static checks
NOT TESTED CogVideoX実download/remove、v0.9.2 release/install、installed v0.9.2 browser
NOT TESTED production動画生成。capability unavailableを維持
```

公開video capabilityは`video.text_to_video`と`video.image_to_video`の両方を
`unavailable / video_runtime_not_adopted`として明示した。UIは入力面を表示するが、利用可能性を偽らず
submitしない。既存`video.generate`契約、candidate catalog、routing/adoption stateは変更していない。

## 次にやること（1つだけ）

```text
1. このsliceをcommit/push/PR/mergeし、v0.9.2 signed bundleを公開する
2. ControlDeck標準update後、installed browserで追加1／削除2と理由表示を確認する
3. 13.8GB CogVideoX実download/removeは既存snapshotを壊さない隔離storeで評価する
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの一般的な継続指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeckはgeneric grant publishだけ別PR #246で修正・merge。Media固有route/dependency/文言は0。
既存`frontend/tsconfig.tsbuildinfo`変更1件は保全。ControlDeck server PID 2231760は15:53:09起動。
installed v0.9.1へ標準update済み。PID 2325466/2325471、127.0.0.1:9130でhealthy / contract 2.0。
`current`はversions/0.9.1、rollback用versions/0.9.0を保持。公開bundleは30,954,097 B、SHA-256
`ae9087ca6f1548260dd69f980face65cde003f380f8fa74488e68b4d8d098bf2`。
Cog runtime/snapshot/evidenceは `/data1tb/mediaforge-g7-cogvideox2b` に外部保持。
Hunyuan weight/snapshot/partial download は0。dedicated runtimeだけ外部構築済み。
Wan runtime/model は移動・削除しない。
Wan VACE downloadは `/data1tb/mediaforge-g7-wan21-vace/hf` に外部保持し、partialを消さない。
Wan T2V 1.3B weights/partial snapshotは0。runtimeはrepo内ignored `.venv`へ構築済み。
`sonicforge-acceptance.service` はexternal操作で14:52:03にsuccess停止・transient unit削除済み。
127.0.0.1:9140のexternal SonicForge acceptanceは現在healthy / contract 2.0、Speech Essentials/Music
ok、Game Audio missing。Qwen/llama process 0。B5はCPU-only / software renderingでこの
external環境を変更せず、ControlDeck resource request増分0。競合時は Broker を
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
