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


## 0.33.14 signed release and installed MCP acceptance

PR637 merged at82a69c796355c070567aae16b59dda07c3b74b22. Exact signed bundle:
38,058,432 bytes; SHA2565567fb461472557e089b0e47020a9215450c7ca84922da16ea9ccded0e290f17.
Release was downloaded again and checked for signature, source/file hashes, and
tamper rejection. Fresh packaged service reported setup_required in0.865878427s.
Normal ControlDeck feature update/restart installed0.33.14, PID135776, healthy in
1.034162622s. All1573 pre-update Asset metadata records and representative three
Asset HTTP hashes were preserved; served frontend and capability matrix matched.
No active MediaForge Job/session was interrupted by the update.

Real OpenCode/Qwen/MCP Job0f6de426a73c completed. Hero rig retry Job
job_9f7a3f009a9b43d5a0ced08fce4fb6c7 succeeded and published revision
revision_818f77d57af046b984b13d0876085f7f. Preview GLB
asset_babcc6eee39f4829b368bf7fa6c03de4:3,602,564 bytes,
SHA25614e5b8c27d47d97108c0056e6d573fe5c1dac7e0e1203d945f56a5553b96b0db.
The normal grant/pack delivery to exports/player-1024-rigged.glb had identical
bytes/SHA, independently checked against the immutable Asset metadata.
The two NPC rig failures are independent shape-measurement failures; they are
recorded, with no automatic retry or false animation success. This validates the
worker-result contract repair, not natural animation or the whole street.
Evidence: maintenance/release-0.33.14-20260923 and shopping-street-20260923.
