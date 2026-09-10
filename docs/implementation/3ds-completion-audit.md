# 3D Studio 完了監査

Date: 2026-09-09
Status: PARTIAL / 初期提供の完了判定を撤回。設計・必須条件は縮小しない。

2026-09-10 installed.69でsetupのブラウザ切断後10分超認証更新を追加受入。
mf-setup-host-long-installed-0.28.69-20260910、実Chrome repair→page.close→650秒診断registry flock。
同一操作のHost credential refresh1/success（audit23353）後、653.413秒でrepair ready/完全一致receipt。
journal committed/実generation/停止なし、独立Host GET succeeded、旧行/registry/両exe SHA/PID保持。
health22回1.067〜4.302ms。人工登録待ちであり自然な長時間制作ではない。
setupのこの条件は受入済み。GUI自身の長時間更新・期限切れ・全E/全故障matrix/全GOAL/A〜F/GAは未完了。

2026-09-10 PR482で.69署名公開/consumer/標準導入を受入。新journal列以外の既存値保持。
追加の実Chrome ja320正常repair/switch/restoreは26.402秒で成功、実4.5.9 GLB probe、
journal committed/停止要求なし/実generation一致、正常時の補足なしをstatus/DOMで確認。
3Host childの独立GET/receipt一致、旧行/registry/両exe SHA保持、Host/MF PID不変。
証跡mf-setup-host-installed-0.28.69-20260910。正常系であり中断回復・遅延取消・
再認証のinstalled異常系受入は残る。setup10分refreshは上記で追加受入。全GOAL/A〜F/GA PARTIAL。

2026-09-10 PR471〜479の公開journal/実体照合/rollback/startup回復/日英補足に対し、
source core再起動後の正規owner再認証を実Hostで追加確認。
`mf-publication-reauth-host-20260910`、実4.5.9 repair21.801秒ready後、終了transportだけ注入失敗。
別coreは認証前照合0、無認証WS拒否、新tokenによるstatus要求で0.173秒sent=true/完全一致receipt。
独立Host GETは新child running→succeeded。旧childのcanceled不一致は上書きせず、補足へ投影。
元専用data DB/registry/exe SHA保持、Host/稼働MF再起動なし。製品基準1752tests成功。
この短時間source成功をsigned installed/10分setup refresh/期限切れ/全Eの成功へ読み替えない。
署名配布/installed正常系は上記へ更新。異常系のinstalled条件は引き続き受入が必要。全GOAL/A〜F/GA PARTIALを維持。

2026-09-10 PR463の修復checkpointをsigned installed0.28.68で受入。
`mf-repair-registration-cancel-installed-0.28.68-20260910`、実Chrome repair→page.close、
診断flockで候補登録待ちを作り、previous旧inode/候補別inodeを実確認して正常Host cancel API200。
42.321秒で両canceled、旧両exe hash/inode/registry/旧DB行保持、専用stage回収/login失効。
独立DB/Host control/旧inodeを照合。Host固有取消理由のreceipt不一致は保持。
登録待ち中の取消復元の証拠であり、下記長時間試験の原因解決・失効rollback・refresh成功ではない。

2026-09-10 **installed0.28.67の長時間setup試験は不合格**。
`mf-setup-host-long-installed-0.28.67-20260910`、実Chrome修復受付→切断→診断registry flock待ち。
healthは603.645秒までhealthyだがrefresh0、約210秒でhost_context_lostを記録。原因未確定。
診断interruptで615.360秒ロック解放後、ready+host_context_lost/cancel1が残る不整合を観測。
元exit130/passed=false保持。fresh実Chromeで成功outboxの実確定結果をHostへ照合しJob終端、
独立audit exit0で旧行/registry/両exe hash保持/staging回収/login失効を確認。
回収成功を長時間認証更新の成功へ読み替えない。原因診断と公開中の認証喪失制御修正を優先する。

2026-09-10 setup Host連携を署名installed0.28.67で確認。実Chrome ja320 opaque iframeから
正式repair API→通常UI switch/restore、23.499秒成功、3Host childと完全一致receiptを独立確認。
別の専用repairでは正常Host cancel API200→実page.close→11.345秒で両canceled。
`mf-setup-host-cancel-installed-0.28.67-20260910`、旧DB行/registry/両exe hash・inode保持、staging回収。
Host固有取消理由のreceipt不一致は保持し、完全一致成功と扱わない。診断login失効、Host/MF PID保持。
先行sourceの650秒queue/refresh1→実Blender install成功670.669秒はsource限定の証拠。
installed setup10分超refresh/認証失効・再起動全matrixは未検証であり、全E/3DS/GA PARTIALを維持する。

