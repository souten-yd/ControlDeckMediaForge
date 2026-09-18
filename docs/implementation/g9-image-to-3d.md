# G9 — 画像から3Dを生成する（Pixal3D）＋ 3D系MCPの断捨離

Date: 2026-09-18
Status: implementation plan / 着手済み。進捗は §8 を見ること
Target: ControlDeckMediaForge

関連する正:

- `docs/implementation/goal-roadmap.md` の G9 節（本計画が埋める枠）
- `docs/design-3d-assets-and-opencode.md`（asset/revision と OpenCode 経路）
- `docs/implementation/g8-high-quality-mcp-3d-assets.md`（§1.7 で G9 を候補と位置づけ）
- `AGENTS.md`「契約凍結」「完了の定義」

**この計画は新機能を発明しない。** roadmap G9 に既に書かれている
「image-to-3D アダプタ → raw mesh → Blender production pipeline → 検証 + export」を、
実際に動くモデルで埋める。capability の枠 `3d.image_to_3d`（現在
`{"state": "unavailable", "reason": "planned_for_g9"}`）もすでに `app.py` にある。

---

## 0. なぜ今か

コンセプト画像から 3D を作る経路が、現状は型付き Blender レシピしかない。
実際にコンセプトアート（R05 WEAVER、4脚歩行機）から組んでみた結果、
5 revision 重ねてシルエットまでは寄ったが、参照画像の再現には届かなかった。
手で積むレシピの限界であって、レシピ実装の不足ではない。

同時に、画像→3D が入ると前提が変わる 3D 系の MCP 道具がある。G9 を足すだけだと
道具が増えて面が膨らむので、**同じ機会に削る**。

---

## 1. 採用モデル: Pixal3D（第一候補）/ TRELLIS.2（退避先）

| | Pixal3D | TRELLIS.2 | Hunyuan3D 2.1 |
|---|---|---|---|
| ライセンス | **MIT** | **MIT** | Tencent 独自。EU/UK/韓国不可、1M MAU 超は別契約 |
| 出力 | GLB（PBR テクスチャ付き） | GLB（PBR） | mesh + texture 別 |
| R9700 での既知不具合 | 報告なし | 報告なし | ROCm issue #5981: テクスチャ破損（6.4.0〜7.2.0、形状は正常） |

**両者は競合ではない。** Pixal3D（TencentARC, SIGGRAPH 2026）の master 実装は
TRELLIS.2 backbone にもとづく改良版で、その上に**画素を逆投影して 3D へ持ち上げ、
画素と 3D の対応を直接張る**仕組みを載せている。従来の「画像特徴を attention で
緩く注入する」やり方に対し、再構成に近い忠実度を狙う設計である。

R05 で不足していたのは「それらしい形」ではなく**参照画像そのものの再現**なので、
Pixal3D が狙う軸がそのまま用途に合う。

Hunyuan3D 2.1 は採らない。ライセンス制限に加え、R9700 でテクスチャが壊れる既知不具合が
ROCm 6.4.0〜7.2.0 を通して未解決のため。

### 1.1 固定する上流（2026-09-18 時点の実測）

```text
weights   HuggingFace TencentARC/Pixal3D
          sha b0cb2e1b794cab9aa0ac38a95d794a4d9337437f
          license mit / lastModified 2026-08-31
code      GitHub TencentARC/Pixal3D (default branch: master)
```

checkpoint は工程ごとに分かれている（`_mv` は多視点入力版）。

| ckpt | サイズ | 役割 |
|---|---|---|
| `ss_flow_img_dit_1_3B_64_bf16` | 5.36 GB | Sparse Structure flow（64³） |
| `ss_dec_conv3d_16l8_fp16` | 0.15 GB | SS decoder |
| `slat_flow_img2shape_dit_1_3B_{512,1024}_bf16` | 各 5.55 GB | Shape flow |
| `shape_dec_next_dc_f16c32_fp16` | 0.95 GB | Shape decoder |
| `slat_flow_imgshape2tex_dit_1_3B_1024_bf16` | 5.55 GB | Texture flow |
| `tex_dec_next_dc_f16c32_fp16` | 0.95 GB | Texture decoder |

単視点 1024 の1経路だけなら **約 18.5 GB**、`_mv` も入れて約 37 GB、全部で 46 GB。
DiT は 1 本 1.3B で、工程が逐次なので low-VRAM モードなら峰は DiT 1 本ぶんに落ちる。

**多視点版がある**ことは G9 roadmap の「参照・多視点の準備」とそのまま噛み合う。
R05 のように正面と斜めの2枚がある素材はこちらに載る。単視点を先に通し、
多視点は後続とする。

### 1.2 これは pip だけでは入らない — ネイティブ拡張6本の移植が要る

**ここが本計画で最も重い部分なので、着手前に把握しておくこと。**

Pixal3D の導入は「まず TRELLIS.2 の導入手順に従う」から始まる。その TRELLIS.2 は
`setup.sh --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm` という
**CUDA ネイティブ拡張の集合**を要求し、README は「24GB 以上の NVIDIA GPU が必要。
A100 と H100 で検証」と明記している。`inference.py` も `import o_voxel` を直接叩く。

つまり素の pip では入らない。ただし**ROCm で通した先行例がある**
（`toastmanAu/trellis-2-rocm-comfyui`）。そこで当てている内容:

