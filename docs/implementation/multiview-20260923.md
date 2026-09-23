# 複数方向画像からの3D: 調査・評価・モバイル統合

Status: 手動複数面は0.33.20を署名配布・通常導入し、実4面生成/PC・320px表示/取消を確認済み。
自動方向候補は評価中。側面は形状不一致で未採用、背面の実OpenCode/MCP要求は受付前に失敗。
契約修正候補の進行は[画像編集MCPスキーマ](image-edit-mcp-schema-20260923.md)を参照。
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

1枚との改善比較、左右非対称/人物、
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

## 2面の比較と1面用既存重みの棚卸し

main6383fdcをmergeし、製品差分なし・文書3ファイルだけの差分を確認。
公式4面と同じnative/shared weights/res1024/seed42で、先頭の正面/右側面2枚を入力。
既存Brokerのmaintenance/exclusive lease 80cb64f4-eb39-4ab1-972d-4f290917af74を取得し、
108回更新後にreleased。既存画像/重みのみを使用し、追加取得/重みコピー0。
official-2-reuse: exit0、543.873269秒、device観測最大5,981,609,984B、
owned process tree RSS最大4,074,057,728B。各conditioning段のview0/1使用をlogで確認。
このVRAMはdevice全体の0.2秒周期観測であり、厳密なプロセス確保量ではない。
GLB SHA256 54cc4eca5cfa5a7d915f2bbddd19e9dbe71051c6e6e87aa7c269bb7d9dc3d29a。
Blender4.5.13実再importは1mesh/947086triangles/622043vertices/4096角2画像。
既存render-calibrated.pyで元camera4方向をCPU描画。正面/背面の2面版と4面版を目視し、
顔と後頭部の対応を確認。見た目だけで4面が優れるとは判定できない。

compare-silhouettes.pyは元RGBAのalphaを1024→512 LANCZOS、閾値128で同条件比較。
形状の位置/倍率を合わせ込まず、上記source由来の座標変換だけを使用する。
4面の再計算は既存値と完全一致。2面の非入力方向も検査した。

|入力|正面|右側面|背面|左側面|4方向平均|
|---|---|---|---|---|---|
|2面|0.983405|0.978032|0.979296|0.977966|0.979675|
|4面|0.979751|0.979788|0.981167|0.980181|0.980222|

これは公式の1物体・1seedの輪郭IoUであり、一般的な生成精度/材質再現の改善証明ではない。
前景/背面の大形状は両者で近い。正面の鼻輪・目・細部の色や模様は差があり、
人物/非対称物体の品質、2面の採用判断は未受入。
証跡official-2-reuse/{result,render,silhouette-calibrated-comparison}.json/4PNG。

既存installed単視点descriptorのSS/形状512/形状1024/材質flow4ファイルも棚卸し。
GGUFReaderでそれぞれ700tensorの名前とshapeがcandidateの対応MV flowと一致することを確認。
これは互換な構造の確認であって、重み値の一致や単視点実行の成功ではない。
既存F16単視点4flowと共通5個への9symlinkをmodels/pixal3d-sv-reuse-v1へ作成。
sv-reuse-inventory.json、sv-reuse-manifest.jsonに根拠を保存。再取得/重みコピー0。
1面の比較はMV重みを1枚へ誤用せず、--pixal3d-weights svを明示する準備をした。
その1面と3面のjob JSONは準備のみ、まだ実行していない。SVは既存F16/MVはQ8なので、
今後の差を画像枚数だけの効果とは呼ばない。既存単視点runtimeの登録は変更していない。

## 3面の実測（2026-09-23追記）

上記準備済みofficial-3-reuse-job.jsonだけを新規実行。既存a18bc842/binary/9参照重みと
同じ公式RGBAの先頭3枚（正面/右/背面）、res1024/seed42/GPU1/R9700。
各conditioning段でview0/1/2の使用をlogで確認。追加ダウンロード/重みコピー0。
Host maintenance/exclusive lease4ddce9d0-86e3-42a1-8a9a-9c8a5458cbe3を105回更新後released。
exit0、531.111765秒、device観測最大5,973,966,848B、owned process tree RSS最大3,806,732,288B。
GLB35,564,196B、SHA256 ae2b29fd59d133679b0e23c233f25b98101dfba57e984482167076b7651b7039。
Blender4.5.13再import:1mesh/991406triangles/674113vertices/4096角2画像、有限geometry/UV/材質。
既存render-calibrated.pyで元camera4方向をCPU描画、geometry変更なし。
正面と背面を目視し、顔/後頭部/台座の対応を確認。材質は輪郭IoUから評価しない。

