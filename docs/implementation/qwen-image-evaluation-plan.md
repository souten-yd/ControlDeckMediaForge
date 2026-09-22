# Qwen-Image-2.1 導入評価計画

Date: 2026-09-22

## 0. 同定（済み）

upstream で確認した。**台帳にある `Qwen-Image-2512` とは別のモデルである。**

```text
model_id    Qwen/Qwen-Image-2.1
revision    790c92633540aa0cb11d9abf19eb46d861714758
更新        2026-09-21（公開 2026-09-20）
license     other（Qwen Research License）  ← Apache-2.0 ではない
pipeline    QwenImage21Pipeline（diffusers が Day 0 対応）
既定 dtype  bfloat16
重み        30.84 GiB
              text_encoder 16.33 / transformer 13.25 / vae 1.26
能力        text-to-image / 編集 / 参照画像 最大 10 枚 /
            **RGBA 透過の生成と編集**
規模        視覚生成部 7B（Single-Stream DiT 32 層）
```

台帳の `Qwen/Qwen-Image-2512` は重み 53.7 GiB・Apache-2.0・t2i のみで、
別物として残す。**2.1 は小さく、能力は広い。**

## 1. なぜ検討に値するか

| | FLUX.2-klein 4B（採用済み既定） | Qwen-Image-2.1 |
|---|---|---|
| 重み | 実行時ピーク VRAM 6.6 GiB（int8/int8 + cpu_offload） | 30.84 GiB（bf16） |
| 能力 | t2i / 単一参照編集 / inpaint / outpaint / 複数参照 / variation / strict_edit | 同等 + **参照 10 枚** + **RGBA 透過** |
| license | Apache-2.0 | **Qwen Research** |

MediaForge は `asset_brief.alpha_intent` を既に持っている。**透過を後処理の
マット抜きではなくモデルが直接出せる**なら、ゲーム素材の用途では効きが大きい。
これが検討する主な理由である。

## 2. 容量の見積もり（実行時ピークは未測定）

| | 値 |
|---|---:|
| GPU VRAM | 31.9 GiB（32,624 MB） |
| host RAM | 30 GiB（空き 25） |
| 空きディスク | 195 GiB |

- **bf16 のまま 30.84 GiB は VRAM 31.9 GiB に対して余裕が無い。**
  活性化と KV を足すと入らない見込み
- 約14.8 GiBはtransformerとtext_encoderの重みだけを半分にした概算。
  bf16 VAEの1.26 GiB、量子化メタデータ、活性化、作業領域を含まない。
  重みだけでも約16.05 GiBであり、実行時に収まるかは未測定
- `enable_model_cpu_offload()` が upstream で案内されている。host RAM 30 GiB
  との兼ね合いは実測が要る

2512とは容量が違うため、2.1を独立に評価する。見積もりから搭載可能とは断定しない。

## 3. 先に潰すべき3つの壁

### 壁1: ライセンスが Apache-2.0 ではない（最重要）

**Qwen Research License** である。採用済みの既定（Apache-2.0）と条件が違う。
先に法的な可否を決めないと、測っても使えない。

- [公式ライセンス](https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE)
  §1(i)/§2は研究・評価目的の非商用利用に限定。商用は別途ライセンスが必要。
  再配布は契約の同梱、変更表示、通知の保持など§3の条件に従う。
- 重みを利用する前に、この条件への利用者の明示的同意を記録する
- 使えるなら、MediaForge の既存の同意機構
  （`model.license_acceptance_id`）への対応は将来の採用判断で検討する。
  今回は製品台帳を変更せず、固定revision・license・同意範囲を評価記録に残す
- **進む条件**: 利用条件が受け入れ可能で、同意記録の形が決まっている
  → 決まらないなら、ここで終わり

### 壁2: diffusers の版を上げる必要がある

`runtimes/rocm-torch/requirements.txt` は **`diffusers==0.40.0`** で固定。
`QwenImage21Pipeline` は入っていない。