| 拡張 | ROCm での扱い | ビルド時間 |
|---|---|---|
| `cumesh` | HIP パッチを当ててソースビルド | 約5分 |
| `flexgemm` | Triton ベース。ROCm 向けに組み直し | 約1分 |
| `nvdiffrast` | HIP パッチ。**CUDA ラスタライザではなく OpenGL backend を使う** | 約3分 |
| `nvdiffrec_render` | 移植 | 約2分 |
| `o_voxel` | 移植 | 約3分 |
| `custom_rasterizer` | PyTorch の自動 HIP 化で通す | 約3分 |
| `flash-attn` | **移植しない**。PyTorch の cross-attention（SDPA）へ倒す | — |

先行例の実測環境: **ROCm 7.2.2 / PyTorch 2.11.0+rocm7.2 / RX 7900 XTX (gfx1100, RDNA3)
/ 24GB / Python 3.10**。shape のみと texture 込みの両方が通り、GLB が出ている。

この機体は `rocm-torch` が ROCm 7.2.1 / torch 2.10 なので近いが同じではない。

### 1.3 未確定のリスク（probe で潰す）

1. **RDNA4 / gfx1201**。先行例は RDNA3（gfx1100）まで。
   fp32 GEMM の破損は **この機体で再現した**。詳細は §1.5。
2. **nvdiffrast が OpenGL backend になる**。MediaForge の worker は headless の
   サブプロセスなので、**EGL の初期化**が要る。先行例も headless/WSL2 では GL context を
   早期に初期化しないと EGL が失敗すると書いている。`runtimes/blender-web` 側に GL の
   下地はあるが、worker からは別経路になる。
3. **`natten==0.21.0`**。上流は `NATTEN_CUDA_ARCH` 指定の source build を要求する。
   NATTEN には **Flex Attention backend**（PyTorch 実装・ROCm 対応）があるので経路は
   あるが、多次元タイリングの融合ができないぶん遅い。CUDA カーネル版は使わない前提で組む。
4. **`flash_attn`**。上流が「無ければ `ATTN_BACKEND=sdpa` で代替できる」と明記。入れない。
   `inference.py` は既定を `flash_attn` にしているので**環境変数で上書きする**。
5. **追加の重み**。Pixal3D 本体のほかに `inference.py` が2つの HF repo を参照する。
   固定対象は3つ:
   - `TencentARC/Pixal3D`（sha `b0cb2e1b…`）
   - `Ruicheng/moge-2-vitl`（MoGe-2。単眼形状推定）
   - `camenduru/dinov3-vitl16-pretrain-lvd1689m`（DINOv3。画像条件付け）
6. **`git+https://github.com/microsoft/MoGe.git`**。上流 requirements が git 直参照。
   固定 revision へ読み替える。
7. **VRAM**。1536 の実測値が公開されていない。32GB で足りなければ low-VRAM（1024）へ。

**Pixal3D が駄目でも作り直しにはならない。** backbone が同じなので runtime と拡張一式は
共通で、退避は「Pixal3D 固有の段を外して TRELLIS.2 の素で回す」だけで済む。
逆に言えば**拡張6本が通らなければ両方とも駄目**なので、probe の第一関門はそこになる。

### 1.6 実測: ネイティブ拡張のビルド結果（gfx1201 / ROCm 7.2.1）

2026-09-18。`runtimes/trellis2-probe/.venv`（torch 2.10.0+rocm7.2.1、Python 3.12.3）。

| 拡張 | 結果 | 要ったこと |
|---|---|---|
| `o_voxel` | **成功・import OK** | `ROCM_HOME=/opt/rocm` の明示だけ。setup.py に HIP 分岐あり |
| `flex_gemm` | **成功・import OK** | ビルドはそのまま。Triton 設定の TF32 を ROCm で無効化 |
| `cumesh` | **成功・import OK** | fork と3種のソース修正が要る（下記） |
| `nvdiffrast` | **成功・import OK** | CUDA ラスタライザは stub。GL ラスタライザを別途組む（下記） |
| `nvdiffrec_render` | **成功・import OK** | nvdiffrast と同じ枠で組める |
| `flash-attn` | 入れない | `ATTN_BACKEND=sdpa` で代替 |

**実機検証（2026-09-18）:** headless で `dr.RasterizeGLContext` が取れ、三角形の
ラスタライズは被覆 1,352/4,096（幾何から出る期待値 約1,310）、`dr.interpolate` の
重心座標の和は min/max ともに 1.0000 だった。**通っただけでなく値が合っている。**

再現手順は `runtimes/trellis2-probe/build-nvdiffrast-rocm.sh` に置いた。

**先に潰すべき環境の罠:** torch の `ROCM_HOME` 自動判定がこの機体では
`/opt/rocm-7.2.1/core-10.0` を掴む。そこに `include/hip/` は無く、
`'hip/hip_runtime.h' file not found` で全部の HIP 拡張が落ちる。
**`ROCM_HOME=/opt/rocm ROCM_PATH=/opt/rocm` を明示すること。**
これは G9 に限らず、この機体で HIP 拡張を組むとき常に要る。

**CuMesh に要る修正**（上流 `JeffreyXiang/CuMesh` ではビルドできない）:

1. fork `visualbruno/CuMesh` を使う。
2. `src/clean_up.cu` の `::cuda::std::tuple`（libcu++）は HIP に無い。
   `rocprim::tuple` へ差し替える。`rocprim::tuple` は explicit constructor なので
   `return {a,b,c}` のブレース初期化も明示構築へ直す。
