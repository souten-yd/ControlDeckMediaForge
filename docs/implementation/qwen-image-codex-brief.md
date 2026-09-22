# Codex への実装指示（Qwen-Image-2.1 評価）

この文書は完了したDiffusers/Quanto評価の指示を保存したもの。
利用者の追加依頼「コミュニティなどを調査し、適切な組み合わせを調査して適用して」に
よる次のVulkan評価・実測後のローカル研究用途への適用は
[別スライス](qwen-image-21-vulkan-20260922.md)で扱う。

2026-09-22実行状態: [実機評価結果と未実施項目](qwen-image-21-evaluation-20260922.md)。
評価道具と回帰確認は実装・実測済み。Qwenは通常画像1枚を生成したが708秒を要した。
CPU互換性・RAM余裕・時間の条件は不通過。製品台帳・adapter・共有runtimeの変更なし。

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

- transformers>=5.17も必要。diffusersの対応commitと依存版を固定した候補環境で、
  現行FLUX.2-kleinと同一条件（1024x1024、seed、量子化、offload）で比較する。
  6.6 GiB / 4.5秒は過去の参照値。今回のcold/warm時間とVRAM・品質を実測する。
- 回帰を認めたら共有runtimeの更新は行わず、差分を報告して止まる。

## タスク 2: `scripts/qwen_image_probe.py`

- 引数: `--model-id` `--revision` `--device {cpu,gpu}`
  `--dtype {bf16,fp16}` `--quantization {none,int8}`
  `--offload` `--prompt` `--seed` `--repeat` `--width` `--height` `--rgba`
- GPU評価では任意の `--blas-library {auto,cublas,cublaslt}` を受け、実際の
  PyTorch preferenceも記録する。ROCmでcublasはhipBLASに対応する。
  2026-09-22の参照比較では環境変数単独でfp32不一致が残ったため追加した。
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

- 同一seedのhashは再現性の検査であり、GEMM正しさの唯一の検出手段ではない。
  有限値・参照演算との数値比較を別に記録し、未測定はNOT TESTEDとする。
- bf16を起点にするが、全演算の安全を仮定しない。既知報告のBLAS版・形状を確認する。
- int8の14.8 GiBは一部の重みの概算。VAEや活性化等を含む実行時VRAMを測る。
- alphaの存在と、背景が実際に透明で前景が残ることを分けて検査する。
- ライセンスは研究・評価目的の非商用利用に限定。重み利用前に明示的同意を記録し、
  **評価を超えて製品経路へ繋げないこと**。
