# 2026-09-19 Pixal3Dの明示CPU背景除去

`ux1/pixal3d-background`、親PR569 / `71ecc7d`。
画像のみからの生成に必要な、opaque入力のBiRefNet→foreground framing→MoGe→native GLBを接続。
base-planへ通常版BiRefNetの明示CPU/F32前処理を先に追加した。
GPU自動fallbackでも、BiRefNet/MoGeのVulkan移植完了でもない。
生成本体のGGML/Vulkan backend指定と正規Host lease条件は維持する。

## 実装

`runtimes/trellis-cpp-pixal/background.py`は固定HF source
`e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4`の実BiRefNetを使用する。
`birefnet.py` / `BiRefNet_config.py` / `config.json`のhashを照合し、検証したPython bytesを
直接compileしてprivate moduleへ読み込む。近隣pycへの差替え、runtime remote code loader、
`from_pretrained`、暗黙のcheckpoint/backbone downloadは使用しない。
実コードは [固定HF tree](https://huggingface.co/ZhengPeng7/BiRefNet/tree/e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4)。
この作業で取得したものはsource/configだけで、配布重みは取得・使用していない。

モデルはfull Swin-L、backbone pretrainingを明示false。
local safetensorsは許可root・2GiB上限・SHA-256、全tensor名/shape、float dtype/finite、
固定relative-position index、batch counterを検査。meta parameterで構成検査してから
CPU model storageを確保しstrict loadする。F16/BF16/F32格納に対応し、計算はCPU/F32。
source/checkpoint hashは同意やadoption receiptではない。呼出側が別途管理する。

Pixal既定の1024²へのtorchvision Resize/ToTensor/Normalize、最後のlogitsのsigmoid、
ToPILImageによるuint8切捨て、Pillow既定mask resizeを維持する。
既存MediaForge画像workerのBiRefNet Lite ONNXで代用しない。
foregroundの事前1024-edge縮小、alpha>0.8、bbox/crop/compositeも既存実装のまま。
各Swin block・decoder段へ取消を伝播し、自分のhookだけを終了時に外す。

`prepare_camera.py`は4つのbackground CLI引数をまとめて要求。
必要なopaque画像だけでmodelを読み、callback scope終了とGC後にMoGeを読み込む。
透明入力では指定済みproviderも読み込まない。既存outputはmodel実行前に拒否・保持。
manifestへ実際のinput-alpha/provider使用、source/checkpoint、合成/実checkpoint宣言、
CPU/F32/1024入力を記録する。既存Python callbackはcaller-owned/unspecifiedとして保持。
正式manifestは配列書込み完了後に公開し、取消・失敗時は所有outputだけを回収する。

## 実機CPUで観測した結果

workerは既存隔離venv、Torch2.10.0のCPU実行、2 thread、GPU visibilityを3種とも-1、HF offline。
**全220,176,498 parameterの実fullモデル、1024²入力**を使用した。
パラメータは合成で、実input-skipのconvolutionを赤色前景へ校正したfixture。
全Swin-Lの2scale encoderとdeformable decoderが実行されるが、学習済みsegmentation品質ではない。
F16格納のsynthetic safetensorsは444,473,644byte、SHA-256:
`57aa9f7d26cd51c3b4f4a0b0ee09b93a9bc49200a1cd32f4daa4e3c5f2b6c93a`。

| 検証 | 実測 |
|---|---|
| 新providerのfull forward | 14.781299秒 |
| 固定Pixal wrapper参照 | 14.441112秒、RGBA全bytes一致 |
| マスク | alpha 0〜255 /11値、入力RGBのbytes不変 |
| opaque入力の別process前処理 | 18.439189秒、background→MoGe→hash付き配列・manifest完成 |
| alpha入力でprovider skip | 無効hashのproviderを渡しても未使用。PR569のframed/RGB low/high/cameraと全bytes一致 |
| 不正入力・scope・型・取消等 | 17条件pass |
| 実SIGTERM | encoder block実行を観測後に送信、exit1、0.940673秒でreap、outputなし |
| native CPU全生成 | 0.704632秒、SS7→upsample1792→HR51→1024-grid |
| 出力GLB | 48,532byte /590三角形 |
| 独立core/Blender4.5.9 | GLB再検証・実再import成功。UV1、128²画像2、材質channel接続あり、armature0 |

参照比較は固定Pixal `pipelines/rembg/BiRefNet.py`のtransform式と`__call__`をASTから実行し、
CUDAのdevice literal1箇所だけをCPUへ変更した。推論/resize/丸めは変更しない。
形状を縮小したBiRefNetへ差し替えたり、用意したmaskをprovider結果として返したりしていない。
MoGe/3D本体はPR569/568の既存合成fixtureであり、そこを全幅学習済みに変更した意味ではない。

native binaryはPR569で確認したものと同一SHA-256、native source差分0。
9個のnative model hash、MoGe checkpoint hash、BiRefNet descriptorをsource manifestへ、
全前処理manifest・sampler/settings/norm hashをinput manifestへ束縛した。
GLBは保守証跡内に保持し、今回さらにLibraryへ合成fixtureを増やしていない。
前の登録済み3件とPR570の状態は変更しない。

## 再現と証跡

```bash
cd /tmp/mediaforge-pixal-background-20260919
/data1tb/ControlDeck/data/feature-data/media-forge/runtimes/pixal3d-probe/.venv/bin/python \
  runtimes/trellis-cpp-pixal/check_background.py \
  --source /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/pixal3d-probe/sources/BiRefNet-hf/e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4 \
  --pixal-source /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/pixal3d-source \
  --moge-source /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/pixal3d-probe/sources/MoGe \
  --camera-fixtures /data1tb/ControlDeck/data/feature-data/media-forge/maintenance/g9-pixal-camera-20260919/cpu-verified \
  --pipeline-fixtures /data1tb/ControlDeck/data/feature-data/media-forge/maintenance/g9-pixal-naf-projection-20260919/pipeline-first \
  --binary /tmp/mediaforge-pixal-naf-projection-build/pixal-pipeline-check \
  --core-python /data1tb/ControlDeckMediaForge/.venv/bin/python \
  --blender /data1tb/ControlDeck/data/feature-data/media-forge/runtimes/blender/blender-4.5.9-linux-x64/install/blender \
  --output-dir /data1tb/ControlDeck/data/feature-data/media-forge/maintenance/g9-pixal-background-20260919/cpu-first
```

実行済みoutputは再利用・上書き不可。再試験時には新しい明示outputを使う。
managed `maintenance/g9-pixal-background-20260919/`の`cpu-first/report.json`、
preprocess/native/core/Blender/termination log、GLB・mask・入力、synthetic checkpoint、
`cpu-first.log`、`source-provenance.json`へ実証跡を保持。
CPU MoGe inner autocastのF32非対応warningは既知のまま記録し、明示F32推論は完走した。

最終 `./mf.sh test`: **2211 passed /2 warnings /237.31秒 /exit0**。
以後product/checker変更なし。文書参照、全66runtime source hash、`git diff --check`を確認。

**NOT TESTED / 残り**: 配布済み学習checkpointの全tensor table・実segmentation精度、
学習済みMoGe/3Dと品質、正規Host lease付きVulkan、production worker入口とadoption/署名導入、
新しい学習済み成果物のLibrary登録、骨付きanimation。全体目標は未完了。
重み同意は既出質問への回答待ち。次はprivate CPU前処理とnative生成をproduction workerの
既存Scene Jobs/Host admission/取消/Blender/Asset境界へ接続する。
