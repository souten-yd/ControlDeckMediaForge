# OpenCodeの継続と明示停止の受入（2026-09-23）

利用者の「明示終了まで継続してよい」「Codexなどからは止められるよね」を適用する。
Host寿命に連動する自動停止案を取り下げ、継続中の実行を観測し、対象だけを明示停止する。
Codexへの停止依頼・自身で起動した検証のcleanupを含み、画面の手動操作に限定しない。
Host Job/unitの責務のため汎用Host別PR。Media固有のHost経路や別Jobs基盤は追加しない。

Host PR340/31e3420: 保存opencode.run/interruptedだけ実systemdを照合。
running/状態不明/結果未回収を区別し、owner/RBAC付きcancelで対象を実停止してからcanceled保存。
OpenCode画面の「バックグラウンドの実行」から一覧と停止へ到達する。TUI/providerの寿命は変更なし。
source実systemd/隔離DBの3heartbeat unit、Host再起動越し継続とPC1280/320px/APIの個別停止を確認。
全1171passed/2skipped/1warning107.27秒、frontend build24.60秒。
Job/unit/lease空きを確認後通常deck.shでroot mainを更新、PID456446/health ok。
通常operator認証のPC1280/320pxで実履歴25件、停止ボタン1個、横overflow/page error0。
旧Jobe67c69a17071はinterrupted/external_result_unavailable、過去の失敗は保持。
これは閲覧のみで、実OpenCodeの再起動越し継続やinstalled停止実行の成功とはしない。

同じタイトルのJobが複数あるため、Host別追補で開始時刻/実行ID/確認文を追加。
同名3unitのPC/320px個別停止はsourceで確認。実OpenCodeは継続中のまま触らず受入する。

停止中Qwen3.8-27Bから通常OpenCode/API/Gatewayを使う読み取り限定Job2291014cbcf0を実行。
session ses_f32fcf23cffecM4vaj4Dk0iWTg、77.058秒/succeeded。
READMEとacceptance-summaryのread2回だけ、商店街の起動方法/モバイル操作/未検証点を3行返した。
独立OpenCode DBと保存Host結果・Broker全3要求を照合。予約cold30,979,147,560B/後続0B/0B、
全granted/released、expired/retry0。shell/MCP/編集/別agent呼出し/追加モデルDL0、project Git clean。
lock前の到着時刻を採取していないので、以前の2.021286秒差の同時cold条件と同一とは言わない。

証跡managed maintenance/shopping-street-20260923下:
- opencode-recovery-source-4: report/browser JSON、PC/320 PNG（初回fixture失敗履歴はsource〜source-3に保持）
- opencode-recovery-installed: installed/browser/cold-result/cold-independent JSON、cold-resource-samples.jsonl
- opencode-run-identification-source: 同名処理のPC/320px/HTTP停止

既存llama-runtime.json/Pixal採用receiptは更新前後hash一致。MF0.33.18/既存1枚生成/商店街7GLBは不変。
物理携帯・実OpenCode継続中のHost再起動・失われたstdoutの回収はNOT TESTED。
3D複数面は別draft641で2/3/4面評価、1面比較/人物/非対称/生成視点/取消/installed/MCP/UI未受入。
今回MFは文書のみ。直近製品gate2512passed/3warnings418.24秒の後に製品codeを変更していない。

## 実installed OpenCodeの明示停止（追記）

Host PR341/e34c7caを通常導入、PID486604/healthy。Job/unit/lease空きを確認後の更新。
自身で起動した実OpenCode/Qwen Jobcfce488f01aa、unit PID487050を対象に確認。
PC1280/320pxに同じ開始時刻/実行IDを表示し、320pxの停止確認から当該IDだけを終了。
通常Jobs=canceled、unit=inactive/MainPID0、active lease0、商店街Git clean。
横overflow0/button44px/page error0。モデル追加取得0、他実行への停止0。
証跡opencode-identification-installed/{installed,stop,stop-browser}.json/PC・320 PNG。
この明示停止は実OpenCodeの受入。実推論継続中のHost再起動を意図的に起こす検証は未実施。
Host最終製品gate1171passed/2skipped/1warning106.87秒、frontend build22.08秒。