2026-09-10 signed/installed0.28.57で自然長時間の画像工程を確認。
同専用panelのquality生成は待機約106秒→生成238.346秒→成功、native PID実観測163.032秒。
画像適用後のGLB内包image/元版hash保持、両Host成功/GPU renew23/releaseを独立確認。
証跡mf-natural-texture-quality-installed-0.28.57-20260910。人工遅延なし。
Eの制作画像工程の追加証拠。Blender CPU演算や今回OpenCode/10分refresh/engine品質の証拠ではない。
0.28.57の署名公開/標準update/DB保持は確認済み、全3DS/GA/EはPARTIALを維持する。

2026-09-10 texture候補も自然長時間成功に未到達。installed.56で2048角はresource_limit、
同sceneの1024角/qualityは120秒admission応答喪失でworker前失敗。Host Job/待機予約は診断で回収。
MediaForgeのadmission例外が所有Host終端を通知しない欠陥を修正、source→実Host HTTPで両failed。
全1392 tests成功。ただし不明request IDの自動回収、署名配布/installed修正受入は残件。
元診断exit1と手動回収を保持。自然120秒超/OpenCode/画像品質/engine成功には読み替えない。

2026-09-10 E自然負荷の候補を実測。installed.55の8高分割球+UVは2.133秒、
別作業で更新された.56の128bone/32剛体parts/3clips各25秒は6.950秒、両exit0/Host成功同期。
実GLBのskin1/128joints/3animationsを独立確認したが、両方exceeds_120_sec=false。
`mf-natural-uv8-installed-0.28.55-20260910` / `mf-natural-animation-installed-0.28.56-20260910`。
候補校正の証拠であり自然120秒超/refresh/品質/engineの受入ではない。全E/3DS/GA PARTIAL。

2026-09-10 installed0.28.55旧4.5.9 GUI中の新版4.5.13 update失敗→正常retryを追加。
`mf-update-failure-installed-0.28.55-20260910`: 候補probeのみpidfd SIGTERM、旧GUI/PID/全47scene/162revision/688hash保持。
正常update後の既定4.5.13でも同GUI4.5.9固定。元診断は最終registry配列順bytes assertでexit1、
独立auditは全登録identity/履歴/hash/プロセス回収を確認しexit0。両結果を区別して保持。
D-01/02のinstalled旧→新版差分は補完したが、全D/3DS/GA完了にはしない。

2026-09-10 scenario Dの[必須条件別対応表](3ds-runtime-evidence.md)を追加。
観測JSONを再読し、source/package/installedの範囲を分離。次の不足はinstalled旧→新版updateと
候補probe失敗→retry。逆方向exact installを同じ証拠にしない。
再導入のstarting応答だけで再編集成功とせず、後続の実RFB編集保存へ根拠を接続。
過去の全挙動再実行ではなく、全D/3DS/GA PARTIALを維持する。

2026-09-10 installed0.28.55実CDN download取消/再開: 正規API cancelで1,671,168Bのpartial/進捗/ETag保持。
通常repair再送後は同inodeの全archive/hash一致→実Blender probe/ready、
`mf-repair-resume-installed-0.28.55-20260910`、60.838秒/exit0。47scene/162revision/64hash/registry保持。
既定4.5.13/Host/MF PID不変、独立比較で正常cache/backup一致・partial/metadata/staging回収。
wire-level Range採取、process crash/電源断、重複asyncio task取消、今回browserは未検証。
取消flagによる通常中断/再試行の追加証拠であり、全D/3DS/GA完了にはしない。

2026-09-10 installed0.28.55修復cache改ざん: 正常archiveを退避しcopyだけ1byte反転、
正規repairはSHA不一致でfailed、不正cache削除/旧runtime・全scene/history保持。
正常cache復元→通常repair実probe/ready、`mf-repair-tamper-installed-0.28.55-20260910`、25.228秒/exit0。
47scene/162revision投影・旧版関連64hash/registry保持、既定4.5.13/Host/MF PID不変。
独立照合で正常cache復元/staging空/未終端操作0。取得済みcacheの改ざん条件をinstalledでも補完。
CDN通信中改ざん/物理ENOSPC/今回browser/全D/3DS/GAの完了にはしない。

