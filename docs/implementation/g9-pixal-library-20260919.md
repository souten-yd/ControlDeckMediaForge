# 2026-09-19 既存3D成果物のLibrary登録

利用者の「成果物あるの？ライブラリに追加して」に対応。既存trellis.cppの2件を
稼働MediaForge 0.28.87で再確認し、Pixal3DのCPU移植検証で作成済みのGLBを1件追加した。
学習済みPixal3Dの新規生成、Vulkan実行、モデル採用・署名導入の成功とはしない。

## 登録された成果物

| 内容 | Asset ID | bytes | 今回の操作 |
|---|---|---:|---|
| trellis.cpp `ref_vk.glb` / 元WebP | `asset_eb160c5649954d48a615693f0e3c3c6b` | 11,443,236 | 既存登録・取得を再確認 |
| trellis.cpp `s01_vk.glb` / 元WebP | `asset_77a23cf2d502453a8046b376d161adec` | 11,189,676 | 既存登録・取得を再確認 |
| Pixal3D CPU / 合成重みの検証用GLB | `asset_fb6f0e144cfe45e3bec02996b366eb53` | 48,220 | 新規登録 |

PixalのLibrary要約は
`[検証用] Pixal3D CPU移植・合成重みサンプル（学習済み生成ではありません）`。
ダウンロード名は `pixal3d-cpu-synthetic-validation.glb`。
warningsにも合成重み・人工形状であり、学習済み品質やVulkan動作の証拠ではないことを記録した。
元GLBはPR569の `g9-pixal-camera-20260919/cpu-verified/connected/asset.glb`。
576三角形・UV1・128²画像2件は同PRのBlender4.5.9再import証跡に対応する。
骨・animationは追加していない。

新GLBのSHA-256:
`83162c993fca95932da399769d2a5d4bb31b05f2879494c049c2cbdad453b4db`。
既存trellis2件も稼働HTTPで全bytesを取得し、次の既存hashと一致した。

- ref: `7c4bb4b1b8cd4a29c868b234d4137f16bcefd1bd2160771cda07054706e02628`
- s01: `f9e460426a486a5c80c55968e898e9105069d20bbe1408a4f3c3b5f30f86ea78`

## 登録経路と実測

生GLBの公開import endpointは名前・intent・warningsの入力を持たないため、今回だけの
保守scriptで稼働版と同じ0.28.87の `Store.create_job/register_asset/update_job` を使用した。
既存asset/provenance/Jobs基盤へ追加し、既存DBのinitialize/migration、旧Assetの書換えは行わない。
実データrootは `feature-data/media-forge/data`。元2件のStore応答と稼働HTTP応答の一致を
書込み前に照合した。Host DB・認証・Brokerには触れていない。

import provenanceは `operation=asset.import` / `model_id=media-forge/local-import` /
`runtime_adapter=deterministic.glb-import` とし、今回推論したように記録しない。
`source_kind=synthetic` / `source_backend=cpu`、元GLB内のinput/source hash、seed、上流revision、
元生成時刻を保持。`license=development-synthetic` はこの合成fixtureの記録であり、
配布checkpointのライセンス同意・adoption receiptを作成した意味ではない。

実行（実行時のcwdに依存しない）:

```bash
PYTHONPATH=/tmp/mediaforge-webp-20260919/backend \
  /data1tb/ControlDeckMediaForge/.venv/bin/python \
  /data1tb/ControlDeck/data/feature-data/media-forge/maintenance/g9-pixal-library-20260919/register-artifact.py
```

独立validator 1.1.0で元GLBを検査した後、新Asset・sidecar・成功Jobを保存。
実稼働HTTPは以下を観測した。

- `/health`: HTTP200 / healthy、currentは`versions/0.28.87`。
- 新AssetとprovenanceとJob: HTTP200、synthetic表示・警告・succeededを確認。
- 新Asset content: HTTP200、元GLBと全bytes一致。
- `/workspace-api/library`へ`kind=all, media_kind=glb, limit=120`:
  HTTP200、3件すべて掲載、新要約とwarnings一致。
- 同scriptを再実行: hashで既存1件を再利用し、`created=false`。重複登録なし。
- 3件のprivate viewer `model/open`→`models/{handle}/bytes`→`close`:
  HTTP200、全chunk再結合のbyte数/SHA-256一致、独立構造・texture memory検査passed、
  今回開いた3handleをすべて解放。ブラウザ画素・操作の受入ではない。

初回script起動はvalidator版定数のimport名を誤記してImportError、書込み前に終了した。
実名`VALIDATION_VERSION`へ修正後に上記登録と再確認が完了した。
製品コード・稼働サービス・GPU・モデル重みの変更はない。

## 証跡と残り

managed `maintenance/g9-pixal-library-20260919/`へ`register-artifact.py`、
`registration.json`、`recheck.json`、`viewer-delivery.json`、`full-test.log`を保存。

この記録branchで `./mf.sh test`: **2211 passed / 2 warnings / 237.96秒 / exit0**。
以後の変更は記録のみ。文書参照と`git diff --check`も確認した。

NOT TESTED: 今回登録後のブラウザ描画・操作、学習済みPixal3Dの実生成と品質、
正規Host lease付きVulkan、production worker/adoption/署名導入、骨付きanimation。
画像からの本生成機能とPixal3D導入評価という全体目標は未完了。
背景除去provider接続は `ux1/pixal3d-background` の未変更作業treeで継続可能。
