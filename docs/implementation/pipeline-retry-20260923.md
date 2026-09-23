# 失敗した制作工程だけを明示再試行

Status: 0.33.13 merged/released/installed / 実OpenCode MCP再開中。

商店街制作で、1024主人公はmodel完了後のrigでscene_recipe_failed、
本屋と歩行者2種はmodelのresource_wait_timeoutに到達した。既存pipeline.statusの
status/approve/cancelには失敗段を再試行する操作がなく、成功したモデルを保持したまま
製品修正後のrigを同じMCP pipelineで再開できなかった。

base-planのG9へ先に設計を追記。action=retryとexpected_job_idを追加し、
対象owner/失敗pipeline/現在の失敗Job/実Jobのfailedまたはcanceledを検査する。
同じ成功済みrevisionとrequestを保持。失敗履歴は8回まで。旧Job IDで二重送信しても
新しい試行を再実行しない。失敗結果不明、Jobなし、成功Jobの結果欠落は再照合が必要。
dispatch前に履歴とJob不明状態を永続化し、取消・例外・再起動後のpollで自動再送しない。
MCP/通常workspace transportの同じ契約を使い、別のJob基盤やHost変更は作らない。

source確認:

- 既存pipeline試験と新規の再試行/履歴/元model保持/確認待ち/同時・古い再送/owner/
  実Job状態/8回上限/dispatch例外・取消・再起動・Job欠落の試験を通過。
- 実source uvicornへ通常HTTP POST。Host broker/画像workerだけ明示fakeの専用fixture。
  resource拒否でJob failed→明示retryで別Job succeeded→次modelはawaiting_approval。
  元失敗Job保持、他actor404、古いretry409、後段Job未作成を確認。
- 証跡maintenance/shopping-street-20260923/retry-http.jsonとretry-http-server.log。
  source processは停止し、そのfixture dataは一時directoryから回収済み。
- node --check frontend/app.js / git diff --check通過。新しい画面ボタンは追加していない。

NOT TESTED: 署名installedでの実OpenCode/Qwen/MCP再開、物理スマホ。
resource_wait_timeoutの発生自体を解消したとは扱わない。再開は1件ずつ行う。
別件のMCP502で生成Job IDが失われる問題とHost cold start実再受入は継続課題。

全体gate: `PYTEST_ADDOPTS=--basetemp=/tmp/mfp-test-20260923 ./mf.sh test`
2454 passed /3 skipped /3 warnings /353.97秒。skipは当初build venv参照を置かなかった
署名test3件だけ。MediaForge専用build venvを接続後、該当tests/test_release_signing.pyは
3 passed /.23秒。全2457件を実行して通過した。製品コードや期限は変更していない。

0.33.12依存は既にPR634/635でmerge・署名公開・ローカル導入済み。実PID78171/healthy。
このsliceは0.33.13として同じ通常release手順で適用し、元failed pipelineを実MCPで再開する。

## 0.33.13公開とローカル適用

PR636、source64010fd5ad8920702c9fbad51bb1483a8d174c57を署名公開。
公開物再取得、署名/改ざん拒否、6tar entries/243embedded entries、worker/frontend一致を検証。
bundle38,058,814B、SHA256340cdbb6af508199c55d24de687da099af91bb3d6a8b2e1c57558e1901ad5e86。
新規data package起動.871291秒、Blenderなしのunavailable維持。

active MF Job/session0で通常deck.sh feature update media-forge、再起動。
current0.33.13/実PID91239/healthy .824347秒、更新前1567Asset metadata保持、代表3HTTP SHA/
served frontend一致、3D capability不変。実配信schemaにretry/expected_job_idを確認。
証跡release-0.33.13-20260923。WebのみのOpenCode Jobは生成/Blenderを呼ばず継続した。

同じ元failed pipelineをretryする実OpenCode/Qwen3.8-27B Host Job718d8c07704dを開始。
今回は主人公rigとカフェ/花屋exportのCPU工程のみ。GPU再生成はWeb実装終了後に1件ずつ。
結果/実MCP受入はまだNOT TESTED。元pipelineや素材を手で書き換えて再開していない。

また、通常認証Host Libraryの主人公第4版を1280/320pxで実再生/停止した。
12bones/22122tris/1clip、320px overflow0、origin null、page errors0。
証跡shopping-street-20260923/host-walk-confirm.json。物理電話/ゲーム移動時の接地は未受入。
