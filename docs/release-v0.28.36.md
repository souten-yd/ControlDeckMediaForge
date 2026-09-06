# v0.28.36 — Libraryの英語表示と受入確認

Libraryの詳細表示で、検証記録がない場合の英語文言を「Not recorded」に統一しました。
読み込み中の詳細見出しも英語になります。既存Asset、scene、Blender runtime registryの
形式や公開APIは変更しません。

sourceでは親65件・子63件の関連素材を、既定60件のページ送りで欠落・重複なく辿り、
前ページへ戻れることを日英320pxで確認しています。これは明示したsynthetic lineageの
試験で、実制作や本番データの60件超受入を意味しません。

Hostの汎用言語通知修正を含む環境では、既存0.28.35でも実Hostからの動的通知による
Libraryの日英切替と選択・関連一覧・接続の保持を1280/320pxで確認済みです。
言語入力はbrowser languagechange fixtureで、ブラウザ設定画面の操作とは区別します。
新バンドルとinstalled0.28.36の受入結果は公開時に追記します。

統合3D Studioの全必須受入は引き続きPARTIALです。既知のlive resize直後の入力不達、
全失敗/取消/資源競合matrixなどは、この文言修正で解消したとは扱いません。

## 更新・ロールバック

ControlDeckの標準署名検証付き更新を使用します。更新前にJob/GUI/環境処理の終端を確認し、
DBとruntime registryのsnapshotを保持してください。0.28.35からschema変更はなく、
同版へのcore rollbackで新しいデータ変換は不要です。Blender環境は別管理のまま保持します。
0.28.34以前へ戻す場合は、0.28.35 release noteの履歴削除/同版再導入・registry互換条件も
確認してください。利用者の既存Blenderやグローバル設定へは書き込みません。
