# 3D Studio — scenario D 更新・削除の証拠対応

Date: 2026-09-10
Status: PARTIAL。全3DS/GAの完了判定ではない。

正は [G8計画 §4 D](g8-3d-studio-plan.md) と
[runtime設計 §4–5](../design-blender-runtime-and-web.md)。本書は要件を変更せず、
各条件に対する実測の範囲と残る配布経路の確認を区別する。
2026-09-10に下記observations.jsonの実データを再読した。新しい実操作の再実行ではない。
sourceは実Ubuntu/実Blenderだが稼働Host経由ではなく、packageは配布artifactを専用dataで起動したもの。
installedはHostが管理する稼働版。これらを互いに読み替えない。

## 必須条件と証拠

証跡名はすべて `/data1tb/<証跡名>/observations.json`。
表の「確認済み」はその行の限定された範囲を表し、scenario全体の承認ではない。

| ID / 必須条件 | 実データで確認した証拠 | 範囲・残件 |
|---|---|---|
| D-01 A稼働中にBを導入してAを維持 | `mf-owned-probe-failure-source-20260910-r2`: 4.5.9の同sessionをready/pinnedのまま4.5.13 updateがready。`mf-parallel-runtime-installed-0.28.53-20260910-r2`: 4.5.13 GUI中に4.5.9 exact install、同PID/hash/inode/RFB画素を保持 | installed旧→新版も0.28.55で追加確認済み（下記追記）。元診断exit1と独立audit exit0を区別。自然故障/更新中手編集は未検証 |
| D-02 B probe失敗でもAが使用可能 | 前者のcandidateだけpidfd SIGTERM、update failed後にAの実GLB入出力probe/同session ready、正常retry。`mf-probe-failure-installed-0.28.53-20260910`: 候補4.5.9 probe失敗→retry中も4.5.13 GUI/PID/hash保持 | installed旧→新版も0.28.55で追加確認済み（下記追記）。元診断exit1と独立audit exit0を区別。自然故障/更新中手編集は未検証 |
| D-03 参照中のA削除を拒否 | `mf-stale-removal-after-ack-installed-0.28.54-20260910`: GUI開始後、古い確認はremove_changed、新確認+履歴同意もin_use。`mf-job-removal-installed-0.28.54-20260910`: 実Host child受付後live3で同じ2拒否、正規取消後live0 | installed GUI/Job双方確認済み。今回は再実行していない |
| D-04 停止後、追加確認付きでAのみ削除し履歴保持 | `mf-history-installed-0.28.52-20260910-r2`: 日本語320pxの設定から4.5.9を実削除、旧scene/revision/asset hashes保持。`mf-removal-first-job-source-20260910`: 停止だけではproject_reference拒否も記録 | installed明示削除とsource既定拒否を区別。履歴や旧pinを削除して通した試験ではない |
| D-05 確認前後にGUI/Jobが開始しても再拒否 | 上記GUI after-ackと `mf-stale-removal-installed-0.28.53-20260910` のbefore-ack、上記Jobのstale/fresh確認 | installedで確認済み。GUIとJobを同じプロセス参照の証拠として混同しない |
| D-06 削除処理中の逆順受付を保護 | `mf-removal-first-job-source-20260910`: 実rename/unregister間のguardに明示gate、GUI/recipe取得待機→削除完了後scene_runtime_unavailable。Host呼出0、新Job0、runtime参照0 | source実削除で確認済み。Hostはuncalled fixture。installedで自然に同じ競合タイミングを観測したものではない |
| D-07 接続切断/core再起動でも同じ削除確認を保持 | `mf-removal-restart-source-20260910`: client再接続→専用core SIGTERM→別core、同operation5bb9…/全preview/fingerprint/ack=trueでready。同版再導入と6hash保持 | source実プロセスで確認済み。初回preflight停止はfixture。installed core再起動/rename途中crash/電源断は未検証 |
| D-08 不在中のLibrary/backup、同版再導入→同scene再編集 | `mf-history-installed-0.28.52-20260910-r2`: viewerと21,464,415B backup/28entries。`mf-reinstalled-edit-installed-0.28.52-20260910`: 同scene_ca920…で実RFB複製/保存、mesh4→8、旧版保持 | installedで組合せ確認済み。前者の記録にある開始応答はstartingであり、それ単独をready/再編集の証拠にしない。再編集は後者が補完する |
| D-09 External解除で外部実体を削除しない | `mf-external-registration-20260906`: 解除/再作成/明示再登録と外部inventory。`mf-external-settings-package-0.28.34-20260906`: 日語1280/320で取消/解除/reload/再登録、7.944秒、errors0 | 専用packageで確認済み。mode文字列はsource_standalone_headedのままで、package起動同定/5,580files不変は当時のstatus記録に依存。installed外部/英語外部は未検証 |
| D-10 archive改ざん | `mf-repair-tamper-installed-0.28.55-20260910`: cache copy1byte反転、SHA不一致failed/不正cache除去、旧exe/47scene/162revision/64hash保持→正常repair実probe | installed取得済みcache条件で確認済み。CDN通信中の改ざんではない |
| D-11 容量不足 | `mf-repair-capacity-source-20260910-r2`: 修復前/展開前にfree=0を注入、insufficient_disk、8hash/旧inode/scene保持、失敗後の実Blender入出力成功 | source容量判定2箇所で確認済み。実diskを埋めたENOSPC/書込途中容量枯渇やinstalled障害注入ではない |
| D-12 中断と再開 | `mf-repair-resume-installed-0.28.55-20260910`: 実CDN downloadを正規cancel、1,671,168B/進捗/ETag保持→通常repair再送→同inode全archive/hash→実probe/ready | installed通常取消/再送確認済み。wire Rangeヘッダー未採取、process crash・重複task.cancelの試験ではない |
| 関連GOAL-03 修復 | `mf-repair-protection-installed-0.28.53-20260910`: live修復拒否。`mf-repair-download-installed-0.28.55-20260910`: 停止済み同版の実CDN正常repair/実probe/制作物保持 | installed live拒否と正常repair確認済み。D-10/11/12が失敗/中断条件を補完 |

