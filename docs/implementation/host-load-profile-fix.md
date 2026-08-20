# Codex実装指示 — ControlDeck: LLM退避コスト計測の分離と永続化

対象リポジトリ: `souten-yd/ControlDeck`
基準head: `8681eb7`（PR #207 merge後）
想定PR: 1本（backend中心 + 設定UIの表示追加）

> **このファイルは ControlDeckMediaForge に置いているが、作業対象は ControlDeck リポジトリである。**
> Media Forge G7（動画）で LLM 退避が実際に必要になるため、依存関係の記録として本リポジトリに置く。
> 関連: [`goal-roadmap.md`](goal-roadmap.md) G7
前提: Add-on Platform v2 PR-0〜PR-E はマージ済み

---

## 0. 背景（推測ではなく実装の確認結果）

PR-D2 で managed supervision は入ったが、**現状の閾値計算では実質的に発火しない**。
根拠は以下の3点で、いずれもコードと実測記録から確認済み。

### 0.1 cold と warm を同じプールに入れている

`backend/app/resources/telemetry.py` の `record_load_measurement()` は
すべてのロード計測を `cold_load_cost_sec = process_start_sec + model_load_sec` として
単一の `_load_samples[residency_key]` deque に入れている。cold/warm の区別が無い。

PR-D2 の実測記録には次の2つの数字が並んでいる。

```text
cold-load p90       83.038 s   （ディスクからの初回ロード）
stop後の再起動        7.851 s   （page cache が温まった状態での再ロード）
```

約10倍差。両方が同じプールに入る。

### 0.2 その結果 thrash guard が過剰抑止になる

`backend/app/models_mgmt/resource_provider.py` の `_yield_allowed()`:

```python
if request.estimated_runtime_sec <= max(costs) * THRASH_FACTOR:
    self._telemetry.record("yield.suppressed", reason="thrash_cost")
    return False
```

`THRASH_FACTOR = 2.0`、`costs` は `cold_load_p90()` の戻り値。
`max(costs)` を使うため、cold の外れ値がそのまま閾値を支配する。

```text
83.038 * 2.0 = 166.076 秒
```

**推定実行時間が 166 秒を超える job しか LLM を退避できない。**
実際の退避コスト（= 退避直後の再ロード）が 7.851 秒であっても同じ。
画像生成はほぼ全滅する。

thrash guard の意図は「退避コストに見合わない job で載せ替えない」ことであり、
比較すべきは **退避直後に発生する再ロードのコスト = warm** である。
cold を使うのは誤り。

### 0.3 永続化が無く、最小サンプル数も無い

- `_load_samples` は in-memory の `deque` のみ。`data_dir` へ書いていない
- ControlDeck を再起動すると全消去され、`cold_load_p90()` が `None` を返す
  → `_yield_allowed()` は `load_cost_unknown` で **常に退避を拒否**する
  → 再起動のたびに managed が「次に cold load が起きるまで無効」になる
- `cold_load_p90()` はサンプル1件でも値を返す（`_percentile` に下限が無い）
  → n=1 の p90 は p90 ではない

---

## 1. このPRの目的

以下の3つだけを行う。managed の既定化はしない。

1. ロード計測を **cold / warm に分類**し、退避判断には warm を使う
2. ロードプロファイルを **`data_dir` へ永続化**する
3. 退避判断に **最小サンプル数**を設け、未達時は保守側（退避しない）に倒す

加えて、判断に使った値と抑止理由を **UI と API から見えるようにする**。
現状は `yield.suppressed` の counter に入るだけで、なぜ退避しないかが利用者に見えない。

---

## 2. やってはいけないこと

```text
managed を既定値にすること（RuntimePolicy.supervision の default は "observed" のまま）
推定値・カタログ値への fallback を追加すること（実測のみという原則を崩さない）
jobs.status enum の変更
既存 test の削除・書き換え（追加のみ）
THRASH_WINDOW_SEC / THRASH_MAX_YIELDS の緩和
llama-server に動的 unload を実装しようとすること（別課題）
estimated_runtime_sec の供給者をControlDeck側に作ること（§6参照）
Media固有の概念を持ち込むこと
```

