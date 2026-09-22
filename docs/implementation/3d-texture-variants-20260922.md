# 既存3Dの材質画像から派生候補を作る

Date: 2026-09-22. Branch: `ux1/3d-texture-variants`.

利用者が既存3Dの画像をAIで改善し、画像だけ複数作って選択・貼り替えたいと依頼。
既存の画像Job/Library/MaterialBinding/比較・採用を拡張し、別の基盤を追加しない。

## 実装

- 材質パネルに現在画像/選択したLibrary画像/新規作成と1〜4候補を追加。
- private `scenes.material.extract` はownerとcurrent revisionを確認し、
  trusted Blender workerでpacked base color/emission画像を抽出する。外部参照や
  複雑なshader、normal等の物理mapは推測して変換しない。
- 抽出画像に元.blendのID/hash/licenseを記録。派生画像は通常のimage.edit入力から
  parent lineageを持つ。画像生成だけではsceneを変更しない。
- 候補サムネイルを選び、既存の材質比較→採用へ渡す。過去候補も同じ対象ごとに表示。
  reload時はdurable Jobから復元。1画面24候補、過去画像は共通Libraryにも保持。
- UV領域の配置を保つ編集指示を付けるが、AIによる位置ずれや質感改善は保証しない。
  テクスチャは3Dに貼った比較を経て採用する。

## 実測

証跡はFeature maintenance `texture-variants-20260922/`。

`PYTHONPATH=backend:. .venv/bin/python .../extract-real.py`:
既存Pixal3D宝箱の.blend Asset `asset_81497d6049c5440e9a22fecee6b11848`を
正規content APIで読み、独立dataに複製してBlender4.5.13で検証・抽出。
Mesh_0 / slot0 / Base Color / UVMapから4096×4096 RGBA PNG、20,926,322B、
5.001458秒。SHA `117a11d2d68f12d692755c6c51492135368c2f3e13c5bdbd712431c666907217`。
元.blend bytes、元scene/revision不変、抽出画像のparent lineage、作業一時ファイル0を確認。

`node .../ui-source.mjs`:
実core/Blenderの独立fixtureに対し、画像workerと編集capabilityだけを明示fakeとして
Chromeで確認。1280pxで3候補→2枚目を選択→実Blender材質preview→旧版/候補の
2画面比較→破棄を通過。scene不変、page error0。320pxでoverflow0、reload後も
候補復元。これは実AI画質やinstalled-host生成の受入ではない。

初回全suiteは新規テストのJSON schema照合で`grant_id:null`もserializeしたため
1 failed / 2380 passed。入力schemaに合わせexclude_noneへ修正し当該テスト通過。
続く全suiteは既存のadmission待機2秒timeout、再実行は既存のautosave
起動を含む1秒制限で1.170秒となり、それぞれ1 failed / 2380 passed。
前者のcancellation6条件は個別再実行で通過。新機能の失敗と混同しない。
PR612のQwen sliceを統合し、0.33.0として ./mf.sh test:
2400 passed / 3 warnings / 272.68秒 / exit0。既存の時間制限テストも含め全件通過。

## 残件

PR merge、Qwen通常生成sliceとの統合、署名release・通常更新、実Hostの画像編集3候補、
Library lineage、材質比較、モバイル/restart受入は未実施。実AIでのUV保持・
改善品質はNOT TESTED。元checkoutは変更していない。

## 0.33.0 installedで判明した出力寸法の欠落

正規Hostで4096角の抽出まで成功したが、image.editの候補寸法が未指定のため
入力4096角が生成上限検査へ入りresource_limitで失敗。0.33.1で候補1024角を
明示し、画面にも表示する。実AI候補の再確認はこれから。

## 2026-09-22 3Dテクスチャ参照編集の実測と枠修正（0.33.2準備）

0.33.1でQwen横長1024×768と背景除去付き1024角PNGを実Hostから生成・Library登録済み。
宝箱の材質抽出は成功したが、編集adapterが元の4096角を推論寸法に使い、通常生成の
8.8GiB枠でOOMした。画像編集の実機測定を追加し、0.33.2で次を修正する。

- texture候補だけ参照画像を要求canvasへ揃えて推論。元Assetは保持する。
  coreもscene_textureでは学習面積への拡大を行わず、測定済みの各辺内で渡す。
- 実FLUX.2-klein/int8/cpu_offload、元4096角→候補1024角3枚を51.990秒で生成。
  3SHAは別。通常Host lease14GiB、Torch上限12GiB、GPU全体ピーク12,581,740,544B。
  先の同条件12GiB lease試験では13,057,523,712Bで監視停止したため、この観測最大値を
  texture専用profileのpeakに採用。通常生成の値・モデル選択・依存は変えない。
- texture実測profileでpeakと所要時間をbrokerへ申告し、workerは測った12GiB内へ制限。
  GPU以外の余裕は既存headroomを維持。最終成功runはHost200、cgroup OOM0、lease返却済み。
- ./mf.sh test: 2407 passed / 3 warnings / 275.70秒。0.33.2 installed UI/3D比較は公開後。実測原本: maintenance/texture-runtime-20260922。