2026-09-10 source修復容量失敗: free=0 fixtureを修復前/展開前に注入し、実HTTPでinsufficient_disk。
`mf-repair-capacity-source-20260910-r2`、11.120秒/exit0、8hash/scene/旧exe inode保持。
両失敗後の実Blender4.5.9 GLB入出力probe成功、独立照合でstaging空/未終端操作0。
unitではhash/容量2箇所の3ケースで旧環境保持→正常retryを確認。
物理ENOSPC・installed改ざん受入・全D/3DS/GA完了へ読み替えない。

2026-09-10署名0.28.55公開/再取得/実Host署名検証/標準update10.698秒healthy、DB/registry保持。
installedの停止済み4.5.9 repairをcache退避→実CDN転送→実probeで受入、58.081秒/exit0。
`mf-repair-download-installed-0.28.55-20260910`、47scene/162revision投影・旧版関連64hash保持、
既定4.5.13不変、旧版同SHAでinode更新、Host/MF PID保持。download health70samples p95 .967ms。
従来未検証だった停止後正常repairと、今回のchunk I/O修正の実CDN経路を補完。
installed重複取消/opaque browser/物理ENOSPC/全setup off-loop/全D/3DS/GAの完了にはしない。

2026-09-10 D中断経路修正: downloadの進捗DB/fsyncがloop threadで動く2 REDを再現。
chunk write/flush/progressとfsyncをowned threadへ移し、重複取消でも終端まで追跡。
`mf-download-io-source-20260910-r2` 0.993秒passed、実archive/実TCP health5.686ms、
3回取消→1MiB保持→Range再開→全377,929,956B/hash一致。通信/遅延fixture、導入probeではない。
署名配布/installed・実ENOSPC・全setup off-loopは未検証。全D/3DS/GA PARTIAL。

2026-09-10 source削除確認の再起動保持: 専用coreでdurable preflightへ到達後、HTTP client再接続、
owned SIGTERM/別core起動で同operation ID/全preview/ackを保持した実削除再開を確認。
`mf-removal-restart-source-20260910`、23.113秒/親exit0、両子はSIGTERM(-15)で終端。
同版再導入/既定復元、6hash/scene/revision保持、両PID/staging回収を独立照合。
初回preflight停止は明示fixture。installed browser/電源断/mid-rename crashは未検証。
全D/3DS/GA PARTIALを維持する。

2026-09-10 source逆順Job受付: 実remove guard中のscene.edit取得thread到達/pending→
削除後runtime_unavailable、Host fixture呼出0/新Job0/refs0。active別版へfallbackしない。
`mf-removal-first-job-source-20260910`、25.762秒/exit0、health1.637ms/setup_required。
同版再導入/同scene再起動/停止、6hash/履歴保持、既定復元/専用units回収。
実Host認証/Agent HTTP/OpenCodeやcreate retry/material逆順は未検証。全D/3DS/GA PARTIAL。

2026-09-10 source逆順GUI受付: 実remove guard内の明示thread gate中にGUI受付到達/pendingを確認。
health1.581ms、削除commit後422/scene_runtime_unavailable・GUI record追加0。
同4.5.9再導入/同scene再起動/停止、6files hash・履歴保持、既定復元/専用unit回収。
`mf-removal-first-source-20260910-r2`、25.340秒/exit0。installed/自然遅延/Job逆順は未検証。
unitの不在模擬だけから進んだsource証拠であり、全D/3DS/GA完了ではない。

2026-09-10 installed Job受付→削除再拒否: 新規専用recipeの実Host child受付後、
旧版inactive/live3（recipe_jobs1/GUI0）でstale確認をremove_changed、fresh確認をin_use拒否。
正規取消で両Job canceled/参照0、旧scene/registry/runtime保持、実削除なし。
`mf-job-removal-installed-0.28.54-20260910`、7.261秒/exit0。一時既定変更は復元済み。
逆順受付・重複取消や全D/3DS/GAの完了へ拡大しない。

