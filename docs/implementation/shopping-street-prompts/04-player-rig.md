主人公1体の既存pipelineを続け、骨入れ・walk clip・GLB書き出しを検証する工程です。
画像/3Dは再生成しない。pipeline.startは呼ばない。
evidence/player-model.jsonのpipeline_9840d28cf9164e0288c10cf8f80da18bをstatusで読む。
model=succeeded/rig=awaiting_approvalなら、rigをapproveして同じpipelineをstatusで追う。
rig成功後のexport=awaiting_approvalもapproveし、export Asset IDを得る。
各pollの間はsleep 15程度。HTTPエラーは未実行の証拠ではない。start/approveの盲目的な再送は禁止。
失敗したら実IDと理由を記録して止める。shellからAPI/Blender Pythonを呼ばない。

監督側が元GLBを4方向から描画して観測した事実:
scene_889d23ec8c874d91bfa6347b3d4076a5、revision_08ac7ad5018b457ea581655067fc5e83。
未rigのpreview Assetはasset_0b420f1f16584fccb9c0283e790af61f、148034 triangles、
1 mesh/1 textured material/0 bones/0 animations、Three.js読込エラー0。
体/手足は分離しているが、元の黄色上着が茶色、肌が赤くなった色の品質問題がある。
この工程は骨変形を先に測るためであり、外観品質の合格を意味しない。

export成功後にoutput grantを取得し、media.packでexports/player-rigged.glbへ配置。
既存の未rig Assetもmedia.packでexports/player-unrigged.glbへ配置（再生成しない）。
evidence/player-rig.jsonに同pipeline/scene/revision/rig Job/export Asset/receipt/hashを保存。
三角形数/ボーン数/変形の見た目は監督側で読み戻して検査するので、未計測を合格と書かない。
