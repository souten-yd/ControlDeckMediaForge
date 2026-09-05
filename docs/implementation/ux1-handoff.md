# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 2026-09-05 3DS-4b browser scene import / revision UI

PR #226、branch `ux1/3d-scene-import-ui`、実装commit `573b610`。作る媒体へ3D Studioを追加し、incremental
SHA-256、512 KiB chunk、256 MiB上限の`.blend` file input、scene一覧、immutable revision履歴、既存の
validated GLB viewerによる各版previewを実装した。path/raw `.blend`/working leaseはbrowserへ出さない。

実Chromeのsource processで1,247,112 Bを3 chunk、1.447298秒で取り込み、16,128 triangles / 1 materialの
previewを表示。upload中cancel後のstaging 0と同owner再beginも確認した。日英再描画、320/320 px、主操作
45.994 px、console/page error 0。fullは904 passed / 1 warning / 78.00秒。0.27.4 bundleは
31,397,686 B / SHA-256 `1bbb21f0bf06db3a19fb250fa31dccaf69d3b35ed1a4f2fe5da6734b10f4cb81`、
doctor ok。packaged browserでも同じfileを3 chunk、1.163959秒で保存・表示した。

実ControlDeck opaque iframeは **NOT TESTED**、ControlDeck変更0。次は`ux1/3d-scene-backup`でexact
backup/restoreを実装する。

## 2026-09-05 3DS-4b private working-copy transport

PR #225、branch `ux1/3d-scene-working-copy`、実装commit `5a95a21`。3DS-4b coreをlifespanへ接続し、owner-scoped
WebSocket/standalone private transport、session working list、socket切断時upload回収を追加した。
公開OpenAPI/addon/tool/executorは未変更。実Uvicornの1,247,112 B / 3 chunk importは0.343030秒、
working commit 0.252321秒、二重writerは422。packaged 0.27.3でもimport 0.296297秒、commit
0.274779秒、revision 2件、autoexec sentinel 0。fullは902 passed / 1 warning / 79.74秒。
候補bundle 31,392,211 B / SHA-256
`197099156662638de8bd122bec4a30dc35a69ca06b55efe0d73a7c95628c2323`、doctor ok。

browser UI/ControlDeck installedは **NOT IMPLEMENTED / NOT TESTED**、ControlDeck変更0。次は
`ux1/3d-scene-import-ui`でbrowser import/scene表示、その後`ux1/3d-scene-backup`。

## 2026-09-05 3DS-4b core bounded working copy

PR #224、branch `ux1/3d-scene-working-core`、実装commit `c03c8dc`。256 MiB `.blend` / 512 KiB chunk / 10分upload、
owner同時1件、single-writer WorkingCopy lease、runtime pin、trusted Blender validation/export、独立GLB検査、
immutable Asset/revision commitを実装した。working leaseとbase/current revisionは同じtransactionで再検証し、
競合・期限切れbytesはrecoveryとして残す。raw `.blend`はLibraryに直接出さない。

実Blender 4.5.9で1,247,112 Bのsphereを3 chunkでimport 0.268493秒、working commit 0.267828秒。
8,066 vertices / 16,128 triangles / preview 1,138,160 B、revision 2件、runtime参照1。悪意あるtext blockは
保持して検査したがautoexec sentinelは生成されなかった。fullは897 passed / 3 skipped / 1 warning /
78.17秒。private transport/browser/ControlDeck/packageは **NOT TESTED**、ControlDeck変更0。
次は`ux1/3d-scene-working-copy`のprivate WS/standalone transportを独立PRにする。

## 2026-09-05 3DS-4a immutable scene revision persistence

PR #222、branch `ux1/3d-scene-revisions`、実装commit `9d053fb`。owner-scoped SceneDocument、append-only
SceneRevision、依存Asset hash、Blender runtime identity、validation report、optimistic commitをSQLiteへ
追加した。`.blend`は公開Asset MIMEへ加法的に追加したがpublic import/tool/executorは未追加。
private `scenes.list/get`、session part、standalone mirrorだけを提供する。過去revisionのruntime参照は
managed removeを拒否し、revisionが参照するAsset削除も拒否する。

実Blender 4.5.9の`.blend` 426,550 BとGLB 1,748 Bを保存し、別Uvicornの再起動前後および0.27.2
packaged processでscene応答1,354 B / SHA-256
`511e636c46dbfc1846cdc06da54962c8fb3079a05018097abdebd29e4d3e6b09`が同一。runtime参照数1、
preview削除はrevision参照で拒否。full gateは896 passed / 1 warning / 74.83秒。候補bundleは
31,357,017 B / SHA-256 `c4d020a530449f9620c4b193b34e5bc77d2cf44475646c06f5f658640ffe644b`、
doctorは`ok / 0.27.2 / packaged=true`。