---

## 3. 実装 — cold / warm 分類

### 3.1 分類規則

**測定側で page cache の有無を判定しようとしないこと。** 移植性が無く不安定。
代わりに **ロードの由来**で決定的に分類する。

```text
warm : 同一 residency_key の unload/stop が記録されてから
       WARM_WINDOW_SEC 以内に開始されたロード
cold : それ以外（起動後初回、長時間経過後、別モデル）
```

`WARM_WINDOW_SEC` 既定 900（15分）。定数として `telemetry.py` に置き、設定化しない。

この規則なら「broker が退避させた直後の再ロード」が必ず warm に分類され、
thrash guard が必要としている数字と定義が一致する。

### 3.2 telemetry の変更

`backend/app/resources/telemetry.py`

```python
def record_unload(self, residency_key: str) -> None:
    """Mark a stop so a following load can be classified as warm."""
```

- `_unloaded_at: dict[str, float]` を追加し、`self._clock()` を記録
- `record_load_measurement()` に `load_kind` を自動付与する
  - 呼び出し側からは受け取らない。`_unloaded_at` を見て telemetry 内で決定する
  - 決定後、その key の `_unloaded_at` は消す（1回のみ warm 判定）
- sample に `"load_kind": "cold" | "warm"` を追加

既存の `cold_load_cost_sec` フィールド名は**変更しない**（永続化互換とAPI互換のため）。
`load_kind` で意味を分ける。

### 3.3 新しい取得API

```python
def reload_cost_p90(self, residency_key: str) -> LoadCostEstimate | None:
    """Return the cost basis for a yield decision, or None if insufficient."""
```

戻り値は dataclass または dict:

```python
{
  "value_sec": float,
  "basis": "warm" | "cold",      # どちらを使ったか
  "sample_count": int,
  "warm_count": int,
  "cold_count": int,
}
```

選択規則:

```text
warm サンプルが MIN_WARM_SAMPLES 以上   -> warm の p90 を返す（basis="warm"）
それ未満で cold が MIN_COLD_SAMPLES 以上 -> cold の p90 を返す（basis="cold"）
どちらも未達                            -> None
```

```python
MIN_WARM_SAMPLES = 3
MIN_COLD_SAMPLES = 3
```

**bootstrap について。** warm サンプルは退避が起きないと増えないが、
退避には warm サンプルが要る、という循環がある。これは意図的に
「cold にfallbackして保守的に振る舞う」ことで解く。
cold basis の間は閾値が高く退避がほぼ起きないが、
**利用者が手動の「今すぐ退避」を実行すれば warm サンプルが1件増える**。
3回手動実行すれば warm basis へ移行する。この挙動を §5 のUIで明示すること。

`cold_load_p90()` は表示用に残す。削除しない。

### 3.4 `_percentile` の下限

現在の `_percentile` はサンプル1件でもその値を返す。
`reload_cost_p90` 側で件数チェックを行うので `_percentile` 自体は変えなくてよいが、
`cold_load_p90()` を直接呼んでいる箇所が他に無いかを grep して確認すること。

---

## 4. 実装 — 永続化

### 4.1 保存先

```text
data_dir() / "resource-load-profiles.json"
```

`app.config.data_dir()` を使う。`backend/app/models_mgmt/runtime_policy.py` の
`_path()` と同じ流儀に合わせる。

### 4.2 形式

```json
{
  "schema_version": 1,
  "profiles": {
    "llama:qwen3-27b:<hash>": [
      {
        "measured_at": 1755700000.0,
        "process_start_sec": 6.2,
        "model_load_sec": 76.8,
        "cold_load_cost_sec": 83.0,
        "first_token_latency_sec": 0.733,
        "load_kind": "cold"
      }
    ]
  }
}
```

