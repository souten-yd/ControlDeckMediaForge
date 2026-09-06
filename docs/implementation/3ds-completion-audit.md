# 3D Studio 完了監査

Date: 2026-09-06
Status: PARTIAL / 初期提供の完了判定を撤回。設計・必須条件は縮小しない。

対象: PR #213のGOAL-01〜10と`g8-3d-studio-plan.md` §4 A〜F。
監査開始コードはmain `1f4392a2d426a742046d0c03c99272ffb5e41c87`。その後PR #246/247をマージし、
本監査でv0.28.17（target `4293d20`）の終端照合を受入後、v0.28.19（target `583fea1`）を
正式署名公開・標準updateしLibrary viewerをoverlayなしで受入した。さらにv0.28.20（target `c26f67d`）
の材質照明・新旧双方のcontext復旧をinstalled受入した。さらに0.28.23（target `22fc2b9`）を
署名公開・標準updateし採用前候補比較/破棄/採用/復元をinstalledで確認。
2026-09-06の現在稼働版は0.28.37/healthy（署名公開/consumer検証/標準update14.645秒）。
更新前後8テーブル全行/registry不変、real63-child Library paging/offset60 locale保持を
installed320/1280で再受入した。retryのactive切替実行は未確認。詳細はstatus/handoff。
0.28.26ではnative windowで比較入力・不変refreshのDOM保持と全比較/採用/復元を確認した。
新版の他操作の受入を旧版やcandidateの証拠から推定しない。
以前の個別実測は維持するが、条件の一部だけの実測から行全体を成功扱いしない。
下表の「未確認」は今回の監査で条件全体に対応する証拠を確定できていない意味で、コード不在とは異なる。

## 利用者ゴール別

2026-09-06 installed real paging追加: 通常Agent作成/編集と正規revision restore61回で
専用scene1件/63版を生成。synthetic DB挿入なし、既存scene/revision metadata全件不変。
実installed0.28.36の1280/320で初版sourceのchildren63を60→3→60→3、全ID集合/一意、
offset60で実Hostの日英通知/選択・load・session保持、横overflow0/page errors0を確認。
証拠 `/data1tb/mf-library-real-paging-installed-{320,1280}-20260906`。
生成データ `/data1tb/mf-library-real-fixture-installed-20260906/fixture.json`。
126 Asset/26,978,198 Bの実hash/size、provenance sidecar、復元bytes一致もread-only確認。
この専用scene/historyは保持。親60件超は従前source/bundle fixtureの証拠であり、
本runのinstalled parents0から親60件超を推定しない。言語入力はbrowser fixture。
GOAL-01の追加境界受入が完了したが、全体matrixはPARTIALを維持する。

2026-09-06 v0.28.36: 長いdetail titleの横overflowをcandidate実画像で発見し修正。
修正bundleの実Chrome日英320で親65/子63のpaging/英語fallback/dialog横overflow0を確認。
署名公開→consumer/Host trust検証→標準update25.868566秒。8テーブル全行/registry不変。
installed0.28.36でも実Hostからの日英通知・選択保持を1280/320で再確認。
大きなlineageは専用Storeのsynthetic fixture/standalone bundleであり、
installed Hostの60件超受入へ読み替えない。全matrix完了とはしない。

2026-09-06 live locale追加: Host汎用PR #293/294がmerge済み。本番Host frontendを3f71878へ
fast-forward/buildし、実8765→installed MF0.28.35で日英の動的通知を1280/320で受入。
選択source/offset0/filter/関連ID列/load/nonce/scene不変、page errors0。
言語入力はnavigator.language + browser languagechange fixtureで、実ブラウザ設定UIではない。
bridge eventとworkspace responseは実経路。証拠mf-library-live-locale-installed-{320,1280}-20260906。
60件超installed pagingの残件は維持する。

