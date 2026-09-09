# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 2026-09-10 v0.28.55 signed/installed and real-CDN repair

準備PR #405 merge/tag aa940cd4e569c19216cee37bb03f8c99cf8ccf18、ux1/release-0-28-55-acceptance、記録PR作成前。
exact release checkout/build/audit/sign/public4files再取得/実Host署名検証/標準updateまで実施。
31,537,666B/SHA f6b4c31dd30e459b61face3b63772f2c71a6de697bdd60ea17e3310cbe5c716a。
build/publicは /data1tb/mf-0.28.55-{build,public}-20260910、audit抽出package-k44om2jl。
全idle/backup/再照合後update10.698秒healthy、DB全table/registry不変、backup mf-0.28.55-update-4i5zx261。
Host1141433保持、MF1152101。標準保持で.53実行bundleだけ整理/.54保持、user通知済み。
installed inactive4.5.9のcacheだけ退避して正規repair、実CDN転送/実probe/同版公開58.081秒/exit0。
証跡 mf-repair-download-installed-0.28.55-20260910、operation4335ed440ad847d98aa16ec90dd42348。
47scenes/162revisions/旧版関連64hash保持、既定4.5.13不変、旧exe inode45649239へ同SHA修復。
health download70samples p95 .967ms/max1.072ms。registry/Host/MF PID不変、cache backup保持。
準備gate1384 tests/165.44秒/build/Node5。記録sliceは文書のみ。全D/3DS/GA PARTIAL。
次はDの容量不足/改ざん/中断残件とmetadata I/Oを照合して進める。
NOT TESTED: 今回browser/installed重複取消/Web pack実download/物理ENOSPC/全setup off-loop。

## 2026-09-10 v0.28.55 preparation

base PR #404 merge96b7d0e13d4292497629dc124b1accb7d0c1914e、ux1/release-0-28-55、PR作成前。
addon/core0.28.55、release-v0.28.55.md追加。全1384 tests/165.44秒/2既存warnings、build差分0/Node5成功。
署名公開/導入は準備commit時点で未実施。次はnormal merge→exact checkout build/audit/sign/public再取得。
installed0.28.54/MF1116213/Host1141433を確認。別image.editは自然成功/worker回収後、新Job queuedあり。
更新前に全Job/GUI/runtime操作idleを再検査。Host/PCは再起動しない。
外部診断 /data1tb/mf-0.28.55-{audit,install,repair-download}.py を準備したが実行前。
旧cacheを退避して実CDN repairを確認する計画。旧scene/history保持・失敗時cache回復を検証し、
installed重複取消そのものの証拠へは拡大しない。全D/3DS/GA PARTIAL。

## 2026-09-10 download write isolation

base PR #403 mergec39c606f839b9c991b389d46f59e8bf3474f02b8、ux1/3d-download-write-isolation、PR作成前。
前turnは削除確認再起動受入/mergeまで進捗。D中断経路調査でchunk書込/progress/fsyncの同期処理を発見。
新規2 REDでloop thread実行を確認し、owned thread/反復shieldへ変更。symlink/非regular/size変更も拒否。
追加10ケース（thread identity、1/3回取消、partial置換negative）成功、既存manager回帰も成功。
scripts/3ds_download_io_e2e.py、証跡 /data1tb/mf-download-io-source-20260910[-r2]。
実archive/実disk/実TCP health、通信・slow-writeはfixture。初回0.958秒/exit0、-r2 0.993秒passed。
health5.686ms、3回取消→1MiB保持→Range再開→377,929,956B/SHA一致、partial回収。
専用dataだけ変更、元archive保持。download-only operationはcanceled、install成功とはしない。
独立DB/hash照合でもcanceled/bytes_done=377929956/partial0。全1384 tests/145.75秒/2既存warnings、build/Node5成功。
製品修正は未配布。次は署名release準備/公開/installed受入、続いてD失敗matrixへ戻る。
NOT TESTED: installed/実CDN/物理ENOSPC/全setup off-loop/全D/3DS/GA。全体PARTIAL。

## 2026-09-10 removal confirmation core restart

base PR #402 merge2aa28ac26e6da9629eae457d0e433fa411b7aba5、ux1/3d-removal-confirmation-restart、PR作成前。
前turnはJob逆順受入/mergeまで進捗。今回は確認済み削除のHTTP client再接続/別coreプロセス再起動。
script scripts/3ds_removal_restart_e2e.py --evidence-dir /data1tb/mf-removal-restart-source-20260910。
実測23.113秒/親exit0、core1134091→SIGTERM(-15)→新core1134111→同ID/preview/ackで削除再開。
最初だけpreflight gate fixture、再起動後は未変更core。固定隔離rootだけ/Host・installed変更なし。
6hash/scene/revision保持、同版再導入probe成功/元既定復元、両PID/staging回収を独立確認。
unitは確認5条件×journal3状態、10ケース追加/対象17ケース成功。deleting状態はrename crashの模擬ではない。
全1374 tests/2既存warnings/148.10秒、viewer build差分0/Node5、py_compile/diff成功。
製品code/公開契約/版数/署名artifact変更なし。全D/3DS/GA PARTIAL。
次: Dの容量不足/改ざん/導入中断について既存証拠とinstalledとの差分をまとめて検証する。
NOT TESTED: installed browser、電源断/mid-rename crash、GUI再編集、例外時自動再導入。

## 2026-09-10 removal-first recipe Job admission

base PR #401 merge731f52fc40969240998e6a42bdf4350a71ffedd2、ux1/3d-removal-first-job、PR作成前。
前turnはGUI逆順実機受入/mergeまで進捗。本sliceは同実削除commit中のscene.edit Job受付。
script --history-reinstall --hold-removal --hold-removal-job。Job domain/scene/runtimeは実体、Hostだけuncalled fixture。
証跡 /data1tb/mf-removal-first-job-source-20260910、25.762秒/exit0、health1.637ms/setup_required。
旧版削除guard中Job取得thread/pending→削除後runtime_unavailable、Host0/新Job0/refs0。
同版再導入/同scene再起動/停止、6hash/旧revision保持、元既定復元、2units回収/staging空を独立確認。
unit空Job期待の誤りをbaseline一致へ修正後、対象/recipe-pin22ケース成功。製品bug修正ではない。
全1364 tests/2既存warnings/160.27秒、viewer build差分0/Node5、py_compile/diff成功。
製品/Host/installed/公開契約/版数/署名artifact変更なし。全D/3DS/GA PARTIAL。
次: durable削除確認の中断/core再起動保持を実処理で検証する。
再開はmain/PR/statusを照合し、test_blender_history_removal.pyと削除operation journalを読む。
NOT TESTED: installed Agent/OpenCode、create retry/material逆順、自然遅延、GUI入力、例外時自動再導入。

## 2026-09-10 removal-first GUI admission

base PR #400 merge9b0f3323bb3a4bdf363ba20e56278cf348dfac96、ux1/3d-removal-first-admission、PR作成前。
前turnは意図確認のみ/no progress。現行mainとPR #213設計を再確認して逆順受入を追加。
scripts/3ds_runtime_removal_e2e.py --history-reinstall --hold-removal とunit 2ケース。
実remove guard内で最大15秒のthread gate、GUI受付thread到達→pending/health応答→削除commit後422。
証跡 /data1tb/mf-removal-first-source-20260910-r2、25.340秒/exit0、health1.581ms/setup_required。
固定隔離rootだけで4.5.9を削除/同版再導入、同scene再起動/停止、6files hash・旧版保持。
既定4.5.9復元/2runtime登録、active GUI0、staging/removing空、専用2units回収を独立照合。
製品code/Host/installed/版数/署名配布の変更なし。全D/3DS/GAはPARTIAL、GA-4/5も維持。
gate: 全1363 tests/2既存warnings/146.80秒、対象9ケース再実行、viewer build差分0/Node5、py_compile/diff成功。
次: Job受付が削除より後の場合を実削除commitと組み合わせて確認する。
再開: status/main/PRを照合後、同scriptとscene_recipe_jobsのruntime受付を読む。
NOT TESTED: installed逆順、自然遅延、Job逆順、例外時自動再導入、GUI入力。

## 2026-09-10 installed Job admission removal protection

base PR #399 merge86fb8bec08a206620f306cb5d8a11cd40e360a87、ux1/3d-installed-job-removal。
前turnは.54署名導入/回帰/mergeまで進捗。今回は実Host Job参照による削除再拒否の文書受入。
ephemeral /data1tb/mf-job-removal-0.28.54.py、既存Host診断venv/環境。
初回idle gateでexit1、別image.edit実Job/worker1120012をread-only追跡し自然成功後に再実行。
login/変更前の拒否。成功証跡 /data1tb/mf-job-removal-installed-0.28.54-20260910、7.261秒/exit0。
全idle→旧版4.5.9へ一時switch→新規専用64sphere Job受付→既定4.5.13復元。
inactive旧版live3（in-process2/recipe1）でstale/fresh確認をremove_changed/in_use拒否。
job_486ad88e1663442b81b71f50dbfd8bec/Host7b29f60793ddは正規取消で双方canceled、live0。
新sceneなし/取消Jobのasset_ids空、全旧scene/revision投影/registry bytes/旧exe hash・inode保持、独立72files hash一致。
一時login revoke、service tokenは60秒/actor16でメモリのみ。MF1116213/core1116217/Host667000不変。
文書のみ、既存1361 tests/build/Node5を参照。実行中Blender PID自体は未採取、生成完走ではない。
全D/3DS/GA PARTIAL。次は削除が先に始まる逆順受付の実機証拠を照合する。

## 2026-09-10 v0.28.54 signed and installed

準備PR #398 merge8b5bb0375e09bae1523275e4e8f3dfb89244a460/tag v0.28.54をexact checkout。
既存bundle-build環境とbuild_release_bundle.pyでbuild、外部mf-0.28.54-audit.py監査/doctor成功。
31,535,647 B/SHA310c7b8a037780faef25e94c65ff156b766ad0cb56b88266a317bb5132ef6c33。
build/verification /data1tb/mf-0.28.54-build-20260910、package-nh4o5lhq。
既存publisher鍵で署名公開、公開4files再取得はmf-0.28.54-public-20260910。
Host診断venv/既存CONFIG/PYTHONPATHでmf-0.28.54-install.py実行、実署名/bytes一致、
全idle/backup/再検査→標準update10.052秒healthy、DB全table/registry bytes不変。
backup /data1tb/mf-0.28.54-update-tz3fdb8w、Host667000不変、MF1116213。
標準規則で.52実行bundleのみ整理、.53/.54保持。公開releaseで復元可能と通知済み。
準備全1361 tests/139.39秒/build/Node5成功。本記録sliceは文書のみ。
全3DS/GA PARTIAL。installed重複取消自体とJob/削除の全競合はまだ未検証。
installed回帰はmf-stale-removal-after-ack-0.28.54.pyで実施、証跡同名installed-20260910。
同意済みpreview後GUI開始→stale/fresh live削除拒否、実opaque RFB描画、49.978秒passed/
58.057秒login revoke/exit0。旧scene14版/28hash/runtime hash・inode/registry保持。
独立3 scenes/current pin/72files保持、GUI0、session1bcc8c9ab5bb41949dcbef31e924a111 unit不在。
MF1116213/Host667000不変。これをinstalled重複取消の証拠へ読み替えない。
次はJob受付/削除競合の未検証条件を補完する。

## 2026-09-10 v0.28.54 release preparation

base PR #397 mergef48f5db04f88627612ca8672df4d9d25a4e75d37、ux1/3d-release-0-28-54。
前turnは重複取消参照漏れ修正/実受入/mergeまで進捗。addon/core版を0.28.54へ揃えた。
docs/release-v0.28.54.md追加、API/DB/runtime版変更なし。本修正はまだ未配布。
次は準備PRの通常merge exact commitからbundle build/監査/署名/公開再取得、
idle/SQLite backup/再確認後に標準update・installed受入。全3DS/GA PARTIAL。
全1361 tests/2 warnings/139.39秒/exit0、viewer build差分なし、Node5/diff check成功。
ephemeral /data1tb/mf-0.28.54-{audit,install}.py準備/py_compile済み、本処理は未実行。
auditはPYZの_finish_cleanup/呼出/取得解放を追加検査。installは旧.53/idle/backup/再検査必須。
installed.53/MF1082083/Host667000不変、未終端Job/GUI/setup0を確認。導入前には再確認する。

## 2026-09-10 repeated admission cancellation cleanup

base PR #396 merge2a0d80dc4580a25567260088e76e71980741ac32、ux1/3d-admission-repeat-cancel。
前turnはinstalled GUI/stale削除拒否/mergeまで進捗。Job参照調査で重複取消のleakを発見。
取得thread待ちへ2/3回取消でlive1が残る2ケースRED→owned cleanup task/反復shieldで修正。
Host受付失敗・制作finallyのcloseにも適用し、3回取消中もthread終端まで追跡する2 tests追加。
同期取得/解放はto_threadのまま、cleanup例外は伝播。公開契約/DB/版数変更なし。
実source診断は既存3ds_recipe_runtime_pin_e2e.pyへ取得遅延/3回取消を追加。
証跡 /data1tb/mf-repeated-admission-cancel-source-20260910、1.037秒/exit0。
取消でHost未呼出/live0、その後実Blender4.5.9 cube成功/GLB1756B/終端live0、旧exe hash不変。
Host/遅延はfixture、Blender/検証processは実物。installedの同条件受入ではない。
次は全gate/merge後に署名release準備・installed受入。全D/3DS/GA PARTIAL。
全1361 tests/2 warnings/152.33秒/exit0、viewer build差分なし、Node5/py_compile/diff check成功。
最終診断-r2は0.660秒/exit0、参照回収後の実Blender制作/GLB同hash成功。
MF1082083/Host667000は不変。未配布、旧untracked .venvは保持。

## 2026-09-10 installed stale removal confirmation

base PR #395 mergeb871ccd54476070bbf786af23bb13af734de662e、ux1/3d-installed-removal-stale。
前turnはinstalled probe失敗保護/mergeまで進捗。今回はpreview後のGUI受付で削除を再拒否する受入。
製品変更なし。ephemeral /data1tb/mf-stale-removal-0.28.53.py、既存Host診断venv/環境。
Settings preview/live0/project2→GUI ready→履歴確認/実buttonでstale fingerprint拒否。
fresh live previewでもack=trueの正規API要求をin_use拒否、operation一覧不変。
実4.5.9 opaque RFB描画/scene14版とsource/GLB28hash・exe hash/inode・registry bytes保持。
証跡 /data1tb/mf-stale-removal-installed-0.28.53-20260910、45.558秒passed/53.657秒revoke/exit0。
個別GUI/loginのみfinally回収。削除/再導入/サービス再起動なし。
同意checkboxを先にcheckしてからGUI開始する逆順も別診断で完走。
/data1tb/mf-stale-removal-after-ack-0.28.53.py、証跡mf-stale-removal-after-ack-installed-0.28.53-20260910。
13.661秒stale拒否/13.796秒fresh live拒否、49.653秒passed/57.742秒revoke/exit0。
両session9f952c14cb1e44ddbfaae3ffb906095b/e5e210baff234081af28503f1c42bb5c終端/unit不在。
独立照合で前PRの3 scenes/17 revisions/72files保持、GUI0、MF1082083/Host667000不変。
文書のみ。製品gateはPR #394の1357 tests/build/Node5を参照、今回再実行ではない。
全D/3DS/GA PARTIAL。Job受付・削除実行中の並行受付等は残る。次はJob側の参照保護と既存実機証拠を照合。

## 2026-09-10 installed exact probe failure

base PR #394 merge667906adeb24403551541ea625bb486ef2392f8f、ux1/3d-installed-probe-failure。
前turnはsource故障注入/実受入/mergeまで進捗。今回はinstalled同故障の受入記録のみ。
実core1082090（MF main1082083）のexe/UID/親とpackaged probe SHAを確認。
開始時Job/GUI/setup全終端、旧managed4.5.9はuser:16の専用2 scenesのみ参照。
ephemeral /data1tb/mf-probe-failure-0.28.53.py、既存Host診断環境で実行。
証跡 /data1tb/mf-probe-failure-installed-0.28.53-20260910。
inactive4.5.9だけ一時削除→4.5.13 GUI→旧版exact install候補だけpidfd SIGTERM→retry。
個別login revoke/専用GUI stop/旧版不在なら同版restoreのfinallyあり。
旧→新版updateや自然発生故障とは区別する。製品コード/版数変更なし。
installed実行exit0: 4.5.13 GUI描画→候補PID1100108/親1082090だけSIGTERM、57.264秒failed。
同GUI/runner1099805を保持、retry旧版4.5.9実probe成功、121.385秒passed/126.387秒own stop。
一時login revoke、page errors0。旧3 scenes/17 revisions/72files hash保持を独立確認。
独立検査初回はfield名の誤りKeyError、修正後read-only再照合成功（製品障害ではない）。
session3658ca124e6943e98db06d7a04da0dafのunit不在、GUI0/staging0/候補PID不在。
旧版を同固定archiveから復元、active4.5.13/外部投影不変、MF1082083/Host667000不変。
文書のみ。前PR製品gate1357 tests/154.35秒/build/Node5を参照、今回再実行ではない。
全D/3DS/GA PARTIAL。次は確認付き削除とJob/GUI同時受付の不足する競合条件を実機照合する。

