残る店3種類と歩行者2種類を、既存の参照画像からMediaForge MCPで3D化する工程。
参照画像は監督側が確認済み。evidence/references.jsonの対応を使う。
画像を再生成しない。短い処理と証跡だけにし、応答/schemaを全転記しない。

evidence/remaining-models.jsonがあれば各pipeline_idを再利用し、新規開始を繰り返さない。
未開始の対象だけmedia.pipeline.startを各1回呼び、返されたpipeline_idを直ちにJSONへ追記。
共通mode="confirm"、refine_with_pixal3d=false、export=true、seed=1731から順に固定。
- cafe: ひだまり商店街 カフェ、resolution=512、rig=false
- florist: ひだまり商店街 花屋、resolution=512、rig=false
- bookstore: ひだまり商店街 本屋、resolution=512、rig=false
- npc-coral: ひだまり商店街 歩行者コーラル、resolution=1024、rig=true、rig_ratio=.15
- npc-blue: ひだまり商店街 歩行者ブルー、resolution=1024、rig=true、rig_ratio=.15

各pipelineを同じIDでmedia.pipeline.statusから追跡。生成はGPUの共通待ち行列に任せる。
poll間隔は15秒。model後のrig/exportがawaiting_approvalになったら承認せず停止。
全5対象がmodel完了またはfailedになるまで状態を追跡し、JSONに各image/pipeline/scene/
revision/Job/stage stateを簡潔に記録して工程終了。HTMLやpackや骨入れはこの工程に含めない。
失敗を成功扱いしない。HTTPエラー/timeoutは未生成の証拠ではないので再送せず、記録して終了。
任意Blender/Python生成、shellからの生成API呼出しは禁止。外観合格は監督側が判定する。