2026-09-06 Library追加: 専用source synthetic lineageで親65/子63の実HTTP/Chrome日英320を確認。
60/60→5/3→60/60、全128 ID欠落/重複なし。英語Validation空fallbackを修正・source再受入。
`/data1tb/mf-library-paging-20260906`。installed本番は最大children12件のみで、
この境界受入をinstalled60件超の証拠にはしない。実Host動的locale通知も残件。

2026-09-06 v0.28.35: PR #326 exact mergeから署名公開しconsumer/Host trust照合、標準update
16.54秒。package実Chromeでは日英320の旧版削除/再導入、旧版不在のGLB/backupを79.551秒で確認。
installed日本語1280/320・英語geometry probe1280/320とnative desktopで確認checkbox/active保護、
runtime不変を実測。英語の通常viewport変更直後はpointerがHost IFRAMEへ届きdialog未表示が再現。
追加の固定初期viewport英語1280/320は通常pointerで全pass。live resizeの証拠にはしない。
成功した別modeへ読み替えて解消済みとはしない。製品code変更なし、原因の確定は未完了。
本番旧版の実削除は実行せず、package専用rootの実削除と区別する。詳細はimplementation-status。

2026-09-06 PR #325 source追加受入: 日英1280/320の確認UI、日英320の実削除/同版導入、
旧版不在中のscene履歴/GLB描画/backup保存とZIP全entry照合を実Chromeで確認。
`/data1tb/mf-history-settings-20260906-r3`、104.143秒passed、localeはfixture入力。
再開/identity変更7 tests追加、全1125 passed。installed更新/署名releaseは次工程。

2026-09-06 candidate: 専用source実HTTPでproject-pinned inactive 4.5.9の確認付き削除、
同archive再導入、同scene GUI再起動を73.218秒で実測。scene/revision/全6 Asset関連ファイル不変、
active4.5.13維持。証拠 `/data1tb/mf-history-reinstall-20260906`。
日英browser/Library backup操作/確認journal再開matrix/installed署名受入は未実施。
これはscenario D全体の完了ではない。詳細はimplementation-statusのcandidate記録。

| 条件 | 確認済み証拠の範囲 | 判定と残件 |
|---|---|---|
| GOAL-01 共通Library | 署名installed0.28.29/30で画像/GLB/.blend filter、親子双方向移動、metadata移動中model read0、明示GLB表示、scene不変。0.28.36の実children63でpaging全集合、offset60で実Host日英通知と選択保持を1280/320で追加確認（browser言語入力fixture） | VERIFIED（共通Libraryの指定操作と子63件境界）。親65/子63の両側境界はsource/bundle fixture、installed親60件超とは区別。320px viewer背景scrollも0.28.30で修正・受入済み |
| GOAL-02 viewer | 署名installed0.28.19でLibrary→3D card、±XYZ回転・zoom両方向、逆操作差分0、320px、scene不変をoverlayなしで確認 | VERIFIED（利用者指定操作の範囲）。2026-09-06利用者確認によりwire/animationは必須から除外 |
| GOAL-03 設定管理 | 4.5.9/4.5.13共存/active切替/参照中削除拒否。隔離source日本語Settingsで実download更新、active削除拒否、未参照旧版削除、再導入、stamp退避からの修復と実Blender probe。installed0.28.31でdesktop/320pxの説明幅・横overflowなし・project参照削除保護を未変更scriptでも再確認 | PARTIAL: 完全空環境browser install、installed日英/lifecycle、失敗後再開とscenario Dの全条件を照合。前回単発pointer不達の原因は未確定 |
| GOAL-04 Web Blender | `.14-long/observations.json`: 621.451秒GUI、入力、保存revision 2→3、reload/reconnect | VERIFIED（この操作範囲）。credential refreshの証拠ではない |
| GOAL-05 OpenCode一巡 | installed0.28.26、実OpenCode同一run289.585秒でtyped剣→画像生成→材質→export→ZIP→配置、4制作Job成功、全長1.005m/加工後356 triangles | VERIFIED（この自然言語制作経路）。同じ剣での比較採用/GUI/復元はscenario Bへ残す |
| GOAL-06 既存画像比較採用 | 署名installed0.28.26で既存画像の比較/破棄/採用/復元、さらに同sceneで実FLUX.2画像生成→候補比較/破棄→採用3→4、dependency/parent/hash一致、Broker解放を確認 | VERIFIED（既存/生成画像のbase color比較採用の範囲）。全PBR channelやOpenCode制作一巡の証拠ではない |
| GOAL-07 やり直し | restoreとcrash/idle等の復旧保存。競合分岐救出をsource/package/installedの実Blender・browserで確認 | PARTIAL: 失敗工程だけの再試行の全条件照合。standalone candidate ID脱落はPR #246で修正済み |
| GOAL-08 grant配置 | 同runのGLB/生成PNG/manifest入りG8 ZIPを直前project grantで配置。receipt3件/実bytes/Asset/provenance hash一致、ZIP内部と元GLB hashも一致 | VERIFIED（manifest入りZIPを含む3ファイル配置の範囲）。復元後の再配置はscenario Bへ残す |
| GOAL-09 取消/回収 | Broker待機取消、133.122秒の実行取消、Host終端同期、session終了 | PARTIAL: 各経路のprocess/予約回収を対応する証拠へ紐付け |
| GOAL-10 Broker共存 | 稼働LLM中はwaiting、idle後はBrokerがLLMを退避して57.869秒画像生成 | PARTIAL: 音声を含む共存条件の証拠と非対応GPU GUIの条件付き扱いを照合 |

