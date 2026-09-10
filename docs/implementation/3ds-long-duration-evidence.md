# 3D Studio 長時間受入の証拠対応

Date: 2026-09-10 / Status: PARTIAL

対象はg8-3d-studio-plan.md §4 E。以下は異なる既存実行の証拠であり、
同一run・同一releaseの一巡として合算しない。人工待機を自然な制作時間へ読み替えない。

| 条件 | 実測証拠 | 限界 |
|---|---|---|
| 10分超GUIと認証更新 | installed.30、mf-rfb-renewal-negative-0.28.30-20260906。480.340秒でRFB instance2、同sessionで660.433秒接続、671.862秒実編集保存、mesh1→2、login回収 | ディレクトリ名negativeは失敗を意味しない。更新後の実GUI入力保存まで確認済み。現在版での新実行・GPU描画ではない |
| 10分超setupと認証更新 | installed.69、mf-setup-host-long-installed-0.28.69-20260910。browser切断、650秒診断flock、refresh監査23353 success、653.413秒repair完了、Host成功一致 | 人工的な反映前待機。自然download/演算・反映後取消・期限切れではない |
| 自然120秒超の制作工程 | installed.57、mf-natural-texture-quality-installed-0.28.57-20260910。画像生成238.346秒、native観測163.032秒、同panel材質適用GLB、Host2件成功、GPU lease renew23/release1 | 画像工程の実演算。Blender CPU演算や今回OpenCode制作、見た目の完成品質の証拠ではない |
| child更新後の取消と終了同期 | installed.30、mf-credential-refresh-installed-0.28.30-20260906。644.700秒、元期限後615.630秒cancel、5 succeeded/1 canceled、Host終端一致 | CPU queue fault injection。自然制作やGUI/setup自身の認証更新とは別 |
| 通常画像の資源待ち更新と取消 | source PR488、mf-source-image-renewal-6hxjs5ll。実workspace WS/Broker、初期TTL180秒、audit24014 success、252.378944秒待機→通常取消で0.366秒local/Host/request canceled | 待機自体は実LLM競合、TTLは診断条件。画像未実行・lease未取得。主診断末尾URL誤り404/exit1を保持、独立取消/control監査exit0。自然10分・installed成功ではない |
| 通常画像の実待機更新から生成・終了 | source PR490、mf-source-image-renewal-dfpxj82d。初期TTL180秒、実Broker待機中refresh2、680.587秒generating、704.618秒画像/Host成功/通常sent1。独立SHA/PNG/provenance、GPU0 activate1/renew2/release1確認 | 待機は実LLM競合、初回TTLだけ診断条件。長い待機を長い画像演算へ読み替えない。通常TTL/installed.70/GUI共存は未確認 |

## 今回の読み取り専用再照合

外部 `/data1tb/mf-long-duration-evidence-audit-20260910.py`、exit0。
証跡 `/data1tb/mf-long-duration-evidence-audit-ehx6fhxm/observations.json`。
5原観測ファイルのSHA、GUIの旧新revision JSONと現在DB、実GLBのmesh nodes1/2を照合。
旧新blend/GLBと制作画像の5 Assets/8,274,480Bは実bytes SHAとDB provenanceが一致。
制作画像のJob成功、CPU試験6Jobの現終端、.69 setup journal保持、
画像適用済みtextured-panel.glbの独立監査SHAも確認。
この照合は過去のプロセス操作を再実行したものではなく、現在版のGUI認証更新の新証拠ではない。

## 残るEの条件

GPU ID/実VRAM/driver、CPU session・GPU session・Cycles・画像生成・Host LLMの
組合せ、競合時の保存→GUI停止→解放→画像実行→GUI復帰は、対応する実機証拠で別途判定する。
software GUIの終了確認からGPU leaseを推測しない。GPU GUI/Cyclesの条件付き提供を
「利用可能」と偽らず、設計CHECK-03と現capabilityを照合する。
この表だけで全E、3DS-8、ゲームアセット完成を宣言しない。
次はGPU/共存の既存証拠と現capabilityを照合し、未受入の組合せを特定する。
