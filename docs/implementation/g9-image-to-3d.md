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

1. **RDNA4 / gfx1201**。先行例は RDNA3（gfx1100）まで。さらに先行例は
   **fp32 matmul で M > 2^19 行のとき GEMM が黙って壊れる**問題に触れており、
   RDNA4 に関わる話として記録されている。**probe はこれを明示的に確かめること**
   （壊れても例外は出ない。出力を検算する必要がある）。
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
| 2a | ネイティブ拡張6本を gfx1201 で通す（probe の第一関門） | 未着手 | ビルド可否／EGL／fp32 GEMM 検算 |
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
