# MediaForge 0.33.17

`asset.pack`で出力形式を省略すると、ZIPを選ぶようにしました。画像生成の既定PNGは変わりません。
明示的なPNG等の指定や複数出力は、Job作成前に必要な形式・個数を示して拒否します。
以前はPNGが入り、処理開始後に`unsupported_pack_profile`で失敗していました。

既存ZIP要求、元Asset/来歴、過去の失敗要求は保持します。モデル・runtimeの追加取得はありません。
検証記録は[pack出力既定](implementation/pack-output-default-20260923.md)を参照。