## 次の不足と停止条件

2026-09-10 D-09 installed試行は未達。mf-external-installed-0.28.63-20260910は
解除前からdamagedのlegacy行を解除し、再登録timeoutでexit1。稼働bundleに外部root設定がなく、
source外部inventory先とpackaged既定rootが異なる。正しいready参照のpreflightが診断に欠落していた。
当該登録だけ事前JSONへ復元し、外部6544entries不変・registry一致を独立確認。詳細はstatus。
通常再登録成功とはしない。設定済みready外部を対象にする次の受入と、既存source/package成功を区別する。

2026-09-10追記: **D-01/02のinstalled旧→新版updateを補完済み**。
`mf-update-failure-installed-0.28.55-20260910`で4.5.9 GUI稼働中に4.5.13 update候補をpidfd SIGTERM、
失敗後も旧GUI/同PID/hash維持、正常retry→既定4.5.13でも旧GUIは4.5.9固定。
47scene/162revision/688hash保持。元runはregistry配列順のbytes assertでexit1、
別independent-audit.jsonは全登録項目のID単位一致、履歴/hash、プロセス回収を確認してexit0。
元runのpassed=falseは保持し、更新成功と診断cleanup assertionを区別する。
上表D-01/02の「installed旧→新版が残る」はこの追記で解消。自然故障/更新中手編集は未検証。
次はEの自然120秒超制作へ進む。D-06/07/09/11のscope制限はそのまま残す。

1. D-01/02の**installed旧→新版update**で用いた準備条件（今後の無条件再実行指示ではない）:
   A=4.5.9の専用scene GUI中にB=4.5.13候補を検査し、候補probe失敗→正常retry→既定BでもA固定を確認。
   現在Bが導入済みなので、既存Bをそのままprobeする短絡経路だけで「並行導入成功」にしない。
   準備にB削除が必要なら、全Job/GUI/runtime idle・全履歴pin・正しい同版cache・backup・
   影響範囲・正規追加確認を先に照合する。削除が保護で拒否されたら、その理由を迂回しない。
   他利用者のJobやsceneを停止/変更せず、旧版へのpin書換えで受入を通さない。
2. D-06/07/09/11はsource/packageで具体的動作の証拠がある。installedとの不足を明示して残し、
   一律「未実装」や「全失敗経路未検証」へ戻さない。配布受入で必要な差分を個別に選ぶ。
3. 物理ENOSPC、電源断、wire capture等の未実施条件は記録を残す。
   観測した取消をcrashと呼ばない一方、列挙した未実施条件すべてを無根拠に新しい必須goalへ追加しない。
   元の必須条件と実際の故障モデルに基づいて完了を判断する。
4. D以外のA/C/E/F、GOAL-01〜10、GA-0〜8/GA-Xは独立に残す。
   特にボーン/有機weight/IK/歩行clipの機能追加やengine受入を、runtime検証で代替しない。

## この監査の限界

観測JSONのstage名だけで成功とせず、operation action/state/runtime、確認payloadの一致、
probe結果、参照数、実体保持、終了記録を対象範囲で読んだ。
外部packageの起動同定とinventoryはJSONだけでは自己完結していないため、その制限を表へ残した。
過去の全assetを今回再hashしたわけではなく、全UI・全版を再実行したものでもない。
この文書追加ではruntime/cache/制作物/Host/PCを変更していない。
