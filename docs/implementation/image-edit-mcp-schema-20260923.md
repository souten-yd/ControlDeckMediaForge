# 単一参照編集のMCPスキーマ評価

## 実OpenCodeで観測した失敗

通常ログインからOpenCode 1.18.30/Qwen3.8-27Bを起動し、保存済み人物正面の
背面候補を既存image.editで1件だけ作るよう依頼した。
Host Job `50715bdc703e`、session `ses_f323df276ffeTbroqFwprYEwdn`、208.725451秒。
OpenCode自体はsucceededだが、MCPのmedia.generateは同じ不正引数で3回とも
`HTTP422/schema_validation_failed/constraints.origin_notes`。
1回のみ・再送禁止という指示に反して2回再送した事実も保持し、成功扱いしない。

依頼はwidth/height1024、seed42、reference、strict_edit=false、透過必須のasset_brief。
実際の3callはseed/asset_briefを欠き、無関係なscale_m=1、origin_notes=""、
compile_optionsを追加していた。3入力は全く同一。
受付前の拒否なのでMediaForge Job追加0、生成画像0。元Asset全metadata/実SHAとprojectを保持。
Host PID674922不変、active lease0。停止を試みる前に実Jobが終端しており、
プロセスsignal/Job cancelの実行は0。他のOpenCodeへは操作していない。

## 契約で確認した不整合と修正候補