bounded upload、working copy/lease、実Blender隔離import/saveは **NOT IMPLEMENTED** で3DS-4b、
backup/restoreは3DS-4c。browser/ControlDeck installed/GPU/Web Blenderも **NOT TESTED**。
ControlDeck変更は0件。次は`ux1/3d-scene-working-copy`。

## 2026-09-05 3DS-3 shared Library GLB viewer

PR #219、実装commit `b5a73824030b5506e409e7f6b0cc9e0a3b5c8a98`。
LibraryをAll/Images/Videos/3Dの共通filterへ拡張し、raw GLBと既存G8
`3d.project.glb` ZIPを同じinteractive viewerで表示する。Three.js 0.185.1はnpm integrity、
source/bundle SHA-256、MIT noticeを固定し、CDNを使わず最初のモデルを開くまで読み込まない。
opaque iframeはconnection-scoped handleから512 KiB chunkだけを受け、ZIP stagingはclose/socket切断で
回収する。64 MiB GLB、8,192 px/辺、67,108,864 texture pixel、同時2 handleをfail-closedで強制する。

実Blender 4.5.9で3,116 Bのanimation付きcubeを生成し、実Chromeで12 triangles / 1 material /
1 animation、play/pause、hidden時frame 10→10、復帰後17、WebGL context loss/restoreを確認した。
実G8 job `job_9062c76d510c4c12b2b36d1c1800fc5c`のZIPは24 triangles / 2 materialsで、raw GLBとの
前後比較と7 contextの解放を確認。320 pxは横溢れ0、操作高43.995 px、最終console/page error 0。
5回開閉後のheap増分は450,592 B。候補bundle 31,346,609 B / SHA-256
`a0b24e41e7af790e6dbc1993c6655e13a88cf03122b85f4b8abaa2a820b9cd78`でも同じanimation GLBを
描画し、module 643,367 B / SHA-256 `99935b9427ddad9aa892a8046376da55eaa3e5fe8873d3cdaafbabb6f530b843`
を配信した。full gateは891件PASS。

実ControlDeck opaque iframe、texture付き実モデル、64 MiB上限付近、context lossを伴う破損GPU、
material slot/画像差替え、Blender edit、scene/revisionは **NOT TESTED / NOT IMPLEMENTED**。
ControlDeck変更は0件。次は3DS-4 scene/revision/working copy。

## 2026-09-05 3DS-2c protected remove / shared CLI

PR #218、実装commit `4b5cdbb3c2b37978d17f3226d0012e4364adef3c`。
`ux1/3d-runtime-remove`でmanaged runtimeの削除preview/確認fingerprint、active/live G8参照拒否、
atomic staging、registry失敗rollback、service restart後cleanup、UI日英ダイアログを実装した。
source互換の`blender build/status`を保ち、稼働serviceの同じmanagerを呼ぶmanaged CLIも追加した。
実4.5.9のpreviewは1,168,332,155 B、live pin中とstale previewを拒否し、Settings削除後もactive
4.5.13、download cache、asset/scene hashを保持。CLIで4.5.9再導入/切替後、4.5.13も削除できた。
Chrome日英/320 px/active拒否/自動終端追従、console/page error 0。full 884件がPASS。
0.27.0 bundle 31,163,397 B / SHA-256 `c3baa20ea6adabc0390ba012a04ed0d39a70477bd99c9870b054e582bc1f3ae0`を
packaged processで起動し、doctor、health、runtime status、未導入remove previewのfail-closedを確認。
3DS-2は完了、次は3DS-3 Library GLB viewer。
実ControlDeck opaque iframe、公開release、GPU/Cycles、Web Blender以降は **NOT TESTED**。

## 2026-09-05 3DS-2b side-by-side update / switch / repair

PR #217、実装commit `5d19897af20aabb18f218fed1ff5891e93973c79`。
`ux1/3d-runtime-update`でofficial catalogへ4.5.13を追加し、4.5.9をG8互換版として残す
side-by-side更新、probe後のactive切替、検証済み版への明示切替、同一版のatomic修復を実装した。
正規4.5.13 archive 378,033,952 Bを取得し、更新54.507秒、実probe 4.5.13 / Python 3.11.15 / GLTF
import/export true。active 4.5.13でもG8は4.5.9を解決し、実HTTP jobのZIPは44,292 B / baseline同一hash。
実executable欠損からの修復は20.091秒で同一hashへ復元。Chrome更新操作、日英、320 pxもPASS。
full gateは875件、packaged serveでも4.5.9/4.5.13 catalogを確認。次は3DS-2c参照保護付き
removeとCLI共通化。
実ControlDeck opaque iframe、公開release、GPU Blender、Web Blender以降は **NOT TESTED**。