`.14-long`は`/data1tb/mf-3ds8-browser-0.28.14-long`、`.14-material`は
`/data1tb/mf-3ds8-browser-0.28.14-material`、`.15-texture-gpu`は
`/data1tb/mf-3ds8-texture-gpu-0.28.15`を指す。その他の実測値はimplementation-statusの
2026-09-06 installed lifecycle / v0.28.15 release記録に由来する。

## 必須シナリオ別

scenario Dの停止後A削除とproject pin保護の差について、base-plan §12とruntime設計§4.1に
履歴を保持する明示確認付きmanaged削除/同版再導入を定義した。既定の参照拒否と
active/Job/GUI/working-copyの保護は維持する。確認付き削除自体は実装・実機受入とも未完了。
受付保護の先行実装はsource実Blender+遅延Host fixtureで1.801秒exit0、Host待ち/slot待ちの
参照1と解除拒否、制作成功後参照0を確認。HTTP/installed/GUI durable参照の証拠ではない。
前sliceのB削除や0.28.34のproject拒否を、このA削除条件の成功へ読み替えない。

durable参照集計をmanaged/external previewへ追加し、managed削除経路をworker-thread化。
source実HTTP/GUIで34.140秒passed、ready時はsession1+working copy1、停止後0を確認。
全6 Asset/provenance bytesとscene/revision metadataは不変。GUI受付/削除commit間の排他と
確認付き削除は残件。今回active/project拒否も併存し、runtime削除自体は実施していない。

続くsourceでGUI queuedの版固定と通常/復旧working-copyのguard付きworker取得を実装。
copy threadをgateで待たせた実HTTPは/health200を0.003346秒で応答（状態setup_required）、
remove previewは待機、解除後session1+working1、実GUI停止後0。4.060秒passed、6ファイル不変。
確認付きの実削除commitとGUI同時開始の受入、正確な同版再導入は引き続き未完了。

v0.28.34（target f806f54609e34924086887744ae30d6852aec297）署名公開/consumer再取得、
標準update17.353秒/healthyを確認。package日本語1280/320の外部解除・reload非復活・再登録は
7.944秒exit0、外部5,580 filesのinventory不変。installedはlegacy登録なしのため
managed Settings日英/1280/320の削除保護とruntime不変を受入し、外部操作とは区別する。
証拠はimplementation-statusのv0.28.34記録参照。全D/Fの未確認条件は維持する。

