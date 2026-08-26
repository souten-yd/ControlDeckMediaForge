# G7 — video runtime and deterministic packaging

設計の正: `docs/base-plan.md` §11 / `docs/implementation/goal-roadmap.md` G7  
前提: G1 で凍結した公開契約へ加法的に載せ、画像 worker や ControlDeck 本体へ動画依存を漏らさない。

## 0. 利用者に届ける状態

普通の chat / workspace から短い動画を作り、待機理由・進捗・cancel を確認できる。
出力はモデルが書いたファイルをそのまま公開せず、FFmpeg で codec、container、寸法、
fps、frame 数、尺を正規化してから asset / provenance / lineage に登録する。

G7 は次の全スライスが実機で通るまで未完了である。

```text
V0  additive public contract + deterministic FFmpeg boundary
V1  revision-pinned candidate probe and model adoption gate
V2  video worker adapter + routing + Broker lease/progress/cancel
V3  workspace/chat/library playback and animation profile
V4  installed ControlDeck / R9700 / SonicForge coexistence acceptance
```

## 1. V0 — contract and FFmpeg boundary

### 1.1 公開 operation

既存設計どおり `video.generate` と `video.edit` を追加する。モデル名を公開引数にしない。

```text
video.generate + inputs 0      video.text_to_video
video.generate + inputs 1      video.image_to_video
video.generate + inputs 2..8   video.multi_keyframe（対応 runtime のみ）
video.edit     + inputs 1..8   video edit / extend（V2 で constraints を型付け）
```

出力は `mp4` または `webm`。image/pack operation は動画形式を受理せず、video operation
も image/zip 形式を受理しない。Asset の既存必須 field は変えず、MIME に
`video/mp4` / `video/webm`、任意 metadata に `duration_sec` / `frame_rate` を加える。

V0 では capability document の `video.image_to_video=unavailable/planned_for_g7` を維持する。
API ingress は将来の要求を保存できるが、実行は `capability_unavailable` で fail-closed にする。
モデル未実測の状態で fake 動画や画像 sequence を成功として返さない。

### 1.2 worker 境界

FFmpeg 実装は `worker_packs/video/` が所有する。core は worker 実装を import しない。
呼び出し元は job root 内へ realpath containment 済みの source/output だけを渡す。
subprocess は配列引数、`shell=True` なし、timeout 付きとする。

V0 の正規化範囲:

```text
入力 video stream      ちょうど 1
出力寸法                偶数、16px 以上
fps                     1..120
尺                      0 < seconds <= 300
MP4                     H.264 / yuv420p / faststart、任意 AAC
WebM                    VP9 / yuv420p、任意 Opus
検証                    ffprobe で stream/codec/container/dimensions/fps/frame count/audio
失敗時                  partial output を削除し、理由を握り潰さない
```

V0 はモデル出力を作らないため GPU lease を取らない。V2 では生成 worker が lease を所有し、
FFmpeg stage は同じ durable job の CPU-only `normalize` phase として生成後に走る。

## 2. V1 — model adoption gate

候補は `Wan2.2 TI2V-5B` を最初の軽量 T2V/I2V probe、Wan A14B と LTX-2.x を比較候補とする。
候補名は routing 契約ではなく評価対象であり、置換可能でなければならない。

実行前に公式 repository / model card / license / pinned revision を確認し、base-plan §24 の
10 項目を埋める。snapshot が取得済みでも available にはしない。R9700 / gfx1201 で次を実測する。

```text
runtime build/import/preflight
最小 1-frame または最短 clip smoke
実用最短 clip の cold/warm wall time
VRAM resident/execution_peak/cold_load_peak/headroom
host RAM / process swap / cancellation latency
出力の decode、frame 数、fps、寸法、尺
```

動かない、VRAM が収まらない、Host watchdog を巻き込む、または出力が壊れる候補は延期する。
カーネル自作や ControlDeck への動画固有依存追加には進まない。

### 2.1 Wan2.2 TI2V-5B の V1 判定（2026-08-26）