### 4.3 要件

```text
起動時に読み込み、schema_version 不一致・破損・型不一致は「無いもの」として扱う
  （例外を投げてWeb起動を止めない。warning ログのみ）
書き込みは atomic（tmp へ書いて os.replace）
key あたり最大 _max_profile_samples 件（既存 deque の maxlen を尊重）
MAX_PROFILE_AGE_DAYS = 30 を超える sample は読み込み時に破棄
書き込み頻度は record_load_measurement 時のみ。高頻度イベントでは書かない
ファイル全体の上限サイズを設け、超過時は古い key から落とす
`clear()`（telemetry.py:212 付近）はファイルも削除すること
```

OOM profile（`_oom_profiles`）も同じファイルに入れてよい。
入れる場合は `"oom_profiles"` として別キーにし、schema_version を共有する。

---

## 5. 実装 — 可視化

### 5.1 `_load_profiles()` の拡張

`GET /api/v1/resources` の応答に含まれる profile へ以下を追加:

```json
{
  "residency_key": "...",
  "cold_load_cost_sec": { "p50": ..., "p90": ..., "count": ... },
  "warm_reload_cost_sec": { "p50": ..., "p90": ..., "count": ... },
  "yield_basis": "warm" | "cold" | "insufficient",
  "yield_threshold_sec": 15.7,
  "first_token_latency_sec": { ... }
}
```

`yield_threshold_sec` は `reload_cost_p90().value_sec * THRASH_FACTOR`。
利用者が「何秒以上のjobなら退避するのか」を直接読めるようにする。

### 5.2 設定UIの表示

既存の managed supervision 設定画面（PR-D2 で追加済み）に、以下を**表示のみ**で追加する。

```text
退避判断の基準       warm 実測 / cold 実測（暫定）/ サンプル不足
基準値               15.7 秒（warm p90、サンプル 4 件）
退避する条件         推定実行時間が 31.4 秒を超えるジョブ
直近の抑止理由       サンプル不足 / 退避コストに見合わない / 最低常駐時間 / 短時間に頻発
```

cold basis のときは次の一文を出す:

```text
退避後の再読み込み実測が不足しているため、初回読み込みの実測値を暫定で使っています。
この間は退避がほとんど発生しません。「今すぐ退避」を数回実行すると精度が上がります。
```

320px と 1280px の両方で overflow が出ないこと。

### 5.3 待機Job UI

`yield.suppressed` の理由を、待機中Jobの wait reason 詳細に反映する。
「GPUの空き待ち」だけで止めず、なぜ LLM を退避しないのかが分かるようにする。
文言は host 側が持ち、broker は enum を返す（既存方針を維持）。

---

## 6. `estimated_runtime_sec` について（このPRの範囲外・確認のみ）

`grep -rn "estimated_runtime_sec" backend/` の結果、
**読む箇所しか存在しない**（`schema.py:87` の定義と `resource_provider.py` の判定2箇所）。
セットする実装が無い。

したがって現状すべての yield は `_yield_allowed()` の

```python
if request.estimated_runtime_sec is None:
    self._telemetry.record("yield.suppressed", reason="runtime_unknown")
```

で抑止される。これは実装漏れではなく、値を出す側（Media Forge）が未実装だから。

**このPRでControlDeck側に推定器を作らないこと。** Media固有の知識が必要になり境界を汚す。
やることは以下のみ:

- `runtime_unknown` が §5.2 の「直近の抑止理由」に正しく出ること
- `docs/design-ai-resource-broker.md` に
  「`estimated_runtime_sec` は要求元が申告する。未申告の要求は退避を誘発しない」
  を明記する

---

## 7. テスト要件

`backend/tests/` に追加。既存テストは1件も壊さない。

### 7.1 分類