公開constraintsは自由形式で、JSON Schema上は未知キーを許可するが、
additionalPropertiesを明示せず、既存seedもpropertiesへ掲載していなかった。
llama.cppは未指定additionalPropertiesをfalseとして扱うと
[公式文書](https://github.com/ggml-org/llama.cpp/blob/b10917/grammars/README.md#json-schemas--gbnf)
に明記されている。
実ランタイムと同じb10917のPython converterを固定し、Hostと同じ長さ制約除去をした
旧schemaを変換するとseedの規則と追加キー規則が両方存在しないことを再現した。
これは独立した契約不整合の証拠であり、今回の3callの全挙動が文法だけに起因すると
断定する証拠ではない。実OpenCode/LLM経由での修正後再確認を必須とする。

既存seedをintegerとして掲載し、additionalProperties=trueを明示する。
画像設定をwidth/height/seed/edit_mode/strict_edit/asset_briefの順に掲載し、
pack専用項目には用途を付記。不要な任意項目を空文字や既定値で埋めないよう説明する。
既存tool名/endpoint/必須fieldは維持。packの空origin_notesは引き続き拒否する。
実行コード、モデル、権限、broker、Hostの検証は変更しない。

## Source受入

対象23testsを通過。元の編集JSON、透過設定、seed、自由形式のguidance_scaleを受理し、
packの不正metadataを拒否する契約を検査した。
隔離dataの実uvicorn/HTTPで配信schemaとsourceの一致、元JSONの妥当性を確認。
この隔離coreはsetup_requiredで、画像生成をしたものではない。
固定converterの旧grammar22,880Bにseed/追加キー規則なし、候補26,317Bに両方あり。
初回private検査はprimitiveの別名規則を探して失敗。実キーのkv規則へ訂正して確認した。
第三者モデルの取得0。調査で取得したのは固定converterのsource35,277Bのみ。

初回全体は2558pass/1fail/3warnings/364.23秒。
参照セットfieldとcanonical schemaの厳密一致検査が追加説明により失敗した。
共通fieldは元定義を保持し、pack項目の用途はconstraints全体の説明へ集約。
対象の契約/参照セット56testsを通過。0.33.21の最終`./mf.sh test`は
2559passed/3warnings/398.92秒、exit0。以後製品code変更なし。
修正候補の署名配布/installed MCP/背面生成/画質はNOT TESTED。
透過やseedの存在だけで、背面の形状一致や自動3Dへの採用を認めない。
次は全体gate、PR、署名配布と通常更新後、同じ実OpenCode/MCP要求の受付と実出力を検証する。

private証跡はmaintenance/multiview-20260923/mcp-back-candidateの
result/tool-parts/independent/source-contract JSON、旧/候補GBNF、full-test.log。

## 0.33.21の配布と通常更新

PR657、merge `7db182ad8ebf8634699fe3f7be0dce997099a280` のclean checkoutから
既存build環境でbundleを生成し、既存publisher鍵で署名した。
tar.gzは38,092,882B、SHA256
`fe401ce76d5fc12d34e03822f56d544b193a7fe509a92d44bed30485b6684015`。
trusted catalog公開鍵でmanifest/signature/size/hashを検証、改ざんmanifestを拒否。
archive6項目、embedded244項目、frontend/対象schema/workerのsource一致を確認。
model/venv/DB/秘密鍵の混入なし。新規model取得0。

展開した配布物を空のmanaged directoryで実起動し、setup_requiredと3D unavailable、
修正schemaの配信、pack既定値と不正要求の拒否を確認（0.877秒）。
これは画像生成の受入ではない。GitHub Release v0.33.21の4assetを再取得し、同じ検証を通過。
GPU lease/OpenCode unit/MediaForge Job/setup/Blender sessionがidleの状態でDBをbackupし、
通常の`deck.sh feature update media-forge`を実行した。
current0.33.21/PID711535/healthy、Host PID674922/NRestarts0。
旧1593 Assetの全metadataと代表3content SHA、runtime registry全JSON、
単視点/複数面を含むimage_to_3d capability、配信static filesとschemaを照合した。
4方向の既存入力も実contentを再取得し、元fixtureとの画素一致と4枚相異を再確認。

private証跡: maintenance/release-0.33.21-20260923のbuild/update log、
artifacts/downloadedのverification.json、clean-smoke.json、post-update-check.json。
同一条件の実OpenCode/MCP要求による再受入は別に記録する。

## installed OpenCode/MCPの再受入と候補品質

通常認証から同じ背面候補の依頼を送信。OpenCode Job `3c589f2cfcec`、
session `ses_f3221e6f0ffeyqMVHep2QYu1XE`、170.563235秒でsucceeded。
実DBのtool partはmedia.generate 1回、completed、再送/別tool/子agent/停止操作0。
Host側MCP Job `d0bf3b8f6dad`、MF `job_230f25e4c7ce4aa78d089b2032e940ab`もsucceeded。
MCP呼出し54.256秒、MF保存時刻差53.990640秒。

実引数はseed42、reference、strict_edit=false、1024角、alpha requiredを保持し、
前回のorigin_notes/scale_m/compile_options混入はない。
一方、asset_brief.aspect_intent=squareを落とし、consistency_group=""とhard_constraints=[]を
追加した。brief以外の入力は依頼と一致するが、JSONの完全転記は未達。
モデルの最終説明も実引数の正確な記録ではないため、受入根拠には使わない。
width/height明示により今回は出力の正方形が保たれた。あらゆる任意設定の遵守は未受入。

成果物 `asset_2d4d8458e4464731ac93f1b7e945a73f`、1024×1024 RGBA、992,703B、
SHA256 `e016027e69c29e569e6698d52e0f1843903b46d672821c49b7e1f527f6fa304e`。
既存FLUX.2-klein-4B/diffusers0.40.0、text encoder/transformer int8、cpu_offload、seed42。
元正面Assetを親に持ち、来歴の参照SHA/出力SHAを実bytesと照合。元metadata/SHAと商店街projectは不変。
Host PID674922不変。LLM3件/画像1件のleaseはすべてreleased、active0。
独立検査helperは初回にMF Job IDをHost leaseのJob IDと誤照合して失敗した。
実MCP応答に記録されたHost Job IDとownerを照合するよう訂正し、再読取で確認した。
新規model取得0、再生成0。

目視では顔のない背面・1人・1バッグを確認したが、バッグは画面右に残り、
既知背面の画面左とは異なる。持つ手が反転し、体形/髪の結び位置にも差がある。
この候補はLibraryへ保存するが、複数面3Dには採用しない。
全画素の81.899452%がalpha0、四隅alpha0、前景boundsは[317,73,810,972]。
通常Host LibraryのPC1280/タッチ320pxで、この候補と既存4面GLBを開閉。
透明背景での表示、GLBの実回転、opaque origin、overflow0/pageerror0を確認した。
物理スマホ、任意写真の方向/形状整合、自動候補の比較・選択UIと自動3DはNOT TESTED。
MCP受付の改善は実確認できたが、自動方向画像の品質完成や完全な指示遵守とはしない。

private証跡はmaintenance/multiview-20260923/mcp-back-candidate-0.33.21の
request/result/tool-parts-independent/independent/visual-review JSON、画像、resource samples。
表示の証跡はrelease-0.33.21-20260923/host-installed/library.jsonと実画面PNG。