|入力|正面|右側面|背面|左側面|4方向平均|
|---|---|---|---|---|---|
|3面|0.980511|0.979946|0.981542|0.979996|0.980499|

2/4面と同じ512角・alpha閾値128・camera変換だけで比較。3面が全般に優れるとは判断できない。
非入力の左側面も輪郭は近いが、今回の公式fixtureはほぼ対称な1物体である。
証跡official-3-reuse/{result,render,silhouette-calibrated-comparison}.json、stdout.log、camera-0〜3.png。
1面SVは未開始。人物/非対称物体/生成視点/取消/installed/MCP/320px MV UIはNOT TESTED。
既存単視点receipt/登録は保持。製品へのMV採用は未完了。今回は文書のみ更新。

## 1面SVの実測と参照画像編集の失敗箇所

既存SV F16 flowと既存共通5重みの9参照だけで、同じnative・公式正面・res1024/seed42を実行。
`official-1-sv-reuse`: 453.378568秒/exit0、Broker90回更新/released、
device観測最大6,727,626,752B、owned process tree RSS最大3,167,158,272B。
GLB SHA256 f772bad7e965875252af9ff5b3d1cd468e4a8663c800f2a2bd74e021b5ddfb82。
実Blender4.5.13で1mesh/970868triangles/651265vertices/4096角2画像を確認。
元camera4方向をCycles CPUで描画し、正面と背面を目視。追加DL/重みコピー0。

| 入力 | 正面IoU | 右IoU | 背面IoU | 左IoU | 平均IoU |
|---|---:|---:|---:|---:|---:|
| 1枚SV | .979940 | .860550 | .877435 | .861829 | .894938 |
| 2枚MV | .983405 | .978032 | .979296 | .977966 | .979675 |
| 3枚MV | .980511 | .979946 | .981542 | .979996 | .980499 |
| 4枚MV | .979751 | .979788 | .981167 | .980181 | .980222 |

この物体では複数面の側面・背面の輪郭が元画像に近い。SVの背面は首/台座の接合形状が異なる。
ただし1物体・seed42であり、SV F16とMV Q8 flowというモデル/精度の違いもある。
枚数だけの効果を分離した比較でも、一般的な品質向上・テクスチャ忠実度の証明でもない。
証跡: `official-1-sv-reuse/{result,render,silhouette-calibrated-comparison}.json`、camera-0〜3.png。

先の参照編集失敗はLLM同居だけが原因とは確定できないため、quiet条件で1回再評価した。
`generated-right-512-quiet/quiet-before-submit.json`: device270,532,608B、active/reserved lease0。
実Host Job8a2765972b00 / MF job_ea504bbddcdd4382825976fd190da193はresource_oom。
workerはHIPの上限8.80GiBに達し2.25GiBの確保に失敗。device空き23.20GiBという実エラーを保存。
core sourceは通常生成の枠を参照編集にも使い、別測定済みの編集枠はscene_textureだけに限定していた。
さらに通常参照編集は元画像1024角で推論し、要求512角への縮小は後処理だった。
同一要求を反復せず、既存重み・明示Broker leaseで編集枠を個別評価する。
未解決時点で自動視点生成や生成画像の整合性を成功扱いしない。
人物/左右非対称、取消、installed/MCP/320pxでのMV操作はNOT TESTED。

## 入力画像の重複監査（利用者からの確認）

`input-view-identity-audit.json`で全実行のargv/transformsと実入力を再照合。
正面3be4c193…、右d1fbbd66…、背面3ad7d9a9…、左fdffe243…は全て異なるSHA256。
4枚を目視し、実際に0/90/180/270度の別画像であることを確認。native logはSS/形状/材質の
各conditioningでview0〜3を処理。2枚は正面/右、3枚は正面/右/背面、4枚は全方向。
正面1枚を複製して複数面として投入していない。生成AIの側面候補はどの3D実行にも未使用。