3. `src/dtypes.cuh` の `Vec3f` 既定 constructor を `__device__` から
   `__host__ __device__` へ。`hipcub::DeviceSegmentedReduce` が identity を
   host から作るため。
4. `setup.py` から NVCC 専用フラグ（`--extended-lambda` 等）を落とす。
5. vendored な `third_party/cubvh` は git submodule ではないので eigen を直接 clone する。
6. `cumesh/remeshing.py` を fork のものへ差し替える。

**nvdiffrast に要る修正**（一番重い）:

1. 本体の CUDA ラスタライザ（CudaRaster）は **PTX のインラインアセンブリ**を使っており
   HIP へ移植できない。v0.4.0 側では stub にして interpolate / texture / antialias だけ組む。
2. 代わりに **v0.3.5 の OpenGL ラスタライザ**を別モジュールとして組み、`ops.py` を
   patch して `RasterizeGLContext` から使えるようにする。
3. HIP-GL interop（`hipGraphicsGLRegisterBuffer` 等）は Mesa のオープンドライバでは
   動かないので、GPU-GL のやり取りは **CPU 経由**にする
   （`hipMemcpy D2H` → `glBufferSubData`、`glGetTexImage` → `hipMemcpy H2D`）。
4. `__frcp_rz` は CUDA 専用なので `__fdividef(1.0f, x)` へ。
5. ROCm 7.2 の warp 同期は 64bit マスクを要求するので `0xffffffffu` を
   `(unsigned long long)` へ、`amask` も `unsigned long long` へ。
6. **guard は Masquerading 版を使うこと。** 素の `c10::hip::OptionalHIPGuard` は
   `DeviceType::HIP` しか受けず、ROCm torch が Python から cuda を名乗るため
   `HIPGuardImpl initialized with non-HIP DeviceType: cuda` で落ちる。
   `ATen/hip/impl/HIPGuardImplMasqueradingAsCUDA.h` と `HIPStreamMasqueradingAsCUDA.h` から
   `at::hip::OptionalHIPGuardMasqueradingAsCUDA` /
   `at::hip::getCurrentHIPStreamMasqueradingAsCUDA` を取る。
   torch 2.10.0+rocm7.2.1 の `c10/hip/HIPGuard.h` にこれらは無い。
7. `EGL/egl.h` が要る（`libegl1-mesa-dev`）。`GL/gl.h` と `KHR` は既に入っていた。

**FlexGEMM に要る修正:** `flex_gemm/kernels/triton/spconv/config.py` の
`allow_tf32 = True` を ROCm で False にする。TF32 は NVIDIA 専用で、ROCm の Triton は
`ieee` / `bf16x3` / `bf16x6` しか持たない。Triton の cache も捨てる。

### 1.5 実測: gfx1201 で fp32 matmul が M > 2^19 のとき黙って壊れる

**2026-09-18、この機体で再現。** torch 2.10.0+rocm7.2.1 / ROCm 7.2.1 /
AMD Radeon AI PRO R9700 (gfx1201) / 34.2 GB。

`A(M,64) @ B(64,32)` を CPU と突き合わせた結果:

| M | 最大絶対差 | 不一致要素数 | |
|---|---|---|---|
| 262,144 (2^18) | 0.000e+00 | 0 | OK |
| **524,288 (2^19)** | 0.000e+00 | 0 | OK |
| **524,289 (2^19+1)** | 1.596e+01 | 32 | **壊れる** |
| 1,048,576 (2^20) | 5.048e+01 | 16,775,541 | 壊れる |
| 1,500,000 | 4.730e+01 | 31,219,651 | 壊れる |

境界はちょうど 2^19。**例外は出ない。** 通ったことを成功と読んではいけない。

範囲を詰めた結果（M = 2^20）:

| 対象 | 結果 |
|---|---|
| `float32` matmul | **壊れる**（max 4.675e+01、16,775,468 要素） |
| `torch.nn.functional.linear` (fp32) | **壊れる**（max 3.318e+03） |
| `bfloat16` matmul | OK |
| `float16` matmul | OK |
| elementwise（mul/add） | OK |
| fp32 を 2^18 行ずつに分割 | **OK**（max 0.000e+00） |

**この計画にとっての意味:**

- TRELLIS.2 / Pixal3D の checkpoint は `_bf16` 系で、推論の主経路は bf16 なので
  **そのままでは踏まない**見込みが高い。
- 踏むとすれば、decoder・voxel 処理・幾何処理のどこかに紛れる fp32 matmul である。
  **probe と adapter は出力を検算すること**。速度だけ測って通ったことにしない。
- 回避は「2^19 未満へ分割する」で足りる。分割した結果は CPU と完全一致した。

**この不具合はこの計画に閉じない。** 同じ機体の image / video runtime でも、
fp32 の大きい matmul を通す経路があれば同じことが起きる。G9 とは別に扱うこと。

### 1.7 重みの入手（2026-09-19 実測）

`microsoft/TRELLIS.2-4B`（**MIT**、sha `af44b45f2e35a493886929c6d786e563ec68364d`）は
22 files / **16.24 GB**。実測で取得に 22 分 34 秒かかった。

**`facebook/dinov3-vitl16-pretrain-lvd1689m` が gated。** TRELLIS.2 の画像条件付けが
これを参照するので、HF のライセンス承諾と token が無いと 401 で止まる。
上流の重みだけ揃えても動かない点に注意。