2026-09-10署名0.28.54を公開/再取得/実Host署名検証し、標準update10.052秒healthy。
DB全table/Blender登録保持。installed実ブラウザのstale/live削除拒否とRFB描画・終了回収も確認。
`mf-stale-removal-after-ack-installed-0.28.54-20260910`、58.057秒/exit0。
重複取消回収修正の同梱を監査したが、installedで重複取消を発生させた受入は未実施。
全D/3DS/GAはPARTIALのまま。

2026-09-10 Job参照回収: 受付中の2/3回取消でlive参照が漏れる2ケースREDを再現し修正。
取得/解放のowned cleanupを反復shieldで終端まで追跡。source専用registry/実runtimeで
3回取消→参照0→実Blender通常制作成功/終端0、`mf-repeated-admission-cancel-source-20260910`。
Host応答はfixture、1.037秒/exit0。署名配布/installed同条件は未検証、全D/3DS/GAはPARTIAL。

2026-09-10 installed stale削除確認: Settings preview後に4.5.9 GUIを開始し、
履歴checkbox同意の前/後どちらの順序でも実削除buttonの古いfingerprintをremove_changed拒否。
新しいlive preview+ack=trueも正規APIでin_use拒否。削除operation追加0・旧runtime/制作物保持。
`mf-stale-removal[-after-ack]-installed-0.28.53-20260910`、両exit0、53.657/57.742秒login回収。
実RFB描画/両GUI終端、独立3 scenes/17 revisions/72files保持。Job受付や削除実行中の競合へは拡大しない。

2026-09-10 installed候補probe故障: 稼働4.5.13 GUI中の4.5.9 exact install候補だけpidfd SIGTERM。
probe失敗→正常retryの間、同GUI/runtime/runner PID・active executable hash/inodeを保持。
`mf-probe-failure-installed-0.28.53-20260910`、121.385秒passed/126.387秒own stop/exit0。
3 scenes/17 revisions/72files保持、旧版復元/候補/GUI/staging回収、Host/MF PID不変。
逆方向exact installの故障保護をinstalledでも補完。新版update、自然故障、全D/3DS/GA完了ではない。

2026-09-10 source故障追加: 未変更の実4.5.13 candidate probeだけをexact identity/pidfdでSIGTERM。
A4.5.9 GUI・旧版/scene保持、B update失敗→正常retryでactive4.5.13へ切替、既存GUIは4.5.9固定。
`mf-owned-probe-failure-source-20260910`、45.922秒/exit0、候補PID/専用GUI/staging回収。
従来のprobe script置換とは異なる故障条件。installed Hostや自然発生故障の証拠ではない。
最終コード-r2も46.297秒/exit0、旧7hash/元revision保持と候補/GUI/staging回収を再確認。
全1357 tests PASS。installed同条件・例外cleanup故障注入は未検証のまま維持する。

2026-09-10 installed別版並行導入: A=4.5.13実RFB GUI中にB=4.5.9をexact install。
B不在→verifying→readyを観測し、同A session/runtime/runner PID/実行file hash・inodeを保持。
`mf-parallel-runtime-installed-0.28.53-20260910-r2`、80.889秒passed/85.896秒GUI停止/exit0。
専用Bの英語Remove button実削除→同版再導入、3 scenes/17 revisions/72files保持、unit回収。
これは逆方向の別版導入であり、旧→新版update/active切替やB probe失敗の受入ではない。
全D/3DS/GA PARTIAL。導入中の手編集と完全な英語画面受入もNOT TESTED。

2026-09-10署名0.28.53公開/consumer署名検証/標準update10.240秒healthy、DB/registry保持。
installed実opaque RFBの4.5.9稼働中repairはin_use拒否、同GUI/scene/assets/実行file inode保持。
`mf-repair-protection-installed-0.28.53-20260910`、86.973秒/exit0、一時login/専用unit回収。
下記修復保護の稼働中拒否をinstalledでも補完。停止後正常repairはsourceのみ、
B並行導入/probe失敗や全D/3DS/GAが完了したとは扱わない。