2026-09-06 External追加: resolverの永続抑止/明示再登録（#317）に加え、
source private HTTP/WS管理操作と設定UIを実装。専用source日本語Chrome1280/320で
確認取消・登録解除・reload後非復活・再登録、active managed維持を5.973秒exit0で確認。
`/data1tb/mf-external-settings-browser-20260906`。外部5,580 filesのsize/SHA/mode不変。
project確認後変更拒否はunit fixture。installed Host/英語/実project参照browser拒否は
未検証であり、これだけでExternal全条件やscenario D全体を完了にしない。

2026-09-06削除追加: `/data1tb/mf-runtime-removal-resume-20260906/observations.json`。
専用source HTTPで旧4.5.9のGUI ready/停止後ともproject参照によりremove POST422。
未参照4.5.13だけ削除成功（1,167,187,993 B）、旧版/scene/revisions/全6 Asset filesの
実bytes size/SHA保持、GUI unit inactive/MainPID0、2.008秒exit0。
この領域に個別画像Assetはない。旧A停止後の削除はproject pin保護が拒否するため、
未参照B削除をA削除の成功へ読み替えない。External解除経路の実装差分も残る。

2026-09-06 scenario D追加証拠: source専用HTTP/実Blenderで候補4.5.13のprobeを
意図的に不合格にし、旧4.5.9のactive/実probe/GUI接続を維持。正常probe再試行で
新版ready/active後も同GUIは旧版にpinされた。67.985秒exit0。
`/data1tb/mf-update-probe-failure-final-20260906/observations.json`。
実RFB handshakeとAPI metadata/旧binary hashの照合であり、全Asset bytes保全、
ブラウザ操作、参照中削除/停止後削除、scenario D全体の受入ではない。

| 条件 | 残る照合・実測 |
|---|---|
| A clean環境/表示 | 全操作、320px、日英、既存画像がBlender不在でも利用可能な証拠。390pxだけで320px成功とはしない |
| B 制作一巡 | VERIFIED（再開/再試行を含む同一制作物）。OpenCode剣→既存画像2→3→新規生成/比較採用3→4→GUI入力保存6→7→第6版を第8版へ復元→元projectのrestored-exportsへGLB/PNG/manifest入りZIP配置。全8版不変、旧出力保持、新3 receipt/実bytes/manifest hash一致 |
| C lifecycle | 既存crash/idle/restart/expiry証拠は維持。競合candidateは保持だけを復旧完了としない |
| D 更新/削除 | 稼働A中にB導入、B probe失敗、A削除拒否、停止後Aのみ削除と資産hash保持、External解除、容量不足/中断を個別照合 |
| E GPU/長時間 | installed0.28.30の644.700秒CPU queue fault injectionでchild refresh4件/元期限後取消/終端一致。さらに既存GUIの480.340秒RFB再接続・同一session660.433秒継続・実入力保存を672.072秒runで確認（PR #293）。自然な120秒超演算・setup自身の10分超credentialとGPU組合せ評価は残る |
| F release | 署名公開/update/改ざん拒否証拠は維持。rollbackは候補health成功後の例外注入であり、migration失敗や自然なhealth不良の証拠へ読み替えない。clean install等も個別照合 |