参考: Pixal3D は同じ DINOv3 を非 gated のミラー
（`camenduru/dinov3-vitl16-pretrain-lvd1689m`）で参照している。

取得先は `data/feature-data/media-forge/hf-cache` に置いた（`HF_HOME` で指定）。
リポジトリの中には入れない。

### 1.4 依存が既存 runtime と衝突する

上流 `requirements.txt` は `transformers==4.57.3` / `diffusers==0.37.1` を要求する。
`runtimes/rocm-torch` は `transformers==5.15.1` / `diffusers==0.40.0` なので**同居できない**。
別 venv にする。同居させると何が起きるかは `runtimes/rocm-torch/requirements.txt` の
コメントに実機事故として残っている（別の加速器版 wheel が ROCm の torch を置き換え、
`cuda.is_available()` が False になった）。

---

## 2. 採用 probe（最初の関門。ここで必ず止まる）

重量級モデルの採用は **probe → adapter の2段**。型は
`worker_packs/video/hunyuan15_probe.py`。probe は評価器であって製品アダプタではなく、
repository 名を解決しないので重みを落とせない。呼び出し側が上流ライセンスを承諾した
うえで固定 snapshot のパスを渡す。

新規:

- `runtimes/pixal3d-probe/requirements.txt`
  probe 用なので `runtime.conf` は置かない（既存 probe runtime と同じ扱い）。
- `worker_packs/three_d/pixal3d_probe.py`
  `--snapshot` / `--work-root` / `--output` / `--preset` を取り、結果を1行 JSON で返す。

probe は2段に分ける。**先に拡張、次に生成。**

**2a. 拡張ビルドの関門**（`--preset extensions`）

```text
cumesh / flexgemm / nvdiffrast / nvdiffrec_render / o_voxel / custom_rasterizer を
gfx1201 で build & import できるか
nvdiffrast の OpenGL backend が headless（EGL）で context を取れるか
fp32 matmul の M > 2^19 行で GEMM が壊れていないか（結果を CPU と突き合わせて検算する。
  壊れても例外は出ないので、通ったことを成功と読まない）
```

ここが通らなければ Pixal3D も TRELLIS.2 も動かない。**止めて報告する。**

**2b. 生成の計測**（`--preset smoke` / `low-vram-1024` / `standard-1536`）

```text
選ばれた attention backend（sdpa へ倒せているか、natten が ROCm 経路を選べたか）
解像度ごとの所要秒数（1024 / 1536）
ピーク VRAM
出力 GLB の構造検証結果（既存 glb.validate_glb を通す）
TRELLIS.2 素での同条件（退避先の実力）
```

**合否の判断:** 拡張が揃わない / GEMM 検算が合わない / EGL が取れない / 1024 も 1536 も
VRAM に収まらない、のいずれでも止めて報告する。Pixal3D だけ駄目で TRELLIS.2 が通るなら、
退避先で進めてよいか判断を仰ぐ。

### 2.1 実測: TRELLIS.2 は gfx1201 で動く。ただし入力を選ぶ（2026-09-19）

`runtimes/trellis2-probe`、ROCm 7.2.1 / torch 2.10.0 / gfx1201 / 34.2 GB。

**通ったこと:**

| | |
|---|---|
| attention | `ATTN_BACKEND=sdpa` / `SPARSE_ATTN_BACKEND=sdpa`（両方要る。§2.2） |
| conv | `flex_gemm` |
| ラスタライザ | OpenGL（CUDA 版は stub） |
| 読み込み | 37〜65 秒 |
| 生成 | 81〜122 秒（既定 12 step × 4 段） |
| 書き出し | 140〜202 秒 |
| ピーク VRAM | **4.88 GB**（32 GB に対して十分な余裕） |

**上流サンプル（`assets/example_image/T.png`）は破綻なく出た。** 4,424,912 頂点 /
6,314,020 面で、機械部品の形が素直に立ち上がっている。**つまりスタックは正しい。**

**一方で L01 DAWNBRINGER の4面図（正面）は破片になる。** 前処理後の画像は
1022×1022 で機体が枠いっぱいに収まった良い絵（目視確認済み）なのに、出てくる
メッシュは装甲板がばらばらに散る。上半身だけを切り出して塊の大きい対象にしても
同じだった。

原因は**未確定**。有力なのは2つで、どちらも決め切れていない。

1. §1.5 の fp32 GEMM 破損が形状の復号のどこかを踏んでいる。probe は毎回
   `fp32_matmul_sane: false` を返している。ただし上流サンプルも 4.4M 頂点で
   2^19 を大きく超えており、それが通っている点と整合しない。
2. 単視点の TRELLIS.2 が、正投影のコンセプトアート・細い四肢の人型という
   入力領域に弱い。サンプルはコンパクトな機械部品である。

**次に効くのは多視点。** 4面図が揃っているのだから Pixal3D の `inference_mv.py`
（`_mv` 付き checkpoint）へ載せるのが筋で、上の 2 が主因ならこれで解ける。
1 が主因なら多視点でも同じように壊れるので、**切り分けとしても意味がある。**

### 2.2 実測: 動かすまでに要った手当て

素の TRELLIS.2 はこの機体では起動しない。要ったのは以下。

