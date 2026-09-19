# G9 trained model preparation and CPU evaluation — 2026-09-19

`ux1/g9-trained-models`、親PR574 / `68cb66a`。利用者の「同意する」を、直前に提示した
DINOv3 License / Pixal3D MITのローカル学習済み重み利用への同意として記録した。
正規Host leaseやruntime採用の証拠へ読み替えない。

証跡root: managed `maintenance/g9-trained-models-20260919/`。
重み: managed `data/models/hub/` と `models/g9-trained/`。core venvにはML依存を追加しない。
参照workerは既存 `runtimes/pixal3d-probe/.venv`、Python3.12.3、Torch2.10.0+ROCm7.2.1。
CPU評価ではHIP/ROCR/CUDAを明示的に隠し、Torch GPU initialized=falseを記録。

## 取得と変換

`trained-models-lock.json`へ11役割の配布revision・サイズ・SHA-256・config hashを固定。
PixalはTencentARC/Pixal3D `b0cb2e1b794cab9aa0ac38a95d794a4d9337437f` の7本。
NAFは公式release asset、MoGeはRuicheng/moge-2-vitl、背景はZhengPeng7/BiRefNet通常版。
すべて外部モデル領域へ保存し、配布元のLFS/release SHA-256を照合してから使用する。
モデル名がbf16でも、今回の評価は明示F16行列格納・F32演算。上流BF16演算受入ではない。

7本すべて取得/hash照合完了: 24,044,852,614byte、取得script全体2370.822104秒。
NAF/BiRefNet/MoGeを含む今回の新規取得は25,797,021,341byte。
再利用DINOを合わせた11役割は26,403,794,781byte、変換後native GGUF9本は
13,662,302,656byte。各出力のSHA/サイズは`model-inventory.json`、配布照合は
`pixal-download.json` / `aux-download.json`。全取得processはexit0で終了。

実SSチェックポイントだけにpersistent `rope_phases` が含まれ、最初の変換は余分なtensorとして
exit1。converterを修正し、SSでだけcomplex64/shape/finite/budgetを検査後、固定上流の
座標・周波数式で再計算した値との完全一致を要求する。実4096×64の全値は一致、raw hash
`480331b0de122b6c7e3468aaf19c608b0152d963a4f9d70e3855e3d510d51dd2`。
nativeが同じ座標から再生成するため、この定数は検査記録を残してGGUF格納から除く。
未知tensor、改変phase、NaN、shape/type違いは拒否。失敗logを保持し、修正後に変換完走。

Facebook DINO公式repoのconfigは`GatedRepoError`、HF tokenなし。公式HF checkpointは取得0。
既に利用者が所有していたtrellis.cpp用GGUF10件、計16,467,590,304byteについて配布SHA一致を
10.958394秒で確認。`import_trellis_dino.py`はそのうち固定DINO606,773,440byteだけを読み、
全318tensor/shape/type/finiteと配布digestを検査。使用値はF32に展開した数値で完全一致。
使わない最終affine norm2tensorの理由/hashも残す。出力606,776,320byte、SHA
`656bca247de426da315bc15e38b4bfe8bffa02d8c8ca4997a1126e11dad527aa`。

publisher `ilintar/trellis2-gguf` / revision `a57397bd3d351599d9729fc144b3f87c3f87d65b` を
そのままprovenanceへ残す。timm no-QKV-bias ViT-L/16であり、gated HF原本のprecisionを偽装しない。
新しいmirror downloadは行っていない。上流pipeline JSONのBRIA RMBG-2.0も取得/使用0。
明示BiRefNet CPU providerは設計済みの選択であり、上流BRIAとの品質同等を主張しない。

## 実測CPU受入

元trellisサンプルの`ref_front.png`（700²、SHA
`be160b8b234fdcc25c67499b7a0be471870feca6f62cfa168518e5059cb162de`）を複製して実行。
通常版BiRefNet1024²→MoGe2 ViT-L/14→Pixal framing/camera→512/1024 RGB arrayが完走。
framed画像を実際に開き、機械部品のシルエットと透明背景を確認。
カメラangle0.46125787953639397rad、distance2.1294095516204834、foreground124285pixel、
fitting有効点2590。これは推定結果であり、実物カメラの正解値との精度検証ではない。

|検証|実行内容|結果|
|---|---|---|
|DINO512|全24層/1024幅、実入力、timm1.0.22厳密load＋Pixal non-affine norm|global最大誤差1.364946e-5、patch2.426729e-4、native5.191447秒、参照3.312537秒|
|DINO1024|同じ実重み、4096patch＋5prefix|global1.442432e-5、patch2.586842e-4、cosine0.9999999404、native31.658932秒、参照17.413634秒|
|Shape HR flow|学習済み全30層/1536幅、8合成座標/条件、2step CFG7.5/rescale0.5|6比較すべてpass、最大9.155274e-5、native11.548591秒、参照5.082288秒|