## 2026-09-10 owned candidate probe failure

base PR #393 mergeedf0a53f4357148de22f0bf9d847f0fa677e983f、ux1/3d-owned-probe-failure。
前turnはinstalled並行導入受入/mergeまで進捗。production変更なし、acceptance診断を追加。
scripts/blender_probe_fault.py: operation IDのcandidate executable・全argv・UID・親PIDを照合し、
pidfd再照合後にそのプロセスだけSIGTERM。thread内/stop event/timeout/descriptor回収、9 tests。
scripts/3ds_update_probe_failure_e2e.py --terminate-candidate-probeは固定隔離rootのみ。
初期GUI/setup0と候補参照0を検査しBを除去、A GUI開始、新B実probeをterminate、retry。
実行はPYTHONPATH=.:backend .venv/bin/python、証跡 /data1tb/mf-owned-probe-failure-source-20260910。
23.639秒候補PID1089251/親1089031へSIGTERM、B update failed、A4.5.9 GUI/旧bytes保持。
45.351秒retry4.5.13 ready/active切替でも同A GUIは4.5.9、明示stop後既定4.5.9へ戻す。
45.922秒passed/exit0。未変更の実preflight、RFB handshakeのみで画素/編集までは未実施。
元scene保持、以前のsource baselineの6 asset/provenance+旧exe計7 hash一致、staging空。
session658e29ad6f734dce87d487601b85ef05終端/unit not-found/inactive/MainPID0、候補PID不在。
隔離rootは両版を保持しactive4.5.9。installed.53/MF1082083/Host667000は不変。
新modeのfinallyは例外時も自分のGUIだけ正規HTTP停止。停止失敗自体の注入はNOT TESTED。
次はinstalled候補への適用に必要な親process/stage所有権をread-only確認する。
全D/3DS/GA PARTIAL、自然発生/installedでの同故障の証拠には読み替えない。

再開時の前test handleは不在/pytest processなし。全gateを再実行し1357 passed/2 warnings/
154.35秒/exit0。viewer build差分なし、Node animation5 tests/py_compile/diff check成功。
最終identity照合後にもstopを検査する順序へ調整。旧untracked .venvは保持する。
最終コード実機-r2: /data1tb/mf-owned-probe-failure-source-20260910-r2、46.297秒/exit0。
候補1097947/親1097665へのSIGTERM→probe失敗、45.746秒retry readyでも旧GUI4.5.9固定。
同版復元/GUI stop/既定4.5.9、旧7hash/元revision保持、staging0/候補PID不在を独立確認。
session d74c7b3a4fa34e35b59223ce657ef4b3のunit不在、MF1082083/Host667000不変。

## 2026-09-10 installed parallel exact-runtime install

base PR #392 merge43e8f45925947d19767ad3481c8e7c8ff3dcb799、branch ux1/3d-installed-parallel-runtime。
前turnは署名.53導入/受入まで進捗。今回はA=4.5.13 GUI中のB=4.5.9 exact installを確認。
初回Jobs0検査でexit1、ログイン/削除前。連続image.editの実Job/workerをread-only追跡し、
他Jobを止めず自然終了後に別証跡-r2で実行。ephemeral /data1tb/mf-parallel-runtime-0.28.53.py。
Host診断venv/既存CONFIG/PYTHONPATH/DISPLAY/XAUTHORITY、一時mf-e2e loginのみfinally revoke。
専用2sceneのみ参照するinactive Bを英語Remove button/履歴確認で削除し、同固定archiveから戻した。
AはMF3DS OpenCode motion acceptanceのscene_509b6ee0b688492997b86b535d70ec9a、user:16。
18.405秒B削除→30.780秒A実RFB ready→B verifying/ready中に同A runtime/session/runner PID1087038。
実B archive6,510members/展開1,168,332,002 B/実probe4.5.9、64.845秒ready観測。
80.889秒passed、85.896秒専用GUI停止、exit0/page errors0。
証跡 /data1tb/mf-parallel-runtime-installed-0.28.53-20260910-r2。
3 scenes/17 revisions/72files hash保持、A executable hash/inode不変、active4.5.13/legacy投影維持。
session040096fdea9a492aaf1acea6a290a768、unit not-found/inactive/MainPID0、GUI0。
installed.53/MF1082083/Host667000不変、B再導入済み。約1.17GBの旧実行環境だけ一時削除と通知済み。
文書のみ。準備全1348 tests/145.63秒/buildを参照、今回の再実行ではない。
この逆方向exact installを旧→新版updateやB probe失敗に読み替えない。手編集/保存も未実施。
次は並行導入の失敗条件を隔離fixtureで補完しinstalledとの差を記録する。
全D/3DS/GAはPARTIAL、容量/改ざん/中断/同時受付等の残件を維持。.venvはそのまま保持。

## 2026-09-10 v0.28.53 signed and installed

準備PR #391は通常merge330e0b0b6543e4ef2507b46775dd1f86e0849de5。
exact checkout /data1tb/ControlDeckMediaForge-release-0.28.53/tag v0.28.53。
既存build_release_bundle.py/PyInstaller6.22.0/Python3.12.3でbundle生成・監査、
既存publisher鍵で署名・公開、公開4files再取得と実Host署名検証を確認。
artifact31,573,646 B/SHAe8a22e13602634510f549b19f890074ae28d2bf68bf73e64cedfccefde1dbd80。
/data1tb/mf-0.28.53-build-20260910/verification.json、public-20260910に証跡。
auditは新repair guard/参照/shield/threadを含む。packaged doctor:ok/.53/packaged=true。
Host診断venvで/data1tb/mf-0.28.53-install.pyを実行、全idle→backup→再確認→標準update。
10.240秒/healthy、DB全table fingerprint/Blender登録bytes不変、Host667000不変/MF1082083。
backup /data1tb/mf-0.28.53-update-vvnnqdet。保持規則で.51実行bundleのみ整理、.52/.53保持。
制作物/runtime削除なし、旧bundleは公開releaseで復元可能と通知済み。
準備全1348 tests/145.63秒、Node5/viewer build成功。本記録sliceは文書のみ。
全3DS/GAはPARTIAL、未検証の条件を完成扱いしない。

installed保護は/data1tb/mf-repair-protection-0.28.53.pyをHost診断venvで実行。
既存CONFIG/PYTHONPATH/DISPLAY=:0/XAUTHORITYを利用、一時mf-e2e loginのみfinally revoke。
opaque frame/Origin:null/overlayなし、同専用acceptance-sword第14版、4.5.9実RFB描画確認後、
正規workspace APIで同版repair。73.721秒でin_use拒否、同GUI ready/scene/旧assets/registry保持。
runtime executable SHA/inode不変。86.912秒stop/86.973秒revoke/exit0/page errors0。
証跡 /data1tb/mf-repair-protection-installed-0.28.53-20260910。
session c77efb16b51d42849a5d324fac238535、unit not-found/inactive/MainPID0。
Host667000/MF1082083不変。PNGはGUI描画のみ、編集保存やSettings文言受入ではない。
稼働中拒否のinstalled不足のみ補完。停止後正常repairのinstalled、別版並行導入/probe失敗は残る。
次はDの別版並行導入/失敗の安全なfixtureと実行境界を確認する。

## 2026-09-10 v0.28.53 release preparation

baseはPR #390 merge9d0f67ad06838a379641d5fd3899a647596255df。
前turnは修復保護実装/実機受入/mergeまで進捗。ux1/3d-release-0-28-53で
addon/coreを0.28.53へ揃え、docs/release-v0.28.53.mdを追加。
API/DB/runtime版変更なし。source修復拒否→停止後修復成功の証拠は前節を維持する。
開始時installed0.28.52、Jobs0/GUI0。リリース準備段階では導入環境へ未適用。
次は準備PRの通常merge exact commitからbundle build/監査/署名/public再取得、
idle/SQLite backup/再確認後に標準updateし、installed修復保護を確認する。
ephemeral監査/導入script /data1tb/mf-0.28.53-{audit,install}.pyは前版からapply_patchで準備。
auditは埋込み_publish_repairのguard/参照検査と_installのshield/to_threadも検査する。
installはJobs/GUIに加えsetup operationも全終端を要求する。まだ両script未実行。
全`./mf.sh test`: 1348 passed/既知warnings2/145.63秒/exit0、viewer build生成差分なし、
Node animation5 tests/diff check成功。
全3DS/GAはPARTIALで維持。.venvは既存untracked symlinkを保持。

## 2026-09-10 repair live-runtime protection

branch ux1/3d-repair-live-protection、base PR #389 merge3471b5950ab2dbd73ab65bc623f2237ec03eb684。
前turnは実再編集/mergeまで進捗。installed別Job稼働中のためruntime変更を避けて調査し、
修復candidate公開のlive参照再検査/受付排他の欠落を発見。late in-process/durable参照2件RED。
backendの修復公開だけworker threadへ移し、既存removal_guard内で参照/cancel再検査、
rename/registry/rollback/cleanup/readyを追跡。shutdown取消は開始済み公開threadを待つ。
active/履歴pinだけでは拒否しない。既存修復/rollbackと新規3 tests、関連54 tests PASS。
新scripts/3ds_repair_live_e2e.pyは既存隔離clean-setup rootだけを使用し、初期idleを検査。
PYTHONPATH=.:backend .venv/bin/python scripts/3ds_repair_live_e2e.py
--evidence-dir /data1tb/mf-repair-live-source-20260910、25.053秒/exit0。
実Blender4.5.9 GUI ready中に同版repair、実archive/展開/probe後にin_useで拒否。
旧8files hash/scene保持、GUI継続ready→明示stop。session758af0dbfdf341c5824afeb4655083d5、
unit not-found/inactive/MainPID0。source healthはsetup_requiredであってhealthyではない。
実RFB手入力は未実施。詳しいID/hash境界はimplementation-status同日repair節。
installed0.28.52/MF1054020/Host667000は不変。本修正は未配布。
診断へ停止後の正常repairも追加しmf-repair-live-source-20260910-r2で再実行、46.009秒/exit0。
稼働中拒否→24.120秒stop→同版repair ready、実展開1,168,332,002 B/GLTF import/export true。
directory inode変更で実差替えを確認、既存8files hash/scene保持。旧専用runtimeは通常cleanupで整理、
同固定archiveから再構築可能。session e1198bffb0304189be931c1b37f313e9。
全`./mf.sh test`: 1348 passed/既知warnings2/143.93秒/exit0、viewer build生成差分なし、
診断py_compile/diff check成功。製品版数はまだ0.28.52のまま。
次は署名release準備とinstalled受入。A稼働中B導入/probe失敗等のD残件は保持。
全3DS/GA PARTIAL、完成/blockedにはしない。.venvは既存untracked symlinkのまま保持。

## 2026-09-10 installed reinstalled-runtime browser edit

branch ux1/3d-reinstalled-browser-edit、baseはPR #388 merge
fc171f864d8638318a84e96cb10ae9097dd12708。前応答は説明のみ、今回実機受入を前進。
installed0.28.52/MF1054020/Host667000、開始時Jobs0/GUI0を確認。
詳しいコマンド・受入境界はimplementation-statusの同日same-scene RFB節。
/data1tb/mf-reinstalled-edit-0.28.52.pyをHost診断venv/既存CONFIG/PYTHONPATH/DISPLAYで実行。
固定user:16/scene_ca920fd634b14dfea8215567e930bb7a/base第13版/全旧版4.5.9 pinを検査。
再導入後の同sceneで正規API起動→実opaque RFB描画→canvas click/A/Shift+D/Escape→通常保存。
4.5.9固定、mesh4→8/triangles236→472、実GLB mesh nodes4→8、第14版へ確定。
66.978秒passed、67.040秒login revoke、exit0/page errors0。password/global設定変更なし。
証跡 /data1tb/mf-reinstalled-edit-installed-0.28.52-20260910。
第14版revision_1479631eb20e4909a4ae975e71fa2cbf、GLBasset_c889d0b198f84dea82ae3db6c7388eb1、
1,761,820 B/SHAf132b3e074dfa4cf0282218839784ac683101f9fb90366fc9674300a612348e2。
PNGの複製見た目は未確認。構造変化とGUI描画の証拠を混同しない。
前削除baselineの14旧版/60files hash保持、別Recovery scene不変。新第14版は保持。
session c78a1982e18f483a96bd11f1a7e28d05 stopped、unit not-found/inactive/MainPID0、GUI0。
サービス再起動・runtime変更・外部Blender変更なし。製品code/版数変更なし。
同版再導入後のRFB編集の不足のみ補完、全D/3DS/GA PARTIAL。
次はA稼働中B実導入/probe失敗の安全な対象/故障注入境界を確認する。
英語本削除、同時受付競合、改ざん/容量不足/中断等はNOT TESTED。
GUI終端後の全`./mf.sh test`: 1345 passed/既知warnings2/142.07秒。
viewer build成功/生成差分なし、Node animation5 tests/diff check成功。文書のみで版数変更なし。

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
[原因別証拠表](3ds-lifecycle-evidence.md)にscenario Cの全項目を分離した。
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
branch `ux1/release-0.28.32`。mobile runtime touch targetのCSS修正を配布する版数更新。
公開契約/DB/runtime変更なし。新releaseの署名公開/標準更新/installed positiveは未実施。
次は版数PRを通常mergeしexact mergeからbundle構築、署名公開/再取得検証/標準更新を行う。
再開するinstalled受入は `3ds_settings_protection_installed_e2e.py --expected-version 0.28.32
--require-readable-layout --require-touch-targets --probe-geometry --locale <ja|en>`。
全体3DS-8と入力不達原因は未完了を維持する。
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

PR #297 merge `01986b2a36feeecfa114429264fbcf089026732f`を確認。
branch `ux1/release-0.28.31`でaddon/core版を同期。公開latestは0.28.30。
差分はmobile Settings行/狭いheaderのCSSと受入script/文書。公開契約/DB schema/Blender runtime変更なし。
source日英320/1280と旧installed negativeは直下の記録。新releaseの署名公開・標準更新・installed成功は未検証。
次は版数PRを通常mergeし、exact mergeからbundleを構築/正式署名公開する。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1054 passed / 既知warning1 / 113.04秒。diff check成功。

## 2026-09-06 mobile Settings layout — source verified / installed pending

PR #296 merge `f9ca26f48882bd8e58568320aa25847ee3f2b9e5`を確認。
branch `ux1/3d-settings-mobile-rows`。767px以下でruntime行を1列にし、controlsを説明の下へ配置。
buttonsはmin-height44px/折返し可。420px以下のheaderもflex-wrapを許容し、縦scrollbarのある
320pxで設定buttonが右へ押し出される別原因を修正。機能/公開契約/Host変更なし。

隔離dataのsource9161/PID78593で新`3ds_settings_layout_source_e2e.py`を実行。
before `/data1tb/mf-settings-layout-before-20260906`: 英語320/text0/root305/319で失敗。
rowだけ修正したafterもtext255.663になったがroot305/319で失敗。headed Chromeでheaderの
nav-settings右端307.106>client305を観測し、header折返しを追加。
after2 `/data1tb/mf-settings-layout-after2-20260906`: exit0、日英320ともroot305/305、text255.663、
controlsが説明の下、row client280/scroll280。日英1280はroot1265/1265、desktop横並びを維持。
runtime state前後一致、page errors0。localeはsource document設定でありHost locale eventの証拠ではない。
撮影を目視確認。sourceはSIGINT/exit0で停止。

installed scriptへ`--require-readable-layout`を追加。旧0.28.30で実行した
`/data1tb/mf-settings-layout-installed-negative-0.28.30-20260906`はtext0/root305/319で期待どおり失敗。
個別login revoke/overlayなし/削除送信なし。新しいflagで未修正版を検出できた。
修正版の署名配布/installed成功はNOT TESTED。次は通常merge後に版数更新/正式署名配布し、同flagを再実行。
全体3DS-8はPARTIAL。稼働版は変更していない。
gate `./mf.sh test`: 1054 passed / 既知warning1 / 119.47秒。diff check成功。

## 2026-09-06 installed Settings project-reference protection / mobile defect

PR #295 merge `c98f12ea3c9e6b32a5f17456aa8c800411806fcd`を確認。
branch `ux1/3d-installed-settings-protection`。新`3ds_settings_protection_installed_e2e.py`は
installed0.28.30/実Host opaque iframe/専用mf-e2e個別loginでSettings削除previewのみ操作。
Host診断Python、CONTROL_DECK_CONFIG=Host config/PYTHONPATH=Host backend、
`--expected-version 0.28.30 --evidence-dir /data1tb/mf-settings-protection-layout-installed-0.28.30-20260906`。
初回`mf-settings-protection-installed-0.28.30-20260906`と寸法追記runの双方exit0。
desktop viewport1280/320の双方で4.5.9はproject参照2、4.5.13は23。
非active4.5.9もproject_referenceでcan_remove=false、active4.5.13はactive_runtimeも併記。
確認button hidden/戻るbutton visible、runtime status/operation journal前後一致、page errors0。
削除送信/新規導入/scene変更なし。個別login revoke/password不変。Host PID2196/MF PID31432 active不変。

