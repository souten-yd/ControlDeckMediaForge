# 2026-09-19 Pixal3D private worker入口のCPU実測

親PR571 / `f887fbc71b04974cc93f2c8c79c675a61fc88739`、branch `ux1/pixal3d-worker-entry`。
画像入力生成へ接続する前提として、評価CLIから独立したprivate worker入口を追加した。
既存評価CLIはseedがF32 settings arrayで、16,777,217を正確に保持できず、固定limitや
故障注入/noise入力も持つ。新入口では整数seedと明示limitを使い、評価用入力を除外する。
coreのScene Jobs/採用receipt接続はまだ実装していない。installedで利用可能とはしない。

## 変更と境界

- `worker_spec.py`: exact private descriptor、9 native model role、許可root、ファイルサイズ/SHA、
  CPU前処理source/checkpoint、sampler/normalization、整数seed以外の生成設定を検証。
- `worker_entry.py prepare`: CPUで背景除去/MoGeを実行し、入力画像・descriptor・8出力のidentity、
  正確な整数seedを束縛した`ready.json`を最後に公開。終了後に親がGPU admissionを行う。
- `worker_entry.py generate`: ready hashと全入力を検証、明示backend/deviceでnativeを起動し、
  report/GLBを検査してidentityを再照合してから`complete.json`を公開。
- `pixal-generate`: backendを作らない`inspect`と、CPUまたはVulkanを明示する`generate`。
  native生成の式・RNG方式は維持。seedはtext→uint32で0..2^31−1を保持する。
- `bounded_npy.h`: NPY v1/little-endian/F32/C-order、header上限、shape積、正確なbyte数、
  finiteを検査。shape積/実ファイルサイズ検査より前にtensor領域を確保しない。
- workerは所有出力だけを回収し、既存出力を上書きしない。native子はworkerと同じprocess group。
  取消/timeout時にTERM、5秒後に必要ならKILL/reap。失敗stderr末尾はprivate診断へ保持する。

private manifestはlicense同意・GPU lease・adoption receiptではない。
親が正規Host admission/renewal/group回収、独立Blender検査、既存Asset登録を所有する。
CPU評価をVulkanからのfallbackに使わない。MoGe/BiRefNetは明示CPU経路である。

## 実行と結果

fixed trellis `2516c48b677050c570f47eba2e68dc8a5bc918b0`、GGML
`737e88f25d4f62254f3b7a726fd9663036cc94da` の既存source/buildに対し、別overlayをbuildした。

```bash
cmake -S runtimes/trellis-cpp-pixal/native \
  -B /tmp/mediaforge-pixal-worker-build -DCMAKE_BUILD_TYPE=Release \
  -DTRELLIS_SOURCE_DIR=/data1tb/ControlDeck/data/feature-data/media-forge/runtimes/trellis-cpp \
  -DTRELLIS_BUILD_DIR=/data1tb/ControlDeck/data/feature-data/media-forge/runtimes/trellis-cpp/build
cmake --build /tmp/mediaforge-pixal-worker-build --target pixal-generate pixal-pipeline-check -j 2
```

configure/buildともexit0。`pixal-generate` SHA-256は
`3ecdbfa3a2d91001b2bb3b8c96d603c5ecf374dbcf956def003dbefff5b26f98`。
同時buildした旧評価binaryは`1109e3381858e0a7b444ce4eac1f4c936a0a448da527c3f673a2a4581e0b6998`、
前回と一致。GGML4 libraryとruntime source73ファイルのhashも保存・再照合した。

実行済み検証コマンド（以下の変数は保存先の省略表記）:

