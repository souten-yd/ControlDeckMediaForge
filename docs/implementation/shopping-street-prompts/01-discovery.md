この工程は道具の確認だけです。新規画像/3Dの生成はまだ開始しません。
利用者の最終目標は、ローカルQwen3.8-27BとOpenCodeからMCPで画像→3D生成した店舗と
人物を使い、ボーン付きの人物が歩くモバイル対応・三人称のHTML商店街を作ることです。

使用可能なMCPの実一覧/公開契約に従い、MediaForge capabilitiesを照会してください。
media.generate / media.scene.from_image / media.scene.rig / media.scene.snapshot /
media.scene.export / media.job.status / media.pack / control_deck.project_output_grant
の有無を確認し、必要ならcontrol_deck.tool_contractで契約を取得してください。
外部のBlenderMCPやexecute_blender_codeがあると仮定しないでください。
まだ利用可能性しか分からない事項を「生成成功」「品質合格」と書かないでください。

結果はこのprojectのevidence/discovery.mdへ書いてください。実際に呼んだMCP名、
画像生成/画像→3D/骨入れの利用可否、3Dのresolutionと実行時間、入力/返値の要点を記録。
使うモデルはこのセッションに設定されたローカルQwen3.8-27Bだけです。
クラウドAPI、別プロジェクト、OSやモデル導入、認証設定変更、秘密値閲覧は行いません。