公式 Wan2.2 repository commit `42bf4cfa` と model revision `921dbaf3` を固定し、
Apache-2.0 の TI2V-5B を R9700/gfx1201 で評価した。core/image 環境から分離した ROCm
runtime を使い、UMT5 CPU phase と GPU generation phase を別 process にした。upstream の
CUDA-only FlashAttention 呼び出しは upstream 自身の PyTorch SDPA fallback へ固定した。
独自 kernel は追加していない。

実測した 512x320 / 17 frames / 30 steps は cold 412.790 秒、warm 3 回は
75.955 / 71.972 / 71.221 秒、incremental peak VRAM は最大 30,552,207,360 bytes、
process peak RSS は最大 20,525,383,680 bytes、process swap は 3 回とも 0 bytes だった。
同一 seed の warm 出力 SHA-256 は 3 回一致し、固定 prompt の robot / solar panel / landscape
を識別できた。ControlDeck Broker の queue、activate/renew/release と 1.007 秒の cancel、
SonicForge lease の後続取得も実測した。

一方、より長い 256x256 / 49 frames / 30 steps は完走したが 235.053 秒、process swap
1,754,775,552 bytes となり、映像も固定 prompt の被写体を維持できなかった。I2V、native
720p、公式既定 121 frames / 50 steps は未実測である。このため V1 の採用ゲートは次の判定とする。

```text
ROCm runtime / bounded short smoke     PASS
Broker admission / lease / cancel      PASS
512x320 / 17-frame bounded quality     PASS（比較用の短尺候補）
実用 clip quality / host RAM safety    FAIL
I2V / native 720p / upstream default   NOT TESTED
supported/default runtime adoption     DEFERRED
```

catalog の resource measurement は実測値へ更新するが、state は `experimental`、recommended
profile は空、公開 capability は unavailable のままにする。V2 へ進む再開条件は、実用最短
clip が prompt を維持し、process swap 0 で完走する profile または別候補を見つけること。
候補比較をせず、この probe を production adapter に昇格させない。

### 2.2 host-memory lifecycle follow-up（2026-08-26）

upstream の `offload_model=True` は denoise 後の transformer を CPU に materialize してから
VAE decode する。短命 evaluator は decode 後に transformer を再利用しないため、この境界で
parameter storage を meta tensor へ破棄し、GPU storage を解放して CPU copy を作らない方式を
比較した。これは evaluator lifecycle の変更であり、kernel、public contract、Host の変更ではない。

実 browser/Broker smoke は process swap 0、peak VRAM 13,752,025,088 bytes で成功した。
384x256 / 33 frames / 30 steps も process swap 0、peak VRAM 14,045,294,592 bytes で完走したが、
284.677 秒のうち VAE decode が 210.810 秒を占め、被写体の形状崩れが残った。

512x320 / 33 frames は SonicForge が使う non-yieldable LLM residency 中の2要求を
`insufficient_capacity` で fail-closed にした後、自然 release 後に2回完走した。固定 prompt
の robot / solar panel / dusk と同じ SHA-256 を再現し品質は PASS したが、process swap は
2,501,005,312 / 346,812,416 bytes で zero-swap gate を満たさなかった。host RAM lifecycle の
改善と品質は PASS、運用 reliability は FAIL とし、V2 adoption gate は閉じたままとする。

### 2.3 replacement candidate preflight（2026-08-26）

Wan practical profile が zero-swap gate を落としたため、次の比較候補は HunyuanVideo-1.5
480p T2V distilled とする。公式 HunyuanVideo-1.5 は 8.3B、offload 有効時の公称最小 VRAM
14GB で、LTX-2.x の 22B transformer + 12B text encoder より先に R9700 で測る根拠がある。

weight 取得前に専用 ROCm runtime を分離構築した。fixed Diffusers conversion revision は
`1abb14f0`、公式 model identity は `tencent/HunyuanVideo-1.5@9b49404b`。Diffusers 0.40.0 の
`HunyuanVideo15Pipeline` / transformer / VAE import、gfx1201、PyTorch SDPA default backend は
PASS した。CUDA-only Flash/Sage/Flex/SGL kernel は導入しない。

