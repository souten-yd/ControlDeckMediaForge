# G8拡張 — 統合3D Studio 実装計画

Status: 3DS-0〜8 VERIFIED / 統合3D Studio初期提供完了
Date: 2026-09-06
設計の正: [3D Studio](../design-3d-studio.md)、base-plan、integration、workspace UX

## 0. この計画の位置づけ

既存G8 B0〜B5の成果を前提にする追加計画。過去の完了記録を新規Web Blenderの実績に読み替えない。
G9生成3Dモデル採用とは分離し、画像生成モデルの変更やSonicForge統合を前提にしない。
すべての変更はControlDeckMediaForgeで行う。必要な汎用Host変更だけ別PRにする。

## 1. 現状とギャップ

3DS-0の対象commit・fixture・実機互換性表は
[`3ds-compatibility.md`](3ds-compatibility.md) に固定した。
3DS-1は同表へruntime resolver、legacy登録、設定診断、G8同一hashの実測を追記した。
scene/revision/working copyへ進んだ。3DS-4a persistence、3DS-4b core/transport/browser UI、3DS-4c
exact backup core/private transport/browser UI、3DS-5a Web操作pack管理、3DS-5bの隔離GUI runner・
保存/終了まで完了した。installed ControlDeck opaque iframeでの再確認は3DS-8 release acceptanceへ残し、
3DS-5cで認証付きRFB gateway/noVNC接続・再接続、3DS-5dでidle、crash、Host disable/revocationと
復旧候補のpolicyと3DS-6aの既存Library画像から検証済みrevisionを作る材質bindingまで実装した。
3DS-6bはdurable image jobのscene文脈、reload復元、cancel/retry、preview、明示選択から既存
MaterialBinding commitまでをsource/packageで実装・確認した。3DS-6cは現行版/旧版の2画面比較と、旧版を
新しいimmutable current revisionへ復元する工程をsource/packageで確認し、3DS-6のexit条件を閉じた。
3DS-7はtyped Agent recipe、durable detached child Job、stable actor ownerをsource/packageで確認した。
3DS-8でinstalled-host/OpenCode/GPU/release acceptanceを完了した。Expert scriptは別capabilityの3DS-Xであり、
初期提供の完了条件には含めない。

| 項目 | 調査で確認した現状 | 追加するもの |
|---|---|---|
| Blender | 4.5.9固定runtime、build/status、trusted compiler | 複数版resolver、設定UI、更新/修復/削除 |
| 3D加工 | GLB import、normalize/LOD/material/collision、preview ZIP | scene制作、版、画像材質、interactive viewer |
| Library | 画像・動画・GLB等の共通asset/provenance | .blend、scene revision、依存表示、3D絞り込み |
| OpenCode | Host Agent MCPから既存media tools | typed制作、長時間jobの受付/再照会 |
| Web transport | Host binary relay、MediaForge JSON WS | 専用RFB endpoint、GUI session lifecycle |
| release | MediaForge署名bundle、Host publisher verifier | 同じbundleへの3D code同梱と回帰gate |

「コードあり」「過去の記録あり」「この変更の実機確認済み」は区別する。

## 2. フェーズと依存

| ID | 利用者に届ける状態 | 主な変更 | 前提 | exit gate |
|---|---|---|---|---|
| 3DS-0 | 現状と変更範囲が再確認できる | baseline/contract fixture、互換性表、既存G8再確認 | 本設計 | 対象main/実機版と既存画像・GLB経路を記録 |
| 3DS-1 | 設定でBlender状態を確認できる | runtime resolver、legacy登録、read-only診断UI | 0 | 既存build/statusとG8加工が変わらない |
| 3DS-2 | 設定で導入・更新・削除できる | durable setup、staging、active版、修復、CLI共通化 | 1 | clean install/失敗/rollback/参照保護 |
| 3DS-3 | Libraryでモデルを回して確認できる | 遅延GLB viewer、thumbnail、絞り込み、単純比較 | 0 | 実GLB・日英mobile・memory回収 |
| 3DS-4 | 制作ファイルを版付きで保存できる | scene/revision/working copy、依存、.blend import | 1,3 | 旧版保存・owner/lock・backup/restore |
| 3DS-5 | サーバーBlenderをブラウザ操作できる | GUI pack、隔離runner、RFB relay、再接続、保存 | 2,4 | 実GUI・保存・切断・終了・権限取消 |
| 3DS-6 | 画像をモデルに貼って調整できる | MaterialBinding、画像job再利用、UV、preview/commit | 4 | 既存画像を貼る→新規生成→採用/復元 |
| 3DS-7 | OpenCodeから制作を一巡できる | typed recipes、tool/schema追加、durable child jobs | 4,6 | 指示→形状→texture→GLB→grant配置 |
| 3DS-8 | 共存と配布を実機で確認できる | GPU session、競合、release/upgrade/rollback受入 | 2〜7 | 必須GOALと回帰、公開bundle consumer検証 |
| 3DS-X | Expert scriptを隔離実行できる | 別権限、script artifact、OS sandbox | 5,7 | 脱出negative、timeout/cancel、再現記録 |