2026-09-10修復保護追加: candidate公開時のlive参照欠落を2件REDで再現し、
受付guard/worker thread/取消追跡を実装。隔離source HTTP/実Blender4.5.9の稼働中修復は
実archive/候補probe後にin_use拒否、旧8files/scene保持、GUI終端回収、25.053秒/exit0。
`mf-repair-live-source-20260910`。installed未配布、A稼働中B導入/probe失敗の証拠ではない。
同診断-r2で停止後の正常repairも実行、46.009秒/exit0。1,168,332,002 Bを同版再構築、
directory inode変更・既存8files/scene保持。全1348 tests PASS、修正のinstalled受入は別途必要。

2026-09-10 scenario D再編集追加: 同じacceptance-swordを再導入済み4.5.9で実RFB編集・通常保存。
`mf-reinstalled-edit-installed-0.28.52-20260910`、66.978秒passed/67.040秒revoke/exit0。
第13→14版、mesh4→8/triangles236→472、独立GLB8 mesh nodes/1,761,820 B。
旧2 scenes/14 revisions/60files保持、専用GUI終端/unit回収。PNGから複製の見た目は未確認。
以下のAPI起動のみの不足をこの入力/保存/構造検査で補完。並行更新/probe失敗等は依然未完了。

2026-09-10 scenario D追加: installed署名0.28.52/日本語320px Settingsで、
inactive managed4.5.9を履歴確認付きで実削除し、同archiveから同版を再導入。
不在中にGLB表示/13版backup実download、28 entriesのsize/SHA照合。
2 scenes/14 revisions/既存60files保持、active4.5.13/legacy identity維持。
同sceneの4.5.9 GUI ready→stoppedとunit回収、59.982秒/exit0を確認。
`mf-history-installed-0.28.52-20260910-r2`。再開はAPI、RFB手編集は未実施。
この受入範囲のsource-only制限を解消。並行更新/probe失敗/競合等、D全体は未完了。

2026-09-10追加: 署名installed0.28.52/opaque frame/overlayなしで個別animation previewを確認。
`mf-animation-installed-0.28.52-20260910`、腕振り1秒/待機2秒、モデル画素変化、
速度/先頭戻し/pause、英語320px、元scene保持。GA-5の表示操作の追加証拠であり、
歩行制作、有機weights/IK、engine取込や残るA〜F全体の完了を意味しない。

2026-09-10追加: installed0.28.51の既定connected idle1800秒を実機完走。
`mf-default-idle-installed-20260910-r2`、exit0/passed=true、idle_timeout終端。
再接続でも入力時刻不変、8→16 meshesを別sceneへ回収、実GLB16 nodes/22216 B、
旧16ファイルhash保持、所有3 PID/cgroup/root/socket回収。GOAL-09の本条件を補完。
全lifecycle故障matrix・GPU競合・全3DS/GA完成を意味しない。

2026-09-10 lifecycle追加: installed0.28.49のready GUIで未保存手編集後にMediaForgeだけを
正常再起動。Blender3 PID/作業file bytesは保持し、同sessionで実描画/追加編集/保存を確認。
第7→8版、2→8 meshes、実GLB8 nodes、旧14ファイルhash不変、終了後process回収。
`mf-core-restart-edit-installed-20260910-r2`。HTTP healthy0.986秒は画面復帰時間ではない。
接続中既定idle1800秒や保存途中crash等の残件へ、この証拠を広げない。

2026-09-10追加: installed署名0.28.49で実OpenCodeの失敗診断→入力修正→新edit成功を確認。
専用fixtureの不在object ID失敗に対し、元Job/失敗Job/snapshotを取得後、正しい対象を
[2,0,0]へ移す一操作を実行。144.116秒/5 tools/exit0、実GLB座標・第2版・旧source保持を照合。
証跡 `/data1tb/mf-opencode-failure-repair-20260910`。GOAL-07の修正経路の追加証拠であり、
全失敗matrix、幾何品質/rig自動修正、C/GOAL-09のidle/restart等を完了にはしない。

2026-09-09現在: 署名0.28.45の公開consumer検証・標準update・実HTTP healthyを確認。
installed4.5.13の実RFBで手編集後、書込拒否→日英警告/旧bytes保持→次interval成功→
Blender子crash→別sceneへ2 meshes回収を確認。元scene/旧版hash不変、全process回収。
`mf-autosave-installed-20260909`、日英はbrowser languagechange入力fixture、
全1204 tests PASS。C/GOAL-09のidle/expiry/restart等の残件は保持。
以下の0.28.38等の版数/プロセスは各実測日の歴史的証拠であり、現在稼働版とは区別する。

