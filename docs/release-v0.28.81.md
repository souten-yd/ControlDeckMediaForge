# v0.28.81 — MCPの任意形状メッシュと制作ガイド

既存のmedia.scene.create/editへmesh.createを加えます。頂点と三角/四角面から
髪束、衣服shell、防具等の基礎形状を作れます。頂点・面数とgeometry増幅の上限、
不正index、重複face、退化face等の検証をcoreと独立Blender workerで行います。
任意Pythonや外部pathを入力する機能ではありません。

media.capabilitiesにLLM/VLM向け制作ガイドを追加します。現在のschemaを確認し、
段階的に制作・確認・修正すること、画像を実際に見ていなければ視覚検証済みと
報告しないこと、構造・見た目・変形・ゲーム納品を別々に評価することを案内します。
詳細調査と高品質制作計画もリポジトリに追加しています。

sourceでは実Blender4.5.9で形状生成・GLB再import・CPU描画を確認しました。
試作はblockoutであり、高品質キャラクターの目標には未達です。
VLMの導入/自動評価、hair/cloth simulation、局所編集、複雑な変形と実engine受入は
今回の完成機能ではありません。M1のinstalled OpenCode受入は導入後に別途記録します。

DB migrationはありません。旧revisionと入力asset、既存Blender登録を保持します。
旧版へのservice rollbackは可能ですが、旧版はmesh.createを拒否するため、
新recipeの再試行には対応版が必要です。既存操作のschemaの意味は変更しません。
Web BlenderのOS自動セットアップ/完全隔離は未完了のままです。

配布・導入・OpenCode実行結果はdocs/implementation-status.mdへ実測後に記録します。

## 導入確認

固定commit f5093eaa9f9984e0b40364a91f115d61709dc5b3から署名配布し、公開物を再取得して
Host consumerで署名・サイズ・hashを検証しました。通常更新で.80から.81へ切り替えhealthyを確認。
DB16テーブル、制作ファイル2,392件のファイル情報、Blender登録は更新前後で一致しました。
稼働版のcapabilityでmesh.createと制作ガイドを確認しています。実OpenCode試験では
診断設定のツール制限を補正しましたが、作成引数の送信が中断され、制作・納品の受入は未達です。
M1完了ではありません。詳細はimplementation-statusに記録しています。
配布検証用の一時コピーは回収済みです。
