# Web Blenderの終了ボタン

稼働中はMediaForgeの全画面共通の上部に「Web Blenderを終了」が出る。
対象名を確認し「新しい版として保存して終了」か「変更を破棄して終了」を選ぶ。
準備中は「起動を取り消す」。表示だけ閉じる操作は変更しない。

確認対象をsession IDに固定し、選択中の別sceneを誤って終了しない。
終了要求中/保存中/停止中の重複送信を拒否し、要求失敗は明示して再試行できる。
API/DB/モデル/Hostの変更はなく、既存owner付きprivate session APIを使用する。

## 変更前と実行記録

本番0.33.7のDB読取とsystemd/psでactive session0、Blender/Xtigervnc0を確認。
直前の `blendersession_57732640138e4b7285072df5493ab8b5` は
`blender_session_disconnected_timeout` / interrupted。
`working_fb7a3b96f0a14e70b356961b2851960d` はrecoveryとして残っていた。
既に終了済みなのでkill/破棄操作は行わなかった。

証跡: feature-data/media-forge/maintenance/web-blender-exit-20260922。

- `ui.mjs` / `source-ui.json`: Chrome1280/320px touch。全4画面で入口あり、簡易詳細、
  日英、取消、破棄説明、44px、横overflow0/page error0。
  Session応答だけ制御し、要求失敗→再試行、二重送信拒否、古い確認から別sessionを
  終了しないこと、queued/preparing/startingの取消を確認。実API終了とは分ける。
- `real-session.mjs` / `real-session.json`: source standalone実API/Blender4.5.13。
  fixture `scene_601ac9af9d764ed9b13df657902f9056` のみ使用。
  320pxでLibraryへ移動し、RFBを開かず上部ボタンから終了。
  stopはsession b1aa522.../0.265秒/stopped/saved=false、2版維持。
  saveはsession 8b409768.../4.614秒/stopped/saved=true、2→3版。
  両systemd unitはinactive。元の正式利用者sceneは編集していない。
- `PYTEST_ADDOPTS='--basetemp=/data1tb/mf-exit-full' ./mf.sh test`:
  2413 passed /3 warnings /154.72秒。frontend160件/セッションを含むfocused177件も通過。
  最後に終了中文言を「変更を破棄」から保存にも正しい「Web Blenderを終了」へ統一し、
  frontend160件/node構文/git diffを再確認した。

## 0.33.8の公開と適用

PR625を通常mergeし、source `2a737f8ddfde5be5d9ce4fa13f78702eea66c097` から署名公開。
release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/0.33.8 。
artifactは38,036,421B、SHA256は
`80eb27e8b915275ded775d1e4ccfb18d0e57113bb7cff2179f7c574545f5bcc4`。
公開物を再取得し、publisher署名/改ざん拒否/archive6項目/embedded241項目と
frontend/対象worker bytes一致を照合。fresh managed dirsの起動は0.867882秒、
runtime未導入のためsetup_required/3D unavailableを維持した。
証跡はmaintenance/release-0.33.8-20260922。

本番の `job_6f6e01f5e90f4c72a261205c2e9c81b1` の3D生成がsucceededになるまで待ち、
Job/session0で `deck.sh feature update media-forge` を実行した。取消やkillはしていない。
currentはversions/0.33.8、PID3841988でhealthy。1543 Asset metadata保持、代表3 Assetの
HTTP SHAとserved frontend bytes一致、3D capability不変を確認。
Job/session0で通常再起動し0.828258秒でhealthy、PID3844880。再度同じ照合を通過。
installed standalone Chrome1280/320pxで上部終了ボタン/日英/44px/二重要求防止を確認。
session応答を制御したUI受入であり、本番user owner sessionの実終了操作ではない。
PCからの別件3D表示エラーを受け、通常Chrome/実AMD GPUでも最新3素材の描画を確認したが、
Hostログ13:29:17 UTCにはthree-viewer.jsの401があった。Cookieなしのmodule読込は別sliceで修正中。
専用operator session.jsonは不在。認証付きinstalled Host browserは再ログイン待ちで
NOT TESTED。認証を偽装せず、確認済みのsource実Blenderと区別する。
実スマホ本体・新規画像推論・fresh GPU構築・rollbackは今回NOT TESTED。
