# 3D Studio lifecycle evidence map

Date: 2026-09-10 / Status: PARTIAL

対象は [実装計画](g8-3d-studio-plan.md) §4 C と GOAL-09。
証拠を原因ごとに分離し、過去の実測と現在の再検証を混同しない。
以下の証拠名は `/data1tb/<証拠名>/observations.json` を指す。

| 条件 | 実測証拠と証明できる範囲 | 残件・限界 |
|---|---|---|
| 二つのbrowser / writer競合 | `mf-3ds8-browser-0.28.14-long`: second_writerがblender_session_busy、reload後reconnected=true | 同記録のキー送信だけでは形状変更を証明しない |
| 切断・再接続 | 同long記録で621.451秒保持と再接続。`mf-rfb-renewal-negative-0.28.30-20260906`で同sessionのconnections 1→2をheld_sec480.340で観測、660.433までconnected、gui_edit_saved=true | 後者のnegativeというディレクトリ名は失敗判定ではない。背景復帰のvisibility証拠とは別 |
| 背景復帰 | `mf-background-return-installed-20260907-native`: 通常Chromeへno_defaultsで接続。opaque frameのvisible→hidden→visible、背景15.0495秒、同session/実描画復帰後の複製・保存で第4→5版/mesh1→2。実GLB nodeも1→2、旧版bytes不変 | 短時間desktop tab切替の範囲でVERIFIED。OS suspend/mobile背景/未保存故障回収とは別 |
| idle終了 | `mf-default-idle-installed-20260910-r2`: installed0.28.51、既定connected idle1800秒、実入力後観測1793.120秒でidle_timeout。8→16 meshesを別sceneへ回収、旧16ファイルhash保持、3 PID/cgroup/root/socket回収 | 旧.14の5秒fixtureからの推測ではない。入力後観測とterminal_secは起点が異なる。GPU/電源断とは別 |
| 保存失敗でも終了 | `mf-save-conflict-cleanup-installed-20260907`: 5.831秒でfailed・process回収。追加`mf-unsaved-save-conflict-installed-20260907`: 実RFBで2→4 meshes、保存前working bytes不変、競合後5.037秒でfailed・process回収。候補から別scene初版へ4 meshesを回収、競合側1 meshの第6版は不変 | 保存API内部のBlender保存後の競合。save以前のcrash/定期autosave/GPU leaseとは別 |
| Blender crash | `mf-autosave-installed-20260909`: installed0.28.45/Blender4.5.13、実手編集1→2 meshes、自動保存の書込拒否/日英警告/旧bytes保持→次interval成功→Blender子kill。3.458秒でrunner_lost、全3 PID/cgroup/root/socket回収、同hashの別scene初版へ2 meshesを回収 | source-only/未配布という旧制限はこの受入範囲で解消。言語はbrowser languagechange fixture。保存途中kill/次interval以前の変更量、batch worker crashとは別 |
| 切断猶予終了 | `mf-disconnect-grace-cleanup-installed-20260907-final`: 実noVNC接続後Close view only、connected_at=null/disconnected_at非null、既定300秒で302.270秒後終端。3 PID/cgroup/root/socket消滅、durable参照0 | 接続表示だけを描画品質の証拠としない。手編集なし |
| MediaForge再起動 | `mf-core-restart-edit-installed-20260910-r2`: 0.28.49/HTTP healthy0.986秒、Host PID不変、GUI3 PIDを保持。同session再接続・実描画・追加手編集・保存で第7→8版/2→8 meshes、旧14ファイルhash不変、終了後3 PID/cgroup/root/socket回収 | ready中の正常service restart。RAM内の未保存複製を保持し再接続後の編集も保存。core crash/保存途中/電源断とは別。初回runの黒画面は描画復帰成功に含めない |
| Host認証期限切れ | `mf-expiry-edit-installed-20260909`: installed0.28.45、実Host opaque browserで1→2 meshes、120秒autosave後に正規署名TTL20秒でcore RFBへ接続。30.031秒で4403、30.309秒でhost_revoked。全3 PID/cgroup/root/socket回収、同hashの別sceneへ2 meshes復旧、旧版保持 | 期限切れ接続はHost proxy経由ではなく署名identity→installed core。後続複製キーの実効果は未確認なので、raw文言の「autosave後の複製を失った」は採用しない |
| 復旧候補と正式版 | .38保存競合では候補515,342 Bを通常recovery.forkで別scene初版へ確定しsource hash一致。child crashと切断終了も候補450,236 Bから別scene確定、元scene/候補不変 | 未検証候補の存在だけを復旧成功としない。未保存手編集の回収範囲は次の試験で測る |

## 手編集とファイルの証拠