320 screenshot目視で設定行の英語が縦に崩れ、横scrollを発見。
寸法runはiframe inner320/root client305/scroll319、非active行width280.981/text0/controls247.666。
CSS `#blender-runtime-list .row`のminmax(0,1fr) autoと横方向controlsでtext列が0まで縮む。
削除保護の受入とlayout不良を分離する。320px設定全体を合格にはしない。
次はこの証拠PRを通常mergeし、別sliceでmobile runtime行を縦積みにしてsource/installedで再検証する。
今回script/文書のみ、製品変更なし。全体3DS-8/GOAL-03/scenario DはPARTIAL。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 112.49秒。diff check成功。

## 2026-09-06 Settings lifecycle — source browser scope verified

PR #294 merge `e07c56e11430c31c00a7621c3e9658a513449488`を確認。
branch `ux1/3d-setup-settings-ui`、製品/Host/TTL変更なし。新2 scriptで前回の隔離dataを使用。
source起動は`MEDIA_FORGE_DATA_DIR=/data1tb/mf-long-setup-source-20260906
MEDIA_FORGE_BLENDER_LEGACY_ROOT=/data1tb/mf-long-setup-source-20260906/absent-legacy
PYTHONPATH=backend:. .venv/bin/python -m uvicorn mediaforge.app:app --host 127.0.0.1 --port 9161`。
PID68057、偽downloadなし。診断Python/Playwrightから日本語Settingsの実ボタンを操作した。

`3ds_setup_settings_ui_e2e.py --evidence-dir /data1tb/mf-setup-settings-ui2-20260906`: exit0/57.062秒。
最初のrun `mf-setup-settings-ui-20260906`はactive削除時のbuttonをdisabledと仮定して失敗。
実装はhidden＋handlerのcan_remove guardで保護していたため、製品でなくassertionを訂正。
4.5.9/4.5.13両方のactive削除拒否を確認。実外部downloadの固定4.5.13 updateは54.993秒でready。
378,033,952 B、SHA `da4e69b06b75b9e642d106496c50e7e240218b411d2f6e18271c1d1d819cef91`一致。
6512 member/1,167,187,839 B展開、Blender4.5.13/Python3.11.15/background/glTF入出力probe成功。
live/project参照0の隔離4.5.9だけをpreview/confirmで削除、1,168,332,155 B回収、active4.5.13不変。

続けて`3ds_setup_repair_ui_e2e.py --evidence-dir /data1tb/mf-setup-repair-ui-20260906`: exit0/43.132秒。
画面から4.5.9を再導入し21.721秒でready。その隔離版の.runtime.jsonだけをevidenceへrenameして保持し、
再読込でdamaged/repairボタンを確認。repair操作は43.047秒でready、実4.5.9/glTF probe成功。
stamp再作成、active4.5.13不変、page errors0。元stampはoriginal-runtime-stamp.jsonとして保持。
repaired screenshotを目視確認。DB全6 operation終端（5 ready/1 canceled）、staging空。
source PID68057はSIGINT/exit0で終了。Host PID2196/MF PID31432 activeで不変。
隔離runtime2版/cache/元stampを保持。製品差分なしで新規release不要。
完全空環境のbrowser install、installed opaque iframe、live/project参照削除拒否、全scenario Dは未完了。
次は通常PR merge後、installed設定画面での非破壊確認と未検証条件の受入を進める。全体3DS-8はPARTIAL。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 114.25秒。diff check成功。

## 2026-09-06 long setup acceptance — source scope verified

PR #293 merge `ba4432b80bca225005d562089ad9984028a3c86f`を確認。
branch `ux1/3d-long-setup-acceptance`。製品/Host/TTL変更なし。
BlenderRuntimeManagerはHostIdentity/Host clientを保持せず、durable operation IDで動く。
setupはHost child Jobではなく、開始/状態取得/取消の各入口と転送継続を分けて受入する必要がある。
新`3ds_long_setup_source_e2e.py`は固定4.5.9実archive377,929,956 Bをmanifestのsize/SHAで確認し、
隔離source Uvicornの実loopback HTTPからinstall/状態/health/取消/再installを操作する。
archive配信のみhttpx fixtureで64KiB/秒に制御。Blender展開・検証・probeは実物を使う。
これは実Host credential更新、外部回線download、設定browser UIの受入ではない。

実行: `PYTHONPATH=backend:. .venv/bin/python scripts/3ds_long_setup_source_e2e.py
--data-dir /data1tb/mf-long-setup-source-20260906
--archive /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9/downloads/blender-4.5.9-linux-x64.tar.xz`。
PID62708/tool session67258、operation `blenderop_5c6383c803304ba8acfb76f728e2c521`。
60.249秒でdownloading/3,866,624 B、HTTP health成功。Host PID2196/MF PID31432 activeで不変。
同runはexit0で終端。631.247秒/41,156,608 Bで取消を確認し、652.011秒に再導入ready。
再導入operation `blenderop_cdb9c83c1c914c78ae28ea6bd923a08c`。
実archive SHA `dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d`を再照合し一致。
6510 member/1,168,332,002 B展開、実Blender4.5.9/Python3.11.11/background/gltf export/import成功。
read-only DBで2 operationがcanceled/ready、staging空、partialなし、PID62708消失を確認。
Host PID2196/MF PID31432はactiveで不変。隔離runtimeとarchiveは後続受入用に保持。
証拠 `/data1tb/mf-long-setup-source-20260906/observations.json`。
PR #294に結果文書を追記。今回追加は文書のみ、unit再実行なし/diff check成功。
次は通常merge後、設定画面からのsetup lifecycleを実ブラウザで確認する。
全体3DS-8/Scenario EはPARTIAL。実Host credential/外部回線/browserの受入へ読み替えない。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 110.22秒。script含む差分はcommit/pushして保持する。

## 2026-09-06 RFB credential renewal — existing installed path verified

branch `ux1/3d-rfb-credential-renewal`、baseはPR #292 merge `56c9e40`。
利用者のloopback認証不要の指摘を受け、Host main `97aba42`をread-onlyで確認。
`security/localhost.py`はkernel peer loopbackとX-Requested-With:ControlDeckを要求する。
現在の呼出元はLLM gateway（key不要）とagent MCP（署名/owner確認を維持し期限だけ許容）の2経路。
addon-runtime introspect/RFB proxyには適用されず、service tokenの期限を引き続き検証する。
遠隔browser由来でもHost→MFはloopbackになるので、ここでowner/権限を省略しない。

PR #293は最初に期限前1012を追加したが、実機証拠で不要と判明し製品変更/対応unit test/設計変更を撤回。
Hostは8分ごとにbridge nonceを更新し、MFの既存session.updated handlerはnonce更新だけでなく
開いているRFBを再接続していた。署名installed0.28.30/overlayなしでこれを検証した。
新`3ds_rfb_renewal_installed_e2e.py`をHost診断Pythonで実行、専用mf-e2e/個別login revoke/password不変。
証拠 `/data1tb/mf-rfb-renewal-negative-0.28.30-20260906/observations.json`。
directory名は当初negativeを予想した名だが、結果はexit0/672.072秒のpositive。
session `blendersession_5ff146d2416c4b00a7e460becf1bac37`で、接続後480.340秒にRFB instance2本目を観測。
660.433秒まで同一session/connected、実GUIでmesh複製して671.862秒に保存成功。1→2 meshes、
32256 triangles/16132 vertices、GLB独立検査passed/2,179,304 B。
scene `scene_b2f21eddc2c548cc8cb7865d32e9a1bc`のrevision1→2、旧版レコード不変。
旧blend/GLBの実SHAも前回CPU試験値と一致。新GLB SHA `232b1916491b012a57422ebfdd1d487babccfdc698392481b22cf489a3452ed2`。
Host PID2196/MF PID31432はactiveで不変。試験sessionはstopped/unit inactive/MainPID0。page errors0。
候補source診断は並行Xvnc display99競合で2回startup failure（2回目で理由を取得）。lockを削除せず候補は終了、
未公開診断scriptは不要な製品変更と一緒に撤回した。隔離data `mf-rfb-renewal-source{,2}-20260906`は保持。
新規release不要。PR #293をscript/受入文書だけに変更。`./mf.sh test`: 1053 passed / warning1 / 112.01秒。
全体3DS-8/Scenario EはPARTIAL。setup自身の10分超credential、自然な長時間演算/GPU組合せは未検証。
次はPR #293を通常merge後、setup長時間credentialの現実装/受入範囲を確認する。

## 2026-09-06 installed CPU child credential refresh — verified scope

PR #291 merge `f513927b3bb11ad53395862fec55a8534de96eb0`を確認。
branch `ux1/3d-credential-refresh-0.28.30`。製品/Host/script/TTL/worker timeout変更なし。
既存 `scripts/3ds_credential_refresh_e2e.py --expected-version 0.28.30
--evidence-dir /data1tb/mf-credential-refresh-installed-0.28.30-20260906`をHost診断Python、
PYTHONPATH=Host backend/CONTROL_DECK_CONFIG=installed configで実行。PID33983、exit0、644.700秒。
dedicated mf-e2eのCPU scene recipe6件。4つの正確な子processだけをpidfdで各160秒SIGSTOP/SIGCONTし、
後続2件を元の600秒TTLより長く待機させる既存fault injection。既存user Job/service/GPUは停止しない。

482.542秒までに後続success child `2ef6f7e7dedb`のrefresh監査successを観測。
cancel child `c33bfd0fdb62`もrefresh成功後、615.630秒に取消/host_terminal_sent=true。
644.700秒で全6件終端、local/Host DBとも5 succeeded/1 canceled、全件host_terminal_sent=true。
後半4 childでrefresh success各1、先行2件は更新不要の時間内に成功してrefresh0。
MF PID31432/Host PID2196は前後不変/active。非終端local Job0、停止した4 PIDは/procから消失。
Blender4.5.13、各成功sceneは16128 triangles/8066 vertices、独立GLB構造検査passed。
実10 asset bytesのsize/SHA-256とmetadata/provenance.output_sha256、親ID一致をread-onlyでassert。
最終scene `scene_b2f21eddc2c548cc8cb7865d32e9a1bc`、revision `revision_103e9176714c4d0bbc88c1404f954b13`。
最終GLB `asset_992db7c350bf44d1996c19c08ac3dfe0`は1,138,216 B、
SHA `b468c73ca925889e3c55b5b48658526e00bbca2f0d7e3047f4eef0ea2475261b`。専用5 scene/10 assetsは証拠として保持。

これは600秒を跨ぐ実child credential更新・待機・取消・終端同期の受入であり、自然な長時間演算や
OpenCode自然言語制作、GUI/setup自身のrefreshの証拠にはしない。全体scenario E/3DS-8はPARTIAL。
次は10分超GUI/sessionの正規認証更新を検証する。試験時Host/MFのrestart/updateを並行しない。
今回差分は実測文書のみ。unit test再実行なし、diff check成功。既存source gate1053件成功を維持。

## 2026-09-06 v0.28.30 signed / installed viewer scroll acceptance

PR #290 merge/tag `bdaa379d682feedbea476fc037772b6dae095b9c`からexact bundle構築・正式署名公開。
31,500,089 B、SHA `dfa398205c0706bd4b02409db8e4681546588ee4231850240f932f1f9b9b11a6`。
公開4 asset再取得/checksum/Host trusted publisher verifier/tag一致、packaged doctor ok/0.28.30。
private DB backup `/data1tb/mf-0.28.30-pre-update-20260906.sqlite3`は2,007,040 B。
全制作Job/session/setup終端確認後、標準registry.update 10.500秒で0.28.29→0.28.30/healthy/enabled。
MF PID31432/15:12:39 JST、Host PID2196不変。installed/bundle core SHAはともに
`9f2c65b96588215249462dff3759102ba01bb064aab5413155b2d1c56a8e776d`。

branch `ux1/3d-viewer-0.28.30-acceptance`。Host診断Python/PYTHONPATH=Host backendで
`scripts/3ds_library_navigation_installed_e2e.py --scene-id scene_a94df57d689d4636844b3586dd9fed7d
--expected-version 0.28.30 --require-scroll-lock
--evidence-dir /data1tb/mf-viewer-scroll-installed-0.28.30-20260906`を実行、exit0。
overlayなし、既存専用scene、login個別revoke/password不変。320px root client320/scroll320/hidden、
viewer320/320、close後scroll復帰。旧0.28.29 negative305/319/visibleと同じassertionで修正を確認。
4nav/Settings復帰、画像/GLB/.blend filter、親子双方向、明示GLB実表示、scene不変、page errors0を維持。
実screenshotで横scroll消失を目視確認。公開再取得/build/package/exact worktree/backupは保持。
source code gateは1053 passed / 既知warning1 / 112.29秒。今回追加は実測文書のみ、diff check成功。
次は600秒TTLを跨ぐchild credential refreshの専用CPU queue試験を、service更新と並行せず再実行する。
自然な長時間制作、GUI/setupのrefresh、全A/C/D/E/Fは未完了。統合3D Studio全体はPARTIAL。

## 2026-09-06 Release 0.28.30 preparation

PR #289 merge `5b7fa617d909c649e4d43d5eafd56564e8c77651`を確認。
branch `ux1/release-0.28.30`でaddon/core版数を同期する。公開latestは0.28.29。
viewer背景scroll修正のsource受入とinstalled旧版negativeは直下の記録。
新しい版の署名公開・標準更新・installed受入はNOT TESTED。次は版数PRを通常mergeする。
全体3DS-8はPARTIAL、元の必須GOAL/A〜Fを縮小しない。
gate `./mf.sh test`: 1053 passed / 既知warning1 / 112.29秒。diff check成功。

## 2026-09-06 full-screen viewer background scroll

PR #288 merge `073158b`を確認。branch `ux1/3d-viewer-modal-scroll`。
installed0.28.29の320pxでroot client305/scroll319を再現。viewerは100vwだが、背景rootの
縦scrollbarが残る。既存比較dialogと同じ`html:has(#viewer[open]) { overflow: hidden; }`を追加し、
GLB/画像共通のfull-screen modalを開く間だけ背景scrollを停止する。閉じた後はCSS条件が外れて戻る。
公開契約/asset/scene/Hostコード/稼働版は変更していない。

source coreを既存隔離data `/data1tb/mf-library-lineage-source-20260906`で9159へ起動。
`scripts/library_lineage_ui_e2e.py`にGLB/画像双方のlayoutとclose後scroll復帰を追加した。
修正前はoverflow=visibleで失敗（小fixtureではroot320/320で横overflow自体は出ない）。
修正後run `/data1tb/mf-viewer-scroll-after-20260906`はexit0、GLB/画像とも320/320/hidden、
close後visible、scene不変、日英filter/親子移動を維持、page errors0。撮影を目視確認。
source PID17963はSIGINTで正常終了し、終端exit0を確認。

installed scriptへ`--require-scroll-lock`を追加。既存専用scene/0.28.29で同flagを実行した
`/data1tb/mf-viewer-scroll-installed-negative-0.28.29-20260906`はroot305/319/visibleで期待どおり失敗。
overlayなし、login個別revoke、scene書込なし。修正版の署名配布/installed成功はNOT TESTED。
次は修正PRを通常mergeし、署名新版へ反映して同じflagをinstalledで成功させる。
gate `./mf.sh test`: 1053 passed / 既知Starlette warning1 / 115.62秒。diff check成功。

## 2026-09-06 Release 0.28.29 preparation

### Signed release / installed acceptance

版数PR #287 merge/tag `a906cff03a67ce9ae9f325b62a775589659f1186`。
exact worktree `/data1tb/ControlDeckMediaForge-release-0.28.29`から既存build_release_bundle.py、
PyInstaller6.22.0/Python3.12.3で31,500,563 Bのbundleを構築し正式publisher keyで署名公開。
SHA `20e247de72c90f6997eab2889aab7c4450eb7346688c4d58ce7d292d6d1edef8`。
公開4 assetを`/data1tb/mf-0.28.29-public-20260906`へ再取得、checksum/Host publisher verifier/tag一致。
packaged doctor ok/0.28.29。private DB backup `/data1tb/mf-0.28.29-pre-update-20260906.sqlite3`
2,007,040 Bを保持。利用者の再開指示後、全制作Job/session/setup終端を確認して標準registry.update。
10.166秒で0.28.28→0.28.29/healthy/enabled。MF PID13607、Host PID2196は不変。
installed core SHA `c47a0d0c51e304fd6bb5838b815cb333c56936e652baa460abe3033579538d29`はbundleと一致。

branch `ux1/3d-release-0.28.29-evidence`、新script `scripts/3ds_library_navigation_installed_e2e.py`。
Host診断Python/PYTHONPATH=Host backend、既存専用mf-e2e scene、個別login作成/revoke、password不変。
`--scene-id scene_a94df57d689d4636844b3586dd9fed7d --expected-version 0.28.29
--evidence-dir /data1tb/mf-library-navigation-installed-0.28.29-20260906`でexit0。
overlayなしの実opaque iframeで1280/320pxの4nav/設定復帰、画像/GLB/.blend filter、
画像↔source↔GLB、明示GLB表示、scene不変、metadata移動中model read0、page error0。
撮影した320px viewerには横scrollが見えるため全mobile layout合格とはしない。寸法観測を追加中。
次はこのviewer横scrollの発生要素を確認する。日英切替/Host履歴/relationsの60件超pagingと
全体3DS-8 A/C/D/E/F・長時間credentialはNOT TESTEDのまま。
exact worktree/build/package展開物は調査用に保持。稼働実体へsourceをoverlayしていない。
寸法追加runもexit0。`/data1tb/mf-library-navigation-installed-0.28.29-layout-20260906`に
inner320/root client305/scroll319、viewer client320/scroll320を記録。viewer内部ではなく背景rootのoverflow。
gate `./mf.sh test`: 1052 passed / 既知warning1 / 113.38秒、diff check成功。

