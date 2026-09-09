# 3D Studio lifecycle evidence map

Date: 2026-09-09 / Status: PARTIAL

対象は [実装計画](g8-3d-studio-plan.md) §4 C と GOAL-09。
証拠を原因ごとに分離し、過去の実測と現在の再検証を混同しない。
以下の証拠名は `/data1tb/<証拠名>/observations.json` を指す。

| 条件 | 実測証拠と証明できる範囲 | 残件・限界 |
|---|---|---|
| 二つのbrowser / writer競合 | `mf-3ds8-browser-0.28.14-long`: second_writerがblender_session_busy、reload後reconnected=true | 同記録のキー送信だけでは形状変更を証明しない |
| 切断・再接続 | 同long記録で621.451秒保持と再接続。`mf-rfb-renewal-negative-0.28.30-20260906`で同sessionのconnections 1→2をheld_sec480.340で観測、660.433までconnected、gui_edit_saved=true | 後者のnegativeというディレクトリ名は失敗判定ではない。背景復帰のvisibility証拠とは別 |
| 背景復帰 | `mf-background-return-installed-20260907-native`: 通常Chromeへno_defaultsで接続。opaque frameのvisible→hidden→visible、背景15.0495秒、同session/実描画復帰後の複製・保存で第4→5版/mesh1→2。実GLB nodeも1→2、旧版bytes不変 | 短時間desktop tab切替の範囲でVERIFIED。OS suspend/mobile背景/未保存故障回収とは別 |
| idle終了 | `mf-3ds8-idle-0.28.14`: idle/disconnect設定各5秒、8.695秒で終端、復旧保存revision8 | 既定connected idle1800秒の実測ではない。開始時PID集合と終端後回収、手編集回収量は未照合 |
| 保存失敗でも終了 | `mf-save-conflict-cleanup-installed-20260907`: 5.831秒でfailed・process回収。追加`mf-unsaved-save-conflict-installed-20260907`: 実RFBで2→4 meshes、保存前working bytes不変、競合後5.037秒でfailed・process回収。候補から別scene初版へ4 meshesを回収、競合側1 meshの第6版は不変 | 保存API内部のBlender保存後の競合。save以前のcrash/定期autosave/GPU leaseとは別 |
| Blender crash | `mf-gui-child-crash-cleanup-installed-20260907`: 5.266秒でrunner_lost・process回収。追加source `mf-autosave-crash-evidence-final-20260907-r2`: 実手編集1→2 meshes、自動保存の実書込拒否/警告/旧bytes保持→権限復元→次interval成功後にBlender子だけkillし、同hashの別scene初版へ2 meshesを回収（実GLB一致） | 新autosaveはsource受入258.512秒。installed0.28.38には未配布。保存途中のkill/次interval以前の変更量はNOT TESTED。batch worker crashとは別 |
| 切断猶予終了 | `mf-disconnect-grace-cleanup-installed-20260907-final`: 実noVNC接続後Close view only、connected_at=null/disconnected_at非null、既定300秒で302.270秒後終端。3 PID/cgroup/root/socket消滅、durable参照0 | 接続表示だけを描画品質の証拠としない。手編集なし |
| MediaForge再起動 | `mf-3ds8-core-restart-0.28.14`: health復帰0.933秒、同session再接続、保存revision9 | 過去の再起動試験。今回service再起動なし。手編集回収量・当時の全PID回収は未照合 |
| Host認証期限切れ | `mf-3ds8-host-token-expiry-0.28.14`: 実署名token TTL20秒、25.038秒でRFB close4403/host service token expired、host_revoked、復旧保存revision10 | 秘密値は記録しない。手編集回収量・当時の全PID回収は未照合 |
| 復旧候補と正式版 | .38保存競合では候補515,342 Bを通常recovery.forkで別scene初版へ確定しsource hash一致。child crashと切断終了も候補450,236 Bから別scene確定、元scene/候補不変 | 未検証候補の存在だけを復旧成功としない。未保存手編集の回収範囲は次の試験で測る |

## 手編集とファイルの証拠

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

1. desktop短時間の背景hidden→visible、同session/描画/続く入力保存は上記native試験で確認。
   Playwright既定のfocus emulationで全tab visibleとなる初回失敗は成功に含めない。
2. 保存競合では追加2 meshesを全て回収できた（元2→回収4、実GLBでも確認）。
   2分autosaveはsource実装・実GUIの書込失敗/再試行後crash回収を確認。
   署名release/標準updateとinstalled4.5.13/日英受入も2026-09-09に上記の範囲で確認。
3. idle/expiry/restartの残る回収証拠を確認し、不足箇所だけ専用sessionで補う。
   GPU予約はsoftware GUIのprocess回収から推測せず、GOAL-10側の実lease証拠と照合する。

アプリ変更・版数変更・release・service再起動はこの監査sliceに含めない。
