# v0.28.85 — 参照画像から改善する3D制作基盤

MediaForge内の既存scene/Jobs/Assetへ、参照セット保存、revision固定の多視点観察、
Hostの実画像レビュー、別候補を比較する有限の修正ループを追加します。
曲面loft/sweep、断面編集・開端接合・subdivision、UV seam/unwrap/pack、CPU法線/AOベイク、
局所ウェイト補正、脚IKの焼込み、回転互換の移動キーが使えます。
ビューアーは動作のloop/1回再生を扱い、停止でrestへ戻せます。

公開契約は加法拡張です。既存回転クリップのpayloadと意味、画像生成のGPU譲り渡し動作を保持します。
新recipeは配信されたcapabilities/schemaを確認して使ってください。
画像レビューと候補選択は助言であり、品質承認ではありません。
このリリースのsource実機試験は曲面・ベイク・変形のfixtureおよびGLB再import/ビューアー操作です。
実VLM、installed MCP/OpenCode、恐竜の比較は配布後の別受入として記録します。

DB schema変更はありません。更新前のDBとruntime registryを退避し、旧source/GLB/履歴を照合します。
旧0.28.84へrollbackすると新tool/operationを使えず、新しいreference_set dependencyを含むsceneを
そのまま旧版で扱えるとは保証しません。新scene/Assetを退避してから更新前snapshotを復元する
復旧経路を残します。既存制作物とBlender本体の削除・変換は行いません。