PR #285 navigation `ae9ed17`、PR #286 Library `05e556f`の通常mergeを確認。
branch `ux1/release-0.28.29`でaddon/core版数を同期する。稼働版は0.28.28のまま。
前段の実source受入/1052 testsは直下の記録。正式署名bundle公開とinstalled受入は次の段階で、
まだ成功とは記録しない。旧DB/scene/runtimeを保持し、標準Host updateだけを使う。
`./mf.sh test`: 1052 passed / 既知warning1 / 117.71秒。diff check成功。
利用者の新依頼「ControlDeck Blender Skills実行連携」を優先し、版数準備branchを保存してここで中断。
0.28.29のPR/merge/tag/build/署名公開/導入は未実施。installed0.28.28を変更していない。

再開時の実測: PC bootは2026-09-06 14:40:53、Host PID2196/active。
MediaForgeはcurrent=versions/0.28.28、unit disabled/inactive、Host feature enabled=false。
意図した無効化の可能性を保持し、再有効化の可否を利用者へ確認中。版数PRはサービス変更なしで進める。
再起動直前の追加testは利用者の再起動指示で634 passed時点にSIGINT/exit2、中断を成功とは数えない。
次は版数PRを通常mergeし、そのexact commitから署名bundleを構築する。
再起動後gate `./mf.sh test`: 1052 passed / 既知Starlette warning1 / 115.55秒、exit0。

## 2026-09-06 Web Blender primary navigation

直後の追加依頼「下部の作る・ライブラリ・状況の並びにWeb Blender」を
別worktree `/data1tb/ControlDeckMediaForge-webnav` / branch `ux1/web-blender-navigation`で実装。
先行Library作業の未commit差分は`ControlDeckMediaForge-3ds4`に保持し、本sliceに混ぜない。
4番目のnav、専用`/web-blender` view、現在地表示、Settingsからの復帰、
既存3D切替からの接続、last_view保存を追加。移動ではGUI起動しない。
source standalone serverをport0で起動し、実port44891に対し
Host診断Pythonで `scripts/web_blender_navigation_e2e.py --url http://127.0.0.1:44891
--evidence-dir /data1tb/mf-webnav-final-20260906` を実行、exit0。
1280/320pxの4入口往復、Settings復帰、3D切替、直接URLでscene表示、page errors0。
320px下部4ボタンは各80x60px、同じy=840。JSON/screenshotsを同directoryに保持。
installed Host iframeでの戻る/進む、GUI編集、公開release/更新はこのsliceではNOT TESTED。
稼働版の更新・Host変更・ユーザーシーン操作なし。全体3DS-8は未完了のまま。
最終gate `./mf.sh test`: 1047 passed / 3 skipped (build runtime不在の署名tests) /
既知warning1 / 110.12秒。diff check成功。試験専用server PID2851228終了。

## 2026-09-06 Common Library formats and lineage

追加slice `ux1/3d-library-lineage`でGOAL-01の.blend掲載、GLB/Blender filter、
private metadata relations(60件paging)、親子リンク、詳細から明示previewを補完。
source受入用data `/data1tb/mf-library-lineage-source-20260906`、実Blender4.5.9の2 revisionを保持。
browser script `scripts/library_lineage_ui_e2e.py`、失敗/成功の詳細はimplementation-status冒頭。
Web Blender nav PR #285はmerge `ae9ed17`。本branchへ取込済み、文書競合は両entry保持。
Libraryのinstalled受入と署名release反映はまだNOT TESTED。全体3DS-8は未完了。
headed runは全filter/双方向リンク/詳細からGLB実表示までexit0。
`./mf.sh test`: 1051 passed / 既知warning1 / 130.00秒。diff check成功。
統合後gateは1052 passed / 既知warning1 / 113.64秒。
source再起動後にLibraryとWeb Blender navの実browser受入も再成功。
evidenceは`mf-library-lineage-browser-restarted-20260906` / `mf-library-webnav-integrated-20260906`。
source server終了。installed exe/cwdは実測0.28.28、PID2744941 active。
次はこのLibrary sliceを通常PR merge後、正式署名release/updateでnav/Libraryをinstalled受入する。

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

## 2026-09-06 installed generated texture comparison/adoption

PR #276 merged `33d05e72f6d8685f9196a4961ad02ae515f8190e`をfetch確認。
branch `ux1/3d-generated-material-acceptance`。installed0.28.26/healthy/enabled、開始時Host/local Job全終端。
`scripts/3ds_generated_material_installed_e2e.py`を追加。既存専用mf-e2e sceneを使用し、
native headed Chrome/opaque iframeの画像生成→結果選択→候補比較/破棄→再比較/採用を操作する。
モデル導入/重み取得/service restart/Host変更/overlayなし。ログインは個別作成/revoke、password不変。

実行: Host診断venv/PYTHONPATH=Host backendで同scriptに
`--scene-id scene_a94df57d689d4636844b3586dd9fed7d --expected-version 0.28.26
--evidence-dir /data1tb/mf-generated-material-installed-0.28.26-20260906`。
Job `job_cfd0e32824284a59b909bb907ae76a52`は11.110秒でsucceeded。
FLUX.2 Klein4B/distilled、diffusers0.40.0、Apache-2.0、weights
`sha256:f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278`をprovenanceで確認。
画像Asset `asset_bd5a2cabd39a4e12b3682049a1a16946`、1024x1024 RGBA PNG 2,232,149 B、
SHA `51097d8edb6b8babdba9277d31912094e3e901870a1d569d598810ff4b91669b`、画像validator4件passed。
白い現在版と青いタイル候補の比較画面を実画像でも確認。生成/比較/破棄ではhead不変、採用で3→4版。
新revision dependencyとsource provenanceのparent/reference hashが生成画像と一致し、旧3版は不変。
Blender4.5.13、base_color/UVMap、packed=true、external_images0、scene validation、page error0。

Host DB read-only照合: Host Job `ffe974bcc230` succeededのresult.asset_idsは同画像Asset。
resource request `7f668961-e15e-486a-bbc4-9bc68c305182`とlease
`2d9d2bec-0c72-4d4e-8593-8ed25b991104`のactivate/renew/releaseは同Host Job/gpu0、すべてsuccess。
lease終了state=releasedを確認。他サービスの停止を試験が要求したものではない。
gate `./mf.sh test`: 1030 passed / 既知Starlette warning1件 / 115.64秒。diff check成功。

GOAL-06は既存/生成画像のbase color比較採用の範囲を受入済み。全体3DS-8とscenario Bは未完了。
次はOpenCodeで剣の形状→生成画像→材質→export→grant/receiptを同一制作物で追跡する。
今回のUI試験を自然言語OpenCode、全PBR channel、mobile touch、長時間credentialの証拠にしない。

## 2026-09-06 native-window comparison acceptance

PR #275 merged `0a5596346973bfbc61e4acedd7e06345598b5425`をfetch確認。
branch `ux1/3d-comparison-input-hit-test`。製品/Hostは変更せず、read-only診断script
`scripts/3ds_compare_hit_test.py`で既存試験sceneのボタン座標とHost/iframeのpointer受信を測定。
emulated1280x900では下端button中心約y882のpointer/clickをHostのIFRAME要素が受信し、
子frameは受信せず比較も開かない。一方中心約y834ではframeのBUTTONが受信し開く。
同じ下端buttonはkeyboard Enterでも開き、scenes.get前後一致。重なりやJS lockとは異なる。
証拠 `/data1tb/mf-compare-hit-test-{expanded,bottom}-0.28.26-20260906`。

headed Chromeのviewport emulationを外したnative windowでは下端pointerもframeに届き比較が開く。
`/data1tb/mf-compare-hit-test-native-0.28.26-20260906`の実innerHeight835/outerHeight945、
screen954、DPR1.508333。emulatedではinner900/outer945/screen900/DPR約1だった。
この環境のviewport emulationと実windowの入力領域差として扱い、一般的な全Chrome不具合とは断定しない。
installed E2Eをno_viewport=True/実window基準へ修正。UIコードoverlayやJSによる比較open代行はしない。

`3ds_material_preview_installed_e2e.py --expected-version 0.28.26 --refresh-during-click`
（Host診断venv、PYTHONPATH=Host backend、既存original.blend、新規evidence-dir）を2回成功。
最終証拠 `/data1tb/mf-material-preview-native-final-0.28.26-20260906`。
scene `scene_a94df57d689d4636844b3586dd9fed7d`、採用前/破棄head不変、採用1→2/復元2→3、
復元source SHA一致、pointerdown→同一scene refresh→pointerupでbutton保持/比較open、
切断後採用禁止、日英表示、opaque origin null、page error0。最終native1280x835/DPR1.508333。
日本語比較画面を実画像でも確認。初期window寸法と最終値は両方JSONへ記録する。
過去のtimeoutは削除せず、今回の試験環境修正と成功証跡を併記する。
次は生成画像→候補比較→採用のinstalled経路と、OpenCode/配置receiptを同一制作物で通す。
生成画像/mobile touch/長時間credential/全release A〜Fは未完了。全体3DS-6/3DS-8はPARTIAL。
gate `./mf.sh test`: 1030 passed / 既知Starlette warning1件 / 112.99秒。diff check成功。

## 2026-09-06 v0.28.26 signed / installed, comparison timeout remains

PR #274 merge/tag target `c262cf23f67a9f17a7bcee3d93f13e36fd7f577d`からexact bundle構築・正式署名公開。
31,491,976 B、SHA `fc1520265de2df36fe7725cf2638d503d47545353828b6487d4ded31ff7f4408`。
公開4 asset再取得/checksum/Host publisher verifier/tag target成功。packaged doctor ok/0.28.26。
core SHA `ff4d657253a229e36e3375f3e1840492ee97c4ae25f944c484c69d62e464d0da`はinstalled実体と一致。
全Job/session/runtime/model operation終端を確認し、private online DB backup
`/data1tb/mf-0.28.26-pre-update-20260906.sqlite3`（1,712,128 B）を保持。
標準registry.update 10.380秒、0.28.25→0.28.26/healthy/enabled。
MF PID2677797/12:26:16 JST、Host PID2642902/11:51:27 JSTは不変。Host restart要求なし。

既存専用mf-e2e scene `scene_257528fdd6a540818537d5e93f893870`でread-only DOM identityを再検査。
openScene→比較button参照保持→同一scene再取得後のbutton.isConnected=True、scenes.get前後一致=True。
0.28.23のFalse/Trueに対しDOM保持修正の導入は確認できた。試験ログインは個別作成/revoke、password不変。
一方、`3ds_material_preview_installed_e2e.py --expected-version 0.28.26`の新規scene
`scene_fceb3d1ae9b24f3da38cfb9ec879cdbd`は比較/破棄/採用1→2後、旧版比較openで再びtimeout。
証拠 `/data1tb/mf-material-preview-installed-0.28.26-20260906`。pointer/clickがframeへ届かず、
locked/disabled false、compareReady0/dialog false。DOM保持だけで全timeoutが解消したとはしない。
次は旧版比較ボタンの実座標とHost/iframe側のhit targetを観測し、入力が届かない経路を特定する。
直接JS呼出で比較を開いて操作成功の代用にしない。既存sceneを読み取り専用で使い試験資産の増加を避ける。

exact release worktreeを削除（Gitで再作成可）、build/package作業directoryをgio trashへ退避（復元可）。
公開再取得 `/data1tb/mf-0.28.26-public-20260906`、browser証拠、private backupは保持。
新版full browser flowはFAILED、生成画像/OpenCode一巡/全release A〜Fは未完了。全体3DS-6/3DS-8はPARTIAL。

## 2026-09-06 v0.28.26 source preparation

PR #273 merged `7e6462e551db430052ae471d7782cb5b4094ee89`。公開latestと実installedは
0.28.25/healthy/enabledを確認。branch `ux1/3d-material-v02826`でaddon/coreを0.28.26へ同期する。
比較ボタンを不変refreshで保持する修正を配布するための版準備。canvas補正を含む並行変更は保持。
新しい版の署名/公開/導入/installed受入はNOT TESTED。全体3DS-6/3DS-8はPARTIAL。
版準備gate `./mf.sh test`: 1030 passed / 既知Starlette warning1件 / 110.06秒。

## 2026-09-06 revision comparison refresh race

PR #269 merged `daf9df6fd909a4ae7edf6daf3f7d92c6e2015951`をfetch確認。
branch `ux1/3d-material-compare-diagnostic`。installed0.28.23の比較timeoutを再現し、
試験scriptにpointer/click、openScene/比較開始終了の状態記録を追加した（認証情報は記録しない）。
`/data1tb/mf-material-preview-trace-0.28.23-20260906`では比較click自体が記録されず、
locked/disabled false、compareReady0/dialog falseのままtimeout。別試験ではscroll時の
Element is not attachedを確認。同一sceneのopenSceneが毎回revision DOMをreplaceしていた。
frontendではscene ID/name/current revision/locale/revision metadataのkeyが変わる時だけ
revision DOMを再生成し、不変refreshではボタンを保持する。版/言語の変更表示は維持する。

source fixtureを9047で起動し、実Blender4.5.9/通常Chromeでpointerdown→同一scene refresh→
pointerupを挟んでも旧版比較が開くこと、採用2→3/復元3→4・旧blend bytes一致、
比較/破棄head不変、切断時採用禁止、日英/320px（root320/320、dialog280/280）、page error0。
証拠 `/data1tb/mf-material-refresh-browser-20260906/observations.json`。
同fixtureのdata-dir `/data1tb/mf-material-refresh-ui-20260906`を保持する。
installed0.28.23にはこの修正を導入していない。修正の署名新版/installed受入と生成画像一巡はNOT TESTED。
全体3DS-6/3DS-8はPARTIAL。
gate `./mf.sh test`: 1026 passed / 既知Starlette warning1件 / 111.46秒。node構文/diff check成功。
自分が起動したsource fixture9047はCtrl-Cで停止し、terminal exit0を確認した。
追加のread-only installed検査は既存mf-e2e sceneを同じ内容で再読込し、
`button_retained=False, scene_unchanged=True`を観測。実体差替えを確認した。
手動座標pointerのinstalled負例はpointerイベントを記録できず、そのtimeoutだけを差替えの証明にはしない。
sourceにボタンのisConnected assertionも追加、同fixtureを保持して再起動/再実行した
`/data1tb/mf-material-refresh-browser-identity-20260906`は4→5→6版で全assert成功。
再起動した9047も停止/exit0。過去の全timeoutの原因を網羅したとはしない。
並行mainの#270（canvas補正）/#271（0.28.24版更新）と公開0.28.24を確認。元変更を保持して取り込む。
両変更を保持して取り込み、status末尾の競合は双方の追記を残して解消。
統合後gate `./mf.sh test`: 1030 passed / 既知warning1件 / 111.71秒。diff check成功。
終了前registry.statusはinstalled0.28.23/healthy/enabled。公開latest0.28.24とは異なる。
次はこの修正を含む署名版の準備とinstalled受入。版数は並行releaseを再確認して選ぶ。

## 2026-09-06 v0.28.23 signed / installed acceptance in progress

PR #268 merged `22fc2b95f051bac3e77f740a76367677bdb0358d`、tag v0.28.23は同commit。
exact detached source/PyInstaller6.22.0/Python3.12.3から31,490,364 Bのbundleを構築し正式署名公開。
SHA-256 `8a6eb22131b8a2ca305af4f2524a070f1c3051622cd14092ebc9cf311023db64`。
公開4 assetを`/data1tb/mf-0.28.23-public-20260906`へ再取得、checksum/Host publisher verifier成功。
packaged core doctorはok/0.28.23。launcher直接実行は必須data-dir環境変数不足で失敗したため、
同梱coreのdoctorを実行した。core SHA `6e00a7307fe9850eee997db765643a051ed6e2f59d1cd0d6fd88bd1b4a1f2f41`。
installed実体hashも一致。更新直前の2回の検査ではlocal/Hostのrunning Jobを各1件検出し更新しなかった。
その後全Job/session/runtime/model operation終端を確認、非公開online DB backup
`/data1tb/mf-0.28.23-pre-update-20260906.sqlite3`（1,466,368 B）を保持。
標準registry.updateは10.756秒、0.28.22→0.28.23/healthy/enabled。
MF PID2645893/11:53:53 JST。Host PID2642902/11:51:27 JSTのまま（Host restart要求なし）。