## 2026-09-05 3DS-2a durable Blender install / cancel / restart

PR #216、実装commit `48ac9c9d3d3542a93b547ad64b3c2d79d4099bfc`。
`ux1/3d-runtime-install`でBlender専用journal/manager、trusted catalog限定download、size/hash/archive
検証、atomic install、probe、opaque登録、cancel、Range/ETag restart、private transport、Settings
進捗を実装した。正規377,929,956 B archiveのclean installは25.659秒、managed 1,605,023,227 B、
probe全true。G8 ZIPは44,292 B / SHA `c78ef18d...a468b`でbaseline同一。8 MiB停止→Range再開と
8 MiB cancelも実測。full 867件、focused 240件、bundle build/doctor、日英/320 px ChromeがPASS。
実Host opaque iframeは未認証のため未検証。次は3DS-2b update/switch/repair、その後remove。
Web Blender、scene、viewer、材質、OpenCode制作、GPU Blender、release公開は未実装・未検証。

## 2026-09-05 3DS-1 runtime resolver / Settings diagnostics

PR #215、実装commit `4c7c6f793f2c6936b74bfc755fe5f3a29e14def6`。
`ux1/3d-runtime-status`でversioned registry/resolver、legacy 4.5.9登録、G8 runtime解決、
private status transport、read-only Settings診断を実装した。実Uvicorn/Blenderで3DS-0と同じ
796 B cubeから44,292 B / SHA-256 `c78ef18d...a468b`の同一ZIPを得た。registryは258 B /
mode 0600 / raw pathなし。standalone Chromeでready/missing、診断、日英、320 pxを確認した。
実ControlDeck opaque iframeは未認証で`/login`へ遷移したため **NOT TESTED**。
次は3DS-2の最初の小PRとしてdurable install/cancel/restart復帰を実装する。その後に
update/switch/repair、参照保護付きremoveを別sliceで行う。Web Blender、scene、viewer、材質、
OpenCode制作、GPU Blenderは未実装・未検証。

## 2026-09-05 3DS-0 baseline

PR #213はmerge commit `9469d8e4e4980752082f5081da7ba6e95d184622`でmainへ入った。
`ux1/3ds-0-baseline`で既存Add-on/public/G8契約fixtureと
`docs/implementation/3ds-compatibility.md`を追加した。source runtimeはBlender 4.5.9 ready、
実Uvicorn/実Blenderで同じGLBを2回加工したZIPはbyte-identical。installed 0.27.0は画像availableだが
bundle外runtimeを解決できずG8は`runtime_not_installed`で、3DS-1のresolver対象。
最終gateはfocused 176件、full 851件、static/link checksがPASS。
次は3DS-1 runtime resolver、legacy登録、read-only設定診断を独立PRで実装する。
Web Blender、scene、viewer、材質、OpenCode制作、runtime lifecycleは未実装・未検証。

## 2026-09-05 3D Studio設計の引き継ぎ（文書のみ）

利用者の決定: 画像と3DをMediaForgeへ実装・管理・配布まで統合する。
設計も本リポジトリへ置き、別SceneForgeリポジトリは使わない。
`docs/design-3d-studio.md` と関連runtime/Web、asset/OpenCode、開発/release設計、
`docs/implementation/g8-3d-studio-plan.md` を追加した。
次の3D作業は最新main/実機状態を照合する3DS-0、その後runtime resolver/設定診断の3DS-1。
この計画追加ではruntime/API/UIコード、addon manifest、版数、Host、稼働環境を変更していない。
新しい3D機能はNOT IMPLEMENTED、Blender/GPU/ブラウザ受入はNOT TESTED。
以下の旧引き継ぎは履歴として保持する。古いbranch/版数を現在状態とみなさず最新を確認する。

## 現在地