3DS-3は3DS-1/2と独立に開発可能だが、この表は並列agent実行を要求するものではない。
一つのフェーズが大きければ機能と失敗経路を保つ小PRへ分ける。
3DS-0→3DS-1と3DS-2のdurable install/cancel/restart、side-by-side更新/切替/修復、
参照保護付き削除とCLI共通化、3DS-3 Library GLB viewer、3DS-4 scene/revision/working copyと
exact backup/restore、Web操作packの固定・導入・実display probe、隔離session runner、実Blender GUI入力、
保存・終了、専用RFB gateway、noVNC接続、明示切断後の再接続、idle/crash/disable/revocation時の
fail-closed終了、復旧候補からの検証済みrevision化、既存Library画像の型付き材質bindingは完了した。
3DS-6bの画像生成jobからの採用、取消、再試行はsource/packageで完了した。画像編集jobからの採用は既存Library
Asset選択で同じMaterialBindingへ到達する。3DS-6cのrevision compare/restore、3DS-7のtyped recipesと
durable child job orchestrationも完了した。3DS-8は実installed Hostで制作一巡、opaque iframe、session lifecycle、
GPU/Broker競合、120秒超Job、署名release/update/rollbackを確認し、初期提供を完了した。

## 3. PRスライスの候補

| branch候補 | 変更と受入 |
|---|---|
| ux1/3d-runtime-status | runtime resolver + 既存stamp読取 + 設定状態表示 + G8回帰 |
| ux1/3d-runtime-install | UIから基本環境のinstall/cancel/再開 |
| ux1/3d-runtime-update | side-by-side更新/切替/修復 + active参照保護 |
| ux1/3d-runtime-remove | 削除preview/確認/managed保護/制作物保持 |
| ux1/3d-library-viewer | 共通LibraryとGLB実表示、既存画像layout回帰 |
| ux1/3d-scene-revisions | scene table/migration、immutable revision、依存、optimistic commit |
| ux1/3d-scene-working-copy | bounded .blend import、single-writer working copy、実Blender検査/保存 |
| ux1/3d-scene-backup | exact backup/restore core、missing/tamper/partial失敗、旧版保持 |
| ux1/3d-scene-backup-transport | owner-scoped private upload/download transport、切断回収 |
| ux1/3d-scene-backup-ui | browser backup download/restore upload UI、実Chrome/opaque iframe |
| ux1/3d-web-blender | 1 session software GUI起動/入力/保存/終了、OS隔離（3DS-5b完了） |
| ux1/3d-session-gateway | 認証付きRFB relay/noVNC、接続・切断・再接続 |
| ux1/3d-session-recovery | 再認証/idle/crash/Host disable |
| ux1/3d-texture-binding | 既存画像の材質割当て→revision |
| ux1/3d-texture-generation | 画像jobとの工程連携・cancel/retry |
| ux1/3d-agent-recipes | 型付き生成/修正とOpenCode durable経路 |
| ux1/3d-gpu-coexistence | 実GPU GUI/Cycles/画像/LLMの共存と終了 |
| ux1/3d-release-acceptance | clean bundle/update/rollback、実測とrelease note |

branch候補は予約名ではない。既存PRと競合する場合は別名を使う。

## 4. 実機受入シナリオ

### A. 初回導入

BlenderなしのMediaForgeで画像・Libraryが利用可能。設定から基本環境を導入し、
ページを閉じて再接続しても進捗が戻る。GLB加工を実行して正しいZIPを得る。
Web操作packの不足は分けて表示し、導入後にBlender GUIが開く。

### B. 制作一巡

