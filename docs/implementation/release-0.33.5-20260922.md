# 0.33.5 派生画像と元3D・モバイル材質変更の実機受入

Date: 2026-09-22. 0.33.5で導線・材質保存・再起動後の関連保持を実測。
最終画面確認で履歴のモバイル配置崩れを発見し、0.33.6へ引き継いだ。

## 実装と公開

PR617で来歴から元scene/制作元版を解決し、Library画像と3Dのviewer/詳細から材質編集へ
移動できるようにした。通常Library画像編集も元の文脈を引き継ぐ。
PR618は元対象が無い際の未選択を材質再取得後も維持する。
PR619はHost opaque iframe内の合成click位置ずれを、既存単一tap補正で解消する。
source/Job履歴の一時状態ではなく、永続provenance・親Asset・owner照合を使う。

- source: `191f11c523e3804d64c7a24f8c3771fdd708709a`（PR619 merge）。
- release: <https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/0.33.5>。
- artifact: `control-deck-media-forge-0.33.5-linux-x86_64.tar.gz`、38,024,139 bytes。
- SHA256: `915aaf1a2a2df78b852199de1242dea8d6e365f2f2a2317579584daeb86ec2d2`。
- ./mf.sh test: **2410 passed / 3 warnings / 277.88秒 / exit0**。
  最終frontend contract160 passed、node構文/git diff確認も通過。
- 通常build/signで公開し、公開物を再取得。双方でcanonical manifest/size/SHA/Ed25519と
  改変manifest拒否、archive6/embedded241 entries、frontend/worker/model catalogのsource一致を検査。
  モデル重み/venv/SQLite/private keyの混入なし。
- fresh managed directoryで展開bundle起動0.864638秒、setup_required/runtime_not_installed。
  GPU runtime新規構築を確認したものではない。
- `/data1tb/ControlDeck/app/deck.sh feature update media-forge` exit0。
  current/manifests/process cwd/exeは0.33.5、更新後PID3727949/healthy。
  元1517 Assetのmetadata保持、元宝箱.blend/既存rig GLB/既存Qwen PNGのHTTP SHA一致。
  served frontendはsource bytes一致、既存TRELLIS/Pixal3D capabilityも変化なし。

0.33.3は材質対象の再取得問題を公開後に見つけ、prereleaseへ移してローカル未適用。
0.33.4は通常適用したがHost tap失敗を発見。両者の失敗を成功に数えず0.33.5で再検証した。

## 実Hostブラウザ

実Chrome、`http://127.0.0.1:8765/x/media-forge/workspace/library`、通常operator認証、
公開bundleそのものを1280×1000と320×844・touch有効で操作。コードの一時差し替えなし。

対象: 実FLUX画像`asset_bc049097a63e4d10afa7175d0f1b4726`、
元scene `scene_b9aad097879747d5ab674bdd78eda073`、
制作元/元current `revision_459c6661ae0a47b982cd7fbbd146d5f0`。
Mesh_0 / slot0 / base_color / UVMapを保持。

- 画像の「元の3Dを開く」で元sceneへ移動し、材質panelを開ける。
- 「この画像で材質を変更」で元の対象と画像を選択済みにして実Blender比較→破棄。
- 詳細で制作元の版GLBを表示し、3D viewerの「材質を変更」から戻れる。
- 各widthで実tap成功、image viewerボタン44/60px、詳細ボタン44px。
  frame/Host/viewerの横overflow0、page error0、allow-same-origin無しを維持。
- 元sceneの前後JSONは完全一致。比較/移動だけで旧assetや版を書き換えない。

## 材質採用・永続化

通常Host UIで元宝箱.blendを「モバイル材質変更の検証用コピー（宝箱）」として取り込み、
320×844のtapで2枚目画像を選択→比較→採用。元のsceneは前後JSON一致。

- コピー: `scene_7a6fca31d136460a8ed572d3bb9f605e`。
- 新版: `revision_b826443acd784bde98083161f59e9315`、版数1→2、旧版保持。
- source: `asset_a790a824d4af4dfb9605bb5419f43539`。
- GLB: `asset_5edcdcc822594888a6e1ff3570089df9`。
- dependencyは選択画像asset_bc049.../記録SHAと一致。
  GLBのbaseColorTextureを復号した1024角RGBA SHAと選択画像のRGBA SHAは
  `86781d18c34025a23c0b37a84cc9f0a96527c35dcab1f14137c07055fcd9fb15`で一致。
- サービス再起動後PID3729919/healthy。初回checkはlisten前に接続拒否となり、
  起動後の再確認で成功。再起動後も元画像→元scene/対象・画像選択を復元し、コピー2版と
  材質dependency保持を確認。元1517 Asset保持、総1521 Asset、Job0/未解放lease0。
- 最終screenshotで旧版説明幅0px/高さ1123.703125pxとなる配置崩れを確認。
  同じCSSの事前適用では幅236px/高さ61.984375pxへ復旧し、操作44px以上。
  これは0.33.6で正式配布する。0.33.5のモバイル見た目を完全受入とは扱わない。

## 証跡と対象外

Feature data `maintenance/release-0.33.5-20260922/` の
`artifacts/verification.json`、`downloaded/verification.json`、`clean-smoke.json`、
`update.log`、`after-update-check.json`、`scene-links-host.json`、`mobile-adopt-copy.json`、
`saved-texture.json`、`after-restart-check.json`、`after-restart-ui.json`、`host-final.json`、
`mobile-layout-patch.json`と各320/1280 screenshot。
先行source/fake画像の検査は `texture-scene-links-20260922/`。実画像検証と区別する。

NOT TESTED: 実スマートフォン本体、fresh GPU runtime構築、rollback、今回の変更による
新規AI画像生成。既存の実生成画像を使用した材質交換/来歴導線の受入であり、
AIがUV配置を完全保持する品質保証ではない。ControlDeck本体のsource変更なし。
