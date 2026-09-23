# 生成人物の軽量化停止と腕を下ろした姿勢の自動rig

Status: 0.33.16 merged/released/installed。実OpenCode/sculptor/MCPでNPC2体のrig成功。納品・商店街全体は確認中。

実OpenCode/Qwen/MCPで生成済みの歩行者2体を、元の画像/3Dを再生成せず診断した。
元revision/Assetを変更せず、feature-data/media-forge/maintenance/shopping-street-20260923の
private診断コピーを用いた。追加モデル取得0。既存Pixal3D Vulkan/モデル設定は不変。

## 原因と修正

- weld後にratio=.15でDecimateすると、青は285012→60642面、赤は286137→54982面。
  指定の約42800面まで到達せず、他の縮約可能な部分が潰れた。四方向描画で頭・胴・脚の破綻を確認。
  法線再計算off、小さいweld距離、非manifold頂点の保護、座標拡大はいずれも採用しない。
- ratio=.30では青85503/赤85841面を残し、頭・胴・脚の形を保持。
  Decimateの結果が目標三角形数＋丸め許容（最大2面または1%）を上回ったらcandidateを拒否する。
  固定reason `decimate_target_unreachable`から「ratioを増やして面を残す」の案内を返す。
  到達率だけで形状品質を保証せず、描画/変形を別に検査する。
- 赤い人物は腕を下ろしており、粗い断面格子では腕と胴が隣接セルとして結合した。
  格子だけ細かくすると、軽量化された胴の疎な頂点が複数の偽の部品に割れた。
- 従来の頂点測定が失敗する直立2脚候補だけ、実三角形の水平断面を128段で測り、
  格子幅75%でも同じ人物条件（2脚/複数断面の3部品/関節/頭）を確認する。
  下部帯の頂点が24未満の場合も同じ面測定を使う。メッシュ/UVへ頂点を追加しない。
- 50万三角形、200万断面/補間試行、20万測定点の上限。未知の形を人と断定しない。
  既存測定が成功する人物と一般的な4/6脚の処理・heat修復の上限は維持する。

## 実core → Blender → 結果検証

`npc-core-acceptance.py`でSceneWorkspace._apply_recipe_worker、managed Blender4.5.13の
trusted scene_recipe.py、本体のworker結果検証を実行。

|入力|設定|実測|結果|
|---|---|---|---|
|青NPC|.30|4.960461秒|32993 vertices /85503 triangles /12bones、成功|
|赤NPC|.30|5.033492秒|34266 vertices /85841 triangles /12bones、成功|
|青NPC|.15|4.210451秒|第2操作で拒否、面を残す案内、scene未公開|
|赤NPC|.15|4.262860秒|第2操作で拒否、面を残す案内、scene未公開|
|既存1024主人公|元の同一recipe|4.571101秒|成功、geometry/UV/画像/bones/weights hash一致|
|既存512主人公|元の同一recipe|2.523818秒|成功、geometry/UV/画像/bones/weights hash一致|

`surface-final-audit.py`は元と候補のsurface距離をBVHで双方向測定（元頂点1/7＋候補全頂点）。
身長比99 percentileは青.0005176/赤.0004048、最大.0042213/.0042357。全連続面の厳密Hausdorff保証ではない。
画像packed SHAは元と一致。全頂点に有限・正規化済み最大4影響、欠損/不正0。

全25frame、身長1.8m換算で足表面の左右間隔最小は青+.121821m/赤+.074917m。
手領域1079/878 verticesの脚bone weightは0。ループ始終一致。
足底の下がり最大1.9794cm/1.2941cmは残り、Webの接地補正と組み合わせた最終受入が必要。
頭の変位最大1.2488cm/.1672cm。これらを自然な歩行全体の完成としない。

trusted scene_document.pyでGLBへ書出し、実Chrome/Threeで4方向と歩行3時刻を描画。
12bones/1skin/1秒loop/36tracks、画像付きmesh1、page error0。正面/斜め歩行を目視。
衣服の色むらは元テクスチャに残る。診断GLBは正式MCP納品物の代用にしない。

