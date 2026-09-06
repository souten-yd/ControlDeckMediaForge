# 3D Studio 完了監査

Date: 2026-09-06
Status: PARTIAL / 初期提供の完了判定を撤回。設計・必須条件は縮小しない。

対象: PR #213のGOAL-01〜10と`g8-3d-studio-plan.md` §4 A〜F。
監査開始コードはmain `1f4392a2d426a742046d0c03c99272ffb5e41c87`。その後PR #246/247をマージし、
本監査でv0.28.17（target `4293d20`）の終端照合を受入後、v0.28.19（target `583fea1`）を
正式署名公開・標準updateしLibrary viewerをoverlayなしで受入した。さらにv0.28.20（target `c26f67d`）
の材質照明・新旧双方のcontext復旧をinstalled受入した。さらに0.28.23（target `22fc2b9`）を
署名公開・標準updateし採用前候補比較/破棄/採用/復元をinstalledで確認。現行0.28.26/healthy。
0.28.26ではnative windowで比較入力・不変refreshのDOM保持と全比較/採用/復元を確認した。
新版の他操作の受入を旧版やcandidateの証拠から推定しない。
以前の個別実測は維持するが、条件の一部だけの実測から行全体を成功扱いしない。
下表の「未確認」は今回の監査で条件全体に対応する証拠を確定できていない意味で、コード不在とは異なる。

## 利用者ゴール別

| 条件 | 確認済み証拠の範囲 | 判定と残件 |
|---|---|---|
| GOAL-01 共通Library | installed scene表示と既存画像の選択 | PARTIAL: 画像/GLB/.blendの全絞込と親子双方向移動の操作証拠を照合 |
| GOAL-02 viewer | 署名installed0.28.19でLibrary→3D card、±XYZ回転・zoom両方向、逆操作差分0、320px、scene不変をoverlayなしで確認 | VERIFIED（利用者指定操作の範囲）。2026-09-06利用者確認によりwire/animationは必須から除外 |
| GOAL-03 設定管理 | 4.5.9/4.5.13の共存、active切替、参照中削除拒否 | PARTIAL: 全操作の画面完結、失敗後再開とscenario Dの証拠を照合 |
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

| 条件 | 残る照合・実測 |
|---|---|
| A clean環境/表示 | 全操作、320px、日英、既存画像がBlender不在でも利用可能な証拠。390pxだけで320px成功とはしない |
| B 制作一巡 | OpenCode剣scene_f1554d9ba0f741968d9c468206ea3198で生成画像/材質/配置まで確認。同じ剣で既存画像→候補比較/採用→GUI修正→復元→再配置を残す |
| C lifecycle | 既存crash/idle/restart/expiry証拠は維持。競合candidateは保持だけを復旧完了としない |
| D 更新/削除 | 稼働A中にB導入、B probe失敗、A削除拒否、停止後Aのみ削除と資産hash保持、External解除、容量不足/中断を個別照合 |
| E GPU/長時間 | 132秒SIGSTOPはdetached維持/取消の証拠のみ。期限内child credential refreshの実応答、Host終端、120秒超制作と10分超session/setupの対応を実測 |
| F release | 署名公開/update/改ざん拒否証拠は維持。rollbackは候補health成功後の例外注入であり、migration失敗や自然なhealth不良の証拠へ読み替えない。clean install等も個別照合 |

GPU GUIは設計§4とCHECK-03の条件付き提供に従いsoftware-onlyを正直に表示する。
GOAL-02の証拠は `/data1tb/mf-viewer-six-axis-library-installed-0.28.19-20260906/observations.json`。
通常Chrome/AMD内蔵GPUであり、R9700/software GPU描画や実mobile touchの実績ではない。
viewer release gateの日英切替・mobile入力・model切替memory回収/context lossの再照合は残る。
比較paneのtextureなし/ありcontext復旧とclose時context解放は0.28.20で追加確認した。
証拠 `/data1tb/mf-material-compare-installed-0.28.20-{old,current}-20260906/observations.json`。
これはbyte単位のheap/VRAM回収や全model切替回帰の証拠ではない。
Eevee/Cycles probeをGPU GUI動作と見なさず、CPU/画像/LLMとの組合せ評価を別々に記録する。
credential更新は**失効前**に行う要件であり、失効tokenからの自己再発行は要求しない。

現在コードではHost child token TTLは600秒、MediaForgeのrefresh marginは120秒、
scene worker timeoutは180秒。単一workerの132秒維持ではrefresh条件へ届かない。
実Host DBを`mode=ro`で読み、`audit_logs`の`username=addon:media-forge`かつ
`action=addon.runtime.job.credential.refresh`を検索した結果は0件。
これは現在残る監査記録の観測であり、削除済み履歴まで含めた不実行の証明ではない。

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
