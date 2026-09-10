# v0.28.62 — 保存済みアニメーション設定の確認

新しい制作版の検証結果に、Blenderへ実際に保存されたクリップ設定を追加します。
Job結果とscene snapshotから、実効fps、actionのフレーム範囲、rig/clip ID、
保存されたループ要求を確認できます。

`loop_requested`は保存metadataであり、滑らかな動きやゲームエンジンの再生設定の
合格印ではありません。一般のactionや読み取れない設定、重複、32件を超える分は
未報告件数へ計数します。旧制作版の情報欠落も「クリップなし」とは扱いません。

旧入力・既定値、画像・G8、既存制作版は変更しません。DB移行、HostやBlenderの
更新、モデル追加取得は不要です。新しい公開schemaはscene-animation-settings.jsonです。

## 検証と残件

PR #437でBlender4.5.13/4.5.9の実制作・保存・再読込を確認しました。
省略したidleはfalse、明示したbendはtrueで、実HTTPでも両制作版の設定を確認しています。
ソース版の全1524テスト、viewer build、Nodeテストが成功しています。

署名公開・4ファイルの再取得一致・Host署名検証後、標準更新を9.611秒で完了しました。
DBとBlender登録の保持、healthy応答、実行実体と新schema配信を確認しています。
実Host MCPでもJob結果とsnapshotのidle false/bend trueが一致し、GLB配置と
実Blender再読込による変形を確認しました（診断1.761秒）。
OpenCodeの判断改善への効果、GUI編集後の設定、複雑なキャラクター品質、
ゲームエンジン導入、全3D Studio受入はまだ未検証です。