GPU GUIは設計§4とCHECK-03の条件付き提供に従いsoftware-onlyを正直に表示する。
2026-09-06の署名packaged0.28.32/専用空Blender領域では、Settings実クリックから
基本環境を導入し、downloading中page.close→新pageで同ID/進捗復元→58.794秒ready、
実4.5.9/glTF入出力probeとreload後readyを確認した。
証拠 `/data1tb/mf-clean-packaged-browser-0.28.32-20260906/observations.json`。
これはstandalone packageの初回導入であり、installed Host iframe・画像生成・G8 ZIP・
web pack/GUIを含むscenario A全体の成功には拡大しない。
同じ専用package/dataの続行ではSettingsのweb pack実導入、cube import、Blender4.5.9の
実RFB画面表示と破棄終了/プロセス回収を確認した。初回試験のopen操作不足による失敗後、
同sessionへ再接続して成功。証拠 `/data1tb/mf-clean-web-pack-{browser,resume}-0.28.32-20260906`。
これはsoftware表示。画像生成/G8 ZIP/installed Host clean installはまだ未確認。
続く同じ専用package0.28.32のG8実HTTPでは、同cube GLBからJob成功/ZIP44,745 B、
3 entriesのsize/hash/CRC、Provenanceと元素材の対応、PNG、GLB、12 trianglesを照合した。
証拠 `/data1tb/mf-clean-g8-package-0.28.32-20260906/observations.json` と実ZIP。
元scene/GLB不変。このrunだけではBlender不在時画像実行/Library・Host初回導入は未確認。

2026-09-06追加: signed0.28.33の専用data/空Blender registryで実画像生成とLibrary表示を確認。
証拠 `/data1tb/mf-no-blender-image-0.28.33-20260906`。既存MF画像venv/HF cacheを明示流用し、
Host診断用service credentialから実HTTP/Host Job/Brokerを通す。449.484秒、FLUX.2-klein、
PNG256x256/45,160 B、provenance/output hash一致、Blender status前後不変。
Host/local succeeded、gpu0 lease activate/renew36/release、released receipt、worker終了を照合。
日本語320px実ChromeのLibrary画像1件を目視確認。全runtime空のclean installや通常Host
初回認証・セットアップはこの専用環境から推定しない。scenario A/F全体はPARTIALを維持。
PR #294でsetupの隔離source HTTP/低速archive fixtureを実行。631.247秒取消、652.011秒再導入ready、
実Blender4.5.9/glTF入出力probe成功、終端2 operation/空stagingを確認した。
実archive/hash/展開は実物だが転送はfixture。実Host認証/外部回線/設定browserの残件は閉じない。
GOAL-02の証拠は `/data1tb/mf-viewer-six-axis-library-installed-0.28.19-20260906/observations.json`。
通常Chrome/AMD内蔵GPUであり、R9700/software GPU描画や実mobile touchの実績ではない。
viewer release gateの日英切替・mobile入力・model切替memory回収/context lossの再照合は残る。
比較paneのtextureなし/ありcontext復旧とclose時context解放は0.28.20で追加確認した。
証拠 `/data1tb/mf-material-compare-installed-0.28.20-{old,current}-20260906/observations.json`。
これはbyte単位のheap/VRAM回収や全model切替回帰の証拠ではない。
Eevee/Cycles probeをGPU GUI動作と見なさず、CPU/画像/LLMとの組合せ評価を別々に記録する。
credential更新は**失効前**に行う要件であり、失効tokenからの自己再発行は要求しない。

以前の監査時、Host child token TTLは600秒、MediaForgeのrefresh marginは120秒、
scene worker timeoutは180秒。単一workerの132秒維持ではrefresh条件へ届かない。
実Host DBを`mode=ro`で読み、`audit_logs`の`username=addon:media-forge`かつ
`action=addon.runtime.job.credential.refresh`を検索した結果は0件。
これは現在残る監査記録の観測であり、削除済み履歴まで含めた不実行の証明ではない。

2026-09-06 installed0.28.30再試験では、通常TTL/timeoutのまま644.700秒のqueue fault injectionがexit0。
後半4 childの期限前refresh監査success、615.630秒の元期限後cancel、5 succeeded/1 canceledの
Host/local終端一致と全terminal_sent、停止した4子process消失、全10生成asset bytes/hashを照合。
証拠`/data1tb/mf-credential-refresh-installed-0.28.30-20260906/events.json`。Host/MF PID不変。
上記0件は過去監査の観測であり、今回の4件successを含む現在の総数ではない。
人工的なqueue待機を自然な長時間演算やGUI/setup自身のrefreshへ読み替えず、scenario E全体はPARTIAL。

