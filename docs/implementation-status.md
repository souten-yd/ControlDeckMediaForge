# Media Forge implementation status

## 2026-09-10 setup admission I/O boundary

base PR448 merge342e2d7、ux1/3d-setup-admission-offloop。
BlenderRuntimeManager.requestを追加、HTTP/WSのinstall/web_install/update/repair/switch/cancelを接続。
既存同期helperは共通prepare/launchへ分離して互換保持。実catalog/registry/DB受付はworker thread、
実行task生成はloop側。同一要求の照会/作成をworker内lockで直列化、二重作成を防ぐ。
要求3回取消でもowned admissionを完了してdurable操作をspawnし、manager.stopも受付を待つ。
公開入力/結果、trusted source、既存state/取消/既定版選択policyは維持。

tests/test_blender_admission_io.py: 修正前29884終端exit1/7failed、HTTP6経路のloop I/Oと新受付未提供を検出。
修正後関連37passed/6.21秒、重複受付追加後関連107passed/24.65秒。
最終focused14passed/2.97秒はHTTP6/WS6/3回取消+停止/同時重複1journalを検査。
全test70963終端exit0/1555passed/既知2warnings/153.99秒、viewer43ms/生成JS差分0、Node5pass。

外部 `/data1tb/mf-admission-offloop-source-20260910.py` を
`PYTHONPATH=backend:. .venv/bin/python`で実行、31236終端exit0/22.343秒。
専用dataのみ、既存固定4.5.9 archiveをコピーしてhash検証。元cache/既存runtime/稼働Hostに変更なし。
証跡 `/data1tb/mf-admission-offloop-source-20260910/observations.json`。
実TCP install受付を明示thread gateで保留中、別HTTP /healthは1.524msで200、受付requestは未完了。
解除後operation blenderop_4789dcedce864fa9add9a9f946fd8efaを1件作成→ready。
実archive377929956B/SHA dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d、
6510members/1168332002展開bytes、実Blender4.5.9/Python3.11.11 background/glTF export/import成功。
受付workerとloopのthread別、元cache hash保持、専用core終了。
受付待機はfixture、archive/展開/probeは実物。remote download/installed/Host認証試験とはしない。

NOT TESTED: 新受付の署名配布/installed UI、実行中全I/O、exact/removeの重複取消全条件、setup Host credential、全3DS/GA。
稼働.64/MF1768792/Host1384554を変更しない。次: gate→通常merge→署名導入とHost所有権の残件。

## 2026-09-10 v0.28.64 signed / installed status projection

PR447 merge/tag対象de4a269d8ef6f1381313e20319082dfad6da17d3。
exact checkout `/data1tb/ControlDeckMediaForge-release-0.28.64`でbuild47424終端exit0、
PyInstaller6.22.0/Python3.12.3/log13.942秒。artifact31587097B、
SHA256 659f5ac7bd1d874eda4e2e72b143d542886e60306f9715cdc5d0c07fb9db0cbd。
外部audit exit0/203entries、状態投影3関数のexact source/packed code一致とoff-loop同梱確認、
旧schema/制約/worker/mobile UI保持、packaged doctor ok/0.28.64。
証跡 `/data1tb/mf-0.28.64-build-20260910/verification.json`、package mf-0.28.64-package-rgi9z4nq。
既存publisher key/既存bundle-build venvで署名・自己検証exit0。公開42053終端exit0/4assets uploaded。
公開完了後download5242を開始、終端exit0。初回.63のupload競合を繰り返していない。

外部mf-0.28.64-install.pyをHost診断venvで実行、39815終端exit0。
公開4files/build一致、Host trusted署名検証、idle/全SQLite backup後に標準update。
backup `/data1tb/mf-0.28.64-update-4sw67q63`、10.066秒healthy、全DB table/registry bytes保持。
Host PID1384554不変、MF1768792、実exe SHA505ee5ef5a14fa30d784606f609147feddf2ca0c7d995d42d994b2942aff4d40。
実配信schema/exact source一致。旧.62実行bundleのみ標準保持2で整理、.63/.64/data/runtime保持。
旧実行bundleは公開署名releaseから再取得可能。モデル追加/Blender更新/Host再起動なし。

installed UIはscripts/3ds_settings_protection_installed_e2e.pyをHost診断venvで
--expected-version 0.28.64 --initial-width 320 --locale ja/en --headless
--require-readable-layout --require-touch-targets --require-history-confirmationで検査。
証跡 `/data1tb/mf-settings-status-installed-0.28.64-{ja,en}-20260910`。
日本語95441/英語61273とも終端exit0。source/HTTP overlayなしの実Host opaque iframe。
両言語でboot/明示状態照会/両managed preview/既定off確認を検査、横overflow0/buttons44px、
errors0/runtime state全体不変、専用login失効。削除は実行しない。
これは正常なinstalled状態取得であり、installedへ遅延fixtureを注入した試験ではない。
全setup I/O/credential refresh/全GOAL/A〜F/GAはPARTIALのまま。

## 2026-09-10 v0.28.64 preparation

PR446 merge f0afdb1790a2c1053e9b8c1be0b84e498e2c3db2からux1/release-0-28-64。
addon/core版数とrelease noteを更新。全test67891終端exit0/1541passed/既知2warnings/149.01秒、viewer44ms/差分0、Node5pass。
外部mf-0.28.64-audit.py/install.pyを準備しpy_compile成功。auditへ状態投影3関数の
exact source/packaged code比較とto_thread/shield同梱検査を追加。準備は実行成功ではない。
標準更新は全4公開files一致/Host署名/idle/全DBbackup/実exe/配信schema/保持検査を維持。
保持2による旧.62実行bundleだけの整理を事前通知。制作data/runtime保持、Host再起動なし。
現在.63、.62/.63を保持。次: full終端→commit/push/通常merge→exact build/署名公開/導入。
NOT TESTED: .64公開/consumer/導入/installed状態経路、setup認証/全3DS/GA。

## 2026-09-10 runtime status I/O boundary

base PR445 mergebc3d714、ux1/3d-runtime-status-offloop。
長時間setupの照合中にblender_runtime_partがasyncのworkspace初期化/明示状態/standalone HTTPから
同期catalog/registry/Web pack/DB検査を直接呼ぶと確認。状態取得にもlegacy登録書込がある。
同期投影をworker threadへ移し、繰り返し取消でも開始済み処理の終端を待つ。
結果schema、既存検証、登録policyは保持。他のsession部品/setup受付/実行全体のoff-loop化ではない。

tests/test_blender_status_io.pyの最初2ケースは修正前24505 exit1/2failed/1teardown error。
loop上の検査と取消中の同期waitを検出。修正後関連78passed/19.13秒、
HTTP/3回取消/WS明示/WS初期化の最終focused4passed/0.59秒。
全test43494は1539passed/既知2warnings/152.61秒。この収集後にWS2casesを加え全体を再実行。
最終22111は終端exit0/1541passed/既知2warnings/154.44秒。型注釈追加後のfocused4もexit0。
viewer build47ms/生成JS差分なし、Node5passed。

外部mf-status-offloop-source-20260910.py初回はhealth1.521msを観測したが、worktree既定の
legacy rootに実体がなくready期待でexit1。R2は既存外部rootをSettingsで明示、専用dataのみを使用。
`PYTHONPATH=backend:. .venv/bin/python /data1tb/mf-status-offloop-source-20260910-r2.py`
終端exit0/0.281秒。証跡 `/data1tb/mf-status-offloop-source-20260910-r2/observations.json`。
実TCPのstatus検査を明示thread gateで保留中、別接続healthが1.516msで200、statusは未完了。
解除後status200/実4.5.9のready checks、3検査すべてloopと異なるthreadを確認。専用core終了。
人工的な検査待機であり、長時間download/Host認証/installed修正の受入ではない。

setup自体の認証残件: BlenderRuntimeOperationにHost child/credential fieldはなく、
workspace install等はidentityを渡さずBlenderRuntimeManagerのlocal operationを開始する。
既存631秒source試験もHost認証なし。scene Jobのrefresh成功をsetupのrefreshへ転用しない。
次はsetupのHost所有権/credential lifecycleの設計・実装対応を照合し、実長時間受入を補完する。
NOT TESTED: 今回修正の署名配布/installed UI、全setup I/O、setup Host credential、全3DS/GA。
稼働.63/MF1573521・Host1384554は変更なし。

## 2026-09-10 configured external reference / installed D-09 acceptance

base PR444 merge4599a6c、branch ux1/3d-external-configured-acceptance。
既存config.pyの正式環境変数MEDIA_FORGE_BLENDER_LEGACY_ROOTを使用。read-only resolverで
`/data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9`のstamp/manifest/executable/workerを事前検証。
Job/GUI/setup全終端確認後、専用一時systemd user runtime drop-inで当該rootを明示しMFのみ再起動。
Host PID1384554不変、試験MF PID1562182。既存外部file/Host設定/bundleは変更しない。
これは明示server設定下の受入であり、未設定のbundleがsource runtimeを自動検出した証拠ではない。

外部 `/data1tb/mf-external-installed-0.28.63-20260910-r2.py`をHost診断venvで実行。
21153終端exit0、20.973秒passed/21.045秒login失効。
証跡 `/data1tb/mf-external-installed-0.28.63-20260910-r2`。
解除前に実processのroot環境値と実API ready/全checksをassert。全制作DB行snapshotも保存。
実Host opaque iframe/installed.63/overlayなし、Chrome headlessで日英×1280/320の4条件。
通常pointerで取消→登録解除→新pageから再接続後抑止→通常再登録、横overflowなし/page errors0。
全previewはunregister/live0/project0/reclaimable0/ready。各caseで外部6544entriesのSHA/size/mode/
symlink/dir集合と、58scenes/180revisions/967assetsの全行一致、active4.5.13/登録identity保持。

試験後、作成した90-mf-external-acceptance.confだけ削除、daemon-reload/MF再起動で元設定へ復帰。
MF PID1573521/DropInPaths空、Host1384554不変、実HTTP /health healthy。
独立read-only比較で外部inventoryと制作DB全行一致、登録をruntime_id順に比較して全JSON一致。
最初の独立比較はregistry配列順まで要求してexit1（再登録でlegacyが末尾へ移った）。
各登録内容・active・抑止が不変の独立比較はexit0。配列bytes不変とは記録しない。
元環境には外部root指定がないためlegacy表示の元damaged状態は改善したと主張しない。

README/APIへ正式設定経路・bundle既定root・ready事前条件・外部file非変更を明記。
製品コード/公開契約/依存/署名bundle変更なし。文書のみのため全test/buildの新規実行なし。
NOT TESTED: 外部の任意version/参照中競合の追加matrix、物理mobile入力、全D/全3DS/GA。
D-09の設定済み固定外部のinstalled日英差分を補完。旧失敗traceは保持。次はA/C/E/F等の残件。

## 2026-09-10 installed external registration acceptance failed / restored

base PR443 merge ce1140f、branch ux1/3d-external-installed-acceptance。
外部登録解除/再登録のinstalled差分を検査する外部診断
`/data1tb/mf-external-installed-0.28.63-20260910.py`をHost診断venvで実行。
証跡 `/data1tb/mf-external-installed-0.28.63-20260910`、79358終端exit1/65.638秒。
実Host opaque iframe/overlayなし/日本語1280でcancel→unregister→再接続後抑止を確認。
しかし再登録を待つ条件がtimeout、finallyの通常UI再登録もtimeout。診断loginは65.640秒で失効。
4画面条件の完走・通常再登録成功は未達であり、D-09をVERIFIEDへ変更しない。

解除前previewはstate=damaged/live0/project0/can_remove=true/reclaimable0。
実MF PID1483422の環境をキー限定で読取: MEDIA_FORGE_BLENDER_LEGACY_ROOT未設定。
config.pyの既定はREPOSITORY_ROOT（packaged sys._MEIPASS）/runtimes/blender-4.5.9であり、
診断がinventoryした `/data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9` を指す設定ではない。
register_legacyは_ready失敗時にfalseを返して抑止を維持するため、登録行の存在だけでは再登録可能性を証明しない。
診断の解除前preflightがstate=ready/正しい参照先を確認していなかった不備を記録する。
利用者の既存Blenderへ勝手に参照を変更したり、壊れた登録をreadyとして扱う修正は行わない。

診断終端後、登録JSONの当該legacy行と抑止のみをapply_patchで事前状態へ戻した。
独立read-only照合55578終端exit0: registry-before.jsonとのJSON全体一致、外部6544entriesの
全file SHA/size/mode・symlink target・directory集合がexternal-before.jsonと一致。
外部ファイル/managed runtime/active版は変更なし。DBは全Job/GUI/setup終端、58scenes/180revisions/967assets。
診断は制作APIを呼ばないが、実行前DB全行snapshotはファイルに保存していないため全行不変の独立証拠とはしない。
元のdamaged表示へ戻したのであり、再登録成功や外部参照の修復とは報告しない。

今回は文書のみ、製品コード/Host/service設定・依存変更なし、全test/buildを新規実行していない。
次: 正式なサーバー設定経路の外部root指定を確認し、設定済みready外部の範囲でinstalled受入を再計画。
解除前にready/参照先/全DB保存/通常再登録の前提を厳格検査する。既存のsource/package成功は維持。
全GOAL/A〜F/GAはPARTIAL、他の安全な残件も継続可能。

## 2026-09-10 v0.28.63 installed / mobile RFB acceptance

download41993は終端exit0、公開本体31585503B/SHA d9327c3f20a53850e63f685dba4a1cf545726ddbcd1b8d4b7819b2f526a04f2b。
`mf-0.28.63-install.py`をHost診断venv/CONTROL_DECK_CONFIGで実行し88248終端exit0。
全4公開files/build一致、Host trusted署名検証、idle確認、全SQLite backup後に標準update。
backup `/data1tb/mf-0.28.63-update-cf8it2q_`、10.288秒healthy、全DB table fingerprint/registry bytes保持。
Host PID1384554不変、MF PID1483422、実exe SHA7520edee920fa8b08b90236cb85d3954f831f5f44dfc89c2783ebad0ad557d37。
実配信schema/exact source一致。保持2の標準整理で旧0.28.61実行bundleのみ削除、.62/.63/data/runtime保持。
旧bundleは署名releaseから再取得可能。Host再起動/依存・model追加なし。

`mf-mobile-blender-installed-0.28.63-20260910.py`を同Host診断venvで実行、87262終端exit0。
証跡 `/data1tb/mf-mobile-blender-installed-0.28.63-20260910/observations.json`。
source/HTTP/transport overrideなし、実Host opaque iframe、Chrome320x640/touch emulation。
open/補助Enter/保存をtap、文字入力とcanvas focusはkeyboard/mouse。8.585秒で実4.5.13 canvas1007色、
14.043秒passed、14.046秒owned session終端、14.113秒診断login失効、page errors0。
scene_fd74c96138df40e9a69a1483bee2adfcを第6→7版、fps30→24、旧6版/全旧hash/mesh数/clip設定保持。
新版revision_17d1026f3e314e4fbbae42f561398e2a、source asset_2fbf9ca1f13b4b5ca22cfd396e385b92、
GLB asset_242d698c10244446ac94cda075cc77c6。
独立managed Blender `--background --factory-startup --disable-autoexec --python-exit-code 1 --python-expr`
読込exit0、fps24/actions2/両range[0,48]をassert/出力確認。
独立DB読取でもowned blendersession_355c9cc90afd4d1a9493041caf5cbbd8はstopped、7revision。
sqlite3 CLI不在のためPython標準sqlite3のread-only接続で確認（追加installなし）。

今回は受入文書のみ。既記録1537 tests/build/Node gate後の製品コード変更なし。
NOT TESTED: 物理mobile端末/IME/全touch-only編集、今回新GLBのengine再生、全GOAL/A〜F/GA完了。
PR443のinstalled新UI待ちは補完。全体PARTIAL、次は必須受入表の残件へ進む。

## 2026-09-10 v0.28.63 signed publication / consumer download running

PR442 merge/tag対象4aafb4feaa549c76bda0d6560192ced948e2249c。
exact checkout `/data1tb/ControlDeckMediaForge-release-0.28.63`でbuild32197終端exit0。
PyInstaller6.22.0/Python3.12.3、build log13.698秒、artifact31585503B、
SHA256 d9327c3f20a53850e63f685dba4a1cf545726ddbcd1b8d4b7819b2f526a04f2b。
build evidence `/data1tb/mf-0.28.63-build-20260910`。
外部audit exit0/203entries、exact source UI/worker/schema一致、旧guard/公開制約保持、
mobile helper/100dvh/旧display:noneなしを確認。package mf-0.28.63-package-xgcr6mo3。
packaged doctor ok/0.28.63、既存bundle-build venv/既存publisher keyで署名・自己検証成功。
`gh release create v0.28.63 --target 4aafb4f...` は69685終端exit0。
GitHub公開4assets uploaded/non-draft/non-prereleaseを確認。

初回download41691は公開upload終端前に取得を開始したため本体なしの3filesでexit0。
外部install診断は本体FileNotFoundErrorで署名検証・backup・更新より前にexit1。稼働版未変更。
upload終端後 `gh release download v0.28.63 --dir /data1tb/mf-0.28.63-public-20260910 --skip-existing`
を実行。41993継続中、PID1479493を48秒で実観測、本体5511296Bまで取得。
完了サイズ31585503B/全4files一致はまだ未確認。同handleを追跡し、観測timeoutで再取得しない。
完了後 `/data1tb/mf-0.28.63-install.py` の全bytes/Host署名/idle/backup/標準updateを実行する。
次のinstalled GUIは `/data1tb/mf-mobile-blender-installed-0.28.63-20260910.py`（overlayなし）。
現在.62、Host再起動なし、旧.61整理もまだ実行していない。全GOAL/A〜F/GAはPARTIAL。
NOT TESTED: consumer取得完了/署名consumer/導入/installed新UI、物理mobile/IME/engine。

## 2026-09-10 v0.28.63 preparation

PR441 merge97cb94b19bd500d1fb23d8ba5a1944f10f424a26からux1/release-0-28-63。
addon/core版数とrelease noteを追加。全test78582終端exit0/1537passed/151.22秒/既知warning2、viewer build44ms/差分0、Node5。
外部mf-0.28.63-audit.py/install.pyを前版の保持・署名・exact bytes検査から準備。
新UIの同梱/旧mobile非表示なし/入力補助をauditへ追加。py_compile成功、未実行。
mf-mobile-blender-installed-0.28.63-20260910.pyはHTTP/source overlayなしのinstalled browser試験へ変更。
同専用sceneの第6版からopen/補助Enter/保存をtouchで検査する予定。準備を実機成功とはしない。
現在current0.28.62、保持0.28.61/62。標準保持2による旧.61bundleのみの整理を事前通知。
data/runtimeは整理対象外。全GOAL/A〜F/GAはPARTIAL、Host変更/再起動なし。
NOT TESTED: .63公開/署名consumer/導入/installed新UI、物理mobile/IME/engine。

## 2026-09-10 opaque iframe touch activation / real Blender acceptance (PR441)

前turnは補助keyのeditor context修正で進捗。今回はBlender/Hostを除いた2buttonの最小iframeで再現。
Chrome headless/320x640/is_mobile/has_touch、sandbox allow-scripts、iframe top88px、scroll5505px。
touchはopen/clientY244へ届くがclickはclose/clientY156へずれた。通常inline onclick付きでも再現。
MediaForgeのBlender操作欄/dialogだけにsingle-touch button activationを追加。
元buttonが接続済み/有効、同指の開始終了が10px以内かつbutton内の場合だけtouchendをcancelし
button.click()を1回呼ぶ。drag/cancel/multitouch/disabled/領域外終了は処理しない。
canvasやフォーム入力全般へ適用せず、keyboard/mouseの既存click経路を保持。

`scripts/3ds_mobile_blender_ui_e2e.py` 実Chromeで日英6viewport成功。
opaque最小再現はopen_onceになり、drag/cancel/multitouch/disabled/end_outsideの5negativeは
preventDefaultなし/追加clickなし。これらnegativeは合成TouchEventによるhandler検査であり
物理端末のgesture受入ではない。focused155/0.09秒、viewer64ms/差分0、Node5。

外部 `/data1tb/mf-mobile-blender-source-ui-20260910-r3.py`（OUT r19）をHost診断環境で実行。
証跡 `/data1tb/mf-mobile-blender-source-ui-20260910-r19`、12.325秒passed/exit0。
通常認証bootstrap後にsource関数/dialog/CSSを置換するbrowser限定overlay。
320pxのopen/補助Enter/保存に実Chrome touch入力、文字入力とcanvas focusはkeyboard/mouse。
openのtouchend→元buttonのclick1回、6.795秒で実Blender4.5.13 canvas1007色、
24→30fpsを新版revision_4b315df7c5d84811bcb3d8146ea00f66へ保存、旧5版/旧hash保持。
12.328秒owned session終了、12.395秒login失効。独立DB照合でstopped/6revision。
新source asset_eb53557cfdae46e2b7c27a5e3c08fabb.blendを実managed Blenderで
`--background --factory-startup --disable-autoexec --python-exit-code 1 --python-expr`読込し
fps30/actions2 assert成功/exit0。旧失敗証跡/版を保持し、成功へ書き換えない。

全 `./mf.sh test` 59562は終端exit0/1537passed/既知warning2/154.34秒。source受入は補完したが、
NOT TESTED: signed installed新UIのbootstrap/同梱確認、実mobile端末、IME/全操作/全GOAL/A〜F/GA。
製品版数/稼働.62/Hostに変更なし。PR441通常merge後に署名版へ反映しinstalled受入する。

## 2026-09-10 assisted keys restore Blender editor context (PR441)

前turnのfps不一致を原寸canvasで切り分け。外部診断r16/r17は画像取得後保存せず終了。
`/data1tb/mf-mobile-blender-source-ui-20260910-r16/console-native-before.png` に
`bpy.context.scene.render.fps = 24` の完全入力を確認、afterでも未実行。
r17は実sendKeyを元実装へ転送する診断記録で65293/Enterのdown/up両方を確認。
ポインターをconsoleへ戻して通常Enterを送ると実行された。toolbar移動でBlenderの
ポインター下editorが変わるため、キー送信だけでは元editorへ届かない。

frontendはcanvas pointerdownの相対座標を保持し、補助key前に同canvasのmousemoveとして復元。
固定noVNCのMOUSE_MOVE_DELAY=17msを実コードで確認し30ms待ってkeyを送信。
private RFB methodには依存しない。待機後同RFB/connectedを再照合、disconnectでanchorを消去。
ブラウザ回帰はpointer復元→key順序と待機中disconnect時keyなしを追加。
診断fixtureのdisconnectがanchorを消さず次viewportで失敗したため製品と同じ消去へ修正。
日英6viewportの実Chrome診断は修正後exit0。viewer build40ms/差分0、Node5。

実source UI overlay→installed API/Blender4.5.13はr18で11.375秒passed、
11.379秒owned session終了/11.457秒login失効。320px・mouse操作でありtouch成功とはしない。
証跡 `/data1tb/mf-mobile-blender-source-ui-20260910-r18`、fps30→24を保存factsで確認、
旧4revision/旧hash保持、2clips設定/1mesh不変。新版revision_ac4d6abff2df435ba71742bb9cba5853。
managed Blenderでsource asset_15ac411ffa834d348b8e70ed111b2225.blendを
`--background --factory-startup --disable-autoexec --python-exit-code 1 --python-expr`で独立読込し、
fps==24/actions==2 assert成功/exit0。補助キーでの実設定変更を今回初めて確認。
全 `./mf.sh test` 72132は終端exit0/1537 passed/既知warning2/169.78秒。
NOT TESTED: touch誤click解消、
installed新UI/実mobile端末、全GOAL/A〜F/GA。PR441 draft/稼働.62保持、Host変更なし。

## 2026-09-10 mobile touch/click coordinates and real RFB display (PR441)

前turnの段階切り分けを受け、外部診断mf-mobile-blender-source-ui-20260910-r3.pyを改良。
証跡 `/data1tb/mf-mobile-blender-source-ui-20260910-r8`〜`-r15` を別々に保持。
r8/r9ではbutton bbox=(29,309.625,262,46)、iframe=(0,88,320,490)、local hitは正しいopen。
r10でpointerdown/touchstart/pointerup/touchendはscene-blender-open/clientY244.625へ届くが、
生成clickだけscene-detail-close/clientY165へ変わることを記録。scrollY5505は不変。
誤targetを直後assertで停止し、30秒のRFB待ちに進まなくした。
r11 touch-action:manipulation、r12 is_mobile=Trueでも同じで、CSS試行は製品へ採用していない。

r13の同320px/mouse比較は正しいtarget→実RFB connected/1007色まで成功。
ただし診断が旧CSSを残していたためdialogはdisplay:none、canvasクリック前失敗。
r14で旧workspace styleを除いてsource CSSへ置換すると実画面を表示し、保存で第3版を追加。
fps30→24は未反映のため終端exit1、成功扱いしない。旧2版/旧asset hashesは保持検査を通過。
r15はその第3版から同条件で再確認。5.288秒connected/実canvas1007色、7.548秒補助key有効、
console-before-enter.pngで実Blender Python console表示を確認。10.786秒に保存後fps不一致でexit1。
第4版を追加したがfpsは30のまま。補助Enter有効だけで設定変更成功とはしない。
全r8〜r15のowned sessionは独立DB照合でstopped、現在4revision。
これらは通常認証bootstrap後のsource UI関数/dialog/CSS overlayとinstalled API/実Blenderの試験。
installed新UIやtouch成功に読み替えない。初回のHTTP overlayも未解決の別診断制約として保持。

次: 320px canvasの原寸pixelを取得し、文字入力→補助Enter前後のconsoleと実key送信を照合。
失敗保存の第3/4版を消して履歴を隠さず、正確なcurrentから次試行を始める。
製品コードは8821b0eから不変、PR441 draft/全1537 gate維持、今回文書のみ。
NOT TESTED: 補助Enterの実設定変更、正しいtouch click、installed配布版/実mobile端末、全GOAL/A〜F/GA。

## 2026-09-10 mobile acceptance failure stage isolated (PR441)

source8821b0e/PR441 draft、製品コード変更なし。前turnはUI実装/全1537test/PR作成で進捗。
今回の診断は外部 `/data1tb/mf-mobile-blender-init-probe-20260910[-r2|-r3].py`。
HTTP応答overlayでdocument200/new keys/config/scriptを確認、Host bridgeとnonceも存在、origin null。
手動connectSocket→bootの診断はworkspace_transport_unavailableを返した。
同320px/new contextでoverlayなしの `mf-mobile-blender-init-native-20260910.py` は
6.618秒でboot成功、busy false/bridge ready。全probeはlogin失効して終端、GUIを作らない。
HTTP overlayの認証cookie/WS差分の詳細原因は未確定。製品のmobile初期化障害とは断定しない。

正常bootstrap後に変更対象6関数/HTML dialog/CSSだけをブラウザ内で差し替える別診断を実施。
`/data1tb/mf-mobile-blender-source-ui-20260910-r3.py`、証跡末尾r3〜r7は別directoryで保持。
r3は診断regex過剰escapeでGUI前失敗。修正後r4/r5はsource overlay完了/専用GUI readyだが
tap後dialog false、選択scene空、RFB未生成。r6のheadlessでも同じで、native CDPだけとは断定しない。
r7はscroll完了後750ms待ちを追加しclick captureを観測。3.573秒で
requested target scene-blender-open に対し actual click target scene-detail-close、
旧mobile gateなし/dialog false/selected空を確認。33.576秒でRFB待ち失敗、
33.842秒owned session終端、33.900秒login失効。RFB接続を実行した証拠ではない。
全r4〜r7のowned sessionがDBでstopped、対象sceneの旧current
revision_8cf8c752e3734fe1949dd4eec6053b54と2revision維持を独立read-only照合。

次: viewport/iframe scroll/入力座標の実測と正常target到達のassertを追加し、
誤target時は接続待ちへ進まない。UI入力とRFB/Blender入力の境界を分離して受入を続ける。
PR441はdraftのまま、署名配布なし/.62不変。NOT TESTED: 新UIの実RFB入力/保存、
installed新UI/実mobile端末、全GOAL/A〜F/GA。今回文書のみ、既存全test gateを再実行していない。

## 2026-09-10 mobile Web Blender access implementation

PR440 merge68f021a0a37b82ff5333e5141a1296be32678332からux1/3d-mobile-blender-access。
設計§5のmobileフルGUI利用に対し、現行は開始/復旧disabled、open早期return、CSS display:noneの
3段階で阻止していた。画面幅の禁止だけを除き、runtime/Web pack/稼働競合/復旧base競合保護は保持。
767px以下は100dvh dialog・縦scroll・折返し・保存/終了1列、PC/keyboard/mouse推奨を日英表示。
Esc/Tab/Enter/矢印7keyの入力補助を追加。noVNC connect後だけ有効、disconnect時無効。
固定noVNC実体のsendKeyはdown省略でpress/releaseを送ることを確認。非公開connectionStateを
推測で参照せず、connect/disconnectイベントに紐づく所有stateで制御する。

`/data1tb/ControlDeck/app/.venv/bin/python scripts/3ds_mobile_blender_ui_e2e.py` exit0。
実Chrome headlessの320x640/640x320/1280x800各日英6ケースでdialog表示/閉じる、
document/dialog横overflowなし、touch tap→7key送信呼出、切断後7button無効/送信なし。
HTML/CSS/関数/辞書はsourceを読込、RFBのみ明示fixture。実Blender入力とは扱わない。
focused frontend155 passed/0.19秒、Node5、viewer build41ms/生成物差分なし。
初回focusedは旧desktop-only・760px期待値2件で失敗し、承認済み設計に合わせ期待値を修正。
同修正前の全test94076は2 failed/1535 passed/149.13秒で終端exit1。
修正後の全 `./mf.sh test` 78368は1537 passed/既知warning2/151.29秒、終端exit0。
外部source UI overlay診断 `/data1tb/mf-mobile-blender-source-ui-20260910.py` と同`-r2.py`は
いずれも#app[aria-busy=false]待ちで31.111/31.103秒に失敗。両診断login失効、GUI未作成。
初回はworkspace生成済みHTMLを未展開templateに置換する診断欠陥を発見。
R2は元configを保持するinline style/script/dialog置換へ変更したが同じ待ちで失敗。
したがってtemplate置換だけが原因だったとは断定しない。live input/save成功扱いにしない。
証跡 `/data1tb/mf-mobile-blender-source-ui-20260910[-r2]/observations.json` を保持。
次は再試行を増やす前にframe初期化/表示状態と実際の置換適用有無を観測する。
NOT TESTED: 新UIのlive RFB/Blender保存、installed opaque iframe、実mobile端末、入力IME/修飾キー、
新UI署名配布。backend/Host/稼働0.28.62を変更せず、全GOAL/A〜F/GAはPARTIAL。

## 2026-09-10 OpenCode saved-settings terminal acceptance / GUI saved fps

PR #440の実runは終端exit0、476.429秒、33 events / 8 tools。
証跡 `/data1tb/mf-opencode-saved-settings-installed-0.28.62-20260910`。
`PYTHONPATH=backend .venv/bin/python scripts/3ds_verify_opencode_flow.py --evidence-dir
/data1tb/mf-opencode-saved-settings-installed-0.28.62-20260910 --database
/data1tb/ControlDeck/data/feature-data/media-forge/data/media-forge.sqlite3` を再実行しexit0/verified true。
実director読込、初期5操作と両loop=true、Job/snapshotの保存値一致、export前の照合順序、
fresh exports grant、receipt/Asset/provenance/実bytesを検査。scene_90ee167578dc4e5c925cbb6bad1b115f、
revision_1ef77f62760144e98e8e269525298a6f、job_693dd75188f54754b2b8d886eadcd6a1。
納品 `MF3DS-OpenCode-Saved-Settings-20260910/exports/weighted.glb` は32140B、
SHA256 0d4e37c06850c795429342342209ff3cff63ba70a59155f15abbb076101d7317。
同証跡の実Blender4.5.13 `--inspect --fixture auto_skin --posed` はpassed true、
source114頂点/混合48、再import480頂点/混合192、最大2影響、2秒clip、
5時刻の最大位置差2.4646110694144804e-07m。親1426898/子1426968は再確認時不在。
以前の.60/.61失敗traceは保持。promptと保存結果照合も変えたためschema説明単独の改善とは断定しない。

別の専用scene_fd74c96138df40e9a69a1483bee2adfcでWeb Blender保存後factsを確認。
外部診断 `/data1tb/mf-animation-facts-gui-0.28.62-r2.py` を既存DISPLAY=:0の専用Chromeで実行。
Blender自体は専用隔離session/RFBのまま。証跡
`/data1tb/mf-animation-facts-gui-installed-0.28.62-20260910-r2/observations.json`。
22.526秒で実canvas/1068色、RFB Python consoleへfps=30入力、67.609秒で保存検査passed。
revision_f014c141740b4fffacec1b46f98a1626を保持し、新版revision_8cf8c752e3734fe1949dd4eec6053b54。
fps24→30、idle false/bend trueと0→48frameは不変、旧source/GLB hashes保持、page errors0。
67.612秒owned session終端、67.670秒診断login失効を記録。
実managed Blender4.5.13で新source asset_74ed9ec9e71e4e9da7338bf556a3af41.blendを
`--background --factory-startup --disable-autoexec --python-exit-code 1 --python-expr`で独立読込。
fps==30/actions==2をassertしexit0、両action range [0,48]を実出力で確認。
最初のGUI試験は保存前edited.pngのscreenshot timeoutで失敗した記録を保持。
R2はその任意撮影だけを外し、保存値・旧版保持・回収のassertionを維持した。

コードは既記録の全1536 tests通過後に変更なし。今回追加は受入文書のみ。
NOT TESTED: このGUIのfps欄マウス編集/新GLB再生、一般的な自由制作の安定性、
画像付き複雑character、歩行/IK/root motion、ゲームエンジン導入、全GOAL/A〜F/GA完了。
稼働版0.28.62、今回Host変更/再起動/新releaseなし。全体PARTIALを維持する。

## 2026-09-10 OpenCode saved-settings acceptance running

PR439 mergefb3fb7321d2ece5021be7421b6f9cdceb9e3e714、ux1/3d-opencode-saved-settings。
既存auto_skin診断へ任意--saved-settingsを追加、過去mode/失敗判定は変更しない。
納品前にstatusとsnapshotの保存factsを照合し、両loop true/24fps/0→48frame/未報告0を要求。
欠落や不一致時はexport/packせず停止する追加prompt。要求したcreate入力の厳格条件も維持。
verifierは両revision同一、保存値、status→snapshot→export順序も検査。12追加casesで
欠落/false/数値loop/fps/range/未報告/rig/clip不足/不一致/別revision/早期exportを拒否する。
focused67 passed/0.90秒、build40ms/差分0/Node5。
全 ./mf.sh test は1536 passed/既知warning2/148.59秒/exit0（62231終端）。

実run: Host診断環境でscripts/3ds_opencode_flow_e2e.py --director-auto-skin --saved-settings
--project-name MF3DS-OpenCode-Saved-Settings-20260910
--evidence-dir /data1tb/mf-opencode-saved-settings-installed-0.28.62-20260910。
既存smoke不在後に開始、handle57218/親1426898/子1426968、23秒時点同PID生存/events0。
private build/24tool preflight通過、実MCP create schema21699Bを新evidence内へ記録、
SHA56b3c97cdd3751730ace7ddb542a6f7a5e2e5b53b8ce2906796d13afd1b2ada5。
これはbridge時点のschemaであり最終LLM推論入力の証拠とは区別する。
稼働.62/Host/既存scene/global設定不変。終端/品質を先取りしない。
code8d9a0e05df3d9042eec1e1597d1a90251d228e1dをcommit/push、PR #440作成。
3分11秒でも同OpenCode PID生存/tool出力なし、同handle追跡。実機終端待ちで未マージ。
NOT TESTED: 本runの終端・成果物、GUI後facts/engine/複雑character/全3DS・GA。

## 2026-09-10 v0.28.62 signed installed / saved facts MCP accepted

PR438 merge/tagd4dcf03c170673846322c662007c0744ac43dedf。
exact /data1tb/ControlDeckMediaForge-release-0.28.62でbuild_release_bundle.py、52285 exit0/log13.107秒。
artifact31543807B/SHA4c1e5378c1c7076f3b544765b6057e4243abfe0d7f6fa9073d5f8ccc06c6526d。
mf-0.28.62-audit.py exit0/203 entries:source worker/schema一致、新animation_facts/model/schema同梱、
旧guard/recipe制約維持、packaged doctor ok/.62。package mf-0.28.62-package-ldlpjwem。
既存bundle-build venvで署名/自己検証、新鍵/依存取得なし。
公開57685/download73848 exit0、public mf-0.28.62-public-20260910の4filesがbuildと一致。
外部mf-0.28.62-install.pyをHost診断環境で実行、58970 exit0/9.611秒。
署名/idle/DBbackup後標準update、backup /data1tb/mf-0.28.62-update-_ap76cz6。
全DBtable fingerprint/Blender登録不変、healthy、Host1384554前後不変/MF1424628。
実exeSHA4fa65c3ba4ea5a9ba0604cb52a14b99b51125a2fd99cfd71d69990ef9dc44b6bはauditと一致。
新scene-animation-settings.jsonとcreate schemaの実HTTP配信=exact source。
標準保持2で旧.60実行bundleのみ整理、.61/.62/data/runtime保持。事前通知済み、旧公開版から回復可能。

実MCP: mf-animation-facts-mcp-installed-0.28.62.py、98610 exit0/1.761秒。
証跡 /data1tb/mf-animation-facts-mcp-installed-0.28.62-20260910。
24tools→create→status→snapshotで保存factsのidle省略false/bend明示true、24fps/0→48frame/未報告0一致。
export→新exports grant→weighted.glb配置、実Blender4.5.13 auto_skin --posedでsource/GLB変形一致。
scene_fd74c96138df40e9a69a1483bee2adfc、revision_f014c141740b4fffacec1b46f98a1626、
GLB asset_2b206d5ad54a40d787ec1345c3181ac6、job_fda5570c649e4db18291656daece32ad。
Host childdf7c7756a8c7は実DBでsucceeded、private runtime-config-mf-auto-skin-14ca460b1f4.json不在を独立確認。
project MF3DS-Animation-Facts-MCP-20260910/exports/weighted.glb32140B、
SHA51eb7fb98c1efee4b49c3af1c5d022129d83854e663e8791c1a8dfbf593aefd9。
receipt/Asset/provenance/実bytes一致、旧scene/revision/登録不変。
全test版数gate1524 passed/154.54秒/既知warning2、build39ms/差分0/Node5。記録sliceはdocsのみ。
NOT TESTED: OpenCodeによるfacts照合と指定遵守改善、GUI後facts、複雑character/engine/全3DS・GA。
次は実OpenCode診断へ納品前のfacts照合を追加し、既存strict条件を緩めず再受入する。

## 2026-09-10 v0.28.62 preparation

PR437 mergeff60f6598d86cf4c11bb1467a1fbdfa37f80f9c8確認、ux1/release-0-28-62。
addon/core版数とrelease note追加。新animation_settingsを同一bundleへ配布する準備。
viewer build39ms/生成物差分0/Node5成功。版数変更後の全testは1524 passed/既知warning2/154.54秒/exit0（9850終端）。
外部mf-0.28.62-audit.py/install.py、mf-animation-facts-mcp-installed-0.28.62.pyを準備/compile成功。
新schema/model/worker同梱、旧契約・guard維持、標準署名/backup/idle/配信実体照合を含む。
MCP診断は新projectでidle省略false/bend明示trueのJob結果・snapshot一致とGLB実変形を検査予定。
準備時.61/MF1411733/Host1384554、実DB未終端Jobs/GUI/setup0、既存OpenCode smokeなし。
標準保持2で旧.60実行bundleのみ整理対象と事前通知、.61/data/runtime保持。Host変更なし。
NOT TESTED: .62公開/導入/実MCP/OpenCode効果、GUI後facts、engine/複雑character/全3DS・GA。

## 2026-09-10 saved animation settings facts

PR436 merge50c48faec0c1c0dd02cbe2ba412452f87352688c確認、ux1/3d-clip-result-facts。
独立.blend validatorへanimation_settingsを加法出力。scene実効fps、typed rig/clip IDs、
実action frame範囲、保存loop_requestedを最大32件報告。一般/不正/重複/overflowは未報告数へ計数。
loop metadataを端点・速度・engine品質の合格判定にしない。旧facts欠落は未検査で、旧入力/既定を維持。
coreは新factsの型/finite/範囲/一意/総action件数を検査。旧worker fieldsも互換受理。
公開scene-animation-settings.json、GA-5設計/API、15tests、既存実機診断の--animation-settingsを追加。
新しい同期DB/I/Oやcore bpy importなし。既存recipe workerの成功protocolは変更しない。
focused27 passed/3.27秒、build42ms/生成物差分0/Node5。
全 ./mf.sh test は1524 passed/既知warning2/148.94秒/exit0（59812終端）。

実診断: PYTHONPATH=backend:. .venv/bin/python scripts/3ds_game_static_e2e.py
--fixture auto_skin --animation-settings --runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9
--managed-root /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/blender
--evidence-dir /data1tb/mf-animation-facts-source-20260910。
4.5.13/exit0/2.054秒、初版idle省略→saved false、2版でbend明示→true/idle false保持。
実source/GLB2clip変形再import、失敗後旧版hash保持、provenance/lineageは既存domainで記録。
scene_b8f2a69a26154cd9b9dcfa05660eff07、初版revision_efac4e3ae07742e7bc5d2dcef129b21d、
2版revision_392cecb9806b4b3a8a5ddd345280fd44。両factsは24fps/0→48frame/未報告0。
managed-rootを省略した同診断も別dir mf-animation-facts-source-4.5.9-20260910でexit0/2.491秒。
専用source core PID1417088/port19130を同診断dataで起動し、実HTTP scene GETで両revisionの
factsが保存値と一致、新schema GET200/exact source一致を確認。専用core通常終了exit0。
稼働.61/MF1411733/Host1384554/既存sourceは変更なし。継続中OpenCodeなし。
NOT TESTED: 新factsのsigned installed/MCP/OpenCode効果、GUI変更後facts、複雑character/engine、全3DS/GA。

## 2026-09-10 OpenCode auto skin R2 terminal — guidance not sufficient

base PR435 mergeeb9172b275bc82ffcc46b18fddfc370f332523e2、ux1/3d-auto-skin-r2-audit。
同run26740はexit0/207.032秒/9tools/38events、親1411807/子1411873不在。
証跡 /data1tb/mf-opencode-auto-skin-installed-0.28.61-20260910。
実director102.957秒/capabilities118.136/create141.433/status144.859/export158.742。
両animation.clip入力でloop省略。最初のoutput grantはrelative_directory='.'でerror、
exportsへ再申請後pack成功。失敗時停止要求にも違反し、strict verifierは全tool成功assertでexit1。
説明改善後も全依頼不合格。既定falseをtrueへ変更せず、失敗trace/成果物を保持する。
Job job_2ba7fd84c7c64d3a883c0834809aa85dとHost child256756cd08b9は実DBでsucceeded。
scene_15c1bd0cdc7a47fca00e7be64e034945、revision_0b509360cc1e48309f96e2a4c741fd97、
source asset_50e102f4325941f2bc60ba61246e5849、GLB asset_fb5524ff4b834ac39dc284e17836558f。
R2/exports/weighted.glb32140B/SHAd511701f6789aa286a86a5078f033a7dca8b3ebcd705508fc37b424649ade194。
receipt/Asset/provenance/実bytes一致、correlation mf3ds-89d7fd218afe4092のprivate config残存0。
初回独立auditは失敗toolのoutput欠落を考慮せずKeyError。失敗toolを明示報告する修正版で
成功した納品部分だけ照合しexit0。strict verifierを緩めたものではない。
実Blender4.5.13でsource/実配置GLBをauto_skin --posed検査、exit0/0.266秒。
2clip変形/各2秒/混合weightsの結果はposed-inspection.json。依頼全体の合格へ読み替えない。

外部mf-loop-mcp-schema-0.28.61.pyのread-only診断はexit0/0.583秒。
専用private configをfinally回収、制作Job/新project追加なし。
実Host /tools HTTP200/90124B/24tools、同bridge tools/list exit0/24tools。
AnimationClip descriptionのEVERY clip、loopのboolean/default=false/説明を実応答で確認。
Host model_facing_schemaはminLength/maxLengthのみ除去。現時点MCP配信でloop欠落なし。
LLMに渡った最終推論リクエストのschema変換/モデル判断の切り分けは未検証で、モデルだけが原因とは断定しない。
次は実適用clip設定を制作結果/snapshotで照合できる情報を設計する。自然言語の意図を
backendで勝手に推測したり、全clipをループへ暗黙変更したりしない。
本sliceは診断記録のみ、製品/installed/Host無変更。版数gate1509/149.23秒を参照。
全3DS/GA、複雑character/engine、R2の依頼品質は未完了。継続中OpenCodeなし。

## 2026-09-10 v0.28.61 signed installed / OpenCode R2 running

PR434 merge/tag d2b1ec49021f2133b165cb5189793fbea9992c9d。
exact /data1tb/ControlDeckMediaForge-release-0.28.61でbuild_release_bundle.pyを実行、
12895 exit0、PyInstaller6.22.0/Python3.12.3/log13.801秒。
artifact31542393B/SHAe20c385c4fa2c9fcff2047050c17a9029d011e67b978f8bb9a96ca9c80654265。
mf-0.28.61-audit.py exit0:202 entries/source同梱/秘密値混入検査/packaged doctor ok、
loop説明3schema/既存自動bind/旧guard維持、description除外契約treeは.60と同一。
package /data1tb/mf-0.28.61-package-k2g_j89b/control-deck-media-forge-0.28.61-linux-x86_64。
初回signはcore診断venvのcryptography不在でexit1、公開はmanifest不在で未作成。
依存追加せず既存bundle-build venvで署名/自己検証exit0。既存publisher鍵を使用、生成なし。
公開handle55308/download16532ともexit0、正規v0.28.61に4assets、draft/prerelease=false。
public /data1tb/mf-0.28.61-public-20260910の4bytesはbuildと一致。
外部mf-0.28.61-install.pyをHost診断環境で実行、93480 exit0/9.707秒。
署名/idle/DBbackup/再照合後標準更新、backup /data1tb/mf-0.28.61-update-28vyd5kq。
全DBtable fingerprint/runtime登録一致、healthy、MF1411733、Host1384554前後不変。
実exeSHA52d0bdf7819f5773ece18b4aee9d114d2665c0464307f68726baee7ecce5d4a0が監査bundleと一致、
実create schema=exact source、新loop説明/自動bindを配信。標準保持2で.59bundleだけ整理、
.60/.61/data/runtime保持、旧bundleは公開releaseから回復可能。事前通知済み。

既存smoke不在確認後、同じ--director-auto-skin診断を新project
MF3DS-OpenCode-Auto-Skin-20260910-R2で開始。証跡
/data1tb/mf-opencode-auto-skin-installed-0.28.61-20260910、handle26740、親1411807/子1411873。
private build/24tool preflightを通過し実OpenCode開始、まだ終端未確認。
旧.60の不合格trace/出力を保持、同じstrict verifierを使う。結果を先取りしない。
全testは版数変更後1509 passed/149.23秒/既知warning2、build40ms/差分0/Node5。
記録sliceはdocsのみ。NOT TESTED: R2終端/生成物、engine/複雑character、全3DS・GA。

## 2026-09-10 v0.28.61 preparation

PR433 merge8136dc76d2c1d3128353b4295f752b563494a2c3確認、ux1/release-0-28-61。
addon/core版数とrelease note追加、ループ説明以外の製品挙動・公開制約は不変。
viewer build40ms/生成物差分0、Node5成功。版数変更後の全testは1509 passed/既知warning2/149.23秒/exit0（30092終端）。
外部 /data1tb/mf-0.28.61-{audit,install}.py を既存.60手順から準備、py_compile成功。
新loop説明の同梱と3schema制約tree不変、署名/公開bytes/idle/DBbackup/実exe配信照合を含む。
準備時installed.60、MF1384429/Host1384554、Host clean main。実DBで未終端Jobs/GUI/setup各0、
既存OpenCode smoke不在。Hostを変更・再起動せず、global設定/既存Blenderを変更しない。
標準保持2により.59実行bundleのみ整理対象となることを事前通知。data/runtime/.60は保持。
NOT TESTED: .61公開/署名consumer/導入/実OpenCode、engine/複雑character/全3DS・GA。

## 2026-09-10 animation loop schema guidance

PR432 merge0a26acd4ec2918a247649463f882dc5fafec8d9c確認、ux1/3d-animation-loop-guidance。
実OpenCodeの2回のloop省略を受け、AnimationClip本体とloop fieldの説明を追加。
各clipへの明示true、端点一致だけで有効にならないこと、Job成功と依頼充足の違いを明記。
原因が説明不足だけであるとは確定しない。既定false/任意field/validationは維持する。
3公開schemaとdocs/api同期、既存default/端点検証と説明一致の4tests追加。
focused21 passed/0.23秒、viewer build45ms/生成物差分0、Node5成功。
専用source core PID1402727/127.0.0.1:19130、data /data1tb/mf-loop-guidance-source-ul8GII。
urllib実HTTPでcreate/edit/workflow schema3件200、exact source一致、descriptionを除くtreeは
origin/mainと同一。診断exit0、専用coreのみ通常終了exit0（handle76064）。
稼働0.28.60/MF1384429/Host1384554は変更なし。
全 ./mf.sh test は1509 passed/既知warning2/146.64秒/exit0（handle5326終端）。
NOT TESTED: 新説明のsigned installed/OpenCodeへの効果、複雑character/engine、全3DS/GA。
次は全test終端→通常PR→署名版準備後、同じstrict条件で新OpenCode受入。

## 2026-09-10 OpenCode auto skin terminal — strict acceptance FAILED

PR #432診断の同run50315はexit0/779.375秒/8 tool calls/34 eventsで終端。
実director読込→capabilities→create→status→snapshot→export→新grant→pack。
job_b99ecae01f4445e782181a482156f487、Host child09a42d623866は双方実DBでsucceeded。
scene_b98739e6bbf946f88292cb1f39653f6c、revision_129ed350e2fa498a89dbe3624bd1ccbc、
source asset_314a0254a7424a83ac15ce0dde8e7ef3、GLB asset_56437745bd7140f69e8f9830ba01279a。
実配置weighted.glbは32140B、receipt/Asset/provenance/実bytesのsize・SHA一致を独立確認。
親1388601/子1388651不在、correlation mf3ds-a2fdc4c209a84bbeを含むprivate config残存0。
実Blender4.5.13で3ds_game_static_e2e.py --inspect --fixture auto_skin --posedを
sourceと実配置GLBに実行しexit0/0.273秒。114頂点/48混合→480/192混合、最大2影響、
idle/bend各2秒、5時刻world差最大2.4646110694144804e-07m。posed-inspection.jsonを保持。
しかし3ds_verify_opencode_flow.pyはexit1: 両animation.clipでloop=trueが省略され公開既定false。
実変形と端点一致は確認できたが、依頼したloop検証を有効にしていないため全依頼は不合格。
verifierを緩めず、再制作/再起動/既存出力変更なし。共通inspectorのinstalled未検証欄は
この実OpenCode traceとは別scope。複雑character/画像付きskin/engine/全3DS・GAは未受入。
最終code全test1505 passed/150.62秒、以降docsのみ。次はloop指定漏れの制作経路改善。

以前のarray R2追加監査: 同じ実Blender inspector --fixture arrayはexit1/0.080秒、
実.blendのconstant_offset_displaceが要求(1.5,0,1.5)でないことを確認。strict不合格を維持。
配置stairs.glb6232B/SHAa945b41cf25d171c0303a6569dc9a2bc47a011f56040fd8623f24884b6f7361d、
receipt/Asset/provenance/実bytes一致、MediaForge JobとHost childa35f48249959はsucceeded。
correlation mf3ds-9ea12ef89ab945d3を含むprivate config残存0。GLB再import形状検査は
source指定違いで停止したため未実施。失敗を納品成功で上書きしない。

## 2026-09-10 OpenCode automatic skin acceptance running

Base PR431 merge8676610c3fc907f96fb8aac2d7e5131947609e04、ux1/3d-opencode-auto-skin。
既存診断へ--director-auto-skinを追加。専用の新規projectで実director読込、現行schema/capability確認、
連続uv_sphere/2骨/skin.bind_auto/idle・bend各2秒を自然言語で依頼する。
固定fixtureの寸法/骨位置/回転/キー時刻を明示する実行受入であり、キャラクターを自由設計する試験ではない。
自由shell/file/webを禁止したprivate実行config、named directorだけのskill権限、実build解決を検査。
verifierへ5操作の種類/順序/対象/形状/骨階層/clipと、export後の新grant/配置入力の一致を追加。
既存の実skill読込/全tool成功/Job終端/receipt/実file/Asset/provenance照合は維持。
剛体代用・別mesh・骨階層違い・形状違い・loop省略・回転違い・時間違い・余分な操作・
skill未読・失敗tool・配置先違い・改ざんbytes・異なる/早すぎるgrantをnegativeで拒否する。
focused55 passed/0.80秒、viewer build39ms/生成物差分0、Node5成功。
先行full1502 passed/145.04秒はgrant検査追加前のcollection。
最終コードの ./mf.sh test は1505 passed/既知warning2/150.62秒/exit0（handle32193終端）。

実行command: Host診断venv/configでscripts/3ds_opencode_flow_e2e.py
--director-auto-skin --project-name MF3DS-OpenCode-Auto-Skin-20260910
--evidence-dir /data1tb/mf-opencode-auto-skin-installed-20260910。
handle50315、親1388601/実OpenCode1388651。既存smoke未実行を確認して開始。
3分経過時の同PID生存/events0を確認。再開時9分42秒でも同PID生存、events7467B。
同handleの出力で384.873秒のskill tool、641.007秒media.capabilities実行を確認。
診断code3c3da4714841d037364a0834b52049f00a730972をcommit/push、PR #432作成。
GitHub main rulesはPR必須/必要承認0、PRはCLEAN/checks空。実機終端待ちのため未マージ。
終端未確認であり成功/失敗を先取りしない。
稼働0.28.60、Host1384554/MF1384429は変更なし。global設定/他sceneを変更しない。
終了後にstrict verifierと実Blender auto_skin inspector、Host Jobs/receipt/設定回収を照合する。
NOT TESTED: この実OpenCodeの終端/生成物、複雑character/画像付きskin/engine、全3DS/GA。


## 2026-09-10 v0.28.60 published/installed / real MCP automatic binding

PR430 merge/tag b1b62b237ea67c97b52793b51fcff2998ea02509。
exact /data1tb/ControlDeckMediaForge-release-0.28.60 でbuild_release_bundle.pyを実行、41502 exit0。
PyInstaller6.22.0/Python3.12.3、buildログ15.001秒、artifact31,542,402B、
SHA83ac8f7fb651a9ccd454618f6eeeed40470a48c797cd4c1c956974c625dd0d79。
mf-0.28.60-audit.py exit0: 202 entriesの禁止path/秘密値拡張子/certifi公開PEMを検査、
worker/frontend/schema bytes一致、新SkinBindAuto class/3schema、既存guard/cleanup/download等を照合。
packaged doctor ok/0.28.60/packaged=true。抽出package mf-0.28.60-package-8hkphpe3。
既存publisher鍵で署名/自己検証、通常公開v0.28.60へ4filesを公開。
mf-0.28.60-public-20260910へ再取得しbuild4filesと一致、実Host署名検証も成功。

外部mf-0.28.60-install.pyをHost診断venv/configで実行、45062 exit0/11.698秒。
idle/全table backup/再照合後に標準update。backup /data1tb/mf-0.28.60-update-vkfmd1mv。
DB全table fingerprint/runtime registry bytes不変、HTTP healthy、MF1384429。
実exe SHA2a8d98c52444b81c19a9d7c7c90a2b6a2810f1e4b0d7da690f025d97e1b539adはaudit packageと一致。
稼働HTTP配信scene-create schemaはexact source JSONと一致しskin.bind_autoを含む。
標準保持2版で.58実行bundleだけ整理、事前通知済み。公開releaseで回復可、.59/.60/data/runtime保持。
Hostはupdate直前/直後とも1340115で不変。今回Host変更・再起動は実施していない。

実MCP: mf-auto-skin-mcp-installed-0.28.60.py の初回tools/listがprotocol error、exit1。
証跡mf-auto-skin-mcp-installed-0.28.60-20260910、cleanup0.039秒/job_id=null、設定削除確認。
生のprotocol errorを記録していないため初回原因を確定しない。
read-only preflightはHTTP200/88,938B/24tools、同bridgeもexit0/24tools。
Hostはその間に別途1384554へ変わり、systemd開始10:31:48 JST、初回失敗file時刻10:31:47.399。
時間が近いという証拠であり、因果は未確定。Host sourceはclean main164fa26のまま。
制作Job未作成・同project exports空を確認して、resume診断を新evidence dir -r2へ実行。
再実行は新projectを重複作成せず、原失敗traceを保持する。handle80634 exit0/2.112秒。
MCP tools/list→create→status(succeeded/host_terminal_sent=true)→snapshot→export→新grant→pack。
job_3836cae7792b4431adf0d13518b44259、Host child7b305fe607a3は実DBでもsucceeded。
scene_b578b611cef04aec915f3811357c85df、revision_ddda27f9d9b543999b58e1a1eca806fb、
GLB asset_f1a2b6184d524753803df374dc0e9191。
CodeDEV/MF3DS-Auto-Skin-MCP-20260910/exports/weighted.glbは32,140B、
SHAb5c63cd8f12c853770c0fa08910ef865111521f938c127391baba44f5acb9af3。
receipt/Asset/provenance.output_sha256と実bytes一致。旧scene/revisionsとruntime registry不変。
実Blender4.5.13で同source/配置GLBを再検査: 114頂点/48混合、import480/192混合、最大2影響、
weight合計誤差2.9802322387695312e-08。idle/bend各2秒、5時刻最大world差2.4646110694144804e-07m。
共通inspectorのNOT TESTED欄はsource向けであり、MCP実行証拠はこのwrapper traceで別に確認する。
初回/再実行private config2件の不存在を独立確認。global設定/他project/既存Blender実体変更なし。

記録sliceはdocsのみ、versioned full gate1487 passed/153.76秒、build59ms/Node5を参照。
NOT TESTED: 新操作のOpenCode LLM/director、engine、複雑なcharacter/画像付きskin、この版の実cancel、
clean/失敗rollback全matrix、全3DS/GA。次は新operationの実OpenCode自然言語受入。


## 2026-09-10 v0.28.60 preparation

PR429 merge74378e8a004b019a1ee979d77433b80fd4ee4dd4確認、ux1/release-0-28-60。
addon/coreを0.28.60へ更新、release noteへ新automatic bindingと前提/制限/未受入を記載。
全 ./mf.sh test:1487 passed/既知warning2/153.76秒/exit0、viewer build59ms/生成物差分0、Node5成功。
外部mf-0.28.60-audit.py/install.pyとmf-auto-skin-mcp-installed-0.28.60.pyを準備しpy_compile成功。
前版監査を維持し、新schema/typed classの同梱・実exe/配信schema一致検査を追加。
MCP診断は専用project/actor16で新規sceneだけを作り、2clips付きGLBを配置/実再importする計画。
準備時点では実行していない。新署名公開/導入/installed MCP/OpenCode/engineはNOT TESTED。
SQLite CLI不在のためPython標準sqlite3のread-only照合で未終端Job/GUI/runtime操作すべて0確認。
稼働MF1334774/0.28.59、Host1340115。Hostは別途main164fa2690743f4956462ca597a4b911a67e13c7aへ更新済み。
今回Host変更・再起動なし。全3DS/GAはPARTIAL。次は通常merge→exact checkoutでbuild/audit/sign/公開受入。


## 2026-09-10 typed automatic skin binding — SOURCE VERIFIED / INSTALLED NOT TESTED

Base PR428 merge1e6a7d658b8f03f4287f9e36ec425c44adf50ad6、ux1/3d-auto-skin-bind。
設計GA-4へ入力/予算/失敗条件を先に追加し、既存recipe@1にskin.bind_autoを加法実装。
stable rig IDと1〜16 mesh IDs。rest/identity typed rig、独立・未bind・modifierなしmeshに限定。
合計50,000 vertices/100,000 faces/300,000 corners/1,000,000 vertex-bone pairsを処理前に制限。
finite/非縮退face/transformを検査、CPU bone heat→上位4影響/正規化→保存値/実rest形状を検査。
欠落/不正weightsはallowlist診断で工程失敗。別方式へのfallbackなし。既存skin.bindは不変。
async coreへ同期処理を追加せず、既存worker/Job/candidate/revision/exportを利用する。
3公開schemaの新definition/variantだけを除去してorigin/mainとJSON構造を比較、既存契約不変を確認。
能力一覧は同じ型定義から導出し、Blender不在時は新operationも公開しない。

実行: PYTHONPATH=backend:. .venv/bin/python scripts/3ds_game_static_e2e.py --fixture auto_skin
--runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9
--managed-root /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/blender
--evidence-dir /data1tb/mf-auto-skin-source-20260910-r3。
管理対象4.5.13、exit0/2.132秒。114頂点/224 triangles/2骨の連続sphereをbindし48頂点が複数骨影響。
idle2秒→別revisionへbend2秒追加。各clipの0/12/24/36/48frameを実評価し、端点一致と中間変形を確認。
GLB再importで480頂点/192混合（split）、最大2影響、weight合計誤差2.9802322387695312e-08。
rest差1.1920928955078125e-07m、同時刻clipの最大world点差2.4646110694144804e-07m。
GLB第1版30,596B/第2版32,140B。Scene/Asset/Job/provenanceに正規登録し実bytes/hashを照合。
scene_786e3e3b8da94a728c0f71a3ee13b849、revision40faae4882c040deaa37403a0792cb1a→2289d574e92f49a2a9f218b3bc3a25c9。
既存rigへの再bindは1/1で拒否。新mesh/rigのbind後に欠落object操作を加えたeditは4/4で失敗。
どちらもhead/2版を保持、第1版blend/GLB hash不変。診断dataは専用dirのみ、稼働Host/sceneは変更なし。

同commandに--runtime-id blender-4.5.9-linux-x64、別dir mf-auto-skin-source-4.5.9-20260910で
旧4.5.9もexit0/2.823秒、同じweight/clip誤差と失敗後旧版保持を確認。
既存rig fixtureをmf-auto-skin-rigid-regression-20260910へ実行、4.5.13/exit0/2.283秒。
11骨/25剛体meshのrest/pose/GLB再importを既存検査で確認。今回新画像生成/GUI操作は実施なし。

失敗も保持: 初回commandはPYTHONPATHにrepo root不足でimport前exit1（生成物なし）。
修正後の初回sourceはexit0/2.04秒。r2はcollapsed meshをheatが受理し診断assertでexit1/0.797秒。
この結果で非縮退face検査を追加し、r3/4.5.9で実collapsed surfaceをheat前に拒否した。
実heatソルバー自体の失敗注入ではない。欠落/NaN/負/未知骨weightはpure negativeで拒否確認。
focused auto-bind/failure reader63 passed/0.16秒、先行関連69 passed/1.55秒。
全 ./mf.sh test は1487 passed/既知warning2/169.60秒/exit0（handle67502終端）。
frontend build43ms/生成物差分0、Node5成功、diff check成功。
NOT TESTED: 署名新版/installed MCP/OpenCode、この操作の実cancel、複雑なcharacter、weight補正/IK、
歩行/root motion、全時刻の制作意図/見た目/engine取込、全3DS/GA完成。稼働版は0.28.59のまま。
次は通常merge→署名版へ同梱・導入→実Host MCP/OpenCodeで自動bindの受入。


## 2026-09-10 automatic-weight feasibility / not a published operation

Base PR427 merge b20fc16、branch ux1/3d-auto-weight-probe。
scripts/auto_weight_probe.py は管理対象Blenderだけで動く独立診断。既存sceneを開かず、
新規evidence directoryだけへfixture/source/GLB/provenanceを保存する。製品API・版数・Host変更なし。
実行: managed blender-4.5.13-linux-x64/install/blender --background --factory-startup
--disable-autoexec --python-exit-code 1 --python scripts/auto_weight_probe.py
-- --evidence-dir /data1tb/mf-auto-weight-probe-20260910-r5。
exit0、内部0.129秒、Blender4.5.13 LTS/hash daeeeca98fb0。
242頂点/2骨の連続sphereへARMATURE_AUTO、48頂点が複数骨の影響を受ける。
raw heatのweight合計誤差0.022996604442596436を観測。最大4影響へ制限して明示正規化し、
sourceとGLB再import双方で最大誤差2.9802322387695312e-08、最大2影響。
bind前後のrest差1.1920928955078125e-07m、上側骨local X 0.6radで最大変位0.384176245m。
GLB再import後はvertex splitで287頂点/51混合、同poseの対称最近点距離1.8143349382111313e-07m。
実armature modifier参照とrest/poseを照合。bone.custom_shapeとして実参照されるhelperだけを除外。
source419324B/SHA c695d51d81f0c7188ec85262f6ec69ec6d43574c2d0edb75ba2c2c0ee80b06ba、
GLB19540B/SHA 1d37cddcb53ffcd1a49b67a5fe904b2a28976eb4a3d52fa621c10e4e5aabf3d6。
script SHA76b8d3591ffa03d91a0bf5160b5083130b480c660430d8f8c70d150f7e685258。
生成物は製品Asset登録ではない。observations/provenanceにlineageとNOT TESTEDを保持する。

失敗履歴も保持: 初回はraw正規化assert、r2はhelperを含めたmesh件数、r3は丸め点集合のpose一致でexit1。
r2生成ファイルに後追いfailure/provenance記録を追加し成功に変更しない。
r4の物理距離検査成功後、NaN/負値がpositive filterで隠れないよう検査を強化してr5再実行。
tests/test_auto_weight_probe.py は欠落geometry/空geometry/NaN/負値/非正規化/剛体のみを拒否し、13 passed。
全 ./mf.sh test は1448 passed/既知warning2/144.68秒/exit0。npm run build:viewer は54ms/生成物差分0、
node --test tests/model-animation.test.mjs は5 passed。diff check成功。診断のみで新署名releaseは作らない。
NOT TESTED: typed API/MCP/OpenCode自動weight、複雑なcharacter、heat失敗処理、weight補正、
animation clip/engine取込/見た目。GA-4/5/全3DSはPARTIAL。次はbounded typed bindと失敗時旧版保持。

同時に既存OpenCode R2の終端記録をread-only確認: observations exit0/1134.769秒/8tools、
親1334951/子1335041は不在。既存strict verifierはexit1: local_offsetが要求[1.5,0,1.5]ではなく
[0.75,0,0.75]。全tool completedを制作合格と扱わない。配置物の独立Blender検査と回収監査は残件。
証跡 /data1tb/mf-opencode-array-installed-0.28.59-20260910、原events/observationsは書換えない。


## 2026-09-10 v0.28.59 published/installed / fresh OpenCode run started

PR #426 merge/tagff02850da78be483687cf94eb2ec86d60d33996f。
exact checkout /data1tb/ControlDeckMediaForge-release-0.28.59でbuild_release_bundle.py exit0。
build /data1tb/mf-0.28.59-build-20260910、artifact31,538,968 B、
SHA6238a574e1faa7e739181227431c94f3b659fc743808fbd08913e52ea009374e。
外部audit exit0、202 entriesの禁止path/秘密値拡張子/certifi公開PEM、既存worker/frontend/bytecode検査、
新配置schema同梱/排他形式説明/0.28.58との制約tree不変、packaged doctor ok/0.28.59を確認。
展開先 /data1tb/mf-0.28.59-package-nk5fpq31/control-deck-media-forge-0.28.59-linux-x86_64。
既存publisher鍵で署名/自己検証し、通常公開v0.28.59へ4filesを公開。
public /data1tb/mf-0.28.59-public-20260910の再取得4filesとbuild bytesは全一致。

外部mf-0.28.59-install.pyをHost診断venv/configで実行、exit0/11.281秒。
実Job/GUI/runtime操作0、全SQLite table snapshot/backupとregistryを保持して標準update。
backup /data1tb/mf-0.28.59-update-roe1fpqx、更新前後全table fingerprint/registry bytes一致。
installed0.28.59/HTTP health healthy、MainPID1334774、実exeとaudit package SHA一致:
4c222c8ce10b864ed200f1278152da412ab5820be632edfe1da465c4a6053ecb。
標準保持2版により旧.57の実行bundleのみ整理、.58/.59残存。事前通知済み、旧版は公開releaseで回復可。
制作物/Blender環境/既存projectを削除せず、更新後のschema HTTP200/新説明一致を確認。
schema SHA5067e13cd7fa2cb7e57d08c5392096b738b027ba96ed4a19a697f7eb51ed4fcc。

Hostは開始時1141433だったが、install直前/直後は同1327409。今回の更新はHostを再起動していない。
別途Host checkoutがclean main fc6e0a88745af2da0acfe52f4dfe6ab24b00ce3eへ進んだことをread-only確認。
Host PR312（古いtool出力prune）がmergeされ、その親にPR311が含まれる。実Broker故障受入とは別。
これ以前の「Host311未導入/更新待ち」は当時の記録であり、今の環境と混同しない。

新規OpenCode --director-arrayを同じ診断prompt/strict verifierのまま開始。
project MF3DS-OpenCode-Array-20260910-R2、証跡 /data1tb/mf-opencode-array-installed-0.28.59-20260910。
handle68218、親1334951/子1335041を確認。既存run/配送物は再作成・上書きしない。
開始時events0/終端observationsなし。旧runとHostも異なるため、新結果をMF説明だけの因果証拠にしない。
build77859/sign50517/public58930/install94170は全exit0。継続はOpenCode68218のみ。
記録sliceはdocsのみ、新規test/build再実行なし。版数gate1435passed/168.01秒/2warningsを参照。
NOT TESTED: 新規strict OpenCode終端、engine取込、全3DS/GA、今回の失敗rollback。

## 2026-09-10 v0.28.59 preparation

PR #425通常mergecc406cb2f6898348062aa4e76b560b61a3074dedをfetch確認。
branch ux1/release-0-28-59、addon/coreを0.28.59へ揃えrelease note追加。
開始時installed0.28.58、実HTTP health healthy、Host1141433/MF1260659 activeを確認。
viewer build41ms/生成物差分0、Node5 passed、diff check成功。
版数更新後の全test30474は1432 passed/1 failed/147.37秒でexit1。
前sliceと同じdirectory診断テストが全process FD数223→93の減少で等数assert失敗。
release gateの不安定性を放置せず、testだけをreader専用os proxyで実open/close追跡へ変更。
全processのGC/他処理の解放を検査対象へ混ぜず、各呼出後の未回収0と実open回数を確認する。
意図的close省略の実FD残存を検出するnegativeと、無関係FD解放が追跡へ影響しないcaseを追加。
fixture自身が意図的leakを回収する。製品reader/close処理・fallback条件は変更しない。
focused24 passed/0.02秒、全test再実行handle64212は1435 passed/既知warning2/168.01秒でexit0。
外部 /data1tb/mf-0.28.59-audit.py と mf-0.28.59-install.pyを準備、compileall成功。
前者は旧auditを継承し、新配置schema同梱・排他形式の説明・0.28.58との制約tree不変を追加検査。
後者はpublic4files一致/署名/idle/DB全table backupとfingerprint/registry保持/Host PID不変を確認して標準更新する。
両scriptはまだ未実行。build/public/署名/導入/新規OpenCode再受入はNOT TESTED。
次: full gate確定→通常PR merge→exact checkout/build/audit/sign/public再取得→標準MF update。
Host再起動や他Job停止はしない。既存制作物・前回失敗trace・全3DS/GAの残件は保持する。

## 2026-09-10 placement form guidance / source HTTP acceptance

前PR #424は通常merge5e057f1、branch ux1/3d-placement-form-guidance。
実OpenCode初回packの単一+items混在を受け、公開schemaのroot/asset_id/filename/items説明へ
SINGLEとBATCHの排他・省略するfield・1件時の単一推奨を明記。API文書も両形式へ同期。
公開oneOf/型/required/上限/拒否動作は変更しない。誤入力を暗黙に正規化して成功扱いしない。
説明の露出テスト1件、単一field混在/両方混在/null混在の書込0拒否4件を追加。
focused tests/test_contracts.py + test_host_execution.py:77 passed/既知warning1/23.61秒。

専用data /data1tb/mf-placement-guidance-source-TaysV4でsource Uvicornを127.0.0.1:19130へ起動。
実GET /schemas/project-asset-placement.jsonは200、新説明/ローカルschema一致、
descriptionを除く再帰的なschema制約treeはorigin/mainと完全一致。
HTTP body SHA5067e13cd7fa2cb7e57d08c5392096b738b027ba96ed4a19a697f7eb51ed4fcc。
初回は未セットアップ環境へhealth=healthyを期待した診断assertでexit1。
期待を見直し、実health HTTP200/setup_requiredを記録して再診断exit0/0.036秒。
両専用coreは通常Ctrl-C終了/exit0。installed core/Host/モデル/既存projectを変更しない。
NOT TESTED: installed MCPへの新説明配信、実OpenCode新規runでの混在回避。説明変更だけで改善保証しない。
全回帰handle72146は1432 passed/1 failed/147.50秒でexit1。
未変更test_scene_recipe_failure.pyのdirectoryケースが全process FD数224→94の減少で等数assert失敗。
原因を今回のschema変更やFDリークと断定しない。単独同file22 passed/0.02秒、
製品/検証ロジック無変更の全回帰再実行handle86260は1433 passed/既知warning2/148.43秒でexit0。
新規testの型注釈を補完し、その5casesも1.17秒/exit0で再確認。最初の失敗記録は保持する。
viewer再build73ms/生成物差分0、Node5 passed、専用19130 listener回収とdiff checkを確認。
署名bundle導入後に新規専用runで再受入する。
前回failed traceと配置物を保持し、全3DS/GAはPARTIAL。

## 2026-09-10 OpenCode array run terminal / delivery recovered, strict gate failed

PR #424 source8c9c0c9の診断を同runで追跡。handle27239はexit0/2038.269秒で終端。
実OpenCode session ses_f776dcfe5ffeRboleo233P0I7O、9 tool calls/36 events。
skill520.739秒→capabilities541.657→create1406.991→status1486.889→snapshot1576.130→
export1663.060→fresh grant1750.802→pack error1838.361→pack completed1934.042。
初回packは単一(asset_id/filename)と一括(items)を同時指定し、MCPはgeneric request failed。
公開oneOf/production placement_manifestのextra=forbidがこの混在を拒否することと整合する。
OpenCodeは同じasset/grantを単一形式へ修正し成功した。ただし「失敗時停止」の指示に反する。
既存strict verifierを実行し、全tool completed条件でAssertionError/exit1を確認。
検証条件を緩和せず、**今回の厳格な一巡受入はFAILED**として記録する。

制作Job job_65b1f8ced2844562897803ffb7b2adeaは実DB succeeded。
scene_abb18e599cdf4309b3d5807f576873ca、revision_43396c9ed11f43bc99818910f0e5e49a。
source asset_7c287dddd8c34480951d85dbdcf066d9、GLB asset_fb0a9d3e0ca34823b15c88fd4e4b8546。
OpenCodeが選んだ3操作はcube寸法[.4,.8,.2]、array count6/local_offset[1.5,0,1.5]、同stepの材質。
実Blender4.5.13 --inspect --fixture arrayでsource/GLBを独立検査、exit0。
6段/72 triangles/48座標、world bounds[-.2,1.7]/[-.4,.4]/[-.1,.85]とGLB再import一致。
base RGBA[0,.55,.55,1]/metallic0/roughness.6も保持。inspection.jsonは同evidence-dir。
配置先 /data1tb/ControlDeck/CodeDEV/MF3DS-OpenCode-Array-20260910/exports/stairs.glb、6232 B、
SHA5067e0095e7a7eb45665083770335c5ca68d87ea09a0c37a3314c6ba186c900f。
read-only独立照合で成功receipt/実bytes/Asset metadata/provenance.output_sha256全一致。
Host a0767ae8c170/f37c21b062cf/c03a93069fd9も実DB succeeded。
専用config runtime-config-mf3ds-cdbb011e92a7447e.json不在、親1286593/子1287125消失。
保持証跡 /data1tb/mf-opencode-array-installed-20260910。再作成/既存配置上書きはしない。

全gate1428 tests/151.72秒/既知warning2、focused37/実Blender検査、frontend変更なし。
本PRは診断追加と実失敗の記録であり、製品の配布変更なし。追加release不要。
次: media.packの単一/一括排他をtoolの説明でも明確にし、混在拒否を維持して新規実行で再受入。
任意応答喪失の補完や同grant二重配送を暗黙許可しない。全3DS/GA、engine取込/接合品質は未完了。

## 2026-09-10 OpenCode array delivery acceptance in progress

Base origin/main5e2b99c、PR #213 MERGED/9469d8eを再確認。
branch ux1/3d-opencode-array-acceptance。既存診断へ--director-arrayを追加し、
director実読込→現在schema→6段の配列→GLB→fresh grant配置を自然言語で依頼する。
world間隔X0.3/Z0.15mと元cube寸法を指定し、local offsetのJSON recipeは渡さない。
verifierは実skill先行・3操作/6段/local offset・Job成功・receipt/実bytes/DB provenanceを照合する。
6つの配列positive/negativeとpermission追加を含むfocused35 passed。
全./mf.sh testはhandle41666終端exit0、1426 passed/既知warning2/249.04秒。
viewer再build63ms/差分なし、Node5 passed、git diff --check成功。

実行中: Host診断venv/PYTHONPATH=Host backendで
scripts/3ds_opencode_flow_e2e.py --director-array --project-name MF3DS-OpenCode-Array-20260910
--evidence-dir /data1tb/mf-opencode-array-installed-20260910。
handle27239、親PID1286593/子OpenCode1287125の生存を08:53 JSTに再確認。
events.jsonlは0 bytes、observations.json未作成。実制作/配送/独立Blender検査は未確認。
観測待ちを失敗/成功扱いせず同handleを追跡し、重複run・他process停止・Host再起動はしない。
現在coreへの実HTTP /healthはhealthy。既存installed.58 MCP配列成功とは別試験。
NOT TESTED: 今回の自然言語制作完了、ゲームエンジン取込、接合品質、全3DS/GA。
次: 同run終端→verifier→保持sourceと配置GLBを実Blender --inspect --fixture arrayで照合。

継続確認: commit3e85a5bをpushしdraft PR #424を作成。再実行なしで同handleを追跡。
520.739秒でskill、541.657秒でmedia.capabilitiesが実completed、各step_finishも記録された。
OpenCode DBの専用session ses_f776dcfe5ffeRboleo233P0I7Oと一致。
skill出力3694文字/capabilities2508文字、最初のassistant入力29035/output358 tokens。
09:03 JST時点で次assistant応答待ち、制作Job/GLB/最終observationsは未確認。
同PIDのHost8765へのESTAB接続を確認。共有LLMのログではtask129の大きなprompt処理が進行するが、
本sessionとの一意対応は未確定。これを本依頼のtoken数/根本原因と断定しない。
他依頼/モデルを停止せず、同runの終端を待つ。今回追加はread-only診断記録のみ、test再実行なし。

検証器レビューで材質対象/作成順とGLB材質保持の検査不足を補完。
対象相違・primitiveより先の材質操作を拒否するnegative2件を追加、focused37 passed/0.43秒。
array_fixtureはscene meshが段1個であること、単一Principled材質のbase RGBA/metallic/roughnessが
sourceとGLB再importで1e-5以内に一致することを独立検査する。
保持済み前回MCP source_f1c4f7a5fcf54a1aa389e12ad5e04cdf.blendと
MF3DS-Array-MCP-20260910/exports/stairs.glbを実Blender4.5.13で--inspect --fixture array。
exit0、6段/72tri/48座標一致、material [.05,.25,.3,1,0,.5]保持。
証跡 /data1tb/mf-array-material-inspection-nUvgsn/inspection.json。
これは前回MCP生成物での検査器受入。待機中OpenCode runの成功にはしない。
変更後の全testはhandle85668終端exit0、1428 passed/既知warning2/151.72秒。
frontend変更なし、前回viewer/Node5結果を維持。git diff --check成功。

## 2026-09-10 v0.28.58 published/installed and MCP array delivery

PR #422通常merge/tag88c17bd2ee31c94c737349f73993528d1a60eb27。
exact checkout /data1tb/ControlDeckMediaForge-release-0.28.58でbuild_release_bundle.pyを実行しexit0。
artifact31,539,237 B/SHA750f8f1e370d0f155fb67e5ab66d48c979c22bc08bfef3352e93e39377c96285。
外部mf-0.28.58-audit.pyは202 entriesの禁止path/秘密値拡張子・certifi公開PEM・
worker/schema/frontend bytes一致、同梱ArrayModifier/公開3 schema定数、packaged doctor okを確認。
既存publisher鍵で署名/自己検証し、通常公開release v0.28.58へ4 filesを公開。
public再取得4filesとbuild bytesの一致、実Host trusted publisher検証を標準更新前に確認。

mf-0.28.58-install.pyは実Job/GUI/runtime idle、SQLite backupと全table fingerprint再照合、
registry再照合後に標準updateを実行。13.076秒/exit0、healthy/DB全table/registry保持。
backup /data1tb/mf-0.28.58-update-d8eeyh6d、Host1141433保持、MF MainPID1260659。
実/proc/1260659/exeとaudit抽出binaryのSHAはともに
1e1fb56591f781ded82d6d9c5a8188975b049c3cd8ea3025ec12c25a836a0bbd。
標準2版保持で旧.56実行bundleだけ整理し、.57/.58を保持。制作data/Blenderは削除せず、
旧bundleは公開releaseから再取得可能と通知。Host修正PR311の導入・再起動はしていない。

外部mf-array-mcp-installed-0.28.58.pyはOpenCode用の実Host MCP bridgeでtools/list、
新modifier.array公開とcreate受付を確認。ただし初回はMCP envelopeのHost Job IDと
output内のMF Job IDを取り違え、detached KeyErrorと取消拒否でexit1。
新規作成を再実行せず、受信済みjob_d5eff63dd52044c9ae19a5ea1ba2b64dの実HTTP succeededを確認。
mf-array-mcp-installed-0.28.58-resume.pyは同じMCP config/同Jobでstatus→snapshot→export→
正規project grant→media.packを続行し、1.187秒/exit0。この時間は再開区間だけを表す。
一時runtime configはfinallyで削除、残数0。Host受付12e5a1f7ca4b/child92b4abba2fccは
独立read-only DBでも両succeeded。秘密tokenをログ・証跡へ保存しない。

scene_e45604f9d7c3458c80b3604ab37fd7b9、revision_0548e2ad2ede4f8da6d4be90de3fa793、
GLB asset_9762b4505f2d4470840d1ba2c71c6266。配置先
/data1tb/ControlDeck/CodeDEV/MF3DS-Array-MCP-20260910/exports/stairs.glb、6,224 B、
SHA73d162ae1eb89b22e0eb888be13e45a27ba229846b8d3b3ffd597ee2e39488ab。
receipt/Asset/provenance/実配置bytes一致。Blender4.5.13で実blend/配置GLBを再importし、
6段/72 triangles/48座標、local scale間隔の一致を確認。再開前のscene/revision投影と
registryを再開後に比較して不変。初回診断全区間の全旧scene snapshot一致とはしない。
証跡 /data1tb/mf-array-mcp-installed-0.28.58-20260910（初回/再開eventsと実Blender inspection）。

準備gate1419 tests/158.79秒/2warnings、viewer差分0/Node5。記録sliceは文書のみ。
NOT TESTED: 今回のOpenCode LLM/director実読込、engine import、接合品質、全3DS/GA。
次: 新操作を含む実OpenCode制作受入とGA-1の後続操作。Host再起動は承認待ちのまま。

## 2026-09-10 v0.28.58 preparation

PR #421 merge93242b58453c36a6be3b003e40b7ba619bb9e276を基準にux1/release-0-28-58。
addon/coreを0.28.58へ揃え、固定個数配列の意味・上限・互換性・未受入範囲をrelease noteへ記載。
開始時currentは0.28.57、実HTTP /healthはhealthy。Host再起動は行わない。
外部 /data1tb/mf-0.28.58-audit.py/install.pyを準備。auditは既存artifact検査に加え
同梱ArrayModifierのoperation定数/非零validatorを確認する。installは旧0.28.57を要求し、
全Job/GUI/runtime idle・SQLite backup/全table fingerprint・registry保持の標準手順を維持。
実行前であり、準備を署名公開・導入済み・installed MCP受入として扱わない。
viewer build差分0/Node animation5 passed。版数変更後の全 `./mf.sh test` は
1419 passed/既知warning2/158.79秒、exit0。diff check/外部診断compileall成功。

## 2026-09-10 GA-1 fixed-count array authoring / source acceptance

base MF PR #420 mergec7a63a9、branch ux1/3d-array-modifier。Host再起動の承認返信はなく、
Host修正の導入は保留してMediaForgeの次のtyped制作操作を実装した。
`modifier.array`はstatic meshへ元を含む2〜64個の非破壊配列を追加する。
非零local_offsetはlocal mesh座標であり、object scale/rotationの影響を受ける。
relative/object/curve offsetやcaps/mergeは公開しない。parent/constraints/animation/shape-key、
二重array、不正個数/offsetを拒否。duplicate/mirrorと配列後bevelの増幅をallocation前に
既存100万geometry予算で検査し、未知GUI array設定は安全と仮定しない。
create/edit/workflowの3 schemaとcapability由来一覧、docs/api・GA設計を加法更新。
既存画像/G8/recipe operationの名前は変更せず、任意Pythonを公開しない。

実診断は `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_game_static_e2e.py
--fixture array --runtime-root /data1tb/mf-long-setup-source-20260906/runtimes/blender/blender-4.5.9-linux-x64
--evidence-dir <下記>`。4.5.13は追加で
`--managed-root /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/blender`。

- mf-array-source-4.5.13-20260910-final: 4.5.13 / 2.193秒 / exit0
- mf-array-source-4.5.9-20260910-final: 4.5.9 / 3.083秒 / exit0

隔離data/registryで実domain→workerを実行。元8 verticesのcubeから6段/72 triangles、
実評価48座標とGLB再importの全座標が一致。別revisionでX+2m、旧blend/GLB hash保持。
二重arrayはOperation1/1、過大bevelはOperation2/2でscene_recipe_failedとなり、
成功head/2 revisionsを保持。Asset SHA/provenance、runtime executable hashも一致。
初回4.5.13 runは2.162秒成功、その後拒否位置/codeのassertを強化して上記finalを再実行。
本番のruntime登録・既存scene・Host/service/global設定は変更しない。

27件の新試験でschema/不正値/未知GUI設定/増幅予算/worker事前拒否を検査。
focused実行で最初にmf.shへ引数を渡し拒否されたため、直接pytestで実行した。
最終focusedは62 passed/既知warning1/1.63秒。
viewer build成功/生成差分0、Node animation5 tests成功。
最終全 `./mf.sh test`:1419 passed/既知warning2/157.83秒、exit0。
対象code/診断のcompileallとgit diff --checkも成功。
NOT TESTED: 署名公開/installed MCP/OpenCode、engine取り込み、watertight接合、
Boolean/mesh編集/有機weights/IK/歩行/GA全体と元3DS必須受入の完成。

## 2026-09-10 retained lifecycle evidence refresh / Host deployment approval pending

前sliceはHost PR #311 mergea32567c、MF記録PR #419 mergec3d66a7まで完了。
実稼働Hostはmain6d3cd2a/PID1141433/activeで未反映、checkoutはclean。
read-only DBでHost queued/running0、MF queued/running0、GUI active0、runtime operation active0を確認。
別opencode.exe/llama-serverは存在し停止しない。Hostサービスのみの再起動可否を利用者へ確認中。
今回Host/PC/MediaForgeの再起動・checkout反映は行わない。

次の作業選択で、C/D要約表が最新の下段証跡を反映せず、autosave未実装や
installed旧→新版未受入を繰り返し指示していると確認。原因別証拠表へ限定範囲を反映した。
外部 `/data1tb/mf-current-lifecycle-audit-20260910.py` をcore venvで実行、exit0。
autosave/expiry/default-idleのraw3件の終端理由/手編集回収/cleanup記録を確認し、
復旧3 revisionの現在DB一致、旧版と復旧22 Assets/5,368,096 BのSHA/provenance一致、
実GLB mesh nodes2/2/16を再照合。証跡 `/data1tb/mf-current-lifecycle-audit-g1gzbc9j`。
read-only schema確認の初回queryは不存在path列で失敗したが、変更なし。
schema上のstorage_nameを用いた上記auditは成功。raw証跡は書き換えない。
expiryのrawにある「autosave後の複製を失った」は当時のスクリーンショットで裏付けがなく、
後続キー入力の実効果NOT TESTEDという既存の訂正を保持する。

文書だけのsliceでMF test/buildは再実行せず、git diff --checkを実施。
NOT TESTED: 今回の新規lifecycle操作/現在PID回収、全C/D/E/3DS/GA、Host修正導入。
ゲーム制作の有機weights/IK/歩行/造形品質/engine受入は独立した未完了要件として保持。

## 2026-09-10 Host queue receipt correction / installed acceptance pending

前sliceの署名0.28.57/自然画像生成記録はMediaForge PR #418で通常merge
ca9dd4fa788ce3bea6fd7de5145fb4459f219500。3DS/GAの残件は維持する。
Hostが発行した未受信request IDはMediaForgeだけで照会・取消できないため、汎用Host別PR
https://github.com/souten-yd/ControlDeck/pull/311 を実装し通常mergeした。
source a6753e0ebca7a19f6ff5fe17a492177a74b15c17、merge a32567cc02ba2f17281c3076a0bdf59525cfe477。
queue受付でprovider退避taskをmax_wait_secまで待つ処理を外し、IDで照会・取消できるようにした。
fail_fastの退避結果判定とacquireの待機は保持、公開schema/timeout/GPU割当条件は変更なし。
MediaForge側の120秒timeout延長や独自予約回収は追加しない。

Host回帰5casesは修正前2 failed/3 passed→関連58 passed/3.78秒。
隔離systemd/Uvicornの実HTTP fixtureでは退避gate閉鎖中に202/IDを0.001068秒で受信し、
同IDのGET/DELETE、別待機の退避後grant/release、最終lease0を確認。全0.194703秒/exit0。
証跡 /tmp/cd-resource-receipt-chdal_xh/observations.json、再実行可能なHost tools scriptを同梱。
実Host認証route/実GPUの証明ではない。初回fixture422の修正、最初の全testでworktree
.venv不在による2失敗もHost statusへ記録。最終全./deck.sh testは1066 passed/2 skipped/
既知warning1/95.08秒、frontend build20.47秒、compileall/diff check成功。
本番Host PID1141433/activeを保持、再起動・稼働checkout変更なし。Host修正は未導入。
このMF sliceは文書のみでMF test/buildは再実行していない。

NOT TESTED: 導入済みHost/MediaForgeでの同条件受入、実GPU退避、任意の応答喪失時の
未受信ID回収/冪等再送、全E/3DS/GA。過去のtimeout全件の根本原因と断定しない。
次: 稼働Hostの作業・接続状況と更新権限を確認して導入受入を別段階で進める。
ボーン/weights/IK/歩行/造形品質/engine受入のゲーム制作要件は引き続き未完了。

## 2026-09-10 v0.28.57 signed release and installed update

準備PR #417 merge/tag567bf2ebea44cd83bb3484bf10f967bfa60118a7。
exact checkout /data1tb/ControlDeckMediaForge-release-0.28.57で既存build_release_bundle.pyを実行。
PyInstaller6.22.0/Python3.12.3、build /data1tb/mf-0.28.57-build-20260910、exit0。
artifact31,537,008 B/SHA a8d676839fe4bab724aed179c0dc148bbcca138dee1eed0131e6501a3b0f72eb。
外部mf-0.28.57-audit.pyはCArchive202entriesの禁止path/生成物/秘密値拡張子検査、
certifi公開PEM一致、worker/schema/frontendのsource bytes一致、packaged doctor okを確認。
PYZの_acquire_host_lease bytecode/constants/namesがexact source compileと一致。
これは同梱検査であり、installed動的失敗試験ではない。audit抽出先mf-0.28.57-package-xz5e0ifc。

既存publisher鍵でsign/自己検証、tag v0.28.57/通常releaseへ公開。公開4filesを
/data1tb/mf-0.28.57-public-20260910へ再取得し、全build bytesと一致。
外部mf-0.28.57-install.pyは実Host trusted publisher検証、全Job/GUI/runtime idle、
SQLite backup/全table再照合、registry再照合後に標準release_bundle.installを実行。
10.167秒/exit0でhealthy、DB全table/registry不変。backup mf-0.28.57-update-rxtfjtk1。
Host1141433保持、MF1176927→1196201/core1196206、実processはversions/0.28.57/bin/mediaforge-core。
installed binaryとaudit抽出binary SHAは共に5eccae6d75a859463ea8b062a34c980772c99aa32d68149c656f14dfed4922d9。
50scenes/165revisions保持、更新直後active Job0。標準保持で.55実行bundleだけ整理、.56/.57を保持。
制作data/runtime/外部Blender/個人設定は削除せず、.55は公開releaseから再取得可能と通知。

準備gate1392tests/145.44秒/2warnings、viewer差分0/Node5。この記録sliceは文書のみ。
更新直後のNOT TESTED: clean installed一式、自然120秒超制作、全release失敗matrix、全3DS/GA/E。
自然長時間の画像工程は以下の追加受入で確認。他の未検証項目は継続する。

同版の追加受入: 外部mf-natural-texture-quality-0.28.57.pyで既存専用panelを再利用し、
通常workflowへ1024角/1枚/qualityを受付。0.043秒でjob_d98925b1adcc4442b8aa15f81ba6863bを返した。
今回は約106秒でadmission応答が返り、108.258秒でgenerating、346.604秒でsucceeded。
生成開始から238.346秒、全診断346.636秒/exit0。前回のtimeoutが毎回起きるとはしない。
native sd-cli PID1197716はargvの出力先を同Job IDへ照合。1秒間隔の独立読取観測で
163.032秒継続→PID消失、最大サンプルRSS27,812,859,904 B。厳密なpeakや全実行時間ではない。
sleep/SIGSTOP/CPU制限/step水増しなし。通常quality routingの既存city96/FLUX.2-dev-gguf、
実argv steps20/seed0、provenanceのlicenseはFLUX-1-dev-Non-Commercial-License。
新規weight導入はなく、この記録を商用利用条件の確認済みという意味にはしない。
PNG asset_b95ab22e65424204833a8359f1e22039、1024角/1,624,920 B、SHA
d0e112c19750e624942947ae392250ffc00773d3dd24d52173e4492d7f9fc014。
目視では青緑の装甲板・橙の印・縁の摩耗が描かれるが、陰影/ボルトも画像に含まれる。
純粋なPBR albedoやseamless、完成robotの品質合格とは扱わない。

続くmf-texture-apply-installed-0.28.57.pyで同panelへbase_colorを適用、2.202秒/exit0。
job07a489adb2de4616bdb7a766139c7f5f、revision_1b61a4db0dae4779b7a4853d664c6897を確定。
旧source/GLB hashを保持し、新revisionの画像dependency ID/hashを確認。
GLB asset_9a754bd8b707420dba6ac74f9f386c30、1,607,176 B/SHA
c2f8caaee1c9d360660eee85c0c79599517e8611dc7993fd8dd9e7c15e245b2c。
実GLB JSONを独立解析し、baseColorTexture/embedded image1/外部image URIなしを確認。
独立mf-texture-result-audit-0.28.57.pyはexit0。実Host DBで画像3e9b8f3efff4・材質638f61d48813の
両succeeded、GPU lease3a998348-03a0-4ea8-b061-7a4e7e7c4953のactivate1/renew23/release1成功。
証跡 /data1tb/mf-natural-texture-quality-installed-0.28.57-20260910（PNG/GLB/観測/独立audit）。
Eの自然120秒超制作の画像工程を補完した。Blender CPU演算、credential refresh、
今回OpenCode/GUI比較/engine取り込みの証明ではない。installed失敗通知の再現試験にはならなかった。
次: admission応答喪失の予約回収契約を調査し、残るE/GOAL-09を進める。
Host broker.submitは退避taskをmax_wait_secまで待ち得る一方、MediaForge HTTP上限は120秒。
このsource上の境界差と実稼働条件を照合する。必要な汎用Host変更は別PRとし、待機者を強制停止しない。

## 2026-09-10 v0.28.57 preparation

PR #416 merge6991877d730c982cecc5ca2eedd34d6debe0be60を基準にux1/release-0-28-57。
addon/coreの版数を0.28.57へ揃え、release-v0.28.57.mdへadmission失敗通知と残件を記載。
`./mf.sh test`: 1392 passed / 2既存warnings / 145.44秒 / exit0。
`npm run build:viewer`: exit0/生成物差分0、Node animation5 PASS、git diff --check成功。
installed0.28.56を保持、開始時Job/GUI/runtime操作は全idle。Host/PC再起動なし。
準備時点で署名公開・導入・installed修正受入はNOT TESTED。全3DS/GA/E PARTIAL。
外部mf-0.28.57-audit.py/install.pyを準備。前者はembedded admission関数とexact sourceの
bytecode/constants/names一致も検査し、後者は旧.56/全idle/DB backup/registry保持を要求する。
次はnormal mergeのexact checkoutからbuild/audit/sign/public再取得/標準updateへ進める。

## 2026-09-10 texture admission failure and Host terminal notification

前turnはPR #415 merge3f4250076c2032a667dd61e2643af21578840494と実機候補調査。
branch ux1/3d-texture-workload-acceptance。installed0.28.56/MainPID1176927、core1176932。
実bundleのimage/models.jsonとimage/worker.pyはsource SHA一致。Host/API timeoutは現行600秒、
MediaForge resource admission HTTP timeoutは120秒であり、異なる上限を混同しない。

外部診断 `/data1tb/mf-natural-texture-0.28.56.py` は、正規Agentで専用panelを作成:
scene_c19a0c389d974517b04c8eced93b0355 / revision_14e53598da744f80971ee53c94f4a19e。
画像workflow受付0.061秒、2048角/4候補/autoは測定済みmodel envelopeを超えてresource_limit。
job_ec85b76f34234e0e9523736cfb153d15/Host88e5a0d5558eは両failed、画像生成なし、診断exit1。
上限を変更せず、同sceneを再利用した1024角/1枚/qualityを
`/data1tb/mf-natural-texture-quality-0.28.56.py` で正規workflowへ受付（0.024秒）。
新weights/driver/個人設定の変更なし。job52c5bcd2827a4771a458c6f9d6b9ccdfは120.249秒で
host_unreachable/ReadTimeout、generating未到達、画像0件、診断exit1。長時間制作成功ではない。

Host DB/APIを読み、Host56526e9b5e5eがrunningのまま、request
cdf707ce-65f2-40b1-b5ac-6aa08b86a24eがwaiting/held_by_other_owner、leaseなしと確認。
blockingには稼働LLM Qwen3.8-27Bが記録されていた。LLMを停止せず、requestの応答が
120秒内に届かなかった原因全体は未確定とする。診断専用user16/Jobとの一致を照合後、
`/data1tb/mf-natural-texture-cleanup-0.28.56.py` で正規DELETE→canceled、Host PATCH→failed。
cleanup.jsonに手動診断回収と明記。製品の自動回収成功とは扱わない。
証跡は `/data1tb/mf-natural-texture[-quality]-installed-0.28.56-20260910`。

原因の一つはJobManager._acquire_host_leaseのHostApiError処理がreporter=Noneで
所有Host Jobへの失敗通知を省いていたこと。既存_updateへreporterを渡すよう修正。
Host通知も失敗した場合は既存のlocal失敗保存を維持し、attached親Jobを勝手に終端化しない。
既存拒否testへHost終端assertを追加、transport/response失敗×owned/attachedの4ケースを追加。
修正前3 FAILED、修正後対象5 PASS。新同期I/O/Host変更/公開schema変更はない。

外部 `/data1tb/mf-admission-terminal-source-20260910.py` はsource manager→実Host HTTPで検証。
admission失敗だけ注入。Host e14fa434e746/local job40a11359ce4b4029a099fcd3238cf2f5が
両failed、worker0/asset0、0.060秒/exit0。元診断はimport設定の不足で副作用前失敗、
続くStore.initialize忘れでHost作成後に失敗。同じ所有Host Jobを照合・再利用して回収し、
observations.jsonにその事実を保持した。診断Host venvはtoken発行のみ、stdin pipeで
MediaForge venvへ渡し、tokenをfile/log/argvへ保存しない。製品環境を混用しない。

`./mf.sh test`: 1392 passed / 2既存warnings / 150.11秒 / exit0。
`npm run build:viewer`: exit0、生成物差分なし。git diff --check成功。
今回の修正はまだ署名配布・installed受入前。既存UX状態は変更しない。全3DS/GA/EはPARTIAL。
NOT TESTED: 自然120秒超生成、材質候補の採用、画像品質、今回OpenCode/browser/engine、
応答喪失時の不明request IDの自動回収、Host再不通時の終端outbox。
次: この修正の署名配布・installed失敗通知受入と、admission応答喪失後の予約回収契約を調査。
Hostが発行した不明request IDを推測せず、必要な汎用Host変更は別PRとする。

## 2026-09-10 natural authoring workload calibration (120-second gate not met)

前turnはPR #413 merge8fbcdfd5c6d416b4418fe06c3b7ccf440bf0c039まで進捗。
source mainには別PR #412の0.28.56/Agent説明修正、さらに#414のbuild smoke修正が入り、保持した。
branch ux1/3d-natural-workload-measurementのbaseはf8a95af。製品変更は行っていない。
Eの自然120秒超制作に向け、既存の180秒worker timeout/64操作/骨格・clip予算を照合。
人工sleep/SIGSTOP/CPU制限/上限緩和を使わず、正規Agent→detached Host childで2候補を計測した。

```bash
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml PYTHONPATH=/data1tb/ControlDeck/app/backend /data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-natural-uv-0.28.55.py --count 8 --evidence-dir /data1tb/mf-natural-uv8-installed-0.28.55-20260910
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml PYTHONPATH=/data1tb/ControlDeck/app/backend /data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-natural-animation-0.28.56.py --count 32 --evidence-dir /data1tb/mf-natural-animation-installed-0.28.56-20260910
```

最初の8高分割球+UV展開16操作はinstalled0.28.55で2.133秒/exit0、job675ea881b4aa4998ac2354ac25b9cd7d。
Host ae05cf656fbd/local双方succeeded、scene_d06ad1f93ac34460801c042c0666dedaを作成。
実Blender4.5.13、129,024triangles/64,528vertices、GLB9,104,288 B、SHA
c1f4ab4f6203d493de8199596b2b9aec3471d635167f2f8c4b2262c609b28723。
所有recipe PID1176425の観測CPU1.93秒/RSS338,468,864 B、観測区間0.512秒。
poll間隔0.5秒のサンプルであり、CPU/RSSの厳密な総量・peakではない。

続くanimation開始前、別作業の更新でcurrent0.28.56へ変化していたため、.55固定scriptは副作用前にexit1。
そのまま再試行せず、current/healthy/core1176932(parent1176927)を照合。
実bundleのscene_recipe.py/scene_document.py bytesがsourceと一致することを確認して.56用診断を実行。
この更新・署名公開はこちらが実施したものではなく、独立release acceptance成功の主張もしない。

32剛体part・128bone階層・各600frame/24fpsのloop clip3本、37操作は6.950秒/exit0。
job99f4b0d09d61408ea9c15d0642587f72/Host d498bb419e2e双方succeeded、
scene_97449c53e65d433686aa90f8285f0dac、revision_a66c14b297a743dfb5f0bfdc248f0444を作成。
GLB実bytesを別途解析し、skin1/128joints、3animations各384channels/25秒を確認。
GLB3,953,148 B、SHA3dbb870c92c7df380aa67a16e3ab85bc9a7051491ff748f23f9a126f656f5749。
validation/export PID1177266の観測区間5.384秒、CPU29.74秒/RSS489,160,704 B。
CPU秒は複数threadの合計であり、実時間120秒超と読み替えない。短いrecipe processはこのrunでは未捕捉。

両runとも既存scene/revision投影/registry保持、新規の検証用2sceneと4assets/provenanceのみ追加。
別read-only照合で両Host終端、実blob/provenance存在/hash、所有PID消失、未終端Job0を確認。
両observationsはexceeds_120_sec=false。2候補は自然長時間試験には不適であり、Eの必須gateは未達。
この骨格出力を格好よいrobot/有機変形/歩行/engine再生の受入にしない。
次は既存の画像・材質制作の処理条件/予算を照合し、意味のある自然長時間Job候補を選ぶ。
時間稼ぎの重複操作やfixture待機を成功根拠にしない。
文書のみ、全test/build・新releaseなし。NOT TESTED: 自然120秒超/credential refresh/今回browser/engine/全E/GA。

## 2026-09-10 installed newer update candidate failure and retry

base PR #411 merge13f98cfe5b2a3560332b3bf0b5555aa34d3e1767、ux1/3d-installed-newer-update。
別image Job job_f24a44f8ea4642b99ef171ef032cffb4のrunningを確認し、変更せず自然succeededを待った。
全Job/GUI/runtime idle、4.5.13参照45scenesが全てuser:16、378,033,952 Bの固定cache SHAを確認。
外部診断 /data1tb/mf-update-failure-0.28.55.py を準備し、実core child1152107/parent1152101、
current0.28.55、展開済みtrusted preflightのSHA/argvを照合して実行した。

```bash
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml PYTHONPATH=/data1tb/ControlDeck/app/backend DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3 /data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-update-failure-0.28.55.py
.venv/bin/python /data1tb/mf-update-failure-0.28.55-audit.py
```

証跡 `/data1tb/mf-update-failure-installed-0.28.55-20260910`。専用user:16ログインのみ作りfinally revoke。
SQLite/registry backupと全47scene/162revision/関連688hashを記録し、既定を一時4.5.9へ切替。
英語Settingsの履歴確認checkbox/Removeでinactive4.5.13のみ削除（1,167,754,332 B）。
全scene/history/hash保持後、同acceptance-swordの4.5.9 GUIを起動、実RFB1310colors。
GUI session bea1375825134eb7ba2410c12d2e0a24/PID1167503を維持してaction=updateを実行。
5dd93be5c853449c9088a2b09441efb4の新候補probe PID1168098だけをpidfd SIGTERMし、
failed/blender_runtime_install_failedを確認。旧GUI ready/同PID/hash/inode46146687、全履歴/hash保持。
次のupdate83518b1544c646c9aaec10e969666808は正常probe/ready、既定4.5.13へ切替後も同GUIは4.5.9。
162.906秒のother_install_preserved_guiに結果を記録。4.5.13実GLB入出力成功、page errors0。
gui-after-other-install.pngを目視し、Blender4.5.9画面/同scene objectsを確認。手編集の試験ではない。

ただし診断終了時のregistry bytes完全一致assertが失敗し、元runは163.233秒/login回収/**exit1**。
成功stageを含むが、最上位passed=falseをそのまま保持する。無条件に再実行しない。
差分を読むと、削除/再登録した4.5.13がruntimes配列の末尾になっただけだった。
register_managedは新規rowをappendし、resolve_active/resolve_registeredはIDで検索する。
G8候補4.5.9同士の相対順序も変わっていない。配列順を元へ手書き復元せず、独立auditで
重複IDなし・全top-level fieldsと全runtime rowの一致・既定版保持を照合した。
independent-audit.jsonはaudit_passed=true/exit0、registry_identity_equal=true/bytes_equal=false。
backup対比で全47scene/162revision投影、688file SHA保持、旧exe SHA/inode維持、新exe固定SHA一致。
候補/GUI PID消失、GUI stopped、staging/removing空/未終端runtime操作0、両managed ready/health healthy。
Host1141433/MF1152101保持。新版runtimeは正規updateで復元済み、制作物/外部runtime削除なし。

製品の更新保護と独立監査は成功したが、元診断全体のexit0とは記録しない。
文書のみのPR、全test/build・新releaseなし。変更のない基準はPR #408の1387tests/146.39秒/build/Node5。
NOT TESTED: 更新中の手編集、自然発生probe故障、全scenario D/3DS/GA。
D-01/02のinstalled旧→新版差分を補完。次はEの自然な120秒超制作と既存refresh証跡を照合し、
人工queue待機ではない専用制作Jobの受入を進める。Dのsource/package限定条件は表に維持する。

## 2026-09-10 scenario D requirement-to-evidence audit

base PR #410 merge5eea4845e731bd5fc6dce9f1b83c78afe700ecfb、ux1/3d-runtime-evidence-audit。
前turnはinstalled実CDN取消再開/mergeまで進捗。本turnはread-onlyの原証跡再照合。
g8計画§4 Dの文からD-01〜12を導出し、3ds-runtime-evidence.mdへ対応表を追加。
probe failure、parallel runtime、history removal/re-edit、GUI/Job stale確認、reverse受付、
confirmation restart、external、capacity、tamper、resumeのobservations.jsonを実際に読んだ。
最初の集計はdictをlistと仮定してAttributeErrorで停止。events/checks/直接fieldを区別して再読した。
read-only失敗であり実operationを再起動していない。

実データ上、source4.5.9→4.5.13はaction=update、失敗→retry後も同4.5.9 session ready。
installedの並行受入は逆向き4.5.13 GUI中の4.5.9 exact installで、旧→新版updateではない。
次の実機sliceをこの差分に固定した。確認済みの改ざん/通常取消を再び未実装へ戻さない。
history再導入のログはstarting応答を格納しているため、それ単独をready/再編集の証拠にしない。
同sceneでの後続RFB複製/保存4→8meshesの証拠へ明示的に接続した。
external package JSONはsource mode文字列を保持しており、起動同定/inventoryは当時statusにも依存。
その限界、source容量fixture/再起動gate、installedとの差分を表へ残す。

文書のみ、runtime/cache/制作物/Host/PC変更なし。全test/build・全asset再hash・過去全操作の再実行なし。
対応表の17観測JSON読取、D行12件、相対文書リンク存在、git diff --checkを確認。
基準gateは変更のないPR #408の1387 tests/146.39秒/build/Node5。全D/3DS/GA PARTIAL。
次はinstalled旧A=4.5.9 GUI中のB=4.5.13 update失敗→正常retryを受入する。
B導入済みの短絡probeだけで並行導入成功にせず、準備の影響・全idle・履歴pin・正規追加確認・
同版cache/backupを確認する。保護拒否や他Jobを迂回しない。

## 2026-09-10 installed real-CDN repair cancellation and resume

base PR #409 merge778ef9fa92f2609e4278d76d9d18b85e2a29e17b、ux1/3d-installed-repair-resume。
既存unitの取消partial保持/manager再起動Range検証と、PR #404のsource通信fixtureを照合。
その証拠をinstalled成功へ読み替えず、稼働0.28.55の正規APIと実CDNで追加受入を行った。

```bash
.venv/bin/python /data1tb/mf-0.28.55-repair-resume.py
```

全Job/GUI/runtime操作idle、inactive4.5.9/live0/固定archive SHAを確認し、正常cacheだけ退避。
実download operation blenderop_49db32a56f6a461a94f97d5148c8ca22の正の進捗を観測後、正規cancel。
0.971秒時点でcanceled、1,671,168 Bのpartialと進捗が一致し、ETag保持、元archive先頭のSHAと一致。
旧exe SHA/inode46020214、全47scene/162revision投影、関連64 asset/provenance、registryを保持。
通常repair blenderop_c3cdcf8841b84838a66381a76cdf1390を再送し、完全archiveを事前に戻さず追跡。
downloading1.000→verifying39.160→installing48.444→probing59.835→ready60.349秒。
証跡 `/data1tb/mf-repair-resume-installed-0.28.55-20260910`、60.838秒/exit0。
保持partialのinode33327669と最終archive inodeが一致、377,929,956 B/SHA
dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d、退避cacheとも一致。
コードはexisting partialでRange/If-Rangeを送り206/Content-Range/ETag一致を検査する。
今回の動的証拠はpartial保持→同inode全archive→実probeであり、wire-level header採取はしていない。
実probeは4.5.9/background/GLB入出力、6,510members/1,168,332,002 B。
修復後旧exeは同SHA/inode46146687、既定4.5.13/SHA/inode46028345とMF1152101/Host1141433は不変。
全poll health healthy。独立read-only照合でも全scene/revision・64hash・registry・cache/backup一致、
partial/metadata回収、staging/removing空、未終端runtime操作0、health healthyを確認。
正しい旧cacheは証跡dirにbackup保持。制作物や外部runtimeは削除していない。

文書のみのPR。製品code/公開契約/版数変更なし、全test/build再実行・新releaseは行わない。
変更のない基準gateはPR #408の1387 tests/146.39秒/viewer build差分0/Node5。
NOT TESTED: wire-level Range capture、process crash/電源断、重複asyncio task取消、今回browser、全matrix。
APIの取消flagとasyncio task.cancelは別経路。今回をPR #404の重複task取消のinstalled証拠にはしない。
次はscenario Dの必須条件と蓄積したsource/installed証跡を一覧照合し、未証明の条件だけを次受入に選ぶ。
全D/3DS/GA PARTIALを維持し、ボーン/有機weight/IK/歩行等の機能追加要件を縮小しない。

## 2026-09-10 installed repair rejects tampered cache and retries

base PR #408 merged d01cacc1bfc8ce1672826dab207208faff110529、ux1/3d-installed-repair-tamper。
installed current0.28.55、MF1152101/Host1141433、全Job/GUI/runtime操作idleを確認。
外部診断 `/data1tb/mf-0.28.55-repair-tamper.py` をMediaForgeの既存venvで実行した。
source/製品code変更なし。正規loopback workspace APIのrepairを使い、runtime実行fileを直接変更しない。

```bash
.venv/bin/python /data1tb/mf-0.28.55-repair-tamper.py
```

証跡 `/data1tb/mf-repair-tamper-installed-0.28.55-20260910`、25.228秒/exit0。
baseline.jsonに全scene/revision投影・旧版関連asset hashes、registry.jsonに登録snapshotを保持。
inactive managed4.5.9/live0/exact archive identityを再照合し、正しいcacheをrename退避。
新しいcopyの最終1byteだけ反転（377,929,956 B、SHA
0dc3a9c5cea265e63777f8bd097fed6d497bbf05c22031d2eae70327ad0c2b60）。backupのSHA不変を確認。
operation blenderop_95b06c17dacf4b61b8c06cf1532d8ce3は1.848秒でfailed、
blender_runtime_install_failed / Blender archive SHA-256 differs。管理機構が不正cacheだけを削除した。
旧exe SHA/inode45649239、47scenes/162revisions、旧版関連64 asset/provenance、registry保持を確認。
有効backupをcacheへ戻し、通常repair blenderop_448938ebc3204a6facd38f956540ee15を開始。
verifying2.220→installing12.997→probing24.373→ready24.890秒。
実probeは4.5.9/background/GLB入出力、6,510members/1,168,332,002 Bを確認。
旧exeは同SHAのままinode46020214へ修復、既定4.5.13のSHA/inode46028345は不変。
Host/MF PIDも不変、全pollのhealth healthy。正常cache SHAは
dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d。
独立read-only照合でも全scene/revision投影・64hash・registry・正常cache一致、
staging/removing空、未終端runtime操作0、health healthyを確認。退避cacheは正常位置へ復元済み。

このPRは受入文書のみ。source test/buildは変更せず、直前PR #408の1387 tests/146.39秒と
viewer build差分0/Node5成功を基準とする。今回は全test再実行や新release公開を行っていない。
NOT TESTED: CDN通信中改ざん、物理ENOSPC、今回browser/GUI入力、全失敗matrix。
全D/3DS/GA PARTIALを維持。次はDの中断再開について既存source/installed証拠を照合し、
不足するinstalled download取消→再開を検証する。利用者の他JobやHost/PCは停止しない。

## 2026-09-10 repair capacity failure preservation

base PR #407 merge3c9e21b3953e428353cbb8fef14ff95c06481e1e、ux1/3d-repair-failure-acceptance。
PR #213はmerged、別PR #406のbuild self-checkも保持。直前turnはボーンの意図確認のみ。
未commitだった修復失敗試験を照合し、対象20ケースを再実行して成功を確認した。
追加3ケースはhash不一致/修復前容量不足/展開前容量不足の拒否と、旧exe bytes/inode・registry保持、
失敗staging不在、その後の正常repairによる同bytes・別inodeへの公開を検証する。
archive/probeはunit fixtureであり、稼働版の改ざん受入とは扱わない。

```bash
PYTHONPATH=backend:. .venv/bin/pytest -q tests/test_blender_history_removal.py --tb=short
PYTHONPATH=backend:. .venv/bin/python scripts/3ds_repair_live_e2e.py --evidence-dir /data1tb/mf-repair-capacity-source-20260910-r2 --capacity-failures
```

後者は固定隔離rootの実4.5.9/実archive/実TCP APIを使用し、容量照会だけfree=0へ制御する。
物理diskを満杯にはしない。元試験のobservations.jsonは12.869秒passed、process不在を確認し、
失われたterminal handleを再起動理由にせず、完了確認後に別evidence dirで再実行した。
最終-r2は11.120秒/exit0、前段0.322秒・展開前10.649秒にinsufficient_diskで終端。
旧exe inode51918004、registryと6 asset/provenanceを合わせた8hash、同scene応答を保持。
両失敗後に実Blender preflightで4.5.9/background/GLB import/exportを確認した。
healthは隔離sourceのsetup_requiredで応答。installed healthyやGUI入力遅延の証拠ではない。
独立read-only照合でも8hash一致、staging/removing空、未終端runtime操作0を確認。

viewer build生成差分0、Node animation5ケース成功。最初のNode指定は不存在filenameで失敗し、
実在するtests/model-animation.test.mjsで再実行した。./mf.sh testは1387 passed/2既存warnings/146.39秒/exit0。
py_compileとgit diff --checkも成功。
製品code・公開契約・版数・Host・稼働版への変更なし。全D/3DS/GA PARTIAL。
NOT TESTED: 物理ENOSPC、installed改ざんcache拒否/再試行、今回のbrowser/GUI入力、全失敗matrix。
次は稼働版0.28.55の全idleを再照合し、正しいcache退避→改ざんcopy拒否→正常cache復元/repairを受入する。

## 2026-09-10 v0.28.55 signed release and installed real-CDN repair

準備PR #405 merge/tag aa940cd4e569c19216cee37bb03f8c99cf8ccf18を
`/data1tb/ControlDeckMediaForge-release-0.28.55` へexact checkout。既存bundle-build環境で
build_release_bundle.py --version 0.28.55 --output-dir /data1tb/mf-0.28.55-build-20260910 を実行。
PyInstaller6.22.0/Python3.12.3、artifact31,537,666 B、SHA
f6b4c31dd30e459b61face3b63772f2c71a6de697bdd60ea17e3310cbe5c716a。
外部mf-0.28.55-audit.pyでCArchive202 entries、禁止path/生成物・秘密値拡張子の検査、
certifi公開PEM一致、worker/schema/frontend source bytes一致、packaged doctor ok/0.28.55を確認。
PYZの既存修復guard/参照cleanup/RFB/monitorと新_download_io/_append_download_chunkの同梱を監査。
code nameの構造監査を重複取消のinstalled動的試験と混同しない。
audit抽出先はmf-0.28.55-package-k44om2jl、verification.jsonはbuild配下。

既存publisher鍵（0600）で正規sign、tag v0.28.55/public通常releaseを公開。
公開4filesを `/data1tb/mf-0.28.55-public-20260910` へ再取得し、build bytes一致/実Host署名検証。
別image.edit2件の自然成功を確認し、Job/GUI/runtime操作の全idle→SQLite backup/全table照合→
再度idle/fingerprint/registry照合後に標準release_bundle.installを実行した。

```bash
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml PYTHONPATH=/data1tb/ControlDeck/app/backend /data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-0.28.55-install.py
```

10.698秒/exit0で0.28.55 healthy。backup/evidenceは `/data1tb/mf-0.28.55-update-4i5zx261`。
DB全table/registry bytes不変、MFは1116213→1152101、Host1141433は更新前後で不変。
本turn開始時点でHostは以前の667000から1141433へ変わっていた。こちらからHost/PC再起動は行わない。
標準保持で0.28.53実行bundleのみ整理、0.28.54/.55保持。制作data削除なし、公開releaseから再取得可能と通知。

導入後 `/data1tb/mf-0.28.55-repair-download.py` を実行。idleとinactive4.5.9/live0を再確認し、
既存の正しいarchive cacheだけを証跡dirへrename退避。runtime自体を先に削除しない。
正規loopback workspace APIから4.5.9 repairを開始し、実CDN→書込進捗→hash/展開→実probe→同版公開を確認。
証跡 `/data1tb/mf-repair-download-installed-0.28.55-20260910`、58.081秒/exit0。
operation blenderop_4335ed440ad847d98aa16ec90dd42348。
downloading0.286→verifying36.409→installing45.706→probing57.073→ready57.589秒。
377,929,956 B/SHA dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d、
退避cacheとも一致。実probeは6,510members/1,168,332,002 B/Blender4.5.9/GLB入出力成功。
health112 samples全healthy。download中70 samplesのp95（nearest rank）0.967ms/max1.072ms。
これはloopback HTTP healthでありGUI入力遅延や全setup off-loop保証ではない。
47scenes/162revisions投影、旧4.5.9関連64 asset/provenance hashes、registry bytes保持。
旧実行fileは同SHAのままinode46020227→45649239（同版修復）。既定4.5.13/SHA/inode46028345不変。
Host1141433/MF1152101はrepair前後でも不変。元cacheは証跡dirへ保持し、新cacheは検証済み同bytes。
独立read-only比較でも更新backup対比の全scene/revision投影、64hash、registry一致、未終端runtime操作0を確認。
managed staging/removingも空であることを再照合した。

準備gateは1384 tests/165.44秒/build/Node5成功。この受入記録は文書のみ、全test再実行とはしない。
NOT TESTED: 今回のopaque browser操作、installed重複取消、Web pack実download、物理ENOSPC、
改ざん/中断全matrix、全setup off-loop、全D/3DS/GA。次はD失敗matrixの不足とmetadata I/Oを照合する。

## 2026-09-10 v0.28.55 release preparation

base PR #404 merge96b7d0e13d4292497629dc124b1accb7d0c1914e、ux1/release-0-28-55。
前turnはdownload I/O修正/PR #404 mergeまで進捗。addon/coreを0.28.55へ揃えrelease noteを追加。
全1384 tests/2既存warnings/165.44秒/exit0、viewer build生成差分なし/Node5/diff check成功。
この準備commit時点では署名公開/installed更新は未実施。
現在installed0.28.54 healthy、MF1116213、Host1141433を実照合。
別image.edit job_a248d36966704d6388aa4b55fd7045feは自然成功、その後のworker1144063消失も確認。
次のjob_a1dc8c94700c49cf963e41e7755e7fb7 queuedを確認したため、更新はまだ開始しない。
通常の公開物build/audit/署名/再取得準備を進め、導入前に全Job/GUI/operation idleを再検査する。
容量不足/改ざん/中断matrix、全D/3DS/GA PARTIALを維持する。

## 2026-09-10 download write/progress isolation and repeated cancel

base PR #403 mergec39c606f839b9c991b389d46f59e8bf3474f02b8、ux1/3d-download-write-isolation。
前turnは削除確認再起動受入/PR #403 mergeまで進捗。Dの容量/改ざん/導入中断を照合中、
_download_attemptがchunk書込・flush・進捗DB更新・fsyncをevent loopで同期実行していると確認。
進捗更新とfsyncのthread identityを検査する2ケースを追加し、修正前の2 REDを再現した。
遅いstorageがcoreを止める不具合を先に修正し、物理容量不足などのmatrixは未完了のまま維持する。

Blender/Web pack共通downloadにowned _download_ioを追加。
chunkごとの取消flag照合・書込/flush・進捗更新と最終fsyncをworker threadへ移す。
開始済みthreadは1/3回取消でもshieldを繰り返して終端まで追跡し、例外を握り潰さない。
partialはO_NOFOLLOW/O_NONBLOCKで既存fileだけopenし、regular/期待sizeを照合する。
symlink/欠落/size変更/FIFOを拒否し、外部target不変/進捗0をtestで確認。
fsync/progressそれぞれの1/3回取消でも待機継続→partial/progress保持を確認。追加10ケース成功。
既存managerのinstall/cancel/ETag再開の回帰も成功。
ただしdownload metadata/他のsetup DB・filesystem操作まで全てoff-loopにした変更ではない。

```bash
PYTHONPATH=backend:. .venv/bin/python scripts/3ds_download_io_e2e.py --evidence-dir /data1tb/mf-download-io-source-20260910
PYTHONPATH=backend:. .venv/bin/python scripts/3ds_download_io_e2e.py --evidence-dir /data1tb/mf-download-io-source-20260910-r2
```

新規専用data/cacheだけへ書き、既存隔離rootの検証済み4.5.9 archiveをread-only参照。
HTTP transportは固定fileをstreamするfixture、write遅延も明示gate。runtime導入や実CDN試験ではない。
初回0.958秒passed/exit0、型注釈整理後-r2は0.993秒passed。
実TCP core healthはwrite gate中5.686ms/setup_required、3回取消でも開始済みwriteを待機。
解放後partial/progress=1,048,576 Bを照合し、同ETag/Range=1048576から残りを再開。
完了377,929,956 B、SHA dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d。
元archiveも同hash保持、partial/metadata回収。最後はdownload-only fixtureのoperationをcanceledにし、
導入成功と偽らず次回起動でinstallを自動再開させない。専用coreもshutdown。
既存画像・runtime・scene・Host/installed環境を変更しない。証跡のdownloadコピーは専用dataへ保持。
独立read-only照合で-r2のarchive bytes/hash、operation canceled/bytes_done=377929956、partial0を確認。
全gate: ./mf.sh test は1384 passed/2既存warnings/145.75秒/exit0。
viewer build生成差分なし/Node5、py_compile/diff check成功。

NOT TESTED: この修正の署名配布/installed受入、実CDN、物理ENOSPC、Blender/Web pack実導入、
全setup経路のoff-loop保証、全D/3DS/GA。次はこの製品修正を署名releaseへ含めて導入確認し、
その後Dの容量不足/改ざん/中断の残件へ戻る。

## 2026-09-10 durable removal confirmation across isolated core restart

base PR #402 merge2aa28ac26e6da9629eae457d0e433fa411b7aba5、ux1/3d-removal-confirmation-restart。
前turnはJob逆順受付受入/PR #402 mergeまで進捗。本sliceはscenario Dの接続再作成/再起動時確認保持。
`scripts/3ds_removal_restart_e2e.py` を追加。固定された既存隔離rootだけを使い、
初期read-only検査でJob/GUI/runtime operationの全idleとasset/scene snapshotを確認する。
親が専用TCP socketを確保し、FDを配列引数のowned child coreへ渡す。個人設定/Host変更なし。
最初のcoreだけ_removeを非同期gateへ置換し、確認内容がdurable preflightにある時点で待機させる。
確認用HTTP clientを閉じて別clientで同一operationを再照会後、owned process handleへSIGTERM。
終了をwaitで確認してから、fixtureなしの別coreプロセスを起動し、実削除を再開する。
任意PID探索/killはしない。stop上限を超えた場合は自分のchildだけkillして失敗し、成功扱いしない。

```bash
PYTHONPATH=backend:. .venv/bin/python scripts/3ds_removal_restart_e2e.py --evidence-dir /data1tb/mf-removal-restart-source-20260910
```

実測は23.113秒/親exit0。0.422秒に専用core1134091起動、health=setup_required。
0.695秒にHTTP client再接続で操作blenderop_5bb9e9fbe041478f867d28215f4fbcb2の
acknowledge_history=true/全removal_previewの一致を確認。対象はinactive4.5.9、project参照1/live0。
0.900秒に旧core終端（SIGTERM returncode=-15）、1.317秒に新core1134111起動。
1.341秒に同じoperation ID/preview/fingerprint/ackを保持してready、旧runtime不在/6hash・scene/revision不変。
22.966秒に同版4.5.9再導入成功、固定archive SHA dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d、
実probeは6,510members/1,168,332,002B/GLB入出力成功。元の既定4.5.9も復元。
23.113秒に新coreもSIGTERM終端（-15）。親exit0を子exit0と混同しない。
独立read-only照合で旧6hash/全scene-revision投影保持、2runtime登録/既定4.5.9、
staging/removing空、両専用PID不在を確認。隔離実行環境のみ一時削除/同版復元、制作物削除なし。

unitはhistory restartの5確認条件（正常/ack欠落/不正型/active変更/catalog変更）を
queued/preflight/deletingの3 journal stateへ拡張（10ケース追加）。
ここでdeletingはDB状態fixtureであり、rename途中の実crash試験ではない。対象17ケース成功。
全gate: ./mf.sh test は1374 passed/2既存warnings/148.10秒/exit0。
npm run build:viewer生成差分なし、Node5、py_compile/diff check成功。
製品code/公開契約/Host/installed環境/版数/署名artifactは変更しない。
NOT TESTED: installed Host/opaque browser、電源断、mid-rename crash、GUI再編集、
例外時自動再導入、全D/3DS/GA。全体完了へ拡大しない。
次はscenario Dの容量不足/改ざん/導入中断の既存証拠と実installedとの差分をまとめて埋める。

## 2026-09-10 removal-first recipe Job admission

base PR #401 merge731f52fc40969240998e6a42bdf4350a71ffedd2、ux1/3d-removal-first-job。
前turnはGUI逆順受入/PR #401 mergeまで進捗。今回は同じ実削除commitと制作Job受付を組み合わせた。
`scripts/3ds_runtime_removal_e2e.py` の `--hold-removal-job` は既存hold-removal/history-reinstallを必須とする。
real SceneRecipeJobManager.submit/SceneWorkspace.acquire_recipe_runtimeと実scene pinを使い、
Hostだけは呼ばれたら失敗するfixtureにする。認証/実Host child受付を証明するものではない。
scene.edit要求は既存current revisionを指定。active4.5.13、scene pin4.5.9の状態で、
4.5.9削除guard中にJob取得thread到達/pending/Host未呼出を確認する。
解放後はscene_runtime_unavailableで拒否し、保存済みJob投影の前後一致・task/ref回収を検査する。

```bash
PYTHONPATH=backend:. .venv/bin/python scripts/3ds_runtime_removal_e2e.py --evidence-dir /data1tb/mf-removal-first-job-source-20260910 --history-reinstall --hold-removal --hold-removal-job
```

隔離rootは既存 `/data1tb/mf-clean-packaged-0.28.32-QBvHfm` のみ。25.762秒/exit0。
2.240秒health1.637ms/setup_required、JobとGUI受付pending。
2.547秒Job拒否/Host呼出0/新Job0/runtime refs0、2.589秒GUIもHTTP422/record追加0。
2.780秒旧runtime不在・scene/revision/Library投影/6 asset-provenance hashes保持。
固定4.5.9 archive（SHA dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d）
再導入の実probe成功。同sceneのGUI再起動/停止後、元の既定4.5.9へ復元した。
独立照合: 同6hash保持、active GUI0、2runtime登録、staging/removing空。
session a62a856bac7f4b2dae23c2a3ff3a4593 / eff858c3bdab43219f460b1e5700f826 の
専用unitsはnot-found/inactive/MainPID0。installed/Host/個人Blenderは変更しない。
隔離された実行環境だけ一時削除/同版復元し、制作物・履歴を削除しない。

unitは既存GUI/working逆順testへrecipeケースを追加。
初回の3失敗は、fixtureのscene作成Jobが存在するのに空リストを期待したtest側の誤り。
既存Job投影との一致へ修正後、対象/recipe-pinの22ケース成功。製品不具合のREDとはしない。
製品code/公開契約/Host/版数/署名artifact変更なし。
全gate: ./mf.sh test は1364 passed/2既存warnings/160.27秒/exit0。
viewer build生成差分なし、Node5、py_compile/diff check成功。
NOT TESTED: installed/実Host Agent HTTP/OpenCodeの逆順受付、create retry/materialの逆順、
自然遅延、GUI入力、例外時自動再導入、全D/3DS/GA。
次: durable削除確認の中断・core再起動時保持を実処理で確認する。

## 2026-09-10 removal-first GUI admission, isolated real runtime

base PR #400 merge9b0f3323bb3a4bdf363ba20e56278cf348dfac96、ux1/3d-removal-first-admission。
前turnの意図確認だけでは実装進捗なし。PR #213のmerged状態と現行main/規約/設計を再照合。
既存testの「resolve_registeredを不在に置換」は削除中の競合を証明しないため、
逆順のGUI/working受付unit 2件と、既存実機scriptの--hold-removalを追加した。
製品code・公開契約・Host・版数・署名artifactは変更しない。

```bash
PYTHONPATH=backend:. .venv/bin/python scripts/3ds_runtime_removal_e2e.py --evidence-dir /data1tb/mf-removal-first-source-20260910-r2 --history-reinstall --hold-removal
```

対象は既存の隔離root `/data1tb/mf-clean-packaged-0.28.32-QBvHfm` のみ。
実removeのrename後/unregister前、removal_guardを所有するworker threadに最大15秒の明示gateを置く。
新規GUIの_create_guarded到達を別eventで確認してからHTTP healthと受付pendingを検査する。
fixtureは時間順の制御だけで、削除・registry更新・再導入probe・GUI runnerは実処理。
finallyでgateを解放し、開始済みHTTP要求/削除pollを終端まで待つ。

初回 `/data1tb/mf-removal-first-source-20260910` は25.568秒/exit0、health1.377ms。
最終scriptの-r2は25.340秒/exit0。2.241秒時点でGUI受付pending、health HTTP成功/1.581ms。
health本文はsetup_requiredでありhealthy受入とはしない。
削除commit後、2.588秒でscene_runtime_unavailable/HTTP422。拒否したGUIのdurable record追加0。
2.778秒で旧版不在、scene/revision・Library投影・6 asset/provenance hash保持。
同じ4.5.9を固定archive SHA dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d
（377,929,956 B）から再導入し、実probeで6,510 members/1,168,332,002 BとGLB入出力成功。
同scene_2642c93f480d427d920267ac790405e2を4.5.9で再起動→停止、元の既定4.5.9へ復元。

独立照合でactive GUI0、.removing/.staging空、2runtime登録/既定4.5.9、6files hash保持。
専用session c27cdc338d294899a97083cee51df2d1 / 621208cf21904f21a150f21da63acace の
正しいunit名をコードから照合し、双方not-found/inactive/MainPID0。
最初のunit照会はblendersession_を含めた誤名だったため、正しい名前で再検査した。
隔離環境の4.5.9実行環境だけを一時削除・同版再導入した。制作物やinstalled環境は削除していない。

gate: ./mf.sh test は1363 passed/2既存warnings/146.80秒/exit0。
型注釈整理後の対象test再実行9ケース成功、npm run build:viewerは生成差分なし、
node --test tests/model-animation.test.mjs は5 passed、py_compile/diff check成功。
NOT TESTED: installed Host/opaque browserでの逆順競合、自然な遅延、Job逆順受付、
GUI framebuffer/手編集、例外時の自動同版再導入、全D/3DS/GA。
失敗経路の全matrixへ拡大しない。次はJob受付の逆順保護を同じ実削除commit条件で検証する。

## 2026-09-10 installed Job admission blocks stale and fresh removal

base PR #399 merge86fb8bec08a206620f306cb5d8a11cd40e360a87、ux1/3d-installed-job-removal。
前turnは署名0.28.54公開/導入/ブラウザ回帰/通常mergeまで進捗。
既存sourceのHost待機fixtureだけではinstalled Job受付との削除競合を証明しないため、
実Host child/Agent HTTPとworkspace bridgeによる専用Job受入を追加した。製品変更なし。

外部診断 `/data1tb/mf-job-removal-0.28.54.py` をapply_patchで作成。
最初の実行はidle gateでexit1。別image.edit job_df77ab94ca3e4bacbc1e97e89cf4b476がrunningだった。
ログイン・設定変更・証跡directory作成前の拒否。実MF cgroupのPython PID1120012も確認し、
他Jobを止めずread-only追跡。元Jobのsucceededと未終端Job0を確認して再実行した。

実行:

```bash
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml PYTHONPATH=/data1tb/ControlDeck/app/backend DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3 /data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-job-removal-0.28.54.py
```
既存mf-e2e/user16の一時loginをfinally revoke。Agent HTTPのservice tokenは既存正規issuerで
TTL60秒・actor16へ限定し、メモリ内だけで使用、出力/ファイル保存なし。
全idle/非active旧版/live0/project2を検査し、workspace正規switchで既定を一時4.5.9へ。
既存sceneには触れず、新規64 uv_sphere（各vertices128）のbounded recipe Jobを受付。
受付直後に既定4.5.13へ戻し、旧版へ固定された実Job参照がある場合だけ削除を要求する。
すでにJobが終端なら削除要求を送らず失敗終了する。finallyで自分のJobだけ取消し、
既定が自分の一時設定のままなら戻す。他actorの第三の既定変更は上書きせず検知する。

証跡 `/data1tb/mf-job-removal-installed-0.28.54-20260910/observations.json`、7.261秒/exit0。
6.470秒idle preview→6.609秒job_486ad88e1663442b81b71f50dbfd8bec受付、
実Host child7b29f60793dd/detached=true。旧版はinactive、live3（in-process2/recipe_jobs1）。
6.800秒の古いfingerprint+ack=trueをremove_changed、6.863秒のfresh live確認+ack=trueをin_use拒否。
GUI/working copy参照は0で、Job参照による遷移を分離できた。
自分のJobを正規APIで取消し、7.070秒canceled/host_terminal_sent=true/live0へ回収。
旧preview fingerprintへ戻りcan_remove_with_history=trueとなったが、実削除は行っていない。
新scene/revision追加なし、取消Jobのasset_idsは空。全既存scene/revision投影・registry bytes・旧exe hash/inode不変。
旧exe SHAde8e8092c49e42cc6f1adde86aea0202ea5bad3338725887ecbcb7274dd0f926/inode46020227。
7.095秒cleanup/既定復元確認、7.261秒一時login revoke。

独立DB照合: Host childとMediaForge Jobは双方canceled、未終端Job0。
以前の受入baselineの72 files hashも保持。MF cgroupはmain1116213/core1116217だけでBlender子なし、
Host667000/MF1116213 active/PID不変。Job実行中のBlender PID自体は採取していないため、
生成完走や特定の演算段階でのprocess取消の証拠にはしない。
文書のみ。製品gateは0.28.54準備1361 tests/139.39秒/build/Node5を参照、今回再実行ではない。
診断py_compile/diff check成功。全D/3DS/GA PARTIAL。
NOT TESTED: installed重複取消、削除実行中の逆順受付、確認の切断/再起動保持、容量不足/中断等。
次は削除処理が先に始まる逆順の受付保護と既存実機証拠を照合する。


## 2026-09-10 v0.28.54 signed and installed

準備PR #398は通常merge8b5bb0375e09bae1523275e4e8f3dfb89244a460。
exact checkout /data1tb/ControlDeckMediaForge-release-0.28.54/tag v0.28.54。
既存build_release_bundle.py/PyInstaller6.22.0/Python3.12.3で軽量bundleを作成。
出力 /data1tb/mf-0.28.54-build-20260910、31,535,647 B、
SHA310c7b8a037780faef25e94c65ff156b766ad0cb56b88266a317bb5132ef6c33。
外部診断/data1tb/mf-0.28.54-audit.pyでCArchive202 entries、検査対象の禁止path/生成物拡張子なし、
certifi公開PEM一致、worker/schema/frontend exact bytes、既存修復/RFB/monitorと今回cleanup構造を照合。
packaged doctor:ok/version0.28.54/packaged=true。
展開先 /data1tb/mf-0.28.54-package-nh4o5lhq/control-deck-media-forge-0.28.54-linux-x86_64。
verification.jsonに監査結果を記録。コード構造の照合をinstalled重複取消動作の証拠へ読み替えない。

既存publisher鍵/mode600でsign_release.py sign・自己署名検証を実施し、正規公開:
https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.54
公開4filesを/data1tb/mf-0.28.54-public-20260910へ再取得。
Host診断venv/既存CONTROL_DECK_CONFIG/PYTHONPATHで/data1tb/mf-0.28.54-install.pyを実行。
公開bytes一致/実Host trusted publisher検証、idle→SQLite backup/registry backup→全idle/全table再検査→標準update。
10.052秒healthy、DB全table fingerprint/Blender登録bytes不変、Host667000不変、MF1116213。
backup /data1tb/mf-0.28.54-update-tz3fdb8w、observations.jsonに前後照合を保持。
標準保持規則で0.28.52実行bundleだけ整理、0.28.53/.54を保持。制作物/runtime削除なし。
旧bundleは公開releaseから復元可能と利用者へ通知。PC/Host再起動なし。

準備gateは全1361 tests/139.39秒/既知warnings2、viewer build生成差分なし/Node5成功。
本記録sliceは文書のみ。全3DS/GAはPARTIAL、installed重複取消/Job削除競合の残件を維持。

installed回帰は既存Host診断venv/CONFIG/PYTHONPATH/DISPLAY/XAUTHORITYで
`/data1tb/mf-stale-removal-after-ack-0.28.54.py`を実行。
証跡 `/data1tb/mf-stale-removal-after-ack-installed-0.28.54-20260910`。
同意済みSettings削除preview→同旧版GUI起動→古い確認buttonのremove_changed拒否、
fresh live確認+ack=trueのin_use拒否、operation追加0、実opaque RFB描画1321色を確認。
49.978秒passed/57.998秒own cleanup/58.057秒login revoke/exit0/page errors0。
同acceptance-sword第14版・source/GLB28hash・旧runtime hash/inode・registry bytes不変。
終了後の独立照合でも前baselineの3 scenes/current pin・72 files保持、GUI0。
session1bcc8c9ab5bb41949dcbef31e924a111のunit not-found/inactive/MainPID0、MF1116213/Host667000不変。
この回帰はGUI/削除保護の証拠であり、本修正の重複取消をinstalledで発生させた証拠ではない。
次はJob受付と削除競合の未検証条件を補完する。全3DS/GAは引き続きPARTIAL。


## 2026-09-10 v0.28.54 release preparation

PR #397 mergef48f5db04f88627612ca8672df4d9d25a4e75d37と最新handoffを確認。
前turnは重複取消のruntime参照漏れ修正/実Blender受入/通常mergeまで進捗。
ux1/3d-release-0-28-54でaddon/core版を0.28.54へ揃え、release noteを追加。
本修正のsource受入と未配布/未検証範囲を区別する。公開契約/DB/runtime版変更なし。
次は準備PRを通常mergeし、exact commitからbundle監査・署名・公開再取得・標準更新を行う。
全3DS/GAはPARTIAL。既存untracked .venvは保持し、Host/制作物へ変更しない。
全`./mf.sh test`: 1361 passed/既知warnings2/139.39秒/exit0。
viewer build成功/生成差分なし、Node animation5 tests/diff check成功。
ephemeral /data1tb/mf-0.28.54-{audit,install}.pyを前版から準備しpy_compile成功。
auditは今回の_finish_cleanupと3箇所の回収構造を埋込みPYZでも検査する。
installは公開4files一致/Host署名/旧版0.28.53/全idle/DB backup/再検査を要求する。
まだ両診断の本処理は未実行。現在installed0.28.53、MF1082083/Host667000 active/PID不変、
実DBの未終端Job/GUI/setupは0。公開・導入時には再確認する。


## 2026-09-10 repeated admission cancellation runtime-reference cleanup

base PR #396 merge2a0d80dc4580a25567260088e76e71980741ac32、ux1/3d-admission-repeat-cancel。
前turnはinstalled stale削除確認/GUI受付の再拒否と通常mergeまで進捗。
Job受付の参照保護を調査し、取得thread待ちの取消が重なるとruntime参照が漏れる不具合を再現。
tests/test_scene_recipe_runtime_pin.pyの取消回数を1/2/3へ拡張し、修正前は2/3回の2ケースが
live_reference_count=1（期待0）でRED。最初のshield後、取消処理のawait acquisitionへ
次の取消が伝播し、実threadが返すExitStackを受け取れなくなるためだった。
これは削除を誤許可する観測ではなく、不要な使用中参照が残る障害。

SceneRecipeJobManagerの取消時取得回収を別のowned cleanup taskへまとめ、
反復shieldで追加取消から保護し、実threadの終了とreferences.closeまで待ってから元例外を返す。
Host受付失敗時のcloseと実行task finallyのcloseにも同じ回収待ちを適用。
処理の例外はtask.resultで伝播させ、握り潰さない。同期の参照取得/解放はto_threadのまま。
取消を無視して制作を継続する変更ではなく、開始済み資源回収だけを最後まで追跡する。
さらにHost失敗/正常制作後の解放thread待ちへ3回取消を入れる2 testsで、
gateを開くまではtask未完了/live1、終われば追跡0/live0を確認。関連3 test filesはPASS。
公開API/DB/schema/Host/版数変更なし。

既存scripts/3ds_recipe_runtime_pin_e2e.pyへ明示的な取得遅延fixtureと3回取消を追加。
専用data/registryだけを書込み、既存隔離runtimeは読取参照する。
実行コマンド:

```bash
PYTHONPATH=backend:. .venv/bin/python scripts/3ds_recipe_runtime_pin_e2e.py --evidence-dir /data1tb/mf-repeated-admission-cancel-source-20260910 --managed-root /data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/runtimes/blender --legacy-root /data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/runtimes/blender/blender-4.5.9-linux-x64
```
1.037秒/exit0。3回取消ではHost child未作成/live0へ回収し、その後の通常制作では
Host待ち/slot待ちlive1・登録解除拒否・実Blender4.5.9によるcube制作成功・終端live0を確認。
job_a7ff774c5bc84c08a18ab2f98781664a、scene_f83b8aeab6de4e838a13445e3b355d15初版、
source426,899 B/SHA dca6c173718d2ae47133d9d927932d72b6d86c2da0fdd17dd6f785785ee7960e、
GLB1,756 B/SHA a9a481e36f7508a853767920c73bb42d2a541ddfbd9a956b6afb132a8a0d3e20。
旧Blender executable SHAde8e8092c49e42cc6f1adde86aea0202ea5bad3338725887ecbcb7274dd0f926不変。
Host応答/取得遅延はfixture、Blender batch/独立検証は実process。installedでの重複取消とは区別する。
NOT TESTED: この修正の署名配布/installed受入、Jobと実削除のinstalled競合、全D/3DS/GA。
次は全gate/通常merge後、既存署名release経路で配布しinstalled受入を進める。

全`./mf.sh test`: 1361 passed/既知warnings2/152.33秒/exit0。
viewer build成功/生成差分なし、Node animation5 tests/py_compile/diff check成功。
診断の取得timeout時にも取消してから待つfinally経路を整え、最終コードを別証跡-r2で再実行。
`/data1tb/mf-repeated-admission-cancel-source-20260910-r2`、0.660秒/exit0、
3回取消/Host未呼出/参照0→通常制作成功/参照0、GLB size/hashは初回と一致。
job_3c7d840247e443f28cab51190e00eaf1、scene_e63f56934a904984b298b2c7de47a86f。
取得timeout自体の実機注入は未実施。installed MF1082083/Host667000 active/PID不変。
既存untracked .venvは保持。全D/3DS/GAはPARTIAL、修正のinstalled受入は次release以降。


## 2026-09-10 installed stale removal confirmation versus GUI admission

base PR #395 mergeb871ccd54476070bbf786af23bb13af734de662e、ux1/3d-installed-removal-stale。
前turnはinstalled候補probe失敗保護/再導入受入と通常mergeまで進捗。
今回はscenario Dのpreview後GUI開始による再拒否を、installed署名0.28.53で検証。
製品code/版数変更なし。既存acceptance-sword/user:16/第14版/全版managed4.5.9を固定。
開始時Job/GUI不在、setup全終端・非activeを確認し、旧版exe hash/inodeとregistry bytesを記録。
Host診断venv/既存CONFIG/PYTHONPATH/DISPLAY/XAUTHORITY、一時mf-e2e loginのみfinally revoke。
外部診断 `/data1tb/mf-stale-removal-0.28.53.py` を既存repair受入からapply_patchで作成。
Settingsの実削除dialogでlive0/project2/履歴確認既定off・未確認disabledを確認。
同dialogを保持したまま正規APIでGUIを開始し、ready後に履歴checkboxをcheckして削除buttonをclick。
古いfingerprintの送信をbackendがblender_runtime_remove_changedで拒否した。
続いて稼働中の新previewでacknowledge_history=trueを正規APIへ送ってもin_use拒否。
新previewはworking copy1/session1/live合計2、確認付き削除も不可。
setup operation一覧が前後一致するため、受付で拒否され削除operationは作成されていない。

証跡 `/data1tb/mf-stale-removal-installed-0.28.53-20260910/observations.json`。
5.598秒preview/5.619秒GUI受付→11.593秒stale拒否→11.727秒fresh live拒否。
同4.5.9 GUIの実opaque RFB描画1275色、45.558秒passed/53.595秒own cleanup/
53.657秒一時login revoke、exit0/page errors0。元scene全投影・14版のsource/GLB28 hash不変。
exe SHAde8e8092c49e42cc6f1adde86aea0202ea5bad3338725887ecbcb7274dd0f926/inode46020227不変、
registry bytes不変。実削除/再導入は不要であり行わなかった。UIは拒否codeを表示し完全な翻訳文言の受入ではない。

同意checkboxを先にcheckしてからGUIを起動する逆順も、
`/data1tb/mf-stale-removal-after-ack-0.28.53.py`で別証跡へ実行。
両診断の起動は次の環境でscript名だけを変更する:

```bash
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml PYTHONPATH=/data1tb/ControlDeck/app/backend DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3 /data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-stale-removal-after-ack-0.28.53.py
```
証跡 `/data1tb/mf-stale-removal-after-ack-installed-0.28.53-20260910`。
7.576秒同意済みpreview→7.598秒GUI受付→13.661秒stale拒否→13.796秒fresh live拒否。
RFB描画1321色、49.653秒passed/57.681秒own cleanup/57.742秒revoke、exit0/page errors0。
こちらもsource/GLB28 hash・同第14版・exe hash/inode・registry bytes不変、operation一覧不変。

終了後の独立read-only照合では前PR baselineの3 scenes/17 revisions/current pin・72 files hashも保持。
session9f952c14cb1e44ddbfaae3ffb906095b/e5e210baff234081af28503f1c42bb5cはstopped、
両unit not-found/inactive/MainPID0、GUI0。MF1082083/Host667000 active/PID不変。
実画面の表示を確認したが手編集/保存は行っておらず、その品質や性能を推定しない。
文書のみ。PR #394の変更なし製品gate1357 tests/154.35秒/build/Node5を参照し再実行ではない。
両診断py_compileとdiff check成功。全D/3DS/GAはPARTIALで維持。
NOT TESTED: Job受付との同条件、削除実行中の並行受付、接続切断/再起動時の確認保持、
容量不足/中断等の残matrix。次はJob側の受付参照と既存実機証拠を照合する。


## 2026-09-10 installed exact candidate probe failure acceptance

PR #394 merge667906adeb24403551541ea625bb486ef2392f8fと最新handoffを再確認。
前turnは隔離sourceのexact pidfd故障注入/再試行受入と通常mergeまで進捗。
ux1/3d-installed-probe-failureはinstalled受入の記録sliceで、製品コード/版数変更なし。
read-only開始時: installed0.28.53、MF main1082083/core1082090、Host667000はactive。
Job/GUI/setupは全終端。managed4.5.9の参照は既存user:16受入2 scenesだけ。
coreのexe/UID/親PIDを照合し、実packaged preflight
`/tmp/_MEIZWNOAN/worker_packs/blender/preflight.py`のrealpathとSHA
3c029ca69fb6021e1c7a7f3387e0767346170cddab8140b2fd968dacc6271950をsourceと照合。
環境変数の読取はpackaged rootだけを抽出し、秘密値は出力しない。

診断`/data1tb/mf-probe-failure-0.28.53.py`を既存parallel受入からapply_patchで追加。
Host診断venv/既存CONTROL_DECK_CONFIG/PYTHONPATH/DISPLAY/XAUTHORITYで実行。
既存mf-e2e user16の一時loginだけを使いfinally revoke、password/global設定変更なし。
前提/削除preview/固定cache identityを検査し、inactive4.5.9だけ履歴確認付きで一時削除。
4.5.13 GUIを起動し、4.5.9 exact installの候補だけPR #394 helperでSIGTERMする。
再試行と専用GUI停止、例外時の同版再導入finallyを持つ。多数sceneが使う4.5.13は削除しない。
これは逆方向exact installであり、旧→新版update/active切替や自然発生故障と区別する。

実行コマンド（Host内部importはこの外部診断だけ、製品コードへ追加しない）:
```bash
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml PYTHONPATH=/data1tb/ControlDeck/app/backend DISPLAY=:0 XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3 /data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-probe-failure-0.28.53.py
```
証跡 `/data1tb/mf-probe-failure-installed-0.28.53-20260910/observations.json`、exit0。
17.110秒でinactive旧版除去・履歴保持、27.203秒で4.5.13実RFB描画1096色を確認。
候補PID1100108/親1082090、operation blenderop_a6e73ffdc7704b49bce00c7494ce914eの
exact staged executable/全argv/UIDを再照合したpidfd SIGTERMでprobe失敗。
57.264秒failed観測、68.289秒で同GUI ready/runtime4.5.13/runner PID1099805と
active実行file hash/inode・元scene/asset保持を確認。稼働GUIやcore自体にはsignalを送らない。
retry blenderop_44b3cdb6761b402795f152f076c2c835はready、実4.5.9 probe/GLTF import/export true、
6,510 members/展開1,168,332,002 B。同GUI/runnerはverifying/installing/readyを通して保持。
121.385秒passed、126.387秒自分のGUI停止、最後に一時login revoke。page errors0。
PNGはGUI描画の証拠であり、再導入中の手編集/保存やロボットの見た目品質の証拠ではない。

独立照合の初回は証跡のfield名をdocumentと誤りKeyErrorで中断（read-only、変更なし）。
実schemaのsceneに直し再照合: 3 scenes/17 revisions/current pin・関連72 files hash保持、
再導入4.5.9 executable SHAde8e8092c49e42cc6f1adde86aea0202ea5bad3338725887ecbcb7274dd0f926。
GUI0/staging0/候補PID不在。session3658ca124e6943e98db06d7a04da0dafの
unit not-found/inactive/MainPID0。active4.5.13/外部登録投影不変、MF1082083/Host667000 active/PID不変。
約1.17GBの旧版実行環境だけ一時削除し同版復元済みと利用者へ通知。制作物の削除なし。

本PRは文書のみ。変更のない製品gateはPR #394の1357 tests/154.35秒・viewer build/Node5を参照し、
このturnで全gateを再実行したとはしない。診断py_compile/diff check成功。
NOT TESTED: 新版update/active切替のinstalled同条件、自然故障、例外cleanup故障注入、
インストール中のGUI編集、削除同時受付/容量不足/中断の全matrix。全D/3DS/GA PARTIAL。
次は確認付き削除とJob/GUI同時受付の実機証拠を照合し、不足する競合条件を補完する。


## 2026-09-10 exact owned candidate-process failure and update retry

PR #393 mergeedf0a53f4357148de22f0bf9d847f0fa677e983fからux1/3d-owned-probe-failure。
前turnはinstalled別版導入中のGUI維持/記録mergeまで進捗。
既存source故障試験はpreflight scriptを差し替える方式だったため、未変更の実probeを
起動し、その候補プロセスだけを終了させるacceptance専用診断を追加した。
production core/公開schema/版数は変更しない。

scripts/blender_probe_fault.pyはexact operation ID/version/managed root/trusted scriptを要求。
親processの各threadのchildrenだけを調べ、UID/PPid/executable realpath/全argvを一致検査。
pidfdを開いた後にも同じidentityを再確認し、数値PIDではなくpidfdへSIGTERMを送る。
候補が見つからない・一致しない場合は無送信でtimeout、stop eventで追跡を終える。
proc読取/待機/シグナルはworker thread内、descriptorはfinally close。
9 testsでpath/argv/parent/欠落/不正ID/取消・再照合失敗時の無送信とdescriptor回収を確認。
これは通常のBlender操作機能でも、任意processを止めるpublic APIでもない。

scripts/3ds_update_probe_failure_e2e.pyへ--terminate-candidate-probeを追加。
既存隔離root /data1tb/mf-clean-packaged-0.28.32-QBvHfmだけを使い、
inactive/unreferencedな4.5.13の除去→4.5.9 GUI→4.5.13 update失敗→正常retryを実行する。
初期GUI/setup不在、exact root、削除previewの参照0を検査。新modeはtimeout/例外でも
自分のsessionだけを正規HTTP stopで回収するfinallyを持つ。停止要求の独立失敗注入は未実施。
既存のscript置換modeは既定のまま維持。pidfd helperはproductionからimportしない。

実行: PYTHONPATH=.:backend .venv/bin/python scripts/3ds_update_probe_failure_e2e.py
--terminate-candidate-probe --evidence-dir /data1tb/mf-owned-probe-failure-source-20260910。
2.414秒で実RFB3.8 handshake/1280x720、4.5.9 GUI ready。
23.639秒で候補PID1089251/親1089031をexact stage/argv/UID照合後にSIGTERM。
operation blenderop_10d02da5e27641a1adcde9d4f9627cf7はfailed/blender_runtime_install_failed、
messageはBlender preflight failed。24.064秒でA GUI ready/active4.5.9/元scene・assets metadata保持、
旧実行file hash不変と別実preflight4.5.9/GLTF import/export trueを確認。
retry blenderop_954d781f0ff04137a5f27a0978b13eb5は45.351秒ready、
archive378,033,952 B/6,512 members/展開1,167,187,839 B/実probe4.5.13。
activeは新版4.5.13へ切り替わるが、既存GUIは同sessionの4.5.9/connectedのまま。
明示GUI停止後に隔離rootの既定を4.5.9へ戻し、45.922秒passed/exit0。

独立確認: 既存source受入baselineの6 asset/provenance filesと旧executable計7 hash一致。
元revision_498980e910484e38a621d2d5844bed03保持、active GUI0、staging空、候補PID不在。
session blendersession_658e29ad6f734dce87d487601b85ef05、unit not-found/inactive/MainPID0。
同固定archiveからBを復元済み、隔離rootには両版が残り既定は4.5.9。
installed0.28.53/MF1082083/Host667000はactive/PID不変、利用者runtime/Job/制作物には変更なし。
NOT TESTED: installed Hostでの同故障、自然発生probe失敗、実RFB画素/入力・保存、全D/3DS/GA。
次はこのexact所有権診断をinstalled候補に適用できるか、親processとstage境界をread-only確認する。

再開時、前回全test handleは不在かつpytest processなし。結果を推定せず全gateを再実行。
最終identity照合後にもstopを確認する順序へ調整し、`./mf.sh test`は
1357 passed/既知warnings2/154.35秒/exit0。`npm run build:viewer`成功・生成差分なし、
`node --test tests/model-animation.test.mjs`5 passed、診断py_compile/diff check成功。

最終コードで同コマンドを別証跡`/data1tb/mf-owned-probe-failure-source-20260910-r2`へ再実行。
24.010秒で候補PID1097947/親1097665だけSIGTERM、operation
blenderop_0fc15d0598334bf890928f307bef0736はprobe失敗。旧GUI ready/connectedを保持。
retry blenderop_cd3a208e33c340439295787b33638c0eは45.746秒ready、
同session/runtime4.5.9を保持したままactive4.5.13。明示stop/既定4.5.9へ戻し46.297秒passed/exit0。
独立read-only検査で旧7 hash/元revision保持、GUI0/staging0/候補PID不在、
session d74c7b3a4fa34e35b59223ce657ef4b3のunit not-found/inactive/MainPID0。
MF1082083/Host667000はactive/PID不変。隔離した未参照B runtimeのみ一時除去して同版復元済みと通知。
例外cleanupの故障注入とinstalled同条件は引き続きNOT TESTED。

## 2026-09-10 installed side-by-side exact install while another GUI stays pinned

PR #392 merge43e8f45925947d19767ad3481c8e7c8ff3dcb799とhandoffを確認。
前turnは0.28.53署名公開/導入/修復保護受入まで進捗。ux1/3d-installed-parallel-runtimeで記録。
全体Dの別版導入中の稼働維持を、A=4.5.13 GUI / B=4.5.9 exact installとして確認する。
これはA=旧版からB=新版へのupdate/active切替を実測する試験とは区別する。
4.5.13は多数sceneが参照するactive版なので削除しない。Bの4.5.9だけがuser:16の
acceptance-swordとRecoveryの2 scenesを参照し、固定archive377,929,956 B/
SHAdcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3dがcacheにあることを確認。

/data1tb/mf-parallel-runtime-0.28.53.pyを前のhistory診断からapply_patchで作成。
最初は開始前Jobs0検査でexit1。ログイン・削除・GUI開始前で環境変更なし。
job_2612ce682b8c42d28fef53f837918b8fのrunning→succeededと、続くimage.editを読み取り専用で追跡。
実worker PID1085433の存在も確認し、他Jobを止めずに待機。全Jobs0になってから
別証跡mf-parallel-runtime-installed-0.28.53-20260910-r2で再実行した。
Host診断venv、既存CONFIG/PYTHONPATH/DISPLAY=:0/XAUTHORITYを使用。
開始時と削除直前にidle検査、旧版参照scene/ownerの固定検査、失敗時の同版再導入finally付き。
一時mf-e2e loginだけを作り最後にrevoke、password/global設定変更なし。

実Host iframeで英語Remove button/履歴checkboxの既定off・未確認disabledをassertし、
通常pointer確認でBを削除。18.405秒でB directory消滅、3 scenesの全投影/hash保持。
削除後にAの受入用ロボットscene_509b6ee0b688492997b86b535d70ec9aを正規APIで起動。
実RFB connected/描画1096色、4.5.13 pinを確認。30.780秒でA GUI ready。
Bのinstall_exactを正規workspace APIへ要求し、verifying/ready両方で
同session ready/runtime4.5.13と同runner MainPID1087038を確認。
operation blenderop_a62ebac699cd45859c4efb8caa7f6b99、実archive6,510 members/
展開1,168,332,002 B、実preflight4.5.9/GLTF import/export true、64.845秒でready観測。
80.889秒でpassed、85.896秒で専用GUI停止、finally login revoke、exit0/page errors0。
削除したBの実行環境は同版へ復元済み。制作物は削除せず、active4.5.13も切り替えていない。

独立再照合: 3 scenes/17 revisions/72関連filesのhash・旧revision投影不変、GUI0。
A executable SHAe3ce4e960a2fd3beb1f9d2299e38b3804475ccd395193013aec239a4b75bfbfe、
inode46028345不変。外部登録の投影も前後一致（外部実体の健全性を新たに主張しない）。
session blendersession_040096fdea9a492aaf1acea6a290a768、unit not-found/inactive/MainPID0。
Host667000/MF1082083不変。PNGはGUI描画の証拠で、導入中の手編集/保存は未実施。
英語削除buttonの実操作を確認したが、全画面の完全英語化や削除dialog全体のスクリーンショット
受入は主張しない。画像では既存の日本語ラベルも残っている。
約1.17GBのB実行環境のみ一時削除・同版再導入した範囲を利用者へ通知済み。

文書のみ。製品gateは0.28.53準備の全1348 tests/145.63秒とviewer buildを参照、
本turnで再実行したとはしない。NOT TESTED: 新版update/active切替、B probe失敗、
削除と受付の実競合、容量不足/改ざん/中断全matrix。全D/3DS/GAはPARTIAL。
次は並行導入の失敗条件を、現在版を壊さない隔離fixtureで補完しinstalledとの差を記録する。

## 2026-09-10 v0.28.53 signed release and standard installed update

準備PR #391 source89ffbf9099a1598e9569cb07f80d41431cf6a772、通常merge
330e0b0b6543e4ef2507b46775dd1f86e0849de5をexact checkout/tag v0.28.53へ固定。
checkout /data1tb/ControlDeckMediaForge-release-0.28.53。
同checkoutでpython3 scripts/build_release_bundle.py --version 0.28.53
--output-dir /data1tb/mf-0.28.53-build-20260910
--pyinstaller /data1tb/ControlDeckMediaForge-3ds4/runtimes/bundle-build/.venv/bin/pyinstaller。
既存PyInstaller6.22.0/Python3.12.3使用、exit0。
artifact31,573,646 B/SHAe8a22e13602634510f549b19f890074ae28d2bf68bf73e64cedfccefde1dbd80。
/data1tb/mf-0.28.53-audit.pyでCArchive202 entries、禁止名なし、certifi公開PEM一致、
worker/schema/frontend各bytesをexact source照合。PYZの修復guard/参照再検査と
_installのshield/to_thread、既存RFB observer/failure reader/fresh monitorも確認。
packaged doctor:ok/version0.28.53/packaged=true。
展開先 /data1tb/mf-0.28.53-package-suto6775、build/verification.jsonに記録。

既存publisher鍵で署名/自己検証し、通常公開:
https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.53
公開4filesを/data1tb/mf-0.28.53-public-20260910へ再取得。
Host診断venv/既存CONTROL_DECK_CONFIG/PYTHONPATHで
/data1tb/mf-0.28.53-install.pyを実行。local/public bytes一致と実Host trusted signature検証、
Jobs/GUI/setup全終端→SQLite backup→再idle/全table fingerprint/registry照合後、標準install。
10.240秒でinstalled0.28.53/実HTTP healthy、DB全table/registry bytes不変。
backup /data1tb/mf-0.28.53-update-vvnnqdet、observations.jsonに結果を保持。
Host667000不変、MF1082083。標準保持処理で0.28.51 executable bundleのみ整理し、
0.28.52/.53を保持。旧bundleは公開releaseから再取得可能。制作物/runtime削除なし。
利用者へ整理範囲を通知済み。準備全1348 tests/145.63秒、Node5/build成功を参照。
本記録sliceは文書のみ。全3DS/GAの完了とはしない。

installed修復保護: Host診断venv/既存CONFIG/PYTHONPATH/DISPLAY/XAUTHORITYで
/data1tb/mf-repair-protection-0.28.53.pyを実行。user:16の専用scene/base第14版を固定検査し、
正規Host opaque frame/Origin:null/overlayなしで4.5.9 GUIを起動、実RFB接続/描画1282色を確認。
同runtimeのrepairを正規workspace APIへ要求、73.721秒でfailed/blender_runtime_in_use。
operation blenderop_f280a6da698142d7807822bfef5f14aa。独立DB/実ファイル再照合でも旧28assets hash一致、GUI0。
同GUI readyと描画を保持し、scene全投影/旧asset hash/registry bytes不変、
実行ファイルSHAde8e8092c49e42cc6f1adde86aea0202ea5bad3338725887ecbcb7274dd0f926、
inode46020214不変（稼働treeの差替えなし）。86.912秒で専用session停止、
86.973秒で一時login revoke、exit0/page errors0。password変更なし。
証跡 /data1tb/mf-repair-protection-installed-0.28.53-20260910/observations.json。
session blendersession_c77efb16b51d42849a5d324fac238535、終端unit not-found/inactive/MainPID0。
MF1082083/Host667000はactive/PID不変。PNGは実GUI描画の証拠であり編集保存の証拠ではない。
setup要求はAPI経由で、Settingsのエラー文言操作や修復後の再編集を実測したとはしない。
この稼働中修復拒否のsource-only制限を補完した。停止後の正常修復は前source実機を参照し、
installedの同条件・B並行導入/probe失敗・全D/3DS/GAは未完了として維持する。
次は残るDの別版並行導入/失敗の安全なfixtureと実行境界を確認して進める。

## 2026-09-10 v0.28.53 release preparation

前goal turnは修復時の稼働版保護を実装・実Blender受入しPR #390 mergeまで進捗。
origin/main 9d0f67ad06838a379641d5fd3899a647596255dfとhandoff/配布規約を再確認し、
ux1/3d-release-0-28-53でaddon/core版を0.28.53へ揃えた。
release noteは修復の稼働参照再検査・受付排他・off-loop公開・停止時の追跡を説明し、
source実機と未実施の署名/installed受入を分離。API/DB/Blender版の変更はない。
開始時installed0.28.52、実DB Jobs0/GUI0。環境更新は公開consumer検証・backup・再idle確認後に行う。
本準備PR時点でartifact生成・署名・公開・installed更新はNOT TESTED。
全`./mf.sh test`: 1348 passed/既知warnings2/145.63秒/exit0。
viewer build成功/生成差分なし、Node animation5 tests/diff check成功。

## 2026-09-10 repair publication preserves live Blender runtimes

PR #389 merge3471b5950ab2dbd73ab65bc623f2237ec03eb684から
ux1/3d-repair-live-protection。前goal turnは実再編集受入/mergeまで進捗。
installedでは別の画像Jobが実行中だったためruntime変更を行わず、コードを調査。
修復はcandidate probe後に既存directoryをrenameするが、削除と異なり稼働参照の
再検査/受付guardがないことを確認。候補probe中にin-processまたはdurable recipe Jobの
参照を増やす回帰テスト2件で、修正前は誤ってreadyになることを再現した。
最初の試行のdurable fixture import typoは修正後に再実行し、両件とも同じ欠落でREDを確認。

修復の公開をworker threadへ移し、既存removal_guard内でcancelとin-process/durable
Job・GUI・working copy参照を再検査。liveがあればblender_runtime_in_useで候補を拒否。
guardを保持してrename/registry/失敗rollback/cleanup/ready永続化を行う。
開始済み公開threadはshieldしshutdown取消でも終端まで待つ。activeや履歴pinだけでは
停止済み版の修復を拒否しない。外部版の所有権や公開schema/G8契約は変更しない。
新規のblocking DB/filesystem/lock待機をasync実行へ追加しない。
既存の停止済み破損版修復/registry失敗rollbackに加え、late参照2件、
公開off-loop/停止待機1件がPASS。関連manager/history-removal/runtime-reference54 tests成功。

実機は利用者installedとは別の既存受入root
/data1tb/mf-clean-packaged-0.28.32-QBvHfmだけを使用。
PYTHONPATH=.:backend .venv/bin/python scripts/3ds_repair_live_e2e.py
--evidence-dir /data1tb/mf-repair-live-source-20260910 を実行、25.053秒/exit0。
開始前に専用DBのJobs/GUI/setup全終端を確認。scene_2642c93f480d427d920267ac790405e2の
実software Blender4.5.9を起動し、実HTTPで同版repairを要求。
377,929,956 Bの固定archive検証/展開/実candidate probe後、24.720秒で
blenderop_a88add260d3a420d8bf14b288bd8c84d failed/blender_runtime_in_use。
同GUIはready、scene全投影と既存8files（registry/Blender executable/制作物/provenance）SHA不変。
HTTP healthは応答成功だがsetup_required（隔離sourceの環境stamp不足）で、healthyとは記録しない。
session blendersession_758af0dbfdf341c5824afeb4655083d5は25.010秒stopped、
unit not-found/inactive/MainPID0。Host667000/MF1054020はactive/PID不変。
候補stagingのみ既存失敗cleanupで回収、元runtime/制作物/外部Blenderは削除しない。

停止後の正常修復も同診断へ追加して別証跡mf-repair-live-source-20260910-r2で再実行。
23.831秒で稼働中拒否、24.120秒で専用session停止、46.009秒で同版repair ready/全体passed、exit0。
成功operation blenderop_be139ffd3fb64d52a6f954ef29401a2c、archive6,510 members/
展開1,168,332,002 B、実preflightは4.5.9/GLTF import/export true。
runtime directory inode51918012→51924524で実差替え、既存8files SHA/scene投影不変。
専用受入rootの旧実行環境は通常修復cleanupで整理した。同固定archiveから再構築可能、
制作物/installed runtimeの削除なし。全`./mf.sh test`: 1348 passed/既知warnings2/143.93秒/exit0。
viewer build成功/生成差分なし、診断py_compile/diff check成功。

NOT TESTED: 本修正の署名配布/installed受入、実RFB入力、A稼働中B本導入/probe失敗、
repair中process crashの全rollback matrix。修復拒否をB導入の証拠へ読み替えない。
全D/3DS/GAはPARTIAL。次はこの稼働版保護の署名release準備・導入とinstalled確認を行う。

## 2026-09-10 installed same-scene RFB edit after exact Blender reinstall

PR #388 merge fc171f864d8638318a84e96cb10ae9097dd12708から
ux1/3d-reinstalled-browser-edit。直前の応答は説明のみで新しい受入なしと分類し、
現main/PR #213 MERGED、handoff/設計、installed0.28.52を再確認。
開始時Jobs0/GUI0、MF1054020/Host667000 active。元checkoutの別branchと.venvは変更しない。

前回旧版削除/同版再導入を行った同じuser:16のacceptance-swordを対象に、
ephemeral診断 /data1tb/mf-reinstalled-edit-0.28.52.pyをapply_patchで作成。
既存background-return診断のnative_browser/asset_hashes/mesh_countとinstalled browser helperを再利用。
scene ID、owner、base revision、13版全てのruntime pin、全体idleを開始前に固定検査。
Host診断venvでCONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml、
PYTHONPATH=/data1tb/ControlDeck/app/backend、DISPLAY=:0、
XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3を指定して実行。
一時loginのみ作成/finally revoke、既存passwordや利用者global設定は変更しない。

実Host opaque frame/Origin:null/overlayなし。scene選択と開始は製品helper/正規API、
再導入済みruntime blender-4.5.9-linux-x64/version4.5.9をready投影で確認。
実RFB connectedと描画1089色を25.899秒で確認し、canvasへのclick/A/Shift+D/Escape後、
通常Save new revision and finishをclick。66.978秒でpassed、67.040秒でlogin revoke、exit0。
元第13版revision_6350c1fd694347b886b3b2c8de0f312bから
第14版revision_1479631eb20e4909a4ae975e71fa2cbfへ確定。
独立Blender検証mesh4→8/triangles236→472、実GLB JSONのmesh参照nodeも4→8。
新GLB asset_c889d0b198f84dea82ae3db6c7388eb1、1,761,820 B、
SHAf132b3e074dfa4cf0282218839784ac683101f9fb90366fc9674300a612348e2。
画面PNGでは重複形状を目視確認できていないため、描画と入力/保存後の構造検査を分けて記録する。
証跡 /data1tb/mf-reinstalled-edit-installed-0.28.52-20260910/observations.json、page errors0。

独立read-only DB/bytes照合で、前回baselineの2 scenes/14旧revisions全投影と
関連60ファイルのSHA一致。別Recovery sceneは不変、編集対象のcurrent更新だけが意図した変更。
session blendersession_c78a1982e18f483a96bd11f1a7e28d05はstopped、active GUI0、
専用unit not-found/inactive/MainPID0。旧版への復元や制作物削除はせず新第14版も保持する。
Host/MFのrestart、runtime切替/再導入、外部Blenderへの変更はこのturnでは行わない。

scenario Dの同版再導入後「同一sceneで再編集」の不足を補完した。
NOT TESTED: 英語本削除、削除と新規受付の実競合、A稼働中B導入/probe失敗、
改ざん/容量不足/中断のinstalled全matrix。全D/3DS/GAはPARTIALのまま。
次はA稼働中B操作の安全な対象・故障注入境界を確認してDの残条件を進める。
GUI終端後に全`./mf.sh test`: 1345 passed/既知warnings2/142.07秒。
`npm run build:viewer`成功/生成bundle差分なし、Node animation5 tests成功、diff check成功。
文書のみのPRであり、新しい製品releaseは不要。installed0.28.52で上記受入を行った。

## 2026-09-10 installed history-preserving 4.5.9 removal and exact reinstall

前goal turnは0.28.52公開・導入・個別animation受入/PR #387 mergeまで進捗。
origin/main c055acd085229f3aedbba5c96d078489a599b07bと引き継ぎを確認。
ux1/3d-installed-history-reinstallで実測記録を追加。製品code/版数変更なし。

read-only前提調査: managed4.5.9 inactive、managed4.5.13 active、legacy4.5.9は別登録。
旧版参照はuser:16のacceptance-sword13版と同Recovery1版のみ（2 scenes/14 revisions）。
最初は別生成Jobがrunningだったため変更せず、後に自然終了/Jobs0を確認した。
既存3ds_settings_protection_installed_e2e.pyをHost診断venv/既存CONFIG/PYTHONPATH/DISPLAYで実行:
--expected-version 0.28.52 --require-readable-layout --require-touch-targets
--require-history-confirmation --locale ja --initial-width 320
--evidence-dir /data1tb/mf-settings-preflight-installed-0.28.52-20260910。
exit0/Origin:null/overlayなし、確認既定off・再openでoff、未確認disabled、確認時enabled、
active4.5.13は確認でも削除不可。runtime status/journal不変。320px/44px controls/横overflowなし。
旧版previewはlive0/project2、exact_reinstall4.5.9、reclaimable1,168,898,465 B。

cacheのblender-4.5.9-linux-x64.tar.xzは377,929,956 B、
SHAdcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3dで固定catalog一致。
/data1tb/mf-history-installed-0.28.52.pyをapply_patchで用意し同Host診断環境で実行。
初回はpreviewの非同期応答を待たずNone参照でexit1。削除要求前であり環境変更なし。
dialog/preview待ちを加え、別証跡 /data1tb/mf-history-installed-0.28.52-20260910-r2で再実行。
user:16と旧版参照scene集合を固定検査。個別一時loginだけ作成しfinallyでrevoke、password変更なし。
旧版のrealpath/所有権/非active/live0/project2/cache identityを確認してから、
日本語320px Settingsの履歴確認checkboxと削除buttonを実pointer操作。

実測: 15.431秒でmanaged旧版directory消滅、2 scene全投影/既存ファイルhash保持。
不在区間に13版の元sceneからバックアップ21,464,415 Bを実download。
manifestのdocument/revisions一致、全28 entriesのsize/SHA照合。
GLBビューワーも表示し、保存PNGを画像検査（236 triangles/4 materials/animation0）。
35.257秒で不在区間のbackup/GLB確認を終了し、Settingsの「この版を導入」を実click。
59.953秒で同sceneを旧runtime ID/4.5.9のGUI readyへ再開、続けて停止。
再開/停止は正規blender.sessions API。RFB手入力/追加編集まで確認したとはしない。
全診断59.982秒/exit0/passed=true、page errors0。エラー時は旧版が不在なら
同exact installで復元するfinallyを持つが、今回その復旧分岐は未使用。

独立再監査: 14版/2 sceneに関わる60ファイルのhash一致。
session blendersession_9caa087fd0c94883b6c7487a8351f63dはstopped、
unit not-found/inactive/MainPID0、active GUI0。
registryのruntime identity/ownership/archive hash集合とactive4.5.13は更新前と一致。
再登録により配列順だけ変わったのでregistry bytes不変とは書かない。legacy登録は不変。
MF1054020/Host667000はactive/PID不変。service restart、他Job取消、外部Blender/制作物削除なし。
約1.17GBの旧実行環境を一時削除・同版再導入したことを利用者へ通知済み。

本sliceは実機受入と文書のみ。製品gateはrelease準備1345 tests/138.50秒を参照し、
本turnで再実行したとはしない。scenario Dの「停止済み履歴参照版を削除→同版再導入」
と不在中のGLB/backupをinstalledで補完した。全D/3DS/GAはPARTIALを維持する。
NOT TESTED: 再導入後のRFB編集、英語での本削除、同時受付との削除競合、
稼働A中のB実導入/probe失敗、改ざん/容量不足/中断のinstalled全matrix。
次は同じ旧版sceneの再導入後RFB編集を確認し、残るDの各条件を証跡へ対応付ける。

## 2026-09-10 v0.28.52 signed / installed / opaque animation acceptance

PR #386 MERGEDのb5e5b77a418d67d64b87f7d530839225c3df9b00をexact checkout/tagへ固定。
checkout /data1tb/ControlDeckMediaForge-release-0.28.52、tag v0.28.52。
既存scripts/build_release_bundle.pyとbundle-build venv/PyInstaller6.22.0/Python3.12.3でbuild。
/data1tb/mf-0.28.52-build-20260910、artifact31,534,370 B、
SHAff5d5fe47a9131efd4eacbc1b9d75b103269698143fa97b8987c747c9568b14f。
/data1tb/mf-0.28.52-audit.pyでCArchive202 entries、禁止名なし、certifi PEM一致、
worker2/schema3/frontend6のexact bytes、既存failure reader/RFB observer/monitor修正を照合。
packaged doctor:ok/version0.28.52/packaged=true。
展開先 /data1tb/mf-0.28.52-package-dqxjge1n、build/verification.jsonに記録。

既存発行者鍵で署名・自己検証し正規公開:
https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.52
公開4ファイルを /data1tb/mf-0.28.52-public-20260910へ再取得。
Host診断venv/既存CONTROL_DECK_CONFIG/PYTHONPATHで
/data1tb/mf-0.28.52-install.pyを実行。public bytes一致/実Host trusted publisher検証、
idle→SQLite backup→再確認→標準install。10.177秒でinstalled0.28.52/実HTTP healthy。
DB全table fingerprint/Blender登録bytes不変、Host667000不変、MF1054020。
backup /data1tb/mf-0.28.52-update-oww7wqjq/observations.json。
標準保持規則で0.28.50実行bundleのみ整理、0.28.51/.52保持。制作物/runtime削除なし。
旧bundleは公開releaseから再取得可能。利用者へ通知済み。

installed opaque browser:
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml
PYTHONPATH=/data1tb/ControlDeck/app/backend DISPLAY=:0
XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3
/data1tb/ControlDeck/app/.venv/bin/python /data1tb/mf-0.28.52-animation-installed.py
専用mf-e2e sessionを作成しfinallyで同sessionだけrevoke。overlayなし/Origin:null。
既存scene_509b6ee0b688492997b86b535d70ec9aのcurrent GLBをLibrary/3D/cardから開いた。
asset_4d359d6ce7da4684a0156750e7d146e5、SHA
b36b26954162e40ced1a0dc99de958a4b76218f635324055244d35ba615ea61d。
/data1tb/mf-animation-installed-0.28.52-20260910/observations.json、exit0/passed=true。
arm_swing1秒とidle2秒を単独選択/0.5倍速再生→pause。0.5167/0.9084秒で
操作欄を除いたモデル領域の変化36,408/6,247 pixels、pause後の時刻不変を確認。
先頭戻し、英語label、parent320pxで選択/2倍速/overflowなし、閉じる/action回収、
元scene投影不変/page errors0。元GLB hashも別read-onlyで照合。
本変更のsource-only制限をこの範囲で解消する。見た目の芸術的品質や歩行の証拠にはしない。

準備全1345 tests/138.50秒、追加Node5 tests/viewer build成功を参照。
本記録sliceは文書のみ。全3DS/GAはPARTIAL、engine/有機weight/IK等はNOT TESTED。
次は完了監査に残るscenario Dの設定ライフサイクルをinstalledで補完するため、
対象runtimeの所有権・同版再導入可能性・専用scene pinと既存証跡を再確認する。

## 2026-09-10 v0.28.52 release preparation

前goal turnは個別animation previewのPR #385通常mergeまで進捗。
main c919ca631b6c00364b96679938fd49b608828e55とhandoffを照合し、
ux1/3d-release-0-28-52でaddon/core版を0.28.52へ揃えた。
release noteはsourceで確認した個別clip/速度/先頭戻し・日英320pxと、
warm約3〜6秒の目標未達、installed受入未実施を分離して記録する。
DB/public schema/capability/Blender runtime変更なし。

開始時installed0.28.51/MF1024680/Host667000 active、実DB Jobs0/GUI0。
npm run build:viewer / node --test tests/model-animation.test.mjs（5 passed）/diff check成功。
全 ./mf.sh test:1345 passed/既知warning2/138.50秒、exit0。
次は本PRの通常merge後、exact checkout/tagからbundleを生成して署名・公開・標準導入する。
監査/導入診断を /data1tb/mf-0.28.52-{audit,install}.py にapply_patchで準備。
監査ではworker/schemaに加えfrontend6ファイルのexact bytesも確認する。
導入はexact tag/署名/public bytes→idle→SQLite backup→再確認→標準install。
現段階では未実行なので署名/導入成功とはしない。全3DS/GAはPARTIAL。

## 2026-09-10 individual animation preview — source acceptance

前turnはPR #384通常mergeまで進捗。origin/main dab4119f537e91b9a6422023a7ed498620dec405を確認し、
ux1/3d-animation-previewで作業。既存.venv symlinkは未追跡のまま保護。
全clip同時再生を廃止し、indexによる単一clip選択・先頭戻し・0.25/0.5/1/2倍速を実装。
同名clipを区別し、選択変更で先頭へ戻して再生/停止状態を保持。全操作は表示専用。
モデル切替/終了でactionを回収、再表示は先頭clip/1倍速/停止。日英locale更新は選択を保持。
frontend/model-animation.mjsを固定Three.jsの既存bundleへ含め、source/bundle hashを更新。
API/schema/Blender/runtime/Hostに変更なし。

node --test tests/model-animation.test.mjs: 実Three mixerの5 tests成功
（単一clipの実座標、同名識別、pause/restart/speed、不正値、空/終了後のaction回収）。
node --check frontend/app.js / npm run build:viewer / focused frontend+viewer tests成功。
最終全 ./mf.sh test:1345 passed/既知warning2/141.91秒、exit0。
実GUI診断を終了してから直列実行。viewer再buildも同SHA/diff check成功。
PR作成前、ブロッカーなし。source受入後の通常PR/署名配布を続ける。
source実機:
PYTHONPATH=.:backend .venv/bin/python scripts/3ds_animation_preview_e2e.py --serve
--data-dir /data1tb/mf-animation-preview-source-data-20260910
--glb /data1tb/ControlDeck/data/feature-data/media-forge/data/assets/asset_4d359d6ce7da4684a0156750e7d146e5.glb
（loopback8937、専用dataへimmutable import。production入力は読取のみ）。
browserはHost診断Pythonに既存MF site-packagesをPYTHONPATHで参照してPillowを使用。
DISPLAY=:0/XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3、
同script --data-dir 同上 --evidence-dir /data1tb/mf-animation-preview-source-20260910-r6。
新規pip導入/Host設定変更なし。

最終run exit0/passed=true、実GLTFLoader/WebGL、136 triangles/6 meshes/2 clips。
arm_swing1秒とidle2秒を別再生。操作欄を除いた実画像差分を0.5442秒/0.94125秒で確認。
pause後時刻不変、動作中選択、先頭戻し、速度、英語切替、320px操作44px高、
閉じる→action停止→再表示の初期状態をassert。元GLBのSHA
b36b26954162e40ced1a0dc99de958a4b76218f635324055244d35ba615ea61d不変。
初回はidleの冒頭0.5秒静止区間を比較して失敗。診断の観測点を修正した。
中間runはhiddenの別thumbを選択/重複selector/close event直前の判定で失敗し、
Library限定selectorと正式closeイベント完了待ちへ修正。失敗証跡は別dirに保持。
r5成功後、操作欄の文言変化をgeometry証拠に含めないcropを加えr6で再成功。

既存scripts/3ds3_viewer_e2e.mjsも同sourceで実行:
cold641.728ms、hiddenでframe11→11、visibleで18、WebGL context復旧、
日英/320px overflowなし/44px controlsまでは確認。
後段のthumbnail img naturalWidth待ち(line226)でexit1。thumbnails実file2件は存在。
この失敗runの全回帰成功・繰返し5回のheap回収は主張しない。
その後origin/mainのlibraryCardもmodel_3dは常にplaceholderを返すことを確認。
古い診断のcaptured-thumbnail期待との不一致であり、本sliceの表示変更ではなかった。
診断に明示--thumbnail-mode placeholderを追加し（既定capturedは維持）、
現行のplaceholder表示/画像非表示をassertした上で後段も再実行。
r6/viewer-regression.png.json: exit0/errors0、cold213.718ms、hidden frame9→9/復帰16、
context復旧、320px、5回closeの全context解放、JS heap増444760 B、module取得1回。
warm6046.563/3032.865/3030.910/3027.776ms。warm1秒目標は未達であり性能達成としない。
このsource実機をinstalled opaque Hostの証拠へ読み替えない。
Host667000/MF1024680はactive/PID不変、installed0.28.51にこのUI変更はまだ入っていない。
NOT TESTED: 本変更の署名配布/導入、engine再生、有機weight/IK、全3DS/GA。
次は本変更の署名配布・installed opaque Hostでの個別clip受入。

## 2026-09-10 installed default idle acceptance complete

署名installed0.28.51/Blender4.5.13の既定idle1800秒診断がexit0で終端。
証跡 `/data1tb/mf-default-idle-installed-20260910-r2/observations.json`、passed=true。
実行コマンドは直下の導入記録と同じ。CLI1024735/handle24245の終了を再確認した。
session blendersession_23e6efc5118049f182b38608f72b50e2は
interrupted/blender_session_idle_timeout。最終入力17:45:12.191318 UTCを保持し、
終端更新18:15:18.185248 UTC。入力後からの診断観測1793.120秒で、
terminal_sec1785.096は後段wait開始からの時間（serverの1800秒設定とは別）。
画面要求・実再接続で入力時計を延長せず、切断猶予による誤終了もなかった。

実RFB複製後の8→16 meshesを通常recovery.forkで別scene初版へ回収。
scene_7053e308961c5808999f8f5a8d19f6b3 / revision_25e999602ba646e09fca62e6d45420ca。
候補/source547950 B、SHA80dc08dae81d98703dc08ecaa8090e86418c8bfcddc0266222a7d0540cfdbc2b。
独立read-only照合で実GLB22216 B/16 meshes/16 nodes、
SHA553e5d0c54378009bf1e7b7035f9902febf678ca4074bf1442d98dd869e1a680を確認。
診断は元scene投影不変をassertし、再監査でも旧16ファイルのSHA一致。
所有PID1025055/1025059/1025120消滅、診断のcgroup/root/socket回収assert成功。
実DBのactive GUI0、MF1024680/Host667000はactiveでPID不変。

本sliceは実測記録のみ。全3DS/GAはPARTIALのまま。
ux1/3d-default-idle-verified、base origin/main4ecc52f（PR #383 MERGED）。
全 ./mf.sh test:1345 passed/既知warning2/144.94秒/exit0、viewer build/diff check成功。
次はfrontend/model-viewer-source.jsの全clip同時再生を個別clip選択へ改めるslice。
現在は未実装。新branch作成前に本記録PRを通常mergeし、origin/mainを再確認する。
NOT TESTED: 電源断・保存途中crash・GPU lease/競合・全設定導入失敗matrix・
ゲーム用の有機ウェイト/IK/歩行/個別clipプレビュー等。idle受入から推定しない。

## 2026-09-10 v0.28.51 signed / installed / idle retry running

PR #382 MERGEDのad61a431ca2424d285fa81c38ced25aa360ce740をexact checkout/tagへ固定。
checkout /data1tb/ControlDeckMediaForge-release-0.28.51。
既存bundle-build venv/PyInstaller6.22.0/Python3.12.3とscripts/build_release_bundle.pyを使用。
/data1tb/mf-0.28.51-build-20260910のartifact31,532,718 B、
SHA58e0b0cca8164463404cd8009fda51e45a2ecd22d24a7c3fa3459dea95fa2cf9。
/data1tb/mf-0.28.51-audit.pyでCArchive201 entries、禁止名なし、certifi PEM一致、
worker2/schema3 exact bytes、PYZ内のRFB observerと修正monitorのrunner_activeを確認。
専用data/cacheのpackaged doctor:ok/version0.28.51/packaged=true。
展開先 /data1tb/mf-0.28.51-package-e6lq0pyo、build/verification.jsonへ保存。

既存発行者鍵で署名/自己検証して正規公開:
https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.51
公開4ファイルを /data1tb/mf-0.28.51-public-20260910へ再取得、全bytes一致。
/data1tb/mf-0.28.51-install.pyをHost診断venv/既存CONFIG/PYTHONPATHで実行。
実Host trusted publisher検証、Jobs0/GUI0、SQLite backup、再確認後に標準install。
9.982秒でinstalled0.28.51/HTTP healthy、DB全テーブルfingerprintとruntime登録bytes不変。
backup /data1tb/mf-0.28.51-update-zkg98th1/observations.json。
Host PID667000不変、MF PID1024680。標準保持規則で0.28.49実行bundleのみ整理し、
0.28.50/.51を保持。制作物/runtime削除なし、旧bundleは公開releaseから再取得可能。

修正版で同じ既定1800秒診断を新sessionとして開始:
Host診断Python、既存CONFIG/PYTHONPATH/DISPLAY=:0/
XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3、
scripts/3ds_save_conflict_cleanup_installed_e2e.py
--scene-id scene_3f3b5f1e97e94b268722ea45cc811c50 --expected-version 0.28.51
--failure-kind connected-idle --evidence-dir /data1tb/mf-default-idle-installed-20260910-r2。
実CLI PID1024735/exec handle24245、
session blendersession_23e6efc5118049f182b38608f72b50e2、4.5.13 readyを実DBで確認。
初回0.28.50の失敗runは保持し上書きしない。新runは実行中、終端・回収は未確定。
次turnは同handle/PID/証跡を再確認し、観測待ちを理由に再起動/再実行しない。
準備全1345 tests/150.19秒、viewer build成功。記録sliceは文書のみ/diff check。
全3DS/GAはPARTIAL、既定30分/本番再接続の修正完走/復旧mesh確認はまだNOT TESTED。

## 2026-09-10 v0.28.51 release preparation

前goal turnは実機idle失敗の競合修正/PR #381通常mergeまで進捗。
main ba0e988f669f8215c57ac860d19cca6990abbb88とhandoffを再確認し、
ux1/3d-release-0-28-51でaddon/coreを0.28.51へ揃えた。
release noteには0.28.50での約15分誤終了とred/green再現、修正後source回帰、
既定30分未達を明記。DB/schema/capability/runtime変更なし。
開始時installed0.28.50/MF1001944/Host667000、active Jobs0/GUI0を実測。
viewer build/diff check成功。全 ./mf.sh test:1345 passed/既知warning2/150.19秒、exit0。
署名公開・導入・既定30分再試験は準備完了後。全3DS/GAはPARTIALを維持する。

## 2026-09-10 default idle run failed / stale monitor snapshot repair

前turnまでの待機は同じ実CLI/PIDを確認したverified wait。
installed0.28.50の30分試験はexec3638/CLI1004438がexit1で終端した。
913.496秒sampleまでready/connected/入力時刻不変だったが、最終状態は
interrupted/blender_session_disconnected_timeoutであり、idle成功ではない。
last_activity_at17:14:32.231864 UTC、connected_at17:22:02.473389 UTC、
disconnected_at=null、updated_at17:30:07.071092 UTCという不整合を実DBで確認。
Host667000/MF1001944は不変。所有PID1004742/1004746/1004802とsession root消滅。
候補working_c80e8b407b684f71bb064f053d9003db/scene.blendは547950 B、
SHAd4ef821de34415a9aed27a890a0fa28497f5b310a998cbe26480b5650cf85951。
/data1tb/mf-default-idle-installed-20260910/failure-audit.jsonに別途記録。
元observations.jsonのpassed欠落を成功へ読み替えない。復旧形状の確認は未到達。
今後の診断失敗はpassed=false/error_type/終端の安全な時刻・原因fieldを記録する。

monitorはDB再読取後にcontroller.activeをawaitし、その間のgateway release後も
古いsession.updated_atで切断猶予を判定し、古い接続fieldごとSTOPPINGを書いていた。
runner probe内でreleaseし時計を600秒進める決定的fixtureでready→interruptedの誤終了を再現。
追加testは修正前1 failed/0.64秒。probe awaitを既存DB再読取の前へ移し、
両probe後の最新sessionで状態/接続期限を判断する。同期I/Oやpolicyを追加・変更しない。
修正後focused34 tests/3.60秒/既知warning1成功。
これは実機の記録に一致する競合再現であり、30分再試験の代わりではない。
PR #381へ失敗証跡と修正を含め、installed本修正/既定30分受入は未完了のまま保持する。
source実GUI回帰:
PYTHONPATH=.:backend .venv/bin/python scripts/3ds_autosave_source_e2e.py --serve
--data-dir /data1tb/mf-probe-clock-source-data-20260910、既存read-only4.5.9/runtime-Webと
asset_263d5f26d18b4d05b65357c4aa8d26e7.blendを使用。
Host診断Python/既存DISPLAY/XAUTHORITYで同script --verify-input-activity
--evidence-dir /data1tb/mf-probe-clock-source-20260910を実行。
session f278e4cb3fba4c398b1ac220b51b3904、44.265秒で画面要求/入力/再接続の時刻判定成功。
136.609秒で既定autosave候補445460 B、
SHAf8cd1e882b9fc9361f3be72ba20b34802cfb2c1583f9571f3d729894f1d78a5f。
所有Blender子crash→同source hash/2 meshesを138.523秒で回収、元正式版不変。
browser exit0、専用source server正常終了。source healthは標準起動外のenvironment missing/
setup_requiredであり、healthyやinstalled30分受入の証拠へ拡大しない。
GUI終了後の全 ./mf.sh test:1345 passed/既知warning2/156.42秒、exit0。
次は本修正の署名release/標準update後、既定idleの同じ実診断を新しい専用sessionで再実行する。

## 2026-09-10 v0.28.50 installed / default connected idle diagnostic

前goal turnは署名公開/PR #380 mergeまで進捗。main a2081e6とhandoffを再確認。
開始時job_a9b39db312f74d52baceb93ecc316d0fがrunning/generatingで更新を行わず、
診断の準備を進めた。その後実DBでactive Jobs0を確認し標準updateを再実行。
/data1tb/mf-0.28.50-install.py、Host診断venv、既存CONTROL_DECK_CONFIG/PYTHONPATH。
署名/public bytes照合→idle→SQLite backup→再確認→標準installの順。
10.401秒で0.28.50/HTTP healthy、Host PID667000不変、MF PID1001944。
DB全テーブルfingerprintとBlender登録bytes不変、更新後Jobs0/GUI0を確認。
backup/証跡 /data1tb/mf-0.28.50-update-qk_3u_rk/observations.json。
currentはversions/0.28.50。標準保持規則で0.28.48実行bundleだけが整理され、
0.28.49/.50を保持。制作物/runtimeは削除しない。旧bundleは公開releaseから再取得可能。

ux1/3d-default-idle-acceptanceで既存installed lifecycle診断にconnected-idle mode追加。
専用mf-e2e sceneだけを実RFB複製し、既定idle1800/disconnect300秒をassert。
操作を送らず30秒ごとに同sessionの状態/接続状態/最終入力時刻を証跡へ追加。
時刻リセット・短縮policy・早期/過遅終了・別原因終端は拒否する。
終端後にPID/cgroup/root/socket回収、候補hashと復旧source一致、
回収mesh数2倍、元正式版/旧hash保持まで既存診断を使う。
server timeout/認証時計を置き換えず、Host/他processを停止しない。
停止観測開始は実入力後のためelapsed許容1790〜1900秒だが、
server policyは厳密1800秒。新7 casesを含むfocused17 tests/0.08秒通過。
viewer build/diff check成功。全 ./mf.sh test:1344 passed/既知warning2/141.53秒、exit0。
実診断をHost診断venv/既存CONFIG/PYTHONPATH、DISPLAY=:0、
XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3で開始した:
scripts/3ds_save_conflict_cleanup_installed_e2e.py
--scene-id scene_3f3b5f1e97e94b268722ea45cc811c50 --expected-version 0.28.50
--failure-kind connected-idle --evidence-dir /data1tb/mf-default-idle-installed-20260910。
実CLI PID1004438、exec handle3638。session blendersession_2c16d66b8b1447ff9a5198405b11f935。
Blender4.5.13の実描画/ConnectedをPNGで確認。RFB複製入力後のworking hash不変をassert。
38.067秒sampleでready/connected、最終入力17:14:32.231864 UTCの不変を確認。
診断は実行中でありpassed未確定。次turnは同handle/PIDを再確認して観測を継続し、
観測待ちだけを根拠に再起動/再実行しない。最終復旧mesh数・終端回収もまだNOT TESTED。
全3DS/GA/ボーン制作全体はPARTIALを維持する。

## 2026-09-10 v0.28.50 signed publication / installed update deferred

PR #379 MERGEDのae63fbe2ab519effdc88ed8e55b71d71e7f705c4をexact checkout/tagへ固定。
checkout /data1tb/ControlDeckMediaForge-release-0.28.50、build /data1tb/mf-0.28.50-build-20260910。
既存scripts/build_release_bundle.pyをbundle-build venv/PyInstaller6.22.0/Python3.12.3で実行。
artifact31,533,336 B/SHA915f36d835b645ddf558b212fdabf99b852e72ef1dd7954c2f937504f5a6de3e。
/data1tb/mf-0.28.50-audit.pyでCArchive201 entries、禁止名混入なし、
certifi PEM一致、worker2/schema3 exact bytes、PYZのfailure readerとrfb_client_activity同梱を確認。
専用data/cacheのpackaged doctor:ok/version0.28.50/packaged=true。
展開先 /data1tb/mf-0.28.50-package-h_eusz5o、buildのverification.jsonへ記録。

既存発行者鍵で署名・自己検証し、v0.28.50を正規release公開:
https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.50
artifact/checksum/manifest/signatureの4公開ファイルを
/data1tb/mf-0.28.50-public-20260910へ再取得し全bytes一致。
実Hostのtrusted publisher検証で同version/hashを確認（同dir/verification.json）。

標準update診断 /data1tb/mf-0.28.50-install.pyをHost診断venv/
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml/
PYTHONPATH=/data1tb/ControlDeck/app/backendで実行したが、2回ともidle gateで拒否。
開始前はJobs0だったが直前に生成Jobが開始していた。install呼出には到達していない。
job_5b6bed82abb44b3ea17b44eea2bb77ecはrunning→succeededを実DBで確認。
続いてjob_3db1d1e81a974beab686bc4574c7e0d9、
job_17a8641c63264f288e7d2f9d638f44ba、job_e197c881b7974790ad988d6ab456773d等の
別生成Jobが連続してrunningとなった。これらを取り消さずserviceも止めない。
installed0.28.49/MF PID975293/Host667000を維持し、公開済みを導入済みとは書かない。
この記録は署名/public consumer受入のみ。productionデータ削除/Blender変更なし。
release preparationの全1337 tests/138.93秒とviewer build成功を参照。
次は生成処理の落ち着いた時点でidle・backup・再確認付き標準updateを再開し、
installed0.28.50とDB/registry保持を確認後、既定connected idle1800秒を測る。
NOT TESTED: installed本修正・idle・全3DS/GA完成。全体目標はPARTIAL、権限不足とはしない。

## 2026-09-10 v0.28.50 release preparation

前goal turnはPR #378の実装・実source受入・通常mergeまで進捗。
merge e4568d9acee3b5c346e36828e8629bccfdce5775をorigin/mainと照合し、
ux1/3d-release-0-28-50でaddon/coreを0.28.50へ揃えた。
RFB入力だけを数えるidle修正と再接続時刻保持を配布する準備。
DB/schema/tool/capability/runtime pinの変更はない。
docs/release-v0.28.50.mdにsource証拠とinstalled/30分idle未検証を明記。
開始時の実installedは0.28.49、active Jobs0/GUI0、
Host PID667000/MF975293ともactive。service再起動はまだ行っていない。
viewer build/diff check成功。全 ./mf.sh test:1337 passed/既知warning2/138.93秒、exit0。
署名/public download/Host trusted verify/標準update/installed idleは次の実測。
全3DS/GAゴールはPARTIALを維持する。

## 2026-09-10 RFB input-only idle clock (source)

main6e534b7とPR #213 MERGEDを再確認。ux1/3d-rfb-input-activity。
既存relayは全binary frameで操作時刻を更新し、画面更新要求もidle延長になっていた。
さらにacquire_gatewayが再接続ごとに時刻をリセットしていた。
base-plan/integration/runtime-Web設計を先に更新し、両者を修正。
固定noVNC/XvncのRFB3.8/Noneをbounded observerで判定し、完全なkey/pointerだけを数える。
画面要求/negotiation/fence/clipboard/resizeは数えない。分割/結合を跨いで解析し、
header最大20 B、可変payloadは保持せずskip、未知形式/上限超過はfail-closed。
readyの切断では最終入力時刻を残し、core再起動後は永続時刻からmonotonic期限を再構成する。
Host/public schema/個人設定/既存Blender実体は変更しない。新しい同期I/Oは追加しない。

実sourceコマンド: PYTHONPATH=.:backend .venv/bin/python scripts/3ds_autosave_source_e2e.py
--serve --data-dir /data1tb/mf-rfb-input-source-data-20260910-r2
--runtime-root /data1tb/mf-long-setup-source-20260906/runtimes/blender/blender-4.5.9-linux-x64
--web-root /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/blender-web
--blend /data1tb/ControlDeck/data/feature-data/media-forge/data/assets/asset_263d5f26d18b4d05b65357c4aa8d26e7.blend。
browserはHost診断venvのPython、DISPLAY=:0、
XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3、同script
--data-dir <上記> --evidence-dir /data1tb/mf-rfb-input-source-20260910-r2 --verify-input-activity。
初回serveはPYTHONPATH=backendのみでscripts import失敗。.:backendへ修正。
先行run /data1tb/mf-rfb-input-source-20260910 は127.707秒/2 meshes回収成功だが、
再接続修正前のsourceなので再接続の証拠には含めない。

最終run: session blendersession_8a6249d94371453ea0044927ce58d414。
実RFB手編集1→2 meshes、保存前working hash不変。
24回の実framebuffer requestでdurable入力時刻不変、実canvas pointerで更新、
Close view only→同session再接続後も入力時刻不変（36.188秒時点）。
既定120秒autosaveの成功を126.307秒時点で観測。候補445460 B、
SHA771d3e345bc4749b0dcadeac7bc91929269a21c9c675af54c4056c030b506a39。
所有Blender子だけをpidfdでkillし、runner_lostとPID/cgroup/root回収を確認。
復旧forkで同source hash/2 meshesを128.123秒時点で確認、元scene正式版不変。
observations.json passed=true/page_errorsなし、browser exit0、専用source serverも正常終了。
source /health は標準mf.sh起動外のためenvironment missing/setup_required。
GUI成功をcore全体healthy/installed受入へ読み替えない。

focused44 tests/6.21秒/既知warning1、viewer buildとdiff check成功。
全 ./mf.sh test:1337 passed/既知warning2/140.88秒、exit0。
NOT TESTED: installed本修正、既定connected idle1800秒終了、core再起動後の本変更の実機期限、
GPU lease、全3DS/GA完成。次は署名配布・導入後に実入力を伴う既定idle終了を測る。

## 2026-09-10 installed core restart preserves unsaved GUI edits

前turnは実OpenCode修正受入/PR #376 mergeの進捗。main7644e35とhandoff/lifecycleを再確認。
ux1/3d-core-restart-editで既存GUI診断へ明示core-restart modeを追加。
唯一の検証GUIとactive Jobs0を直前に照合し、固定cdapp-feature-media-forge.serviceだけを
systemctl --user restartする。Host/PC/他unitは再起動しない。busy/不正IDを拒否する4 tests追加。

実コマンドはHost診断venv、DISPLAY=:0、
XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.AZO7U3、
scripts/3ds_save_conflict_cleanup_installed_e2e.py --scene-id scene_3f3b5f1e97e94b268722ea45cc811c50
--expected-version 0.28.49 --failure-kind core-restart --evidence-dir <下記>。
既存の専用mf-e2e material conflict enだけを新revisionへ進め、旧版を保持する。

初回 /data1tb/mf-core-restart-edit-installed-20260910:
MF960863→972623/HTTP healthy0.979秒、Host667000不変。
保存後mesh1→2/第6→7版と旧bytes保持は成功したが、再接続直後PNGは黒画面だった。
接続フラグだけで描画成功とするassertionが弱いため、実canvas色数とConnected文言を待ち、
再接続後にも手編集して保存する診断へ修正。初回を描画復帰成功には読み替えない。

最終 /data1tb/mf-core-restart-edit-installed-20260910-r2/observations.json:
session blendersession_b6603c2744064043820c13f159778598、
旧MF972623→975293、Host667000不変、HTTP healthy0.986秒（画面復帰時間ではない）。
専用GUIのPID974155/974159/974203、unit/root/socket/cgroupを再起動後も保持。
第7版の2 meshesをRFB操作で4へ複製し、autosaveを待たずcore再起動。
再起動前後のworking .blend hash不変、同sessionへopaque iframeから再接続。
実Blender描画/Connectedを確認し、追加RFB操作後にSaveで第8版/8 meshesを確定。
再接続PNGではoutliner4 objectsを実視認。直後の追加編集PNGは更新前の4 objects表示であり、
8への変更は保存後のBlender検査/GLB bytesで確認した。
revision_fade9d2ba6fe4defa1ee48b896cd8afd、
GLB asset_74066341b1164748a53efa842cbe38a4/11376 B、
SHAed30cddbc76b94a0c380c0161b64e84f941c73ef45d597cf09304b22ad48f24d。
独立GLB読取で8 mesh nodes（glb-verification.json）。
全旧14 source/previewファイルhash不変。保存終了後3 PID/cgroup/root/socket消滅、active GUI0。
これはready状態の正常service再起動とRAM内編集の継続であり、電源断/crash/保存途中の復旧とは別。
一時認証sessionはfinallyでrevoke、個人設定/既存Blender実体/Hostコードは変更しない。

focused14 tests、viewer build/diff check成功。
GUI並行の全テスト初回は1311 passed/1 failed、151.57秒。
既存test_autosave_status_read_does_not_block_event_loopの全経路<1秒assertionで1.121秒となった。
GUI終了後、同test単独は成功。基準を緩めず、最終全 ./mf.sh testを直列再実行:
1312 passed/既知warning2/144.85秒、exit0。
同時負荷との因果関係は断定しない。production変更なし、installed0.28.49を維持。
NOT TESTED: 接続中既定idle1800秒、core crash/保存途中再起動/電源断、GPU lease、全3DS/GA完成。
次は同じ手編集・ファイル保持・process回収の観測を既定connected idle終了へ適用する。

## 2026-09-10 real OpenCode diagnosis and corrected edit

前turnは0.28.49署名配布・installed MCP直接修正の進捗。main12fd048とhandoffを再確認。
branch ux1/3d-opencode-failure-repairでscripts/3ds_opencode_repair_e2e.pyを追加。
新規専用project/sceneだけでMCP setup:立方体作成→2操作editの後半を不在IDで失敗させる。
ここまでは手入力fixture。その後は実OpenCode/既存local gatewayへ自然言語で修正を依頼。
元制作Job・失敗Jobの照会、snapshotのbase確認、入力修正、新Job成功までを実LLMが行う。
private configの許可はstatus/snapshot/edit/capabilitiesのみ。skill/shell/file/webは無効。
正しいIDを答えとしてpromptへ渡す代わりに元Jobを照会させるが、失敗recipe内には既存target IDも含む。
複雑な幾何検査からの推論、Blender Skills読込、rig修正の受入とは扱わない。

実コマンド: CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml
PYTHONPATH=/data1tb/ControlDeck/app/backend /data1tb/ControlDeck/app/.venv/bin/python
scripts/3ds_opencode_repair_e2e.py --project-name MF3DS-Failure-Repair-20260910
--evidence-dir /data1tb/mf-opencode-failure-repair-20260910。
専用CLI PID963977、exit0/144.116秒。
実tool完了:元Job28.618秒、失敗Job37.029秒、snapshot44.843秒、
edit93.385秒、新Job成功98.809秒。5実tool callsのみ。
失敗理由を参照したうえで不要な中間移動を省き、targetを[2,0,0]へ移す単一操作へ修正した。
最終応答も実エラー・原因・新Job/revisionを正しく報告。

scene_2d2921e9829e4f3b8e3d5321f436d268、
base revision_d5a150ae08654629a519c6f4c5393e8c、
失敗Job job_173f97a4b6e04a1d8c3c832c305f4e4d、
修正Job job_0df96adff0794d0fb2dc6a9ffe72c5e0 succeeded、
第2版revision_f8280780203f44578145bdbc5bd3bca3。
旧sourceのHTTP再取得hash不変、元版を親にした2 revisionsを確認。
GLB asset_8b0ec8fa2f964f21b8dcff09ee8458e9/1780 B、
SHAe58749af6bd4b6e8bc6b2e4d8525f994be1347adee630090bb576ccc0ba21e59。
独立読取でGLB一mesh/一node/translation[2,0,0]を確認。
実DBの成功Job、正規化した実tool入力とdurable recipeの一致も確認。active Jobs0。
証跡は上記dirのevents.jsonl、observations.json、delivery-verification.json、prompt.txt。
一時provider configはfinallyで削除。既存robot/project files/Blender実体/Host設定は変更しない。

verifierは診断前/欠落/遅い診断、終端未確認、別scene/base/対象、誤座標、retry流用、
追加edit/shellを拒否する11 tests。実行後に診断CLI cleanupの二重finallyを追加し、
terminate timeout時は所有childをkill/waitしてもconfig削除へ到達する。
この強制終了分岐はNOT TESTED、上記実runは正常終了。
frontend build:viewer/diff check成功。最終全 ./mf.sh test:1308 passed/既知warning2/138.31秒、exit0。
NOT TESTED: 見た目・rig/animation自動修正、全3DS/GA完成。
次は原3DSの残存lifecycle受入（実手編集後のidle終了/再起動復旧）へ戻る。

## 2026-09-10 v0.28.49 signed / installed / MCP failure correction

PR #374 MERGEDのf3eb61542a13a7cb053680c2b32eaa30c1b14a40をexact checkout/tagに固定。
31,568,987 B/SHA119ada52b1535ad8855c5857d520f5ff18bfa946f1ac55499b9c2e48a1abd431。
PyInstaller6.22.0/Python3.12.3、CArchive201 entries、禁止名混入なし、
certifi PEM一致、worker2/schema3ファイルexact bytes一致、新failure readerのPYZ同梱を確認。
専用data/cacheでpackaged doctor:ok/version0.28.49/packaged=true。
監査: /data1tb/mf-0.28.49-audit.py、build-20260910/verification.json
（後者の完全pathは/data1tb/mf-0.28.49-build-20260910/verification.json）。
既存鍵で署名しv0.28.49公開。公開4ファイルをpublic-20260910へ再取得してbuildとbytes一致、
実Host trusted署名検証も通過。利用者の鍵生成/個人設定への書込は行わない。

専用診断 /data1tb/mf-0.28.49-install.pyでidle再検査→SQLite backup→標準exact-tag install。
10.393秒、実HTTP healthy、DB全15テーブルfingerprintとBlender registry bytes一致。
backup: /data1tb/mf-0.28.49-update-ub76uv_a（observations.jsonに前後比較）。
Host PID667000不変、MF960863、current0.28.49、保持版0.28.48/0.28.49。
標準保持で0.28.47の実行bundleだけ整理。制作data/Blender実体は保持し、
旧実行版は公開releaseから再取得可能。利用者へ通知済み。

実installed Host MCPの直接呼出しで、新規専用scene作成→2操作editの後半を不在IDで失敗
→snapshotで元版保持→同baseからIDを修正した新edit成功を確認。LLM実行とは区別する。
最終証跡: /data1tb/mf-recipe-failure-installed-20260910-final/observations.json
診断: /data1tb/mf-recipe-failure-installed-20260910.py。所要2.419秒。
scene_48f6b6b9a465498fadd7e42cde911931。
create Job job_b36bf89c5c374be99611ba4968e6f0aa succeeded、
失敗 Job job_8220835954d64ebda13b5988b3ba46d5 failed/scene_recipe_failed、
修正 Job job_942fe860a17149da91dce8e6b13dcc71 succeeded。
実MCPのerror.messageはOperation 2/2 (transform.set, object_id=missing) failed:
target object does not exist; inspect stable object IDs。
失敗後revision_count1、修正後2/親は元版。旧sourceを再取得して
SHAfa4442be19bb06980ca730dd67d8da8740f21b92db68f705efd854491ffee528不変を確認。
入力は既存schemaで正規化後、実DB request_jsonとledgerの2件が一致。active Jobs0。
一時provider configはfinallyで削除。新規検証sceneだけを操作し既存robotは変更しない。

初回MCP診断はprimitiveの必須name/dimensions不足で拒否。
r2は操作成功/2.495秒だが、記録配列の参照共有で失敗入力のledgerが後の訂正値へ変化した。
コピー保存へ直したfinalの新規sceneで再検証し、r2のledgerを最終証拠へ読み替えない。
DBとの初回照合はdefault展開前/後の比較でassertion失敗、同schema正規化後に一致を確認した。
各中間検証sceneは保持している。未追跡.venvは既存のまま除外。

配布準備の全テスト1297 passed/既知warning2/137.72秒、viewer build成功。
今回の追記はdocsのみ、diff checkを実施。
NOT TESTED: 自然言語の自動修正一巡、全3DS/GA必須受入の完成。
次は実LLMへ失敗診断を返して修正を完走させる経路を検証する。

## 2026-09-10 v0.28.49 release preparation

PR #373 MERGED/main c06eace24b285d3ecb388a3f65cf855c5a2ec733を確認。
前turnは失敗箇所診断の実装・実Blender受入・mergeを完了した進捗。
ux1/3d-release-0.28.49でcore/addonを0.28.49に揃えrelease noteを追加。
公開schema/tool/capability/DB migration変更なし。
全 ./mf.sh test:1297 passed/既知warning2/137.72秒、exit0。frontend build:viewer/diff check成功。
実HTTP /health healthy、Host PID667000/MF921443 active。
DB Job終端のみ（canceled9/failed189/succeeded593）、GUI終端のみ（failed4/interrupted9/stopped19）。
GUI表/列の初回読取は名称違いで失敗し、sqlite_master/PRAGMAで確認した
blender_web_sessions.stateから上記を取得。失敗した読取をidle証拠には使わない。
installed0.28.48/制作物/個人設定は変更していない。
次は確定mainからbundle構築・監査・署名公開・標準updateとinstalled MCP受入。
NOT TESTED:0.28.49の配布/導入/LLM自動修正、全3DS/GA完成。

## 2026-09-10 typed recipe operation failure context (source)

最新main57c6ff6、PR #213 MERGED、現行設計/引き継ぎを再確認。
前回の自然言語の用語確認は実装進捗ではなく、.48以降の次の安全な実装を開始した。
branch: ux1/3d-recipe-failure-context（PR作成前）。全体GOALはPARTIALのまま。
Host user unit PID667000、MF921443 active。system unitではなくuser unitを確認する。
installed0.28.48は変更せず、既存Blender/利用者設定/Hostコードへ書き込まない。

_apply_recipe_workerにはpython-exit-code指定がなく、操作例外が出力欠落として報告されていた。
--python-exit-code 1を追加し、trusted workerが失敗時だけprivate failure@1に
0始まりindex/固定reason/Blender版を記録する。coreは4 KiB以下・通常file・版・index・
reason allowlistを検査し、元のvalidated recipeから1始まり番号/操作type/object_idを組み立てる。
既存error.code=scene_recipe_failedとerror.messageを使い、公開schema/tool名は変更しない。
不正/欠落診断は一般エラー。生の例外・traceback・パスは返さない。
新規file読取はasyncio.to_thread内、O_NOFOLLOW/O_NONBLOCKでリンク/FIFO待機を拒否する。

自己検査で初版readerのdirectory open後のfd漏れを再現（20回:4→24）。
open/fstat/readをfinally closeへ変更し、修正後20回:4→4、negative testも追加した。
初回fd診断はtransform入力不足でPydantic拒否、location追加後に上記漏れを観測した。
不足入力の実行をfd検査の成功とは扱わない。
22 testsは診断構造/巨大・不正UTF-8・深いJSON/型違い/版違い/秘密文字列/
missing・symlink・FIFO・directoryとfd保持を検査。既存Job projectionのerror保持もassert。

実コマンド: PYTHONPATH=.:backend .venv/bin/python scripts/3ds_game_static_e2e.py
--fixture motion --replace-clip --runtime-root /data1tb/mf-long-setup-source-20260906/runtimes/blender/blender-4.5.9-linux-x64
--evidence-dir <下記>。4.5.13は追加で
--managed-root /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/blender。
最終証跡:
- /data1tb/mf-recipe-failure-context-source-20260910-final:4.5.13/3.282秒/PASS
- /data1tb/mf-recipe-failure-context-source-4.5.9-20260910-final:4.5.9/3.276秒/PASS

両版でcreate→clip追加→同clip置換の3版、source/GLBの骨/動作/旧曲線とhash保持を検査。
置換後に不在object参照を続けたrecipeは
Operation 2/2 (transform.set, object_id=missing) failed: target object does not exist; inspect stable object IDs
をscene_recipe_failedとして返し、元head/3 revisions/6 assetsを保持した。
これは実Blender+domainの診断で、実installed Agent MCPやLLM自動修正の受入ではない。
frontend build:viewer/diff check成功。全 ./mf.sh test:1297 passed/既知warning2/139.15秒、exit0。
NOT TESTED: この変更の署名bundle/installed、自然言語による自動修正、全3DS/GA完成。
次はこの変更を署名版へ配布し、installed MCPで失敗箇所取得→修正の経路を検証する。

## 2026-09-10 v0.28.48 signed / installed / manual MCP repair

PR #371のmain b6b2a985ff5fdb2e0cd8dd26aed2aea8b21eb821から署名版v0.28.48を構築・公開。
artifact31565842 B、SHA7795859e9989b9d0e6aada08e222690d26e29f74449cfb949308c06a2f5408c2。
CArchive201 entries、制作物/venv/秘密鍵等の禁止名混入なし、certifi PEMはbuild runtimeと一致。
worker2ファイルとcreate/edit/workflow schemaはexact checkoutと同一。
packaged doctor:0.28.48/ok。初回launcher診断は必須Host環境変数不足で失敗し、
専用feature-data/cacheを指定した再実行で成功。実Host設定を省略した失敗を製品障害としない。
公開4ファイルを再取得しbuildとbytes一致、実Host trusted署名検証も成功。
証跡: /data1tb/mf-0.28.48-build-20260910/verification.json、
/data1tb/mf-0.28.48-public-20260910。

idleとbackup後、exact-tag標準installで.47→.48を9.807秒で更新。
DB全15テーブル/Blender registry不変、実HTTP healthy、addon enabled=true/version0.28.48。
Host PID667000不変、MF921443。backup/比較結果:
`/data1tb/mf-0.28.48-update-aqnlovyf/observations.json`。
標準保持で.46実行bundleのみ整理し、.47/.48を保持。制作data/Blender実体は削除しない。
旧実行版は公開releaseから再取得可能。PC/Host再起動は実施しない。

実installed Host MCPのedit schemaでreplaceを確認し、前回directorが作った
scene_509b6ee0b688492997b86b535d70ec9aの第1版を明示baseとして修正。
両腕Xを±0.250→±0.225m、既存idle/arm_swingを同じkeysでreplace=true/loop=trueへ変更。
Job job_33ee2dedbb384336b7fcf8a0318078ad succeeded、1.731秒。
新revision revision_52149c92fb8a41f1b1f727390a010258。
GLB asset_4d359d6ce7da4684a0156750e7d146e5、29932 B、
SHAb36b26954162e40ced1a0dc99de958a4b76218f635324055244d35ba615ea61d。
before/after source/GLBをopaque Asset IDで取得し、4件とも実bytes/metadata/provenance hashを照合。
一時実行configは削除、active Jobs0。元projectのexports/robot.glbも不変。

証跡 `/data1tb/mf-motion-repair-installed-mcp-20260910` の
observations.json、repair-inspection.json、glb-inspection.json、placement.json。
実Blender4.5.13でframe0のmesh edge/triangle BVH交点を検査し、
修正前の胴/両腕false→修正後true、頭/脚を含む指定5接合すべてtrue。
2 actionのloop metadataはfalse→true、全curve/keyは不変。
inspect_repair.py SHA cbde97180e609af411ee75365f8d9763d85e598eff81901b44ab8f6fa3400270。
GLB再importでも7骨/6部品/136 triangles、idle2秒/arm_swing1秒、
実mesh移動・loop両端差0を確認。これはframe0接合の検証で、全時刻の接合/見た目承認ではない。
新しいproject grantからrepaired-exports/robot.glbへmedia.packで配置。
receipt committed=true、Host asset:cdb8b4b5-75e2-4bf6-990d-5663a700a64f、
実bytes/receipt SHA一致、元exports不変。旧版を上書きせず同scene第2版として保持した。

配布準備全テスト1275 passed/既知warning2/137.27秒、frontend build:viewer/diff check成功。
今回の追記はdocsのみ。修正は手動MCP呼出しであり、LLMが検査から自動修正した証拠ではない。
NOT TESTED: 自然言語修正一巡、全時刻接合、browser/engine playback、見た目/歩行、
原3DS/GA全体完成。次は検査結果を自然言語修正へ戻す経路と残存3DS必須受入を進める。

## 2026-09-10 v0.28.48 release preparation

PR #370のmain630225eからcore/addonを0.28.48へ揃え、release noteを追加。
clip replaceの明示性・旧insert-only互換・共有action保護・旧revision保持を記載。DB migrationなし。
事前確認: installed0.28.47、Host PID667000/MF876222 active、active Jobs0、GUI稼働0。
全 `./mf.sh test`:1275 passed/既知warning2/137.27秒、exit0。
frontend build:viewer/diff check成功。署名公開・標準update・installed受入は次工程。

## 2026-09-10 explicit clip replacement in immutable scene revisions

前turnはPR #369の実director制作/失敗品質検出を完了した進捗であり、全体完成ではない。
main3ad2c81と現在のhandoff/編集worker/GA設計を再確認。
既存transform.setは位置を変更できる一方、clip ID重複は追加専用で拒否するため、
base-plan/integration/GA設計を先に更新し、animation.clipへstrict bool replace（既定false）を加法追加。
create/edit/workflow公開schemaとdocs/apiを同期。operation名/件数13、旧insert-only動作は維持する。
replace=trueは同じtyped rigの既存clipを要求し、全tracks/name/loop/frame_countを置換する。
FPSは既存scene一致、他action/旧revisionは保持。任意action編集や他rigの参照解除を行わない。

workerは既存action構造、全rig/NLA、対象ID一意性、共有action/余分なusersを検証。
置換後のclip/key/sample予算を再計数し、隔離workerの作業コピー内だけで
旧曲線を解放して新曲線を作る。最大32 clipsで同容量の置換に33個目を恒久追加しない。
構築/後続処理/export失敗で元immutable sourceやcurrent revisionを上書きしない。
新しい同期処理はBlender worker内のみ。Host/個人設定/既存Blender実体へ変更しない。

scripts/3ds_game_static_e2e.py --fixture motion --replace-clipと
scripts/motion_fixture.pyでcreate idle→arm_swing追加→同ID置換の3版を実行。
sourceの腕振りを1秒/-60度から2秒/-30度へ修正し、loop/nameと同時刻の実bone角を確認。
既存idle全curve不変、clip/NLA件数2、旧source/hash不変、GLB再importの前腕bounds差<1e-4m。
不在ID/replaceなしの重複/FPS変更/loop不一致/別rig共有の5 negativesを拒否。
32 clipsまで追加した作業メモリで3回置換し、action/NLA件数32とidle不変を確認。

最終原子性診断:
`/data1tb/mf-clip-replacement-atomic-source-20260910-r2`（Blender4.5.13）3.171秒、
`/data1tb/mf-clip-replacement-atomic-source-4.5.9-20260910-r2`（4.5.9）3.179秒、双方PASS。
さらにreplace→不明object参照のrecipeはscene_recipe_worker_invalidで失敗し、
headは第3版のまま、Asset6件、Job成功3/失敗1。各Asset metadata/provenance hashも照合。
このエラーは既存runnerの出力欠落検査によるもので、詳細な失敗操作の公開は未実装。
初回実行はPYTHONPATHのrepo root不足。共有rig negativeの初回はview_layer更新前で
pose未構築のため診断側AttributeErrorとなり、更新後に正しいRuntimeError拒否を確認。
原子性negativeの初回は想定error codeが実装と異なり診断assertion失敗。
既存runnerの非zero終了/出力欠落の両拒否codeを区別して記録するよう修正した。
中間の失敗証跡は保持し、最終PASSへ読み替えない。

focused animation/rig/static/contracts64件、frontend build:viewer/diff check成功。
全 `./mf.sh test`:1275 passed/既知warning2/138.86秒、exit0。
未署名公開・未installed・未OpenCode受入。導入済み0.28.47でreplaceを利用可能とは案内しない。
NOT TESTED: 前回robotの隙間/loop指定修正、自然言語での修正一巡、見た目/歩行/engine、
GA全体と原3DS必須ゴールの完成。
次は署名版へ配布・導入し、前回不合格のrobotを同じsceneの新revisionとして修正・再検証する。

## 2026-09-10 actual OpenCode director motion delivery / quality gate failed

最新main7240b9cとPR #213（MERGED）、3DS設計/関連3文書/G8計画を再照合。
installed0.28.47、Host PID667000/MF876222 activeを確認した。
scripts/3ds_opencode_flow_e2e.pyへ--director-motionを追加。
private実行configだけでdirector読込を許可し、既存剣/画像/復元モードは維持する。
自然言語から新規robot、rigid skin、idle/arm_swing、GLB、project grant配置を依頼。
手入力recipeでのMCP受入とは別の、実LLM/skill実行である。

実コマンドはHost診断venvで
`scripts/3ds_opencode_flow_e2e.py --director-motion --project-name MF3DS-Director-Motion-20260910 --evidence-dir /data1tb/mf-director-motion-installed-20260910`。
OpenCode1.18.29/current auto/local gateway、既存Qwen3.8-27Bを使用。
最初のbuild応答headerが300000ms timeout。同一CLIの自動retryを追跡し、
390.550秒でskill completed（本文3694文字）、397.762秒capabilities、
565.919秒create、600.981秒status、618.019秒snapshot、624.832秒export、
632.261秒grant、637.393秒pack、655.425秒exit0/8 tool calls/robot.glb一件。
Brokerの直近requestに同LLM residentをblockingとするexpiredがあるが、
cold起動時の根本原因・requestとの一意対応は未確定。再起動/モデル切替は行わない。
証跡は同evidence-dirのevents.jsonl/observations.json/resource-diagnosis.json。

制作Job job_719babe2682241409bd62f4e64fb23abは実DBでもsucceeded。
scene_509b6ee0b688492997b86b535d70ec9a、
revision_0db4ed1de5724ae7b7554908bc8e5f49、
GLB asset_328a09210c634ce7ad4cc546fc23552f。
29932 B/SHA464d7265aa1431b92aa31287c16b6790ac2ea54520700f3d5bc4e11779d90303。
単一配置receiptと実bytes/Asset metadata/DB provenance.output_sha256の一致を診断確認。
一時runtime configはfinallyで削除済み、active Jobs0。既存制作物/他OpenCode processは変更しない。

追加scripts/3ds_inspect_motion_delivery.pyを実Blender4.5.13で実行:
7 bones/6 skinned meshes/136 triangles、寸法0.610×0.260×0.980m。
idle2秒/arm_swing1秒、実評価meshの中間移動と両端差0、GLB hash不変を確認。
motion-inspection.jsonを保持。sourceとの比較・ブラウザ/engine再生の証拠ではない。

**制作依頼全体は不合格**。生成recipeはloopを省略し、公開既定falseのため
loop端点のworker検証が無効。実GLBの両端一致だけで指定不足を合格に変えない。
追加verifierはこの実入力をAssertionErrorで拒否した。
またrestの実GLB boundsで胴X最大0.190m、右腕X最小0.195m（左側も同様）、
両腕に約0.005mの分離を確認。接合要求を満たさず、かっこいいrobotの完成とは案内しない。
旧skill表でも現行schemaの骨格/clipを実行できた証拠だが、品質の自動修正は未受入。

verifierはskill未読/遅い読込、欠落操作/clip、duration/loop指定、
不正Job/receipt/bytes/revision/toolを拒否。単一/一括media.packの両契約を扱う。
focused28 tests、frontend build:viewer/node --check/diff check成功。
最終全 `./mf.sh test`:1272 passed/既知warning2/176.53秒、exit0。
NOT TESTED: 指摘を受けた自然言語修正と再検証、接合の自動品質検査、
歩行/root motion/滑らかなweights/IK/FK、見た目承認、全3DS/GA完成。
次は接合/clip指定の検証結果を制作の修正工程へ戻す経路を進める。
公開product変更のない診断sliceで、installed版は0.28.47を維持する。

## 2026-09-10 v0.28.47 signed release / installed MCP rig and clips

PR #367のmain709b185から署名版v0.28.47を公開・標準導入した。
artifact31565033 B、SHA256
9647c10c03497a181173c32681ca435f828eea0c59779285eba76d058f058f80。
公開4ファイルを再取得しbuildとの同一性、Hostの信頼済み署名検証を確認。
packaged doctorは0.28.47/ok。bundle監査・embedded worker/schemaのexact checkout一致も確認した。

idle確認・SQLite backup後のexact-tag標準updateは10.032秒。
実HTTP healthy、13 operations、DB全15テーブルとBlender registryは更新前後一致。
Host PID667000は不変、MFは876222へ更新。証跡:
`/data1tb/mf-0.28.47-update-24txxywi/observations.json`。
標準2世代保持で.45実行bundleのみ整理、.46/.47を保持。制作data/runtimeは削除しない。
旧実行版は公開releaseから再取得可能。

実installed Host MCPで11 bones/25部品robot+idleをcreateし、
別revisionへarm_swingをedit、両方GLB export・opaque Asset ID経由download:2.471秒/PASS。
証跡: `/data1tb/mf-rig-clip-installed-mcp-20260909/observations.json`。
created/edited blendとGLBをBlender4.5.13で検査。editedのposed-inspection.jsonで
idle2秒/arm_swing1秒、旧clip不変、GLB motion保持、loop端点一致、
duplicate clip/FPS変更拒否がtrue。4出力のSHAとDB provenance.output_sha256を再照合、
active Jobs0を確認した。これは手動MCP呼出しであり、LLM/skill実行の証明ではない。
inspectorの汎用not_testedにあるinstalled MCPはinspect単体の範囲で、
この外側の実MCP runner証跡と区別する。

release準備の全テスト1258 passed/既知warning2/139.25秒を継承。
今回の追記はdocsのみ。NOT TESTED: 新操作の自然言語OpenCode/director、
ブラウザでのclip再生、歩行/root motion、分布weights、IK/FK/retarget、
engine再生、見た目の承認、原3DS/GA全体完成。
次は自然言語/skillから新操作を使う経路と既存3DS未受入項目を進める。

## 2026-09-09 v0.28.47 release preparation

PR #365/#366を含むmain23d51b2からrelease準備。
core/addonを0.28.47へ揃え、docs/release-v0.28.47.mdへrig/rigid skin/pose/clipの
対応範囲・制限・旧operation互換とrollback注意を記載。DB migrationなし。
現在installedは0.28.46、実HTTP healthy、Host PID667000/MF825614 active。
事前確認時にactive Jobs0、GUIはfailed4/interrupted9/stopped19のみ。
全 `./mf.sh test`:1258 passed/既知warning2/139.25秒、exit0。diff check成功。
署名構築/公開/標準update/installed MCP受入は次工程で、source検証と混同しない。

## 2026-09-09 typed animation clips and real GLB playback samples

recipe@1へanimation.clipを加法追加、公開create/edit/workflow schemaとAPIを同期。
同じunionからsupported_operations13個を導出。typed rigのrest-local XYZ/LINEAR回転tracks、
0〜frame_countの昇順keys、loop端点一致、未指定boneのrest回転を明示。
fps1〜60/最大600 frames・120秒、128 tracks/256 keys per track、
scene32 clips/262144 scalar keys/250000 bone-frame samples。保存済みcurveを実計数して予算を検査。
clip ID重複、既存FPS不一致（実render fps/fps_baseも照合）、drivers/非typed actions・rig/
非rig animation/unmutedまたは未知NLA stateを拒否する。
新clipをactiveにし、旧clipを含むmuted NLA stashes/旧immutable revisionsは保持する。
生成/更新時の同期Blender処理はworker内のみ。Host/新規依存/任意bpy API公開は追加しない。

実scripts/3ds_game_static_e2e.py --fixture motionとscripts/motion_fixture.pyで
59操作の11骨/25部品robot+idleを作成し、別revisionへarm_swingを追加。
/data1tb/mf-motion-source-20260909-final（Blender4.5.13）1.869秒、
/data1tb/mf-motion-source-4.5.9-20260909-final（4.5.9）1.890秒、両方PASS。
idle2秒/arm_swing1秒、旧idleの全curve/key bytes相当JSONが不変、
各clipの実frame0/mid/endでmesh bounds center移動、両端差<1e-5mを検査。
GLBを実再importし、両actionのframe_range/durationと同時刻のworld mesh center差<1e-4m。
短いclip追加で2秒idleが1秒へ切り詰められないことも確認。
重複ID/scene fpsを30へ変更したnegativeは新action作成前に拒否し、action件数不変。
旧source/executable hashとAsset hash/provenanceも検証した。

初回4.5.13 fixtureのsourceからCPU Cycles16 samplesで動画を作成。
/data1tb/mf-motion-source-20260909/motion-preview/arm-swing.mp4、
H264/480x540/24fps/24frames/1.000000秒（実ffprobe）。
37503 B/SHA72bfb5edfa50ded3aff4eb7a42235ea910e0d2ac12fd3407de04ff3dc193937a。
provenance.jsonにsource blend SHA/出力SHA/renderer/framesを記録、source不変。
動画からframe0/12/23を抽出して全3枚を実閲覧し、曲げ戻しを確認した。
初回renderはsibling importで失敗し、recipe用importを遅延させて再実行成功。
初回ffmpeg抽出はfilter引用で失敗し、修正後の抽出を閲覧した。全動画の実ブラウザ再生は未実施。

最終全 `./mf.sh test`:1258 passed/既知warning2/140.73秒、exit0。
focused animation/rig/static/contracts61件、frontend build:viewer/diff checkも成功。
未リリース/未installed/MCP。4.5.9/13 source workerのclip作成・評価・GLB受入に限定する。
NOT TESTED: walking/root motion、速度連続性/自然な動作品質、IK/FK/retarget、
分布weights、engine再生、installed OpenCode、原3DS/GA全体完成。
次はrig/clipをまとめた署名版の公開・導入と実MCP受入。配布が終わるまで利用可能とは案内しない。

## 2026-09-09 typed bone / rigid skin / static pose foundation

利用者が明示したBlenderボーン/動きアニメーションの最初のproduct slice。
armature.create / skin.bind / pose.setをrecipe@1へ加法追加し、
公開create/edit/workflow schemaとdocs/apiを同期。operation discoveryは同じunionから12操作を導出。
骨IDはASCII48文字、ordered parents/重複・零長・非有限を拒否、1 rig128/scene256 bones。
skinは新規独立mesh全vertexを1 boneへweight1、最大64 mesh/1M vertices。
既存parent/weights/constraint/animation/shape-key/shared data/unsupported modifierを上書きしない。
poseは既知骨のrest-local XYZ回転±180度だけを置換し、未指定骨は保持。
typed marker付きrigのみ、action/他種rig混在は拒否。これはclipや有機weightsの完成ではない。

実診断scripts/3ds_game_static_e2e.py --fixture rigでsource domain→既存worker→
独立scene/GLB検証→immutable Asset/revisionを使用。scripts/rig_fixture.pyは
25部品robotを11 bonesへbindし、rest形状不変→public pose.setで右前腕60度→
実world頂点の移動/胴体不変→GLB再importでskin/weight/前腕pose boundsを検査する。
初回/R2はGLB importerが作るIcosphere（bone.custom_shapeで実参照）を
制作meshへ誤算入して失敗。bone表示helperだけを区別して25 meshを確認。
R3はskin再importまでPASSしたが、R4でpose bounds比較を加えるとrestへ戻る欠陥を実検出。

固定Blender runtimeのio_scene_gltf2ソースでexport_rest_position_armature既定trueを確認。
scene_document.pyは全rigがtyped/staticでactionsなしの場合だけfalseを指定し、
current poseをGLBのrest poseとして出す。元blendのbone restは不変。
既存untyped/animated入力のexport設定は変えない。clipを保持したexportの検証は後続。
この修正後、/data1tb/mf-rig-source-20260909-r5（4.5.13）1.716秒、
/data1tb/mf-rig-source-4.5.9-20260909（4.5.9）2.202秒、両方PASS。
restでskin無効とのvertex差<1e-5m、前腕最大移動0.3894653035m、
未操作torso差<1e-6m、再import skin25 mesh/11 bones・weights合計1・
前腕bounds差<1e-4m、旧source/executable hash不変、Asset hash/provenanceを検証。

r5/posed-renderへCPU Cycles3視点を生成し斜め像を実閲覧。
pose後も24接合pairのmesh edge/triangle ray交点を確認、離したhead negativeもPASS。
斜めPNG470815 B/SHA3638f6efaf57ba3b339f55f51cb08022e57f9395d4d4d3ab574eb653a3827c85。
全 `./mf.sh test`:1244 passed/既知warning2/138.86秒、exit0。
focused rig/static/contracts47件とfrontend build:viewer/diff checkも成功、viewer生成物差分なし。
新操作は未リリース・未installed/MCP受入。Host/global設定/既存Blenderへ変更しない。
NOT TESTED: motion clips/待機歩行、distributed weights/IK/FK、engine再生、installed/OpenCode、
ユーザーの外観承認、全GUI操作との組合せ、original3DS/GA全体完了。
次はこのsliceの署名導入/実MCP確認と、bounded keyframe/clipの後続実装。

## 2026-09-09 robot contact and multiview source acceptance

利用者の剣の隙間指摘に対応し、scripts/robot_fixture.pyで既存公開recipeだけの
静止robot fixtureと実mesh接合/CPU多視点renderを追加。既存static診断に--fixture robot、
Blender --python-exit-code 1を追加。初回はBlender側のsibling module importで
inspection.jsonが作られず失敗したため、診断script directoryを明示して再検証した。
製品core/Host/公開契約は変更しない。これはLLM制作・installed実行ではない。

実行: PYTHONPATH=backend:. .venv/bin/python scripts/3ds_game_static_e2e.py
--fixture robot --evidence-dir /data1tb/mf-robot-contact-source-20260909-final
--runtime-root /data1tb/mf-long-setup-source-20260906/runtimes/blender/blender-4.5.9-linux-x64
--managed-root /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/blender。
独立data/registryのみ使用し、実Blender4.5.13で4.653秒PASS。
25 meshes、modifier評価後2724 triangles、指定24接合pairで世界座標のmesh edge rayと
相手triangle BVHの交点を検出。AABB overlapだけではない。
頭のedgeを5m離したnegative fixtureはneckとの交差なし。任意の包含/coplanar判定は未対応。
CPU Cycles/16 samples/640x720のfront/side/three-quarter PNGを生成、
R2の全3視点とfinal斜め像を実際に閲覧。首・腰・肘に芯材があり部品が浮いていない
静止試作を確認したが、箱形主体であり利用者の「格好よい」の承認は未取得。
final斜めPNG467256 B/SHA2e78963b0e22182760dea088793f6ccd1426b531e1e3401abd97e89858550ced。
旧source/Blender executable hash不変、生成Asset hash/provenanceを検証した。
GUI/Host processやglobal設定は変更しない。render用camera/lightは検査processのメモリ内だけ。

利用者の「ポーン」はBlenderのボーン（骨格）と確認済み。GA-4/5を必須として維持。
次はbounded骨格/部品割当て→pose→vertex weights→待機/歩行clip→GLB再import/再生。
現行scene_document.pyはexport_animations=Trueで出すがbone/weight/key予算の検証はなく、
compile_asset.pyはrig/animation付き入力の破壊的geometry/material optionを拒否する。
このcode readだけでrig対応済みとはしない。typed rig操作と実受入は未実装。
全 `./mf.sh test`:1231 passed/既知warning2/141.98秒、exit0。diff check成功。
NOT TESTED: installed/MCP robot生成、rig/動的接合/animation、engine import、
ユーザーによる外観承認、従来3DS/GA全体完了。

## 2026-09-09 director skill / static operation acceptance diagnostic

既存OpenCode制作診断へ `--director-static` を追加。専用の新projectだけを作り、
blender-director実読込→複製・ミラー付き剣→新規画像材質→GLB/G8 ZIP/grant配置を検査する。
上流スキル/Host/coreは変更しない。現在の公開schemaで新2操作をpreflightし、
実OpenCode `debug agent build --pure` の解決済みskill=true、shell/read等=falseもassertする。
検証器は実skill呼出のcompleted/name/body/作成より前の順序、新recipe両操作とhandle基準X mirror、
既存Job/Asset hash/provenance/依存/receipt/寸法/2000 triangles上限を別々に検査する。
一覧への掲載や手順文だけでは成功としない。現在のgeometry目視/engine受入は別ゲート。

初回 `/data1tb/mf-director-static-installed-20260909` は診断設定の不備で不合格。
OpenCode1.18.29ではlegacy tools.skill=trueとpermission.skillを重複させると、
permission変換のkey順序により後続の全拒否が勝ち、debug agentのskill=falseを観測した。
toolsからskill項目を除き、名前別permissionだけにすると実resolved skill=trueに変わり、
shell/read/edit/write/task/webfetchはfalseのまま。専用一時configのみ、global変更なし。
初回実MCPは新2操作を含むcreateを実行したが、1個目は2892 triangles、mirror基準指定もなく、
2個目のsceneを作成しており依頼の品質を満たす証拠にならない。
画像生成/材質/GLB exportまで到達したが、skill実読込なしのため完走受入には使わない。
既知4 JobすべてsucceededをDBで確認後、所有PID827946をexe検証/pidfdでSIGTERM。
387.995秒、exit=-15、配置files0。専用configはfinallyで削除し、試験Assetは追跡用に保持。
この結果を「エージェントが利用可能なskillを無視した」とは解釈しない。

修正後R2は `/data1tb/mf-director-static-installed-20260909-r2`。
実OpenCode1.18.29/local Host gateway/auto、installed MediaForge0.28.46、Blender4.5.13。
105.876秒にskill(name=blender-director) completed、実本文3694文字を受領。
242.913秒にcreate、255.551秒にJob succeededを確認、snapshot/inspectまで成功。
scene_3230c522d9c9454b88959587fefe75c4、
revision_897bb461c2864fe39ff07d9cb8ea052f、5 meshes/322 triangles。
実recipeの独立複製とhandle基準X mirror、およびskill読込の順序を専用検証器でPASS。
ただしこれは接合・外観品質や制作全工程の合格ではない。

利用者が剣の隙間を指摘し、ロボット/カメレオン相当の造形を希望したため品質を再評価。
入力primitiveのZ extentではblade下端とguard上端が0.03m、
guard下端とhandle上端が0.025m離れている（modifier評価後の接触検査ではない）。
寸法/triangleだけで「完成」と扱わず、次sliceは接合・多視点シルエットを検査するrobot受入へ。
カメレオンの有機形状はcurve/mesh編集等の拡張対象で、現行部品組合せを完成品と偽らない。

この段階で専用PID835973をexe/pidfd検証し終了、551.693秒/exit=-15/files0。
OpenCode session exportで実行中image.generateのintentを照合し、未応答の専用
job_1d5dee700743436981aa29c6c3e888e6がqueuedのまま残ることを確認。
scene専用MCP media.job.cancelでは拒否されたため、既存standalone DELETE
/api/v1/jobs/<id>で同一の試験Jobだけ取消し、実HTTP status=canceled、active Jobs0/GUI0。
この待機理由は未診断。CLIを止めるだけでは背景Jobが回収されない点も残件として記録する。
両runの専用configはfinallyで削除。Host/core再起動なし、試験Assetは保持。
R2の新規画像適用/GLB/ZIP/配置、見た目品質、engine importはNOT TESTED。全フロー未完了。
最終 `./mf.sh test`:1230 passed/既知warning2/141.66秒、exit0。
途中runは修正前testを収集した後の診断helper更新で1 failed/1229 passedとなったため破棄し、
修正後の全suiteを最初から実行した結果を上記とする。
`npm run build:viewer`、`node --check frontend/app.js`、diff check成功、生成viewer差分なし。

## 2026-09-09 v0.28.46 signed publication, installed update and MCP schema

PR #361 merge `5bb01865112e1f9315885308432412cafad992c0`を別detached worktreeへ固定し
build_release_bundle.pyで構築（PyInstaller6.22.0/Python3.12.3）、既存publisher keyで署名公開。
artifact31,556,638 B/SHA0e1b8f9e1f3b8c9fd49b1060501067639784c3f77b8c7aad347db5a7e7b5c1b6。
bundle/公開再取得は/data1tb/mf-0.28.46-build-20260909とmf-0.28.46-public-20260909。
tar path/typeとembedded201 entriesを検査し、worker recipe/公開schema3種はexact checkoutと一致。
秘密鍵/venv/モデル/制作物の混入なし（certifiの公開CA bundleだけ許可・実bytes照合）。
packaged doctorはok/version0.28.46/packaged=true。公開4 filesはbuild出力とbyte一致、
実Host trusted publisher verifierもPASS。これはpackaged CLI/配布検証であり実制作ではない。

稼働Job/GUI0を再確認し、/data1tb/mf-0.28.46-update-i348oipzへ
SQLite backupとBlender registryを0700 directory/0600 filesで保存。
tag固定specによる標準release_bundle.installで0.28.45→0.28.46、28.243秒成功。
全15 tableの行multiset/件数が完全一致（Job781/Asset654/scene38/revision144/GUI32等）、
Blender registry bytesも不変。実HTTP200/healthy、enabled/requested_enabled=true。
current→versions/0.28.46、実core PID825614/825618。Host667000はPID不変。
標準2世代保持で0.28.44実行bundleを削除、直前0.28.45は保持。旧bundleは公開releaseから再取得可能。
制作データ、Blender実体、利用者global設定を削除・変更しない。

実HTTP capabilitiesにsupported_operations9個とobject.duplicate/modifier.mirrorを確認。
Host providerが作る専用runtime config/正規MCP bridgeでtools/listを実行し、
19 tools中media.scene.createのinputSchemaに新2操作が含まれることをassert、exit0。
一時runtime configはfinallyで削除。これは実MCP schema配信の証拠であり
LLMがdirectorを読んで新操作を実行した証拠ではない。実skill読込/制作受入は次slice。
release準備commitの全1221 tests/138.33秒を参照。この記録sliceはdocs-only。
GA全体/3DSの未完了条件、engine import、clean installed/失敗rollback残件は維持。

## 2026-09-09 v0.28.46 release preparation and skill discovery

PR #360 merge `54e9c2d69a9999db8b05d6a09e38eee6de2d6db7`からux1/3d-release-0.28.46。
core/addon版を0.28.46へ揃え、複製・ミラーの内容/制限と旧版での新recipe再実行拒否を
release noteへ記載。DB/既存Asset形式は変更しない。
全 `./mf.sh test`:1221 passed/既知warning2/138.33秒、exit0。
core/addon版一致、diff check成功。署名bundle生成/公開/標準updateは次工程。

現在のHost skill statusはBlender Skills2026.07.10-cd1、installed/enabled/effective=true、
execution.ready。Host診断環境でproviderが作る専用runtime configを使い、
実 `opencode debug skill --pure`を実行、6 skills中にblender-directorを確認、exit0。
一時runtime configはfinallyで削除。グローバル設定へ追加しない。
これはdiscoveryの証拠で、実制作中のskill読込や新2操作実行の証拠ではない。
既存OpenCode診断はskillを無効にしていたため、次の専用受入ではdirectorだけを許可し、
実skill toolの読込結果・MCP実行・成果物を別々に検証する。

## 2026-09-09 game-asset roadmap and first typed modelling operations

利用者のゲーム制作向け全機能の設計・実装開始依頼に基づき、base-plan §12と
integration §18を先に拡張。`docs/design-game-asset-authoring.md`へ
GA-0〜8/GA-X（静的mesh、UV/PBR/bake、LOD/collision、rig、animation、
環境/VFX、engine delivery、Expert、統合release）と依存・実機gateを定義。
エンジンは質問中で、未指定の間はgeneric GLB/glTF。ゲーム本体/engineの再実装ではない。
PR #213の必須3DS/GOAL/A〜Fは維持し、単純なpropだけを全体完成とはしない。

PR #359 merge25c6ce4からux1/3d-game-authoring-foundation。
最初のsliceとしてobject.duplicate/modifier.mirrorを既存recipe@1へ加法追加。
複製mesh datablockは独立、stable IDを新規予約、親/constraint/animation/shape-keyは拒否。
mirrorはlocal/reference空間、unique XYZ、1個/object、merge距離はlocal mesh座標0〜0.1。
事前の保守的geometry増幅予算1,000,000、mirror/bevel以外のmodifier付き増幅は拒否。
既存の64操作、worker subprocess/timeout/cancel、独立GLB検査/immutable commitを保持。
capabilityのsupported_operationsは同じrequest unionから導出し、未導入時は宣伝しない。
公開create/edit/workflow JSON schemaとdocs/apiを同期。Hostやskill adapterには未変更。

新診断scripts/3ds_game_static_e2e.pyをMediaForge自身のPython、
PYTHONPATH=backend:.で実行。新しい専用data/registryだけを使い、runtime実体はread-only。
最初はPYTHONPATH不足でimport失敗、その次は診断用JobRequestのasset.pack入力不足で停止。
既存typed orchestrationと同じmedia.inspect記録へ修正後、
/data1tb/mf-game-static-source-20260909-r2 はBlender4.5.9、1.677秒passed/exit0。
/data1tb/mf-game-static-source-4.5.13-20260909 は既存managed4.5.13を専用registryへ登録、
1.190秒passed/exit0。稼働環境のregistry/active版は変更していない。

両方で左右支柱/梁を制作・後続transform編集し旧source hash不変。
実Blender inspectorでdata独立性（copy vertex変更が元に影響しない）、
材質slot独立性、mirror参照保持、評価済み60 triangles/X境界±1.2mをassert。
独立GLB JSONも3 mesh nodes/60 triangles、6,864 B、
SHA5d486108fbfb77b50638533d50e904aa6b214aa152393a18e33280cef1d57132で両runtime一致。
新旧4 Assetの実hash/provenance対応も確認。実Blender/domain受入でありinstalled MCPではない。
新14 testsでstrict入力、schema3種、ID重複、geometry予算、runtime有無とcapability対応を検証。
初回全テストは未導入fixtureが既存legacyを検出して1 failed/1220 passed。
未導入resolveを明示fixture化してfocused14件/contractとの34件はPASS。
最終全 `./mf.sh test`:1221 passed/既知warning2/139.10秒、exit0。
frontend build:viewer/node --check/diff check成功、viewer生成物差分なし。
稼働Blender registryは0.28.45更新前backupとのbyte一致を再確認。

installedは0.28.45のままで、この新2操作は未配布。
GA-0の実director読込、GA-1全体、installed MCP/engine import/署名配布はNOT TESTED。
次は本sliceの通常merge後、署名版を導入して実スキル→MCPでこの操作を受入し、
array/Boolean/mesh編集と後続工程を計画の依存順で拡張する。

## 2026-09-09 installed authorization expiry and scope extension

PR #358 merge b71291fからux1/3d-expiry-edit-recovery。
既存診断へauth-expiryを追加。実Host opaque browserで専用sceneを1→2 meshesへ複製、
製品120秒autosaveの成功後にviewだけ閉じる。Host診断環境で同ownerの正規署名service token
TTL20秒を発行し、installed coreのRFB endpointへ接続（Host proxy経由とは区別）。
実RFB banner後30.031秒で4403/host service token expired、30.309秒でhost_revoked。
秘密tokenは出力・保存なし。実行:
`scripts/3ds_save_conflict_cleanup_installed_e2e.py --scene-id
scene_3f3b5f1e97e94b268722ea45cc811c50 --expected-version 0.28.45
--failure-kind auth-expiry --evidence-dir /data1tb/mf-expiry-edit-installed-20260909`。
passed=true/exit0、session blendersession_f6aa41d5d50545c8a6409f2c7f4b2547。
全PID808034/808038/808081・cgroup/root/socket消滅、元scene/旧版hash不変。
468,914 B/SHA4d4a6b4493fbdc9f4f04dd307da9f3ae5dda872600de25bb6c012d6ecec77bdfの
候補からscene_971a177ed6725ec2b4fcdde225793ba4へ通常fork、source hash一致/検証2 meshes。

重要: autosave後にも複製キーを送ったがpost-autosave-edit.pngのoutlinerは2 objectsのまま。
raw observationsのrecovery_boundaryにある「post-autosave duplicate not retained」は
過剰な結論なので採用しない。診断の記録文言をinput effect not assertedへ修正した。
直前autosaveの回収は証明したが、その後の実編集の損失量はNOT TESTED。
不正session/user入力をHost import/発行前に拒否する3 tests追加、
全 `./mf.sh test`:1207 passed/既知warning2/140.97秒、exit0。

利用者からゲーム制作に必要な機能全体の設計・実装開始を追加依頼された。
次はbase-plan/統合設計にゲーム用asset制作拡張を追加し、MCP型付き操作を段階拡張する。
エンジン未指定の間はGLB/glTF基準。既存3DSのidle/restart等の残件は削除しない。

## 2026-09-09 installed autosave failure, retry and crash recovery

PR #357 merge `0fc4b0dc6e6fad3fb92064ee55885008f6b8a2ad`から
branch ux1/3d-autosave-installed。既存専用GUI診断へ--failure-kind autosave-crashを追加。
専用mf-e2e scene、稼働GUI不在、installed版/healthを検査し、Blender4.5.13をassert。
実RFB canvasのA/Shift+D/Escapeで1→2 meshesへ編集し、保存前working hashと正式版不変を確認。
自分のworking directoryだけを0500にするcontext managerは正常/例外時に元modeへ戻し、
symlink/別rootを拒否する追加3 testsを持つ。既存利用者設定へ書き込まない。

Host診断Pythonで
`scripts/3ds_save_conflict_cleanup_installed_e2e.py
--scene-id scene_3f3b5f1e97e94b268722ea45cc811c50 --expected-version 0.28.45
--failure-kind autosave-crash --evidence-dir /data1tb/mf-autosave-installed-20260909`
を実行しpassed=true/exit0。実Host opaque iframe/Chrome/installed4.5.13 software GUIを使用。
session blendersession_df3a4b3cfad74d4ebcb3d3165b3b1651。
製品120秒timerは変更せず15秒間隔poll。編集後の観測開始から125.090秒で
保存失敗/旧bytes保持と日英警告、230.111秒で次の保存成功/警告解除/接続維持を確認。
日英はブラウザnavigator.language+languagechangeのfixture入力を正規Host bridgeで配信。
製品文言/stateの差替えや永続language設定変更ではない。日英screenshotも保持。

開始時PID800905/800909/800963のうち、executable/cgroup/pidfdで確認した
Blender800963だけをSIGKILL。3.458秒でrunner_lost、
3 PID/cgroup/root/socket消滅、active GUI0、working directoryは0700へ復元。
468,914 Bの候補SHA256
`9fabe0194f2d29aa33ba69b7d2b5967e54752280a00983276865cca1c420fe86`を保持。
正規recovery.forkでscene_1ad63290d7805fa9ac71ab6420eef70fの初版
revision_5fde7d0aa3c248f38df6955638701eadへ確定しsource hash一致。
実Blender検証2 meshes、独立read-only GLB JSONも元1→復旧2 mesh node。
復旧GLB3,272 B/SHA224d9e0fb77c2835aaf514c86d046f262c3c5bdb96a790d8c674b5bb3f955c35。
元scene第6版の全投影/旧revision source・GLB hashは不変、候補・復旧sceneを保持する。
page errors0、専用Host loginはfinallyでrevoke。Host667000/MF798514/798518は不変。

全 `./mf.sh test`: 1204 passed/既知deprecation warning2/139.51秒、exit0。
診断py_compile/diff check成功。製品codeや版番号は変更せず、診断/受入文書だけを追加。
これはinstalled自動保存の失敗→再試行→crash回収の受入。
保存途中のkill、電源断、次autosaveより後の編集量、GPU lease、connected idleはNOT TESTED。
C/GOAL-09全体はPARTIAL。次はidle/expiry/restartの未保存手編集回収量と全process回収の不足証拠を補う。

## 2026-09-09 v0.28.45 signed release and installed update

PR #356 merge `02bb6681bac6dd91fd0b234cd9c64fca9e2da7ad`を固定して
別detached worktreeでbundle構築、既存publisher keyで署名しv0.28.45を公開。
公開先から再取得した4ファイルはbuild出力とbyte一致、Host trusted publisher検証もPASS。
artifact 31,553,471 B、SHA256
`acf6573c0e1adfff5d5c068ed13c25670d35d43071226a41fad4c08cee700464`。
packaged doctorはstatus=ok/version=0.28.45/packaged=true。
これはCLI検証でありGUI受入ではない。

稼働Job/GUIが0件であることをDBで確認し、0700の専用backup
`/data1tb/mf-0.28.45-update-ho4q51ys`へSQLite backupとruntime registryを0600で保存。
Host診断環境から既存release_bundle.installをtag固定specで実行し、
0.28.44→0.28.45が11.444秒で成功。グローバルcatalogは変更していない。
最初のread-only事前確認はGUI table名の誤記で停止、実schemaの
blender_web_sessionsへ修正後に再確認した。失敗した確認では更新を開始していない。

全15 tableの旧行multisetと件数が更新後も一致（Job779/Asset650/scene36/revision142/
GUI30等）。Blender runtime registryのbytesも不変。
証拠はbackup内observations.json。そこでhealthy keyは存在せずnullだったため、
追加のregistry.statusで正しいhealth=healthyを確認し、実health HTTP200/status=healthyもassert。
enabled/requested_enabled=true、currentはversions/0.28.45、
実core PID798514/798518。Host PID667000は不変。直前0.28.44 bundleを保持。
標準の2世代保持で0.28.43実行bundleは削除され、公開releaseから再取得可能。
制作データ・Blender実体・利用者global設定の削除なし。

このsliceは署名配布/標準updateの受入記録で、source自動保存受入はPR #355の証拠。
installed4.5.13の日英警告/再試行/クラッシュ回収はNOT TESTED、次sliceで実施する。
clean installed Host/故障rollback/残るGOAL・A〜Fは引き続きPARTIAL。
全テストはrelease準備commitの1201 passed/138.10秒を参照し、本docs-only sliceで再実行とはしない。

## 2026-09-09 v0.28.45 release preparation

PR #355 merge `77be1f1805ab068823374276a6dbb2dd25166580`から
branch `ux1/3d-release-0.28.45`。core/addonの版を0.28.45へ揃え、
release noteに自動保存の内容・限界・0.28.44との保存形式互換性を記載した。
全 `./mf.sh test`: 1201 passed/既知warning2/138.10秒、exit0。
core/addon版一致を実コードからassert。署名bundle生成/公開/consumer検証/標準updateは未実施。
次はこのPRのmerge commitを固定してbuildし、既存publisher keyで署名・再取得検証する。
installed4.5.13/日英受入と3DS残件は維持。既存の制作データ・runtime/global設定は不変。

## 2026-09-09 autosave integration with current main

保存済みのsource受入変更をcommit `906e390`へ確定し、最新main
`7b739bc`（PR #354、0.28.44）をmerge commit `c27ac31`で取り込んだ。
追加された画像透過/参照入力等を保持し、競合なし。全 `./mf.sh test`は
1201 passed/既知deprecation warning2/140.06秒、exit0。
node --check、npm run build:viewer、git diff --check成功、viewer生成物差分なし。
先行9月7日のsource実機証拠は保持。main統合後のGUI再実行とは読み替えない。

現行Host registry.statusのread-only確認はMediaForge0.28.44、enabled/requested_enabled=true、
health=healthy。current symlinkはversions/0.28.44、実core PID501057/501062、
Host control-deck-web.serviceはactive/PID667000。9月7日の0.28.38/PID記録は歴史的証拠。
自動保存の新codeはまだinstalled版へ配布していない。次は通常PR merge後に
未使用の新しい版番号で署名release/consumer検証/標準updateとinstalled日英受入を進める。
Host checkoutはmain ahead1で、変更・restartしていない。無関係な .venv symlinkも保持。

## 2026-09-07 GUI periodic autosave (source candidate)

PR #348 merge `69d04d9d84eea27669a1dbba98047a047e958f31`から
branch `ux1/3d-autosave`。runtime/Web設計§7の120秒autosaveをBlender側timerに実装。
隔離working copy内の一時directoryへcopy保存（relative_remap=false/compress=false）し、
FINISHED/header/fsync後にscene.blendをatomic replace。旧candidateを保存途中に上書きしない。
正式revision/Asset確定は行わず、既存の独立検証・明示保存/forkを維持する。
製品の通常save commandも同じsnapshot関数へ統一。Blender標準の一時autosave設定は
session内だけ無効化し、利用者のpreferencesを保存しない。

失敗statusをcoreがasyncio.to_threadで読む。readyは保持し、GUI dialog/scene欄に日英警告、
次の成功で解除。180秒を超える通知欠落/停止も警告し、結果不明を成功扱いしない。
通知/heartbeat書込失敗は静的診断を出してtimerを継続、次intervalで再試行する。
modal操作等でBlender timerが遅れるため120秒は目標であり上限保証ではない。
追加10 testsで境界120秒、copy/atomic置換、書込失敗/CANCELLED/header不正/replace失敗時の
旧bytes保持と再試行、警告/解除、遅いstatus読取中のevent loop応答、
symlink/identity不正、stale/missing通知、通知書込失敗後のtimer継続を検証。
最終全 `./mf.sh test`: 1145 passed/既知warning1/160.55秒、exit0。
`npm run build:viewer`成功（生成物差分なし）、node --check、py_compile/diff check成功。

新診断 `scripts/3ds_autosave_source_e2e.py`は専用data rootのsource HTTP/WS/GUIを使う。
既存4.5.9とWeb packを参照するだけで、導入更新操作やHost再起動は行わない。
最初のserverはPYTHONPATHにrepo rootがなくimport失敗、終端確認後に修正して起動。
最初のbrowserはstandalone session一覧refresh不足で接続待ちtimeout、owned sessionをstop。
API ready後に正規refreshSessionを呼ぶ修正後、
/data1tb/mf-autosave-crash-evidence-20260907-r2 は133.117秒passed。
実RFBでCube複製後、130.310秒時点で468,914 Bのautosaveを観測（15秒間隔poll）。
SHA b214cab95c6c7856e9a7f9ecb0247f7abb715d15fd7182055c313231cee3843c。
自分のBlender子だけをpidfd/executable/cgroup確認後にkill、runner_lost後に候補を通常fork。
新source hash一致・復旧2 meshes・元sceneの確定版不変・process/cgroup/root消滅をassert。
これは先行source試験。最終試験は以下の別sessionで行った。

最終sourceサーバは新root /data1tb/mf-autosave-source-final-20260907、
unit mf-autosave-source-final-20260907（RuntimeMax600秒）。初回final browserは日本語警告を
英語だけでassertして停止した。日本語警告の実画面と旧bytes保持は確認済みだが、
そのrunを再試行成功とはしない。owned GUI終了とdirectory権限復元をfinallyで確認。
診断を日英文言の実測記録へ修正し、同じ稼働serverで別sessionを開始。
--fail-first-autosave --data-dir /data1tb/mf-autosave-source-final-20260907
--evidence-dir /data1tb/mf-autosave-crash-evidence-final-20260907-r2 は258.512秒passed/exit0。

最終session blendersession_2236254f00744fdbbdf4dd30042bbd68。
実RFBでCube1→2へ複製、保存前hash/正式版不変。
自分のworking directoryだけを一時0500にして実書込拒否を起こし、135.054秒時点で
autosave ok=false、旧bytes不変、正規refreshSession後に日本語のdialog警告を確認。
元のdirectory modeへ戻し、255.184秒時点で次の120秒intervalの保存成功と警告解除。
自動保存468,914 B、SHA8ef2f2daec61db391777be5bceb2d9b9bc14bd3b365f7556215c9fd5ac17fe87。
これは15秒pollの観測時刻で、timerの正確な実行時刻/最大遅延保証ではない。

実在したPID996734/996738/996785のうちBlender996785だけを
pidfd取得後の実行ファイル/cgroup再確認でSIGKILL。
runner_lost後に全3 PID/cgroup/session root消滅、候補hash不変をassert。
通常fork先scene_a3718b63246c5c1a91824ca692ce56acの初版sourceと候補hash一致、
実Blender検証2 meshes、元sceneの確定版不変。追加read-only実GLB解析も2 mesh node、
3,272 B/SHA224d9e0fb77c2835aaf514c86d046f262c3c5bdb96a790d8c674b5bb3f955c35、
provenance sidecar/DB一致。page errors0、active GUI0。元source/候補/復旧sceneは保持。
最終source unitは明示stopしinactive/MainPID0。Host849052/MF905518/905522はPID不変。
source /healthは環境marker不在のsetup_requiredでありhealthyと記録しない。
日本語警告を実機確認。英語警告/installed4.5.13/強制終了が保存途中に重なる場合/
電源断/次autosave前の変更回収量はNOT TESTED。署名配布・installed受入は次slice。

署名installed版は0.28.38のままで、新autosaveはまだ配布していない。
source受入完了後、通常PRをマージし、次の署名release/標準update/installed受入へ進む。
C/GOAL-09/全3DS完了とはしない。

## 2026-09-07 unsaved GUI edit retained on save conflict

PR #347 merge `9758cb581c4756b89493baf58a8a87e91f44796d`から
branch `ux1/3d-unsaved-recovery`。既存診断
`scripts/3ds_save_conflict_cleanup_installed_e2e.py`へ--manual-editを追加。
save-conflictだけで許可し、他modeとの組合せは引数段階で拒否する。
Host診断Pythonで--scene-id scene_3f3b5f1e97e94b268722ea45cc811c50
--expected-version 0.28.38 --manual-edit
--evidence-dir /data1tb/mf-unsaved-save-conflict-installed-20260907 を実行、passed=true/exit0。

実Host opaque frameで正規GUI start、Blender描画を確認してcanvas click/A/Shift+D/Escape。
元第5版の2 meshesを複製し、保存要求前のworking scene.blend hashと確定sceneは不変。
この段階ではGUIメモリ内の編集であり、新revisionやworking fileへの保存はしていない。
通常revision restore APIで同専用sceneの第6版（1 mesh）を先に確定して競合を作る。
正規blender.sessions.save APIは実Blender保存後にscene_revision_conflict、5.037秒でfailed。

session blendersession_0a1a24fa5ce247678d5bb2a16b1c8f7e、開始時PID980386/980390/980439。
failed後のprocess/cgroup/root/socket消滅、元scene第6版全投影不変をassert。
480,198 Bの未検証候補、SHA757fbbda9e75337ba4675946c4480dd910bb8bb08637a90445b20a90acdbbf92を
正規recovery.forkで別scene_23451e30760d594399312c56c2380789の初版へ確定。
新sourceと候補hash一致、復旧先は実Blender検証4 meshes、元の5版JSONとsource/GLB hash不変。
追加のread-only実GLB JSON検査も元2 node/競合側1 node/復旧先4 nodeと一致。
復旧GLB asset_c097bda35acf4ecdb51c24588261fed1、5,968 B、
SHA4bf808b729a8fe9f06ebf61106cbb89807accfcabf505242d853d131bcdc32fb。
確認対象GLBのprovenance sidecar/DB一致。active GUI0、開始時3 PID不在、
Host849052/MF905518/905522はPID不変。元第6版・復旧scene・候補は保持する。

この故障では追加した2 meshesを全て回収できた。保存API以前にBlender自体が落ちた場合の
メモリ内容の回収やautosaveの成功へ読み替えない。runtime/Web設計§7の2分autosaveは
未実装と明記され、gui_session_bootstrap.pyもsave command時の保存だけであることを確認。
次の実装sliceで隔離working copyへの定期autosaveと故障後回収を扱う。
C/GOAL-09全体はPARTIAL。service restart/runtime/global設定変更なし。
全 `./mf.sh test`: 1135 passed/既知warning1/167.73秒、exit0。
診断py_compile/diff check成功、終端unit not-found/inactive/MainPID0。

## 2026-09-07 installed native background return

PR #346 merge `19924bee14f80ec04d6be7427ca1da117ad62e8b`から
branch `ux1/3d-background-return`。新診断
`scripts/3ds_background_return_installed_e2e.py --scene-id
scene_3f3b5f1e97e94b268722ea45cc811c50 --expected-version 0.28.38
--evidence-dir /data1tb/mf-background-return-installed-20260907-native`をHost診断Pythonで実行。
専用mf-e2e scene名・既存GUI不在を検査し、正規Host opaque WSで実software Blenderを起動。
scene選択とGUI開始は製品helper/正規API、複製・保存は実canvas入力/通常button。

初回 /data1tb/mf-background-return-installed-20260907 はGUI描画後にhidden待ちtimeout。
自分のsessionだけを通常stopし32.631秒でlogin revoke、保存版追加なし。
空白2 tabでも同じ現象を再現し、ローカルPlaywright coreBundle.jsの既定
Emulation.setFocusEmulationEnabled=trueを確認。追加CDP sessionのfalse指定だけでは
両tab visibleのまま。通常Chromeを専用一時profileで起動して
connect_over_cdp(no_defaults=True)で接続すると実hidden→visibleがPASS。
最終診断はこの方式。visibilityの偽装や製品code overlayは行わない。
一時profileは終了時に削除し、既存利用者profileへ書かない。

最終session blendersession_72e2174a37de48baa613279889aef914。
実frameの色数1091を確認後、別の実tabへ切替。opaque frameのvisibility記録は
visible at24256.600→hidden at28277.600→visible at43327.100 ms、背景15.0495秒。
同session ready/connected・描画503色へ復帰し、canvas click/A/Shift+D/Escape後に
通常Save new revision and finish。74.438秒でpassed、74.568秒で専用login revoke、exit0。
第4版→第5版、実Blender検証mesh1→2、全旧revision JSONとsource/GLB bytes SHA不変。
返却画面screenshotはBlender描画の証拠で、複製オブジェクトの見た目の差は主張しない。

追加read-only DB/実ファイル照合: GLB JSONのmesh参照nodeも1→2。
新source468,914 B/SHA17a719fa6e140c6400a7993c407f8bbcfca6744a86ffa0d91aeee2de206ae2c3、
新GLB3,272 B/SHA224d9e0fb77c2835aaf514c86d046f262c3c5bdb96a790d8c674b5bb3f955c35。
新revision revision_d37a3ad9b42c4298a53ffd1a0235bfe5、source/preview provenance sidecarとDB一致。
session stopped、active GUI0、Host849052/MF905518/905522のPID不変。
新第5版は保持。サービス再起動・runtime/global設定変更なし。
診断browserの正常/例外時cleanupとno_defaults指定を追加2 testsで確認。
これは短時間のdesktop背景復帰/実入力保存の受入。OS suspend、mobile背景、
未保存手編集の故障後回収量、GPU lease、C/GOAL-09全体の完了とはしない。
次は未保存編集の回収候補と確定版の内容差を実測する。
全 `./mf.sh test`: 1135 passed/既知warning1/156.05秒、exit0。
診断py_compile/diff check成功。終端unitはnot-found/inactive/MainPID0。

## 2026-09-07 lifecycle evidence mapping

PR #345 merge `ddfd37ccaa34f9f207f00faa14dd296ffd882ad3`から
branch `ux1/3d-lifecycle-evidence-map`。設計PR #213のmerged状態とorigin/mainを再確認。
[原因別証拠表](implementation/3ds-lifecycle-evidence.md)にscenario Cの全項目を分離した。
8 raw observationsのread-only監査は
`/data1tb/mf-lifecycle-evidence-audit-20260907/observations.json`、passed=true。
9 revision JSONと現在DB、21 Asset/24,128,377 BのSHA/size/provenanceを照合済み。
再開後のPython sqlite mode=ro検査も全21実ファイルhash/size/sidecarと9版ID存在がPASS。
`.30` raw eventsはheld_sec480.340でconnections2、660.433までconnected、
671.862秒でsame_session/gui_edit_saved=true、672.072秒で診断login revokeを記録。

`.14-long`の入力/版増加だけでは形状変更を証明できないため、GOAL-04の編集証拠を
成功した`.28-gui-canvas`の4→8 meshes/保存第7版/復元第8版へ修正した。
機能を撤回したのではなく、対応する実測証拠を明確化した。
C/GOAL-09はPARTIAL。次は実background hidden→visibleと手編集保存、
その後に未保存編集の回収量を専用sceneで実測する。既存の故障試験を一律に繰り返さない。
本sliceは文書のみ。service restart、runtime/global設定、制作データへの書込はなし。
全 `./mf.sh test`: 1133 passed/既知warning1/157.84秒、exit0。
新規相対リンクの実在確認とgit diff --checkはPASS。アプリ/GPU実機の再試験ではない。

## 2026-09-07 installed default disconnect grace acceptance

PR #344 merge `7602b678c1719588ca66c2452a5ad4f662096717`から
branch `ux1/3d-disconnect-grace-cleanup`。既存GUI診断へ
--failure-kind disconnect-timeoutを追加。設定は既定disconnect_grace_sec=300のまま。
`scripts/3ds_save_conflict_cleanup_installed_e2e.py --scene-id
scene_3f3b5f1e97e94b268722ea45cc811c50 --expected-version 0.28.38
--failure-kind disconnect-timeout --evidence-dir /data1tb/mf-disconnect-grace-cleanup-installed-20260907`
をHost診断Pythonで実行。正規WS startで実software Blender4.5.13/Web pack1.0.0がready。
製品openBlenderViewで実noVNC/RFB接続し、Connected表示とserver connected_at非nullを確認。
通常「Close view only」buttonで切断し、設定を変更せず自然なtimeoutを待つ。

初回session blendersession_7c12f9d7ebe24b4c9d8d5c2388284b05は302.161秒で
blender_session_disconnected_timeout/保存なしの終端へ遷移、passed=true/exit0。
猶予中の120秒時点でunit active、durable working/session参照は各1（recipe/unresolved0）。
終端後は開始時PID948243/948247/948290、cgroup/session root/socket不在をassert。
450,236 B候補を通常forkでscene_d9fa6891e745506b9cc51d763317bd00の初版へ確定、
元候補・新source SHA70665510ca9742db744858ce63b3b9092cb93e9569281bca1745ff157d2d945f一致、
元scene第4版全投影不変。これは手編集後の未保存内容を測った試験ではない。

初回の切断待機predicateは過渡状態のconnected_at残存を受理したため、
最終診断ではdisconnected_at非nullかつconnected_at=nullを要求し、接続時刻も証拠へ保存する。
同一セッションの安定した切断DB状態もread-onlyで確認した。初回の終端後にだけ、
最終scriptを別証拠 /data1tb/mf-disconnect-grace-cleanup-installed-20260907-final で再実行。
最終session blendersession_757826b8b90844b3a722354b62ca3cebは302.270秒で
disconnected_timeout終端、passed=true/exit0。接続16:05:13.759959Z、切断16:05:29.521742Z。
PID957403/957407/957504とcgroup/root/socket消滅、同450,236 B/hashの候補を
scene_cff2a7987e16544390190af4a90f097fの初版へ確定。元scene/候補bytes不変。
終了後のdurable recipe/working/session/unresolved参照は全0。
Host849052 active/MF905518/905522はPID不変。初回・最終とも通常timeoutだけで終了した。

製品code/runtime/global設定は変更せず、シグナル・service restartも行わない。
GUI描画品質/手入力/connected idle 1800秒/GPU leaseは未検証。Connected直後の
初回screenshotは空画面だったため、接続証拠を描画完了や編集成功の証拠にはしない。
既存本番sceneは検証専用の同sceneだけを読む。復旧forkの新scene/候補は保持する。
全 `./mf.sh test`: 1133 passed/既知warning1/159.78秒、exit0。
最終script py_compile/diff check成功。C/GOAL-09全体はPARTIALを維持する。
次は既存ライフサイクル証拠を原因ごとの監査表へ整理して残件を特定する。

## 2026-09-07 installed Blender child crash cleanup

PR #343 merge `9cbe729241460cc3b3da607fca4509dedffa363c`から
branch `ux1/3d-gui-child-crash-cleanup`。既存GUI診断へ明示
--failure-kind blender-crashを追加（既定save-conflictを維持）。
`scripts/3ds_save_conflict_cleanup_installed_e2e.py --scene-id
scene_3f3b5f1e97e94b268722ea45cc811c50 --expected-version 0.28.38
--failure-kind blender-crash --evidence-dir /data1tb/mf-gui-child-crash-cleanup-installed-20260907`
をHost診断Pythonで実行、passed=true/exit0。

自分で新規起動したsession blendersession_af9c9b2b932f48088eba5023ede344faの
unit mediaforge-blender-af9c9b2b932f48088eba5023ede344fa.serviceをIDで照合。
ready時のcgroup.procsは938854/938858/938903。
Blender実行ファイルの候補が1件だけであることを調べ、PID fdを開いてから
実行ファイルが同managed runtime配下であることと同cgroup所属を再確認し、
PID938903のfdだけへSIGKILLを送った。unit全体やHost/core/他Blenderへsignalしない。
PID再利用による誤対象化を防ぐため、送信はpidfd_send_signalを使用する。

実製品がblender_session_runner_lostとして5.266秒でfailed/saved=falseへ遷移。
ready時に実在した3 PID/cgroup/session root/RFB socketが終端応答後に全て不在。
元scene第4版の全投影は不変。復旧candidate450,236 B、
SHA70665510ca9742db744858ce63b3b9092cb93e9569281bca1745ff157d2d945fを保持。
通常scenes.recovery.forkで別scene_4538f2f3d6f65d548682f35a2c34aac0へ検証済み初版を確定し、
新source実bytesと候補hash一致、元候補bytes/元scene不変をassert。page errors0。
GUIへの手入力やRFB接続はなく、未保存手編集量の復旧範囲を測ったとはしない。

終了後read-only実行参照（recipe_jobs/working_copies/sessions/unresolved_sessions）は全て0。
Host849052 active/MF905518/905522はPID不変、service restart/runtime/global設定変更なし。
新sceneと復旧候補は保持し、専用login sessionだけfinally revoke。
診断helperの追加4 testsは対象一致時だけfdへsignalし、外部runtime・cgroup不一致・複数候補では
signal0/開いたfd解放を検証する。Playwright importをmain内へ移してcore testの依存を増やさない。
本番codeは変更せず、batch worker crash/GPU lease/idle/RFB入力の受入へ広げない。
GOAL-09/C/3DS-8全体はPARTIAL。次は残る終端原因・資源予約の証拠を照合する。
最終script py_compile/diff check成功。
全 `./mf.sh test`: 1133 passed/既知warning1/162.99秒、exit0。

## 2026-09-07 installed GUI save conflict cleanup and recovery fork

PR #342 merge `ed1329a2f629dbbec854f6a5cd0f4e303f58b0eb`から
branch `ux1/3d-save-conflict-cleanup`。新診断
`scripts/3ds_save_conflict_cleanup_installed_e2e.py --expected-version 0.28.38
--scene-id scene_3f3b5f1e97e94b268722ea45cc811c50
--evidence-dir /data1tb/mf-save-conflict-cleanup-installed-20260907`をHost診断Pythonで実行。
専用mf-e2e material conflict scene/name/版数と他GUI不在を確認。
実Host opaque iframeの正規WSからsoftware GUIを開始し、実Blender4.5.13/Web pack1.0.0がready。
RFB接続や手編集はこのrunでは行わない。APIでstart/save/restore/forkを呼ぶ試験と明示する。

session blendersession_b4162ff56714489b960e4e59c4515c65、
unit mediaforge-blender-b4162ff56714489b960e4e59c4515c65.service。
ready時のcgroup.procsでPID929922/929926/929968、session rootとRFB Unix socketの実在を確認。
GUIが第3版を基準に保持中、同じ専用sceneを通常revision restoreで第4版へ進め、
正規blender.sessions.saveを送信。実Blender保存後のcommitがscene_revision_conflictで拒否、
5.831秒でfailed/saved=false。復旧候補を返し、先に確定した第4版を上書きしない。

failed応答後、上記3 PIDの/proc不在、cgroup/session root/socketの不在をassert。
core/Hostや他unitへsignal・stop・restartを送らない。停止は製品自身の通常保存失敗cleanup。
候補scene.blendは515,342 B、
SHA287f28c7be443f21413d1dec20f4ecbd08f7844d86567a660f0c2634e45cc12f。
正規scenes.recovery.forkで別scene_a5204dc326e95bb5ab9938e7e0f71827の初版へ確定し、
新sourceの実bytes hashが候補と一致。元候補bytesと元scene第4版全投影は不変。
未検証候補の保持だけで復旧成功とせず、別sceneへの検証済み確定まで確認した。
新scene/元scene第4版/復旧候補を検証物として保持。page errors0、passed=true/exit0。

終了後read-only Store.active_scene_runtime_references(4.5.13)は
recipe_jobs/working_copies/sessions/unresolved_sessions全て0。
全GUI24件終端、working copy active0。Host849052/MF905518/905522はPID不変・稼働。
専用login sessionだけfinally revoke、既存password/global設定/runtime実体は不変。
本runはsoftware GUI保存競合とprocess/参照解放・復旧確定の証拠。
RFB入力、worker crash、idle、GPU leaseの証拠には広げず、GOAL-09/C全matrixはPARTIAL。
最終script py_compile/diff check成功。
全 `./mf.sh test`: 1129 passed/既知warning1/158.02秒、exit0。
次はC/GOAL-09の他終端原因を対応する実機証拠へ紐付け、不足を実測する。

## 2026-09-07 installed stale material conflict and retry

PR #341 merge `90b32055f4c7e0364528df80a4e8c557fd4f76ac`から
branch `ux1/3d-material-conflict-installed`。新診断
`scripts/3ds_material_conflict_installed_e2e.py`をHost診断Pythonで実行。
--expected-version 0.28.38、--blendは既存専用cube fixture、--imageは過去の
実生成PNG /data1tb/mf-no-blender-image-0.28.33-20260906/generated.png。
専用mf-e2eの新規sceneへ通常UIでimportし、同PNGを通常assets.import。
別の実Host opaque tabから正規scenes.material.applyで第2版を確定する。

初回jaは既存open_scene helperが折り畳まれた一覧buttonのvisibleを待ちtimeout。
scene_0d1d0c1a18a84c479f67ce47377b6397/初版とimport画像は保持。
-r2は別タブ更新後のfocus refreshで最新headが反映され、古いformのbuttonがdisabled。
これは保護動作であり、worker失敗や競合表示の成功ではない。
scene_108541c7553e4867bbb4ea191dba58ae/2版を保持。各runの終端後に診断を修正した。

最終診断は最新sceneを取得・通常selectで対象と同画像を再選択したうえで、
保存した旧bindingを製品compareMaterialCandidateへ直接渡す。
実Host/MediaForge WSはscene_revision_conflict
（material source revision is no longer current）を返す。
失敗要求の入口は比較helper直接呼び出しであり、通常buttonから旧版を送信できたとはしない。
HTTP/WS応答・worker・frontend codeはmock/overlayしない。旧版拒否はworker起動前の検査で、
worker crash/Agent retry_job_idの証拠には読み替えない。

--locale ja: /data1tb/mf-material-conflict-installed-ja-20260907-r3、
scene_0bcfede227a24869880c1d2754dd2ba1、passed=true/exit0。
--locale en: /data1tb/mf-material-conflict-installed-en-20260907、
scene_3f3b5f1e97e94b268722ea45cc811c50、passed=true/exit0。
実native desktop Chrome/opaque origin null、日英の両pane終端文言・採用無効、
失敗前後のscene投影/元imageと2版source/GLB bytes SHA不変をassert。
閉じる→scene再読込後のobject/image/slot/channel/UV選択保持、
通常「割り当てて比較」button→実Blender候補2pane描画→明示採用で第3版。
採用前head不変、以前の2版不変、同じ画像ID/hash依存、元Asset bytes不変、
既存全scene/revision value_json不変、page errors0。日英のlocaleはbrowser context入力。
日本語conflict.pngを目視確認。新scene/画像/版は検証物として保持する。

追加read-only照合: release前snapshotの既存460 Job全列不変、
本turn追加13 Jobは全てmedia.inspectで画像生成/編集0。終了時Job473全終端、
working copy active0、material-previews配下0。Host849052/MF905518/905522はPID不変、
service restart/runtime/global設定変更なし。専用login sessionのみfinally revoke。
全 `./mf.sh test`: 1129 passed/既知warning1/159.84秒。最終script py_compile/diff check成功。

installed版競合の表示と成功画像再利用は確認した。worker失敗、Agent retry_job_id、
mobile touch、新画像生成、全GOAL-07/3DS-8 matrixの未確認条件は維持する。
次は残るライフサイクル/資源解放受入の実測を監査表に沿って進める。

## 2026-09-07 v0.28.38 signed bundle and standard update

PR #340 merge/tag target `3832e6fb3483e9f9dda75cdc0975fdd2f96f3570`。
exact detached /data1tb/ControlDeckMediaForge-release-0.28.38で
`python3 scripts/build_release_bundle.py --version 0.28.38
--output-dir /data1tb/mf-0.28.38-build-20260907
--pyinstaller /data1tb/ControlDeckMediaForge-3ds4/runtimes/bundle-build/.venv/bin/pyinstaller`。
PyInstaller6.22.0/Python3.12.3、約21秒/exit0。
artifact31,516,530 B、SHA a4921fd964f638cc4c90e2e7b2196cf934af43dbe7fe5a34500f757fef2ae527。
展開先 /data1tb/mf-0.28.38-package-2xhjl09u/control-deck-media-forge-0.28.38-linux-x86_64。
archive6 entries/embedded199、safe paths/types、秘密鍵・venv・モデル重み・制作物なし。
runtimesはrequirements.txtだけ、embedded frontend/app.jsはexact source bytesと一致。
core31,778,136 B/SHA5996db3bb5e7c7904cf15d4d0034850192987890d7c5ed68e90a2e6c99b98cbd。
addon/feature版一致、専用feature data環境を指定したpackaged doctorは
status=ok/version0.28.38/packaged=true/exit0。

新規専用fixture /data1tb/mf-library-paging-bundle-0.28.38-20260907をseedし、
mf-library-02838-acceptance/9163でpackageを実起動。
healthは環境snapshot不在のsetup_requiredで、healthyとは扱わない。
`3ds_library_paging_e2e.py browser --server-kind bundle --evidence-dir`同rootは
実Chrome日英320で60/60→5/3→先頭復元、全128 ID一意・全集合、
横overflowなし/errors0/exit0。synthetic lineageのstandalone bundle試験。
終了後にexact owned unitだけstopしinactive確認。

既存publisher key（mode0600）で標準sign_release.py sign・自己検証。
GitHub v0.28.38の4 assetsを公開し、consumer
/data1tb/mf-0.28.38-public-20260907へ再取得。sha256sum -c OK/buildとcmp一致、
tag exact commit一致。Host trusted publisherの_verify_signed_releaseでも
version0.28.38/hash/sizeを照合。鍵内容の出力・global設定変更なし。

直前に本番Job460/GUI23全終端、active working0、runtime操作5 ready/model操作0を確認。
snapshot /data1tb/mf-0.28.38-pre-update-20260907（directory0700/files0600、
DB2,822,144 B/integrity ok、registry SHA
dd43b2e8b6897c9671958c3b4cc2f57dca82969a5d1d8492909761e86636741a）。
snapshotと本番8テーブル全行一致・registry bytes一致を更新直前に再検査。
正規registry.update('media-forge')が14.189秒で0.28.37→0.28.38、
healthy/enabled/requested_enabled=true、exit0。
更新後もassets/scene_documents/scene_revisions/blender_web_sessions/jobs/
scene_working_copies/blender_runtime_operations/model_operations全行不変、registry bytes不変。
current→versions/0.28.38、installed core hashはpackage一致。
Host PID849052 active/再起動なし。MFの新core process905518/905522を確認。

installed `3ds_library_locale_installed_e2e.py --expected-version 0.28.38`を
既存real63-child fixtureで--width 320/1280の順に実行、双方exit0。
証拠 /data1tb/mf-library-real-paging-installed-0.28.38-{320,1280}-20260907。
実Host opaque iframeで60→3→60→3、63 ID一意・全集合、offset60の日英通知[ja,en]、
source/filter/関連列/scene/load/session保持、横overflow0/page errors0、scene投影不変。
言語入力だけfixture、Host通知と素材応答は実経路。新規制作Jobは投入しない。
終了時Host849052 active、MF905518/905522は生存。素材失敗受入には読み替えない。

製品全gateは版準備で1129 passed/既知warning1/150.44秒、viewer build差分なし。
本追記は配布実測docsのみ。導入済みの素材失敗表示・再試行受入、全GOAL/scenario matrixは
引き続きPARTIAL。次はinstalled HTTP/browserの素材失敗工程を元画像保持条件で確認する。

## 2026-09-07 v0.28.38 material failure display release preparation

PR #339 merge `fcf9676cacc9a24044bcd3a533c889b4c80872be`をfetch確認し、
branch `ux1/3d-material-v02838`でaddon/coreを0.28.38へ同期。
材質prepare失敗後の終端表示修正と日英source実ブラウザ受入を配布対象にする。
release noteへ保存形式不変、0.28.37へのcore rollback互換、未実施の配布受入を記録した。

本番read-onlyでcurrent→versions/0.28.37、Host PID849052 active。
Jobs460件全終端（326 succeeded/126 failed/8 canceled）、GUI23件全終端、
working copyはcommitted29/recovery3/released8でactive0、runtime operation5件ready、
model operation0を確認。既存制作物・runtime・サービスを変更しない。
Host main2a6f237と既存frontend/tsconfig.tsbuildinfo変更は保全する。

本版の署名公開・標準update・installed失敗表示受入は未実施。
GOAL-07/3DS-8全体はPARTIALのまま。次はexact mergeから標準bundleを作り、
内容/署名/consumerを検証して配布・導入済み環境の受入へ進む。
全 `./mf.sh test`: 1129 passed/既知warning1/150.44秒、exit0。
`npm run build:viewer`成功・生成物差分なし、node --check/diff check成功。

## 2026-09-07 material failure display and browser retry

PR #338 merge `b453e8f546aedd31d963e295f0693908c3b9f96d`から
branch `ux1/3d-material-retry-browser`。新診断
`scripts/3ds_material_retry_browser_e2e.py`のserveをMediaForge Python、
browserを既存Playwright診断Pythonで実行。専用data/loopback9164と既存owned
Blender4.5.9のread-only参照を使用し、通常.blend upload/importでfixtureを作成。
過去の実生成PNGを通常importして再利用し、このrunでは画像生成しない。
初回applyのworker bindingだけ存在しないobjectへ変更し、実Blenderの失敗を発生させる。
HTTP/WebSocket要求・応答やbrowser表示のmockはしない。locale入力だけfixture。

修正前の日本語320ではretry自体は成功したが、失敗画面の両比較paneに
「読み込んでいます…」が残る不具合を実画像で発見。pane終端assert追加後の
英語1280は期待The current revision is unchanged.に対しLoading…で失敗した。
frontendのcurrent tokenかつ候補不在のcatchだけを修正し、元版不変と割当失敗を
日英で表示する。採用禁止・詳細error・候補が既にある場合の既存処理は維持する。

修正後browserの--width 320 --locale ja、および--width 1280 --locale enは
双方observations.json passed=true/page_errors=[]。
証拠 /data1tb/mf-material-retry-browser-fixed-ja-320-20260907 と
/data1tb/mf-material-retry-browser-fixed-en-1280-20260907。
失敗後busy解除/採用不可/両pane終端表示、旧scene全投影と元image/source/previewの
実HTTP bytes SHA不変、閉じた後の対象・画像・slot/channel/UV選択保持をassert。
同じ割当buttonで再試行して2 pane描画、採用前は旧版不変、明示採用後だけ2版になり、
旧revision不変・同じ画像dependency・元3 Asset hash不変・横overflow0を確認した。
日本語修正後failed.pngでも終端文言を目視確認した。
終了後のread-only DB照合では日英ともJobはmedia.inspect3件のみ、画像生成/編集0、
working copyはcommitted1件・active0、material-previews配下0件。
これは停止後の検査であり、停止前のcleanupを追加実測したとはしない。

検証serverはsource standaloneでhealth=setup_required（環境snapshot不在）。
installed Host/新画像生成/Agent retry_job_id/全失敗matrixの証拠ではない。
英語serverはbrowser完了後、RuntimeMaxSec=300に達してsystemdが停止したことを
journalで確認（timeout）。現在inactive、稼働製品serviceを停止・変更していない。
本修正の署名配布・installed受入は未実施。GOAL-07/3DS-8はPARTIALを維持する。
node --check、script py_compile、git diff --check成功。
全 `./mf.sh test`: 1129 passed/既知warning1/509.91秒、exit0。
次はこの修正を通常PRでmergeし、署名bundle・installed受入へ進む。

## 2026-09-07 installed retry keeps original Blender after default switch

PR #337 merge `4479d72f1d444b1bd0af38dd990cacb105462969`から
branch `ux1/3d-retry-installed-acceptance`。新診断scriptは既存専用mf-e2eの取消Job
job_fb5b2171ee68442f86b889b10754273b（元4.5.13、primitive1件）のみを再試行対象にする。
owner/取消/検証用名称/入力数/installed0.28.37 healthyを検査し、
実行中Job・GUI・working copyが0であることを直前に確認した。

`3ds_retry_installed_e2e.py --expected-version 0.28.37
--job-id job_fb5b2171ee68442f86b889b10754273b
--evidence-dir /data1tb/mf-retry-installed-0.28.37-20260907`をHost診断Pythonで実行、
4.375秒/exit0。実Host opaque iframeのprivate bridgeで既定を4.5.9へswitch/ready後、
正規service identityのAgent HTTPで保存済みrequest+retry_job_idを一度だけ送信。
新Job job_f563a90199b043d882c4f4a5e666cf16は実Blender4.5.13でsucceeded。
実行中の既定は4.5.9のまま、Job pin/worker result/新revisionはいずれも4.5.13。
retry_ofは元取消Job。Host child DBもsucceeded、host_terminal_sent=trueを追加read-only照合。

finallyで正規switchを使い既定4.5.13へ戻しready、runtime registry bytesは開始前と一致。
元Jobの全DB列、既存scene/revision value_json全件不変、新scene/初版各1件だけ増加。
新scene scene_d997978d6b854edda365a8ec780cd620と新source/GLB2件は検証物として保持。
新Assetの実size/SHAとmetadata一致。runtime削除/再導入/worker故障注入/画像生成は行わない。
専用login sessionだけfinally revoke、既存password/global設定は不変。
Host849052/MF848621ともPID不変・active。こちらからservice restartなし。

これはsigned installedの実Agent HTTP/実Blender/実Host bridge受入で、Host fixtureではない。
switchはworkspace内call経由であり、Settingsの物理button click受入とは区別する。
再試行時の元環境保持はinstalledまで確認した。材質の故障後retryはsourceのみ、
全GOAL-07/3DS-8/C/D/E/Fの不足をこの1経路で完了扱いしない。
次はGOAL-07の残るHTTP/browser失敗工程受入を、既存成功画像保持の条件に沿って進める。
全 `./mf.sh test`: 1128 passed/既知warning1/172.05秒。script py_compile/diff check成功。

## 2026-09-06 v0.28.37 signed retry release installed

PR #336 merge/tag target `bb949db9d927ce2074f34a7aab0b89254528c38b`。
exact detached /data1tb/ControlDeckMediaForge-release-0.28.37で標準buildを実行、
--output-dir /data1tb/mf-0.28.37-build-20260906。PyInstaller6.22.0/Python3.12.3、exit0。
artifact31,516,076 B、SHA 7eb1c6490fc21d42784a1e382275b999936485cdfeacd0de3e26c215503964b5。
展開 /data1tb/mf-0.28.37-package-mkemqdqj/control-deck-media-forge-0.28.37-linux-x86_64。
archive6 entries/embedded199を検査、秘密値・venv・重み・制作物の混入なし。
最初の一律runtimes拒否は同梱requirements.txtに反応したため、依存定義と実体を区別して再検査。
最初のdoctorは必須feature data環境変数なしで拒否。専用領域を明示した再実行で
ok/version0.28.37/packaged=true/exit0。addon/feature版一致、PYZ内retry_pinも確認。
core SHA 73d4384a9e9476f208ca3980c2a3f6697bafd16465dd34966f30fdea308912fa。

同じ未公開packageを専用systemd unit mf-library-02837-acceptance/9163で起動。
専用fixture Storeを使用しhealthは環境snapshot不在のsetup_required。healthyとは扱わない。
`3ds_library_paging_e2e.py browser --server-kind bundle
--evidence-dir /data1tb/mf-library-paging-bundle-0.28.37-20260906`は日英320で全pass。
親60/子60→5/3→先頭復元、128 ID集合/一意、英語fallback、横overflow0/errors0。
synthetic lineage/standalone package受入であり、実制作/installed Host受入とは区別。
試験後にexact owned unitをstopしinactiveを確認。

既存publisher key（mode0600）で署名・自己検証、GitHub v0.28.37の4 assetsを公開。
公開consumer取得先 /data1tb/mf-0.28.37-public-20260906でsha256sum -c OK、
build artifactとcmp一致。GitHub tag exact target一致、Host trusted publisherの
_verify_signed_releaseでversion/hash/size一致。global agent設定/既存Blender変更なし。

更新前snapshot /data1tb/mf-0.28.37-pre-update-20260906:
directory0700、DB2,809,856 B/integrity ok/files0600。
registry SHA dd43b2e8b6897c9671958c3b4cc2f57dca82969a5d1d8492909761e86636741a。
更新直前にsnapshotと8テーブル全行一致を再検査してから標準registry.updateを実行。
14.645秒で0.28.36→0.28.37/healthy/enabled/requested_enabled=true。
current→versions/0.28.37、installed core SHAはpackageと一致。
更新後もassets/scene_documents/scene_revisions/blender_web_sessions/jobs/
scene_working_copies/blender_runtime_operations/model_operationsの全行（rowid順）が一致、
registry bytesも不変。MF PID848621 active、こちらからHost restartなし。

製品全gateは版準備時1128 passed/既知warning1/158.41秒。本追記は実測docsのみ。
再試行時active切替のinstalled実行と全GOAL/scenario matrixは引き続きPARTIAL。
installed Library `3ds_library_locale_installed_e2e.py --expected-version 0.28.37`を
既存real63-child fixtureで320/1280実行。初回320はpage.gotoでHost8765接続拒否。
MFは同PID848621/active、Host旧PID816370は終了し新PID849052/HTTP200へ回復したことを
read-only確認。こちらからrestartせず、終端したbrowser試験だけを別証拠directoryで再実行。
成功証拠 /data1tb/mf-library-real-paging-installed-0.28.37-320-20260906-r2 と
/data1tb/mf-library-real-paging-installed-0.28.37-1280-20260906、双方exit0。
実Host opaque iframeで子60→3→60→3/63 ID一意・全集合、offset60で日英通知[ja,en]、
source/filter/関連列/scene/load/session保持、横overflow0、scene不変/page errors0。
language入力のみfixture、Host通知/素材応答は実経路。新規制作Jobなし。
終了時Host849052/MF848621ともactive。Host別作業mainは2a6f237になっており保全した。
次のinstalled retry候補は専用user:16の取消Job job_fb5b2171ee68442f86b889b10754273b
（Credential acceptance 6fee7bad1386 cancel、primitive1、runtime4.5.13）。
候補選定はread-onlyで、再試行・active切替はまだ行っていない。

## 2026-09-06 v0.28.37 retry release preparation

PR #335 merge `4d508774dd7f859494b93bb3c07b204c0b6bf77c`をfetch確認。
branch `ux1/3d-retry-v02837`、addon/coreを0.28.37へ同期。
#334の再試行時exact runtime保持を配布対象とし、release noteに挙動、
元環境不在時の明示拒否、保存形式不変/0.28.36 rollback互換を記録。
sourceの実Blender受入とHost fixtureの範囲は前2記録を参照。
本番read-onlyでJobs459全終端（325 succeeded/126 failed/8 canceled）、
GUI23全終端、working copy active0を確認。MF PID700886 active。
Hostは別作業main a564c38/PID816370、frontend/tsconfig.tsbuildinfoの変更は保全する。
この時点で新bundleのbuild・署名・公開・標準update・installed retryは未実施。
全 `./mf.sh test`: 1128 passed/既知warning1/158.41秒。diff check成功。
全体3DS-8/GOAL-07等の未確認条件を縮小しない。

## 2026-09-06 material failed-stage retry reuses existing image

PR #334 merge `4a86add7fecbe25e20ae74521f9c4e8530b735ce`から
branch `ux1/3d-material-retry-acceptance`。診断scriptだけを追加し製品codeは変更しない。
`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_material_retry_e2e.py
--evidence-dir /data1tb/mf-material-retry-source-20260906-final
--managed-root /data1tb/mf-long-setup-source-20260906/runtimes/blender
--image /data1tb/mf-no-blender-image-0.28.33-20260906/generated.png
--image-sha256 1ed7bf93ca6c4c0d3ed50aac7ad90c04288d0cf3dfffac38f397ee701e6ba542`。
専用registry/dataとread-only owned実Blender4.5.9、Host credential/control fixtureで2.386秒exit0。

画像は過去の実FLUX.2成功Job job_a6ea97330a684034bf4404a6a3e82cdeの保存PNG bytesを
hash確認して通常importする。このrunで画像を生成したとはしない。import provenanceは
元生成Jobのprovenanceとは別。実cube/材質/UVをtyped createで作り、初回の材質workerだけ
存在しないobject名を与える診断用faultを注入。永続request/bindingは変更しない。
実Blenderはtrusted resultを生成せず、coreがscene_material_worker_invalidとしてfailed。
最初のscriptはscene_material_rejectedを期待してassert失敗したが、実際のfail-closed分類を
確認して修正。-r2は2.129秒で成功、成功済みJob不変assertも加えた-finalが最終証拠。

scene_26427d1a360747cc8548a6d9d405c550、取り込みimage
asset_9626a37739a7498b885b7bbbf8c68c88。失敗後はscene/revision全応答、
全既存Asset metadata/provenance/実bytes hash不変、新Asset0。
manager再作成後、同じscene/material入力とretry_job_idで新試行。
retry_of/input hash一致、成功後は旧版不変で2版、新Assetはsource/GLB2件のみ。
画像import/形状成功Jobは全field不変、追加Jobは失敗材質と成功retryの2件だけ。
新revisionの画像dependency ID/hash一致、全出力の実hashもmetadataと一致。
材質worker試行2回、image.generate/edit Job0、runtime参照0/active working copy0/
material staging空を照合した。復旧候補を成功済み制作版と取り違えない。
全 `./mf.sh test`: 1128 passed/既知warning1/160.43秒。最終script py_compile/diff check成功。

これはsource domain/process受入であり、installed Host・HTTP・browser・GPU生成・
全retry失敗matrixの成功には広げない。既存稼働service/runtime/sceneを変更しない。
GOAL-07はPARTIALのまま、次は#334修正を署名bundleへ載せて導入経路を確認する。

## 2026-09-06 retry preserves original Blender runtime

PR #333 merge `e3c19a2b012c65b648f847fc79fc1b2067adbd13`を確認し、
branch `ux1/3d-retry-runtime-pin`。GOAL-07を照合中、失敗scene.createのretryが
保存済みruntime_id/versionを使わず、その時点のactive環境を再選択する不具合を発見。
追加2 testsで修正前を再現: active変更後はlegacy IDへ変わり、元managed登録解除後も
別環境で受理された。修正後は旧Jobの永続pinを取得threadへ渡し、同じremoval guard内で
exact runtimeの検証・参照取得を行う。不在/不適合はHost child作成前に
scene_runtime_unavailable。edit/materialは既存base/current検査と旧pin一致も要求する。
公開schema/入力/成功済み版の意味を変更せず、任意runtime指定も公開しない。
新たな同期DB/HTTP/process待機をasyncへ追加しない。取得取消と参照解放の既存保護を維持。

focused scene recipe/pin28 tests成功。新testsはfailed attempt後のmanager再作成・active切替、
元登録なし拒否、Host Job/worker追加なし、retry_of/元版一致/参照0を検査する。
実機 `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_retry_runtime_pin_e2e.py
--evidence-dir /data1tb/mf-retry-runtime-pin-source-20260906-r3
--managed-root /data1tb/mf-long-setup-source-20260906/runtimes/blender`は1.547秒/exit0。
隔離registry/dataだけを使用。既存owned runtime実体は読み取り専用、導入/削除なし。
4.5.9で受け付けた待機Jobを正常cancel、managerを作り直しactive4.5.13へ変更した後、
retryは実Blender4.5.9で成功。input hash/idempotency key一致、retry_of元Job、参照0。
source426,899 B/GLB1,756 Bの実size/SHAとmetadata一致、独立GLB検査12 triangles。
Host credential/controlはfixtureであり、HTTP/installed/browserの証拠ではない。
初回は診断scriptのcatalog指定漏れ、r2は必須primitive name欠落で実行前失敗。
それぞれ終了を確認してscriptを修正、別証拠directoryのr3で成功した。製品失敗とは区別。
診断module importもasync外へ移した最終scriptを-final directoryで再実行、0.815秒/exit0。
同じpin/取消/実Blender/Asset検査を再確認。全 `./mf.sh test` は
1128 passed/既知warning1/157.86秒。最終script py_compile/diff checkも成功。

稼働0.28.36への修正配布は未実施。材質失敗時の成功済み画像再利用、全retry matrix、
GOAL-07/3DS-8の完了は主張しない。次は該当材質工程の実機受入と修正の署名配布。

## 2026-09-06 installed Library real 63-child paging

PR #332 merge `102f2787638e2ea713ddadced65f19b549ddc25c`をfetch確認し、
branch `ux1/3d-library-installed-paging`で実installed0.28.36を検証。
`scripts/3ds_library_installed_fixture.py --expected-version 0.28.36
--evidence-dir /data1tb/mf-library-real-fixture-installed-20260906`を既存Host診断Pythonで実行。
専用mf-e2eの正規service identityから実Agent HTTPでcube作成/transform編集を行い、
Job job_9721927fa88e469c98d193b0fdaf1ace / job_66e7b2c31d8c4571b7710994a263d102が成功。
実Host opaque iframeから正規scenes.revisions.restoreを61回実行。34.805秒/exit0。
DBへのsynthetic挿入や既存scene変更はない。以前のscene/revision value_jsonは全件不変、
追加sceneは1件だけとread-only照合。検証専用scene/historyは意図的に保持し、
削除保護を回避するcleanupは行わない。既存mf-e2e passwordは不変、作成sessionだけfinally revoke。

scene_92c45d0e9ee14d96bd64a436b2e52466、63 revisions、初版source
asset_f085bf863bf84e1caa24e6cd3c098541。初版preview1・編集source1・復元source61の
実children63件ができた。fixture.jsonに全IDs/Job結果/各restore応答を保存。
追加read-only実bytes検査で126 Asset、26,978,198 Bのsize/SHAがmetadataと一致、
126 provenance sidecarがDBと一致、61復元のsource/preview bytesは初版hashと一致。

`3ds_library_locale_installed_e2e.py --paging-fixture
/data1tb/mf-library-real-fixture-installed-20260906/fixture.json --expected-version 0.28.36
--scene-id scene_92c45d0e9ee14d96bd64a436b2e52466 --width 320|1280`を実行。
証拠 `/data1tb/mf-library-real-paging-installed-{320,1280}-20260906`、双方exit0。
本番8765→署名installed MFのLibrary blend filterから初版cardを実クリック、
子60→3→60→3、63 ID一意/全集合一致、offset120なし、前ページ同じ列を確認。
offset60で実locale.changed [ja,en]、source/filter/関連ID列/scene選択/load/nonce保持、
日英label再描画、dialog/document横overflow0、scene全応答不変/page errors0。
nonceは比較時のメモリ内だけで、証拠に出さない。320英語screenshotも実画像で確認。
言語入力だけnavigator.language/languagechange fixtureで、Host通知/素材応答は合成しない。
初版のparentsは0件。このrunをinstalledで親60件超の証拠とはせず、
親65/子63の専用source/bundle fixtureの既存証拠と区別する。

全 `./mf.sh test`: 1126 passed/既知warning1/167.01秒。script py_compile/diff check成功。
製品backend/frontend/公開契約/版数/配布物は変更なし、新releaseも不要。
終了時MF PID700886/active、Host8765 listener PID757950を確認。Host変更/こちらからのrestartなし。
GOAL-01のinstalled60件超の不足を解消。全体3DS-8のC/D/E/F・GOAL-07/09/10等はPARTIAL。
次は失敗工程だけの再試行（GOAL-07）の実装と実機証拠の対応を照合する。

## 2026-09-06 v0.28.36 signed release and installed Library acceptance

PR #331 merge/tag target `d6e1f041a415902582fb39698ef2fd1659d5e3f5`。
exact detached /data1tb/ControlDeckMediaForge-release-0.28.36-r2で標準bundle build、
--output-dir /data1tb/mf-0.28.36-build-20260906-r2。PyInstaller6.22.0/Python3.12.3、exit0。
artifact31,516,338 B、SHA ba0e087bb4cc97beb03c671d2e9821a879e7c52beac517366c24c40941013d8a。
旧candidate（b51434...）は未公開のまま保持し、この再buildだけを署名・公開した。
archive6 entries/embedded199、禁止混入なし、certifi公開CA/private key区別、
同梱stylesのwrap rule、addon/feature/packaged doctor0.28.36一致を再確認。
展開先 /data1tb/mf-0.28.36-r2-package-t30h68ed/control-deck-media-forge-0.28.36-linux-x86_64。
core SHA b2db4da0483259e3c435f52762c909b17caf99b54feaf91332d03173d160faed。

専用package unit PID689328/9163で同じsynthetic Storeへ接続。環境未導入のhealthは
setup_requiredでhealthyとは書かない。`3ds_library_paging_e2e.py browser --server-kind bundle
--evidence-dir /data1tb/mf-library-paging-bundle-0.28.36-20260906-r2`は日英320全pass。
親60/子60→5/3→元page、128 ID集合/一意、英語Not recorded、dialog横overflow0/page errors0。
専用unitは試験後stop/inactive。これはbundle/standalone受入で、installed Hostの60件超ではない。

既存publisher keyで署名/自己検証しGitHub Release v0.28.36の4 assetsを公開。
公開consumer再取得先 /data1tb/mf-0.28.36-public-20260906でsha256sum -c OK、
build artifactとcmp一致。Host trusted catalogの署名検証でversion/hash/size一致。
GitHub tag refがexact target d6e1f04と一致。global agent設定や既存Blenderを変更していない。

更新直前の本番Jobs396/GUI23/runtimeops3/modelops0は全終端、working copy active0。
private snapshot /data1tb/mf-0.28.36-pre-update-20260906（directory0700/files0600）、
SQLite2,076,672 B/integrity ok、registry SHA
dd43b2e8b6897c9671958c3b4cc2f57dca82969a5d1d8492909761e86636741a。
標準registry.updateは25.868566秒、0.28.35→0.28.36/healthy/enabled/requested_enabled=true。
current→versions/0.28.36、installed core SHAがpackageと一致。runtime registry SHAも不変。
read-onlyでsnapshotと現在のassets/scene_documents/scene_revisions/blender_web_sessions/jobs/
scene_working_copies/blender_runtime_operations/model_operationsの全行（rowid順）が一致。
Hostは別作業でPID658027へ更新されていた。今回はこちらからHost restartなし。
MF更新後PID700886/active、Host658027/activeを確認。Hostの別作業ファイルは保全した。

実installed `3ds_library_locale_installed_e2e.py --expected-version 0.28.36`を
--width 320/1280で実行し両方exit0。証拠
/data1tb/mf-library-live-locale-installed-0.28.36-{320,1280}-20260906。
実locale.changed [ja,en]、選択source/offset0/filter/関連ID列/load/nonce保持、
scene全体不変/page errors0。言語入力のみbrowser fixture、通知/responseは実経路。
公開release noteへ結果を反映。製品code gateは修正exact treeの1126 passed/163.19秒、
この追記は実測docsのみ。全GOAL/scenario matrixとinstalled60件超はPARTIALのまま。

## 2026-09-06 v0.28.36 candidate paging and detail-title overflow

PR #330 merge `4075df202791bda7b3e99c94557b70a10bc516e3`からexact detached checkout
/data1tb/ControlDeckMediaForge-release-0.28.36で標準bundle build実行。exit0、
artifact31,514,810 B/SHA b51434a5ce1d9528827761897eb63b12b7898dd6061584ad71e4cd72f9b2ff46。
/data1tb/mf-0.28.36-build-20260906に保持。未署名・未公開・本番未導入。
archive6 entries/embedded199を検査、venv/weights/制作物/SQLite混入なし、
certifi公開CA以外の.pemなし/PRIVATE KEYなし。addon/feature/packaged doctor0.28.36一致。
core SHA a33a022b15fbd2beb1ef65395c41f505cbae7a89e3c8b858b004345541d0173b。
展開先 /data1tb/mf-0.28.36-package-i0dzdmdk/control-deck-media-forge-0.28.36-linux-x86_64。

専用systemd unitの実package PID657006/9163、環境未導入healthはsetup_required。
--server-kind bundleの実Chrome日英320で60/60→5/3→60/60、全128 ID一意/集合一致、
英語Validation Not recorded/page errors0を確認。
証拠 /data1tb/mf-library-paging-bundle-0.28.36-20260906。
ただしscreenshotで長いsource ID見出しの横はみ出しとdialog内横scrollを観測した。
document幅のassertだけではdialog内部overflowを捕まえられなかったため、公開を保留。

branch ux1/3d-library-detail-wrap。#detail-titleにoverflow-wrap:anywhere/min-width:0を追加。
paging受入scriptで先頭/末尾ページのdialog scrollWidth<=clientWidthを追加。
旧packageへ追加assertを実行し、最初のpageでhorizontal overflow失敗を再現。
初回は起動直後の接続拒否で、同じlive unitのhealthを確認後再試行した。再起動していない。
証拠 /data1tb/mf-library-overflow-before-20260906（再試行のassert失敗）。

修正sourceを同じowned Storeへ向け別の専用unitで起動。日英320で新assertを含め全pass、
全128 ID、先頭/末尾/戻る不変、英語fallback、page errors0。screenshotでも見出し全体の
折返しと横scroll消失を確認。証拠 /data1tb/mf-library-overflow-after-20260906。
使った3つの専用unitは試験後それぞれstop/inactive。本番runtimeやsceneは変更しない。
修正後全MF gate初回は76%以降にexit143/SIGTERMで終了、原因未確定でpassとは扱わない。
source専用unitのjournalは正常shutdown complete（PID662516）を確認。
再実行の全gateは1126 passed/既知warning1/163.19秒。py_compile/diff check成功。
修正を含む新exact mergeから0.28.36を別build directoryへ作り直す。
旧candidateを配布せず、package再受入→署名公開→consumer検証→標準updateを続ける。

## 2026-09-06 v0.28.36 Library release preparation

PR #329 merge `7cbd8c4697e15a2efb8f6400ce8436fce224341f`をfetch確認。
branch `ux1/3d-library-v02836`。addon/coreを0.28.36に同期。
PR #328の英語Validation空欄/読み込み中Details修正を配布へ進める。
新release noteはschema変更なし、0.28.35 rollback互換、全3DS-8 PARTIALを明記。
paging受入scriptにbase-url/server-kindを追加し、sourceとbundleの証拠を区別する。

`PYTHONPATH=backend:tests:. .venv/bin/python scripts/3ds_library_paging_e2e.py seed
--evidence-dir /data1tb/mf-library-paging-bundle-0.28.36-20260906`で専用Storeへ
親PNG65/source .blend1/child GLB63を作成。source asset_6dfed1fc3e0241a2a2896ebd9c531501。
既存owned実bytesを再利用したsynthetic lineageで、新Blender制作でも本番DBでもない。
script py_compile/diff check成功。バンドルのbrowser受入はまだ実行していない。

本番read-only: installed currentは0.28.35。Jobs396全終端（262 succeeded/126 failed/8 canceled）、
GUI23全終端（17 stopped/4 interrupted/2 failed）、runtime ops3 ready/model ops0、
working copy committed29/recovery3/released8、active0。
runtime registry SHA dd43b2e8b6897c9671958c3b4cc2f57dca82969a5d1d8492909761e86636741a不変。
Host612020/MF396381 active。Hostのllama.py/test_llama_kv_capacity.pyは別作業で保全。
全 `./mf.sh test`: 1126 passed/既知warning1/187.16秒。新tag/署名/公開/標準updateは未実施。

## 2026-09-06 Library live locale bridge acceptance

Host PR #294 merge `2fafa2d4256b14108a4beddd6b414491af53bd24`は
frame/device/Jobs streamの構造化終了処理。全1022 passed/2 skipped/154.50秒と、
専用systemd実WebSocketの20回text/binary切断+故障1回、残存direction0を確認してmerge。
Host PR #293 merge `3f718782ec759a3813f764e76fa741ad164eb32d`は汎用languagechange購読/
locale.changed通知。関連内容はHost implementation-status。Media固有Host codeなし。

再開時Hostは別作業PR #295のrestart中（PID407562/deactivating）。
こちらから停止/再起動せず、PID612020/activeへの遷移をread-only確認。
新script `scripts/3ds_library_locale_installed_e2e.py`を既存Host診断Pythonで実行。
専用mf-e2e sessionだけを作りfinally revoke、password/scene/runtimeを変更しない。
ブラウザ入力としてnavigator.language + languagechangeを与えるが、bridge eventや
workspace responseは合成しない。受信portは記録して元handlerへ渡すだけ。

まず隔離Host Vite5179（マージ済みfrontend、/apiと/addon-frameは本番8765へproxy）から
installed MF0.28.35へ接続。320/1280ともja→en、実locale.changed受信2件、
選択source/offset0/filter/関連ID列/load時刻/nonce/scene選択不変、scene全体不変、
opaque origin null/page errors0を確認。
証拠 `/data1tb/mf-library-live-locale-candidate-{320,1280}-20260906`。
320英語screenshotも実画像で確認。candidate Host UIとinstalled MFを区別する。

別作業の変更がPR #295へmergeされcanonical Hostがcleanとなったこと、
HEAD697f94c→origin/main3f71878がfrontend/docsだけ（backend差分0）を確認。
Host canonicalをfast-forwardし標準frontend build44.03秒成功（既知chunk warning）。
実8765のHTMLはindex-CC8QHKQj.jsを参照。Host612020/MF396381のPID不変/active、
こちらからservice restartなし。
続いて本番URL8765で320/1280を同script（--candidate-host-uiなし）で実行し双方exit0。
証拠 `/data1tb/mf-library-live-locale-installed-{320,1280}-20260906`。
両幅で実locale.changed [ja,en]、日本語/英語の詳細labelとLibrary filter label再描画、
source asset_53a56a66f4384ecdb8506f0f9529ffa6/offset0/filter/関連ID列/load/nonce保持、
scene全体不変/page errors0。1280日本語screenshotも実画像で確認した。
専用Vite PID613280はSIGINT/exit130で停止。
全 `./mf.sh test`: 1126 passed/既知warning1/236.66秒。script py_compile/diff check成功。
GOAL-01の60件超installed pagingと、実ブラウザ設定UIからの言語変更は未検証。

## 2026-09-06 Library default-page boundary acceptance and English fallback

PR #327 merged `6bd004d7e8f24605e6ee7b376cf3e27670b2f0e8`を確認。
branch `ux1/3d-library-paging-acceptance`。
本番read-only集計で最大children12件を観測。60件超を本番データで受入したとは扱わない。
追加testは親65/子63のsourceを作り、private HTTPとWebSocketで既定60件、
offset0→60→120→0の一致、末尾5/3件、truncated/next_offset、重複/欠落なしを確認。
asset_pathを拒否fixtureにしてmetadata-onlyを検査。focused3 tests passed。

新 `scripts/3ds_library_paging_e2e.py` のseedをMF Python、
browserを既存Host Playwright診断Pythonで実行（coreへの依存追加なし）。
`--evidence-dir /data1tb/mf-library-paging-20260906`。
fixtureは専用Storeの親PNG65件・source .blend1件・child GLB63件。
.blend/GLBはowned旧受入の実bytes、lineageはsynthetic acceptance fixtureと明記。
新Blender制作を実行した証拠ではない。本番DBや既存sceneを書き換えない。

初回browserはblend card待ちtimeout。Libraryが絞り込み前の実asset行でcursorを進めるため、
sourceより新しいGLB63件を越える「もっと見る」が必要だった。scriptを既存cursorに従う
UI操作へ修正し、日英320pxで60/60→5/3→60/60、全128 ID一意・集合一致、
末尾nextなし・前ページ復元・document横overflowなし/page errors0を実Chromeで確認。
localeはapplyTheme入力fixture、実Hostの言語変更通知の証拠ではない。

英語screenshot検査でValidation空欄のfallbackだけ「記録なし」が残る実装を発見。
frontendをNot recordedへ修正し、読み込み中Detailsも英語化。
実browserで英語Validation値をassertして再実行exit0。HTTP/Storeの製品変更なし。
本番0.28.35にはこのfallback修正を未導入。新署名releaseを出したとは扱わない。

Host側read-only調査: EmbeddedAddonViewは接続時にlocale.changedを送る。
その後のthemeTokens変更はtheme.changedのみで、browser languagechange購読もない。
MediaForge側にはlocale.changedの詳細再描画/offset保持処理があるが、実Hostからの
動的通知経路はまだ未検証。汎用Host通知が必要なら別PRの範囲として進める。
GOAL-01はsource境界受入が進んだが、installed60件超/実Host動的localeはPARTIAL。
修正前全gate1126 passed/160.30秒、修正後最終 `./mf.sh test` は
1126 passed/既知warning1/163.69秒。node syntax/diff check成功。
専用source PID409380と修正後PID415143はそれぞれSIGINT→shutdown complete/exit0。
本番MFはPID396381/activeのまま。次はHostの汎用locale通知契約と実fixture付き受入を検討する。

## 2026-09-06 v0.28.35 signed release and installed history confirmation

PR #326 merge/tag target `7ec457ac7bc87b73e3306b6a255ddfa143e790e9`。
exact checkout /data1tb/ControlDeckMediaForge-release-0.28.35で
`python3 scripts/build_release_bundle.py --version 0.28.35
--output-dir /data1tb/mf-0.28.35-build-20260906
--pyinstaller /data1tb/ControlDeckMediaForge-3ds4/runtimes/bundle-build/.venv/bin/pyinstaller`。
PyInstaller6.22.0/Python3.12.3、exit0。artifact31,516,941 B、
SHA eea782de56b0ce9e2e4cb1e810b7cdc490658ef2d957022c8e8a8a28c16bfa05。
外側archive6 entries、embedded199 entriesを検査。最初の.pem一律拒否は
certifi/cacert.pemで失敗。公開CA束でPRIVATE KEYなしを確認して区別し、
秘密鍵/venv/weights/.blend/SQLite混入なし。addon/feature/core doctorの0.28.35一致。
展開先 /data1tb/mf-0.28.35-package-346YqT、core SHA
ebb7a7255082d10d9073375904145364bd524de497e5babed01054d4ab4e06e1。

公開前の同一artifactを専用owned clean setup root、PID375803/9162で起動。
`scripts/3ds_history_settings_e2e.py --verify-preserved-ui
--evidence-dir /data1tb/mf-history-settings-package-0.28.35-20260906`
は79.551秒/exit0、日英1280/320・確認reset・日英320で実削除/同版再導入。
旧版不在区間のGLB表示/backup保存、ZIP全entry size/SHA照合、全6files/scene/revision不変。
localeは入力fixture（script内source mode文字列は同じだが接続先はpackage実process）。
試験runtimeは再導入済み、GUI未終端0を確認後SIGINT、application shutdown complete/exit0。

既存publisher keyでsign_release.py署名/自己検証成功（Host診断Python、core依存追加なし）。
GitHub Release v0.28.35の4 assetsを公開。consumer再取得先
/data1tb/mf-0.28.35-public-20260906でchecksum・size・build artifact実bytes一致。
Host trusted catalogの_verify_signed_releaseで公開manifestの署名/identity/versionを検証。
GitHub tag refがexact merge targetと一致。公開鍵は既存80bNiqW1CzAzQ3LSqYqtwecm6TYQywDLxGACF9AVsac=。

更新直前も本番Jobs/GUI/runtime operations未終端0。
private snapshot /data1tb/mf-0.28.35-pre-update-20260906:
DB2,076,672 B/integrity ok、registry488 B、双方0600。
標準registry.updateは16.54秒、0.28.34→0.28.35/healthy/enabled/requested_enabled=true。
current→versions/0.28.35、installed core SHAはpackageと一致。
runtime registry SHA dd43b2e8b6897c9671958c3b4cc2f57dca82969a5d1d8492909761e86636741a
がsnapshotと不変。Jobs396/GUI23/runtimeops3全終端・件数不変。
MF PID396381 active、Host PID250878不変、Host restartなし。

実installed `scripts/3ds_settings_protection_installed_e2e.py --expected-version 0.28.35
--require-readable-layout --require-touch-targets --require-history-confirmation --locale ja`
は /data1tb/mf-history-settings-ja-installed-0.28.35-20260906でexit0。
opaque origin null、Host/child実locale一致、1280/320でold project参照2は確認既定off、
チェックでenabled/再openでoff、active+project23の新版は確認でも削除不可。
本番remove送信なし、runtime status全体不変。専用loginはfinally revoke、password不変。
英語初回はpointerがHost IFRAMEに届きchild events0/dialog hiddenで失敗。
同版無変更の--probe-geometry再実行r2は日英切替なしの英語1280/320全pass、
各pointerがchild BUTTONへ届いた。JS click/keyboard代替で成功にしていない。
初回の入力未到達の原因はこの記録だけでは確定しない。
通常再実行r3でも同位置で失敗。pointerdownはHost IFRAME、pointerupのみchild BUTTON。
--native-viewportは英語desktopで通常pointer全pass（実innerWidth1248）。
resize後reload案は設定buttonのtoggleで設定を閉じたため検証script側が失敗し、採用しない。
受入scriptに--initial-widthを追加し、起動時から固定viewportで開く検証を分離した。
--initial-width 320は英語実installedで確認reset/active保護/横overflowなし/44px button、
runtime不変を通常pointerでpass。証拠は同prefixの-native/-fixed320。
--initial-width 1280も全pass（-fixed1280）。英語fixed320の確認画面を実画像で確認した。
これはlive resize直後の入力問題の修正ではない。製品codeは変更せず残件を保持する。

全gate1125 passed/既知warning1/186.39秒（版準備）。今回は実測文書と受入scriptの変更。
受入script追加後の全gate: 1125 passed/既知warning1/157.30秒。diff check成功。
新機能は署名installedへ到達。全D/F matrix、installedでの実削除、
全体3DS-8受入は引き続きPARTIAL。次はcompletion auditの残件を依存順に進める。

## 2026-09-06 v0.28.35 history-preserving management release preparation

PR #325 merged `da9da4c2347ed5b8d9c856bdf23724022bfe1993`をfetch確認。
branch `ux1/3d-history-v02835`。addon/coreを0.28.35へ同期し、release noteに
履歴確認・同版再導入・稼働保護とrollback条件を記載した。
installed Settings受入scriptへ任意--require-history-confirmationを追加。
本番runtimeを削除せず、inactive旧版の確認既定off/チェック時enabled/再open時off、
active版の削除拒否とruntime status全体不変を要求する。旧版向け既存挙動も維持する。

公開latest/本番installedは0.28.34、標準registry.statusでhealthy/enabled/requested_enabled=true。
本番Host/MF PID250878・244551/active、currentはversions/0.28.34。
read-only SQLiteで396 Jobs全終端（262 succeeded/126 failed/8 canceled）、
GUI23終端（17 stopped/4 interrupted/2 failed）、runtime ops3 ready/model ops0。
working copyはcommitted29/recovery3/released8、activeなし。
この時点では本番update/restartや新署名公開を実行していない。
版準備gate `./mf.sh test`: 1125 passed/既知warning1/186.39秒。diff check成功。

次はexact merge headから軽量bundle、専用packageで確認/削除/再導入受入、
署名公開・consumer検証・標準update・installed確認へ進む。
3DS全体はPARTIAL、これまでのsource受入をinstalledの証拠にしない。

## 2026-09-06 history removal restart and Settings acceptance

PR #325 candidate head `7e81f7e`を確認して継続。追加7 tests:
durable確認を保持した再開、確認欠落/不正bool、受付後active変更、catalog変更の削除拒否、
exact installのarchive SHA/size変更時の再開拒否。初回3 testsはbase manifestとの不一致で
catalog_invalidになった。base manifestも同時更新した有効catalog変更fixtureへ修正し、
要求したidentity-change検査まで到達させた。最終7 passed。
`./mf.sh test`: 1125 passed/既知warning1/166.33秒。製品コードの追加変更なし。

source専用server PID343487/9162を既存owned clean rootで起動。本番Hostへ変更なし。
新 `scripts/3ds_history_settings_e2e.py` をHostの既存browser診断Pythonで実行。
coreへPlaywright依存追加なし。初回はDISPLAY未指定でChrome起動前に失敗（製品操作なし）。
実user環境のDISPLAY=:0/XAUTHORITYを指定して再実行。
`--evidence-dir /data1tb/mf-history-settings-20260906-r2` は日英1280/320すべてpassed。
さらに `--verify-preserved-ui --evidence-dir /data1tb/mf-history-settings-20260906-r3`
は104.143秒/exit0、page errors0。native Chrome pointer操作（JSでclick代用なし）。
localeのみproduction applyTheme/renderへfixture入力し、installed Host locale.changedとは区別。

両言語1280/320で確認既定off、未確認button disabled、チェック後enabled、
再render後の確認保持、dialog再open時のoff、document/dialog横overflowなし。
日英320pxそれぞれで実remove→未導入版button→実exact再導入。
旧4.5.9不在区間にWeb Blenderのscene履歴1版を表示し、GLB viewerを開く。
実canvasは12 trianglesのcubeを表示（日本語320 screenshotも画像検査）。
backup buttonから実downloadし、ZIP manifestのdocument/revisionsが元と一致、
全entryの実bytes size/SHA一致。最後にSettingsへ戻り同版再導入。
全6 immutableファイルSHA、scene/revisionsは不変、active4.5.13維持。
削除した検証用Aは再導入済み。backup ZIP2件はevidence dirへ保持。
最終runtime operation ready、GUI未終端0を実HTTP確認後、専用serverへSIGINT。
同processがapplication shutdown complete/exit0。利用者の常用serviceは停止しない。

PR #325のsource実装/再開・Settings/保存保持受入は完了。
本番installedでこの変更を動かした証拠・新署名releaseはまだない。
次は通常マージ後、署名bundleを公開・標準updateしinstalled Settingsを再受入する。
3DS-8/scenario D全matrixや全体goal完了をこの記録だけで主張しない。

## 2026-09-06 history-preserving removal and exact reinstall (candidate)

PR #324 merged `d754f5d3dc1312577e02939c2065c316269cfa30` をfetch確認。
branch `ux1/3d-history-preserving-removal`。runtime design §4.1の実装を開始。
managed removeに既定falseのacknowledge_historyを追加し、bool以外を拒否。
inactive・live参照ゼロ・trusted catalogとversion/archive hash一致時のみ履歴確認を許す。
project参照なしの従来削除を維持し、active/GUI/Job/working/in-process保護は確認でも解除しない。
preview fingerprintにexact再導入identityを含め、durable削除journalに確認内容を保持。
private WS/HTTPにinstall_exact(runtime_idのみ)を追加。受付DB/FSはworker thread、取消時も追跡。
既存staging/hash/probeを使い、再導入時に別active版やscene pinを変更しない。
設定UIに未導入catalog版の導入button、既定offの履歴確認checkbox、日英説明を追加。
このUIはまだbrowser実測前。外部登録解除の入力・公開agent/schema/Hostは変更しない。

追加testは実SQLite scene/revision/画像dependencyとfixture Asset bytesの保持、
default/不正bool/active/live拒否、正確な4.5.9再導入、active4.5.13維持、
重複導入/未知ID拒否。初回追加testはStore取得引数順の誤りで失敗し修正。
既存focused43 passed、追加test passed。
`./mf.sh test`: 1118 passed/既知warning1/159.65秒。node --checkとdiff check成功。

実行: `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_runtime_removal_e2e.py
--history-reinstall --evidence-dir /data1tb/mf-history-reinstall-20260906`。
専用clean setup rootで実HTTP/実Blender、73.218秒passed/exit0。
candidate4.5.13をexact導入し、旧4.5.9 GUI稼働中は確認付き削除も422拒否。
停止後も確認なしは422、確認付きで旧版のみ1,168,332,155 B削除。
scene/revision/Asset metadataと全6ファイル（.blend/GLB/ZIP/provenance）のsize/SHA不変。
旧版不在のGUI開始は422/scene_runtime_unavailable。scene pinを変えず、
archive SHA dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d の
4.5.9を再導入しprobe成功。同じsceneを4.5.9 GUIでready→stopped。
session blendersession_12bee578ec65464d9921befd8baa586b、停止unit inactive/MainPID0。
activeは4.5.13を保持し、再導入後も全履歴・6ファイル不変。
検証rootは現在A+B共存/active B。削除したAは同版再導入済み、制作物削除なし。
本番Host/MF active/PID250878・244551を照会、restart/updateは要求していない。

残件: 確認journal再開・catalog変更/競合の追加test、日英320px browser実測、
Library表示/backup操作、installed受入・署名release。今回RFB画面/入力はNOT TESTED。
本sliceはcandidate、3DS-8/scenario D全体はPARTIAL。マージ前に残件の検証を続ける。

## 2026-09-06 guarded GUI and working-copy admission

PR #323 merged `7962356b44b7db27a44d72f640be02df60ec54f6` をfetch確認。
branch `ux1/3d-working-admission-guard`。
GUI createをasync admissionへ移し、worker thread内のresolver.removal_guardで
runtime ID/version検証とqueued record保存を一体にした。復旧元owner/scene/current revisionも検査。
未導入/削除済み版は受付前に明示拒否、開始済みrecord作成はrequest取消で放棄しない。
旧queued recordのruntime nullは引き続き読める。新しいqueuedは最初から版を固定する。

通常/復旧working-copy作成も同じguard内でruntime検査・copy・DB lease確定を行う。
app WS/HTTP、GUI準備、材質適用、材質候補採用の全production callerをasync worker取得へ接続。
待機中の取消は開始済みthreadの終了を待ち、新規copy/leaseをreleaseする。
GUI停止/中断は旧準備taskのcleanupをjoinしてから終端へ進み、shutdownも追跡を維持する。
queued pinと準備したworking版が変わればfail-closed。すでにstopping/stoppedのrecordを
遅れて準備し直さない。公開schema/agent/Host/frontend変更なし。

初期focused38件中1件が失敗。async受付後にはcopy準備が進み得るため、
「即停止時にcopyのDB行が一度も作られない」という旧assertは成立しなくなった。
released行の保持は許容し、active copyなし/実directory空/controllerなしを要求するassertへ更新。
追加7 casesはnormal/recoveryと削除guardの競合、準備thread中のstop/interrupt/shutdown、
削除済みruntimeの事前拒否、GUI recordの固定とrequest取消後の記録保持。
focused5 modules: 45 passed/既知warning1。
最終 `./mf.sh test`: 1117 passed/既知warning1/185.31秒。diff check成功。

実行: `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_runtime_removal_e2e.py
--live-references-only --hold-working-admission
--evidence-dir /data1tb/mf-working-admission-guard-20260906`。
専用clean setup領域のsource実HTTP/実4.5.9 GUI。新flagはcopy thread内部の明示gate fixtureであり、
Blender binary/runner/DB/HTTPは実物。runtime切替/削除は行わない。
4.060秒passed/exit0。queued responseで4.5.9 pin、copy gate中のremove previewはpending。
同区間の/healthはHTTP200/0.003346秒、statusはsetup_required（healthyとは記録しない）。
解除後previewはsession1+working copy1/live2、実GUI ready後も2、停止後0。
正規remove POSTは両状態で422/in_use。active/project保護も併存し、liveだけが拒否理由とはしない。
session blendersession_206d0ccc97914646a548b8085118f2b8、停止unitはinactive/MainPID0。
scene/revision/Asset metadataと既存全6ファイルのsize/SHAは前後不変。具体hashはobservations.json。
本番Host/MFは照会時active/PID250878・244551。こちらからrestart/update要求なし。

実削除commitが先行するGUI同時開始、確認付き履歴削除、同版再導入、
installed Host/browser、今回のRFB画面/入力、新署名releaseはNOT TESTED。
次は停止済みmanaged版の明示確認付き削除をdurable operationへ保存し、正確な同版再導入へ接続する。
3DS-8/scenario DはPARTIAL、本番0.28.34へこの変更を導入したとは扱わない。

## 2026-09-06 durable runtime references and off-loop removal

PR #322 merged `4e0c9b20ac79683de53d1ef35f44e3d18ff89132` をfetch確認。
branch `ux1/3d-durable-runtime-references`。Store.active_scene_runtime_referencesを追加し、
同じDB read snapshotで未終端recipe Job、active working copy、稼働GUIを集計。
GUIの未確定runtimeはworking/recoveryのpinを優先し、未指定ならscene current revisionを読む。
不明/不正/他owner等でpinを解決できなければ全版の削除を拒否。期限超過だけでactive参照を外さない。
managed/external両previewのlive_reference_countをin-process+durable合計にし、内訳も追加。
これは参照数でありdistinct process数ではない。内訳もfingerprintへ束縛する。
旧previewは再取得が必要。削除済みregistryのjournal回収は既存経路を維持する。

managed preview/受付/削除本体をworker threadへ移し、private WS/standalone双方でawait。
開始済み受付/削除threadはrequest取消で放棄せず、durable operationとtaskを追跡する。
stopは受付threadの引渡しを待ってから実行taskを回収。Store通知先のSessionSubscription.deliverは
call_soon_threadsafeを使用していることをコードで照合した。公開contract/Host/frontend変更なし。
GUI受付/working-copy新規作成と削除commit間の全競合排他はまだ残件。
既定のproject拒否を維持し、確認付き削除は公開していない。

追加testはGUI全9 state、復旧/作業copy pinと期限、壊れた/不明pin、Job全5 state、
後から増えたdurable Jobによるfingerprint拒否、受付/削除threadの取消後完了。
初期focusedは49 passed/既知warning1。不正working_idの空listもfail-closedに追加し、
同module再実行25 passed/既知warning1。初期全gate1109 passed/289.27秒。
最終コードの `./mf.sh test`: 1110 passed/既知warning1/172.49秒。diff check成功。

実行: `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_runtime_removal_e2e.py
--live-references-only --evidence-dir /data1tb/mf-durable-runtime-references-20260906`。
既存専用clean setup領域のみ、source appの実loopback HTTP/実Blender GUI。
34.140秒passed/exit0。実session blendersession_01ee2af865aa4b709c4315d41c6c0cdb、
4.5.9/ready時はin-process0、durable sessions1/working_copies1、live合計2。
停止後は全durable0/live0、project参照1は保持。正規fingerprint付きremove POSTは
両状態で422/blender_runtime_in_use。今回旧版はactiveでもあり、liveだけが拒否理由とはしない。
GUI unitは停止後inactive/MainPID0。RFB接続・画面・入力はこのsliceでは未実施。

scene_2642c93f480d427d920267ac790405e2の全scene/revision/Asset metadataと、
immutable全6ファイル（.blend434663B/GLB1936B/ZIP44745B/provenance3件）のsize/SHA前後一致。
具体hashはobservations.jsonに記録。個別画像Assetはこの領域にない。
live-references-onlyではruntime切替・削除・再導入は行わない。
Host/MF unitはactive/PID250878・244551。こちらから本番restart/updateを要求していない。

実機のGUI準備中pin未確定を狙った競合、削除commitとの排他、確認付き履歴削除、
正確な同版再導入、installed Host/browser、新署名releaseはNOT TESTED。
次はGUI/working-copy受付と削除commitの排他をworker-thread境界で整合させる。
該当経路はBlenderSessionManager.create/_prepare、SceneWorkspace.acquire_working_copy/
acquire_recovery_working_copy、およびappのprivate WS/HTTPとmaterial previewからの呼出。
3DS-8/scenario DはPARTIAL、稼働版0.28.34へ新機能を導入したとは扱わない。

## 2026-09-06 recipe admission runtime pin

PR #321 merged `1a5bc35f4a37307867821f86039be5f1c1c55010` をfetch確認。
branch `ux1/3d-recipe-admission-pin`。runtime設計§4.1の受付中保護を実装。
SceneWorkspace.acquire_recipe_runtimeは削除と同じguard内で版選択と参照取得を行い、
guardを離してから参照だけを返す。呼出と解放はasyncio.to_threadへ移した。
Host child応答待ち→実行slot待ち→Blender処理/取消cleanupまで同じ参照を保持する。
受付taskもmanagerが追跡し、stopで取消・回収する。実行taskのfinally開始を確認してから
submitが返り、wait_cleanupは参照解放まで待つ。公開契約/Host/画像/G8変更なし。

focused `tests/test_scene_recipe_runtime_pin.py tests/test_scene_recipe_jobs.py
tests/test_scene_agent_api.py`: 29 passed/既知warning1。
追加6 casesは実resolverとfixture worker/Hostで、Host待機中のactive切替・登録解除拒否、
成功/不正応答/取消/stopでの参照解放、取得thread待ち取消、slot待ちとworker後片付け中の保持。
全gate `./mf.sh test`: 1085 passed/既知warning1/163.01秒。

実行: `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_recipe_runtime_pin_e2e.py
--evidence-dir /data1tb/mf-recipe-admission-pin-20260906
--managed-root /data1tb/mf-long-setup-source-20260906/runtimes/blender
--legacy-root /data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/runtimes/blender/blender-4.5.9-linux-x64`。
1.801秒exit0。新しい専用data/registryだけを書込み、既存runtimeは読取参照。
遅延Host応答は明示fixture、Blender batchと独立scene/GLB検査は実4.5.9 process。
Host待ち/slot待ちのlive参照は各1、active切替後も登録解除はlive referencesで拒否。
job_5bba3ed09faa4a748509c23691d2edd3 succeeded、元のmanaged runtime/version pin維持。
scene_fba79736625f4109a88f926a850d491eの初版を確定、終了後live参照0。
.blend426,899 B SHA c4c25d2c436de9437b86ce9e9a3d70ba6786a859c81255e84f1410a6c60f6b0b、
GLB1,756 B SHA a9a481e36f7508a853767920c73bb42d2a541ddfbd9a956b6afb132a8a0d3e20。
実binary SHA de8e8092c49e42cc6f1adde86aea0202ea5bad3338725887ecbcb7274dd0f926は前後不変。
これはdomain/実process受入であり、HTTP/Settings/installed Hostの受入ではない。
Host/MF user unitは照会時active/PID250878・244551。本sliceからrestart/updateは要求していない。

確認付き履歴削除、GUI/working-copy/queued recipeのdurable集計、同版再導入は未実装・NOT TESTED。
今回のin-process pinだけでscenario Dを完了にしない。新release/installed回帰もNOT TESTED。
次はdurable参照集計とruntime管理側のworker-thread化を進め、GUI準備中の未確定pinも保護する。
全体3DS-8/scenario DはPARTIAL。

## 2026-09-06 scenario D stopped-runtime removal policy

PR #320 merged `da4e54bfcd93d7aa36552b88ef9c0604428eceed` をfetch確認。
branch `ux1/3d-runtime-history-removal-policy`。今回は設計文書のみ。
base-plan §12を先に更新し、runtime設計§4.1とscenario Dを整合させた。
保存済み履歴参照は既定拒否を維持し、同版再導入が可能な停止済みmanaged版だけに
明示確認付き削除を追加する。画像/scene/全revision/pin/provenanceは一切書き換えない。
active/待機/実行/保存/停止処理の参照は確認でも迂回しない。外部実体の削除権限は増やさない。

根拠は実コードと前slice実測: Store.scene_runtime_reference_countは全scene_revisionsを
COUNT(DISTINCT scene_id)し、BlenderRuntimeManager.remove/_removeはproject_referenceを
理由に拒否する。GUI停止後も旧版Aを削除できないため、scenario Dの条件と差がある。
BlenderRuntimeResolver.live_reference_countはin-process参照のみであり、
GUI/queued recipe/active working copyは別のdurable集計が必要。
Storeにはblender_web_sessions/scene_working_copies/scene_recipe_tasksのruntime列がある。
SceneRecipeJobManager.submitはruntime選択後にHost child作成をawaitするため、
新しい確認付き削除を公開する前にその受付区間のpin保持も照合する。

選択理由: 永久拒否はD未達、履歴削除はGOAL-07違反、自動pin変更はimmutable/reproducibility違反。
追加確認と正確な同版再導入を一体で実装する。確認は既定off/backend強制/再検査、
operationへ永続化、取消/再開を含め実機受入する。既存remove入力の既定保護は維持する。
現在の製品実装は変えていない。0.28.34の既存拒否を新機能の成功に読み替えない。
実装/新テスト/実機削除/再導入はNOT TESTED。文書リンク・節番号・diff checkのみ確認。
次はdurable参照集計とJob受付区間のpin保護を実装し、確認付き削除の前提を固める。
全体3DS-8/scenario DはPARTIAL、稼働版は前sliceで確認した0.28.34のまま（本slice更新なし）。

## 2026-09-06 v0.28.34 signed release and installed Settings regression

PR #319 merge/tag target `f806f54609e34924086887744ae30d6852aec297`。
exact detached worktree /data1tb/ControlDeckMediaForge-release-0.28.34で
`python3 scripts/build_release_bundle.py --version 0.28.34
--output-dir /data1tb/mf-0.28.34-build-20260906
--pyinstaller /data1tb/ControlDeckMediaForge-3ds4/runtimes/bundle-build/.venv/bin/pyinstaller`。
PyInstaller6.22.0/Python3.12.3、ビルドexit0。artifact31,504,675 B、
SHA ac56e35a25dc1047e8207674d9e0edbe26344fe730c0d62e1bc913eb507c0d8e。
外側archive6 entriesはlauncher/core/両manifestとdirectoryのみ。Blender/weights/venv同梱なし。
展開先 /data1tb/mf-0.28.34-package-eLdLkz、addon/feature/core doctorの0.28.34一致。

既存専用external test data /data1tb/mf-external-settings-QEvrmAでpackage PID240632/9161。
公開前の同一artifactから `scripts/3ds_external_settings_e2e.py
--evidence-dir /data1tb/mf-external-settings-package-0.28.34-20260906` を実行。
Host診断Playwright Python/実headed ja、1280/320で確認取消→解除→reload→明示再登録、
managed active維持、横overflowなし/errors0、7.944秒exit0。320px screenshotを目視。
script内mode文字列はsource_standalone_headedのままだが、接続先は上記package実process。
同外部inventoryを再読し5,580 files/1,168,332,155 Bのsize/SHA/mode等の前後一致。
専用PID240632 SIGINT/package handle exit0、port9161解放。全環境clean installではない。

最初の署名commandはMF core Pythonにcryptographyがなくimport失敗（鍵読取前）。
依存を追加せず、既存Host診断Pythonで同sign_release.pyを実行し署名/自己検証成功。
既存publisher keyのみ、公開鍵80bNiqW1CzAzQ3LSqYqtwecm6TYQywDLxGACF9AVsac=。
GitHub Release v0.28.34へartifact/checksum/manifest/signatureの4 assetを正規公開。
/data1tb/mf-0.28.34-public-20260906へconsumer再取得、実bytes/build一致/size/SHA照合。
Host trusted catalogの_verify_signed_releaseで署名・identity・version検証、
GitHub tag refがexact merge targetと一致。release notesに旧registry snapshot復元条件を掲載。

更新前の本番396 Jobs全終端（262 succeeded/126 failed/8 canceled）、
GUI23終端（17 stopped/4 interrupted/2 failed）、runtime ops3 ready/model ops0。
private backup /data1tb/mf-0.28.34-pre-update-20260906はDB2,076,672 Bとregistry、mode0600。
標準registry.updateは17.353秒、0.28.33→0.28.34/healthy/enabled/requested_enabled=true。
current→versions/0.28.34、MF PID244551 active、Host PID2078不変。
installed/package core SHA 3ef34604e51d44950721b27fee1fbbbdfc0fd1ace90c58be21736bb826538ce5が一致。
runtime registryはbackupと実bytes一致、active4.5.13/managed2版のまま。Job/session件数不変。

実installed `scripts/3ds_settings_protection_installed_e2e.py --expected-version 0.28.34
--require-readable-layout --require-touch-targets --locale {ja,en}
--evidence-dir /data1tb/mf-settings-{ja,en}-installed-0.28.34-20260906` を順番に実行。
両exit0、opaque origin null/Host-child locale一致、1280/320で実pointer/dialog表示、
旧版project参照2/新版active+project参照23による削除保護、runtime status全体不変、errors0。
320px client/scroll305、文字領域255、button高さ44。英語320px確認画面を目視。
専用loginは各scriptでfinally revoke、既存password不変。runtime削除送信なし。
本番legacy登録は存在しないため、外部解除のinstalled受入には読み替えない。
外部操作のpackage日本語は受入済み、installed外部/英語外部/locale切替/全D/FはNOT TESTED。
版準備全gate1079 passed/既知warning1/154.26秒。今回追記は実測文書のみ。
次はscenario Dの停止後旧版削除とproject pin保護の差を設計・現行実装で解消する。
全体3DS-8はPARTIALを維持。

## 2026-09-06 v0.28.34 external registration release preparation

PR #318 merged `7c6dfb9dbeaa6059c6934633f6d80700cc1f2be9` をfetch確認。
branch `ux1/3d-external-v02834`、addon/coreを0.28.34へ同期。
外部legacy登録解除の永続抑止・明示再登録・設定UIと参照保護を配布する版準備。
公開latest v0.28.33、Host標準registry.statusでinstalled0.28.33/healthy/enabled/
requested_enabled=trueを確認。本番runtime registryはmanaged4.5.9/4.5.13のみ、
active4.5.13、legacy登録なし。試験都合で本番のexternal登録を作らない。

0.28.34の署名bundle公開/consumer再取得/標準update/installed受入はまだNOT TESTED。
次はexact merge headからbundle構築、専用packageで外部解除/再登録を受入し、
署名公開・標準update・installed既存Settings回帰へ進む。
旧coreへrollbackする際、外部解除の抑止fieldを使用済みならruntime registryの
事前snapshotも復元する（旧coreは未知fieldをfail-closed拒否）。
全体3DS-8/scenario D/FはPARTIALを維持。
版準備gate `./mf.sh test`: 1079 passed / 既知warning1 / 154.26秒。diff check成功。

## 2026-09-06 external registration Settings and guarded management

PR #317 merged `22800333d2866c3616c1c57fcfba7828756f2d35` をfetch確認。
branch `ux1/3d-external-registration-settings`。
BlenderRuntimeManagerにexternal preview/登録解除/再登録を追加し、private WSと
standalone HTTP双方へ接続。新メソッドはblender.runtime.unregister.preview/unregister/register_legacy。
任意path/URL/versionは受け取らず、固定configured legacy IDのみ。
確認fingerprintとactive/live/session/project参照を実行直前に再検査する。
他のruntime operation稼働中は拒否。同期DB/registry処理はasyncio.to_thread内、
取消でも開始したatomic writeの終端を待つ。外部実体のremove/repair/installを呼ばない。
登録変更は短いatomic操作でdownload journalを新設しない。応答喪失時はregistry statusで復元する。

設定のlegacy行へ「登録解除」、確認dialogへ外部ファイル/画像/制作物/履歴を変更しない説明を追加。
解除中だけ「既存環境を再登録」を表示。日英文字列/既存dialog/320px layoutを再利用。
managed削除・公開agent/workflow/schema・Hostコードは変更なし。docs/api.mdへprivate操作を記録。

受入専用source root `/data1tb/mf-external-settings-QEvrmA`、port9161/PID222538。
core Pythonのinline setupで新しいdata/registryを作り、前sliceと同じ二つの既存受入runtimeを
読み取り参照。外部inventoryをexternal-before.jsonへ保存後、uvicornを起動。
実行: HostのPlaywright可能な診断Pythonで
`scripts/3ds_external_settings_e2e.py --evidence-dir /data1tb/mf-external-settings-browser-20260906`。
DISPLAY=:0/XAUTHORITYは既存user session。製品へHost import/venv共有を追加しない。
実headed Chrome/日本語、1280x600と320x600で確認→取消→解除→reload→再登録、
active/G8のmanaged4.5.9維持、横overflowなし、page errors0。5.973秒exit0。
confirmation-320.pngを実画像で確認。ブラウザ内JSでactionやdialogを代行しない。
終了後MF core Pythonで同外部inventoryを再計算し、5,580 files/1,168,332,155 Bの
size/SHA/modeとdirectory/link一覧が前後一致。新download・既存runtime/registry変更なし。
専用source PID222538へSIGINT、元toolのexit0を確認。本番へのrestart/update要求なし。

追加7 testsはHTTP active拒否/解除再登録、確認後のproject増加、任意path/managed ID/
確認不足の拒否、worker thread実行と取消後完了、busy拒否。project増加はunit fixture。
実DBの制作物参照を伴うbrowser拒否、installed Host opaque iframe、英語/locale切替、
dark/light変更、長時間認証、任意外部版はこのsliceでNOT TESTED。
全gate `./mf.sh test`: 1079 passed / 既知warning1 / 166.62秒。
`node --check frontend/app.js`、diff check成功。
次はこの管理UIを含む署名版を正規公開/導入し、installed日英Settingsの同操作を確認する。
旧版rollback時のregistry snapshot復元条件（#317）は維持。3DS-8全体はPARTIAL。

## 2026-09-06 external legacy registration persistence foundation

PR #316 merged `c3d1aad1945634c2be980a91de9af62971300bc3` をfetch確認。
branch `ux1/3d-external-registration-state`。
resolverにunregister_legacyと明示register_legacy(explicit=True)を追加。
外部実体は変更せず、registry row除去とlegacy_registration_disabled=trueを
既存staging/fsync/atomic replace一回で保存。status/startupの再検出は抑止を尊重する。
active/live参照は拒否、壊れた外部stampの明示再登録はfalseで抑止を保持。
project pin/fingerprintを扱うorchestratorとUIは次sliceであり、まだ公開操作は追加しない。
同期registry primitiveはworker threadで呼ぶ前提。新async request経路は追加していない。
statusに加法的private field、agent/workflow/公開schemas/Hostは変更なし。
旧registryはそのまま読める。新抑止fieldを持つregistryは旧coreがfail-closedで拒否するため、
旧版rollbackでは事前registry snapshotも復元する要件をruntime設計へ明記した。

実機script `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_external_registration_e2e.py
--evidence-dir /data1tb/mf-external-registration-20260906` はexit0 / 5.129秒。
新しい専用registryのみ書込み。外部参照は既存受入用
/data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/runtimes/blender/blender-4.5.9-linux-x64、
代替managed参照は別の既存受入用/data1tb/mf-long-setup-source-20260906/runtimes/blender。
両領域の既存registry/実体、本番環境は変更しない。新downloadなし。
実4.5.9/background/glTF import/export probeは解除前/明示再登録後とも成功。
解除→resolver再作成/status/自動登録でlegacy非復活、managed active/G8維持、
明示再登録後のみlegacy復活を確認。registryに外部生pathを保存しない。
外部6,511 entries中5,580 files/1,168,332,155 Bの実size/SHA/modeとdirectory/link一覧が
解除後/再登録後に前後一致。observations.jsonへ全inventoryとprobe/statusを保存。

追加unit testsは抑止永続化/明示復帰、active/live拒否、壊れたstamp、
atomic replace失敗時の旧registry保持、不正bool4例、lock symlink拒否。
全gate `./mf.sh test`: 1072 passed / 既知warning1 / 152.45秒。diff check成功。
実file probe/hash証拠とは別で、GUI/HTTP/Settings受入の代用ではない。
任意外部版・公開管理・project参照保護との統合・signed release/installedはNOT TESTED。
次は同primitiveをworker threadで呼ぶproject参照/fingerprint付き管理操作と、
設定の登録解除/再登録導線へ接続する。全体3DS-8/scenario DはPARTIAL。

## 2026-09-06 runtime removal protection and immutable asset hashes

PR #315 merged `6899713922c3b75232a51514062eb2b777fac9bb` をfetch確認。
branch `ux1/3d-runtime-removal-evidence`。製品/Host/公開契約変更なし。
新 `scripts/3ds_runtime_removal_e2e.py` は専用領域
`/data1tb/mf-clean-packaged-0.28.32-QBvHfm` のみをsource app/実HTTPで操作する。
実行: `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_runtime_removal_e2e.py
--evidence-dir /data1tb/mf-runtime-removal-resume-20260906`。exit0 / 2.008秒。
GUI `blendersession_fb98414ac7dd429c8c6164a02a0d1428` は旧4.5.9/ready。
既定を4.5.13へ切替後、旧版remove_previewはactive=false/project_reference_count=1、
can_remove=false。正規fingerprint付き実remove POSTも422/blender_runtime_in_use。
GUI停止後も同project保護で422。scene revisionを消して保護を迂回しない。

既定を旧4.5.9へ戻し、未参照4.5.13のpreviewを取得、正規removeを実行。
op `blenderop_e14ed351d27b40628fcbd8d1a734ced1` ready、removed_bytes=1,167,187,993。
新版managed directory消失、旧binary存在、registry/activeは旧版だけ。
同scene/document/全revision/Asset API metadata前後一致。
assets配下全6ファイル（blend434,663 B、GLB1,936 B、ZIP44,745 B、provenance3件）
を実bytes SHA-256/sizeで前後照合。具体hashは同証拠observations.jsonへ保存。
個別画像Assetはこの領域にないため画像実bytes保持の受入とは呼ばない。
systemd user unitはinactive/MainPID=0、source app exit0。
削除したのは専用4.5.13のみ。保持済みarchiveから標準updateで再導入可能。

初回 `/data1tb/mf-runtime-removal-20260906` は1.869秒でassert失敗。
live_reference_countはin-process batch/working-copy参照数で、GUI readyでも0。
GUIの削除保護はproject_referenceに由来することをコードとHTTPで照合し、
想定を修正。同sessionの生存を確認して再利用した。GUI再作成や製品修正で代用しない。
今回RFB接続/入力/画面表示は未実施。既存probe受入とは別script。
hash verifierに内容・provenance変更、symlink拒否、空baseline拒否の3 unit testsを追加。
初期gate1060 passed/既知warning1/140.89秒。
最終gate `./mf.sh test`: 1063 passed/既知warning1/142.13秒。diff check成功。
本番Host PID2078/MF PID181914はactiveのまま（本sliceから再起動なし）。

scenario Dの「停止後A削除」はproject pin保護との未解決な差がある。
今回の未参照B削除をその条件の成功に読み替えない。
External解除はresolverのlegacy登録/managed解除拒否しか見つからず、公開登録解除経路は未確認。
次はExternal登録解除の設計・実装差分を確定し、外部実体を保持する管理操作を進める。
全体3DS-8/scenario DはPARTIALを維持。

## 2026-09-06 rejected candidate update preserves pinned Blender GUI

PR #314 merged `933ea4f0d0aa8867ca238747db130ae5edb5bb53` をfetch確認。
branch `ux1/3d-update-probe-failure`。製品/Host/公開契約の変更なし。
新script `scripts/3ds_update_probe_failure_e2e.py` は以前の専用clean setup領域
`/data1tb/mf-clean-packaged-0.28.32-QBvHfm`だけをsource appの実loopback HTTPで操作する。
これは署名installed版の受入ではない。fixtureは候補4.5.13の実Blender内で
background=falseのprobe JSONを返す。download/hash/展開/Blender binaryは実物。

実行: `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_update_probe_failure_e2e.py
--evidence-dir /data1tb/mf-update-probe-failure-final-20260906`。exit0 / 67.985秒。
同scene `scene_2642c93f480d427d920267ac790405e2`の
GUI `blendersession_6ac54af91f6d42ef9624f555624cefc8`へ実RFB handshakeし接続を保持。
34.094秒で候補op `blenderop_52dc8fe7d9e049049be4d8d4aba16312` failed、
blender_runtime_install_failed / Blender preflight result differs。
registry/activeは旧4.5.9だけ、旧版実background/glTF import/export probe成功。
正常probeへ戻して再試行op `blenderop_66687a8ca2ba46d7915ed0fa59bc4600`は
67.188秒時点ready、既定4.5.13でも既存GUIは4.5.9/ready/connectedのまま。
候補archive378,033,952 B、SHA da4e69b06b75b9e642d106496c50e7e240218b411d2f6e18271c1d1d819cef91。
取得済み検証済みarchiveを使用。旧binary SHA
de8e8092c49e42cc6f1adde86aea0202ea5bad3338725887ecbcb7274dd0f926が前後一致。
scene/Asset API metadata前後一致。全Asset実bytes hash比較とは呼ばない。
最後にGUIを保存せずstopped、既定を旧版へ戻した。新版は導入済みのまま。
追跡したsystemd user unitはActiveState=inactive/MainPID=0。source serverもexit0。

途中のscript失敗を保持: 初回sessions/items key誤り、続行時の重複session HTTP422、
実download完了後のfixture version_string比較によるbounded JSON不在、
RFB binary subprotocol不足のHTTP403。最終scriptは同scene既存sessionを再利用、
version tupleを照合しbinary subprotocolを指定した。製品障害修正とは扱わない。
証拠は /data1tb/mf-update-probe-failure{,-retry,-resume,-rfb,-final}-20260906 に保持。
RFB handshakeは実browser画面表示/入力/保存や認証期限更新の証拠ではない。
全gate `./mf.sh test`: 1060 passed / 既知warning1 / 147.82秒。
次はscenario Dの参照中削除拒否・停止後の対象限定削除と実Asset hash保持を同領域で検証。
External解除/容量不足等を含むscenario D全体、3DS-8全体はPARTIALを維持。

## 2026-09-06 Blender-absent real image generation and Library

PR #313 merged `9dc22b7fa542d759291a3fb001b1f5d001aed2fd` を確認。
branch `ux1/3d-no-blender-real-image`。
新scripts/3ds_no_blender_image_e2e.pyは既存署名0.28.33専用processへHTTPを送り、
実model provenance/PNG/hash、Blender不変を確認する。製品/Host/契約変更なし。
専用root `/data1tb/mf-no-blender-real-0.28.33-xLNyee`、feature/cache/absent-legacy、
port9161、package `/data1tb/mf-0.28.33-package-dOeUsF/control-deck-media-forge-0.28.33-linux-x86_64/bin/mediaforge`。
画像だけ既存MF管理venv
`/data1tb/ControlDeck/data/feature-data/media-forge/runtimes/rocm-torch/.venv/bin/python`と
HF_HOME `/data1tb/ControlDeck/data/cache/huggingface` を明示参照。
Blender runtime/operation0、active null、base/web missing。新重み取得/provisionなし。

認証setupはHost診断Pythonで既存mf-e2eのactive/workflows.runを確認し、
Host proxy標準_service_headersで短命service credentialを発行、子MF core Pythonの
MF_ACCEPTANCE_AUTHORIZATION環境変数だけで渡した。tokenを印字/証拠/global configへ保存しない。
repo内の新scriptはHost内部をimportせず、実Host introspection/Job/Brokerを使用。
これは診断用に発行した有効権限であり、通常installed browser/proxy認証の受入ではない。
script command: --evidence-dir /data1tb/mf-no-blender-image-0.28.33-20260906。
実POST /addon/v1/workflow/execute、image.generate/auto/256x256/steps4/seed73/local_only。
local Job `job_a6ea97330a684034bf4404a6a3e82cde`、
Host Job `0b952daf7e20`、449.484秒exit0。
73.346秒waiting_resource、75.351秒starting、76.356秒running/generating、
449.458秒succeeded。遅延の内訳は未診断。再投入・性能設定の変更なし。

Asset `asset_1a1a19d02f344caa8d7f738ef7c75cc2`、
PNG45,160 B、SHA `1ed7bf93ca6c4c0d3ed50aac7ad90c04288d0cf3dfffac38f397ee701e6ba542`。
実PNG decode/256x256/asset-provenance-output hash一致、実画像を目視（青い陶器cube）。
diffusers.flux2-klein0.40.0/FLUX.2-klein-4B/Apache-2.0、
weights SHA f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278。
Blender status API全体前後一致、Library assetsは生成した1件のみ。
同専用packageの実headed Chrome日本語320pxで/library直開き、画像1件/空表示なし、
naturalWidth/Height160、page errors0。library-320.pngを目視確認。
ブラウザ観測は診断inline Playwright、出力は同dir/library.json。

実Host DBの対象Job/auditだけをhost-terminal.jsonへ記録しsucceededを照合。
Resource request `f8e5901e-d589-49a0-9abc-57637c164c92`、
lease `7d35d2de-4126-43b2-b48d-68e25a4380fd`、
request1/activate1/renew36/release1がsuccess。
専用loginから実GET /api/v1/resourcesで対象Jobだけを抽出しresource-receipt.jsonへ記録、
gpu0/shared-safe/26,048,477,593 B、lease releasedを確認。login finally revoke。
実GPU total34,208,743,424 B、観測時used21,136,957,440 B（peakとは呼ばない）。
image worker PID189754は終端確認時に消失。
package PID187688は停止確認時すでに消失、tool exit143と正常shutdownログ。
その後のSIGINT送信はNo such process。停止発信元未確認であり自分のSIGINT成功とは書かない。
本番Host2078/MF181914はactiveのまま。

Blender不在で実画像→Libraryまで利用できる範囲を追加確認。
画像runtime/HF cacheを流用した専用packageであり、全環境clean install、
通常Host初回セットアップ、scenario A/F全体は未完了。
449秒の実Jobを、全GPU組合せやcredential refresh成功へ読み替えない。
次は完了監査の残条件を再照合し、runtime更新/停止/再開の未受入条件を進める。
全gate ./mf.sh test: 1060 passed/既知warning1/162.93秒。diff check成功。

## 2026-09-06 image-upload graceful disconnect gate

PR #312 merged `b22cd61e7d1466967381bf419017c56fdcda6c08` を確認。
branch `ux1/3d-image-disconnect-gate`。前sliceで記録した画像uploadの残件を扱う。
既存test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_upは
context exit（Starlette側のASGI cancelを伴う）の後で最大5秒cleanupを待っていた。
#309のscene側と同じく、graceful close処理と強制cancelを区別する。

画像testもsocket.close()を明示送信し、同socket context内でwork_dirが空になるまで
最大5秒観測するよう変更。テスト側同期threadだけで既存50msのfilesystem pollを行い、
app asyncへwait/sleepは追加しない。import APIの再試行も行わない。
close前には未完了uploadが存在することをassertし、空状態だけの自明な成功を防ぐ。
既存1MiB超chunk transport、PNG512x512 import、incomplete拒否のassertは維持。
製品/Host/公開契約/依存変更なし。forced ASGI cancellationの耐性を修正したとは扱わない。

対象画像test+scene transport fileの3 tests pass。
今回の変更はtest前提の補正であり、実ネットワーク切断や画像生成の実機受入ではない。
installed0.28.33と前sliceの実機証拠は維持し、3DS全体はPARTIAL。
次はBlender不在の専用packageで、Hostが受理する利用者/Job権限とBroker leaseを通した
実画像生成を検証する。standalone認証省略やfake出力で代用しない。
全gate ./mf.sh testは1060 passed/既知warning1/156.61秒。diff check成功。

## 2026-09-06 v0.28.33 signed release and standard update

PR #311 merge/tag `0fb8e1141a8b7aa2e3d5eb21a0d08d51039bf8b5` をGitHub refで照合。
exact detached worktree `/data1tb/ControlDeckMediaForge-release-0.28.33`から
`python3 scripts/build_release_bundle.py --version 0.28.33
--output-dir /data1tb/mf-0.28.33-build-20260906
--pyinstaller /data1tb/ControlDeckMediaForge-3ds4/runtimes/bundle-build/.venv/bin/pyinstaller`。
exit0、tar31,499,472 B、SHA
`e9ddc9c23d3eccaa2b876130dc273b2f08c9d80f8932ad9bc3ca1e5f52ff5e1b`。
外側6 entriesはlauncher/core/addon/featureのみ。Blender binary/model/venvなし。
専用展開 `/data1tb/mf-0.28.33-package-dOeUsF` でaddon/feature版0.28.33、
packaged doctor status ok/version0.28.33を照合。

既存正式publisher鍵でsign/self-verify、v0.28.33へ4 assetsを公開。
consumer download `/data1tb/mf-0.28.33-public-20260906` はHost trusted catalog
_verify_signed_releaseと実size/SHA、build bytes一致を確認。Hostコード/鍵変更なし。
同packageの専用doctor-feature/doctor-cache/absent-legacy/port9161でserve（PID174225）。
`scripts/3ds_standalone_routes_e2e.py
--evidence-dir /data1tb/mf-standalone-routes-package-0.28.33-20260906`、
既存Host診断venv/実DISPLAYとXAUTHORITY、headed Chrome日本語1280/320px、
exit0/48 checks。9 routes直開き/reload、back/forward、重複historyなし、
Jobs/assets/runtime/sessions前後不変、page errors0。320px screenshot目視確認。
HTTP/JS overlayなし。専用serverはSIGINT後exit0。

更新直前の本番jobs396全終端、GUI23全終端（failed2/interrupted4/stopped17）、
runtime operations3ready/model operations0をDB読取で確認。
online DB backup `/data1tb/mf-0.28.33-pre-update-20260906.sqlite3`
0600/2,076,672 B後、Host標準registry.update('media-forge')で0.28.32→33。
29.624秒、healthy/enabled/requested_enabled=true、
current→versions/0.28.33、MF PID181914 active/Host PID2078不変。
installed/package core SHA両方
`22d154e4c41598148205bb567314681cc6ec97e81a6eba169dbc17b97e058ccd`。

installed回帰: 実Host診断venv/PYTHONPATH/config、DISPLAY/XAUTHORITYで
scripts/3ds_library_navigation_installed_e2e.py --scene-id scene_a94df57d689d4636844b3586dd9fed7d
--expected-version 0.28.33 --require-scroll-lock --locale ja
--evidence-dir /data1tb/mf-library-ja-installed-0.28.33-20260906、exit0。
実headed Chrome/opaque iframe/overlayなし、Host/子lang ja、両幅image6/GLB8/blend9表示、
親子双方向移動、metadata移動model reads0、明示GLB表示、scene不変、page errors0。
320px root/viewer client/scroll全320、root overflow hidden。実GLB screenshot目視確認。
専用mf-e2e loginはscript finallyでrevoke。ユーザーパスワード変更なし。
日英live切替・全素材paging・他必須受入をこの日本語runで成功扱いしない。
次は残る画像upload disconnect gateとBlender不在の実画像生成経路を進める。

版数PRの全gateは1060 passed/既知warning1/148.61秒。
本sliceは配布/受入文書のみで、全testを再実行したとは記録しない。
修正済み単体routeのsigned package受入と標準更新を確認したが、全3DSはPARTIAL。
Blender不在での実画像生成、画像upload TestClient強制cancelの残件、
他の必須A〜Fはこのreleaseによって完了へ読み替えない。

## 2026-09-06 release 0.28.33 preparation

PR #310 merged `07703a3a6636dc291e87e11813203f67b60cd12a` を確認。
branch `ux1/release-0.28.33`。単体起動のdirect URL/history修正を配布する版数更新。
addon/coreを0.28.33へ揃える。DB/runtime/公開契約変更なし。
現行installedは0.28.32/healthy/enabled/requested_enabled=trueをHost標準statusで確認。
修正sourceの48 browser checksは前sliceに記録済み。新bundleの公開/導入はまだNOT TESTED。
次は通常mergeのexact headからbuild、既存正式鍵で署名公開、consumer再取得検証、
専用packageで同48 checks、標準Host updateと稼働版照合を行う。
3DS全体と残る必須シナリオはPARTIALを維持する。
gate ./mf.sh test: 1060 passed/既知warning1/148.61秒。diff check成功。

## 2026-09-06 standalone direct routes and browser history

PR #309 merged `33c18588abccdc0ac6253b7574c7cee7a6784f48`。
branch `ux1/3d-standalone-routes`。専用stashのroute変更を復元済み。
frontend/app.jsは単体起動の初期画面をURLから選び、last_viewより優先する。
既存/jobsはActivity、/modelsと/profilesはSettingsへ対応。/と/createはCreate。
ナビ移動は同じpathなら履歴を増やさずpushState、popstateはsync:falseで表示だけ更新する。
Host iframeのhost.route.sync/route.changedと既存初期preferences経路は変更していない。
API/依存/公開契約/Blender実行処理の変更なし。

前回signed0.28.32の/library直開き失敗を根拠に修正。
source serverは既存専用 `/data1tb/mf-no-blender-0.28.32-jODjIO/feature/data` を使用、
MEDIA_FORGE_BLENDER_MANAGED_ROOTを同feature/runtimes/blender、
MEDIA_FORGE_BLENDER_LEGACY_ROOTを専用absent-legacyに指定。
`PYTHONPATH=backend .venv/bin/python -m uvicorn mediaforge.app:create_app --factory
--host 127.0.0.1 --port 9161`（PID144938）。製品source、HTTP応答/JS overlayなし。
既存Host診断venvのPlaywrightで実headed Chrome、DISPLAY=:0/実XAUTHORITY、
`scripts/3ds_standalone_routes_e2e.py --evidence-dir /data1tb/mf-standalone-routes-source-20260906`、
exit0/48 checks。日本語1280/320pxで9 routes直開きとreload、Library→Web Blender→Activity、
back2回/forward、同一tab再click時history.length不変をassert。
Jobs/assets/runtime/sessions API前後完全一致、page errors0、320px screenshot目視確認。
移動でBlenderやJobは開始しない。source PID144938はSIGINT後exit0。

最初のroute全testは1059 passed/1 failed/153.27秒。
切断testのscene_upload_busyは別PR #309でgraceful closeのtest前提を修正し、製品変更とは分離。
関連frontend tests153件pass。#309統合後の全gateは1059 passed/1 failed/161.27秒。
今度はtest_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_upが失敗し、
orphan画像uploadのwork directoryが残った。これもcontext終了によるASGI cancel後に
cleanupを待つtestであり、画像側は#309の修正範囲外。未解決として保持する。
本sliceはsource受入であり、修正の署名package/installed受入はNOT TESTED。
次は版数更新と署名配布後、同route scriptで公開packageを検証する。
Blender不在での実画像生成と残る必須シナリオは未完了。3DS全体はPARTIAL。
最終全gate再実行は1060 passed/既知warning1/140.78秒。node --checkとdiff check成功。
再実行の成功を画像upload切断testの根治扱いしない。本番PID2078/60180は不変。

## 2026-09-06 deterministic graceful-disconnect transport gate

PR #308 merged `f52c3eb2833ade09718b689880da4700795d7a74`。
route修正のsource Chrome受入は48 checks pass、
`/data1tb/mf-standalone-routes-source-20260906`（1280/320px、直URL/reload/history、
Job/assets/runtime/sessions前後不変）。ただしroute変更はまだ未commit/未配布。
作業は専用stash `owned standalone route slice pending transport gate` に保持し、
branch `ux1/3d-transport-disconnect-gate` で既存testの切断gateを分離。

route全testは1059 passed/1 failed/153.27秒。前回と同じ
test_authenticated_workspace_transport_imports_and_locks_without_paths のresumed result欠落。
read-only pytest pluginで応答をassertすると単独1回目に
scene_upload_busy / owner already has an active Blender uploadを再現。
現在のStarlette WebSocketTestSession.__enter__はcontext終了でclose送信後に
ASGI task cancel scopeをcancelする。MediaForgeのupload解放は複数awaitの後にあるため、
このテストはgraceful close完了と強制cancelを区別していなかった。

testを変更し、abandoned socketへ明示closeを送った後、そのupload IDのcancel_uploadが
実行されたthreading.Eventをtest側で最大5秒待ち、実IDを照合してからcontextを終了する。
appのasync内でwait/sleepせず、製品cleanupや認証・公開契約は変更しない。
resumed応答もokを先にassertして今後の失敗本文を保持する。
これは実ネットワーク/ASGI強制cancel耐性の修正証拠ではなく、graceful切断のtest前提修正。
本番Host/MFは変更なし。source PID144938はSIGINT後exit0。
次はこのgateを通常merge後、専用route stashを戻して修正PR・署名配布へ進む。
全gateは1059 passed/既知warning1/168.67秒。実行中にEvent通知を対象ID限定へ絞ったため、
その最終test本文は対象file2 testsを別に再実行しpass。diff check成功。

## 2026-09-06 Blender-absent image/Library preflight

PR #307 merged `2600ca325cfa645163f57fd0207e9938a3ed8885`。
branch `ux1/3d-no-blender-image`。新script
`scripts/3ds_no_blender_preflight_e2e.py` は認証/生成を代替しないread-only受入。
専用root `/data1tb/mf-no-blender-0.28.32-jODjIO` のfeature/cache、
absent-legacy、port9161で既存署名0.28.32 packageを起動（PID102366）。
画像だけ既存MediaForge管理venv
`/data1tb/ControlDeck/data/feature-data/media-forge/runtimes/rocm-torch/.venv/bin/python`
とHF_HOME `/data1tb/ControlDeck/data/cache/huggingface` を明示参照。
新runtime/重み取得なし。これは全runtimeが空のclean installではない。

実HTTPはBlender missing/runtimes0/operations0/active null、Web pack missing、
image.text_to_image available/local/measured、3d.scene_recipe unavailableを返した。
healthはHTTP200だがenvironment snapshot不在によるsetup_requiredでありhealthyとは記録しない。
実headed Chrome/日本語でLibraryナビをclickし空表示と種類filterを確認、page errors0、
screenshot目視確認。commandは既存Host診断venv（Playwright、Host importなし）で
`scripts/3ds_no_blender_preflight_e2e.py --evidence-dir /data1tb/mf-no-blender-preflight-retry-20260906`、
DISPLAY=:0/実XAUTHORITY指定、exit0。
最初の `/data1tb/mf-no-blender-preflight-20260906` は /library 直開きがCreateを表示してexit1。
frontend/app.js初期化はlast_view優先でstandalone pathnameをweb-blenderのみ解釈している。
ナビ移動の成功で直URL不具合を解消扱いしない。次の独立sliceで初期route/戻る進むを検証する。

画像生成はNOT TESTED。通常standalone /api/v1/jobsはHost executionを付与せず、
実model選択後host_lease_requiredで失敗する実装を確認。LLM gatewayのloopback免除と
Addon Runtimeの利用者/Job権限は別経路。Brokerを省略した生成やfake画像を実生成と見なさない。
本番Host/MF PID2078/60180は変更せず、専用PID102366はSIGINT後exit0。
scenario A/F、GOAL-01/03はPARTIALを維持。生成に必要な正規Host経路の検証は残件。
初回全testは1058 passed/1 failed/129.54秒。既存
test_authenticated_workspace_transport_imports_and_locks_without_paths の切断直後再接続で
resumed応答にresultがなくKeyError。単独再実行はpass。エラー本文がassert前に失われており、
原因は未確定。切断cleanupがupload解放前にawaitする実装は確認したが、raceと断定しない。
製品/test変更なしで全gate再実行は1059 passed/既知warning1/163.72秒。diff check成功。

## 2026-09-06 clean package G8 ZIP continuation

PR #306 merged `517673ce442484adabba9c7b3e1efca5db3a8ad1`確認。
branch `ux1/3d-clean-g8-package`。新 `scripts/3ds_clean_g8_package_e2e.py` と
synthetic verifier negative tests。製品/Host/公開契約変更なし。
前2sliceの専用data `/data1tb/mf-clean-packaged-0.28.32-QBvHfm` と
署名package0.28.32を同じfeature/cache/absent-legacy/port9161で再起動（PID74790）。
最初のHost診断venv実行はPillow不在でimport時exit1、副作用なし。
既存MediaForge core venv（httpx/Pillow）で実行し、Hostへ依存を追加していない。

command: `.venv/bin/python scripts/3ds_clean_g8_package_e2e.py
--evidence-dir /data1tb/mf-clean-g8-package-0.28.32-20260906`、exit0/1.065秒。
同scene `scene_2642c93f480d427d920267ac790405e2` の既存GLB
`asset_d8548f7e2e3548359b4656b9dddc4781` を入力に、
実HTTP POST /api/v1/jobs（202）、operation=asset.pack/profile=3d.project.glb、
triangle_budget12/output zip/local_only=true。Job `job_d4575fd7aab440f5945c87ecfa117f9f` succeeded。
生成Asset `asset_0ec65313251048e9bf8b12fabd31d426`、ZIP44,745 B、
SHA `f46afc3ea12d599396b7ce95502dac6416d7ef9267453e34f2d2bffac14f20ae`。

実ZIP3 entries、CRC、GLB/PNG/manifest size/hash、Asset/Provenance/元GLB参照hash、
compiler Blender4.5.9/1.1.0、PNG decode、GLB header/lengthを照合。
元GLBとZIP内GLBは共に1,936 B/SHA
`d6d61e731d1936825b450a527474864bd3df086ef4e8a3379907386f7d52c3ea`。
preview43,414 B/SHA `f46fa6e1e269705a6cea9de2370e3a5bf6f65543a1864dd38bce4a681d2424de`。
previewを展開してキューブを目視確認。manifestはmesh1/triangles12/vertices24、
bounds[-1,-1,-1]〜[1,1,1]。scene全体API前後一致、元GLB bytes不変。
read-only DBでもG8 Job succeeded、既存import Job succeeded。package PID74790はSIGINT後exit0。
本番Host/MFサービス、ユーザーglobal Blender/configは変更していない。

verifierはZIP bytes改ざん、parent欠落、reference hash不一致、manifest不一致の4 negativeを拒否、
整合するsynthetic fixture1件を受理する。これらは実機証拠とは分離する。
空Blender導入→web pack→GUI表示/終了→同素材G8 ZIPまで専用package環境で受入が進んだ。
scenario AのBlender不在での実画像生成/Library利用、installed Host初回導入はこのrunの範囲外。
次はBlender不在時の画像実行・Libraryの残条件と、Host Broker認証経路を確認する。
全体3DS-8/残る必須シナリオはPARTIAL。専用data/生成ZIPは証拠として保持。
gate `./mf.sh test`: 1059 passed / 既知Starlette warning1 / 111.70秒。diff check成功。

## 2026-09-06 clean package Web pack / real GUI continuation

PR #305 merged `04388c98a2b16ae8871a34e0a74cd85de5bd6302`確認。
branch `ux1/3d-clean-web-pack`。新 `scripts/3ds_clean_web_pack_e2e.py`、製品/Host変更なし。
前回の専用 `/data1tb/mf-clean-packaged-0.28.32-QBvHfm` と署名package0.28.32を
同じfeature/cache/absent-legacy/port9161指定で再起動（PID66056）。
導入済みの専用Blender `.../feature/runtimes/blender/blender-4.5.9-linux-x64/install/blender`
のfactory-startup/backgroundから `<root>/acceptance-cube.blend` を新規保存した。
最初にbin/blenderを指定したcommandは存在せずexit127、実配置を確認してinstall/blenderへ訂正。
既存利用者ファイル/production runtimeは変更していない。

実headed Chrome、日本語Settingsで同scriptに
`--blend <root>/acceptance-cube.blend --evidence-dir /data1tb/mf-clean-web-pack-browser-0.28.32-20260906`。
web missingから専用導入buttonをclick、7.034秒でready。
operation `blenderop_82248c9c0f944cb38510b6593dd74072`、
TigerVNC1.16.2/noVNC1.7.0、software_display probe成功。
実download15,769,716 B、2 archive実hashを独立照合:
TigerVNC15,042,988 B/SHA `5b70c84baefc09a030cfc78315c34ccb55b2a0dde4092b7da67a1962c5f0dea6`、
noVNC726,728 B/SHA `b1003a11b6e6e8d8f7f5e5586daae7f8ca651d8aee0aa155ff9ac841c48f52c6`。
展開165 members/35,067,968 Bと244 members/2,471,032 B。
UI importは10.752秒でscene `scene_2642c93f480d427d920267ac790405e2`、
revision `revision_498980e910484e38a621d2d5844bed03`（1版）。
実validatorはBlender4.5.9/mesh1/triangles12/vertices8、GLB構造passed/1,936 B。

初回scriptは起動後の自動画面openを誤って仮定し42.798秒でtimeout。
実UIは起動→ready→「Blenderへ戻る」の2段階。製品変更は不要と判断しscriptを訂正。
actionもweb専用名ではなくruntime_idで対象operationを識別、sceneDocumentのID参照を訂正。
元processを再起動せず、`--resume-scene scene_2642c93f480d427d920267ac790405e2` で
`/data1tb/mf-clean-web-pack-resume-0.28.32-20260906`へ再実行、exit0/1.919秒。
同session `blendersession_f218e5c939ea4d3594b30eaff34d9766` のRFB接続、
実Blender4.5.9/cube/通常GUIをscreenshotで目視確認し、UI「破棄して終了」でstopped/saved=false。
sceneは1版を維持、page errors0。公開session snapshotのgui_ready行は直前のdisconnected状態だが、
画面の接続表示/実framebufferと最終session.connected_atで接続を確認した。
systemd user unit `mediaforge-blender-f218e5c939ea4d3594b30eaff34d9766.service` inactive/MainPID0、
DBもstopped。基本/webの2 setup operationはready。
package PID66056へSIGINT後exit0。専用scene/runtime/archiveは次のG8 ZIP受入用に保持。

これは空Blender setupからの同一専用環境でのweb導入→import→GUI表示→終了を、
失敗/再開を含めて確認したもの。GPU描画、GUI編集保存、画像生成、G8 ZIP、
installed Host iframeのclean install、scenario A全体は未完了。
次は同じGLB `asset_d8548f7e2e3548359b4656b9dddc4781` からG8 ZIP生成と内容検証を進める。
source Assetは `asset_24d8b1a3e1654c4d9c4a18a7c046393e`。本番serviceは変更なし。
gate `./mf.sh test`: 1054 passed / 既知Starlette warning1 / 112.45秒。diff check成功。

## 2026-09-06 clean packaged Blender install / browser reconnect

PR #304 merged `f61e47dea0d2058b9357c57b24e74a5411282f65`確認。
branch `ux1/3d-clean-packaged-setup`。新 `scripts/3ds_clean_packaged_setup_e2e.py`。
製品変更なし。公開検証済み0.28.32 packageを、新規mktemp
`/data1tb/mf-clean-packaged-0.28.32-QBvHfm` の専用feature/cacheで起動。
`CONTROL_DECK_FEATURE_DATA_DIR=<root>/feature CONTROL_DECK_SHARED_CACHE_DIR=<root>/cache
MEDIA_FORGE_BLENDER_LEGACY_ROOT=<root>/absent-legacy MEDIA_FORGE_PORT=9161
/data1tb/mf-0.28.32-package-iYzsMs/control-deck-media-forge-0.28.32-linux-x86_64/bin/mediaforge serve`。
package PID62393、既存Blender/production registry/既存downloadを流用しない。
source appではなく配布済みcore/UI、standalone loopback。画像runtime provision/重み取得なし。
画像catalogには既存共有モデルのread-only情報も表示されるため、全モデルが空の環境とは呼ばない。

実headed Chrome/日本語Settingsへ、Host診断venv（Playwrightのみ）で
`scripts/3ds_clean_packaged_setup_e2e.py --evidence-dir /data1tb/mf-clean-packaged-browser-0.28.32-20260906`。
exit0/61.828秒。初期runtime0/operation0/active null/base missing/web missingと導入buttonをassert。
Settingsの基本環境導入buttonを実クリック。operation
`blenderop_d7a54c8bf2f648abbc716383caaae506` がdownloading中の1.227秒にpage.close、
新pageで1.608秒に同ID/downloading/409,600 Bの進捗を確認。
実外部download（fixtureなし）37.216秒でverifying、47.250秒installing、58.794秒ready。
377,929,956 B、SHA `dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d`。
6510 members/1,168,332,002 extracted bytes、Blender4.5.9/Python3.11.11、
background/gltf import/export probe成功。download実ファイルの独立sha256sumも一致。

基本環境導入buttonは非表示、web pack missingと専用導入buttonは維持。
最終page.reloadでも同operation/ready、page errors0。ready screenshotを目視確認。
read-only SQLiteはoperation1件ready、managed runtimeは4.5.9のみ、staging空。
package PID62393へSIGINT、exit0。専用runtime/archive/DBを次のweb pack受入用に保持。
本番Host PID2078/MF PID60180は変更なし。利用者のglobal Blender/configへ書込なし。

GOAL-03/scenario Aの空BlenderからのSettings導入・ページ切断再接続の範囲を追加受入。
installed Host iframeでのclean install、画像生成、G8 ZIP、web pack導入/GUIはこのrunではNOT TESTED。
全体3DS-8とscenario Aを完了扱いしない。次は同じ専用package/dataを再起動し、
Settingsからweb packを導入してGUI開始条件を検証する。
同scriptの再実行は空registryを要求するため、新しい専用data領域が必要。
gate `./mf.sh test`: 1054 passed / 既知Starlette warning1 / 113.20秒。diff check成功。

## 2026-09-06 v0.28.32 signed release / installed touch targets verified

branch `ux1/3d-release-0.28.32-acceptance`。PR #303 merge/tag
`b0ecc255116cb26d8aa153a4fb7713fdb238264b`からexact detached worktreeでbundle構築。
`python3 scripts/build_release_bundle.py --version 0.28.32 --output-dir /data1tb/mf-0.28.32-build-20260906
--pyinstaller /data1tb/ControlDeckMediaForge-3ds4/runtimes/bundle-build/.venv/bin/pyinstaller` exit0。
tar 31,499,396 B、SHA `228adcd9287db3bd970a16a2e598182e605d139ca71e781fc0210e02d7f50812`。
外側6 entriesはlauncher/core/addon/featureのみ。addon/feature/core doctorの版数一致。
`/data1tb/mf-0.28.32-package-iYzsMs` 配下の専用data/cacheでpackaged doctor ok。
既存正式publisher鍵で署名・自己検証しv0.28.32へ4 assets公開、
`/data1tb/mf-0.28.32-public-20260906`へ再取得。Host trusted catalogの
`_verify_signed_release`とtar実size/SHA一致を確認した。新鍵・Hostコード変更なし。

更新前は0.28.31/healthy/enabled、local Job396件・GUI23件・runtime操作3件すべて終端。
online DB backup `/data1tb/mf-0.28.32-pre-update-20260906.sqlite3`（0600、2,076,672 B）後、
Host診断Pythonの標準 `registry.update('media-forge')`で0.28.31→0.28.32、10.059秒。
healthy/enabled/requested_enabled=true、MF user service PID60180 active、Host PID2078不変。
installed/package core SHA共に
`07dba6ea0312d1281da6cf85a1cdde90e7b629ac9cd49f0c24f3a8ab4ed22b3d`。

installed受入command: Host診断venv/PYTHONPATH/configと実DISPLAY=:0/XAUTHORITYで
`scripts/3ds_settings_protection_installed_e2e.py --expected-version 0.28.32
--require-readable-layout --require-touch-targets --probe-geometry --locale <ja|en>
--evidence-dir /data1tb/mf-settings-touch-<ja|en>-installed-0.28.32-20260906`。
日英とも**headed Chrome / overlayなし / exit0**。Host/子locale一致。
320pxのruntime3 buttons全44px/minHeight44px、説明255px/root305/305、desktopは39pxを維持。
各runは両幅/両runtimeのpreview4件、project参照2/23による削除不可、確認button非表示、
戻る操作、子BUTTONへのpointer3種到達、runtime前後一致/page errors0。
個別login revoke/password不変、削除送信/scene変更なし。日本語320px screenshot目視確認。

44px不足のsource negative/修正/installed negative/署名installed positiveが揃った。
事前trial/撮影も含む今回の成功を、断続的iframe入力不達の原因確定や全条件の修正とはしない。
本sliceは配布/実機記録のみ、コード追加なし。diff check成功。
1054 tests/115.02秒は版数PRのgateであり、文書PRでの再実行ではない。
全体3DS-8/GOAL-03/必須A〜Fの残件は維持。
次は隔離したpackaged環境の空runtimeから、Settingsの初回導入を実ブラウザで検証する。

## 2026-09-06 release 0.28.32 preparation

PR #302 merged `b9cf655d113a4a58df9df60f79091fa2471f287c`確認。
mobile runtime buttonの実高44px修正を配布するためaddon/coreを0.28.32へ同期。
公開契約/DB/runtime変更なし。source日英320pxは44px実測、旧installed0.28.31は39pxのnegative。
新releaseの署名公開・標準更新・installed positiveは未実施。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1054 passed / 既知Starlette warning1 / 115.02秒。diff check成功。

## 2026-09-06 runtime touch-target correction from installed geometry

PR #301 merged `f288ea01ae215c2167e5e0628799db7886ac320d`確認。
branch `ux1/3d-settings-hit-geometry`。installed診断へ `--probe-geometry` を追加。
通常Locator trial（入力なし）後のbutton/iframe矩形、DOM hit、computed minHeight、
親scroll/scale/transformとクリック前撮影を記録。pointer失敗時はEnter入力を比較するが、
元のpointer例外を成功に変えない（今回成功runではこのkeyboard分岐未実行）。

installed0.28.31のen headlessとja headedで
`3ds_settings_protection_installed_e2e.py --expected-version 0.28.31
--require-readable-layout --locale <en|ja> --probe-geometry --evidence-dir <下記>`、
enだけ `--headless`、Host診断venv/config/PYTHONPATH、jaは実XwaylandのDISPLAY/XAUTHORITY。
`/data1tb/mf-settings-hit-geometry-en-0.28.31-20260906` と
`/data1tb/mf-settings-hit-geometry-ja-0.28.31-20260906` は双方exit0。
日英desktop/mobile preview4件、参照数2/23、runtime不変/page errors0。
mobile iframe rect x0/y48/320x590、zoom1/transform none/pointer-events auto、
button DOM hit=true、実pointerは子BUTTONへ到達。事前撮影/trialでtimingも変わるため、
過去の不達の原因を確定・解決したとはしない。

この診断で**mobile button実高39px/minHeight38px**を確認。
既存44px宣言より、後方の共通 `button:not(...):not(#shell-nav button)` が
IDを含む高specificityで優先されていた。static testの宣言存在確認だけでは見逃していた。
製品修正はmobile `.runtime-row-controls button` のmin-height44pxへ
`!important` を付ける限定CSSのみ。汎用button/desktop/公開契約/Host/DB変更なし。
sourceとinstalled受入へ `--require-touch-targets` と実computed寸法記録を追加。

隔離source data `/data1tb/mf-long-setup-source-20260906` をsource9161/PID49459で起動。
`scripts/3ds_settings_layout_source_e2e.py --require-touch-targets --evidence-dir <下記>` を実headed Chromeで実行。
before `/data1tb/mf-settings-target-before-20260906` は320en/3 buttons全39pxでexit1。
after `/data1tb/mf-settings-target-after-20260906` はexit0。
320日英すべて44px/minHeight44px、text255px/root305/305、controlsは説明の下。
1280日英は従来39px/minHeight38pxを維持、root1265/1265、page errors0/runtime不変。
source PID49459はSIGINT後exit0を確認。
source localeはdocument設定でありHost locale eventの証拠へ読み替えない。

旧installed0.28.31で同installed scriptへ `--require-touch-targets` を追加した
`/data1tb/mf-settings-touch-negative-installed-0.28.31-20260906` は、
desktop preview後mobile全3 button39pxで期待どおりexit1。
個別login revoke、削除送信なし。新flagが現行未修正版を検出することを確認。
次は修正PRを通常mergeし、署名新版を標準更新して同flagの日英installed受入を行う。
installed修正後はNOT TESTED。入力不達原因・全体3DS-8/必須シナリオは未完了を維持。
最終gate `./mf.sh test`: 1054 passed / 既知Starlette warning1 / 109.99秒。diff check成功。

## 2026-09-06 installed Host locale acceptance / iframe input still intermittent

PR #300 merged `1759518b06b0c11ff0d422dbc989087ffcc5f9e5`確認。
branch `ux1/3d-installed-locale-acceptance`。Library/Settings受入scriptに
`--locale ja|en` と比較診断用 `--headless` を追加。
Playwright contextのlocaleを指定し、Hostのnavigator.language→通常theme/bridge→
子document.langの一致と実labelをassertする。子langの代入、Host message偽造、製品overlayなし。
これは初期localeの実経路であり、開いたままのlanguage-change event受入ではない。
Settingsの独立scroll_into_viewはstatus refreshによるdetached ElementHandleで失敗したため除去。
通常Locator.clickのscroll/re-resolutionを使用。emulated高さは900→700へ変更したが、
それだけでは下記入力不達を解消していない。

installed0.28.31、Host診断venv/PYTHONPATH/CONTROL_DECK_CONFIG、headed時は実Xwaylandの
DISPLAY=:0/XAUTHORITY指定。Library commandは
`scripts/3ds_library_navigation_installed_e2e.py --expected-version 0.28.31
--scene-id scene_a94df57d689d4636844b3586dd9fed7d --require-scroll-lock --locale <ja|en>
--evidence-dir <下記>`。
ja headed `/data1tb/mf-library-ja-installed-0.28.31-20260906` はexit0。
en headed `/data1tb/mf-library-en-installed-0.28.31-20260906` はnav-createのaria-current未更新でexit1。
enに `--headless` を付けた `/data1tb/mf-library-en-headless-installed-0.28.31-20260906` はexit0。
成功2runはHost/子locale一致、日英filter label、画像/GLB/.blend絞込、
親子双方向移動、明示GLB表示、metadata移動中model read0、scene全体不変、page errors0。
320px viewer root/viewerとも320/320、背景overflow hiddenとclose後復帰。
日本語GLB screenshotを目視。画像filterのcard数はja6/6、en54/24（desktop/mobileの観測件数）、
GLB8/8、blend9/9。全件数やpaging完了の証拠にはしない。

Settingsは同scriptへ `--expected-version 0.28.31 --require-readable-layout --locale ja`。
`/data1tb/mf-settings-ja-installed-0.28.31-20260906` は上記detached scrollでexit1。
retryとheight700 runはdesktop preview2件成功後、mobile pointerが親IFRAMEだけへ届き、
子events0/preview_received=false/dialog_open=falseでexit1。
証拠 `/data1tb/mf-settings-ja-{retry,height700}-installed-0.28.31-20260906`。
headless ja `/data1tb/mf-settings-ja-headless-installed-0.28.31-20260906` はexit0、
Host/子ja、設定/削除dialogの日本語、両幅/両runtimeの削除保護、runtime前後一致/page errors0。
headless en `/data1tb/mf-settings-en-headless-installed-0.28.31-20260906` は最初のdesktop clickでexit1。
こちらも親IFRAME events3/子events0/previewなし。したがってheaded固有・高さだけ・認証問題とは断定しない。
各runの個別login revoke、削除送信なし、Host PID2078/MF PID29462 active不変。

次はiframeのcompositor hit-testとresize/scroll反映を診断し、入力不達の再現条件を確定する。
Host内部の製品変更はしていない。GOAL-01の初期日英表示証拠は増えたが、
language-change、60件超relations paging、入力不達、全体3DS-8/必須シナリオはPARTIAL。
最終gate `./mf.sh test`: 1054 passed / 既知Starlette warning1 / 113.39秒。diff check成功。

## 2026-09-06 installed 0.28.31 Settings layout / pointer recheck

PR #299 merged `0634094d2815333def72f82f9a63d9e9e2e0355d`確認。
branch `ux1/3d-settings-pointer-acceptance`。製品/Host変更なし。
既存 `scripts/3ds_settings_protection_installed_e2e.py` にpointerdown/up/click到達先、
実window/対象button寸法、preview受信/dialog open、失敗時も含む撮影を追加。
診断用 `--native-viewport` はviewport emulationを行わず、desktopだけを検査する。

Host診断venv/PYTHONPATH/CONTROL_DECK_CONFIGと稼働XwaylandのDISPLAY=:0/
XAUTHORITYを指定し、同scriptに `--expected-version 0.28.31 --require-readable-layout` を渡した。
`/data1tb/mf-settings-pointer-emulated-0.28.31-20260906` はexit0。
desktop Host1280/iframe1056、root1041/1041、text715.484/857.766px。
mobile iframe320/root305/305、runtime2行ともtext255px。両runtimeのpointer3種が子frame BUTTONへ到達、
preview受信/dialog open=true、参照数2/23で削除不可、確認button hidden、戻る操作成功。
runtime status/operation前後一致、page errors0。320px screenshotを目視し説明・確認画面を確認。

追加診断がtimingへ影響した可能性を切り分けるため、exact release worktree
`/data1tb/ControlDeckMediaForge-release-0.28.31` の**未変更script**を同引数で再実行。
証拠 `/data1tb/mf-settings-original-repeat-0.28.31-20260906`、exit0。
同じdesktop/mobile寸法、preview4件、runtime不変、page errors0。
診断scriptの `--native-viewport` も
`/data1tb/mf-settings-pointer-native-0.28.31-20260906` でexit0。
実window inner1248x835/outer1280x964、iframe1014、root999/999、
2 runtimeの実pointer到達/削除保護/戻る、runtime不変、page errors0。
全試験で個別login revoke/password不変、削除送信/scene書込/overlayなし。
終了時Host PID2078/MF PID29462 active不変。

前回dialog hiddenの原因は再現できず未確定。これを認証不具合や修正済み製品bugとは呼ばない。
0.28.31のmobile Settings layoutとproject参照削除保護は上記再実行範囲で受入。
日英Host locale切替、空環境install、scenario D全体の成功には拡大しない。
次はinstalled Host localeを通した日英Library/Settingsの受入を進める。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1054 passed / 既知Starlette warning1 / 130.64秒。diff check成功。

## 2026-09-06 v0.28.31 signed release / installed browser acceptance incomplete

branch `ux1/3d-release-0.28.31-acceptance`。PR #298 merged
`fc48b7a14a8b0948db8f344699955f8b07631499`、同commitをtag v0.28.31として通常公開。
既存build/署名物を再確認し、専用mktemp data/cacheを指定したpackaged doctorは
`{"status":"ok","version":"0.28.31","packaged":true}`。
公開4 assetsを `/data1tb/mf-0.28.31-public-20260906` へ再取得。
Host trusted catalogの `_verify_signed_release` と実tar bytes照合が成功。
tar 31,499,258 B、SHA `bbe826e12cf36c942f0998c0983e51c168759cc32ed023de595ed0a7fd0ea931`。

再開時Host user service PID2078 active、MediaForge processなし/HTTP9130到達不可。
registryは0.28.30/requested_enabled=true/enabled=false/health=error。
明示disableと断定せず、設定上の有効化要求が維持されていることを再確認した。
local DBはJob396件すべて終端、runtime operation ready3、GUI session23件すべて終端。
online backup `/data1tb/mf-0.28.31-pre-update-20260906.sqlite3`（0600、2,076,672 B）後、
Host診断Pythonで標準 `registry.update('media-forge')` を実行。
13.587秒で0.28.30→0.28.31、enabled/requested_enabled=true、healthy。
user service PID29462 active、Host PID2078不変、実HTTP /health healthy。
installed coreと検査済みpackage coreのSHAは共に
`4396cdd231ff5711cb04c96b5fa441079a5644dcb28614e1b5244c7300c07ead`。

installed Settings再試験は未合格。最初はDISPLAY未設定でChrome起動失敗。
user managerと実XwaylandからDISPLAY=:0、
XAUTHORITY=/run/user/1000/.mutter-Xwaylandauth.HOXYU3を確認し、
`scripts/3ds_settings_protection_installed_e2e.py --expected-version 0.28.31
--require-readable-layout --evidence-dir /data1tb/mf-settings-layout-installed-0.28.31-display-20260906`
をHost診断venv/実headed Chromeで再実行。
Settings表示/desktop layoutまでは到達したが、最初のRemoveクリック後dialog hiddenでexit1。
観測iframe width1056/root client1041/scroll1041、runtime text715.484/857.766px、page errors0。
preview0件、320px未到達、runtime不変の最終assert未到達。個別試験loginはfinallyでrevoke。
原因は未確定。過去のviewport入力問題と同一と決めつけず、次はこのボタンのpointer到達とAPI応答を切り分ける。
製品変更/追加runtime導入/削除送信なし。全体3DS-8と必須受入はPARTIALを維持。
本sliceは文書のみ、diff check実施。1054 testsのgateは版数PR時の既存証拠で、今回再実行していない。

## 2026-09-06 release 0.28.31 preparation

PR #297のmobile Settings行/header修正を配布するためaddon/core版を0.28.31へ同期。
公開0.28.30とは区別する。新releaseの署名公開/標準更新/installed受入はNOT TESTED。
公開契約/DB schema/Blender runtime変更なし。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1054 passed / 既知warning1 / 113.04秒。diff check成功。

## 2026-09-06 mobile Settings layout — source verified

branch `ux1/3d-settings-mobile-rows`。runtime行を767px以下で縦積み、操作button44px以上/折返し可、
420px以下headerの折返しを追加。rowだけではroot横overflowが残り、header設定buttonの超過も実測して修正。
新source browser scriptは日英320/1280でexit0。320はtext0→255.663、root client305/scroll319→305/305、
操作欄は説明の下。1280はroot1265/1265で横並び維持。runtime不変/page errors0、撮影目視確認。
証拠 `/data1tb/mf-settings-layout-{before,after,after2}-20260906`。source PID78593正常終了。
installed0.28.30の`--require-readable-layout` negativeはtext0/root305/319を検出して失敗。
証拠 `/data1tb/mf-settings-layout-installed-negative-0.28.30-20260906`。個別login revoke/削除送信なし。
修正版の署名公開/installed成功はNOT TESTED。製品差分はCSSだけ、Host/公開契約変更なし。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1054 passed / 既知warning1 / 119.47秒。diff check成功。

## 2026-09-06 installed Settings protection — verified; mobile layout defect found

installed0.28.30の実Host opaque iframeで新`3ds_settings_protection_installed_e2e.py`を実行、
previewのみ/個別login revoke/password不変/overlayなし。desktop viewport1280/320両方でexit0。
4.5.9は非activeだがproject参照2で削除不可、4.5.13は参照23とactiveで削除不可。
確認button hidden、戻るbutton visible、runtime status/operation journal前後一致、page errors0。
証拠 `/data1tb/mf-settings-protection-layout-installed-0.28.30-20260906`。削除やscene書込なし。
Host PID2196/MF PID31432 active不変。
一方、320 screenshotで設定行の縦崩れ/横scrollを観測。root client305/scroll319、
非active行width280.981/text0/controls247.666。削除保護成功を320px layout成功へ読み替えない。
次sliceでruntime行のmobile列割りを修正する。製品差分なし、全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 112.49秒。diff check成功。

## 2026-09-06 Settings lifecycle — VERIFIED SOURCE BROWSER SCOPE

branch `ux1/3d-setup-settings-ui`、隔離source9161/PID68057、日本語Settingsの実ボタンを操作。
`3ds_setup_settings_ui_e2e.py`は57.062秒/exit0。active版の削除確認はhidden、can_remove=false。
固定4.5.13実外部download378,033,952 B/hash一致、update54.993秒ready/実Blender/glTF probe成功。
参照0の隔離4.5.9のみpreview/confirmで削除し1,168,332,155 B回収。有効4.5.13は不変。
証拠 `/data1tb/mf-setup-settings-ui2-20260906`。最初のrunはdisabledとhiddenのassertion誤りで失敗、製品変更なし。
`3ds_setup_repair_ui_e2e.py`は43.132秒/exit0。画面から4.5.9を再導入後、隔離stampをevidenceへ退避して
damaged/repair表示を確認。修復で実4.5.9/glTF probe成功/stamp再作成/active4.5.13不変/page errors0。
証拠 `/data1tb/mf-setup-repair-ui-20260906`、元stampを保持。repaired画面を目視確認。
DB6 operationは5 ready/1 canceled、staging空、sourceはSIGINT/exit0で終了。
Host PID2196/MF PID31432 activeで不変、稼働runtime/製品/Host設定は変更なし。
完全空環境browser install、installed opaque iframe、live/project参照保護、全scenario DはNOT TESTED。
全体3DS-8はPARTIAL。script/文書のみなので新規release不要。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 114.25秒。diff check成功。

## 2026-09-06 long setup source probe — VERIFIED FOR SOURCE SCOPE

branch `ux1/3d-long-setup-acceptance`に固定実Blender archiveの低速配信fixtureを使う
隔離source HTTP受入scriptを追加。製品/Host/TTL変更なし。
managerはHost credentialを保存せず、durable setup operationとして動作することをコードで確認。
実行PID62708/session67258、60.249秒でdownloading/3,866,624 BとHTTP health応答を観測。
同runはexit0。631.247秒/41,156,608 Bでcanceled、652.011秒で再導入ready。
377,929,956 Bの実archive SHAは固定manifestのdcdc3eca...と一致、6510 member/1,168,332,002 B展開。
実Blender4.5.9/Python3.11.11/background/gltf export/importのprobe成功。
read-only DBで2 operationはcanceled/ready、staging空/partialなし/PID62708消失。
Host PID2196/MF PID31432 activeで不変。隔離runtime/archiveは後続受入用に保持。
証拠 `/data1tb/mf-long-setup-source-20260906/observations.json`。
実Host credential更新/設定browser UI/実外部回線は対象外、別途受入が必要。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 110.22秒。
今回追加は結果文書のみ、unit再実行なし/diff check成功。製品差分なしで新規release不要。

## 2026-09-06 RFB credential renewal — VERIFIED EXISTING INSTALLED PATH

Host `97aba42`のloopback例外はLLM gateway/agent MCP限定とコードで確認。
RFBは期限付きservice identityを再検証するが、MFの既存session.updated handlerにはRFB再接続も存在。
当初追加した期限前1012処理は実機証拠を受け撤回。PR #293は受入script/文書だけに変更。
installed0.28.30の実Host opaque iframeで`3ds_rfb_renewal_installed_e2e.py`を実行、exit0/672.072秒。
証拠 `/data1tb/mf-rfb-renewal-negative-0.28.30-20260906`（negativeは当初予想の名前、結果はpositive）。
接続後480.340秒に接続instance1→2、660.433秒まで同一sessionでconnected、GUI入力のmesh複製を保存。
scene `scene_b2f21eddc2c548cc8cb7865d32e9a1bc` revision1→2、1→2 meshes、32256 triangles/16132 vertices。
Blender4.5.13/独立GLB検査passed、新GLB2,179,304 B、SHA `232b1916491b012a57422ebfdd1d487babccfdc698392481b22cf489a3452ed2`。
旧版レコード/実blend・GLB SHA不変。page errors0。専用login個別revoke/password不変、試験session終端。
Host PID2196/MF PID31432不変、Blender unit inactive/MainPID0。Host/global config/TTL/稼働版変更なし。
隔離sourceの並行起動はdisplay99競合で失敗、lock削除なし。不要な候補scriptは撤回、隔離dataは保持。
`./mf.sh test`: 1053 passed / 既知Starlette warning1 / 112.01秒。全体3DS-8/Scenario EはPARTIAL。
setupの長時間credential・自然な長時間演算/GPU組合せはNOT TESTED。製品差分なしのため新規release不要。

## 2026-09-06 installed CPU child refresh across 600s — VERIFIED FOR THIS SCOPE

installed0.28.30/healthyで既存`3ds_credential_refresh_e2e.py`を実行、PID33983/exit0/644.700秒。
証拠 `/data1tb/mf-credential-refresh-installed-0.28.30-20260906/events.json`。
dedicated CPU6 Jobの先行4 Blender childへ各160秒のpidfd SIGSTOP/SIGCONTを行うqueue fault injection。
TTL600/worker timeout180を変更せず、元の期限前の後半4 child refresh success各1件をHost監査で確認。
success child `2ef6f7e7dedb`の監査時刻06:23:55.882692 UTC、cancel child `c33bfd0fdb62`は同.883385。
615.630秒の取消と644.700秒の完了を確認。local/Hostの6件は5 succeeded/1 canceledで一致し、
全host_terminal_sent=true。MF PID31432/Host PID2196不変。local非終端0、停止した4 child PIDは消失。

5 scene/10 assetsを生成、Blender4.5.13、各16128 triangles/8066 vertices、独立GLB検査passed。
全10実ファイルのsize/hashとmetadata/provenance、親IDをread-onlyで照合しassert成功。
最終GLB1,138,216 BのSHA `b468c73ca925889e3c55b5b48658526e00bbca2f0d7e3047f4eef0ea2475261b`。
試験専用制作物は証拠として保持。Host/global config/model/既存scene/製品コード変更なし。
過去のrefresh0件/Host停止による失敗記録は維持し、この無再起動runの成功で過去を上書きしない。
自然な長時間演算、GUI/setupのrefresh、OpenCode自然言語による長時間制作はNOT TESTED。
scenario E/全体3DS-8はPARTIAL。今回文書のみ、unit test再実行なし/diff check成功。

## 2026-09-06 v0.28.30 signed / installed viewer scroll — VERIFIED FOR THIS SLICE

PR #290 merge/tag `bdaa379d682feedbea476fc037772b6dae095b9c` exact sourceから正式bundle構築/署名公開。
31,500,089 B、SHA `dfa398205c0706bd4b02409db8e4681546588ee4231850240f932f1f9b9b11a6`。
公開4 asset再取得/checksum/Host署名検証/tag一致、packaged doctor ok/0.28.30。
private online DB backup2,007,040 Bと全Job/session/setup終端を確認。標準update10.500秒、
0.28.29→0.28.30/healthy/enabled。MF PID31432、Host PID2196は不変。
installed/bundle core SHA `9f2c65b96588215249462dff3759102ba01bb064aab5413155b2d1c56a8e776d`一致。
公開再取得 `/data1tb/mf-0.28.30-public-20260906`、backup `/data1tb/mf-0.28.30-pre-update-20260906.sqlite3`。

`3ds_library_navigation_installed_e2e.py --expected-version 0.28.30 --require-scroll-lock`を
既存専用scene/Host診断Pythonで実行しexit0。実opaque iframe/overlayなし/login個別revoke。
証拠 `/data1tb/mf-viewer-scroll-installed-0.28.30-20260906`。320px root320/320/hidden、
viewer320/320、close後scroll復帰。旧0.28.29 negative305/319/visibleに対する同一検査の成功。
4nav/Settings復帰、画像/GLB/.blend filter、親子双方向、明示GLB、scene不変、page errors0。
撮影したGLB画面で横scroll消失を目視確認。source gate1053 passed / 既知warning1 / 112.29秒。
今回は文書のみ追加、diff check成功。全体3DS-8 A/C/D/E/Fと長時間credentialは未完了のまま。

## 2026-09-06 Release 0.28.30 preparation

PR #289 merge `5b7fa61`の全画面viewer背景scroll修正を配布するためaddon/core版数を0.28.30へ同期。
新しい版の署名公開/標準更新/installed受入はNOT TESTED。公開0.28.29とは区別する。
既存公開契約/DB schema/runtime/sceneは変更しない。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 112.29秒。diff check成功。

## 2026-09-06 viewer modal background scroll — source verified

branch `ux1/3d-viewer-modal-scroll`。全画面viewer表示中だけhtml rootのscrollを停止するCSSを追加。
100vwのviewerを背景scrollbarで狭くなったroot内へ置く状態を避け、閉じた後は通常scrollへ戻す。
画像/GLB共通、既存材質比較のscroll制御は維持。公開契約/scene/asset/Hostコード変更なし。

source9159/既存隔離素材に対し`library_lineage_ui_e2e.py`の新検査を実行。
beforeはoverflow visibleで失敗（小fixtureでは320/320であり横overflowの再現ではない）。
after `/data1tb/mf-viewer-scroll-after-20260906`はGLB/画像320/320/hidden、close後scroll復帰、
日英filter/lineage維持、scene不変、page errors0。GLB screenshotを目視確認。source process正常終了。
installed0.28.29へ`3ds_library_navigation_installed_e2e.py --require-scroll-lock`を実行した
`/data1tb/mf-viewer-scroll-installed-negative-0.28.29-20260906`はroot305/319/visibleで失敗し、
未修正版を新assertionが検出することを確認。診断は個別login作成/revoke、overlay/scene変更なし。
修正版の署名公開/installed受入はNOT TESTED。全体3DS-8はPARTIALのまま。
gate `./mf.sh test`: 1053 passed / 既知Starlette warning1 / 115.62秒。diff check成功。

## 2026-09-06 v0.28.29 signed / installed navigation and Library

PR #287/tag target `a906cff03a67ce9ae9f325b62a775589659f1186`からexact bundleを構築・正式署名公開。
31,500,563 B、SHA `20e247de72c90f6997eab2889aab7c4450eb7346688c4d58ce7d292d6d1edef8`。
公開4 asset再取得/checksum/Host署名検証/tag一致、packaged doctor ok/0.28.29。
全制作Job/session/setup終端とprivate DB backup 2,007,040 Bを確認後、標準registry.updateは
10.166秒、0.28.28→0.28.29/healthy/enabled。Host PID2196不変、MF PID13607 active。
installed/bundle core SHAはともに`c47a0d0c51e304fd6bb5838b815cb333c56936e652baa460abe3033579538d29`。
公開再取得 `/data1tb/mf-0.28.29-public-20260906`、backup `/data1tb/mf-0.28.29-pre-update-20260906.sqlite3`。

`scripts/3ds_library_navigation_installed_e2e.py`をHost診断Pythonで実行しexit0。
既存専用scene `scene_a94df57d689d4636844b3586dd9fed7d`、password変更なし/個別session revoke、
native headed Chromeから実Host opaque iframeへ接続。frontend overlay/scene authoringなし。
1280/320pxの4nav・設定復帰・画像/GLB/.blend filter、画像↔source↔GLBの双方向移動、
metadata移動中model read0、明示GLB表示、scene不変、page errors0。
証拠 `/data1tb/mf-library-navigation-installed-0.28.29-20260906`。
画像を目視したところ320px viewerに横scrollがあり、mobile layout全体の合格は記録しない。
寸法観測を追加し、発生要素を次に確認する。日英切替/Host戻る進む/60件超relations paging、
新releaseの全A/C/D/E/F・credential refreshはNOT TESTED。全体3DS-8はPARTIALを維持。
寸法追加run `/data1tb/mf-library-navigation-installed-0.28.29-layout-20260906`もexit0。
inner320/root client305/scroll319、viewer client320/scroll320。背景rootで14px overflowを実測した。
gate `./mf.sh test`: 1052 passed / 既知warning1 / 113.38秒。diff check成功。

## 2026-09-06 Release 0.28.29 preparation

PR #286 merge `05e556f1232d8bb943f2d519a6daa1e5e5be07c4`後、addon/core versionを0.28.29へ同期。
Web Blender primary navと共通Library formats/lineageを同じ既存MediaForge bundleへ載せる。
この版数slice時点では署名公開/標準update/installed受入はNOT TESTED。稼働0.28.28を維持。
gate `./mf.sh test`: 1052 passed / 既知warning1 / 117.71秒。利用者のBlender Skills連携依頼を優先し、
branchをcommit/pushして公開前に中断。release PR/merge/tag/build/sign/installは未実施。

再開時、PC boot 2026-09-06 14:40:53を確認。Host PID2196 active、MediaForgeは
0.28.28 installedだがenabled=false/health=error、unit disabled/inactive/MainPID0。
無断で再有効化せず利用者へ確認中。再起動直前の追加testは634 passed時点で明示中断(exit2)、
全通過の証拠には含めない。保存済み版数branchからサービス変更なしでrelease準備を再開する。
再起動後の再実行 `./mf.sh test`: 1052 passed / 既知Starlette warning1 / 115.55秒、exit0。

## 2026-09-06 Common Library formats and lineage — source acceptance

PR #285 Web Blender navigationは通常merge `ae9ed17f77ddd39df9b3236db4bdbfcd6dbbe11d`を確認。
本sliceはbranch `ux1/3d-library-lineage`の保持差分を再開し、GOAL-01の不足を補完。
`.blend`をmetadata cardとして共通Libraryへ表示し、GLB/Blender MIME別filter、
private `assets.relations`とstandalone mirror、親/派生の双方向リンク、60件単位の次/前ページを追加。
詳細からGLB/画像を明示閲覧でき、viewer前後移動から.blendを除外する。
未知の合否を持つBlender factsは失敗と偽らず中立表示。locale変更で開いている詳細を再描画し、
閉じたdialogへの遅いresponseを無効化する。公開Asset/tool契約、scene書込方式は変更しない。

`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_material_preview_ui_e2e.py --serve
--data-dir /data1tb/mf-library-lineage-source-20260906
--legacy-runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9 --port 9159`で
隔離data dirへ実Blender4.5.9の2 revision/画像材質/GLBを作成、source core HTTP200。
最初のPYTHONPATH=backendだけの起動はscripts import失敗/exit1、再実行前はserver未起動だった。
`scripts/library_lineage_ui_e2e.py`をHost診断Pythonで実行。
最初のbrowser runは試験側wait_for_function引数ミス、修正後は1280px日本語/320px英語で
画像2/GLB2/.blend2のfilter、画像↔source↔GLBの双方向移動、素材本体取得0、scene不変、page errors0。
詳細のGLB閲覧を加えたheadless runは表示失敗。独立probeでheadless WebGL2=false、
headed WebGL2=trueを確認。失敗screenshotは`/data1tb/mf-library-lineage-browser-preview-diagnostic-20260906`に保持。
metadata-only成功証拠は`/data1tb/mf-library-lineage-browser-reviewed-20260906`。
初回full gateは旧「.blendを一覧から隠す」assertion1件で失敗(1050 passed)。
GOAL-01に合わせsource/preview両方の掲載とsource preview_kind=Noneを検査するassertionへ更新した。
installed Hostでの全filter/lineage/ページ送りと公開bundle反映はNOT TESTED。GOAL-01全体の完了にはしない。
最終headed run `/data1tb/mf-library-lineage-browser-headed-20260906`はexit0、全filter/双方向移動に加え
詳細の「素材を見る」から実GLB表示成功、編集ボタン非表示、scene不変、page errors0。
`./mf.sh test`: 1051 passed / 既知warning1 / 130.00秒。`git diff --check`成功。
main `ae9ed17`取込後、進捗文書の競合は両entryを保持して解消。
source serverだけを同dataで再起動し、Library受入
`/data1tb/mf-library-lineage-browser-restarted-20260906`とnav受入
`/data1tb/mf-library-webnav-integrated-20260906`を再実行、両方exit0/page errors0。
統合後gate `./mf.sh test`: **1052 passed / 既知warning1 / 113.64秒**。source serverは正常終了。
GitHub latest releaseはv0.28.28、実installed PID2744941のexe/cwdもversions/0.28.28、service active。
本sliceの変更を稼働版へoverlayしていない。次は正式版数更新・署名公開・標準updateとinstalled受入。

## 2026-09-06 Web Blender primary navigation — source browser verified

利用者指定の並び「作る・ライブラリ・状況・Web Blender」に4番目の入口を追加。
専用view `/web-blender`へ既存scene UIを移動し、3D切替も同じ入口へ接続。
設定からの復帰、選択中のaria-current、last_viewの保存に対応。nav移動でGUI起動なし。
設計の正base-plan §16 / design-workspace-ux追補を同期。

実source coreを独立したtemporary data dirでloopback port44891へ起動。
`/data1tb/ControlDeck/app/.venv/bin/python scripts/web_blender_navigation_e2e.py
--url http://127.0.0.1:44891 --evidence-dir /data1tb/mf-webnav-final-20260906` exit0。
実Chromeで1280/320pxの全4入口移動、Settings復帰、3D切替、直接URL表示にassertion成功。
320pxは4ボタン各80x60px、一列表示。page errors0、JSON/screenshots保存。
installed opaque iframeのhistory、GUI起動/編集、release/installed更新はNOT TESTED。
先行Libraryの未commit差分は別worktreeに保持。本sliceはそれを含まず、全体3DS-8完了ではない。
最終 `./mf.sh test`: 1047 passed / 3 skipped / 既知Starlette warning1 / 110.12秒。
`pytest tests/test_release_signing.py -q -rs`で3 skipは本worktreeのbuild runtime不在と確認。
`git diff --check`成功。専用source server PID2851228は正常終了、稼働serviceは停止していない。

Date: 2026-08-26
Scope: MF0-0 through MF0-7 and G0 through G6 complete; G7 V0 complete, V1 adoption deferred; G8 B0-B4 complete

G8 planning started on 2026-08-26. The current host has no `blender` executable. The implementation order,
license/process boundary, GLB-only first import, deterministic compiler/package, typed options, and installed
acceptance are fixed in `docs/implementation/g8-blender-production.md`. Blender execution, GLB import, worker,
workspace, agent placement, and installed acceptance are **NOT TESTED** at this point.
Planning gate: `./mf.sh test` reported `711 passed, 1 warning in 48.10s`; `git diff --check` passed.
Repository head at final MF0-7 verification: `8c6ab98382f43db8a58ff1dcf7dc6fcde113968a` (`origin/main`)
Repository head released and verified for G1: `1e88472e753fd484638f072f7c4b327c8010ab60` (`v0.1.2`)

## Video model candidate catalog — IMPLEMENTED, SNAPSHOT VERIFIED

Wan 2.2 TI2V-5B／I2V-A14B／T2V-A14B／Animate-14B、LTX-2.3、HunyuanVideo-1.5の
exact revisionとbounded checkpoint identityを、既存Model Registry／Model Managementへ追加した。
全候補は`experimental`、recommended profileなしであり、R9700向けavailable/defaultや動画worker実装を
主張しない。Wan TI2V-5B だけは 2026-08-26 の bounded R9700 probe 後に resource measurement
confidence を `measured` としたが、品質 gate は不合格で unavailable のままである。その他は
measurement confidence `low`、ROCm未実測。runtime packageまでsnapshotが閉じるWan生成3件だけを
managed download対象とし、Animate／LTX／Hunyuanはexternal ownerとしてbackendでもdownloadを拒否する。
UIは動画候補filter、実験的表示、外部runtime所有表示を追加し、別の動画モデル管理APIは作っていない。

ローカル自動検証はcatalog／manager／frontend集中46件成功、`./mf.sh test`全274件成功（23.54秒）。

実model download: 製品のdurable installerを並列1で使い、Wan 2.2 TI2V-5Bのfixed revision
`921dbaf3f1674a56f47e83fb80a34bac8a8f203e`を取得した。operation
`modelop_0164bf6e9d79411b87bfe97c2c0c9f3d`は2026-08-22 18:12:50 JSTから19:15:16 JSTまで
3,745.295068秒で、34,201,521,212／34,201,521,212 bytes、errorなし、`ready`となった。download中は
partialが`.downloads/<operation_id>`内だけにあり、全取得後に`verifying`を経てsnapshotへatomic配置された。
平均転送量は約9.13 MB/sで、配信帯域の一時低下は観測したがretry/errorは観測しなかった。resumeは実中断を
行っていないためNOT TESTED。

初回の開発CLIはtracked configのhome既定を使い、root filesystemへ一旦配置した。これはNVMe証拠として採用せず、
同一filesystem上の実運用store
`/data1tb/ControlDeck/data/feature-data/media-forge/data/models`へcopy後、5 weight全てのsizeとSHA-256を
独立再計算した。34,201,521,212 bytesの全weightがcatalogと一致し、required file 7件とrevisionも一致した
（25.66秒、最大RSS 31,768 KiB）。その後registryはWanを`managed/removable/installed`、既存共有FLUXを
`external/installed/available`として同時に検出した。home既定model pathはこのNVMe storeへのsymlinkに切り替え、
root filesystem使用率は89%から77%へ戻った。誤配置元の同一copyは削除せず
`/data1tb/mediaforge-recovery/root-misplaced-Wan2.2-TI2V-5B-20260822`へ退避している。

Wanの主用途はText-to-Video／Image-to-Video、規模は5B、R9700の第一評価候補である。snapshot取得時点では
ROCm runtime動作は NOT TESTED だったが、2026-08-26 の G7 V1 で bounded T2V を実測した。
現在は hardware backend に ROCm、resource measurement confidence `measured` を記録する。一方、
stateは`experimental`、healthy=false、recommended profileなし、公開 capability unavailable を維持する。
詳細と不採用理由は末尾の G7 V1 節を正とする。

## MF0-0 — COMPLETE for the requested environment slice

The core service, heavyweight ROCm runtime, caches, and persistent Media Forge data are separated. Section 10 was executed from retreated `.venv` / runtime state on the target host. This status uses runtime observations; lint, syntax checks, and unit tests are not counted as proof that the environments work.

## MF0-1 — COMPLETE

The loopback service skeleton, Add-on v2 manifest, schema serving, four-state health contract, contribution-level availability, and setup snapshot integration are implemented. Unfinished execution contributions fail closed with explicit reasons and actions; no fake job runner or later MF0 behavior is claimed in this slice.

Real-process verification on 2026-08-21:

```text
ControlDeck ./deck.sh ext lint: valid=true, warnings=0
healthy health:        HTTP 200, 0.001353 sec
degraded health:       HTTP 200, 0.000551 sec
unavailable health:    HTTP 200, 0.000397 sec
setup_required health: HTTP 200, 0.000414 sec
schema response:       HTTP 200, 0.003092 sec
placeholder response:  HTTP 200, 178 bytes
```

For all four health states, `navigation:workspace=available` remained stable while `workflow_executor:media.generate=unavailable`. The manual health switch returned 404 unless `MEDIA_FORGE_ENABLE_TEST_ENDPOINTS=1`.

The final default process returned `setup_required` in 0.001575 seconds with a 2373-byte response. Core/runtime/GPU setup items were `ok`, model library was `missing`, and the disabled test switch returned HTTP 404.

## MF0-2 / MF0-3 — COMPLETE for the local job and asset slice

The local API now provides a durable SQLite job queue, a bounded fake-worker subprocess, explicit cancellation/timeout/crash normalization, deterministic validation, immutable asset copies, provenance sidecars, and lineage fields. Host token, GPU lease, and Jobs bridge remain MF0-4 and are not claimed here. The fake worker is CPU-only; it does not acquire or use the GPU.

Real-process evidence using an isolated temporary data directory:

```text
submit -> succeeded -> asset/provenance: 40 ms
PNG: 128x80, 8-bit RGBA, 716 bytes
same intent + seed output SHA-256:
  823c25d57f4e077f3a67fc129ce267cba2a0973d2e011ff39cecb8faa0bf3393
second run same hash: yes
worker crash result: failed / worker_crash
next job after crash: succeeded
running cancel result: canceled
normal terminal work-directory entries: 0
```

The provenance response contained the fake implementation ID, `CC0-1.0` license, empty warnings, and passed `image.non_empty`, `image.dimensions`, `image.mode`, and `image.alpha` validators. Capability discovery did not expose the implementation/model ID.

Shutdown and crash isolation were exercised separately:

- graceful service stop during a running job produced `failed / service_stopped`, not `worker_crash`
- `SIGKILL` of the exact service PID during a running job left the database row running; on restart it became `failed / service_restarted`
- the isolated child worker was gone after parent death and stale work entries changed from 1 before restart to 0 after restart
- persisted job and asset lists remained readable after restart

During the first isolated-data attempt, `mf.sh serve` was found to overwrite an explicit `MEDIA_FORGE_DATA_DIR`. Two exact test jobs and assets therefore entered the default data tree. This was not accepted as isolated evidence: the script was fixed to preserve the explicit variable, the database was backed up to `/tmp/mediaforge-mf03-cleanup.yx1Ia0/media-forge.sqlite3.backup`, the two identified files were moved to trash, and only their exact database rows were deleted. Verification reported zero remaining test jobs/assets. The complete E2E was then rerun successfully in `/tmp/mediaforge-mf03-e2e.s5f9e6`, which was moved to trash after evidence collection.

## MF0-4 — COMPLETE

ControlDeck upstream `main` was re-audited at
`f86cb82055bc0d572c6ec8f91fc956834aaf4dc9`. Its Add-on Runtime provides
token introspection plus scoped Jobs, resource, grant, and output APIs. Media
Forge uses only those HTTP contracts: it imports no ControlDeck module, receives
no session cookie, and no longer provisions or reads the Host signing key.

Incoming credentials are introspected at
`/api/v1/addon-runtime/token/introspect`. Media Forge then verifies active state,
`addon_id=media-forge`, nonempty subject, expiry, maximum lifetime, and granted
capabilities. Credentials are excluded from object representations and Host
errors do not include response bodies. Raw Unix/Windows/file-URI paths remain
recursively rejected; file content moves only through opaque `grant:` and output
IDs.

Hosted generation now creates or attaches a ControlDeck Job before admission,
requests a real Broker lease before entering the worker-local execution guard,
reports all four VRAM dimensions plus `estimated_runtime_sec`, activates and
renews the lease, observes Host cancellation, and releases or cancels Broker
state in `finally`. ControlDeck forces the request owner to
`addon:media-forge`; Media Forge does not send a caller-selected owner. Attached
agent Jobs leave terminal ownership to ControlDeck's outer runner, while Jobs
created for the workspace are terminalled by Media Forge. Host-managed queued
jobs are failed with `host_context_lost` after restart instead of resuming
without their short-lived authority.

Real-process verification on 2026-08-21 used disposable ControlDeck and Media
Forge data directories, the public ControlDeck API, the real AMD GPU Broker,
and separate loopback processes:

```text
agent generation: HTTP 200 in 0.648 sec
ControlDeck Job: 3151f0d8aacf / succeeded / register_asset / 1000 of 1000
Broker lease: c088e41f... / gpu0 / owner addon:media-forge / released
reservation: 335544320 bytes / exclusive-preferred
two concurrent jobs: first granted; second waiting / device_busy_exclusive / queue 1
completion times: 1.685 sec and 2.327 sec; all leases released
Host cancel: running Job 015c881fe14e -> canceled; active lease -> released
10 sec job: HTTP 200 in 10.671 sec; lease.renewed delta 1
scoped file roundtrip: 31 input bytes -> 31 output bytes; content identical
file transport response: grant/output/asset IDs and metadata only; no path
```

The fake worker is CPU-only, but the MF0 contract deliberately acquires a small
real GPU reservation so the complete admission/renew/cancel/release lifecycle is
exercised before G1 substitutes a GPU worker. Two-job contract testing also
confirmed that only one worker subprocess runs while the second job waits for
Host admission.

The initial real-process run found that Workflow and Context Action correlation
subjects could not prove their initiating user to the Runtime API:

```text
workflow executor token subject = workflow:<execution_id>
  Add-on Runtime Jobs/Resources accept numeric user or job:* subjects only
context action token subject = context:<user_id>
  Add-on Runtime Grants accept numeric user or job:* subjects only
```

No Media Forge fallback was added. The generic Host boundary was instead fixed
on merged ControlDeck PR #212 (`2dad80b3`) by separating signed `actor_user_id` from the correlation
subject and binding real Runtime grants through an exact per-call `grant_ids`
allowlist. Media Forge then removed both fail-closed availability blocks, runs
Workflow generation through the same leased Host Job path, and consumes the
actual Context Action read grant without receiving or reflecting a path.

Current exact-code real-process acceptance used ControlDeck main `2dad80b3` and
Media Forge `e0f4b89`, isolated ControlDeck／Media Forge data, separate Uvicorn
processes, the public Host API, and the real AMD GPU Broker. The complete run
took 20.199074 seconds:

```text
discovery: workflow executor 1, context action 1
workflow dry-run: Media Forge Job delta 0
workflow execution: SUCCEEDED; generated Media Forge Job succeeded
context file: 1206-byte 48x48 RGBA PNG validated through Runtime grant; path/grant reflected false
normal generation: 0.627521 sec; 335544320-byte gpu0 reservation; lease released
two concurrent Jobs: second device_busy_exclusive / queue 1; both leases released
Host cancel: Job canceled; lease released
10-second Job: 13.094774 sec wall time; lease renew delta 5; lease released
scoped read/output: 1206 bytes; SHA-256 identical; Host asset committed
disable while active: Job canceled; lease released; re-enable healthy
```

The driver removed its temporary Workflow and uninstalled the Add-on in
`finally`. The isolated services and directories are removed after evidence
collection. No ControlDeck module, cookie, signing key, or path crossed into
Media Forge. Final `./mf.sh test` completed with 51 passed in 3.38 seconds;
this is regression evidence, not a substitute for the real-process run above.

## MF0-5 / MF0-6 / MF0-7 — COMPLETE

The embedded workspace provides Create, Library, Jobs, Models, and Settings without localStorage, sessionStorage, cookies, or parent DOM access. It waits for the MessageChannel handshake before first paint, validates the parent origin, applies initial/theme-change tokens without reload, handles locale/safe-area/route/session/disable events, syncs routes, updates the title, exposes the command-palette shortcut, and clears busy state on disable. Standalone rendering remains available when the page is not framed.

Workflow, agent capability/generate/inspect, command, and edit-image context endpoints are implemented with service-token enforcement and structured job/asset responses. Capability discovery and all agent tool responses contain no model name; inspect returns the license, lineage, validation, warnings, and output hash without implementation identity. Context responses do not echo the scoped token.

The first installed-host attempt exposed three real integration defects that
unit/static checks had not detected: health reason codes outside ControlDeck's
closed enum, 401 responses for external iframe CSS/JS, and 401 responses to
opaque-origin iframe HTTP API calls. The implementation now uses only host
reason codes, serves the trusted workspace CSS/JS inline, and carries bounded
structured workspace RPC over ControlDeck's nonce-bound authenticated WebSocket
proxy. Raw paths are rejected on that transport and asset previews are capped at
12 MiB before base64 encoding.

Final installed-host browser verification used ControlDeck PR #213's exact tree
(merged as `a5e4fc7`), isolated ControlDeck and Media Forge data directories,
real loopback processes, Chromium at 1280x800 and 320x700, and installation
through ControlDeck's public Add-on API. The reusable driver was
`scripts/mf0_control_deck_e2e.py`; it deleted its temporary Workflow and always
uninstalled the Add-on in `finally`. The final run completed in 15.162338 seconds
with zero browser console errors and zero page errors. Observed results:

```text
disabled: Media navigation absent
setup_required: setup dialog and missing model library visible
healthy: Media navigation and opaque iframe workspace visible
workspace initial paint: Host iframe invisible and themed connection overlay visible before response
workspace transport: bridge ready; Create produced one fake asset and one succeeded Host Job; Library preview rendered
theme: light -> dark applied without reload; in-frame marker survived
route: Library back / forward / reload / share URL preserved
Files: real scoped image grant read; edit-image opened /x/media-forge/workspace/create
agent API: media.capabilities returned ControlDeck job_id=6559bae30693 and asset_id=job-result:6559bae30693
agent response: no model_id, fake implementation name, FLUX, or Qwen string
workflow: media.generate discovered; dry-run Media Forge Job delta 0; real execution SUCCEEDED
Broker: second fake GPU Job waiting / device_busy_exclusive / queue 1; both Jobs succeeded
disable: iframe and all executable contributions removed; saved Workflow remained readable
re-enable: all pre-disable assets remained visible
mobile 320px: companion rendered and iframe remained absent
```

The run ended with Broker active 0 / waiting 0 and all four observed leases in
`released`. The FOUC assertion uses a test-only, process-once, maximum-two-second
workspace response delay; normal mode is zero and cannot enable the hook unless
test endpoints are explicitly enabled. The assertion captured the actual Host
iframe as `invisible` with its connection overlay visible before the delayed
workspace response, then observed the bridge becoming ready.

Check J was completed after the generic Host projection shipped in ControlDeck
PR #214 (merge `60ab09d8`). No Media-specific route, dependency, tool, or
capability was added to ControlDeck. An isolated ControlDeck process generated a
0600 OpenCode runtime config whose local stdio MCP projected the current effective
Add-on agent tools. External OpenCode 1.18.18 reported
`controldeck_addons connected` and discovered these three public contributions:

```text
media.capabilities
media.generate
media.inspect
```

The stdio MCP called `media.capabilities` through the real Host endpoint and
received ControlDeck Job `4aa6c2f74ae9` plus opaque asset ID
`job-result:4aa6c2f74ae9`. With that token still alive, disabling Media Forge
changed discovery from 3 tools to 0; re-enabling changed it from 0 to 3. This
proves discovery is based on current Host availability rather than a stale
startup snapshot.

Finally, a real `opencode run` process called
`controldeck_addons_media_capabilities` exactly once, received Host Job
`7966ff194635`, and replied `available`. The process exited 0 in 19.5 seconds.
The tool result contained capability names and fake availability metadata but no
`model_id`, model field, FLUX, or Qwen identity. The first `auto` attempt started
the local 27B model but did not reach a tool call within five minutes; it was
interrupted and is not counted as success. The bounded retry used the already
loaded local model with minimal reasoning and completed.

After verification, Media Forge was disabled and uninstalled through the public
Host API. The isolated Host and Media Forge processes, ports 18770/9134, and the
Qwen3.8-27B instance started for this check on port 8097 were stopped. The
token-bearing runtime config and login cookie were deleted.

## Implemented artifacts

- `mf.sh`: non-root guard; Python 3.11+ check; independent data directory; shared cache discovery; stamp-based core/runtime creation; broken-venv rebuild; doctor/build/list/prune/test/serve commands; disk preflight; real ROCm tensor verification; cheap health snapshot generation.
- `requirements.txt`: lightweight core dependencies only. Importing `torch` in the final core environment exits 1 with `ModuleNotFoundError`.
- `runtimes/rocm-torch/`: ROCm 7.2.1 PyTorch 2.10 requirements, size/download metadata, and `.refs` containing `image`. The runtime environment is not shared with core or ControlDeck.
- `config/config.yaml`: Media Forge data defaults to `~/.local/share/control-deck-media-forge`; model libraries remain explicitly unset; `auto_provision=true` starts a visible, locked background runtime build when the environment is missing.
- Environment health is read from `config/environment-status.json`, an ignored snapshot written outside the request handler. Missing/invalid snapshots fail closed as `setup_required`.

Final Python prefixes observed:

```text
core_prefix=/data1tb/ControlDeckMediaForge/.venv
runtime_prefix=/data1tb/ControlDeckMediaForge/runtimes/rocm-torch/.venv
```

## Section 10 real-machine evidence

Host:

```text
Python 3.12.3
ROCm 7.2.1.70201-81~24.04
AMD Radeon AI PRO R9700 / gfx1201
repository filesystem=/dev/nvme0n1p1 ext4
repository filesystem total=983349346304 bytes
```

### 1–4. Retreated state, doctor, cold core start, and health

Both Media Forge venvs were absent for the initial check. `./mf.sh doctor` reported `core_env=missing`, `rocm_runtime=missing`, `model_library=missing`, and both ROCm tools. It selected these shared paths:

```text
PIP_CACHE_DIR=/data1tb/ControlDeck/data/cache/pip
UV_CACHE_DIR=/data1tb/ControlDeck/data/cache/uv
HF_HOME=/data1tb/ControlDeck/data/cache/huggingface
```

Tree hashes before and after the clean `doctor` call were identical:

```text
Media Forge: 35949df532f0149d45eb66f81e7e4dc0622417e95e62b00cedd86cd10324c156
ControlDeck:  8bf954ab6dbce61bd79e58543010ee800825364d6313b74008a89ff006ed5842
```

`./mf.sh serve` created the core environment and served real HTTP in 5.835 seconds. Its cold size was 115724645 bytes. `GET /health` returned HTTP 200 with `status=setup_required`, `rocm_runtime=missing`, and `gpu=checking`.

After the final implementation, a missing runtime stamp was exercised again with automatic provisioning disabled. The real health response included the measured/index-derived estimate:

```text
rocm_runtime.state=missing
rocm_runtime.message="Run ./mf.sh env build rocm-torch; estimated download 2100000000 bytes"
gpu.state=checking
```

### 5–6. Clean runtime construction and actual GPU execution

Before download, `./mf.sh env build rocm-torch` displayed:

```text
runtime=ROCm 7.2.1 PyTorch 2.10 runtime
estimated_download=2100000000 bytes
available=809378115584 bytes
required_with_headroom=8589934592 bytes
```

From runtime-venv creation to installed Torch metadata was 225 seconds. From creation to the final successful GPU snapshot was 264 seconds. The latter includes correction and reruns described below. Final runtime size was 4445904539 bytes. The shared pip cache gained 45 files / 1956470511 bytes.

The first construction attempt installed the packages and then exposed a `set -u` wrapper defect (`snapshot: unbound variable`). That defect was fixed rather than recorded as success. PyTorch then warned that NumPy was absent; NumPy was added to the runtime requirements and the clean final GPU check was rerun.

The final real GPU operation produced:

```json
{
  "torch_version": "2.10.0+rocm7.2.1.gitb07cec22",
  "hip_version": "7.2.53211",
  "device_count": 2,
  "devices": [
    {
      "name": "AMD Radeon AI PRO R9700",
      "gcn_arch": "gfx1201",
      "total_memory_bytes": 34208743424
    },
    {
      "name": "AMD Radeon Graphics",
      "gcn_arch": "gfx1036",
      "total_memory_bytes": 16302784512
    }
  ],
  "selected_device": 0,
  "free_memory_bytes": 33975959552,
  "total_memory_bytes": 34208743424,
  "tensor_result": 16773120.0,
  "elapsed_sec": 0.05090730299707502
}
```

The second device's memory value is the value reported by Torch. `rocm-smi` separately reported a 536870912-byte iGPU VRAM aperture; no inference was made to reconcile those two interfaces.

### 7–10. Warm start, stamps, inventory, and prune safety

- Warm `./mf.sh serve` logged `core requirements unchanged; skipping pip` and reached HTTP readiness in 0.277 seconds.
- A real health request took 0.001537 seconds; repeated requests were 0.001487 and 0.001473 seconds, all below the three-second contract.
- Adding one line to top-level `requirements.txt` caused the next start to log `installing core dependencies`. Restoring the final file caused one final install, and `.venv/.req-stamp` exactly matched the final requirements SHA-256 `875d8f1916f28b5f0e3f98c0302a3664ae21e9a1e671ee1512ab24881fa0ca40`.
- A deliberately non-executable/missing core `bin/python` was detected as broken. `mf.sh` removed only the approved core venv path, rebuilt it, and the resulting real service returned HTTP 200 in 0.001473 seconds.
- With `auto_provision=true` and the runtime stamp retreated, `mf.sh serve` logged the runtime name, 2100000000-byte estimate, 802764632064-byte capacity result, and started a lock-protected background build. It restored the stamp, reran the real GPU operation, and reported a zero-byte pip-cache delta. With `auto_provision=false`, the same missing-stamp setup did not build, remained `setup_required`, and exposed the manual build action.
- Final `./mf.sh env list` output:

```text
core       state=current size_bytes=116345980 refs=-
rocm-torch state=current size_bytes=4445904539 refs=image
```

- `./mf.sh env prune` printed `keeping rocm-torch: referenced by image`; size remained 4445904539 bytes. Core was never a prune candidate.
- With a temporary required capacity of 9999999999999 bytes, build exited 1 before installation, reported the actual 802764906496 bytes available, preserved runtime size and stamp, and exposed `rocm_runtime.state=error` in the health snapshot. The committed requirement was restored to 8589934592 bytes.

### 11. Shared cache evidence

The runtime used ControlDeck's configured cache root without importing or executing ControlDeck code. The two largest downloaded wheels were present in that shared pip cache:

```text
torch body:  1645259227 bytes, mtime 2026-08-21 08:00:13.355694214 +0900
triton body:  301690151 bytes, mtime 2026-08-21 08:00:44.899307331 +0900
pip cache:   2369228186 bytes total after the run
HF_HOME:     /data1tb/ControlDeck/data/cache/huggingface
HF dir mtime: 2026-08-18 08:13:25.254909152 +0900
```

No model was downloaded in MF0-0, so `HF_HOME` contained no new file and its mtime did not change. Model-cache reuse is therefore NOT TESTED rather than inferred. A warm runtime rebuild reported `pip cache delta: 0 bytes`.

Explicit user cache values were preserved exactly. Running doctor with `/tmp/mf00-user-{pip,uv,hf}` values printed those same paths and did not create them. With all cache variables unset and an unreadable ControlDeck config, doctor warned and selected Media Forge's own `data_dir/cache/{pip,uv,huggingface}` paths.

### 12. Persistent-data independence

No data was deleted. Canonical paths and filesystems were observed as:

```text
Media Forge: /home/souten/.local/share/control-deck-media-forge
             /dev/sda2, device 2050
ControlDeck: /data1tb/ControlDeck/data
             /dev/nvme0n1p1, device 66305
media_inside_controldeck=no
controldeck_inside_media=no
```

The Media Forge path still contained `media-forge.sqlite3`, `assets/`, and `work/`. Thus deleting either configured tree cannot select the other tree by containment. This is the requested non-destructive path proof; actual deletion was intentionally not performed.

## Additional behavior checks

- Temporarily removing the GPU snapshot left the real core service running. Health returned HTTP 200 / `setup_required`, with `gpu.state=checking`; restoring and rerunning the GPU check returned it to `ok`.
- Latest full `./mf.sh test`: 52 passed in 3.37 seconds with one upstream Starlette/httpx deprecation warning. Core and runtime `pip check` both reported no broken requirements. This is regression evidence only, not runtime proof.
- `bash -n mf.sh` and `git diff --check` passed. These are static checks only.
- ControlDeck's generic Context Action route gap was fixed and merged separately
  in ControlDeck PR #213 (`a5e4fc7`). No Media-specific route, action, dependency,
  or implementation module was added to the Host.

## NOT TESTED / intentionally deferred

- Worker-pack enable/disable mutation of `.refs`: no worker-pack lifecycle is present yet. The current non-empty reference and prune protection were tested.
- Hugging Face model download/cache reuse: no model adoption or weights belong to MF0-0.
- Model library configuration: deliberately remains `missing`; selecting and benchmarking a model belongs to G1.
- ControlDeck Jobs creation, Broker waiting reason, and lease cleanup were
  observed through the real Host API during the browser run. Dedicated visual
  inspection of the Jobs/Broker detail screens and their cancel controls remains
  NOT TESTED.
- Hosted service-shutdown failure and lease cleanup are covered by contract tests
  but not a separate current real-process crash run. Active disable, Host cancel,
  and their lease releases were measured through public APIs.

## Scope boundary

MF0-0 through MF0-7 / G0 through G2 are complete. The real image route, R9700
acceptance evidence, and trusted release-bundle standard installation path were
exercised end-to-end. Media Forge PRs #10/#11/#14 and ControlDeck's generic provider
PRs #216/#217/#219 are merged. G2's measured editing and bounded semantic-review
evidence is recorded below. G3 and later have not started.

## G1 — local image generation (COMPLETE, 2026-08-21)

### Adopted route and model gate

`black-forest-labs/FLUX.2-klein-4B` at immutable revision
`e7b7dc27f91deacad38e78976d1f2b499d76a294` is installed in the shared NVMe
Hugging Face cache and is the measured automatic `image.text_to_image` route.
The pinned weight set is 15,964,212,614 bytes; the cache repository occupied
15,988,907,862 bytes. A repeated `./mf.sh model download flux2-klein-4b`
completed in 0.36 seconds with 51,144 KiB maximum RSS and did not re-download
weights. The provenance weight identity is
`sha256:f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278`;
license is Apache-2.0. `docs/models.md` records all ten adoption-gate answers.

The production registry exposes only `image.text_to_image`, state `available`,
installed/healthy true, and confidence `measured`. `model_id` remains optional
and internal routing still accepts `auto / fast / balanced / quality /
low_vram / manual`. Premature edit capabilities were removed rather than
claiming G2 behavior.

### Cold-load diagnosis and bounded optimization

Media Forge uses Diffusers, not ComfyUI, so ComfyUI Dynamic VRAM flags were not
applicable to this route. The directly observed slow path was CPU/mmap loading
followed by `pipeline.to("cuda")`: one 512x512 job took 852.587283 seconds.
`device_map="cuda"` alone was still over 142.209076 seconds when canceled, and
Diffusers-only mmap disabling still left the Qwen3 text encoder loading after
353.455380 seconds when canceled.

The adopted adapter explicitly loads `Qwen3ForCausalLM` and the FLUX pipeline
with direct device placement and mmap disabled. Equivalent jobs then measured
37.284804 seconds on the first optimized attempt, 25.762736 seconds on the
second, and 14.936748–15.789333 seconds after cache/compiler warm-up. Enabling
Hugging Face parallel loading reduced measured 512 load from 11.508421 to
10.589401 seconds (about 8% of load time); it is retained as a secondary
optimization, not described as the root fix. Persistent NVMe Hugging Face,
AMD COMGR, and MIOpen cache paths are exported by `mf.sh`.

On 2026-08-22 the direct route was hardened against silent regression into
offload. After load, the worker inspects component devices, device maps, and
Accelerate hooks; `direct_device_map` fails rather than succeeding if any
CPU/disk/meta target or CPU/offload hook is present. The final real Workflow /
Broker run completed in 15.049693 seconds (load 10.426083, generation 1.487908)
with pipeline, text encoder, transformer, and VAE all on `cuda:0`, zero offload
hooks, zero non-GPU targets, a released lease, and a 168,170-byte PNG.

The bounded `cpu_offload` comparison completed in 40.504328 seconds on its first
valid run (load 25.533552, generation 7.037108; sampled incremental peak VRAM
8,879,714,304 bytes) and 18.069923 seconds after cache warm-up (load 9.655885,
generation 4.586891). It left all four components on CPU between calls and the
worker detected offload hooks on the text encoder, transformer, and VAE. A
separate direct sample used 21,819,142,144 incremental bytes. Identical seed and
settings produced the same SHA-256 on both routes. The first aggressive-observer
attempt that caused `host_unreachable` is excluded, not relabeled as a model
failure. These observations retain direct placement as default; offload is a
low-VRAM diagnostic tradeoff rather than a speed fix.

This hardening is released as v0.1.2. Relative to the frozen v0.1.1
contract, `addon.json` changes only its release version; contribution IDs,
schemas, agent/workflow inputs, and required asset/provenance fields are
unchanged.

The public GitHub Release artifact
`control-deck-media-forge-0.1.2-linux-x86_64.tar.gz` is 29,043,648 bytes with
SHA-256 `855303fd90e25e2ff2886b255fd98365c862eb417e0e57268cb0e8a27c06916c`.
Its release digest, downloaded file, and ControlDeck trusted-catalog pin agree.
The archive contains neither a venv nor model weights; its packaged provision
reused the persistent runtime/model cache and completed in 4.972467 seconds.

ControlDeck PR #219 installed that exact public bundle through the standard
release-bundle provider in 18.375702 seconds. A real Workflow/Broker generation
then completed in 13.327802 seconds (load 9.265287, generation 1.483399), with
all four inspected components on `cuda:0`, no offload hooks or non-GPU map
targets, and the lease released. A final exact-PR-head Chromium run traversed
Settings disable/enable, the opaque Media iframe, Models, Create, Library, and
Provenance in 16.2 seconds with zero page errors. Its separate image job took
12.888887 seconds (load 9.013070, generation 1.458398), again with direct GPU
placement and zero active/waiting Broker work afterward.

A fully empty Hugging Face cache download of approximately 15.99 GB remains
NOT TESTED. The release download and warm persistent-cache reuse above are not
presented as empty-cache model-download evidence.

### R9700 measurements and lease envelope

All measurements below used the AMD Radeon AI PRO R9700 / gfx1201, ROCm, local
NVMe, four inference steps, and a separate PyTorch worker process:

```text
1024x1024 first product job:       208.820067 s (included first kernel compilation)
1024x1024 repeated product job:     18.009386 s
1024x1024 parallel-loading repeat:  17.933032 s
  adapter load / generation:        11.344260 / 3.537276 s
512x512 committed-manifest job:     15.031645 s
  adapter load / generation:        11.140961 / 1.471561 s
worker peak RSS:                    16,384,692,224 bytes
worker peak swap:                   0 bytes
resident VRAM:                      0 bytes
execution peak VRAM:                29,625,200,640 bytes
cold-load peak VRAM:                32,275,578,880 bytes
headroom:                            1,073,741,824 bytes
broker reservation:                33,349,320,704 bytes
R9700 total VRAM:                   34,208,743,424 bytes
```

The static lease estimate conservatively uses the worst observed cold-load
peak. Every measured success acquired a Host lease, declared
`estimated_runtime_sec=208.820067`, renewed it, and released it. Eight requested
optimized generations completed without an unrequested failure. The two slow
diagnostic variants were explicitly canceled and are not counted as failures.

### Real product behavior

- The same prompt/settings/seed produced byte-identical 512 and 1024 pairs.
  The 1024 sample SHA-256 is
  `bf83e5941312a6221b13b5c604876ba6b4ea2322c60b4265472f5d756ccdc162`.
- The requested adult tomboy anime character with orange mesh hair was generated
  by Media Forge itself. The retained 1024 asset is
  `/data1tb/mediaforge-g1-e2e-XOqcbh/media-optimized-final/assets/asset_4134e5db722a401e9cac8d5106277f6a.png`.
- An installed-host Playwright run completed Create -> ControlDeck Job -> Library
  preview -> provenance in 17.551425 seconds. It observed a succeeded Host job,
  a 512x512 asset, the real model/hash/license, and zero console/page errors.
- Host cancellation at two seconds ended the Media job as `canceled` in
  2.5947 seconds and left zero active leases.
- SIGKILL of the sole real worker PID during a leased 1024 job was normalized to
  `worker_crash` (`worker exited with code -9`) in 2.431407 seconds. The lease
  count returned to zero and the core remained `healthy`.
- With a live 15,891,902,464-byte llama.cpp model, managed Broker policy retained
  chat availability (`READY`) and placed the image request in `waiting` with
  reason `yield_load_cost_unknown`, queue position 1, cancel/lower-priority
  actions, and the LLM identified as a yieldable blocker. It did not silently
  overcommit or kill chat merely to satisfy the image request.
- Latest full Media Forge regression run: 80 passed in 3.95 seconds with one
  upstream Starlette/httpx deprecation warning. This is regression evidence,
  not the runtime evidence above.

### Release-bundle standard installation

GitHub Release `v0.1.1` publishes the verified linux-x86_64 artifact used by the
trusted ControlDeck catalog. It is 29,041,267 bytes with SHA-256
`66dfb88425d61e533e5ca8b45e0e19169e07e66cbc9ba1846364de4177981d4a`.
The bundle contains the packaged core and pinned runtime recipe, but no source
checkout, prebuilt venv, PyTorch wheels, or model weights. Its `provision`
lifecycle builds the persistent worker venv and verifies GPU/model readiness
before the provider can select the version.

An isolated real ControlDeck updated the public v0.1.0 bundle to v0.1.1 in
37.914599 seconds. During provisioning, `current` and PID 1599352 remained on
v0.1.0. After smoke/health, both version trees remained and `current` switched
atomically to v0.1.1/PID 1627743. The persistent ROCm venv occupied
4,686,979,949 bytes; the shared NVMe pip/model caches were reused. Health
reported R9700/gfx1201, PyTorch 2.10.0+ROCm 7.2.1, and an installed/healthy
model.

A post-switch health-gate fault injection exercised rollback through the real
version tree, systemd service, and Add-on registry. `current`, the running
service, and the enabled manifest returned to v0.1.0 in 10.4 seconds; a normal
API update then restored healthy v0.1.1. This is an explicit health failure
injection, not a claim that a public release was naturally unhealthy.

The installed v0.1.1 bundle generated through the real ControlDeck
Workflow/Broker path. It acquired a 33,349,320,704-byte lease, renewed it six
times, released it, and produced a 512x512 PNG of 128,589 bytes with SHA-256
`9a1920654a48007c4917385d05af43a82d144803c66c19cefb906a9e93be962e`.
Its provenance identifies FLUX.2 Klein 4B, Apache-2.0, and Media Forge 0.1.1.
A Chromium Settings -> enable -> Media -> Create -> Library -> Provenance run
also produced a 159,515-byte PNG, passed in 19.5 seconds, and observed no page
errors or active lease after completion.

The isolated uninstall stopped and removed the managed service, disabled and
unregistered the Add-on, and removed `current`, `versions`, and `downloads`.
The provider reported `installed=false`, `enabled=false`, `not-installed` and
required no Host reload. Persistent feature data remained exactly
4,687,592,191 bytes / 8 files, including both generated PNGs (128,589 and
159,515 bytes); the worker runtime and shared cache were not deleted.

After the lifecycle environment was hardened and ControlDeck PR #217 was
merged, its exact provider contents were run again against the isolated host.
Install job `de4cf085cfd3` completed in 11.521913 seconds from persistent warm
runtime/cache state and returned v0.1.1 / healthy; the live service again
reported R9700/gfx1201, ROCm 7.2.1, and model installed/healthy. A second real
uninstall returned `not-installed` and left the same 4,687,592,191 bytes / 8
files. This closes the gap between the pre-hardening runtime evidence and the
merged provider implementation.

Media Forge full regression at the released code completed with 80 passed in
8.01 seconds. ControlDeck provider final-head regression completed with 738
passed / 1 skipped in 61.79 seconds, frontend production build transformed
1,542 modules, and the installed-bundle browser E2E passed. These are regression
evidence and do not replace the real process observations above.

### G1 public contract freeze

The public contract is frozen at Media Forge commit `b29cec0` / release v0.1.1.
The freeze covers `schemas/*.json`, `addon.json` contributions, agent tool and
workflow executor names/inputs, and required asset/provenance fields as
documented in `docs/api.md`. The recorded SHA-256 values are:

```text
addon.json                    30d1c9f64c7069eb556cc9ef1bf10bc1fc508855c1a32ca98d32fed6bd1d2583
asset-reference.json          76bcdf271278cc206d1595a8ea5d96737382d9ed2c8649ea9856acfac5c7147b
asset.json                    51903d157035ccb75e6384ea4fb63b5180e847be1890cecc3a8560bd61510241
empty-input.json              c26eb030dfc9f52409427dd4e03b4dc270b2151d534e864ac546531607d753af
job-reference.json            41191771b145ff3984e658622a57d1d6d154fb608b54e139ed02f44f761c34ab
job-request.json              e5f42b412f39f37e3435717aba4a1ba0af15e99d25bcfaef89a179151ced43f4
model.json                    a1495f9f2ee395a1865fbcd73a8a77baf2e8a1a9eaefec918d8412884a963234
provenance.json               9579f96c0921176617474867515b1797cb68aa0a62c3dbd8c1bbb5d1f89b8697
```

Future goals may add capabilities or optional fields. A breaking change first
requires the documented impact, migration, and contract/schema version bump.

### NOT TESTED / intentionally deferred

- A kernel page-cache drop was intentionally not performed on the shared host;
  fully cache-cold storage timing is NOT TESTED.
- Qwen-Image fallback was not downloaded or benchmarked because the adopted
  route passed the measured gate.
- A natural hardware OOM is NOT TESTED. Error normalization and admission-floor
  adjustment are covered by tests; unsafe oversized requests are rejected by
  model limits before lease acquisition.
- A fully cache-empty download of the pinned 15.99GB model is NOT TESTED. Both
  direct bundle provisioning and the ControlDeck update reused the verified
  shared NVMe model cache; this is not reported as cold-download evidence.
- The installed-bundle Settings/Create E2E used a 1280x800 Chromium viewport.
  A separate 320px mobile Settings layout run is NOT TESTED; Media uses the
  declared companion surface rather than squeezing the workspace into mobile.
- G3 character consistency and G5 M5Stack expression/gesture variants have not
  started out of roadmap order.

## G2 — image editing (COMPLETE, measured 2026-08-22)

The existing frozen `image.edit` operation now accepts exactly one imported
source asset plus `strict_edit=true` and an `editable_mask_asset_id`. Imports
are bounded PNG/JPEG byte streams; neither the public API nor the opaque
workspace transport accepts a filesystem path. Masks are canonical RGBA PNGs,
must match the source, and empty/full masks fail explicitly before GPU
admission.

The worker sends only the bounded mask crop to the model. Core then composites
the patch, recopies protected pixels from the immutable source, and runs an
independent RGBA-channel comparison. Any protected-pixel difference produces
`strict_edit_invariant_failed` and no asset. Provenance records source and mask
hashes; lineage contains the source as the parent. No schema or Add-on
contribution changed after the G1 freeze.

Real R9700 acceptance used isolated Media Forge and ControlDeck data, the
installed-host agent route, a real Broker lease, the retained Media Forge G1
anime character, and a 10,179-pixel mouth mask:

```text
first accepted edit:       17.772403 sec (load 9.037687, generation 5.164945)
same-seed repeat:          13.942717 sec (load 9.045363, generation 1.394409)
third-generation edit:     14.959 sec (load 10.085912, generation 1.329025)
protected pixel changes:   0 in every accepted output
editable pixels changed:   10,154 of 10,179
same-seed output hash:     identical
three-generation lineage: source -> edit -> re-edit
sampled worker peak RSS:   8,743,202,816 bytes
sampled worker swap:       0 bytes
sampled absolute VRAM use: 17,898,610,688 bytes
lease after completion:    active 0 / waiting 0
invalid full mask:         failed / invalid_edit_mask / asset count 0
```

The first real attempt found a product defect rather than producing accepted
evidence: the worker completed in about 27.4 seconds but the agent endpoint's
25-second bounded wait returned 504 first. The wait is now 110 seconds, below
the Host's 120-second generic execution timeout; three later runs passed. This
failed attempt is not counted as a successful generation.

Installed-host Chromium then exercised Create operation selection, chunked
source/mask upload through the authenticated opaque iframe transport, real edit,
Library, and provenance. It completed in 17.786943 seconds, added exactly three
assets, observed protected difference 0 and editable pixels 10,179, and recorded
zero console/page errors. After the final fail-closed/upload-cleanup audit, the
exact branch was restarted and the same browser route passed again in 32.869204
seconds (adapter load 9.219171, generation 17.133812), again adding exactly
three assets with protected difference 0 and no browser errors. Evidence is
retained at `/data1tb/mediaforge-g2-e2e.Frwz2w/browser-final/`.

The host had approximately 3.9 GB of globally allocated swap during diagnosis,
mostly stale pages from unrelated long-lived processes. Media Forge worker swap
was zero and `vmstat` showed no sustained swap-out. RAM shortage/pagefile
thrashing is therefore not the cause of the observed 12-minute-class G1 load;
the measured direct-placement/mmap path remains the applicable fix.

Focused strict-edit, worker, adapter, and host-transport regression completed
with 49 passed. Full `./mf.sh test` completed with 101 passed in 5.41 seconds.
These are regression evidence only; the product evidence is the real
process/browser run above.

### Outpaint

Outpaint remains the existing `image.edit` operation with
`edit_mode=outpaint`, `strict_edit=true`, and a larger target canvas. It accepts
no mask because the exterior region is derived deterministically. The source is
centered, recopied after model generation, and independently checked before
registration. Crop-sized, unchanged-sized, non-multiple-of-16, non-strict, and
caller-mask combinations fail before worker execution.

A real installed-host Chromium run extended the retained Media Forge-generated
512x512 anime character to 768x512:

```text
first browser total:        108.756109 sec
  load/generation:           10.742962 / 92.188142 sec
warm separate-worker total:  19.807051 sec
  load/generation:           10.774391 / 3.397528 sec
source RGBA differences:     0 across 262,144 pixels
generated exterior:          131,072 pixels
same-seed repeat:             byte-identical 281,762-byte PNG
lineage:                      imported source -> outpaint result
browser errors:               0
placement/offload:            all cuda:0 / hooks 0 / non-GPU targets 0
Broker after each:            active 0 / waiting 0
```

The first route-specific compile cost is recorded rather than hidden. The warm
run came from a new worker process and reused persistent NVMe/ROCm caches.
Visual inspection found the entire character unchanged and the gray background
continued naturally into both generated side regions. Evidence is retained at
`/data1tb/mediaforge-g2-e2e.Frwz2w/outpaint-browser/` and
`outpaint-browser-warm/`.

Focused outpaint/edit/adapter/API/host regression completed with 85 passed.
Full `./mf.sh test` completed with 118 passed in 9.65 seconds. These are
regression evidence only.

### NOT TESTED / remaining limits

- Natural OOM during edit is NOT TESTED. Existing conservative G1 lease values
  remain in use; the sampled absolute VRAM value is not substituted for the
  lease envelope.
- A 60-second Host iframe proxy read bound returned 502 before the intentionally
  failing 108-second two-candidate semantic review reached its terminal state.
  The durable Media Forge and ControlDeck Jobs continued, stopped at the stated
  retry budget, and released the lease. Long synchronous agent-tool UX belongs
  to G4 and is not claimed as solved by G2.
- No release version is assigned by this source-development slice.

### Single-reference edit, inpaint, and variation

PR #16 merged the strict masked compositor and validator as Media Forge main
`18960a8`. The next additive slice keeps `image.edit` and exposes an `edit_mode`
constraint: `reference` for whole-image instruction editing, `variation` for a
new alternative from one source, and `inpaint` for strict masked editing. The UI
requires a mask only for inpaint and clearly warns that reference/variation may
change the whole image. Invalid combinations fail before GPU admission.

The first 1024x1024 variation job found a new first-use cost: load completed in
9.424858 seconds, while reference-image ROCm compilation/generation took
229.208449 seconds. Its 180-second browser assertion timed out, so it is not
reported as a browser pass. The underlying job succeeded and released its
lease. Two cache-warm, separate-worker installed-host Chromium runs then passed:

```text
variation:       27.002184 sec browser total; load 9.655933; generation 10.720631
reference edit:  25.875298 sec browser total; load 10.693552; generation 9.148814
final exact branch variation: 25.737216 sec; load 9.577456; generation 9.121249
assets per run:  source import + one lineage child
output pair:     identical 1,447,679-byte PNG / SHA-256 b03dd63d...778689
browser errors:  0
placement:       pipeline/text encoder/transformer/VAE cuda:0; offload hooks 0
Broker after:    active 0 / waiting 0
```

The final exact branch also reported `available` for single-reference edit,
inpaint, variation, and strict edit, and the post-run Broker query returned
active 0 / waiting 0.

Visual inspection confirmed the requested cheerful two-hand waving pose while
retaining the orange mesh hair and black/orange hoodie. This is edit quality
evidence for this sample, not a G3 consistency claim. Evidence is retained under
`/data1tb/mediaforge-g2-e2e.Frwz2w/variation-browser-warm/` and
`reference-browser-warm/`.

Focused editing/API/host regression completed with 68 passed. Full
`./mf.sh test` completed with 106 passed in 5.62 seconds. These are regression
evidence, not substitutes for the real browser and worker observations above.

### Multi-reference edit

`image.edit` now accepts `edit_mode=multi_reference` with 2..4 asset inputs.
The first input is the editable primary and sole lineage parent; additional
inputs are visual references, and provenance hashes every input. Strict mode is
rejected for this path. The worker receives only contained job-local copies and
the FLUX.2 adapter uses its official image-list input; model identity remains
absent from capability/tool responses.

Real installed-host Chromium used a Media Forge-generated 512x512 primary and
two Media Forge-generated references. Both separate-worker runs succeeded:

```text
first browser total:          28.895831 sec; load 9.890928; generation 11.739208
repeat browser total:         21.830374 sec; load 9.882474; generation 4.771229
assets per run:               3 imports + 1 result
lineage parent count:         1 (primary)
provenance reference hashes:  3
same-seed result:             byte-identical 352,021-byte PNG
browser errors:               0
placement/offload:            all cuda:0 / hooks 0 / non-GPU targets 0
Broker after each:            active 0 / waiting 0
```

Visual inspection confirmed that features from all routes were reflected: the
primary black/orange design and hoodie, orange mesh detail, and the referenced
two-hand waving pose. This does not claim the broader G3 identity metric.
Evidence is retained under
`/data1tb/mediaforge-g2-e2e.Frwz2w/multi-reference-browser/` and
`multi-reference-browser-repeat/`.

Focused multi-reference/edit/adapter/API/host regression completed with 90
passed. Full `./mf.sh test` completed with 123 passed in 6.54 seconds. These are
regression evidence only.

### Bounded semantic review

The frozen `qa.semantic` and `qa.max_regeneration_attempts` fields now drive an
optional local VLM review. The reviewer endpoint is restricted to a loopback
HTTP origin; its request forces `num_gpu=0`, `temperature=0`, a 4,096-token
context, structured output, and a 768x768 / 2 MiB maximum review image. Core has
no VLM/torch dependency. `image.semantic_review` is unavailable when the exact
configured model is absent.

Deterministic validation of every candidate completes before the first VLM
call. With the default retry budget zero, rejection is advisory and is retained
as a provenance warning. A positive budget is explicit opt-in: only `count +
budget` candidates are generated and all-rejected output fails with
`semantic_review_exhausted`; a semantic pass never overrides a deterministic
failure.

The optional reviewer is Ollama `qwen3-vl:2b`, ID `0635d9d857d4`, 1.9 GB,
Apache-2.0. Direct R9700-host measurements using the retained Media
Forge-generated 512x512 character were:

```text
first CPU-only review before bounded-JPEG change: 40.665945 sec
warm review before bounded-JPEG change:           16.612088 sec
exact bounded-JPEG cold review:                   31.289228 sec
exact bounded-JPEG warm review:                   13.745254 sec
Ollama processor:                                 100% CPU
review runner RSS observed:                       about 3.0..4.3 GiB
review runner swap:                               0 bytes
GPU VRAM before/after direct review:              184,848,384 / 184,848,384 bytes
```

A real ControlDeck agent/Broker product job generated a new 512x512 image and
then reviewed it successfully in 40 seconds. The exact final branch repeated
the same job in 35 seconds as asset
`asset_c99a931c8d624d6baeee6262682f3757`. It recorded the real FLUX model, reviewer,
passed deterministic validators, semantic result, seed, license, and output
SHA-256 `8f6b4aa1...69fd78c`; the two outputs were byte-identical and all 17 observed
Broker leases were released with zero waiting requests after the run.

A second real strict-edit job deliberately requested a full-scene blue
elephant through a small edit mask. Both VLM reviews rejected the two bounded
candidates and the durable job failed explicitly with
`semantic_review_exhausted` at retry budget one after about 108 seconds. No
asset was registered and the Broker lease was released. Full `./mf.sh test`
completed with 133 passed on the final branch. These are regression evidence
only; the real jobs above are the runtime evidence.

## UX1 — workspace UI/UX (DESIGNED, NOT IMPLEMENTED, 2026-08-22)

設計と実装指示のみを追加した段階であり、**コードは 1 行も書いていない**。
実測値は存在しない。以下はすべて「未実施」である。

```text
docs/design-workspace-ux.md            設計の正（IA・段階開示・レイアウト・文言表・却下案）
docs/implementation/ux1-workspace.md   PR-U0〜U7 の実装指示とテスト計画
docs/base-plan.md §16                  ナビゲーション決定を改訂（7 項目 → 3 + 設定）
docs/base-plan.md §3.9 / §3.10         却下案を追記（平坦な全表示 / host 側モバイル画面）
```

### 設計が解こうとしている実測済みの欠落

G0 の workspace のまま G1〜G3 を積んだ結果として、以下がコード読解で確認済み。

```text
モバイル       addon.json が mobile: "companion" のため、ControlDeck は 768px 未満で
               AddonCompanion（状態カードのみ）を描画する。asset も進捗も出ない。
書き出し       host.file.export と host files bridge は実装済み（/test/host-files/roundtrip で
               疎通実績あり）だが、workspace UI に書き出し導線が 1 つも無い。
マスク作成     inpaint はマスク PNG を要求するが、UI はファイル選択のみ。
capability     /api/v1/capabilities を UI が呼んでいない（出し分けが無い）。
進捗           pollJob が create-status ノードにのみ書き込み、タブ移動で見えなくなる。
ライブラリ     asset ごとに assets.content（実測 1.4 MB 級）を直列取得している。
G3 UI          profile / reference collection の UI が存在しない。
```

### 契約に対する予定変更（実施前）

```text
公開 API / schemas / workflow / agent tools / provenance 必須項目   変更なし
/ws への追加メソッド                                                実装詳細として追加予定
addon.json  mobile: "companion" → "embedded" / version 0.1.2 → 0.2.0  実施前
ControlDeck リポジトリ                                              変更しない（差分 0 行が完了条件）
```

`embedded` への変更は、モバイル専用 IA を実装した PR でのみ行う。
未実装のまま宣言だけ変えることを禁止する（縮小 workspace は UX 規約違反）。

### NOT TESTED（このセクション時点ですべて未実施）

```text
新 /ws メソッドの実装・テスト
モバイル埋め込みの実機確認（状態カードではなく workspace が出ること）
マスクエディタ
書き出しの sha256 一致
サムネイル導入前後の転送量比較
push 更新の遅延測定
320px / 390×844 でのレイアウト実測
```

### PR-U0 — workspace transport foundation (IMPLEMENTED, measured 2026-08-22)

`/ws` に表示系メソッドを追加した。公開 API・`schemas/`・`addon.json` は変更していない。

```text
capabilities.get   公開 capability document + サイズ envelope + clamp 済み preset
library.list       asset に由来(generated/edited/imported)・要約・保護画素差分を付与
                   edit_mask は既定で除外。ページングは読み取った最古行を基準にする
assets.thumbnail   WebP・長辺 512px 上限・64KiB 上限・data_dir/thumbnails へキャッシュ
preferences.*      ControlDeck identity subject 単位。allowlist 外のキーを拒否、4KiB 上限
jobs.watch/unwatch job.changed を push。接続あたり 10 job、200ms 間引き、終端で自動解除
```

#### 実測（本開発機、fake worker 構成、1024×1024 ノイズ画像 50 枚）

`assets.list` + `assets.content`（現行 app.js の経路）と、
`library.list` + `assets.thumbnail` を同一データで比較した。
`/ws` は base64 で運ぶため、content の実バイト数を 4/3 倍して計上している。

```text
元 PNG 1 枚:                        295,396 bytes
before  転送量 50 枚:            19,715,361 bytes (18.80 MiB)
after   転送量 50 枚:             2,777,682 bytes (2.65 MiB)
削減:                                  85.9%
after   生成込み所要:                 1.163 sec
after   キャッシュ命中時:             0.009 sec
最大サムネイル:                      41,392 bytes（上限 65,536）
```

サムネイル形式は測定で決めた。同じ画像を 256px へ縮小したとき PNG は
220,714 バイトで 64KiB に収まらず、解像度を 128px まで落とす必要があった。
WebP q80 は 256px を保ったまま 41,392 バイト。実装は画質を先に譲り
（80→65→50）、それでも収まらない場合にだけ解像度を下げる。

#### 確認したこと

```text
./mf.sh test                      155 passed（追加 17 件。従来 138 件は不変）
新メソッドの host identity 要求    未認証接続は従来どおり 4401 で切断
reject_host_paths                 5 メソッドすべてで unscoped_host_path を確認
listener 例外の隔離               購読側が例外を投げても job 更新が継続することを確認
preferences の秘密漏れ            拒否メッセージに送信値が含まれないことを確認
```

#### NOT TESTED / 未実施

```text
subresource 直接取得の可否（設計 §10.1）
    installed host とログイン資格情報が必要なため未実施。
    PR-U5（書き出し・原寸プレビュー）の着手前までに実施する。
    サムネイルはこの結論に依存しないため、PR-U1〜U4 は先行できる。
実ブラウザでの動作
    本 PR は transport のみ。UI は未実装であり、実機証拠は PR-U7 で取る。
実 GPU での生成を伴う push 挙動
    fake worker 構成でのみ確認。実 worker の phase 遷移頻度は未計測。
```

### PR-U1 — workspace shell (IMPLEMENTED, browser-observed 2026-08-22)

情報構造を 5 タブから 3 ナビ + 設定へ作り替え、段階開示とモバイル専用レイアウトを入れた。

```text
frontend/index.html   3 ナビ・モードトグル・skeleton・詳細断片を <template> に分離
frontend/styles.css   PC 2 ペイン / モバイル単一列 + 下部タブ。edit.css を統合して 1 本化
frontend/app.js       capability による出し分け、preferences 復元、jobs.watch での進捗、
                      library.list + assets.thumbnail での一覧、phase/失敗の日本語化
addon.json            mobile: "companion" -> "embedded" / version 0.1.2 -> 0.2.0
backend/app.py        /activity ルート追加、stylesheet を 1 本に
```

#### 実機ブラウザ観測（standalone、Chromium、light と dark の 2 パス）

`scripts/ux_standalone_e2e.py` を実行。証跡は `/data1tb/mediaforge-ux1-evidence/{light,dark}/`。

```text
desktop 1280x800   2 ペイン / ナビ 3 / シンプルで advanced-* が DOM に 0 件
詳細モード          advanced-* 16 件が出現、モデル方針 6 種、戻すと再び 0 件
capability 反映     video.image_to_video と 3d.image_to_3d を「使えません」と表示
編集操作            画像添付で 5 種が出現し、保護保証の文言が操作と同時に切り替わる
phone 390x844      下部タブが position: fixed、単一列、横スクロール 0px、
                    タップ標的 60px、一覧 2 列
narrow 320x640     横スクロール 0px
console / page error  両パスとも 0 件
初期表示            0.06 sec（standalone・fake ではない実 manifest 構成）
```

崩れを 1 件見つけて直した。`[hidden]` が `.sub-field { display: grid }` に負けており、
「一部だけ直す」を選んでいるのに参照画像の入力と件数バッジ 0 が出ていた。
`[hidden] { display: none !important }` を入れ、E2E に選択と入力の対応を検査する
assertion を追加した（スクリーンショット目視だけでは見落とす種類の崩れ）。

#### 確認したこと

```text
./mf.sh test        171 passed（追加 16 件の静的契約テストを含む）
静的契約テスト       storage API 不使用 / DOM 契約 id / advanced-* が template の外に無い /
                    UI が読む capability が backend の出力の部分集合 /
                    失敗文言の code が実在 / 全 phase に日本語がある /
                    preferences キーが allowlist 内 / addon.json の mobile と version
```

`./mf.sh test` は 1 度だけ
`test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_up`
で失敗した。standalone の開発サーバを同時に動かしていた回であり、その後
単体 1 回・全体 5 回では再現しなかった。原因は特定できていないため、
再発したら記録する。

#### NOT TESTED / 未実施

```text
installed host での埋め込み表示
    768px 未満で状態カードではなく workspace が出ることを実機で未確認。
    addon.json は embedded を宣言済みだが、確認は PR-U7 で行う。
モードの再読込またぎの復元
    preferences の永続化は backend 単体テスト済みだが、UI 経路は standalone では
    /ws を張れないため未確認（standalone は identity を持てない）。
theme token の反映・safe_area・route 同期・通知条件
    host bridge が要るため未確認。
サイズ preset の実値
    standalone では capabilities.get が envelope を返さずフォールバック値を使う。
    実 envelope に基づく preset は installed host で確認する。
マスクを筆で描く経路
    未実装（PR-U3）。現在はマスク画像のファイル指定のみ。
失敗時の「出口」ボタン
    未実装（PR-U4）。現在は日本語 1 文までで、操作は付いていない。
```

### PR-U2 — create experience (IMPLEMENTED, browser-observed 2026-08-22)

作成画面の検証を「GPU を取りに行く前」に寄せ、無視される入力を出さないようにした。

```text
送信前検証   intent 未記入 / manual なのにモデル未指定 / 16 の倍数でない寸法 /
             envelope 外 / inpaint でマスク未指定 / 参考画像 1〜3 枚の範囲外 /
             outpaint が元画像より小さい・広がっていない
             すべて inline error で止め、import も job 作成も行わない
寸法の計測   添付時に createImageBitmap でブラウザ側が測る。
             これが無いと outpaint の可否が受付後にしか分からない
サイズ欄     出力寸法が元画像で決まる操作（inpaint / reference / variation /
             multi_reference）では欄ごと隠す。選ばせた値が無視される状態を作らない
             outpaint では「広げる先の大きさ」に変わり、元画像の寸法を併記する
目安時間     measured な実測がある場合のみ表示
ドロップ     画像のドラッグ&ドロップに対応
```

`<form novalidate>` にした。ブラウザ既定の吹き出しは文言を持てず、モバイルで
見落としやすいため、検証と表示を `requestProblem()` に一本化している。

#### 実機ブラウザ観測（standalone、Chromium、light と dark の 2 パス）

送信は `page.route` で捕捉して 202 を返し、実際の生成は起こしていない
（この開発機には実モデルが入っており、本当に投げると GPU を数分占有するため）。

```text
16 の倍数でない幅 1000      送信されず「幅と高さは 16 の倍数にしてください」
広がっていない outpaint     送信されず「少なくとも片方の辺を大きくしてください。」
manual を選んだ送信         model_policy=manual と model_id が載り schema 適合
既定の送信                  schema 適合 / local_only=true / model_id は載らない
編集を選んだとき            サイズ欄が消え、外側を広げるときだけ戻る
console・page error         両パスとも 0 件
```

捕捉した送信内容は `/data1tb/mediaforge-ux1-evidence/light/submitted-request.json`。

#### 直したこと

```text
envelope 未取得時に寸法検証が丸ごと無効化されていた
    standalone や取得失敗時に「16 の倍数」の規則が受付後にしか効かなかった。
    フォールバック envelope（256〜1024・16 の倍数）を使って必ず検証する。
目安時間の表示が誤解を招いていた
    registry の measured_runtime_sec は初回実行（モデル読み込みと
    カーネルコンパイル込み）の実測 208.82 秒であり、暖まった後の 10〜17 秒台とは
    別物。「目安 209 秒前後」と出すと大きく外れるため、
    「初回は約 209 秒（モデルの読み込みを含む実測）。2 回目以降は短くなります。」に変更。
```

#### 確認したこと

```text
./mf.sh test   172 passed（UI が投げる code にも日本語文言を要求する試験を追加）
```

#### NOT TESTED / 未実施

```text
実際の生成を伴う受付         送信は捕捉して止めているため、GPU 経路は未確認
installed host での検証       envelope の実値・theme・grant は PR-U7
筆でマスクを描く経路          未実装（PR-U3）。現在はマスク画像のファイル指定のみ
outpaint の方向ハンドル       未実装（PR-U3）。現在はプリセットからの寸法指定のみ
失敗時の出口ボタン            未実装（PR-U4）
```

### PR-U3 — mask editor and outpaint (IMPLEMENTED, browser-observed 2026-08-22)

外部ペイントツールが必須だった inpaint を、画面内で完結できるようにした。

```text
マスク編集   canvas に筆で塗る。太さ（短辺の 4% を既定）・消しゴム・取り消し 8 段・全消去
             pointer events で 1 本指描画 / 2 本指ピンチ拡大 / Ctrl+ホイール拡大
             出力は元画像と同寸法の 2 値 PNG（塗った所=白、それ以外=黒）で、
             既存の import 経路（purpose=edit_mask）へ流す
             空マスクと全面マスクは決定時に止める（backend と同じ規則を UI でも見せる）
外側を広げる 比率（元のまま / 16:9 / 正方形 / 9:16）と倍率（1.25 / 1.5 / 2）から
             目標寸法を計算し、元画像を中央に置いた枠を preview で見せる
             16 の倍数・元画像を内包・少なくとも 1 辺拡大・envelope 内を UI で保証
詳細モード   マスク画像の直接指定を残す（既存経路を消さない）
```

#### 設計を 1 件修正した

実装前に backend を確認したところ、`outpaint_plan` は
`left = (width - source.width) // 2` で元画像を**必ず中央へ置く**。
設計に書いていた「上下左右のハンドルをドラッグ」は非対称拡張を前提にしており、
現行契約では表現できない。できるかのような操作を見せないため、
比率と倍率の選択に変更し、`design-workspace-ux.md` §6 F2 と
`ux1-workspace.md` §5 に根拠を記録した。中央配置の前提が変わっていないことを
静的試験でも検査している。

#### 実機ブラウザ観測（standalone、Chromium、light と dark の 2 パス）

実際のポインタ操作で塗り、送信は捕捉して生成させていない。

```text
何も塗らずに決定       ダイアログが閉じず「変えたい場所を塗ってください。」
実際に塗った結果       1,108 ピクセル（全体の 1.7%）を変更対象として記録
取り消し・消しゴム     操作でき、状態が切り替わる
送信された constraints strict_edit=true / edit_mode=inpaint /
                       editable_mask_asset_id=asset_... （実際に import された資産）
外側を広げる           「256×256 を中央に置いて 512×288 へ広げます。」
                       constraints は 16 の倍数・元画像を内包・1 辺拡大・strict_edit=true
console・page error    両パスとも 0 件
```

証跡: `/data1tb/mediaforge-ux1-evidence/{light,dark}/`（`mask-editor.png` / `outpaint.png` を含む）

#### 確認したこと

```text
./mf.sh test   174 passed
静的試験の追加  マスクのファイル指定が詳細モードにしか無いこと、
                非対称拡張の操作が UI に無いこと、中央配置の前提が変わっていないこと
```

#### NOT TESTED / 未実施

```text
実機のタッチ操作        pointer events で実装しているが、実端末の指操作は未確認。
                        Playwright のマウス操作でのみ確認した
実際の生成を伴う inpaint 送信を捕捉して止めているため、strict edit の実行経路は未確認
全面マスクの UI 阻止    筆で全面を塗る操作が長いため未実施。backend 側は既存試験で確認済み
installed host での確認 PR-U7
失敗時の出口ボタン      未実装（PR-U4）
```

## Release v0.2.0 (2026-08-22)

UX1 の PR-U0〜U3 と G3 backend を含む版を公開した。

```text
artifact  control-deck-media-forge-0.2.0-linux-x86_64.tar.gz
bytes     29,121,065
sha256    ec7dd2296b8a640acb780c30b39c54e19c65a5488ebc4ec1c876bf9aa43f97c6
release   https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.2.0
```

#### リリース物そのものに対する検証

ソースツリーではなく、**展開したバンドルを起動して**確認した。

```text
起動            bin/mediaforge-core serve が health 200 を返す
配信内容        workspace HTML 80,781 バイトに 3 ナビ・モードトグル・マスク編集・
                広げ方・詳細テンプレート・受付前エラー・モバイル下部タブが含まれ、
                旧 UI の operation select は含まれない
addon manifest  version 0.2.0 / mobile embedded
実ブラウザ試験  scripts/ux_standalone_e2e.py がバンドルに対して PASSED
                1280×800 の 2 ペイン / 390×844 の下部タブ・横スクロール 0px /
                320px 崩れなし / console・page error 0 件
```

#### 未確認のまま公開した点（リリースノートにも明記）

```text
installed host での埋め込み表示
    mobile: "embedded" を宣言しているが、実機ホストで 768px 未満に
    状態カードではなく workspace が出ることを確認できていない。
    確認には ControlDeck のログイン資格情報が必要（PR-U7）。
実端末のタッチ操作          Playwright のマウス操作でのみ確認
実際の生成を伴う inpaint    送信を捕捉して止めているため実行経路は未確認
生成物の書き出し            未実装（PR-U5）
キャラクター／画風の UI      未実装（PR-U6）
```

#### ホスト側カタログ

ControlDeck の `backend/app/features/trusted-catalog.json` は v0.1.2 を pin している。
v0.2.0 を配布するには ControlDeck 側の別 PR が必要。

## PR-U7 partial — installed-host acceptance (2026-08-22)

テスト用の管理者 `mf-e2e` を作り、実機の ControlDeck に対して
`scripts/ux_control_deck_e2e.py` を実行した。

```text
bridge                ready（standalone ではなく host bridge に接続）
theme token           host から届いた値が適用される（accent #3b82f6 等）
サイズ preset         実 envelope 由来の 1024x1024 / 1024x576 / 576x1024
                      standalone のフォールバックではない
詳細モードの永続化    再読込後も維持される（standalone では確認できなかった項目）
route 同期            /x/media-forge/workspace/library まで URL へ反映
モバイル 390x844      状態カードではなく workspace が出る（embedded 宣言が効いている）
                      下部タブ fixed / 単一列 / 横スクロール 0px / タップ標的 60px / 一覧 2 列
console・page error   0 件
```

`mobile: "embedded"` の実機確認は v0.2.0 時点で唯一残っていた重要な未確認事項であり、
これで解消した。

## 実使用で見つかった不具合（2026-08-22）

実機のモバイルで実際に触ったことで、試験では出なかった問題が 6 件出た。

### 1. パッケージ済み worker が起動できない（最も重い）

installed bundle での画像生成が**必ず** `worker_crash` になっていた。
worker を手で起動して原因を特定した。

```text
ModuleNotFoundError: No module named 'mediaforge'
  worker_packs/image/adapters/diffusers_flux2.py:10
```

G2 で adapter が `mediaforge.image_edit` / `mediaforge.outpaint` を import する
ようになったが、bundle には凍結された core しか無く worker の venv からは
import できない。dev で気付かなかったのは、親プロセスから継いだ `PYTHONPATH` に
たまたま `backend` が含まれていたためで、経路として保証されていなかった。

修正: bundle へ `backend/mediaforge` を同梱し、worker の `PYTHONPATH` を明示する。
`worker_packs` が import する自リポジトリのパッケージが bundle に入っているかを
検査する試験を追加した。

**残る設計上の問題**: worker が core を import すること自体が
`AGENTS.md`「worker は core から実装を import しない」に反する。
今回は動作を先に戻した。`image_edit` / `outpaint` は PIL だけに依存する純粋な
幾何処理なので、worker pack 側へ寄せるのが筋。層の整理は未着手。

### 2. 端末の写真が取り込めない

3024x4032 の写真は取り込みの画素数上限（2048x2048）を超えて失敗し、
画面には「うまくいきませんでした」としか出ていなかった。
出力はどのみち envelope 内の寸法になるので、送る前にブラウザ側で縮小する。

### 3. base64 の chunk がパスとして誤検出される

`reject_host_paths` が運搬用の base64 本体まで検査しており、先頭が `/` になる
chunk（base64 のアルファベットに含まれるため約 1/64）が `unscoped_host_path` で
拒否されていた。取り込みが不定期に失敗する原因であり、
`test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_up` の
間欠失敗の正体でもある。

この間欠失敗は PR-U0 より前のコミット（6499047）を worktree に取り出して
8 回中 1 回再現することを確認しており、UX1 の変更が持ち込んだものではない。
修正後は 5 回連続で通る。

### 4. 入力しただけで「未保存」警告が出る

`host.busy` を keystroke ごとに立てて降ろしていなかった。Media Forge に保存の
概念は無く、実行中の作業はサーバ側の job として残る。実際に失うものがある間だけ立てる。

### 5. 取り込み中の進捗が出ない

job になる前の取り込み時間が最も長いのに進捗が無かった。モバイルではステージが
画面外にあり、常時表示のミニバーが唯一の手掛かりになる。

### 6. 版の出所が二重化していた

`doctor` が 0.1.2 を返し、provenance にも 0.1.2 が記録されていた。
`mediaforge.__version__` へ一本化し、pyproject は hatch の dynamic version で読む。

### 修正後の実機確認

```text
インストール済み 0.2.2 経由の実生成   1024x1024 が 20 秒で完了し結果を表示
モバイルの進捗バー                    生成中に表示される
「未保存」                            入力しただけでは出ない
端末写真の取り込み                    3024x4032 -> 768x1024 に縮小して成功
console・page error                   0 件
```

## Release v0.2.1 / v0.2.2

```text
v0.2.1  b3405cd7662de9972dabe5182c8996ac3f6b63a4807c7ecbf42f0929324ca75a  29,126,043 bytes
v0.2.2  a8e6e7342d2a4885bf3a45ca23803f671de3b1f53915caf13232f101a2817992  29,320,459 bytes
```

ControlDeck の `trusted-catalog.json` は v0.2.2 を pin 済み（ControlDeck PR #222）。
この開発機の稼働環境も 0.2.2 へ更新し、旧版は versions/ に残してロールバック可能。

## ControlDeck 側の変更（利用者の許可のもと・汎用機能に限定）

```text
PR #220  trusted-catalog の pin を v0.2.0 へ
PR #221  quick action / command を宣言どおり実行する host API と、
         Quick Actions のアイコンを NAVIGATION から引く修正
PR #222  trusted-catalog の pin を v0.2.2 へ
```

PR #221 は「宣言された contribution を実行する」汎用機能であり、Media 固有の
分岐は入れていない。Media Forge 側は contract どおり
`{"route": "/x/media-forge/workspace/create"}` を返しており、host が呼んで
いなかっただけだった。

## UX2 PR-M0 — model catalog and ownership (2026-08-22)

既存の単一 `ModelRegistry` に、公開 `/api/v1/models` schema を変更せず
catalog metadata を合成した。Media Forge 管理ストアと共有 Hugging Face cache は
別 root として走査し、同じ model identity が双方で有効なら registry 全体を
`model ownership is ambiguous` として fail-closed にする。管理 root からの symlink
脱出は installed と認めない。external snapshot は生成に利用できるが
`removable=false` である。

開発機で `./mf.sh model list` を実行した実測:

```text
model       black-forest-labs/FLUX.2-klein-4B
revision    e7b7dc27f91deacad38e78976d1f2b499d76a294
domains     general,illustration,poster,background
source      /data1tb/ControlDeck/data/cache/huggingface (NVMe/ext4)
state       available / installed=yes / healthy=yes
ownership   external / removable=no
scan time   0.03 seconds
max RSS     14,340 KiB
```

別プロセスの core を `127.0.0.1:9138` で起動し、`/health` は healthy、
`/api/v1/models` は従来の公開 field 集合のまま上記モデルを installed/healthy と返し、
`/api/v1/capabilities` は `image.text_to_image` を local/measured/available と返した。
この確認用 managed root は `/data1tb/ControlDeckMediaForge/.runtime-evidence/m0/models`
（NVMe device 66305）を指定し、観測後の一時データは `/tmp` へ退避した。

`./mf.sh test` は 189 passed（13.24 秒）。これは契約回帰の証拠であり、上記の
実プロセス/API/実ストレージ観測とは区別する。モデルの新規 download、resume、
verify、remove、Settings UI は PR-M1/M2 のため **NOT TESTED**。稼働中の installed
bundle は v0.2.4 であり、M0 はまだリリース bundle へ含めていない。ControlDeck の
コード変更は不要だった。

## UX2 PR-M1 — durable model install/remove backend (2026-08-22)

trusted catalog の pinned revision だけを対象にする durable operation を実装した。
URL、repository、command は workspace input として受け取らない。転送は常に
`parallelism=1` で、各ファイルは現在 offset から最大 5 回まで再試行する。
partial は `.downloads/<operation_id>` に隔離し、required file と weight の
size/SHA-256 検証後に同一 filesystem 上で atomic promote する。明示 cancel は
partial を削除し、service shutdown / Ctrl-C は再開用に残す。external model と
実行中 job が保持する managed model の削除は拒否する。

開発機の NVMe 上に空の external cache と専用 managed root を作り、実際の
FLUX.2 Klein 4B を取得した。

```text
operation id       modelop_f392eb94cd4d445499a957d5e5b87485
model/revision      black-forest-labs/FLUX.2-klein-4B
                    e7b7dc27f91deacad38e78976d1f2b499d76a294
managed root        data/model-management/managed（/dev/nvme0n1p1, ext4）
transfer mode       sequential, parallelism=1
interruption        780,840,902 bytes で Ctrl-C
resume              同じ operation id / queued から再開し 781,119,430 bytes を観測
resume process      1,592.15 seconds / max RSS 63,088 KiB
operation elapsed   1,691.26 seconds（中断と再起動を含む DB timestamp 差）
verified blobs      15,975,681,525 bytes / 13 snapshot files
final state         ready / installed=yes / healthy=yes / ownership=managed /
                    removable=yes
partial cleanup     ready 後 `.downloads/` に operation directory なし
registry rescan     0.10 seconds / max RSS 24,892 KiB
repeat install      model_already_installed、0.15 seconds、exit 1
```

開発中の実転送では 2 件の失敗も観測した。1 件目は size 未知の完了済み小ファイルへ
Range request を送り HTTP 416 になったため、`Content-Range: bytes */<total>` と
local size が一致する場合だけ完了として扱うよう修正した。2 件目は受信途中の
remote close で失敗したため、offset 継続の bounded retry を追加した。失敗 operation
は `failed` のまま durable history に残り、partial は削除されている。成功 run では
約 10.39 GB 地点で受信停止後に同じ operation のまま進行が戻った。

実転送対象の合計が cache directory 全体の初期概算より 13,226,337 bytes 小さいことを
観測したため、catalog の `approx_download_bytes` は検証対象 13 files の実合計
15,975,681,525 bytes に補正した。成功 operation は補正前の概算値を durable history
として保持しているが、以後の operation は補正値を使う。

同じ managed root と空の external cache で実 core を `127.0.0.1:9139` に起動した。
最初の確認で `model_library=missing` を観測し、`mf.sh` の setup 判定が外部
`HF_HOME/hub` の存在だけを前提にしていたことを特定した。managed hub も判定対象にし、
core venv の interpreter で registry を読むよう修正後、実 HTTP で `/health` は
`healthy` / `model_library=ok`、`/api/v1/models` は対象モデルを
`installed=true` / `healthy=true` / `available` と返した。

`./mf.sh test` は 202 passed（14.39 秒、全 command 15.50 秒、最大 RSS
180,192 KiB）。これは契約回帰の証拠であり、上記の実ダウンロード、再開、検証、
実プロセス/API観測とは区別する。実 15.98 GB model の remove は、次工程でも使うため
**NOT TESTED**。小さい隔離 fixture の remove、external/in-use拒否、cancel cleanup、
hash不一致、symlink脱出、workspace event はテストで確認した。managed copyからの
実画像生成と Settings UI は **NOT TESTED**（後続 M2/C5）。ControlDeck のコード変更は
不要だった。

## UX2 PR-M2 — Settings Model Management (2026-08-22)

既存 Settings に、Simple から到達できるモデル管理を追加した。保存容量、
Installed / Recommended / All、media type/domain chip、friendly name、導入・削除、
inline progress、global model progress を表示する。model ID、revision、hash、runtime、
backend、生 capability、VRAM/時間、license/gated は Advanced template を mount した
ときだけ DOM に現れる。Simple の操作対象は一時 catalog index で結び、model ID を
`data-*` にも置かない。

`media_types`（image / video / audio_video）は catalog/UI 分類専用として追加した。
routing は読まず capability が唯一の挙動契約である。runtime capability family と
矛盾する catalog は registry 全体を fail-closed にする。これにより将来の動画・
音声付き動画も同じ Model Management を使えるが、G7 model の download/worker/default
昇格には着手していない。

実ブラウザと実 core/private WebSocket/durable SQLite を使う隔離 E2E
`scripts/ux_model_management_e2e.py` を実行した。モデル byte だけを 32 MiB の
fixture にし、実 installer/verifier/atomic managed store/remove を通した。

```text
Download開始                 1 tap
install wall time            10.539 seconds
別画面の global progress     visible
reload/reconnect             同じ active operation を operations.list から復元
Advanced detail              Simple DOM には無し / Advanced で model_id 等を確認
external model               disabled「共有モデル」/ destructive action 無し
Remove                       action 後の確認 dialog は 1 回だけ
390x844 horizontal overflow  0 px
320x640 horizontal overflow  0 px
console / page error         0 件
evidence                     /tmp/mediaforge-m2-evidence/
```

この試験で 3 件の実不具合を検出して修正した。

1. mount URL が `/` で終わると WebSocket URL が `//ws` になったため末尾 slash を正規化。
2. 最後に Settings 以外を見て reload すると operation を復元しなかったため、boot 時に
   durable operation を常に読む。
3. 小さい remove が watch 登録前に完了すると queued 表示に残ったため、watch 直後にも
   durable list/catalog を再取得して event race を収束させる。

実 managed FLUX.2 Klein 4B を読む standalone core に対して既存
`scripts/ux_standalone_e2e.py` も実行し PASSED。desktop ready 0.120 秒、390px/320px
overflow 0、console error 0 件だった。既存スクリプトが outpaint 後の
`source → target` 寸法表示を旧形式として parse していた 2 箇所も更新した。

`./mf.sh test` は 207 passed（12.10 秒、全 command 13.22 秒、最大 RSS
181,556 KiB）。これは契約回帰で、上記ブラウザ/実process観測とは区別する。
実 15.98 GB model の削除、installed ControlDeck の配布版でのM2表示、G7動画model、
managed copyからの画像生成は **NOT TESTED**。大容量modelはNVMeに保持した。
ControlDeck のコード変更は不要だった。

## UX2 PR-C0 — CreativeSpec/template/compiler (2026-08-22)

公開 JobRequest/schema/addon contract を変更せず、private planning object と
deterministic compiler を追加した。`CreativeSpec` は domain、SceneSpec、PoseSpec、
CompositionSpec、CameraSpec、VariationSpec、ReferenceRole を持つ。template は
`creative/templates.json` のversioned dataであり、DOMやengine adapterへhardcode
していない。Cameraは将来の動画でも共用できるが、MotionSpecはG7まで受理しない。

`creative.templates` と `creative.validate` はauthenticated workspace transportだけに
追加した。compilerは既存intent/constraintsへcompileし、template ID/version、役割、
envelopeを含むnormalized planを`constraints.creative_plan`へ保存する。空/全Autoは
requestを1 fieldも変えない。scene/pose不整合、unknown template、unavailable
capability、requestに無いreference role assetをjob作成前に拒否する。routingは
変えず、auto requestへmodel IDを追加しない。

別Python processで実templateをloadし、anime / presenting_device / holding_item /
full_body_off_center / eye_level / expressionのspecを1,000回compileした。

```text
catalog version            2026.08.22
template counts            domain 6 / scene 8 / pose 9 / composition 8 /
                           camera 7 / variation 5 / reference role 5
empty request identical    true
1,000 compile elapsed      0.029042 seconds
deterministic hashes       unique=1
process wall / max RSS     0.11 seconds / 30,012 KiB
model routing              model_policy=auto / model_id=null
plan snapshot              constraints内のplanとcompiler resultが一致
invalid combination        creative_combination_invalid / field=pose /
                           「選んだシーンとポーズは組み合わせられません。」
```

最初の測定コマンドは製品起動時と同じ`PYTHONPATH=backend`を付け忘れ、
`ModuleNotFoundError: mediaforge`で0.01秒終了した。上記の成功値には含めていない。
focused testは43 passed。`./mf.sh test`は222 passed（15.63秒、全 command
16.93秒、最大 RSS 185,752 KiB）。これは契約回帰の証拠であり、上記の
実 process compile 実測とは区別する。CreativeSpecを使うUI、
実job生成、profile/reference統合、variation child生成はC1〜C3のため **NOT TESTED**。
G7 MotionSpec/動画modelは **NOT TESTED**。ControlDeck変更は不要だった。

## UX2 PR-C1 — Create creative direction UI (2026-08-22)

既存 Create の intent、画像取り込み、サイズ、枚数、実行、result stage、
Advanced panel を移動・複製せず、Simple に Domain と閉じた
「シーンと見せ方」を追加した。全ラベルは C0 の versioned template data
から導出し、Simple に model 名や engine 語を出していない。Advanced の
domain/scene/pose/composition/camera/variation と自由補足は従来どおり
template を mount したときだけ DOM に存在する。

Auto のままでは `creative.validate` を呼ばず、prompt-only の既存 JobRequest
形を維持する。指定があるときだけ private compiler による検証・compile
を job admission 前に行う。standalone workspace も同じ compiler を使うため、
OpenAPI から除外した same-origin の `/workspace-api/creative/validate` を追加した。
これは public API ではなく、path/model を受理しない。

隔離 data dir の実 core（`127.0.0.1:9141`）と Chromium で
`scripts/ux_creative_c1_e2e.py` を実行した。

```text
Simple advanced nodes          0
Domain labels                  自動 / アニメ / イラスト / 写真 / 2Dゲーム / ポスター
prompt-only constraints        width=1024 / height=1024 / creative_plan無し
directed selections            scene / pose / composition / camera / variation を独立選択
compiled routing               domain=anime / model_id=null / catalog=2026.08.22
invalid combination            job POST 0件 / inline理由を表示
Advanced nodes                 27
320x640 horizontal overflow    0 px
tab order                      intent -> scene/pose/composition/camera/variation -> submit
console / page errors          0 / 0
evidence                       /tmp/mediaforge-c1-evidence/
```

`./mf.sh test` は224 passed（15.64秒、全 command 16.89秒、最大 RSS
189,288 KiB）。これは回帰gateであり、上記の実process/browser観測とは区別する。
Character/Style と role-aware reference は C2、複数差分 job は C3 のため
**NOT TESTED**。CreativeSpec 指定での実 GPU 生成・品質差は C5 のため
**NOT TESTED**。G7 MotionSpec/動画モデルは **NOT TESTED**。ControlDeck 変更は不要だった。

## UX2 PR-C2 — Character / Style / role-aware references (2026-08-22)

新しい profile store を作らず、G3 の ReferenceCollection / CharacterProfile /
StyleProfile を Create に接続した。Simple では「キャラ・画風を使う」の選択だけを
出し、collectionのrole metadata、またはprofile kindからidentity/styleを推定する。
strength sliderのmatrixはSimple DOMに存在しない。

ReferenceCollection schema に省略可能な `roles` map を加法的に追加した。
旧asset/collection/clientは省略でき、既存fieldの意味は変わらず、migrationと
contract version bumpは不要。jobごとのoverrideはprofileを変更せず
CreativePlan/provenanceに保存する。roleはidentity/style/pose/composition/clothing/
palette/prop/environment。

model catalog に `reference_roles` と `supports_reference_strength` を加法し、
active model群の共通role、最小`max_references`、strength対応をprivate envelopeの正とした。
FLUX.2 Klein 4Bは8 role、最大4参照、numeric strength未対応とし、未対応
strengthは理由付きでdisabledにした。

隔離data dirの実core（`127.0.0.1:9142`）に6画像、2 collection、2 profileを
実HTTPで登録し、Chromiumで`scripts/ux_reference_roles_c2_e2e.py`を実行した。

```text
Simple profile inference       character refs 3枚 / role matrix DOM 0
deliberate pose variants       wave / peace / holding_item（同一profile・identity）
identity fixed / pose changed  identityは固定、pose役のassetだけswap
style fixed / composition      style profileは固定、composition役assetだけswap
strength support               3 controls全てdisabled（model metadata=false）
reference admission            character 3 + style 3は上限4枚の手前でjob POST 0
320x640 horizontal overflow    0 px
console / page errors          0 / 0
evidence                       /tmp/mediaforge-c2-evidence/
```

初回browser probeでstandalone shimにprivate envelopeが渡らず上限0枚と表示する
実不具合を検出した。coreが算出したtemplate/preset/envelopeをworkspace HTMLへ
dataとして埋め込み、standaloneとembeddedが同じ数値的正を使うよう修正した。

`./mf.sh test`は228 passed（12.59秒、全command 13.93秒、最大RSS
191,848 KiB）。実GPUで3 pose/reference swapの視覚品質はC5のため **NOT TESTED**。
numeric strengthは対象modelが未対応なで **UNAVAILABLE**。ControlDeck変更は不要だった。

## UX2 PR-C3 — intentional pose/scene/composition batches (2026-08-22)

`count > 1` と pose / scene / composition variation の組み合わせを、単一workerへの
曖昧な複数出力ではなく、2〜8件の明示的child CreativeSpecへ展開するplannerを追加した。
各childは異なるtemplate snapshot、seed、batch ID/indexを持ち、通常のjob admissionを
1件ずつ通る。親batchはSQLiteへ永続化し、reload後のprogress復元、logical cancel、
successful assetを残すpartial stateを提供する。public JobRequest/schema/addon contractは
変更していない。

隔離data dirの実core（`127.0.0.1:9143`）、fake workerの別process、Chromiumで
`scripts/ux_creative_batches_c3_e2e.py`を実行した。

```text
pose x4                  holding_item / typing / peace / wave
pose seeds               1664062594 / 1664062595 / 1664062596 / 1664062597
composition x4           bust_up / full_body_center / full_body_off_center /
                         three_quarter
result candidate assets  pose batch 4件
reload/reconnect          batch IDを復元、表示は「差分を作っています（0/4）」
logical cancel            child 4件すべて canceled、queued/running 0件
partial success           succeeded 1 / canceled 3 / retained asset 1
Advanced Activity         親batchからchild job ID 4件を展開
browser wall time         3.4 seconds
320x640 overflow          0 px
console / page errors     0 / 0
evidence                  /tmp/mediaforge-c3-evidence-20260822d/
```

初回browser runは実modelを空rootへ隔離した結果、capabilityが正しく
`model_not_installed`となり受付前に422で停止した。実modelを偽ってavailableにせず、
experimental manifestでfake workerを明示するfixtureへ切り替えた。次のrunではSimpleの
progress detailにbatch IDが出ると仮定したprobeがtimeoutし、実際のSimple表現に合わせて
進捗文言と可視状態を観測した。3回目は新しいparent drilldownの長いIDが320pxでoverflow
する実不具合を検出し、grid childのmin-widthと折返しを修正後に上記runが完了した。

`./mf.sh test`は240 passed（16.39秒、全command 17.81秒、最大RSS 203,108 KiB）。
これは契約回帰であり、上記の実process/browser観測とは区別する。
実GPUによる4 pose / 4 compositionの視覚品質、ControlDeck broker上での4-child連続
admission、installed-host iframeでのreconnectはC5まで **NOT TESTED**。fake workerは
CPU-onlyでありlease不要。ControlDeck変更は不要だった。

## UX2 PR-C4 — multi-cut planner + deterministic Composer (2026-08-22)

Poster / Character Sheetを新しいtop-level appやpublic operationにせず、既存Createの
Domainとcomposition presetとして追加した。2〜4件のmain/coding/device/chibi shotを
同じCharacter/Style constraintを持つ通常の`image.generate` child jobへ展開し、完了後に
CPU-only Composerがversioned layoutのregionへcrop/配置、枠、safe margin、日本語title/
caption、固定出力寸法を適用する。最終assetは`asset.pack`で、全child assetをlineageと
hash付きprovenanceに持つ。

日本語fontは環境から選んだNoto Sans CJKをdata dirへSHA-256名で初回cacheし、layout
snapshotへfont hashを保存する。model/venv内へ置かず、text再編集時も同じcached bytesを
使う。今回の実測cacheは19,484,784 bytes、SHA-256は
`b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a`。

隔離data dirの実core（`127.0.0.1:9144`）、別process fake worker、Chromiumで
`scripts/ux_multicut_composer_c4_e2e.py`を実行した。

```text
child shots                 3 jobs / 3 assets（main / coding / device）
final poster                1024x1536 RGBA PNG
initial SHA-256             b6168adc74b8c34db2090aa1bd8661132490eb060da95d3d065ca6f0e14512fb
title/caption update        image.generate job delta 0 / final revision +1
changed SHA-256             ee99bf1ef7f1c2b0789d35096dfa18d61d12c9ab3187e74be218598af2bd09b5
same layout+children        initial SHA-256と再一致
lineage                     parent asset 3件がshot asset 3件と完全一致
mobile viewer               natural 1024x1536 / existing viewerを使用
browser wall time           4.6 seconds
320x640 overflow            0 px
console / page errors       0 / 0
evidence                    /tmp/mediaforge-c4-evidence-20260822b/
```

最初のbrowser runではPillow default fontが日本語を豆腐字形にする実不具合を画像で確認した。
上記のcontent-addressed font cacheへ修正し、2回目の画像で日本語glyphを目視確認した。
focused testでは2/3/4 shot layoutのbyte-for-byte再現、safe dimensions、hosted workspace
child path、文字更新時のchild不変を確認した。実GPU shotの視覚的一貫性とinstalled-host
iframeはC5まで **NOT TESTED**。`./mf.sh test`は255 passed（23.75秒、全command
25.21秒、最大RSS 248,256 KiB）。これは回帰gateであり、上記の実process/browser観測とは
区別する。ControlDeck変更は不要だった。

## UX2 PR-C5 — semantic evaluator + R9700 acceptance (2026-08-22)

既存のdeterministic validatorとC0 plannerの後段に、6軸（identity / style /
pose-action / scene / composition / obvious breakage）のCPU-only advisory
Evaluatorを追加した。候補asset IDだけを受け取り、結果を順位表示する。自動再生成は行わず、
評価前後のjob件数も不変である。入力は最大8候補・4参照・16KiB plan、画像は既存の
768x768 / 2MiB境界を再利用する。path入力、remote origin、壊れたJSON、timeoutは
`creative_evaluation_unavailable`でfail-closedする。public schema / addon.json /
agent tool / workflow executorは変更していない。

隔離ControlDeck（`127.0.0.1:18765`）と現在のMedia Forgeソース
（`127.0.0.1:19130`）、実Broker、R9700/gfx1201、保持済みNVMe modelを使った。
3件はすべてControlDeck Workflowからleaseを取得し、完了後に解放した。

```text
candidate 1                  15.967179 s; load 11.335529 / generation 1.584339
candidate 2                  17.460744 s; load 13.448332 / generation 1.461965
candidate 3                  19.440341 s; load 14.989607 / generation 1.592628
resolution / steps           512x512 / 4
first absolute VRAM peak     21,245,644,800 bytes
later absolute VRAM peaks    17,478,889,472 / 17,470,918,656 bytes
maximum worker RSS           16,494,501,888 bytes
worker swap                  0 bytes
lease renew / after          each 1 / active 0
model/revision               FLUX.2-klein-4B / e7b7dc27...a294
runtime                      Diffusers 0.40.0 / direct_device_map / cuda:0
weights / license            f3fcfa8f...ae278 / Apache-2.0
```

目視では3枚とも短い黒髪、オレンジメッシュ、黒/オレンジhoodie、顔と配色が
一貫し、端末提示・手振り・3/4 poseの差分が成立した。実出力と証跡は
`/data1tb/mediaforge-c5-e2e-20260822/`へ保持する。

Ollama 0.31.1の`qwen3-vl:2b` thinking tagは`think=false`を無視し、1画像でも
約105秒をreasoningだけに使ってcontentを空で返した。最初の3候補評価と切り分け1候補は
HTTP 422でfail-closedし、成功扱いしていない。非thinking rendererの同容量
`qwen3-vl:2b-instruct`（digest `ea422f1e7365`, 1,889,519,783 bytes,
Apache-2.0）へ切り替え、以下を実測した。初回pullは72%後に再試行したため、安定取得とは
記録しない。

```text
direct evaluator             3 candidates / 40.60 s
ranked first                 asset_906012a17a1145d399fc82545d639385
Media Forge jobs             3 -> 3
GPU VRAM before / after      59,949,056 / 59,949,056 bytes
regeneration_requested       false
installed-host iframe        40.222 s / same first candidate
320px overflow               0 px
browser console/page errors  0 / 0
semantic review instruct     accepted / first response 12.88 s / warm 2.08 s
```

workerをlease取得後1秒でSIGKILLしたprobeは1.374453秒で`worker_crash`へ正規化され、
active lease 0、core health `healthy`を確認した。既存の同一revision multi-reference
実測は`docs/models.md`のG2 supplementを採用ゲート証跡として参照するが、C5では再実行
していない。LoRAはcatalog metadataが`supports_lora=false`のため **UNAVAILABLE**。
共有Hostのkernel page cache dropは行わず、完全storage-cold loadは **NOT TESTED**。
ControlDeckコード変更とhosted CI利用はどちらも0件。

focused evaluator / semantic / frontend / workspace transport regressionは84 passed、
full `./mf.sh test`は262 passed（25.10秒）。これは契約回帰証跡であり、上記の
実Workflow/GPU/VLM/browser観測とは区別する。

## Release v0.3.0 — Creative direction workflow (2026-08-22)

UX2 M0〜C5を、ポーズ指定を含む最初のCreative direction機能版として公開した。
Release tagは、version bumpと全bundle入力を含むexact commit
`c4754ac26fb310978f1d806d0a55e4b993aabdee`を指す。動画候補catalogの作業中差分は
別worktree/別branchに隔離し、このartifactへ含めていない。

```text
release       https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.3.0
artifact      control-deck-media-forge-0.3.0-linux-x86_64.tar.gz
bytes         30,781,945
sha256        d8055331b96befc3de2bbf99cb3823ad6a5159158a0fab6521f40f8d719aa48f
build         18.02 seconds / max RSS 115,648 KiB
doctor        status=ok / version=0.3.0 / packaged=true
manifest      addon 0.3.0 / feature 0.3.0 / entrypoint bin/mediaforge
```

展開したbundleを`127.0.0.1:9140`で実際に起動し、source treeではなく配布binaryへ
HTTPとChromiumを接続した。標準workspace試験は20.52秒、desktop ready 0.076秒、
390px/320px horizontal overflow 0、console error 0件でPASSED。入力fixtureは既存の
858-byte PNG（SHA-256 `8314eb3e...e47`）を証跡directoryへ明示配置した。fixtureが
無い最初の試行は`FileNotFoundError`で停止しており、成功には数えていない。

ポーズ専用のbrowser試験は1.32秒で、`presenting_device` scene、`holding_item` pose、
`full_body_off_center` compositionが別々のCreativePlan fieldへcompileされ、model IDを
強制しなかった。`coding_at_desk + wave`の不正組合せはjob送信前に日本語理由付きで
拒否された。320x640 overflowは0、console/page errorは0/0。証跡は
`/data1tb/mediaforge-v0.3.0-evidence/`へ保持する。

version bump後の`./mf.sh test`は262 passed（24.97秒、全command 26.43秒、最大RSS
257,956 KiB）。これは回帰gateであり、上記の配布binary/HTTP/browser観測とは区別する。
v0.3.0 bundleのControlDeck trusted catalog導入・installed-host更新と、実端末の指操作は
**NOT TESTED**。動画runtimeはこのReleaseに含まれず **UNAVAILABLE**。hosted CIと
ControlDeckコード変更は0件。

## Creative Intelligence protected-field regression fix (2026-08-22)

PR #46 merge後のfull gateで、モデル応答がfull `PromptPlan`をechoすると、server-owned
`version / original_intent / mode`まで`PromptPlanDraft(extra=forbid)`へ渡され、意図を
保護する既存試験が`prompt_plan_invalid`で失敗する回帰を観測した。provider出力を
objectに限定し、この3 fieldだけをvalidation前に捨てる。その他の未知fieldは従来どおり
fail-closedであり、`provider_model`混入を拒否する試験を追加した。

```text
before full gate     1 failed / 272 passed（動画catalog統合branch上で観測）
focused after fix    7 passed
main full after fix  269 passed / 24.58 seconds
full command         26.06 seconds / max RSS 261,500 KiB
```

これはAI応答境界の回帰修正であり、実providerへのHTTP、実画像生成、GPU動作は
**NOT TESTED**。public schema / addon.json / agent tool / workflow executorは変更していない。
hosted CIとControlDeckコード変更は0件。

## Settings の拡張情報を詳細モードへ移動 (2026-08-22)

Settings の既定表示から「この拡張機能について」と capability 一覧を外し、ヘッダーの
「詳細」を選んだ時だけ `template` から DOM へ載せる詳細領域へ移した。モデル管理は
シンプル／詳細の両方に残し、backend の capability document と local-only 強制は変更して
いない。ControlDeck 側の変更も不要だった。

現在のソースを隔離data directory・`127.0.0.1:9140`で実起動し、Chromiumから標準workspace
試験を実行した。シンプル設定では `advanced-capability-list` が DOM に0件、詳細切替後は
11 capability が表示された。desktop ready 0.071秒、390px/320px horizontal overflow 0、
console/page error 0件で、全browser試験は20.5秒でPASSEDした。証跡は
`/tmp/mediaforge-settings-detail-evidence/`に置いた。

最初の試行はfixture不在の`FileNotFoundError`、2回目は試験が詳細モードからシンプルへ
戻さず後続mask検査へ進む問題で停止しており、成功には数えていない。installed-host iframe、
実端末の指操作、リリースbundleは **NOT TESTED**。hosted CIは使用していない。
full `./mf.sh test`は275 passed（28.86秒）。これは回帰gateであり、上記の実process/browser
観測とは区別する。

## Creative Intelligence CI-1 — provider-neutral AI cutover (2026-08-22)

productionのsemantic reviewerとCreative EvaluatorからOllama固有のURL、model、port、
`/api/tags`、`/api/chat`を除去し、ControlDeck `ai.inference` grant配下の
`vision.analyze`へ置き換えた。Media Forgeはcapabilityと画像data URL、構造化response schema
だけを送り、Host応答のprovider/model追加fieldは無視する。候補画像は768px・JPEG・2MiBに
制限し、最大4参照は1枚の決定的なreference sheetへまとめる。deterministic validation、
advisory既定、bounded retry/rankingは変更していない。

ControlDeck exact `d97508b103cd302add46e6bf26899613a46920c3`を、既存PR #226の隔離data
directory・`127.0.0.1:18776`で実起動した。現在のMedia Forge sourceは
`127.0.0.1:19131`、既存のexperimental fake worker fixtureを使い、source manifestを
Add-on v2として登録・`ai.inference`を含む11 grantでenableした。ControlDeck発行service
token経由のagent generationで次を観測した。

```text
target 1              qwen3-vl:2b-instruct / ControlDeck-selected Ollama
job                   job_f2ebdcfc33be4d0c881b6cfb017cd85b / succeeded
elapsed               7.510583 seconds
asset                 asset_aa62546278e94d0e8bb21c8eff54fe04
target 2              qwen3-vl:2b / ControlDeck-selected Ollama
job                   job_52ccfff09b304269bea80d6c52784304 / succeeded
elapsed               2.182804 seconds
asset                 asset_5df5b8d9449b40adb8c6b647ed748162
Media Forge config    target切替前後で変更0件
Host audit            addon.runtime.ai.complete / resource_id=vision.analyze
audit metadata        capabilityだけ。provider/model identityなし
```

2件目はsemantic rejectionを正しくadvisory warningとして返し、再生成要求0件だった。1件目は
summaryが意図不一致を述べた一方`accepted=true`を返すモデル品質上の矛盾を観測したため、
transport成功とは分けて品質PASSには数えない。これはCI-4 evaluatorで扱う課題である。

両VLMの`vlm_enabled`をfalseにした状態でagent capabilityが
`vision_analyzer_unavailable`となることを確認した。同じHost経路で`qa.semantic=false`の
prompt-only生成は0.492620秒、job `job_b73babe372414904aa1cdf76248c3542`、asset
`asset_47f39979736b4215be58bf04e0ba0b3c`でsucceededした。semantic=trueはjob
`job_dc773d1fdfd54d5cb7a757d50a9b3f3a`が`vision_analyzer_unavailable`でfail-closedした。

隔離Host停止前にruntime policyとmodel configを元へ戻し、試験でloadしたOllama VLMもunload
した。共有ControlDeckは`control-deck-web.service`を再起動し、`active`かつ
`GET /api/v1/health = {"ok":true}`を確認した。ControlDeck repository変更は0件で、既存の
`frontend/tsconfig.tsbuildinfo`差分は保持した。llama.cpp runtimeへの切替を通した
Media Forge再実行、installed release bundle、実画像workerは **NOT TESTED**。hosted CIは
使用していない。

focused CI-1 / semantic / evaluator / frontend / workspace / host execution regressionは116 passed。
full `./mf.sh test`は275 passed（23.36秒）。これは回帰gateであり、上記の実Host・service
token・target切替観測とは区別する。

## 画像モデルカタログ v1 (2026-08-22)

測定済み既定のFLUX.2 Klein 4Bに、用途が重複しない3候補を追加した。publisherの
Hugging Face APIから同日に取得したexact revision、各weightのsize/SHA-256を固定し、
canonical weight identity hashの再現試験を追加した。

```text
general/text quality    Qwen/Qwen-Image-2512 @ 25468b98 / external / 57,704,574,910 B
anime/illustration      Illustrious-XL-v2.0 @ 69459c1f / managed / 6,938,042,078 B
lightweight fallback    segmind/SSD-1B FP16 @ 60987f37 / managed / 4,468,829,801 B
```

3候補はすべて`experimental`、`measurement_confidence=low`、CUDA metadataのみ、
recommended profileなしである。未実測候補はROCm routerへ入らず、downloadしても
Availableへ昇格しない。Illustriousはbounded single checkpoint、SSD-1Bはbounded FP16
Diffusers setなので明示download対象にできる。57.7GBのQwenはruntime envelope未確定のため
externalのままにした。

単体workspaceが`/api/v1/models`の最小応答を全件「汎用画像」と推測していたため、trusted
catalog由来の表示metadataを既存Model schemaへoptional fieldとして加法追加した。既存required
field、routing、job/asset/provenance、agent/workflow契約は不変で、migrationとversion bumpは
不要。catalog metadataが無いregistryでは従来の最小応答のままである。

現在のsourceを`127.0.0.1:9142`で実起動した。実HTTPは全10件、画像4件を返し、既存FLUXだけが
available/installed/healthy、3候補はexperimental/not-installed/not-healthyだった。Chromiumの
単体workspaceでSettingsの「画像候補」を選ぶと次の4 cardが0.148秒で表示された。

```text
FLUX.2 Klein 4B
Qwen Image 2512
Illustrious XL v2.0
Segmind SSD-1B (FP16)
console / page errors       0 / 0
standalone action boundary  4 cardsすべて「CLI で管理」（UI installを偽らない）
```

private WebSocket、durable model operation、installerを使う既存実ブラウザfixtureも再実行した。
画像filter 2 cards、download tap 1、reload後のoperation復元、削除確認1、install 10.538秒、
390px/320px overflow 0、console/page error 0/0を観測した。最初の単体browser assertionは
仕様にない日本語「軽量」tagを期待して停止したため成功に数えず、実card名とadoption tagを
検査する形へ直して再実行した。

focused catalog/model manager/frontend/API regressionは67 passedと39 passed、最終
`./mf.sh test`は279 passed（28.51秒）。これは回帰gateであり、上記の実HTTP/browser観測とは
区別する。3候補のweight download、runtime adapter、R9700/ROCm推論、VRAM/時間/品質、
 installed-host iframeは **NOT TESTED**。ControlDeck変更とhosted CI利用は0件。

## Creative Intelligence CI-2 — Creative Director / action variations (2026-08-22)

既存PromptPlanner、CreativeCompiler、C3 durable batch/child Jobを再利用し、新規画像向けの
provider-neutral Creative Directorを実装した。UIは`そのまま` / `自動` / `演出強め`を持ち、
`text.generate`利用可能時だけSimpleの既定を`自動`にする。ActionStateは既存
`PoseSpec(preset=custom)`へbounded projectionし、canonical PromptPlanはprivate
CreativePlan/provenanceへ保存する。manual scene/pose/composition/cameraはDirector出力より優先する。

実モデル初回試験でprovider schemaの全fieldが省略可能だったため、`{}`が合法になり
`assistance_used=true`だが内容が空になる欠陥を観測した。この試行は成功に数えない。provider
向けstrict schemaだけ全object fieldをrequiredにし、内容ゼロも`prompt_plan_invalid`へ正規化して
fail-softにした。canonical product modelの既定値とpublic schemaは変更していない。

ControlDeck PR #226 merge commit `d97508b103cd302add46e6bf26899613a46920c3`の隔離Hostを
`127.0.0.1:18776`、source Media Forgeを`127.0.0.1:19131`で実起動した。隔離Hostから
現在稼働中のQwen3.8-27B llama.cpp endpointをControlDeck policyで選択し、Media Forgeには
provider/model/portを渡していない。実service tokenで次を観測した。

```text
Host capabilities             text.generate=true / vision.analyze=true
creative.text_direction       available
prompt-only Director          robot / inspecting / PoseSpec custom
original intent               compile後も先頭一致
canonical source              control-deck:text.generate
Host audit delta              text.generate 1 / vision.analyze 0
directed action batch         3 child Jobs / custom pose 3 / distinct action 3
batch Host audit delta        text.generate 1 / vision.analyze 0
batch persistence             reconnect getでchild 3件
```

画像生成は、共有LLMが25,166,778,368 bytesをresident使用しHost policyがexclusiveかつ
supervision=observedだったため、GPU leaseが`device_busy_exclusive`で正しく待機した。3 child
Jobsと先行確認jobは明示cancelした。installed-host browserの最終job
`job_e14912bacadd4328a5d6bdcfbdfc1a4a`は画面で待機を観測した後、8096 endpoint停止後にHostが
leaseをactivateし、fake workerがsucceeded、asset `asset_edd01a97d4ae4c658ed293050e559fb5`
1件、lease releaseまで到達した。最終確認はactive lease 0 / waiting request 0。この検証で
leaseを迂回してworkerを走らせていない。別のstandalone実プロセスではtext assistance unavailableを
`text_generator_unavailable`としてfail-softにし、元prompt不変のままCPU fake job
`job_337079b8298240abb00bf8cb83b56990`がsucceeded、asset 1件を返した。

実installed-host Chromiumでは`自動`が既定、Simple PoseがAuto時だけhidden、生成後の
「理解した内容」に元の希望・対象・動き/状態・scene・構図/camera・提案が表示された。
Hostは生成jobを「GPU の空きを待っています」と表示し、その後のjob terminalは上記のとおり
succeededだった。browser観測は16.581秒、console/page error 0件。
standalone Chromiumは390px/320pxともoverflow 0、3 mode、
理解した内容DOM 1、Advanced Pose到達を確認した。証跡は
`/tmp/mediaforge-ci2-hosted-ui.oeKn9z`と`/tmp/mediaforge-ci2-director-ui.uZ6kC2`。

実GPU画像生成、実画像品質、art_directの主観品質、reference付きVision連携（CI-3）は
**NOT TESTED**。focused CI-2 regressionは130 passed、最終`./mf.sh test`は287 passed
（24.93秒）。これは回帰gateであり、上記実Host／実browser観測とは区別する。
ControlDeck repository変更0件、hosted CI利用0件。

## Creative Intelligence CI-3 — Reference Intelligence (2026-08-22)

既存assetをPillowだけで測るversioned `VisualFacts` と、ControlDeck
`vision.analyze`から厳格な`VisualAnalysis`を得るprivate workspace経路を追加した。cache keyは
asset SHA-256とfacts/semantic analyzer versionから作り、同一bytesを別asset IDで参照しても
再解析しない。paletteは256px以内へ縮小してから量子化し、alpha 32未満を除外する。完全透過
画像へ黒を捏造しない。元assetは読み取りだけで、coreへtorch/transformers/OpenCVを追加していない。

Createには画像が存在するときだけ「全体／主役／動き／色／構図／画風」を表示する。選択した
観点のserver生成JSON要約だけをCreative Directorへ渡し、画像data URLはVision呼び出しだけに
留める。profileは変更しない。`そのまま`かつ参照なしではText/Vision呼び出し0件を回帰試験で
固定した。C3の3 childは同一cache要約を共有し、Vision呼び出しは親で1件だけだった。

ControlDeck PR #226 merge commit `d97508b103cd302add46e6bf26899613a46920c3`の隔離Hostを
`127.0.0.1:18776`、現在のMedia Forge sourceを`127.0.0.1:19131`、ControlDeckが選択した
Qwen3.8-27B + mmproj endpointを`127.0.0.1:8096`で実起動した。C5でR9700生成済みの
512x512 RGBA画像（SHA-256 `78fa04f7...f3a2`）をinstalled-host Chromiumから取り込み、
次を観測した。

```text
VisualFacts                    512x512 / alpha=true / opaque_fraction=1.0
Vision VisualAnalysis          50.353 seconds / subject=person / action=holding smartphone
facts cache                    573 bytes
semantic cache                 4,414 bytes
same asset second analysis     0.060 seconds / analysis_cache_hit=true
Director with pose summary     13.287 seconds / structured context 1件
Host audit delta               vision.analyze 1 / text.generate 1
original assistance            false / 追加audit 0
320px overflow                 0 px
browser console/page errors    0 / 0
evidence                       /data1tb/mediaforge-ci3-evidence-20260822/
```

最初のbrowser試行は存在しない一時model manifestを指定してworkspace初期化が停止したため、
成功に数えていない。その後の2試行で、長い実asset名が320px幅を95px押し広げる実不具合を
観測した。Director grid子の縮小境界と添付名の`overflow-wrap:anywhere`を追加し、fresh data/cache
で上記最終runを再実行した。最終確認はBroker active lease 0 / waiting request 0、試験用LLMを
unload、隔離Host/Media Forgeを停止、共有ControlDeckはactiveかつhealth okだった。

focused reference/director/batch/workspace/frontend regressionは109 passed。最終
`./mf.sh test`は303 passed（28.11秒）。これは契約回帰証跡であり、上記の実Host/Vision/browser
観測とは区別する。public schemas / addon.json / agent tool / workflow executorは変更していない。
C4 multi-cutのAI shot briefはCI-5、Evaluator統合はCI-4なので **NOT TESTED**。実GPU生成、
profileへの自動反映（仕様上行わない）、installed release bundleは **NOT TESTED**。
ControlDeck repository変更0件、hosted CI利用0件。
# MiniMax H3 bounded catalog and runtime evaluation (2026-08-22 to 2026-08-23, active)

The official `MiniMaxAI/MiniMax-H3` FL2VA revision
`42ed227ee7df40d41602854ae760620d6eb651fe` was measured from the Hugging Face
tree as 81 selected files / 144,051,182,625 bytes. A real managed download to
the NVMe model store was canceled at 1,865,101,859 bytes after the 32GB local
artifact limit was established. The operation reached `canceled`; its contained
`.downloads/modelop_2f7d58dbfd13401d94b3a6eb7d70c1c2` tree was absent afterward,
and no installed `models--MiniMaxAI--MiniMax-H3` repository existed.

The replacement candidate is `unsloth/MiniMax-H3-GGUF` revision
`d629413c2e5b51b38c453668b75ca3b06ca92703`: pruned FL2VA UD-Q2_K_XL,
Qwen3-VL Q2_K_M, and two Comfy-Org VAEs at revision
`0f7fb980293fcc4d55c1158cbda920806682ed5d`, totaling 26,978,277,946 bytes.
The installer now accepts only those catalog-pinned per-weight sources, requires
an exact license-acceptance identifier, rejects managed artifacts at or above
32,000,000,000 bytes before creating an operation, and still transfers one file
at a time directly under the configured model store.

Observed local gate after these changes:

```text
./mf.sh test
309 passed, 1 warning in 27.88 sec
```

The real GGUF download operation `modelop_0dfc422e9d9d480a996e02ba552d6b89`
ran sequentially against the NVMe feature-data model store from
`2026-08-22T14:12:33.901575+00:00` through
`2026-08-22T15:01:33.263368+00:00` (49 minutes 00 seconds). It reached
`ready` with `26,978,277,946 / 26,978,277,946` bytes and no error or cancel
request. The installed snapshot occupied 26,978,361,344 bytes; the NVMe had
657,629,118,464 bytes available afterward. The operation-specific temporary
download tree was absent after promotion, and catalog discovery reported
`installed=yes`, `healthy=no`, `state=experimental`.

An independent `sha256sum` over all four inference files completed in 17.49
seconds with 3,740 KiB maximum RSS. All values matched the catalog pins:

```text
denoiser      cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8
text encoder  a8ccadccd57ef34c838ffb8a7da8368bb554721b2760274a1d3b0df63960b997
video VAE     7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522
audio VAE     8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48
```

This proves bounded download, verification, and installation only. The pinned
stable-diffusion.cpp runtime was then fetched at exact commit
`97d2990807fe6d558e395f8764198d7c7e7b411c` with pinned shallow submodules and
configured for HIPBLAS/gfx1201. The documented `clang` command first failed in
0.18 seconds because clang was not on `PATH`; using the ROCm 7.2.1 compiler at
`/opt/rocm-7.2.1/lib/llvm/bin/{clang,clang++}` configured successfully in 2.59
seconds. A single-parallel Release build completed in 539.64 seconds with
7,153,248 KiB maximum RSS. The runtime tree occupied 1,233,055,744 bytes and
the resulting `sd-cli` SHA-256 was
`7c2aebea172e4199da1307769a1b6dc38cecd73c102e3262351283702ed7de03`.

The first CLI smoke correctly exposed a missing runtime search path for
ROCm's `libomp.so`; no system library was installed. With the isolated runtime
library path `/opt/rocm-7.2.1/lib/llvm/lib:/opt/rocm-7.2.1/lib`, `sd-cli
--help` succeeded and `--list-devices` completed in 0.06 seconds / 86,796 KiB
maximum RSS. It reported the R9700 as `ROCm0`, gfx1201, 32,624 MiB VRAM, plus
the integrated gfx1036 GPU as a separate `ROCm1`; future evaluation must pin
the R9700 explicitly.

Immediately before inference, the host had 32,605,573,120 total RAM,
27,586,805,760 available RAM, and 1,516,511,232 bytes of swap already used.
The 26.98GB weight set therefore leaves too little evidence to assume that
full `--offload-to-cpu` will be practical. A mixed/streamed placement may still
be viable, but must be measured rather than inferred.

R9700 model load/generation, VRAM execution phases, RAM/swap deltas, output
quality, runtime cancellation, and prompt-recipe Gateway projection are still
**NOT TESTED**. They were not run directly because every GPU evaluation must
hold a ControlDeck lease, while this catalog slice does not yet provide an H3
worker/evaluator capable of receiving a Host service identity, creating its
Host Job, renewing the lease, and releasing it. An unauthenticated resource
probe returned HTTP 401 as designed; no token was forged, signing key read, or
unrelated model lease reused. Runtime evaluation may use bounded CPU/RAM offload even
when working memory exceeds 32GB VRAM, but only practical measured wall time,
safe RAM headroom, and absence of sustained swap thrashing can make that route
eligible. The 32,000,000,000-byte managed-artifact limit remains unchanged.
After recording the download checkpoint, the local full `./mf.sh test` gate
reported 309 passed and one dependency deprecation warning in 25.47 seconds.
After the runtime/device evidence update, the final local full gate reported
the same 309 passed and one warning in 26.30 seconds. Hosted CI
was not used, and ControlDeck repository changes remain zero.

## MiniMax H3 bounded evaluator implementation (2026-08-23, active)

A private Model Management evaluation action now accepts only the catalog-pinned
`unsloth/MiniMax-H3-GGUF` identifier. It creates or attaches a ControlDeck Host
Job, requests the broker with all four VRAM dimensions and
`estimated_runtime_sec=1800`, activates and renews the granted lease, observes
both local and Host cancel, and releases the lease in its isolation boundary.
The native command is an argument array with a fixed 640x384 / 5-frame / 1-step
bounded smoke preset. It pins `ROCm0`, places the text encoder on CPU and
diffusion/VAE on the GPU, and does not enable unbounded full CPU offload.

The evaluator records elapsed time, worker RSS/process swap, system swap-in and
swap-out page deltas, baseline/peak R9700 VRAM, output bytes/hash, and bounded
ffprobe metadata. The output and runtime log stay below the private data root;
no path, prompt, repository, URL, or command is accepted from the workspace.
Evaluation metadata is capped at 16 KiB. A service restart fail-closes an
in-flight evaluation because its short-lived Host identity cannot be resumed.

An isolated preflight using a temporary SQLite data directory and the actual
NVMe model/runtime roots returned
`available_model_ids=['unsloth/MiniMax-H3-GGUF']`. Focused evaluator, Model
Management, frontend-contract, Host-execution, and video-catalog tests passed
86 tests in 11.45 seconds. The full local gate after the evaluator changes was:

```text
./mf.sh test
317 passed, 1 warning in 31.12 sec
```

The isolated subprocess tests observed lease activate/renew/release, Host and
local cancellation, process-group termination, nonzero native exit isolation,
restart fail-closed behavior, fixed mixed placement, and video-plus-audio
validation. These are implementation/contract observations, not R9700 tensor
execution evidence. The real evidence is recorded in the following section.
Hosted CI was not used and the ControlDeck repository was not changed by this
evaluator slice.

## MiniMax H3 real R9700 evaluation and RAM-offload decision (2026-08-23)

The first installed-workspace action exposed two integration defects before a
model was allowed to run. The Host accepted and activated a real 33,073,741,824
byte lease, but consecutive forced Job progress updates exceeded the Host's
2 Hz limit and HTTP 429 was normalized to `host_request_rejected` in operation
`modelop_0bded9ab51d4431eb060a7f2d9331a3c`. `force=True` now waits until the
0.55-second progress interval instead of bypassing `ProgressGate`; a focused
clock-based regression test covers this behavior. The lease was released.

The workspace had also used `window.confirm()` even though the Host's opaque
iframe intentionally omits `allow-modals`; Chrome ignored the call and no
request was submitted. Gated license acceptance now uses an in-workspace
`dialog`, and the non-destructive evaluation action starts directly. An actual
installed-host Chromium action subsequently reached the evaluator with zero
console/page errors. The Host sandbox was not weakened.

Operation `modelop_c52ded655bbc4f3a8d5d1aee12bc7c79`, Host Job
`19498496a63a`, completed the shipped bounded smoke preset:

```text
input                         640x384, 5 requested frames, 1 step, 24 fps
elapsed                       160.860 sec
parameter placement           text encoder 13,985.83 MB RAM
                              diffusion + VAE 13,331.93 MB VRAM
peak process RSS              26,347,757,568 bytes
peak process swap             0 bytes
baseline / peak R9700 VRAM    59,912,192 / 14,614,786,048 bytes
incremental peak VRAM         14,554,873,856 bytes
system pswpin / pswpout       +1,167 / +192,766 pages
output                        122,118-byte WebM, SHA-256
                              0a66b4e5b71e769b5c10b6daf04de0ca5b4d5aa92b51e50d0143bd2617b6712a
media                         VP8 640x384 24fps 0.167sec + stereo PCM s16le
```

Independent `sha256sum` and `ffprobe` reproduced the stored hash and media
metadata. The extracted frame was inspected at original resolution and showed
an incoherent hair/skin smear with no complete person. A one-step smoke is not
a quality preset; it proves the native runtime and output validator only.

A second internal probe used the upstream README's 640x384, 25-frame, 4-step
shape to test useful quality. MiniMax aligned 25 frames to 39. Text conditioning
took 115.48 seconds, and diffusion tensor load then took 65.33 seconds. Sampled
RSS reached at least 19.78 GB, process swap at least 671.3 MB, and system
swap-free fell by about 1.31 GB before sampling ended. `systemd-journald`
reported memory pressure at 01:23:57, 01:24:01, and 01:24:24 JST. The
ControlDeck watchdog timed out at 01:24:30 and restarted the Host at 01:24:57.
Operation `modelop_93008f35df39411fbc3dcf885f6d30f8` failed closed as
`host_unreachable` after about 182 seconds; no video was written. The evaluator
then terminated its worker boundary. No GPU runtime crash is inferred from
these observations.

This quality route is rejected: placing working memory beyond VRAM into RAM is
permitted in principle, but it is practical only if measured wall time, safe
RAM headroom, non-growing swap, Host responsiveness, cancellation, and output
quality all pass. Here Host coexistence, swap behavior, completion, and quality
failed. The shipped evaluator therefore stays at the successful bounded smoke
preset, and H3 remains `experimental`, `healthy=no`, and unroutable. The
32,000,000,000-byte managed-artifact download limit is unchanged and is not a
working-memory limit.

Finally, an installed-host Chromium run started
`modelop_5881b25aec82401fbcb6bed66cbfdffb` and pressed the workspace cancel
button after 6 seconds. It reached `canceled` in 6.24 seconds with no browser
console errors; no `sd-cli` process remained. Host API `/api/v1/resources`
reported request `a0a10307-d048-4abf-8aa6-c0a8a6a51db0`, lease
`258a08cd-5fc5-4a9f-8a0d-b9398f00bcca` as `released`, and Host Job
`470a851b4cc5` as `canceled`. Hosted CI was not used. Public schemas,
`addon.json`, agent tools, workflow executors, and asset/provenance contracts
were not changed. The final local regression gate for this exact worktree was
`318 passed, 1 warning in 31.05s`; this is regression evidence and is not
substituted for the real browser, Host API, process, or R9700 observations
above.

## v0.3.1 release-bundle and installed Host update (2026-08-23)

PR #58 merged as `bcfa6701aee892f5fa2c574c5f6ae1f464fb1207`. An exact-head local
bundle build produced
`control-deck-media-forge-0.3.1-linux-x86_64.tar.gz`, 30,641,380 bytes,
SHA-256 `1b15eaa58f477bce982c3dcc3b093518c84382d11f8fc6bb7a9e1afe47dd30c4`.
The checksum file verified locally and the uploaded GitHub Release asset digest
reported the same value. The release target is the merge commit above.

The extracted bundle started as a real process on port 9137. Its isolated temp
data root correctly reported `setup_required`, rather than claiming a configured
runtime. Standalone Chromium then passed both light and dark runs with 32
advanced nodes, 320px/narrow overflow 0, console errors 0, deterministic edit
and outpaint assertions, and 13 capability states. Evidence is under
`/tmp/mediaforge-v031-evidence.bkUipk/` and is ephemeral local evidence.

ControlDeck PR #227 changed only the trusted artifact SHA. The first real
update failed closed before changing `current`, because the v0.3.1 manifest's
standard `ai.inference` capability was not yet in the trusted allowlist. The
existing v0.3.0 service was restored healthy. ControlDeck PR #228 then added
only that existing provider-neutral capability to the catalog allowlist; it did
not add a Media route, implementation, dependency, or UI string. The corrected
local Host gates passed 28 release-bundle/add-on-AI/contract tests. Hosted CI
was not used.

The second real Optional Feature Manager update succeeded:

```text
version:          0.3.1
state:            installed, managed, enabled, healthy
current:          versions/0.3.1
previous_version: 0.3.0
systemd main PID: 421078
```

Real HTTP `/health` returned contract 2.0 / healthy with the R9700 gfx1201,
ROCm Torch runtime, model library, and disk checks all `ok`. H3 evaluation was
not started without a normal authenticated workspace action: unsigned token
creation, signing-key access, and reuse of another job's lease remain forbidden.
Therefore actual H3 load/generation, RAM/VRAM/swap peaks, output validation,
real cancel, and quality remain **NOT TESTED**. The installed logged-in browser
was opened at `/x/media-forge/workspace/settings`; at that checkpoint the H3
card's `実機で評価` button remained unpressed. The later bounded smoke evidence
below supersedes that checkpoint.

After recording the exact release and installed state, the local full gate
remained 317 passed with one dependency deprecation warning in 28.02 seconds.

## v0.3.2 release-bundle and installed Host update (2026-08-23)

PR #60 merged as `676f8cce1e4ecdc929967a2923250440cc4de817`. An exact-head
local bundle build produced
`control-deck-media-forge-0.3.2-linux-x86_64.tar.gz`, 30,642,575 bytes,
SHA-256 `ec864154b9d5e79fdfee8f616d3b02bd74ac29f80fd10822ac676881de12e3d9`.
The checksum file verified locally and the uploaded GitHub Release asset digest
reported the same value. Release v0.3.2 targets the merge commit above. Hosted
CI was not used.

The extracted artifact started as a real process on port 9137. Its isolated
data root correctly returned `setup_required`, and the bundle served the
v0.3.2 manifest, in-workspace model dialog, and updated JavaScript. Standalone
Chromium passed light and dark runs with 32 advanced nodes, 13 capability
states, phone and 320px overflow 0, 60px mobile tabs, deterministic mask and
outpaint assertions, and zero console errors. The first attempts also exposed
that `scripts/ux_standalone_e2e.py` did not create its declared `sample.png`;
manual fixtures made the release checks pass, and this evidence slice adds a
dependency-free deterministic 64x64 PNG writer so future runs are self-contained.
Evidence is under `/tmp/mediaforge-v032-evidence.9nl0ol/` and is ephemeral.

ControlDeck PR #230 changed only the generic trusted-catalog SHA and merged as
`a47e4175e55f74d18b20bb5400b2fea96d048167`. No route, provider code,
dependency, capability, or Media-specific UI string was added. From the Host's
expected backend cwd, the local release-bundle, Add-on AI, and contract gate
passed 28 tests in 1.18 seconds. A prior invocation from the repository root
failed two subprocess CLI checks because `app` was not importable from that
cwd; the correct invocation passed and no code change was needed.

The real Optional Feature Manager update completed in 23.59 seconds:

```text
version:             0.3.2
state:               installed, managed, enabled, healthy
current:             versions/0.3.2
previous_version:    0.3.1 (update result)
retained versions:   0.3.1, 0.3.2
systemd main PID:    474013
```

The installed service unit and `current` symlink both resolve to v0.3.2. Real
HTTP `/health` returned contract 2.0 / healthy with core, ROCm runtime, R9700
gfx1201, model library, and disk checks all `ok`. An authenticated installed
Chromium session observed Host bridge `ready`, the H3 card and evaluation
button, the new model dialog, and zero console/page errors. Host
`/api/v1/resources` reported zero active Media Forge leases.

The shared data/model boundary was preserved. Before and after update the H3
snapshot occupied 26,978,278,484 bytes, and the denoiser blob independently
hashed to its pinned
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
No native H3 worker remained. The update did not delete Media Forge assets,
models, feature data, or shared caches. Public contracts were unchanged. After
the self-contained light/dark browser rerun, the local full regression gate was
`318 passed, 1 warning in 29.34s`; tests are not substituted for the installed
service, browser, Host API, and filesystem evidence above.

The evidence and self-contained E2E fixture merged in Media Forge PR #61 as
`4c310cb19d26bbf548c93c145a24f84314a0cd80`. ControlDeck recorded the Host-side
update in PR #231 as `ee28acb1527ccad8856bacbad297c7954bc55739`.

## MiniMax H3 version-pinned prompt recipe (2026-08-23)

Media Forge now owns a private `minimax-h3-prompt-writing` projection based on
the upstream `skills/h3-prompt-writing` layout at commit
`d21241f0a4b3acbb34c97dae47fa417b7065e438`. The adapter supports T2VA, I2VA,
FL2VA, L2VA, and Ref2VA without adding a public model-specific API. It bounds
duration to 4--15 seconds, validates mode-specific reference counts, assigns
`<Picture n>` / `<Video n>` / `<Audio n>` labels, validates required and unknown
labels, preserves caller-declared dialogue/lyrics/visible text verbatim, and
renders a fixed three-field or six-field result. Arbitrary skill execution,
repository/path/command input, and Media Forge provider/model/port selection do
not exist.

The upstream skill text was not vendored because that pinned repository commit
has no root license file covering it. The consulted `SKILL.md`, `base-en.txt`,
and `ref-en.txt` hashes are pinned in code as
`a7000443588ca3f145e3b3fd8900f14e0325dc460bd811268fac89a9dc8e56d0`,
`2cfebc096a6e08370f288d468d90b60f7f9bcb938f94bf090816e910e48e75fc`, and
`1e574f356716ad55612247ffb7bbccbcdb484ad96599d63c7dca1af186b1fab7`.
This records provenance without redistributing the source text.

An isolated real ControlDeck process on port 18776 used its normal AI routing
policy and a normal Add-on bridge service identity. A source Media Forge process
on port 19131 submitted a prompt-only T2VA projection. ControlDeck selected and
served its configured text model; Media Forge sent exactly one
`text.generate` request and no `vision.analyze` request. The successful warm
request completed in 14.126 seconds and returned a 1,519-byte rendered prompt
with the required field order and the Japanese dialogue string preserved. Host
audit entries recorded only capability `text.generate`; no provider/model
identity was added to Media Forge provenance.

The first real response was strict-schema JSON inside one Markdown JSON fence.
The initial parser rejected it as `prompt_recipe_invalid`; the adapter now
accepts exactly one bounded JSON fence while still rejecting surrounding prose.
A projection that omitted required verbatim text also failed closed, and a
subsequent corrected projection succeeded. No automatic retry loop was added.
After the run, the selected text runtime was unloaded, Broker active/waiting
counts were both zero, isolated processes were stopped, and the shared installed
v0.3.2 service remained healthy on port 9130. ControlDeck source changes were
zero; its pre-existing `frontend/tsconfig.tsbuildinfo` modification was not
touched.

Focused recipe/workspace transport tests passed 38 tests. The full local gate
was `333 passed, 1 warning in 34.60s`. Hosted CI was not used. Public schemas,
`addon.json`, agent tools, workflow executors, and asset/provenance contracts
were unchanged. Real H3 generation with this projection, video quality, and a
release bundle containing this slice are **NOT TESTED**. H3 remains
Experimental, unhealthy, and unroutable. CI-4 Unified Evaluator was completed in
the following slice; public G7 video work remains deferred.

## Creative Intelligence CI-4 — Unified Evaluator (2026-08-23)

The former binary semantic reviewer and C5 six-axis evaluator now converge on
one `HostCreativeEvaluator` and the canonical `EvaluationResult` dimensions:
`intent`, `subject_identity`, `action_state`, `palette`, `composition`, `style`,
`props_clothing`, and `visual_integrity`. `semantic_review.py` and its binary
provider schema were removed. The frozen `qa.semantic`,
`image.semantic_review`, and `semantic_review_exhausted` contract names remain
compatibility entrances/results, but they no longer select a second reviewer.

Deterministic PNG/edit/outpaint validation still completes first. Normal
single-candidate generation with `qa.semantic=false` performs no VLM call.
Explicit comparison and opt-in QA use the same evaluator. Only dimensions
implied by user controls and reference roles are scored; all other dimensions
must be null or the provider result fails closed. Acceptance and advisory rank
derive from that result. Opt-in regeneration consumes only the existing 0..3
candidate budget, and provenance records scores, issues, strengths, retry
suggestions, relevant dimensions, review budget used, and capability-level
evaluator identity. It records no required provider/model identity. If the
evaluator is unavailable or invalid, deterministic-valid output remains usable
with an explicit advisory warning.

Focused evaluator, QA, and Creative Intelligence tests passed 30 tests. They
cover palette-only references not scoring action, role-specific dimensions,
irrelevant-score rejection, deterministic failure preceding VLM, advisory
single-candidate behavior, second-candidate acceptance with
`review_budget_used=2`, bounded exhaustion, evaluator-unavailable degradation,
and existing C5 result-stage ranking.

For real acceptance, an isolated ControlDeck on port 18776 and source Media
Forge on port 19131 used a normal login, bridge handshake, and Host-issued
service identity. Two deterministic 192x192 imported PNG candidates were sent
through the existing `creative.evaluate` workspace method. The request
completed in 18.338 seconds, returned two advisory ranked results, requested no
regeneration, and populated only `intent` and `visual_integrity`; the other six
canonical scores were null. Both candidates were accepted with rank score 100.
This is transport/schema/ranking evidence for deliberately simple fixtures, not
a broad subjective-quality benchmark.

The isolated Host audit DB contained exactly two successful
`addon.runtime.ai.complete` entries, each with only capability
`vision.analyze`. Broker active leases and waiting requests were both zero.
The ControlDeck-selected text/vision runtime was unloaded, ports 18776, 19131,
and 8096 were closed, the shared Add-on registry was restored byte-for-byte to
its pre-test normalized v0.3.2 manifest, and installed port 9130 remained
healthy. ControlDeck source changes were zero; the pre-existing
`frontend/tsconfig.tsbuildinfo` modification was untouched.

Installed-bundle browser behavior, release bundle creation, real FLUX candidate
evaluation, and subjective ranking across complex reference roles are **NOT
TESTED** in this slice. Public schemas, `addon.json`, agent tools, workflow
executors, and asset/provenance contracts were unchanged. Hosted CI was not
used. G4 Coding Agent project/output grant placement was completed in the later
section below; G7 video remains deferred.

The final full local regression gate for this worktree was
`336 passed, 1 warning in 32.36s`. This is regression evidence and is not
substituted for the real Host bridge, AI audit, process, or cleanup observations
above.

## G4 prerequisite design correction (2026-08-23)

Repository inspection found that ControlDeck already provides browser-issued
read/export grants and atomic Runtime output commit, but its OpenCode Add-on MCP
token is not bound to the current project and has no non-interactive generic
project-output grant tool. Therefore the earlier roadmap statement that all G4
Host acceptance was implemented was too broad. Media Forge cannot close this
gap without receiving or deriving a raw Host project path, which is forbidden.

`controldeck-integration-plan.md` §11.1 now defines the minimum generic Host
prerequisite: bind the MCP token to an already-resolved managed project and
issue an opaque Add-on output grant for a bounded existing project-relative
directory. No Media-specific Host route/policy is permitted. Host
implementation, Media Forge `media.pack`, atomic real project placement,
OpenCode code-reference update, and build/test are **NOT TESTED** at this design
checkpoint. The docs-only worktree retained the full regression gate at
`336 passed, 1 warning in 33.19s`; hosted CI was not used.

## G4 Coding Agent project asset placement (2026-08-23)

ControlDeck PR #232 implemented the minimum generic prerequisite from
`controldeck-integration-plan.md` §11.1: direct CodeDEV child projects are bound
to job-scoped OpenCode MCP tokens, and eligible Add-ons can receive an opaque
project output grant for one bounded existing subdirectory. Root, traversal,
backslash, and symlink escape requests fail closed. PR #233 changed the generic
generated MCP client timeout from 10 to 135 seconds, above the existing 120-second
Host Agent Job and 130-second stdio bridge bounds. Neither Host change contains a
Media-specific route, provider, model, or path contract.

Media Forge adds the `media.pack` agent tool and additive
`project-asset-placement.json` schema. It accepts only an immutable Media Forge
asset ID, an opaque export `grant:` ID, and an optional safe filename. It requires
the token-bound correlation job, rejects raw paths and MIME/extension mismatch,
then reuses the existing Host staged upload and atomic commit. The response
contains the Host `asset:` ID, Media Forge asset ID, filename, MIME, size, and
SHA-256; it contains no project/model/provider/path identity.

Real acceptance used installed ControlDeck, the source Media Forge on port 19131,
OpenCode 1.18.18, the configured local 27B text/vision runtime, and R9700 gfx1201.
The first resource attempts correctly exposed and retained three failures:

```text
observed supervision       resource_unavailable / insufficient_capacity
old generated MCP config  request timed out at 10.006 and 10.005 seconds
pre-fix semantic QA       image worker ended but its exclusive lease remained,
                          so vision runtime load and job waited until endpoint timeout
```

The semantic-QA deadlock was fixed by canceling lease maintenance and confirming
the image generation lease release immediately after the worker exits, before
deterministic post-processing can opt into `vision.analyze`. Release failure now
fails the job closed instead of starting Host AI while ownership is ambiguous.
The Host audit shows the successful final lease activated at 09:21:28, renewed
seven times, and released at 09:22:43; only then did `vision.analyze` complete at
09:23:06. A regression records an empty Host reserved-lease snapshot at the AI
call. Repeated diagnostic runs entered the Broker anti-thrash window, so the final
run explicitly stopped the then-idle LLM before the tool request; a preceding run
had already demonstrated automatic managed yield to the same R9700 worker.

The successful OpenCode run performed the planned sequence without human file
placement:

```text
project inspect           README.md / index.html / package.json / verify.mjs
media.generate            107.901 seconds, capability auto, local_only=true
worker                    load 64.520666 s / generation 1.236461 s
Media Forge asset         asset_c591c6e3e07b43a094a0b76be1f006ec
output                    PNG RGBA 256x256 / 73,238 bytes
SHA-256                   a10381bf2e99f650f69b145cb5457f2ac816885e77a6a82bd16aef41f085a45e
deterministic validators  non-empty / dimensions / mode / alpha all passed
unified evaluator         accepted; intent 1.0 / visual_integrity 1.0
Host output grant         opaque grant only; no path returned to Media Forge
Host committed asset      asset:d21d042b-444d-4cc3-9fa0-5e5e68522b0e
code update               index.html -> assets/player-robot.png
npm run build             PASS / verified 73238 byte project asset
npm test                  PASS / verified 73238 byte project asset
```

The committed Host asset size and SHA match the immutable Media Forge asset. A
visual inspection confirmed a readable centered blue robot with transparent
background; this is direct output-quality evidence for this one 2D-game fixture,
not a broad model-quality benchmark. Focused host/evaluator regression passed 47
tests. The final full gate passed 344 tests in 34.58 seconds with one upstream
Starlette/httpx deprecation warning. The exact-head bundle, extracted bundle,
installed update, and installed-browser acceptance were completed in the release
section below. Hosted CI was not used.

## v0.4.0 G0–G4 release-bundle and installed Host update (2026-08-23)

Release v0.4.0 targets G4 merge commit
`5a340ac2a9729b1fd591e4287c7adfca1252ff4a`. The exact-head local bundle is
`control-deck-media-forge-0.4.0-linux-x86_64.tar.gz`, 30,971,889 bytes, SHA-256
`51ee55c1da6d491852e145d6e2fc42b1b46eccedfae50176b1a34d6ba5f98799`.
The local checksum and GitHub Release asset digest match. Hosted CI was not used.

The extracted artifact ran as a real process on port 9137 with an isolated data
root. It correctly returned `setup_required`, contract 2.0, and
`agent_tool:media.pack=available`; the packaged manifest reported version 0.4.0
and the additive `media.pack` endpoint/schema. Standalone Chromium light and dark
runs both passed with 32 advanced nodes, 13 capability states, mask/outpaint
pointer assertions, 390px and 320px overflow 0, 60px mobile tabs, and zero
console errors.

ControlDeck PR #234 changed only the generic trusted artifact SHA and merged as
`f716630b9067ca0d91ffe2722ac75ce849bb5ac6`; PR #235 records Host evidence.
The release-bundle/Add-on-AI/contract focus passed 28 tests in 1.19 seconds.
The real Optional Feature Manager update completed in 12.75 seconds with max RSS
784,004 KiB and returned version 0.4.0, previous version 0.3.2, installed,
managed, enabled, and healthy. `current`, service WorkingDirectory, and ExecStart
all resolve to v0.4.0; versions 0.3.2 and 0.4.0 are retained. Real HTTP health
reported every R9700 gfx1201/ROCm/model/disk setup check `ok`.

The first installed-browser attempt stopped on a stale E2E fixture assertion:
the current UI intentionally has six ratio presets plus custom, while the script
still required exactly three. The fixture now verifies the six named bounded
presets, 16-pixel divisibility, and a dimensionless custom choice. Rerun light
and dark Chromium both passed with Host bridge `ready`, correct theme tokens,
advanced-mode persistence across reload, Host route sync, 390px overflow 0,
60px tabs, two-column mobile library, and zero console/page errors.

Post-update cleanup observed Host active lease 0, waiting request 0, Media Forge
lease 0; saved Media Forge jobs 41 with active 0; and no image/video worker.
The H3 snapshot remained 26,978,278,484 bytes and its 8,063,029,344-byte denoiser
blob retained SHA-256
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
All 94 asset files remained. Browser-test sessions were revoked and the existing
fixture user's password hash was restored after each run. H3 quality generation,
public video generation, CI-5, and CI-6 remain **NOT TESTED** by this release.
The final release-evidence worktree regression gate passed 344 tests in 34.55
seconds with one upstream Starlette/httpx deprecation warning.

## Creative Intelligence CI-5 — C4 shot direction (2026-08-23)

C4 multi-cut compositions now accept the existing Director mode and accepted
Reference Intelligence context. For non-`original` mode, Media Forge sends one
provider-neutral `text.generate` request and validates exactly 2--4 structured
shot briefs. Count, index, and the `main` / `coding` / `device` / `chibi` roles
are supplied and revalidated by Media Forge rather than selected by the model.
The accepted parent plan and per-shot action, scene, composition, camera, and
details are projected into the existing normal child Job path. The existing C4
Composer remains authoritative for crop, frame, safe margins, dimensions, and
exact title/caption. Exact composition text is absent from the diffusion child
plans.

No new generation, batch, composer, evaluator, or retry subsystem was added.
The CI-4 `EvaluationResult` path remains the only semantic evaluator, and the
existing `qa.semantic` 0..3 budget is preserved. An accepted reference analysis
is reused across children. Prompt-only composition does not request
`vision.analyze`. `original` mode makes no AI call, and unavailable, invalid,
duplicate, or non-distinct AI results fail soft to deterministic C4 planning.

Real installed-ControlDeck structural acceptance used the source service on
port 19132, the installed Host on port 8765, its configured Qwen3.8 27B text
runtime, R9700/gfx1201 Broker, and the existing fake image worker. The successful
browser run completed in 64.452 seconds and observed:

```text
Director calls              1 text.generate / 0 vision.analyze
composition                 composition_0914b433af5d44aa8a877c9ab8578e4b
server-owned roles          main / coding / device
ordinary child Jobs         3 succeeded
shot assets                 3
deterministic final assets  1
exact text                  CI5 EXACT TITLE / CI5 EXACT CAPTION, composer only
mobile                      320px overflow 0
browser errors              console 0 / page 0
wall time                   64.452 seconds
```

The fake worker declares a one-second resource estimate while the selected
LLM's measured yield threshold was 47.188 seconds. Broker therefore correctly
reported `yield_thrash_cost` instead of evicting the LLM for a shorter fake
task. After an explicit operator `llama.stop_instance()` action, the three
ordinary child requests were granted in order; all three leases activated and
released, and the final restored Host snapshot had active leases 0, waiting
requests 0, lease-reserved bytes 0, and no resident key. This is bounded
structural/transport evidence, not evidence that a one-second fake workload
should trigger automatic managed yield.

Initial setup recorded one rejected test configuration and one real integration
defect. A raw source manifest was rejected because it lacked the Host-normalized
runtime contract; the test then used the installed normalized manifest with
only its loopback base URL changed. With that corrected, three concurrently
waiting child Jobs eventually received HTTP 429 from Host progress updates: the client scheduled at
the exact 0.5-second boundary using request-start time and repeatedly sent the
same waiting state, while resource and cancel state were each polled every 0.1
seconds. Media Forge now uses a 0.65-second progress margin, suppresses identical
waiting reports, and polls waiting resource state at 0.5 seconds. Focused Host,
workspace, composer, Creative Intelligence, and frontend regression passed 147
tests. The full local gate passed 351 tests in 38.71 seconds with one upstream
Starlette/httpx deprecation warning.

After acceptance, test browser sessions 457--460 were revoked and the fixture
password hash restored. The Add-on registry, state, and runtime policy were
restored byte-for-byte to SHA-256 `ceefb170451e3f396de4e4ac6c6f28d2c1374e9629de667a4788f814aeca5556`,
`9d56a834f40c90cdd3784e8d10abceddd23fa87e6c0a24dca7ce9c7379d220c4`,
and `4aa1aa93f1051dbe1d5e5b3addaa1be60ac2d964f7a4ee3d07173cedc0abbc2f`.
Installed v0.4.0 returned healthy on port 9130 with `observed` supervision and
120-second minimum uptime. ControlDeck remained at exact `origin/main`; its
pre-existing `frontend/tsconfig.tsbuildinfo` modification was untouched.

Automatic managed text-to-real-image handoff, real R9700 multi-shot image
generation, identity/style consistency, evaluator ranking of real child
candidates, subjective final-composition quality, 390px installed acceptance,
and a release bundle containing CI-5 are **NOT TESTED**. These remain CI-6
acceptance items. Hosted CI was not used and public frozen contracts were not
changed.

## v0.5.0 CI-5 release-bundle and installed Host update (2026-08-23)

Release v0.5.0 targets CI-5 merge commit
`8e822876864a48078edd41e5ca3a8957d78da067`. The exact-head artifact is
`control-deck-media-forge-0.5.0-linux-x86_64.tar.gz`, 30,982,625 bytes,
SHA-256 `9e24c3bff45cc4ab1763269758c202c55ab60ffd517664b1775bbd8eeecfa0be`.
The local checksum and GitHub Release digest match.

The extracted bundle ran on port 9137 from
`/tmp/mediaforge-v050-extracted.GK26Zm` with an isolated data root and returned
`setup_required`, contract 2.0, and `media.pack=available`. Standalone light and
dark Chromium runs reported ready in 0.130 and 0.125 seconds, 32 advanced nodes,
all six bounded ratio presets plus custom, 320px overflow 0, 60px mobile tabs,
a two-column phone library, and zero console errors.

ControlDeck PR #236 changed only the trusted catalog artifact SHA and merged as
`0b56d309fa1cafe195012a0961cf20f6e7bd1a8c`. Its focused release-bundle tests
passed 28 tests in 1.22 seconds. The real feature update from v0.4.0 completed in
15.29 seconds with max RSS 784,384 KiB and swap operations 0. Installed status
reported v0.5.0, managed, enabled, and healthy; retained versions are v0.4.0 and
v0.5.0. The pre-update 94 asset files and 67,170,534,265-byte feature-data root
were retained. Hosted CI was not used.

## Creative Intelligence CI-6 — installed Host and R9700 gate (2026-08-23)

Acceptance used installed ControlDeck on port 8765, installed Media Forge
v0.5.0 on port 9130, the Host-selected Qwen3.8-27B Vulkan text/vision target,
and FLUX.2 Klein 4B on the R9700/gfx1201 ROCm worker. The add-on effective state
contained `ai.inference`. Media Forge `config/config.yaml` remained SHA-256
`9a0acf73dbacc75a02df29ae19cd88b042d988c3959a9b9243a861a2c8bb80e2`
and contains no provider, model, or port selection. CI-1 acceptance had already
switched between two ControlDeck-selected Qwen3-VL Ollama targets with zero
Media Forge config changes; this run used the later Qwen3.8 llama.cpp target
through the same capability contract.

The v0.5.0 real-reference run imported the retained 512x512 character image.
`vision.analyze` completed in 50.263 seconds, the same asset hash hit the cache
in 0.061 seconds, and the reference-aware Director completed in 11.851 seconds.
The Host audit delta was exactly `vision.analyze`, then `text.generate`.
Original mode used no assistance. The installed iframe had 320px overflow 0
and browser errors 0.

The main R9700 run produced these results:

```text
prompt-only Director       15.218 s / text.generate 1 / pre-generation vision 0
uncommon human action      custom one-handed backbend pose / 17.107 s image Job
original non-human action  solar-panel rover / Director calls 0 / 22.407 s image Job
C3 action variation        text.generate 1 / 2 child Jobs / 37.504 s total
child actions              welding cracked panel / replacing blown fuse
generated outputs          4 PNG RGBA assets at 256x256 / deterministic validation PASS
QA budget                  semantic=false / max_regeneration_attempts=0 / retries 0
installed mobile           390px overflow 0 / 320px overflow 0
browser                    console errors 0 / page errors 0
```

Visual inspection confirmed the human backbend and lantern, an orange rover
with deployed solar panels, an orange robot welding with visible sparks, and a
second orange robot working at a fuse panel. This is direct evidence for these
five bounded prompts, not a broad FLUX quality benchmark or a claim of perfect
identity consistency.

Explicit unified evaluation compared the two real C3 candidates in 34.456
seconds and ranked the welding asset first for the welding intent. Generation
Job count remained 46 before and after, proving advisory evaluation created no
new Job. Its 320px overflow and browser errors were zero.

For fail-soft acceptance, the installed grant and image capability remained
present while compatible Host text/vision targets were temporarily reduced to
zero. Director returned `host_ai_unavailable`; the unchanged prompt-only path
generated a validated solar-panel rover in 20.088 seconds. The add-on state,
Qwen role selection, and Broker policy were restored afterward. Removing the
grant itself was also tried and correctly made the Host hide the contribution
as missing a declared requirement; that pre-generation attempt is not counted
as the AI-unavailable generation result.

Before managed handoff, resident Qwen used 31,582,920,704 of 34,208,743,424
R9700 VRAM bytes. The real image lease automatically yielded it and VRAM fell
to approximately 8.1 GB before worker loading. The sampler observed maximum
GPU use 98%; swap moved from 3,631,087,616 to a maximum 3,994,058,752 bytes.
After all tests, ControlDeck reported requests 0, leases 0,
lease-reserved bytes 0, resident keys 0, and R9700 VRAM used 59,924,480 bytes.
RAM available was 28,657,033,216 bytes and swap used 3,917,365,248 bytes.

All temporary browser sessions were revoked and the fixture password hash was
restored. Add-on state returned to SHA-256
`9d56a834f40c90cdd3784e8d10abceddd23fa87e6c0a24dca7ce9c7379d220c4`;
runtime policy returned to `observed` with 120-second minimum uptime. Installed
v0.5.0 remained healthy. The retained H3 snapshot stayed 26,978,278,484 bytes
and its 8,063,029,344-byte denoiser retained SHA-256
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
H3 quality was not retried and remains experimental, unhealthy, and unroutable.
Public video generation remains **NOT TESTED**. Hosted CI was not used and the
frozen public contracts were unchanged.

The final canonical local regression gate passed 351 tests in 42.27 seconds
with one upstream Starlette/httpx deprecation warning. This is regression
evidence and is not substituted for the installed browser, Host audit, Broker,
R9700, provenance, or visual observations above.

## Worker/core image composition boundary (2026-08-23)

The image worker no longer imports `mediaforge.image_edit` or
`mediaforge.outpaint`. Worker-owned PIL planning/composition now lives in
`worker_packs/image/edit_composition.py`. The independently implemented core
`validate_strict_edit` and `validate_outpaint` remain authoritative after the
worker exits; no worker validation result is trusted or reused by core.

The real worker environment now sets `PYTHONPATH` to the worker-pack root only
and does not inherit the parent development path or expose `backend`. The
release builder no longer ships `backend/mediaforge` source as worker data. A
static AST regression rejects every absolute `mediaforge` import under the
image worker pack, and the bundle regression rejects reintroducing core source
for the worker. Frozen public schemas, `addon.json`, operations, tools,
provenance, and Host contracts did not change.

Focused strict-edit, outpaint, adapter, routing, and bundle regression passed
48 tests. Real acceptance stopped the installed v0.5.0 unit and ran the exact
source branch on the same port 9130 with the installed data, model store, ROCm
runtime, and ControlDeck Host/Broker path. The installed unit was restored
afterward.

```text
strict edit       20.106 s / asset_486013ae0738421c9cad20fab48fb115
worker timing     load 10.639245 s / generation 5.877777 s
core validator    protected pixel difference 0 / editable pixels 10,179
outpaint          107.367 s / asset_2bcb5869f4b44471b249af134a42fb04
worker timing     load 8.383039 s / generation 94.004853 s
core validator    source pixel difference 0 / generated pixels 131,072
placement         all components cuda:0 / offload hooks 0 / non-GPU targets 0
browser errors    0
Broker cleanup    active 0 / waiting 0 / reserved bytes 0
```

Visual inspection confirmed the strict result retained the source outside the
mouth edit and the outpaint result retained the complete centered 512x512
source while generating both side regions. The first browser attempt was
**not** a generation result: the historical G2 fixture still targeted a removed
operation select and stopped before asset import or GPU work. The dedicated
boundary fixture uses the current opaque bridge and completed both Jobs.

Installed v0.5.0 returned healthy after restoration, no image worker remained,
and R9700 VRAM use was 59,924,480 bytes. H3 quality was not run. Hosted CI was
not used. The final canonical local regression gate passed 352 tests in 37.33
seconds with one upstream Starlette/httpx deprecation warning. G5 M5 companion
profiles/validators/pack are the next slice.

## v0.5.1 worker-boundary release and installed Host update (2026-08-23)

Release v0.5.1 targets worker-boundary merge commit
`2b3114dd8e2c92c1b4464a1c2d600b0a8aff57cd`. The exact-head artifact is
`control-deck-media-forge-0.5.1-linux-x86_64.tar.gz`, 30,585,125 bytes,
SHA-256 `a615fc014d6584c255c72399b40963dbc06a4f5bd99d02ee3137b083f7409c0f`.
The local checksum and published GitHub Release digest match.

PyInstaller archive inspection found
`worker_packs/image/edit_composition.py` and the FLUX adapter, and found zero
worker data entries for `mediaforge/image_edit.py` or `mediaforge/outpaint.py`.
The extracted bundle ran on port 9137 with an isolated data root and returned
`setup_required`, contract 2.0, and the existing contributions. Standalone
Chromium reported ready in 0.082 seconds, 32 advanced nodes, 320px and narrow
overflow 0, 60px tabs, a two-column phone grid, and console errors 0.

ControlDeck PR #237 changed only the generic trusted artifact SHA and merged as
`ab2b9c82440f5e6adfb8833ce38ea7983ddf89bf`. The canonical backend-cwd
release-bundle/Add-on-AI/contract suite passed 28 tests in 1.19 seconds with one
upstream warning. An earlier root-cwd invocation passed 26 but failed two CLI
subprocess tests because `app` was not on their module path; that environment
mistake is not counted as a product result.

The real Optional Feature update completed from v0.5.0 to v0.5.1 in 11.51
seconds with max RSS 786,632 KiB and swap operations 0. It retained the existing
116 asset/provenance files and 67,174,355,135-byte feature-data root. Installed
worker acceptance then produced:

```text
strict edit       13.086 s / protected pixel difference 0 / editable 10,179
outpaint          108.380 s / source pixel difference 0 / generated 131,072
browser errors    0
installed light   bridge ready 0.639 s / mobile overflow 0 / console errors 0
installed dark    bridge ready 0.638 s / mobile overflow 0 / console errors 0
```

Final `current`, service WorkingDirectory, and ExecStart resolved to v0.5.1;
versions v0.5.0 and v0.5.1 were retained. Status was active, running, enabled,
and healthy. The persistent asset/provenance file count became 126 after the two
source/mask/result groups, with feature data 67,177,490,449 bytes. Broker active
leases, waiting requests, and reserved bytes were zero, no image worker
remained, and R9700 VRAM use was 59,924,480 bytes.

The H3 snapshot remained 26,978,278,484 bytes and its 8,063,029,344-byte
denoiser retained SHA-256
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
H3 quality was not retried. Hosted CI was not used and frozen public contracts
were unchanged. G5 is the next implementation slice.

## G6 S1 — 永続化読み出しの前方互換（2026-08-24）

利用者報告「状況タブが読めない」を実プロセスで再現し、根本原因を特定した。
installed v0.5.1（pid 705506 / :9130）へ実 HTTP を投げた結果:

```text
GET http://127.0.0.1:9130/api/v1/jobs   ->  500  21 bytes
service.log の traceback
  mediaforge/app.py:1092 list_jobs -> store.py:292 list_jobs -> store.py:720 _job
  pydantic ValidationError: 2 errors for JobRequest
    inputs         List should have at most 16 items after validation, not 21
    output.format  Input should be 'png','webp' or 'jpeg', input_value='zip'
```

`Store._job()` が保存済み行を **その時点の `JobRequest` で再検証**していた。
公開契約を加法的に広げた版が書いた行を旧版が読めず、1 行の不整合が
`jobs.list` を**コレクション単位**で落としていた。UI はこの失敗を捕まえて
「状況を読み込めませんでした。」と出すだけなので、状況タブ全体が死ぬ。

実データでの実測。installed の実 DB（`media-forge.sqlite3` 491,520 bytes）を
複製し、v0.5.1 の契約（`inputs<=16` / `format` に `zip` 無し）で読ませた:

```text
実 DB の job 行                              90
v0.5.1 契約で厳格に読めない行                3
  job_bbd62caeea9a47aba49a8f9e2ac112b2
  job_c24d3e60d7514a22bce00d8fb6e6036f
  job_7319eaf22ee34a2d95e54c266ce13509
修正前   この 3 行のうち 1 行目で例外。一覧全体が 500
修正後   提供できた行 90 / 90、degraded 3、失われた行 0
```

修正は「ingress で厳格に検証し、読み出しは寛容にする」。
`StoredJobRequest` は `JobRequest` の部分型で、値の意味は変えず受理範囲だけ広げる。
`Job.request` を `SerializeAsAny` にしたので、新しい版が書いた未知フィールドを
古い版が黙って落とさない（`future_field` が往復することをテストで固定した）。
degraded 行は表示は続けるが実行は fail-closed（`job_record_unreadable`）。

欠陥は job 固有ではなかったため、コレクション読み出し全体を行単位 fail-soft に
した（assets / library page / profiles / reference collections / creative
batches / creative compositions）。

```text
./mf.sh test   363 passed, 1 warning in 36.59s（G5 の 359 + S1 4 件）
```

NOT TESTED: 修正版を実 installed へ入れ替えた状態でのブラウザ操作は未実施。
S2 以降と合わせて 1 度で実機受入する。

## G6 S2 — workspace session と一覧サムネイルの往復削減（2026-08-24）

「GUI が重い」の内訳を実ブラウザで計測した。installed v0.5.1（実データ:
job 90 / asset 95）の workspace を読み取りのみで開き、要求を数えた。

```text
修正前   boot ready 2.609 秒   要求 104 件
           api/v1/assets/{asset}/content   95   一覧カード 1 枚 1 往復
           api/v1/models                    2
           その他（capabilities / profiles / reference-collections /
           assets / creative batches / compositions / index）  7
```

主因は 2 つあった。

1. boot が直列 10 往復で状態を組み立てていた（`preferences.get` から
   `jobs.watch` まで）。状態の正がクライアント側の `state` にあった。
2. 一覧のサムネイルが 1 枚 1 往復だった。埋め込み時は 24 枚 = 24 往復、
   standalone の shim では `limit` を無視して 95 枚の**原寸**を取っていた。

対応は 2 つ。

```text
workspace.session   boot と更新を 1 メソッドへ集約。部分指定で読み直せる
                    部分ごとに fail-soft（Host AI probe が落ちても session は返る）
                    jobs / model operations の watch はサーバが張る
session.changed     変わった部分名だけを push。1 秒 polling 3 本を削除
                    （job / creative batch / creative composition）
                    polling は push の無い standalone にだけ残した
一覧サムネイル      160px WebP をカードに同梱。往復 0
                    原寸と拡大表示は従来どおり個別要求のまま
```

同じ実データでの実測。

```text
修正前   boot ready 2.609 秒 / 要求 104 件
修正後   boot ready 0.264 秒 / 要求  14 件      -89.9% / -86.5%
```

埋め込み時はさらに減る。standalone に残る 13 件は集約 endpoint を持たない
shim がクライアント側で束ねているためで、埋め込みでは `workspace.session`
1 往復になる（サムネイル同梱により追加要求 0）。

サーバ側の集約コストは増えていない。実 DB に対する in-process 実測で
旧 11 メソッドの合計 14.05 ms に対し `workspace.session` は 14.25 ms。

```text
./mf.sh test                368 passed
scripts/ux_standalone_e2e.py PASSED / console errors 0 / phone overflow 0
```

NOT TESTED: installed ControlDeck の埋め込み iframe での実測。S3 以降と
合わせて 1 度で実機受入する。

## G6 S3 — AI と画像生成の resource turn 分割（2026-08-24）

「VLM が VRAM を返さないため画像生成が失敗する」の根本原因を実機設定から特定した。

```text
/data1tb/ControlDeck/data/model-runtime-policy.json
  supervision = "observed"   （"managed" ではない）
-> LlamaCapacityProvider._managed() が False
-> reservations() の yield_level が常に NONE
-> broker は設計上 LLM を降ろさない
実機 LLM   Qwen3.8-27B-UD-Q4_K_M + mmproj-BF16 / ctx_size 262144 / n_gpu_layers 999
実機 GPU   R9700 34,208,743,424 B
```

Media Forge は既に生成 lease を vision 前に解放していた（image -> vision 方向）。
足りないのは逆方向（LLM -> image）で、add-on から「AI ターン終了」を伝える口が
公開契約に存在しなかった。

### ControlDeck 本体 / OpenCode との競合（利用者指摘）

実機の経路を確認した。

```text
integrations/opencode/settings.json
  base_url = http://127.0.0.1:8765/api/v1/llm/v1   use_gateway = true
runtime policy  gateway_only = true
```

OpenCode も ControlDeck chat も同じ gateway を通るため、add-on の `ai/complete`
と同じ `_acquire_gateway_lease` / `_active_requests` に集約される。ControlDeck は
idle unload 用に「使用中なら降ろさない」判定を既に持っている
（`_has_connected_clients` / `_opencode_session_uses` / `idle_exclude` / `role`）。

**新しい判定を作らず**、明示解放はこの判定集合と drain 経路をそのまま再利用した。
30 分の idle unload と同じ決定を、時間ではなく要求で起こすだけにした。

### 変更

```text
ControlDeck（別 PR #238）
  POST /{addon_id}/ai/release   ai.inference を持つ任意の add-on が使える宣言
  /ai/complete + ensure_ready   gateway_chat と同じ on-demand 起動
                                これが無いと解放が次の要求を壊す

Media Forge（本 PR）
  4 ステージ  analyze -> release_ai -> generate -> review
              release_ai は lease を持たずに宣言だけ行う
              先に AI 常駐を落としてから受理を求めるので二重予約も deadlock も無い
  1 回だけ    リトライループを作らない（chat / OpenCode を飢えさせない）
  理由付き    解放拒否 + VRAM 由来の受理失敗のときだけ
              host_ai_residency_retained として拒否理由を添える
              それ以外の受理失敗に AI 常駐の話を混ぜない
  旧 Host     404 は既知状態として扱い、従来どおり broker 受理へ落とす
```

```text
./mf.sh test                            376 passed
ControlDeck backend pytest -q           760 passed, 1 skipped（62.93 秒）
```

`llama.py` の `asyncio` は関数内 import のままにした。module 直下へ移すと
`test_jobs_persistence::test_two_exclusive_resource_jobs_execute_serially` の
broker 受理が `queued` のまま止まることを実測で切り分けた。

NOT TESTED: 実機での「LLM 常駐 -> 解放 -> 画像生成」通し。ControlDeck PR #238 を
入れてから rocm-smi の VRAM 推移込みで 1 度に実測する。

## G6 S4/S5 — 到達性とモデル選択（2026-08-24）

backend の /ws method 48 件と frontend の呼び出しを突き合わせ、実装済みだが
GUI から到達できない機能を洗い出した。

```text
到達できなかった
  profiles.create / profiles.delete            G3 一貫性プロファイル（PR-U6 未着手）
  reference_collections.create / .delete       参照コレクション
  asset.pack                                   G5 M5 companion pack
  creative.prompt_recipe                       H3 版固定 prompt recipe
  assets.list                                  library.list が上位互換
  jobs.unwatch / models.operations.unwatch     内部用。UI 機能ではない
```

### 追加した入口

```text
キャラ・画風の登録   設定画面に作成・削除を追加した
                     参照コレクションは profile と一体で作る
                     （利用者に 2 段階を意識させない）
配布用にまとめる     詳細モードから asset.pack を起動できるようにした
                     スロットは profile の宣言だけを根拠に組む
                     media 固有のスロット名を UI へ書き写さない
使うモデル           おまかせ / 指定する の 2 段。詳細モードで
                     fast / balanced / quality / low_vram / manual へ到達できる
選んだ理由           provenance の parameters.model_route から日本語で出す
```

### 出さなかったもの（理由付き）

```text
creative.prompt_recipe   H3 は experimental / healthy=no / unroutable のまま。
                         完了できない機能を GUI に出さない。
                         H3 の条件が改善したときに同じ PR で出す。
media.inspect            operation としては未実装（G0 から capability_unavailable）。
                         「実装済みだが到達できない」ではないため入口を作らない。
                         agent 用 /addon/v1/agent/inspect は provenance 参照であり、
                         workspace では assets.provenance から既に到達できる。
assets.list              library.list が上位互換。二重の入口を作らない。
```

### domain 対応 routing

catalog は各モデルに `domains` を持っていたのに routing が使っていなかった。
`route()` が domain 一致を policy_rank より前段の候補絞りに使うようにした。
一致 0 件なら全候補へ落とす（シーンを選んだだけで使えるモデルが消えない）。
明示指定は自動判断より強く、domain で上書きしない。

### 実ブラウザでの到達確認（読み取り + 実操作）

```text
model_choice_visible                     true
model_choice_manual_reveals_select       true
profile_add_buttons                      true
profile_dialog_open / character_fields   true / true
pack_hidden_in_simple                    true
pack_visible_in_advanced                 true
pack_profiles                            ["m5.companion.pack"]
pack_slot_rows                           21   （base 1 + eyes 12 + mouth 8）
pack_progress                            "0/21 割り当て済み"
page_errors                              []
```

キャラ登録の往復も実操作で確認した。

```text
character_options_before                 1（「使わない」のみ）
作成後 profile_rows                      1   "オレンジの子"
作成後 character_options                 ["使わない", "オレンジの子"]
削除後 profile_rows                      0
削除後 character_options                 1
page_errors                              []
```

```text
./mf.sh test                 387 passed
ux_standalone_e2e.py         PASSED / console errors 0
boot ready                   0.081 秒 / 要求 15 件（機能追加後も退行なし）
```

NOT TESTED: installed ControlDeck の埋め込み iframe での操作。

## G6 S6 — 利用者が追加する HuggingFace モデル（2026-08-24）

「HuggingFace などからダウンロードできるカタログ機能」への対応。
取得系は既にあった（`worker_packs/image/catalog.json` の revision pin 付き
エントリ、`models.install` の SHA-256 検証・再開・32GB 上限）。不足していたのは
**利用者が任意の HF モデルを足せない**ことだけだった。

### 採用しなかった案

```text
GUI から HF Hub を検索して任意 repo を導入する
  却下。revision 非固定・実測 VRAM 無し・license gate・任意コード実行の risk。
  local-first の検証可能性が壊れる。
```

curated pinned catalog を信頼経路として維持し、明示的な第 2 経路を足した。
信頼経路を検証可能にしている規則は、追加分にもそのまま適用する。

```text
revision 固定   moving ref を取得前に不変 commit へ解決する
digest         配布元が返した sha256 を全 weight に持たせ、既存 installer が検証する
license        表示した名前をそのまま承諾させる（本文の提示が先）
実測 gate      experimental で登録し、routing は選ばない
               models.evaluate の実測に成功して初めて昇格する
parser         追加分も shipped manifest と同じ validator を通す
```

### variant 選択（実測で必要と判明）

実 API に当てて分かったこと。HF の diffusers repository は同じ重みの
Flax / ONNX / OpenVINO 版と、fp32 / fp16 の二重持ちを同居させている。
全部数えると導入上限を超え、代表的な repository がひとつも入らない。

```text
stabilityai/stable-diffusion-xl-base-1.0
  全ファイル      49,952,537,087 バイト   上限 32,000,000,000 を超過
  1 variant 選択   7,105,346,772 バイト   weights 5 個
stabilityai/sdxl-turbo
  全ファイル      42,463,333,800 バイト
  1 variant 選択   6,938,011,430 バイト   weights 4 個
```

shard（`model-00001-of-00002.safetensors`）を variant と取り違えて落とすと
壊れたモデルが届くため、shard は全て残すことをテストで固定した。

### 実 HuggingFace に対する /ws 実測

```text
resolve                0.285 秒
  固定した revision    462165984030d82259a11f4367a4eed129e94a7b（要求は "main"）
  weights / bytes      5 / 7,105,346,772
  license              openrail++
  usable_for_generation false
  warn                 実行アダプタ未実測 / 重複 42,011,397,612 バイトは取り込まない
承諾なしの追加          ok=false  custom_model_license_not_accepted
承諾ありの追加          ok=true
catalog 反映            state=experimental installed=false rev=462165984030
二重追加                ok=false  custom_model_exists
削除                    catalog から除去された
```

### Flux 系と SD 系で個別ローダーが要るか（利用者質問への回答）

要る。ただし「モデルごとに 1 から書く」ではなく**系統ごとの薄い adapter**である。

```text
worker_packs/image/adapters/ が既にその境界
  base.py            ImageAdapter Protocol（generate / edit）
  diffusers_flux2.py FLUX.2 用。pipeline class と参照編集の意味論が固有
  native.py          Diffusers を使えない runtime 用の口（未実装）

SD1.5 / SDXL / SD3 は Diffusers の AutoPipelineForText2Image /
Image2Image / Inpaint で 1 個の共通 adapter に相乗りできる。
新規に要るのは pipeline class の選択、dtype と offload 方針、
inpaint / img2img / reference の引数対応表、negative prompt や scheduler の有無だけ。

別 adapter が要るのは次の場合に限る
  Diffusers に pipeline が無い（stable-diffusion.cpp / GGUF 単一ファイル等）
  参照編集の意味論が固有（FLUX.2 の multi-reference がこれ）
  trust_remote_code を要求する（原則入れない）
```

本 PR では共通 adapter を**実装していない**。実測していない adapter を
available にしないため、追加したモデルは `usable_for_generation=false` として
その理由を明示する。取り込みと検証はできるが生成にはまだ使えない、が現状。

```text
./mf.sh test                 412 passed
ux_standalone_e2e.py         PASSED / console errors 0
実ブラウザ到達確認            page errors 0
```

NOT TESTED: 追加したモデルの実ダウンロードと `models.evaluate` の実測。
共通 adapter が無い状態で実行しても生成の証拠にならないため、別スライスへ送る。

## G6 S3 実機検証 — LLM 常駐 / 解放 / 復帰（2026-08-24）

ControlDeck を `infra/addon-ai-explicit-release` ブランチのまま再起動して実測した。

```text
経路の存在      POST /api/v1/addon-runtime/media-forge/ai/release
                無効 token -> 401（404 ではない = 配線済み）
runtime policy  llama.cpp / supervision=observed / gateway_only=true / yield_max=4
対象            Qwen3.8-27B-UD-Q4_K_M + mmproj-BF16 / ctx 262144 / n_gpu_layers 999
GPU             R9700 34,208,743,424 バイト
```

### ❷ の根本原因が数値で確定した

```text
LLM 常駐時の VRAM   59,912,192 -> 31,555,141,632（+31,495,229,440）
```

**34.2GB の GPU のうち 31.5GB を LLM が占有する。** FLUX.2 Klein 4B の
実行 peak は 29,625,200,640 バイトなので、常駐したままでは絶対に入らない。
`supervision=observed` では broker が降ろさないため、待っても解消しない。

### 解放の実測

```text
実行中の要求がある間   released=False reason=drain_timeout（120.058 秒待って拒否）
使用が終わったあと     released=True  reason=released  0.737 秒
                       VRAM 31,555,141,632 -> 59,912,192（全量返却）
推論を 1 回通した直後  released=True  reason=released  2.380 秒
```

### ❽ OpenCode 経由の生成（利用者指摘 2026-08-24）

**最初の設計では成立しなかった。** 実測で判明した。

```text
integrations/opencode/settings.json  base_url = .../api/v1/llm/v1  use_gateway = true
resolve_backend_port()               8096（LLM の実ポートと一致する）
-> _opencode_session_uses は活動中の OpenCode セッションに True を返し続ける
-> 解放は常に opencode_active で拒否される
-> OpenCode から add-on へ生成を頼む経路が、この機能が必要な場面でだけ死ぬ
```

明示解放が idle unload の 30 分窓を引き継いでいたのが誤りだった。idle loop が
「最近誰か触ったか」を見るのは**誰も要求していない**からで、その場合は暖めた
まま保つのが安全側になる。明示解放は逆で、**要求した側が今その VRAM を必要と
している**。実行中の推論を切らない保証は drain 側が持ち、降ろしたものは
`ensure_ready` で自動復帰する。

修正後、OpenCode セッションが活動中に見える状態を再現して測り直した。

```text
load              4.040 秒   VRAM 59,912,192 -> 31,555,141,632
旧判定            _opencode_session_uses = True   （これを見ていたら解放できない）
新判定            release_reason = ""             （解放可）
解放要求          released=True reason=released 0.356 秒
                  VRAM 31,555,141,632 -> 59,912,192（-31,495,229,440 全量返却）
次の turn の復帰   ok=True 5.836 秒（ensure_ready による自動復帰）
後片付け          VRAM 59,912,192（測定前と同じ）
```

残る保証は変えていない。

```text
実行中の推論を切らない      drain（実測 drain_timeout で拒否）
streaming 中は降ろさない    _has_connected_clients
運用者の明示除外            idle_exclude
embedding / reranker        role で対象外
```

`freed_bytes` は降ろしたモデルファイルの大きさである。実際に空く VRAM は
KV cache を含むため大きい（16,464,440,224 に対し 31,495,229,440）。

```text
ControlDeck backend pytest -q   764 passed, 1 skipped（57.66 秒）
```

NOT TESTED: Media Forge 側を実 add-on として動かした「analyze -> release_ai ->
generate」の通し。installed feature は v0.5.1（旧 core）のままであり、
本 PR の core を bundle 化して入れ替えるまで実行しない。

## G6 v0.6.0 バンドル導入と installed 実測（2026-08-24）

```text
bundle   ./mf.sh bundle build 0.6.0 /data1tb/mediaforge-release-bundles
artifact control-deck-media-forge-0.6.0-linux-x86_64.tar.gz
bytes    30,640,703
sha256   ef57f26f78bb5816f967c9256dfce07ae9a135d64602f4137f09004b9bfed73d
```

展開したバンドルを :9137 で起動し、配信 HTML が新 UI であることを確認した。

```text
model-choice 14 / pack-section 2 / custom-repo 2 / profile-add-character 2
workspace.session 4 / session.changed 4
ux_standalone_e2e.py   PASSED / console errors 0
到達確認                pack_slot_rows 21 / page errors 0
```

installed feature を v0.5.1 から v0.6.0 へ入れ替えた（systemd drop-in で
`versions/0.6.0` を指す。`current` symlink も更新）。

### ❸ が installed で解消した

```text
修正前   GET http://127.0.0.1:9130/api/v1/jobs -> 500（1 行の不整合で全件喪失）
修正後   GET http://127.0.0.1:9130/api/v1/jobs -> 200  90 件  degraded 0
         /api/v1/assets -> 200   /api/v1/capabilities -> 200
```

degraded 0 なのは v0.6.0 の契約が当該行を厳格に読めるため。旧契約で読めない
行が来ても一覧は落ちないことは `tests/test_store.py` と実 DB 90 行での
before/after 実測（v0.5.1 契約で 3 行が読めず、修正後は 90/90 提供）で固定した。

### 残る未実測と再現手順

Media Forge 側の「analyze -> release_ai -> generate」通しは、ControlDeck への
ログインが要るため未実施。**利用者のパスワードは扱わない**方針のため、
そのまま実行できる受け入れスクリプトを用意した。

```bash
MEDIA_FORGE_E2E_PASSWORD=... \
  /data1tb/ControlDeck-release-bundle/.venv/bin/python \
  scripts/g6_resource_turn_e2e.py \
    --control-deck-url http://127.0.0.1:8765 \
    --username <name> \
    --evidence-dir /data1tb/mediaforge-g6-evidence
```

このスクリプトが検証すること。

```text
1. boot が workspace.session 1 往復で終わること（WebSocket frame を数える）
2. 状況タブが記録を読めること（degraded 行があっても落ちない）
3. Host LLM を gateway 経由で常駐させ、実際に VRAM を握らせること
4. 実画像 job の phase 列に release_ai が現れ、generating より前にあること
5. VRAM が生成前に返っていること / 実画像が 1 枚できること
6. Broker が空で残り、worker プロセスが残らないこと
```

VRAM は rocm-smi の実測値を phase ごとに記録する。モデル自身の申告ではなく
デバイスを読む。


## G6 resource turn E2E スクリプトの事前検証（2026-08-24）

利用者に実行してもらう前に、ログイン不要で検証できる部分を実プロセスに当てて直した。

```text
framesent の payload      dict ではなく Union[bytes, str] を直接渡す仕様だった。
                          dict 前提のままだと全フレームが空になり、
                          「boot が 1 往復」の判定が常に偽で落ちていた。
                          binary / 非 JSON / method 無しフレームも来るため
                          数えられないものは捨てる形に直し、単体で確認した。
broker snapshot の経路    /api/v1/resources/snapshot は 404。正しくは
                          /api/v1/resources（未認証で 401 = 経路は存在する）。
login helper              ci6_r9700_e2e.py の実績あるものをそのまま再利用した。
                          ControlDeck の login は SPA なので HTML からは確認できない。
```

boot 判定は「`workspace.session` がちょうど 1 回」に加えて、
旧 boot が個別に投げていた 10 メソッドが 1 つも復活していないことも見るようにした。

## G6 resource turn の物理受け入れ（2026-08-24）

利用者から login アカウント作成の承認が出たが、**アカウント作成とパスワード入力は
実施しない**方針を維持した。代わりに、認証境界だけを stub にして物理現象は
すべて実物で測る受け入れを作った（`scripts/g6_resource_turn_physical_e2e.py`）。

```text
実物        常駐 LLM / それが握る VRAM / 実際の解放 / FLUX worker / 生成 PNG
stub        ControlDeck の token・lease の HTTP 面だけ
            ただし ai/release は ControlDeck 自身のコードで本物の unload を行う
別途実測済  Host 側の解放可否判断（G6 S3。実 ControlDeck に対して実測）
```

### 結果

```text
LLM 常駐            VRAM 59,912,192 -> 31,555,141,632   load 8.038 秒
解放                released=true reason=released       0.146 秒
解放後の VRAM        59,912,192（全量返却）
生成                 succeeded / asset 1 枚 / 17.706 秒
  model_id           black-forest-labs/FLUX.2-klein-4B
  runtime_adapter    diffusers.flux2-klein
  weights_hash       sha256:f3fcfa8f…dfae278（manifest と一致）
  output             256x256 PNG / 114,310 bytes
  model_route        policy=auto domain=general domain_matched=true candidate_count=1
worker placement     device_mode=direct_device_map
                     component_devices すべて cuda:0
                     offload_hooks=[] non_gpu_devices={} non_gpu_map_targets=[]
worker timing        load 10.640 秒 / generation 1.074 秒
解放後の VRAM ピーク   18,147,024,896（51 サンプル / 0.25 秒間隔）
後片付け             VRAM 59,912,192 / loaded instance 0
```

順序は log でも確認した。

```text
POST .../ai/release        200
uvicorn.error              ai turn released ... released=True reason=released
POST .../resources/requests 202
POST .../resources/leases/lease-request-1/activate 200
image worker timing / placement
```

**AI ターンの終了宣言が、生成 lease の要求より前**にある。設計どおり。

### ❷ が物理的に確定した

```text
LLM 常駐          31,555,141,632 バイト
FLUX 実占有        18,147,024,896 バイト（解放後の実測ピーク）
合計              49,702,166,528 バイト
GPU 総容量         34,208,743,424 バイト
```

**合計が GPU 容量を 15.5GB 超える。** 常駐したままでは物理的に共存できない。
`supervision=observed` では broker が降ろさないため、待っても解消しない。

### 測定側の誤りを 2 回直した（緑を鵜呑みにしない）

```text
1 回目   phase 境界でだけ VRAM を読んでいた。generating に入るのは worker が
         確保する前なので idle を拾い、「GPU を使っていない」ように見えた。
2 回目   ジョブ全区間のピークで見ていた。常駐 LLM の 31.5GB に支配されるため、
         画像 worker が GPU を 1 バイトも使わなくても必ず通る判定だった。
3 回目   サンプルに時刻を持たせ、解放より後の区間だけでピークを取るようにした。
         これで初めて 18,147,024,896 バイトという画像 worker の実占有が出た。
```

worker の placement log は worker 自身の申告なので、rocm-smi の実測と揃えて
初めて証拠として扱う。両方を assertion に入れた。

### CPU オフロードについて（利用者指示 2026-08-24）

許容の指示を受けたが、**今回は不要だった**。`direct_device_map` のまま
`offload_hooks=[]` で完走している。

catalog の `measured_vram_bytes` は 33,349,320,704 で、今回の実占有
18,147,024,896 の約 1.84 倍を申告している。これは最大解像度側の envelope で
あり誤りとは限らないが、broker へ GPU のほぼ全量を予約させる値ではある。
`device_mode: cpu_offload` は registry が既に受理する値なので、より大きな
モデルを載せる際の選択肢として使える。ただし wall time / RAM headroom /
swap / Host watchdog を実測するまで available へ昇格させない（H3 と同じ gate）。

## G6 resource turn E2E のログイン失敗を診断可能にした（2026-08-24）

利用者が実行したところ 20 秒の Playwright TimeoutError で止まった。原因は
監査ログで確定した。

```text
SELECT timestamp, action, username, result FROM audit_logs WHERE action LIKE 'login%'
2026-08-24 02:46:42  login  user='mfe2e'  result='failure'
```

**パスワード違い**であって TOTP でも rate limit でもスクリプトの不具合でもなかった。
この環境の TOTP は `totp_requirement=optional` / `require_totp_for_admin=False`
なので、そもそも二要素は要求されない。

問題は、原因が違っても症状が同じになっていたこと。URL の遷移だけを待つと
パスワード違い・rate limit・二要素要求のどれもが同じ 20 秒 timeout と
40 行のトレースバックになり、利用者が原因を知る手段が無かった。

`/auth/login` の応答を直接見て、サーバが実際に言ったことを返すようにした。

```text
401 + detail                  -> ユーザー名とパスワードの確認を促し、
                                 ./deck.sh passwd <user> を案内する
401 + two_factor_required     -> TOTP が有効である旨と reset-totp を案内する
429                           -> 5 回/分・20 回/分の制限と待ち時間を案内する
200 だが遷移しない            -> 現在の URL を出す
```

実測（誤ったパスワードで意図的に失敗させた）:

```text
FAILED: ログインに失敗しました（HTTP 401: ユーザー名またはパスワードが正しくありません）。
        ユーザー名 mfe2e とパスワードを確認してください。
        パスワードを設定し直すには ./deck.sh passwd <user> を使います。
```

40 行のトレースバック / 20 秒 -> 1 行 / 6 秒。

なお、この環境には既に `mf-e2e`（ハイフン入り）という E2E 用アカウントがあり、
2026-08-23 の CI-6 実行で繰り返し成功している。新規作成は不要だった。

## G4H A1 — AssetBrief と決定的な出力幾何（2026-08-24）

実使用（OpenCode の Hanabi プロジェクト）で報告された「wide landscape と要求
したのに 1024x1024 が生成された」を、実物と記録から追って直した。

### 実物で確認した欠陥

```text
/data1tb/ControlDeck/CodeDEV/Hanabi/assets/keyart/
  background-keyart.png   1024x1024  RGBA  1,296,977 bytes
  fireworks-keyart.png    1024x1024  RGBA  1,977,542 bytes
```

provenance を追うと、要求は次の形だった。

```text
constraints    {}            <- 寸法がひとつも渡されていない
model_policy   quality       <- agent が方針まで選んでいる
intent         "... wide landscape composition ..."  <- 散文の中だけ
validation     image.dimensions passed (1024x1024)   <- 寸法の存在は見るが用途は見ない
```

生成側の既定は `worker_packs/image/worker.py` の
`width_default = 1024` で、**stack の最下層**にある。ここは用途を知らない。

消費側の実害も確認した。

```text
index.html   #title-bg   object-fit: cover
-> 正方形を横長の面へ cover するため上下が切られる
-> 「上 2/3 の空を開ける」「下端に観客のシルエット」という指示どおりに
   構図された部分が、まさに切り落とされる
```

もう 1 件、報告に無かった欠陥を実物から見つけた。

```text
fireworks-keyart.png は #title-fw として背景の上に 300px で重ねられている
alpha min=255 max=255  半透明以下の画素 0/1,048,576 (0.00%)
-> 透過が要件のはずの重ね要素が、独自の夜空と観客を持つ不透明な完成シーン
-> 背景と内容が重複し、drop-shadow は花火ではなく四角い箱の縁に付く
```

### 対応

用途から幾何を**生成前に決定的に**解決する層を入れた（`asset_brief.py`）。

```text
AssetBrief          role / aspect_intent / target_dimensions / safe_areas /
                    alpha_intent / consistency_group / hard_constraints
                    provider・model・sampler・prompt の欄を持たない
resolve_layout      優先順位は
                      request の明示寸法
                      > brief の明示寸法
                      > brief の aspect 指定
                      > role 既定
                      > 従来どおり（何も推論しない）
                    envelope（multiple_of / min / max / max_pixels）へ必ず収める
infer_brief_from_intent
                    既存の散文から構造語だけを決定的に拾う。AI 呼び出し 0 回。
                    確信が持てなければ何も推論せず従来の挙動を変えない。
```

公開契約は変えていない。brief は既に自由形の `JobRequest.constraints` に載る。

### 実測（当時と同じ形で再実行）

```text
background    1024x576  16:9  source=brief.aspect_intent   （当時 1024x1024）
fireworks     1024x576  16:9  source=role_default          （当時 1024x1024）
明示 1024x1024 1024x1024       source=request.constraints   （推論は明示を上書きしない）
AI 呼び出し    0 回
```

### AI Director を要求変換に挟む案（利用者提案 2026-08-24）

**採用しない。** 実測に基づく理由を `g4-agent-asset-workflow-hardening.md` §3.2b
へ記録した。LLM 31.5GB と FLUX 18.1GB は 34.2GB の GPU で共存できず、AI を
挟むたびにモデルのスワップが要る。実測でスワップ 1 往復は 15〜25 秒
（LLM load 4.0〜12.1 秒 / release 0.146〜0.371 秒 / FLUX load 10.6〜14.9 秒）。
全生成の前段に置くとこれを毎回払う。Director は既に `text.generate` を持って
おり、二つ目の AI 層にもなる。

決定的抽出で報告された欠陥は解消したため、Director への相乗り（tier 2）は
A3 へ送り、本スライスでは実装しない。

```text
./mf.sh test   451 passed（従来 412 + A1 39）
```

NOT TESTED: 解決後の寸法での実画像生成、および透過が必要な emblem 用途の
実生成。A3 / A5 で実機確認する。

## G4H A1b — defect と finding の分離（2026-08-24）

利用者の指摘「予算を制限する場合、必要な生成が行われない可能性はないか」への
対応。あり得るため、規則を明示して実体化した。

```text
予算は「任意の改善」を縛る
予算は「必要な修正」を縛らない
予算切れは報告する。黙って成功にしない
```

二つの階層を型で分けた。

```text
BriefDefect   用途に対して客観的に誤っている
              canvas 不一致 / 必須 alpha の欠落 / 想定外の透過
              -> 予算に関係なく修正するか、理由を名指しで失敗する
finding       評価器の主観的な判断（A3 で実装）
              -> QA 予算で縛る。予算切れは未解決事項を添えて返す
```

最良の守りは検査ではなく予防である。A1 で canvas を構造的に解決したため、
寸法不一致は「検出して作り直す」対象ではなくなった。予防は swap 0 回、
作り直しは 1 往復まるごと（実測 15〜25 秒）。

### validator の主張を正直にした

`validate_png` は `{"validator": "image.alpha", "alpha": true}` を返していたが、
これは「mode が RGBA である」という意味でしかなかった。Hanabi の花火キーアートは
完全不透明のままこの検査を通過していた。実際の最小 alpha を見るようにした。

```text
before  {"validator": "image.alpha", "status": "passed", "alpha": true}
after   {"validator": "image.alpha", "status": "passed",
         "mode_has_alpha_channel": true, "has_transparency": false, "minimum_alpha": 255}
```

### 実物での検出確認

```text
background-keyart.png  実物 1024x1024 透過=False  要求 1024x576
  DEFECT canvas_mismatch  expected=1024x576  actual=1024x1024
fireworks-keyart.png   実物 1024x1024 透過=False  要求 透過必須
  DEFECT alpha_missing    expected=alpha channel with transparent regions  actual=fully opaque
```

alpha は required / forbidden / auto の三状態を保つ。bool へ潰すと「不要」と
「禁止」が混ざり、片方が誤って defect になる。

```text
./mf.sh test   458 passed
```

NOT TESTED: defect 検出後の自動再生成（A3 の範囲。現時点では理由を名指しして失敗する）。

## G4H — 資産生成の手順設計（2026-08-24）

利用者提案「画像以外を全部実装してから資産をまとめて生成し、VLM で確認して
コード修正か再生成をまとめる。逆も」を評価し、`g4-agent-asset-workflow-hardening.md`
§6.8 に決定を記録した。

```text
採用    コード先行。Hanabi では必要な事実が既に CSS にあった
          #title-bg object-fit: cover        -> 面は横長。正方形は切られる
          #title-fw width: min(52vw, 300px)  -> 小さな重ね要素であって完成シーンではない
                    filter: drop-shadow(...) -> 形のある被写体を期待する = 透過が要る
        brief を「推測」から「実測」に変えられる

不採用  検査前に全部まとめて生成する形。画風が外れると N 枚無駄になる
        代わりに anchor 1 枚を先に作って確認する。同じ FLUX 常駐の中で
        行うので追加 swap は 0

不採用  資産を先に作ってからコードを書く順序
        brief が測る対象を持たず、形容詞へ退行する。Hanabi の失敗の再現になる

採用    「画像ではなくコードを直す」判断はしばしば正しく、再生成より安い
        ただし Media Forge は project source を書き換えない。不一致と
        どちら側で解決できるかを報告し、決めて直すのは coding agent
```

結果として swap は資産数によらず 2 回のまま。

## G4H A1c/A2 — 複数枚生成と agent への指針（2026-08-24）

### 複数枚生成での defect の扱い（利用者指摘）

「生成枚数は 1 枚だけじゃない場合も適用しているか」という指摘で、扱いの誤りを
見つけた。`_validate_output` は候補ごとに走るが、最初の defect で全体を失敗させて
いた。4 枚頼まれて 1 枚の alpha が欠けただけで、良い 3 枚まで捨てることになる。

```text
修正前   候補 1 枚の defect -> job 全体が失敗
修正後   defect のある候補だけを落とす
         残りが 0 なら理由を名指しで失敗する（黙って返さない）
         落とした事実は warnings に残す
```

幾何は job 単位で 1 度だけ解決されるので、`output.count` が何枚でも全候補が
同じ面に収まる（テストで固定）。

### A2 — agent へ届く指針

指針が確実に届く経路は **JSON Schema の `description`** である。どの agent
harness でも提示されるため、OpenCode 専用の分岐を作らずに済む。
`addon.json` の contribution 形は変えていない。

`schemas/job-request.json` へ加法的に追記した。

```text
top level          用途を伝える。provider 向けの prompt を書かない。model を名指さない
intent             構造要件は asset_brief へ。実使用で "wide landscape" が
                   この欄にしか無く、正方形が返った事実を明記
constraints        明示 width/height は常に推論に勝つ
constraints.asset_brief   role / aspect / safe_areas / alpha / consistency_group
                          role ごとの既定（emblem・sprite は alpha 必須、
                          background は横長・不透明）を説明文に書いた
model_policy       auto のままにする。quality / low_vram は必要なときだけ
qa                 既定のまま。semantic=true は model swap を伴う。
                   予算は主観的な再試行だけを縛り、brief への客観的な不一致は
                   予算に関係なく修正または報告される
examples           Hanabi の 2 資産（背景と emblem）を正しい形で載せた
```

`schemas/project-asset-placement.json` へは grant のタイミングを書いた。

```text
grant は配置の直前に取る。生成の前に取らない（生成は数十秒かかり期限切れになる）
期限切れなら新しい grant を取り直して 1 度だけ再試行する
Media Forge は path を受け取らない
```

例が古びて嘘になるのを防ぐため、schema の `examples` が自分自身の schema を
通ること、かつ実サービスが 202 で受理することをテストで固定した。

```text
./mf.sh test   468 passed
```

NOT TESTED: 実 agent harness（OpenCode / Codex）がこの description を提示して
実際に purpose-level 要求を出すか。A5 の実機 E2E で確認する。

## G4H A3 — 用途に応じた評価（2026-08-24）

Hanabi の背景は単体では美しく、実際に prompt どおりに構図されていた。使えな
かったのは面の比が違ったからで、それは主観の問題ではない。「良い画像か」と
訊いていたら yes と答えていたはずである。

評価を「綺麗か」から「その用途に使えるか」へ変えた。既存の Unified Evaluator と
canonical `EvaluationResult` をそのまま使い、別系統は作っていない。

```text
brief_dimensions   用途が要求する観点だけを選ぶ
                     background          composition / palette
                     character_portrait  subject_identity / composition
                     sprite              subject_identity
                     texture             style
                     safe_areas あり     composition を追加
                     general             追加なし
brief_rubric       その用途で「使える」とは何かを評価器へ渡す
                     background  上に描かれる。UI や文字の背後で読めるか。
                                 支えるのではなく主張しすぎていないか
                     emblem      独立した紋章として読めるか。背景と重複する
                                 完成シーンになっていないか
                     safe_areas  「上 40% は title and menu のために空けること。
                                 被写体が侵入していないか報告せよ」
                     hard        「no text in the image」等をそのまま渡す
```

寸法・alpha・形式は決定的に解決済みなので、評価器には
「canvas は 1024x576 (16:9) で確定済み。寸法や形式について述べるな」と明示する。
VLM に蒸し返させない。

brief を渡さない既存の呼び出しでは観点の選び方が一切変わらないことをテストで
固定した。

### 予算切れの扱いを実装に合わせて訂正した

計画 §6.7 に「予算切れは最良候補を返す」と書いていたが、実装は
`semantic_review_exhausted` で job を失敗させる。確認した結果、実装の側が
正しい。`qa.semantic=true` と retry 予算は、呼び出し側が「不適合なら拒否せよ」と
明示的に頼んでいる状態であり、拒否された候補を黙って返せばそのゲートを
無意味にする。§6.7 の要件は「隠さないこと」であって「成功させること」ではない。

既知の代償として記録した: 決定的には妥当な候補も job ごと捨てられるため、
実 GPU 仕事が主観的判断で失われる。失敗した job が資産を持つ形は public な
意味を変えるため、A3 には畳み込まない。

defect の判定が QA 予算をまったく参照しないことも、経路の形でテストに固定した。
参照させた瞬間に、予算を使い切った job が誤った資産を成功として返せるようになる。

```text
./mf.sh test   486 passed
```

NOT TESTED: 実 VLM がこの rubric で用途不一致を実際に指摘するか。A5 の実機
E2E で、Hanabi 相当の資産に対して確認する。

## G4H A4 — 配置マニフェストと受領書（2026-08-24）

実使用では、関連する資産を 1 個ずつ `media.pack` へ渡していた。呼び出し側から
見ると何が配置されたのか応答から確定できず、最後に shell の `ls` / `file` で
確かめる必要があった。応答が受領書として不足していたためである。

### 受領書

単体形の応答へ加法的に `receipt` を足した。既存の呼び出し側が読んでいる欄
（`asset_id` / `media_asset_id` / `name` / `mime_type` / `size` / `sha256`）は
そのまま残る。

```text
PlacementReceipt
  committed / source_asset_id / host_asset_id / filename / media_type
  sha256 / size_bytes / width / height / role / warnings / error
```

project の path は入れない。呼び出し側が知るのは「どのバイト列がどの名前で
置かれたか」だけで、project がどこにあるかは知らない。

### 複数件配置

`items[]` 形を追加した。単体形はそのまま維持し、応答の形も呼ばれた形に揃える。

```text
preflight   1 バイトも書く前に全件の宛先名を確定させる
            重複名 / 欠落資産 / 拡張子と MIME の不一致はここで拒否し、
            何も commit しない
書き込み     1 件ずつ commit する。失敗したらそこで止め、残りは
            not_attempted として報告する
応答        committed_count / requested_count / partial / atomic:false
```

**`atomic: false` を明示する。** ControlDeck が原子的に扱えるのは 1 ファイルで
あり、N 件をまとめて「全部か無か」と名乗ると、部分的に書かれた状態を呼び出し側が
見落とす。Host に汎用 transaction primitive が入るまでこの表現は変えない
（計画 §8.3 / H3）。

### 実測

```text
3 件一括           committed_count 3 / partial false / 各 receipt の
                   sha256・size・width・height が元資産と一致
重複名             422 duplicate_placement_filename / outputs 0 件
                   （大文字小文字を畳んで比較する）
欠落資産           404 asset_not_found / outputs 0 件
同一資産の二重指定  422 invalid_project_asset_placement
受領書の path 漏れ  なし
./mf.sh test       492 passed
```

NOT TESTED: 途中失敗して `partial: true` になる経路。stub host が commit を
失敗させないため、実機 E2E（A5）で確認する。

## UX3 — シーン/見せ方カタログの汎用化と設定の重複解消（2026-08-24）

### カタログがキャラクター中心だった

利用者指摘「シーンと構図が一般的ではない」。実際、全項目が「人物が何をしているか」
だった。Hanabi のような背景・風景・物・抽象の依頼を表す手段が無く、実使用でも
散文へ逃げていた。

```text
                旧    新
domains          7 ->  16   水彩 / 油彩 / フラット / ドット絵 / 線画 / 3D /
                            コンセプトアート / 浮世絵 / 背景 を追加
scenes           8 ->  34   場所・時間帯・天候を追加（自然 / 街 / 室内 / 夜空 /
                            水辺 / 朝焼け / 夕暮れ / 雨 / 雪 / 霧 / 森 / 山 /
                            砂漠 / 宇宙 / 水中 / 廃墟 / カフェ / 教室 /
                            ファンタジー / SF 都市 / 祭り など）
compositions     8 ->  27   汎用レイアウトを追加（中央 / 三分割 / 左右対称 /
                            上下横の余白 / 広く見渡す / 寄り / 真上から /
                            継ぎ目なし / 斜め / 誘導線 / 額縁 / シルエット /
                            奥行き / パノラマ / アイソメ / 見下ろし / 横スクロール）
cameras          7 ->  16   俯瞰 / 接写 / 遠景 / 傾け / あおり / 望遠圧縮 /
                            広角 / 背景ぼけ / 全面ピント
variations       6 ->   9   配色違い / 光の違い / アングル違い
```

人物を必要としない場面は `compatible_poses` を `auto` だけにして、関係のない
ポーズ選択を出さない。既存 ID は 1 つも削除していない（`poster` /
`character_sheet` は composer が参照している）。

`registry._DOMAINS` に `background` があるのに選ぶ手段が無かったので追加した。

### 詳細モードで同じ設定が 2 箇所に出ていた

利用者指摘「シーンと見せ方と詳細設定で設定内容がかぶる」。実際に重複していた。

```text
簡易 #creative-simple        ドメイン / シーン / ポーズ / 構図 / カメラ / 変化
詳細 #advanced-create        ドメイン / シーン / ポーズ / 構図 / カメラ / 変化
                             （同じ 6 つが再掲され、同じ state を書いていた）
```

同じ設定が 2 箇所にあると、どちらが効いているのか利用者に分からない。

```text
整理後
  選択      「シーンと見せ方」に 1 組だけ置く
  詳細モード 同じ選択を繰り返さず、言葉での補足だけを足す
             （シーン / ポーズ / 構図 / カメラ の詳細 4 欄）
             幅・高さ・出力形式・枚数・モデル方針・参照の役割・QA は従来どおり詳細のみ
```

### 生成画像の書き出し

設計 §F4 保存A で仕様が決まっていて host files bridge も実装済みだったが、
**UI から呼ぶ導線が 1 つも無かった**（`design-workspace-ux.md` §25 が既に指摘済み）。

`assets.export` を実装し、ビューアに「保存」を足した。応答は配置と同じ
`PlacementReceipt` 形で返し、保存したものを `ls` で確かめ直さずに済むようにした。
単体表示ではホストがいないため、その旨を明示して失敗させる（できないことを
できるように見せない）。

### 実測（実ブラウザ）

```text
simple_scene_options        34
simple_composition_options  27
simple_camera_options       16
domain_chips                16
詳細モードでの select 重複    0（旧 advanced-* の 6 つは削除済み）
詳細モードの補足入力          4
page_errors                 []
./mf.sh test                499 passed
```

NOT TESTED: 実 ControlDeck 上での `assets.export` の往復（host bridge の
`host.files.export` 応答形を実機で確認していない）。実機受入で確認する。

## UX3b — シェルの刷新と、実機で見つかった 3 件の不具合（2026-08-24）

利用者が実機（モバイル埋め込み）の画面を提示。表示の問題より先に、動作の
不具合が 2 件見つかった。

### 1. 前回の解析結果が新しい指示の生成に渡っていた

画面では指示が「宇宙戦艦…」なのに「理解した内容」は前回の「ライオンさん」の
ままだった。表示だけの問題ではない。`state.directorPlan` は送信時に
`director_plan` としてそのまま渡るため、**前の解析が別の生成に効いていた**。

`director-mode` の変更時には捨てていたが、指示文の変更時に捨てていなかった。
指示を書き換えたら解析結果ごと捨てるようにした。

### 2. 進捗が 5% から完了へ飛ぶ

backend の phase と progress を追うと原因は明白だった。

```text
generating   0.05
  （ここに GPU の生成全体が入る。実測 load 10.6-14.9 秒 + 生成 1.1-2.2 秒、
    大きい面では最大 208 秒）
postprocess  0.65
```

割合は本当に分からない区間である。嘘の数字を動かす代わりに、
`generating` / `waiting_resource` / `release_ai` は不確定表示にし、
経過時間と実測由来の目安を出すようにした。`prefers-reduced-motion` では
ループさせない。

### 3. タブを移って戻ると進捗が消える

`showProgress` は届いたイベントでしか描かれず、状態から作り直す経路が無かった。
`job.changed` で受け取った最新状態を `state.jobs` に保ち、作る画面へ戻ったとき
`restoreProgressView()` で描き直す。

### シェルの見た目

```text
ナビ      文字だけのタブ -> 線画アイコン + ラベル。現在地は上側の細い印
          （ホストのタブバーと縦に並ぶため、下線だと読みにくい）
設定      絵文字の歯車 -> 線画アイコン。現在地を示すようにした
アイコン  SVG を直接埋め込む。opaque sandbox では外部資産を取りに行けず
          CSP でも止まる。currentColor で塗るので theme.changed に追随する
```

```text
./mf.sh test   515 passed
実ブラウザ      430x860 で描画確認、page errors 0
```

NOT TESTED: 実 ControlDeck 埋め込みでの見え方（ホストのタブバーとの重なり）。

## SD 系共通 adapter と、配布元の検索カタログ（2026-08-24）

### 系統ごとの薄い adapter（利用者質問への実装での回答）

「Flux 系と Stable Diffusion 系で個別のローダー開発が必要か」への回答を実装で示した。
**要るが、モデルごとに 1 から書くのではなく系統ごとの薄い adapter である。**

```text
worker_packs/image/adapters/
  base.py            ImageAdapter Protocol（generate / edit）
  diffusers_flux2.py FLUX.2 用。pipeline class と参照編集の意味論が固有
  diffusers_sd.py    SD 1.5 / SDXL / SD 3 共通（新規）
  native.py          Diffusers を使えない runtime 用の口（未実装）
```

SD 系が 1 個で足りるのは、Diffusers の `AutoPipelineForText2Image` が
pipeline class の解決を既に引き受けているためである。実際に系統固有なのは
次の 4 点だけだった。

```text
どの pipeline class を作るか        AutoPipeline が config から解決する
この機材での dtype と offload 方針   SD 系は fp16。bf16 の FLUX とは別
generate / img2img / inpaint の対応  1 つの Protocol へ寄せる
negative prompt と guidance          FLUX.2 Klein は取らない
```

worker は `runtime_adapter` の名前で adapter を選ぶ。表は module 属性名を持ち、
import 時にクラスを固めない（固めると試験が差し替えた偽 adapter が使われない）。

`trust_remote_code` は明示的に `False` にしている。取り込んだ重みが任意の
コードを持ち込める経路を開かない。

`edit` は実装せず `NotImplementedError` で落とす。strict inpaint には
protected-pixel 保証、outpaint には別の不変条件があり、実測していない経路が
それらを名乗るのは、無いことより悪い。

**実測していないため、この adapter を使う catalog エントリは `experimental` の
ままである。** 実機での測定は別スライス。

### 配布元の検索

repository ID の手入力だけでは、名前を既に知っている人にしか使えなかった。
検索を足した。

```text
models.custom.search
  query / sort / pipeline_tag / limit
  sort は downloads / likes / lastModified / createdAt
  未知の並び順は黙って別の順で返さず拒否する
    （黙って返すと、並べ替えたつもりのまま誤った表を読むことになる）
  library=diffusers と使える pipeline に限って問い合わせる
    （取り込めない形式ばかり並べても選べない）
  壊れた要素は飛ばし、検索全体を失敗させない
  導入済みは already_added として印を付ける
```

UI は表で出す。数値は等幅で縦に揃える（桁が揃わない表は比較に使えない）。
**表から直接は取り込まない。** 「中身を見る」は既存の resolve へ渡し、
版の固定・digest・ライセンス明示承諾を必ず通る。

実 API 実測（`stable diffusion` で検索）:

```text
sort=downloads    1,605,410 DL  stabilityai/stable-diffusion-xl-base-1.0
                  1,440,259 DL  stable-diffusion-v1-5/stable-diffusion-v1-5
sort=likes        8,068 ★      stabilityai/stable-diffusion-xl-base-1.0
                  7,054 ★      CompVis/stable-diffusion-v1-4
sort=lastModified 2026-08-24    pruna-test/test-save-tiny-stable-diffusion-pipe-smashed
```

```text
./mf.sh test   529 passed
実ブラウザ      表 3 行を描画、page errors 0
```

NOT TESTED: SD adapter による実生成。実機測定まで `experimental` を維持する。
LoRA は利用者指示どおり後続の計画とする。

## UX4 — 導入済みモデルを見比べられる表（2026-08-24）

モデル管理はカードだけだった。カードは 1 件ずつの説明には向くが、容量・状態・
VRAM を縦に揃えられないため、「どれを消すか」「どれが使えるか」を決める用途に
使えない。検索結果と同じ表の言葉づかいに揃えた。

```text
列        モデル / 状態 / 採用 / 容量 / VRAM / ライセンス / 操作
既定       表（見比べる用途が多い）。カードは切り替えで残す
数値       等幅で縦に揃える
操作       表とカードで同じ（ダウンロード / 削除 / 実機で評価 / 中止）
保持       model_layout として preferences に置く。ブラウザ保存領域は使わない
```

実ブラウザ実測:

```text
layout chips     ['表', 'カード']
既定             table 表示 / cards 非表示
行数             13（同梱カタログ全件）
切り替え後        table 非表示 / cards 表示
page errors      []
```

FLUX.2 Klein 4B が「導入済み / available / 約 14.9 GB / VRAM 31.1 GB」、
それ以外が「未導入 / 実験的・未実測 / 未計測」と一目で分かる形になった。

```text
./mf.sh test   532 passed
```

## UX5 — この機材で動くかを表に出す / ダウンロードの行き先（2026-08-24）

### 実行可否

容量とライセンスが並んでいても「これは動くのか」は分からなかった。判定できる
材料は既にあった（各モデルの実測 VRAM と、この機材の VRAM 量）が、後者が
どこにも出ていなかった。

```text
環境スナップショット   _verify_gpu は total_memory_bytes を既に取得していたのに
                       文章の中にしか入れていなかった。gpu_memory として数値で出す
capabilities           device.vram_bytes として UI へ届ける
                       取れないときは 0。推測しない
```

判定は 4 段階にした。

```text
実行可能        実測 VRAM <= この機材の VRAM
オフロード前提   実測 VRAM が上回るが、CPU オフロードで動く見込みの範囲
未計測          実測が無い。分からないものは分からないと出す
起動不可        明らかに載らない、または capability を持たない
```

**実測していないものを「動く」とは言わない。** 未計測は未計測のまま出し、
重みの大きさは目安にしかならないので、明らかに載らない場合だけ起動不可とする。
CPU オフロードは動くが遅くなる選択肢なので、実行可能とは分けて出す。

並び順に「この機材で動く順」を足した（同順位なら実測 VRAM の小さい順）。

実ブラウザ実測（VRAM 34,208,743,424 バイトとして）:

```text
実行可能  1 件   FLUX.2 Klein 4B（実測 31.1 GB）
未計測    9 件
起動不可  3 件   MiniMax H3 系（117-134 GB）
page errors 0
```

### ダウンロードの行き先

ダウンロードは数十 GB かかることがあり、押したあとの行き先が無かった。
進行中・完了・失敗を 1 か所にまとめ、進行中があれば自動で開く。
終わったものも残す（何が落ちたのかを後から確かめられないと、やり直して
よいのかが分からない）。

```text
./mf.sh test   537 passed
```

NOT TESTED: 実機での `gpu_memory` 出力（provision を再実行するまで既存の
environment-status.json には現れない）。実機受入で確認する。

## UX6 — 実機フィードバックによるモバイル最適化（2026-08-24）

LAN プレビューを実機（iPhone）で確認してもらい、指摘を反映した。

### ダイアログの入力に指が届かなかった

利用者から「タップしても入力できない。モックサーバの仕様か」と質問。
**モックの仕様ではなく CSS の不具合だった。** 決めつけずに調べて正解だった。

```text
dialog { max-height: 82vh }   高さは切っていた
                              overflow-y が無く、はみ出した部分へ到達できない
```

キャラ登録の名前欄は上部にあり、画面外へ出たまま送れなかった。
`overflow-y: auto` を入れ、モバイルでは下からのシートにした（中央寄せの小窓は
ソフトキーボードが出ると入力欄ごと隠れる）。実機幅 390px で名前・見た目の
両方に入力できることを確認した。

### カードと表で出す情報が食い違っていた

同じモデルなのに、カードは 5 つのタグ、表は 2 つしか出していなかった。
表示が 2 つあると、片方だけ直る。**表に統一し、カードと切替を削除した**
（利用者指示）。死んだカード描画 4,480 文字も除去した。

### 「CLI で管理」が何を指すか分からなかった

説明のない専門用語だった。何ができないのかを言うようにした。

```text
before  CLI で管理
after   操作できません（+ この表示では追加・削除ができない旨を title と見出しに）
```

### モバイルで必要な情報が画面外に出ていた

横に伸びる表では、容量・VRAM・操作が右へはみ出して読めなかった。モバイルでは
1 行を積み上げ、各セルに列名を添える（積んだ途端に「14.9 GB」が何の数字か
分からなくなるため）。

```text
実測（390px）  page_overflow_px 0 / table_overflow_px 0
               モデル・この機材・状態・採用・容量・VRAM・ライセンス・操作の
               8 項目すべてが横スクロールなしで可視
```

### 「用途」は選ぶ基準になっていなかった

利用者指摘「用途って何？不要ではない？」。そのとおりだった。
`text-to-image` / `image-to-image` は配布元の技術的分類で、SD 系はほぼ全部が
text-to-image のため絞り込みの役に立たない。実際に決めているのは
「どんな絵を作るモデルか」なので、配布元のタグで画風を選べるようにした。

```text
実 API 実測
  anime      -> Lykon/dreamshaper-7, John6666/nova-furry-xl-il-v120-sdxl
  pixel-art  -> Limbicnation/pixel-art-lora, adirik/pixel-art-lora-flux.2-klein-4B
  realistic  -> John6666/diving-illustrious-real-asian-v50-sdxl
```

### その他

```text
参照の選択    「最大 4 枚」と書きながら選択状態が見えなかった。選択中の枚数を
              出し、上限に達したら選べない枠を淡くする
並び順        ダウンロードの状況と repository 直指定を、使用頻度の低い順に下げた
歯車          もう一度押すと閉じ、設定の前にいた画面へ戻る
```

```text
./mf.sh test   539 passed
```

## UX7 — 実機での作り込み（2026-08-24）

LAN プレビューを見ながら、指摘のたびに直した。以下はすべて実機の指摘由来。

### 撤去したもの

```text
「この拡張機能について」以下   静的な説明文と診断表示。毎回読む価値がないのに
                              毎回場所を取っていた
repository の直接指定          検索が入ったことで使われない。検索に出てこない版が
                              要る場合は CLI から入れる
モデルのカード表示             表と出すタグが食い違っていた。表示が 2 つあると
                              片方だけ直る。表に統一した
詳細設定の幅・高さ             上の「サイズ」と重複し、しかも詳細側が上書きして
                              いた。どちらが効くのか分からない状態だった
```

### 直した不具合

```text
検索が動かない       単体表示に検索経路が無かった。配布元の検索はホストを
                     必要としないので /workspace-api/models/search を足した
導入・削除が出ない   単体表示の shim が management_available を false に固定して
                     いた。ローカルのモデル管理もホストを必要としないので、
                     実際に設定されているものを返すようにした
検索結果の表が崩れる  セルに列名が無く、積み上げると数字だけが裸で並んでいた
2 列が 13 列になる    auto-fill に minmax(0, ...) を渡すと列が無限に増える。
                     最小幅は実数で与え、はみ出しは子の min-width: 0 で防ぐ
横あふれ 76px        td.name に後から display:block を当てており、潰せる指定が
                     効いていなかった。長いモデル名が枠を押し広げていた
カードがガタつく      align-items: start で名前が 2 行の側だけ伸びていた。
                     stretch にし、操作を margin-top: auto で下端へ揃え、
                     名前に 2 行ぶんの場所を先に取る
```

### 実測（390px）

```text
横あふれ            0
列数                2
同じ行の高さ不一致   0
操作ボタン          ダウンロード / 共有モデル / 外部ランタイムで導入 / 32GB上限対象
検索                anime で 3 件（実 API）
./mf.sh test        547 passed
```

## G4H A5 — coding agent から build/test までの実機受け入れ（2026-08-25）

`scripts/a5_agent_asset_path_e2e.py` が経路全体を 1 回で通す。実物は GPU・
モデル・生成された画素・プロジェクト・その build と test。stub は ControlDeck
の grant 配管だけで、commit されたバイトは実プロジェクトへ書く（メモリ内で
済ませると、壊れた配置が誰にも気づかれず通ってしまう）。

```text
project analysis
  -> purpose-level asset request   prompt / model / 画素数を一切書かない
  -> real generation on the GPU
  -> deterministic inspection against the brief
  -> output grant requested late   バイトが在ってから頼む
  -> placement receipt
  -> code updated from the receipt 推測したパスではなく受領書の名前と digest
  -> build
  -> test
```

実測（2026-08-25、AMD Radeon AI PRO R9700）:

```text
agent が出した brief   role=background surface=game aspect_intent=landscape
                      hard_constraints=["no text in the image"]
                      safe_areas=[top 35% title and menu]
Media Forge が決めた   1024x576（landscape を用途から解決）
routing               black-forest-labs/FLUX.2-klein-4B（agent は指定していない）
生成                   28.05 秒 / 730,468 bytes
受領書                 committed=true sha256 が検査済み資産と一致
project への commit    title-background.png 730,468 bytes
build / test          0 / 0（3 passed）
./mf.sh test          588 passed
```

### 実機でしか出なかったこと — 宣言された必須条件が検査されていない

初回実行は緑で通ったが、生成物には文字が入っていた。`hard_constraints` に
`"no text in the image"` を宣言していたにもかかわらずである。

`hard_constraints` は評価器の rubric にしか渡っておらず、評価器は既定で回さ
ない。回さないこと自体は意図した設計で、必須条件のために毎回 model 載せ替え
を強いるのは高すぎる。問題は `warnings: []` を返していたことで、これは「確か
めた、問題なかった」と読める。決定的検査が見ているのは幾何・mode・alpha まで
で、絵の中身は読んでいない。

確かめていないものは、確かめていないと言う。評価器は既定のまま回さず、
warnings に未検査の必須条件を名指しで残す。

```text
before  warnings: []
after   warnings: ["以下は宣言された必須条件ですが、この実行では検査して
                   いません（qa.semantic を有効にすると検査します）:
                   no text in the image"]
```

NOT TESTED: OpenCode の UI から人手で駆動した経路。ここでは coding agent の
役を script が演じている。OpenCode 固有の部分（session、tool 呼び出しの形）は
未検証で、Media Forge 側の入口は同じ `/addon/v1/agent/pack` を使っている。

## 導入済み画像モデルの一括検証（2026-08-25）

`scripts/verify_installed_models.py` が、導入済みの画像モデルを 1 つずつ実際に
走らせて確かめる。カタログが並べている 55 の pipeline クラスは「ランタイムが
構築できる形式」であって「全部この機材で動く」ではない。後者を証明するには
55 個落とすことになるので、証明できるのは手元にあるものだけである。

未実測なら測って昇格し、実測済みでも 1 回走らせる。数か月前に測ったモデルが
ランタイム更新で壊れても、走らせなければ誰も気づかないためである。画像ワーカー
の経路でないモデル（GGUF 動画系）は、黙って省かず「対象外」として並べる。省くと
報告が「全部通った」に見える。

実測（2026-08-25、AMD Radeon AI PRO R9700 / 512x512 / 8 steps）:

```text
black-forest-labs/FLUX.2-klein-4B     20.7 GB   45.34 秒   333,821 bytes
segmind/SSD-1B                         5.8 GB    6.93 秒   278,849 bytes
stabilityai/stable-diffusion-xl-base    8.5 GB    7.78 秒   411,811 bytes
Wan-AI/Wan2.2-TI2V-5B                 対象外（native.wan2.2）
unsloth/MiniMax-H3-GGUF               対象外（native.stable-diffusion-cpp）

通った 3 / 失敗 0 / 対象外 2
```

NOT TESTED: 落としていない 52 形式。構築できることは runtime の mapping から
分かるが、この機材で動くことは落として走らせるまで分からない。新しく入れたら
このスクリプトを回す。

## モデル本来の設定を、モデル自身から決める（2026-08-25）

SDXL base の生成結果がおかしいという指摘から。実測 3 枚:

```text
1024x1024 / 4 歩   にじんだ壁に robot の破片が浮くだけ   ← 実際の生成経路
512x512  / 8 歩    指示した被写体が存在しない別の絵      ← 検証スクリプト
1024x1024 / 30 歩  指示どおりの写真                     ← SDXL 本来の設定
```

モデルは正常で、流し込んでいた設定が間違っていた。`worker.py` が歩数を一律
`4` に既定していた。4 は FLUX.2 Klein（蒸留済み）の値で、core は歩数を一切
送っていなかったので、SD 系は必ずこの歩数で回っていた。共通の既定は置けない。

寸法は推測しない。`unet.sample_size` × VAE の縮小率が、そのモデルが学習された
寸法である。SDXL / SSD-1B は 128 × 8 = 1024、SD 1.5 は 64 × 8 = 512。55 の形式
のどれでも repository の中身から同じ手順で出るので、形式ごとの表を持たない。

縦横比も同じ考えで揃える。SDXL が公表しているバケット（1024x1024, 1152x896,
1216x832, 1344x768, 1536x640 とその転置）は「64 の倍数で面積が 1024^2 に近い」
ものの集合そのものなので、学習寸法から計算で出る。要求された比を保ったまま、
面積を学習時に合わせる。総画素を増やすと、モデルが見たことのない広さになり
同じ被写体が 2 つ並ぶ。

歩数だけは中身から出ない。scheduler が LCM/TCD なら少歩数だと分かるが、
SDXL Turbo も SDXL Lightning も素の SDXL と同じ pipeline クラスと scheduler を
名乗る。分からないと認めて多い側（30 歩）に倒してある。多い分は時間を損する
だけで絵は出るが、少なすぎると絵が出ない。「評価」で実際の値が分かる。

評価も本来の設定で走らせる。小さく短く測ると速いが、測った値が実使用と別物に
なる。SDXL は 512x512 / 8 歩で 8.45GB と記録されていたが、本来の 1024x1024 /
30 歩では 12.55GB 要る。その差だけ routing が少なく確保していた。実測済みでも
測り直して書き戻すようにした。

`verify_installed_models.py` の "verified" は "generated" に改めた。PNG が
返ったことしか見ていないので、崩れた絵を「通った」と報告していた。

実測（2026-08-25、AMD Radeon AI PRO R9700、いずれも本来の設定）:

```text
black-forest-labs/FLUX.2-klein-4B   1024x1024 /  4 歩  29.9 GB  17.36 秒
segmind/SSD-1B                      1024x1024 / 30 歩  18.9 GB  11.34 秒
stabilityai/stable-diffusion-xl     1024x1024 / 30 歩  12.5 GB  12.76 秒
```

NOT CHECKED: 絵が正しいかどうかは自動では見ていない。上の 3 枚は目視した。

## 自動で決められない設定を、言って選べるようにする（2026-08-25）

寸法と縦横比はモデル自身の config から決まるが、歩数だけは決まらない。
蒸留版（Turbo / Lightning / LCM）は素の親と同じ pipeline クラスと scheduler を
名乗るので、配布物からは見分けられない。多い側（30 歩）に倒してあるが、
Turbo 系にそれを当てると時間を損し、ガイダンス 7.0 のままだと絵が焼ける。

そこで「何が決まっていて、何が決まっていないか」を判定した側が文章にして
返す。`generation_defaults.summary()` が `settled` と `needs_check` を作り、
`/api/v1/models` の `generation` に載る。UI はそれを並べるだけで、判断を
やり直さない。2 か所に分けると片方だけ直る。

詳細設定に出るもの:

* 確認が必要な項目（枠付き）— 項目・現在値・なぜ決められなかったか・どうするか
* 自動で決まった項目（折りたたみ）— 項目・値・何を根拠に決めたか
* プリセット — 判別できなかったときだけ Turbo / Lightning が出る。素のモデルに
  4 歩を勧めると崩れるので、決まっているモデルには出さない
* 歩数とガイダンスの直接入力。既定から変えたときだけ要求に載せる

ガイダンス 0 を通せるようにした。0 は「CFG を使わない」という指示で、Turbo 系は
それを前提に蒸留されている。registry と worker の両方が `0 <` で弾いていたので、
そのモデルを正しく回せなかった。

実測（2026-08-25、導入済み 3 件）:

```text
FLUX.2 Klein   4 歩 declared  確認が必要: なし              プリセット 2
SSD-1B        30 歩 declared  確認が必要: なし              プリセット 2
SDXL base     30 歩 assumed   確認が必要: 歩数・ガイダンス   プリセット 4
```

描画は jsdom に実物の template を載せて確認した。NOT TESTED: 実ブラウザでの
見た目（playwright がこの環境に無い）。

## 配布元として Civitai を選べるようにし、既定にする（2026-08-25）

Hugging Face には diffusers 形式の基盤モデルが並ぶが、実際に絵を作るときに
使われている調整済みのものは Civitai にある。検索できないものは存在しない
のと同じなので、切り替えられるようにし、既定を Civitai にした。

**検索だけ足すと「見つかるが動かない」ものが既定で並ぶ。** Civitai が配るのは
単一の safetensors で、`diffusers.sdxl` は `from_pretrained` でディレクトリを
読む。`diffusers.sdxl-single-file` は models.json に名前だけあって実装が無かった。
単一ファイルの読み込みまで含めて 1 つの作業とした。

系統は safetensors の中身から判定しない。判定には UNet の次元を読むことになり、
Pony や Illustrious のような派生で外す。配布元が `baseModel` として名乗って
いるものを使い、名乗っていなければ取り込まない。

実測して分かったこと:

```text
検索    GET /api/v1/models      認証不要
形式    1 version = 1 .safetensors
系統    version.baseModel が "SD 1.5" / "SDXL 1.0" / "Pony" などを名乗る
digest  file.hashes.SHA256 が付く。手元計算ではなく配布元の公表値を使う
取得    /api/download/models/{versionId} が署名付き URL へ転送する
UA      既定の User-Agent は 403。認証の問題ではないので鍵を求めない
```

Hugging Face の token を Civitai に送らない。他所の資格情報を、要求されても
いない相手に渡すことになる。

実機で通した経路（2026-08-25）:

```text
検索      civitai/4384 DreamShaper 8      SD 1.5   1.99GB
解決      base_model=SD 1.5 → 512x512 / 30 歩、diffusers.sdxl-single-file
取得      2,132,625,894 バイト、sha256 が API の公表値と一致
生成      512x512 / 30 歩 / 60.7 秒 → 指示どおりの絵（目視）
```

やらないこと: LoRA。Civitai の多くは LoRA だが Media Forge に経路が無い。
検索を Checkpoint に絞ってある。NSFW は既定で外す。

## LoRA を使えるようにする（2026-08-25）

LoRA は「モデル」ではない。選んだ checkpoint に載せるもので、単体では絵を
作れない。registry には別の capability（`image.lora`）で載せた。routing は
`capability in item.capabilities` で候補を絞るので、`image.text_to_image` を
求める経路には最初から現れない。旗を立てて後から除外する作りにすると、除外を
書き忘れた経路が 1 つでもあれば LoRA が本体として選ばれる。

### 読み込めるまでに 2 つ詰まった。どちらもエラーからは分からない

**transformers 5 で CLIP のモジュール名が変わっていた。** 今は
`encoder.layers.0.mlp.fc1` で、以前は `text_model.encoder.layers.0.mlp.fc1`
だった。diffusers 0.40 は encoder にモジュール名を訊いて、それを変換済みの
state dict から引いて rank 表を作る。state dict 側には古い接頭辞が残っている
ので全部外れ、空の表を持って `IndexError: list index out of range` で落ちる。
場所も理由も示さないし、LoRA 側は壊れていない（実測: add_detail.safetensors は
text encoder 216 個・UNet 576 個のテンソルを持つ）。読み込んだ encoder の形に
合わせて鍵を書き換える。逆方向には触らないので、古い transformers でも動く。
text encoder 側を捨てて UNet だけ載せる手もあるが、それは黙って別の絵になる。

**SDXL の LoRA は SGM のブロック番号で保存されている。** `load_lora_weights`
は unet の config を `lora_state_dict` に渡して変換している。こちらで state
dict を作るなら同じものを渡す必要があり、渡さないと「該当する層が無い」と
延々並べて落ちる。

**LoRA は選んだモデルとは別の repository に入る。** モデルの境界は
そのモデル 1 つ分に絞ってあるので、同じ境界で見ると必ず外に出る。境界を
広げるのではなく、LoRA 用の根（導入先）を別に渡す。

`peft` をランタイムの依存に追加した。無いと `load_lora_weights` が拒む。

### 実機で確かめたこと（AMD Radeon AI PRO R9700）

```text
SD 1.5   midjourneyanime を DreamShaper 8（単一ファイル）に  絵が変わった
SDXL 1.0 Detail Tweaker XL を SDXL base（ディレクトリ）に      絵が変わった
```

adapter の経路が別なので、両方通して初めて「LoRA が動く」と言える。同じ seed
で前後を並べて目視した。

Civitai の一部の LoRA は 401 を返す（早期公開など）。鍵が要る配布物なので、
そう伝える。UA 不足の 403 とは別の理由である。

### 土台は同じ操作で自動解決する（2026-08-27 更新）

LoRA は 40MB 前後だが土台は 2〜7GB ある。取り込む前に、載せる先が手元に
あるかを調べる。無ければその系統の checkpoint を依存として解決し、LoRA と
合わせた容量・双方のライセンスを 1 回の確認にまとめる。利用者が土台を選ぶ、
別のチェックを入れる、別のダウンロードを押す、という操作は要求しない。

登録は LoRA と土台を 1 回の durable 更新で行い、ダウンロードも同じ要求から
開始する。生成時は LoRA の系統で routing 候補を絞る。UI の手動モデル選択に
互換性判定を委ねない。

### UI

* 検索行に種別（モデル本体 / LoRA）。Hugging Face には LoRA の経路が無いので、
  そちらを選んだときは種別を出さない
* 結果に系統と起動語。系統は詳細情報であり、土台を選ばせる操作にはしない
* 生成画面に LoRA の選択と強さ（0〜2、4 個まで）。最初に選んだ LoRA と同じ
  系統だけを追加選択でき、土台は自動 routing する
* モデルの選択肢から LoRA を除く。混ぜると、選んでから断られる

起動語は prompt に自動で足す。足したことは job に残る。既に入っている語は
足さない（二重に入れても効きは強くならず、他の語の重みが薄まる）。

やらないこと: LoRA の学習。動画モデルへの適用（経路が別で未計測）。

## 署名した通りのバイト列を配る（2026-08-25）

v0.9.0 の導入が「信頼できる publisher の鍵に一致しない」で拒まれた。署名も
鍵も正しく、canonical なバイト列に対しては検証が通る。原因は配っている
ファイルの方で、末尾に改行を 1 つ足していた。

署名は改行の無いバイト列に付いている。ControlDeck 側が受け取ったバイト列から
改行を落としてくれている間は通っていたが、検証を厳格化してその処理が無く
なった途端に、正しい署名が拒まれた。落としてもらう前提で配っていたのが
間違いである。配るものと署名したものを同じにする。

v0.7.3 と v0.8.0 も同じ形で配ってある。既に導入済みで、downgrade は拒まれる
ので影響は無いが、それらを今から検証し直すことはできない。

## G7 V0 — additive video contract と FFmpeg 正規化境界（2026-08-26）

G7 を `docs/implementation/g7-video-runtime.md` の V0〜V4 に分けた。V0 はモデルを
動かさず、既存の汎用 `video.generate` / `video.edit` 設計を公開 JobRequest へ加法的に
載せ、生成物を公開する前の決定的 FFmpeg 境界を worker pack に置くスライスである。

契約:

```text
video.generate inputs 0 / 1 / 2..8   T2V / I2V / multi-keyframe の将来 routing
video.edit     inputs 1..8            入力なしと 9 件以上を ingress で拒否
output                                mp4 / webm のみ
Asset MIME                            video/mp4 / video/webm を加法追加
Asset metadata                        duration_sec / frame_rate を任意追加
capability                            unavailable / planned_for_g7 を維持
runtime 未実測 job                    capability_unavailable で fail-closed
```

FFmpeg worker 境界は配列 subprocess、timeout、1 video stream、偶数寸法、fps 1..120、
尺 300 秒以下を強制する。MP4 は H.264/AAC、WebM は VP9/Opus。ffprobe で codec、
container、寸法、fps、frame count、audio を再検証し、失敗時は partial output を消す。

実ファイルでの単体実測（Ubuntu system FFmpeg 6.1.1、保存先
`/data1tb/mediaforge-g7-v0-evidence/2026-08-26/`）:

```text
source.mkv       160x90 / 24fps / 2秒 / video+audio   251,768 bytes
normalized.mp4   128x72 / 12fps / 1.25秒 / 15 frames / H.264 / audioなし
                 0.07秒、max RSS 61,564 KiB、6,259 bytes
                 sha256 45052db72a23d29525aecb028a84056e27a61a9044b46a045999f33d4e755daf
normalized.webm   96x64 / 24fps / 0.508秒 / 12 frames / VP9 / Opus audio
                 0.09秒、max RSS 72,752 KiB、18,194 bytes
                 sha256 6a8495a0033d2f67c63aecee0d19beb20a4185480a5cfeb1055aca75bf081ed5
GPU               use 0%、KFD process 0、R9700 VRAM used 59,912,192 bytes
```

branch core を `127.0.0.1:9160` で実起動し、実 HTTP でも確認した。

```text
POST /api/v1/jobs video.generate/mp4
  202 Location /api/v1/jobs/job_a9756b1cd48a4dd0966d7294967d8fc8
GET 同 job
  failed / capability_unavailable / "video.generate has no measured local runtime"
GET /api/v1/capabilities
  video.image_to_video = unavailable / planned_for_g7
installed v0.9.0 GET :9130/health
  healthy / R9700 gfx1201 / torch 2.10.0+rocm7.2.1.gitb07cec22 / HIP 7.2.53211
```

検証:

```text
focused + store + bundle   61 passed
./mf.sh test               683 passed, 1 warning in 50.24s
git diff --check           PASS
compileall                 PASS
```


NOT TESTED: 動画モデルの import/generation/quality、R9700 VRAM、Broker lease/wait/cancel、
LLM 退避/復帰、SonicForge job との同時 admission、installed bundle/browser playback。
V1 の revision-pinned candidate probe と V2〜V4 の範囲であり、video capability は
それらが通るまで unavailable のままにする。release bundle 上の system FFmpeg 検出/
provision も V2 前提として未実施。ControlDeck の変更は 0 件。

実装 PR: Media Forge #119。

## G7 V1 — Wan2.2 TI2V-5B revision-pinned R9700 probe（2026-08-26）

V1 は production video worker を作らず、既存の private Model Management evaluator へ
fixed preset を追加して候補採否を測るスライスとした。公式 model revision は
`921dbaf3f1674a56f47e83fb80a34bac8a8f203e`、weight は 34,201,521,212 bytes、
Wan2.2 source は commit `42bf4cfaa384bc21833865abc2f9e6c0e67233dc`、license は
Apache-2.0。source は unrelated S2V/Animate の eager import だけを除く固定 patch
（diff SHA-256 `4fd9b36b24f3385057445de8551c79b947498f253c061f56a457dc42a21afb93`）を
preflight で検証する。モデル本体の FlashAttention 呼び出しは upstream に既存の PyTorch
SDPA fallback へ置換し、custom kernel は追加していない。

runtime は外部 `/data1tb/mediaforge-g7-v1/runtime` に分離し、torch 2.10.0 / ROCm 7.2.1、
diffusers 0.33.1、transformers 4.51.3 ほかを exact version で構築した。core と image runtime
は共有していない。最初の diffusers 0.40 組合せは Hugging Face Hub dependency bounds が
衝突したため不採用とし、採用した runtime は `pip check` が成功した。UMT5 は meta device
構築、mmap weight、`assign=True` で CPU process に読み、GPU generation process と重ねない。
実 encode は 8.37 秒、max RSS 10,455,924 KiB、process swap 0 だった。

実 ControlDeck の installed iframe から短命 browser identity を取得し、Host Job、Broker
request/activate/renew/release を通して評価した。導入済み manifest は変えず、評価中だけ branch
core を同じ 9130 port / data directory で起動した。テスト account の password hash は実行中だけ
置換し、各 run の `finally` で元の exact hash に復元した。秘密値は証跡・log に出していない。

固定 prompt / seed、guide 5.0 の 512x320 / 17 frames / 30 steps:

```text
cold operation modelop_6a8a15fa02884ec29ad315c3e1d31fab
  elapsed 412.790 sec / peak VRAM 30,612,889,600 B / peak RSS 20,501,524,480 B
  process swap 0 / H.264 24fps / 0.708 sec / 117,318 B

direct-BF16 warm 3 samples
  elapsed                    75.955 / 71.972 / 71.221 sec
  peak VRAM                  30,611,857,408 / 30,612,119,552 / 30,611,984,384 B
  peak RSS                   20,525,383,680 / 19,526,950,912 / 20,201,570,304 B
  process swap               0 / 0 / 0 B
  output                     512x320 / 17 frames / H.264 / 24fps / 0.708 sec / 97,849 B
  SHA-256                    6b0e0d22ea349394cc4436fd84bed19f67b70739ab8aca83b7bd43c2ad9fe90a
```

3 warm sample は同一 hash で、抽出 frame では orange robot、solar panel、landscape を識別でき、
短尺比較候補としての prompt coherence があった。cold 412.790 秒は初回 kernel/cache compile を
含む観測で、warm runtime と混同しない。resource request は最大実測 30,700,000,000 bytes と
1 GiB headroom に更新した。

実用最短を狙った 256x256 / 49 frames / 30 steps は operation
`modelop_73cade3efa7546ad89807e115321a4d3`、Host Job `c59e40978822` で完走した。

```text
elapsed                    235.053 sec
peak VRAM                  20,528,300,032 B（incremental 20,468,387,840 B）
peak RSS / process swap    19,341,029,376 / 1,754,775,552 B
system swap pages delta    in 540,476 / out 539,847
output                     256x256 / 49 frames / H.264 / 24fps / 2.042 sec / 130,960 B
SHA-256                    9b7ec4eca742b20783597803aa94cf2f762d833f9dbc7e1017ac5014e9c9dfd2
```

decode と container は正常だったが、frame 0/24/48 の目視では被写体が崩れ、orange robot / solar
panel / dusk を維持しなかった。さらに process swap が 0 でない。したがって「実用 clip quality /
host RAM safety」は **FAIL** とし、Wan を Available/Recommended/production route に採用しない。
catalog の `measured` は bounded resource envelope の confidence だけを意味し、品質採用ではない。

Broker / cancellation / 共存:

```text
SonicForge/LLM hold 中     30.239 GB request は insufficient_capacity で fail-closed
hold 解放後                同じ browser route が granted、Wan process が開始
cancel                     modelop_65ac98568fa541378a70a38a8e8e6f48
                           VRAM 11,342,323,712 B 時点から 1.007 sec で canceled
                           lease release、Wan process 0、VRAM 59,912,192 B
SonicForge 後続 request    Media Forge release の 0.717 sec 後に activate
completed cleanup          lease 0、Wan process 0、baseline VRAM 59,912,192 B
```

cancel run で最初に prompt embedding が残ることを発見し、terminal state に関係なく削除し、
failed/canceled では partial video/frame/probe も削除するよう修正した。回帰 test を追加した。
評価後は branch core を停止し、installed Media Forge v0.9.0 service を再起動した。実 health は
`healthy`、R9700 gfx1201、torch 2.10.0+rocm7.2.1、HIP 7.2.53211、GPU memory
34,208,743,424 bytes と応答した。ControlDeck の変更は 0 件。

`base-plan.md` §24:

1. T2V/I2V の軽量候補だが、今回証明したのは bounded T2V だけ。
2. isolated Wan runtime と private evaluator が必要。既存 image adapter は使わない。
3. gfx1201 で smoke/短尺/49-frame は完走したが、実用 gate は swap/quality で不合格。
4. 上記に cold/warm、VRAM/RSS/swap/runtime を記録。resource envelope は measured。
5. weight/source は Apache-2.0。
6. 公開 asset/provenance は V2 未実装のため **NOT TESTED**。
7. 17-frame は有望だが、実用 clip は installed alternatives を正当化する品質でない。
8. process group cancel、Host Job、Broker release は実測 PASS。
9. upstream SDPA fallback のみ。custom kernel はない。固定 source patch は evaluator import 用。
10. generic video capability の裏側なので catalog/runtime を削除しても公開 API は変わらない。

判定: runtime/import、bounded short generation、Broker isolation、cancel は **PASS**。実用 clip
品質と zero-swap は **FAIL**。I2V、native 720p、公式既定 121 frames / 50 steps、V0 FFmpeg
normalizer との production 接続、公開 Asset/provenance、installed release bundle の動画再生は
**NOT TESTED**。V1 model adoption は **DEFERRED**。再開条件は、prompt を維持し process swap 0
で完走する実用最短 profile、または別候補の比較結果である。V2 へは昇格させない。

検証:

```text
focused evaluator/catalog    17 passed
./mf.sh test                 686 passed, 1 warning in 48.38s
git diff --check             PASS
compileall                   PASS
```

## G7 V1b — Wan evaluator host-memory lifecycle 比較（2026-08-26）

V1 の 49-frame probe で観測した process swap を、transformer offload と VAE decode に分離した。
upstream `offload_model=True` は denoise 後に約10GBの transformer を CPU へ移してから decode
する。1 job で終了する evaluator は transformer を再利用しないため、同じ offload 境界で
parameter storage を meta tensor 化して GPU storage を破棄し、CPU copy を作らないようにした。
custom kernel、upstream source patch、ControlDeck 変更は追加していない。

実 installed browser identity / Host Job / Broker route:

```text
discard smoke operation     modelop_5b67d9512287455e8919e1aa994a1c62
elapsed                     25.307 sec
peak VRAM / RSS / swap      13,752,025,088 / 19,181,559,808 / 0 B
output                      256x256 / 1 frame / H.264 / 24fps / 2,411 B
SonicForge hold wait        acquiring_resource 35.4 sec、release 後に生成

candidate operation         modelop_2adb1fff80bb4c8397f639c8c9885f0e
profile                     384x256 / 33 frames / 30 steps / guide 5.0
elapsed                     284.677 sec（VAE decode 210.810 sec）
peak VRAM / RSS / swap      14,045,294,592 / 20,670,320,640 / 0 B
system swap pages delta     in 55,845 / out 63,443
output                      H.264 / 24fps / 1.375 sec / 115,130 B
SHA-256                     db3188a464db34aa1a6b5196897061df78e495f6ef56be116d6c323c549f14f5
```

384x256 の frame 0/16/32 は robot / panel / landscape に近い構造を持つが、形状崩れが大きく
採用品質ではない。RAM lifecycle は **PASS**、この profile の実用品質は **FAIL**。

より高解像度の 512x320 / 33 frames は、約30.239GBの SonicForge/LLM residency 中の
operation `modelop_d3703e07a74949dcab9622e8ceb96cf1` と直後の再試行を Broker が
`insufficient_capacity` で fail-closed にした。worker/GPU process は起動せず、test account
hash は復元した。その residency が自然 release した後、同じ profile を2回実行した。

```text
operation                   modelop_389b17382055448f9fc36300599387f2
elapsed                     185.270 sec
peak VRAM / RSS / swap      20,762,644,480 / 17,313,533,952 / 2,501,005,312 B

operation                   modelop_bcc4b8bf3672437e986905bcfc1a3291
elapsed                     129.742 sec
peak VRAM / RSS / swap      25,293,598,720 / 19,265,691,648 / 346,812,416 B

both outputs                512x320 / 33 frames / H.264 / 24fps / 1.375 sec / 143,262 B
both SHA-256                744c4f85f0b52bc29cba9cd4a423e5ac95b93fdf53ec8c9e23e6073907e95d6a
```

frame 0/16/32 は orange robot、前面 solar panel、dusk field を維持し、時間方向も一貫した。
品質と deterministic output は **PASS**。ただし process swap が2回とも0ではなく、改善後も
346,812,416 bytes 残ったため zero-swap / operational reliability は **FAIL** とする。

結論: meta-discard lifecycle と 512x320/33-frame 品質は有望だが、Wan の production adoption は
引き続き **DEFERRED**。別候補またはさらに単純な maintainable lifecycle が prompt coherence と
zero-process-swap を同時に満たすまで V2 へ進まない。評価終了後は branch core を停止し、installed
Media Forge v0.9.0 を再起動した。実 health は `healthy`、contract 2.0、R9700 gfx1201、
torch 2.10.0+rocm7.2.1、HIP 7.2.53211。Wan worker は0、ControlDeck変更は0件。

検証:

```text
focused evaluator/catalog    17 passed
./mf.sh test                 686 passed, 1 warning in 51.30s
git diff --check             PASS
compileall                   PASS
```

## G7 V1c — HunyuanVideo-1.5 weight-free R9700 preflight（2026-08-26）

Wan 512x320 practical profile が prompt quality は通った一方で2回とも process swap を残したため、
別候補を一次資料から比較した。LTX-2.3/2.5 は 22B transformer に別の 12B text encoder を要し、
公式 quick start bundle は約66GiB、low-memory route は FP8/offload 前提である。HunyuanVideo-1.5
は公式に 8.3B、offload 有効時の minimum GPU memory 14GB、480p T2V と Diffusers default
attention route を公開しているため、次の bounded candidate に選んだ。

評価 identity:

```text
official model       tencent/HunyuanVideo-1.5
official revision    9b49404b3f5df2a8f0b31df27a0c7ab872e7b038
Diffusers conversion hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_t2v_distilled
conversion revision  1abb14f06518f37448dcf3a6917dd086dd7045c7
bundle               13 weight files / 53,367,753,676 bytes
all snapshot files   53,384,320,234 bytes
```

core/image/Wan runtime と分離した `/data1tb/mediaforge-g7-hunyuan15/runtime` を exact package
versions で構築した。size は 4,688,976,346 bytes、`pip check` は broken requirements 0。
最終 weight-free preflight は 2.34 秒、max RSS 832,056 KiB、OS swap 0 で完了した。

```text
torch          2.10.0+rocm7.2.1.gitb07cec22 / HIP 7.2.53211
GPU            AMD Radeon AI PRO R9700 / gfx1201
diffusers      0.40.0
transformers   5.15.1
imports        HunyuanVideo15Pipeline / HunyuanVideo15Transformer3DModel /
               AutoencoderKLHunyuanVideo15
attention      PyTorch SDPA default / custom kernel 0
GPU process    preflight 後 0
```

公式 runtime が挙げる Flash Attention、Flex-Block-Attention、SageAttention、SGL-Kernel は
CUDA/H-series向け最適化であり、この probe には入れない。standard PyTorch SDPA で gfx1201 を
先に評価する。

license は Tencent Hunyuan Community License Agreement（HunyuanVideo 1.5 release
2025-11-21）。利用開始が同意となり、EU/UK/South Korea を除く Territory、acceptable-use、
distribution/notice、第三者提供時の表示条件、100M MAU 条件などを含む。conversion repository
の `license: other` 表示だけで単純化しない。利用者の明示同意なしに 53GB weight を取得しない。

判定: isolated runtime build/import、R9700 enumeration、default SDPA は **PASS**。weight download、
hash verification、model load、generation、VRAM/RSS/swap、quality、cancel、Broker、installed browser は
**NOT TESTED**。次の操作は license acceptance 後の bounded sequential download であり、現在は
**BLOCKED PENDING LICENSE ACCEPTANCE**。ControlDeck 変更は0件。

最終 gate:

```text
dedicated pip check        broken requirements 0
weight-free preflight      PASS / 2.34 s / max RSS 832,056 KiB / OS swap 0
installed /health          healthy / contract 2.0
ROCm process cleanup       KFD process 0
full                       686 passed / 2 warnings / 51.28 s
git diff --check           PASS
compileall                 PASS
```

## G7 V1d — Hunyuan license-gated evaluator preparation（2026-08-26）

V1c merge 後も weight / partial snapshot 0 を維持したまま、同意後の実測で使う private evaluator
runner と core admission 経路を実装した。公式推奨では 480p T2V CFG-distilled は 50 steps が必要で、
8/12 steps は 480p I2V step-distilled 向けであるため、T2V quality preset を短縮推測値へ置換しない。

runner invariant:

```text
model identity       tencent/HunyuanVideo-1.5@9b49404b
conversion identity  hunyuanvideo-community/...480p_t2v_distilled@1abb14f0
snapshot ingress     local path only / exact revision / HF cache containment
network              local_files_only / HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE
runtime              dedicated Python / torch BF16 / model CPU offload / VAE tiling
attention            PyTorch SDPA / custom kernel 0
input                 fixed prompt / negative prompt / seed 260826 / fixed presets
artifact              H.264 yuv420p MP4 / exact dimensions, fps, frame count
failure               partial MP4 and temporary frame directory cleanup
```

core へ optional runtime/snapshot/preset 設定を追加した。両 path と revision containment が通らない
限り model evaluation control に現れない。設定後の操作も既存 Host Job → Broker queue/lease/renew/
cancel/release → process-group metrics → ffprobe validation を通す。実測前の request は
`execution_peak=30,700,000,000`、`cold_load_peak=32,000,000,000`、
`headroom=1,073,741,824 bytes`、`estimated_runtime_sec=3600`、`confidence=low` とし、採用値ではない。
Wan source `PYTHONPATH` は Hunyuan subprocess へ漏らさない。

実 runtime で runner CLI import と既存 weight-free R9700 preflight を再実行した。

```text
runner --help              PASS / heavy import・network なし
weight-free preflight      PASS / R9700 gfx1201 / PyTorch SDPA
ROCm process cleanup       KFD process 0
focused                    20 passed / 1 warning
full                       693 passed / 1 warning / 46.96 s
model load / generation    NOT TESTED
weight / partial snapshot  0 / license acceptance 待ち
ControlDeck changes        0
```

判定: evaluator/admission/evidence preparation は **PASS**。model load、Host Broker 実要求、cancel、
artifact、VRAM/RSS/swap、quality/determinism は weight 不在のため **NOT TESTED**。通常の video
capability は unavailable、catalog は experimental/unmeasured のまま。

isolated data directory / `127.0.0.1:9162` で branch core を実起動した。`GET /health` は
`setup_required`（空の isolated data なので正しい）/ contract 2.0、model catalog は
`evaluation.available_model_ids=[]` を返した。Hunyuan entry は `experimental`、`installed=false`、
`measurement_confidence=low`、recommended profile 0。`video.image_to_video` は
`unavailable/planned_for_g7` のままで、設定なしの evaluator 準備が capability を誤昇格させないことを
確認した。branch core は正常 shutdown、installed v0.9.0 は `healthy`、KFD process は0。

最終 gate:

```text
focused                    20 passed / 1 warning
full                       693 passed / 1 warning / 46.96 s
branch core real HTTP      PASS / hidden-until-configured / capability unavailable
installed /health          healthy / contract 2.0
ROCm process cleanup       KFD process 0
git diff --check           PASS
compileall                 PASS
```

## G7 V1e — CogVideoX-2B Apache fallback evaluation（2026-08-26）

HunyuanVideo 1.5 は Tencent Hunyuan Community License の明示同意待ちを維持し、先に
Apache-2.0 の T2V-only 候補 `zai-org/CogVideoX-2b` を評価した。model revision は
`1137dacfc2c9c012bed6a0793f4ecf2ca8e7ba01`。19 files / 13,775,572,738 bytes の exact
snapshot を取得し、5 LFS object の size と SHA-256 を全件照合した。取得中に Xet route が
connection struggling で停止したため、partial を削除せず `HF_HUB_DISABLE_XET=1` の公式 Range
route へ切り替えて完了した。

core/image/Wan/Hunyuan と分離した `/data1tb/mediaforge-g7-cogvideox2b/runtime` を使った。
torch 2.10.0+rocm7.2.1、HIP 7.2.53211、Diffusers 0.40.0、Transformers 5.15.1。
weight-free preflight は R9700/gfx1201、CogVideoX pipeline/transformer/VAE import、PyTorch SDPA
を確認した。runner は exact local snapshot、offline-only、FP16、sequential CPU offload、VAE
slicing/tiling、固定 prompt/negative prompt/seed、H.264 MP4 を強制する。公式外の低解像度を品質
証拠にせず、720x480 を維持した。

最初の 5-frame smoke は Diffusers の temporal compression 条件と一致せず、6分42.98秒後に
frame-count validation で FAIL した。partial output は残らず、GPU は baseline へ復帰した。
通常 frame count は4の倍数、公式 profile は48生成frames + conditioning frameの49であることを
runtime source/configから確認し、smokeを8 framesへ修正した。修正後 smoke:

```text
preset / network             720x480 / 8 frames / 1 step / offline
elapsed / wall               53.316 / 57.85 sec
load / generate              0.893 / 52.077 sec
max RSS / process swap       19,452,981,248 / 0 B（/usr/bin/time: 18,997,052 KiB / swaps 0）
output                       H.264 / 8fps / 11,443 B
SHA-256                      8c9aefea092a9efef17ea7794d0a98c097f9bf4b01a8f325ecbd40214a47d0f4
system swap pages delta      in 612 / out 19,540
```

公式 quality run は installed v0.9.0 を一時停止し、branch core を同じ9130/data
directoryで起動して、短命 Host service identityから実行した。このsliceによるControlDeck
code/DB/manifest変更は0。Host worktreeには今回触れていない既存
`frontend/tsconfig.tsbuildinfo`変更1件がある。

```text
operation                    modelop_eea78a015e9c45aab311a6e14b6424ba
Host Job                     bf25a3d596be
Broker request / lease       52c974fe-c64f-4145-bda0-0e4c5b813553 /
                             6aaa9ab9-09f7-476a-bc95-4326ef3a0cf6
preset                       720x480 / 49 frames / 50 steps / 8fps
elapsed                      930.861 sec（denoise 282 sec、decode支配）
peak VRAM                    14,996,635,648 B（delta 14,936,723,456 B）
peak RSS / process swap      19,315,003,392 / 0 B
system swap pages delta      in 29,888 / out 29,985
output                       H.264 / 6.125 sec / 235,251 B
SHA-256                      a0932382761efe621e8b30c03be59ddb1ed70c78acff44f3ba87e00f8aceb857
```

Host audit は request `granted`、lease `active`、約10秒ごとの renew、10分時点の短命 credential
refresh、最終 `released` を記録した。完了後 Cog process 0、KFD process 0、R9700 VRAM
59,912,192 B。branch coreを正常停止し、installed Media Forge v0.9.0を再起動した。実 `/health`
は `healthy` / contract 2.0。

frame 0/24/48 の目視では orange field robot、solar panel、dusk field、locked camera を一貫して
維持し、SSIM は0→24が0.724、24→48が0.810だった。被写体・構図品質は **PASS**。一方、要求した
「solar panels を折り畳む」動作は明瞭でなく action adherence は **FAIL**。system swap activityと
930.861秒のlatencyも実用gateを満たさない。process swap 0、Broker lifecycle、artifact boundsは
**PASS**。deterministic repeat、Cog固有cancel、SonicForge active residencyとの同時要求、公開
Asset/provenance、I2Vは **NOT TESTED**（I2Vは本modelのcapability外）。

判定: CogVideoX-2BはR9700 backendを実証したが、`experimental` / low-confidence / recommended
profile 0のまま **DEFERRED**。T2V production routeへ採用せず、V2へ昇格しない。Apache-2.0候補
なのでHunyuanのterritory/MAU/AUP制約はないが、再配布時のLICENSE/NOTICE、変更表示、特許・商標
条件は維持する。次の再開条件は、zero system-swapと明確なaction adherenceを短いruntimeで満たす
別T2V候補、またはCogの保守可能なdecode/RAM lifecycle改善である。

最終 gate:

```text
focused                    33 passed / 1 warning
full                       700 passed / 1 warning / 49.15 s
git diff --check           PASS
compileall                 PASS
installed /health          healthy / contract 2.0
ROCm process cleanup       KFD process 0 / VRAM 59,912,192 B
ControlDeck slice changes  0（既存 frontend/tsconfig.tsbuildinfo 変更1件は保全）
```

## G7 V1f — Wan 2.1 1.3B T2V/I2V candidate preflight（2026-08-26）

CogVideoX-2B が action adherence、latency、system swap の gate を落としたため、次の Apache-2.0
候補を official Hugging Face metadata / model card / Diffusers 実装から固定した。T2V は
`Wan-AI/Wan2.1-T2V-1.3B-Diffusers@0fad780a534b6463e45facd96134c9f345acfa5b`、I2V は
`Wan-AI/Wan2.1-VACE-1.3B-diffusers@ec4d2cb062b548996b179d493fdd05340de702a1`。
両方とも public / non-gated、model card の license tag は Apache-2.0。

official tree API の全件を revision 固定で列挙した。

```text
T2V snapshot / weights      28,935,653,511 / 28,928,720,056 bytes
T2V files / LFS inference   31 / 10
T2V weights identity        sha256:5ae5898aacc245296343d129de399f7dcc153900dbbdf882da12a4b18b162569
VACE snapshot / weights     19,043,130,596 / 19,036,896,776 bytes
VACE files / LFS inference  27 / 8
VACE weights identity       sha256:2c488c292438aaa2914e96dea0b8cb929eda504adfb6bb583f721ea63d1be315
```

T2V の text encoder は float32 約22.7GB、VACE は bfloat16 約11.4GB。VACE official card と
Diffusers 0.40.0 の call signature は video / mask / reference_images conditioning を持ち、first-last-
frame-to-video と image/video-to-video を明示する。このため VACE を I2V 候補、T2V 1.3B を T2V
候補として別々に実測する。

専用 `wan21-1.3b-probe` runtime を `./mf.sh env build` で構築した。

```text
runtime size               4,686,651,246 bytes
build elapsed              26 sec / pip cache delta 160 bytes
pip check                  broken requirements 0
torch / HIP                2.10.0+rocm7.2.1 / 7.2.53211
Diffusers / Transformers   0.40.0 / 5.15.1
preflight                  PASS / 2.15 sec / max RSS 959,360 KiB / swaps 0
GPU                        AMD Radeon AI PRO R9700 / gfx1201
attention                  PyTorch SDPA default / custom kernel 0
cleanup                    KFD process 0 / VRAM 59,912,192 bytes
```

exact snapshots には model card がリンクする `LICENSE.txt`、LICENSE、NOTICE がいずれも存在せず、
revision 固定 HTTP は全て404だった。model card の Apache-2.0 宣言は記録するが、managed promotion /
再配布前に authoritative license text と applicable notices を bundle へ含める。

判定: source/license identity、bundle bounds、dedicated runtime、R9700 imports/default attention は
**PASS**。weight download/hash/model load/generation、VRAM/RSS/swap、quality、determinism、cancel、
Broker、installed browser、SonicForge coexistence は **NOT TESTED**。catalog は external /
experimental / low-confidence / recommended profile 0、公開 capability は unavailable のまま。
次は小さい VACE snapshot を先に download/hash し、Broker 経由 I2V gate を評価する。

最終 gate:

```text
focused                    9 passed / 1 warning
full                       702 passed / 2 warnings / 48.88 sec
compileall / diff check    PASS / PASS
installed /health          healthy / contract 2.0 / Media Forge v0.9.0
SonicForge                 sonicforge-acceptance.service active
ROCm cleanup               KFD process 0 / R9700 VRAM 59,912,192 bytes
ControlDeck slice changes  0（既存 frontend/tsconfig.tsbuildinfo 変更1件は保全）
```

## G7 V1g — Wan 2.1 VACE 1.3B bounded I2V evaluation（2026-08-26）

exact snapshot `Wan-AI/Wan2.1-VACE-1.3B-diffusers@ec4d2cb062b548996b179d493fdd05340de702a1`
を `/data1tb/mediaforge-g7-wan21-vace/hf` へ取得した。27 files / 19,043,130,596 bytes、incomplete
0件。8 inference LFS objects / 19,036,896,776 bytes は全件でsize/SHA-256が一致し、aggregate identityは
`sha256:2c488c292438aaa2914e96dea0b8cb929eda504adfb6bb583f721ea63d1be315`。

pinned Diffusers snapshotにLICENSE/NOTICEはない。official original VACE
`@574e6a744642ce3bee319afc31496b88bde8aac4` の `LICENSE.txt` は11,357 bytes、SHA-256
`c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`でApache License 2.0本文。
これをDiffusers snapshot内への同梱証拠とは扱わない。

exact local snapshot/offline-only、内部生成first-frame/mask、固定prompt/seed/preset、BF16 transformer、
FP32 VAE、model CPU offload、VAE slicing/tiling、PyTorch SDPA、silent H.264 MP4のprivate runnerと、
complete-snapshot-onlyのHost Job/Broker evaluatorを実装した。通常routing/recommended profileは変えない。

最初のload smokeはDiffusers prompt cleanerの`ftfy`不足を実検出してFAIL。partial output、lease、GPU
processは残らなかった。専用runtimeへ`ftfy==6.3.1`をpinして再buildし、size 4,691,289,880 bytes、
`pip check` broken requirements 0、R9700/gfx1201 preflight PASSを確認した。

installed v0.9.0を一時停止し、branch coreを同じ127.0.0.1:9130/data directoryで実行した。ControlDeck
code/DB/manifest変更0。Hostの既存`frontend/tsconfig.tsbuildinfo`変更は保全した。

```text
first operation / Host Job  modelop_1cc631a2db6d4feb8a12797981c23ac8 / 765f6c654597
Broker request / lease      4e3c79f5-4001-4a6d-b3a4-8d42bc0c7e5d / 234e804e-1c51-48e1-a11a-6966f4cc2b8a
preset                      256x256 / 5 frames / 1 step / 16fps / offline
core / runner / generate    264.045 / 260.206 / 258.718 sec
peak VRAM / delta           15,692,148,736 / 15,632,236,544 B
peak RSS / process swap     22,964,568,064 / 0 B
system swap page delta      in 2,890 / out 24,510
output / SHA-256            12,745 B / f216c929e95fde9aec4e99a7c10c1ef1061d9f934f232d64435db65244765077
Broker lifecycle            granted / active / renew 26 / released
```

lease release後、Qwen3.8-27B llama.cppが約30.3GB VRAM residentの状態で再要求するとoperation
`modelop_04311ee8578b4b3590997067b713ffae` / Host Job `762746655151` / request
`51e03af2-b510-4d17-b9b2-52c866b88554` は `insufficient_capacity`。worker未起動・直接競合なしで
Broker fail-closed **PASS**。実LLMを停止せず、最終利用12:22:43からControlDeckの30-minute policyを
待ち、12:53:19の自然解放後にだけ再実行した。

```text
optimized operation / Job   modelop_0c6d098f7b5e4b0981faea6206ae8c89 / 5dadb1a12ac9
Broker request / lease      58a6b7e6-0a84-42c3-afc2-da05767dce81 / 956e199a-e74f-4abc-b42a-35d6f35c55e2
bound                       max_sequence_length=128
core / runner / generate    234.486 / 213.310 / 209.625 sec（denoise 136.06 sec）
peak VRAM / delta           15,686,881,280 / 15,626,969,088 B
peak RSS / process swap     20,991,193,088 / 3,891,077,120 B
system swap page delta      in 965,924 / out 1,066,354
output / SHA-256            14,494 B / 9a5bebd61075b14d854d232d6fd1bb3f2590c180330faf3aeaff242246fdac4e
artifact                    H.264 / 256x256 / 16fps / 5 frames / 0.3125 sec
Broker lifecycle            granted / active / renew 22 / released
```

frame 0/2/4はblue panel、orange body、arms、wheels、green fieldとlocked compositionを保持し、smoke
subject stabilityは **PASS**。ただし1-step/5-frameで234.486秒、3.89GB process swap、100万超の
system swap-out pagesとなりlatency/RAM gateは **FAIL**。512x320 / 33 frames / 30 steps candidateは
採用判定を変えずswapを悪化させるため実行しない。

判定: ROCm/offline boundary、Host Job/Broker lifecycle、artifact bounds、LLM優先coexistenceは
**PASS**。candidate quality、repeat、cancel、公開Asset/provenanceは **NOT TESTED**。VACEはexternal /
experimental / low-confidence / recommended profile 0のまま **DEFERRED**、G7 V2へ昇格しない。
再開条件はprocess/system swap 0を実測できる保守可能なoffload/RAM改善または別I2V候補。T2V 1.3B
weights/partial snapshotは0を維持する。

最終 gate:

```text
focused                    32 passed / 1 warning
full                       711 passed / 1 warning / 48.38 sec
compileall / diff check    PASS / PASS
installed /health          healthy / contract 2.0 / Media Forge v0.9.0
services                   Media Forge / ControlDeck / SonicForge active
ROCm cleanup               VACE/KFD process 0 / R9700 VRAM 59,912,192 B
ControlDeck slice changes  0（既存 frontend/tsconfig.tsbuildinfo 変更1件は保全）
```

## G7 V1h — VACE prompt/model lifecycle follow-up（2026-08-26）

V1gの3,891,077,120 B process swapを追加weight/custom kernel/Host変更なしで改善した。固定prompt embedsを
GPUで生成し、UMT5/tokenizerを破棄してからmodel CPU offloadを適用すると同一SHA、process swap 0を
2回再現したが、system swap-outは5,639 / 1,921 pages残った。

VAE/scheduler/tokenizer/text encoder/transformerを公式component loaderで直列化し、text encoder破棄後に
transformerをロードした最良値:

```text
operation / Host Job         modelop_c50d8aa2472440d9b126450f67cd750f / eedcdf7b2887
Broker request / lease       7f3cfff0-c1a8-4fe3-9d20-add9c0edc9e4 / 67a50ea4-d7cd-44cd-bb35-da728fffba0a
core / runner / generate     110.622 / 108.069 / 103.037 sec
peak VRAM / delta            19,462,033,408 / 19,402,121,216 B
peak RSS / process swap      10,251,010,048 / 0 B
system swap page delta       in 70 / out 401
output / SHA-256             14,494 B / 9a5bebd61075b14d854d232d6fd1bb3f2590c180330faf3aeaff242246fdac4e
```

`device_map` direct GPU loadはpeak RSS 12,437,766,144 B、swap-out 14,940 pagesへ悪化したため除外。
V1g比でlatency/RSS/process swapは改善しdeterminismも **PASS** だが、zero system-swapは **FAIL**。
candidate quality/cancel/public assetは **NOT TESTED**、VACEは **DEFERRED** のまま。LTX-Video 2B
0.9.8、SkyReels 1.3B、Hunyuanはいずれも独自licenseの明示acceptanceなしにweight取得しない。

最終 gate は lifecycle/preflight/catalog/evaluator の focused が `32 passed, 1 warning in 5.85s`、
`./mf.sh test` が `711 passed, 1 warning in 48.28s`。対象2ファイルの `compileall` と
`git diff --check` も通過した。branch core停止後、installed Media Forge v0.9.0を復元し、
Media Forge / ControlDeck / SonicForge はすべてactive、実 `/health` はhealthy / contract 2.0、
VACE/KFD process 0、R9700 VRAM 59,912,192 Bを確認した。ControlDeck変更は0で、既存
`frontend/tsconfig.tsbuildinfo` の変更1件を保全した。

## G7 V1i — VACE VAE delayed-load comparison / G7 deferral（2026-08-26）

V1hの残存system swapに対し、追加weight、custom kernel、Host変更なしでVAEのロード順だけを比較した。
installed Media Forge v0.9.0を一時停止し、branch coreを同じ9130/data directoryで起動した。実
installed iframe identity、Host Job、Broker、R9700、SonicForge activeの経路を使った。

```text
                              VAE delayed load                   V1h control
operation                     modelop_2caa9d49a5f24be69d69f8bb49a36d1f
                                                                modelop_1954e9cd95c94d6fa612a6f7c5038acd
Host Job                      8697762eb240                      d50b0d07bda3
core elapsed                  111.829 sec                       110.931 sec
peak RSS / process swap       10,430,042,112 / 0 B              10,245,021,696 / 0 B
peak VRAM / delta             22,179,917,824 / 22,120,005,632 B 19,462,152,192 / 19,402,240,000 B
system swap in / out          123 / 3,597 pages                 9,748 / 2,977 pages
output                        14,494 B / H.264 / 5 frames       same
SHA-256                       9a5bebd61075b14d854d232d6fd1bb3f2590c180330faf3aeaff242246fdac4e
```

遅延loadはRSS、VRAM、swap-outの全てで対照より悪く、コード差分を戻した。Diffusers 0.40.0の
group/disk offloadは利用可能だが、1-step denoiseが約51秒のVACEで各blockを30 steps再転送する経路は
実用latencyを改善しない。専用runtimeにはTorchAO / bitsandbytesがなく、ROCm/gfx1201で検証済みの
量子化backendも確認できないため追加しなかった。

判定は **DEFERRED**。V2〜V4、candidate quality、cancel、公開Asset/provenanceは **NOT TESTED**。
通常video capability、catalog state、recommended profileは変更しない。再開条件は明示license acceptance
済みの軽量候補、またはzero-swapと実用latencyを同時に満たす別のpermissive候補。評価後はbranch coreを
正常停止し、installed v0.9.0を復元した。Media Forge / ControlDeck / SonicForgeはactive、実healthは
healthy / contract 2.0、VACE/KFD process 0、R9700 VRAM 59,912,192 B。試験用`mf-e2e` password hashは
各run後に元値へ復元し、新規browser sessionをrevokeした。ControlDeck code/manifest変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。

最終 gate はVACE runner focused `6 passed, 1 warning`、`./mf.sh test`が
`711 passed, 1 warning in 48.01s`、`git diff --check`がPASS。採用コード差分は0件。

## G8 B0 — pinned Blender runtime / license boundary（2026-08-26）

実機にはsystem Blenderが無かったため、ControlDeck、core venv、ML runtimeへ依存を追加せず、公式
Blender 4.5.9 LTS Linux x64 portable archiveを専用runtimeへ明示provisionした。

```text
archive                     blender-4.5.9-linux-x64.tar.xz
download / SHA-256          377,929,956 B / dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d
archive safety              6,510 members / extracted payload 1,168,332,002 B
runtime total               1,546,263,669 B
Blender / embedded Python   4.5.9 / 3.11.11
real preflight              background=true / glTF import=true / export=true
status                      0.21 sec / max RSS 264,380 KiB
ready build                 0.21 sec / max RSS 272,104 KiB / reused=true
```

installerはexact HTTPS host/name/size/hash、単一top-level root、relative contained link、member count、
展開sizeを強制し、device/FIFO/escapeを拒否する。stagingで実preflight後だけatomic installし、runtime rootは
repository `runtimes/`配下に限定する。preflightは固定 `--background --factory-startup --disable-autoexec
--python <trusted-file>` のみで、temporary HOME/XDG/Blender user dirsを終了時に削除する。`--python-expr`、
chat script、root installは実装していない。

Blender/bpy workerはGPL-3.0-or-later境界として分離した。Blender binaryはrelease bundleへ同梱せず、
生成assetのlicenseをGPLと記録しない。focused installer testsは10件PASS。B1以降のGLB import、compile、
asset/provenance、preview、timeout/cancel、installed browser/agentは **NOT TESTED**。

実行後Blender process 0、R9700 VRAM 59,912,192 B、Media Forge / ControlDeck / SonicForge active、
installed healthはhealthy / contract 2.0。ControlDeck code/manifest変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件を保全した。

最終 gateはfocused `10 passed, 1 warning`、full `721 passed, 1 warning in 46.48s`、Python
`compileall`、`bash -n mf.sh`、`git diff --check`がPASS。

## G8 B1 — bounded GLB import / independent validation（2026-08-26）

public Asset MIMEへ `model/gltf-binary` を加法的に追加し、`purpose=source` の browser / workspace
byte transportから単一GLB 2.0をimportできるようにした。filenameやpathは入力せず、元bytesを変更せず
hash/storeする。Blenderと独立したcore validatorはmagic/version/declared length、JSON/BIN chunk、
UTF-8/finite JSON/depth/value count、top-level count、bufferView/accessor range、mesh/node/scene reference、
external buffer/image URI、required extensionをboundedに検査する。未計測のrequired extensionとsparse
accessorはB1ではfail-closed。

コード生成した第三者asset非依存のtriangle GLBは620 B。一時data rootと実Uvicorn
`127.0.0.1:9160`に対するHTTP importは201を返し、Asset/contentのSHA-256はともに
`29e22906825ae044e2b37aee45e767f6f253227e9f5b8e2f50b281fbddec4e5f`。provenanceは
`asset.import` / `user-provided` / `validator.glb=1.0.0`、scene/node/mesh/primitives=1、
accessor/bufferView=2を返し、source filename/pathは含まなかった。破損bodyは422
`invalid_glb_import`、失敗後work entry 0。サーバ停止後に一時data rootを削除し、port 9160の
listenerも0。

focused GLB tests 10件はPASS。Blender re-import、Host `grant:` read、installed-host browser、B2 compile /
preview / package / cancelは **NOT TESTED**。ControlDeck code/DB/manifestは変更していない。
最終gateは `./mf.sh test` が `731 passed, 1 warning in 47.16s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。

## G8 B2 — deterministic Blender compile package（2026-08-26）

既存 `asset.pack` にcanonical `profile=3d.project.glb` を加法し、1件のGLB Assetから
`asset.glb` / `manifest.json` / `preview.png` の3 entry ZIPを作る固定経路を実装した。
G1のprofile regexは先頡英字だけで計画済みIDを受理できなかったため、既存値を壊さない
加法的変更として先頭数字を許可した。それ以外のpattern、path、operator、scriptは許可しない。

coreが起動できる子processは次の固定形だけ。request/resultもjob root内の固定名で、
workerは入出力filenameとexact fieldを再検査する。

```text
blender --background --factory-startup --disable-autoexec \
  --python worker_packs/blender/compile_asset.py -- \
  --request request.json --result result.json
```

temporary HOME/XDG/Blender user dirs、`LIBGL_ALWAYS_SOFTWARE=1`、GPU visibility空、process group
timeout/cancel、stdout/stderr各256 KiB上限をcoreで強制する。workerはcamera/light/text/driver/
custom propertyを除去し、MESH/EMPTY/ARMATURE以外をreject、meter/Y-up・finite transform・
transform apply・normal inspection・orphan purge後にGLBを書き出す。previewは固定Workbenchで描画し、
Blenderが付けるDate/RenderTimeなどのancillary PNG metadataを除いてから独立検査する。

最終CPU-only設定の別process 2回は1.19 / 1.01 sec、max RSS 652,092 / 658,288 KiB。
生成triangleのhashは次の3件で完全一致した。Eeveeとmetadata未正規化Workbenchはpreview
hash不一致のため不採用。assertionは緩めていない。

```text
asset.glb    8135b0ea92cdfa047a8eeaf11bbd8a5ff634f0086696d40aaf1e05438c450868
preview.png  6dc759022f4cc116e0ce216483962c4db63efb844ad06f0b320352ac357b046f
ZIP          aaa87f7fe6fdb5873360e60749208b68c0f9fad1d52bce8042a9013edf3740e3
```

最終コードの実Uvicorn `127.0.0.1:9160` でJob APIを2回実行し、job
`job_7af008abcb38430fbff26fc2ed3548cb` / `job_1b30c0e07fb64a238b864f18201ce306` は両方
succeeded、ZIP hashも上記と一致しbyte-identical。実行後work entry 0、Blender process 0、
R9700 VRAM 59,912,192 B。一時data rootはtrashへ移動し、port 9160 listenerも0。

focused B2 tests 5件はpackage metadata/order、2回hash、Asset/provenance、任意option reject、
failure/cancel partial asset 0、trusted commandをPASS。実process cancel/timeout、installed Host Job phase、
browser/agent/grant、B3 optionは **NOT TESTED**。
最終gateは `./mf.sh test` が `736 passed, 1 warning in 50.77s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。

## G8 B3 — typed production options（2026-08-26）

`constraints.compile_options` にprivate versioned `3d.compile-options@1` を追加した。Pydanticとtrusted
Blender workerの両方がexact fields/type/boundsを検査し、unknown field、`apply_transforms=false`、
非降順LOD、budget 12未満、任意operator/script/pathをrejectする。compile optionを省略した
B2 requestは既存の固定defaultと同じ。

```text
apply_transforms       true固定
repair_normals         bool
remove_degenerate      bool
merge_by_distance_m    null or 0.0000001..1.0
triangle_budget        null or 12..200,000
lod_ratios             0..3件 / 0.05..0.95 / strict descending
collision              none / box / convex_hull
materials              preserve / basic_pbr
preview                fixed_workbench固定
```

workerはmesh edit、triangle budget、material単純化、LOD mesh、collision proxyを明示option時だけ
実行し、manifestの固定10 operationそれぞれに `parameters/results/warnings` を保存する。
コード生成material cubeで全optionを別process 2回実行し、base 12 triangles、LOD 6、box
collision 12、material changed 1、最終scene 30 triangles / 21 vertices / 3 meshes。hashは次の3件で
byte-identical。

```text
asset.glb    908d3fb060e268c9b1321aca2eb7e476b91cad4d27b4e59aba2b6a15155ba48e
preview.png  3832e4195bf68fb6a8af843102e3ac48319a345177028699b921b7c78292411a
ZIP          e2b9994cde08796f5d51b7f057c7be832cb2ea4b3f3632f8a4e79cece987e3f2
```

repair fixtureはmerge 1e-6 m + degenerate removal + normal repairで4→3 vertices、2→1 triangles、warning 0。
cube convex hullは8 vertices / 12 triangles。triangle budget上限はコード生成3,625,792 B gridで
推測でなく測定した。200,978→199,999 triangles、別process 2回は2.09 / 2.03 sec、max RSS
880,552 / 887,708 KiB、GLB SHA
`d19346f5f044dc9eca525d75958264ae53bea7b8a937e89a896a87b46a20e853`、ZIP SHA
`f98ef70872f2dd40983016f62b5b5b43a57b41f0592f845a4f806be6d128c99b`で完全一致。

focused B3/schema/job testsは9件PASS。実installed Host/browser/agentのoption入力、real cancel/timeout、
rig/animation付きassetは **NOT TESTED**。
最終gateは `./mf.sh test` が `740 passed, 1 warning in 54.70s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。

B3はsoftware rendering + GPU visibility空で実行し、Qwen/llama processには触れていない。最終確認時、
先行していたtransient `sonicforge-acceptance.service` は14:52:03にexternal操作でsuccess停止・unit削除済み。
代わりにPID 2116151/2116153が `/tmp/cd-sf-catalog-v010-acceptance/.../sonicforge-core serve`
としてport 9140で稼働し、healthは `setup_required` / contract 2.0、Qwen/llama process 0。
このexternal SonicForge acceptance環境は変更・停止していない。

## G8 B4 — workspace / agent / project placement（2026-08-26）

Blenderをrequest時に起動しないexact stamp / executable / trusted worker確認をcapability
`asset.3d_project_pack`へ追加した。Createはruntime ready時だけGLB選択を表示し、Simpleではasset選択後だけ
「プロジェクト用ZIPを作る」を表示する。AdvancedはB3の型付きfieldだけへ到達し、Simpleへ戻した場合は
hiddenだったAdvanced値を送らず固定defaultへ戻る。公開jobは既存 `asset.pack` +
`profile=3d.project.glb`、Agentは既存 `media.generate`、配置は既存 `media.pack` のままで、raw project /
Blender path、operator、script bodyは追加していない。

Library投影へpreview種別とsuggested filenameを加えた。3D packageはZIPをfilesystemへ展開せず、entry順を
`asset.glb` / `manifest.json` / `preview.png` に固定し、暗号化、member count、展開後合計128 MiB、manifest
1 MiB、preview 8 MiB、manifest schema/profile/preview size/hashを検査してからpreview bytesだけをWebPへ
変換する。`../escaped` を含むarchiveはrejectされ、外部file作成0。画像でも3D packageでもないassetは
thumbnail HTTPを要求しない。単体表示もembedded transportと同じLibrary投影を使う。

実Uvicorn `127.0.0.1:9162`、一時data root、実Blender 4.5.9、実Chromiumで620 B triangle GLBを選択した。
Simpleで未選択時action非表示、選択後表示、Advancedでnormal repair / degenerate removal / merge 1e-6 m /
triangle budget 12 / box collision / basic PBRを入力し、browserが送ったexact typed requestをassertした。
job `job_a90bb3d8adee4db79b6e3265e60b2386` は0.727 secでsucceededし、40,603 B ZIP Asset
`asset_393d4c4a6db44bdeb217e9b621647539`、SHA-256
`adb22b8daadd6aae5c14b79460d4d774dcc8588ff213afdf5bd7b7b696d7ae3e` を登録した。Library cardは
`data:image/webp;base64,` preview、viewerは `ZIP · プレビュー`、console/page errorは0。スクリーンショットは
15,144 B。GLB選択後のSimple表示は320px viewportでhorizontal overflow 0。終了時core healthはhealthy /
contract 2.0、work entry 0、Blender child 0、port 9162 listener 0。

Host stubを使うfocused contractでは、同じ3D requestを既存Agent generateへ渡し、embedded WebSocket
Library cardのWebPを取得後、既存Agent packで `project-ready.zip` を `grant:export-1`へcommitした。
receiptは `application/zip`、payloadはZIP magic、tmp/repository path leak 0。hostile ZIP、capability
stamp fail-closed、Simple/Advanced disclosure、Agent/Library/placementを含むfocused 200 testsはPASS。
実installed ControlDeck browser/identity/Host Job/real grant、real Agent Blender execution、reconnect、
cancel/timeout、rig/animation付きassetはB5として **NOT TESTED**。

最終gateは `./mf.sh test` が `746 passed, 1 warning in 48.51s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。ControlDeck code/DB/manifest変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。installed Media Forgeは127.0.0.1:9130でhealthy /
contract 2.0、R9700 VRAM 59,912,192 B、Qwen/llama process 0。SonicForge 9140はexternal変更により現在
healthy / contract 2.0（Speech Essentials/Music ok、Game Audio missing）であり、このsliceでは変更していない。

## G8 B5 — installed ControlDeck acceptance（2026-08-26）

実installed ControlDeck、branch core、実Chromium、実Blender 4.5.9でB5を完了した。workspaceへ
browser bytesとHost file pickerの両方から3,625,792 B / 200,978-triangle GLBをimportし、Asset
`asset_ecbc752b93624c31a19b7434a32fbb89` / `asset_6ce100e79154436199748fd798788674` は入力と同じ
SHA-256 `4e4e65714e409e34d18b3be5e21cc39eddee6e3eca6467e292846801ca13c04c`。Host picker経路は
opaque `grant:` IDだけをprivate workspace transportへ渡し、Host pathを送受信しなかった。

workspace job `job_2eed58a192c149ea92dab25c57a23f38` は実行中reload後の再接続でも`running`を観測して
succeeded。Agent Host Job `c43db95ba470` もsucceededし、Host最終phaseは`package`、progressは
1000/1000、event 1件。両経路の別Blender processが作ったZIPはbyte-identicalだった。独立検査値は次の通り。

```text
source GLB     3,625,792 B  4e4e65714e409e34d18b3be5e21cc39eddee6e3eca6467e292846801ca13c04c
package ZIP      919,412 B  8568abd66b538f543b2a9a95993e5caa07a841b7f0a68f4696fe0c4debc5424e
asset.glb      4,815,840 B  0b1e065062f160a4f668dc000e0d860a08226da6b039f7134931b01e782f775a
preview.png       36,338 B  26d07b3311c80ab56feb2dda838e033a7c347d4eb2a02528543a1143867e6cc0
manifest facts  triangles=200,000 / vertices=100,627 / bounds=[0,0,0]..[317,0,317]
```

Libraryは実previewを表示し、browser console/page errorは0、screenshotは108,791 B。Agent packは
Host asset `asset:fe47805b-72ea-49dd-b882-16415862f24e`へ919,412 Bをcommitし、receiptと実committed
bytesのSHA-256はZIPと一致した。

Host cancel job `64c1e07551e5` は実Blender child PID 2235001を観測後canceledへ収束し、child 0、partial
asset/work 0。CPU-only `asset.pack`中のHost cancelをGPU lease taskに依存せずpollするよう修正し、実行中の
ControlDeck resource request増分は0だった。`MEDIA_FORGE_BLENDER_TIMEOUT_SEC=0.05`の別processではjob
`job_d7ef5e588ea04ea489db073afe9b5bdf` が0.070 secでfailed、errorは`blender_compile_failed` /
`Blender compiler exceeded the 0.05 second timeout`、asset/work 0、coreはhealthy。

永続store `/tmp/mediaforge-g8-b5-recovery-R3jDf5` では、core停止中にqueuedだった実Blender job
`job_1d07586985694ff786a95d0fcf506129` が再起動後succeeded。別job
`job_7b8a1398f19d4ce898a3ab22a7ec0056` は`running` / phase `validate`で、service cgroup内の実Blender
PID 2236235をsystemdのkill記録で確認して
service cgroupをSIGKILLし、DBにrunningのまま残ることを確認した。同じstoreで再起動するとfailed /
`service_restarted` / asset 0へ収束し、work file 0、health healthy。

実project placementでHostの中央stagingとgrant先が別filesystemの場合に`os.replace`が`EXDEV`となる
generic境界不具合を観測した。Media Forge側ではraw pathを受けず、Hostのatomic commit契約も弱めず解けないため、
ControlDeck別PR #246でgrant先directory内tempへのcopy、fsync、同一directory内no-overwrite atomic publishへ修正した。
exact head `2cdc1cd264ed777651c5c0ba8af9ffbf2a473261`、merge commit
`8a6fc31d748c789b131282911e49a131ae03ff8d`。ControlDeck focused 31件はPASS。fullは814 passed / 1 skipped /
5 failedで、4件は共有Host Job active-limit状態、1件は固定1秒のresource timingであり、各該当testはclean
processまたは単独実行でPASSした。Media固有route/dependency/文言はHostへ追加していない。

schema discoveryでroot `type`を要求する実Hostに合わせ、placement schemaへ`type: object`を追加した。
各`oneOf` branchは既にobject限定のため受理集合は変わらない。Host progressのforced final updateがrate gate
境界で自己rejectした実raceは10 ms safety marginで修正した。

終了時、導入済みMedia Forge v0.9.0をsystemd PID 2237186/2237197で127.0.0.1:9130へ復元しhealth
healthy / contract 2.0。SonicForge 9140は変更せずhealthy（Speech Essentials/Music ok、Game Audio missing）。
実Blender process 0。rig/animation付きassetは **NOT TESTED** であり、静的mesh profileの対応範囲へ含めない。

最終gateはfocused 200件、`./mf.sh test` 750件がPASS（既知のStarlette warning 1件 / 50.23s）。
Python `compileall`、`node --check frontend/app.js`、`git diff --check`もPASSした。

## Mobile Create media switch（2026-08-26）

利用者の明示要求により、Create最上部へ「画像を作る／動画を作る」の2択segmented controlを追加した。
390pxと320pxでは全幅2列、各touch target高さ44pxで、server-side preference `create_media` に選択を
保存する。画像側の既存挙動は維持し、動画側はpromptと任意の元画像を表示する。これはtimeline型の動画編集器では
なく、元画像なしは`video.text_to_video`、1件ありは`video.image_to_video`へ対応する生成面である。

現在の公開capabilityは両方とも`unavailable / video_runtime_not_adopted`。動画面への切り替えと入力は可能だが、
実行ボタンを「動画は現在利用できません」として無効化し、理由と設定へのexitを表示する。capabilityを
`experimental`または`available`として受け取った場合だけ、既存公開契約`video.generate`、MP4、count 1、
`local_only=true`を送る。元画像ありではimport済みopaque asset IDをinputsへ1件入れ、pathやmodel名は送らない。

実standalone Chromiumで390px / 320pxを確認した。horizontal overflowは両方0、390pxの各切り替えは
176x44px、320pxは141x44px、browser console/page errorは0。unavailable時の理由表示、実行不可、設定exitを
assertした。テスト内でcapability documentだけを`experimental`へ置き換え、text-to-videoではinputs 0件、
image-to-videoではinputs 1件となるexact requestを捕捉した。

導入済みControlDeckの実mobile shellでも、branch coreを一時的に127.0.0.1:9130へ接続して同じUIを確認した。
390px / 320pxのhorizontal overflowは0、touch targetは176x44px / 141x44px、console/page errorは0。
終了後はbranch coreを停止し、導入済みMedia Forge v0.9.0を127.0.0.1:9130へ復元した。

focused frontend/API/schema/video testsはPASS。最終gateは`./mf.sh test`が
`751 passed, 1 warning in 54.86s`、Python `compileall`、`node --check frontend/app.js`、
`git diff --check`がPASS。実動画runtime、weight取得、GPU動画生成、出力再生品質、timeline編集は
**NOT TESTED**。Tencent licenseへの同意・利用開始は行っていない。ControlDeck code/DB変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。

## v0.9.1 release / installed video-screen reachability（2026-08-26）

利用者が実ControlDeckから動画生成面へ到達できないことを報告した。稼働processは
`versions/0.9.0/bin/mediaforge-core`、配信HTMLに`create-media-switch`は無く、原因はmerged UIを含まない
旧bundleへ復元したままだったことであり、Host routeやcapability gatingの不具合ではなかった。

versionを`addon.json`と`mediaforge.__version__`で0.9.1へ揃え、Media Forge #147（exact head
`f7f42c7af6e34420d2dba4017f733a6f4d58c8c7`、merge commit
`cc3f342d77a20e98d95fcc43d276e1aafdcd8d94`）をmergeした。同じmerge commitをtag `v0.9.1`として
bundleを構築・署名・公開した。

```text
artifact   control-deck-media-forge-0.9.1-linux-x86_64.tar.gz
bytes      30,954,097
SHA-256    ae9087ca6f1548260dd69f980face65cde003f380f8fa74488e68b4d8d098bf2
manifest   275 B / signature 89 B
release    https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.1
```

公開releaseから別fileへ再downloadし、30,954,097 Bと同じSHA-256を確認した。展開した配布binaryの
`doctor`は`version=0.9.1 / packaged=true`。別port 9166で起動したbundleはHTMLに切り替えを含み、
両video capabilityを`unavailable / video_runtime_not_adopted`として返した。

実ControlDeckの標準`./deck.sh feature update media-forge`は11.89秒、max RSS 783,412 KiBで成功し、
結果は`version=0.9.1 / previous_version=0.9.0 / healthy`。`current`は`versions/0.9.1`を指し、
rollback用0.9.0も保持した。0.9.0 / 0.9.1 version treeは31,082,798 B / 31,222,710 B、永続
feature-dataは78,755,964,188 B、Asset APIは18件。終了時service PID 2325466/2325471、9130 healthは
`healthy / contract 2.0`。

実ControlDeckへ短命test identityでloginし、route `/x/media-forge/workspace/create`のopaque iframe内で
「動画を作る」を押して動画面へ到達した。390px / 320pxの各touch targetは176x44px / 141x44px、
horizontal overflow 0、browser console/page error 0。理由は「実用条件を満たす動画モデルがまだありません。」、
submitはdisabledだった。これは導線のPASSであり、実動画runtime/weight/GPU生成/品質/timeline編集は引き続き
**NOT TESTED**。license同意・モデル取得は0。ControlDeck code/DB schema変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。

release前gateはfocused 199件と`./mf.sh test` 751件がPASS（既知warning 1件 / 53.52s）。GitHubの
required checkは設定0件だった。

## v0.9.2 video model management clarity（2026-08-27）

実ControlDeck v0.9.1の`/x/media-forge/workspace/create`から動画面、設定exit、動画候補filterまでを
短命test identityで再現した。候補12件は表示されたが、導入済みWan TI2V／MiniMax H3 GGUFだけが削除可能、
未導入候補は外部管理または容量超過であり、操作不能理由がhover titleに隠れていた。また導入済み未採用状態を
「要確認」、Create側を「実用条件を満たす動画モデルがまだありません」と表示していたため、利用者からは
追加・削除機能が無く、license acceptance不足で生成不可に見える状態だった。

設定contributionとPCヘッダの入口を「モデル管理」と明記し、動画filterで候補／導入済み／追加可能／削除可能の
件数を表示する。各行は`導入済み・利用可/利用不可`を区別し、外部管理・容量超過の理由をtouchでも常時読める
本文にした。Createは導入済み動画モデルを検出した場合、モデル不足とは言わず「実用品質とメモリ安全性を
満たした実行環境が未採用」と説明する。license acceptanceはexact checkpointのdownload許可であり、runtime
採用ではないことも動画filterへ明記した。

CogVideoX-2Bは13,775,572,738 bytes、exact revision、LICENSE、必須file、全weight size/SHA-256が閉じ、
32,000,000,000 bytes未満のmanaged installer条件を満たすため、checkpoint ownershipだけを`managed`へ変更した。
これにより現在の動画filterは候補12／導入済み2／追加可能1／削除可能2となる。CogVideoXのdownload/removeは
可能になるが、R9700評価でaction adherence、latency、system swap gateを落としているため`experimental`、
healthy=false、recommended 0、公開video capability unavailableは維持する。download操作の横にも、取得だけで
動画生成は有効にならないと表示する。

focused frontend/catalog/manager/transportは211件、その後catalog/manager/frontendは155件がPASSした。
最終`./mf.sh test`は751 passed / warning 1件 / 51.73秒。branch coreを実feature-dataへread-only相当で
別port 9131起動し、standalone Chromium 1280px/320pxで上記件数、CogVideoX download表示、理由本文、横overflow 0、
console/page error 0を確認した。既存Wan/H3 modelは削除していない。

Media Forge #149（exact head `cb3e760d9e1e7339e1ae921568a9cd025c79181b`、merge
`0d69a24abfc7389424cc09901e7de760bd1b7af7`）をmergeし、同じmerge commitをtag `v0.9.2`として
bundleを構築・署名・公開した。署名はmanifestのexact bytesに対してEd25519検証した。公開Releaseを
別のtemporary directoryへ再downloadし、local buildと同じ30,866,305 bytes、SHA-256
`61a0a41ef3a068625ca3068634fa4bdb3d3b655005a00d6cda571d707d490c55`を確認した。manifestは275 bytes、
signatureは89 bytes。展開binaryの`doctor`は`version=0.9.2 / packaged=true`。別port 9166のbundleは
CogVideoXを`managed / installed=false / experimental`として返し、320px Chromiumで追加可能表示、
横overflow 0、console/page error 0だった。

実ControlDeckの標準`./deck.sh feature update media-forge`は14.22秒、max RSS 786,400 KiBで成功した。
`version=0.9.2 / previous_version=0.9.1 / healthy`、`current`は`versions/0.9.2`、rollback v0.9.1を保持。
version treeはv0.9.1が31,222,710 bytes、v0.9.2が31,133,110 bytes、永続feature-dataは
78,755,927,268 bytes。9130の実processはPID 46572、exact v0.9.2 binary、health healthy / contract 2.0。

短命test identityで実ControlDeckのopaque iframeを1280px/320pxで操作した。Createは「動画モデルは
導入済みだが実用品質とメモリ安全性を満たす実行環境が未採用」と表示し、設定exit後は動画候補12、
導入済み2、追加可能1、削除可能2を表示した。CogVideoXにはダウンロードbuttonと「取得だけでは生成は
有効にならない」の本文、Wan TI2V／H3 GGUFには`導入済み・利用不可`と削除buttonを確認した。
320pxの横overflow 0、両幅console/page error 0。公開capabilityはT2V/I2Vとも
`unavailable / video_runtime_not_adopted`のまま。

CogVideoX 13.8GBの実managed download/removeは、既存外部evaluation snapshotを変更しないため
**NOT TESTED**。既存snapshot 18,734,841,514 bytesとpartialを移動・削除していない。production動画生成も
不採用gateを維持して **NOT TESTED**。Release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.2

## LoRA zero-config base routing（2026-08-27）

LoRA は単体生成モデルではなく、互換する base checkpoint が必要である。旧UIは不足時に
「土台も一緒に取り込む」チェックと別downloadを要求し、生成時も手動checkpoint選択へ
候補を従属させていた。さらにcustom Civitai entryのsourceを`huggingface`と保存していたため、
登録後の実download URLが誤っていた。

LoRA resolveは不足するbaseをexact revision・license・bytes込みのdependencyとして返す。
UIはLoRAとdependencyの条件・合計容量を1回で確認し、1回の`models.custom.add`でcatalogを
atomic更新して両方のmanaged downloadを開始する。baseはinstall後に同じ要求の後続処理で
自動評価する。Createはinstalled LoRAをmanaged catalogでも`kind=lora`として認識し、LoRAを
選ぶと手動model指定をautoへ戻す。core routingは選択LoRAの正規化familyをhard constraintにし、
異系統混在をworker起動前に拒否する。trigger word自動追加とprovenance上のresolved modelは維持した。

実Civitai APIで`civitai/58390`をread-only resolveした結果、revision `62833`、
`lora.diffusers`、base `SD 1.5`、37,861,176 bytesと観測した。手元にbaseが無い条件では
DreamShaper `civitai/4384` revision `128713`、2,132,625,894 bytesをdependencyとして解決した。
検索APIではDetail Tweaker XL `civitai/122359` revision `135867`、base `SDXL 1.0`、
228,452,344 bytesも観測した。重みdownloadは利用者による当該配布条件の同意前なので開始していない。

focused 6 filesはPASS。最終`./mf.sh test`は757 passed / warning 1件 / 64.13秒。
release bump後の再実行も757 passed / warning 1件 / 55.35秒。

Media Forge #151（exact head `e321755890fd013acf14b90263d5e77fa8cd1e18`、merge
`963f26712e513515ef02b75aa249c4bab34e392c`）とv0.9.3 release #152（exact head
`7c80970267521b69910f17495e3444d1717c1898`、merge/tag
`db4eddd77cde5c2349b5ba80872832ce815f2495`）をmergeした。bundleは30,957,893 bytes、
SHA-256 `41d7d392dba52527bfa8a11506eaeb0c83489926a01ea196085275389d70d397`。
公開Releaseを別temporary directoryへ再取得してhash一致、manifest 275 bytes、signature 89 bytes、
trusted publisher公開鍵によるEd25519検証成功を確認した。

実ControlDeckの標準`./deck.sh feature update media-forge`は13.15秒、max RSS 786,640 KiB、
swap 0で成功した。`version=0.9.3 / previous_version=0.9.2 / healthy`、`current`は
`versions/0.9.3`。実process PID 159617/159621のうち159621が127.0.0.1:9130をlistenし、
healthはhealthy / contract 2.0。v0.9.3 version treeは31,225,870 bytes、永続feature-dataは
78,755,927,268 bytesで変更していない。

短命identityで実ControlDeck opaque iframeを操作した。1280pxでLoRA検索結果
`civitai/58390`、不足baseの「必要な土台も自動でダウンロードします」、単一の
「同意してダウンロード」、旧`lora-base-together` 0件を確認した。1280px/320pxとも
horizontal overflow 0、console/page error 0。短命sessionは終了時にrevokeした。

当該配布条件の同意ボタンは押していないため、実LoRA weight downloadとsame-seed適用比較は
**NOT TESTED**。これはライセンス未同意を成功扱いしない境界である。2026-08-25のSD1.5/SDXL
実weight適用証跡は維持する。Release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.3

## Civitai LoRA/DreamShaper registration repair（2026-08-27）

利用者が実ControlDeck v0.9.3でCivitaiのLoRAと自動base DreamShaperを導入しようとすると、
「導入できない」と表示された。永続状態をread-only調査したところ、16:25の試行後も新規
model operationは0件で、custom catalogにもCivitai entryは残っていなかった。download開始前の
catalog parser rollbackである。

実Civitai exact revision `civitai/58390@62833`（LoRA）と`civitai/4384@128713`
（DreamShaper）をtemporary catalogへ組むと、最初に`model registry identity is invalid`を再現した。
source parserはCivitaiの数値versionを許可していたが、runtime descriptorだけ40桁Git commit固定だった。
`civitai/<number>` namespaceに限って1〜12桁の数値versionをimmutable runtime identityとして許可した。
generic repositoryの40-hex制約は維持する。

続いて単一SafeTensor配布の`required_files=[]`を拒否する不整合も再現した。weightsは従来どおり
非空、正のsize、公開SHA-256必須のまま、追加config fileだけ空を許可した。修正後、live Civitai
metadataから組んだtemporary registryはLoRA `62833 / lora.diffusers / SD 1.5`とDreamShaper
`128713 / diffusers.sdxl-single-file / SD 1.5`の2件をparseし、installed=falseとして返した。
重みdownloadは行っていない。

focused 6 filesはPASS。最終`./mf.sh test`は759 passed / warning 1件 / 51.13秒。
release bump後の再実行も759 passed / warning 1件 / 52.19秒。

Media Forge #154（exact head `240beeaccac8730d49b2af5bdf696f95a0f3dc07`、merge
`0965efe5f51daa7869a338c6ddcedcb2304c36d5`）とv0.9.4 release #155（exact head
`4e9629c`、merge/tag `9fc7793a1dc7e1a7c673aecc35dfad090ef25c98`）をmergeした。
bundleは30,959,024 bytes、SHA-256
`cec0920bb79dd0179965d2ecc6f220fbed477348c8a4c915b719ec77e5d59093`。公開Releaseを
別temporary directoryへ再取得してhash一致、manifest 275 bytes、signature 89 bytes、Ed25519
検証成功を確認した。

実ControlDeckの標準updateは16.68秒、max RSS 786,880 KiB、swap 0で成功した。
`version=0.9.4 / previous_version=0.9.3 / healthy`、`current=versions/0.9.4`、PID
181500/181506、127.0.0.1:9130、contract 2.0。v0.9.4 treeは31,226,582 bytes。

短命identityで実installed iframeを再確認した。1280pxで`civitai/58390`を検索・resolveし、
DreamShaper dependency、自動base本文、単一の「同意してダウンロード」を確認した。1280px/320px
ともhorizontal overflow 0、console/page error 0。sessionはrevokeした。同意ボタンは押しておらず、
07:00 UTC以降のmodel operationは0件、weight download 0。利用者がUIから再同意して初めて実取得を
開始する。Release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.4
証跡更新後のexact main gateは`./mf.sh test` 751 passed / warning 1件 / 54.52秒、`git diff --check` PASS。

## 使うモデルの常時表示と LoRA 互換ゲート（2026-08-28）

利用者から実機 v0.9.4 の「画像を作る」で、モデルが FLUX.2 Klein 4B のまま LORA 欄に
`civitai/16014 SD 1.5 lineart monochrome` が並び、未チェックなのに強さのスライダーが 1.00 で
出ている、という指摘を受けた。FLUX.2 Klein 4B は catalog 上 `supports_lora=false` で LoRA 系統も
持たないため、この組み合わせは成立しない。

まず「おまかせ」が実際に変わるのかを read-only で確認した。`routing/router.py` の `route()` は
capability → hardware backend → installed/local path → `state==available` かつ healthy →
`measured_vram_bytes <= free_vram_bytes` → 要求 domain 一致（fail-soft）→ `policy_rank[policy]` →
model_id の順で絞る。仕組みとしては変わるが、`worker_packs/image/models.json` で image の
`available` は `black-forest-labs/FLUX.2-klein-4B`（auto 10）と `segmind/SSD-1B`（auto 50）の
2 件だけである。さらに `custom_models.py` は利用者追加モデルへ
`policy_rank {"auto": 1000000}` を与え、`record_measurement()` は `state` を `available` へ上げても
`policy_rank` を更新しない。よって利用者が自分で入れたモデルは auto で選ばれ得ない。
「おまかせは事実上ほぼ固定」であり、選択を常時出すという利用者の条件が成立する。

frontend だけを変更した。使うモデルは常時見える単一 select（先頭が「おまかせ（自動で選ぶ）」、
以降は導入済み・healthy・`kind != lora` の image 土台）にした。LoRA 選択中に手動指定を黙って
auto へ落とす旧挙動をやめた（`jobs.py` の `_resolved_loras()` が既に系統不一致を
`lora_incompatible` で日本語表示する）。LoRA 一覧は `loraTargetFamily()` で絞り、土台指定時は
`supports_lora=false` なら候補 0 件、それ以外は `normalizeFamily` 一致のみ。強さのスライダーは
チェック済みの行にだけ描画し、未使用行は 1 列 grid にした。土台変更で載らなくなった選択は外し、
外した件数を 1 行で知らせる。backend/API/契約は変更していない。

実 Chrome（Chrome/151.0.7922.169、headless、CDP、390x844 mobile emulation）で
`http://127.0.0.1:9131/` の実 build を操作し、SD 1.5 / SDXL 1.0 の LoRA を catalog へ足して
実機の状況を再現した。観測は以下のとおり。

```text
おまかせ    : select=(auto) 非 hidden、候補 3（おまかせ / FLUX.2 Klein 4B / Segmind SSD-1B）
              LoRA 2 行とも未チェック・スライダー無し、payload {}
FLUX.2 指定 : payload {"model_policy":"manual","model_id":"black-forest-labs/FLUX.2-klein-4B"}
              LoRA 行 0 件、「FLUX.2 Klein 4B は LoRA を載せられません。導入済みの LoRA は
              SD 1.5 / SDXL 1.0 用です。」
SSD-1B 指定 : LoRA 行は SDXL 1.0 の 1 件のみ（SD 1.5 は消える）、未チェックでスライダー無し
チェック後  : 同じ行にスライダー出現、0.75 へ動かすと表示 0.75 /
              state.selectedLoras [{"model_id":"civitai/99999","weight":0.75}]
FLUX.2 へ戻す: 行 0 件、状況欄「選んだモデルに載せられない LoRA 1 件の選択を外しました。」
```

`./mf.sh test` は 761 passed / warning 1 件 / 58.62 秒、`git diff --check` PASS。
frontend contract に、モデルが常時見えて auto に戻れること、LoRA 選択が手動土台を捨てないこと、
強さが載る組み合わせにだけ出ることの 3 件を追加した。

実 ControlDeck（`/data1tb/ControlDeck/data/features/media-forge/versions/0.9.4`、PID 181506、
127.0.0.1:9130）へはまだ入れていない。実 LoRA weight を載せた生成での見た目差分は
**NOT TESTED**。導入済み instance での確認は release 時に行う。

## 機能切り替えのヘッダー移設と題名の重複解消（2026-08-28）

利用者から、MediaForge と SonicForge の両方で機能切り替えを「詳細」の左のヘッダーへ移し、
題名が二重に出ているので下側を消す、切り替えは「シンプルスマート」に、という指示を受けた。

`画像を作る / 動画を作る` の 2 ボタンは `#create-media-picker` として本文の先頭にあり、モバイルでは
横幅いっぱいの sticky で 1 行を丸ごと使っていた。これをヘッダー常駐の単一 select
（`.function-switch`、SonicForge と同じ形）に置き換え、`.modeswitch` の直前に置いた。試験中バッジは
select の項目に入れられないので、`video.*` が experimental のときだけ項目名を「動画を作る（試験中）」に
する。`#create-media-picker`・`.media-switch`・`.switch-badge` の CSS と、`create-media-image` /
`create-media-video` / `create-media-video-badge` の参照は消えた。backend/API/契約は変更していない。

題名は ControlDeck の host ヘッダーが同じ文字列を出すので二重に見える。DOM から消すと読み上げが
題名を失うため、`html:not([data-bridge="standalone"])` のときだけ視覚的に隠す（1x1 + `clip-path`）。
スタンドアロンでは従来どおり見える。モバイルでは幅を切り替えの側に回すため常に隠す。

実 Chrome（Chrome/151.0.7922.169、headless、CDP）で `MEDIA_FORGE_PORT=9131 ./mf.sh serve` の実 build を
1440x900 と 390x844 で操作した。観測は以下のとおり。

```text
1440 画像 : 切り替えは header 内、右端 1145 <= modeswitch 左端 1155、header 高 <= 72、横溢れ無し
1440 動画 : select=video、#app[data-create-media]=video、題名は standalone なので表示
390  画像 : 切り替え x=75 w=109、modeswitch x=194 w=132、1 行に収まり縦書きに潰れない、題名は非表示
390  動画 : 同上で value=video
埋め込み  : data-bridge="ready" にすると題名は 1x1 / clip-path: inset(50%)、DOM には残る
例外      : JavaScript 例外 0 件、console error は favicon.ico の 404 のみ
```

`./mf.sh test` は 761 passed。frontend contract は、切り替えが header 内で `.modeswitch` より左に
あること、`.function-switch select` が押せる高さと `appearance: none` を保つことを検証する。
実 ControlDeck 導入済み instance での確認は release 時に行う。

## 作る素材の切替をヘッダーの絵 2 択にする（2026-08-28）

v0.9.5 の時点では、作る素材の切替はヘッダーのプルダウン 1 個だった。利用者から
「動画を作る／画像を作るはアイコンにしてシンプル／詳細の左に置いてほしい」という指示があり、
`.mediaswitch` として `.modeswitch` と同じ丸みの分割ボタンへ置き換えた。選択肢が 2 つしか無く
どちらも一目で分かる形を持つため、開いてから選ぶ手数が 1 つ減る。絵は文字を持てないので、
試験中であることは印（`[data-experimental="true"]::after`）と `aria-label` / `title` の
両方で伝える。

実装中に、既存の総称ボタン規則
`button:not(.primary):not(.chip):not(.icon):not(.edit-action):not(.modeswitch button):not(#shell-nav button)`
が `.mediaswitch button` にも当たり、`:not()` 内の id によって特異度が勝つため押下中の
accent 背景が出ないことを実ブラウザの描画で見つけた。除外へ `.mediaswitch button` を足して直した。
テストは通ったままだったので、これは実機描画でしか出なかった不具合である。

実 Chrome（Chrome/151.0.7922.169、headless、CDP、390x844 mobile emulation）での観測。

```text
ヘッダー並び : H1 | ローカルのみ | grow | create-media-switch | modeswitch | nav-settings
              高さ 52px、horizontal overflow 0
当たり判定  : 画像 44x38 / 動画 44x38（狭幅 359px 以下は min-width 34px へ）
画像→動画    : aria-pressed が入れ替わり、createMedia=video、
              「どんな動画を作りますか？」、動画欄 hidden=false
動画→画像    : 元へ戻る。overflow は常に 0
取り込み中   : setHostBusy(true) で 2 つとも disabled、押しても素材は変わらない
```

`./mf.sh test` 761 passed / 2 warnings / 59.69 秒、`git diff --check` PASS。

host header の 詳細 ボタンと 2 段ヘッダーは Media Forge 側では消せない。実体は
ControlDeck の `app/frontend/src/features/addons/EmbeddedAddonView.tsx:403-408` にある
埋め込み add-on 共通ヘッダーで、`{title}` と `{addon.name} · {routePath}` に加えて
`/settings?extension=<id>` へ飛ぶ 詳細 ボタンを常に描く。add-on 側から header へ
操作を出す拡張点は contract 2.0 に存在しない。**NOT IMPLEMENTED**。

## v0.9.5 の署名リリースと実 ControlDeck 反映（2026-08-28）

Media Forge #157（exact head `891601f`、merge `d7fae4f`）、#158（`7d2305e` /
`1a97074`）、#159（`8430a4d` `e42df1f` / `d9aa5e1`）、#160（`4823347` /
`e8fb0d1`）を main へ merge した。#160 は自分の `git add -A` が `dist/` を巻き込み、
30MB の tarball と署名が main まで入った件の後始末である。`dist/` を追跡から外し
`.gitignore` へ足した。履歴の blob は残す（push 済み main の書き換えは割に合わない）。

先に tag と本文だけ作った asset 0 件の v0.9.5 は、#159 / #160 を含まないため削除し、
`e8fb0d1dfb38f900b5f7477bb80fcf09d8b94213` から作り直した。bundle は 30,961,873 bytes、
SHA-256 `167b1b924b4f65e798d173c5de5d1658783660213e994a18099c5f1342645f2a`。
manifest 275 bytes、signature 89 bytes。公開 Release を別 directory へ再取得して
`sha256sum -c` 一致、manifest の feature_id / version / platform / architecture /
size_bytes / sha256 が bundle と一致することを確認した。

実 ControlDeck の標準 `./deck.sh feature update media-forge` は 11.88 秒、max RSS
784,320 KiB、swap 0、exit 0 で成功した。`version=0.9.5 / previous_version=0.9.4 /
healthy`、`current` は `versions/0.9.5`、rollback 用に `versions/0.9.4` を保持。実 process は
PID 726119/726123 で 726123 が 127.0.0.1:9130 を listen し、health は healthy /
contract 2.0。v0.9.5 version tree は 31,229,870 bytes。

実 installed instance（127.0.0.1:9130）を実 Chrome（390x844）で操作した観測。

```text
ヘッダー  : H1 | ローカルのみ | grow | create-media-switch | modeswitch | nav-settings
           高さ 52px、絵 2 択は表示モードの左、当たり判定 40x32、horizontal overflow 0
           動画アイコン押下で aria-pressed 入替・「どんな動画を作りますか？」・動画欄表示
使うモデル: 非 hidden。おまかせ + 導入済み 3 件
           （FLUX.2 Klein 4B / Segmind SSD-1B / stabilityai SDXL base）
LoRA      : 導入済みは civitai/16014（SD 1.5）1 件
  おまかせ            → 行 1 件・未チェック・スライダー無し
  FLUX.2 Klein 4B     → 行 0 件「LoRA を載せられません。導入済みの LoRA は SD 1.5 用です。」
  Segmind SSD-1B      → 行 0 件「（SDXL 1.0）に載せられる LoRA がありません。」
  stabilityai SDXL    → 行 0 件「LoRA を載せられません。」
  おまかせでチェック  → 同じ行にスライダー、selectedLoras [{civitai/16014, 1}]
```

利用者のスクリーンショットにあった「FLUX.2 Klein 4B なのに SD 1.5 LoRA と強さの
スライダーが出ている」状態は、実機で再現しなくなった。

この確認中に、今回の slice の外にある実データの問題を 2 件観測した。どちらも未修正である。

```text
1. LoRA civitai/16014 が要る SD 1.5 の土台 civitai/4384（DreamShaper）は healthy=false で、
   土台の一覧に出ない。state も experimental なので auto でも選ばれない。つまり実機では
   この LoRA を載せられる土台が 1 つも無い。おまかせでチェックはできるが、
   生成まで進めば backend が拒否する見込みである（実行は未実施）。
2. loraCandidates() は installed だけを見て healthy を見ないため、healthy=false の
   civitai/16014 が候補に出ている。土台側は healthy で絞っており、扱いが揃っていない。
```

利用者が追加した `stabilityai/stable-diffusion-xl-base-1.0` は base_model が SDXL 1.0 でも
`supports_lora=false` として登録されており、LoRA を載せられない。custom model の既定値である。

host header の 詳細 削除と 2 段ヘッダーの 1 行化は利用者が別タスクで進めるため、
この slice では **NOT IMPLEMENTED** のままとする。

## LoRA が連れてきた土台が使えるようになるまで（2026-08-28）

利用者から「生成まで進んでバックエンドで断られるのは嫌なので、必要な土台は
ダウンロード時に自動で導入して動くようにしてほしい」という指示があった。実機の
`civitai/16014`（SD 1.5 LoRA）は導入済みだが、載せられる土台が 1 つも無い状態だった。

実機の永続状態を read-only で調べ、原因を特定した。

```text
model_operations   civitai/16014 install ready 18,986,312/18,986,312   22:13:43→22:13:47
                   civitai/4384  install ready 2,132,625,894/同        22:13:43→22:17:03
                   civitai/4384 の evaluate 操作は 0 件
custom-models.json civitai/4384  state=experimental / confidence=low
```

土台の自動ダウンロード自体は動いていた。止まっていたのは、その次の自動評価である。
`ModelEvaluator.evaluate()` は operation を作る前に `_preflight()` を呼ぶが、
`_preflight()` は Wan / Hunyuan / CogVideoX / VACE / H3 の 5 preset しか知らず、
それ以外は `model_evaluation_unsupported` を送出する。一方 `_run()` は画像モデルを
`_preflight()` の**前**に `_run_image_evaluation()` へ振り分けていた。判定が 2 か所に
分かれて食い違っていたため、画像モデルは「評価を始めることだけができない」。
operation 行すら作られないので、画面にも記録にも何も残らなかった。
`evaluate_installed_lora_base` はその `ModelOperationError` を握り潰していた。

`stabilityai/stable-diffusion-xl-base-1.0` が measured なのは、UI ではなく
`scripts/verify_installed_models.py`（CLI）で測ったためである。UI からの画像モデル
評価は一度も成立していなかった。

直したのは 3 点である。

```text
1. 画像評価かどうかの判定を _runs_as_image_evaluation() 1 か所に集約し、
   evaluate() と _run() の両方がそれを使う。画像モデルは _preflight() を通さない
2. 追従を in-process task 頼みにしない。unmeasured_lora_bases() が「導入済み LoRA が
   要る系統で、まだ measured でない土台」を挙げ、models.list のたびに評価を始める。
   再起動で task が消えても次に開いたときに追いつく
3. 失敗を握り潰さない。始められなかった評価は理由付きで log へ出す。
   一度 failed になった評価は自動で繰り返さず、利用者が押し直すまで再開しない
```

`./mf.sh test` は 765 passed / 1 warning / 68.32 秒（新規 4 件）、`git diff --check` PASS。
新規テストは修正を戻すと `model_evaluation_unsupported` で落ちることを確認済みである。

v0.9.6 を実機へ入れた直後、追従の掛け先を間違えていたことが分かった。帳尻合わせを
bridge の `models.list` にだけ置いていたが、埋め込みの boot は個別 method を呼ばず
集約の `workspace.session` を通る（`models.list` を呼ぶのは詳細モードの再描画だけ）。
つまり ControlDeck の中では一度も走らない。15 分待っても評価は始まらず、実機ログにも
`/ws` 接続が無かった。`session_snapshot()` の `models` を作るところへ移し、
そこを外すと落ちるテストを足した。766 passed / 1 warning / 61.45 秒。

## 実機が出した次の 2 段（2026-08-28）

v0.9.7 を入れた後、利用者が画面を開き、実機ログに帳尻合わせの実行と、その失敗理由が出た。

```text
INFO:     WebSocket /ws [accepted]
WARNING:  could not start the base evaluation for civitai/4384: model_not_found
```

握り潰しをやめたことで理由が出た。追従の掛け先（session_snapshot）は正しく動いている。
止まっていたのは、同じ種類のずれの 3 段目である。`_image_candidates()` は custom を含む
`registry_loader` を見るのに、`_model()` は shipped manifest しか見ないため、
`civitai/4384` を「信頼カタログに無い」として拒否していた。`_model()` に custom loader への
フォールバックを足した。

同じ時刻に利用者が実行した生成 job も失敗していた。

```text
job_e4a1b7cf6ab544978f7e25ed6069deda  host_managed=1  failed
  created 2026-08-28T04:32:37Z / updated 04:34:10Z
  model_policy=auto  loras=[{civitai/16014, weight 1}]
  intent  "ロボット. indoor. standing; idle; front-facing; …"（演出が動いた＝LLMを使った）
  error   worker_crash / worker exited with code 2
```

経路はこうである。演出で LLM がロードされる → LoRA を選んでいるので routing は SD 1.5 系に
絞る → SD 1.5 の土台は `civitai/4384` だけで未計測、`available` 0 件 → `_select_real_model()`
が例外ではなく `None` を返す（本物のモデルが 1 つも無い開発環境向けのフォールバック）→
`selected is None` なので `_release_host_ai()` が飛ばされ、**AI ターンの終了宣言が行われない**
→ model を持たない payload でワーカーが起動し exit code 2 で落ちる。

「LLM が降りない」と「理由の分からない worker_crash」は同じ 1 つの分岐から出ていた。
LoRA を選んでいるのに載せる先が無い場合は、既にある `lora_base_unavailable`
（「選んだ LoRA に互換する評価済みの土台がありません」）で断るようにした。LoRA を
選んでいない場合の `None` は開発経路として残す。

AI ターンの解放方針そのもの（使ったら必ず閉じるか、VRAM が要るときだけ要求するか）は
利用者の判断で**現状維持**とした。モデルの寿命は ControlDeck が持つ、という境界を変えない。

過去の成功 job では解放は正しく効いている（`released=True reason=released
freed_bytes=16,464,440,224`）。

`./mf.sh test` は 768 passed / 1 warning / 66.15 秒（新規 2 件）、`git diff --check` PASS。
どちらの新規テストも、修正を戻すと `model_not_found` と `DID NOT RAISE` で落ちる。


## 落とし終えたものを、人が開くまで放置しない（2026-08-28）

利用者が `civitai/4384` を削除し、HuggingFace の `Lykon/DreamShaper` を入れ直した。
download は 05:47:29→05:56:22 の 8 分 53 秒、5,481,450,296 bytes で ready になった。
系統は落とした `model_index.json` の pipeline class（`StableDiffusionPipeline`）から
`SD 1.5` に解決され、LoRA `civitai/16014` を載せられる土台がやっと揃った。
v0.9.8 の修正も効いており、評価候補に `Lykon/DreamShaper` が載る。

```text
評価できる候補 : ["unsloth/MiniMax-H3-GGUF", "Lykon/DreamShaper"]
導入済みLoRAの系統: {"sd15"}
評価待ちの土台  : ["Lykon/DreamShaper"]
```

しかし評価は始まらなかった。帳尻合わせは workspace の boot でしか走らず、download が
終わった 05:56 以降、誰も画面を開いていなかったためである。追従を LoRA 依存の経路だけに
掛けていたので、checkpoint を単体で入れたときは何も起きない。落とし終えたものが、人が
開くまで使えないまま残る。

`follow_install()` に寄せ、`models.install` からも同じ追従に乗せた。依存の経路と 2 つ
持たない。boot での帳尻合わせは、再起動を跨いだ取りこぼしの受け皿として残す。

`./mf.sh test` は 769 passed / 1 warning / 63.09 秒（新規 1 件）、`git diff --check` PASS。

途中、利用者から「ControlDeck に接続できない」との報告があった。実機を確認すると
ControlDeck 本体（PID 851488、15:24:47 起動）は正常で、`/health` は LAN 192.168.68.200 /
192.168.68.67 と Tailscale 100.82.8.44 のいずれからも 200 を返した。原因は iPhone 側の
Tailscale が offline（`last seen 5m ago`、relay "tok" 経由）だったことである。
Media Forge 側の変更とは無関係で、13:51:52 起動の 0.9.8 process は稼働を続けていた。

## 載せられるかを宣言ではなく実際で決める（2026-08-28）

`Lykon/DreamShaper` の自動評価は動いた。06:48:42→06:48:56 の 14 秒で ready、
execution peak VRAM 3,939,438,592 bytes、runtime 13.0 秒、512x512、出力 325,726 bytes。
記録後は `state=available / healthy=true / measured_vram_bytes=5,013,180,416` となり、
「使うモデル」の候補が 3 件から 4 件へ増えた。

それでも LoRA は載せられなかった。実 Chrome（installed 127.0.0.1:9130、390x844）で
DreamShaper を指定すると LoRA 行は 0 件、説明は
「Lykon/DreamShaper は LoRA を載せられません。導入済みの LoRA は SD 1.5 用です。」だった。

原因は `custom_models.py:1205` が、利用者の追加したモデルを常に
`"supports_lora": False` で登録することである。一方 backend はこの旗を一切見ておらず、
`_resolved_loras()` は系統の一致だけで判定する（`jobs.py` / `router.py` に
`supports_lora` の参照は 0 件）。つまり旗は画面専用のゲートで、自分で足した
checkpoint は worker なら載せられるのに、画面が必ず隠していた。

載る条件は「diffusers の checkpoint であること」と「系統が分かること」の 2 つで、
これは導入後に repository 自身を読めば決まる。`_observed_defaults()` で
`base_model` を読む場所に寄せ、立てる方向にだけ動かすようにした。系統を持たない
FLUX.2 Klein 4B は false のまま残り、宣言で立っている SSD-1B は触らない。

`./mf.sh test` は 769 passed / 1 warning / 53.30 秒（新規 1 件）、`git diff --check` PASS。

## 打ち切りの予算が枚数を数えていなかった（2026-08-28）

利用者から「そんなに長い時間動かしていないのに失敗した」との報告。実機の job を見ると、
同じ設定が通ったり落ちたりしていた。

```text
job_8838a3c7  succeeded  80.0s   count=4 1024x1024 lora あり
job_d1f45685  failed     103.4s  count=4 1024x1024 lora あり  worker_timeout
job_9a482525  failed     106.5s  count=4 1024x768  lora あり  worker_timeout
```

`jobs.py` の打ち切りは `max(worker_timeout_sec, measured_runtime_sec * 3 + 30)` で、
`measured_runtime_sec` は評価で 1 枚だけ作ったときの値である（DreamShaper は 13.0 秒）。
つまり 4 枚頼まれていても予算は 13*3+30 = 69 秒のままで、モデルが遅いのではなく
枚数のぶんだけ落ちていた。ぎりぎり通ったのが 80.0 秒の 1 件である。

最初は枚数を掛けて予算を広げたが、利用者から「そんなにギリギリでなくてよい。生成器が
動いているかを見て、定期的に数え直す方がよいのでは」との指摘があり、そちらへ変えた。
総時間の予測は、枚数も解像度も要求ごとに変わる以上どう組んでも外れる。見るべきは
止まっていないかである。

`_communicate_while_progressing()` が、出力先の枚数が増えている間は待ち、増えなくなって
からの時間だけを数える。猶予は `max(worker_timeout_sec, measured_runtime_sec * 3 + 30)`
のままで、これは「総時間」ではなく「1 枚ぶんが止まったと判断するまで」の意味になった。
最初の 1 猶予はモデルの読み込みに使われる。枚数ぶん予算を積む作りと違い、本当に固まった
worker には 1 猶予で気づける。

成功した job の実測も記録しておく。4 枚とも 512x512 で出ており、SD 1.5 の native へ
正しく寄せられている（要求は 1024x1024）。`Lykon/DreamShaper` に `civitai/16014` が
載り、provenance に model_id と LoRA が残っている。**LoRA は実機で動いた。**

## ヘッダーの寄せ方（2026-08-28）

利用者の指示により、作る素材の切り替えと表示モードの切り替えを左へ、設定だけを右端へ
逃がした。余白（`.grow`）を 2 つの切り替えの後ろへ移すだけで済む。実 Chrome（390x844）で
左端からの余白 16px、右端までの余白 16px、horizontal overflow 0 を確認した。

`./mf.sh test` は 771 passed / 1 warning / 62.93 秒（新規 2 件）、`git diff --check` PASS。

## G7 の不採用理由を実測で訂正する（2026-08-28〜29）

利用者から「Reddit などで ROCm の動画生成の相場を調べてほしい。2 分で 5 フレームは
普通ではないか」との指摘を受けた。調べたところ相場は次のとおりで、指摘は正しかった。

```text
AMD Radeon AI PRO R9700 (32GB, gfx1201) / ROCm 7.2
  Wan 2.2 i2v 1024x576 81 frames        初回 約 300 秒（2 回目以降は既知の不具合で 45 分超）
RX 7900 XTX
  Wan 2.1 1.3B 832x480 25 steps         約 24 分
  14B FP8 480P 81 frames 30 steps       20 分弱（TeaCache + torch.compile 後）
```

出典: ComfyUI issue #12672、Wan2.1-T2V-1.3B の AMD support discussion。

そのうえで V1 をやり直した。まず判明したのは、DEFERRED の根拠だった「111.8 秒で 5 フレーム」
が `smoke` プリセット（256x256・**1 step**）の値で、生成性能を測っていなかったことである。
実用プリセットは一度も走っていなかった。

実用プリセット（512x320・33 frames・30 steps）を RAM オフロード可の条件で完走させた。

```text
elapsed 3408.2s（56.8 分） / generate 3401.3s / load 6.1s
peak VRAM 18.61 GB / 34.2 GB      max RSS 11.0 GB
swap in +127 MB / out +96 MB
出力 h264 512x320 33 frames 2.06 秒 54,568 B / デコード正常 / exit 0
```

**メモリは合格である。** 不採用理由の半分だった zero-swap は、GPU が空いた状態では
実質的に満たしている。以前の測定は GPU に 26 GB が常駐した状態のものだった可能性が高い。

残る 56.8 分の内訳を切り分けた。仮説を 4 つ潰してから、pipeline 内部を計測して特定した。

```text
CPU オフロード on/off        107.9s → 102.2s        影響なし
ステップ 1 → 3              +0.4 秒                0.19 秒/step。健全
VAE タイリング on/off        101.68 / 101.71s       影響なし（256x256 では発動しない。比較は無効）
同一 process で 2・3 回目     101.774 / 101.591 / 101.710s   初回限定の支度ではない

内部計測（256x256 5 frames 1 step、float32、オフロードなし）
  vae.encode           2 回  100.21s   最遅 50.12s   ← 固定費のほぼ全部
  vae.decode           1 回    1.20s
  transformer.forward  2 回    0.22s   ← ノイズ除去は速い
```

VAE を bfloat16 にすると悪化した（encode 239.50s / decode 22.22s）。ROCm/RDNA4 では
この 3D 畳み込みは float32 の方が速い経路に乗る。現状の float32 は正しい。

**符号化 100.2 秒に対して復号 1.2 秒**という 83 倍の非対称が残る。そしてこの符号化は
VACE 固有である。VACE は参照映像とマスクを条件に取るモデルなので、生成前にそれらを
潜在空間へ通す（だから 2 回）。素の text-to-video にはこの処理が無い。

公開している文言は「文章から短い動画を作ります」であり、主用途は T2V である。条件付け
専用の重い前処理を持つ VACE を評価候補の中心に据えていたことが、そもそもの取り違えだった。
ノイズ除去そのものは 0.22 秒で、モデルもハードも問題を示していない。

したがって G7 の DEFERRED 理由「実用 latency を満たさない」は、実測に照らして正しくない。
Wan 2.2 TI2V-5B での再計測へ進む。

probe には計測手段を追加した（`--offload` / `--vae-memory` / `--vae-dtype` / `--steps` /
`--repeat` / `--trace`）。既定は従来の挙動のままである。

## ライブラリで動画を見られるようにする（2026-08-29）

ビューアは `<img>` しか持たず、動画 asset を開いても再生できなかった。`<video>` を足し、
mime が `video/` のときはそちらへ渡す。閉じ方は閉じるボタン・Esc・背景と複数あるので、
要素の `close` イベントで停止と解放を行い、押した場所ごとの止め忘れを作らない。

## V1 合格 — Wan 2.1 T2V 1.3B（2026-08-29）

VACE の 100 秒が条件付け符号化であるという見立てを、条件付けを持たない候補で確かめた。
`Wan-AI/Wan2.1-T2V-1.3B-Diffusers` の固定 revision `0fad780a534b6463e45facd96134c9f345acfa5b`
（Apache-2.0）を利用者の明示同意のうえ取得した（2,514.9 秒、27 GB、incomplete 0）。
preflight が既に pin していた revision をそのまま使い、専用 runtime
`runtimes/wan21-1.3b-probe`（torch 2.10.0+rocm7.2.1 / diffusers 0.40.0 / ftfy 6.3.1）で測った。

同一条件（256x256・5 frames・1 step）の比較。

```text
                       VACE            T2V
vae.encode        2 回 100.21s        0 回      ← 条件付けが無い
vae.decode        1 回   1.20s        1 回 1.23s
transformer       2 回   0.22s        2 回 0.39s
generate 合計         101.78s             3.87s
```

`vae.encode` は 1 度も呼ばれない。101.7 秒の固定費は VACE 固有の条件付けであった。

実用プリセット（512x320・33 frames・30 steps）。

```text
generate 144.64s（2.4 分）   load 162.77s（コールド、process 1 回きり）
wall 321.05s（5.4 分、mp4 書き出し込み）   max RSS 24,699,984 KiB
  transformer.forward  60 回   24.16s   0.8 秒/step
  vae.decode            1 回  118.20s   ← 生成の 82%。現在の最大費目
  vae.encode            0 回
出力 h264 512x320 33 frames 2.06 秒 29,629 B / デコード正常 / exit 0
swap out +1,226,210 ページ (4.68 GB) / in +1,142,815 ページ (4.36 GB)
```

同じ R9700 の公開報告は 1024x576・81 frames で約 300 秒であり、今回の 512x320・33 frames
生成 144.6 秒／全体 321 秒は同等の水準である。**latency は相場どおりで、不採用の理由に
ならない。** G7 の DEFERRED 判定は、評価候補の取り違え（T2V の用途に対して条件付け
専用の VACE を中心に据えた）と、性能を測っていない数字（smoke = 1 step）に基づいていた。

正直に残す点が 2 つある。swap は 4.68 GB 書き出しており、max RSS 24.7 GB は本機 30 GB に
対して小さくない。同時に重いものを動かせば影響が出る。もう 1 つは VAE 復号が 118.2 秒で
生成の 82% を占めることで、今回はタイリングを切って測った。ここは詰める余地がある。

なお background で起動した probe は 2 回とも読み込み中に停止された（利用者の操作では
ないことを確認済み、OOM の記録は権限の都合で未確認）。前景では完走する。原因は未特定。

## 生成した動画をライブラリへ出す道は、まだ無い（2026-08-29）

利用者の「生成した動画はライブラリから見れるようにして」に対し、ビューアは `<video>` を
持つようにした。しかしその先が繋がっていない。

```text
asset import   PNG / JPEG / GLB のみ。video/mp4 は受け付けない（asset_import.py）
asset 登録     operation ごとに image/png か application/zip を直書き（jobs.py）
thumbnail      is_thumbnailable は image/png,jpeg,webp,application/zip のみ
```

つまり動画 asset を作る経路が core に無く、V1 で作った mp4 を見せる手段が現時点で存在
しない。これは G7 V2（本番実行）の範囲であり、V1 合格を受けて次に作るものである。

## V2-a — 動画 asset をライブラリが扱えるようにする（2026-08-29）

V1 合格を受けて、動画を一覧と拡大表示で扱える土台を作った。生成経路（V2-b）はまだ無いので、
この段階では「動画 asset があれば正しく出せる」ところまでである。

```text
thumbnails   video/mp4 を is_thumbnailable へ追加し、1 枚目を取り出して静止画の経路に乗せる
             worker の FFmpeg 実装は import せず、system binary を配列引数・timeout 20 秒・
             使い捨て directory の中だけで呼ぶ。壊れた入力は枠を作らず ThumbnailError
library      preview_kind に "video" を足し、duration_sec / frame_rate を entry へ出す
frontend     カードに ▶ と尺の印。一覧では自動再生しない。viewer は video 要素で再生し、
             dialog の close で停止・解放する（閉じ方が 3 通りあるため押下箇所ごとに書かない）
```

実クリップでの確認: V1 で作った 512x320 33 frames 2.06 秒 29,629 B の mp4 から、
256x160 の webp ポスターを 2,154 B で生成できた。

`./mf.sh test` は 775 passed / 1 warning / 64.82 秒（新規 2 件）、`git diff --check` PASS。

## V2-b（1/2）— 動画 worker（2026-08-29）

`worker_packs/video/worker.py` を追加した。core はこの実装を import せず、やり取りは
画像 worker と同じ行ごとの JSON である（`ok` / `error`、`resource_oom` の区別、
`MAX_MESSAGE_BYTES`）。

実測にもとづく既定を worker へ固定した。

```text
VAE dtype        float32。bfloat16 は符号化 2.4 倍・復号 18 倍の悪化を実測
device 配置      収まる限り退避しない。退避しても生成は 5% しか変わらず読み込みが倍
pipeline 保持    process が生きている間 1 度きり。コールド 162.8 秒を要求ごとに払わない
出力             frames -> ffmpeg で組み立て -> ffmpeg.normalize -> probe で検証
                 公開する形は正規化済みの 1 つに揃え、生成器の書き出しをそのまま出さない
```

外から来る値は信じない。model path は境界内に限り、adapter は既知のものだけ、
寸法は偶数かつ 16..1024、frames 5..161、steps 1..50、fps 1..120、intent は非空。
境界の外や範囲外は GPU を動かす前に断る。

test は GPU を要さない部分（境界・検証・規約の一致）で 10 件。生成そのものは V1 の実測で
裏付けている。`./mf.sh test` は 785 passed / 1 warning / 66.88 秒。

残りは core 側である。`video.generate` の実行経路（worker 起動・phase・asset 登録）と
routing / capability がまだ無い。

## V2-b（2/2）と V2-c — core 側の実行経路と採用（2026-08-29）

core に `video.generate` の経路を作り、capability の固定をやめた。

```text
capability     video.text_to_video を実態から出す。runtime が無ければ
               video_runtime_not_installed、モデルが無ければ model_not_installed。
               入力画像から動かす経路は worker に無いので image_to_video は据置
runtime        画像と別 venv。MEDIA_FORGE_VIDEO_RUNTIME_PYTHON で差し替えられる。
               同じ venv に載せると片方の pin を動かしたときもう片方が黙って壊れる
worker 選択    adapter が動画のものなら動画 worker を起動する
asset 登録     _register_video_outputs。画像側の検証（brief defect、意味レビュー）は
               絵を見る前提なので当てない。形の検証だけを行い、中身が動画かは
               worker の probe が見ている。video/mp4 / 寸法 / 尺 / fps を asset へ残す
catalog        Wan-AI/Wan2.1-T2V-1.3B-Diffusers を available / managed / measured へ。
               既存 entry を置き換えではなくその場で更新した（revision と weight hash は
               取得済みのものと一致）。measurements は実測値をそのまま入れた
```

旧方針を守っていた test 5 件を更新した。守る値は残し、「動画候補は routable にしない」
という前提だけを外した。available な adapter は画像 worker が実装しているものに限る、
という不変条件は、実装している worker を全部足す形へ広げた。

重みは同一 filesystem 上のハードリンクで実機の置き場へ配置した（27 GB、空き容量の変化なし）。

`./mf.sh test` は 785 passed / 1 warning / 63.70 秒、`git diff --check` PASS。

## V2-c / V2-d — 実機で video.generate が通るまで（2026-08-29）

0.10.0 を入れた直後は `video_runtime_not_installed` だった。bundle launcher が画像 runtime しか
feature data へ向けておらず、installed な Media Forge が repository の中を探していた。
`MEDIA_FORGE_VIDEO_RUNTIME_PYTHON` を feature data 配下（`runtimes/wan21-t2v`）へ向け、
runtime と重みを同一 filesystem のハードリンクで配置した（venv は複製せず、
`sys.prefix` が配置先を指すことと torch 2.10.0+rocm7.2.1 / diffusers 0.40.0 / ftfy 6.3.1 の
import を実機で確認）。

0.10.1 で capability が変わった。

```text
video.text_to_video  -> available / implementation local / confidence measured / local_only
video.image_to_video -> unavailable / video_runtime_not_adopted（worker に経路が無い）
```

次に job を投げると `capability_unavailable` で落ちた。dispatcher が
`image.generate` / `image.edit` / `asset.pack` の 3 つしか知らず、runtime が揃っていても
video を弾いていた。通すようにしたうえで、動かせる動画モデルが無いときは fake worker へ
落とさず理由を名指しするようにした（落とすと「PNG しか出せない」と言われ、何が足りないのか
分からなくなる。LoRA で直したのと同じ形である）。0.10.2 で反映。

REST の `/api/v1/jobs` から投げた job は `host_lease_required` で落ちる。これは正しい。
GPU job は ControlDeck の lease を通す必要があり（AGENTS.md 規約 8）、workspace 経由の
identity を持つ経路だけが実行できる。画面からの実行は **NOT TESTED**。

画面側の条件は満たしている。`videoCapabilityUsable()` は available / experimental を通し、
作るボタンは `video && !usable` のときだけ無効になるので、いまは押せる状態にある。

installed v0.10.2 / healthy / contract 2.0。`./mf.sh test` 785 passed。

## 画面から動画を作ると即失敗した（2026-08-29）

実機で 2 件、0.9〜1.2 秒で `worker_error: width must be an integer` として落ちた
（job_6bfb298d / job_d92ab004）。画面は `constraints: {}` を送っており、これは正しい。
どのモデルが選ばれるか画面は知らないのだから、公開要求に寸法を持ち込ませない設計である。
埋める場所を worker に求めていたのが誤りだった。worker 側に既定を置くと、モデルを増やす
たびにその固定値が全部へ掛かる。

`_resolved_video_request()` を core に置き、選んだモデルの実測既定から埋めるようにした。
画像側の `_resolved_request()` と同じ考え方である。指定された値は動かさない。正規化は
偶数しか受けないので、奇数は生成の前に落とす。catalog には実測した設定
（native 512x320 / steps 30）を入れ、frames 33 / fps 16 は 2.06 秒のクリップとして
144.6 秒で作れた設定を core の既定に置いた。

`./mf.sh test` 786 passed。

## 受理が 10 秒で切れていた（2026-08-29〜30）

寸法の修正後、画面からの動画 job は `width must be an integer` を出さなくなった。次に
出たのは 22〜27 秒後の `host_unreachable: ControlDeck Host API is unreachable`
（job_65751f36 / job_e2b2afa2）。ControlDeck 本体は稼働しており、`/health` も
`/api/v1/health` も 200 を返していた。AI ターンの解放も成功している。

原因は 2 つ重なっていた。

```text
1. host client の共通 timeout が 10 秒。受理は VRAM を空けることを含むので足りない。
   実測では 16.5 GB の常駐を降ろしてからでないと通らない要求がある
2. httpx のあらゆる失敗を "ControlDeck Host API is unreachable" の 1 文へ潰していた。
   timeout なのか接続不能なのかが区別できず、切り分けに 1 往復ぶん余計にかかった
```

受理の POST だけ 120 秒へ広げた。待機そのものは `resource_status` の速い poll が
引き受けるので、長く待つのは最初の 1 度きりである。エラーは例外の型と本文を添えるように
した。これで次に落ちたときは理由が残る。

`./mf.sh test` 787 passed。

## 動画の設定を簡易にも詳細にも置く（2026-08-30）

利用者から「動画は作れたし再生もできた。ただし簡易・詳細とも設定項目が一切なかった。
特にモデル選択と画質、時間設定は両方でできるように」との指摘。作れるだけで、どう作るかを
選べない状態だった。段階開示は「簡単にするために削る」ことではない。

```text
使うモデル   媒体で一覧が変わる。画像は FLUX.2 / SSD-1B、動画は Wan 2.1 T2V 1.3B。
             以前は data-image-create で画像専用だったため、動画では選べなかった
画質 (L1)    標準 512x320 / 横長 640x384 / 正方形 448x448。数値ではなく意味で選ばせる
長さ (L1)    2秒 33 / 3秒 49 / 5秒 81 フレーム
目安時間(L1) 実測 144.64 秒（512x320・33 フレーム・30 歩）からの外挿。面積は注意機構に
             二乗で効き、長さはフレーム数に比例する。初回のモデル読み込みは別に明示する
詳細 (L3)    歩数 / ガイダンス / フレーム数 / fps / 打ち消し語。簡易の選択を奪わない。
             指定したものだけを送り、残りは選ばれたモデルの実測既定で埋まる
```

実 Chrome（390x844）での観測。

```text
画像        モデル候補 3 件（おまかせ + FLUX.2 + SSD-1B）、動画設定は hidden
動画へ切替  モデル候補 2 件（おまかせ + Wan 2.1 T2V 1.3B）、画質・長さが出る
            目安「512×320 / 33 フレーム。作るのにおよそ 2 分かかります。」
横長 + 5秒  目安「640×384 / 81 フレーム。作るのにおよそ 13 分かかります。」
            送信 {"width": 640, "height": 384, "frames": 81}
詳細モード  歩数・ガイダンス・フレーム数・fps・打ち消し語が出る
```

面積を 1.5 倍・長さを 2.45 倍にすると目安が 2 分から 13 分へ伸びる。二乗で効くことが
画面の数字に出ている。押してから知らせない。

`./mf.sh test` 789 passed / 1 warning / 61.34 秒（新規 2 件）、`git diff --check` PASS。

## 評価は終わっていたが、何も変わっていなかった（2026-08-30）

利用者から「MiniMax の評価ボタンを押しても評価が終わらない。ブラウザを閉じたからか」との
問い合わせ。実機を見ると評価は**成功して終わっていた**。

```text
modelop_fc571456  unsloth/MiniMax-H3-GGUF  evaluate  ready
  03:37:45 → 03:40:15（149.28 秒）  host_job=2cfdf9cb277f
  peak VRAM 14,763,892,736 B / peak RSS 23,699,308,544 B / process swap 0
  出力 640x384 vp8 0.167 秒 122,118 B
```

ブラウザを閉じたことは関係ない。job も model operation も server 側の durable な記録で、
閉じても走り続ける。

止まっていたのは記録の方だった。`record_measurement` は `_run_image_evaluation` にしか
無く、MiniMax のような native 経路は結果を operation に残すだけでモデルの計測値を
更新しない。150 秒かけて測っても `measurement_confidence` は low、
`measured_vram_bytes` は None のまま。画面は何も変わらないので「終わらない」ように見える。

画像経路には既に正しい注記があった。「測れたのに書き残せないなら、成功と言っては
いけない。次に開いたとき、また未計測に戻っている」。同じことが native 経路で起きていた。

```text
native 経路      _record_native_measurement() を完了直前に呼ぶ。書き残せなくても
                 評価そのものは成功しているので job は失敗させない
出荷モデル       出荷 manifest は実行時に書き換えない。測った値は runtime 側の
                 measurements.json へ重ねる。ModelRegistry.load が上から被せる
state           動かさない。測ることと使ってよいと決めることは別で、測っただけで
                 routing に載るなら評価を押すことが採用を意味してしまう
読む側          custom_models.overlay() が追加分と測定値を 1 組で返す。測定値だけ
                 別経路で渡すと、渡し忘れた読み手が「未計測」と言い続ける
```

`./mf.sh test` 791 passed / 1 warning / 53.10 秒（新規 2 件）、`git diff --check` PASS。

## workspace の配信が無圧縮だった（2026-08-30）

利用者から「Media Forge への接続にめっちゃ時間がかかる。軽量化してほしい」との指摘。
測ると、workspace の文書だけが無圧縮で出ていた。

```text
配信          356,733 B / content-encoding なし / cache-control: no-store
gzip -9 相当   91,349 B（74% 減）
内訳          <script> 253,108 B（app.js） / <style> 48,623 B / markup 他
```

workspace は markup と style と script を 1 応答へ畳んで返す作りなので、この 1 本が
そのまま接続の待ち時間になる。手元は 15 ms でも、実機は Tailscale の relay 経由である
（`relay "tok"` を 2026-08-28 に観測済み）。

WebSocket は無関係だった。uvicorn の `ws_per_message_deflate` が既定 True で、boot の
session snapshot は既に圧縮されている。無圧縮で残っていたのは HTTP の文書だけである。

`GZipMiddleware(minimum_size=1024)` を入れた。実測。

```text
/                            356,733 B -> 91,376 B  (74% 減)
/api/v1/models                24,158 B ->  5,190 B  (79% 減)
/workspace-api/models/catalog 22,919 B ->  5,180 B  (77% 減)
/api/v1/capabilities           1,602 B ->    372 B  (77% 減)
```

小さな応答まで圧縮しても CPU を使うだけなので下限を 1 KB に置いた。

boot のうち thumbnail は 4 件で base64 12,368 B（160px webp）であり、重い側ではない。
文書が全体の 74% を占めていた。

`./mf.sh test` 792 passed / 1 warning / 66.15 秒（新規 1 件）、`git diff --check` PASS。

## 評価が記録されず、実行環境の無いモデルが候補に見えていた（2026-08-30）

利用者から「MiniMax を評価したが終わらなかったし、動画生成 AI の候補としても
選択できない」との指摘。別々の 2 件だった。

### 1. 記録が効いていなかった（私の取り違え）

0.11.1 で native 経路にも `record_measurement` を足したはずが、15:36 の評価
（161 秒、ready）でも `measurements.json` は作られず、`measurement_confidence` は
low のままだった。原因は `RuntimeMetrics` に `elapsed_sec` が無いのに
`getattr(metrics, "elapsed_sec", 0)` で拾おうとしていたことで、0 が返って
ガードが黙って抜けていた。

```text
RuntimeMetrics  started_at / baseline_* / peak_rss_bytes / peak_process_swap_bytes / peak_vram_bytes
result          elapsed_sec / peak_vram_bytes / peak_rss_bytes / ...
```

operation へ残すのと同じ `result` から読むようにした。加えて、前のテストが
ソース文字列しか見ておらず壊れた実装を通していたので、実際に関数を呼ぶテストへ
差し替えた。旧実装では落ちることを確認済みである。

### 2. MiniMax は動画候補になり得ない

`unsloth/MiniMax-H3-GGUF` が名乗る adapter は
`native.stable-diffusion-cpp-minimax-h3` で、これを実装する worker が無い。

```text
画像 worker  diffusers.flux2-klein / diffusers.sdxl / diffusers.sdxl-single-file
動画 worker  diffusers.wan2.1-t2v
出荷カタログの動画候補 12 件のうち、実行できるのは Wan 2.1 T2V 1.3B のみ
```

候補として並ぶこと自体は正しい（調べる対象である）。誤っていたのは、その差を
画面に出していなかったことで、実行できないモデルの評価に GPU を 161 秒使っても
選べるようにならない、と押す前に分からなかった。

`models/adapters.py` に core が起動できる adapter を置き、公開文書へ
`has_runtime` を足した。画面は「実行環境なし」として一覧の判定に組み込み、
モデル管理では押す前に理由を書く。core は worker を import しないので知識が
2 か所に分かれる。食い違わないことは test が見張る（test は worker を import
してよい）。available なモデルは必ず実行できる、という条件も同じ test で守る。

`./mf.sh test` 795 passed / 2 warnings / 53.72 秒（新規 3 件）、`git diff --check` PASS。

## MiniMax H3 FL2VA を本番経路へ載せる（2026-08-30）

利用者の指示は「MiniMax H3 FL2VA と Wan の実行環境を準備し、既に開発済みの
ドライバーがあれば組み込む方針で調査・導入・検証・生成まで」。調べると、駆動系は
**既に完成していた**。評価が使っている `stable-diffusion.cpp` の pinned build
（`97d2990`、`build/bin/sd-cli`）がそれで、実際に 640x384 の動画を作れている。

```text
重み（実機に導入済み、4 点）
  minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf   拡散本体（FL2VA）
  qwen3vl_32b_minimax_h3-Q2_K_M.gguf        言語モデル
  vae/minimax_h3_video_vae_fp16.safetensors 映像 VAE
  vae/minimax_h3_audio_vae_fp32.safetensors 音声 VAE
起動          sd-cli -M vid_gen / te=cpu,diffusion=ROCm0,vae=ROCm0 / --mmap / --diffusion-fa
```

本番の動画 worker に adapter を足し、同じ組み合わせで起動するようにした。評価と本番で
2 通りの起動を持たない。実機で通すまでに 3 つ塞いだ。

```text
1. 重みが blobs/ への symlink である。snapshot だけを境界にすると正しい重みが
   「外」と判定される。境界を repository の根に置く（評価側と同じ扱い）
2. LD_LIBRARY_PATH が無いと libomp.so が見つからず sd-cli が起動しない。
   評価が使っているのと同じ環境を worker にも持たせる
3. MiniMax H3 は音も作る。正規化で include_audio を落とさない
```

実機での生成（本番 worker を直接叩いた）。

```text
生成 57.11 秒 / wall 57.50 秒 / max RSS 23,985,892 KiB / exit 0
出力 h264 640x384 5 フレーム 24fps 0.208 秒 39,070 B + aac 音声
runtime_version 97d2990807fe6d558e395f8764198d7c7e7b411c
```

registry では available / measured / rocm 対応にした（2026-08-30 の評価から
peak VRAM 14,763,892,736 B、149.28 秒）。宣言に rocm が無いと、測ってあっても
routing の候補にならない。

`./mf.sh test` 795 passed（新規 2 件）。

## Wan 2.2 TI2V-5B の実行環境を復元して生成まで通す（2026-08-30）

上流の駆動系（`wan` package）は `/data1tb/mediaforge-g7-v1/Wan2.2-source` に残っていた。
消えていたのは venv だけである。`runtimes/wan-ti2v-probe/requirements.txt` から作り直したが、
そのままでは `wan.configs` が読めなかった。

```text
不足していた依存   einops / imageio（requirements から抜けていた）
追記               imageio==2.37.4 / einops==0.8.1 を pin
```

実機で通した実測（text encoder は CPU、生成は GPU の 2 process）。

```text
smoke          256x256 1 フレーム 1 歩    encode 24.37s + generate 24.57s / wall 61.52s
quality-frame  256x256 1 フレーム 30 歩   encode 27.74s + generate 28.36s / wall 109.52s
candidate-clip 384x256 33 フレーム 30 歩  encode 14.01s + generate 73.48s / wall 100.51s
               出力 h264 384x256 33 フレーム 1.375 秒 115,130 B / max RSS 19.4 GB / exit 0
```

30 歩は 1 歩に対して +3.79 秒（0.13 秒/歩）で、費用の大半は読み込みである。

本番 worker に `native.wan2.2` を足し、評価が使っている probe をそのまま呼ぶ形にした。
評価と本番で 2 通りの起動を持たない。text encoder と生成を別 process に保つのは
device の取り合いを避けるためで、1 つに畳むと 5B が載らない。

registry は available / native 384x256 30 歩、`measured_runtime_sec` を 100.51 へ更新した。
VRAM は G7 V1 の実測（30.7 GB）を据え置く。今回は採取していないので上書きしない。

### 実機の runtime を一度壊し、復旧した

実機の動画 runtime へ `wan` の依存を足すとき、索引を指定せずに pip を走らせたため
torch が CUDA 版 2.13.0 へ入れ替わり、`Found no NVIDIA driver` で動かなくなった。
repository 側の venv は無事だったので、実機側を消して hardlink で作り直し、ROCm の
find-links を明示して入れ直した。

```text
復旧後  torch 2.10.0+rocm7.2.1.gitb07cec22 / torchvision 0.25.0+rocm7.2.1.git82df5f59
        wan.configs 読み込み OK（ti2v-5B を含む 5 構成）/ diffusers 経路も健全
```

ROCm の venv へ何かを足すときは、常に `--find-links` を付ける。付けないと pip は
CUDA 版で上書きする。

`./mf.sh test` 797 passed。

## 動画の設定をモデルごとに最適化する（2026-08-31）

利用者から「時間はもっと選択肢がないか。スライダーで選べるか。各モデルに合わせて
最適化し、評価で確認した適切な設定が選べる UI/UX にしてほしい」との指摘。

3 択だったのはモデルの制限ではなく私の決め打ちだった。ただし連続に選ばせる前に、
モデル側の本当の制約を確かめる必要があった。

```text
Wan（2.1 / 2.2）  num_frames % 4 == 1 でなければならない。外すと diffusers が黙って
                  丸めるので、頼んだ長さと返る長さが食い違う
MiniMax H3        sd-cli は任意のフレーム数を取る。刻み 1 で選ばせてよい
Wan 2.2（私の実装） probe の preset へ丸めていた。頼んだ寸法と違うものが返る作りだった
```

Wan 2.2 の probe に寸法・フレーム数・歩数の上書きを足し、本番は preset を下敷きに
しつつ実際の要求で作るようにした。preset へ丸めるのをやめた。

長さは連続のつまみにし、刻みをモデルが取れる並びに合わせた。画質もカタログの実測
プロファイルから組む。共通の決め打ちを持つと、どれかのモデルで「選べるのに作れない」
値を出すことになる。

```text
registry に video プロファイルを足した（すべて 2026-08-29〜31 の実測）
  Wan 2.1 T2V   16fps / 4 刻み 9..81 / 512x320・640x384・448x448 / 実測 512x320 33f
  Wan 2.2 TI2V  24fps / 4 刻み 9..81 / 384x256・512x320・256x256 / 実測 384x256 33f
  MiniMax H3    24fps / 1 刻み 5..49 / 640x384・512x320・384x384 / 実測 640x384 5f
```

目安時間もモデルごとの実測から出す。面積は注意機構に二乗で、長さはフレーム数に比例
して効く。モデルを選び直したら画質と長さを組み直す。前のモデルの寸法を残すと、
選べるのに作れない値が画面に残る。

実 Chrome（390x844）での観測。

```text
Wan 2.2 指定  画質 384×256 / 長さ 0..18（4 刻み）→ 1.4 秒 / 送信 fps 24
Wan 2.1 指定  画質 512×320 / 長さ 0..18（4 刻み）→ 2.1 秒 / 送信 fps 16
MiniMax 指定  画質 640×384 / 長さ 0..44（1 刻み）→ 0.2 秒 / 送信 fps 24
つまみを動かす 640×384 / 10 フレーム / 目安 2 分 → 5 分
```

途中、公開文書の 3 か所（`/api/v1/models`、管理カタログ、単体表示のマッピング）で
`video` を落としていた。どれか 1 つでも落とすと、画面はどのモデルでも同じ選択肢を出す。
`kind` や `base_model` で以前起きたのと同じ形である。

`./mf.sh test` 797 passed、`git diff --check` PASS。

## 最長の長さが誤っていた／FastH3 LoRA は当たらない（2026-08-31）

利用者から「最大でも 5.1 秒、H3 は 2 秒と表示されるが、生成最大時間は正しいか」との指摘。
表示は私が入れた値どおりだったが、その値が上流の定義と合っていなかった。

```text
Wan 2.1 T2V   81 フレーム / 16fps = 5.06 秒   diffusers の既定と一致。正しかった
Wan 2.2 TI2V  上流 wan/configs/wan_ti2v_5B.py の frame_num = 121 / 24fps = 5.04 秒
              入れていたのは 81（3.4 秒）。低すぎた
MiniMax H3    sd.cpp のドキュメントが 3 例とも --video-frames 56（24fps で 2.33 秒）
              入れていたのは 49（2.0 秒）。根拠のない当て推量だった
```

上流の定義に合わせて直した。H3 はモデル自体が 15 秒まで作れると公表されているが、
この駆動系での上限は未確認なので、ドキュメントが実際に使っている 56 を上限に置く。

### FastH3 / Turbo LoRA は現在の駆動系に当たらない

利用者の「MiniMax H3 Flash は使えるか」を調べた。MiniMax の Fast H3 v1（2026-08-29 発表）は
NVIDIA Blackwell 上で約 14 倍という数字で、重みの配布形態も技術報告も未公開である。
一方 open weight 側では高速化 LoRA として実物が出ている。

```text
lightx2v/Minimax-h3-Turbo          4step / 8step、Apache-2.0、DL 884,976
alibaba-pai/MiniMax-H3-Acc-LoRAs   8step、other
drozbay/MiniMax-H3-FastH3-Preview-LoRA  FastH3 preview、other
```

`sd-cli` は `--lora-model-dir` を持つので、当てられるはずだった。Apache-2.0 の
`minimax_h3_fl2v_turbo_4step_v1.1_768p_bf16.safetensors`（1,383,677,808 B）を取得して
実機で試した結果、**当たらなかった**。

```text
[WARN] Only (0 / 600) LoRA tensors have been applied
unused lora tensor |lora.model.diffusion_model.transformer_blocks.22.attn.to_out.0.weight.lora_down|
4 歩 LoRA なし  63.12 秒
4 歩 LoRA あり  89.31 秒（1.38 GB を読んで 0 個適用。遅くなるだけ）
```

テンソル名の規約が gguf 側と噛み合わない。ComfyUI 版も同じ系統の命名なので見込みは薄い。

なお H3 は読み込みが支配的で、1 歩 57 秒に対し 4 歩 63 秒（1 歩あたり約 2 秒）である。
仮に LoRA が当たっても、速度への効きは小さい。効くのは低歩数での品質の方である。

`./mf.sh test` 797 passed。

## H3 は 15 秒まで作れた／目安時間を実測の形へ（2026-08-31）

利用者から「H3 は 15 秒ならそうして」との指示。公表値をそのまま入れず、この機械で
作れるかを確かめた。前回 56 を入れて誤ったのは、根拠を実測ではなくドキュメントの例に
置いたためである。同じ形を繰り返さない。

```text
640x384 / 4 歩 / R9700
    5 フレーム (0.21 秒)     63.12 秒   max RSS 23.2 GB
  121 フレーム (5.13 秒)    594.72 秒   max RSS 24.9 GB   映像 vp8 + 音声 pcm 正常
  360 フレーム (15.04 秒)  1889.53 秒   max RSS 25.1 GB   17,218,141 B / 正常
```

**15.04 秒が完走した。** 上限を 360 フレームへ上げた。VRAM は 17.8 GB で頭打ちにならず、
制約は時間の方である。あわせて H3 の既定歩数を 1（評価用の下限）から 4（実測した値）へ。

### 目安時間を 1 点比例から固定費＋単価へ

1 点からの比例では、読み込みの固定費が大きいモデルで大きく外れる。H3 の実測
（149.28 秒 / 5 フレーム）を比例で伸ばすと 360 フレームで 179 分となり、実測 31.5 分の
5.7 倍になる。使えない案内である。

実測から固定費と 1 フレーム単価に分け、面積の効き（注意機構は二乗）だけを掛ける。

```text
Wan 2.1 T2V   固定 25.0 秒 + 3.6 秒/フレーム   （33 フレームで 144 秒。実測 144.6 秒）
Wan 2.2 TI2V  固定 20.0 秒 + 2.4 秒/フレーム   （33 フレームで  99 秒。実測 100.5 秒）
MiniMax H3    固定 40.0 秒 + 5.0 秒/フレーム   （  5 フレームで  65 秒。実測  63.1 秒）
                                              （360 フレームで 1840 秒。実測 1889.5 秒）
```

実 Chrome での表示。

```text
Wan 2.2   目盛 0..28   0.4 秒(9f) 1 分未満 / 5.0 秒(121f) 5 分
Wan 2.1   目盛 0..18   0.6 秒(9f) 1 分未満 / 5.1 秒(81f)  5 分
MiniMax   目盛 0..355  0.2 秒(5f) 1 分     / 15.0 秒(360f) 31 分
```

`./mf.sh test` 797 passed。

## 動画を取り込めるようにする（2026-08-31）

利用者から「サンプル動画は見れるようにライブラリに入れておいて」との指示。
実行してみると、取り込み経路が PNG / JPEG / GLB しか受けなかった。生成した動画は
job から登録されるが、既にファイルとして手元にあるものを library へ入れる道が無い。

`video/mp4` / `video/webm` / `video/quicktime` を受けるようにした。上限は画像と分けて
96 MiB に置く（実測: 640x384 の 15 秒で 17.2 MB。共通の 64 MiB で切ると、少し大きい
ものが理由なく弾かれる）。

**取り込んだものは h264/aac の mp4 へ揃える。** 駆動系は webm/vp8 を書くものもあるが、
iOS はそれを再生しない。そのまま置くと、作った端末でだけ見える asset ができる。
library に置くものは見られる形にする、という一点のために正規化する。

中身が本当に動画かは ffprobe で確かめる（worker の実装は import せず、system binary を
配列引数・timeout 付きで呼ぶ）。映像 stream はちょうど 1 本、寸法は 16px 以上かつ
画素上限内、尺は 0 < s <= 300、fps は 0 < f <= 120。外れるものは枠を作らず断る。

`./mf.sh test` 797 passed（新規 1 件）。

## 歩数の既定が誤っていた（2026-08-31）

利用者から「動画がおかしい。画像生成のときも試行回数が少なくおかしかったが、動画は
問題ないか」との指摘。**正しかった。** 同じ誤りを歩数で繰り返していた。

```text
sd-cli の既定        20 歩
ドキュメントの 3 例   --steps を書かない（= 20 を使う）
登録していた値        4 歩   ← library の H3 2 本はこれで作った
```

4 は私が測定に使った値であって、このモデルが要る歩数ではない。frame_max を 56 に
したのと同じ手癖である。**設定値は実測の副産物ではなく、モデルが要求する値から決める。**

20 歩で測り直した（640x384）。

```text
    5 フレーム   177.69 秒   （4 歩では 63.12 秒）
  121 フレーム  2647.52 秒   （4 歩では 594.72 秒。歩数 5 倍に対し 4.45 倍）
  → 固定 71.2 秒 + 21.29 秒/フレーム。360 フレームなら 129 分の見込み
```

1 歩の単価は約 7.2 秒で、目安計算に使っていた 2 秒の 3.6 倍だった。目安時間も過小に
出ていたことになる。式へ歩数を織り込み、どの歩数で測った値かを `measured_steps` として
記録する。書かないと、歩数を変えたときに式が黙って外れる。

lease へ申告する `measured_runtime_sec` も、評価の 1 歩（149.28 秒）から実用設定での
実測（2647.52 秒）へ変えた。評価は「動くか」を見るためのもので、その所要時間を実用の
見積りに流用してはいけない。

Wan 2.1 / 2.2 は上流の既定 30 歩を使っており、この問題は無い。

`./mf.sh test` 798 passed。

## 評価が測った時間で、実用の実測を潰していた（2026-08-31）

前項の 20 歩の実測を出荷しても、実機では効かなかった。overlay が勝っていた。

```text
manifest        measured_runtime_sec 2647.52   （20 歩 121 フレーム）
overlay が上書き                      158.409   （評価の 1 歩 5 フレーム）
実機の API が返す値                    158.409
```

`ModelRegistry.load(measurements=)` は manifest の `measurements` を**丸ごと**
置き換える。評価の記録は VRAM を測るためのものだが、時間の欄まで probe の値で
埋めていたため、出荷した実測が毎回の評価で消えていた。lease は 17 分の 1 で
確保され、実用の設定で回すと途中で切れる。

VRAM は probe が測ったものを残し、時間は manifest の実測を通す。評価は「動くか」を
見る最小の実行であって、実用の設定で払う時間ではない。実機の overlay も直した。

### 宣言した歩数が画面に届いていなかった

`generation` block は `diffusers.` 経路にしか付かない。native の動画モデル
（H3 / Wan 2.2）には届かず、画面は `measured_steps` で代用していた。今日は
両方 20 と 30 で一致しているが、`measured_steps` は「その実測が何歩だったか」で
あって生成に使う歩数ではない。測り直した歩数がそのまま既定にすり替わる。
`video` profile に `default_steps` を入れ、画面はそれを見る。

生成そのものは `_resolved_video_request` が `selected.default_steps` を入れており、
最初から 20 歩で回っていた。ずれていたのは画面の目安時間の方である。

`./mf.sh test` 799 passed（新規 1 件）。

## 写真を撮ったままの解像度で直せるようにする（2026-09-01）

利用者から「自分で撮った写真の透かし除去と画質改善をしたい」。透かし除去は
「一部だけ直す」で今日できるが、**写真を 2048px に縮めてからでないと通らなかった**。
透かしを消すために写真全体の解像度を捨てることになる。

`MAX_IMPORT_PIXELS = 2048 * 2048` は strict edit を入れたとき（d08dae4）の丸い数で、
根拠は残っていない。**strict edit は元画像の解像度をモデルに渡していない。**
生成されるのはマスクの外接矩形＋64px の切り抜きだけで、原寸の元画像へ貼り戻す。
縮小は何も守っていなかった。

何が実際に縛るかを測った（合成 + 検証、原寸 RGBA を数枚持つ）。

```text
   3.1MP  合成 0.81s  検証 0.24s  PNG  4.6MiB  peak RSS  139MiB
  12.2MP       2.90s       0.91s      13.6MiB           433MiB   ← 携帯の標準
  24.4MP       5.22s       1.71s      22.2MiB           828MiB   ← 一眼の標準
  48.0MP       9.16s       3.27s      35.6MiB          1607MiB
```

VRAM は使わない。縛るのは core の RAM である。**24,000,000 画素**に置いた。48MP は
1 ジョブが 1.6GB を抱えるので取らない。動画は尺のぶんだけ復号するため、
`MAX_VIDEO_IMPORT_PIXELS` として 2048x2048 のまま分けた。

worker 側にも同じ 2048 があり（`strict edit dimensions must be in the range 1..2048`）、
こちらも画布の寸法にしか使っていない。同じ線に揃えた。境界の都合で core を
import できないので、値を両方から確かめる試験を置く。

### 実機（R9700 / gfx1201）

4032x3024（12.2MP）の写真に透かしを焼き、その上だけを塗って worker を直接回した。

```text
取り込み           HTTP 201  2.68s   13.57MiB を原寸のまま
生成               1.69s（読み込み 5.42s）  ← 塗った範囲だけを作るので寸法に依らない
出力               4032x3024  13.70MiB
保護画素の差       0（image.strict_edit.unmasked_pixel_diff 通過）
変わった範囲       (3640, 2860, 4001, 2971) = 塗った範囲そのもの
```

透かしは消え、周囲は原寸のまま無傷だった。

### 見られなくなる問題を先に塞ぐ

原寸の写真は PNG で 13.6MiB あり、workspace の転送上限（12MiB）を超える。
`assets.content` はこれを**断っていた**ので、上限だけ上げると「透かしは消せたが
見られない」になる。見るための縮小版（1600px / 2MiB、実測 220KiB）を返し、
縮めたことを画面に書く。原寸は保存で取り出せる（`assets.export` は host へ
ファイルのまま渡すので、この上限に縛られない）。

画面の縮小は、モードで行き先を変える。画像全体を作り直すモードは今までどおり
envelope に収める。「一部だけ直す」だけが原寸を保つ。

`./mf.sh test` 803 passed（新規 4 件）。

## 写真を作り直さずに拡大する（2026-09-01）

利用者の「画質改善」に応える機能が無かった。あるのは生成と編集だけで、「全体を
直す」や「似た別案を作る」は**画像全体を作り直す**。写真の画質を上げる道具ではない。

拡散モデルに「良くして」と頼むのは、写真に対しては誤りである。SwinIR
（Apache-2.0, Liang et al.）の実写 4 倍を入れた。標本化しないので prompt も seed も
無く、同じ絵からは同じ絵が出る。

### 全体を 1 度に通すと入らない

```text
512x384 を丸ごと      43.6 秒   peak VRAM 8.61 GiB   ← 注意機構が面積の二乗
```

写真の大きさでは載らない。256px のタイルに 32px の重なりで処理し、重なりは
平均で溶かす。VRAM がタイルで決まるので、寸法に依らなくなる。

### 実機（R9700 / gfx1201）

```text
0.31MP ->  4.9MP    6.3s   peak VRAM 0.82 GiB   PNG  5.4MiB
0.79MP -> 12.6MP   20.0s              0.81 GiB      15.7MiB
1.12MP -> 18.0MP   24.7s              0.81 GiB      23.2MiB
1.50MP -> 24.0MP   35.6s              0.82 GiB      35.8MiB   ← 上限ちょうど
読み込み 0.12 秒 / cold VRAM 0.06 GiB
```

入力 1 メガ画素あたり約 21.5 秒。**入力の上限は 1,500,000 画素**に置いた。4 倍にすると
16 倍の画素数になるので、これが取り込みの上限（24,000,000 画素）に収まる最大である。
超える画像は、選べるのに作れない値にならないよう受付で断る。

倍率は重みが持っている。核が 1 度だけ掛け算をして出力寸法を決め、画面にも worker にも
させない。別の倍率の重みを足したときに片方だけ直る、という形にしないためである。

### 依存を足すときの固定

`torchvision` を固定せずに入れて、**実機の image runtime を壊した**。pip が PyPI の
最新を選び、それが要求する CUDA 版 torch で ROCm の torch を置き換えた
（torch 2.13.0+cu130、`cuda.is_available()` が False、transformers の遅延 import まで
連鎖して停止）。`requirements.txt` から入れ直し、CUDA の残骸を external して復旧。
生成 1.6 秒で復帰を確認した。

固定すれば find-links の ROCm wheel が選ばれ、torch は触られない
（`torchvision==0.25.0+rocm7.2.1` が入り、torch は据え置き）。**版を書かない
`pip install` を runtime に対して打たない。**

`./mf.sh test` 806 passed（新規 3 件）。

## 加工と生成を分ける（2026-09-01）

利用者から「完全に画像生成しかできないように見える」「加工と生成が混ざっているなら
適切に処置して」。実機の画面を見ると、そのとおりだった。編集は写真を添付して初めて
現れるので、**写真を直しに来た人には入口が無い**。

媒体に「写真を直す」を足した。線は「元の絵が残るか」で引く。

```text
写真を直す（加工）  一部だけ直す / 画質を上げる / 外側を広げる
画像を作る（生成）  文章から / 全体を直す / 似た別案 / 参考を足して直す
```

写真モードでは、作る道具（サイズ・枚数・モデル選択・LoRA・演出）を一切出さない。
出すと「作る」画面に見え、直しに来た人が自分の用事を見つけられない。

### 拡大が選べるのに送れなかった

同時に、実機で報告された失敗を 4 つ直した。いずれも**黙って落ちる**形だった。

1. **SwinIR が土台のモデル一覧に出ていた。** 拡大は絵を大きくするだけで作れない。
   選ぶと、その利用者のあらゆる「作る」が `model_unavailable` で落ちた（実機で再現）。
   `has_runtime` と同じ理由で、選べても作れないものを出さない。
2. **拡大なのに指示欄が必須だった。** 空のまま押しても理由が出ない。拡大は指示を
   取らないので、欄ごと隠して検査からも外す。job の名前だけ核が付ける。
3. **送信する内容が拡大に合っていなかった。** 寸法・`strict_edit`・枚数を付けて
   送っており、受付が「倍率から決めます」と断る。付けない。
4. **読めない画像を「選んでいない」と同じ見た目にしていた。** 選べたのに何も
   起きないように見える。理由を出す。

### 加工した写真が添付できない

`createImageBitmap` に `imageOrientation` を渡していなかった。EXIF で回している写真は
ブラウザとサーバで縦横が食い違い、寸法の一致を要求する「一部だけ直す」が受付で断られる。
向きの付いた写真だけ添付できない、という形で出ていた。見えているとおりに開く。

canvas も直した。携帯の canvas には面積の上限があり、超えると `toBlob` が投げずに
`null` を返す。そのまま `File` を作ると壊れたものを送っていた。入らなければ半分ずつ
落とし、実際に用意できた寸法を表示する。

また、形式が PNG / JPEG でないものは寸法が足りていても canvas を通す。以前は大きい
写真が必ず縮小され、その途中で PNG に直っていたので表に出ていなかった。原寸で
預かるようにした結果、HEIC がそのまま送られて受付で断られる経路ができていた。

実 Chrome で確認（写真モードに切り替え、1024x768 を添付）。

```text
ラベル        ＋ 直したい写真を選ぶ / 送信ボタン「直す」
生成用の欄    サイズ・枚数・モデル選択・LoRA すべて非表示
編集の選択肢  一部だけ直す / 画質を上げる / 外側を広げる
拡大の案内    1024×768 → 4096×3072（およそ 17 秒）
上限超        この画像は大きすぎます。1,500,000 画素までを 4 倍にできます。
拡大時        指示欄は隠れ、送信前の検査も通る
```

`./mf.sh test` 806 passed。

## 手元の端末へ保存する／ライブラリから直す（2026-09-01）

利用者から iPhone で 2 件。

### 「保存先を選べませんでした」

保存は `host.files.export`、つまり **ControlDeck が動いている機械のファイル選択**
だった。手元が携帯だと選ばせる相手が別の機械なので、必ずここで終わる。

見ている端末へ保存する経路にした。共有シートがあればそれを使い（iOS はここから
「画像を保存」で写真に入る）、無ければ普通のダウンロードにする。埋め込みの iframe には
`allow-downloads` が付いているので、どちらも通る。host のファイル選択は、同じ機械で
使っているときの控えとして残す。

原寸は表示用とは別の経路で取る。`assets.content` は 12MiB を超えると縮小版を返すので、
それを保存すると小さくなったことに気づかないまま原寸を失う。`assets.bytes` を足し、
4MiB ずつに区切って運ぶ（base64 が 4/3 に膨らんだうえで 1 つの socket message に
載る必要がある）。実測: 19.8MiB の PNG を、byte 単位で一致したまま取り出せた。

### 「編集ボタンを押しても画像が添付されない」

**そのとおりで、何もしていなかった。** ビューアを閉じて「『画像を追加』から
読み込ませてください」と案内文を出すだけだった。実際に添付する。

原寸を取ってから file input に入れ、普段の添付とまったく同じ道を通す。着地は
「写真を直す」にした。生成側へ落とすと、作り直す選択肢しか出ないうえ、元画像が
モデルの寸法（1024x768）まで縮められる。

あわせて、写真モードでは何を選ぶ前から原寸を保つようにした。縮めてから選び直させると
canvas を 2 度通ることになり、携帯では目に見えて待たされる。例外は「外側を広げる」で、
これは画布ぜんぶをモデルが描くため、モデルが出せる寸法に収める必要がある。

実 Chrome で確認。

```text
原寸の取り出し   19.8MiB を byte 単位で一致（表示側は縮小版を返している）
ライブラリの編集 1200x900 を原寸のまま添付・媒体は「写真を直す」・
                 選択肢は 一部だけ直す / 画質を上げる / 外側を広げる
```

`./mf.sh test` 807 passed（新規 1 件）。

## 写真モードが押されて見えず、選択肢も出ていなかった（2026-09-01）

利用者から実機で 3 件。写真モードを入れた直後の作りが、いくつも不足していた。

### 選んでいるのに押されて見えない

`mediaSwitchButtons()` が image と video しか返しておらず、写真の button に
`aria-pressed` が付かない。画面の中身は写真モードなのに、印だけが画像のまま残る。
**媒体を足したらここに足す。**

### 高画質化が画面に無かった

`#edit-block` に `data-image-create` が付いていた。写真モードは
`[data-image-create]` を消す規則なので、**編集の選択肢そのものが消えていた**。
DOM には在るので、browser 越しの確認で `.edit-action` を数えるだけでは通ってしまう
（実際そうやって見落とした）。表示されているかを見る。

### 並びが「作る」のままだった

指示 → 添付 の順なので、写真を直しに来た人が最初に文章を求められる。利用者の
「変更は不要で高画質化したいだけの場合も対応して」はこの形のことだった。写真モードでは
添付 → 何をするか → 指示 の順に並べ替え、拡大では指示欄ごと消す。

```text
添付 138px / 編集の選択肢 218px / 指示 534px（実 Chrome）
拡大を選ぶと  指示欄 非表示・案内「900×1200 → 3600×4800（およそ 23 秒）」
              送信前の検査も通る
```

### 生成側の選択肢を減らしてしまっていた

写真モードに「直す」を移したとき、生成側からも外していた。利用者から「以前は複数
あったのに 2 つになっている。写真モードとは別で戻して」。**そのとおりで、入口を
増やすつもりが既にある道を塞いでいた。** 生成側は写真モードを足す前と同じ一式に戻す。

```text
画像を作る  一部だけ直す / 外側を広げる / 全体を直す / 似た別案を作る / 参考を足して直す
写真を直す  一部だけ直す / 画質を上げる / 外側を広げる
```

拡大だけは生成側に置かない。元の解像度を要するのに、生成側は添付を envelope まで
縮めるので、縮めた絵を拡大することになる。

`./mf.sh test` 807 passed。

### ライブラリの編集は、選んでいるモードへ入れる

「これを編集」を写真モードへ移していたが、利用者から「選択中の機能モードへ添付して」。
**そのとおりで、利用者が選んだ場所を勝手に捨てていた。** 媒体は変えない。

```text
画像を作る で押す → 画像を作る のまま（envelope に合わせて 1024x768）
写真を直す で押す → 写真を直す のまま（1200x900 原寸）
動画を作る で押す → 動画を作る のまま（動かす元の画像として添付）
```

あわせて、編集を出さない媒体では選択肢を DOM から消す。隠れているだけの前の
選択肢は、「見えていないこと」の確認を素通りする。

## ブレを直す／顔が崩れる件の調査（2026-09-01）

利用者から 2 件。「ブレとかも消せるか」「透かしを消した所が顔だと崩壊する。他の
画像を参考に補完できるか」。

### ブレ補正は入った

拡大（SwinIR）は BSRGAN 系の劣化を想定した学習で、動きブレを取るものではない。
NAFNet の GoPro 版（MIT, Chen et al.）を足した。

丸ごと通すと 1.4MP で 2.94 GiB。拡大と同じタイル処理に載せると寸法に依らなくなる。

```text
1.40MP  1.65s   3.00MP  3.14s   7.68MP  7.55s   peak VRAM 405,778,944 B 一定
合成した動きブレ  PSNR 23.10 dB -> 24.11 dB（丸ごとなら 24.66 dB）
```

倍率 1 なので寸法は変わらず、入力の上限は取り込みの上限（24,000,000 画素）そのままで
よい。拡大と同じ経路・同じ adapter に載せる。どちらも標本化せず、prompt も seed も
持たない。

**最初の測定は誤りだった。** 合成したブレが画像をずらしていたため PSNR が下がり、
「効いていない」と読めた。ずれない形で作り直して測り直した。

### 顔が崩れる件 — 私の仮説は外れた

塗った範囲の切り抜き寸法のまま生成していることが原因だと考え、生成を 768〜1024px へ
上げ、文脈も広げて試した。**実測では逆に悪くなった。**

```text
顔の上の透かし 148x44 を塗って消す
  元の設定（368x320 で生成）   1.4 秒   目がはっきり残る
  変更後（768px へ拡大）      86.6 秒   目が潰れる
```

60 倍遅くなったうえで質が落ちる。仮説を捨てて元に戻した。

崩れるのは**塗った範囲が大きいとき**である。顔の広い範囲を塗ると、モデルはそこに
別人の顔を描く。透かしだけを細く塗れば周りの顔が文脈として残り、実用になる。

### 参考画像は、いまの経路では使えない

adapter は strict edit と `reference_paths` を同時に受ける形になっていたので、
そのまま試した。**参考画像がマスクの中へ縮小コピーとして貼り付いた**（生成 7.3 秒。
条件付けが効いておらず、参考画像そのものが出力になっている）。作り込みが要るので、
使えるものとしては出さない。

`./mf.sh test` 808 passed（新規 1 件）。

## 消して埋める（LaMa）と、拡大モデルの比較（2026-09-01）

利用者から「高画質化に適切な AI を調査して」「透かしを消すと違和感が出る」。

### 透かしを消すと帯になるのは、道具が違うから

いまの「一部だけ直す」は FLUX に**塗った範囲を描き直させて**いる。透かしを消したい
だけの場所でも新しい絵を描くので、絵柄と明るさが変わり、マスクの形の帯が残る。

上流の評価でも、除去は拡散モデルではなく LaMa を採る、とされている
（"LaMa is adopted over traditional diffusion-based methods to preserve original
image characteristics, as diffusion-based techniques often introduce
inconsistencies and artifacts"）。実機で並べると差は明白だった。

```text
顔にかかった透かし（292x36）を消す
  FLUX  25.67 秒   別スタイルの帯が残る
  LaMa   0.42 秒   帯が出ない。周りの網点がそのまま続く
```

LaMa（big-lama, Apache-2.0）を `image.erase` として足し、画面では「消して埋める」に
した。既存の inpaint は「塗った所に描き足す」に改名した。**消すのと描くのは別の
用事である。**

塗っていない所は 1px も変わらない（実測でマスク外の最大差 0）。

費用は写真の大きさではなく塗った範囲で決まる。切り抜いて通すためである。

```text
21.3MP の写真   塗り 300x40     4.23s / 0.58 GiB
                塗り 900x300  115.70s / 3.18 GiB   ← 切り抜きが上限に当たる
                塗り 2000x900 115.86s / 3.19 GiB
```

上限を付ける前は 2000x900 の塗りで 339 秒・14.3 GiB まで伸びた（切り抜きは塗った
範囲の 3 倍角になる）。2,500,000 画素で頭打ちにし、超えたら縮めて通して埋めた所だけ
元の大きさへ戻す。LaMa の出力はもともと滑らかなので、ここで細部は失わない。

### 拡大モデルの比較

OpenModelDB で実写向けとして挙がる 2 つを、同じ写真・同じ機械で回した。

```text
512x683 -> 2048x2732
  SwinIR-M（いま採用）      9.5s   0.82 GiB
  4xNomos8kDAT (CC-BY-4.0) 48.6s   1.57 GiB
  4xNomos8kSCHAT-L         183.7s  2.70 GiB
```

Nomos 系は質感を足す学習をしているぶん粒状感が乗る。手元の試験画像が画面を撮った
もの（網点あり）なので、その粒を強調する形になり、SwinIR の方が素直だった。
**実写の写真での比較はできていない**ので、置き換えは判断しない。速さは 5〜19 倍違う。

### 重みの読み込み

`.safetensors` を `torch.load` に渡していて読めなかった。Hub の blob は拡張子を
持たないので、中身で見分ける（safetensors は先頭 8 byte が長さ、次が `{`）。
big-lama はさらに全体が `model.` で包まれており、spandrel が探す鍵と 1 段ずれる。
剥がしてから渡す。

`./mf.sh test` 808 passed。

## 高画質化で、出す大きさを選ぶ（2026-09-01）

利用者から「画像が荒い写真を高画質化したい」。**両方あるので、大きさを選ばせて
ほしい**との指定。

### 荒い写真の大半が、受付で断られていた

「画質を上げる」はあったが、出す寸法は重みの倍率（4 倍）で固定だった。出力は
取り込みの上限（24,000,000 画素）に収める必要があるので、受ける入力は
1,500,000 画素までになる。**スマホの写真（4032x3024 = 12.2MP）はそこで断られる。**

荒い写真は、小さいとは限らない。もう十分に大きくて、ノイズと圧縮の跡だけが乗って
いる写真の方がむしろ多い。その人に「4 倍にする」しか出していなかった。

重みの倍率の**約数**までを選べるようにした。約数に限るのは、割り切れる縮小だけが
画素の格子を保つからである（面積平均で落とす。補間の種類を選ぶ余地が無く、位置も
ずれない）。網には倍率に関わらず元の写真をそのまま通す。縮めた写真を入れる形には
しない — それでは元の細部を捨ててから直すことになる。

```text
                      前              後
選べる大きさ          4 倍のみ        原寸のまま / 2倍 / 4倍（models.json の宣言）
受ける入力            1,500,000 px    24,000,000 px（取り込みの上限と同じ）
12.2MP のスマホ写真   受付で拒否      原寸で通る
断る対象              写真そのもの    その写真で出せない倍率だけ（収まるものを名指す）
```

入力の上限はもう倍率に依らない。倍率ごとの可否は要求のたびに見る。

### 実測（R9700 / gfx1201、256px タイル・32px 重なり）

同じ 1024x1024 を 3 通りで通した。**費用は出す大きさではなく元画像の面積で決まる**
（どの倍率でも網には同じものを通すため）。VRAM もタイルで決まるので変わらない。

```text
1024x1024 (1.05MP) を入れる
  4 倍  -> 4096x4096  25.51s  24.33s/MP  879,555,072 B
  2 倍  -> 2048x2048  22.18s  21.15s/MP  871,166,464 B
  原寸  -> 1024x1024  21.22s  20.24s/MP  871,166,464 B

4032x3024 (12.19MP) を原寸のまま直す — 前は受付で断られていた大きさ
  原寸  -> 4032x3024  212.1s  17.39s/MP  879,555,072 B  peak RSS 2,036,879,360 B
```

VRAM は 12 倍の面積でも変わらない（タイルで決まる）。大きい方が 1 メガピクセル
あたりは速い（端のタイルの割合が減る）。`per_source_megapixel_sec` は 1.5MP で
測った 21.5 のままにしてある — 17.4〜24.3 の幅の上側で、案内も打ち切りも余裕を
持つ側に外れる。

溜める場所は出す寸法の側へ移した。網の倍率で溜めると、原寸を頼まれたときにも
16 倍の面積を抱える。重なりの数も 3 面から 1 面にした（24MP の出力で 192MB の差）。

worker を実プロセスで回し、同じ 1024x1024 から 1024 / 2048 / 4096 が出ることを
確認した（`upscale_scale` が核 → worker → adapter へ届いている）。

### 出荷済みの「ブレを直す」「消して埋める」が、押すと必ず失敗していた

倍率を通す経路に `scale < 2` の門が残っていた。ブレ補正も消して埋めるも倍率 1 で
同じ経路を通るので、両方ともそこで落ちる。画面には出ているのに押すと失敗する。

main（56897f7）と作業ツリーで、実際の models.json の descriptor を使って核の
解決を回した実測:

```text                     main                                 いま
拡大    OK 3200x2400                          OK 3200x2400  upscale_scale=4
ブレ    FAIL この拡大モデルは倍率を宣言していません   OK 800x600  upscale_scale=1
消して  FAIL この拡大モデルは倍率を宣言していません   OK 800x600  upscale_scale=1
```

前の 2 つの機能追加は adapter までは実測していたが、**核の解決を通していなかった。**
テストも通っていない（テスト環境ではモデルが導入されておらず fake worker へ落ちる
ので、実モデルの経路に入らない）。実一覧の descriptor で解決を回す試験を足した。

画面にも同じ形の取り違えがあった。案内の単価と倍率を引く先が「ブレ補正なら
image.deblur、それ以外は image.upscale」になっていて、消して埋めるを選ぶと拡大の
倍率と単価が出ていた。直し方から capability を引く表にした。実ブラウザで、ブレ補正
が "1024×1024 のまま（およそ 1 秒）"（NAFNet の 1.02 秒/MP）を出し、拡大の 21.5 を
出さないことを確認した。

### 打ち切りを、1 枚の実測ではなく面積で組む

worker の打ち切りは `measured_runtime_sec * 3 + 30` を無出力の猶予にしていた。
SwinIR の実測は 35.6 秒なので猶予は 136.8 秒、1 枚だけ作る直しでは実質 273 秒。
**12.2MP の写真は 4 分掛かるので、上限を上げただけでは受け付けた job が時間切れで
落ちる。** 直しは費用が元画像の面積に比例し、その係数をモデルが宣言しているので、
そこから見積もる。broker へ申告する占有時間も同じ値にした。

### PSNR はこの重みの物差しにならない

採用しているのは `..._SwinIR-M_x4_GAN`、知覚品質へ寄せた GAN 系である。生成した
写真らしい画像（1024x1024）を基準に、荒らしてから直して測った。

```text
A 原寸のまま  JPEG q20 (66,621B) へ荒らし、寸法を変えずに直す
    荒い入力    PSNR 30.40 dB
    直した      PSNR 27.42 dB   21.18s / 879,555,072 B
B 4 倍        256x256 + JPEG q30 (9,131B) から 1024x1024 へ戻す
    LANCZOS     PSNR 23.91 dB
    直した      PSNR 21.71 dB   1.12s / 871,166,464 B
```

**どちらも PSNR は下がるが、目で見ると明らかに良い。** 1:1 で拡大して並べると、
A は JPEG の 8x8 のブロックと色のにじみが消え、木目の筋が基準とほぼ同じに戻る。
B は LANCZOS のぼやけに対して輪郭と質感が立つ。GAN 系は基準に無い質感を作るので
画素単位の一致は落ちる、という既知の性質そのものである。

ずれや明るさの狂いではないことは確かめた（変位を -2..+2 で走査して最良が dy=0,
dx=0、平均 133.66 -> 133.13）。標準偏差だけが 68.16 -> 71.54 と上がっている。
**知覚品質の指標（LPIPS / NIQE）は測っていない。** ブレ補正（NAFNet, L2 学習）で
PSNR を使ったのは正しいが、この重みには当てはまらない。

基準は局所で生成した写真らしい画像であって、**カメラで撮った写真ではない**。
前回からの「実写の写真での比較はできていない」は解消していない。

### 実ブラウザ

`scripts/ux_upscale_scale_e2e.py`（standalone、Chromium headless、1280x900）。

```text
1024x1024   原寸のまま / 2倍 / 4倍 が出て、既定は 4倍
            案内 "1024×1024 → 4096×4096（およそ 23 秒）"
            原寸を押すと "1024×1024 のまま（およそ 23 秒）"（矢印は出ない）
2000x1500   原寸のまま / 2倍。4 倍は 48MP で上限を超えるので出さない
            "…｜4倍は 24,000,000 画素を超えるので選べません"
4032x3024   選べるのが 1 つなので選択肢そのものを出さない
            "4032×3024 のまま（およそ 4 分）｜2倍・4倍は…選べません"
            前はここで "この画像は大きすぎます" だった
```

倍率は models.json の `target_scales` から出す。画面は決め打ちを持たない。

### 未実施

```text
ControlDeck 統合下での end-to-end   dev の service は host lease を要求するため、
                                    HTTP から実 GPU 生成を回せない。核の解決・
                                    worker 実プロセス・実ブラウザまでで確認した
実写の写真での画質比較              手元にカメラの写真が無い
LPIPS / NIQE                        依存を足していない。目視のみ
```

`./mf.sh test` 823 passed（新規 15 件）。

## 塗った所に描き足す — 書き換えになっていた（2026-09-01）

利用者から「塗った場所に書き足すがうまくいかない」「**書き足すというより、書き換える
じゃないか**」。そのとおりで、実際に書き換えていた。

### 塗った所を model へ渡していなかった

経路はこうなっていた。塗った範囲の外周 64px を切り出す → **その切り抜きを丸ごと
描き直す** → 返ってきた絵から塗った所の画素だけ採る。`self.pipeline(image=..., prompt=...)`
にマスクは入っていない。マスクは切り抜きの位置決めと、後段の合成にしか使っていない。

model は「塗った所に描け」と聞いていない。切り抜き全体を prompt で描き直し、それが
塗った形に切り抜かれる。**書き足しではなく書き換えである。**

実機で再現した（1024x1024、空に 200x170 の楕円、"a small red bird flying"）:

```text
切り抜き 329x299 -> 336x304 で全体を描き直し、47.0 秒
  楕円の形がそのまま帯として出る（描き直しで露出が変わり、楕円の中だけ差し替わる）
  鳥は楕円の上端に小さく、大半が切り落とされている
```

diffusers 0.40.0 には `Flux2KleinInpaintPipeline` がある。いま採用している重みの
ままで使える（構成要素は base と同一なので、載せ直しも追加の常駐も無い）。

### 2 つめの罠 — 蒸留の宣言が引き継がれない

`Flux2KleinInpaintPipeline(**pipeline.components)` は `is_distilled` を受け取らない
（構成要素ではないので `components` に入らない）。既定は False で、そのとき pipeline は
classifier-free guidance を前提にする。klein は蒸留済みで guidance が焼き込まれており、
そこへ 1.0 を渡すと **prompt がほとんど効かない**。

実機では、帯は消えたが頼んだ鳥が出ず、塗った所が周りの続きで埋まるだけになった。
これは「消して埋める」の動きであって、描き足しではない。`base.config.is_distilled` を
引き継いだら prompt が効いた。

塗った範囲を振って確かめた（"a large red hot air balloon"、4 歩）:

```text
塗り  3.2% (200x170)   気球が塗った所に出る
塗り 17.4% (480x380)   気球が塗った範囲を埋める
塗り 40.7% (820x520)   大きな気球
いずれも塗っていない所（杭・草・砂利）は元のまま
```

### 周りをどれだけ見せるかは、幅ではなく割合で決まる

塗った所を渡す経路にしても、塗った範囲が広いと model が塗った所の中に**自分の背景
ごと**描いた（曇り空の中で、塗った楕円の中だけが青空になる）。効いていたのは周りの
幅そのものではなく、**切り抜きに対して塗った所が占める割合**だった。

480x380 の塗りに "a large red hot air balloon" を頼んで、周りの幅を振った実測:

```text
周り  64px   切り抜き 568x504（塗り 63%）   18.0s  17.9 GB  楕円の縁が見える
周り 160px   切り抜き 664x600（塗り 43%）   87.3s  18.6 GB  曇り空に馴染む
周り 320px   切り抜き 824x760（塗り 29%）  154.6s  19.9 GB  馴染む。費用 8.6 倍
```

固定 64px をやめ、塗った所の長辺の 1/3（下限 64px）にした。480 に対して 160 になり、
透かし程度の小さな塗りは下限が効くので費用がほとんど変わらない。

切り抜きは元画像の大きさと塗った範囲で決まるので、大きな写真に広く塗ると際限なく
伸びる。attention は面積の二乗で効くため、切り抜きだけに 1024x1024 の上限を掛けた。
**生成そのものには掛けない** — 掛けると、いま 2048 まで通っている参考編集が黙って
縮む。前はどちらにも上限が無く、大きな塗りは card に載らない大きさまで伸びていた。

### 直した後（R9700 / gfx1201、adapter の経路そのまま）

```text
             所要     peak VRAM        塗っていない所の最大差
bird        38.5s   16,677,486,080 B   0
balloon     91.7s   18,430,786,560 B   0
flower      40.0s   17,132,960,256 B   0
（前）      47.0s   —                  帯が残り、頼んだものは楕円の縁で切れる
```

`validate_strict_edit` は 3 件とも passed。塗っていない所の最大差を独立にもう一度
測っても 0 だった。VRAM は生成の実測（29.6GB）より下がる。

### 残っている粗さ

塗った範囲が広く、頼んだものが自分の背景を持つ場合（空に浮かぶ気球など）、model は
塗った所の中にその背景ごと描くので、**塗った形が縁として見えることがある**。周りを
広く見せたことで大きく減ったが、消えてはいない（気球は雲の一部が縁に残る。鳥と花は
縁が見えない）。書き換えではないので写真そのものは壊れない。

### 未実施

```text
ControlDeck 統合下での end-to-end   dev の service は host lease を要求する。
                                    adapter の経路と strict 検証までで確認した
実ブラウザ                          画面側は変えていない（文言も操作も同じ）
周りの割合 1/3 の根拠                1 件の塗りで測った。他の被写体・他の写真では
                                    測っていない
```

`./mf.sh test` 810 passed（新規 2 件）。

## FLUX.2-dev 32B を GGUF で載せる（2026-09-01）

利用者から「Flux で、私の環境で動くより大きなモデルを下さい」「FLUX.2 dev 32B で
別ランタイム含め用意して」「Gguf」。

### 駆動系は既にあった

`stable-diffusion.cpp` の pinned build（`97d2990`、2026-08-19）に `docs/flux2.md` が
入っている。**MiniMax H3 で既に使っている pin がそのまま FLUX.2 に対応していた**ので、
新しい commit を立てる必要は無かった。同じ commit を gfx1201 / HIPBLAS / Release で
建て直した（Ninja、-j8）。

```text
sd-cli sha256 7d4b5a3577db1785158d2feab3a10f55fcde42b1e4c036908991d6aaedc27494
--list-devices  ROCm0 = AMD Radeon AI PRO R9700 / gfx1201 / 32,624 MiB
                ROCm1 = 統合 GPU gfx1036 / 15,547 MiB（掴ませない）
```

前回記録の `7c2aebea…` とは異なるが、同じ commit である（前回は Unix Makefiles で
-j1、今回は Ninja で -j8）。

### 重みは 3 つのリポジトリから来る

```text
拡散  flux2-dev-Q4_K_M.gguf                     20,082,414,560 B  city96/FLUX.2-dev-gguf
文章  Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M 14,333,922,848 B  unsloth（Apache-2.0）
VAE   full_encoder_small_decoder.safetensors        249,519,092 B  BFL small-decoder（Apache-2.0）
                                            合計 34,665,856,500 B
```

**3 つとも gated ではない。** 本体の `black-forest-labs/FLUX.2-dev` は gated だが、
VAE は上流の文書が代替として案内している別リポジトリの Apache-2.0 版で足りる。
HF のトークンは要らなかった。

FLUX.2 は CLIP+T5 をやめて汎用の言語モデルを文章符号化器に据えた設計である。Klein 4B
でも同じ形で、実測すると text_encoder 8.05GB（Qwen3）/ transformer 7.75GB / vae 0.17GB。
「4B」のリポジトリが 16GB あるのはそのためで、dev ではここが Mistral 24B になる。

registry の導入判定は、weight の実体が**主リポジトリの配下**にあることを求める
（`_weight_matches`）。MiniMax H3 が別リポジトリの VAE を抱えているのと同じ形に
組み、blob 名は宣言した sha256 に一致させた。

### `--offload-to-cpu` はこの機械では成立しない

上流の例に従って `--offload-to-cpu` で回すと、**11 分進まなかった**。

```text
文章符号化まで  正常（12,057.93 MB を ROCm0 へ展開 → 10.16 秒 → 解放）
拡散本体        19,152.06 MB を RAM へ展開する段階で停止
                CPU 87.7%（1 コア）/ GPU 3% / RSS 25.53 GB / swap 2→4 GB
```

重みを RAM に置いて VRAM へ流し込む方式なので、RAM 30GB を使い切って swap と往復
していた。計算ではなくメモリ移動で詰まっている（GPU が遊んでいる）。

拡散を直接 VRAM に置き、文章モデルだけ RAM に残す配分に変えたら通った。動画側の
MiniMax H3 と同じ `te=cpu,diffusion=ROCm0,vae=ROCm0` である。

### 実測（R9700 / gfx1201）

```text
配置   総計 34,608.50 MB = VRAM 19,271.14 MB（拡散）+ RAM 15,337.36 MB（文章）
       作業領域 flux 656.00 MB + vae 1,248.50 MB（VRAM）

512x512   4 歩   条件付け  7.14s  標本化  21.39s  復号 0.80s  全体  31.48s
1024x1024 20 歩  条件付け 13.01s  標本化 161.76s  復号 1.91s  全体 181.91s

peak VRAM 26,395,885,568 B（84 サンプル、2 秒ごと）/ 31.86 GiB
最大 RSS  26,911,692 KiB   Swaps 0
```

4 歩では網目状のムラが残る。dev は蒸留された歩数モデルではないので、既定を 20 歩に
した。20 歩の 1024x1024 は写真として通る出来だった。

Klein 4B（1024x1024、4 歩、20.8 秒）に対して **8.7 倍遅い**。

`policy_rank` は**小さいほど優先**である（`router.py` が昇順に並べる）。最初これを
逆に読み、`auto` を 0 にして「おまかせの候補から外した」つもりでいた。実際には
**おまかせで最優先**になる置き方で、1 枚 3 分が既定になるところだった。速さで選ぶ
方針（auto / fast / balanced / low_vram）では 4B より大きい数、質で選ぶ方針では
小さい数にした。試験は絶対値ではなく 4B との前後関係で書いた。

### 本番の worker を実プロセスで通した

評価用の経路ではなく、`worker_packs.image.worker` に本番と同じ payload を渡した。

```text
outputs        1024x1024 RGBA PNG 1,851,581 B
generation_sec 179.02
runtime_version 97d2990807fe6d558e395f8764198d7c7e7b411c
placement      text_encoder=cpu / diffusion=ROCm0 / vae=ROCm0
```

`runtime_version` は diffusers の版を返していた。native の経路は diffusers を通らない
ので、そのまま記録すると嘘になる。adapter が名乗る値を優先し、無いときだけ diffusers
の版に落ちるようにした。

画像側にも native の駆動系を使うものが出たので、核は画像 worker にも
`MEDIA_FORGE_NATIVE_RUNTIME_ROOT` を渡すようにした。渡さないと adapter は起動できない。

### 未実施

```text
ControlDeck 統合下での end-to-end   dev の service は host lease を要求する。
                                    本番 worker の実プロセスまでで確認した
参照画像による編集                  sd-cli は `-r` を持つが測っていない。
                                    adapter は受けたら断る
Klein 4B との画質比較               同じ prompt・同じ seed での並べ比べはしていない
歩数の詰め                          20 歩で採った。28〜50 は測っていない
実ブラウザ                          画面側は変えていない（一覧に 1 つ増えるだけ）
```

`./mf.sh test` 810 passed（新規 2 件）。

## iPhone の写真が投入できなかった（2026-09-01）

利用者から「写真だが定型のサイズしか入らないの？」「任意のサイズに切り取った画像を
iPhone で選択しても投入されない」。

### 変換する仕組みはあったのに、選択でそこまで届いていなかった

```html
frontend/index.html:238
  <input id="source-file" type="file" accept="image/png,image/jpeg">
```

iPhone の写真は既定で HEIC である。画面には HEIC を canvas で PNG へ直す経路が
**既にあった**（`converting = !IMPORTABLE_TYPES.has(file.type)`、コメントにも
「端末の写真は HEIC のことがある」と書いてある）。届いていなかっただけである。
選択の絞り込みを `image/*` にした。参考画像の入口も同じだったので揃えた。

塗った範囲の入口（`#mask-file`）は画面が作る PNG しか受けないので、そのままにした。

### 復号を端末に任せる経路を足した

`createImageBitmap` が HEIC を断る版がある。そこで諦めると「選んだのに何も
起きない」になるので、断られたら `<img>` へ落とすようにした。Safari は `<img>`
なら HEIC を復号する。EXIF の向きは、どちらの経路でも見えているとおりに開く。

`ImageBitmap` 以外は `close()` を持たないので、呼び出しを `close?.()` にした。

### 断りが、出したそばから消えていた

読めない画像を選ぶと `showError` は出ていたが、その後 `refreshAttachment` の末尾と
`selectEditMode` の 2 か所が `clearError()` を呼んで消していた。**画面に残るのは
添付欄の小さな文字だけ**で、これも「選んでも何も起きない」の一因だった。

添付が読めていない状態を `state.attachProblem` として持ち、`clearError()` は立って
いる断りを残すようにした。次の写真を選んだときに下ろす。

### 実ブラウザ（`scripts/ux_phone_photo_e2e.py`、Chromium headless、390x844）

```text
accept              source / reference とも image/*
IMG_0001.HEIC       1007x661 のまま載る。送るのは image/png へ変換したもの
IMG_0002（type 空） 同上。形式を名乗らない端末でも通る
shot.png            そのまま送る。余分な canvas を通さない
notes.txt           載せない。「読み込めませんでした」が画面に残る
```

**Chromium は HEIC を復号しない。** ここで確かめられるのは「PNG / JPEG 以外が選択を
通り、変換されて原寸のまま載るか」までで、実際の HEIC 復号は端末側の仕事である。

### 未実施

```text
実機の iPhone            HEIC の復号そのものは Chromium では測れない
ControlDeck の埋め込み下  standalone で確認した。iframe 越しは未確認
```

`./mf.sh test` 808 passed（画面のみの変更で、新規テストは実ブラウザ側）。

## 直すだけの道具が、土台のモデルとして並んでいた（2026-09-01）

利用者から「Flux がモデル選択に出ない」。出ない理由は稼働中がリリース版で PR が
未 merge だったからだが、確認の途中で**別の不具合**が見つかった。

土台の一覧に「NAFNet ブレ補正」と「LaMa 消して埋める」が並んでいた。どちらも
「無から絵を作る」ことはできない。実測でどれも落ちる。

```text
model_policy=manual で 512x512 の生成を投げた
  tog/nafnet-models               failed  model_unavailable
  AEmotionStudio/lama-inpainting  failed  model_unavailable
  mikestealth/SwinIR              failed  model_unavailable
```

`isBaseModel` が**拡大 1 つを名指しで除いていた**のが原因である。

```js
return capabilities.some((name) => name !== "image.upscale");
```

この関数のコメント自身が「ここに並ぶと、選んだ利用者のあらゆる『作る』が
model_unavailable で落ちる（実機でそうなった）」と書いている。拡大を足したときに
書かれた規則が、ブレ補正と消して埋めるを足したときに追随していなかった。

除く根拠を名前から性質へ変えた。「直すだけ」の capability しか宣言していないものは
土台になれない。次に直す道具を足しても、その集合へ 1 行足すだけで済む。

### 実ブラウザ（`scripts/ux_base_model_choices_e2e.py`）

```text
前  おまかせ / FLUX.2 Klein 4B / Segmind SSD-1B / NAFNet ブレ補正 / LaMa 消して埋める
後  おまかせ / FLUX.2 Klein 4B / Segmind SSD-1B
```

一覧に並ぶ数と選択肢の数が一致すること、直すだけの道具が並ばないこと、作れるものが
落ちていないことを、カタログの宣言から導いて確かめている。

`./mf.sh test` 808 passed（画面のみの変更で、証跡は実ブラウザ側）。

## 使うモデルの一覧が、頼む操作に追随していなかった（2026-09-01）

利用者から「FLUX.2-dev を iPhone で選択すると使えるモデルがないと出る」。

### モデルによって、できることは違う

FLUX.2-dev は `image.text_to_image` しか宣言していない。編集は宣言していない。
それでも編集のときに一覧へ並んでいたので、選んで押すと落ちる。実機
（インストール版 0.21.0）で確認した。

```text
image.generate  manual=city96/FLUX.2-dev-gguf  -> routing 通過
image.edit      manual=city96/FLUX.2-dev-gguf  -> model_unavailable
```

画面はこれを「使えるモデルがありません。」と出す。**モデルは入っていて健全で、
選択肢にも並んでいるのに、である。**

一覧を組むときに、いま頼もうとしている操作が要る capability を見るようにした。
添付が無ければ `image.text_to_image`、あれば選んでいる直し方の capability。まだ
直し方を選んでいないときは絞らない（絞る根拠が無いのに減らすと、選べたはずの
ものが消える）。

指定していたモデルが一覧から消えたときは、`renderModelChoice` が既におまかせへ
戻す作りになっていた。そこはそのまま効く。

### 直すだけの操作では、そもそも選ばせない

拡大・ブレ補正・消して埋めるは capability でモデルが 1 つに決まる。選ばせる意味が
無いうえ、前に指定したモデルが残っていると、それが直せないモデルなので同じ
`model_unavailable` になる。`#model-choice` を出さず、指定も外す。

`data-generate-only` という属性が markup に付いていたが、参照している所は無かった。
死んだ宣言に頼らず、`REPAIR_MODES` から出す。

### 1 件も無いときの案内

「使えるモデルがまだありません。設定から導入してください」は、**入れてはあるが
この操作ができない**ときには誤りである。次にやることが違う（導入ではなく、別の
直し方を選ぶ）。2 つを分けた。

なお `model.installed && model.healthy` を含む行は、契約試験が「LoRA を除いて
いるか」を見張っている。ここで訊いているのは土台に選べるかではないので、
`anythingInstalled()` として別の名前で書いた。試験は正しく反応した。

### 実ブラウザ（`scripts/ux_model_choice_follows_the_job_e2e.py`、390x844）

```text
添付なし          文章から作れるものが並ぶ
写真 + 全体を直す  文章からしか作れないものが消える。指定も auto へ戻る
写真 + 画質を上げる 使うモデルの欄そのものが出ない
```

`./mf.sh test` 827 passed。

## FLUX.2-dev は編集できる。私が測らずに「できない」と書いていた（2026-09-03）

利用者から「本当に画像変更できないの？改めて Flux dev の仕様書や Reddit などを
チェックして」。**指摘のとおりで、私の誤りだった。**

### 何を間違えたか

FLUX.2-dev を入れたとき、`image.text_to_image` だけを宣言した。参照編集を測って
いなかったからである。そこまでは正しい。誤りはその後で、**自分が書いた宣言を根拠に
「モデル側の制約でできない」と説明した**ことである。循環している。

モデルカードには最初からこう書いてある。

```text
"a 32 billion parameter rectified flow transformer capable of generating,
 editing and combining images based on text instructions"
"excels in single-reference editing and multi-reference editing"
参照画像は最大 10 枚、4 メガピクセルまで
```

自分で引用した sd.cpp の `docs/flux2.md` にも「All variants support image editing
with the `-r` flag for context inputs」とあった。読んでいたのに、宣言の方を信じた。

なお**ライセンスは非商用のままである**（`flux-non-commercial-license`）。検索結果に
Apache-2.0 とあったのは Klein との取り違えで、Hub の API で確認した。

### 実測（R9700 / gfx1201、1024x1024、20 歩）

```text
生成のみ              181.9 秒
参照 1 枚の編集       436.1 秒（7:16）   最大 RSS 18.8 GB  Swaps 0
参照 2 枚の合成       724.0 秒（12:04）  最大 RSS 21.4 GB  Swaps 0
塗った所を指す編集    212.9 秒（3:33）   最大 RSS 22.0 GB  Swaps 0
```

参照 1 枚で 2.4 倍、2 枚で 4.0 倍。条件付けの系列が参照ごとに伸びるので素直に
比例する。2 枚の合成では「image 1 の杭を image 2 の納屋の前に」という**番号での
指定が効いた**（`--increase-ref-index`）。

単一参照編集は、元の杭のひび割れ・樹皮・節・垂れた草の茎まで保ったまま季節だけを
冬に変えた。参照編集として期待どおりに働く。

### 塗った所は「守る範囲」ではなく「指す場所」

`--mask` を渡すと、頼んだ鳥の群れは塗った楕円の中に出た。ただし**塗っていない所も
描き直されている**。

```text
塗った所の外  最大差 224  平均 3.52   ← 1px も変わらない、ではない
塗った所の中  最大差 246  平均 53.88
```

この repo の strict edit は「塗っていない所は 1px も変わらない」を不変条件にして
いる。貼り戻せば差は 0 になり `validate_strict_edit` も passed になる（GPU を使わず
確かめた）。**しかしそれをすると塗った形が縁として出る。** model が描いた空と元の
写真の空とで露出が違うためで、PR #195 で Klein 4B について直したのと同じ現象である。
あのときは塗った所を model へ渡すことで解いたが、この経路では `--mask` を渡しても
model は絵全体を描き直して返すので、同じ手が効かない。

守れない保証を名乗るより、守らないと言う方を選んだ。`image.inpaint` は宣言しない。
代わりに `image.masked_edit` を足した。**塗った所は指す場所である**、という別の
capability である。画面では「塗った所を指して直す」、保証欄は「画像全体が変わる
ことがあります」。Klein 4B の「塗った所に描き足す」（1px も変わらない）はそのまま残る。

`strict_edit` を真で受けたら断る。名乗らせると、核が後段で守れたことを検証して
しまう。

### 本番の worker を実プロセスで通した

```text
参照編集        1024x1024  生成 406.5 秒  postprocessing ['pil.convert.rgba']
塗った所を指す  1024x1024  生成 250.5 秒  同上
```

`postprocessing` に strict の合成が入っていない。保証を名乗らない経路なので、
入っていたら誤りである。塗った所を指す編集では、合成しないぶん縁が出ない。

### 未実施

```text
参照 3 枚以上          モデルカードは 10 枚までと言う。2 枚までしか測っていない
image.variation        宣言していない。測っていない
ControlDeck 統合下     本番 worker の実プロセスまでで確認した
実ブラウザ             「塗った所を指して直す」の画面は未確認
```

`./mf.sh test` 827 passed。

### 触っていない不安定なテスト

`test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_up` が
ときどき落ちる。websocket を閉じた後の後始末を 5 秒待って見る作りで、機械が忙しいと
間に合わない。**このスライスとは無関係である。** 負荷を揃えて交互に 10 回ずつ回した:

```text
origin/main    passed=4  failed=6
このブランチ    passed=5  failed=5
```

手を触れていない main の方が多く落ちる。テスト自身のコメントも「待たずに見ると、
機械が忙しいときだけ落ちるテストになる（実際そうなっていた）」と書いており、5 秒では
足りていない。直すなら別のスライスにする。

## UX1 差分の 4 枚で model を 4 回載せ直していた

`creative_batches.py` は 4 枚の差分を `count=1` の job 4 本に展開する。worker の
`main()` は stdin を 1 行ずつ読む loop で、`ImageWorker` は読み込んだ adapter を
`model_id` で持ち続ける。つまり載せたまま次の要求を受けられる作りである。ところが
呼び出し側が `process.communicate(payload)` を使っていた。`communicate` は stdin を
閉じるので、worker は 1 本ごとに終わり、次の job はまた最初から載せていた。

実機の log に残っていた、続けて走った job の載せ直し:

```text
data/features/media-forge/logs/service.log
load_sec=12.637492 generation_sec=16.041516
load_sec=13.154964 generation_sec=15.535938
load_sec=12.775642 generation_sec=15.543959
```

生成が 15.5 秒の要求に、載せ直しが 12.6〜13.2 秒付いていた。

### 直した後

`_exchange_while_progressing` で 1 要求 1 応答を交換し、プロセスは残す。続きの job が
無くなったときだけ下ろす。4 枚ぶんの job で worker を何回起こすかを数えた:

```text
jobs=4  worker_spawns=4   変更前
jobs=4  worker_spawns=1   変更後
```

`fake_settings` の JobManager に 4 本投入し、`asyncio.create_subprocess_exec` を数えた。
実測の載せ直し時間は GPU を llama-server が 22.6 GB 使用中のため測っていない。

### 一緒に直した 4 件

```text
先読みバッファ    `for raw in sys.stdin.buffer` は EOF まで 1 行目を返さない。
                  stdin を開いたまま待つ使い方では止まる。readline にした
print の buffer   pipe 相手の print はブロックバッファで、書いても届かない
返り値の判定      `returncode != 0` は、残してある worker を crash と見なす。
                  失敗は応答の形（`error`）で見る
後始末            communicate は pipe を畳んでいた。使い回しでは自分で畳まないと
                  transport が GC 任せになり、loop を閉じた後に落ちる
```

最後の 1 件は、`stop()` が job task を cancel すると片付けの途中で取り消されて
worker が残る、という形でも出ていた。取り消されても pipe だけは同期で畳む。

`./mf.sh test` 829 passed（warning は 25 件から 1 件に減った）。

## host 配置（システムRAM）への追従

ControlDeck の broker は 2026-09-04 に「誰を追い出すか」から「どこへ載せるか」へ
変わった（`docs/design-ai-resource-broker.md` §0）。LLM の KV が RAM へ落ちると
デコードが致命的に遅くなる（実測 75.4 → 32.6 tok/s）一方、画像生成のような
計算律速の処理は RAM 配置の劣化が桁違いに小さい、という非対称からである。

Add-on 側の契約は 3 つ。

```text
1  CPU で走らせられるなら preferred_devices: ["gpu0", "host"] を送る
2  実際の配置は grant の RequestStatus.device_id が返す
3  device_id == "host" なら VRAM を確保せず RAM で実行する
```

3 を守れないものは host を要求してはならない。要求しなければ従来どおり VRAM だけが
候補になる（`_eligible_devices` の opt-in）。

### 送る側

`image_model_request` は、CPU で走らせられる adapter のときだけ host を候補に挙げる。
`native.stable-diffusion-cpp-*` と `spandrel.upscale` は GPU 前提の駆動系なので挙げない。

`compute_mode` を `exclusive-preferred` から `shared-safe` に変えた。exclusive は
「その device に他の lease も provider 予約も無いこと」を求めるので、LLM が載って
いる限り VRAM の空きに関係なく `device_busy_exclusive` で断られ、共存にならない。
バイトの勘定は `admitted_free_bytes`（observed と予約の大きい方を使う）が見ている。

### 受ける側

grant の `device_id` を `HostExecution` に持ち、`host` なら worker へ渡す
`device_mode` を `cpu` にする。adapter は `pipeline.to("cpu")` で載せ、`torch.cuda`
には触らない。初期化されていない GPU に `synchronize` を投げるとそこで落ちる。

置き場所は 2 か所の鍵に入れた。どちらも「VRAM に載せたものを host 配置の要求へ
渡さない」ためである。

```text
warm worker の署名     置き場所が違えばプロセスを作り直す
adapter cache の鍵     (model_id, device_mode)。model_id だけだと使い回す
```

乱数の器も置き場所に合わせた（`torch.Generator(device=...)`）。CPU と CUDA の
generator は同じ seed でも違う雑音を出すので、**配置が変わると同じ seed でも絵が
変わる**。これは避けられない。

### 測っていないこと

CPU 実行の所要時間は測っていない。GPU を llama-server が 22.6 GB 使用中で、
FLUX.2 Klein（15 GB）を載せると OpenCode 側の LLM を壊すためである。
既知の近い実測は `docs/models.md` の SD 512x512 / 4 歩の比較で、
`direct_device_map` 15.0 秒に対し `cpu_offload`（RAM 常駐・GPU へ逐次転送）が
18.1 秒、ピーク VRAM は 21.8 GB から 8.9 GB だった。`cpu` はそれよりさらに遅い。

`./mf.sh test` 838 passed。

## 生成のたびに LLM を降ろさせるのをやめる

`_release_host_ai` は、実モデルの生成に入る前に毎回 ControlDeck へ「AI ターンを
終える」と宣言していた。画像モデルが 34.2 GB のカードに 33.35 GB を要り、
場所を空けてもらう以外に載せる方法が無かった頃の作りである。

broker が host 配置を持つようになって前提が変わった。VRAM が空いていなければ
生成は RAM へ載る。場所を空けてもらう必要が無い一方、降ろさせる側の代償は
そのまま残っていた ── 使っている最中の OpenCode や chat のモデルを、画像 1 枚の
ために落とすことになる。

消したもの:

```text
_release_host_ai              生成前の宣言そのもの
phase="release_ai"            それを表示するための段階と、UI の不確定表示
_ai_release / _VRAM_WAIT_REASONS
                              拒否理由を握って、後の受理失敗に添えるための保持
host_ai_residency_retained    その言い換え。降ろさせないので起きない
HostAIGateway.release         上を消すと呼び手が居なくなる
HostAIReleaseResult
JobManager(ai_gateway=...)    release 以外に使っていなかった
```

`HostAIGateway` 自体は残る。演出の立案・prompt・評価が `ai.inference` を使う。
ControlDeck 側の `POST /{addon_id}/ai/release` も残る。あれは利用者が「AI の番を
終えた」と宣言する経路で、add-on が job ごとに叩くものではない。

受理の待ちそのもの（`waiting` の 0.5 秒間隔の照会、`max_wait_sec` 300）は残す。
broker の受理は非同期で、照会以外に知る方法が無い。

acceptance script（`g6_resource_turn_e2e.py` / `_physical_e2e.py`）は、
「LLM が VRAM を返したこと」を確かめる形から「LLM が VRAM を持ったまま生成が
通ること」を確かめる形へ変えた。物理側の `ai/release` stub は呼ばれなくなるので
消した。

`./mf.sh test` 833 passed。

## RAM 配置の必要量を VRAM の見積りと分ける

host 配置は宣言だけあって、**一度も効いていなかった**。broker の `_required_bytes`
は device を問わず `vram.required_bytes` を返す。`vram` の見積りは `device_map` で
段階的に載せるときの GPU 側ピークで、RAM 配置の実態とは別物である。

CPU 実行を実測した（2026-09-04、FLUX.2 Klein 4B、`device_mode: cpu`）。
llama-server が VRAM 22.6GB を使ったまま、GPU を一切触らずに測れる。

```text
                       generation_sec   最大RSS      VRAM
512x512  / 4歩              40.26      16.26 GB    変化なし
1024x1024 / 4歩            113.44      18.76 GB    変化なし
placement: pipeline / text_encoder / transformer / vae すべて cpu
```

申告している `vram.required_bytes` は 31.1 GB で、実態の約 2 倍である。この機械の
RAM は 30 GB なので、31.1 GB の要求は host device の総容量を超え、必ず落ちる。
`admitted_free_bytes` との比較で弾かれて gpu0 が空くまで待ち続ける ── つまり
「VRAM が空いていなければ RAM へ」が成立していなかった。

ControlDeck 側に `ResourceRequest.host_bytes` を足し（PR #254）、MediaForge は
実測した常駐量に headroom を足して送る。測っていないモデルには送らない。小さすぎ
れば OOM、大きすぎれば載らない。どちらも推測で決めてよい数字ではない。

カタログの `measurements.host_resident_bytes` は任意である。GPU 前提の駆動系や、
まだ測っていないモデルは持たない。

参考として、カタログの GPU 経路は `measured_runtime_sec` 208.8 秒である。CPU の
113.4 秒はそれより速いが、測り方（cold load を含むか）が違うので直接は比べられない。

`./mf.sh test` 836 passed。

## VRAM の測り方が間違っていた

`DeviceSampler.peak()` がカード全体の使用量の**絶対値**を返し、`baseline` を引いて
いなかった。同じファイルの `GpuMemoryMonitor` は `incremental_peak_bytes` を持って
いるのに、評価側だけが絶対値を採っていた。測定時に載っていた LLM の VRAM が丸ごと
「このモデルに要る量」として記録されていた。

```text
FLUX.2 Klein 4B（重み 15GB）      申告        実測（2026-09-05）
読み込みピーク                 30.1 GiB     14.87 GiB
実行ピーク                     27.6 GiB     20.86 GiB
required_bytes                 31.1 GiB     21.9 GiB
生成 1024²/4歩（2枚目）        208.82 秒     2.98 秒
```

32GB のカードに載らないモデルとして扱われ、「~33GB が確保できません」で拒否されて
いた。RAM 配置（host_bytes）が 30GB の機械に永久に載らなかったのも同じ数字が原因。

直しは 2 段構えにした。

```text
DeviceSampler.increment(baseline)   外から見るなら増分を使う
worker が自分の確保量を申告        torch.cuda.max_memory_allocated()
```

増分でも、測っている間に他の process が伸びれば混ざる。確保した本人に聞けば混ざら
ない。申告があるときはそちらを使い、無いときだけ増分に落とす。

## lease を返しても VRAM は空いていなかった

生成の lease は評価の前に返す。exclusive な画像 lease を持ったまま Host に VLM を
載せさせると単一 GPU で deadlock するからである。ところが差分の 4 枚で載せ直さない
ために worker を残す作りにしたぶん（`_reuse_or_spawn_worker`）、**lease を返しても
VRAM は空かない**。broker から見て「空いた」のに物理的には埋まったままになり、
入らないはずの VLM が admit される。

```text
jobs.py  _release_host_resource()   lease を返す。broker は空いたと見る
         ↓ worker は生きていて 21GiB を握ったまま
         postprocess → vision.analyze   VLM の読み込みを要求
         ↓
         worker を終わらせるのは job queue が空になったとき（もっと後）
```

救っていたのは `observed_used_bytes`（2 秒間隔で更新）だけだった。

評価を行う job では、lease を返す前に worker を終わらせるようにした。評価を行わない
job では worker を残すので、差分の 4 枚で載せ直さない利点は保たれる。

## 全常駐できないときの下限を申告する

`measurements.minimum_vram_bytes` を足した。broker はここまで枠を切り詰めて貸し、
利用者はその枠に自分を縛る（ControlDeck #256）。実測で 8 GiB では成立し、7 GiB では
OOM したので 8 GiB を宣言する。測っていないモデルには送らない。

`./mf.sh test` 840 passed。

## 貸してもらった枠の中で走る

ControlDeck が空き状況から枠を決め（#256）、worker はその枠に自分を縛る。add-on は
他に何が載っているか知らないので、固定値を名乗ると LLM の構成が変わるたびに破綻する。

```text
grant の granted_bytes         →  HostExecution.granted_bytes
  ↓
枠 ≧ 全常駐   direct_device_map   カタログどおり VRAM に載せる
枠 < 全常駐   cpu_offload         重みは RAM、実行するモジュールだけ VRAM へ
device_id=host                cpu  VRAM を取らない
枠が返らない（旧 Host）        カタログの値のまま（後方互換）
  ↓
MEDIA_FORGE_VRAM_BUDGET_BYTES →  torch.cuda.set_per_process_memory_fraction
```

### 実機の通し確認（2026-09-05、llama-server 常駐のまま）

```text
枠 7.92 GiB を渡す      実ピーク 7.83 GiB（枠内に収まった）
device_mode             cpu_offload（自動で切り替わった）
生成 1024²/4歩          38.88 秒（初回。2 枚目以降は 6.7 秒）
llama-server            22.95 GB を保持したまま無傷
```

枠を割ったときは、この process だけが HIP の OOM で落ちる。実測で枠 7/6/4/3 GiB の
いずれでもカードには 24.5〜28.5 GiB の空きが残り、LLM は無傷だった。**見積りを
外しても被害が add-on 側に閉じる**ので、管理側が枠を決める形が安全に成立する。

### LLM が居ない場合

```text
LLM が居ない              gpu0  枠 24.26 GiB  → direct_device_map（全常駐・最速）
LLM 常駐・使用していない   gpu0  枠 10.44 GiB  → cpu_offload
LLM 常駐・使用中           gpu0  枠 10.44 GiB  → cpu_offload
大きい LLM 常駐・使用中     host  枠 18.89 GiB  → cpu
```

LLM が居なければ従来どおり全常駐で最速になる。速度を落とすのは、落とさなければ
そもそも走れない場合だけである。

`./mf.sh test` 846 passed。

## 空いているぶんを使う（モデルごとの下限をやめる）

`measurements.minimum_vram_bytes` を撤回した。モデル固有の値を宣言すると、測って
いないモデルは枠を貸してもらえず、測った値が少しでも足りなければ**そのモデルだけ
突然使えなくなる**。実際 FLUX.2 Klein 4B で 1 枚ぶんの実測 8 GiB を宣言したところ、
連続生成の 2 枚目が OOM した。

```text
枠  7.92 GiB   1枚目 成功（ピーク 7.83）→ 2枚目 resource_oom
枠 10.44 GiB   4 枚とも成功  22.05 / 35.23 / 5.36 / 5.17 秒
```

必要量は解像度・枚数・参照画像で変わるので、事前に 1 つの数字で言い当てられない。
`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True` でも改善しなかったので、断片化では
なく offload の残留分である。

代わりに「これ未満では何をやっても動かない」線（2 GiB）だけを共通で置き、足りるか
どうかは実行が決める。外したら軽い載せ方へ落として走り直す。

```text
direct_device_map  →  cpu_offload  →  cpu（RAM のみ）
```

実機で確認（2026-09-05、llama-server 常駐のまま）:

```text
枠 2GiB / cpu_offload   resource_oom（worker だけが落ちる）
降格して cpu            成功 105.45 秒
llama-server            22.95 GB を保持したまま無傷
```

RAM のみなら VRAM の空きに左右されないので、必ずどこかで着地する。broker も
`residency_key` ごとに OOM 後の下限を学習する（`oom_recommendation`）。


## 2026-09-05 — 統合3D Studio設計・実装計画（文書のみ）

利用者は画像/3DをMediaForgeへ実装まで統合する方針を選択し、設計もMediaForgeへ置くよう指定した。
別SceneForgeリポジトリ/アドオン/配布系統は使わない。

追加文書:

- `docs/design-3d-studio.md`: 設計ゴール、責務、共通Library/UI、初期提供範囲。
- `docs/design-blender-runtime-and-web.md`: 設定から導入/更新/修復/切替/削除、サーバーBlender GUI、保存/再接続/GPU/隔離。
- `docs/design-3d-assets-and-opencode.md`: scene revision、材質/画像、GLB viewer、typed OpenCode制作、durable job。
- `docs/development-release-3d-studio.md`: 既存MediaForgeの開発/管理/署名配布と実機品質gate。
- `docs/implementation/g8-3d-studio-plan.md`: 3DS-0〜8、条件付きExpert、PR単位、受入、開始指示。
- `docs/reference-3d-studio.md`: ControlDeck/MediaForge/SonicForgeの参照commitと確認事項。

AGENTS/README/base-plan/integration/workspace UX/goal-roadmap/handoffから導線を追加した。
AGENTSの古いmobile=companion指示は現行addon.jsonのembeddedへ合わせ、3D追加で退行させない規則とした。
現行ControlDeckにはpublisher署名検証、binary WS relay、detached Jobs、CPU-only job credential refreshの
コードが存在することを確認。noVNC実機、GPU GUI、長時間再接続の動作証拠にはしていない。

検証対象は文書リンク、変更差分、参照commit、既存契約との整合性。実装コード・公開schema・
addon.json・release version・OS/runtime・他リポジトリはこのMediaForge PRでは変更しない。
新規3DS機能: NOT IMPLEMENTED。unit/integration/GPU/Blender/browser/release実機受入: NOT TESTED。
次: 現行mainと対象機を再確認する3DS-0、その後3DS-1を独立PRで実装。


## 2026-09-05 — 3DS-0 current-state / compatibility baseline

PR #213はmerge commit `9469d8e4e4980752082f5081da7ba6e95d184622`でmainへ入った。
3DS-0では `tests/fixtures/3ds-baseline-contract.json` と
`tests/test_3d_studio_baseline.py` に、既存Add-on identity/mobile、Agent/workflow contribution、
public job operation/Asset MIME、G8 profile/package/runtimeを加法的互換性の基準として固定した。
対象状態とCHECK-01〜08は `docs/implementation/3ds-compatibility.md` に記録した。

実機のsource runtimeはBlender 4.5.9 / Python 3.11.11、background・GLTF import/export probeが
すべてtrue。一時data rootと実Uvicorn `127.0.0.1:9164`へ796 Bのcube GLBをHTTP importし、
実Blenderによる `asset.pack + 3d.project.glb` を2回実行した。両jobはsucceeded、44,292 BのZIPは
SHA-256 `c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`でbyte-identical、
2回目は受付から終端まで1,055 ms。entryは固定3件、終了後work entry 0 / Blender child 0。

ControlDeck管理版は `current -> versions/0.27.0`、systemd PID 1241393、9130でhealthy / contract 2.0。
live capabilityは画像を`available / local / measured / local_only`とし、live storeの最新画像Assetは
704x1472 PNG / 7,262 B。一方G8は`unavailable / runtime_not_installed`で、bundle外runtimeをinstalled
serviceから解決する3DS-1の実ギャップを確認した。新規画像GPU jobとbrowser操作は **NOT TESTED**。
Web Blender、scene/revision、viewer、材質、OpenCode制作、setup/update/repair/removeは
**NOT IMPLEMENTED / NOT TESTED**。3DS-0の証拠をこれらへ読み替えない。

最終gateはfocused 176件、`./mf.sh test` 851件がPASS（既知Starlette warning 1件 / 62.14秒）。
Python compileall、frontend JavaScript構文、shell構文、変更Markdownの相対link、
`git diff --check`もPASSした。

## 2026-09-05 — 3DS-1 Blender runtime resolver / read-only Settings diagnostics

PR #215、実装commit `4c7c6f793f2c6936b74bfc755fe5f3a29e14def6`。
MediaForge-ownedのversioned registry/resolverを追加し、既存4.5.9 runtimeを
`legacy-blender-4.5.9`としてopaque登録した。registryは258 B / mode 0600で、JSONに
`/data1tb`、`/home`、`/tmp`は含まれない。symlink registry/managed runtime、root脱出、
不正record、壊れたmanifest/stamp/executable/trusted workerをfail-closedにした。
active runtimeと既存G8用4.5.9解決を分け、設定refresh時は既存runtimeの固定identityだけを
再確認・登録し、移動、削除、download、operator指定activeの上書きをしない。

private workspaceへ`blender_runtime` session part、`blender.runtime.status`、同一origin開発用
`GET /workspace-api/blender/runtime`を追加した。応答はopaque ID、版、ownership、4 integrity check、
別管理のWeb操作pack状態、fingerprintだけでraw pathを返さない。Settingsの先頭へread-only Blender
診断を置き、ready/missing/damaged/invalid/unsupported、legacy/managed、日英locale変更、320 pxを
扱う。3DS-1ではdownload/update/repair/switch/removeを提供せず、画像機能の状態と分離表示する。

一時data rootと実Uvicorn `127.0.0.1:9164`でstatusはready、required 4.5.9、active/G8は
`legacy-blender-4.5.9`、4検査true、fingerprint
`c5015f19e7a0fb8228e426386d0e7aee19be7501852d814da1c08c0f163ebcd9`。
同じ796 B cubeをresolver経由で実Blender加工したjob
`job_23d828f247fa420995b451d07b0a5246`は1.462秒でsucceededし、ZIP 44,292 B / SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`は3DS-0とbyte-identical。
entry 3件、終了後work entry 0 / Blender child 0。

standalone Chromeで日本語ready/診断、英語rerender、別serverのmissing表示を操作した。320 pxで
clientWidth/scrollWidthはともに320、更新ボタン39 px、最終console/page/HTTP errorは0件。
実ControlDeck URLは未認証browserが`/login`へ遷移したため、installed opaque iframe操作は
**NOT TESTED**。installed 0.27.0へのsource変更deployment、GPU Blender、lifecycle操作、Web Blender、
scene/revision、viewer、材質、OpenCode制作も **NOT TESTED / NOT IMPLEMENTED**。

local gateは`./mf.sh test` 859 passed / 既知Starlette warning 1件 / 70.27秒。
Python compileall、frontend JavaScript構文、shell構文、Markdown相対link、`git diff --check`を
最終差分でも再実行する。ControlDeck変更は0件で、既存dirty `frontend/tsconfig.tsbuildinfo`を保持した。

## 2026-09-05 — 3DS-2a durable Blender install / cancel / restart

PR #216、実装commit `48ac9c9d3d3542a93b547ad64b3c2d79d4099bfc`。
Blender専用のdurable operation table/type/managerを追加した。ブラウザ入力はtrusted catalogの
install、またはopaque operation IDのcancelだけで、URL/path/version/executable/commandを受けない。
exact archive size/SHA-256、member数、展開size、traversal、link、device/FIFO、空き容量、実Blender
probeを検証してからmanaged rootへatomic配置し、opaque registryを更新する。ETag一致Rangeだけ
partialを再開し、cancel/失敗はstagingと未登録destinationを残さない。service restartは非終端journalを
queuedへ戻し、配置後registry前の停止も再probeして復旧する。private WS/standalone transportと
Settingsへ導入、進捗、cancel、日英表示を加え、画像model operation schemaは変更していない。

正規archive 377,929,956 B / SHA-256
`dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d`をローカル配信した実機
clean installは25.659秒でready、状態列はqueued/downloading/verifying/installing/probing/ready、
managed files 1,605,023,227 B。probeは4.5.9 / Python 3.11.11 / background / GLTF import/export true。
registryは282 B / mode 0600 / raw pathなし。managed runtimeで同じ796 B cubeをG8加工し、1.312秒、
ZIP 44,292 B / SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`で3DS-0/1と同一。

実archiveを8,388,608 Bでservice停止したoperationはdownloadingから再初期化でqueuedとなり、
同一ETagと`Range: bytes=8388608-`で再開、25.546秒後ready。別cancel実測はcanceled、partial
8,388,608 Bを再開用に保持、staging/destinationなし、runtime unavailable。standalone Chromeは
日英missing、catalog/license/容量、install buttonを表示し、320 px client/scrollとも320、button
39 px、console/page/HTTP error 0件。実ControlDeck opaque iframeは **NOT TESTED**。

local full gateは867 passed / 既知warning 1件 / 64.39秒、focused 240件もPASS。PyInstaller bundleは
31,147,576 B / SHA-256 `fd532fe17949eaf184a5f93697fda2bc8ec2921c289305a6b9c1b8c3516c8264`、
展開後launcher doctorは`ok / 0.27.0 / packaged=true`。一時runtime/bundle/UI領域はゴミ箱へ移した。
update/switch/repair/remove、公開release、installed Host browser、GPU Blenderは
**NOT IMPLEMENTED / NOT TESTED**。ControlDeck変更は0件。

## 2026-09-05 — 3DS-2b side-by-side Blender update / switch / repair

PR #217、実装commit `5d19897af20aabb18f218fed1ff5891e93973c79`。
official Blender 4.5 LTS catalogへ4.5.13をexact entryとして追加した。archiveは
378,033,952 B、SHA-256
`da4e69b06b75b9e642d106496c50e7e240218b411d2f6e18271c1d1d819cef91`、取得元は
`download.blender.org/release/Blender4.5/`、licenseはGPL-3.0-or-later。既存G8契約の4.5.9
entryは変更していない。UI/WS/standalone APIはURL/path/version/commandを受けず、サーバーが
検証したopaque runtime ID、または引数なしのrecommended updateだけを受ける。

更新は新版を別directoryへdownload、size/hash/archive検証、展開、実probeしてからregistryのactiveを
切り替える。旧版と失敗時activeは保持する。switchは登録済みready runtimeだけ、repairはcatalog内の
managed runtimeだけを別stagingへ再構築し、旧directoryを退避してatomic交換する。Settingsへ更新、
修復、検証済み版の選択、操作進捗を日英で追加した。standaloneは操作中だけ500 msで状態を再読込し、
終端後に停止する。埋め込みは既存`session.changed`を使いpollingしない。

一時data/runtime rootで既存の正規4.5.9 archiveからbaseを19.989秒で導入後、正規4.5.13を直接取得した
side-by-side updateは54.507秒でreadyとなった。4.5.13のarchive検証はmember 6,512 / extracted
1,167,187,839 B、実probeはBlender 4.5.13 / Python 3.11.15 / background / GLTF import/exportすべてtrue。
managed runtime実ファイル量は4.5.9が1,605,023,227 B、4.5.13が1,601,081,665 B。registryは488 B /
mode 0600 / raw pathなし。update直後のactiveは`blender-4.5.13-linux-x64`、G8 resolverは
`blender-4.5.9-linux-x64`を選んだ。4.5.13→4.5.9の明示switchもreadyとなった。

activeを4.5.13へ戻した実Uvicorn `127.0.0.1:9165`へ796 B cubeをimportし、実HTTP
`asset.pack + 3d.project.glb` jobは0.779秒でsucceededした。出力は44,292 B、SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`、entryは
`asset.glb / manifest.json / preview.png`で3DS-0〜2a baselineと同一。したがってStudio active版を
上げても、既存G8 compilerは固定4.5.9から変わっていない。

4.5.13の実executableを一時root内で削除するとstatusは`damaged`、executable checkだけfalse、
active resolveはfail-closedになった。cached exact archiveからrepairし、20.091秒で
`queued → verifying → installing → probing → ready`、executable SHAは削除前と同一、active ID維持、
previous staging残留0を確認。fixtureでは4.5.13が4.5.12を報告するprobe失敗で4.5.9 activeを保持し、
新版destinationを残さない。未知runtime ID、任意URL付きupdateも422で拒否した。

実Chromeでは日本語「推奨版へ更新」、英語`Update to recommended`、2版のready/active/switch表示を確認。
ボタン操作後は4.5.13 activeへ自動追従し、320 pxでclientWidth/scrollWidthとも320、button 39 px、
console/page error 0。最初の実測でstandalone method不足を`workspace_method_unsupported`として検出し、
standalone mappingと操作中だけの追従を追加後に再試験した。一時runtime/data/Chrome profileはゴミ箱へ
移し、試験Uvicorn/Chrome/Blender childは停止した。

local full gateは`./mf.sh test` 875 passed / 既知Starlette warning 1件 / 64.08秒。PyInstaller bundleは
31,157,120 B / SHA-256 `2b7ce206d48bc6c6ffebe23b94857dff333924cc135b6b40452738fe5e48de3b`、
展開後doctorは`ok / 0.27.0 / packaged=true`。packaged serveのprivate statusから同梱catalogの
base 4.5.9 / recommended 4.5.13を確認した。実ControlDeck opaque
iframe、installed release、GPU/Cycles、稼働中Web Blender sessionの版pin、remove、Web Blender、
scene/revision、viewer、材質、OpenCode制作は **NOT TESTED / NOT IMPLEMENTED**。ControlDeck変更は0件。

## 2026-09-05 — 3DS-2c protected Blender remove / shared CLI

PR #218、実装commit `4b5cdbb3c2b37978d17f3226d0012e4364adef3c`。
managed Blender削除を既存のdurable operationへ追加した。削除前にopaque runtime ID、version、
logical reclaimable bytes、live/project参照数、block理由、確認fingerprintを返す。remove要求は同じ
fingerprintを必須にし、operation実行直前に同じ参照lock下で再計算する。active版、実行中G8 jobが
pinした版、変更後の古いpreview、catalog外ID、raw path注入、external legacyはfail-closed。
project referenceはscene table未導入の現段階では実測0として返し、将来値を推測していない。

削除対象はmanaged root直下のcatalog IDだけ。directoryを`.removing/<operation-id>`へatomic renameし、
registry record削除後に実体を消す。registry更新失敗は元directoryを復元する。service停止がrename後、
registry commit後のどちらで起きても、残ったjournal/registry/stagingの組合せから再開するfixtureを通した。
asset、scene、履歴、external runtime、再取得可能download cacheは削除範囲外。G8 JobManagerはresolverの
runtime reference contextをBlender child終了まで保持し、既存のdeterministic G8 testでもlive count 1を
観測した。

private WSへ`blender.runtime.remove.preview/remove`、standalone mirrorへ`remove_preview/remove`を追加。
Settingsは各managed版に削除導線、日英preview dialog、容量/実行中参照/制作物参照、active時の確認拒否、
terminal追従を表示する。`./mf.sh blender managed-status/install/update/switch/repair/remove-preview/remove`
はloopback Media Forge serviceの同じorchestratorを呼ぶ。既存source runtime用
`./mf.sh blender build/status`は互換維持。CLIは外部originを拒否し、removeはpreview表示後に対話確認、
または明示`--yes`を要求する。

一時rootで正規4.5.9/4.5.13をside-by-side導入した。inactive 4.5.9 previewは1,168,332,155 B、
live `g8_reference`保持中はcount 1 / `blender_runtime_in_use`、preview後にファイルを加えた要求は
`blender_runtime_remove_changed`で実体無変更。解放後、実ChromeのSettings確認から4.5.9を削除し、
operationは約0.110秒で`deleting → ready`、registry/runtime一覧から4.5.9だけが消えた。active 4.5.13は
readyのまま、G8は正直にmissingとなり再導入ボタンを表示した。active 4.5.13のpreviewは
`active_runtime`でconfirm非表示。

削除前後で一時asset SHA-256
`f37528de73ab4612822894bb8f5e39987a0a43381b7b9c9f397dea7e0059fd00`、scene SHA-256
`1f24b4e82d1251c5021c4e7be4717f8b6c4c8aadc29ea5f26ad2c74d128f2596`は同一。4.5.9 archive cacheも
残った。CLIからcache済み4.5.9を再導入、active切替後、1,167,187,993 Bの4.5.13をpreviewして
`--yes`削除し、最終active/G8 4.5.9 ready、asset/scene hash同一を再確認した。

Chromeは日本語/英語dialog、320 px clientWidth/scrollWidthとも320、console/page error 0。
一時runtime/data/Chrome profileはゴミ箱へ移し、試験Uvicorn/Chrome/Blender childは停止した。
local full gateは`./mf.sh test` 884 passed / 既知Starlette warning 1件 / 66.35秒。
PyInstaller 6.22.0でversion 0.27.0 bundleを再構築し、31,163,397 B、SHA-256
`c3baa20ea6adabc0390ba012a04ed0d39a70477bd99c9870b054e582bc1f3ae0`。展開後のpackaged
`doctor`は`status=ok / packaged=true / version=0.27.0`、port 9166の実processでhealth/runtime statusは
HTTP 200、未導入4.5.9のremove previewは意図どおり`blender_runtime_not_found` / HTTP 422だった。
試験processはgraceful shutdownした。

実ControlDeck opaque
iframe、installed release、GPU/Cycles、Web Blender、scene/revision、viewer、材質、OpenCode制作は
**NOT TESTED / NOT IMPLEMENTED**。ControlDeck変更は0件。3DS-2は完了し、次は3DS-3。

## 2026-09-05 — 3DS-3 shared Library GLB viewer

PR #219、実装commit `b5a73824030b5506e409e7f6b0cc9e0a3b5c8a98`。画像・動画・3Dを同じLibraryから
媒体別に絞り込むprivate projectionと、
raw `model/gltf-binary` / 既存G8 `3d.project.glb` ZIPのinteractive viewerを追加した。公開schema、
`addon.json`、Agent tool、workflow executor、画像生成routeは変更していない。Three.js 0.185.1の
`WebGLRenderer` / `GLTFLoader` / `OrbitControls`だけをnpm lockfileからbundleし、registry integrity、
source SHA-256、bundle SHA-256、MIT noticeを固定した。外部CDN、DRACO、KTX2、Meshopt decoderはない。
viewer moduleは最初の3D assetを開くまで取得しない。

opaque workspaceはAsset IDだけを受け、connection-scoped `modelview_*` handleを返す。GLBは既存の
Blender非依存validationを再実行し、64 MiB以下、texture 1辺8,192 px以下、合計67,108,864 px以下を
強制する。G8 ZIPは`asset.glb / manifest.json / preview.png`のexact entry、manifest profile/size/hashを
検証してsession専用rootへstream展開する。bytesは1要求512 KiB以下、同時handleは2個以下で、close、
asset切替、socket切断、app shutdownにstagingを回収する。応答にserver pathはない。raw GLBは最初の
描画から512 px / 256 KiB以下のWebPをcacheし、以降のgridはGLB本体を読まない。

UIはorbit/pan/zoom、fit、material/neutral/wireframe、3 light/background preset、bounding box、
triangle/material/animation数、animation play/pause、3D asset間の前後移動を提供する。画像viewerの
pointer操作はimage modeだけで維持した。非表示時はanimation frameを止め、復帰、WebGL context
loss/restoreを扱い、切替/終了時はgeometry/material/texture/ImageBitmap、control、renderer、contextを
disposeする。日本語/英語はreloadなしでvisible textとARIAを切り替える。

一時data rootの実Uvicorn `127.0.0.1:9167`へ796 B cubeをimportし、実Blender 4.5.9によるG8 job
`job_9062c76d510c4c12b2b36d1c1800fc5c`はsucceeded、ZIP Asset
`asset_86ea614724c0469c9155f07a41e1fe2b`を生成した。viewerは24 triangles / 2 materialsを描画し、
raw Asset `asset_875a59ae8214470fbf5d9e1505e6f85c`との前後移動後もviewer module取得は1回、7個の旧WebGL
contextはすべてlost、5回開閉後のheap増分は316,496 B、console/page errorは0だった。

さらに実Blender 4.5.9からanimation付きcube 3,116 B / SHA-256
`43c30e4303f0c66667e49257db53fc1597ee7d545e181f5e1ca5ca77bb10bf3b`を書き出し、実Chromeで
12 triangles / 1 material / 1 animation、play/pauseを確認した。表示中のanimation frameは10、
visibility hidden中も10、visible復帰後17。`WEBGL_lose_context`でloss→restore後も描画復旧した。
WebGLは`WebGL 2.0 (OpenGL ES 3.0 Chromium)`、rendererは
`ANGLE (AMD Radeon Graphics radeonsi raphael_mendocino LLVM 20.1.2)`。既存画像640x360も同じrunで
開き、3D moduleの先行fetchなし。320 pxではviewport 320 / document client=scroll 305、操作最小高
43.995 px。最終runのcold 89.155 ms、warm 63.734〜68.990 ms、5回close後heap増分450,592 B、
5 context解放、console/page error 0。

`./mf.sh test`は891 passed / 既知Starlette warning 1件 / 68.16秒。PyInstaller 6.22.0の候補
0.27.0 bundleは31,346,609 B / SHA-256
`a0b24e41e7af790e6dbc1993c6655e13a88cf03122b85f4b8abaa2a820b9cd78`。packaged doctorは
`ok / 0.27.0 / packaged=true`、packaged process `127.0.0.1:9168`はviewer module 643,367 B /
SHA-256 `99935b9427ddad9aa892a8046376da55eaa3e5fe8873d3cdaafbabb6f530b843`をCORS/CORP/immutableで
配信し、同じanimation GLBを12 triangles / 1 animationとして描画した。試験processは停止し、
終了時の`workspace-model-*`とBlender childは0。

実ControlDeck opaque iframe、外部提供のtexture付き実モデル、64 MiB上限付近、driver crash、
material slot選択/画像差替えpreview/Blender edit、scene/revisionは **NOT TESTED / NOT IMPLEMENTED**。
これらは3DS-4〜6のscopeであり3DS-3の実績へ読み替えない。ControlDeck変更は0件。次は3DS-4。

## 2026-09-05 — 3DS-4a immutable scene revision persistence

PR #222、branch `ux1/3d-scene-revisions`、実装commit
`9d053fb`。`SceneDocument`とappend-only `SceneRevision`、revision dependencyをSQLiteへ加法的に
導入した。sceneはHost subjectまたはstandalone ownerで分離し、応答へowner/path/DB keyを返さない。
revisionは`.blend` source、そこから派生したGLB preview、依存AssetのID/SHA-256、Blender
runtime ID/version、Blender/GLB validationを固定する。依存hash不一致、必須validation未通過、異なる
owner、stale base revisionはfail-closedで、transaction失敗時はdocument/revisionを残さない。
Asset公開schemaへ`application/x-blender`を加法的に追加したが、公開import、Agent tool、workflow
executorは追加していない。private workspaceの`scenes.list/get`とsession part、standalone mirrorだけを
追加した。

過去revisionが参照するruntimeはdistinct scene数を`project_reference_count`へ反映し、1件以上なら
managed Blender removeを`project_reference`で拒否する。source/preview/dependency Assetもrevision参照中は
削除できない。migration fixture、owner分離、2 revisionのparent/sequence保持、stale commit、hash tamper、
atomic rollback、runtime/remove連携、private transportをfocused 7件で確認した。

実Blender 4.5.9を`--background --factory-startup --disable-autoexec`で起動し、1 object / unit 1.0 mの
`.blend` 426,550 B / SHA-256
`f51ae0111484d8bc7a06c062ae3540482d34bc2e5a78a2ef2f7a89ee2f6e913d`とGLB 1,748 B /
SHA-256 `bc4f4dca1c895d18e066a48b1191b26064118390dc041baedbcd34590fa01077`を生成した。
GLB validatorはmesh/node/primitive各1、external image/texture 0でpassed。scene
`scene_45ab90f346b14112acfaf3a990f3d423`を保存し、別Uvicorn processのprivate HTTP getは1,354 B /
1.096 ms、再起動前後の応答SHA-256はともに
`511e636c46dbfc1846cdc06da54962c8fb3079a05018097abdebd29e4d3e6b09`。runtime参照数1、preview削除は
revision IDを示す`asset_in_use`で拒否した。sourceは派生previewのlineage参照でも拒否された。

最新`origin/main`（v0.27.2）へrebase後の`./mf.sh test`は896 passed / 既知Starlette warning 1件 /
74.83秒。PyInstaller 6.22.0候補bundleは31,357,017 B / SHA-256
`c4d020a530449f9620c4b193b34e5bc77d2cf44475646c06f5f658640ffe644b`。展開後doctorは
`ok / 0.27.2 / packaged=true`、packaged processのscene getはHTTP 200 / 1.877 ms / 1,354 Bで、
source processと同じ応答hashだった。試験Uvicorn/packaged process/Blender childは停止した。

bounded `.blend` upload、single-writer working copy/lease、隔離runnerによるimport・検査・保存は3DS-4b、
exact backup/restoreは3DS-4cで **NOT IMPLEMENTED / NOT TESTED**。browser UI、実ControlDeck opaque iframe、
installed release、GPU/Cycles、Web Blender、材質差替え、OpenCode制作も **NOT TESTED**。ControlDeck変更は0件。

## 2026-09-05 — 3DS-4b core bounded working copy

PR #224、branch `ux1/3d-scene-working-core`、実装commit `c03c8dc`。`.blend` uploadを256 MiB、chunk 512 KiB、
owner同時1件、10分期限、offset/chunk/total SHA-256一致に制限するdomain serviceを追加した。
active Studio runtimeをlive pinし、専用processのBlenderを`--background --factory-startup
--disable-autoexec`で起動する。trusted workerはversion/background/autoexec、object/mesh/vertex/triangle数、
finite transform/座標、unit=1 m、外部library/image不在を検査し、GLBをexportする。coreはそのGLBを既存の
独立validatorで再検査してから`.blend` sourceとGLB previewをimmutable Asset/revisionへ登録する。
任意script/operator/pathは入力に持たず、subprocessは配列引数、専用HOME、180秒timeout、process group
停止、stdout/stderr各128 KiB上限で実行する。

WorkingCopyはscene/current revision/runtimeを固定して専用rootへcopyし、scene単位single-writer leaseを
10分で保持する。renew/release/commitはownerを再確認する。commitはworking lease、期限、base revision、
current headを同じ`BEGIN IMMEDIATE` transactionで再検証し、revision/head/working terminal化をatomicに
書く。競合時はheadを変えずworkingを`recovery`として保持する。期限切れもbytesを保持し、新writerは取得
できる。scene revision参照中のruntime/Asset保護は維持する。raw `.blend`はbrowser Library projectionへ
出さず、viewer用GLBだけを3D assetとして表示する。

実Blender 4.5.9でtext block 1件（実行されれば外部sentinelを作る内容）を含むsphere `.blend`
1,247,112 B / SHA-256
`2eb41fa6750fbe82c884678655c3752d4e81663ba144f9b9da1934a9971ed6c6`を3 chunkで取り込んだ。
import 0.268493秒、working commit 0.267828秒、revision 2件、runtime参照1件。worker実測は8,066 vertices /
16,128 triangles / text block 1、preview GLB 1,138,160 B。autoexec sentinelは生成されず、2 revisionの
`.blend`/GLB bytesとSHA-256、旧Assetはいずれも保持された。unit/fake workerではupload bound/hash/offset/
owner、lock、renew/release、timeout cleanup、期限切れrecovery、base競合時のatomic rollbackを確認した。

exact core headの`./mf.sh test`は897 passed / 3 environment-dependent skipped / 既知Starlette warning 1件 /
78.17秒。private WS/standalone transportとbrowser UI、実ControlDeck opaque iframe、packaged bundleは
このcore sliceでは **NOT IMPLEMENTED / NOT TESTED**。ControlDeck変更は0件。次はtransportを独立PRにする。

## 2026-09-05 — 3DS-4b private working-copy transport

PR #225、branch `ux1/3d-scene-working-copy`、実装commit `5a95a21`。3DS-4b coreをapp lifespanへ接続し、認証済み
WebSocketへ`scenes.import.begin/chunk/commit/cancel`と
`scenes.working.acquire/renew/release/commit`、sessionのworking copy一覧を追加した。standalone開発用にも
同じdomain serviceを通るprivate mirrorを追加した。Host path、runtime path、working pathは入力・応答に
なく、ownerはintrospection subjectまたはstandalone固定値からだけ導出する。socket切断時はそのconnectionが
開始した未完uploadを回収し、別connectionから同じownerで再開できる。公開OpenAPI、addon contribution、
Agent tool、workflow executorは変更していない。

実Uvicornへ1,247,112 B `.blend`を512 KiB以下の3 HTTP chunkで送り、実Blender 4.5.9によるimportは
0.343030秒、working commitは0.252321秒。二重writerは
`scene_working_locked` / HTTP 422、renewとcommitはHTTP 200、revision 2件を保持した。source/previewは
各revisionで別Asset ID、bytes/hashは一致し、staging/validation/working残留0、Blender child 0。
autoexec probe text block 1件は実行されずsentinel 0。応答内path 0。

`./mf.sh test`は902 passed / 既知Starlette warning 1件 / 79.74秒。PyInstaller 6.22.0の0.27.3候補は
31,392,211 B / SHA-256
`197099156662638de8bd122bec4a30dc35a69ca06b55efe0d73a7c95628c2323`、doctorは
`ok / 0.27.3 / packaged=true`。packaged processでも同じ実fileを3 chunkでimport 0.296297秒、commit
0.274779秒、preview 1,138,160 B、8,066 vertices / 16,128 triangles、revision 2件、lock 422、
autoexec sentinel 0を確認して停止した。

browser UIと実ControlDeck opaque iframeは **NOT IMPLEMENTED / NOT TESTED**。exact backup/restoreは3DS-4c、
Web Blenderは3DS-5。ControlDeck変更は0件。次はbrowser import/scene UIを独立PRにする。

## 2026-09-05 — 3DS-4b browser scene import / revision UI

PR #226、branch `ux1/3d-scene-import-ui`、実装commit `573b610`。既存workspaceの作る媒体へ3D Studioを追加した。
`.blend`はbrowserでも256 MiB上限、512 KiB単位でincremental SHA-256を計算し、宣言後に同じ上限の
sequential chunkとして送る。全fileを一括`arrayBuffer`へ載せない。scene一覧、保存済みrevision履歴、
Blender版、dependency件数、validation済み状態を表示し、各revisionのGLB previewを3DS-3と同じvalidated
viewerで開く。raw `.blend`、filesystem path、runtime path、working leaseはbrowserへ渡さない。
standaloneと認証WebSocketは同じUIから各private transportを使う。3D媒体選択はowner-scoped server
preferenceへ保存し、Cookie/localStorage/sessionStorageは追加していない。

実Chrome headedでsource Uvicornへ1,247,112 B / SHA-256
`2eb41fa6750fbe82c884678655c3752d4e81663ba144f9b9da1934a9971ed6c6`をfile inputから3 chunkで送った。
hashingからBlender検査、scene/revision保存まで1.447298秒、previewは16,128 triangles / 1 material /
animation 0として表示した。最大JSON chunk requestは699,216 B。日本語完了表示から英語へreloadなしで
切替え、statusは`Saved as a validated revision.`、revisionは`Revision 1 · Validated`となった。320 pxは
viewport/document/headerすべて320 px、Studioは1列、主操作45.994 px、横溢れ0。1 import＋viewer
open/close後のJS heap増分は3,516,038 B、console/page error 0。

2 MiBのbrowser uploadを最初のchunk送信前で遅延させてcancelし、`取り込みを中止しました。`、submit再有効、
同ownerの次begin/cancel HTTP 200、upload/validation staging 0、Blender child 0を確認した。実file内の
autoexec probe sentinelも0。

exact code headの`./mf.sh test`は904 passed / 既知Starlette warning 1件 / 78.00秒。PyInstaller 6.22.0の
0.27.4 bundleは31,397,686 B / SHA-256
`1bbb21f0bf06db3a19fb250fa31dccaf69d3b35ed1a4f2fe5da6734b10f4cb81`、doctorは
`ok / 0.27.4 / packaged=true`。packaged processでも同じ1,247,112 Bを3 chunk、1.163959秒で保存し、
16,128 trianglesを表示。日英、320/320 px、console/page error 0、staging 0、autoexec sentinel 0で停止した。

実ControlDeck opaque iframe、installed release、working copyを使う編集、backup/restoreは
**NOT TESTED / NOT IMPLEMENTED**。ControlDeck変更は0件。次は3DS-4c exact backup/restore。

## 2026-09-05 — 3DS-4c exact scene backup core

PR #228、branch `ux1/3d-scene-backup`、実装commit `175ea31`。`media-forge.scene-backup@1` ZIP codecと、
全Asset/job/document/revisionを一つのSQLite transactionで新sceneとして復元するStore境界を追加した。
ZIP entry順は`manifest.json`、revision sequence順の`.blend`/`preview.glb`、Asset ID順のdependency blobに
固定し、manifest identityと各entryのsize/SHA-256を検証する。archive/member/manifest/展開量、`.blend`
256 MiB、GLB 64 MiBをboundedにし、absolute/traversal、重複名、symlink/device、暗号化entry、private root外を
fail-closedにした。復元時は全IDを新規発行し、旧scene/Assetを上書きしない。file publishはno-replaceで、
DB/ファイルの途中失敗時は追加0件に戻す。公開OpenAPI、addon contribution、Agent tool、workflow executorは
変更していない。

unit/integrationでは2 revisionと共有dependencyのexact bytes、新ID/owner分離、固定entry順、missing/tamper/
manifest identity/traversal/duplicate/link/device/member上限、private path、export元hash変更、2件目revision insert
失敗、publish同時衝突を21件で確認した。同時衝突では競合側が作った既存fileを保持し、restore側のDB rowと
temporary fileは0件だった。

3DS-4bの実Blender 4.5.9で作成した2 revision sceneの隔離copyを用い、各`.blend` 1,247,112 B、各GLB
1,138,160 Bを1,225,068 BのZIPへ0.113988秒でexportした。archive SHA-256は
`e07c055d19efca0fce0e0a8d97f1364e3f342354e90542ff09c4c020b1dcf287`、manifest content SHA-256は
`c84ddba3b08274e4b528f39a9d082a69b73d98ea959ccad89fc74540d3ed1da9`。全5 memberのsize/hashをZIPから
再計算して一致した。別ownerへのrestoreは0.018701秒で、scene 1→2、revision 2→4、Asset 4→8、job 2→3。
全4復元Assetのbytesは元と一致し、旧scene不変、別ownerからnot found、staging 0だった。実GLB末尾を1 byte
変更したZIPは`scene_backup_hash_changed`で拒否され、job/Asset/scene/revision追加はいずれも0、staging 0。

exact code headの`./mf.sh test`は916 passed / 既知Starlette warning 1件 / 77.71秒。private WS/standalone
transport、browser UI、packaged bundle、実ControlDeck opaque iframe、
実texture dependency付きsceneは **NOT IMPLEMENTED / NOT TESTED**。dependency blob自体はunitでexact byte
復元済み。ControlDeck変更は0件。次はbackup private transport/browser UIを独立PRにする。

## 2026-09-05 — 3DS-4c private backup transport

PR #229、branch `ux1/3d-scene-backup-transport`、実装commit `d159731`。認証済みWebSocketへ
`scenes.backup.open/read/close`と`scenes.restore.begin/chunk/commit/cancel`を追加し、standalone private
mirrorも同じ`SceneBackupSession`を通す。download handleとrestore uploadは接続内だけで有効、各1件、
512 KiB chunk、10分activity TTL、offset/chunk SHA-256/total SHA-256を強制する。ファイル名以外のpathを
入力・応答せず、切断時cleanupに加えてshutdown時は孤児transferも回収する。公開OpenAPI、addon contribution、
Agent tool、workflow executorは変更していない。

unit/transport 18件でexact ZIP往復、別owner/別connectionからのhandle不可視、upload/download同時上限、
offset/hash/総量/期限、cancel、切断task終了とshutdown cleanup、standalone mirror、Host path拒否を確認した。
最初の実HTTP runでcore内部用1 MiB chunkをtransportへ誤って流用し、base64上限700,000文字で最初のuploadが
422になる不整合を検出した。このrunはscene追加0件で、停止時staging 0。transport専用512 KiBへ分離し、
契約assertionを追加してから全受入を再実行した。

3DS-4bの実Blender 4.5.9由来2 revision sceneを隔離data rootの実Uvicorn `127.0.0.1:9174`で開いた。
現在稼働機のhealthy environment snapshotを明示してhealth `healthy`を確認し、1,225,070 B / SHA-256
`ae94a4c1b75ba8e31080c4ede469fc5c754639c6e93806bd6d57b252f8757f75`のbackupを0.120567秒で作成した。
download/uploadは各3 chunk、最大read JSON応答699,154 B、最大upload JSON request 699,218 B。
upload開始からatomic restore完了まで0.045491秒でscene 1→2、復元revision 2。応答path field 0、公開
OpenAPIの`/workspace-api` path 0。別uploadは524,288 B受信後にcancelし、transfer staging 0、process停止後も
0だった。

`./mf.sh serve`をそのまま使った最初の起動は、この隔離worktreeに無いROCm runtimeのauto provisionを開始した
ため受入に使わず即時停止した。そのrunが作った983 MiBの部分`.venv`だけをtrashへ退避し、以後は直接Uvicornと
既存healthy snapshotで検証した。元checkoutと稼働中serviceは変更していない。

exact code headの`./mf.sh test`は920 passed / 既知Starlette warning 1件 / 85.02秒。browser UI、packaged
bundle、実ControlDeck opaque iframeは **NOT IMPLEMENTED / NOT TESTED**。ControlDeck変更は0件。次は
backup/restore browser UIを独立PRにする。

## 2026-09-06 — 3DS-4c browser backup / restore UI

PR #230、branch `ux1/3d-scene-backup-ui`、実装commit `de0cd4e`。選択したsceneのexact backupをprivate transportから512 KiBずつ読み、
browser側でも総SHA-256とbyte数を検査して`.zip`として保存する。復元はfile全体を一括読込せずsliceごとに
SHA-256を計算し、同じ512 KiB単位で送信してからserver側の全revision/file検証とatomic restoreを呼ぶ。
2 GiB上限、import/download/restoreの相互排他、途中cancel、Host `disable.pending`、日英再描画、
standalone private mirrorを実装した。入力/応答にserver pathを追加せず、公開OpenAPI、Agent tool、workflow
executor、addon contributionは変更していない。bundle identityは0.28.1へ更新した。

3DS-4bの実Blender 4.5.9由来2 revision sceneを隔離data rootの実Uvicorn `127.0.0.1:9175`と実Chromeで
操作した。backupは1,225,331 B / SHA-256
`ee9996ad02530c300c7b6e28ad46d33d6ac628b062ceb34b72d9b8ced4dd36ba`、download 0.220815秒、restore
0.175584秒。download/upload各3 chunk、最大upload request 699,218 Bで、scene 3→4、復元revision 2。
別restoreは最初の524,288 Bをserverが受けた状態で中止し、scene 4のまま、transfer staging 0。
日本語完了、英語再描画/中止、320pxでviewport/document/client各320と単一列を確認し、JS heap増分
2,591,176 B、console/page error 0だった。

`./mf.sh bundle build 0.28.1`は31,429,467 B、SHA-256
`25486a75002e70641e26318b4df9dfa14eb16e945f4994359288501c9499c2ef`。展開binaryのdoctorは
`ok / 0.28.1 / packaged=true`。同binaryの実process `127.0.0.1:9176`でも1,225,378 Bを3 chunkで
download 0.222907秒、restore 0.192467秒、復元revision 2、cancel後scene増分0、staging 0、320px横overflow
0、console/page error 0だった。最初のpackage browser呼出しはscriptのport指定方法を取り違えて停止済み
9175へ接続し、`ERR_CONNECTION_REFUSED`で終了したため受入には数えていない。

focused scene/frontend/transport 239件とexact code headの`./mf.sh test`は921 passed / 既知Starlette
warning 1件 / 83.09秒。稼働ControlDeckは0.28.0 / healthyであることをread-only確認した。既存browser
sessionの一時copyはloginへ遷移し、0.28.1をinstalled状態にしていないため実ControlDeck opaque iframeは
**NOT TESTED**。一時profileはtrashへ退避し、ControlDeck source/service/installed filesは変更0。
3DS-4のsource/package経路を完了し、次は3DS-5 Web Blender、installed release通し受入は3DS-8で行う。

## 2026-09-06 — 3DS-5a Web Blender pack manager

TigerVNC 1.16.2とnoVNC 1.7.0を基本Blenderと別のimmutable Web操作packとして追加した。公式HTTPS URL、
archive byte数/SHA-256、展開root、必須7 fileのSHA-256と実行bit、GPL-2.0-or-later/MPL-2.0を
strict manifestへ固定した。既存Blender operation journalでpreflight→download→verify→install→probe→ready、
Range/ETag再開、cancel、staging回収を扱う。archiveは256 MiB展開量/4,096 member上限、path脱出、重複、
symlink/device/FIFOを拒否し、候補のXvnc/vncpasswd/noVNC版を実probeしてからno-replace publishする。
private browser/CLI入力は`web_install`だけで、URL/path/version/commandを受けない。公開契約変更0、版は0.28.2。

隔離data rootの実Uvicorn `127.0.0.1:9177`から公式archive合計15,769,716 Bをdownloadし、operation
`blenderop_3965d2bda58a4705bfefc69166d1aed0`は6.153秒でready。TigerVNCは165 member /
35,067,968展開B、noVNCは244 member / 2,471,032展開B。pack実体は283 files / 37,539,247 B、
staging entry 0、必須Xvnc/rfb.js hashはmanifestと一致した。実Xvncを1280x720 / 24-bit / security noneで
loopback限定起動し、IPv4 `127.0.0.1`とIPv6 `::1`だけがlisten、RFB 3.8 bannerは2.207 ms、停止後process 0。

実Chrome Settingsは「利用できます（ソフトウェア表示）」、TigerVNC/noVNCの版・license・15.0 MBを表示。
mobile emulationはinner/client/scroll widthすべて320、install button非表示、browser error 0。
`./mf.sh bundle build 0.28.2`のartifactは31,447,404 B / SHA-256
`04d28d0293dc249d1c2dc42e328d2ccf379d7ed184782d334dd0f37328f16759`、展開binary doctorは
`ok / 0.28.2 / packaged=true`。packaged実process `127.0.0.1:9178`もhealth healthy、Web pack ready、
status path token 0、同じ320px/browser error 0。focused 172件とexact headの`./mf.sh test`は
928 passed / 既知Starlette warning 1件 / 82.35秒。

fixtureでは16 B partialでcancel後staging/destination 0、再起動後fresh retry ready、archive hash改ざん・
traversal・link・duplicate拒否を確認した。実session runner、Blender GUI保存、RFB gateway/noVNC接続、
再接続、idle/disable/revocation、実ControlDeck opaque iframe、GPU GUIは **NOT IMPLEMENTED / NOT TESTED**。
このXvnc起動はsoftware display/package互換性の証拠だけである。ControlDeck source/service/installed filesは変更0。
次は別PRの3DS-5b session runner。

## 2026-09-06 — 3DS-5b isolated Blender GUI runner

durable `blender_web_sessions` tableと全体1件のactive unique indexを追加し、Scene working copyの既存
single-writer authorityと組み合わせた。private `blender_sessions` session part、
`blender.sessions.list/start/save/stop`、standalone mirrorを追加したが、入力はScene ID/session IDだけ、
応答はbounded state/runtime/Web pack/display/resultだけでpath、PID、unit、socket、display番号は含まない。
状態はqueued→preparing→starting→ready→saving/stopping→stopped、失敗はfailed/interrupted。saveはGUIへ
明示保存を要求してhash/sizeを受け、process group停止後に既存Blender/GLB独立検査とimmutable revision commitを
通す。discardはworking copyを解放し、起動/保存/runner/reconcile失敗はrecovery working copyを保持する。

session専用transient systemd user unitは`NoNewPrivileges`、`PrivateNetwork`、AF_UNIX限定、
`ProtectSystem=strict`、`ProtectHome=yes`、MemoryMax 8 GiB、TasksMax 128、3 writable rootを設定する。
Xvncは1280x720/24-bit、RFB TCP無効、mode 0600 Unix socketのみ。Blenderは個人Waylandを空にし、
GPU visibilityを消し、system Mesa Lavapipe ICDだけを指定したVulkan GUIで起動する。readyは実Blender
4.5.9、`background=false`、autoexec無効、VULKAN、llvmpipe、実socketがすべて一致した場合だけ成立する。

最初の実機probeでは、systemdの一部kernel保護propertyがuser unitで`218/CAPABILITIES`、Wayland環境を
残したBlenderが個人displayへ接続、Xvnc GLXに必要なcontext extensionが無くOpenGL GUI起動不能、初回設定popup、
`ProtectSystem`/`ReadOnlyPaths`が追加mount `/data1tb`へのwriteを拒否しないことをそれぞれ観測した。
採用不能propertyを外し、Wayland無効、Lavapipe/Vulkan、隔離user preference seedへ修正した。filesystemは
systemdだけに依存せず、Blender起動前にLandlock ABI 3以上を必須化してsession control、working copy、
RFB socket root以外のwriteを拒否する。Xvncは固定済みtrusted componentで`/tmp` X lockが必要なため先に起動し、
sceneを読むBlenderとその子孫へLandlockを適用する。pre-open前は`/dev/null`が拒否されたため、適用前にfdを開く。

sourceのLandlock導入probe `blendersession_f199db196fdb4b9284dc130b7d8aa1e1`は0.584秒でready。
実RFB 3.8 / 1280x720を取得し、unitはMemory 540.6 MiB（peak 571.4 MiB）、94 tasks、Blender childは
`NoNewPrivs=1` / seccomp mode 2、TCP 5999 listener 0。discard後unit inactive、Unix socket 0。
同じLandlock helperでallowlist外`/data1tb/mf-landlock-escape`はerrno 13、allowlist内writeは成功し、
AF_UNIX限定unitでAF_INET作成はerrno 97だった。

inline評価を使わず同梱trusted Python fileだけを使う最終コードから候補bundleを再構築した。実process
`127.0.0.1:9180`へ434,663 B `.blend`をimportし、commit開始からGUI readyまで1.019088秒。mode 0600
Unix socketへ実RFB接続し、click + Shift+D + Enter後のscreenで`Cube.001`を確認した。save/stopは
0.732258秒、working fileは510,540 B / SHA-256
`cdb4c7061e8b8490dae51f910bc59b28cafc221ade00a6ba65719d34cc428bdb`。revision 1→2、objects 3→4、
meshes 1→2、triangles 12→24、vertices 8→16でBlender/GLB validatorはいずれもpassed。停止後unit inactive、
socket/process 0。package unitはMemoryCurrent 574,533,632 B / peak 578,682,880 B、94 tasksだった。

`./mf.sh bundle build 0.28.3`は31,489,331 B / SHA-256
`d345481457c0f4bce16d00b564c4c940d3e26f81956b80cdf6da9c4f76c50769`、展開binary doctorは
`ok / 0.28.3 / packaged=true`。focused session 8件、exact head `./mf.sh test`は936 passed / 既知
Starlette warning 1件 / 88.01秒。候補processはenvironment snapshotを意図的に置かなかったためhealthは
`setup_required`であり、packaged session成立をcore全体のprovision成功へ読み替えない。

認証付きRFB gateway/noVNC browser、接続heartbeat/再接続/idle、disable/revocation、実ControlDeck opaque
iframe、GPU GUI/Cyclesは **NOT IMPLEMENTED / NOT TESTED**。稼働ControlDeckは0.28.0 / healthy / PID 1827940、
ControlDeck source/service/installed files変更0で、既存`frontend/tsconfig.tsbuildinfo`だけdirty。次は別PRの
3DS-5c RFB gateway/noVNC。

## 2026-09-06 — 3DS-5c authenticated RFB gateway / noVNC

PR #233、branch `ux1/3d-session-gateway`、実装commit `72db176`。private Host/standalone WebSocketから
session所有のUnix RFB socketへbinary frameだけを中継するgatewayを
追加した。接続時にowner、READY state、systemd unit active、実socketを再確認し、1 sessionに1 controllerだけを
許可する。browserからの1 messageは1 MiB上限、text/余分なsubprotocolを拒否する。Host経路は既存service tokenを
15秒ごとに再introspectionし、addon/subjectが一致しないかtokenが無効なら切断する。standaloneは同一loopback
Originを必須にした。入力/応答へsocket path、PID、unit、display番号、tokenを追加せず、公開OpenAPI、Agent tool、
workflow executor、addon contributionは変更していない。

noVNC 1.7.0の`core/**/*.js`と`vendor/pako/lib/**/*.js`の実行依存54 files / 579,832 Bをすべて固定manifestへ
追加した。private module routeはその一覧にあるJavaScriptだけを許し、各応答前にsize/symlink/SHA-256を再検査し、
opaque sandbox iframeからのES module importに必要なCORS/CORPだけを付ける。UIはdesktopだけに1280x720を
scale表示し、start/return、表示だけ閉じる、保存終了、破棄終了を分けた。sessionはserver stateから復元し、
切断をbatch cancelへ読み替えず、Host nonce更新時と予期しない切断時はbounded reconnectする。mobileはworkspaceを
押し込まずdesktop案内を返す。版は0.28.4。

隔離data rootのsource Uvicorn `127.0.0.1:9181`、実Blender 4.5.9、実Xvnc、実Chromeから、manifest掲載JSの
取得と`binary` WebSocketを通し、1280x720 framebufferを表示した。「表示だけ閉じる」後もsessionはreadyのまま
停止せず、同じsessionへ2本目を接続して再び1280x720を取得した。browser側noVNC入力でF3 `Add Cube`を送り、
保存後はrevision 5→6、working `.blend` 515,688 B / SHA-256
`7afe139e407c33711b12e0989cf5492ed5294580535e809509ed76b969a43ee1`、objects 4→5、meshes 2→3、
triangles 24→36、vertices 16→24。Blender/GLB validatorはpassed、GLBは4,772 B / nodes 3 / meshes 3、
browser exception 0。終了後systemd unit、Unix socket、Xvnc/Blender process、TCP RFB listenerはいずれも0。
実測でBlender sessionをhost busyにすると3D scene自体へ戻れなくなるUI lockを検出し、Hostの離脱警告と
workspace内navigation lockを分離して修正した。

focused gateway/frontend testは全件通過し、exact codeの`./mf.sh test`は943 passed / 既知Starlette warning
1件 / 89.66秒。ControlDeckはread-onlyでcommit `34bda2f14c2c00e4ead8251bf30d830b2e3bf7a5`、既存dirty
`frontend/tsconfig.tsbuildinfo`だけ、installed 0.28.0 / PID 1827940 / health healthyを確認し、変更0。

`./mf.sh bundle build 0.28.4`は31,503,501 B / SHA-256
`9c1644a40962cf742f5f884203d0d2918d4bee0b195f0db515c82944cbfc9089`。展開binary doctorは
`ok / 0.28.4 / packaged=true`。exact candidate process `127.0.0.1:9182`のrootはweb pack fingerprint付き
`rfb.js?v=...` importを配信した。候補binaryから配信した`rfb.js`はmanifest SHA-256と一致し、同じgateway実装の
実GUI sessionはsubprotocol `binary` / `RFB 003.008`を14.337 msで
返した。WebSocket切断後もsessionはready / disconnected / reconnectable、明示discard後stopped、終了後
unit/socket/process 0。

実ControlDeck opaque iframe、10分超token rotation、Host revoke/disable、idle/crash/recovery policy、GPU/Cycles、
packaged Chromeは **NOT TESTED**。次は別PRの3DS-5d session recovery。

## 2026-09-06 — 3DS-5d session lifecycle / recovery

branch `ux1/3d-session-recovery`。Blender GUIに既定300秒の切断猶予と1,800秒のcontroller idle timeoutを
追加し、server設定はそれぞれ最大3,600秒/86,400秒へ制限した。browser input activityはmemoryで追跡し、
durable更新を15秒にthrottleする。timeout、Blender crash、Host disable、Host credentialの15秒周期再検査失敗は
isolated unitを停止し、session root/socketを回収してworking `.blend`を正式revisionではなくowner-scoped
復旧候補として保持する。候補は新しいwriter leaseへbyte copyし、元候補を変えない。新sessionの保存、
Blender/GLB検証、revision commitがすべて成功してからだけ元候補をreleasedにしてrootを削除する。

standalone scene transportにもworking copy一覧を追加してembedded snapshotとの差をなくし、UIはfresh editと
「復旧候補をBlenderで開く」を分離した。idle / disconnect / Host revoke / disableを日英で区別し、未検証候補を
正式版と表示しない。`disable.pending`は2秒以内に返るprivate interruptを開始してからRFBを閉じる。版は0.28.5。

隔離data rootのsource Uvicorn `127.0.0.1:9183`、実Blender 4.5.9/Xvncで切断猶予を2秒にして起動したsessionは、
ready `17:52:46.906103Z`からinterrupted `17:52:52.175633Z`まで5.270秒だった。errorは
`blender_session_disconnected_timeout`、復旧候補は515,688 B / SHA-256
`7afe139e407c33711b12e0989cf5492ed5294580535e809509ed76b969a43ee1`。その候補から新sessionを起動して保存し、
revision 6→7、working 515,496 B / SHA-256
`cddc910ddfe056542990e0d669d240f1bddbbc0642da75724c215e597d270d6d`、objects 5、meshes 3、triangles 36、
vertices 24、Blender/GLB validator passedを得た。元候補はreleasedとなりroot 0。

別の実session unitをsystemd経由でSIGKILLし、`blender_session_runner_lost`と復旧候補保持を確認した。初回実測で
Unix socket残存を検出し、failure終端の共通cleanupへ修正して再試験した結果、unit、session root、Unix socket、
Xvnc/runner processはいずれも0。Host disable相当のprivate interruptはHTTP受付2.397 ms、stopping
`17:57:10.985471Z`からinterrupted `17:57:11.077835Z`まで91.9 msで復旧候補を保持し、残存resource 0。
実Chromeはdesktopで日英の復旧ボタン/理由、390x844でdesktop案内と横scroll 0、browser exception 0を確認した。

focused lifecycle/recovery/frontend testは全件通過し、exact codeの`./mf.sh test`は952 passed / 既知
Starlette warning 1件 / 91.17秒。`./mf.sh bundle build 0.28.5`は31,509,192 B / SHA-256
`352efcfbf6f7ee3566ec530ea01ee7b76534c8bbe397d346bed0f72907d65693`、展開binary doctorは
`ok / 0.28.5 / packaged=true`。exact package processは既存scene 5件 / working record 18件を読み、実Blender
sessionをreadyにした。private interrupt受付は2.780 msでinterrupted / recovery candidateとなり、終了後
unit/session root/socket/process 0。実ControlDeck opaque iframe、10分超credential rotation、
実Host revoke、GPU/Cycles、packaged Chromeは **NOT TESTED**。次は別PRの3DS-6 material binding。

## 2026-09-06 — 3DS-6a existing Library image material binding

branch `ux1/3d-texture-binding`。`media-forge.material-binding@1`へsource revision、既存画像Asset、object/
material slot、base color / roughness / metallic / normal / emission、UV、wrap、色空間、normal conventionを
固定した。private Host/standalone bridgeと日英UIはscene IDとbindingだけを扱い、path/任意Pythonを受けない。
画像blobはmetadataのsize/SHA-256と再照合し、stale source revisionはcurrentへ暗黙追従せず競合にする。
trusted Blender workerは固定stage、background/factory-startup/autoexec無効/GPU不可視で画像をpackし、既存の
Blender/GLB検査後だけimmutable revisionへする。source asset provenanceは元scene sourceと画像をparent、
画像hashをreference、operationを`scene.material.bind`として記録する。版は0.28.6。

隔離data rootの実UvicornとBlender 4.5.9で、既存sceneのtarget 3件とUVMapを0.252秒で列挙した。実PNG
1,280x720 / 292,693 B / SHA-256 `9707a06cca10bedd8c710d0ad7a1c2f2b887bc18b0ffd0d2e584186aa3f56a06`
をbase color / roughness / metallic / DirectX normal / emissionへ順に適用し、各0.700883〜0.770455秒、
revision 7→12、dependency 5件となった。最終`.blend`は1,141,499 B / SHA-256
`9e55783af878a6c2c54332dee0dee9c049b882da931499bdcf5266a9b71618db`、objects 5 / meshes 3 /
materials 2 / images 3 / external images 0、GLB 285,508 B / textures 4で両validator passed。最新revisionを
bindingへ必須化した後の再適用は0.781秒、stale再送は1.964 msで`scene_revision_conflict`だった。

実Chrome/CDPはLibrary画像1件、target 3件を表示し、roughness適用でrevision 8→9、日英文言、390x844
単一列とbody scroll width 390 / inner width 390、browser exception 0。exact head `./mf.sh test`は
957 passed / 既知Starlette warning 1件 / 93.63秒。`./mf.sh bundle build 0.28.6`は31,554,828 B /
SHA-256 `b03135ac28483fe93c4cdaf2744acbecb32a3a555fdf1a0f1948fc51b4b7cec9`、展開binary doctorは
`ok / 0.28.6 / packaged=true`。exact package processでもtarget 3件を列挙し、DirectX normalを0.712秒で
revision 7→8へ適用した。`.blend`は836,127 B / SHA-256
`6e865cc4fa021a24140f306c82cc8bd8376f624718b5e5b6bd60d4fd35dfe8ac`、external images 0、両validator
passed、終了後active working/material staging 0。

新しい画像生成・編集jobからの採用、前後版同時比較・旧版へのcurrent切替、実ControlDeck opaque iframeは
**NOT IMPLEMENTED / NOT TESTED**。次は別sliceの3DS-6b texture generation orchestration。

## 2026-09-06 — 3DS-6b texture generation orchestration

branch `ux1/3d-texture-generation`。既存durable `image.generate`の`constraints.scene_texture`へ
`media-forge.scene-texture-request@1`を加法追加し、scene ID、source revision、object、material slot、channel、
UV mapを厳格検証する。これは`image.generate`だけに許可し、scene変更権限や別queue/GPU schedulerは持たない。
成功物は通常のimmutable Library Assetとprovenanceになり、job成功時点ではsceneを変更しない。3D Studioは
通常Createとは別にreload後のjobを復元し、cancel、同一durable contextでretry、bounded preview、明示選択を
扱う。その後既存MaterialBindingの「新しい版を保存」を押した場合だけ新revisionへcommitする。
`disable.pending`は実行中texture jobをcancelする。版は0.28.7。

隔離data rootのsource Uvicorn、決定的image worker、実Blender 4.5.9、実Chromeで、生成中reload後もjobを
復元してcancelし、同一文脈のretryを成功させた。job IDはcanceled
`job_02adb3d5c09c493ca07767adcd83ee69`、succeeded `job_901321690c4d4a8c9b670a176479d807`。
生成PNGは1,024x1,024 / 23,489 B / SHA-256
`bc5228bec807cab277aa591bce8c746c5c6313fd3708c7c4287db13744f1823a`。明示選択とMaterialBinding commitで
revision 1→2、dependency 1、最終`.blend` 459,632 B / SHA-256
`61b25bb9f20b3bfc62a4d270a4aa34aa9ca9c1e6319e0eb87d4aad367757fabf`、external images 0、GLB
18,600 B / SHA-256 `cc354349853152769a41aa3452321f51da35c4af65047d85f841c9771bb19405` / textures 1。
Blender/GLB validator passed、日英切替、390x844 overflow 0、console/page error 0。実測中にimport完了後controlsの
再描画漏れ、reload後poll再接続漏れ、reload後retryのform依存、選択後binding context復元漏れ、390px header
overflow 14pxを検出して修正した。

最初のexact package実測ではfrozen executableがfake worker childの`-m mediaforge.workers.fake`をCLI引数として
処理してexit 2となる不具合を検出した。許可argvを完全一致させたinternal dispatchとrelease regression testを
追加後に再構築した。最終`./mf.sh test`は960 passed / 既知Starlette warning 1件 / 94.96秒。
0.28.7 exact bundleは31,565,375 B / SHA-256
`653caa562b7f86d4f27577927f1949fac03c59f0035eb9477546323ed9c83423`、展開binary doctorは
`ok / 0.28.7 / packaged=true`。最終exact packageの実Chromeでもreload→cancel→retry→preview→選択→commitを
再実行し、revision 1→2、同じ23,489 B PNG、dependency 1、`.blend` 459,632 B / SHA-256
`9665cbf1100455b73b3ed36d8a5720d428bceb18ea4b03bb3c5a11e8629ab1`、external images 0、同じ18,600 B
GLB / textures 1、両validator passed、390px overflow 0、console/page error 0。

exact sourceからavailable R9700へstandaloneで同じ型付き要求を送ると37 msで`host_lease_required`となり、
ControlDeck broker外GPU実行をfail-closedにした。ControlDeckはread-onlyでcommit
`34bda2f14c2c00e4ead8251bf30d830b2e3bf7a5`、既存dirty `frontend/tsconfig.tsbuildinfo`だけ、installed
0.28.0 / PID 1827940 / health healthy（R9700 gfx1201 / torch 2.10.0+rocm7.2.1 / HIP 7.2）。保存済み
browser認証が失効して`/login`へ戻ったため、資格情報を迂回せずHost-managed R9700生成と実opaque iframeは
**NOT TESTED**。前後版比較と旧版からのcurrent復元も **NOT IMPLEMENTED / NOT TESTED**。次は別sliceの
3DS-6c revision compare/restoreで3DS-6 exit条件を閉じる。

## 2026-09-06 — 3DS-6c revision compare/restore

branch `ux1/3d-revision-restore`。private workspace/standaloneへscene ID、期待するcurrent revision、同scene内の
旧revisionだけを受ける復元操作を追加した。旧`.blend`、GLB preview、全dependencyのsize/SHA-256とprovenance
identityを再検査し、新しいAsset IDと`scene.revision.restore` provenanceへexact cloneする。scene head自体を
巻き戻さず、現currentをparentにした新しいimmutable revisionをatomic commitするため、旧履歴/Assetは不変。
optimistic conflict、current自身、別scene/missing/tampered assetはfail-closedで、途中登録Assetはrollbackする。
公開OpenAPI、Agent tool、workflow executor、addon contributionは変更していない。版は0.28.8。

UIは旧版とcurrentのGLBを各64 MiB上限、connection-scoped handle、512 KiB以下chunkで同時に読み、独立した
WebGL canvasで比較する。両previewがreadyになるまで復元buttonを無効にし、閉じる/scene切替/disable時はviewerと
handleをdisposeする。隔離data rootのsource Uvicorn + 実Chromeで、材質dependency 1件を持つ旧版を
revision 5→6へ復元した。比較表示0.126秒、復元0.069秒、`.blend` 459,632 B / SHA-256
`6e2aca40cfbe90a9ebdfbf10948c52cc0aca3de2aa49aade57971bfae1a58054`、GLB 18,600 B / SHA-256
`cc354349853152769a41aa3452321f51da35c4af65047d85f841c9771bb19405`は復元元とbyte一致し、新Asset ID、
new provenance、parent=current、dependency保持を確認した。実Blender 4.5.9はobjects 3 / meshes 1 /
materials 2 / images 2 / external images 0 / autoexec disabled、独立GLB validatorはtextures 1でpassed。
日英、390px overflow 0、console/page error 0。final `./mf.sh test`は963 passed / 既知warning 1件 / 95.87秒。

0.28.8 exact bundleは31,570,669 B / SHA-256
`672533021c2170d9233ac56892381ec52b63f81d2ac02371897dfe2b20920f87`、展開binary doctorは
`ok / 0.28.8 / packaged=true`。exact package + 実Chromeでもdependency 1件をrevision 8→9へ復元し、
比較0.129秒、復元0.075秒、desktop/390pxの2画面WebGL、overflow 0、console/page error 0。同じsource/GLB
hash、Blender/GLB validator passed。実ControlDeck opaque iframeは **NOT TESTED** のまま3DS-8 acceptanceへ残す。
3DS-6 exit条件はsource/packageで完了し、次は別sliceの3DS-7 typed Agent recipes。

## 2026-09-06 — 3DS-7 typed Agent recipes / durable child Jobs

branch `ux1/3d-agent-recipes`。`media.scene.create/edit/material/snapshot/export`と
`media.job.status/cancel`、workflow executor `media.scene`を加法追加した。create/editは最大64件の
primitive、transform、bevel、simple PBR material、smart-project UV、light、cameraだけを受ける。
objectは安定`media_forge_id`で参照し、Python、Blender operator名、shell、URL、pathを受けない。
materialは既存`MaterialBinding`、snapshot/export/status/cancelも各Pydantic schemaで実行時に
`extra=forbid`を強制する。既存`JobRequest`、画像/G8 tool、private workspace契約は変更していない。

create/edit/materialはHostへ`detached=true`のchild Jobを作って即時local Job参照を返す。以後はchild
credentialだけでprogress/control/terminalを行い、期限前refresh、Host cancel、Blender slot待ち中cancel、
graceful stopを処理する。bearerは永続化せず、SQLiteにはlocal/Host Job ID、stable owner、exact input/
idempotency hash、runtime/version pin、base revision、stage/result/retry parent、terminal outboxだけを保持する。
restartでcredentialを失ったqueued/running taskは`host_context_lost`/`service_restarted`へfail-closedし、
Blenderを暗黙replayしない。retryはfailed/canceled Jobとbyte-equivalent typed inputだけを新しいJobとして受ける。

実HostのAgent tool callごとにexecution subjectが変わるため、Media Forgeだけではscene ownerを安全に安定化できない
ことを確認した。汎用Host変更をControlDeck PR #270として分離し、署名済みactorがあるintrospectionだけへ
optional `actor_subject=user:<opaque id>`を追加した。Host focused auth/jobsは27 passed。fullは935 passed / 1 skippedに
加え、共有test DBのactive Job漏れ4件とGPU sensor subprocess call順1件の既存order-dependent failureで、
本変更のfocused testはgreen。PR #270はmerge commit
`1c611d6d05d3e90a8b1b07073c9f93c7087faad1`でmerged。Media Forgeはexecution `subject`をHost操作権限のまま保持し、
optional `actor_subject`はowner keyにだけ使う。

実Blender 4.5.9のmanager create→edit→materialは3 Jobすべてsucceeded、terminal送信済みで、submissionは
0.002503 / 0.010185 / 0.001896秒。sceneはrevision 3となり、最終`.blend` 501,758 B / SHA-256
`7fd17795cce0ae9db9d522b8395ffa86b0bacadefbe724362e6d0472989156e1`、GLB 62,136 B / SHA-256
`6686309eb6dffab95aa355387d5f2878f6176cafd9479750fd314e1d3ecf768b`、画像dependency SHA-256
`a97abcc3e51467ce0934adf54d076d3c3e95967437067eed5551cb081648e57f`。provenanceは
`scene.material.bind` / `derived`、親sourceとtextureの両hashを保持した。Blender validatorはobjects 4 /
meshes 4 / vertices 330 / triangles 644 / materials 2 / images 2 / external 0 / autoexec disabled、
独立GLB validatorはimages 1 / textures 1 / materials 2でpassed。

最終worker単体ではclosed vocabulary全10操作を実Blenderで実行し、0.22秒、最大RSS 308,880 KiB、
`.blend` 507,364 B / SHA-256
`4d1d9f9812e36ddd617675c6101f6757ff5067346bbf119c2a407a1a24aa7df6`、stable object 6件、
autoexec disabledを確認した。focused agent/job/contract 28件とmaterial cancel 1件がpassed。exact head
`./mf.sh test`は977 passed / 既知Starlette warning 1件 / 96.24秒。

0.28.9 exact bundleは31,619,208 B / SHA-256
`ec24a51465e952929239f822ac7f33f971ee5d7230ef3f91527884edea9d3c07`。展開binary doctorは
`ok / 0.28.9 / packaged=true`。exact package process `127.0.0.1:9188`は新workflow/tool contributionを
availableとして返し、OpenAPIのscene/job 7 tool routeとworkflow route、Draft 2020-12 schema 7件を実配信した。
environment snapshotを置いていない隔離data rootなのでhealth全体は意図どおり`setup_required`であり、
これをinstalled healthへ読み替えない。

実installed ControlDeckでのOpenCode指示→shape→texture→GLB→grant配置、opaque iframe、120秒超job、
10分超credential refresh、実process restart/rollbackは **NOT TESTED**。3DS-7のsource/package surfaceを完了し、
これらは次の3DS-8 release acceptanceで通し確認する。

## 2026-09-06 — 3DS-8 OpenCode model-schema compatibility

branch `ux1/3d-opencode-schema`。Media Forge v0.28.9をControlDeck標準updaterで0.28.0から更新した。
公開bundleの再取得SHA-256は
`1e788487a2a8aba2b4e80220f2597ce8e438841a753f03f06ee41917b2d68237`、updateは10.56秒 / 最大RSS
782,884 KiB。`current=versions/0.28.9`、旧0.28.0保持、新PID 2143032、health healthy、永続data rootは同一。
Blender 4.5.9は公式377,929,956 B / SHA-256
`dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d`を54.18秒で導入し、version/Python/
GLTF import/export probe成功。Web pack 1.0.0は15,769,716 Bを5.33秒で導入し、TigerVNC 1.16.2、noVNC 1.7.0、
全必須hash、software display probeに成功した。

ControlDeck発行のstable actor/project-scoped token、実OpenCode 1.18.27、Qwen3.8-27Bでtyped制作を開始したが、
最初のLLM requestはHTTP 400
`JSON schema conversion failed: Unsupported ref: scene-texture-request.json`でtool call前に停止した。
原因は3DS-6bの`job-request.json`だけがscene textureを外部file `$ref` にしており、Hostのmodel-facing schemaから
llama.cppへ未解決参照が渡ったため。公開field/意味を変えず同一定義をlocal `$defs`へ内包した。全agent tool schemaの
外部 `$ref` 禁止とscene texture付きjob全体のDraft 2020-12検証を回帰化し、focused contract/baseline/agent 23件、
exact head full 978件 / warning 1件 / 99.02秒PASS。exact 0.28.10 bundleは31,618,956 B / SHA-256
`00cfb8011802ccdb55341ef5845e6a3e1507394e616d004017f6e03d22c636c2`、展開binary doctorは
`ok / 0.28.10 / packaged=true`。
版は0.28.10。正式署名bundle・installed update・同じOpenCode再試行はこのsliceで続ける。opaque iframe、GPU共存、
120秒超job、10分超credential、rollbackは **NOT TESTED**。

## 2026-09-06 — 3DS-8 OpenCode pack schema compatibility

v0.28.10の実ControlDeck/OpenCode 1.18.27 / Qwen3.8-27Bは、schema 400を越えてtyped scene作成を完了した。
local Job `job_8ddb5be450e14369b2ffbe872f59bd96`、Host child `ae68f3b69b0b`はsucceeded / terminal sent。
scene `scene_ca920fd634b14dfea8215567e930bb7a`、revision
`revision_0140264e6a024ea78f8ec2c251b2c899`、objects 4 / meshes 4 / vertices 126 / triangles 236、
autoexec disabled、Blender/GLB validator passed。GLB Asset
`asset_6e3d24cb8e62453e841db3e3f2c72a19`は20,256 B / SHA-256
`2afac7d44d23335cc31776bb8036ac63b957fc1f4b5a292df73d4c8ead8791ad`。project output grant取得も成功した。

最後の`media.pack`だけ、モデルが引数を毎回`{}`にしてOpenCodeのdoom-loop保護で停止した。exact fieldを指定した
限定runでも再現し、auto runは明示停止した。原因は`project-asset-placement.json`だけtop-levelにpropertiesがなく、
単一/batchの各`oneOf`枝内にfieldを置いたmodel-decoder非互換。公開2形態とvalidationを維持し、共通propertiesを
top-levelへ移して`oneOf`を排他条件だけにした。single/batch valid、両形態混在invalid、model-visible fieldsを回帰化し、
focused contract/baseline 22件、final full 979件 / warning 1件 / 97.94秒PASS。最初のfull 1件は既存の
branch object宣言assertで、各branchの`type=object`を維持して解消した。版は0.28.11。
pre-release candidate bundleは31,618,189 B / SHA-256
`2253835678bca317a5cdf5757520f60063a3faa79da9973224619c0d4eb999db`、展開binary doctorは
`ok / 0.28.11 / packaged=true`。正式release/installed再試行の結果は次節へ記録する。

## 2026-09-06 — 3DS-8 stable scene owner

PR #239 / #240はmerge済み。正式v0.28.11 bundleは31,618,928 B / SHA-256
`fc1ce4c04d26a29a68ca0a9e527eba6d0786de017629d5cb9f82b73783d9a1f8`で、署名assets公開後の再取得hash一致を確認した。
ControlDeck標準updateは10.54秒、installed health healthy。実OpenCode 1.18.27 / Qwen3.8-27Bはscene create、
durable status、snapshot、GLB export、project output grant取得と`media.pack`を完走した。scene
`scene_ca920fd634b14dfea8215567e930bb7a`はrevision
`revision_0140264e6a024ea78f8ec2c251b2c899`、objects 4 / meshes 4 / vertices 126 / triangles 236、autoexec disabled、
Blender/GLB validator passed。GLB Asset `asset_6e3d24cb8e62453e841db3e3f2c72a19`は20,256 B / SHA-256
`2afac7d44d23335cc31776bb8036ac63b957fc1f4b5a292df73d4c8ead8791ad`、Host asset化とgrant配置receipt committedを確認した。

installed opaque iframeを実Chromeから開いた次の実測ではscene rowが現れず、同connectionから直接呼んだ
`scenes.list`も空配列だった。SQLiteのscene ownerは`user:16`。Agent REST routeはHost署名済み
`actor_subject`をownerに使う一方、workspaceのscene catalog、working copy、backup/restore、Blender session、RFBは
短命browser tokenの`subject`をownerにしており、同じ利用者の実行経路間で永続sceneを共有できなかった。

branch `ux1/3d-stable-scene-owner`で3D永続資産routeだけを既存`scene_owner()`へ統一した。RFB再認証はaddon、execution
subjectに加えてactor不変も検査する。preferencesはtoken subject単位を維持した。同じ`actor_subject=user:7`を持つ
user/job tokenから同じsceneを読め、`user:8`からは`scene_not_found`になる回帰を追加。版は0.28.12。focused
scene/workspace/backup/Blender/Host transport群はPASS。exact head `./mf.sh test`は979 passed / 既知Starlette
warning 1件 / 100.56秒。0.28.12 candidate bundleは
31,618,636 B / SHA-256 `e4a7b1963e2d81e75055a45b8d843708758a0bc54642fab0e147f0226b6a946e`、
隔離data/cacheへ展開したbinary doctorは`ok / 0.28.12 / packaged=true`。PR/release/installed browser再実測は未実施。

## 2026-09-06 — 3DS-8 opaque iframe noVNC module loading

stable owner PR #241はmerge commit `01d10866b1de1392aa894a89361418ffc2041c3e`でmerged。main exact sourceから再構築した
正式v0.28.12 bundleは31,618,328 B / SHA-256
`f2a9623e73833219bd85194b5d545ceec36e67ff4a398b9afa4d25a2c70124fa`。manifest 279 B、signature 89 Bで自己検証し、
tag targetは同merge commit。公開面から4 assetを再取得して全hash一致を確認した。ControlDeck標準updateは10.56秒 /
最大RSS 788,948 KiB、`current=versions/0.28.12`、旧0.28.11保持、新PID 2174325、health healthy。

owner修正後のinstalled Chromeでは、Agent作成sceneの`scenes.list/get`とdetail表示が成功し、Blender Web session
`blendersession_b88b1e11b0654e5997bc0acdc1b862db`は`ready`、software display 1280x720、TigerVNC/Blender実process稼働。
一方、opaque origin `null`からnative `import()`したnoVNC `rfb.js`はHost frame cookieを送らず、HTTP認証前に401となり、
consoleは`No 'Access-Control-Allow-Origin' header` / `ERR_FAILED`、接続表示はreconnectingのまま。sessionは明示stopした。

branch `ux1/3d-web-client-cors`で、同梱`blender-rfb-loader.js`を`crossorigin=use-credentials`の外部moduleとして遅延ロードし、
そのmodule graphにだけHost frame cookieを送るよう修正した。loaderはmanifest-pinned noVNC `core/rfb.js`だけをimportし、
remote URLや利用者入力を受けない。公開API/contributionは不変。版は0.28.13。focused frontend contract、Blender web、
release bundle群はPASS。exact head `./mf.sh test`は979 passed / 既知Starlette warning 1件 / 99.39秒。
candidate bundleは31,619,516 B / SHA-256
`55d567cb14dcad501730b0ae3e9c7b11953292c756255c167bbeccb4ab25e624`、展開binary doctorは
`ok / 0.28.13 / packaged=true`。PR/release、installed browser再実測は未実施。

## 2026-09-06 — 3DS-8 opaque iframe CORS authority

PR #242はmerge commit `0fbed474262111836fa1bd25b2ca19a41a74aef2`でmerged。main exact sourceから再構築した正式
v0.28.13 bundleは31,617,052 B / SHA-256
`57be1e3fb1b740515cb40f40ec1f09d67a2ac4444c40051699e098b014e43c8a`。署名self-check、tag target一致、公開4 assetの
再取得hash一致を確認した。ControlDeck標準updateは10.54秒 / 最大RSS 788,980 KiB、health healthy。

credentialed loaderへ替えたinstalled Chromeでは認証が通った後、Media Forgeの
`Access-Control-Allow-Origin: *`とHost proxyがopaque origin向けに付ける`Access-Control-Allow-Origin: null`が併存し、
Chromeは`multiple values '*, null'`としてmoduleを拒否した。Hostはuser/frame credentialを知るCORS authorityであり、
Media Forgeはprivate noVNC/loader routeからorigin headerを除く。standalone routeはsame-origin。公開API/contributionは
不変。版は0.28.14。focused Media Forge群とHost opaque subresource回帰1件はPASS。exact head `./mf.sh test`は
979 passed / 既知Starlette warning 1件 / 99.40秒。candidate bundleは31,619,226 B / SHA-256
`17a28d98ffe8cd3afaf71b8b8e66aea902675f423708db00602b45f366d7ab42`、展開binary doctorは
`ok / 0.28.14 / packaged=true`。PR/release/installed browser再実測は未実施。

## 2026-09-06 — 3DS-8 installed lifecycle / recovery conflict

正式v0.28.14 bundleは31,619,593 B / SHA-256
`b4c8b6eae43e9e290339b30522081f388f40c3e8e8d3299e4dd1cda5cf27bd2b`。公開4 assetを再取得しhash一致、
ControlDeck標準updateは10.67秒 / 最大RSS 789,092 KiB、health healthyだった。実OpenCode 1.18.27 /
Qwen3.8-27Bはtyped scene作成、status、snapshot、GLB export、project grant、`media.pack`を完走した。

実installed opaque iframeのscene `scene_ca920fd634b14dfea8215567e930bb7a`では、621.451秒のsessionを維持して
reload/reconnect、別browserの`blender_session_busy`、noVNC入力、revision 2→3保存を確認した。desktopは
inner/client/scroll 1056、mobileは390/390/390で、mobileのBlender操作はdisabled、browser error 0。
既存Library画像Asset `asset_0daea4caf7c74cd49ed85bbef9fba0d6`をBlade/base colorへ明示適用し、
revision 3→4となった。

Blender unitのSIGKILLは2.846秒で`blender_session_runner_lost`となり、working copy 1,438,783 B /
SHA-256 `a5a462671e1607780bed2cfd37d8f3757dcd722fd79a54873905bdd2215cfe45`をcandidateへ保持し、
新sessionからrevision 6へ保存した。idle/disconnectを一時5秒にした実sessionは接続から8.695秒で
`blender_session_idle_timeout`となり、candidateをrevision 8へ保存した。設定drop-inは削除し、installed serviceは
既定1800/300秒へ戻した。MediaForge core再起動中の実RFB sessionは0.933秒でhealth復帰し、同sessionへ再接続して
revision 9へ保存した。再起動で切れた旧WebSocketの403/1006だけを観測し、再接続後は成功した。

実Host署名service tokenをTTL 20秒で発行してRFB bannerまで接続し、15秒周期再検査がexpiryを検出して
25.038秒後にcode 4403 / `host service token expired`で閉じた。sessionは
`blender_session_host_revoked`、candidateをrevision 10へ保存した。秘密tokenは出力・保存していない。

R9700/gfx1201の実VRAMは34,208,743,424 B。Eevee GPU 64x64は2.7709秒、Cycles HIP 4 samplesは
0.26939秒、最大RSS 3,002,844 KiB。Host LLMが27 GB級VRAMを使用中にtexture image jobを投入すると
Brokerが`waiting_resource`へ置き、LLMをunload/reloadしても画像workerと同時実行せずcancelできた。
Host watchdog再起動中のdetached scene jobは`host_context_lost`へfail-closedした。これは120秒超の成功証拠ではなく、
画像生成成功・採用と120秒超detached jobは **NOT TESTED**。

ControlDeckのrelease verifier focused 37件はPASS。正式v0.28.14に対しtrusted署名は受理し、signed manifest改ざん、
wrong key、artifact改ざん、v0.28.13 downgradeはすべて拒否した。live update失敗を注入したrollbackは
**NOT TESTED**。

GUI編集中にscene headを進めてから保存した実競合は正式revisionを上書きせず`scene_revision_conflict`となった。
一方、commitがworking copyをrecoveryへ遷移した後の失敗処理が同じ遷移を再要求し、保存されているcandidateを
responseへ投影できず`result.recovery=null`となる不具合を検出した。`retain_working_copy_for_recovery`を
owner検証付きidempotent操作へ変更し、既存recovery recordをそのまま返す回帰を追加した。版は0.28.15。
focused workspace/session 27件、exact head `./mf.sh test`は980 passed / 既知Starlette warning 1件 /
100.41秒。candidate bundleは31,618,953 B / SHA-256
`f95701cb35c609ad3cf8b0ed75323ad4eb9940171e72b1a20b29f58124f5a02f`、展開binary doctorは
`ok / 0.28.15 / packaged=true`。正式releaseとinstalled競合再確認は **NOT TESTED**。

## 2026-09-06 — 3DS-8 completion / v0.28.15 release

PR #244はmerge commit `aa054bc804dbcce4cb1262cc40188f8db9b01fd0`でmerged。exact mainから再構築した正式
v0.28.15 bundleは31,463,968 B / SHA-256
`6944b24677d40ca176b460f6590f6167780cfb5fd79f1e76995688913526f75d`。manifest 279 B、signature 89 B、
tag target一致、公開4 asset再取得hash一致。Host consumer verifierでpublisher署名、artifact size/hash、safe extract、
package/add-on identity、capability上限を通し、展開binary doctorは`ok / 0.28.15 / packaged=true`。

ControlDeck標準updateはv0.28.14→v0.28.15を10.73秒 / 最大RSS 772,524 KiB / swap 0で完了した。
`current=versions/0.28.15`、previous v0.28.14保持。rollback再起動後の最終PIDは2264346、service active/running、
drop-inなし、health healthy。
実installed opaque iframeでGUI sessionをrevision 11から開始し、並行restoreでrevision 12へ進めて保存した。
結果は`failed / scene_revision_conflict`、scene head/revision countは12のまま、responseはcandidate
`working_0a35fec723ae491bb9abf93c6e533077`を返した。実`scene.blend`は1,438,783 B / SHA-256
`11ff0e65eeec0f33ffb1d7e35dc2b82319b0dd467de964b493ee7b1e3151dcaa`、browser error 0。

Host LLM `requests_processing=0`、VRAM 27,383,910,400 Bからtexture生成を開始すると、BrokerはLLMを停止して
画像workerを実行した。Job `job_e22d39271e7c46da9c306f7c0cf94a0b`は57.869秒でsucceeded。
FLUX.2 Klein 4B / diffusers 0.40.0、1,024x1,024 PNG 1,737,483 B / SHA-256
`a3cb9e4f70eb8a396307576cfccef57e721ac50fa10f7f73a62d671f6276494d`、画像validator 4件passed、
weights hashとApache-2.0 provenanceを保持した。opaque iframeで明示選択してBlade/base colorへ適用し、
revision 12→13、同Asset dependency、scene/GLB validator passed、browser error 0。終了時VRAM 2,625,077,248 B。

120秒超のdetached lifecycleは、実Blender 4.5.13 child PID 2262210だけへSIGSTOPするfault injectionで測定した。
Job `job_650645314a624fe788d04f4e87462055` / Host child `96d2c1faa327`はdetached受付後、
`running / blender_recipe / progress 0.25`を121.996秒と132.033秒に再照会できた。132.085秒に公開
`media.job.cancel`を送り、133.122秒で`canceled / host_terminal_sent=true`。Host Jobもcanceled、対象childは消滅、
残存background Blender 0。別の64 sphere完走試行はGLB 64 MiB上限を`scene_preview_invalid`で拒否したため、
これを長時間成功へ読み替えなかった。

live rollbackは一時Ed25519鍵で署名した隔離v0.28.16を実ControlDeck updaterへ渡した。署名・展開・provision・
doctor・service healthまで通り、`current=0.28.16`とpackaged doctorを観測後にhealth failureを注入した。
9.656秒で例外を返し、`current=0.28.15`、service、Add-on登録、doctor、health healthyへ復帰した。
一時candidate version/download、worktree、秘密鍵は確認後に削除した。正式公開v0.28.15は不変。

`./mf.sh test`はPR #244 exact headで980 passed / 既知Starlette warning 1件 / 100.41秒。既存画像、G8、
OpenCode制作、opaque UI、lifecycle、GPU/Broker、signed release/update/rollbackを実installed Hostで確認し、
当時は3DS-8をVERIFIED、統合3D Studio初期提供を完了と判定したが、以下の完了監査で撤回した。GPU GUI表示、期限内child credential refresh、実installed環境への
容量不足再注入は **NOT TESTED**。interactive GUIはsoftware displayとして提供し、個別Eevee/Cycles GPU probeを
GPU GUIの証拠へ読み替えない。Expert scriptは別capability 3DS-X。

## 2026-09-06 — 完了監査再開 / standalone recovery transport

基準main `1f4392a2d426a742046d0c03c99272ffb5e41c87`からbranch `ux1/3d-standalone-recovery`。
PR #213の必須条件との再照合により3DS-8をPARTIALへ戻し、初期提供の完了判定を撤回する。
過去の個別実測は維持する。全GOALと必須scenarioの判定・残件を
[`3ds-completion-audit.md`](implementation/3ds-completion-audit.md)へ記録した。

コード確認でstandalone session startが`recovery_working_id`を落として通常startへ変える不具合を特定し、
session POSTへ転送する修正と、そのbody内にfieldがあることを検査する回帰を追加した。
`/data1tb/ControlDeck/app/.venv/bin/python scripts/3ds_standalone_session_transport_smoke.py`は
実ChromiumでproductionのstandaloneCallを実行し、隔離loopback HTTP記録器が受け取った
復旧start/通常start/save/stopの4件のbodyをassert、browser error 0。認証/既存データは使用しない。
HTTP記録器は本番backendではなく、実Blender復旧やinstalled受入の証拠にはしない。
修正後の実Blender復旧・署名bundle受入は **NOT TESTED**。

`acquire_recovery_working_copy`のbase revision不一致拒否も確認した。競合candidateのbytes保持は
確認済みだが、分岐救出の利用者経路は未確認。上書き防止を外して解決したことにしない。
長時間credentialは失効**前**のrefreshが必要。132秒Job維持と621秒GUI接続だけから
child credentialが更新されたと推測しない。次の実測と設計照合を継続する。
Hostコードの既定TTLは600秒、recipe managerのrefresh marginは120秒、worker timeoutは180秒。
実Host DBへのread-only SQLで`audit_logs`の`username=addon:media-forge`かつ
`action=addon.runtime.job.credential.refresh`を検索すると0件だった。現在残る記録の観測として扱う。

最終`./mf.sh test`は981 passed / 既知Starlette warning 1件 / 102.21秒。
初回は追加testの文字列切出しミスで1 failed / 980 passed。範囲修正後にfrontend 149件と全体を再実行した。

## 2026-09-06 — recovery fork / v0.28.16 candidate

main `911f154`から`ux1/3d-recovery-fork`。競合candidateを別sceneへ救出するprivate
`scenes.recovery.fork`を追加した。元head/candidateは変更せず、snapshotをpinned BlenderとGLB validatorで
検証、依存blob hashを照合して初版へ確定。元版・candidate・source asset lineageをprovenanceへ保持する。
再送は同candidateに対応する同sceneを返す。埋め込み/standaloneの同じdomain経路と日英・mobile UIを実装した。
embedded `scenes.list`がworking_copiesを返さず再読込で候補を失う点も修正した。

`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_recovery_fork_e2e.py --serve`に新しい隔離data dirと
既存4.5.9 legacy rootを渡し、実BlenderでCube位置を変更した.blendを作成、candidateを残して元headを進めた。
Playwright環境から同scriptの`--url` modeで実HTTP/browser操作を行った。
source: scene `scene_d2204e713dd44887809379aa650d4070` → recovery `scene_f21a1cac27295a5da0f5f39955dbebeb`、
434,663 B / SHA-256 `fab9c6d090accf82d9a6cfde872fe2f9f9299f60908acf5c8ec3a7148d3d5e0c`、0.534秒。
候補bundleの実process: scene `scene_2a9a84e4a9494f648dde816d295ea46b` → recovery
`scene_ef8430a81ec05914a8e4fa6234cb130f`、434,663 B / SHA-256
`a6b1792d203085cd76299aae51aeaa471b6e534b033dbd0df042a8f979b4a3c3`、0.540秒。再送0.287秒。
両方で元head不変、candidate/source asset hash一致、320px overflow 0、再送は同sceneをassert。
package再送はconsole/page error 0。証拠は`/data1tb/mf-recovery-fork-{source,package,package-retry}-evidence-20260906`。

回帰はowner違い、scene違い、欠落/不正/symlink、runtime不一致、依存hash不一致、同時要求、取消後再試行、
commit失敗asset rollback、restart後idempotency、両transportを追加。`./mf.sh test`は993 passed /
既知Starlette warning 1件 / 102.15秒。
v0.28.16 candidateは31,623,524 B / SHA-256
`5eeb7e510233bdc06e35db3aaf0b0c1a92c8da9abe3a1218a53e040edfeca2b5`、doctorは`ok / 0.28.16 / packaged=true`。
正式署名公開・標準update・installed候補の分岐救出は **NOT TESTED**。3DS-8全体はPARTIALのまま。

## 2026-09-06 — installed recovery fork / 正式v0.28.16

PR #247 merged `53faaeb52770b1f151f0000fa73dc02566a99acb`からdetached worktreeで正式bundleを再構築。
31,468,656 B / SHA-256 `8ae198224aa361d31406d2fce151ca4a1eda2ecd0892bd0259bafc97e1b810df`、
packaged doctor `ok / 0.28.16 / packaged=true`、正規publisher署名を自己検証。
https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.16 を公開し、
公開4 assetを`gh release download`で再取得、artifact hash一致・tag target一致。
manifest279 B、signature89 B、sha256119 B。標準`registry.update('media-forge')`で実Host consumerの
署名/integrity/provision/health経路を実行し、11.277秒で0.28.15→0.28.16、managed/enabled/healthy。
計測したPython親processのmaxRSSは48,464 KiBで、childを含む全体peakとはしない。
最終serviceはPID2286511、active/running、drop-inなし。更新前に実行中Job/sessionが0であることをDBで確認した。

`scripts/3ds_recovery_installed_e2e.py`をHost Playwright環境で実行。
以前保存競合で残った`working_0a35fec723ae491bb9abf93c6e533077`を、installed opaque iframeの明示buttonで
`scene_3ac2b7089a3b5cc3b7b1a95ffd96594f` / `revision_aa65c326dc4f454bab24c96b9282ab9c`へ救出した。
元`scene_ca920fd634b14dfea8215567e930bb7a`の13版は完全一致、candidate bytesは1,438,783 B /
SHA-256 `11ff0e65eeec0f33ffb1d7e35dc2b82319b0dd467de964b493ee7b1e3151dcaa`で不変、保存source assetも同hash。
pinned Blender4.5.9でautoexec無効、4 objects/236 triangles、独立GLB validator passed、GLB891,224 B。
元版の画像dependency `asset_0daea4caf7c74cd49ed85bbef9fba0d6`とhashを継承し、source scene/revisionを
provenanceへ保持。再送は同scene。所要0.978秒、origin null、console/page error0。
mf-e2eのpassword/login metadataはfinallyで復元し、この試験が作ったHost認証sessionだけ失効した。
証拠: `/data1tb/mf-recovery-fork-installed-evidence-0.28.16/observations.json` と screenshot。

source/candidateの隔離HTTP serverはすべて停止、exact release用worktreeも削除した。
正式導入への変更は標準updateと利用者向けforkのみ。元scene/candidate/runtimeを消していない。
長時間child credential refreshなどの残件はNOT TESTEDのまま、全体3DS-8はPARTIAL。
今回作成したcandidate/release展開directory各61 MiBと隔離fixture各2.6 MiBの計4 directoryは
`gio trash`で退避した。ごみ箱から復元可能。公開再取得4 assetと観測JSON/screenshotは保持した。
installed acceptance script追加後の最終`./mf.sh test`は993 passed / 既知warning1件 / 101.74秒。

## 2026-09-06 — child credential acceptance / Host interruption

基準main `9ff49ac`、branch `ux1/3d-credential-refresh-acceptance`。導入済みv0.28.16に対し、
正規Host service identity（既存mf-e2e、秘密値はメモリ内のみ）でAgent APIへCPU recipeを投入する
`scripts/3ds_credential_refresh_e2e.py`を追加。4件の試験Blender childをrecipe markerとpidfdで識別し、
各160秒停止/167秒自動再開、後続2件の600秒超待機・refresh・取消・成功・Host同期を検査する。
Host TTL600秒・refresh margin120秒・worker timeout180秒は変更しない。自然なcompute時間や
OpenCode言語制作の証拠とはしない。試験はHost diagnostic venvとPYTHONPATH=Host/backendで実行し、
productのHost importは追加していない。

実行コマンドは`PYTHONPATH=/data1tb/ControlDeck/app/backend /data1tb/ControlDeck/app/.venv/bin/python
scripts/3ds_credential_refresh_e2e.py --evidence-dir <専用directory>`。
初回`/data1tb/mf-credential-refresh-installed-0.28.16`はbootloaderの直接childだけを探索したため
workerを捕捉できなかった。Job `job_b42151196e26470ab33ee4d35040e646`はsucceededで終了した。
子孫探索修正後の`-retry1`ではchild PID2293568を160.069秒保持し再開、次のchild PID2295744を停止。
後続`job_f9862fc65fb848ebad38e563ddb0e3ca` / Host `b77c9525e2dc`は251.002秒までrunning。
次の照会が502 `host_unreachable`、1件succeeded / 5件`host_context_lost`でfailedになった。
Host PID2292673のaccess logは08:39:04〜08:39:17 JSTに約13秒途切れた。原因は未特定であり、
同時刻のmetrics timezone warningだけから因果を断定しない。

test群を並走させない`-retry2`でも150.297秒で6件すべて`host_context_lost`。
対象は`job_2fda5a66d266464cb3702f3c5d3f7071`、`job_e955c6ac272346d6b73b07708a4b7170`、
`job_66eb332aef20483e952ecdedfef597a2`、`job_2bf2e25572b342b0b992cd972cfb42a9`、
`job_7ce07de1334b4595b059afb3b79e3e12`、`job_a2a5b1a3e9fb43d7bbcfab750ebbe7b0`。
Host journalは08:42:17 watchdog timeout/ABRT、08:42:24再開、08:45:11停止、08:45:15再開を記録した。
本試験はHost restartを要求していない。HostはPID2299189でactive、MediaForgeはPID2286511のままactive。
全対象のlocalはfailed、Host DBはinterrupted、refresh監査は各0件、terminal_sentは6件ともfalse。
finally cleanup後のactive local Jobは0、実Blender recipe childは0。対象外Job/既存sceneは操作していない。

試験結果は **FAILED / credential refresh NOT TESTED**。現在コードには終端payloadの永続化と3回の即時送信は
あるが、その後のoutbox再送consumerが見当たらない。またHost runtimeの`host_job`は`jobs.get`のmemoryのみで
DB履歴には到達せず、再起動後の終端照合を妨げる。次は正規identityに基づく再送/照合を解決する。
Hostが確定したinterruptedを無断でfailedへ上書きしたり、未送信を送信済みと表示したりしない。
証拠は3 directoryのevents.json、今回のread-only SQLとsystemd journal。全体3DS-8はPARTIAL。
最終`./mf.sh test`: 993 passed / 既知Starlette warning 1件 / 106.33秒。

## 2026-09-06 — Host終端履歴の読み取り前提

MediaForge側ではHost再起動後のDB履歴にアクセスできないため、汎用Host PR
`souten-yd/ControlDeck#275`（merged `40f1bc0`）でJob controlの履歴読み取りを追加した。現行responseのまま、
正確なAdd-on kind、Job scopeまたはowner、終端状態を照合する。非終端DB行は409、
更新/refreshは404を維持する。Hostの確定終端は書き換えず、実行中Jobへ復活させない。

Host `./deck.sh test`951 passed / 1 skipped / 66.76秒、最新main取込後focused37 passed / 3.49秒。
Host script `tools/addon-job-history-smoke.py`を隔離DB/systemd user unitで実行し、別processの
startup recoveryでrunning→interrupted、実HTTP200、別Job403、refresh404、update404を観測した。
最終証拠`/tmp/cd-job-history-nzou5ckt/observations.json`。試験unit停止済み、稼働Hostは再起動していない。
導入済みHostへの適用、MediaForge outbox再送、長時間credential refresh、今回変更のPC/mobileはNOT TESTED。
この前提修正を終端同期完了とは扱わない。既存Job scopeとactor ownerを混同せず、正規identity復帰後の
再送/照合が残る。MediaForge公開contract/画像/G8/installed v0.28.16には変更なし。
引き継ぎ更新の`./mf.sh test`は993 passed / 既知warning1件 / 105.30秒。

## 2026-09-06 — terminal outbox再送と再認証後照合

source v0.28.17 / branch `ux1/3d-terminal-outbox`。Host PR `souten-yd/ControlDeck#276`はmerged `dac519b`。
汎用終端reconcileは現在有効なservice identityとownerを検証し、新calling Jobからはactive callerと
署名actorの一致も要求する。終端変更・credential更新・資源権限の委譲ではない。

MediaForgeは即時送信3回で未達だったpayloadを、有効child identityが残る間だけbackoff再送する。
identityはメモリのみ。再起動後は所有者の正規status/cancel callで当該Jobだけを再送する。
startupの中断Jobにもoutboxを保持し、確認済み一致だけsent=true、Host既存終端との不一致は
sent=falseとreceiptを永続化して再送を止める。未知/不正receiptや古いHost、認証不成立はpending。
Host controlが確定終端を返したときは制作を中断し、refreshのactor metadataを落とさない。

実行: `PYTHONPATH=/data1tb/ControlDeck-job-history/backend /data1tb/ControlDeck/app/.venv/bin/python
scripts/3ds_terminal_outbox_e2e.py --host-repo /data1tb/ControlDeck-job-history
--core-python /data1tb/ControlDeckMediaForge-3ds4/.venv/bin/python`。
隔離Host systemd processと別core venvで、seed→consume→consumeの3processを実行。
正規introspectionとHost実HTTPを通り、local `job_715a634111454b4d8231e28998d0fb7a` / Host `cf546939b730`は
local failed / Host interruptedを保持してmatches=false、local `job_38af3bc148624939801b76faa20419ca` /
Host `5ab5e06af58b`はsucceededを適用してmatches=true。再起動後の再照合も同receipt、local Job2件、
recipe再実行0。証拠`/tmp/mf-terminal-http-1ppzav37/observations.json`。試験unitはfinallyで停止、inactive。
初回2試行はcore PYTHONPATH不足によるimport失敗。core venvを変更せずrepo rootを追加して解消した。

Host full testは960 passed / 1 skipped / 61.41秒。今回の実機受入は終端fixtureのdomain manager→Host HTTPであり、
full core Agent HTTP、実Blender制作、PC/mobile、installed package、600秒超credential refreshはNOT TESTED。
installed v0.28.16は変更なし。新schema/receiptは加法的。公開署名release/導入後受入は次工程、3DS-8はPARTIAL。
最終source再確認も同じfalse/true・interrupted/succeeded・local2件。
証拠`/tmp/mf-terminal-http-4rjhhdmw/observations.json`、試験unitはfinallyで停止した。
最終`./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 109.09秒。

## 2026-09-06 — v0.28.17署名公開・標準導入・installed終端照合

PR #251 merge `4293d2086aaeed4784a2ad0c2b9776f88415c043`をexact release worktreeでbuild_release_bundleし、
既存publisher keyでsign_releaseした。core venvにはcryptographyがないため初回sign importは失敗。
coreへ依存追加せず既存Host diagnostic venvで署名toolを実行した。artifact31,470,272 B、SHA-256
`997f6cef6e941eca6603cff199d3dbc43a28d030d79ae7fdfbbfe9109af500b3`。通常release v0.28.17を公開し、
4 asset再取得/hash一致、Host publisher verifierのsize/hash一致、tag target一致を確認。
公開再取得directory `/data1tb/mf-0.28.17-public-20260906`。packaged doctorはok/0.28.17/packaged=true。

生成中だった別Job `job_29459166c091438c8c14767cd35c130e`を操作せず、Host/local active0とworker2399992終了を
確認後、Host mainを`dac519b`へfast-forward/restartした。dirty tsconfig.tsbuildinfoは保持。
MediaForge SQLite online backupを非公開専用directoryへ作り、標準registry.updateを実行。
13.627秒で0.28.17/healthy/enabled、actual executableはversions/0.28.17/bin/mediaforge。
Host PID2403274、MediaForge MainPID2403709/child2403714。backupとupdate.jsonは
`/data1tb/mf-0.28.17-installed-evidence-20260906/`に保持する。

`scripts/3ds_terminal_outbox_e2e.py --package-executable .../bin/mediaforge`で配布binaryのfull Agent
status/cancelも実HTTP確認。隔離Job2件・Host差異保持・一致sent=true、再照合で件数不変。
証拠`/tmp/mf-terminal-http-hcxvio45/observations.json`。隔離Host/core unitはfinallyで停止済み。
次に`scripts/3ds_terminal_installed_e2e.py`で前回retry2の明示6 Jobをowner/failed/Host interrupted検証後に
installed status/cancel/statusで18回照会。0.304秒、sent=false・matches=false・Host interruptedを保持し、
Job/asset/scene/revision件数不変。証拠`/data1tb/mf-0.28.17-installed-terminal-retry1-20260906/observations.json`。
初回は別生成Jobを検出して全体idle assertで止まった。終端fixtureだけを操作するため全体idle条件を外し、
対象scope検証と件数不変は維持した。別のactive Jobのcancel/restartは行っていない。

長時間credential scriptに期待version明示引数を追加。今回の終端fixture受入を600秒超refreshの証拠にはしない。
GUI上のHost差異表示、長時間refreshなどの残件は未確認で、3DS-8全体はPARTIAL。
受入script更新後の`./mf.sh test`: 1004 passed / 既知warning1件 / 131.28秒。
exact release worktreeは削除した（Gitから再作成可能）。生成したbuild出力とpackaged展開先の2 directoryは
gio trashへ退避し復元可能。公開再取得4 asset、観測JSON、更新前DB backupは保持する。

### v0.28.17長時間credential試験 — 更新条件前に中断

`PYTHONPATH=/data1tb/ControlDeck/app/backend /data1tb/ControlDeck/app/.venv/bin/python
scripts/3ds_credential_refresh_e2e.py --expected-version 0.28.17
--evidence-dir /data1tb/mf-credential-refresh-installed-0.28.17-20260906`。
全回帰test終了とHost/local active0を確認後に実行し、test群は並走させなかった。
child2409636は160.0676秒停止・再開。child2415439を161.690秒に停止。
191.712秒まで後続running、222.109秒にConnectError、225.185秒にfailedを検出した。
systemdは09:40:12 JSTにMediaForge停止、09:40:13再開を記録。本scriptはrestartを要求していない。
要求主体は未特定。Host PID2403274は不変、MFはMainPID2416323でactive。

最終read-only SQLでは、6件は1 succeeded / 5 failedでHost/local一致、全件host_terminal_sent=true、
credential refresh監査は各0件。blocker0はsucceeded、blocker1はscene_recipe_failed、残る4件はservice_stopped。
Job/Host ID対応はevents.jsonのsubmitted6件に固定。finally後active local0、停止対象child2件とも消滅。
結果はFAILED / credential refresh NOT TESTED。正常なshutdown終端通知の証拠は得たが、480秒条件前の
停止なので更新成功ではない。次の試験には約11分間Host/MediaForgeを再起動しない実行枠が必要。
並行Host側のuntracked frontend/e2e/mediaforge-library.spec.tsとdirty tsconfig.tsbuildinfoは保持した。
最終現物確認では並行PR #252（Library thumbnail改善、merged `7434d7f`）が入り、installedは
0.28.18/healthyへ変わっていた。現行core SHA-256は
`34b5a0f1c7edc0ed65732e4dc26768382be819d1265db4e172a4cbc1aa9c07ac`。
本turnの公開・標準導入・18call照合は0.28.17で取得した証拠であり、新版へ読み替えない。
0.28.18の導入操作は本turnでは要求していない。現行を0.28.17へ戻す操作は行わない。

## 2026-09-06 Library viewer six-axis — CANDIDATE VERIFIED / INSTALLED NOT TESTED

利用者の確認によりLibrary viewer必須を±X/±Y/±Z回転・拡大縮小へ更新した。
制作側の材質比較・採用、Blender編集、他GOAL/A〜Fは維持する。基準main `8484286`、
branch `ux1/3d-viewer-render-acceptance`。6方向15度回転・zoom buttonsを表示専用で追加。
viewer/scene比較のlazy loaderをHost frame配下のcredentialed static moduleへ共通化した。
旧root URLのCORS拒否と専用routeのACAO重複を実browserで確認し、Host変更なしで回避した。
導入済み0.28.18の失敗証拠は `/data1tb/mf-viewer-pixels-installed-diagnostic-20260906/observations.json`。

実行コマンド:
`PYTHONPATH=/data1tb/ControlDeck/app/backend /data1tb/ControlDeck/app/.venv/bin/python
scripts/3ds_viewer_render_installed_e2e.py --scene-id scene_3ac2b7089a3b5cc3b7b1a95ffd96594f
--evidence-dir /data1tb/mf-viewer-six-axis-library-candidate-20260906 --candidate-frontend frontend`。
Host diagnostic venvはsession fixture/ブラウザのみ。製品coreへHost importや依存を追加しない。
専用mf-e2e sessionを発行/個別失効し、パスワードや既存sessionは変更しない。

installed Host/backendへの実通信、candidate frontendのresponse-body overlayで検証した。
ブラウザ自身のrequestと認証/CORS応答headerは変更しない。試験contextのlocal-network-access許可を
明示し、Chromeのopaque iframe別targetもCDPで捕捉。正式bundleのinstalled受入ではない。
通常Chrome / ANGLE AMD Radeon Graphics / radeonsi raphael_mendocino LLVM20.1.2 / OpenGL ES3.2。
Library→3D→対象asset cardから、236 triangles/4 materials/0 animationsのGLBを表示。
±XYZそれぞれの描画差分24432/24594/1773/2485/24379/25023px、逆操作は全て差分0。
zoom in43020px/out41483px、orbit55633px/wheel39771px、fitで差分0へ復帰。
320pxでscroll319、page error0、scene応答不変。viewer通常動作のthumbnail cache保存は許容する。

初期試験は旧import/CORS失敗、候補HTTP再送のSec-Fetch-Dest欠落403、別iframe module捕捉不足、
headless WebGL context作成失敗を順に切り分けた。空pageのheadless Chrome/PlaywrightもWebGL2=null、
通常Chromeではcontext作成成功。software描画やR9700描画の実績とは記録しない。
細い剣の長軸回転はviewport0.5%未満でも1773px変わるため、pixel gateはidle/逆操作の完全一致を
対照に100px超の差分とした。操作角度や製品要件を変更して通したものではない。
先行scene preview入口の成功証拠は `/data1tb/mf-viewer-six-axis-candidate-headed-retry1-20260906`。

NOT TESTED: 新版署名release/導入後overlayなしの受入、日英切替・mobile実タッチの今回の追加操作、
モデル切替memory/context lossの再受入、600秒超credential更新。現行serviceの再起動/更新は行っていない。
全体3DS-8はPARTIAL。次はsource PR gate後、署名版へ反映して同じLibrary受入をoverlayなしで実行する。
source gate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 114.02秒。
`npm ci --ignore-scripts`と`npm run build:viewer`で固定依存から再構築、source/bundle hashのcontract成功。
node構文検査と`git diff --check`も成功。これらをinstalled受入の代用にはしない。

## 2026-09-06 v0.28.19 source preparation

PR #254 merged `76a91b4`のLibrary viewer修正を配布するため、addon/core versionを0.28.19へ同期。
初回read-only確認でinstalled0.28.18/healthy/enabled、Host/local active Job0、Web sessionは
failed2/interrupted4/stopped13、runtime operation ready3、model operation canceled1/failed5/ready25。
初回SQLは誤ったtable名blender_sessionsで失敗し、sqlite_masterで実名blender_web_sessionsを
確認して上記を再照会した。実行中制作は確認されなかったが、update直前にも再照会する。
署名公開・導入・overlayなしのbrowser受入は次段階。ここでは成功と記録しない。
版準備gate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 110.52秒、diff check成功。

## 2026-09-06 v0.28.19 signed release / installed Library viewer — VERIFIED FOR THIS SLICE

PR #255 merged `583fea18e710730a8c56758846c8cfeb13622e52`とtag v0.28.19の一致をGitHub/Gitで確認。
exact detached worktreeから`build_release_bundle.py --version 0.28.19`を実行し、
PyInstaller6.22.0/Python3.12.3で31,474,100 Bの正式bundleを構築した。
SHA-256 `212d062cd2e7c9ad8da67c5f8c6fe0cbd3a3bf06becf0a5688c96758a0a13ffd`。
packaged doctor: status=ok/version=0.28.19/packaged=true。
既存正式publisher keyでsign_release.pyを実行し、通常GitHub Releaseへ4 assetを公開。
manifest279 B / signature89 B / checksum119 B。公開先から再取得してchecksum一致、
Hostの`_verify_signed_release`がtrusted publisher signature/hash/31,474,100 Bを検証した。
公開先: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.19

update直前read-only照会でHost/local active Job0、Web session/runtime/model operation全終端。
SQLite online backup `/data1tb/mf-0.28.19-pre-update-20260906.sqlite3`（1,449,984 B、非公開）を保持。
標準`registry.update('media-forge')`: 10.613秒、previous_version=0.28.18/version=0.28.19/healthy/enabled。
MF MainPID2470070、10:26:06 JST開始、active/running。実行中exeはversions/0.28.19配下、
core SHA-256 `f62ae311ccd2b9375c86ac92bba3942c214869e6b5484dabd7151730eb37f1d0`は公開bundleと一致。
実HTTP `/health`はhealthy。Hostの再起動やruntime/モデルの入替えは要求していない。

実機コマンドはHost diagnostic venvで
`scripts/3ds_viewer_render_installed_e2e.py --scene-id scene_3ac2b7089a3b5cc3b7b1a95ffd96594f
--evidence-dir /data1tb/mf-viewer-six-axis-library-installed-0.28.19-20260906`。
frontend_mode=installed、candidate overlay/CDP差替え/追加接続許可なし。
通常Chrome/ANGLE AMD内蔵GPU/radeonsi LLVM20.1.2/OpenGL ES3.2、opaque origin=null。
Library→3D→asset_4d5f5c8cde0540d49747aec5dc8d68e0のカードから236 triangles/4 materialsのGLBを表示。
±XYZ15度回転の各差分24432/24594/1773/2485/24379/25023px、逆操作は全て差分0。
zoom in43020px/out41483px、orbit55633px/wheel39771px、fit/idleは差分0。
320px/scroll319、page error0、scene応答不変。専用mf-e2e sessionのみfinallyで失効。
既存password/session/sceneを変更しない。通常viewerのthumbnail cache保存だけは許容する。

NOT TESTED: 新版の日英切替・mobile実タッチ・model切替memory/context loss、材質新旧比較全操作、
600秒超credential refresh、全release A〜F。GOAL-02利用者指定操作はVERIFIED、全体3DS-8はPARTIAL。
exact release worktreeは削除（Gitから再作成可能）。build出力/packaged展開先2 directoryはgio trashへ
退避（復元可）。公開再取得4 asset、browser JSON/PNG、更新前DB backupは保持した。

## 2026-09-06 material comparison lighting/context recovery — CANDIDATE VERIFIED

基準main `8ba4f66`、branch `ux1/3d-material-compare-acceptance`。
installed0.28.19のmf-e2e-owned scene_ca920fd634b14dfea8215567e930bb7a、旧12版/現行13版を
実ブラウザで比較。2画面・閉じた両WebGL context解放・instance/handle0・scene不変は成功したが、
両版の刃が黒く、新旧材質が見分けられなかった。PNG hash差のみで材質比較を成功扱いしない。
baseline証拠 `/data1tb/mf-material-compare-installed-0.28.19-20260906`。
実GLBと固定GLTFLoaderを読み、刃はmetallic既定1/roughness0.25、新版だけbaseColorTextureを持つと確認。
old preview asset_dab6f163e9704727a2d5523eec0c23a9は20256 B、current
asset_d406176c628242b3a1feef3335e31bdaは1744476 B。現在版は画像asset_63e9f182fd114c559306f6f797ee939dと
SHA a3cb9e4f70eb8a396307576cfccef57e721ac50fa10f7f73a62d671f6276494dのdependencyを保持している。

固定Three.js同梱RoomEnvironment/PMREMGeneratorによるローカル環境反射を追加。
元のmetallic/roughness/base colorやscene/assetは変更しない。外部HDR/URI・新runtime依存なし。
環境map/一時generator/roomをdisposeし、WebGL復旧時に再生成する。
比較paneがcontext復旧後も「復旧中」のstatusを残す問題を実測し、復旧時のstats再表示を修正した。

実行（Host diagnostic venv、正規mf-e2e sessionを新規発行/個別失効、password変更なし）:
`scripts/3ds_compare_installed_e2e.py --scene-id scene_ca920fd634b14dfea8215567e930bb7a
--old-sequence 12 --current-sequence 13 --evidence-dir /data1tb/mf-material-compare-final-candidate-retry1-20260906
--candidate-module frontend/three-viewer.js --candidate-app frontend/app.js --steel-fixture`。
candidate response本文だけをCDPで差替え、HTTP認証/CORS headerを保持。試験contextの
local-network-access許可は明示。installed sourceの成功とは扱わない。
app SHA a60678f7dbdea56c32b1f42fdbcdf25038f79f85b18ae8723ebffb5d7930b716、
module SHA ae9fcecc3739d0b728d8ff5280dbee6bf42e4a0724ad94db0b739746305c8848 / 647953 B。

487x406 canvasの固定刃ROI x49.7〜50.5%/y20〜50%で、baseline平均RGBは旧1/1/1、新0/0/0。
候補は旧131.34/133.87/137.18、新2.23/9.82/25.40で、旧銀/新版青黒を実画像でも確認した。
このfixtureの旧銀が黒くない/新版の青が表示される条件をassertし、新旧描画差18437pxを記録。
context復旧はstatus文字列復帰と、上40pxのstatus領域を除いたWebGL画素の差分0をassertした。
初回のPNG全体hash不一致は文字antialias領域(x16〜221/y16〜28)のみであり、描画と文言を別検査する。
閉じた両contextはisContextLost=true、instance/handle0、scene応答不変、page error0。
これはGPU context解放の証拠であり、browser heap/VRAMのbyte単位回収の測定ではない。

既存6軸/zoom/orbit/wheel/fit/320px回帰もcandidateで再実行し成功:
`/data1tb/mf-six-axis-environment-candidate-20260906/observations.json`。
最終比較初回はHost deactivating/restart中でERR_CONNECTION_REFUSED。こちらはrestartを要求していない。
Hostは10:38:41 JST/PID2495560/active、health200へ復帰後に同条件を再実行した。
`./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 106.44秒。構文/hash/diff checkも成功。
最初のfocused testはbundle query prefixを17文字にした誤りを検出し、規約通り16文字へ修正した。

NOT TESTED: 照明修正の正式署名版/overlayなしinstalled受入、材質比較からの新規採用全操作、
新版での画像生成/G8実worker回帰、日英/実mobile touch、長時間credential。installed0.28.19は変更なし。
全体3DS-8/GOAL-06はPARTIAL。次はこのsliceをPR/merge後、署名新版と同じ比較/6軸のinstalled受入。

## 2026-09-06 v0.28.20 source preparation

PR #257 merged `2b527d0`の材質照明/context復旧修正を正式配布するため、addon/core versionを0.28.20へ同期。
初回read-only確認: installed0.28.19/healthy/enabled、Host/local active Job0、active Web session0。
Host PID2499072/MF PID2470070はいずれもactive/running。更新直前に再確認する。
署名公開・導入・overlayなしの比較/6軸受入は未実施。全体3DS-8/GOAL-06はPARTIAL。
版準備gate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 103.75秒。diff check成功。

## 2026-09-06 v0.28.20 signed / installed material comparison — VERIFIED FOR THIS SLICE

PR #258 mergeとtag v0.28.20は `c26f67ddb3b297bd29d9a7a350135b1ac5b8a962`で一致。
exact detached worktreeから既存build_release_bundle.py、PyInstaller6.22.0/Python3.12.3で構築。
artifact31,475,892 B / SHA-256 `88f0cdfab3efc67801fa4f2ca2394e38212492ee3870cc10153285fa711d6373`。
packaged doctorはok/version0.28.20/packaged=true。既存正式publisher keyで署名し通常Releaseへ公開。
公開4 assetを再取得、checksumとHost `_verify_signed_release`成功。manifest279 B/signature89 B/checksum119 B。
公開先 https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.20

更新直前read-only照会でHost/local active Job0、Web session/runtime/model operation全終端。
SQLite online backup `/data1tb/mf-0.28.20-pre-update-20260906.sqlite3`（1,449,984 B/非公開）を保持。
標準registry.updateは10.144秒、0.28.19→0.28.20/healthy/enabled。
MF PID2503646、10:49:09 JST開始。installed core SHA
`1bdb6d40d24efaa5d4627e07b2323489bc3b5f109ec5a84c62c93d190ee3be21`は公開bundleと一致。
Host変更/restart、runtime/モデル更新は要求していない。

Host diagnostic venvで`3ds_compare_installed_e2e.py --scene-id scene_ca920fd634b14dfea8215567e930bb7a
--old-sequence 12 --current-sequence 13 --steel-fixture`を実行。
`--context-side`をold/currentから選べる加法的試験引数にし、両paneを別runで検査した。
evidence-dirは `/data1tb/mf-material-compare-installed-0.28.20-{old,current}-20260906`。
両runともfrontend_mode=installed、overlay/追加接続許可なし。新旧材質差18437px、
刃ROI RGBは旧131.34/133.87/137.18、新2.23/9.82/25.40。textureなし/あり双方で
context復旧後のWebGL描画差0・stats表示復帰、close後両context loss=true、instance/handle0、
scene応答不変、page error0。専用mf-e2e sessionのみ個別失効、password変更なし。

`3ds_viewer_render_installed_e2e.py --scene-id scene_3ac2b7089a3b5cc3b7b1a95ffd96594f
--evidence-dir /data1tb/mf-six-axis-installed-0.28.20-20260906`もoverlayなしで成功。
±XYZ回転差26000/27172/10787/9251/25716/26905px、逆操作差0、zoom46412/43828px、
orbit56220px/wheel41342px、fit/idle差0。320px/scroll319、scene不変/page error0。
通常Chrome/AMD内蔵GPUの実測であり、R9700/software描画や実mobile touchとは記録しない。

exact release worktreeは削除（Gitで再作成可）、build/packaged展開先2 directoryはgio trashへ退避（復元可）。
公開再取得4 asset、browser JSON/PNG、更新前DBは保持。
NOT TESTED: 比較からの新規採用/復元を含む全制作一巡、byte単位memory回収、日英/実mobile touch、
新版画像生成/G8実worker回帰、長時間credential、全release A〜F。GOAL-06/3DS-8はPARTIAL。
受入script変更後のgate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 105.01秒。

## 2026-09-06 採用前材質比較 — 実装不足を確認

`git fetch origin`でmain `a1635c9`（PR #259 merge）を確認し、PR #213 merged `9469d8e`を照合。
`design-3d-assets-and-opencode.md` §4/5の未保存preview→前後比較→採用→revision確定に対し、
`frontend/app.js`のapplySceneMaterialはscenes.material.applyを直接呼ぶ。
`backend/mediaforge/scene_workspace.py`のapply_material_bindingはworking source更新後に
commit_working_copyを呼び、openSceneCompareは確定済みsceneRevisionsだけを対象にする。
この関数経路を`sed`/`rg`で現行コードと照合した。既存frontend contract assertも直接applyを要求する。
したがってGOAL-06は実測未確認だけではなく未実装部分を持つ。3DS-6のexit完了判定を撤回した。
過去の画像適用/確定済み新旧比較/context復旧の実測値は変更しない。

次はprivate workspaceに検証済み未保存候補と明示採用/破棄を加法実装し、既存公開Agent契約を維持する。
owner/base revision/runtime pin、bounded opaque preview、候補回収、採用時の競合/再送条件と
head/版数/旧版bytesの受入条件はcompletion auditへ記載した。
本sliceは文書監査のみ。product/Host/制作データ/installed版は変更なし。
候補prepare/compare/adopt/discard、同経路の実Blender/browser操作はNOT IMPLEMENTED / NOT TESTED。
gate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 105.73秒。diff check成功。
このgreenは既存動作の回帰確認であり、採用前比較の設計適合を証明するものではない。

## 2026-09-06 採用前材質候補 domain — VERIFIED FOR CORE SLICE

基準main `45e8531`（PR #260 merge）、branch `ux1/3d-material-preview-core`。
MaterialPreviewManagerを追加。prepareは正式Asset/SceneRevisionを登録せず、owner/connectionに束縛した
専用candidateを保持する。最大2候補、connectionごと1候補、TTL10分、再送結果込み16件。
runtime参照pin、既存texture/GLB/.blend制限、512KiB chunk、候補/依存hashとbase revision再照合を維持。
adoptのみ既存working commitで独立検査・確定し、結果の再送は版を増やさない。
prepare取消/破棄/期限/接続cleanup/起動時孤立候補除去を実装し、採用開始後のrequest取消はcommit完了を待つ。
既存公開Agent/APIの即時material適用は変更していない。app singleton/WS/HTTP/UIの接続は次slice。

追加9 testで候補時head/Asset不変、owner/connection拒否、byte範囲/個数上限、source/GLB/依存改ざん、
head競合、期限、prepare取消、adopt取消後再送、symlink先を消さないcleanupを検査し成功。
既存scene_workspaceと合わせた初回focused runも成功した（追加取消/symlink test前）。

実機コマンド:
`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_material_preview_core_e2e.py
--data-dir /data1tb/mf-material-preview-core-final-20260906
--legacy-runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9`。
既存legacy runtime4.5.9/実Blender background/autoexec無効を使用し、新規隔離Storeだけにcubeと64x64画像を作成。
prepare0.462270664秒、adopt0.266553368秒、GLB2284B、12triangles/1material/1texture、独立GLB検証成功。
preview SHA `8b4c8306011d4343c3111e35ee207b0e489636883569cddffb5879df575aad53`。
scene `scene_a020ed3846034a479621e6ab401c6e6c`の候補作成/破棄時head・asset不変、採用だけ1→2版、
再送後も2版、元blend bytes不変、採用source hashが候補と一致、candidate directory0をassert。
証拠は同data-dirのobservations.json。初回scriptはPYTHONPATH不足（data作成前）と画像purpose誤り
（候補作成前）で停止した。引数を修正してretry1とfinalの新規隔離dirで成功、既存dirを上書きしていない。

NOT IMPLEMENTED / NOT TESTED: private transport/UI接続、実ブラウザの未保存候補比較・採用、
その署名新版とinstalled受入、生成画像との全制作一巡。GOAL-06/3DS-6/3DS-8は未完了。
Host/installedサービス/利用者制作データは変更していない。
gate `./mf.sh test`: 1013 passed / 既知Starlette warning1件 / 132.16秒。diff check成功。

## 2026-09-06 採用前材質候補 private WebSocket — VERIFIED FOR TRANSPORT SLICE

基準main `c054495`（PR #261 merge）、branch `ux1/3d-material-preview-transport`。
appにsingleton manager/startup/5秒周期expiry/shutdown cleanupを接続し、private WSへ
`scenes.material.preview.prepare/read/adopt/discard`を加法追加。認証ownerとserver生成connection IDで束縛、
厳密field検証、raw Host path拒否、connection1要求の上限を維持する。
候補操作だけ非同期taskで応答し、WS receiveを継続するため、prepare中も切断検知・取消・cleanupできる。
既存Job等の通信処理順序と公開Agent material applyは変更していない。

8 transport test成功: prepare/discard時head不変、採用/再送、別connection拒否、準備中Job照会、
重複要求busy、準備中/ready切断回収、shutdown runtime pin回収、raw path/client connection field拒否。
最初の切断testはTestClient context exitによるASGI task強制cancelがcleanup観測へ先行した。
明示socket.close→実cleanup観測→context exitへ直し、下記の実TCP切断でも確認した。

実行コマンド:
`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_material_preview_transport_e2e.py
--data-dir /data1tb/mf-material-preview-transport-20260906
--legacy-runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9`。
新規隔離Store、ephemeral loopback Uvicorn、実TCP WebSocketと実Blender4.5.9を使用。
認証だけ明示FixtureHostであり、installed Hostまたはそのtoken introspectionの実績とはしない。
2284B GLB受信、prepare/discardでhead不変、別接続adopt拒否、採用だけ2→3版、再送後も3版。
ready時とprepare中の切断cleanup、clockを11分進めた実5秒周期expiryで
runtime references0/candidate directories0、scene head不変をassertした。
証拠 `/data1tb/mf-material-preview-transport-20260906/transport-observations.json`。
source serverは試験終了時に停止。Host/installed service/利用者制作データは変更していない。

NOT IMPLEMENTED / NOT TESTED: standalone mirror、未保存候補のブラウザ比較・採用UI、
installed Host認証経路、署名新版受入。GOAL-06/3DS-6/3DS-8は未完了。
gate `./mf.sh test`: 1021 passed / 既知Starlette warning1件 / 113.45秒。diff check成功。
PR #264作成時にmain `1abc62e`への並行更新を確認。#262 mobile reconnectと#263 version0.28.21を
merge commit `38a87e1`で取り込んで保持した。同じ実TCP/Blender scriptを新規隔離dir
`/data1tb/mf-material-preview-transport-main-20260906`で再実行し、上記全assertion成功。
他者の公開/導入作業をこちらが実施したとは記録しない。installed Host受入は引き続きNOT TESTED。
main取込後gate `./mf.sh test`: 1021 passed / 既知Starlette warning1件 / 126.49秒。diff check成功。

## 2026-09-06 採用前材質候補 UI / standalone mirror — SOURCE ACCEPTANCE

基準main `feaa69e`（PR #264 merge）。branch `ux1/3d-material-preview-ui`。
material UIを直接applyからprepare→現行版/未保存候補比較→明示adopt/discardへ変更。
candidate bytesは専用readで受け、正式Assetとしてopenしない。旧版比較/復元を維持する。
standalone mirrorは同一loopback Originを検証し、候補methodだけを受理する専用WSとして追加。
接続再作成/期限で採用を無効化し、閉じる時は候補破棄、prepare中はsocket closeで取消する。
dropSocketはpendingをrejectし、旧socketの応答待ちを残さない。公開Agent apply契約は変更していない。

実機source server:
`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_material_preview_ui_e2e.py --serve
--data-dir /data1tb/mf-material-preview-ui-final-20260906
--legacy-runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9 --port 9047`。
Host diagnostic venv（Playwrightのみ）の同scriptへ`--url http://127.0.0.1:9047 --data-dir 同上
--evidence-dir /data1tb/mf-material-preview-ui-browser-final-20260906`を渡して成功。
通常headed Chrome/AMD内蔵GPU/実Blender4.5.9の隔離fixtureで、青い現行版/赤い未保存候補を実画像で確認。
prepare/discard時scene応答不変、adoptだけ2→3版、旧版復元で4版・旧blend bytes一致、
socket切断後のadopt disabled、日英文言とstats切替、page error0をassert。
320pxでroot client/scroll320/320、dialog280/280。保存前に未保存表示を確認。

初回browserは復元直後の再比較でtimeout。材質情報がcurrent revisionへ追従するまで操作禁止にして修正。
弱い幅検査(scroll<=320)では実画像に横scrollが残り、測定で背景navがroot client305/scroll319と判明。
比較dialog中の背景scroll lockとclient/scroll等値検査を追加し、再実画像/数値を確認した。
最終status文言修正後は別evidence dirで再実行する。既存生成画像E2E scriptも明示採用操作へ更新。
同修正後の最終実行 `/data1tb/mf-material-preview-ui-browser-final-status-20260906`も成功。
既存fixtureの履歴を残して4→5→6版、全assert/page error0、root320/320・dialog280/280を再確認。
隔離source server9047は停止済み。gate `./mf.sh test`: 1026 passed / 既知warning1件 / 121.80秒。
並行main #265のnonce前接続抑制と#266の0.28.22版更新をmerge `20ebd9b`で取り込み、元変更を保持した。
この版更新・公開・導入作業をこちらが実行したとは記録しない。
main取込後gate `./mf.sh test`: 1026 passed / 既知Starlette warning1件 / 126.61秒。diff check成功。

## 2026-09-06 v0.28.23 source preparation

PR #267 merged `ab8a059`の採用前材質比較/明示採用UIを配布するため、addon/core versionを0.28.23へ同期。
版準備gate `./mf.sh test`: 1026 passed / 既知Starlette warning1件 / 115.98秒。
開始時read-only確認: registry.status installed0.28.22/healthy/enabled、GitHub latest release0.28.22。
新版の署名公開/導入/Host browser受入はNOT TESTED。全体GOAL-06/3DS-6/3DS-8はPARTIAL。

NOT TESTED: installed Host/署名新版、生成画像GPU経路を含む全制作一巡。既存画像のsource fixture受入を
生成画像/installed成功へ読み替えない。GOAL-06/3DS-6/3DS-8はPARTIAL。
Host/installed service/利用者制作データは変更していない。

## 2026-09-06 v0.28.23 signed release / installed acceptance

PR #268 merge/tag target `22fc2b95f051bac3e77f740a76367677bdb0358d`から正式bundle構築・署名公開。
31,490,364 B / SHA-256 `8a6eb22131b8a2ca305af4f2524a070f1c3051622cd14092ebc9cf311023db64`。
公開4 asset再取得checksum/Host署名検証成功。packaged core doctor ok/0.28.23。
launcherはdata-dir環境変数なしでは起動拒否し、core doctorで診断した。
core SHA `6e00a7307fe9850eee997db765643a051ed6e2f59d1cd0d6fd88bd1b4a1f2f41`はinstalled実体と一致。
更新前2回はactive Job検出で中止。その後全Job/session/runtime/model operation終端を確認した。
online DB backup `/data1tb/mf-0.28.23-pre-update-20260906.sqlite3`は1,466,368 B、非公開/保持。
標準registry.update 10.756秒、0.28.22→0.28.23/healthy/enabled。MF PID2645893、11:53:53 JST。
Host PID2642902/11:51:27 JSTは不変。公開再取得 `/data1tb/mf-0.28.23-public-20260906`を保持。

installed candidate E2E scriptを追加。専用mf-e2e新規scene、同ユーザーsession個別revoke、
password変更/overlayなし。最初はPillow不在で起動前失敗し標準libraryのPNGへ変更。
Host英語設定による日本語assert失敗を明示localeで修正。再試験は白い現行cube/赤い未保存候補を
比較・破棄してhead不変、採用1→2まで進んだが旧版比較open待ちでtimeout。
失敗証拠 `/data1tb/mf-material-preview-installed-0.28.23-final-20260906`、診断状態を追加し原因確認中。
既存制作sceneは変更していない。新規試験scene/証拠は残す。
gate `./mf.sh test`: 1026 passed / 既知warning1件 / 111.13秒。
NOT VERIFIED: installed全一巡。NOT TESTED: 生成画像一巡/全release A〜F。GOAL-06/3DS-8はPARTIAL。

診断状態だけ追加した再試験は成功。証拠
`/data1tb/mf-material-preview-installed-0.28.23-diagnostic-20260906/observations.json`。
scene `scene_257528fdd6a540818537d5e93f893870`で比較/破棄head不変、採用1→2、旧版復元2→3、
復元source SHA一致、切断後採用禁止、日英表示、opaque origin null、page error0。
白い現行cube/赤い未保存candidateの日本語比較画面を実画像でも確認した。
実行はHost診断venvの同script、`--blend /data1tb/mf-material-preview-ui-final-20260906/original.blend
--expected-version 0.28.23 --evidence-dir /data1tb/mf-material-preview-installed-0.28.23-diagnostic-20260906`。
ただし直前の旧版比較timeoutは原因未確定。単一成功で解決とせず再現調査を残す。
生成画像一巡/mobile touch/長時間credential/全release A〜FはNOT TESTED、全体はPARTIAL。
exact release worktreeを削除（Gitで再作成可）、build/package展開先をgio trashへ退避（復元可）。
公開再取得・browser証跡・非公開DB backupを保持。PR #269へ受入記録を提出した。

## 2026-09-06 comparison click lost during unchanged refresh

installed0.28.23の比較timeoutを再現。`mf-material-preview-trace-0.28.23-20260906`では
clickが届かずlocked/disabled false、compareReady0/dialog false。別のrefresh-click試験は
scroll中のElement is not attachedを記録。同一sceneのopenSceneがrevision DOMを再生成していた。
sourceではscene ID/name/current revision/locale/revision metadataが不変ならDOMを保持する修正。
実行: core venv/PYTHONPATH=backend:.で`3ds_material_preview_ui_e2e.py --serve
--data-dir /data1tb/mf-material-refresh-ui-20260906 --legacy-runtime-root
/data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9 --port 9047`。
Host診断venvで同scriptのbrowser mode（--url http://127.0.0.1:9047）を実行した。
`/data1tb/mf-material-refresh-browser-20260906`でpointerdown→同一scene refresh→pointerupでも
比較が開く、比較/破棄head不変、採用2→3/復元3→4、旧blend bytes一致、日英/320px、
root320/320/dialog280/280、切断時採用禁止、page error0をassert。
NOT TESTED: 修正の署名新版/installed受入、生成画像一巡。全体3DS-6/3DS-8はPARTIAL。
gate `./mf.sh test`: 1026 passed / 既知Starlette warning1件 / 111.46秒。node構文/diff check成功。
source fixture9047はCtrl-Cで停止/terminal exit0。fixture/証跡は保持。
追加read-only installed検査: `scene_257528fdd6a540818537d5e93f893870`の同一内容refreshで
`button_retained=False, scene_unchanged=True`。差替え自体を確認した。
手動座標pointerのinstalled負例はpointerイベントを記録できず、そのtimeoutを根拠に原因を断定しない。
sourceボタンisConnected assertion追加後の再実行も成功。証拠
`/data1tb/mf-material-refresh-browser-identity-20260906`、既存fixture4→5→6版、全assert成功。
同fixture serverを停止/exit0。過去の全timeout原因を網羅したとはしない。
並行main #270/#271のcanvas補正と0.28.24版更新を保持して取り込み、文書競合は両記録を保持した。
統合後gate `./mf.sh test`: 1030 passed / 既知Starlette warning1件 / 111.71秒。diff check成功。
終了前実registry.statusはinstalled0.28.23/healthy/enabled。公開latest0.28.24の導入を推測しない。

## v0.28.24 — brief が決めた画面へ揃える

16:9 の背景を brief で頼むと毎回 `canvas_mismatch` で失敗していた。受付が
brief を 1024x576 へ解決し、投入時に `snap_to_native` が学習寸法のバケット
1344x768 へ寄せ、検査がその差を見て全候補を破棄していた。比は保たれており
画そのものは正しく描けていたので、寸法の決め方が二か所にあることだけが原因。

バケットで生成し、検査の前に要求どおりの画面へ揃える (`mediaforge/canvas.py`)。
比の端数は中央を残して切る。揃えるのは生成のみで、編集は元画像の画面を使う。

## 2026-09-06 v0.28.26 source preparation

PR #273 merge `7e6462e`の比較ボタン保持修正を配布するためaddon/coreを0.28.26へ同期。
開始時の公開latest0.28.25、実registry.status installed0.28.25/healthy/enabled。
canvas補正を含む並行変更を保持。新版署名/公開/導入/installed受入はNOT TESTED。
版準備gate `./mf.sh test`: 1030 passed / 既知Starlette warning1件 / 110.06秒。
全体3DS-6/3DS-8はPARTIAL。

## 2026-09-06 v0.28.26 signed / installed

PR #274 merge/tag `c262cf23f67a9f17a7bcee3d93f13e36fd7f577d` exact sourceから正式bundle構築・署名公開。
31,491,976 B / SHA `fc1520265de2df36fe7725cf2638d503d47545353828b6487d4ded31ff7f4408`。
公開4 asset再取得checksum/Host publisher verifier/tag target確認成功。packaged doctor ok/0.28.26。
core SHA `ff4d657253a229e36e3375f3e1840492ee97c4ae25f944c484c69d62e464d0da`はinstalled実体と一致。
全Job/session/runtime/model operation終端を確認し、private online DB backup
`/data1tb/mf-0.28.26-pre-update-20260906.sqlite3`（1,712,128 B）を保持。
標準registry.update 10.380秒、0.28.25→0.28.26/healthy/enabled。
MF PID2677797/12:26:16 JST、Host PID2642902/11:51:27 JSTは不変。

既存mf-e2e sceneのread-only refreshでbutton_retained=True/scene_unchanged=Trueを確認。
DOM保持は確認したが、新規fixtureのfull browser E2Eは比較/破棄/採用1→2後の旧版比較openでtimeout。
証拠 `/data1tb/mf-material-preview-installed-0.28.26-20260906`、frameにpointer/clickなし、
locked/disabled false、compareReady0/dialog false。全timeoutを修正済みとしない。
次はHost/iframeのhit targetと座標をread-only検証。生成画像/OpenCode一巡/全release A〜Fは未完了。
exact release worktreeを削除（再作成可）、build/package directoryをgio trashへ退避（復元可）。
公開再取得 `/data1tb/mf-0.28.26-public-20260906`、browser証拠、private backupを保持。

## 2026-09-06 installed comparison native-window acceptance

read-only `scripts/3ds_compare_hit_test.py`で既存sceneの比較ボタンを測定。
emulated1280x900下端中心約y882ではHost IFRAMEがpointer/clickを受信、子frameに届かず比較が開かない。
中心約y834では子frame BUTTONが受信して開く。下端もkeyboard Enterは成功、scene不変。
証拠 `/data1tb/mf-compare-hit-test-{expanded,bottom}-0.28.26-20260906`。
native viewportでは下端もpointerで開きscene不変。証拠`mf-compare-hit-test-native-0.28.26-20260906`。
実inner835/outer945/screen954/DPR1.508333に対し、emulated inner900/outer945/screen900/DPR約1。
この環境のemulation/実window入力領域差を確認。製品/Hostコードは変更しない。

installed E2Eをno_viewport=Trueへ修正し2回成功。最終commandはHost診断venv/PYTHONPATH=Host backendで
`scripts/3ds_material_preview_installed_e2e.py --blend /data1tb/mf-material-preview-ui-final-20260906/original.blend
--expected-version 0.28.26 --refresh-during-click --evidence-dir /data1tb/mf-material-preview-native-final-0.28.26-20260906`。
新scene `scene_a94df57d689d4636844b3586dd9fed7d`で比較/破棄head不変、採用1→2/復元2→3、
source SHA一致、押下中のrefreshでもbutton保持/比較open、切断時採用禁止、日英/opaque origin null/page error0。
最終native viewport1280x835/DPR1.508333。実日本語比較画像も確認。JSで比較を開く代用はしていない。
試験ログインは個別作成/revoke、password不変。生成画像/mobile touch/長時間credential/全A〜Fは未完了。
gate `./mf.sh test`: 1030 passed / 既知Starlette warning1件 / 112.99秒。diff check成功。

## 2026-09-06 installed generated texture candidate adoption

installed0.28.26の実UIから既存専用scene `scene_a94df57d689d4636844b3586dd9fed7d`で画像生成。
Host/local Job全終端を確認して開始。新script `scripts/3ds_generated_material_installed_e2e.py`を
Host診断venv/PYTHONPATH=Host backendで`--scene-id <同ID> --expected-version 0.28.26
--evidence-dir /data1tb/mf-generated-material-installed-0.28.26-20260906`として実行した。
Job `job_cfd0e32824284a59b909bb907ae76a52` succeeded/11.110秒。
FLUX.2 Klein4B、diffusers0.40.0、Apache-2.0、weights hash
`sha256:f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278`。
画像 `asset_bd5a2cabd39a4e12b3682049a1a16946`、1024x1024 RGBA PNG 2,232,149 B、
SHA `51097d8edb6b8babdba9277d31912094e3e901870a1d569d598810ff4b91669b`、validator4件passed。
生成/候補比較/破棄でhead不変。明示採用だけ3→4版、旧3版不変、dependencyとsource provenanceの
parent/reference hashが生成画像に一致。白いcube/青いタイル候補を実画像で確認。
Blender4.5.13/base_color/UVMap/packed=true/external_images0、page error0。

Host DB read-only: Host Job `ffe974bcc230` succeededのresultは同画像Asset。
request `7f668961-e15e-486a-bbc4-9bc68c305182`、lease `2d9d2bec-0c72-4d4e-8593-8ed25b991104`の
activate/renew/releaseは同Job/gpu0でsuccess、終了state=released。
モデル取得/Host変更/service restart/overlayなし。ログインは個別作成/revoke、password不変。
gate `./mf.sh test`: 1030 passed / 既知Starlette warning1件 / 115.64秒。diff check成功。
GOAL-06は既存/生成画像base color比較採用を受入。OpenCode自然言語一巡、全PBR channel、
mobile touch、長時間credential、全release A〜Fはこの実測の範囲外。全体3DS-8/scenario BはPARTIAL。

## 2026-09-06 OpenCode shape / generated texture / project delivery

PR #277 merge `7435db65c9bb28f066e402d8d547319fc8000322`をfetch確認。
branch `ux1/3d-opencode-full-flow`。新script `scripts/3ds_opencode_flow_e2e.py`で
専用project `MF3DS-Acceptance-20260906`を作り、実OpenCode1.18.27から既存Host MCPで制作した。
Host診断venv/PYTHONPATH=Host backendを使用（製品coreにHost importを追加しない）。
per-run configのみ、local gateway/model auto、--pure、組込shell/file/web tool禁止。
global設定・既存project・モデル重み・Host/serviceは変更しない。秘密値はredact、終了時に専用config削除。

実行command: 同scriptへ `--project-name MF3DS-Acceptance-20260906
--evidence-dir /data1tb/mf-opencode-full-flow-20260906`。
同一process PID2714469の終端を確認、exit0 / 289.585秒 / JSON events44件。
scene `scene_f1554d9ba0f741968d9c468206ea3198`、
最終revision `revision_ec5cfa2e2bbf4312a37c770f5510ac75`（1→2版）。
capabilities→typed shape→image.generate→snapshot→material→export→既存G8 ZIP→直前grant→media.pack。
imageとshapeのstatus照会は同一stepで並列だが、材質適用前に双方の成功を確認した。
create `job_3b386c6296f948789c1fd55101a0e2ee`、
image `job_a34045e525514134aaafd55954e4e4e2`、
material `job_f781f67e6fa949c28b345852e0da4b51`、
ZIP `job_864a94c6cee64c74891d833bd757c10d` はevent応答/installed DBの両方でsucceeded。

`python3 scripts/3ds_verify_opencode_flow.py --evidence-dir /data1tb/mf-opencode-full-flow-20260906
--database /data1tb/ControlDeck/data/feature-data/media-forge/data/media-forge.sqlite3` はexit0。
read-onlyで3 receipt/実配置bytes/Asset/provenanceのsize・SHA一致、画像dependency/parent/reference、
ZIP内部manifest→加工GLB/preview hashと元GLB hashを照合。全長1.004999995m、加工後356 triangles。
scene validationは292 triangles、G8 compiler再import/export後の356と混同しない。
scene Blender4.5.13、G8固定compiler4.5.9/1.1.0を維持。FLUX.2 Klein4B/diffusers0.40.0、
画像1024x1024/1,579,657 B、新規weights取得なし。
3 filesは `/data1tb/ControlDeck/CodeDEV/MF3DS-Acceptance-20260906/exports` に保持。
GLB 1,586,792 B SHA `61c23209c7c371a2eda8be10fb2ec62f0edeb515f5cdc534c839f607c8d8f194`、
PNG SHA `a7b836de66df01760889e889ca9062c8024112e7a25ad533ec116e32a2f896c0`、
ZIP 1,602,543 B SHA `2515fa1fe043fe719b69145b5ab0b1e7ac64bcdf6cc4c6fccc23a09cee2693a6`。
receipt committed3/partial=false。manifestは既存ZIP内のまま、別の公開契約は追加しない。

GOAL-05は自然言語→生成画像/材質→exportの範囲、GOAL-08はGLB/画像/manifest入りZIP配置の範囲を受入。
画像のno text/no watermark/seamless条件はprovenanceが未検査警告を出しており成功扱いしない。
同じ剣で既存画像→生成画像の候補比較/採用→GUI手動修正→旧版復元→再配置は未実施。
長時間credential refresh、全release A〜F、全体3DS-8は引き続きPARTIAL。
次はこのsceneを使ってscenario Bの残るUI/GUI/復元を追跡する。別sceneの過去証拠で埋めない。
gate `./mf.sh test`: 1035 passed / 既知Starlette warning1件 / 112.90秒。diff check成功。
追加5テストはverifierのsynthetic fixture/negativeであり、実機受入は上記OpenCodeと実bytes照合。
並行PR #280の0.28.27 mergeを確認したが、この実測は0.28.26由来。新版の受入に読み替えない。
PR #281作成後にmain `301b675`を取り込み、status文書の追記競合は両方を保持して解消。
Host registry再確認は0.28.27/healthy/enabled。更新は並行作業由来で、本sliceから要求していない。
main取り込み後のgate: `./mf.sh test` 1044 passed / 既知warning1件 / 113.11秒。
read-only実成果物verifierも再実行exit0。PR #281の差分は受入script/test/文書のみ。

## v0.28.26 — 生成後も model を載せたまま次の依頼を待つ

続けて画像を頼むと毎回モデルの載せ直し（実測で十数秒）を払っていた。job が
終わった時点で「queue に次が居なければ」worker を畳んでいたためで、対話的に
頼む場面では次の依頼は数秒後に来る。

生成後は lease を持ったまま待つ。返して待つと broker からは「空いている」ことに
なり、その上へ LLM が載って単一 GPU では入らない。ControlDeck の pressure を
短い間隔で見て、GPU を求められた時点で降りる。

## 2026-09-06 same-sword material / Web Blender / restore acceptance

PR #281 merged `27f732b72091d695718bc88c064577ba68a1dcd9`から
branch `ux1/3d-sword-ui-flow`。新script `scripts/3ds_sword_ui_flow_e2e.py`。
OpenCodeで作った同一scene `scene_f1554d9ba0f741968d9c468206ea3198`だけを使用する。
native headed Chrome、実opaque iframe、個別session作成/revoke、password不変。
モデル/runtime取得、Hostコード変更、service restart、frontend overlayは行わない。

最初の実行はHost診断venv/PYTHONPATH=Host backendで同scriptに
`--scene-id <同ID> --existing-image-id asset_bd5a2cabd39a4e12b3682049a1a16946
--expected-version 0.28.27 --evidence-dir /data1tb/mf-sword-ui-flow-0.28.27-20260906`。
既存画像の比較/破棄でhead不変、採用だけ2→3版を確認。
画像Job `job_4f38ad44c01a4c1b8e87060d4caf9692`はwaiting_resource。
Host GET /api/v1/resourcesは200、insufficient_vram、GPU使用19,684,872,192 B、
lease予約0、画像worker PID2734937が残っていた。前のleaseはexpired。
sourceの_lingerへ待機jobを入れたlocal再現でも0.5秒でmonitor終了、worker/execution保持、renew0。
これは常駐monitor早期returnの再現であり、lease handoff全体を検証したものではない。
試験Job取消を通常UI transportで要求した時点では、並行service停止によりすでに
failed/service_stopped（cancel_requested0、04:11:30 UTC）だった。取消成功とは記録しない。
並行PR #282 `b625da4`の0.28.28/常駐既定無効化をfetchして取り込み、registry healthyを確認。
本sliceは常駐機能を変更していない。旧workerも消えたことをpsで確認した。

`--expected-version 0.28.28 --resume-after-existing`と新evidence-dir
`/data1tb/mf-sword-ui-flow-0.28.28-20260906`で同じ第3版から再開。
新Job `job_697a8b218d904f26b546125a3f5f145f`は10.082秒でsucceeded、
生成画像 `asset_db2cf2d984c54c7aaa0cca006be72d8a`、FLUX.2 Klein4B、
weights `sha256:f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278`。
生成・候補比較・破棄でhead不変、採用3→4版。Blender起動後の画面open操作を試験が抜かしtimeout。
同sessionへ再接続する試験はHost接続拒否で終了。その後実HTTP200とunit生存を確認して再接続した。
二つのGUI保存試行は第5/6版を作ったがmesh数が増えず、編集成功のassertionを失敗させた。
失敗JSON/screenshotを削除せず保持。第5/6版を手動形状編集の成功証拠にしない。

最終commandは同scriptに `--expected-version 0.28.28 --resume-gui --resume-gui-revisions 6
--evidence-dir /data1tb/mf-sword-ui-flow-gui-canvas-0.28.28-20260906`（scene/image引数は同じ）。
noVNC canvasをclickして選択A→Shift+D→X/0.02/Enter、RFB入力処理の待機を入れる。
実画像でBlade.001/Camera.001/Guard.001とX=0.02mを確認。mesh4→8、triangles292→584、
revision6→7 `revision_f3407cff162f4487ae2d17a863c5339f`の検査済み保存。
第6版を比較画面から第8版 `revision_7af7f629a4d949ada5ec717ab6ef917c`として復元し、mesh4/292 triangles。
旧全版不変、page errors0、origin null。source asset `asset_dc34497d22874eceac048e0d1ba86734` と
復元asset `asset_328e01e7545441ffa6437f2ec3d7b6dc`の実.blendにsha256sumを実行し両方
`5ca5e3846b1c5731b7b29e86a5cef8577342ea8fc6f72598461e35c22350a94c`で一致。
session `blendersession_a62489b8f3124f8589edc84df4d77dbb`のunitはnot-found/inactive/MainPID0、
同sceneのactive session0。編集/保存/復元まで成功、単一無中断runではない。
scriptは明示resume時に版数/依存を照合し、成功済み画像を生成し直さない。

scenario Bは同一剣の既存画像→新規画像比較採用→GUI入力保存→旧版復元まで確認。
残りは第8版からGLB/ZIPをexportし、現在projectへの新しいgrant/receipt/hashを照合すること。
既存の第2版の配置証拠で埋めない。長時間credential refresh/全A〜F/全体3DS-8は未完了。
gate `./mf.sh test`: 1045 passed / 既知Starlette warning1件 / 121.40秒。diff check成功。

## 2026-09-06 restored sword project delivery / scenario B

PR #283 merged `7aab7b76bb806d66002834cc1e2023342e6084fb`をfetch確認。
branch `ux1/3d-restored-delivery`、installed0.28.28/healthy/enabled。
`scripts/3ds_opencode_flow_e2e.py`へ復元済みUI証拠を入力するmodeを追加。
元project `MF3DS-Acceptance-20260906`の新しい兄弟folder `restored-exports`だけを作り、
既存exports3 filesのhashを前後照合。空folderの明示再試行のみ許容、既存出力の上書き拒否。
Host診断venv/PYTHONPATH=Host backend、global OpenCode設定変更なし、shell/file/web禁止、
per-run credential/configだけを使用して終了時に削除する。Host/source/service/モデル重みの変更なし。

初回 `/data1tb/mf-restored-opencode-delivery-20260906` はexit0/69.772秒だが実tool0/出力0。
Bash風テキストは実行されていない。終了コードだけで成功にしない検査を追加した。
Host /toolsは200/18件、さらに実stdio bridge tools/listの起動前確認を追加。
二回目 `/data1tb/mf-restored-opencode-delivery-retry-20260906` はsnapshot/export後、
過去のrestore Jobをmedia.job.statusで照会し、GLB専用packにPNGも渡す不正入力を反復。
この試験専用OpenCode PID2779544だけをSIGTERM、exit-15/381.689秒、出力0を保持。
直前のgenerateもerror、新しいMediaForge Jobは生成されず、最後に取得したgrantで配置もしていない。
scene.exportは同期Asset参照、asset.job_idは履歴、G8 pack入力はGLB1件という現行契約をpromptへ明示。
APIを変更したり、GLB+PNGを受理するよう契約を緩めたものではない。

最終command: 同scriptへ `--project-name MF3DS-Acceptance-20260906
--restored-ui-evidence /data1tb/mf-sword-ui-flow-gui-canvas-0.28.28-20260906/observations.json
--retry-empty-output --evidence-dir /data1tb/mf-restored-opencode-delivery-contract-20260906`。
実OpenCode PID2803322、exit0/85.660秒、実tool7回。最初の正しいGLB1件packにも
MCP errorが1回あり、**同一入力**の再試行でsucceeded。原因は未確定で、無失敗runとは記録しない。
ZIP Job `job_b432af302151415892994939f200f78b`、Asset `asset_78fc671a945049c7b9cc32de0eba6151`。
scene `scene_f1554d9ba0f741968d9c468206ea3198`、
第8版 `revision_7af7f629a4d949ada5ec717ab6ef917c`のGLBと採用画像だけを配置した。
grant `grant:ade4a058-22d9-495b-928b-9a9bdfbc95fc`、receipt committed3/partial=false。
GLB 1,847,240 B SHA `2dfb5a862bf1c30b9b88d3cf8c57bea8ab4aa71baa1076eae2ce64831d9c7b64`、
PNG 1,824,647 B SHA `924ba671a052d1b91baaebab5af43a411c1654fcea66a54c46f20ab73a877ed7`、
ZIP 1,863,588 B SHA `7aa49cce50d088934134497f3c7156e0a904cabbcf0192de794160be9e14ef76`。

`python3 scripts/3ds_verify_restored_delivery.py`へ同evidence-dir、installed DB、
`--ui-evidence <上記UI observations.json>`を渡しexit0/verified=true。
read-onlyでUI復元ID→snapshot/export→Asset→receipt→実配置bytes→ZIP内部manifestを照合。
DBの全8 revisionはUI試験終端と一致、旧exports3 filesもhash不変。加工後356 triangles、4 meshes、texture1。
UI証拠をメモリ上でwrong revision/wrong image/missing historyにした3 negativeはすべて拒否。
同一入力で後続成功したpack errorだけを回復扱いにし、先行成功・別入力・未回復errorは拒否する4 testsを追加。

scenario Bは同一剣の形状/寸法/予算→既存画像→新規画像比較採用→実GUI編集→復元→再配置まで受入。
途中の失敗・再開・再試行を含む証拠であり、一回の無中断実行ではない。
全体3DS-8、A/C/D/E/F、長時間credential、GOAL-01/03/07/09/10の残件は維持。
次はGOAL-01の共通Library絞込と親子双方向移動を実画面で確認する。
gate `./mf.sh test`: 1049 passed / 既知Starlette warning1件 / 113.12秒。diff check成功。