2026-09-07 autosave追加: 隔離working copyへ120秒timer/atomic snapshotを実装。
source実HTTP/WS/Blender4.5.9で書込拒否→日本語警告/旧bytes保持→権限復元→次interval成功、
Blender子だけのcrash後に手編集1→2 meshesを別sceneへ回収、実GLB一致を258.512秒で確認。
`/data1tb/mf-autosave-crash-evidence-final-20260907-r2`。全1145 tests PASS。
この9月7日source試験当時のinstalledは0.28.38だった。署名配布/installed日英・4.5.13受入は
上記9月9日の別証拠で補完した。source試験自体をinstalled試験へ読み替えない。

対象: PR #213のGOAL-01〜10と`g8-3d-studio-plan.md` §4 A〜F。
監査開始コードはmain `1f4392a2d426a742046d0c03c99272ffb5e41c87`。その後PR #246/247をマージし、
本監査でv0.28.17（target `4293d20`）の終端照合を受入後、v0.28.19（target `583fea1`）を
正式署名公開・標準updateしLibrary viewerをoverlayなしで受入した。さらにv0.28.20（target `c26f67d`）
の材質照明・新旧双方のcontext復旧をinstalled受入した。さらに0.28.23（target `22fc2b9`）を
署名公開・標準updateし採用前候補比較/破棄/採用/復元をinstalledで確認。
2026-09-07の現在稼働版は0.28.38/healthy（署名公開/consumer検証/標準update14.189秒）。
更新前後8テーブル全行/registry不変、packageの日英320 Library回帰を確認。
素材失敗表示はinstalled日英native Chromeで旧版要求の実競合として追加受入。
別tabで第2版を確定後、旧bindingを製品比較helperへ直接渡して実WS拒否を確認し、
通常buttonの再試行・未保存比較・採用で第3版。元画像/旧版/既存scene不変。
証拠 /data1tb/mf-material-conflict-installed-ja-20260907-r3 と
/data1tb/mf-material-conflict-installed-en-20260907。
focus復帰で古いformはdisabledになるため、失敗要求入口はhelper呼び出しと明示する。
worker crashやAgent retry_job_idのinstalled受入、全失敗matrixは未完了。
以下の0.28.37実測は当該版の証拠として保持する。
更新前後8テーブル全行/registry不変、real63-child Library paging/offset60 locale保持を
installed320/1280で再受入した。2026-09-07に取消Jobのinstalled retryも追加受入。
実Host bridgeで既定4.5.9へswitchしても元4.5.13で実Blender成功、finally既定復元、
元Job/既存scene/revision不変。4.375秒、Host child succeeded/terminal_sent。
証拠 `/data1tb/mf-retry-installed-0.28.37-20260907/observations.json`。
材質故障後retryは追加のsource standalone実HTTP/WebSocket/Blender/browserで確認。
失敗後の両paneがLoadingのまま残る不具合を修正し、日本語320/英語1280で
旧版・元画像bytes保持、選択保持、再試行・未保存比較・明示採用をassertした。
証拠 /data1tb/mf-material-retry-browser-fixed-{ja-320,en-1280}-20260907。
本UI修正は0.28.38で署名配布済み。installed版競合受入は上記、worker失敗など全matrixは残る。詳細はstatus/handoff。
0.28.26ではnative windowで比較入力・不変refreshのDOM保持と全比較/採用/復元を確認した。
新版の他操作の受入を旧版やcandidateの証拠から推定しない。
以前の個別実測は維持するが、条件の一部だけの実測から行全体を成功扱いしない。
下表の「未確認」は今回の監査で条件全体に対応する証拠を確定できていない意味で、コード不在とは異なる。

## 利用者ゴール別

2026-09-07 installed0.28.38 default disconnect grace追加:
実noVNC/RFB Connectedとserver接続時刻を確認し、通常Close view onlyで切断。
既定300秒を短縮せず、猶予中はunit/working/session参照を維持、302.270秒で
disconnected_timeout終端。3 PID/cgroup/root/socket回収、durable参照全0、
450,236 B候補と同hashの別scene初版確定、元scene/候補bytes不変。
最終証拠 /data1tb/mf-disconnect-grace-cleanup-installed-20260907-final。
手編集/描画品質/接続中idle1800秒/GPU予約の証拠へは広げない。