新script `scripts/3ds_material_preview_installed_e2e.py`は専用mf-e2eの新規sceneだけを変更し、
password変更なし/sessionを個別作成・revoke、frontend overlayなし。既存fixtureは変更しない。
初回は診断venvのPillow不在で起動前失敗、標準libraryの合成PNGへ変更した。
installed初回はHost英語設定に対する日本語assertで失敗し、明示日英切替に修正。
再試験は候補表示/破棄/head不変/採用revision1→2まで進み、旧版比較open待ちでtimeout。
このためinstalled全一巡はまだNOT VERIFIED。失敗画面/JSONは
`/data1tb/mf-material-preview-installed-0.28.23-{final,diagnostic}-20260906`を参照。
診断状態だけ追加した再試験は成功。`diagnostic` directoryのobservations.jsonで
scene `scene_257528fdd6a540818537d5e93f893870`の比較/破棄head不変、採用1→2、復元2→3、
復元source SHA一致、切断後採用禁止、日英表示、opaque origin null、page error0を確認。
日本語比較画面を実画像でも確認した。1回の旧版比較timeoutは原因未確定であり、再現調査を残す。
実行commandはHost診断venv/PYTHONPATH=Host backendで同scriptに
`--blend /data1tb/mf-material-preview-ui-final-20260906/original.blend --expected-version 0.28.23`
と新規evidence-dirを渡した。生成画像経路やmobile touchを成功扱いしない。
次は旧版比較timeoutの再現/原因特定と、生成画像→比較→採用/OpenCode一巡を進める。
gate `./mf.sh test`: 1026 passed / 既知Starlette warning1件 / 111.13秒。
GOAL-06/3DS-6/3DS-8はPARTIAL、生成画像一巡/全release A〜Fは未完了。
PR #269へ証跡を提出。exact release worktreeは削除（Gitで再作成可）、build/package展開先は
gio trashへ退避（復元可）。公開再取得・browser証拠・非公開DB backupは保持する。

## 2026-09-06 v0.28.23 source preparation

PR #267 merged `ab8a059bb61d9046630d01183349d8bc62a878af`。
branch `ux1/3d-material-v02823`でaddon/coreを0.28.23へ同期し、採用前比較UIを正式配布する準備。
開始時の実registry.statusはinstalled0.28.22/healthy/enabled。公開latestも0.28.22。
新しい版の署名/公開/導入/installed Host受入はこの段階ではNOT TESTED。
既存source受入は維持するがGOAL-06/3DS-6/3DS-8はPARTIAL。
次は版準備PR gate/merge、exact main bundle構築・署名公開・標準update、専用fixtureでHost browser受入。
版準備gate `./mf.sh test`: 1026 passed / 既知Starlette warning1件 / 115.98秒。

## 2026-09-06 採用前材質候補 UI / standalone mirror

PR #264 merged `feaa69e3049b0d6577f694ffed731477dd26d99c`をfetch確認。
branch `ux1/3d-material-preview-ui`。既存比較dialogを未保存候補にも使い、prepare→比較→adopt/discardを接続。
旧版比較/復元を維持し、生成画像の選択も同じprepare経路へ入る。直接applyの公開契約は変更しない。
standaloneは同一loopback Originだけの専用WS。candidate以外のmethod/不正Originを拒否する5 testを追加。
再接続でcandidateをinvalidにし採用禁止、dropSocketでpendingもreject。準備中に閉じるとsocketを閉じ取消。
旧版復元直後はmaterial revisionとscene head一致まで操作禁止。locale切替でviewer statsも更新する。
320pxの背景navがclient305/scroll319だったため、比較dialog中は背景scrollをlockした。
最終browserではroot320/320、dialog280/280。表示をclipして判定を通したのではなく背景スクロールを停止。

実Blender4.5.9の新規隔離fixture serverを9047で起動し、通常headed Chrome/AMD内蔵GPUで
日英/320px、青い現在版と赤い未保存候補、prepare/discard時head不変、採用だけ+1、旧版復元+1と
旧blend bytes一致、socket切断後adopt disabled/page error0を確認。
証拠 `/data1tb/mf-material-preview-ui-browser-final-20260906/observations.json`（2→3→4版）。
最終保存status修正後は同fixtureの不変履歴を残したまま別evidence dirへ再実行する。
同修正後の再実行も成功: `/data1tb/mf-material-preview-ui-browser-final-status-20260906`（4→5→6版）。
root320/320・dialog280/280、全assert/page error0を再確認。隔離source server9047は停止済み。
gate `./mf.sh test`: 1026 passed / 既知Starlette warning1件 / 121.80秒。構文/diff check成功。
並行main #265（nonce前の接続抑制）/#266（version0.28.22）を`20ebd9b`で取り込んで保持した。
source UIのstandalone分岐とhost nonce待ちの条件は両立し、無認証mirrorをhost経路の代用にはしていない。
main取込後gate `./mf.sh test`: 1026 passed / 既知warning1件 / 126.61秒。diff check成功。
初回は復元直後の材質情報読み込み中の再比較でtimeout。ready条件修正後は成功した。
初回の弱い幅assertも実画像で見抜き、client/scrollの等値検査へ変更した。

次はinstalled HostでこのUIを受入し、既存画像/生成画像→比較→採用/破棄/復元の制作一巡を照合する。
source browserの成功をinstalled/署名新版へ読み替えない。生成画像GPU経路の再実行もNOT TESTED。
GOAL-06/3DS-6/3DS-8は未完了。Host/installed service/利用者制作データは変更していない。

## 2026-09-06 採用前材質候補 private WebSocket

PR #261 merged `c054495c5a6e203f188e61b4b6a5548c67b07b90`をfetch確認。
branch `ux1/3d-material-preview-transport`。app singletonに候補managerを接続し、startup initialize、
5秒周期expiry、shutdown cleanupと、`scenes.material.preview.{prepare,read,adopt,discard}`を追加。
サーバー生成connection IDと認証ownerを束縛、field厳密検証、raw Host path拒否、connection1要求に制限。
候補だけbackground dispatchにしてprepare中もreceiveを続け、切断でtask取消→cleanupする。
既存通信の逐次処理/公開Agent applyは維持する。8 transport testsを追加して成功。

`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_material_preview_transport_e2e.py
--data-dir /data1tb/mf-material-preview-transport-20260906
--legacy-runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9`成功。
新規隔離Store/ephemeral loopback Uvicorn/実TCP WS/実Blender4.5.9を使用。認証は明示fixtureであり
installed Host認証の証拠ではない。2284B GLB、prepare/discard head不変、別connection adopt拒否、
採用だけ2→3版/再送で増加なし、ready/prepare中の切断回収、clockを11分進めた定期expiryで
runtime reference0/candidate directory0をassert。証拠は同data-dir/transport-observations.json。

次はstandalone mirrorとfrontend未保存候補の比較/採用/破棄を実装する。現行UIはまだ直接applyする。
新候補はassets.model.openのAssetとして扱わず専用readで読み、現行版と並べて表示する。
UI/installed Host/署名新版はNOT TESTED。全体GOAL-06/3DS-6/3DS-8は未完了。
Host/installed service/利用者制作データは変更していない。
gate `./mf.sh test`: 1021 passed / 既知Starlette warning1件 / 113.45秒。diff check成功。
PR #264作成後、並行作業のmain `1abc62e`（#262 mobile reconnect / #263 version0.28.21）を確認し、
`38a87e1`で取り込んだ。相手の変更は保持。再実機証拠
`/data1tb/mf-material-preview-transport-main-20260906/transport-observations.json`も全assert成功。
次のUIはmobile reconnectによる候補失効も表示し、旧connectionの候補を黙って再採用しない。
main取込後gate `./mf.sh test`: 1021 passed / 既知warning1件 / 126.49秒。diff check成功。

## 2026-09-06 採用前材質候補 domain

PR #260 merged `45e85311f135f090d016027becf3fd629954aae9`。branch `ux1/3d-material-preview-core`。
`scene_material_preview.py`にprepare/read/adopt/discard/expire/connection cleanupを追加した。
現時点ではapp/WS/HTTP/UIから未接続。既存公開Agent materialの即時commit契約は変更していない。
候補は正式Asset/revisionではなく専用root内。全体2候補/connection1候補/TTL10分/結果含め16件、
runtime pin、hash再検証、base競合、512KiB chunk、破棄・期限・起動時回収を実装。
採用開始後のrequest取消はcommitの終端を待ち、再送で同じ結果を返す。prepare取消は候補回収。
追加9 testはowner/connection分離、範囲/個数、改ざん、head競合、期限、取消、symlink等を検査する。

実Blender4.5.9を既存legacy runtimeから隔離dataで実行:
`PYTHONPATH=backend:. .venv/bin/python scripts/3ds_material_preview_core_e2e.py
--data-dir /data1tb/mf-material-preview-core-final-20260906
--legacy-runtime-root /data1tb/ControlDeckMediaForge/runtimes/blender-4.5.9`。
prepare0.462秒/adopt0.267秒、GLB2284B/12triangles/1texture、候補作成・破棄でhead/asset不変、
採用だけrevision1→2、再送も2版、旧blend bytes不変、採用source hashと候補一致、候補directory0。
証拠は同data-dirのobservations.json。初回scriptのPYTHONPATH不足とpurpose誤りは修正後に別dir再実行した。

次はappにsingleton managerを作りprivate transportとUI比較を接続する。connection IDはサーバー生成し、
prepare task切断取消・cleanup・定期expire・shutdown cleanupを必ず接続する。現行一般revision比較とは
別に未保存候補を表示し、採用ボタンだけadoptする。両画像入力経路と日英/mobile/競合を実ブラウザで検査。
transport/UI/installed署名新版はNOT IMPLEMENTED / NOT TESTED。3DS-6/GOAL-06/3DS-8は未完了。
installed0.28.20・Host・利用者制作データは変更していない。
gate `./mf.sh test`: 1013 passed / 既知Starlette warning1件 / 132.16秒。diff check成功。

## 2026-09-06 採用前比較の実装不足を確認

PR #259 merged `a1635c9d54837085ac95ec8ef4d0f9acc3acbde5`をfetch確認。
branch `ux1/3d-pre-adoption-gap`。PR #213はmerged `9469d8e`で設計の取り込み待ちはない。
設計asset/OpenCode §4/5は未保存材質候補の比較→採用→revision確定を要求するが、現行
`applySceneMaterial`→`scenes.material.apply`→`apply_material_binding`→`commit_working_copy`は
比較前にheadを確定する。`openSceneCompare`は確定済み新旧revisionだけを表示する。
既存frontend contract testも直接applyを要求し、この仕様差を検出しない。
3DS-6 exit完了を撤回、GOAL-06を実装不足と明記した。署名0.28.20の確定済み版比較の実績は維持する。

次は3DS-6のprivate workspace候補prepare/compare/adopt/discardを実装する。
詳細な安全境界と受入は`3ds-completion-audit.md`「採用前の材質比較がない」に記載。
旧版復元試験だけでこの不足を閉じない。既存公開Agent material契約は破壊せず加法的に進める。
実装入口: SceneWorkspaceのacquire/commit/release_working_copyと_material_operationを再利用できる。
ただしcommit_working_copyはasset登録まで進めるためprepareで呼ばない。ModelViewerSession.openは
既存Asset限定なので、未登録候補用の内部path検証→opaque handle経路とconnection cleanupが必要。
候補のruntime/working lease・metadata・previewの寿命を揃え、一般working commitで採用条件を迂回させない。
今回product/Host/installed service/制作データは変更していない。新候補経路はNOT IMPLEMENTED。
gate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 105.73秒。diff check成功。

## 2026-09-06 v0.28.20 signed / installed material comparison

PR #258 merged `c26f67ddb3b297bd29d9a7a350135b1ac5b8a962`、tag v0.28.20は同commit。
exact worktree/PyInstaller6.22.0/Python3.12.3から31,475,892 Bの正式bundleを構築・署名公開した。
SHA-256 `88f0cdfab3efc67801fa4f2ca2394e38212492ee3870cc10153285fa711d6373`。
公開4 asset再取得checksum・Host publisher verifier成功、packaged doctor ok/0.28.20。
core SHA `1bdb6d40d24efaa5d4627e07b2323489bc3b5f109ec5a84c62c93d190ee3be21`はinstalled実体とも一致。
更新直前Host/local active Job0、Web session/runtime/model operation全終端を確認。
online DB backup `/data1tb/mf-0.28.20-pre-update-20260906.sqlite3`は1,449,984 B、非公開/保持。
標準registry.updateは10.144秒、0.28.19→0.28.20/healthy/enabled。MF PID2503646、10:49:09 JST開始。
Host変更/restartは要求していない。

overlay/追加接続許可なしで比較scriptの`--steel-fixture`を実行し、旧銀/新青黒のRGB条件と
新旧描画差18437pxを確認。`--context-side old`と新しい`--context-side current`を別々に実行し、
テクスチャなし/あり双方のcontext復旧後描画差0・status復帰・閉じた両context loss=true、
instance/handle0、scene不変、page error0を確認した。
証拠 `/data1tb/mf-material-compare-installed-0.28.20-{old,current}-20260906/observations.json`。
Library6軸/zoom/orbit/wheel/fit/320pxも `/data1tb/mf-six-axis-installed-0.28.20-20260906`で成功。
通常Chrome/AMD内蔵GPUの実績であり、R9700や実mobile touchの実績ではない。

exact release worktreeは削除（Gitで再作成可）、build出力/packaged展開先2 directoryはgio trashで退避。
公開再取得 `/data1tb/mf-0.28.20-public-20260906`・browser証拠・DB backupは保持する。
次は比較からの採用/旧版復元を含む制作一巡の不足を、専用fixtureで実操作する。
今回のread-only比較で採用操作まで成功にしない。GOAL-06/3DS-8はPARTIAL、他残件は監査表。
受入script変更後のgate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 105.01秒。

## 2026-09-06 v0.28.20 source preparation

PR #257 merged `2b527d05858bbc4e279d18be16ee85f48b285cd5`。
branch `ux1/3d-material-v02820`でaddon/core versionを0.28.20へ同期。材質照明/context復旧修正は
同PRのコードを維持する。初回確認でinstalled0.28.19/healthy/enabled、Host/local Job0、Web session0。
Host PID2499072、MF PID2470070。今回Host変更/restartは要求していない。
次は版準備PR gate/merge後、exact mainの正式bundle署名公開・標準update・比較/6軸のinstalled受入。
この段階では新版の公開/導入はNOT TESTED。全体3DS-8/GOAL-06はPARTIAL。
版準備gate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 103.75秒。diff check成功。

## 2026-09-06 metallic material comparison candidate

PR #256 merged `8ba4f66`を基準にbranch `ux1/3d-material-compare-acceptance`。
導入済み0.28.19でscene_ca920fd634b14dfea8215567e930bb7aの12版/現行13版を読み取り比較した。
2画面表示・閉じた後の両WebGL context lossとinstance/handle回収・scene不変は成功したが、
刃が両版とも黒く材質差が見えなかった。PNG hash差だけの判定では不十分だった。
証拠 `/data1tb/mf-material-compare-installed-0.28.19-20260906`。

GLB実体と固定GLTFLoaderを照合し、刃はmetallic既定1/roughness0.25で、新版だけbaseColorTextureを持つ。
表示用環境反射がなく、diffuse用hemisphereだけでは刃が黒くなることを候補で切り分けた。
固定Three.js同梱RoomEnvironmentをPMREM化し、材質値/assetを変えず環境照明を追加する。
map/一時generator/roomはdisposeし、context復旧時は環境mapを再生成する。外部HDR/URI取得なし。

実候補 `/data1tb/mf-material-compare-environment-candidate-20260906`では旧版銀/新版青黒を視認。
同サイズ487x406の刃ROI（x49.7〜50.5%, y20〜50%）平均RGBは旧版131.34/133.87/137.18、
新版2.23/9.82/25.40。導入版baselineは旧版1/1/1、新版0/0/0だった。
候補moduleのSHAはae9fcecc3739d0b728d8ff5280dbee6bf42e4a0724ad94db0b739746305c8848。

比較画面のcontext復旧後に「復旧中」statusが残る問題も実測してapp.jsで修正。
復旧後のPNG差はstatus文字のantialias領域(x16〜221,y16〜28)に限定されたため、status文字列は
別assertし、WebGL画素は上40pxのstatus領域を除いて完全一致を検査する。
新script `3ds_compare_installed_e2e.py`は個別mf-e2e sessionを発行/失効し、制作データを変更しない。
candidateはブラウザresponse本文だけ差替え、認証/CORS headerを維持し、overlayと明示許可を記録する。
最終候補の初回はHostがdeactivating/restartでERR_CONNECTION_REFUSED。こちらはrestartを要求していない。
Hostはその後10:38:41 JST/PID2495560/active、health200へ復帰した。
最終候補 `/data1tb/mf-material-compare-final-candidate-retry1-20260906`は全assertion成功。
steel fixtureの旧銀/新青のRGB条件、新旧描画差18437px、context復旧後の描画差0とstatus復帰、
閉じた両context loss=true、instance/handle0、scene不変、page error0を確認。
既存Library6軸/zoom/orbit/fit/320pxも `/data1tb/mf-six-axis-environment-candidate-20260906`で成功。
source gate `./mf.sh test`: 1004 passed / 既知warning1件 / 106.44秒。hash/構文/diff check成功。
全体3DS-8とGOAL-06はPARTIAL。次はsource PR、正式版配布後overlayなしの同じ確認。