```text
unload 記録なしのロード -> cold
unload から WARM_WINDOW_SEC 以内のロード -> warm
unload から WARM_WINDOW_SEC 超過のロード -> cold
warm 判定は1回限り（同じ unload で2回 warm にならない）
別 residency_key の unload は影響しない
```

### 7.2 閾値選択

```text
warm 3件以上 -> basis="warm"、warm の p90 を返す
warm 2件 + cold 5件 -> basis="cold"
warm 0件 + cold 2件 -> None（insufficient）
None のとき _yield_allowed が load_cost_unknown で False を返す
cold 83s / warm 8s 混在時、閾値が 16s 側になる（166s にならない）  ★回帰の本体
```

### 7.3 永続化

```text
record -> 新インスタンスで読み込み -> 同じ p90
破損JSON -> 例外を投げず空プロファイルとして起動
schema_version 不一致 -> 無視して起動
MAX_PROFILE_AGE_DAYS 超過 sample が読み込み時に落ちる
maxlen を超えない
clear() でファイルが消える
atomic write（書き込み途中でプロセスが死んでも既存ファイルが壊れない）
```

### 7.4 統合

```text
managed opt-in + warm basis + estimated_runtime_sec が閾値超 -> 退避する
managed opt-in + warm basis + estimated_runtime_sec が閾値以下 -> thrash_cost で抑止
estimated_runtime_sec = None -> runtime_unknown で抑止
ControlDeck 再起動を模した telemetry 再構築後も退避判断が継続できる    ★回帰の本体
min_uptime_sec / THRASH_WINDOW_SEC / THRASH_MAX_YIELDS の既存挙動が不変
```

### 7.5 回帰（絶対条件）

```text
backend/tests/test_llama_kv_capacity.py（無改変で通ること）
canonical ./deck.sh test 全件（現在 671 件成功・1 skip）
frontend production build
```

---

## 8. 実機検証（PR完了条件）

以下を実際に行い、結果を `docs/implementation-status.md` に記録すること。
数値は実測のみ。推定を書かない。

```text
1. supervision=observed のまま LLM を cold load し、cold sample を1件記録
2. ControlDeck を再起動し、プロファイルが復元されていることをAPIで確認   ★
3. supervision=managed へ opt-in
4. 20GiB exclusive の broker request を投げ、待機させる
5. 「今すぐ退避」を手動実行 -> stop -> grant -> release
6. 続く Gateway request での再ロードが warm として記録されることを確認   ★
7. 5-6 を3回繰り返し、basis が cold から warm へ切り替わることを確認     ★
8. 切り替わり後の yield_threshold_sec が 166s ではなく warm 基準になることを確認 ★
9. 検証後は supervision=observed へ戻し、LLM停止、Broker予約0を確認
```

★ が今回の本体。ここが確認できないPRは未完了とする。

320×700 と 1280×800 の実Chromiumで §5.2 の表示、overflow 0、
認証後 console error 0 を確認すること。

---

## 9. ドキュメント更新

```text
docs/design-ai-resource-broker.md
    cold/warm の定義と分類規則
    reload_cost_p90 の選択規則と MIN_WARM_SAMPLES
    永続化ファイルの位置と schema
    estimated_runtime_sec は要求元申告である旨（§6）
    bootstrap（手動退避で warm を貯める）の説明

docs/implementation-status.md
    §8 の実測結果

docs/addon-ux-guidelines.md
    抑止理由の文言規約（enum -> 表示文の対応）
```

---

## 10. 完了条件

```text
warm/cold が分離され、退避判断が warm 基準で行われる
ControlDeck 再起動後もプロファイルが残り、managed が無効化されない
サンプル不足時は保守側（退避しない）に倒れ、その理由が UI に出る
利用者が「何秒以上のjobで退避するのか」を画面から読める
canonical 全件成功、frontend build 成功、実機で §8 の ★ 4項目を確認
managed の既定値は observed のまま
```

managed の既定化は本PRの対象外。実 Media job による warm サンプルが
十分に貯まってから、別PRで判断する。