base-plan/統合/3D UI設計へ加法方針を記録。単一画像互換、全入力の来歴/固定、重複内容の拒否、
各方向の実画像の表示、手動入力と自動候補の分離、camera仮定と実校正の区別、320px操作を要求。
これらは実装目標であり、現在の製品に複数面UIが導入済みという記録ではない。


参照編集の不足した枠は別PR651/0.33.19で修正し、通常Host経由の512角候補をLibraryへ保存した。
PC/320pxで実表示、元正面Assetと公式正面のdecoded RGBA画素一致も確認済み。
512角では顔が片側になったが、構図/材質/厳密な角度は未受入で、3D入力にはまだ使わない。

## 入力の実画素検査・人物と非対称・実行取消

専用operatorへ通常再ログイン後、0.33.19参照編集のHost Job50f9ce2160f3のlease
057d8785-5975-439f-ad44-1696285ce14cが`released`と通常HTTPで確認できた。
その時点のactive/reservedは0。以前の期限切れ後の終端照会NOT TESTEDを解消した。
再生成/追加モデル取得は行っていない。

`scripts/verify_multiview_inputs.py <views-directory> [--count 2|3|4]`を追加。
これはoperator用の読み取り専用評価道具であり、製品UI/APIやruntime採用を有効にしない。
実画像2〜4枚、共通の正方形RGBA canvas、非空の前景と透過、境界内のファイル、
有限・正規直交・右手系camera、FOV/距離を検査する。同じpath/poseや重複JSON keyも拒否する。
入力順、全ファイルSHA、alphaを乗じた8bit画素SHA、camera、選択した枚数を一つのJSONに出す。
透明画素のRGBやPNG圧縮を変えても同一画像を別方向として通さない。似た画像の知覚判定、
写真とcameraの実対応の推定、生成品質判定はしない。

実fixtureで公式4面と人物4面の検査成功を確認。同じ公式正面を別名・異なるPNG圧縮にした
negativeは`duplicate_image_content`で拒否され、native生成へ投入していない。
証跡`official-input-preflight.json`、`person-input-preflight.json`、`same-pixels-rejection.json`。
native sourceも各frameのpathからRGBAを読み、SS/LR/HR/材質ごとに`views[v].rgb_premult`を
使うことを固定a18bc842の`trellis_cli.cpp`、`pixal3d_cond.cpp`、`pixal3d_cond_gpu.cpp`で再照合した。

取消は公式4面のnativeだけを新規起動し、SS flow実行中20.062806秒で自身のprocess groupへ
SIGTERM。0.200211秒でexit -15、process group消滅、GLBなし、lease
0c809c39-e559-42e8-a7de-bb8007346d6eを4回renew後`released`。
`official-4-cancel/result.json`とSS step10/12のlogを保存。
これは実nativeとoperator supervisorの取消受入であり、未接続の製品MV Jobs/UIの取消受入ではない。

人物の検証画像は商店街の既存主人公GLB（SHA14e5b8c2…）を読み、rest poseと同じ材質を使う。
検証用sceneだけに片側の赤い持ち物を加え、全体を同じ倍率で正規化して、公式と同じ4cameraで
Cycles CPU/1024角RGBAを描画。元GLBの前後SHA一致、4PNGのSHAが全て異なることを確認した。
最初の補助描画はglTF importerの不可視bone widgetまで可視化する誤りがあり、画像を見て拒否。
visible meshだけへ修正して再描画した。拒否した画像はどの3D生成にも使っていない。
これは実物の4方向写真やAIで生成した方向画像の受入ではなく、既知cameraの検証用画像である。

4面`person-asymmetric-4`: Vulkan1/R9700、同じ既存9重み参照、res1024/seed42。
138.620338秒/exit0、27回renew/released、device観測最大6,077,775,872B、
owned tree RSS最大1,643,675,648B。追加DL/重みコピー0。
GLB SHA44035566e8a950c0e3cbf09ca349dc09b9cf5f46dc62221af14b10417d5b11d8。
Blender4.5.13で1mesh/991928tris/750663vertices/4096角2画像、元camera4面CPU描画。
輪郭IoUは正面.965098/右.961427/背面.965805/左.958688、平均.962755（位置/倍率のfitなし）。
目視した4面で顔は前側、脚2本、片側の持ち物を保持。前/背面の赤い領域の重心は元画像から
512角で1px未満、反対側へ大きな赤い領域の複製なし。これは色領域の補助観測であり、
厳密な材質忠実度・細かい手指・rig/歩行・軽量化は未受入。

