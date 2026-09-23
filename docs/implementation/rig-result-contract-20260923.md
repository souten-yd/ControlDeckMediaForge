# 自動ボーン補修結果の本体境界

0.33.13 installed MCPで、主人公1024の既存pipelineを明示retryしたJob
job_480aa45fd5a14d148aedb0b7dfe9c3e3は3.981秒でfailed。
`scene_recipe_worker_invalid / scene recipe result differs`を観測。元model/scene/画像は保持。

原因は0.33.12 workerが全成功結果へ追加した`automatic_weight_repairs`を、
本体`SceneWorkspace._apply_recipe_worker`の許可キーへ追加していなかったこと。
worker直接実行の成功だけをこの境界の受入にしていた検証漏れ。空配列の通常recipeも影響する。

修正: 任意項目を許可し、rig.autoの対象ID、stable ID、報告件数、1〜128頂点、
成分数、距離の有限値/非負、最大距離≤上限、上限=身長×0.005を本体で検証。
旧workerの省略と新workerの空配列は互換。余分なキー/不正報告はfail-closedのまま。

実source本体→Blender4.5.13 subprocess→結果検証を、実1024モデル/同一recipeで実行。
修正前3.449374秒で同じエラーを再現、修正後3.568059秒で成功、補修14頂点/1成分を受理。
scene recipe結果は保持。これはsource実workerでありinstalled/MCP成功ではない。
証跡: maintenance/shopping-street-20260923/core-recipe-{before,after}/acceptance.json。
14回帰ケースは実子プロセスの結果を本体へ渡し、旧/空/補修ありと不正/未知項目拒否を確認。

`PYTEST_ADDOPTS=--basetemp=/tmp/mfr-test-20260923 ./mf.sh test`: 2471 passed /3 warnings /401.67秒、exit0。以後製品コード変更なし。signed installed/MCP再retry、最終商店街の全モデル/操作はNOT TESTED。
