商店街4店舗を実MCPでモバイル向けGLBへ軽量化し納品する。Webコード/人物/画像は変更禁止。新規画像/3D生成なし。
source GLB:
パン屋 asset_bed82e10e6c14c4f97c76a10ea4eda01
カフェ asset_47380d9455c64d268ddf5f89033f6f3b
花屋 asset_18e4a5a81d974b6b806a03dac399ab47
本屋 pipeline_9171d0e4e2d6421d9b1719c400eec575 のstatusから現在の成功modelを確認し、export awaiting_approvalならapproveしてGLB Assetを取得。

順番にmedia.generateでoperation=asset.pack、profile=3d.project.glb、inputs=[{asset_id:<source>,role:source}]、
intent=「既存店舗を画像とUVを保持して30000三角形へ軽量化」、constraints.compile_options={schema_version:3d.compile-options@1,triangle_budget:30000}、output={format:zip,count:1}、local_only=true。
まず発見済みtool_contractで正しいschemaを確認してから短い入力で実行。材料/画像はpreserveの既定、追加repair/merge/LOD不要。
返ったJob/ZIP Assetは直ちにevidence/shop-packs-final.jsonへ保存。各ZIPをmedia.inspectして通常grant/media.packで
exports/<bakery|cafe|florist|bookstore>-mobile.zipへ配置する。失敗ならその対象を再送せず記録。

shellでの通常ZIP検査/ファイル取り出しは許可（Blender/API直接実行は禁止）。ZIPは固定asset.glb/manifest.json/preview.pngのみを読み、
manifest内のSHAと実asset.glbを照合。元exports/<shop>.glbがあればexports/<shop>-source.glbに内容を保存し、
検証済みZIP内asset.glbをexports/<shop>.glbへ配置する。既存source控えがある場合はhash一致を確認して重複上書きしない。
assets/manifest.jsonの4店舗だけstate=exported、sha256=最終GLBのSHA、source_asset_id、pack_asset_id、pack_sha256、triangle_countを事実で更新。
来歴/scene/revision既存項目は保持。ZIP AssetをGLB Assetと混同しない。画像とUVを保つ。物理スマホ性能/品質評価は監督側が実施。
