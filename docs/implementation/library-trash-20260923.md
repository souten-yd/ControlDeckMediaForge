# Libraryの個別削除・ごみ箱・完全削除 — 0.33.10

## 対象と動作

画像、材質画像、GLBの版を個別にごみ箱へ移動・復元・完全削除する。
Sceneに属するAssetを選んだ場合は、その版のBlender/GLBだけを対として確認する。
他の版や入力画像まで連鎖削除しない。版一覧の「この版を削除」からも操作できる。
現行版を外すと残った最新の版へ切り替わり、全版を外すと通常一覧から消える。
ライブラリ→ごみ箱→「完全削除」または「ごみ箱を空にする」。320pxでも同じ操作を提供する。

ごみ箱は実ファイルを保持する。完全削除はAsset本体・provenance sidecar・thumbnailをunlinkし、
不変の来歴と参照を説明するDB上の記録だけを残す。作成済みGLB/Blender内の画像は残る。
材質依存画像は残す版のexternal_images=0の検証を要する。ファイル削除失敗を成功とせず、
cleanup_pendingを永続化し再試行可能にする。起動時も確認済み削除だけを再試行し、残件数を警告する。

owner、実行中Job/作業コピー/session、確認対象のfingerprint、symlink脱出を検査する。
選択は100件、全ごみ箱は5,000件が上限。全体削除は未読ページも対象とし、別ownerの版を除外する。
既存のpublic必須fieldやHostは変更しない。private workspace HTTP/WSを同じdomainへ接続する。
意図的に消した過去入力と破損を区別し、残った版の復元・材質採用・再編集・backupを維持する。
backupは保持した版だけのsnapshotとして連番を付け、元のcanonical履歴は変更しない。

旧版バイナリは削除記録を理解しない。完全削除後はバイナリだけのrollbackで元へ戻せると扱わず、
削除前のDBとファイル両方のbackupが必要。リリース時に正式利用者Assetを試験削除しない。

## 実測

証跡: `feature-data/media-forge/maintenance/library-trash-20260923/`。
試験は本番とは別のdata-v2に合成立方体と16×16画像を作成した。

- `PYTHONPATH=backend:. .venv/bin/python <evidence>/real.py`: 実Blender4.5.13で2.290533秒。
  材質画像完全削除後に実ファイル不在、残GLB SHA不変、埋め込み画像RGBA=(10,120,240,255)。
  別材質へ変更後の旧版復元、入力GLB削除後のworking copy保存、backup出力も成功。
  SHA256: 133e33b6d75dbddb4298501a5bc2a61cf759395a4fa08ccde49a5e6bc0299b64。
- `node <evidence>/browser.mjs`: 実HTTP/source Chrome、1280/320px touchで取消、画像のごみ箱/
  復元/完全削除、1版のpair完全削除、残った版の12三角形と青い画像の描画、日英表示。
  mutation応答の差し替えなし。ボタン46px、横overflow0、page error0。
- `node <evidence>/extra.mjs`: 320px、3D「保存した版」から現行版削除、全版削除後404、
  「ごみ箱を空にする」取消→確定2件、未選択入力GLB200、二重送信なし。
  preview通信だけを1回abortしたUI試験で案内と再試行も確認。横overflow0/page error0。
- 最終ソースで専用14 test、署名3 test通過。単体テストはowner/古い確認/稼働中/埋め込み不足/
  unlink失敗の永続再試行/境界外symlink/backup/private HTTP+WS/全ごみ箱対象変更を含む。
- harnessの初回失敗は同期restoreへのawait、viewerの旧selector、scene操作前の画面遷移、
  scene削除後status期待値422（正しくは404）。新fixture/正しいselectorで再実行し上記を実測。
  製品の失敗をテスト用応答で隠したものではない。

全体gate: `PYTEST_ADDOPTS='--basetemp=/data1tb/mf-trash-final' ./mf.sh test`、
2428 passed /3 warnings /157.29秒。node構文/git diffも通過。
署名公開・installed受入はhandoff/statusに追記する。
NOT TESTED: 認証付き実Host埋め込み画面、実スマートフォン本体、新規AI推論の生成品質。
