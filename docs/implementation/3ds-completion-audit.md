# 3D Studio 完了監査

Date: 2026-09-06
Status: PARTIAL / 初期提供の完了判定を撤回。設計・必須条件は縮小しない。

対象: PR #213のGOAL-01〜10と`g8-3d-studio-plan.md` §4 A〜F。
監査開始コードはmain `1f4392a2d426a742046d0c03c99272ffb5e41c87`。その後PR #246/247をマージし、
現在導入済み版はv0.28.16（target `53faaeb`）。
以前の個別実測は維持するが、条件の一部だけの実測から行全体を成功扱いしない。
下表の「未確認」は今回の監査で条件全体に対応する証拠を確定できていない意味で、コード不在とは異なる。

## 利用者ゴール別

| 条件 | 確認済み証拠の範囲 | 判定と残件 |
|---|---|---|
| GOAL-01 共通Library | installed scene表示と既存画像の選択 | PARTIAL: 画像/GLB/.blendの全絞込と親子双方向移動の操作証拠を照合 |
| GOAL-02 viewer | installed scene preview | PARTIAL: orbit/zoom/material/wire/animationそれぞれのassertionを照合 |
| GOAL-03 設定管理 | 4.5.9/4.5.13の共存、active切替、参照中削除拒否 | PARTIAL: 全操作の画面完結、失敗後再開とscenario Dの証拠を照合 |
| GOAL-04 Web Blender | `.14-long/observations.json`: 621.451秒GUI、入力、保存revision 2→3、reload/reconnect | VERIFIED（この操作範囲）。credential refreshの証拠ではない |
| GOAL-05 OpenCode一巡 | OpenCode形状/create/status/snapshot/export/packと、別のUI画像生成・適用 | PARTIAL: 自然言語からtexture生成/適用まで同じOpenCode制作Job経路で追跡した証拠が未確定 |
| GOAL-06 既存画像比較採用 | `.14-material`でrevision 3→4、`.15-texture-gpu`で生成画像採用12→13 | PARTIAL: 新旧比較を含む全操作のassertionを照合 |
| GOAL-07 やり直し | restoreとcrash/idle等の復旧保存。競合分岐救出をsource/package/installedの実Blender・browserで確認 | PARTIAL: 失敗工程だけの再試行の全条件照合。standalone candidate ID脱落はPR #246で修正済み |
| GOAL-08 grant配置 | 以前のOpenCode export/pack記録 | PARTIAL: GLB/画像/manifestの配置先receiptとhashの全対応を照合 |
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
| B 制作一巡 | GOAL-05/06/08の不足を埋め、同一制作物の履歴とreceiptを対応付ける |
| C lifecycle | 既存crash/idle/restart/expiry証拠は維持。競合candidateは保持だけを復旧完了としない |
| D 更新/削除 | 稼働A中にB導入、B probe失敗、A削除拒否、停止後Aのみ削除と資産hash保持、External解除、容量不足/中断を個別照合 |
| E GPU/長時間 | 132秒SIGSTOPはdetached維持/取消の証拠のみ。期限内child credential refreshの実応答、Host終端、120秒超制作と10分超session/setupの対応を実測 |
| F release | 署名公開/update/改ざん拒否証拠は維持。rollbackは候補health成功後の例外注入であり、migration失敗や自然なhealth不良の証拠へ読み替えない。clean install等も個別照合 |

GPU GUIは設計§4とCHECK-03の条件付き提供に従いsoftware-onlyを正直に表示する。
Eevee/Cycles probeをGPU GUI動作と見なさず、CPU/画像/LLMとの組合せ評価を別々に記録する。
credential更新は**失効前**に行う要件であり、失効tokenからの自己再発行は要求しない。

現在コードではHost child token TTLは600秒、MediaForgeのrefresh marginは120秒、
scene worker timeoutは180秒。単一workerの132秒維持ではrefresh条件へ届かない。
実Host DBを`mode=ro`で読み、`audit_logs`の`username=addon:media-forge`かつ
`action=addon.runtime.job.credential.refresh`を検索した結果は0件。
これは現在残る監査記録の観測であり、削除済み履歴まで含めた不実行の証明ではない。

## 今回発見した具体的なコード差分

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
