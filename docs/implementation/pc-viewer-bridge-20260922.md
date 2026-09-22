# PCの3Dビューア読み込み認証 — 0.33.9

## 失敗の切り分け

利用者のPC表示不可を受け、Host journalから2026-09-22 13:29:17 UTCの
`GET /addon-frame/media-forge/static/three-viewer.js` HTTP401を確認した。
直後のbridge/callには403もある。これはGLB/textureの検証より前のmodule取得である。
実ユーザーの当該ブラウザのCookie設定やURLは未確認であり、特定のブラウザ設定を断定しない。

installed0.33.7の4 GLBはmodel/open HTTP200、EXT_texture_webp検証・browser memory bound通過。
3 GLB（asset_8606dc10... / asset_4fc69639... / asset_148ccced...）はheadlessの通常/SwiftShaderと、
このPCの通常Chrome・実AMD GPUで描画できた。実GPUはradeonsi raphael_mendocino LLVM20.1.2、
三角形277232 /991938 /131508。実GPUの読込は1.264 /3.486 /0.469秒。
これらはstandalone経路であり、当該利用者のHost画面の成功とは扱わない。

## 修正

opaque iframe内のviewer bundle取得は既存Hostの`X-Control-Deck-Bridge-Session`へ
現在のnonceを渡す。Cookieを送らず、固定Add-on URLのGETだけを許しredirectを拒否する。
JS MIMEと2 MiB以内を確認し、一時Blob moduleで評価後にURLを解放する。
nonceをURLやログへ出さない。Hostコード・権限・session発行・GLB/WebP検証の変更はない。

module読込をGLB転送の前に待ち、認証/通信の失敗は専用の日英案内へ分ける。
先行Promiseの拒否がGLB転送中に未処理になる経路もなくす。失敗したmodule cacheは再試行可能。
standaloneは従来の同一origin moduleを使う。0.33.8のWeb Blender終了操作も含む。

## 実行と観測

証跡: feature-data/media-forge/maintenance/pc-viewer-20260922。

- `model-open.json` / `probe.json` / `headed-probe.json`: 上記installed APIと描画結果。
  最初の連続開閉probeはdialog close eventを待たず次のopenと競合したため、close完了後の再実行を記録。
- `host-http-status.json`: Hostログから時刻/path/statusだけ抽出。Cookie/token値は含めない。
- `opaque-module.mjs` / `opaque-module.json`: fake scoped HTTP fixtureを使う実Chrome/opaque iframe。
  Cookie0で旧版は401、修正版はBridge headerで200。1440/320pxで実WebP GLBの131508三角形を描画。
  親DOMへのアクセスは拒否されたまま。Hostの実sessionを生成・偽装した試験ではない。
- `lan-module.mjs` / `lan/opaque-module.json`: 実LAN IPv4の平文HTTP、isSecureContext=false。
  非公開の利用者素材はLANへ配信せず、合成triangle fixtureだけで同じ旧版失敗/修正版成功を確認。
  両幅で親DOM拒否を維持。試験用server/browserは終了済み。
- 上記2つで401拒否→再試行、302拒否→再試行。redirect先への要求0、URL nonce0、Cookie0。
- `error-ui.json`: source UIの320pxでmodule auth/load拒否を注入し日英案内を確認。
  認証失敗時のassets.model.open/bytes要求0。単なる無効GLBエラーとして表示しない。
- Nodeによる実loader関数の回帰: 欠落nonce、401/403、共有Promise、再試行、Blob解放、
  script失敗、通信失敗、非JS/サイズ上限、standalone維持を確認。
- `PYTEST_ADDOPTS='--basetemp=/data1tb/mf-viewer-full' ./mf.sh test`:
  **2414 passed /3 warnings /161.33秒**。focused167件、最後の文言調整後frontend/loader161件、
  node構文/git diffも通過。

## 未実施と反映

PR627を通常mergeし、source `f1b4ae5ac1feeae0e4d74a7d59b83a53dd2f8743` から署名公開。
release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/0.33.9 。
38,037,460B、SHA256 `773c0616c66f3694b69eb1b3fb774b60dbfababcf72385bb4f417279ad6914aa`。
公開物の再取得後も署名/改ざん拒否、archive6/embedded241、frontend/対象worker bytes照合通過。
fresh managed dirsは0.867048秒で起動、runtime未導入のsetup_required/3D unavailableを維持。

active Job/session0で `deck.sh feature update media-forge` を実行し、currentはversions/0.33.9。
更新後PID3865779/healthy、1543 Asset metadata保持、代表3 Asset HTTP SHA/served frontend一致、
3D capability不変を確認。通常再起動後PID3866679/healthy（0.822935秒）で同じ照合を通過。
再起動後のinstalled standalone/通常Chrome/実AMD GPUで上記3 GLBが1.224 /3.475 /0.469秒で描画、
page/console error0。active Job/session0、Web Blender process0、元working copyのrecovery保持。

証跡: maintenance/release-0.33.9-20260922 のverification/installed/restarted-check、
headed-probe、final-core-state。0.33.8/0.33.9の検証済み重複tar4個（152,147,762B）と
今回のpytest専用一時directoryは回収。署名manifest/checksum/verificationと公開release、
正式installed/rollback版は保持し、利用者素材は削除しない。

配布とローカル適用は完了。
専用operator sessionが不在で、利用者へ通常loginを依頼済み。
認証付きinstalled Host browser、利用者が報告した当該PC/browserでの再確認はNOT TESTED。
実スマホ本体、新規AI推論、fresh GPU構築、rollbackも今回NOT TESTED。
