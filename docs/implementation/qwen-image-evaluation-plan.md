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

## 2. 実機に載るか（測って分かっている数字で）

| | 値 |
|---|---:|
| GPU VRAM | 31.9 GiB（32,624 MB） |
| host RAM | 30 GiB（空き 25） |
| 空きディスク | 195 GiB |

- **bf16 のまま 30.84 GiB は VRAM 31.9 GiB に対して余裕が無い。**
  活性化と KV を足すと入らない見込み
- int8 に落とすと約 14.8 GiB（transformer 6.6 + text_encoder 8.2）。
  ここなら余裕がある
- `enable_model_cpu_offload()` が upstream で案内されている。host RAM 30 GiB
  との兼ね合いは実測が要る

**2512（53.7 GiB）では机上で落ちていたが、2.1 は落ちない。** ここが最大の違い。

## 3. 先に潰すべき3つの壁

### 壁1: ライセンスが Apache-2.0 ではない（最重要）

**Qwen Research License** である。採用済みの既定（Apache-2.0）と条件が違う。
先に法的な可否を決めないと、測っても使えない。

- 商用利用の可否を読む
- 使えるなら、MediaForge の既存の同意機構
  （`model.license_acceptance_id`）に載せる。Illustrious XL v2.0 が
  同じ扱いなので前例がある
- **進む条件**: 利用条件が受け入れ可能で、同意記録の形が決まっている
  → 決まらないなら、ここで終わり

### 壁2: diffusers の版を上げる必要がある

`runtimes/rocm-torch/requirements.txt` は **`diffusers==0.40.0`** で固定。
`QwenImage21Pipeline` は入っていない。

**この runtime は採用済みの FLUX.2-klein も使っている。** 版を上げると
既定モデルの経路に影響する。Qwen のためだけに上げて既定を壊すのは割に合わない。

- **進む条件**: 上げた版で FLUX.2-klein が現在の実測値
  （ピーク VRAM 6.6 GiB / 4.5 秒）を再現する
  → 再現しないなら、別 runtime に分ける費用を見積もってから判断

### 壁3: gfx1201 の fp32 GEMM 破損

**M > 2^19 で fp32 GEMM が黙って壊れる**（bf16 は無事）。落ちずに結果だけ
変わるので、目視では気付けない。

upstream の既定が bf16 なのは幸い。ただし量子化や offload の経路で fp32 に
落ちる箇所が無いとは限らない。

- **検出手段**: 同一 seed・同一 prompt で 3 回生成し、**出力の sha256 が
  一致するか**を見る。一致しなければ黒

## 4. 進め方

| 段 | 内容 | GPU | 進む条件 |
|---|---|---|---|
| 1 | ライセンス判断（壁1） | 不要 | 利用条件が受け入れ可能 |
| 2 | diffusers 版上げ + FLUX.2 の回帰（壁2） | 要 | 既定が実測値を再現 |
| 3 | CPU で 1 枚（host RAM のピークだけ測る） | 不要 | 1 枚出て 25 GiB 未満 |
| 4 | GPU bf16 で 3 回・sha256 一致（壁3） | 要 | 3 回一致、破綻なし |
| 5 | int8 で VRAM / 秒数 / 失敗率を測る | 要 | 1 枚 60 秒以内・失敗率 0 |
| 6 | **透過（RGBA）を実際に出す** | 要 | `alpha_intent` の用途で後処理より良い |
| 7 | 台帳へ反映（measured へ昇格） | 不要 | 上記すべて |

段 3 は GPU を触らずに測れる（[[mediaforge-cpu-placement-measured]]）。
**VRAM の見積りは RAM の必要量ではない。**

## 5. 中止条件

- 段 1 でライセンスが受け入れられない → **中止**
- 段 2 で FLUX.2-klein が再現しない → **保留**。runtime 分離の費用を見てから
- 段 4 で 3 回の出力が一致しない → **中止**。gfx1201 の既知破損
- 段 6 で透過が後処理のマット抜きを上回らない → **採用しない**。
  2.1 を選ぶ主な理由が消えるため

## 6. 既定を置き換えるかは別の判断

仮に全段通っても、**既定の置き換えとは別**である。FLUX.2-klein は
6.6 GiB / 4.5 秒で動いている。Qwen 2.1 が int8 で 14.8 GiB・数十秒なら、
「透過や 10 枚参照が要るときだけ選ぶ」形が妥当。`policy_rank` の
`quality` に置き、`auto` / `fast` は 0 のままにする。
