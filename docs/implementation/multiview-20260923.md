# 複数方向画像からの3D: 調査・評価・モバイル統合

Status: 調査中。現行の1枚入力を維持。追加UI/多視点runtimeは未採用。
利用者の2026-09-23依頼: 1枚→別方向画像生成→3D、手動2/3/4枚の追加、モバイル操作。
脚交差修正と商店街制作も継続し、本件で置き換えない。

## 2026-09-23 実sourceで確認した候補

| 候補 | 固定commit | 確認した内容 |
|---|---|---|
| TencentARC/Pixal3D | f7cf38429b0bd264f1995f0f8743a88b1c728b94 | `inference_mv.py`/MV pipeline/専用重み/カメラ付き複数画像を公式公開 |
| pwilkin/trellis.cpp | 883346efb49bd3b46875ea996cb9f195b954d525 | 従来採用は単一画像。出来たGLBの多面renderを多面入力と混同しない |
| raven38/pixal3d.cpp | a18bc842451e0f5f43276c7c3cc02f093cd7a5e3 | native `--views`/`--num-views`/カメラ付きPixal MV。Vulkan build候補 |

公式Pixal MVは別`*_mv`重みを使い、RGBAか背景除去画像＋Blender/NeRF camera-to-world、水平FOV、mesh_scaleを要求する。
元画像のframingをcameraと一致させる。独立crop/rescaleや1枚のコラージュを多視点入力と見なさない。
frame0は正面基準。公式既定例は0/90/180/270度、elevation0、20度FOV。
C++ forkはMVを4枚で、SVを1枚で検証したと記載。2/3枚も受けるが警告し、実機品質保証ではない。
C++ forkのq8_0 manifest 9ファイルは合計7.536239326GiB。これは重みサイズだけでVRAM実測ではない。
三repoのAPI licenseはMITだが、DINOv3/NAF等の依存と既存同意の範囲も確認してから重みを採用する。
OpsiClearの旧multi-image repoはGitHub API404。古い案内だけで採用しない。

## コミュニティ実装の区別

TRELLIS.2 PR104は画像条件をstepごとに替えるstochasticと、各画像の予測を平均するmultidiffusion。
カメラ付きPixal MVと同じ手法ではなく、常に精度が上がるとはしない。公式issue103に悪化の報告もある。
候補の採用は実コード、同条件1/2/3/4枚比較、未知方向の輪郭/材質/欠損/部位数/接地を実測して決める。
別方向画像を生成する処理は未知の背面を推測するので、元画像への一致と生成画像どうしの整合性を別に評価する。

## 実装前の評価条件

1. 固定source/依存/重み/license/hash、明示Vulkan、既存Broker lease、取消と失敗伝播を確認。
2. 同一物体の既知カメラ4画像で1/2/3/4枚を比較。seed/解像度を固定し、全入力の使用を来歴で確認。
3. 既存採用ローカル画像編集モデルで1枚から残り方向を作り、同一canvas/framing/色/部位を検査。
4. 人物と左右非対称の物体で、反対側の重複/脚本数/表裏入替り/テクスチャ投射を確認。
5. 有効な枚数と入力条件だけcapabilityへ公開。未測定のモデル/枚数をauto選択しない。
6. 1枚入力のpayload/出力/既存保存データ互換を保ち、端末画像/Libraryから2/3/4枚追加、方向変更/削除、生成候補選択を320pxでも操作。

生成元と派生画像は既存Asset/lineageへ保持し、3Dの入力依存を全画像に付ける。別アドオン/別asset基盤は作らない。
UIは「1枚から作る」「別方向の画像を用意する」「画像を追加」の流れを段階開示し、詳細でカメラ等へ到達する。
カメラ不一致や足りないruntimeは開始前に説明する。未使用画像を使ったように見せない。

証跡: managed data `maintenance/multiview-20260923`にAPI head metadata、tree、固定source抜粋。
候補source checkout `/tmp/pixal3d-multiview-20260923`。build・GPU生成・品質・mobileはNOT TESTED。
商店街は別の生成Jobを実行中なので、GPU評価を重ねて他の生成を中断しない。

## 参照した一次資料

- https://github.com/TencentARC/Pixal3D/blob/f7cf38429b0bd264f1995f0f8743a88b1c728b94/inference_mv.py
- https://github.com/TencentARC/Pixal3D#multi-view-inference
- https://github.com/raven38/pixal3d.cpp/blob/a18bc842451e0f5f43276c7c3cc02f093cd7a5e3/PIXAL3D.md
- https://github.com/raven38/pixal3d.cpp/blob/a18bc842451e0f5f43276c7c3cc02f093cd7a5e3/models/pixal3d-q8_0-v1/pixal3d-models.json
- https://github.com/microsoft/TRELLIS.2/pull/104
- https://github.com/microsoft/TRELLIS.2/issues/103
