# MCP失敗時の受理済みJob参照

Status: 0.33.18署名公開・通常導入、Host PR337適用、実OpenCode/Qwen/MCP失敗参照を受入。
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

## 署名公開・通常導入

PR647、merge c392021b1795547e6c97d5a33586eed78c23535aを固定し、既存鍵で署名。
v0.33.18公開bundleは38,065,263B、SHA256
68151fcef69b080a46df49e0cd332d0c55ad613b9cc420a8b8038a06d0d0daac。
公開物を再取得し、署名/信頼鍵/改ざん拒否、6archive/244embedded entryとsource一致を検査。
重み/venv/data/秘密値を含まない。新規dataで実起動0.880045秒、未導入runtimeをunavailableとし、
pack形式省略はZIP、不正PNG/countは422/追加Job0。実installedの代替試験ではない。

active Job/scene/WebBlender/runtime/model操作0でDBを保存し、通常feature update。
current0.33.18/PID393256/healthy、既存1585 Asset metadata、代表3content SHA、
全runtime-state JSON、3D capability、配信frontendを保持。
汎用Host PR337/786e76cを別途mainへ統合し、全Host Job/実OpenCode unit/active lease0を確認後、
DBを保存して通常deck.shで再起動。PID394222/health ok、frontendとllama-runtime設定を保持。
モデル取得0。証跡maintenance/release-0.33.18-20260923。

## 実OpenCode/Qwen/MCPでの失敗追跡

通常operator sessionのHost HTTPから指定Qwen3.8-27Bで開始したJob ace32c6b7a89はsucceeded。
session ses_f33364de4ffeXPSfRswmoIJ4Eyで公開media.generateを1回だけ実行。
既存cafe asset_47380d9455c64d268ddf5f89033f6f3bを意図的にprofile=unsupportedでpack要求した。
OpenCode上のtool状態はerror、返却codeはunsupported_pack_profile。
Host job_id=94bde79e1799、upstream_job_id=job_0fe3e640c9c341b0a2c3ded01c01402b、
upstream_status=failedを実error本文で確認。失敗を処理できたOpenCode runの成功と、
意図的に失敗したHost/MF Jobの状態を区別する。

failure-reference-independent.pyで、同じoperatorの通常GET /api/v1/jobs/{Host ID}と
MFのread-only Job APIを照合。Host保存result.errorのcode/両ID/status一致、両Job failed、
MF asset_ids=[]、元Asset metadata/content SHA不変、project Git clean。
再送0、生成/ダウンロードtool call0、成功Assetの捏造0。
media.job.statusは現行scene Job向けなのでこのpackには使っていない。
通常packの同MCP status照会はNOT TESTEDであり、今回の受入は通常Host Jobs HTTPの追跡。
検査script初回はPYTHONPATH不足、次は保存入力の既定grant_id=nullを想定せず失敗。
実公開応答を確認して検査側を修正し、生成を再送せず同一Jobで検査を通した。

## 更新後の通常Hostブラウザ

host-street-acceptance.pyを新証跡ディレクトリで実行し、元の受入証跡を保持。
PC1280px、mobile390/320px（実iframe373/303px）の通常Project Labで、7実モデル/8店舗/
6歩行者、15配置すべての画像、keyboard移動/同時touch移動と視点操作/help/再読込を確認。
全人物足底Y=.062m、横overflow0、page errors/console warning/error各0。
実PCのAMD内蔵GPU/Chromeは300frames/5.0024秒=59.971214fps、p95 16.8ms。
320/1280px screenshotを目視し、三人称人物と画像付き店舗を確認。物理スマホの速度はNOT TESTED。

MF2512tests、Host1150passed/2skippedの最終source gate後に製品コード変更なし。
この追記は実測記録のみ。複数面生成の比較/UI/採用は別途未完了。追加モデル取得は行わない。
