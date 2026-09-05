# 3D Studio compatibility baseline

Status: 3DS-0〜4・3DS-5a VERIFIED / 3DS-5b〜5d source VERIFIED
Date: 2026-09-06

この表は統合3D Studio着手時の互換性基準である。既存画像・G8・公開契約を、後続実装の
「動いたはず」ではなくfixtureと実測で比較する。固定fixtureは
`tests/fixtures/3ds-baseline-contract.json`、検査は `tests/test_3d_studio_baseline.py`。

## 対象状態

| 対象 | 実測した状態 |
|---|---|
| MediaForge source | `origin/main` `9469d8e4e4980752082f5081da7ba6e95d184622`（PR #213 merge） |
| installed MediaForge | `current -> versions/0.27.0`、systemd user unit `cdapp-feature-media-forge.service`、PID 1241393、127.0.0.1:9130 |
| installed health | `healthy`、contract 2.0、既存contribution 10件available |
| installed image | `image.text_to_image=available / local / measured / local_only`。最新保持Assetは704x1472 PNG、7,262 B |
| source Blender | 4.5.9 / Python 3.11.11、background・GLTF import/export probeすべてtrue |
| source runtime | `runtimes/blender-4.5.9`、1,546,263,669 B、legacy stamp/archive hash一致 |
| installed G8 capability | `asset.3d_project_pack=unavailable / runtime_not_installed`。bundleにBlenderを同梱しない既存境界どおり |
| GPU | AMD Radeon AI PRO R9700 / gfx1201 / VRAM 34,208,743,424 B。採取時使用27,134,840,832 B |
| ControlDeck | `07f1c207903c64ff05c8f4e6857b6e025b76a98d`。既存dirty `frontend/tsconfig.tsbuildinfo`は変更していない |

installed imageの行は新規生成を実行したという意味ではない。0.27.0のlive capability応答と、
同じlive storeに保持された2026-09-03の実PNG Assetを確認した。画像生成の新しいGPU job、実ブラウザ、
画面操作は本sliceでは **NOT TESTED**。

## G8実process回帰

一時data rootと実Uvicorn `127.0.0.1:9164`を起動し、コード生成したmaterial付きcube GLBを
HTTP importして `asset.pack + profile=3d.project.glb` を2回実行した。入力は796 B、SHA-256
`f61f0c984f3967aee9840bac635be4fb8533631ae5ab5caeb9bf37837b8d75a8`。