比較許容値は実行前にatol/rtol各1e-3に固定。DINOはcosine>0.99999も要求。
shape参照は固定Pixal source `f7cf38429b0bd264f1995f0f8743a88b1c728b94`。
両側で宣言したF16格納丸め後のF32演算を使う。全grid/12step生成の証拠ではない。
時間はこのPCでのwall clock。取得・別検証も動く状態であり、独占性能benchmarkではない。

既存vision回帰7条件＋converter拒否14＋native拒否19＋同一GGUF再生成2、
flow回帰10条件＋拒否11が全pass。追加の誤ったlocal source、既存出力保持、
trained Vulkan/fault/opt-inなし拒否も確認。CPU専用追加入口からGPUは初期化しない。
追加拒否は7条件pass。SS buffer対応前の `./mf.sh test` は
**2242 passed / 2 warnings / 263.25秒 / exit0**。
SS修正後の一巡は、変更外の`test_adopt_rejects_changed_input_and_preserves_head[head]`で
fake workerの0.2秒制限に達し、**1 failed / 2241 passed / 253.07秒 / exit1**。
対象だけの再実行はコード変更なしでpass。環境負荷を原因と断定せず、失敗logも保持。
warningsは既存Starlette testclientとPillow getdataのdeprecation。
最終全件再実行: **2242 passed / 2 warnings / 249.38秒 / exit0**、`full-test-verified.log`。
以後product/checker変更なし。元checkout `524553d` clean、origin/main `bbdc69a`を再確認。

SS修正後のcheckpoint回帰は6条件、converterの17確認（有効buffer1件を含む）、native拒否9件
が全pass。全9 nativeモデルの`pixal-generate inspect`は`valid=true/source_kind=checkpoint`。
実`worker_entry.py prepare`で11役割をhash検査してから背景・カメラ・512/1024入力を準備し、
**68.673440秒 / exit0**。直接前処理時とframed PNG/RGB low/RGB high/cameraの4ファイルhashが
一致。`trained-worker-result.json`、`trained-job.json`、`trained-worker-prepare/ready.json`を保存。
job descriptorは未採用の評価入力であり、GPU実行や全token設定の収容量を承認するものではない。

## 再現入口と証跡

- `import_trellis_dino.py` / `convert_vision.py` / `convert_flow.py` /
  `convert_ss_decoder.py` / `convert_sparse_decoder.py`: 固定local checkpointから新規directoryへ変換。
- `prepare_camera.py`: `real-cpu-prepare/manifest.json`、全progressは`real-cpu-prepare.log`。
- `check_trained_dino.py`: `dino-cpu-first/`、`dino-cpu-1024/` のreport/expected/native array。
- `check_trained_flow.py`: `shape-flow-cpu-first/` のreport、各stepのvelocity/clean/sample。
- `check_vision_checkpoints.py` / `check_flow.py`: `vision-regression/`、`flow-regression/`。
- SS buffer対応後の`check_checkpoint.py`: `checkpoint-final/`。
- 追加拒否: `trained-rejections/report.json`。CMake/buildのstdout/stderrも同rootへ保存。

初期metadata取得の`ModelCardData`変換KeyErrorは`.to_dict()`へ修正し、初期error JSONを保持。
既存trellis確認の初回は未所有q4 variantを含めてexit1、対象を実所有root10件へ限定して再確認。
MoGeのCPU float32 autocast warningは保持。例外や未検証を成功へ置換しない。
初回receipt監査のpathは誤っていたため、`app.py`とruntime既定値から実際の
`data/runtime-state/{image-to-3d,pixal3d}-runtime.json`へ修正して両方不在を確認。
13:00Z Host auth/meは401、core healthy。元の監査も`admission-audit-initial-paths.json`へ保持。

## 未完了の受入

GPUに使えるHost認証済みMCP/実行コンテキストはこのセッションへ未接続。
Host内部DB/session生成を使わない。正規admission/device mapping/renew/reap/releaseを得てから
Vulkan数値比較とfull生成を行う。利用者への接続情報の質問は回答待ち。

NOT TESTED: 学習済みfull-grid image→GLB、実Host lease付きVulkan、ピークVRAM、3D品質、
上流BF16との比較、runtime adoption/署名導入、installed画像入力から新GLBのLibrary保存、
GLB viewer画素、ボーン/animation。採用receiptなし、未採用capabilityを利用可能にしない。
既存Libraryのtrellis2点と合成Pixal検証用1点を学習済み新規Pixal生成物へ読み替えない。

現worker入口は`g_no_fa=true`を設定している。全token数でのgraph allocation/VRAM受入は
未実施であり、小座標の数値比較を収容量の証拠にはしない。必要なら別スライスでattentionの
メモリを評価・修正し、演算精度/数値比較/lease付きVulkanを別々に確認する。