```text
最終更新    2026-08-28
branch      fix/timeout-counts-the-images（origin/main 1f65a38 から作成）
slice       打ち切りの予算が枚数を数えていなかった / ヘッダーの寄せ方
状態        LoRA実機成功を確認・timeoutの原因特定と修正 / v0.9.11 release前
baseline    full 771 passed / 1 warning / 62.93s（新規2件）
installed   v0.9.10 / 127.0.0.1:9130 / healthy / contract 2.0
GPU         LoRA実機成功 job_8838a3c7 / 4枚 512x512 / DreamShaper + civitai/16014
PR          ControlDeck変更0 / Media Forge #157-#167 merged / release PR前
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

## 現在の slice の結果

```text
PASS       おまかせの実態を router/models.json/custom_models.pyで確認。auto候補は2件固定
PASS       使うモデルを常時表示。先頭「おまかせ」、以降は導入済みhealthyな画像土台
PASS       FLUX.2 Klein 4B指定でLoRA候補0件・理由1行。SSD-1B指定でSDXL 1件だけ
PASS       強さはチェック済みの行だけに描画。0.75操作でstate反映を実Chromeで確認
PASS       土台変更で載らないLoRAを外し、件数を状況欄へ1行表示
PASS       作る素材の切替をヘッダーの絵2択へ。表示モードのすぐ左、高さ52px、overflow 0
PASS       当たり判定44x38、押下でaria-pressed入替・見出し・動画欄が追従
PASS       hostBusy中は2つとも無効。押しても素材は変わらない
FIXED      総称ボタン規則の:not()内idが勝ち押下accentが出ない件。実描画で発見
PASS       full 761 / 2 warnings / 59.69s、git diff --check
NOT TESTED 実LoRA weightを載せた生成の見た目差分（実機installedへ未反映のため）
PASS       signed v0.9.5 / 公開Release再取得でsha256一致 / ControlDeck標準update 11.88s
PASS       installed v0.9.5でFLUX.2指定時にSD 1.5 LoRAと強さが出ないことを実機確認
FIXED      civitai/16014が載る土台が実機に無い件。原因はevaluate()と_run()の判定不一致で、
           画像モデルは評価を開始できずoperation行すら残らなかった
FIXED      追従がin-process task頼みで再起動に耐えなかった件。models.listで帳尻を合わせる
NOTE       loraCandidates()はinstalledのみ判定。LoRA自体は測らなくても載るので不整合ではない
NOT IMPL   host headerの詳細削除と1行化。EmbeddedAddonView.tsx:403-408のホスト共通
           ヘッダーで、add-onからheaderへ操作を出す拡張点がcontract 2.0に無い。別タスク
DEBT       dist/を一度main へ入れた。#160で追跡解除。履歴のblobは残す

（前 slice / v0.9.4 の結果）
PASS       実試行はdownload前、model operation 0件、catalog rollbackと特定
PASS       exact LoRA 62833 + DreamShaper 128713でidentity invalidを再現
PASS       Civitai namespaceだけ数値runtime revisionを許可。generic 40-hexは維持
PASS       verified weightがあるsingle-fileだけrequired_files空を許可
PASS       live metadata temporary registryで2件parse / installed=false
PASS       focused tests / full 759 / static checks
PASS       signed v0.9.4 / public redownload署名検証 / ControlDeck標準update
PASS       installed browser DreamShaper dependency / overflow 0 / errors 0
NOT TESTED 新規LoRA weight download（個別配布条件の利用者同意前）
```

公開video capabilityは`video.text_to_video`と`video.image_to_video`の両方を
`unavailable / video_runtime_not_adopted`として明示した。UIは入力面を表示するが、利用可能性を偽らず
submitしない。既存`video.generate`契約とrouting/adoption stateは変更せず、CogVideoXのcheckpoint
ownershipだけをmanagedへ変更した。

## 次にやること（1つだけ）

```text
1. v0.9.8を反映し、画面を開いてDreamShaperの自動評価が ready まで行くことを実測する
2. 評価が通ったらcivitai/16014を実際に載せたsame-seed比較まで進める
3. host headerの詳細削除と1行化は利用者が別タスクで進行中。こちらからは触らない
```

license は利用開始を同意とみなす Tencent Hunyuan Community License Agreement。EU/UK/South
Korea を除く Territory、acceptable-use、distribution/notice、第三者提供時表示、100M MAU 条件を
含む。ユーザーの一般的な継続指示を license acceptance と解釈しない。

## 境界と外部状態

```text
ControlDeck変更0。既存`frontend/tsconfig.tsbuildinfo`変更1件は保全。ControlDeck server PID 22486。
installed v0.9.4はPID 181500/181506、127.0.0.1:9130でhealthy / contract 2.0。
`current`はversions/0.9.4、rollback用versions/0.9.3を保持。公開bundleは30,959,024 B、SHA-256
`cec0920bb79dd0179965d2ecc6f220fbed477348c8a4c915b719ec77e5d59093`。
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