同じ人物の正面/右2面`person-asymmetric-2`も132.692209秒/exit0、26回renew/released。
device観測最大5,866,340,352B、owned tree RSS1,613,254,656B。
GLB SHA f90291755d983284836d31a014b51d220d9f044eea75211b7f8093a0da2931aa、
1mesh/964868tris/755617vertices/4096角2画像。平均輪郭IoU.960514。
正面/未入力の背面・左面を目視し、脚2本・持ち物の片側保持を確認したが、
入力していないバッグの背面へ白い矩形模様が生じた。4面版にこの模様はない。
輪郭の近さだけで材質を受入としない。2面実行はCPUの全unit suiteと時間が重なっており、
138秒対132秒を枚数による速度改善の証拠にはしない。

正面/右/背面3面`person-asymmetric-3`は127.899962秒/exit0、25回renew/released。
device観測最大6,791,278,592B、owned tree RSS1,684,561,920B。
GLB SHA388f638d02572136d6c4387e05c27c3a7d7f98f05418eb213559b71ec848a51a、
1mesh/998786tris/878753vertices/4096角2画像。
元camera4面での平均輪郭IoU.958994（正面.967073/右.953912/背面.966784/左.948207）。
背面を含む4面を目視し、2面版のバッグ背面の白い矩形模様が3面版にはないことを確認。
赤い持ち物は片側で、後頭部へ顔が描かれていない。輪郭IoUは2面よりわずかに低いため、
枚数増加による全指標の単調改善や全素材への保証にはしない。別方向の入力で未入力面の材質の
逸脱を減らせた1例として記録する。追加DL/重みコピー0。
3人物runと取消runの4leaseが全てreleased、active/reserved0を最後に通常Host HTTPで再照合。
既存trellis/Pixal SV receipt SHAは不変。証跡`person-and-cancel-resource-terminal.json`。

入力検査の対象17testsを通過。最終`./mf.sh test`は2537passed/3warnings/338.77秒、
skip0（既存bundle build環境参照あり）。試験ログ`input-preflight-full-test.log`。
当初のテスト記述の構文誤りは修正後に全体を実行した。runtime採用・製品code/UIの変更はない。

### 製品へ接続するときに同時に扱う境界

- APIは既存1枚payload/過去のretry JSONを保持し、複数面だけを加法的に指定する。
  未採用MVを受けて既存SVへ落としたり、先頭画像以外を無視したりしない。
  現在のtrellis.cpp→Pixal3Dの2段は同じ1枚から各エンジンで生成して版を残す実装であり、
  複数面でも前段meshの加工でもない。「仕上げ」の文言と複数面入力を混同させない。
- 全入力を受付で検証・pinし、admission/staging/再試行/出版直前にも照合する。
  既存`Store.delete_asset`の稼働scene.from_image保護は単一`input_asset_id`だけなので、
  追加した全画像を同じ保護へ含める。公開したscene dependency/lineageも全画像を記録する。
- 現行Pixal SV receipt/prepared入力はfloat32/CPU camera推定の事実を表す。
  MVのQ8 flow＋既存F16共通重み・native conditioningをそこへ偽装しない。
  実測した独立のprivate MV receiptと加法的実行来歴を持つ。
- nativeはRGBA画像をそのままcameraへ対応させる。単視点の独立crop/framing処理を
  流用しない。JPEG/HEICからの背景除去は共通canvasを保持する別の受入が必要。
- 簡易画面は正面/右/背面/左の画像を見せ、追加/差替/削除を320pxで操作する。
  詳細でcameraの前提と設定へ到達できるようにする。撮影方向のラベルだけで校正済みとはしない。
- 自動の方向画像は既存image.editで候補として保存し、方向ごとの比較・選択を挟む。
  失敗候補を自動投入しない。手動の複数面入力と従来1枚生成は独立して使えるようにする。

製品へのMV runtime/UI接続、実MCP/installed/モバイルMV操作は引き続きNOT TESTED。
1024角候補には顔重複が残る。詳細は[参照編集の実測と導入](reference-edit-admission-20260923.md)。
生成/Library表示確認後に専用operator認証が期限切れになり、通常logoutと再ログイン依頼を実施。
再認証後のGPU評価・製品MV runtime/UI統合を続ける。既存の1枚生成と採用receiptは保持。
## 製品への接続: 0.33.20 source受入

