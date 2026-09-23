# MCP失敗時の受理済みJob参照

Status: source実HTTP/全体2512tests受入。0.33.18の配布・installed MCPはNOT TESTED。
Branch: ux1/agent-failure-job-reference、基準48c26b6。

商店街の実MCP失敗で、エラーcodeだけが返り、受理済みJobを照会できなかった。
integration-planへ先に方針を記載し、media.generateの失敗/取消/cleanup timeoutで
同一Job IDと確定済みstatusを返す。wait deadlineは既存のJob IDだけを維持し、
終端を推測しない。未受理にはIDを作らない。HTTP errorと成功結果の区別、元Job/Assetを保持する。
HostにMedia固有の処理を入れず、汎用の参照保持をControlDeck別PRで対応する。

## 実行証拠

関連testsで、unsupported packの502/failed/同一Job ID、成功後cleanup timeoutの
504/job_cleanup_timeout/succeeded/同一Job ID、未受理422/追加Job0を検証。
元worker例外のpathは出さない。既存host executionテストも通過。

`maintenance/shopping-street-20260923/failure-context-source/probe.py`を実行。
独立した実Uvicornの本体へHTTPでpack要求を送り、502のIDで同一failed Jobを取得できた。
Host transportは明示fake、unsupported profileのためGPU/画像/モデル取得0。
同scriptでは独立Host router→Add-on HTTP→stdio bridgeを動かし、失敗3/成功1を
隔離Host DBへ保存、両Job IDの区別、内部path除外、実呼出4回/再送0を確認した。
Host DB/user/keyは試験用であり、稼働Host認証を読み書きしていない。
report.json、process logsを保持。所有サービスは終端、fixture tokenは削除済み。

最終`PYTEST_ADDOPTS=--basetemp=/tmp/mfs18-final ./mf.sh test`は
2512 passed/3warnings/418.24秒、exit0。以後product code変更なし。これは新しいモデル/runtimeを採用する変更ではない。

残件: 0.33.18の署名公開/通常導入、汎用Host修正のmerge/適用、
実OpenCode/Qwen/MCPで受理後失敗を1回起こし、返されたIDで追跡できること。
複数面生成の比較/UI/採用も別途未完了。追加モデル取得は行わない。
