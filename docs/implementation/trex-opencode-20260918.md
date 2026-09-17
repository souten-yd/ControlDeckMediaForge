# ローカルLLMによるティラノサウルス制作の実測

Date: 2026-09-18 (Asia/Tokyo)

利用者の「OpenCodeからローカルLLM・MCP経由でBlenderに恐竜を作らせる」依頼。
制作briefは低ポリ・色付き・静止ティラノサウルス、全長約3m、目標5000 triangles以下、
GLB 1件。形状の座標・サイズ・回転・色はローカルLLMに決めさせた。

## 実行条件

- Source / origin/main: `9304129119ea94dcc9241783a3cef419ec684b8a`。
- Installed MediaForge: `0.28.84`、9130 health healthy。
- OpenCode: `1.18.30`、既存Host gatewayの`controldeck/auto`。
- Gatewayが選択した既存モデル: `Qwen3.8-27B`、8097。
- 実8097 `/props`: `Qwen3.8-27B-UD-Q4_K_M.gguf`、build `b1-8ea2902`。
- Project: `MF3DS-Trex-20260918`。
- OpenCode session: `ses_f4e834d7effeKWoReYKIr7JX3l`。
- 元の実行harnessは`scripts/3ds_opencode_flow_e2e.py`。管理されたmaintenance領域に
  一時コピーを作り、制作promptと期待納品名を`trex.glb`へ変更した。
  `director_static`というharness flagはskill・直接MCP権限のpreflightを再利用するためであり、
  剣のduplicate/mirror受入結果ではない。
- LLMへ許可したものはblender-director skill、MediaForge MCP、project output grant。
  shell/file/web/taskは無効。Host/global設定、モデル/runtimeを変更していない。

実行command（cwd `/data1tb/ControlDeck/app`）:

```bash
CONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml \
PYTHONPATH=/data1tb/ControlDeck/app/backend \
/data1tb/ControlDeck/app/.venv/bin/python \
/data1tb/ControlDeck/data/feature-data/media-forge/maintenance/trex-opencode-20260918/run_trex.py \
  --director-static --project-name MF3DS-Trex-20260918 \
  --evidence-dir /data1tb/ControlDeck/data/feature-data/media-forge/maintenance/trex-opencode-20260918/run
```

## 初回待機と自動再試行

最初のbuild推論要求は`ProviderHeaderTimeoutError`、300000msでtimeout。
同じsessionの自動再試行は07:34:08 JSTにupstream HTTP200へ進んだ。
待機中の実Host `/api/v1/resources`では同じ`llm:Qwen3.8-27B`をblockingとする
`held_by_other_owner`、queue position1、実GPU使用22,922,100,736Bを観測した。
同時期の8097 `/slots`はidle、保存済みprompt2059 tokens。
モデル起動前にtitle/build要求が重なった影響と推定するが、Hostの原因修正・再現試験は未実施。
診断専用mf-e2eの一時HTTP sessionは資源状態のGET後にrevokeした。
LLMは353.441秒でskill、358.560秒でcapabilitiesを実呼出した。

## 回帰確認

同一source commitで`./mf.sh test`: **1952 passed, 2 warnings / 208.81秒**。
このPRは記録のみ。これを恐竜の品質・MCP成功の証拠へ読み替えない。

## 結果

初回runはexit0、600.595秒（最初の300秒timeoutを含む）、MCP/skill計10回。
create54操作と口・歯のeditの両Jobがsucceeded。
scene `scene_9258c7732eff4374858fd3ea6fb91480`、revision `revision_60474ebb9f09455394dec47d3eb455b0`。
asset `asset_75d4beb0eaf14c36857f8daa679f1580`、GLB **135988B**、SHA-256 `74c32cb1715bf2871ce0c77c7dc5640debb1226bbd1ad83403e42d9065d953f3`。
正規grant/receiptのcommitted=true、実file・Asset metadata・provenance output hashが一致。

実Blender4.5.13 LTSでGLBを新規importし、CPU Cycles24samples/960x720で斜め・横・正面を描画。
**34 meshes / 1486 triangles**（groundを含む）。groundを除いたboundsは
[-0.6000000238418579, -1.5299999713897705, 0.0]〜[0.6000000238418579, 2.4250001907348633, 1.7799999713897705]m、前後長約3.955mで目標約3mから外れた。
親エージェントが実画像を観察し、尾が浮いて逆向き、足先が後ろ向き、箱型の胴体、歯が口に隠れる点を確認。
初回の形状品質はFAIL。LLM自身の画像観察はNOT TESTED。

検証scriptのDB指定は、初回が旧root DBでassetなし、2回目が既存空mediaforge.dbでtableなしとなりFAIL。
稼働processのMEDIA_FORGE_DATA_DIRとStore.db_pathから実DB `data/media-forge.sqlite3`へ訂正後PASS。
DBはいずれもmode=roで開き、変更していない。

同じOpenCode sessionへ上記の目視指摘を自然言語で返し、同じsceneを一度修正して
`trex-v2.glb`へ別名納品するrunを開始。座標・回転・操作は引き続きローカルLLMが決定する。
修正runもexit0、**156.502秒 / 7 tool calls**、20操作のedit Job succeeded。
revision `revision_9156adc10d1b4d4e8635ee50c7fbed3f`、asset `asset_724f6911edea4a4f9f25ea54fd642a1f`。
`trex-v2.glb` **136196B**、SHA-256 `a69e7eef3e577b03c21be2e23bb87b10a1bba19609df7a856aba173fc6100f49`。
新しいgrant/receiptと実file/metadata/provenanceのhash一致、初回GLBのhash不変を確認した。
実GLB再import/CPU3方向render成功、34 meshes / 1486 triangles。
groundを除いたboundsは[-0.6100090742111206, -1.5299999713897705, -0.0022491347044706345]〜[0.6100090742111206, 1.6250001192092896, 1.7799999713897705]m、前後長約3.155m。

目視では尾が胴体へ接続し、後方へ先細りになり、足と爪が頭方向を向く改善を確認した。
一方、胴体はまだ大きな箱状、歯は暗い口に隠れ、ティラノサウルスの体形表現は粗い。
最低zも約-0.00225mで、ごく小さい床への食い込みが残る。
**制作・修正・書出し・配置経路はPASS、造形品質はPARTIAL。高品質恐竜の完成とはしない。**
この結果をM1 authored-meshやM2以降、全GA完了に読み替えない。

## 保存と未検証

利用者が試すよう依頼した制作サンプルとして`MF3DS-Trex-20260918`を保持する。
`exports/trex.glb`（初回）、`exports/trex-v2.glb`（修正版）、
`previews/v1-*.png`と`previews/v2-*.png`（斜め・横・正面）を保存。
ユーザーに提示する実体であり、空の検証projectとして削除しない。
元scene/source assetと全revisionもMediaForge側へ保持。

推論と形状・修正recipeはQwen3.8-27Bが生成し、親エージェントは自然言語brief・目視feedbackと
検証用CPU renderだけを担当した。親が代わりに恐竜meshを作成したものではない。
LLM自身のVLM観察・自動視覚修正、rig/animation、UV/texture bake、実game engineはNOT TESTED。
初回の資源待機に対するHost修正・cold同時要求の再現試験もNOT TESTED。

run/repairのprivate runtime configは両方削除済み、所有OpenCode/inspection processは終端。
証跡はprojectの`evidence/`へまとめ、重複renderと一時scriptを含むmaintenance作業領域を回収する。
成果物・元asset・scene/history・runtimeは回収対象に含めない。