`ux1/multiview-generation`で既存`scene.from_image`へoptionalな
`additional_views`/`view_camera`を追加。1枚の保存要求は新しい空fieldを含めず従来互換。
2枚=正面/右、3枚=正面/右/背面、4枚=全方向に限定し、全入力の実画素SHA・
共通canvas・透過・来歴を検査する。入場、待機、準備後、公開直前で同一性を確認し、
生成中は全入力の削除/Trashを拒否。取り消しは既存Jobのprocess/lease cleanupを使用。
単視点とは独立したprivate receipt、mixed precision来歴を持ち、未採用時の1枚へのfallbackは行わない。

モデル追加取得/コピー0。nativeと共有libraryだけ67,336,656Bを永続runtimeへ複製し、
全13memberと既存9重みのSHAを検証した。実行時と同じ`LD_LIBRARY_PATH`で
`ldd`の全ggml依存が永続runtime配下に解決することを確認。
`maintenance/multiview-20260923/candidate-runtime.json`はsource用候補であり、
installedの新機能採用はこの時点ではNOT TESTED。

private `product-source.py`から実`ThreeDGenerator.prepare/generate`を実行。
通常operator認証のHost Broker leaseを取得、人物の異なる4RGBAを投入した。
141.713559秒、device全体観測最大6,943,510,528B、28renew、released。
GLB SHA `d365be30f9552f01339a7ce7b642d8401443faf29e3b40c80178655c88d32305`。
実Blender4.5.13で既存Scene/Assetへのimport、4親画像/4dependency/mixed precision来歴を照合。
991,928tris、750,663vertices、4096角2texture、EXT_texture_webpの構造検査通過。
同cameraでCPU4方向を描画し、顔/後頭部・2脚・片側バッグと画像材質を目視。
これは既知cameraの人物1fixtureであり、任意写真の整合性やrig/deformation受入ではない。
初回private helperはtimeout設定、次はDB初期化不足で生成前に終了。成功runはv3だけで、
途中で私有source workspaceディレクトリを作成した。製品の失敗や再生成として計上しない。

source実Chromeのopaque iframeでPC1280/touch320を操作。
異なる4preview、方向別選択/削除/再追加/端末入力、全画像を含む要求、取消、
詳細camera変更、英語切替、1枚生成への復帰を確認。overflow0/pageerror0。
削除ボタンの一般CSS優先で39pxになる問題を検出し、44pxへ修正して再受入。
通信応答は制御fixtureであり、実installed Host/Jobsの受入とは分離する。
実物理スマホ、自動3方向候補→選択→3D、installed MCPはNOT TESTED。

最初の全体testは2,556pass/3warnings/409.32秒。
その後CSS、版数、API/Workflowの3面要求検証を更新。追加API検証の旧固定Asset件数2件を修正し、
最終./mf.sh testは2,558pass/3warnings/409.46秒、exit0。以後product変更なし。
source成功を製品全体や自動複数面生成の完成とは扱わない。

## 0.33.20の署名配布とinstalled受入

