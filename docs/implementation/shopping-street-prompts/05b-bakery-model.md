承認済みのパン屋画像1枚を3Dにする工程。画像は監督側が確認済み。
evidence/references.jsonのbakery Assetを読み、media.pipeline.startの実契約で
name="ひだまり商店街 パン屋"、image_asset_id=<bakeryのID>、mode="auto"、
resolution=512、seed=1730、refine_with_pixal3d=false、rig=false、export=true、export_format="glb"。
evidence/bakery-model.jsonに既にpipeline_idがあれば開始を再送せず同じpipelineを追う。
開始応答を即保存し、media.pipeline.statusを15秒間隔で終端まで追跡する。
成功したGLBをmedia.inspectし、通常output grantとmedia.packでexports/bakery.glbへ配置。
記録はevidence/bakery-model.jsonにimage/pipeline/scene/revision/Job/Asset/hash/receiptを保存。
画像の再生成、他店舗/人物生成、任意Blender、生成APIのshell直呼びは禁止。
HTTPエラー/timeoutは未生成の証拠ではない。開始や生成を再送せずその場で記録して終了。
3Dの外観は監督側が評価する。処理成功を外観合格と書かない。
