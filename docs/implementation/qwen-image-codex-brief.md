# Codex への実装指示（Qwen-Image-2.1 評価）

対象: MediaForge（`worker_packs/image`, `scripts`）
背景: `docs/implementation/qwen-image-evaluation-plan.md`
範囲: **計画の段 2〜6 を回すための道具だけ。採用の判断はしない。**

```text
model_id  Qwen/Qwen-Image-2.1
revision  790c92633540aa0cb11d9abf19eb46d861714758
pipeline  QwenImage21Pipeline（bfloat16 既定）
重み      30.84 GiB（text_encoder 16.33 / transformer 13.25 / vae 1.26）
license   Qwen Research（Apache-2.0 ではない）
```

## タスク 1: diffusers の版上げと既定の回帰（先にこれ）

`runtimes/rocm-torch/requirements.txt` は `diffusers==0.40.0`。
`QwenImage21Pipeline` を含む版へ上げる。**この runtime は採用済みの
FLUX.2-klein も使う。**

- 上げた版で FLUX.2-klein の実測値を再現することを示す
  （実行時ピーク VRAM 6.6 GiB / 4.5 秒 / 1024x1024）
- 再現しない場合は**版を戻し、差分を報告して止まる**。
  Qwen のために既定を壊さない

## タスク 2: `scripts/qwen_image_probe.py`

- 引数: `--model-id` `--revision` `--device {cpu,gpu}`
  `--dtype {bf16,fp16}` `--quantization {none,int8}`
  `--offload` `--prompt` `--seed` `--repeat` `--width` `--height` `--rgba`
- JSON を 1 つ標準出力へ出して終了する:

```json
{"host_peak_rss_bytes": 0, "vram_peak_bytes": 0, "cold_load_sec": 0.0,
 "per_image_sec": 0.0, "output_sha256": [], "identical_outputs": true,
 "has_alpha": false, "error": null}
```

- 失敗しても JSON を出す（`error.code` / `error.message`）。例外を外へ出さない
- `--rgba` のときは出力が本当に透過を持つか（`has_alpha`）を調べる
- 重みは `HF_HOME` から読むだけ。**ダウンロードしない**。`HF_HUB_OFFLINE=1` で動くこと
- 1 ジョブ 1 サブプロセス、外から止められること

## タスク 3: `tests/test_qwen_image_probe.py`

diffusers を偽物に差し替えて固定する。

- `--repeat 3` で出力が違えば `identical_outputs: false`
- 読み込み失敗でも JSON が出る（例外が外へ出ない）
- GPU が無いのに `--device gpu` → `error.code == "gpu_unavailable"`、終了コード 0
- 重みが無い → `error.code == "weights_missing"`、終了コード 0

## やらないこと

- `worker_packs/image/models.json` を触らない。
  `state` / `measurement_confidence` / `hardware_backends` は測ってから人が上げる
- 新しい adapter（`diffusers.qwen-image-21`）を製品経路へ足さない。
  probe から直接 pipeline を呼ぶ
- 新しい capability や生成 API を足さない
- 量子化や解像度の既定を決めない。すべて引数で受ける

## 受け入れ条件

```bash
python scripts/qwen_image_probe.py \
  --model-id Qwen/Qwen-Image-2.1 \
  --revision 790c92633540aa0cb11d9abf19eb46d861714758 \
  --device cpu --dtype bf16 --quantization int8 \
  --prompt "a red cube" --seed 42 --repeat 3 --width 1024 --height 1024
```

が JSON を 1 つ出して終了コード 0 で終わる。重みが無ければ
`error.code == "weights_missing"`。

## 注意（実機で分かっていること）

- **gfx1201 は fp32 GEMM が M > 2^19 で黙って壊れる。** 落ちずに結果だけ
  変わる。`--repeat` の sha256 一致がその唯一の検出手段なので、省かないこと
- bf16 は無事。upstream の既定も bf16 なので、まず bf16 で測ること
- VRAM 31.9 GiB に対し bf16 の 30.84 GiB は余裕が無い。
  int8（約 14.8 GiB）と `--offload` を先に試すこと
- ライセンスが Research なので、**評価を超えて製品経路へ繋げないこと**