v0.28.16 installedで既定TTLのqueue fault injectionを実行したが、Host到達性喪失/Host再起動により
更新開始前にfailed。retry1は251.002秒までrunning、retry2は150.297秒で6件すべて
`host_context_lost`。retry2のHost DBはinterrupted、local outboxは未送信のまま、refresh監査0件。
成功条件は未達。まず正規identity復帰時の終端再送/Host履歴照会の欠落を解決する。
Host履歴読取は別PR ControlDeck#275（merged `40f1bc0`）で追加し、隔離した別processの実HTTPで
interrupted読取200/別Job403/refresh404/update404を確認した。installed Host適用とMediaForge
outbox再送は未確認。新しいAgent Job subjectから旧childのauthorityを無断で取得しない。
続くHost #276（merged `dac519b`）で終端専用reconcileを追加し、v0.28.17 sourceからの
実HTTP outbox再送を確認した。別core processの再起動・再照合でlocal Job2件は増えず、
Host interruptedとの差異はsent=false、active targetへの適用はsent=trueを保持。
証拠`/tmp/mf-terminal-http-1ppzav37/observations.json`。これは終端fixtureのmanager→Host HTTPであり、
installed Agent経路・GUI表示・自然な長時間制作・600秒超refreshの不足は解消したとは扱わない。
v0.28.17署名公開・標準update後には、full packaged Agent HTTPとinstalledの過去failed6件の
status/cancel/status18回を確認した。Host interruptedとの不一致をsent=falseのまま保持し、
Job/asset/scene/revision件数不変。installed証拠は
`/data1tb/mf-0.28.17-installed-terminal-retry1-20260906/observations.json`。
GUI表示と長時間refreshは、この終端fixture受入から成功へ読み替えない。
v0.28.17の再試験も225.185秒でMediaForge停止/再開に遭遇しFAILED。全6件のHost/local終端一致と
sent=trueは確認したが、refresh監査は各0件。証拠
`/data1tb/mf-credential-refresh-installed-0.28.17-20260906/events.json`。試験がrestartを要求したものではなく、
要求主体は未特定。約11分の無再起動枠を調整して再試験する。
詳細はhandoff/status、証拠は`/data1tb/mf-credential-refresh-installed-0.28.16-retry2/events.json`。

## 今回発見した具体的なコード差分

2026-09-06 source材質retry追加受入: 実生成済みPNGを専用Storeへ通常importし、
typed cube作成→材質workerの対象名fault→元requestのretryを実Blender4.5.9で実行。
失敗時のscene/版/既存Asset bytes・provenance不変、manager再作成後のretryでだけ新2素材/第2版。
元画像/形状Job全field不変、画像generation/edit Job0、新Jobは材質2試行だけ、
同じ画像dependency ID/hash、runtime/working/staging回収を2.386秒exit0で確認。
`/data1tb/mf-material-retry-source-20260906-final/observations.json`。
Host controlはfixture、画像生成は過去の別runであり、このrunでの生成完走ではない。
installed/HTTP/browser/全retry条件は残す。GOAL-07の全体完了は主張しない。

### retryが現在のactive Blenderへ変わる（2026-09-06 / main e3c19a2）

scene.createのretryは元Jobのruntime pinを持つが、取得時にresolve_activeで再選択していた。
2 negative testsでactive変更後の別ID実行と元登録不在時のfallbackを再現し、
旧試行のruntime ID/version/baseを取得guard内で再検証・保持するよう修正した。
source実Blenderでは待機cancel→manager再作成→active4.5.13→元4.5.9でretry成功、参照0。
`/data1tb/mf-retry-runtime-pin-source-20260906-r3/observations.json`、1.547秒。
これはHost fixtureを使うdomain/process受入。installed/HTTP/browser、材質工程の失敗後の
成功済み画像再利用と全retry matrixは未確認。GOAL-07はPARTIALを維持する。

### 採用前の材質比較がない（2026-09-06 / main a1635c9）