| 障害 | 手当て |
|---|---|
| `briaai/RMBG-2.0` が gated（403、承認制） | 入力を切り抜き済み RGBA にすれば `preprocess_image` は背景除去を通らない。読み込み時に必ず構築されるので probe 側で無効化する |
| `facebook/dinov3-…` が gated（401） | ライセンス承諾と HF token。**重み 16 GB を揃えただけでは動かない** |
| sparse attention が `sdpa` を受けない | `config.py` の許可一覧は `xformers` / `flash_attn` / `flash_attn_3` のみ。`ATTN_BACKEND=sdpa` は黙って無視され、既定の flash_attn のまま**重みを読み終えたあとで** `ModuleNotFoundError` になる |
| 全経路が `RasterizeCudaContext` | `RasterizeGLContext` へ置換（`patch-trellis2-source.sh`） |

背景除去は MediaForge が既に持っている BiRefNet の ONNX（MIT、CPU）を使った
（`worker_packs/image/matte.py`）。gated なモデルを増やさずに済む。

### 2.3 実測: hipBLASLt が gfx1201 で fp32 GEMM を壊していた（2026-09-19）

§1.5 の破損の**原因を特定した。hipBLASLt である。**

```
ROCBLAS_USE_HIPBLASLT=0
```

これだけで直る。M = 2^19 / 2^19+1 / 2^20 / 1,500,000 / 4,000,000 のすべてで
CPU と完全一致（max 0.00e+00）になった。効かなかったもの:
`TORCH_BLAS_PREFER_HIPBLASLT=0`、`DISABLE_ADDMM_HIP_LT=1`（どちらも不一致のまま）。

bf16 の速度に目立った影響はない（4096³ を 20 回で 266 ms）。

**この機体で torch を使う経路は、すべてこれを設定しておくべきである。** G9 に限らない。

### 2.4 それでもメッシュは直らなかった

hipBLASLt を切って L01 を生成し直したが、破片のままだった
（3,405,493 頂点 / 4,636,230 面）。構造はいくらか読めるようになったが、
装甲板が散る状態は変わらない。**GEMM 破損は真の不具合だが、この症状の原因ではない。**

残る容疑者は sparse conv（`flex_gemm`）、o_voxel、そして単視点モデルの入力適性。
いずれも未切り分け。

### 2.5 調査: AMD 向けの現状は十分ではない

**コミュニティの到達点は RDNA3 まで。** TRELLIS.2 の ROCm 移植として見つかるのは
`toastmanAu/trellis-2-rocm-comfyui`（gfx1100 / RX 7900 XTX）、
`DrBearJew/trellis2-convrot-rocm`（**gfx1100 のみと明記**）、
`iceblue03/trellis2-rocm-bridge`（gfx1150 / iGPU）、`CalebisGross/TRELLIS-AMD`（RX 7800 XT）。
**gfx1201 / RDNA4 で通ったという報告は見つからない。**