## 2026-09-06 v0.28.19 signed / installed Library viewer

PR #255 merged `583fea18e710730a8c56758846c8cfeb13622e52`。同commitのdetached worktreeから
PyInstaller6.22.0/Python3.12.3で正式bundleを構築・署名公開。tag v0.28.19は同commit。
31,474,100 B / SHA-256 `212d062cd2e7c9ad8da67c5f8c6fe0cbd3a3bf06becf0a5688c96758a0a13ffd`。
公開4 assetを `/data1tb/mf-0.28.19-public-20260906`へ再取得しchecksum一致、Host publisher verifier成功。
packaged doctor ok/0.28.19。core SHAは`f62ae311ccd2b9375c86ac92bba3942c214869e6b5484dabd7151730eb37f1d0`。

更新直前Host/local Job0、Web session/runtime/model operation全終端を確認。
SQLite online backup `/data1tb/mf-0.28.19-pre-update-20260906.sqlite3`は1,449,984 B、非公開/保持。
標準registry.updateで0.28.18→0.28.19、10.613秒、healthy/enabled。
MF MainPID2470070 / 10:26:06 JST開始、実行中exeのcore SHAも一致。Host再起動は要求していない。

`scripts/3ds_viewer_render_installed_e2e.py --scene-id scene_3ac2b7089a3b5cc3b7b1a95ffd96594f
--evidence-dir /data1tb/mf-viewer-six-axis-library-installed-0.28.19-20260906`をHost diagnostic venvから実行。
frontend_mode=installed、overlayなし、追加local-network-access許可なし。通常Chrome/AMD内蔵GPUで
Library→3D→asset card、±XYZ15度回転、zoom両方向、orbit/wheel、fitを実pixel比較で確認。
回転差分1773〜25023px、zoom43020/41483px、逆操作/fit/idleは差分0。
origin=null、320px/scroll319、page error0、scene応答不変。専用sessionだけ失効、password変更なし。
GOAL-02の利用者指定操作をこの範囲でVERIFIEDとし、全体3DS-8はPARTIALのまま。

exact release worktreeは削除（Gitで再作成可）。build出力/packaged展開先2 directoryはgio trashで退避
（復元可）。公開再取得4 asset、browser JSON/PNG、更新前DBを保持。
次はviewerの日英/mobile入力・context loss/memory回収のrelease gateと、修正済み共通loaderを通る
材質新旧比較の実assertionを補う。長時間credentialの無再起動枠は未調整。他GOAL/A〜Fの残件は監査表。

## 2026-09-06 v0.28.19 source preparation

PR #254はmerged `76a91b490ee1eee7daa08e1214da1697f319c5c6`。
branch `ux1/3d-viewer-v02819`でaddon/coreの版を0.28.19に揃えた。viewer実装は同PRのまま。
現行installedは0.28.18/healthy/enabled。初回確認でactive Host/local Job0、Web sessionは全て終端、
runtime/model operationも全て終端。更新直前に再確認する。元checkout/Hostの並行作業は変更しない。
次は版準備PRのgate/merge、exact mainから正式署名bundleを公開し、標準updaterで導入、
`3ds_viewer_render_installed_e2e.py`のcandidate overlayなしで同じLibrary実操作を確認する。
この段階では0.28.19の公開・導入はNOT TESTED。全体3DS-8はPARTIAL。
版準備gate `./mf.sh test`: 1004 passed / 既知warning1件 / 110.52秒、diff check成功。

## 2026-09-06 Library viewer six-axis candidate

利用者がLibrary viewerの必須操作を±X/±Y/±Z回転・拡大縮小に指定し、軸の意味も確認した。
base/UX/3D設計/plan/auditを同期。wire/animationは追加操作とし、制作側の材質比較等は維持する。
branch `ux1/3d-viewer-render-acceptance`、基準main `8484286`。PR #213はmergedを再確認。
6方向15度回転とzoomボタンを実装。モデル中心の表示用pivotだけを回しscene/assetを変更しない。
既存orbit/fit等は保持。viewer/比較画面で共通のcredentialed module loaderを使用する。

現行installed 0.28.18はHost直下の誤URL `/viewer-runtime.js`をimportしCORS拒否で表示失敗。
frame配下へ直すだけでも専用routeのACAO `*`とHostの`null`が重複して拒否された。
既存 `/static/three-viewer.js`をcredentialed module scriptで遅延読込し、HostにCORSを任せる。
Hostコードは変更しない。bundleをlock通り再構築しhashを更新した。

実機候補受入: `/data1tb/mf-viewer-six-axis-library-candidate-20260906/observations.json`。
Host/backendはinstalledのまま、ブラウザ応答本文だけ候補へ差替え。認証/CORS/headersは保持する。
専用mf-e2e sessionを発行しfinallyでそのsessionだけ失効。パスワード変更なし。
Chrome通常表示、AMD内蔵GPU/radeonsi、opaque origin=null、Library→3D→asset cardから操作。
6方向の描画差分1773〜25023px、逆回転は全て差分0。zoom両方向・orbit/wheel・fit復帰も成功。
320px/scroll319、page error0、scene応答不変。thumbnail cache生成は通常のviewer動作に含まれる。
これはcandidate frontendの受入であり、正式bundleの導入成功ではない。

