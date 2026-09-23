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