OpenCodeから単純な剣をtyped recipeで作成。寸法・triangle budgetを検査。
Library画像を材質に適用し、その後新しい画像を生成して差し替える。
viewerで比較して採用し、Web Blenderで手動修正して新revisionを保存。
以前の版へ戻り、現在のproject grantへGLB/ZIPを配置してreceiptを確認。

### C. ライフサイクル

二つのブラウザで同じsceneを開いてwriter競合を確認。切断・再接続・背景復帰、
idle終了、保存失敗、Blender crash、MediaForge再起動、Host認証期限切れを実行。
未保存データがどこまで回収できたかを実ファイルで確認する。
「保存失敗でも終了はできる」「復旧候補と正式版を区別する」を確認する。

### D. 更新・削除

Blender Aでsession稼働中にBをinstallし、Aが差し替わらないことを確認。
Bのprobe失敗でAが使えること、Aの削除が参照中拒否されることを確認。
停止後にAだけ削除し画像・scene・.blend・履歴が残ることをhashで確認。
External登録解除で外部実体を削除しない。archive改ざん・容量不足・中断も検証。

### E. GPU・長時間

実機のGPU ID/VRAM/driverを採取し、型番名だけで容量を仮定しない。
CPU session、GPU session、Cycles、画像生成、Host LLMの組合せを評価。
競合する場合の保存・GUI停止・資源解放・画像実行・GUI復帰を記録。
120秒を超える制作jobと10分を超えるGUI/setupを動かし、credential refresh、
cancel、Host Job終端同期を実測する。

### F. リリース

MediaForge署名bundleをclean install、旧MediaForgeからupdate、失敗rollback。
Blenderなしでも画像が使え、Blender導入済みではruntime/sceneが引き継がれる。
wrong key/manifest/artifact、capability増加、downgrade、migration失敗を拒否・復旧。
公開操作は正規release作業として行い、設計PRでは実施しない。

## 5. 互換性・未確定事項

| ID | 確認事項 | 解決方法 | 未解決時 |
|---|---|---|---|
| CHECK-01 | noVNC binaryとHost nonce/subprotocol | 実opaque iframeの往復・長時間・取消 | Web操作を未提供、G8維持 |
| CHECK-02 | non-root OS隔離 + user unit | filesystem/network/process脱出試験 | GUI/Expertをunavailable |
| CHECK-03 | 対象GPUのGUI/Cycles backend | version/driver別probe・実測 | CPU機能のみ公開 |
| CHECK-04 | 長時間detached job/refresh/restart | 現行Host endpointと実token寿命を検証 | interruptedを明示し再認証 |
| CHECK-05 | large .blend upload/download | bounded chunk/grant transport | 上限内だけ受理 |
| CHECK-06 | frozen schema拡張 | old fixtures + current Host parser | 新toolを公開しない |
| CHECK-07 | 既存runtimeのpersistent化 | legacy参照・copy検証・rollback | 旧固定runtime維持 |
| CHECK-08 | 新旧Blender保存互換 | revision分離と実ファイル比較 | 新版へコピーし元版保持 |

Hostに不足がある場合は、その汎用変更案・依存PR・再開条件をimplementation-statusへ記録する。
この計画は他リポジトリの変更やmergeを自動的に許可するものではない。

## 6. 完了報告の形式

各sliceについてdate、commit/PR、対象機、コマンド、実際の結果、fixture、実測、
回帰確認、既知制限、NOT TESTED、次の一つの作業を記録。
3DS-8までの必須要件が揃って初めて統合3D Studioの初期提供完了とする。
Expertや生成3Dモデルは別capabilityとして未提供でも初期版の完成を妨げない。

## 7. Codexへ渡す開始指示

> AGENTS.md、docs/implementation/ux1-handoff.md、最新のimplementation-statusを読み、
> docs/design-3d-studio.mdと関連3文書、docs/implementation/g8-3d-studio-plan.mdに従って
> MediaForgeへ3D Studioを実装してください。まず現行mainと既存G8/画像機能を確認し、
> 3DS-0→3DS-1の小PRから開始してください。既存契約・画像UI・asset/Jobsを再利用し、
> Blenderは独立runtimeで管理してください。Web BlenderはサーバーGUI方式です。
> 実機受入と未検証項目を記録し、汎用Host変更が必要なら理由と別PRを明記してください。

これは将来の実装用指示であり、この文書追加PRに実装完了を求めるものではない。
