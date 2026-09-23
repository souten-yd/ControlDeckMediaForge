# 別方向の画像候補と比較・明示選択

## スコープ

branch `ux1/multiview-candidates-ui`、base `7bce85d`、0.33.22。
既存の1枚参照 `image.edit` から方向別の候補を作り、元正面と比較する導線。
CreativeBatch/Job/Asset/来歴とHost admissionを再利用する。
方向ごとに異なる指示を使い、正面を複製して面数を満たさない。
元画像・方向contextと実内容を採用時に照合し、別元画像/複製/削除/不一致を拒否。
生成成功、目視確認、校正、3D品質は別の判定とする。

## ソースでの実測

証跡root: feature-data/media-forge/maintenance/multiview-20260923。

- `node view-candidates-ui.mjs`: 実Chromiumのopaque iframe、制御した通信応答。
  PC1280/タッチ320で3方向依頼/取消/自動採用なし/比較後の明示選択/前方向未選択の拒否/
  複製候補拒否/正面変更時の候補隔離/最近のJobを消した後の候補再表示/詳細設定保持/
  英語/簡易モードの状況→比較を確認。横overflow0、操作44px、pageerror0。
  `view-candidates-ui/browser-activity-fix.log` と `result.json`。
- `node product-ui.mjs`: 従来の手動4面の個別選択/除去/再追加/取込/取消/詳細camera/
  1枚への復帰を1280/320で再確認。4previewが相異、overflow0/pageerror0/44px。
  既存installed4面の実contentも再取得し、方向ごとの保存SHA/来歴画素SHAと一致、
  全4枚相異を確認。`view-candidates-ui/existing-four-view-check.json`。
- 実ブラウザで詳細→簡易へ切り替えると、focused inputのblurが再描画を再入して
  DOM NotFoundErrorになることを確認。再入防止で解消。
  また簡易モードの状況が全batchを隠し比較入口も消していたため、方向候補を表示し、
  内部IDと子Job一覧は詳細だけに残した。初期失敗logを証跡へ保持。
- 隔離Uvicorn/SQLite/偽workerへの実HTTP: 正面1枚をimportし3方向を依頼。
  2件は `alpha_missing`、1件成功。全件成功を期待した評価helperは失敗しており、
  成功へ書き換えない。再送せず同DBを再起動して部分成功/来歴/異なる3指示を照合。
  Job履歴4件をclearした後も候補を復元し、成功画像だけをselectできた。
  `view-candidate-http-2/readback.json`。これは実モデルの品質評価ではない。
- preliminary全testは、通常Createへ方向batchが誤復元される問題の修正に際して
  自身のpytestだけを中断。1464passed/3warnings/228.40秒、exit2。
  full-test-interruption.jsonに対象と理由。最終gateとは別記録。

最終 `./mf.sh test`: **2576passed/3warnings/322.27秒、exit0**。
実行中にconstructorの戻り型 `None` 注釈のみ追加し、service testsも追加実行。

追加モデルdownload0。既存Assetや商店街は変更しない。
署名配布・installed新UIでの実生成/選択/Library・候補画質・物理スマホは
このソース受入時点で NOT TESTED。失敗候補を3Dへ自動投入しない。
