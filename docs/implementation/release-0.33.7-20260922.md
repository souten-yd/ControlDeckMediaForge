# 0.33.7 — 3Dの簡易操作・関連元画像と生成ボタン案内

## 現在の状態

PR622とPR623を通常mergeし、source `6705400b074e0a09950f118b992b24c408650793` から
0.33.7を署名公開、通常Host更新でこのPCへ適用した。再起動後もhealthy。
**installed Hostの認証付きbrowser再受入だけは専用session期限切れにより未実施**。
利用者へ `bash ~/mf-login.sh` での再ログインを依頼済み。認証境界を迂回しない。

利用者の入口は「3D」→「作った3Dを編集」→対象を開く→「材質を変更」。
簡易では場所→画像→3Dで確認→採用の順に進める。元画像だけを既定のサムネイル一覧とし、
派生候補・全Libraryへ切替できる。AIに渡す画像の出所を説明する。詳細設定は詳細モードで
変更でき、モード切替で値を保持する。変更済み表示と明示的な推奨設定への復帰を用意した。
保存履歴は折りたたみ、現在の3D表示は独立したボタンから開ける。

## 実行と観測

証跡の基点は `/data1tb/ControlDeck/data/feature-data/media-forge/maintenance/`。

- `3d-simple-flow-20260922/full-accepted.log`:
  `PYTEST_ADDOPTS='--basetemp=/data1tb/mf-test-0922' ./mf.sh test` は
  **2413 passed / 3 warnings / 155.79秒**。最終frontend contract160件、node構文、
  HTML ID重複なし、git diff確認も通過。
- 先行した2回の全体実行は既存2秒待ちの異なるtestで各1timeout。いずれも単独は通過。
  長いNVMe試験pathではUnix socket長制限で20件失敗したため短い専用pathで上記を実行。
  製品コードやテスト期限を緩めて通したものではない。
- `3d-simple-flow-20260922/ui-source.json`: source API/実Blender、画像capabilityだけ明示fake。
  Chrome1280/320px touchで元画像2/全画像6、関連候補選択、材質比較/破棄、現行3D表示、
  詳細値保持/推奨復帰、入力不足のfocusを通過。無効要求0、有効image.edit要求1をGPU前に捕捉、
  二重送信防止、横overflow0/page error0。fixtureのscene head不変。実AI品質の受入ではない。
- `3d-simple-flow-20260922/related-production.json`: 本番宝箱の保存来歴を新resolverで読取。
  元画像4/派生3、0.010463秒、truncated=false。画像bytesを読まず、JobやAssetを作らない。
- release: <https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/0.33.7>。
  `scripts/build_release_bundle.py` / `scripts/sign_release.py sign`、公開物の再取得と独立照合を実施。
  `release-0.33.7-20260922/{artifacts,downloaded}/verification.json`:
  **38,035,896B**、SHA256 **e50d6382e1b76510c03b8d16d777da87080b85375f8e43c257e08f1f4c86b515**。
  trusted publisher署名/改ざん拒否、archive6項目/embedded241項目、frontend全fileと対象worker/catalog
  bytes一致。重み/venv/DB/秘密鍵を含まない。
- `clean-smoke.json`: fresh managed dirsへ展開し0.865500秒でcore到達。
  実runtimeのない新環境ではsetup_required、image-to-3Dはunavailableを維持。
- `update-local.py`: active Job0を確認し1535 Asset metadataを記録後、
  `/data1tb/ControlDeck/app/deck.sh feature update media-forge` を実行。
  currentは `versions/0.33.7`、初回PID3807569。
- `installed-check.json` / `restarted-check.json`: 1535 Assetすべてのmetadata保持、代表3 Assetの
  実HTTP content SHA一致、served app.js/styles.css/three-viewer.jsがrelease sourceとbytes一致。
  image-to-3D capability documentは更新前と同一。
- `restart-ready.json`: active Job0で通常service再起動し0.825544秒でhealthy、PID3807845。
  `deck.sh feature status media-forge` はmanaged/installed/enabled/version0.33.7/healthy。
  `final-core-state.json`: active Job0、Asset1535件。
- `installed-standalone.json`: 正式installed coreの直接表示で1280/320px touchの入口切替、
  詳細設定のDOMからの除去/再表示、横overflow0/page error0。これはHostのopaque iframeや
  Host ownerの既存sceneに対する材質操作の証拠とは分ける。

## 未実施と再開手順

NOT TESTED: 0.33.7の認証付きinstalled Host browserでの元画像選択/比較/再起動後の導線、
Host effectiveと未解放leaseの最終再照合、実スマホ本体、fresh GPU構築、今回の新規AI推論、rollback。
GPU runtime/model/catalogの採用内容は変更していない。

専用operator sessionはhelperが `host_session_expired_use_logout_then_login` を返したため、
通常logout endpointで期限切れsessionだけを失効し、利用者に再ログインを依頼した。
ログイン後、release sourceのcwdで `PYTHONPATH=backend:.` を付け、共有core Pythonから
`maintenance/create-button-20260922/browser-auth.py` に以下のNode scriptを渡す。

1. `maintenance/release-0.33.7-20260922/ui-installed.mjs`
   — 1280/320pxの関連画像、全Libraryの続き、比較/破棄、設定保持、生成入力不足/二重送信を確認。
   AI要求はGPU前に捕捉し、元sceneは採用しない。
2. `maintenance/release-0.33.7-20260922/post-restart.mjs`
   — 320pxの実Library派生画像→元scene、選択画像を維持、元画像のみ表示、元scene head保持。
3. `maintenance/release-0.33.7-20260922/host-final.py`
   — 正規operator経路でeffective healthy、active Job0、MediaForgeの未解放lease0を照合。

失敗があれば未実施を成功へ変えず、修正/再確認する。合格後に本書とhandoff/statusへ追記する。
元checkout `feat/g9-image-to-3d`/`524553d` はcleanで保持。独立source fixtureは停止済み。
