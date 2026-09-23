# 複数方向画像からの3D: 調査・評価・モバイル統合

Status: 公式4面のVulkan生成を評価中。現行1枚入力を維持。追加UI/多視点runtimeは未採用。
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
候補source checkout `/tmp/pixal3d-multiview-20260923`。build/4面GPU生成は下記で実施。
品質比較・mobileはNOT TESTED。既存Brokerのexclusive lease内で評価し、他の生成を中断しない。

## 2026-09-23 既存Vulkan資産の再利用と取得の訂正

利用者から「既に移植・取得済みなので不要なダウンロードをやめて」と指摘。
既存receipt `data/runtime-state/pixal3d-runtime.json`を実確認した。
採用済みはbackend=vulkan、SV/1024、Tencent b0cb2e1、
`runtimes/pixal3d-probe/candidates/native-surface32m-v1/pixal-generate`。
その版と既存重み・runtime registryは変更していない。Pixal3Dが未導入という扱いは誤り。

今回の候補はカメラ付きMV対応forkで、既存snapshotには専用`*_mv` flowがなかった。
しかし共通重みの棚卸し前に9ファイル全部7.536239326GiBを取得したのは不要な取得を含んでいた。
追加ダウンロードを停止し、既存ファイルの参照を使う評価構成へ変更した。

- 新たに必要だった専用MV flow: SS、形状512/1024、材質1024の4個、5.454660624GiB。
- 既存から再利用: DINOv3、NAF、SS/形状/材質decoderの5個。新しいコピーは作らず参照のみ。
- SS decoderは既存trellis snapshotとファイルSHA256が一致。
- NAFは既存GGUFとarchitecture metadataが異なるが、37テンソルの名前/型/値が全て一致。
  candidateのloaderはその重みを読める。DINO/形状/材質decoderは既存F16を使い、
  Q8 publisherの同一ファイルだったとは主張しない。
- 最初の実行の終端と再利用先を確認し、今回取得した共通5ファイル2,235,078,112B
  （2.081578702GiB）を削除。既存重みは削除/変更していない。

証跡: `reuse-manifest.json`（全参照先/サイズ/SHA）、`redundant-download-cleanup.json`。
以後の評価は`models/pixal3d-mv-reuse-v1`を使う。元publisherの9ファイル一括取得を再実行しない。
NAFは既存Apache-2.0帰属、DINOv3は既存同意の範囲を保持し、全体をMITと誤記しない。

## Vulkan実測と残る評価

固定a18bc842/ggml737e88f、GGML_VULKAN=ON、CUDA/HIP=OFFでnative build成功。
`trellis-cli` SHA256 7d36015a4728835ab9702583cedf2e8af224655957ddd017d1df22d527456e79。
公式fixtureの4RGBA/transforms.json、res1024/seed42、明示GPU1/R9700、require-gpu、4threads。
Host maintenance exclusive leaseを取得/更新/解放し、全4画像のconditioningを各段logで確認。

最初の全Q8構成: exit0、526.185103秒、device使用量の観測最大6,055,538,688B、
owned process RSS最大3,894,202,368B。VRAM値は0.2秒周期のdevice全体使用量であり、
プロセスの厳密な確保量ではない。GLB33,399,900B、SHA256
49d7a4f9d3d7a1d8a9ad36dfc4a7776bea6fae9ed779ebc099e2b65e0ac3d842。
Blender4.5.13再import: 1mesh/968076triangles/4096角2画像。有限geometry/UV/材質を確認。
同じ入力cameraで4面CPU render。完成品としての軽量化・方向・素材品質の採用判定ではない。
出力座標の照合を解決: conditioningはRot(x,y,z)=(x,-z,y)、Blender再importはP(x,y,z)=(-x,z,y)。
よって出力cameraへP×inverse(Rot)=diag(-1,-1,1)を適用する。fixtureのC0=Fなので追加の相対回転はない。
この変換なしの初回renderは背面をfrontと誤っていた。未補正画像も保持し、sourceから導いたcameraで
再renderした。見た目へ合わせ込んだ位置/倍率補正は行っていない。

再利用構成の同じ4面: exit0、531.780454秒、device観測最大6,989,856,768B、
owned process RSS最大3,885,461,504B。追加DL/重みコピー0。GLB SHA256
13d8fa1fccaeb5e94b8e0a4240da5e37ecc2750d01334342ad0b17bb43ef5a31、
1mesh/947980triangles/4096角2画像。全4面CPU renderを目視し、顔/横/後頭部の対応を確認。
512角alpha threshold128の輪郭IoUは、全Q8の4面平均0.980354796、再利用版0.980221599。
同じ入力/seed/解像度の形状整合は近いが、元画像の細かい表面模様や鼻輪の色は忠実ではない。
輪郭一致を高品質素材や全体の採用判定に読み替えない。

2/3枚比較、1枚との改善比較、左右非対称/人物、
生成した別方向画像、取消、installed/MCP、320px UIはNOT TESTED。モデル一覧/autoへは採用しない。
1枚→別方向画像の既存image.edit試行は1024/512ともresource_oomで失敗。
実画像がないため生成視点の品質成功としない。証跡`generated-right*`。

## 参照した一次資料

- https://github.com/TencentARC/Pixal3D/blob/f7cf38429b0bd264f1995f0f8743a88b1c728b94/inference_mv.py
- https://github.com/TencentARC/Pixal3D#multi-view-inference
- https://github.com/raven38/pixal3d.cpp/blob/a18bc842451e0f5f43276c7c3cc02f093cd7a5e3/PIXAL3D.md
- https://github.com/raven38/pixal3d.cpp/blob/a18bc842451e0f5f43276c7c3cc02f093cd7a5e3/models/pixal3d-q8_0-v1/pixal3d-models.json
- https://github.com/microsoft/TRELLIS.2/pull/104
- https://github.com/microsoft/TRELLIS.2/issues/103

MediaForge product変更なし。基準82a69c7の全2471tests/401.67秒の既存gateを維持し、
今回はnative実評価と文書のみ。既存Pixal/trellis receiptの参照ファイルも変更していない。