2026-09-07 installed0.28.38 GUI child crash追加:
自分の新sessionのcgroup/executableを照合したBlender PID938903だけをPID fdでSIGKILL。
5.266秒でrunner_lost、3 PID/cgroup/root/socket回収、durable実行参照全0。
450,236 Bのcandidateと同hashで別scene初版を検証済み確定、元scene/候補bytes不変。
証拠 /data1tb/mf-gui-child-crash-cleanup-installed-20260907。
手入力/RFB/GPU/idleの証拠ではない。保存競合の証拠と合わせても全C/GOAL-09はPARTIAL。

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
| GOAL-04 Web Blender | `.14-long`は621.451秒保持/reconnect。実形状変更は`mf-sword-ui-flow-gui-canvas-0.28.28-20260906`の4→8 meshes・保存第7版、復元第8版で確認。`.30` RFB更新も同sessionで編集保存成功 | VERIFIED（保存済み編集/再接続）。longのキー送信と版増加だけを形状変更の証拠にはしない。詳細は[lifecycle証拠表](3ds-lifecycle-evidence.md) |
| GOAL-05 OpenCode一巡 | installed0.28.26、実OpenCode同一run289.585秒でtyped剣→画像生成→材質→export→ZIP→配置、4制作Job成功、全長1.005m/加工後356 triangles | VERIFIED（この自然言語制作経路）。同じ剣での比較採用/GUI/復元はscenario Bへ残す |
| GOAL-06 既存画像比較採用 | 署名installed0.28.26で既存画像の比較/破棄/採用/復元、さらに同sceneで実FLUX.2画像生成→候補比較/破棄→採用3→4、dependency/parent/hash一致、Broker解放を確認 | VERIFIED（既存/生成画像のbase color比較採用の範囲）。全PBR channelやOpenCode制作一巡の証拠ではない |
| GOAL-07 やり直し | restoreとcrash/idle等の復旧保存。競合分岐救出をsource/package/installedの実Blender・browserで確認 | PARTIAL: 失敗工程だけの再試行の全条件照合。standalone candidate ID脱落はPR #246で修正済み |
| GOAL-08 grant配置 | 同runのGLB/生成PNG/manifest入りG8 ZIPを直前project grantで配置。receipt3件/実bytes/Asset/provenance hash一致、ZIP内部と元GLB hashも一致 | VERIFIED（manifest入りZIPを含む3ファイル配置の範囲）。復元後の再配置はscenario Bへ残す |
| GOAL-09 取消/回収 | Broker待機取消、133.122秒の実行取消、Host終端同期、session終了。installed0.28.38保存競合で5.831秒failed、3 PID/cgroup/root/socket消滅・durable参照0・候補から別scene確定を追加確認 | PARTIAL: 他終端原因のprocess/予約回収を対応する証拠へ紐付け |
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
| C lifecycle | [原因別証拠表](3ds-lifecycle-evidence.md)へ照合。installedのautosave書込失敗/再試行→child crash、署名token expiry、既定connected idle1800秒で手編集2/2/16 meshes回収とprocess cleanupを確認済み。2026-09-10に復旧3 revision/22 Assetsの現在DB/hash/実GLBを再照合。定期autosave未実装という旧記述は撤回。全Cの最終照合は継続し、原証跡に記した接続経路・入力効果等の限界を保持 |
| D 更新/削除 | [D-01〜12対応表](3ds-runtime-evidence.md)へ原証跡を照合。installedの履歴保持削除/再編集、GUI/Job参照拒否、cache改ざん/取消再開、旧→新版update/候補失敗retryまで確認済みの範囲で整理。旧→新版runのcleanup assertion exit1と独立audit exit0を区別。D-06/07/09/11のsource/packageとinstalledの差分は残る。全DはPARTIAL |
| E GPU/長時間 | installed0.28.30の644.700秒CPU queue fault injectionでchild refresh4件/元期限後取消/終端一致。既存GUIの同一session660.433秒継続・実入力保存（PR #293）。installed0.28.57で制作画像の自然生成238.346秒→同panel材質/GLB、両Host成功/GPU renew23/releaseを追加確認。setup自身の10分超credentialとGPU組合せ評価等は残る。画像工程をBlender CPU演算や全Eの完了には読み替えない |
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