試験の初期失敗も保持: HTTP route再送はSec-Fetch-Destを失い403、CDP response-onlyへ修正。
opaque iframeの別CDP targetも捕捉する。HTML差替え試験contextだけlocal-network-accessを許可した。
headlessは空pageでもWebGL2=null、通常Chromeはcontext作成成功。software GPU実績とは扱わない。
最初のpixel閾値0.5%は細い剣の長軸回転1773pxを失敗扱いしたため、idle/逆操作の差分0を対照に
100px超の実描画差分をassertする。製品の角度/入力条件は変えていない。
次はこのsliceのsource gate/PR後、署名releaseとinstalled overlayなしの同じLibrary受入。
全体3DS-8はPARTIAL、長時間credential試験の無再起動枠も引き続き未調整。
source gate `./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 114.02秒。
`npm ci --ignore-scripts`、`npm run build:viewer`、source/bundle hash一致、node構文検査、diff check成功。

## 2026-09-06 v0.28.17 signed / installed terminal acceptance

PR #251 merged `4293d2086aaeed4784a2ad0c2b9776f88415c043`からexact worktreeで正式bundleを構築・署名公開。
v0.28.17 tagは同commit。31,470,272 B / SHA-256
`997f6cef6e941eca6603cff199d3dbc43a28d030d79ae7fdfbbfe9109af500b3`、公開4 asset再取得一致、
Host consumer publisher verifier成功、packaged doctor ok/0.28.17。公開先は通常GitHub Release。

画像Job `job_29459166c091438c8c14767cd35c130e`とworker PID2399992の終了、Host/local active0を
確認してからHost mainを`dac519b`へfast-forwardし再起動した。既存dirty tsconfig.tsbuildinfoは保持。
標準registry.updateで13.627秒、0.28.16→0.28.17/healthy/enabled。
Host PID2403274、MF MainPID2403709/child2403714。事前DB backupは
`/data1tb/mf-0.28.17-installed-evidence-20260906/media-forge-pre-update.sqlite3`（非公開、保持）。

packageのfull Agent status/cancelを隔離Hostで確認:
`/tmp/mf-terminal-http-hcxvio45/observations.json`。installedでも過去retry2のmf-e2e-owned failed6件を
status/cancel/statusの18 HTTP callで照合し、Host interruptedは不変、sent=false/matches=falseを保持。
0.304秒、Job/asset/scene/revision件数不変。証拠
`/data1tb/mf-0.28.17-installed-terminal-retry1-20260906/observations.json`。
これは既存終端fixtureの照合であり、未送信新規成功通知や長時間refreshまで成功にしない。
初回installed smokeは別生成Jobを検出してpreflightで停止した。終端対象IDだけを扱うscriptの
不要な全体idle条件を外し、scope/owner/terminalと件数不変を検証して再実行した。
credential scriptは`--expected-version`を追加（既定0.28.16）、新版試験は0.28.17を明示する。
受入script更新後`./mf.sh test`: 1004 passed / 既知warning1件 / 131.28秒。
exact release worktreeは削除（Gitで再作成可）。今回のbuild出力/packaged展開先2 directoryはgio trashで退避し、
公開再取得4 asset・観測JSON・更新前DB backupは保持した。

新版長時間試験はFAILED / refresh NOT TESTED。idle確認後`--expected-version 0.28.17`で開始し、
child2409636を160.0676秒保持・再開、child2415439を161.690秒から保持した。
222.109秒にConnectError、225.185秒にservice_stoppedを検出。
systemdは09:40:12 JSTにMediaForge停止、09:40:13再開を記録。本試験はrestartを要求していない。
要求主体は未特定。Host PID2403274は不変、現在MF MainPID2416323でactive。
全6件は1 succeeded/5 failedでHost/local一致、host_terminal_sent=true、refresh監査各0件。
cleanup後active local0、保持した2 child PIDとも消滅。証拠
`/data1tb/mf-credential-refresh-installed-0.28.17-20260906/events.json`とsystemd/read-only SQL。
並行Host側のuntracked frontend/e2e/mediaforge-library.spec.tsとdirty tsconfig.tsbuildinfoは保持。
次の長時間試験は約11分間Host/MediaForgeを再起動しない時間帯を調整する。
正常なshutdown終端通知をcredential更新成功へ読み替えない。全体3DS-8はPARTIAL。
その後の現物確認では、並行Library PR #252（merged `7434d7f`）に伴い現行installedは0.28.18/healthy。
本turnが公開・導入・18call検証したのは0.28.17であり、その後の再起動時点の新版受入は別作業。
旧版へ戻さない。次回は現行0.28.18のprovenanceと引き継ぎを再照合し、無再起動枠を調整する。

## 2026-09-06 terminal outbox / v0.28.17 source

branch `ux1/3d-terminal-outbox`、基準main `c5afdf9`。Host汎用PR #276はmerged `dac519b`。
Hostの終端専用reconcileはactiveな新callの署名actor/caller/target ownerを検証し、確定済み終端を
上書きせず一致/不一致receiptを返す。既存Job scopeやtoken/resource権限を広げない。

MediaForgeは有効なchild identityで1〜30秒backoffのoutbox再送を行い、失効時は止める。
core再起動後はownerの正規status/cancel callでそのJobのpayloadを再送する。SQLiteにreceiptを追加し、
一致だけhost_terminal_sent=true、不一致はfalseのまま照合結果を保持。中断復旧時にもpayloadを残す。
Host controlのinterrupted/failed/succeededは制作中断へ反映。refresh時actor_subjectも維持する。
APIは加法的metadataのみ、新schemaは`host-terminal-reconciliation.json`。秘密tokenは永続化しない。

`scripts/3ds_terminal_outbox_e2e.py`をHost diagnostic venvから起動し、coreは必ず別のMF venvで3process
（seed→consume→consume）を実行。正規introspection・実Host HTTPで、interruptedとの不一致falseと
active targetへの成功trueを確認。2回目processでも同receipt、local Jobは2件、recipe再実行0。
証拠`/tmp/mf-terminal-http-1ppzav37/observations.json`。これは隔離した終端fixtureの受入であり、
実Blender制作、full core Agent HTTP、installed package、600秒超refreshの成功とは記録しない。
最初のsmokeはcore側PYTHONPATHにrepo rootがなくscripts importに失敗。分離venvを維持して修正後に成功。
試験systemd unitは停止済み。導入済みv0.28.16とHost稼働serviceは変更していない。

次はこのsliceをmerge後、exact mainから署名v0.28.17を公開・標準updateし、installed outbox/status/
cancel・Host差異表示・長時間child credentialを実測する。全体3DS-8はPARTIAL。
credential受入scriptは現時点でinstalled 0.28.16をassertするので、新版受入前に期待versionを
明示引数化する。過去のFAILED記録を新版成功へ書き換えない。
最終sourceの実HTTP再確認も同結果、証拠`/tmp/mf-terminal-http-4rjhhdmw/observations.json`。
最終`./mf.sh test`: 1004 passed / 既知Starlette warning1件 / 109.09秒。

## 2026-09-06 Host terminal history prerequisite

前回PR #249はmerged `a4b7014`。汎用Host PR souten-yd/ControlDeck#275もmerged `40f1bc0`。
Host再起動後にAdd-onからDB履歴へ到達できない問題はMediaForge内で解けないため、別worktree
`/data1tb/ControlDeck-job-history`でJob control読取だけを修正。メモリ不在の終端履歴をowner/Job/Add-on
scope検証後に返す。非終端履歴は409、refresh/updateは404を維持し、終端を上書きしない。

Host full test 951 passed / 1 skipped / 66.76秒、最新main取込後focused37 passed / 3.49秒。
隔離systemd processでDB running→通常startup recovery→interrupted、実HTTP control200、別Job403、
refresh404、update404、DB終端不変を確認。証拠`/tmp/cd-job-history-nzou5ckt/observations.json`。
試験unitは停止済み。Hostの並行UI作業・稼働serviceには触れていない。

**未完了**: 導入済みHostへの適用、MediaForge outbox再送/照合、600秒超credential受入。
新規OpenCode callのJob subjectは旧child Jobへ委譲されないため、actor ownerが一致するだけで
既存job-scope検証を迂回しない。正規identityが戻った後の再送と、Host既存終端の照合結果を
区別する必要がある。単なる履歴読取やinterrupted照合を`host_terminal_sent=true`に読み替えない。
次はこのauthorityを保つ汎用Host終端照合契約とMediaForge永続outbox consumerを実装する。
全体3DS-8は引き続きPARTIAL、導入済みMediaForge v0.28.16は変更なし。
この引き継ぎ更新の`./mf.sh test`: 993 passed / 既知warning1件 / 105.30秒。

## 2026-09-06 child credential acceptance / Host interruption

branch `ux1/3d-credential-refresh-acceptance`、基準main `9ff49ac`。導入済みv0.28.16は変更なし。
`scripts/3ds_credential_refresh_e2e.py`を追加。専用mf-e2eの正規service identityをメモリ内で扱い、
installed Agent APIへCPU recipeを6件投入。自分のchildをmarker/pidfdで固定して各160秒SIGSTOP、
167秒自動再開。後続Jobを600秒超まで待ちrefresh/取消/成功/Host終端を検査する試験であり、
自然な長時間computeやOpenCode制作ではない。Host TTL600 / margin120 / worker timeout180は変更しない。

結果は **FAILED / refresh NOT TESTED**。初回はonefile bootloaderの子孫探索不足で捕捉失敗、そのJobはsucceeded。
探索修正後retry1は251.002秒までrunning、その後照会502 `host_unreachable`。
Hostログは08:39:04〜08:39:17 JSTに約13秒途切れ、1 succeeded / 5 failed `host_context_lost`。
test群を並走させないretry2も150.297秒で6件すべてfailed。Hostは08:42:17 watchdog timeout、
08:42:24再開、08:45:11停止、08:45:15再開を記録。本試験が要求したHost再起動ではない。
retry2はlocal failed / Host DB interrupted、`host_terminal_sent=false`、refresh監査0件。
cleanup後はactive Job 0 / Blender recipe child 0、両service active。

次は未送信outboxとHost履歴照会。managerは3回送信後にidentityを捨て、永続outbox再送consumerが見当たらない。
Host runtime `host_job`はmemoryの`jobs.get`だけを使い、再起動後DB履歴へ到達しない。
正規identity復帰時の再送/照合を詰め、Host既存終端を勝手に書換えない。必要なHost修正は汎用Job契約の別PR。
Host既存dirty tsconfig.tsbuildinfoを保持する。証拠は
`/data1tb/mf-credential-refresh-installed-0.28.16{,-retry1,-retry2}/events.json`。
scriptは一時観測失敗で同じJobを再照会し、失敗時にlocal DB状態を記録する。
最終`./mf.sh test`は993 passed / 既知Starlette warning 1件 / 106.33秒。
これは回帰検査であり、FAILEDの長時間受入を成功へ変更する証拠ではない。

## 2026-09-06 installed recovery fork / v0.28.16

PR #247 merged `53faaeb52770b1f151f0000fa73dc02566a99acb`。同commitから正式v0.28.16を再構築・署名公開した。
bundleは31,468,656 B / SHA-256 `8ae198224aa361d31406d2fce151ca4a1eda2ecd0892bd0259bafc97e1b810df`。
公開4 asset再取得hash・tag target一致、packaged doctor成功。標準Host updaterの署名/consumer/provision/
health経路で11.277秒、0.28.15→0.28.16、healthy。最終PID 2286511、active/running、drop-inなし。

`scripts/3ds_recovery_installed_e2e.py`で既存mf-e2eを一時認証し、installed opaque iframeから
保存競合candidate `working_0a35fec723ae491bb9abf93c6e533077`を別scene
`scene_3ac2b7089a3b5cc3b7b1a95ffd96594f`へ救出した。1,438,783 B / SHA-256
`11ff0e65eeec0f33ffb1d7e35dc2b82319b0dd467de964b493ee7b1e3151dcaa`、0.978秒、pinned Blender 4.5.9。
元sceneの13版は不変、candidate/source asset hash一致、元版の画像dependency継承、再送同scene、
GLB 891,224 B / 236 triangles、browser error 0。mf-e2e認証はfinallyで元へ戻し、この試験sessionのみ失効。
証拠: `/data1tb/mf-recovery-fork-installed-evidence-0.28.16/observations.json`。
今回の隔離fixtureとcandidate/release展開物4 directoryは受入後にgio trashで退避した。
公開物再取得コピーと観測JSON/screenshotは保持。exact release worktreeはGitから再作成可能。
installed acceptance script追加後の`./mf.sh test`は993 passed / 既知warning1件 / 101.74秒。

3DS-8全体はPARTIAL。次は期限内child credential refreshの実測。
現行Host TTL600秒、manager margin120秒、worker timeout180秒を前提に、132秒fault injectionを
更新成功へ読み替えない。競合救出の不足は解消したが、他の全GOALは監査表どおり個別照合を続ける。

## 2026-09-06 recovery fork / v0.28.16 candidate

branch `ux1/3d-recovery-fork`、基準main `911f154`（PR #246 merged）。
保存競合candidateを現行headへ無条件rebaseせず、明示操作で別sceneへ救出するprivate
`scenes.recovery.fork`と日英UIを追加した。pinned runtime・独立GLB検査・依存blob hash確認後にだけ
確定し、元headとcandidate bytes/stateを保持。元revision/asset lineageをprovenanceに記録する。
同candidate再送は同sceneを返す。embedded `scenes.list`のworking_copies欠落も修正した。

隔離source/packaged実HTTP + Chromium + Blender 4.5.9で、位置を変えた434,663 Bの.blendを救出。
source 0.534秒、candidate package 0.540秒、package再送0.287秒、320px overflow 0。
package source asset hashは`a6b1792d203085cd76299aae51aeaa471b6e534b033dbd0df042a8f979b4a3c3`。
元head、candidate、source assetの同一性と再送の同sceneをassert。再送時はconsole/page errorとも0。
証拠: `/data1tb/mf-recovery-fork-{source,package,package-retry}-evidence-20260906/observations.json`。
source/packaged隔離serverは受入後に停止する。installed service/dataにはまだ触れていない。

`./mf.sh test`: 993 passed / 既知warning 1件 / 102.15秒。候補bundleは31,623,524 B / SHA-256
`5eeb7e510233bdc06e35db3aaf0b0c1a92c8da9abe3a1218a53e040edfeca2b5`、doctor `ok / 0.28.16 / packaged=true`。
次はPR merge・exact main正式bundle署名公開・標準update・installed候補の分岐救出。
これらは現時点で **NOT TESTED**。全体の3DS-8はPARTIAL、長時間credential等の残件は監査表に維持する。

## 2026-09-06 完了監査再開 / standalone recovery transport

branch `ux1/3d-standalone-recovery`、基準main `1f4392a2d426a742046d0c03c99272ffb5e41c87`。
下記の「初期提供完了」判定は撤回し、3DS-8をPARTIALへ戻した。過去の実測や公開v0.28.15は変更しない。
最新判定は[`3ds-completion-audit.md`](3ds-completion-audit.md)。GOAL-01〜10/シナリオA〜Fを
一項目ずつ照合する。132秒fault injectionはchild credential refreshの証拠ではない。
必要なのは失効前の正規refreshであり、失効tokenから自己再発行することではない。

standalone session POSTで`recovery_working_id`が脱落する不具合を修正した。
`/data1tb/ControlDeck/app/.venv/bin/python scripts/3ds_standalone_session_transport_smoke.py`で
実Chromium→隔離loopback HTTPの復旧start/通常start/save/stopの4 body一致、browser error 0。
HTTP記録器によるtransport検証であり、修正後の実Blender復旧・署名bundle受入は **NOT TESTED**。
競合candidateはbackendのbase revision検査で再openを拒否するため、bytes保持だけで復旧完了とはしない。
次はこのsliceのtest/PRを閉じ、競合candidateの分岐救出経路と期限内credential refresh実測を進める。
最終`./mf.sh test`は981 passed / 既知Starlette warning 1件 / 102.21秒。
初回は追加testの文字列切出しミスで1 failed / 980 passed。範囲を修正後、frontend 149件と全体を再実行した。

## 2026-09-06 3DS-8 completion / v0.28.15

PR #244はmerge commit `aa054bc804dbcce4cb1262cc40188f8db9b01fd0`でmerged。正式v0.28.15は同commitを
targetに公開した。bundleは31,463,968 B / SHA-256
`6944b24677d40ca176b460f6590f6167780cfb5fd79f1e76995688913526f75d`、公開4 asset再取得hash一致、
Host consumer verifierとpackaged doctor成功。標準updateは10.73秒 / 最大RSS 772,524 KiB / swap 0、
`current=0.28.15`、previous 0.28.14、health healthy。

修正後のinstalled opaque iframe保存競合はrevision 11→12のconcurrent restore後に
`scene_revision_conflict`でfail-closedし、revisionは12のまま、responseにrecovery candidate
`working_0a35fec723ae491bb9abf93c6e533077`を返した。実`scene.blend`は1,438,783 B / SHA-256
`11ff0e65eeec0f33ffb1d7e35dc2b82319b0dd467de964b493ee7b1e3151dcaa`、browser error 0。

LLM idle後の実Brokerは27.4 GB resident LLMを停止し、FLUX.2 Klein 4Bで1,024x1,024 PNG
1,737,483 B / SHA-256 `a3cb9e4f70eb8a396307576cfccef57e721ac50fa10f7f73a62d671f6276494d`を
57.869秒で生成した。opaque iframeで明示選択してBlade/base colorへ適用、revision 12→13、
dependency/provenance/validators、browser error 0を確認した。

実Blender 4.5.13 childへの対象PID限定SIGSTOP fault injectionでdetached Jobを132.033秒までrunningとして
再照会し、132.085秒に公開cancel、133.122秒で`canceled / host_terminal_sent=true`、Host childもcanceled、
残存Blender child 0。live rollbackは一時鍵・隔離v0.28.16を実updaterへ渡し、候補health/doctor後の失敗注入から
9.656秒でv0.28.15 current/service/Add-on登録へ復帰した。一時candidate/version/download/keyは削除した。

`docs/implementation/g8-3d-studio-plan.md`とcompatibilityを3DS-8 VERIFIEDへ更新し、統合3D Studio初期提供を完了。
次の予定sliceはない。Expert scriptは別3DS-X。GPU GUI表示、失効後credential refresh、installed容量不足再注入は
**NOT TESTED**であり、software GUIや自動testをその証拠へ読み替えない。

## 2026-09-06 3DS-8 release acceptance / recovery conflict

branch `ux1/3d-release-acceptance`。正式v0.28.14を実ControlDeckへ標準updateし、installed opaque iframe、
OpenCode、Blender、Host lifecycleを通し確認した。10分超GUIは621.451秒接続を維持し、reload/reconnect、
別browser writer拒否、noVNC入力、revision 2→3保存、390px横overflow 0、browser error 0。既存Library画像は
revision 3→4へ材質適用した。Blender crashは2.846秒で検出して1,438,783 Bのrecoveryを保持し保存、idleは
5秒設定時に接続から8.695秒で終了してrecovery保存、MediaForge再起動は0.933秒でhealth復帰後に同sessionへ
再接続してrevision保存、実Host token 20秒TTLはRFBを25.038秒後に4403で閉じrecovery保存した。既定
idle/disconnect値1800/300秒へ戻した。

R9700/gfx1201はVRAM 34,208,743,424 B。Eevee 64x64は2.7709秒、Cycles HIP 4 samplesは0.26939秒、
最大RSS 3,002,844 KiB。LLM処理中の画像jobはBrokerで`waiting_resource`となり、LLM unload/reload後も
同時GPU実行せずcancelできた。正式bundle 31,619,593 B / SHA-256
`b4c8b6eae43e9e290339b30522081f388f40c3e8e8d3299e4dd1cda5cf27bd2b`は署名、公開再取得、manifest/artifact
改ざん、wrong key、downgrade拒否を実測した。

同sceneのGUI編集中にcurrent revisionを進める保存競合では正式版を上書きせず
`scene_revision_conflict`となったが、commit処理がすでにworking copyをrecoveryへ遷移した後、失敗projectionが
同じ遷移を再要求して`result.recovery=null`にした。recovery保持をowner検証付きidempotent操作へ修正し、
既存candidateを返す回帰を追加、版は0.28.15。focused 27 passed、exact head `./mf.sh test`は980 passed /
既知warning 1件 / 100.41秒。candidate bundleは31,618,953 B / SHA-256
`f95701cb35c609ad3cf8b0ed75323ad4eb9940171e72b1a20b29f58124f5a02f`、doctorは
`ok / 0.28.15 / packaged=true`。次はPR merge、正式v0.28.15公開/標準update、installed保存競合の再実測、
LLM負荷終了後の画像生成・採用と長時間detached Job。live rollback fault injectionは **NOT TESTED**。

## 2026-09-06 3DS-8 opaque iframe CORS authority

branch `ux1/3d-web-client-cors-header`。PR #242はmerge commit
`0fbed474262111836fa1bd25b2ca19a41a74aef2`でmergedし、正式v0.28.13を公開・標準updateした。正式bundleは
31,617,052 B / SHA-256 `57be1e3fb1b740515cb40f40ec1f09d67a2ac4444c40051699e098b014e43c8a`、公開再取得hash一致。
updateは10.54秒 / 最大RSS 788,980 KiB、health healthy。

credentialed loaderで認証は通ったが、Media Forgeの`Access-Control-Allow-Origin: *`とHostがopaque frameへ付ける
`Access-Control-Allow-Origin: null`が同じresponseに残り、Chromeが`multiple values '*, null'`で拒否した。
private noVNC/loader routeからorigin authorityを除き、利用者認証とframe originを知るHostだけにCORS判断を任せる。
standaloneはsame-originのため追加header不要。版は0.28.14。focused Media Forge群とHost opaque subresource回帰1件は
PASS。exact head `./mf.sh test`は979件 / warning 1件 / 99.40秒PASS。candidate bundleは31,619,226 B / SHA-256
`17a28d98ffe8cd3afaf71b8b8e66aea902675f423708db00602b45f366d7ab42`、展開binary doctorは
`ok / 0.28.14 / packaged=true`。PR/release/installed再実測は未実施。

## 2026-09-06 3DS-8 opaque iframe noVNC module loading

branch `ux1/3d-web-client-cors`。正式v0.28.12を実ControlDeckへ標準updateし、10.56秒 / 最大RSS
788,948 KiB、`current=0.28.12`、旧0.28.11保持、新PID 2174325、health healthyを確認した。owner修正後の
installed browserはAgent作成sceneを取得でき、Blender sessionも`ready`、TigerVNC/Blender process稼働まで進んだ。
しかしopaque origin `null`からのnative `import()`はHost frame cookieを送らず、noVNC `rfb.js`が401/CORSで拒否された。
consoleは`No 'Access-Control-Allow-Origin' header`、画面はreconnect表示。sessionは明示stopした。

noVNC module graphを`crossorigin=use-credentials`の外部module entrypointから遅延ロードし、opaque iframeでもHostの
frame cookieを全依存へ送るよう変更した。loaderは同梱固定fileで、既存のmanifest-pinned noVNC routeだけをimportする。
公開API/contributionは変更しない。版は0.28.13。focused frontend/Blender web/release bundle群はPASS。
exact head `./mf.sh test`は979件 / warning 1件 / 99.39秒PASS。candidate bundleは31,619,516 B / SHA-256
`55d567cb14dcad501730b0ae3e9c7b11953292c756255c167bbeccb4ab25e624`、展開binary doctorは
`ok / 0.28.13 / packaged=true`。PR/release、installed browser再実測は未実施。

## 2026-09-06 3DS-8 stable scene owner

branch `ux1/3d-stable-scene-owner`。PR #239（model schema）とPR #240（pack schema）はmerge済み。
正式v0.28.11 bundleは31,618,928 B / SHA-256
`fc1ce4c04d26a29a68ca0a9e527eba6d0786de017629d5cb9f82b73783d9a1f8`で、公開再取得hash一致、標準update
10.54秒、installed health healthy。実OpenCode 1.18.27 / Qwen3.8-27Bはscene create、durable status、snapshot、
GLB export、project grantへの`media.pack`を完走した。scene
`scene_ca920fd634b14dfea8215567e930bb7a`はobjects 4 / meshes 4 / vertices 126 / triangles 236、GLBは20,256 B /
SHA-256 `2afac7d44d23335cc31776bb8036ac63b957fc1f4b5a292df73d4c8ead8791ad`、配置receiptはcommitted。

続くinstalled opaque iframe実測では、UIの`scenes.list`が空を返した。SQLiteの同scene ownerは`user:16`だが、
workspace scene/working/backup/Blender session/RFB routeが短命browser tokenの`subject`をownerに使い、Agent routeだけが
stable `actor_subject`を使っていたことを特定した。3D永続資産routeを既存`scene_owner()`へ統一し、同じactorの
user/job token間共有と別actor隔離を回帰化中。preferencesは従来どおりtoken subject単位。版は0.28.12。
focused scene/workspace/backup/Blender/Host transport群はPASS。exact head `./mf.sh test`は979件 / warning 1件 /
100.56秒PASS。0.28.12 candidate bundleは31,618,636 B /
SHA-256 `e4a7b1963e2d81e75055a45b8d843708758a0bc54642fab0e147f0226b6a946e`、展開binary doctorは
`ok / 0.28.12 / packaged=true`。PR、正式release、installed再実測は未実施。


## 2026-09-06 3DS-8 OpenCode model-schema compatibility

branch `ux1/3d-opencode-schema`。正式 v0.28.9 を実ControlDeckへ標準updateし、実OpenCode 1.18.27 /
Qwen3.8-27Bへ全Add-on toolを渡したところ、制作開始前に
`JSON schema conversion failed: Unsupported ref: scene-texture-request.json` を実測した。原因は
`media.generate` の公開 `job-request.json` が3DS-6bで追加したscene texture contextだけを外部file `$ref` にし、
個別schema/API検証は通る一方、Hostのmodel-facing schemaとllama.cpp制約decodeへ解決されない参照を渡したこと。

公開fieldや意味は変えず、同じ定義を `job-request.json#/$defs/sceneTextureRequest` に内包してlocal `$ref` にした。
全agent tool schemaに外部 `$ref` が無いことと、scene texture付きjob全体をDraft 2020-12で検証する回帰を追加。
focused contract/baseline/agent 23件、exact head full 978件 / warning 1件 / 99.02秒はPASS。版は0.28.10。
exact 0.28.10 bundleは31,618,956 B / SHA-256
`00cfb8011802ccdb55341ef5845e6a3e1507394e616d004017f6e03d22c636c2`、展開binary doctorは
`ok / 0.28.10 / packaged=true`。正式署名bundle、installed update、同じOpenCode制作一巡はこのsliceの残りで
再実測する。3DS-8のopaque iframe/GPU共存/long-lived/rollbackは **NOT TESTED**。

## 2026-09-06 3DS-7 typed Agent recipes

branch `ux1/3d-agent-recipes`。closed vocabularyのscene create/edit、既存MaterialBinding、snapshot/export、
owner-scoped durable status/cancelとworkflow `media.scene`を追加した。create/edit/materialはHostの
`detached=true` child Jobと短命credentialを使い、refresh、Host/local cancel、Blender slot待ち中cancel、
shutdown終端同期を行う。SQLiteはtokenを保存せず、exact input/hash/runtime/base/stage/result/retry/outboxを保持する。
restart時はcredentialを捏造せずfail-closed。既存画像/G8/public `JobRequest`は変更していない。版は0.28.9。

per-call `job:` subjectを跨ぐownerには、別ControlDeck PR #270で追加しmerged済みのsigned optional
`actor_subject`だけを使う。Host focused 27 passed、merge commit
`1c611d6d05d3e90a8b1b07073c9f93c7087faad1`。Host fullの935 passed / 1 skippedに残った5件は共有DBとGPU sensorの
既存order-dependent failureで、focused変更範囲はgreen。

実Blender managerのcreate→edit→materialは3 Job succeeded、revision 3、最終`.blend` 501,758 B、GLB
62,136 B、triangles 644、texture dependency/provenance、両validator passed。closed vocabulary全10操作も
0.22秒、507,364 B、stable object 6件、autoexec disabledで通した。final fullは977 passed / warning 1件 /
96.24秒。0.28.9 exact bundleは31,619,208 B / SHA-256
`ec24a51465e952929239f822ac7f33f971ee5d7230ef3f91527884edea9d3c07`、doctor成功。exact package processは
scene/job 7 route、workflow 1 route、schema 7件を配信した。

実installed ControlDeck/OpenCodeの指示→shape→texture→GLB→grant配置、opaque iframe、120秒超job、10分超refresh、
restart/update/rollbackは **NOT TESTED**。次は別sliceの3DS-8 release acceptance。

## 2026-09-06 3DS-6c revision compare/restore

branch `ux1/3d-revision-restore`。旧版/currentのGLBを各64 MiB上限のprivate handle/chunkで同時表示する比較dialogと、
両preview ready後だけ有効になる明示復元を追加した。backendはscene ID、期待current、旧revisionだけを受け、
旧`.blend`/GLB/dependencyをsize/hash再検査して新Asset/provenanceへexact cloneする。currentを巻き戻さず、現currentを
parentとする新しいimmutable revisionをcommitする。競合/current自身/missing/tamperはfail-closed。版は0.28.8。

