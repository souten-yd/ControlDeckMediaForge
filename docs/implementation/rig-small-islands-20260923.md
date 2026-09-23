# 人物rigの小片に残った重み欠損

Status: source実機受入済み / 0.33.12 release準備。0.33.11で脚交差を直した512版とは別の1024候補の不具合。

実OpenCode/MCPのJob_dcd564c62d2d453f8de8dd8db242ce32はrigでfailed。
同じ元モデル/recipeをBlender4.5.13で診断し、人物12bonesの検出には成功、
16391頂点のうち16377にheat weight、肩付近の1小片14頂点だけ欠損を確認。
小片の幅XYZ=.005010/.005805/.005931m、既存weighted頂点への最大距離.004547m。
失敗版を正式Assetとして登録せず、元revisionを保持した。

設計: 正立人物のrig.autoだけ、全頂点の0.5%以下かつ128頂点以下、1片64頂点以下、
片の対角が身長2%以下、各頂点のdonor距離が身長0.5%以下なら、元heat結果の近傍から
重みを補間する。修復した頂点を次のdonorにせず、全条件を確認してから適用する。
距離・頂点数をrecipe resultへ記録。元geometry/UV/画像を変更せず、既存の4影響/正規化/
rest-pose不変検査を再使用。大きな欠損、遠い浮遊部品、一般skin.bind_autoは従来どおり失敗。

## source実機受入

証跡はfeature-data/media-forge/maintenance/shopping-street-20260923内。
元asset_a94a60e2919d4f7fa0d332b5f4dce0e8と同じ失敗recipeを、managed Blender4.5.13の
`--background --factory-startup --disable-autoexec --python-exit-code 1`で再実行。
trusted workerのscene_recipe.py、scene_document.pyを順に実行した。

- 1024候補: worker3.669381秒/export.414095秒、14頂点/1片を補間、donor最大.004787450m
  （身長1.003715515m、許容.005018578m）。16391頂点、重みなし/不正0、最大4影響、
  総和誤差最大4.84288e-8。12bones、GLB41827tris、1秒loop/36tracks。
- heat-parity.pyは失敗診断.blendと修正版のgeometry/UV/packed画像SHA一致を確認。
  同じ512入力/recipeの再実行では補間0、以前の重みSHAとも一致。既存一般bindは変更しない。
- render-model.mjsの実GLB四方向/歩行描画でpage error0。前・横・斜めの見た目を確認。
  全25frame/身長1.8m換算: 足表面の左右間隔最小+.111551m、手の脚重み0、
  頭の変位最大.000583m、loop始終一致。地面への沈み最大.016296mは残り、
  移動時の接地調整は商店街側で別受入する。SwiftShader描画を実GPU性能証明にはしない。
- focused64tests通過。`PYTEST_ADDOPTS=--basetemp=/tmp/mfi-test-20260923 ./mf.sh test`:
  **2446 passed /3 warnings /433.49秒**。git diff検査通過。

NOT TESTED: 修正版のsigned installed/MCP再実行、物理スマホ。
pipeline.statusには失敗段retryがまだないため、元pipeline再開は別の修正が必要。
商店街HTMLの完成を意味しない。
