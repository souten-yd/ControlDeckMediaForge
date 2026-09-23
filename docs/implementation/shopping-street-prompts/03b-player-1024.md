主人公512版の生成テクスチャが元画像と違うため、同じ画像/seedを1024版で比較する工程。
短く実行し、冗長な途中説明や大きい応答の全転記をしない。
evidence/player-image.jsonの成功画像asset_ba425dadeebc4238ab8d05bd45c1874bを使用。
media.pipeline.start: name="ひだまり商店街 主人公1024比較"、image_asset_id=上記、
mode="confirm"、resolution=1024、seed=1729、refine_with_pixal3d=false、rig=true、
rig_ratio=.15、export=true。
evidence/player-1024.jsonが存在してpipeline_idを持つなら開始を再送せず同じIDを追跡する。
新規開始応答のpipeline_idだけ即保存。media.pipeline.statusで15秒間隔に同じIDを追う。
modelがsucceededかつrigがawaiting_approvalになったら、rigを承認せずこの工程を終了。
最後に同JSONへimage/pipeline/scene/revision/Job/stage stateを簡潔に保存。
画像を再生成しない。3Dの再生成は今回の解像度比較1回のみ。packやHTML作成はこの工程ではしない。
曖昧なHTTPエラー時は再送しない。記録して終了。MCP外の生成API呼出し/Blender実行は禁止。
これは比較候補であり、品質を合格と書かない。