PR [654](https://github.com/souten-yd/ControlDeckMediaForge/pull/654)を通常mergeし、
`5177a7b6e5d8baa54775aa9360e80f7f6c0fd8d4`のclean checkoutからbundle生成。
既存publisher鍵で署名し、[v0.33.20](https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.33.20)へ公開。
38,092,498B、SHA `0436bd2905f98150f759bdb4a77efbe73859e601470d4af5b944d1448b4d3df7`。
公開後のassets一覧cacheが空だったためrelease assets APIの実一覧から正規URLを取得し、
全4assetのsize/digestを照合した。upload再試行は同名422で上書きなし。
consumer再取得後に既存trusted key/署名/tamper拒否、safe tar6entry、PyInstaller244entry、
source一致、重み/venv/秘密値なしを検証。clean bundleの実HTTPでsetup_requiredと旧既定、
不正入力の拒否を確認した。Blender不在時の親capabilityだけを返す既存契約を検査helperで訂正。

active Job/Blender session/管理操作/OpenCode unit/resourceがない状態でDBをbackupし、
`deck.sh feature update media-forge`を実行。currentは0.33.20、実exe/cwd一致、PID581793、healthy。
配信JS/CSS/moduleはrelease sourceと一致。更新前1586 Asset metadata、代表3content SHA、
旧runtime全JSON/単視点capabilityを生成確認後にも再検査し保持を確認した。
新しい独立MV receiptだけを採用、既存9重みを参照。実workerの`/proc/.../maps`で
ggml全4libraryが永続runtimeからロードされることを確認した。追加モデル取得/重みコピー0。

通常operator認証を使い、Hostのopaque iframe（allow-same-originなし）の実file pickerを
320px/touchで操作。正面/右/背面/左の4RGBAを取り込み、別々のpreviewと横はみ出し0を確認。
「複数面：人物と赤いバッグ（4方向）」を送信し、151.703秒で成功した。
native来歴143.241228秒は同じJobの内部計測であり、UI全体の時間とは区別する。

| 結果 | ID |
|---|---|
| MediaForge Job | `job_e7a5e8375b96460b9d14520655120f28` |
| Host Job | `a8037b884af3` |
| scene | `scene_36dfcedb514d4148a9779df0c108d28f` |
| 制作版 | `asset_309cc771285949e781b7c5c169e9700f` |
| GLB | `asset_774b74adc7574ccb8ac168b64138c715` |

生成中は4入力ともTrash previewを`library_production_busy`で拒否。
生成後に通常Asset HTTPの実bytesを取得し、4入力のraw SHA/画素SHAを来歴と照合した。
元fixtureと各方向の画素が一致し、4枚の画素SHAはすべて異なる。
制作版の全4親/`generation_input` dependency、GLBの制作版親、出力2件の実SHA/size、
`vulkan / q8_0_flows_f16_shared`の来歴を確認。従来のfloat32実行来歴は流用していない。

GLBは41,107,216B、991,928tris/1材質/2画像、EXT_texture_webp。
通常PCの実AMD内蔵GPUブラウザで1280pxと320pxの表示・閉じるを確認し、
服/髪/赤いバッグのテクスチャを目視。overflow0/pageerror0、物理スマホはNOT TESTED。
初回headlessはWebGL2 contextを作れず表示失敗、GPUブラウザの初回PC終了入力も届かなかった。
これらの失敗を保持し、別runの320px→1280pxでは実pointer/click/closeを記録して成功を確認した。
全runは同じ保存済みGLBを開いており、表示のための再生成はない。

初回取消helperはprivate作業directoryにJob IDが含まれるという誤りでPIDを照合できず、
自身の`job_c96262c9110c46b6a7f9f294e743f29a`だけを通常APIで取消した。
照合を訂正した別Job `job_bb6513bd6cfc472da89a31f446cb11a6`では実nativeを観測後、
320pxの中止ボタンを押し、0.212秒でcanceled/native消滅/追加Asset0を確認。
Host `9865c7df9b8f`もcanceled、lease `23eea61d-ea7a-4d67-9a29-4b29d7a48bcb`はreleased。
元4画像と成功済みsceneを保持、終了後の4入力のTrash previewも成功（削除は実行しない）。
最後に正常1件/取消2件のHost終端、該当3lease released/active0を通常HTTPで確認した。

private証跡は`maintenance/release-0.33.20-20260923/`の
`multiview.json`、`viewer-hardware.json`、`cancel-ui.json`、`verify-multiview.json`、
`post-multiview-check.json`と実画面PNG。実行は同directoryの
`private-browser.py viewer-hardware.mjs` / `private-browser.py cancel-ui.mjs` /
`verify-multiview.py` / `check-installed.py <release-source> post-multiview`。
cookieはprivate stdinのみ、公開文書やhelperログへ記録しない。

利用入口は「作る→3D→元画像→別の方向を追加」。2枚は正面/右、3枚は背面を追加、
4枚は左も追加。追加カードを外すと従来1枚へ戻る。cameraは詳細モードで変更可能。
実installed生成は4枚を受入、2/3枚は先のnative実測とsource契約検証を根拠とする。
任意写真の校正/品質、rig/deformation、自動方向候補→比較→明示選択、実installed MCP、
物理スマホは未受入。この文書sliceに製品変更はなく、既受入2558testsは再実行していない。

## 正面からの側面候補：人物1件

手動MVのinstalled受入後、既存のFLUX.2-klein単一参照編集で、上記人物の正面Assetから
右/背/左を1件ずつ評価するprivate helperを実行。新しいモデルや重みは取得しない。
最初の右側面だけを送信した段階でHostがwatchdogにより再起動し、通信が切れた。
後続方向は送信せず、同じ生成を再試行しなかった。

| 記録 | 観測 |
|---|---|
| Host | `22aaf130c5ad` / interrupted（再起動） |
| MediaForge | `job_6d66e0f9b6d34734bee4fe4da837cac5` / succeeded |
| 出力 | `asset_e425aec656204ce1ba79ec96f582ad78` / 1024角RGBA / 871,790B |
| SHA | `10c8f8d3401fe992c2dfe0c354e58d467783bb18f0ce6c15f23c3fc7f44abca8` |
| 元画像 | `asset_62eafeae60dc4662883843d73304494c` / 全metadataと実SHA保持 |
| 所要時間 | durable created_at→updated_atの差161.480503秒（正常なHost完了応答ではない） |

Host復帰後、通常HTTPで同じHost Jobのinterrupted、coreのsucceeded、保存済み出力と親/実SHAを照合。
Hostの状態を手動で成功へ書き換えない。画像workerとmatteの自身のPIDは終了し、
通常Broker照会でactive lease0。旧leaseの終端履歴は再起動後取得できず、releasedと断定しない。
生成前後の原画像metadataと実bytes SHAは同一。候補はLibraryに残し、3Dへは渡していない。

候補は1人の側面を描き、茶色の上着/暗いズボン/白靴/黒髪の結び/赤いバッグ1個を保持。
四隅alpha0、完全透明画素割合0.880848885、alpha範囲0..255。
既知の右面と比べバッグ寸法、手/腕、身体の形、構図に差がある。
前景boundsは候補`[407,90,635,969]`、既知右面`[402,101,609,939]`。
これは画像編集の候補出力であり、同じ被写体の校正済み方向画像としては未受入。
向きが変わることだけで自動3Dへ進めない。比較・選択UIの製品接続も未実装のまま保持する。

実journalの18:41:25 JST stall stackはHostの`idle_unload_loop` →
`_revive_endpoint_for_opencode` → feature status → `subprocess.run(--version)`。
18:41:26に30秒watchdog、Host PID486604→604536、memory peak430.5MiB。
再起動原因はこの同期監視であり、MediaForge側からHost loopの待機を解消できない。
汎用Host PR343を`e3d374ad1ff582070a528ae3bddc449d35acde82`でマージし、
active Job/unit/lease0の時点で通常deck.shによりrootへ適用。PID674922/health ok。
同期待機をthreadへ移し、Gateway時の不要なversion照会を省略した。
Host全1175pass/2skip/105.71秒、実隔離HTTPで4秒version照会2回中にも81health応答。
installedの130秒/65health応答は最大4.432ms、PID不変/NRestarts0。
モデル変更やOpenCodeの一括停止は行っていない。

Host更新後、通常Libraryの各カードから4面GLBとこの側面候補をPC1280/320pxで開き、
表示/閉じる、GLB回転による画面変化を実GPU Chromeで確認。横overflow0/pageerror0。
初回private helperのcanvas.toDataURL比較は描画buffer非保持により失敗し、
その証跡を保存して実画面captureの比較へ訂正した。製品viewerは変更していない。
MediaForge current0.33.20/PID581793/healthy、旧1586 Asset metadata、代表3content SHA、
旧runtime全JSON、単視点capability、配布JS/CSS/moduleを再照合した。
この再確認では画像/3Dの再生成なし。物理スマホはNOT TESTED。
追加証跡は`maintenance/release-0.33.20-20260923/host-installed/`と
`post-host-update-check.json`。Host側の詳細はControlDeckの
`docs/opencode-revive-nonblocking-20260923.md`へ記録。

通常Hostのagent-tool HTTPにも追加方向付きの同一Asset要求を1回送り、
`invalid_scene_generation`、MediaForge Job追加0を確認した。
Host応答は502で、これは重複入力拒否の伝達確認に限る。実OpenCode/stdio MCP受入ではない。

private証跡は`maintenance/multiview-20260923/person-generated-candidates/`の
`recovered-result.json`、`right-{host,core}-recovered.json`、`right-asset.json`、
`right-provenance.json`、`alpha-review.json`、`cleanup.json`とPNG。
元の`result.json`と通信例外logも保持。記録だけのsliceで製品テストを再実行していない。