2026-09-10再照合: 外部 `/data1tb/mf-current-lifecycle-audit-20260910.py` を実行しexit0。
上表のautosave/expiry/default-idleのraw JSON・復旧3 revisionの現在DB一致を確認。
旧出力と復旧blend/GLBの計22 Assets/5,368,096 Bを実hash/provenanceへ照合し、
復旧GLBの実mesh nodes2/2/16を再確認。証跡 `mf-current-lifecycle-audit-g1gzbc9j`。
過去の実機動作を今再実行したものではなく、現在PID回収の新しい証明でもない。
表内の未実装/未配布/回収未照合という古い記述を、上記の限定された受入範囲で修正した。

2026-09-09 installed0.28.45/Blender4.5.13の追加証拠:
`mf-autosave-installed-20260909`で実RFB手編集1→2 meshes、
実書込拒否/旧bytes保持/日英警告→次120秒interval成功/警告解除を確認。
言語はbrowser languagechange fixtureから正規Host bridgeを通す。
Blender子だけのkill後3.458秒でrunner_lost、全3 PID/cgroup/root/socket回収。
候補468,914 Bと復旧初版sourceのSHA一致、実GLBも2 mesh nodes、
元scene全投影・旧版source/GLB hash不変。詳細はimplementation-status。
これで上表のsource-only/未配布の制限をこの受入範囲に限り解消した。
保存途中kill/電源断/次autosave後の編集量は未検証のまま。

`.14-long`のrevision2と3はともに4 meshesであり、revision増加だけを
「Add Cubeが成功した」証拠にはしない。GOAL-04の編集証拠は
`mf-sword-ui-flow-gui-canvas-0.28.28-20260906`の成功runへ紐付ける。
同runはcanvas上の複製/移動で4→8 meshes、292→584 trianglesとなり、
第7版を保存後、第6版を第8版として復元した。隣接するgui-input/gui-reconnectの
失敗runは成功証拠へ含めない。これは保存済み編集の証拠で、未保存回収量とは別。

`mf-lifecycle-evidence-audit-20260907`は8件のraw evidenceをSHA付きで照合し、
idle/expiry/restartの保存版、成功GUI編集の前後/復元版、.38の3復旧forkについて
9 revisionのJSONと現在DBを照合したread-only監査。21 Asset、24,128,377 Bの
実bytes SHA/sizeとprovenance sidecar/DBの一致を確認した。
再開後にも全21ファイルのhash/size/provenanceと9 revision IDの存在を再確認した。
この現在のファイル検証を、過去のprocess回収や新しい実機再実行の証拠へ広げない。

## 次の実測

2026-09-10 installed0.28.50の既定idle実診断は失敗:
`mf-default-idle-installed-20260910/failure-audit.json`。
913.496秒までready/connected/入力時刻不変、その後disconnected_timeoutで誤終了。
controller.active待機中のreleaseと古いsession読取による競合をred/green testで再現・修正。
3 PID/session rootは回収され候補547950 Bを保持したが、復旧mesh確認は未到達。
短時間source回帰`mf-probe-clock-source-20260910`は138.523秒/2 meshes回収成功。
この失敗後の修正版0.28.51は署名配布・標準導入済み。
`mf-default-idle-installed-20260910-r2`がexit0/passed=trueで既定1800秒を完走。
実入力17:45:12.191318 UTCから終端更新18:15:18.185248 UTC、idle_timeoutで終了。
入力後観測1793.120秒（後段waitのterminal_sec1785.096とは起点が異なる）。
再接続で入力時計を延長せず、8→16 meshesを別sceneへ復旧。実GLB22216 B/16 nodes、
旧16ファイルhash不変、所有3 PID/cgroup/root/socket回収を確認した。
この証拠で既定connected idleと手編集回収の残件を補完する。GPU/電源断には広げない。

2026-09-10 sourceの前提修正: 全RFB frameと再接続がidleを延長していたため、
完全なkey/pointerのみの操作時計へ変更。`mf-rfb-input-source-20260910-r2`で
24回の画面要求では時刻不変、pointerで更新、再接続でも時刻保持を実測。
既定autosave後の所有Blender子crash→同hash/2 meshes回収も128.123秒で確認。
これは短時間source受入であり、上表の既定connected idle1800秒の残件は解消しない。

1. desktop短時間の背景hidden→visible、同session/描画/続く入力保存は上記native試験で確認。
   Playwright既定のfocus emulationで全tab visibleとなる初回失敗は成功に含めない。
2. 保存競合では追加2 meshesを全て回収できた（元2→回収4、実GLBでも確認）。
   2分autosaveはsource実装・実GUIの書込失敗/再試行後crash回収を確認。
   署名release/標準updateとinstalled4.5.13/日英受入も2026-09-09に上記の範囲で確認。
3. idle/expiry/restartの残る回収証拠を確認し、不足箇所だけ専用sessionで補う。
   GPU予約はsoftware GUIのprocess回収から推測せず、GOAL-10側の実lease証拠と照合する。

アプリ変更・版数変更・release・service再起動はこの監査sliceに含めない。
