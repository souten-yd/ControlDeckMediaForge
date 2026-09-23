製品0.33.13導入後の実MCP再開/納品工程。Webコードは触らない。画像生成/新規pipeline.startもしない。
発見済みMCP media.pipeline.statusのschemaにaction=retryとexpected_job_idが追加された。
必ず最初に同じpipelineをstatusで読む。failedかつ現在のJobが下記IDの場合だけ、retryを1回。
現在runningなら同じIDをpoll、succeededならその結果を回収。古いIDの再送や推測の再生成は禁止。
各対象は終端まで終わらせてから次へ進む。GPU生成を同時に複数出さない。

順序:
1. 主人公1024: pipeline_9dd4bab1fef94853bba40dcc8f0a30bd、failed rig Job job_dcd564c62d2d453f8de8dd8db242ce32。
2. 本屋: pipeline_9171d0e4e2d6421d9b1719c400eec575、failed model Job job_ec49ed49e42c4feebd00281ac26da539。
3. 歩行者コーラル: pipeline_26c659a48d51466ca2b9074b85ef139d、failed model Job job_802bf913278d4bb19a1b24ac13ea40dc。
4. 歩行者ブルー: pipeline_877d59a9344047e9ab730427037819b7、failed model Job job_2552094f316243f5bdbd8db6ce0caa17。
5. カフェ: pipeline_3df6d5608a824dafbda23f514bd3640f、modelは既に成功、export待ち。
6. 花屋: pipeline_892771ec5ecd4b15a63e985d02c5810e、modelは既に成功、export待ち。

retry/approve後は返ったstage Jobを直ちにevidence/retry-exports.jsonへ追記保存し、
15秒間隔で同じpipelineをpoll。model succeeded後のrig awaiting_approvalはapproveする。
rig succeeded後のexportもapprove。本屋/カフェ/花屋はrigなし、export承認だけ。
エラーでfailedになったらその対象は再送せず証跡へ記録し、次の対象へ進む。
通信エラーも未受付と決めつけず記録して止める。HTTP失敗を根拠に新規startしない。

GLB成功時はmedia.inspectし、通常project_output_grantとmedia.packで下記へ実配置する。
exports/player-1024-rigged.glb、exports/bookstore.glb、exports/npc-coral.glb、
exports/npc-blue.glb、exports/cafe.glb、exports/florist.glb。
手元の古いplayer-rigged.glbは不良rigなので使用/代替しない。
各scene/revision/Asset/元画像/新旧Job/GLB hash/pack receiptを簡潔にevidence/retry-exports.jsonへ保存。
assets/manifest.jsonは該当モデルのstateとasset_id/sha256/scene_id/revision_idだけ事実で更新してよい。
URL/kind/heightやWebコードは変えない。元の画像/Asset/版は削除しない。
直接API/shell推論/Blender Python/別agentは使わない。品質判定は監督側が担当。
