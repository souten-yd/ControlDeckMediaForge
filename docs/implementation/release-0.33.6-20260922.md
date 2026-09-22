# 0.33.6 派生画像・元3D・モバイル材質変更の最終受入

Date: 2026-09-22. マージ・署名公開・通常Host更新・実Host UIと再起動後の受入を完了。

## 利用者の操作

Libraryで3Dから派生した画像を開くと「元の3Dを開く」「この画像で材質を変更」が出る。
詳細には元シーン名・制作元の版があり、その版の3Dも呼び出せる。
元3Dのviewerまたはシーン詳細の「材質を変更」から、画像を選択→比較→明示採用する。
採用は新しい版として保存し、元の版を保持する。元対象が現行版になければ選び直す。
複数の元シーンがある場合は詳細から対象を選ぶ。320px幅でも同じ機能に到達できる。

## 実装と公開

- PR617: 来歴/ownerから元sceneと制作元版を解決、画像/3Dから材質編集、通常画像編集の来歴保持。
- PR618: 材質再取得後も、無くなった元対象の未選択を維持。
- PR619: Host opaque iframeでの合成click位置ずれを既存単一tap補正で解消。
- PR620: 520px以下の保存履歴と比較操作を縦配置にして全文表示・44px操作面を維持。
- source: `51a0e54e710d2e8cd7c5af9e54fa5390a2678f65`（PR620 merge）。
- release: <https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/0.33.6>。
- artifact: `control-deck-media-forge-0.33.6-linux-x86_64.tar.gz`、38,021,242 bytes。
- SHA256: `d9296580b33ea25e76d8248f20bd6ae126b67c2c42230828d355ff8d48ddd4e8`。
- ./mf.sh test: **2410 passed / 3 warnings / 274.07秒 / exit0**。
  最終frontend contract160 passed/0.10秒、git diff確認も通過。
- exact detached sourceで通常build/sign。公開物を再取得し、local/downloaded双方で
  canonical manifest/size/SHA/Ed25519/改変拒否、archive6/embedded241、frontend/worker/model catalog
  のsource一致、巨大モデル/venv/SQLite/private key混入なしを確認。
- fresh managed directoryでbundle起動0.864943秒、setup_required/runtime_not_installedを確認。
  GPU runtimeを新規構築した証跡ではない。

## 先行0.33.5での実保存

[0.33.5実測](release-0.33.5-20260922.md)の通常Host UIで、宝箱の検証用コピーに
実FLUX画像`asset_bc049097a63e4d10afa7175d0f1b4726`を採用した。
320×844 touchで比較→採用、版数1→2、旧版保持、元の宝箱scene JSON不変。

コピー `scene_7a6fca31d136460a8ed572d3bb9f605e`、
採用版 `revision_b826443acd784bde98083161f59e9315`、
GLB `asset_5edcdcc822594888a6e1ff3570089df9`。
GLBのbaseColorTextureを復号した1024角RGBAと選択画像のRGBA SHAは
`86781d18c34025a23c0b37a84cc9f0a96527c35dcab1f14137c07055fcd9fb15`で一致。
0.33.6ではこのコピーを保持して再検証し、追加の検証sceneや重複版は作らない。

## 0.33.6 installedと再起動後

`/data1tb/ControlDeck/app/deck.sh feature update media-forge` exit0。
current/manifests/process cwd/exeは0.33.6、更新後PID3738399/healthy。
適用前1521 Assetのmetadataを保持し、元宝箱.blend/既存rig GLB/既存Qwen画像のHTTP SHA一致。
app.js/styles.css/three-viewer.jsはexact source bytes一致、TRELLIS/Pixal3D capability変化なし。

実Chromeで通常Host URL `/x/media-forge/workspace/library`、通常operator認証を使用。
公開bundleのまま、1280×1000/320×844・touch有効で次を再確認した。

- 実画像→元scene、元対象と画像を選択済みの材質→実Blender比較→破棄。
- 詳細から制作元GLBを開く→3D viewerから材質へ移動。
- viewerの操作面44/60px、詳細44px。frame/Host/viewer横overflow0、page error0。
- opaque sandboxを維持。元宝箱sceneの前後JSON一致。
- 検証コピーの履歴説明は両版とも幅236px/高さ61.984375px。履歴操作44px、
  比較操作44/50pxで全文が画面内に収まる。比較の下段もscrollで閲覧でき、
  比較破棄と保存版3D表示が成功。保存GLBのbaseColor画素一致も再確認。

Job0を確認してサービスを明示再起動、0.828926秒でhealthy、最終PID3739883。
再起動後も320pxの画像→元scene/対象/画像選択、コピー2版/採用版ID/dependencyを保持。
再度1521 Asset保持/代表3SHA/served bytes一致を確認。Host effectiveもhealthy、
未解放lease0（履歴34件はreleased）、active Job0。
元checkoutは `feat/g9-image-to-3d` / `524553d` のcleanを保持。
独立source fixtureの自分が起動した9142プロセスは停止した。
実装・署名公開・通常適用の残件なし。以降の変更は受入文書のみ。

## 証跡と対象外

Feature data `maintenance/release-0.33.6-20260922/`:
`artifacts/verification.json`、`downloaded/verification.json`、`clean-smoke.json`、
`update.log`、`after-update-check.json`、`scene-links-host.json`、`mobile-layout.json`、
`saved-texture.json`、`restart-ready.json`、`after-restart-check.json`、
`after-restart-ui.json`、`host-final.json`と各screenshot。全suiteは
`maintenance/texture-scene-links-20260922/full-0.33.6.log`。
来歴の永続性/owner拒否/普通の画像編集の要求検査は
[実装証跡](texture-scene-navigation-20260922.md)に記録し、fake画像/sourceとinstalled実画像を区別。

NOT TESTED: 実スマートフォン本体、fresh GPU runtime構築、rollback、今回の変更による新規AI生成。
既存の実生成画像を用いた材質交換/来歴導線の受入であり、AIのUV配置保持を品質保証しない。
既定モデル/推論runtime/GPU設定とControlDeck本体のsourceは変更していない。