[公式要件](https://github.com/QwenLM/Qwen-Image-2.1#requirements)は
transformers>=5.17も指定している。現在の5.15.1からの更新も回帰対象に含む。
対応するdiffusersの不変commitとtransformersの版を固定した候補環境で先に測る。

**この runtime は採用済みの FLUX.2-klein も使っている。** 版を上げると
既定モデルの経路に影響する。Qwen のためだけに上げて既定を壊すのは割に合わない。

- **進む条件**: 同一入力・seed・量子化・offload・1024x1024で現行と候補を比較する。
  過去の6.6 GiB / 4.5秒を参照値として、生成成功・出力品質・VRAM・cold/warm時間を記録。
  回帰を認めた場合は共有runtimeを更新せず、差分と再開条件を残す

### 壁3: gfx1201 の fp32 GEMM 破損

大規模fp32 GEMMの既知報告は、該当したTorch/ROCm/BLAS・行列形状を
再確認する。gfx1201全般の破損、またはbf16全般の安全性とは断定しない。

- 同一seed・promptの3回生成とsha256は**再現性**を測る。決定的な誤演算も
  同じhashになるため、正しさの証明にはならない。不一致だけでGEMM破損とも断定しない。
- 有限値、CPU等の参照演算との数値比較（dtype・許容誤差・演算形状を記録）、
  生成画像の目視を分ける。数値比較を実施していなければNOT TESTEDとする。

## 4. 進め方

| 段 | 内容 | GPU | 進む条件 |
|---|---|---|---|
| 1 | ライセンス判断（壁1） | 不要 | 利用条件が受け入れ可能 |
| 2 | diffusers 版上げ + FLUX.2 の回帰（壁2） | 要 | 同一条件で既定の回帰がない |
| 3 | CPU で 1 枚（host RAM のピークだけ測る） | 不要 | 1 枚出て 25 GiB 未満 |
| 4 | GPU bf16で3回・再現性と数値比較（壁3） | 要 | 再現性・有限値・数値比較を個別に記録 |
| 5 | int8 で VRAM / 秒数 / 失敗率を測る | 要 | 1 枚 60 秒以内・失敗率 0 |
| 6 | **透過（RGBA）を実際に出す** | 要 | `alpha_intent` の用途で後処理より良い |
| 7 | 採否を報告（台帳変更は別承認） | 不要 | 上記すべて |

段3はGPUを触らずに測れるが、量子化backendのCPU対応を確認する。
メモリ上限とtimeoutを設け、ホストをOOMに追い込まない。
GPU測定はControlDeck brokerのleaseとestimated_runtime_secを通す。
透過はRGBAモード名だけでなく非不透明alpha・前景の保持・輪郭を確認する。
**VRAM の見積りは RAM の必要量ではない。**

## 5. 中止条件

- 段 1 でライセンスが受け入れられない → **中止**
- 段 2 で FLUX.2-klein が再現しない → **保留**。runtime 分離の費用を見てから
- 段4で再現性や数値比較が失敗 → **保留**。原因を調べ、未確認のGPU破損とは断定しない
- 段 6 で透過が後処理のマット抜きを上回らない → **採用しない**。
  2.1 を選ぶ主な理由が消えるため

## 6. 既定を置き換えるかは別の判断

仮に全段通っても、**既定の置き換えとは別**である。FLUX.2-klein は
6.6 GiB / 4.5 秒で動いている。Qwen 2.1の実測ピークVRAM・所要時間・透過品質が許容範囲なら、
「透過や 10 枚参照が要るときだけ選ぶ」形が妥当。`policy_rank` の
`quality` に置き、`auto` / `fast` は 0 のままにする。

## 一次資料

- [固定モデルrevision](https://huggingface.co/Qwen/Qwen-Image-2.1/tree/790c92633540aa0cb11d9abf19eb46d861714758)
- [公式実装・要件](https://github.com/QwenLM/Qwen-Image-2.1)
- [Qwen Research License](https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE)