上流の立場も CUDA 前提で、非 CUDA backend は
[microsoft/TRELLIS.2 issue #74](https://github.com/microsoft/TRELLIS.2/issues/74) で
「探索中」の扱いにとどまる。

**RDNA4 は黙って誤る前例が複数ある。**

- vLLM [PR #40827](https://github.com/vllm-project/vllm/pull/40827)「RDNA4 の
  skinny-GEMM kernel の correctness bug 2件」。gfx1201 で
  **「100% of elements mismatched, max abs diff 520」**と記録されている。
- ROCm TransformerEngine [#520](https://github.com/ROCm/TransformerEngine/issues/520):
  gfx1201 が arch table に無く、FP8 WMMA が**黙って** FP32 へ落ちる。
- 量子化 matmul が **NaN ではなく「妥当に見える誤った値」**を返す例が報告されている。

§2.3 で見つけた hipBLASLt の件も同じ系統で、**この機体固有ではなく RDNA4 全体の
傾向**と見るべきである。新しい GPU 経路を採るたびに CPU と突き合わせる必要がある。

**より確度の高い代替: `pwilkin/trellis.cpp`。** TRELLIS.2-4B を C++/GGML で書き直した
実装で、**Vulkan backend を持つ**。rocBLAS / hipBLASLt を一切通らないので、
上に挙げた系統の不具合を構造的に避けられる。参照実装と op 単位で一致すると謳っており、
UV 展開済み GLB（WebP の PBR テクスチャ）まで出る。bf16 で 16 GB 級に載り、
res-1024 で 3〜7 分（RTX 5060 Ti 実測）。Python 依存も要らない。
RDNA4 での実績は明示されていないが、Vulkan は Mesa RADV が RDNA4 を十分に扱う。

### 2.6 Vulkan（trellis.cpp）を並べて評価する（2026-09-19）

§2.5 の調査を受けて Vulkan を試し、**最終的に両経路を同じ入力で比べて採用を決める**
方針になった。**選ばれなかった側は重みを捨て、手順だけ残す。**

**Vulkan は素直に通った。**

```
deviceName = AMD Radeon AI PRO R9700 (RADV GFX1201)
driverName = radv / Mesa 25.2.8 / Vulkan 1.4.318
```

`pwilkin/trellis.cpp` のビルドはパッチ無しで成功した（596 target、エラー 0）。

```
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON
cmake --build build -j
```

**ROCm 経路との差が大きい。** あちらはネイティブ拡張6本の HIP 移植、gated モデル2つ、
sparse attention の実装追加、ラスタライザの差し替えが要った。こちらは cmake 一発である。

**gated の問題も消える。** 重みは `ilintar/trellis2-gguf` に GGUF で揃っており、
**DINOv3 と BiRefNet も同梱**されている。HF のライセンス承諾も token も要らない。
bf16 一式で約 16.5 GB、q8 で約 9.0 GB、q4 で約 5.5 GB。背景除去も CLI に内蔵
（`--bg-removal threshold|birefnet`）。

まず bf16 で確かめる。量子化は変数を増やすので、素の品質を見てから判断する。

### 2.7 評価の段取り（両経路を同じ入力で比べる）

**比べるもの**

| | 経路 | 入力 |
|---|---|---|
| A | trellis.cpp / **Vulkan** | 単視点（L01 正面） |
| B | TRELLIS.2 / **ROCm** | 単視点（L01 正面）。上流サンプルは済み（§2.1） |
| C | Pixal3D / **ROCm** | **多視点**（L01 4面図）。未実施 |

C は「ROCm だから駄目」ではなく、`einops` の入れ忘れで pipeline 初期化の途中で
落ちただけだった。requirements へ追加済み。

**判断の軸**: L01 が形になるか、所要時間、ピーク VRAM、手順の重さ。

**再現の担保**（選ばれなかった側のため）

| ファイル | 役割 |
|---|---|
| `setup-rocm.sh` | ROCm 環境をゼロから組み直す。拡張5本のビルドと3種のパッチを全部含む |
| `fetch-rocm-weights.sh` | 重みを取り直す（TRELLIS.2-4B / Pixal3D） |
| `build-nvdiffrast-rocm.sh` | nvdiffrast + nvdiffrec の HIP 移植 |
| `patch-trellis2-source.sh` | sparse attention の sdpa 追加とラスタライザ差し替え |
| `requirements.txt` | 版を固定した依存 |

Vulkan 側は `cmake -DGGML_VULKAN=ON` と GGUF の取得だけで、追加の手当ては要らない。

**重みを捨てても作り直せる**のがこの節の目的である。捨てるのは成果物だけで、
作り方は git に残る。

---

## 3. production adapter と G8 への受け渡し

- `worker_packs/three_d/worker.py` — 画像/動画 worker と同じ**行ごとの JSON** 規約。
  core はこの実装を import しない。
- `backend/mediaforge/config.py` に `three_d_runtime_python`
  （既存 `image_runtime_python` / `video_runtime_python` と同じ形）。
- `backend/mediaforge/jobs.py` に 3D 生成 stage。長時間なので `scene_recipe_jobs` と同じ
  **durable + detached job**（Host agent の 120 秒上限を跨がない）。
- GPU は stage ごとに Broker から lease を取り `estimated_runtime_sec` を申告する
  （`AGENTS.md` 規約 8）。別 stage の lease を持ったまま待たない。

G9 完了条件（「生成3Dが同じ asset lineage と検証パイプラインを流れる」）の本体。
**新しい出口を作らない。**

```text
入力画像 asset
  → Pixal3D worker → raw GLB（staging、まだ asset ではない）
  → asset_import.py の validate_glb（64MiB上限・URI禁止・構造検証）
  → Blender worker で .blend 化
  → SceneDocument の初版 SceneRevision として確定
  → 既存 asset.pack / profile=3d.project.glb で GLB + manifest + preview
```

- `.blend` が制作保存形式・GLB は派生物という既存ルールを守る。raw GLB をそのまま
  成果物にせず **SceneDocument の revision にする**。生成後に既存の編集経路で直せる。
- `scenes.py` の条件（`blender.scene` と `glb.structure` の両方 passed）を通らない限り
  current にしない。生成物だからといって検証を緩めない。
- provenance に入力画像 asset とその hash、モデル repo + revision、seed、解像度、
  runtime 版を残す。

capability を `{"state": "experimental", "implementation": "pixal3d", ...}` へ。
roadmap の規則どおり **`available` と偽らない**。トポロジ品質を約束しない。

---

## 4. 3D 系 MCP の断捨離

経路は変えない（`docs/design-3d-assets-and-opencode.md` §6 で固定済み）:
`OpenCode → ControlDeck controldeck_addons stdio MCP → MediaForge agent contribution → durable job`。
**別 MCP サーバーは立てない**（認証・job 所有・asset ID 体系が二重になる）。

### 4.1 実測した現状（0.28.86、2026-09-18）

media-forge 16 本 / スキーマ計 **120,708 bytes**。`create` と `edit` の 2 本だけで
85,156 bytes（全体の 71%）を占め、両者はほぼ同じ SceneRecipe 定義（29 操作）を二重に載せている。

稼働 ControlDeck の `jobs.kind` から数えた実行回数:

| 道具 | 実行回数 | bytes | 判断 |
|---|---|---|---|
| `media.scene.snapshot` | 33 | 573 | 残す |
| `media.scene.create` | 30 | 42,547 | **削除 → `author` へ統合** |
| `media.scene.export` | 26 | 654 | 残す |
| `media.scene.edit` | 20 | 42,609 | **削除 → `author` へ統合** |
| `media.scene.material` | 2 | 2,168 | 残す |
| `media.scene.observe` | 2 | 1,913 | **削除** |
| `media.scene.review` | 2 | 1,399 | **削除** |
| `media.scene.refine` | 1 | 2,447 | **削除** |
| `media.scene.bake` | 0（0.28.86 で追加） | 2,607 | 残す |

### 4.2 何をなぜ削るか

- **`create` + `edit` → `media.scene.author` に統合**
  `scene_id` 省略時は新規作成、指定時は `base_revision_id` 必須で編集。SceneRecipe 定義を
  1 部だけ載せる。Pixal3D が形を作るようになると、レシピは「作る道具」から「直す道具」へ
  役割が変わるので、2 本に分ける理由がなくなる。
  副次効果として、**同名の別文書が量産される事故が構造的に起きなくなる**
  （R05 WEAVER は毎回 `create` を呼んだ結果、同名文書が 5 件できた）。
- **`observe` / `review` / `refine` を削除**
  この 3 本は「レシピを盲目的に組む → 描画して画像にする → vision で見て直す」ループの
  ためにある。Pixal3D が形を作るなら、直し方は「別の画像・別の seed で作り直す」になり、
  ループの前提が消える。実行実績も 3 本合わせて 5 回。**後継は用意しない。**
- **`material` / `bake` / `snapshot` / `export` は残す**
  どれも生成後のメッシュに効く工程で、Pixal3D の出力にこそ要る。特に `bake` は密な生成
  メッシュから low + normal/AO を作る道筋なので相性が良い。
- **`media.generate` 系と sonic-forge は触らない**（3D 関係ではないため）。

### 4.3 結果の見積り

| | 本数 | bytes |
|---|---|---|
| 現在（media-forge） | 16 | 120,708 |
| 断捨離後（`author` + `from_image` 込み） | **13** | **74,340（-38%）** |

これでも SceneRecipe 1 部の 42,547 bytes が残る。ここから先を削るには操作セット自体を
絞る別の判断が要る。**本計画の範囲外**とする。

なお ControlDeck 側の `agent_tool_contract_threshold` による遅延ロードは**既に試して
無効化済み**（ControlDeck `config/config.yaml` のコメントに実測が残っている: 契約を外すと
llama.cpp が道具 schema を文法へ変換して出力を縛るため、モデルが空の引数で呼ぶ）。
効く手は本数と大きさを減らすことだけ。

### 4.4 契約凍結の手当て（`AGENTS.md`「契約凍結」が要求する記載）

agent tool 名と引数は G1 で凍結され「以降は追加のみ」。今回は削除するので規約どおり先に書く。

- **なぜ追加で足りないか**: 目的が面を減らすことなので追加だけでは達成できない。
  `create` / `edit` を残して `author` を足すと 127KB になり悪化する。
- **既存資産への影響**: なし。道具の削除は scene_documents / revisions / assets を消さない。
  過去 job の履歴（`jobs.kind` の文字列）もそのまま残る。
- **移行手順**: `author` は `create` / `edit` の上位互換（`scene_id` 省略=作成、指定=編集）。
  `observe` / `review` / `refine` は後継なしの機能廃止。
- **version bump**: `0.29.0`。`addon.json` の version と `docs/api.md` を同時に更新する。
- `media.scene` workflow executor の `action` も `create|edit|material` から
  `author|material` へ揃える（UI・agent・workflow で別実装を作らない原則）。

### 4.5 G9 の道具

`media.scene.from_image` を `agent_tools` と `workflow_executors` の両方へ追加。
`media.generate` に 3D profile を足す形は採らない（入力契約が違い、experimental を
stable な G8 profile と混ぜない）。

---

## 5. 3D 資産の整理 — 仕組みだけ（データは移動・削除しない）

稼働 MediaForge DB の実測（2026-09-18）:

| | 件数 |
|---|---|
| scene_documents | 68（**collection 未設定 66**、`acceptance` 2） |
| scene_revisions | 205 |
| assets | 1,356（png 935 / glb 205 / blend 205 / zip 7 / mp4 4）、982MB |
| scene_working_copies | 96（**全件期限切れ**。committed 49 / released 35 / **recovery 12**、実体 13MB） |

1. **collection の語彙を固定** — `concept` / `production` / `acceptance` / `experiment` を
   schema の enum に。G9 出力は既定で `experiment` + タグ `g9`。
   **既存 66 件の未設定はそのまま**。後から手で付けられる状態にするのが今回の範囲。
2. **期限切れ working copy の回収** — `committed` / `released` は期限超過で実体を削除する
   定期処理を繋ぐ。`recovery` の 12 件は**自動で消さない**（競合時の復旧候補で、設計上
   「別シーンとして保存」を提供する対象）。一覧に出して利用者が決める。

同名 create のガードは不要（`author` への統合が構造的に防ぐ）。

---

## 6. 実装時に踏む地雷（実測済み）

- agent tool のペイロードは `{"input": {...}}` の封筒に入れる（`app.py` の
  `scene_tool_input`）。外すと本文なしの 422 `invalid_scene_recipe` になる。
- ControlDeck の `backend/app/addons/execution.py` の `_upstream_error` は allowlist に
  載った**短い符号だけ**を通し本文を捨てる。新しい失敗理由には
  `^[a-z][a-z0-9_]{2,63}$` に合う符号を付ける。付けないと呼び出し側は
  「拡張機能の実行に失敗しました」しか受け取れず自力で直せない。
- `mf.sh` の `gpu_verify()` は `runtimes/rocm-torch/.venv/bin/python` 決め打ち。
  新しい runtime を `mf.sh env build` へ載せるなら、ここを runtime 引数で切り替える
  必要がある（probe 段階では `env build` を使わないので影響しない）。

---

## 7. 検証

`AGENTS.md` の完了定義（コードを書くだけでは完了ではない／何を実行し何を観測し何が
NOT TESTED かを記録する）に従う。

1. ソースが 0.28.86 以降で、`addon.json` の道具 16 本が揃っていること
2. probe 用 venv を作る
3. probe を R9700 で実行し、**所要秒数・ピーク VRAM・NATTEN backend・GLB 構造検証**を
   Pixal3D と TRELLIS.2 の両方で記録（gfx1201 と natten が未確認のため本当のゲート）
4. `mf.sh test` と ControlDeck の `./deck.sh test` — 既存 G8 が無傷であること
5. R05 WEAVER の参照画像（背景・人物・文字を切り抜いたもの）を通し、手で組んだ
   `CodeDEV/R05-Weaver/R05-Weaver.glb` と並べて比較する
6. OpenCode から `media.scene.from_image` を呼び、detached job が 120 秒を超えても完走し、
   `media.job.status` で追え、`media.job.cancel` で止まること
7. MCP の面を実測し直す（16 本/120,708 → 13 本/74,340 を確認）
8. `media.scene.author` で作成と編集の両方ができること。既存 scene の編集が
   `create`/`edit` 時代と同じ結果になること
9. 削除した 5 本が capability にも MCP 一覧にも出ないこと。過去 job の履歴が残ること

---

## 8. 進捗

**引き継ぐときはここを見る。** 段ごとに完了したら状態と実測値を書き足すこと。
「コードを書いた」は完了ではない。実行して観測した結果を残してから次へ進む。

| # | 段 | 状態 | 記録 |
|---|---|---|---|
| 0 | ソースを 0.28.86 へ同期 | **完了** | 2026-09-18。`origin/main` = `8a8f1a2`、道具 16 本を確認。作業ブランチ `feat/g9-image-to-3d` |
| 1 | 上流の固定（重み sha・依存・リスク）を文書化 | **完了** | 本文書 §1。HF sha `b0cb2e1b…`、master branch、weights 18.5〜46 GB。**ネイティブ拡張6本の移植が要ることが判明**（§1.2）。固定する HF repo は3つ |
| 2a-1 | fp32 GEMM 検算 | **完了・不具合あり** | 2026-09-18。M > 2^19 で fp32 matmul が黙って壊れることを再現（§1.5）。bf16/fp16 は無事。分割で回避可 |
| 2a-2 | probe 用 venv（ROCm 7.2.1 / torch 2.10.0） | **完了** | `runtimes/trellis2-probe/`。gfx1201 認識、34.2 GB |
| 2a-3 | ネイティブ拡張を gfx1201 で通す | **完了** | 5本すべてビルド・import 成功（§1.6）。flash-attn は入れない |
| 2a-4 | nvdiffrast の OpenGL backend を headless（EGL）で取れるか | **完了** | `RasterizeGLContext` 取得 OK。ラスタライズ被覆と補間を実値で検算して一致 |
| 2b-1 | TRELLIS.2 の重み取得 | **完了** | 16.24 GB / 22分34秒。`microsoft/TRELLIS.2-4B` MIT（§1.7） |
| 2b-2 | TRELLIS.2 の生成計測 | **完了** | 上流サンプルは破綻なし。ピーク VRAM 4.88 GB、生成 81〜122 秒（§2.1） |
| 2b-3 | L01 4面図からの生成 | **未達** | 前処理は良好だがメッシュが破片になる（§2.1） |
| 2b-4 | fp32 GEMM 破損の原因特定 | **完了・回避策あり** | hipBLASLt。`ROCBLAS_USE_HIPBLASLT=0` で完全に直る（§2.3）。ただしメッシュは直らない（§2.4） |
| 2b-5 | AMD 向け対応の十分性を調査 | **完了** | 不十分。コミュニティは RDNA3 まで、RDNA4 は黙って誤る前例が複数（§2.5）。代替は trellis.cpp の Vulkan |
| 2c | Pixal3D の多視点 | 再開 | 前回は `einops` の不足で初期化中に落ちただけ。ROCm の問題ではない。重み再取得中 |
| 2d | trellis.cpp を Vulkan でビルド | **完了** | パッチ無しで成功（596 target / エラー0）。RADV GFX1201 を認識（§2.6） |
| 2e | GGUF 取得と生成 | 進行中 | bf16 約16.5GB。DINOv3 / BiRefNet 同梱で gated 問題なし |
| 2a-4 | nvdiffrast の OpenGL backend を headless（EGL）で取れるか | 未着手 | |
| 2b | `runtimes/pixal3d-probe` + `worker_packs/three_d/pixal3d_probe.py` | 未着手 | |
| 3 | **probe を実機実行して報告・判断を仰ぐ（ここで止まる）** | 未着手 | 所要秒数／ピーク VRAM／attention backend／GLB 検証 |
| 4 | adapter + job + G8 受け渡し | 未着手 | |
| 5 | MCP 断捨離（`author` 統合 → 5 本削除 → 0.29.0 → docs） | 未着手 | |
| 6 | `media.scene.from_image` の公開 | 未着手 | |
| 7 | 資産整理の仕組み（collection enum・working copy 回収） | 未着手 | |

### 決定済みで動かさないこと

- Hunyuan3D 2.1 は採らない（§1）
- 別 MCP サーバーは立てない（§4）
- `observe` / `review` / `refine` に後継は用意しない（§4.2）
- 既存 66 件の collection 未設定はこの計画では埋めない（§5）
- SceneRecipe 42.5KB のさらなる削減は範囲外（§4.3）
