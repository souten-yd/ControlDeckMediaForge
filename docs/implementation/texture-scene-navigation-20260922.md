# 派生画像と元3Dの相互移動・モバイル材質変更

Date: 2026-09-22. Branch: `ux1/texture-scene-navigation`. Release: 0.33.3準備。

## 利用者の操作

- Libraryの派生画像ビューアーに「元の3Dを開く」「この画像で材質を変更」を表示する。
- 詳細には元シーン名・制作元の版と、その版の3Dを見る操作を表示する。
- 元3Dのビューアーとシーン詳細に「材質を変更」を置く。画像からの移動では
  元の対象/slot/用途/UVと選んだ画像を引き継ぎ、比較→採用で新しい版へ保存する。
- 現行版から対象がなくなった場合は割当てを無効にして選び直しを案内する。
  古い画像が最近120件の画像一覧にない場合でも、明示選択した画像をフォームに保持する。
- 通常のLibrary画像編集では元Assetを再利用し、元シーンの文脈を
  `source_scene_texture`へ記録する。画像を縮小した場合もシーンとの関係を保持する。
  この来歴情報でStudio専用の進捗・推論寸法・資源profileへ切り替えない。

## 保存と境界

private assets.relationsの追加応答`scene_links`はcoreが保存済みprovenance、親Asset、
SceneRevisionを照合する。Job一覧の保持件数やブラウザの一時状態に依存しない。
ownerは認証identityまたはstandaloneのlocal ownerから決め、クライアントから受け取らない。
他ownerのscene、別sceneのrevision、壊れた型の文脈はリンクへ昇格させない。
画像bytesを読まず、最大64 Asset/親8段/16シーンまでのmetadata参照に制限する。
新しいDBや公開必須field、Host専用ルートは追加しない。Blender GUIは自動起動しない。

## 実測

原本: Feature maintenance `texture-scene-links-20260922/`。

- `python -m pytest tests/test_asset_scene_links.py tests/test_library_relations.py
  tests/test_frontend_contract.py`: 166 passed / 2 warnings / 3.08秒。
  履歴整理後の再読込、2段派生、元版/現行版の区別、owner/偽revision/型不正拒否、
  authenticated WSとstandaloneのowner分離、metadata-onlyを確認。
- `ui-source.mjs`: 独立source fixtureを実Chromeで1280px/320px、touch有効で操作。
  画像は以前の明示fake worker出力、Blenderは実物。画像→元scene、画像を選択済みの
  材質比較、元版のGLB閲覧、GLB→材質変更を確認。PCは比較破棄で元版不変。
  320pxでは明示採用で1→2版、旧版は保持。横overflow0、page error0。
- `ui-edit.mjs`: 320pxの新規導線ボタンは44px以上。Library編集/モード再準備後も
  元Asset IDを維持。capabilityは明示fixture、submit要求を捕捉して送信前に停止し、
  input Asset/`source_scene_texture`あり・実行用`scene_texture`なしを確認。
  これは実AI生成の証跡ではない。
- 初回の全suiteは2407 passed / 3 skipped / 3 warnings / 274.43秒。
  skippedはbuild runtimeが未接続だった署名3件。接続後の全suiteは2409 passed / 1 failed。
  失敗は既存native子終了テストで、成功した終了による/proc消滅がexists/read間に起きる競合。
  単独再実行は0.08秒で通過。終了を意味するFileNotFoundErrorを正しく扱う検査へ修正し、
  native実装・終了条件は変えていない。
- 最終 `./mf.sh test`: **2410 passed / 3 warnings / 272.53秒 / exit0**。
  署名3件を含めskipなし。`node --check frontend/app.js`、`git diff --check`も通過。

## 残る受入

通常PR merge、署名公開/通常Host更新、installed Hostの実画像からの導線、
320pxの比較/版保存と再起動後の関連復元は未実施。実スマートフォン本体ではNOT TESTED。

## 0.33.3公開後・通常更新前の追加確認

sourceの`stale-target.mjs stale-target-before`で、制作元objectが現行版にない条件を確認。
移動直後は`target="" / disabled=true`、材質再取得後に`Mesh_0 / disabled=false`となり失敗。
元の対象が無いときだけを例外にするのではなく、対象の単一候補自動選択自体を除去する。
有効な元対象の復元と利用者の明示選択は維持。0.33.3はローカルへ適用せず0.33.4へ進む。

`stale-target.mjs stale-target-after`は移動直後/材質再取得後とも
`target="" / disabled=true`で通過。320pxのLibrary編集導線も再確認し、詳細44px、
viewer60pxの操作面と元Asset/元scene文脈の維持を確認した。
0.33.3はprereleaseへ変更し通常更新の対象から外した。修正版0.33.4の ./mf.sh test: **2410 passed / 3 warnings / 276.06秒 / exit0**。