source Uvicorn + 実Chromeは材質dependency 1件の旧版をrevision 5→6へ復元し、比較0.126秒、復元0.069秒。
`.blend` 459,632 B / SHA-256 `6e2aca40cfbe90a9ebdfbf10948c52cc0aca3de2aa49aade57971bfae1a58054`、
GLB 18,600 B / SHA-256 `cc354349853152769a41aa3452321f51da35c4af65047d85f841c9771bb19405`は
復元元とbyte一致し、新Asset ID/provenance、linear parent、dependency保持を確認した。Blender 4.5.9と独立GLB
validator passed、日英、390px overflow 0、browser error 0。

final full testは963 passed / 既知Starlette warning 1件 / 95.87秒。0.28.8 exact bundleは31,570,669 B /
SHA-256 `672533021c2170d9233ac56892381ec52b63f81d2ac02371897dfe2b20920f87`、doctor成功。exact package +
実Chromeもdependency 1件をrevision 8→9へ復元し、比較0.129秒、復元0.075秒、desktop/390pxの2画面WebGL、
overflow 0、console/page error 0、両validator passed。実ControlDeck opaque iframeは **NOT TESTED** で3DS-8へ残す。
3DS-6 exit条件はsource/packageで完了。次は別sliceの3DS-7 typed Agent recipes。

## 2026-09-06 3DS-6b texture generation orchestration

branch `ux1/3d-texture-generation`。既存durable `image.generate`へ
`media-forge.scene-texture-request@1`のscene/source revision/object/material slot/channel/UV文脈を加法追加した。
job成功は通常のimmutable Library Assetを作るだけでsceneを変更しない。3D Studioは通常Createとは別に
reload後の進捗復元、cancel、同一文脈retry、bounded preview、明示選択を行い、既存MaterialBindingの保存を
押したときだけ新revisionへcommitする。`disable.pending`は実行中texture jobをcancelする。版は0.28.7。

source Uvicorn、決定的image worker、実Blender 4.5.9、実Chromeでreload→cancel→retry→preview→選択→commitを
通し、revision 1→2、生成PNG 1,024x1,024 / 23,489 B / SHA-256
`bc5228bec807cab277aa591bce8c746c5c6313fd3708c7c4287db13744f1823a`、dependency 1、external images 0、
GLB 18,600 B / textures 1、両validator passed。日英、390px overflow 0、console/page error 0。
実測でimport後controls再描画、reload後poll再接続、exact-context retry、選択後form復元、420px未満header overflowを
検出して修正した。

final full testは960 passed / 既知Starlette warning 1件 / 94.96秒。0.28.7 exact bundleは31,565,375 B /
SHA-256 `653caa562b7f86d4f27577927f1949fac03c59f0035eb9477546323ed9c83423`、doctor成功。最初のpackaged実測で
frozen executableがfake workerの`-m` argvを処理できずexit 2となる不具合を検出し、exact internal dispatchと
release regression testを追加してbundleを再構築した。最終exact packageの実Chromeも全工程を通し、revision 1→2、
`.blend` 459,632 B、GLB 18,600 B、validator passed、390px overflow 0、browser error 0。

exact sourceからの実R9700 standalone要求は37 msで`host_lease_required`となりbroker外実行をfail-closedにした。
稼働ControlDeckはcommit `34bda2f14c2c00e4ead8251bf30d830b2e3bf7a5`、既存dirty
`frontend/tsconfig.tsbuildinfo`だけ、installed 0.28.0 / PID 1827940 / health healthy。保存済みbrowser認証が
`/login`へ戻ったためHost-managed R9700とopaque iframeは **NOT TESTED**。前後版比較と旧版からのcurrent復元も
**NOT IMPLEMENTED / NOT TESTED**。次は別sliceの3DS-6c revision compare/restore。

## 2026-09-06 3DS-6a existing Library image material binding

branch `ux1/3d-texture-binding`。source revision、Library画像Asset、object/material slot、5 channel、UV、
wrap、色空間、normal conventionを持つ型付きMaterialBindingとtrusted Blender workerを追加した。
private Host/standalone経路と日英UIはpath/任意Pythonを受けず、画像identityとsource revision競合を
fail-closed検査する。適用結果は画像をpackした新しいimmutable scene revision、GLB preview、dependency、
`scene.material.bind` provenanceになる。版は0.28.6。

実Blender 4.5.9でbase color / roughness / metallic / DirectX normal / emissionを各0.701〜0.770秒で適用し、
revision 7→12、依存5件、external images 0、Blender/GLB validator passed。実Chromeはtarget 3件、Library画像、
roughness適用revision 8→9、日英、390x844単一列、exception 0を確認した。stale revisionは1.964 msで
`scene_revision_conflict`。full testは957 passed / 1 warning / 93.63秒。

0.28.6 exact bundleは31,554,828 B / SHA-256
`b03135ac28483fe93c4cdaf2744acbecb32a3a555fdf1a0f1948fc51b4b7cec9`、packaged doctor成功。exact packageも
実DirectX normalを0.712秒でrevision 7→8へ適用し、836,127 B `.blend`、external images 0、両validator
passed、終了後active working/material staging 0。新規画像生成・編集からの採用、前後版比較/旧版採用、
実ControlDeck opaque iframeは **NOT IMPLEMENTED / NOT TESTED**。次は3DS-6b texture generation。

## 2026-09-06 3DS-5d session lifecycle / recovery

PR #234、branch `ux1/3d-session-recovery`、実装commit `746bc12`。既定の切断猶予300秒、controller idle 1,800秒、bounded server設定、
input activityの書込throttleを追加した。timeout、実unit crash、Host disable/revokeはsessionをinterruptedにし、
unit/root/socketを回収してworking bytesを未検証のowner-scoped復旧候補として残す。復旧候補は新writerへcopyし、
Blender/GLB検証とrevision commit成功後だけ旧候補をreleasedにして削除する。UIはfresh editと復旧を分け、
日英の終了理由を表示する。版は0.28.5。

実Blender/Xvncの2秒切断猶予はreadyから5.270秒でinterrupted、515,688 B / SHA-256
`7afe139e407c33711b12e0989cf5492ed5294580535e809509ed76b969a43ee1`を候補に保持した。候補からのsaveは
revision 6→7、working 515,496 B / SHA-256
`cddc910ddfe056542990e0d669d240f1bddbbc0642da75724c215e597d270d6d`、両validator passed、旧root 0。
別sessionのSIGKILLはrunner_lost / recoveryとなり、unit/root/socket/process 0。Host disable相当interruptは
受付2.397 ms、終端まで91.9 ms、resource 0。実Chromeはdesktop日英、390x844案内、横scroll 0、exception 0。
focused testは全件通過し、fullは952 passed / 1 warning / 91.17秒。
0.28.5 exact bundleは31,509,192 B / SHA-256
`352efcfbf6f7ee3566ec530ea01ee7b76534c8bbe397d346bed0f72907d65693`、packaged doctor成功。exact packageの
実Blender sessionもready→private interrupt→interrupted/recoveryとなり、受付2.780 ms、残存resource 0。

実ControlDeck opaque iframe、10分超credential rotation、実Host revoke、GPU/Cycles、packaged Chromeは
**NOT TESTED**。次は別sliceの3DS-6 material binding。

## 2026-09-06 3DS-5c authenticated RFB gateway / noVNC

PR #233、branch `ux1/3d-session-gateway`、実装commit `72db176` + cache identity修正`f94ab59`。private Host/standalone WebSocketからsession所有のUnix RFB socketへ
binaryだけを中継し、owner照合、READY/実unit/実socket再確認、全体1 controller、browser message 1 MiB
上限を強制した。Host経路は既存service tokenを15秒ごとに再introspectionし、subjectが変わるか無効なら切断する。
standaloneは同一loopback Originと`binary` subprotocolを必須にした。socket/path/PID/unit/display/tokenはbrowserへ
返さない。noVNC 1.7.0の実行依存JS 54 files / 579,832 Bをすべてmanifest SHA-256へ追加し、manifest掲載済み
moduleだけをhash再検査してopaque iframe向けCORSで配信する。版は0.28.4。

隔離data rootのsource Uvicorn `127.0.0.1:9181`と実Chromeで、1280x720 noVNC framebufferへの接続、
「表示だけ閉じる」後もsession ready、2本目の1280x720再接続、browser側noVNC入力によるAdd Cube、保存を実測した。
revision 5→6、working `.blend` 515,688 B / SHA-256
`7afe139e407c33711b12e0989cf5492ed5294580535e809509ed76b969a43ee1`、objects 4→5、meshes 2→3、
triangles 24→36、vertices 16→24、Blender/GLB validator passed、browser exception 0。停止後unit/socket/
Xvnc/Blender process 0。focused gateway/frontendは全件通過し、fullは943 passed / 1 warning / 89.66秒。

`./mf.sh bundle build 0.28.4`は31,503,501 B / SHA-256
`9c1644a40962cf742f5f884203d0d2918d4bee0b195f0db515c82944cbfc9089`、展開binary doctorは
`ok / 0.28.4 / packaged=true`。exact candidate rootはfingerprint付き`rfb.js?v=...` importを配信し、候補processでも
`rfb.js` hash一致、同じgateway実装の実GUIへの`binary` / `RFB 003.008`
gateway応答14.337 ms、切断後ready、明示discard後stopped、残存process/socket 0。

実ControlDeck opaque iframe、10分超token rotation、Host revoke/disable、idle/crash/recovery policy、GPU/Cycles、
packaged Chromeは **NOT TESTED**。ControlDeck source/service/installed files変更0で、稼働installedは0.28.0 /
healthy、既存`frontend/tsconfig.tsbuildinfo`だけdirty。次は別sliceの3DS-5d session recovery。

## 2026-09-06 3DS-5b isolated Blender GUI runner

branch `ux1/3d-web-blender-runner`。durable `blender_sessions`、全体1件/single-writer排他、
systemd user transient unit、Unix-only Xvnc、Blender 4.5.9 GUI bootstrap、明示save/discard、再起動時の
ready unit再接続、失敗時recovery working copyを実装した。private session/WS/standalone入力はScene IDか
session IDだけで、path/PID/unit/socket/display番号を返さない。software GUIはWaylandとGPU visibilityを
無効化し、Mesa Lavapipe/Vulkan、autoexec無効をready条件にした。systemd mount保護が追加`/data1tb`への
書込を拒否しない実測を受け、Blender子孫へLandlock ABI 3以上の3-root write allowlistを必須化した。版は0.28.3。

sourceのLandlock導入probeは0.584秒でready、実RFB 1280x720、unit Memory 540.6 MiB / peak 571.4 MiB / 94 tasks、
TCP RFB listener 0。Landlock外部writeはerrno 13、AF_INETはerrno 97、Blender childはNoNewPrivs 1 / seccomp 2。
exact候補bundleでも434,663 B `.blend`をimportし、commit開始からGUI readyまで1.019088秒、click + Shift+D + Enter、
save/stop 0.732258秒。510,540 B / SHA-256
`cdb4c7061e8b8490dae51f910bc59b28cafc221ade00a6ba65719d34cc428bdb`へ保存され、revision 1→2、
objects 3→4、meshes 1→2、triangles 12→24、vertices 8→16、unit/socket/process 0を確認した。
bundleは31,489,331 B / SHA-256
`d345481457c0f4bce16d00b564c4c940d3e26f81956b80cdf6da9c4f76c50769`、doctorは0.28.3 / packaged=true。
focused session 8件とfullは936 passed / 1 warning / 88.01秒。

認証付きRFB gateway/noVNC browser、接続heartbeat/再接続/idle、disable/revocation、実ControlDeck opaque
iframe、GPU/Cyclesは **NOT IMPLEMENTED / NOT TESTED**。稼働ControlDeckは0.28.0 / healthyのまま、
source/service/installed files変更0（既存`frontend/tsconfig.tsbuildinfo`だけdirty）。次は別sliceの
3DS-5c RFB gateway/noVNC。

## 2026-09-06 3DS-5a Web Blender pack manager

branch `ux1/3d-web-blender-session`。TigerVNC 1.16.2とnoVNC 1.7.0を公式URL、archive size/SHA-256、
展開root、必須file hash、licenseで固定した別packとして追加した。既存Blender operation journalを再利用し、
明示download、Range/ETag再開、cancel、archive境界、atomic no-replace publish、実行probe、path-free status、
Settings/WS/standalone/`mf.sh blender web-install`を実装した。版は0.28.2。

隔離data rootの実Uvicornで公式15,769,716 Bを6.153秒で導入し、283 files / 37,539,247 B、staging 0。
Xvncを1280x720 software displayとしてloopback限定で起動し、RFB 3.8 banner 2.207 ms、停止後process 0。
実Chrome/packaged Chromeはready・両license・15.0 MBを表示し、320px client/scroll 320、browser error 0。
bundleは31,447,404 B / SHA-256
`04d28d0293dc249d1c2dc42e328d2ccf379d7ed184782d334dd0f37328f16759`、doctorは0.28.2 / packaged=true、
fullは928 passed / 1 warning / 82.35秒。

session runner、Blender GUI保存、RFB gateway/noVNC、再接続・idle・disable/revocation、実ControlDeck
opaque iframe、GPU GUIは **NOT IMPLEMENTED / NOT TESTED**。ControlDeckは変更0。PR/merge後は
別sliceの3DS-5b session runnerへ進む。

## 2026-09-06 3DS-4c browser backup / restore UI

PR #230、branch `ux1/3d-scene-backup-ui`、実装commit `de0cd4e`。3DS-4c private transportを使い、選択sceneのbackupを512 KiBずつ
読みながらSHA-256を再計算して`.zip`保存し、復元fileも全体SHA-256をincremental計算して512 KiBずつ
送るUIを追加した。2 GiB上限、download/restore/importの相互排他、cancel、`disable.pending`、日英、
standalone mirrorを扱い、pathはbrowserとの契約へ追加していない。版は0.28.1。

実Chrome/sourceで実Blender由来2 revision sceneを1,225,331 B、packaged 0.28.1で1,225,378 BのZIPとして
各3 chunkで保存・復元した。sourceはdownload 0.220815秒 / restore 0.175584秒、packageは0.222907秒 /
0.192467秒。両runで復元revision 2、cancel後scene増分0、transfer staging 0、console/page error 0。
320pxはscroll/clientとも320、単一列。packageは31,429,467 B、SHA-256
`25486a75002e70641e26318b4df9dfa14eb16e945f4994359288501c9499c2ef`、doctorは0.28.1 / packaged=true。
fullは921 passed / 1 warning / 83.09秒。

稼働ControlDeckはinstalled 0.28.0 / healthy。既存browser sessionの一時copyはloginへ遷移したため、
0.28.1 installed opaque iframeは **NOT TESTED**。一時profileはtrashへ退避し、ControlDeck source/service/
installed filesは変更0。PR/merge後は3DS-5 Web Blender、installed releaseは3DS-8で通し確認する。

## 2026-09-05 3DS-4c private backup transport

PR #229、branch `ux1/3d-scene-backup-transport`、実装commit `d159731`。認証WSとstandalone private mirrorへ
backup open/read/close、restore begin/chunk/commit/cancelを追加した。connection-scoped各1件、512 KiB、
10分activity TTL、chunk/total SHAとoffsetを強制し、切断/shutdownでstagingを回収する。公開契約変更0。

実Uvicornで実Blender由来2 revisionを1,225,070 Bへexportし、download/upload各3 chunkでscene 1→2へ
restore。open 0.120567秒、upload+commit 0.045491秒、最大JSON 699,218 B、path field 0、cancel後/停止後
staging 0。初回実測で1 MiB誤配線を検出し512 KiBへ修正・契約test追加済み。fullは920 passed / 1 warning /
85.02秒。隔離起動で生じた983 MiB部分runtimeはtrashへ退避し、元checkout/service変更0。

browser/package/実ControlDeckは **NOT IMPLEMENTED / NOT TESTED**、ControlDeck変更0。次は別PRで
backup/restore browser UIを実装する。

## 2026-09-05 3DS-4c exact scene backup core

PR #228、branch `ux1/3d-scene-backup`、実装commit `175ea31`。`media-forge.scene-backup@1`の固定entry順、
manifest/entry size・SHA-256、member/展開量/path/link/device/重複検証と、全Asset/revisionを新ID・新sceneへ
atomic restoreするcoreを実装した。no-replace file publishとtransaction rollbackにより、tamper/途中失敗/
同時衝突は既存fileを上書きせず追加0件になる。

実Blender 4.5.9由来の2 revision（`.blend`各1,247,112 B、GLB各1,138,160 B）を1,225,068 Bへ
export 0.113988秒、別ownerへrestore 0.018701秒。全member hashと復元byte一致、旧scene不変、owner分離、
staging 0。1 byte改ざんは`scene_backup_hash_changed`、全DB追加0件。fullは916 passed / 1 warning / 77.71秒。

private transport/browser/package/実ControlDeckは **NOT IMPLEMENTED / NOT TESTED**、ControlDeck変更0。
次は別PRでowner-scoped backup upload/download transportとbrowser UIを実装する。

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