```bash
PIXAL_MANAGED=/data1tb/ControlDeck/data/feature-data/media-forge
PIXAL_RUNTIME="$PIXAL_MANAGED/runtimes"
PIXAL_EVIDENCE="$PIXAL_MANAGED/maintenance"
"$PIXAL_RUNTIME/pixal3d-probe/.venv/bin/python" runtimes/trellis-cpp-pixal/check_worker.py \
  --background-source "$PIXAL_RUNTIME/pixal3d-probe/sources/BiRefNet-hf/e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4" \
  --moge-source "$PIXAL_RUNTIME/pixal3d-probe/sources/MoGe" \
  --background-fixtures "$PIXAL_EVIDENCE/g9-pixal-background-20260919/cpu-first" \
  --camera-fixtures "$PIXAL_EVIDENCE/g9-pixal-camera-20260919/cpu-verified" \
  --pipeline-fixtures "$PIXAL_EVIDENCE/g9-pixal-naf-projection-20260919/pipeline-first" \
  --binary /tmp/mediaforge-pixal-worker-build/pixal-generate \
  --baseline-binary /tmp/mediaforge-pixal-worker-build/pixal-pipeline-check \
  --core-python /data1tb/ControlDeckMediaForge/.venv/bin/python \
  --blender "$PIXAL_RUNTIME/blender/blender-4.5.9-linux-x64/install/blender" \
  --output-dir "$PIXAL_EVIDENCE/g9-pixal-worker-20260919/cpu-first"
"$PIXAL_RUNTIME/pixal3d-probe/.venv/bin/python" runtimes/trellis-cpp-pixal/check_worker_lifecycle.py \
  --fixtures "$PIXAL_EVIDENCE/g9-pixal-worker-20260919/cpu-first" \
  --alpha-image "$PIXAL_EVIDENCE/g9-pixal-camera-20260919/cpu-verified/input.png" \
  --allowed-root "$PIXAL_MANAGED" \
  --output-dir "$PIXAL_EVIDENCE/g9-pixal-worker-20260919/lifecycle-first"
```

両checker exit0。既存合成checkpointを使うCPU実processの測定値:

| 対象 | 観測 |
|---|---|
| opaque画像prepare | 18.296240秒、PR571の前処理4ファイルとbyte一致 |
| 新worker generate | 1.216938秒、SS7→upsample1792→HR51→1024-grid |
| 出力 | 48,532byte、590三角形、texture128²、独立core/Blender4.5.9 pass |
| 旧評価入口 | 0.721703秒、生成時刻だけを除いたGLB JSONと全binaryが一致 |
| 反復 | 1.214811秒、同じGLB比較で完全一致 |
| seed整数 | 16,777,216 / 16,777,217 / 2,147,483,647のreportとGLB extrasが一致 |
| 拒否/保持 | 15条件pass。改竄、別job、unknown/role/設定、fault/noise/duplicate引数、不正NPY、既存出力 |
| 背景encoder取消 | 実SIGTERM、exit1、0.917840秒でreap、出力なし |
| native SS flow取消 | 同一groupの実子を観測後SIGTERM、exit1、0.047917秒でreap、出力なし |
| native timeout | 0.2秒設定、子観測後0.211352秒でexit1/reap、出力なし |

5 GLBのcore/Blender検査でUV・画像・材質接続を確認。armatureは全件0。
隣接seedのGLB binary SHAは`c14e3b3d...b3eef6`と`4c5ac0ab...844af8`で異なる。
full SHA、全時刻、PID、bounds、拒否理由は各reportに保存した。
RNGは`mt19937-box-muller-f32-v1`であり、Torchの同じseedとの一致は主張しない。
縮小幅/人工形状/合成重みの検証であり、学習済み生成の品質ではない。

`./mf.sh test`: **2211 passed / 2 warnings / 237.85秒 / exit0**。以後product変更なし。
warningは既存Starlette/httpxとPillow getdata非推奨。full-test.logに保存した。

## Library・残り

2026-09-19T08:30:11Z、稼働`127.0.0.1:9130`のhealth/Library/asset/provenance/contentを実HTTPで確認。
PR570で登録済みの以下3件は掲載され、全contentのSHAが一致。今回の追加書込み0。

- `ref_vk.glb`: `asset_eb160c5649954d48a615693f0e3c3c6b`、11,443,236byte。
- `s01_vk.glb`: `asset_77a23cf2d502453a8046b376d161adec`、11,189,676byte。
- `pixal3d-cpu-synthetic-validation.glb`: `asset_fb6f0e144cfe45e3bec02996b366eb53`、48,220byte。
  Libraryの「合成重み検証用」表示とprovenanceを確認。今回のworker出力への差替えは行っていない。

証跡はmanaged `maintenance/g9-pixal-worker-20260919/` の`cpu-first/report.json`、
`lifecycle-first/report.json`、configure/build/full-test log、build-provenance、library-recheck.json。
元rootは`feat/g9-image-to-3d` / `524553d`でclean、origin/mainは`bbdc69a`。

NOT TESTED: core Scene Jobsへの接続、private adoption receipt、学習済み全幅/実画角/生成品質、
正規Host lease付きVulkan、署名導入、新入口からのLibrary登録、ブラウザ画素、骨付きanimation。
trained重み取得/使用とGPU実行は0。重みの同意・正規leaseは未取得のまま。
次はprivate receiptとCPU prepare終了待ちを既存Scene Jobsへ接続する。
元Host/installed/runtimeを変更せず、全体目標は未完了として継続する。
