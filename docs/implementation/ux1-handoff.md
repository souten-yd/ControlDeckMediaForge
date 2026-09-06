# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

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
