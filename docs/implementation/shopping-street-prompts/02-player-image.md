この工程は主人公の参照画像1枚だけです。3D化はまだ開始しません。
MediaForge MCP media.generateでimage.generateを実行し、その実応答で終端成功を確認。
evidence/discovery.mdも読む。主agentにはmedia.job.statusが露出しないため、存在しない
道具を呼ばない。生成道具が終端結果を返す場合はその結果とmedia.inspectで確認する。
非終端Jobが返った場合はIDを保存し、その事実を報告して止める（重複生成しない）。
モデルは導入済みの利用可能な既定/auto、remoteは禁止。幅/高さは1024。公開schemaに従う。

画像内容（必要なら英語promptに整理してください）:
Original friendly adult young Japanese shop assistant, gender neutral, stylized high-quality 3D game
character with appealing face, short dark hair, mustard yellow jacket, cream shirt, teal straight
trousers, simple white sneakers. Full body entirely visible, front view, neutral relaxed A-pose,
arms separated from torso at about 25 degrees, hands open, straight legs with a clear gap, parallel
feet shoulder width apart. One single person, opaque clothes, no accessories dangling between limbs,
no ground plane or cast shadow, plain clean white background. Symmetrical anatomy, complete hands
and feet, broad readable color regions and soft modeled details. Not a toy on a pedestal, not a
sprite sheet, not multiple views, no text or watermark. The image will be reconstructed into a
single textured skinned 3D game character, so make silhouette and separated limbs unambiguous.

入力を複数枚に増やさない。失敗した時だけJob IDと理由を記録し、別モデルへ無断変更しない。
成功した画像をprojectのexportsへplayer-source.pngとして、既存output grant + media.packで配置。
evidence/player-image.jsonに実Job ID、Asset ID、sha256、receiptを保存。秘密値は保存しない。
このproject以外のファイル、Host/MediaForgeの設定は変更しない。