両jobはsucceededし、ZIPは44,292 B、SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`でbyte-identical。
2回目のHTTP受付から終端観測までは1,055 ms。ZIP entryは順に `asset.glb`、
`manifest.json`、`preview.png`、固定timestampは1980-01-01だった。終了後work entry 0、
実Blender child 0。これはsoftware renderingの既存G8経路であり、GPU Blenderの証拠ではない。

設計PR headでは `./mf.sh test` が848 passed / warning 1件 / 61.84秒。3DS-0 fixture追加後は
851 passed / warning 1件 / 62.14秒。focused 176件、Python compileall、frontend JavaScript構文、
shell構文、変更Markdownの相対link、`git diff --check`もPASSした。

## 未確定事項

| ID | 2026-09-05 baseline | 次の証拠 |
|---|---|---|
| CHECK-01 | Hostにbinary WS relayのコードはあるがnoVNC往復は未実測 | opaque iframe、nonce/subprotocol、長時間、取消 |
| CHECK-02 | systemd user unit + AF_UNIX限定 + Landlock書込allowlistで実GUIを隔離し、filesystem/network/process negativeを実測 | gateway接続中の継続negative、対象kernel更新後の再確認 |
| CHECK-03 | Lavapipe/Vulkan software GUIとRFB入力・保存は実測。GPU/Cyclesは未実測 | GPU display/OpenGL/Cyclesを別々にprobe |
| CHECK-04 | durable setupを8 MiBで停止し再起動後Range/ETag再開、cancelも実測。3DS制作jobは未実装 | 120秒超の制作job、Host credential refresh |
| CHECK-05 | GLB 64 MiBとworkspace JSON上限は既存どおり | bounded .blend chunk/grant transport |
| CHECK-06 | frozen契約fixtureを追加し既存値を固定 | 新schemaごとにold fixture + Host parser |
| CHECK-07 | managed clean install/cancel/restart、opaque登録、resolver経由G8同一hashまで実測 | side-by-side更新、失敗rollback、参照保護 |
| CHECK-08 | 単一4.5.9だけ。新旧保存互換は未実測 | revision分離、実.blend比較 |

## 3DS-5b software GUI runner互換性

Blender 4.5.9のX11/OpenGL経路はXvncのGLXに必要なcontext extensionが無く起動できなかった。
Wayland環境変数を残すと個人の実Waylandへ接続したため、sessionでは`WAYLAND_DISPLAY`を空に固定した。
system Mesa Lavapipe ICDを明示したVulkan経路では`background=false`、autoexec無効、backend `VULKAN`、
renderer `llvmpipe`を実GUIから取得できた。これはsoftware表示の互換性でありGPU対応の証拠ではない。

systemd userの一部kernel保護propertyは対象環境でunit起動時に`218/CAPABILITIES`となったため採用しなかった。
採用したunitは`NoNewPrivileges`、`PrivateNetwork`、`RestrictAddressFamilies=AF_UNIX`、
`ProtectSystem=strict`、`ProtectHome=yes`、MemoryMax 8 GiB、TasksMax 128を持つ。追加mountの
`/data1tb`は`ProtectSystem`/`ReadOnlyPaths`だけでは書込可能だった実測を受け、Landlock ABI 3以上の
write allowlistを必須にした。同じhelperからallowlist外`/data1tb/mf-landlock-escape`への作成はerrno 13、
許可rootへの作成は成功し、AF_INET socketはerrno 97だった。RFBはmode 0600 Unix socketだけでTCP listener 0。

Landlock導入probeのsource sessionは0.584秒でready、Memory 540.6 MiB（peak 571.4 MiB）、94 tasks、
Blender childは`NoNewPrivs=1` / seccomp mode 2だった。候補bundle 0.28.3でも実RFB 1280x720へ接続し、
click + Shift+D + Enterでcubeを複製して保存した。revision 1→2、objects 3→4、meshes 1→2、
triangles 12→24、vertices 8→16を独立validatorが確認し、停止後unit inactive、socket/process 0。
noVNC/gateway、opaque iframe、再接続、idle、disable/revocation、GPU/Cyclesは **NOT TESTED**。

## 3DS-0判定

baseline fixture、互換性表、source/installed/Host/GPU状態、既存G8実process回帰を取得したため
3DS-0のexit gateを満たす。3DS-1からruntime resolverとread-only設定診断を実装する。
Web Blender、scene/revision、GLB viewer、材質、OpenCode制作、runtime lifecycleは
**NOT IMPLEMENTED / NOT TESTED** のままであり、3DS-0成功をそれらの証拠へ読み替えない。

## 3DS-1 runtime resolver / 設定診断

versioned registryとresolverをMediaForge側へ追加し、既存4.5.9 runtimeを
`legacy-blender-4.5.9`として登録した。registryは258 B / mode 0600で、保持するlocationは
`legacy`だけであり、`/data1tb`、`/home`、`/tmp`を含まない。symlink registry、managed root脱出、
壊れたstamp/executable/manifest/trusted workerはfail-closedにする。active runtimeが将来別版に
変わっても、既存G8は正確に4.5.9のready runtimeだけを選ぶ。

実Uvicorn `127.0.0.1:9164`でstatusは`ready`、active/G8は同じopaque ID、4検査はすべてtrue、
fingerprintは`c5015f19e7a0fb8228e426386d0e7aee19be7501852d814da1c08c0f163ebcd9`だった。
resolver経由でbaselineと同じ796 B cubeを加工し、job
`job_23d828f247fa420995b451d07b0a5246`は1.462秒でsucceeded。ZIPは44,292 B、SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`で3DS-0と同一、
entry 3件、終了後work entry 0 / Blender child 0だった。

standalone ChromeでSettingsのready/missing、診断展開、日英切替を確認した。320 pxでは
clientWidth/scrollWidthとも320、更新ボタン高さ39 px、最終console/page/HTTP errorは0件。
基本runtimeと未導入Web操作packは別表示され、missing時も画像機能を利用できる旨を表示した。
実ControlDeck workspaceは未認証ブラウザが`/login`へ遷移したため、installed opaque iframeでの
3DS-1操作は **NOT TESTED**。lifecycle操作、Web Blender、scene/revision、viewer、材質、
OpenCode制作、GPU Blenderも **NOT IMPLEMENTED / NOT TESTED**。

