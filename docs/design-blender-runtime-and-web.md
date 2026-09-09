# Blender環境管理とサーバーGUIのブラウザ操作

Status: 3DS-2 runtime lifecycle・3DS-5a Web pack・3DS-5b GUI runner実装済み / RFB gateway未実装
Date: 2026-09-06
上位設計: [統合3D Studio](design-3d-studio.md)

## 1. Web Blenderの定義

サーバーに導入したBlenderの通常GUIを専用セッションで実行し、その画面と入力をブラウザへ接続する。
ブラウザ内でBlenderをWASM実行する構成ではない。GLBビューワーとは別機能である。

初期候補は **noVNC + WebSocket/VNC relay + 専用仮想display + Blender**。
noVNCがVNCをWebSocketで扱う点は[公式説明](https://novnc.com/)を参照。
実装前にnoVNCの固定revision、VNC server、display方式、配布条件を互換性表へ記録する。
RFBのbinary streamを既存workspace JSON `/ws`へ混ぜず、専用session pathをHost proxyで中継する。

## 2. 管理対象と所有権

| 管理対象 | 管理者 | 設定からの操作 |
|---|---|---|
| MediaForge軽量bundle | ControlDeck Feature lifecycle | 導入・更新・rollback・削除 |
| Blender基本環境 | MediaForge runtime manager | 導入・検証・更新・切替・修復・削除 |
| Web操作pack | MediaForge runtime manager | 導入・診断・更新・削除 |
| GPU driver / kernel / system package | OS管理者 | 不足診断と手順提示。暗黙のsudoや更新をしない |
| 外部登録Blender | 外部管理者 | 診断・登録解除。実体の更新・削除をしない |
| 制作物・画像・履歴 | 利用者 | Library経由の版管理・書き出し・ごみ箱 |

ManagedとExternalを実体・DBの両方で区別する。画面入力から任意URL、実行ファイル、shell commandを
受け取らない。External登録は権限付きのサーバー設定経路で検証し、通常画面にはopaque runtime IDを返す。
OSで導入したBlenderや他アドオンのruntimeを、勝手にScene用として管理下へ移さない。

既存の固定4.5.9 legacy参照についても「実体削除」と「登録解除」を分ける。
解除はregistryから参照を外し、同じatomic registry更新に自動登録抑止を記録する。
status/startupによる再検出では復活させず、明示的な再登録だけで抑止を解除する。
再登録は現在の設定先とstamp/manifestを再検証し、不正なら抑止を保持する。
実行参照・active・project pinの既定の保護はmanagedと同様に維持する。
§4.1の履歴参照確認付き実体削除はmanagedだけに適用し、外部登録解除の権限を拡大しない。
resolverはlive/activeを保護し、設定orchestratorがproject pinと確認fingerprintを保護する。
これはサーバー設定で指定済みの固定legacy実体の操作であり、ブラウザから任意pathを受けない。
registryの加法的private field `legacy_registration_disabled` は省略時false。
旧coreは未知fieldをfail-closedで拒否するため、解除後に旧coreへrollbackする場合は
runtime registryの事前snapshotも復元する。外部Blender実体にはmigrationを行わない。

## 3. runtime配置と既存G8の移行

提案する永続配置（既存Host Featureのdata/cache環境変数を優先）:

| 場所 | 内容 |
|---|---|
| MediaForge data / runtimes / blender / version-platform-arch | immutableなBlender展開先 |
| data / runtime-state | 所有権、catalog、fingerprint、active版、参照、operation journal |
| data / scenes | 制作working copy、autosave、recovery |
| data / assets | 既存immutable asset store。3Dも同じstore |
| data / sessions | session ID、runner識別子、display、lock、期限。秘密値は別保護領域 |
| cache / downloads | 検証前partialと再取得可能cache |
| source / worker_packs / blender | trusted処理スクリプトとpack metadata |

既存実装は `runtimes/blender-4.5.9` と `config/blender-runtime.json` を使う。
`blender_compile.py`にも固定配置参照があるため、UIだけ作って複数版を選べると主張しない。
最初にruntime resolverを追加し、G8の固定互換profileが要求する版を解決できるようにする。

移行手順:

1. 現行runtime stamp、実行version、hash、所有権を読み取り専用で調査。
2. 正常な既存runtimeをlegacy参照として登録。初回から削除・移動・再downloadしない。
3. persistent rootへ移す場合は別の明示operationでstaging copy、検証、参照切替を行う。
4. legacy移行元の旧場所は参照とrollback依存がゼロになるまで保持。
   移行後のmanaged版に対する利用者の明示削除は§4.1に従う。
5. 既存 `./mf.sh blender build/status` とG8既定profileの互換テストを維持。

新しいBlender版をactiveにしても既存G8 profileのcompiler契約を無条件で変更しない。
制作sessionは起動時にruntime IDとversionを固定し、実行中の参照を差し替えない。

## 4. 設定の操作仕様

| 操作 | 動作 | 失敗・競合時 |
|---|---|---|
| 導入 | trusted catalogからexact versionを選び容量確認、download、hash、展開、probe | partial/journalを保持して再開。現在版は維持 |
| 更新確認 | catalogとの差分を表示。自動適用しない | offlineでも導入済み環境が使える |
| 更新 | 新版を隣にstageしprobe後、次回起動の既定に切替 | 稼働job/sessionは旧版のまま |
| 切替 | 検証済み版を既定へ。project pinを尊重 | 不適合版は理由を表示 |
| 修復 | 破損の検証後、同じ版を別stagingで再構築 | 元の制作物は変更しない |
| 削除 | managed runtimeの参照と容量を表示し確認後に対象だけ削除 | 稼働参照ありは拒否。停止後に再試行 |
| cache整理 | 再取得可能cacheだけを整理 | runtime/asset/recoveryを含めない |

初期セットアップは「Blender基本環境」と「ブラウザ操作環境」を別packにする。
「Web Blenderを使う」で両者の必要分を一度に計画できる。画像モデルの全導入を要求しない。
重いBlender downloadを通常のMediaForge起動やbundle更新で暗黙実行しない。
UIと `mf.sh` のCLIサブコマンドは同じorchestratorを呼ぶ。doctor/statusは読み取り専用。
`blender install/update/switch/repair/remove` CLIは稼働中MediaForgeの同じorchestratorを呼び、
READMEへ正式掲載する。source runtime互換用の既存`blender build/status`は変更しない。

### 4.1 停止済み版の削除と履歴の保持（実装目標）

scenario Dは停止後に旧版Aだけを削除し、画像・scene・.blend・履歴の保持を要求する。
0.28.34のproject_referenceは全scene_revisionsを数えるため、単にGUIを止めるだけでは
永続的に削除できない。履歴削除や別版へのpin書換えでこの受入を通してはならない。

- 既定のremoveはproject参照があれば拒否する。既存クライアントの保護を維持する。
- 稼働・待機参照がゼロ、inactive、managed、正確な版の再導入が可能な場合だけ、
  「制作ファイルと履歴は残ります。再編集にはBlender X.Y.Zの再導入が必要です」の
  追加確認を出す。チェックは既定offで、確認なしの送信をbackendでも拒否する。
- private remove入力に任意boolの履歴参照確認を追加する。既定false、bool以外は拒否。
  previewのfingerprintに参照状態・確認対象版・再導入可能性を束縛し、実行直前にも再検査する。
  durable operationに確認内容を保持し、restart時に確認なしの別削除へ読み替えない。
- active版、未終端Job、GUIのqueued/preparing/starting/ready/saving/stopping、
  active working copy、in-process処理の参照は追加確認でも解除できない。
  GUIのruntime_idが未確定な準備中も対象scene/recoveryのpinから保護する。
- Job受付とruntime削除の競合も保護する。Host child作成を待っている間にpinを失わず、
  受付後から終端・process回収まで参照を持つ。終了フラグだけで実processの参照を外さない。
- runtimeのみを既存staging/remove機構で削除する。scene/revision/dependency/asset/provenanceや
  recipeの保存済みruntime_idを変更しない。別のactive版を自動適用しない。
- Libraryの画像・GLB表示、履歴閲覧、制作ファイルbackupは残す。編集・復元などBlenderが
  必要な操作は正しい版の再導入を案内し、不在をavailableと表示しない。
- 設定からtrusted catalogの同一版・同一archive identityを明示再導入できることを確認する。
  現在の推奨版への更新で代用しない。再導入経路がない版は確認付き削除を提供しない。

実装順: durable参照集計と受付/削除の排他 → 同期DB/filesystem処理のworker-thread化 →
追加確認付きoperation/再開 → 日英UIと正確な版の再導入導線 → 同一scene実機削除/再導入。
DB/ORM/同期subprocess待機をasync requestに追加しない。threadの開始済みatomic操作は
接続切断で放棄せず終端まで追跡する。参照lockをevent loop上で保持したまま別threadの
同lock取得を待つ構成を作らない。

設計選択の根拠: 履歴参照を永久拒否する案はscenario Dを満たさず、履歴削除はGOAL-07を壊す。
別版への自動pin変更は再現性とimmutable revisionを壊す。明示確認と同版再導入で双方を維持する。
現時点ではこの確認付き削除は未実装。0.28.34の拒否動作をこの機能の受入とは扱わない。

受付保護の先行実装: SceneWorkspace.acquire_recipe_runtimeがworker thread内で
版選択と参照取得を削除guardと排他に行う。SceneRecipeJobManagerがHost child受付待ち、
実行slot待ち、処理と取消cleanupの終端まで同じin-process参照を所有する。
stopは受付taskも回収し、wait_cleanupは参照解放まで待つ。
durable集計の先行実装はStore.active_scene_runtime_referencesで、未終端recipe Job、
active working copy、稼働GUIを同じDB snapshotから読む。GUIのruntime未確定時は
working/recoveryのpin、未指定ならscene current revisionを参照し、不明なら全版の削除を拒否する。
既存live_reference_countはin-processとdurable参照の合計、内訳をprivate previewへ追加する。
期限超過だけではworking copyの参照を外さず、正式なretireを待つ。
managed削除のpreview/受付/実行はworker threadでDB/filesystem処理を行い、開始済みthreadを
request取消で放棄しない。
GUI受付も同じresolver guard内でruntime ID/versionを確定しqueued recordへ保存する。
通常/復旧working-copy作成は版検査からcopy/DB lease確定まで同guardで排他にする。
全production callerはworker threadの取得をawaitし、取消なら新規copy/leaseを回収する。
GUI停止/中断は前の準備taskのcleanupを待つ。queuedのpinと異なる版へ準備中に変わった場合は
fail-closedにする。削除済み版への新規GUI受付は事前に拒否する。
確認付き削除と、その実削除commitを伴う同時開始/再導入の受入は引き続き残件である。

## 5. durable setup operation

提案状態: queued → preflight → downloading → verifying → installing → probing → ready。
終端: failed / canceled。削除はdeletingを経由する。操作IDを先に永続化してから副作用を始める。
既存model operationのjournal/watch/cancelの設計を再利用し、Blender固有policyはruntime adapterへ置く。
画像モデルのstate enumを必要なく変更せず、operation型を区別する。

- version単位の排他lock。重複要求はidempotency keyで同じoperationへ結び付ける。
- 既定版の切替とDB更新はjournal付きで復旧可能にし、中途状態を照合する。
- download再開はサーバーのRange/ETag一致を確認。不一致ならpartialを再利用しない。
- archiveはsize/hash、展開size/member数、path traversal、symlink、device/FIFOを検証。
- probeはversion、background処理、GLB再入出力、GUI起動を別々に記録。
- CPU基本機能はGPU/ROCm不在でも診断できる。HIP/Cycles対応は別probe。
- UI再読込や切断でsetupを消さない。cancelは所有runnerへ伝達しstagingだけを片付ける。
- 削除対象はmanaged rootのrealpath内に限定。live referenceとTOCTOUをlockで検証する。

## 6. session構成

```mermaid
flowchart TD
  UI["MediaForgeのWeb Blender画面"] --> Proxy["ControlDeck認証付きWS proxy"]
  Proxy --> Gateway["MediaForge session gateway"]
  Gateway --> VNC["session専用VNC server"]
  VNC --> Display["session専用display"]
  Display --> Blender["固定版Blender GUI"]
  Manager["durable session manager"] --> Gateway
  Manager --> Runner["systemd user runner"]
  Runner --> VNC
  Runner --> Blender
```

Blenderとdisplay/VNCはsession専用process group / cgroupでまとめる。
HostのWeb processやMediaForge HTTP requestの生存期間を寿命の基準にしない。
Linuxではsystemd user unitでrunnerを所有する。権限・隔離要件を満たすrunnerを先に検証する。
web APIがprocessを起動してすぐ忘れる方式や、個人の既存X11/Wayland sessionへの接続を採らない。

3DS-5bではtransient systemd user unitをdurable session IDへ固定し、`NoNewPrivileges`、
`PrivateNetwork`、`RestrictAddressFamilies=AF_UNIX`、memory/task上限を設定した。XvncはTCP RFBを
無効化したmode 0600のsession専用Unix socketだけを開く。追加mountに対するsystemdの
`ProtectSystem`/`ReadOnlyPaths`単独では書込を拒否できない実機結果だったため、Blender起動前に
Landlock ABI 3以上を必須とし、session control、scene working copy、RFB socketの3 root以外への
書込をkernelで拒否する。隔離を構成できなければsessionはfail-closedにする。Xvncは自身のX lockを
作る必要がある固定済みtrusted componentなのでLandlock適用前に起動し、利用者sceneを読むBlenderと
その子孫だけを追加のfilesystem sandboxへ入れる。

初期software displayはGPUなしでも接続・保存を検証できることを優先する。
Xvfb/VNCを起動しただけでGPUアクセラレーションが成立したとは記録しない。
GPU display/VirtualGL/EGL等は候補を実機比較し、OpenGLとCycles HIPの結果を別々に残す。
3DS-5bのsoftware sessionはWaylandを明示的に無効化し、固定X displayとsystem Mesa Lavapipe ICDだけを
使うVulkan GUIである。ready条件は`background=false`、autoexec無効、VULKAN backend、llvmpipe renderer、
実RFB socketの一致であり、GPU accelerationやCycles HIPをavailableとは扱わない。

## 7. session状態・再接続・排他

実装状態: queued → preparing → starting → ready → saving/stopping → stopped。
failed / interruptedは原因付き終端。disconnectedはRFB gatewayを追加する次sliceで接続状態として実装する。
3DS-5bはsession ID、owner、scene、working copy、runtime/Web pack pin、systemd unit ID、結果、時刻をDBへ保存する。
接続heartbeatと期限はgateway sliceで追加する。

初期policy（3DS-5bで実装済みの項目と、gateway以降で実装する項目を区別する）:

- 同時編集sessionは利用者1件、ホスト全体1件。上限拡大はRAM/VRAM実測後。
- 同一working sceneはsingle writer lock。二つ目のタブは閲覧または明示takeover。
- 接続断後10分猶予、入力なし30分で保存・終了を試行。期限をUIへ表示（未実装）。
- autosave間隔2分を目標、保存先を隔離working copyへ限定。
  2026-09-07 source実装: Blender timerで120秒ごとに同working directory内の
  一時directoryへcopy保存し、完了/header/fsync後にscene.blendをatomic replaceする。
  保存前の失敗は直前snapshotを保持する。通常の製品保存commandも同じ保存関数を使う。
  Blenderのmodal操作中などはtimerが遅延し得るため、120秒を上限保証とはしない。
  autosaveはimmutable Asset/revisionを作らず、正式版は引き続き明示保存・独立検証で確定する。
  Blender標準の一時autosave設定はsession内だけ無効化し、利用者の設定へ保存しない。
  保存失敗または180秒を超える結果通知欠落/停止はcoreが非同期thread読取で検知し、
  readyを保ちながら日英の警告をGUI dialog/scene欄へ表示する。次の成功で警告を解除する。
  書込障害で通知自体が失敗してもtimerを継続し、次intervalで再試行する。
  source実機と署名installed受入はimplementation-statusで分けて記録する。
- 保存後に独立した検証・asset commitでrevisionを確定。autosaveは正式版ではない。
- 終了時は入力停止→保存要求→最大30秒待機→process group終了→予約・lock回収。
- 保存に失敗した場合はrecovery copyと理由を保持し、「保存済み」と表示しない。
- Host disableの2秒以内応答では新規受付停止と終了開始を返す。大きい.blendの保存完了を2秒と偽らない。

ブラウザ切断はsessionをただちにkillしない（gateway sliceで実装する）。MediaForge再起動ではrunnerの生存とownershipを照合する。
Host再起動や認証失効時には新しい正規identityを得るまで編集再開しない。
終了したプロセスのPID再利用を避けるためunit IDと起動時刻も照合する。

## 8. 入力と通信

- 接続はHost HTTPS/WSS・opaque iframe bridgeを通す。loopback VNCをLANへ直接公開しない。
- gatewayはHost service tokenを検証し、session owner、権限、有効状態、期限を接続ごとに確認。
- ブラウザへHost bearerや長命VNC passwordを渡さない。接続情報をURL queryやログに残さない。
- noVNCのbinary subprotocolとHost nonce subprotocolの併用、Origin:null、長時間socketを実ブラウザ検証。
- 接続後の権限剥奪・disableも反映する。proxyのhandshake認証だけに頼らずgatewayで定期再検証・終了。
- 解像度、frame size、buffer、fps、帯域、接続数を上限付きにする。RFBを破損する任意byte破棄はしない。
- 遅い受信者には更新要求抑制・解像度/品質低下、回復不能なら再接続を使う。
- clipboard、共有ファイル転送は初期無効。必要時に明示操作・サイズ上限・権限を追加。
- キー解放をblur/disconnectで保証し、押しっぱなしを残さない。IME、JIS配列、wheel、修飾キーを検証。
- ファイル入出力はMediaForge Library/Host grantからscene working directoryへのstageで行う。

## 9. GPU予約と相互待ちの防止

CPU-only sessionはGPUを使わない設定と実測を確認する。GPUを使うGUIはidleでもVRAMを保持するため、
rendererを描いている瞬間だけ予約する方式は不可。GPU process存続期間に合うHost leaseを保有・更新する。
終了と解放を確認する前にleaseだけを返さない。GPU jobは `estimated_runtime_sec` を必ず申告する。

画像生成を要求したときにGUIのGPU保持で競合する場合:

1. 共存可能ならBrokerが両方をadmit。
2. 共存不能なら保存・GUI終了で実VRAMを解放し、画像工程へ移る。
3. 成果物確定後に固定版Blenderで再開する。利用者へ中断理由を表示。

CPU fallbackはその操作で検証済みの場合のみ。Cycles GPU未対応をhealthyとして通さない。
OpenCodeのLLM、画像worker、Blender batchを一つの長期leaseで囲まない。
既存G8のCPU-onlyパスへ不要なGPU leaseを追加しない。

## 10. 実装前の確認ゲート

現行ControlDeckにbinary WebSocket relayとCPU-only job credential refreshのコードは存在する。
ただしnoVNCを通した継続接続・権限取り消し・対象機GPU描画は未検証である。
不足があれば汎用Host transport/runnerの別PRとし、Media固有コードをcoreへ入れない。
正規の環境でOS隔離を構成できない場合は詳細理由を示し、Web操作だけをunavailableにする。