`design-3d-assets-and-opencode.md` §4/5は「未保存preview」「前後比較して採用し、新revisionへ確定」を要求する。
現行`frontend/app.js`の`applySceneMaterial`は`scenes.material.apply`を直接呼び、結果後にsceneを再読込する。
`backend/mediaforge/scene_workspace.py`の`apply_material_binding`はworker結果をworking sourceへ移した直後に
`commit_working_copy`を呼ぶ。`openSceneCompare`は既存`sceneRevisions`の旧版とcurrentだけを受ける。
したがってこれは単なる実機証拠不足ではなく、設計された操作順序の実装不足である。
`tests/test_frontend_contract.py`の既存assertも直接apply呼出を要求しており、greenではこの不足を検出しない。

次の実装は3DS-6へ戻る。既存公開Agent material操作の意味を破壊せず、private workspaceに
検証済み候補のprepare / compare / adopt / discardを追加する。候補は正式revisionやLibrary成功assetとして
公開せず、owner/base revision/runtime pin・期限・容量制限を保持し、opaque handleでpreviewを読む。
adopt時だけ同じ候補bytesと依存を再検証してcurrent一致条件で一度確定する。discard/期限切れ/切断・再起動時は
currentを変えず候補資源を回収する。競合は明示エラーにし、再送で重複revisionを増やさない。
既存画像と生成画像の双方で「比較中と破棄後はhead/版数不変、採用後だけ+1、旧版bytes不変」を
実Blender・installed browserで確認するまでGOAL-06/3DS-6を完了に戻さない。

domain補完は`scene_material_preview.py`で実装し、隔離実Blender4.5.9で上記head/版数/旧版bytes条件を確認。
証拠 `/data1tb/mf-material-preview-core-final-20260906/observations.json`。ただしprivate transportと
未保存候補のブラウザ比較は未接続であり、installed操作の不足はまだ解消していない。
続くprivate WS補完は `/data1tb/mf-material-preview-transport-20260906/transport-observations.json`で
実TCP/Blender、別connection拒否、準備中/ready切断回収、定期expiryを確認した。認証はfixtureであり
installed Host認証/ブラウザの証拠ではない。standalone mirror/UIの不足は引き続き残る。
その後standalone mirror/UIを接続し、実Blenderとsource Chromeで未保存比較→破棄→採用→旧版復元を確認。
証拠 `/data1tb/mf-material-preview-ui-browser-final-20260906`。日英と320pxも確認したが、
installed Host/生成画像を含む制作一巡の不足まで閉じたものではない。

`frontend/app.js`のstandalone session POSTが`recovery_working_id`を落としていた。
通常startへ化けるため、そのIDを明示転送する。公開契約とHost実装は変更しない。
`scripts/3ds_standalone_session_transport_smoke.py`をHostのPlaywright環境から実行し、
Chromium→loopback HTTPで復旧start/通常start/save/stopの4 bodyをassert、browser error 0。
これは実ブラウザのtransport検証であり、HTTP記録器は本番backendではない。
この修正後の実Blender復旧とinstalled署名bundle受入は **NOT TESTED**。

別件として`acquire_recovery_working_copy`はcurrentとcandidate baseが異なると
`scene_recovery_conflict`を返す。上書き防止は維持すべきだが、競合candidateから別版を救出する
利用者経路をv0.28.16 candidateで追加・source/package実測した。private `scenes.recovery.fork`は
別SceneDocumentへ保存し、元head/candidateは維持する。実測と残件はhandoff/statusを参照。
baseを無条件に現行版へ付け替える修正はしない。
正式v0.28.16のinstalled opaque iframeでも、元scene13版と1,438,783 Bの候補を保持したまま
別sceneへ救出（0.978秒）し、画像依存/lineage/hash、再送同scene、browser error 0を確認した。
証拠は`/data1tb/mf-recovery-fork-installed-evidence-0.28.16/observations.json`。
これは競合救出の証拠であり、他の未確認条件を成功にしない。
