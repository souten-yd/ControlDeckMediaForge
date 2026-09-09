# v0.28.50 — Web Blenderの無操作判定を修正

画面更新通信や再接続だけで無操作の期限が延びる問題を修正します。
固定noVNC/XvncのRFB接続で、完全なキーボード・ポインター入力だけを操作として数えます。
画面要求、handshake、clipboard、resize等の制御通信は操作として数えません。
再接続では最終入力時刻を保ち、core再起動時は永続時刻から期限を再構成します。
未知の通信形式は推測せず接続を拒否します。

## 検証と配布状態

PR #378で実装。実source Blender4.5.9で24回の画面更新要求による時刻不変、
実マウス入力による更新、再接続後の時刻保持を確認しました。
既定2分の自動保存後、所有Blender子のcrashから同じhashの2 meshesを回収し、
元の正式版と旧ファイルを保持しました。source受入は128.123秒です。
実装PRの全テストは1337 passed（既知warning2）。
署名公開・公開4ファイル再取得・実Hostのtrusted publisher検証を確認しました。
初回更新は連続する生成Jobを検出してidle gateで中止しました。
その後Jobs0を確認し、標準更新で0.28.50/実HTTP healthyを確認しました。
DB全テーブルとBlender登録を保持し、ControlDeck本体のプロセスは変更していません。
既定30分の無操作終了の実機受入は未検証です。
最新の配布状態と実測は[実装状況](implementation-status.md)へ記録します。

## 互換性

DB migration、公開schema/tool名、capabilityの追加はありません。
固定済みのブラウザ操作packを使います。Blender runtimeや個人設定を変更しません。
更新/rollback前にGUIを保存・終了し、稼働Jobがないことを確認してください。
旧版へ戻すと旧版の無操作判定へ戻ります。制作物・旧revisionは保持します。
全3D Studioやボーン・歩行・有機的ウェイト・ゲーム用アセット機能の完成を宣言する版ではありません。
