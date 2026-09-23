この工程は承認済み主人公画像からの3D化1回だけです。画像は監督側で目視確認済み。
まずevidence/player-image.jsonを読み、そこに記録された成功した画像Asset IDを使う。
主agentへ露出しているMediaForge MCP media.pipeline.startの実契約を使い、
name="ひだまり商店街 主人公"、image_asset_id=<その画像ID>、mode="confirm"、
resolution=512、seed=1729、refine_with_pixal3d=false、rig=true、export=trueで開始。
既存のevidence/player-model.jsonにpipeline_idがあれば新規startせず同じpipelineをstatusする。

返されたpipeline_idを即evidence/player-model.jsonへ保存。media.pipeline.statusで同じpipelineを追う。
各pollの間はshellのsleep 15程度でよい（生成/API直呼びは禁止）。
model段がsucceededかつrig段がawaiting_approvalになったら、この工程は終了。
rigをapproveしない。pipelineをcancelもしない。次工程で同じpipelineを続ける。
evidence/player-model.jsonに入力画像/pipeline/scene/revision/実Jobと最後の応答を保存。
主agentに露出しないmedia.scene.*を直接呼ばない。取得できない三角形数等を推測しない。
HTTPエラー/timeoutは未生成の証拠ではない。同じstartを絶対に再送しない。
曖昧な結果は記録して終了し、監督側の状態確認を待つ。
完成品質とは書かず、形状とテクスチャの目視評価前であることを明記する。
ローカルMCP以外の生成、Blender Python、shellによる生成API直呼びは禁止。