## 3DS-2a durable install / cancel / restart

Blender専用operation journalを画像model operationとは別table/typeで追加した。状態は
queued→preflight→downloading→verifying→installing→probing→ready、終端failed/canceled。
ブラウザはinstallまたはopaque operation IDのcancelだけを渡し、URL/path/version/commandを
指定できない。公式manifestのexact size/hash、展開member/size/path/link/device制約、空き容量、
実Blender probeを通過したcandidateだけをmanaged rootへatomic配置してregistryへ登録する。
partialはETag一致Rangeだけ再開し、stagingはcancel/失敗で除去する。配置とregistry更新の間で
停止したjournalも再probeして完了できる。

正規377,929,956 B archive（SHA-256 `dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d`）を
ローカル配信源にしたclean installは25.659秒、managed filesは1,605,023,227 B。probeは
Blender 4.5.9 / Python 3.11.11 / background / GLTF import/exportすべてtrue、registryは282 B /
mode 0600 / raw pathなし。そのruntimeによるcube G8は1.312秒、ZIP 44,292 B / SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`でbaselineと同一だった。

同archiveを8,388,608 Bでservice停止するとjournalはdownloadingのまま残り、再初期化でqueued、
`Range: bytes=8388608-`と同一ETagで再開し25.546秒後ready。別実測cancelはcanceled、partial
8,388,608 Bを保持、staging/destinationなし、runtime unavailableだった。Chromeでは日英の
未導入表示、exact catalog/license/容量、導入button、320 px client/scroll 320、button 39 px、
console/page/HTTP error 0件。update/switch/repair/removeと実Host opaque iframeは
**NOT IMPLEMENTED / NOT TESTED**。

## 3DS-5a Web操作pack管理

Web操作環境を基本Blenderと別のimmutable packとして管理する。TigerVNC 1.16.2の
[公式generic Linux archive](https://sourceforge.net/projects/tigervnc/files/stable/1.16.2/)と、
noVNC 1.7.0の[固定commit](https://github.com/novnc/noVNC/tree/63107bd06d9e1f6136ff21aeda8cd62cbf0d433e)を
HTTPS URL、archive byte数/SHA-256、展開root、必須file SHA-256、licenseで固定した。
TigerVNCは15,042,988 B / SHA-256
`5b70c84baefc09a030cfc78315c34ccb55b2a0dde4092b7da67a1962c5f0dea6`、noVNCは
726,728 B / SHA-256 `b1003a11b6e6e8d8f7f5e5586daae7f8ca651d8aee0aa155ff9ac841c48f52c6`。
symlink/device/FIFO、重複・脱出path、member数、展開量、hash不一致を拒否し、候補を実行probeしてから
no-replaceで公開する。ブラウザ・CLIは`web_install`だけを指定し、URL/path/commandを入力しない。

隔離data rootの実Uvicornで公式2 archiveを取得したoperationは6.153秒でready。TigerVNCは165 member /
35,067,968展開B、noVNCは244 member / 2,471,032展開B、pack実体は283 files / 37,539,247 B、
staging entry 0だった。同梱Xvncを1280x720 / depth 24 / security none / loopback限定で実起動し、
listenはIPv4 `127.0.0.1` とIPv6 `::1`だけ、`RFB 003.008` bannerは2.207 ms、停止後process 0。
これはsoftware display probeであり、認証済み製品sessionやGPU GUIの証拠ではない。

実ChromeのSettingsは「利用できます（ソフトウェア表示）」、TigerVNC/noVNCの版・license・15.0 MBを
表示した。mobile emulationはinner/client/scroll widthがすべて320、browser error 0。0.28.2 bundleは
31,447,404 B / SHA-256 `04d28d0293dc249d1c2dc42e328d2ccf379d7ed184782d334dd0f37328f16759`、
packaged doctorは`ok / 0.28.2 / packaged=true`。packaged実processも既存packをready、path token 0と判定し、
同じ320px/browser結果だった。focused 172件、full 928件PASS / 既知warning 1件 / 82.35秒。

切断中partial保持・cancel・fresh retry、archive改ざん/脱出/link/重複は自動testで確認した。
systemd user隔離runner、Blender GUI保存、RFB gateway/noVNC接続、再接続、idle/disable/revocation、
実ControlDeck opaque iframe、GPU GUIは **NOT IMPLEMENTED / NOT TESTED**。次は3DS-5b session runner。

## 3DS-5c RFB gateway / noVNC

noVNC 1.7.0の実行依存JavaScript 54 files / 579,832 Bを固定SHA-256で検査してから配信し、browserは
session IDだけで認証済みprivate WebSocketへ接続する。gatewayがowner/READY/unit/socketを確認してUnix RFBへ
binaryだけを中継し、1 sessionのcontrollerを1本に限定する。Host用protocolはbrowserのBridge nonceを既存Hostが
検証・除去した後の`binary`だけをupstreamで受け、standaloneは同一loopback Originを強制する。

sourceの実Chromeで1280x720表示、明示切断後の同一session再接続、noVNC入力、保存を確認した。保存結果は
515,688 B / SHA-256 `7afe139e407c33711b12e0989cf5492ed5294580535e809509ed76b969a43ee1`、
objects 5 / meshes 3 / triangles 36 / vertices 24、両validator passed。停止後process/socket/listener 0。
0.28.4 bundleは31,503,501 B / SHA-256
`9c1644a40962cf742f5f884203d0d2918d4bee0b195f0db515c82944cbfc9089`、packaged doctor成功、exact candidate rootの
fingerprint付きimport配信を確認した。同じgateway実装の候補processによる実RFB bannerは14.337 ms。実ControlDeck
opaque iframe、token rotation/revoke、disable、idle/crash
recovery、packaged Chrome、GPU/Cyclesは **NOT TESTED**。

## 3DS-5d lifecycle / recovery互換性

private session recordへ接続・切断・最終操作時刻とrecovery source IDを追加したが、既存recordはdefault値で
読める。既定は切断猶予300秒、controller idle 1,800秒で、上限付きserver設定だけが変更できる。timeout、
Blender unit消失、Host disable、15秒周期のHost credential再検査失敗はunitを停止し、working `.blend`を
正式revisionへせずowner-scoped復旧候補にする。候補を開くと新writerへbyte copyし、元候補はimmutableのまま。
Blender/GLB検証とcommitが成功した後だけ元候補をreleasedにしてbytesを回収する。

実Blender 4.5.9/Xvncで切断猶予を2秒へ短縮したsessionはreadyから5.270秒で
`blender_session_disconnected_timeout`となり、515,688 B / SHA-256
`7afe139e407c33711b12e0989cf5492ed5294580535e809509ed76b969a43ee1`を復旧候補に保持した。同候補を
新sessionで開いて保存するとrevision 6→7、working 515,496 B / SHA-256
`cddc910ddfe056542990e0d669d240f1bddbbc0642da75724c215e597d270d6d`、objects 5 / meshes 3 /
triangles 36 / vertices 24、Blender/GLB validator passedとなり、旧候補recordはreleased、旧rootは0。

別の実sessionをsystemd経由SIGKILLすると`blender_session_runner_lost` / recovery candidateとなり、修正後は
unit、session root、Unix socket、Xvnc/runner processが0になった。Host disable相当のprivate interruptは受付
2.397 ms、stopping→interrupted 91.9 msで、同じく候補を保持し残存resource 0。実Chromeではdesktopの日英
復旧ボタン/説明、390x844のdesktop案内、横scroll 0、browser exception 0を確認した。
exact codeのfull testは952 passed / 既知Starlette warning 1件 / 91.17秒。
0.28.5 exact bundleは31,509,192 B / SHA-256
`352efcfbf6f7ee3566ec530ea01ee7b76534c8bbe397d346bed0f72907d65693`、packaged doctor成功。exact packageでも
実Blender ready、interrupt/recovery、unit/root/socket/process 0を確認した。

実ControlDeck opaque iframe、10分超credential rotation、実Host revoke、GPU/Cycles、packaged Chromeは
**NOT TESTED**。
