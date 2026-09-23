主人公1024候補の既存pipelineを続ける。製品の人物rig修正0.33.11は導入済み。
evidence/player-1024.jsonのpipeline_9dd4bab1fef94853bba40dcc8f0a30bdをmedia.pipeline.statusで確認。
media.pipeline.statusの実schemaに従い、待っているrigをapproveし、15秒間隔で同じIDを追う。
rig成功後のexport待ちもapproveし、成功したGLBをinspect、通常output grant/packで
exports/player-1024-rigged.glbへ配置する。
evidence/player-1024-rig.jsonに各stageのJob/scene/revision/Asset/hash/receiptを簡潔に保存。
開始済みのpipelineを新規startしない。画像/3D再生成なし。任意Blender/API shell直呼びなし。
通信エラー時は再送しない。成功/失敗とも正直に記録して終了。品質判定は監督側が行う。
冗長な説明やschemaの全転記は不要。必要なMCP呼出しと短い証跡ファイルだけ実行。