候補 bundle は 13 weight files / 53,367,753,676 bytes で、Tencent Hunyuan Community License
Agreement が適用される。利用開始自体が同意となり、地域、acceptable use、配布・表示条件を含むため、
明示同意なしに weight download を開始しない。runtime preflight は PASS、weight/inference は
**BLOCKED PENDING LICENSE ACCEPTANCE / NOT TESTED** とする。

### 2.4 license-gated evaluator preparation（2026-08-26）

weight 取得前に、Hunyuan 候補の private evaluator runner と Host admission 境界を実装する。
runner は repository ID を受け取らず、exact revision 名のローカル Hugging Face snapshot だけを
受理する。`local_files_only=True`、Hub/Transformers offline、telemetry off を強制し、固定 prompt / seed /
preset 以外を public input にしない。

```text
smoke           256x256 / 5 frames / 1 step（load/ROCm のみ。品質証拠ではない）
candidate-clip  640x384 / 33 frames / 50 steps（bounded 比較）
official-clip   848x480 / 121 frames / 50 steps（公式 cfg-distilled step数）
```

core は専用 runtime と conversion snapshot が両方明示設定され、revision/model index の containment
検証を通った場合だけ評価操作を提示する。通常の capability router / recommended profile / available
state は変えない。評価操作は既存 Host Job と Broker lease、renew、cancel、release、VRAM/RSS/swap
metrics、ffprobe validation を再利用する。実測前の Broker envelope は `confidence=low` の保守値であり、
catalog measurement や production routing へ転記しない。

この準備コード自体は license acceptance や weight download を行わない。実 runner の model load /
generation は引き続き **BLOCKED PENDING LICENSE ACCEPTANCE / NOT TESTED** とする。

## 3. V2 — execution

private runtime adapter が raw frames/video を job root に書き、V0 の FFmpeg stage が公開 asset
へ正規化する。router は required capability、local-only、policy、実測 resource envelope だけで
選ぶ。`model_id` は manual opt-in 以外で public request に要求しない。

GPU job は ControlDeck Broker へ実測値と `estimated_runtime_sec` を申告し、lease acquire / renew /
cancel / release を通す。待機中は Broker の reason を job phase と Host Jobs に伝える。
Media Forge 内にグローバル GPU scheduler を作らない。

動画 asset の上限は画像用 64 MiB を流用せず、V1 の実測から operation 別に bounded に決める。
推定だけで上限を拡大しない。

## 4. V3 — user surface

Create の段階開示へ video を追加し、capability unavailable の間は既定表示しない。
Library は poster/thumbnail を先に読み、動画本体を一覧で自動再生しない。Activity は queued、
waiting、generating、normalizing、validating、registering を復元できる。cancel は tab を閉じても
durable job へ届く。animation profile は generic operation の profile であり専用 API にしない。

## 5. V4 — installed acceptance

SonicForge が並行稼働する実 host で Broker を唯一の調停経路として次を実測する。

```text
text-to-video と image-to-video を chat/workspace から各 1 本
待機理由、見込み、進捗、cancel と再接続復元
LLM 退避回数、抑止理由、warm reload sample、生成後の LLM 復帰
lease 全解放、残存 worker なし、core healthy
出力 MP4/WebM の codec/container/dimensions/fps/frame count/duration
asset lineage/provenance と installed browser playback
SonicForge job と競合した場合の queue/admission（同時に VRAM を直接取り合わない）
```

Host 変更が必要なら Media Forge 側で解けない理由を 1 行で記録し、汎用機能だけを ControlDeck
の別 PR にする。Media 固有 route、依存、文言は Host へ入れない。

## 6. 完了判定

V0〜V4、focused/full gate、実 R9700、installed ControlDeck browser、Broker/VRAM/worker cleanup の
証拠が揃ったときだけ G7 完了。未実測候補や壊れた smoke は capability unavailable のまま記録する。