証跡: `npc-*-surface-final/acceptance.json`、`npc-*-surface-reject/acceptance.json`、
`surface-final-audit.json`、`npc-*-surface-final/render.json`とPNG、`rig-surface-full-test.log`。

NOT TESTED: signed installed/MCP、正常Hostの商店街全7モデル、物理スマホ。

## 回帰検証

`PYTEST_ADDOPTS=--basetemp=/tmp/mfs16-tests ./mf.sh test`:
**2496 passed /3 warnings /313.80秒 /exit0**。以後product変更なし。
新回帰は実面の断面/重複面/移動・拡大/不正・作業量上限、近接腕、疎な脚帯、
既存成功時の非再測定、縮約停止の拒否と固定案内。既存4/6脚・欠損腕の判定を維持。
GLBは青7,147,496B/85343 triangles、赤7,261,680B/85647 triangles（書出し後）。

## 0.33.16の公開・ローカル更新

PR642、source bb7dad8ce2cf2942222e96a8e35a763290e791ac、merge
1e5fc5197da72633f5b364bb57869609c2de4b72を固定して既存鍵で署名公開。
38,063,409B、SHA256 52b1fcd45850591c410a28a25c98d7cd24b58c7f9501aa3c0b86113c962c4149。
公開物再取得、signature/改ざん拒否、6tar/244embedded entry、worker source一致を確認。
新規dataのpackage起動.869142秒、Blenderなしをunavailableと正しく表示。

active MF Job/Blender session0でDB snapshot後、通常feature updateとservice restart。
current versions/0.33.16、PID217691、healthy .824489秒。更新前1580 Asset metadataと
代表3 AssetのHTTP SHA、served frontend、image-to-3D capability、TRELLIS/Pixalのruntime receipt SHAを保持。
モデルの新規取得なし。証跡release-0.33.16-20260923。

通常loginのHost HTTPで実OpenCode/Qwen3.8-27Bを起動。
最初のJob6903af33e230は誤って別のtool_contractを探す指示を与え、agentが自runの認証設定を
読んでMCPをHTTPで直接照会したため取消。秘密値は証跡へ転記せず、この経路を受入に使わない。
次の1b7ca9df922eは設定探索禁止を守ったが、buildに見えない道具をcapabilitiesから探し続けた。
Hostの現行providerを確認し、buildからscene/job toolsを外してsculptorへ割り当てる設計と判明。
これも正常cancelで停止。両runともMF生成Job0/停止後unit inactiveを確認し、重複生成なし。

正しい既存sculptor経路を明示したJob781d15da871fを開始。契約schemaはMCP一覧にあり、
別tool_contractは現設定では非公開。認証設定を読む必要はない。Host code/config変更なし。
元NPCの画像/3Dとscene.rig ratio=.30を使用。旧pipelineのratio=.15 failedを成功に読み替えない。
sculptorから公開MCPを実呼出し、両sceneの元headを確認してratio=.30を各1回送信。
media.job.statusで両方succeeded、元画像依存と元revisionを親に持つ第2版を確認。

|対象|MF Job|新revision|preview GLB Asset|
|---|---|---|---|
|coral|job_21bde7a799e54d0f90a46b00a67f10dd|revision_57fd9ebbce6f406e8b7bf361e4cffc3f|asset_fa903c1fd175423f93585a95bd82819e|
|blue|job_46200fdc76fc458e83642c036da13930|revision_84a16e0add014eb7bb460e95af194436|asset_0c7229a98f3043798fc8ca26985800dc|

両方12bones/1walk clip、重み欠損・不正0、最大4影響。DBのpreview metadataは
coral 7,261,520B/SHA7391b3924dfe7e0ea25ae8c39a3e1614e738a5073daa16cc06f5f45eaa4cd8ab、
blue 7,147,348B/SHAc110ffa2f46b8afc50efd3b600122e8e7bacc24e835fed35a52d48a366a7de72。
旧failed pipelineは再試行・書換していない。agentが書いたsubmitted_atは実Job時刻と
一致しないため時間計測には使用しない。通常grantでの納品と最終Web受入は確認中。
