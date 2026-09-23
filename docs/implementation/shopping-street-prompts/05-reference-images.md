商店街の店舗4種類と歩行者2種類の元画像を、MediaForge MCPで各1枚（計6枚）作る工程。
この工程では3D化しない。evidence/references.jsonが既にあれば既存結果を回収し、再生成しない。
media.generate.batchの実schemaを読み、一括生成を1回だけ呼ぶ。model_policy=auto、local_only。
各1024x1024、output PNG、背景は白、影なし、対象全体が枠内、温かい立体イラスト調。
画像の意味条件はintentだけでなく公開schemaのasset_briefにも適切に指定する。

店舗は全て「単独の小さな日本の路面店の建物」。通り全体やジオラマ台座は描かない。
正面から少し斜め、左右の外壁・屋根まで完整。文字は短い装飾的看板だけでよい。
1 bakery: brick-red roof, cream plaster, sage green striped awning, wide glass shopfront,
  bread baskets behind glass, warm Japanese neighborhood bakery, no people, isolated whole building.
2 cafe: terracotta roof, warm wooden facade, deep teal awning, large cozy window,
  coffee cup sign, two-floor compact Japanese neighborhood cafe, no people, isolated whole building.
3 florist: cream roof, pale blush plaster, forest green trim, small flower planters integrated
  against storefront, single compact Japanese flower shop, no people, isolated whole building.
4 bookstore: dark blue roof, pale timber facade, rust-red canopy, books visible through large
  storefront window, cozy compact Japanese bookshop, no people, isolated whole building.

人物は一人ずつ、頭から靴まで全身正面A-pose、腕と胴・両脚の隙間を明瞭に。
主人公のexports/player-source.pngと同じ程度の様式化（その画像は新規生成しない）。
5 npc-coral: friendly adult woman, short auburn bob hair, coral cardigan, cream shirt,
  navy straight trousers, beige sneakers, empty hands, no handbag, plain white background.
6 npc-blue: friendly adult man, short brown hair, sky blue casual jacket, white shirt,
  olive straight trousers, white sneakers, empty hands, no bag, plain white background.
人物に台座/床/影/文字/複数view/他人を入れない。手足を切らない。

完了応答に含まれる各Job/Assetをmedia.inspectで確認。
配置直前にoutput grantを取得し、media.packのBATCHでexports/bakery-source.png、
cafe-source.png、florist-source.png、bookstore-source.png、npc-coral-source.png、npc-blue-source.pngへ配置。
evidence/references.jsonへ呼び出し実引数、各対応/Job/Asset/hash/receiptを保存。
HTTPエラーやtimeoutは未生成の証拠ではない。生成呼び出しを再送せず、その場で記録して終了。
見た目は監督側が評価するので、生成/pack成功を外観合格と書かない。
