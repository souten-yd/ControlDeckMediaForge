# 別方向の画像候補と比較・明示選択

## スコープ

branch `ux1/multiview-candidates-ui`、base `7bce85d`、0.33.22。
既存の1枚参照 `image.edit` から方向別の候補を作り、元正面と比較する導線。
CreativeBatch/Job/Asset/来歴とHost admissionを再利用する。
方向ごとに異なる指示を使い、正面を複製して面数を満たさない。
元画像・方向contextと実内容を採用時に照合し、別元画像/複製/削除/不一致を拒否。
生成成功、目視確認、校正、3D品質は別の判定とする。

## ソースでの実測

証跡root: feature-data/media-forge/maintenance/multiview-20260923。

- `node view-candidates-ui.mjs`: 実Chromiumのopaque iframe、制御した通信応答。
  PC1280/タッチ320で3方向依頼/取消/自動採用なし/比較後の明示選択/前方向未選択の拒否/
  複製候補拒否/正面変更時の候補隔離/最近のJobを消した後の候補再表示/詳細設定保持/
  英語/簡易モードの状況→比較を確認。横overflow0、操作44px、pageerror0。
  `view-candidates-ui/browser-activity-fix.log` と `result.json`。
- `node product-ui.mjs`: 従来の手動4面の個別選択/除去/再追加/取込/取消/詳細camera/
  1枚への復帰を1280/320で再確認。4previewが相異、overflow0/pageerror0/44px。
  既存installed4面の実contentも再取得し、方向ごとの保存SHA/来歴画素SHAと一致、
  全4枚相異を確認。`view-candidates-ui/existing-four-view-check.json`。
- 実ブラウザで詳細→簡易へ切り替えると、focused inputのblurが再描画を再入して
  DOM NotFoundErrorになることを確認。再入防止で解消。
  また簡易モードの状況が全batchを隠し比較入口も消していたため、方向候補を表示し、
  内部IDと子Job一覧は詳細だけに残した。初期失敗logを証跡へ保持。
- 隔離Uvicorn/SQLite/偽workerへの実HTTP: 正面1枚をimportし3方向を依頼。
  2件は `alpha_missing`、1件成功。全件成功を期待した評価helperは失敗しており、
  成功へ書き換えない。再送せず同DBを再起動して部分成功/来歴/異なる3指示を照合。
  Job履歴4件をclearした後も候補を復元し、成功画像だけをselectできた。
  `view-candidate-http-2/readback.json`。これは実モデルの品質評価ではない。
- preliminary全testは、通常Createへ方向batchが誤復元される問題の修正に際して
  自身のpytestだけを中断。1464passed/3warnings/228.40秒、exit2。
  full-test-interruption.jsonに対象と理由。最終gateとは別記録。

最終 `./mf.sh test`: **2576passed/3warnings/322.27秒、exit0**。
実行中にconstructorの戻り型 `None` 注釈のみ追加し、service testsも追加実行。

追加モデルdownload0。既存Assetや商店街は変更しない。
署名配布・installed新UIでの実生成/選択/Library・候補画質・物理スマホは
このソース受入時点で NOT TESTED。失敗候補を3Dへ自動投入しない。

## 0.33.22の署名配布と通常更新

PR659 `4c4b3c6`（source `ea1e1c0`）を通常merge。署名bundleは38,110,741 B、
SHA-256 `757ae97bd91e8819ca102acdfbcaa5b1e68162fb1285f6ce93f330143a32425a`。
既存trusted公開鍵、canonical署名、改ざん拒否、6tar entries、244embedded entries、
新service moduleとfrontend/schema/workerのsource一致、重み/DB/秘密値混入なしを確認。
4assetを公開後に再取得して同じ検証を通過。

抽出した配布物を新規data/cacheで起動し0.886458秒で応答。未導入3D/参照編集は
unavailableで、候補要求はJob作成前に拒否。既存packの既定zip/不正output拒否も確認。

実行中Job/model操作/Blender session/両prefixのOpenCode unitとactive leaseがない
状態でDB backupを保存し、通常 `deck.sh feature update media-forge` を実行。
current0.33.22/PID751496/healthy。旧1594 Asset metadata、代表3content SHA、
runtime-state全JSONを保持。配信app.js/styles/schemaは配布sourceと一致。
3D capabilityは更新前と同じ、Host PID674922を保持。
証跡: maintenance/release-0.33.22-20260923。

### installed 0.33.22で見つかったタッチ不具合

通常ログイン/320pxで生成前に候補見出しのタップが失敗し、画像Job追加0。
診断でtouchstart/endはscene-view-candidates-titleへ届く一方、後続のtrusted clickが
scene-generation-add-viewへずれ、候補を開かず右面の空欄が増えることを確認。
スクロール停止を500ms待っても再現。初回helper失敗を成功へ書き換えない。

0.33.23修正候補: 既存のtouch activationを任意selectorで再利用し、新しい候補欄の
summaryとcheckbox/そのlabelに限定して追加。既存button経路は同じ。
ドラッグ/複数指/無効/領域外終了の既存guardを保持し、native select/canvasは対象外。
通常Hostにこの関数だけをsource overlayした診断では、実touchが正しいsummaryの
click1回に変わり、details.open=trueを維持。これはinstalled配布受入ではない。
実モデル生成と0.33.23配布は、この修正の最終gate後に行う。

最終 ./mf.sh test は2576passed/3warnings/345.50秒、exit0。以後製品コード変更なし。
source opaque iframeを88px下げた1280/320で比較/確認labelのタップ/明示採用/履歴等も通過。
通信応答はfixture、overflow0/pageerror0/44px。証跡touch-source-ui/result.json。

## 0.33.23署名公開・通常導入

PR660 `4fadfff`（source `6125d0c`）を通常merge。bundle 38,108,046 B、
SHA-256 `f25743aa44eefd719628c3b7dee2857173d717ff42bdc5e49402237654df214b`。
既存鍵署名、trusted公開鍵、改ざん拒否、source一致/混入検査、公開4asset再取得を通過。
新規data/cacheで0.877356秒で応答、未導入参照編集/3DのunavailableとJob受付拒否を維持。

実行中Job/model/Blender/OpenCode unit/leaseなしを確認しbackup後に通常feature update。
current0.33.23/PID770023/healthy。旧1594 Asset metadata/代表3content SHA/
runtime-state全JSONを保持し、配信frontend/schemaは新sourceと一致。3D capability不変。
Host PID674922を保持。証跡maintenance/release-0.33.23-20260923。

### 通常UIでの3方向生成と独立照合

通常ログイン/opaque iframeの320pxから1回だけ依頼し、batch
`batch_ad986d092bfb4a60bdfb6ecce4507692` の3子Jobがsucceeded。
依頼から最終終端のUI観測は156.636秒。追加送信/モデルdownload/3D生成0。
元正面は `asset_62eafeae60dc4662883843d73304494c`。既存FLUX.2-klein-4Bを使用。

| 要求方向 | Job | 保存画像 | bytes | 作成〜終端秒（待ち時間込み） |
|---|---|---|---:|---:|
| right | job_9c1b623a40aa4bb0b92ac8330ff44be5 | asset_7213c04aeeef4eb69a2781ef408af155 | 871121 | 68.927568 |
| back | job_4b810130bc40455ea46c27a1aad710f5 | asset_e37bfeb687a349538a32329ec629f7a3 | 924452 | 104.800423 |
| left | job_f95b3a2928bc437fbd33ef7135794d18 | asset_d935d74a1cc8476ab102fc63caadd469 | 746570 | 155.117458 |

全1024 RGBA、四隅alpha0、alpha0割合83.3082%/82.6424%/83.5325%。
3出力の実SHA/画素SHAは互いに異なり、正面の複製でもない。元正面のmetadata/実SHA、
親ID/参照SHA/方向context/保存版0.33.23を独立HTTPで照合。Hostの3leaseは全released、
active0、Host PID674922不変。旧1594 Assetとruntime-stateを再照合し、総Asset1597、
active Job0、商店街project変更0。証跡 `host-installed/candidate-verification.json`。

### UI受入の範囲と失敗記録

- 通常installedの比較画面: 320/1280で3候補すべてを実タップし、元画像と各候補を表示。
  未確認時の採用ボタン無効、opaque origin、横overflow0、pageerror0を確認。
  候補カードを画面中央へスクロールしてからタップした最終結果は
  `candidate-comparison.json`（6件passed）。再生成はしていない。
- 通常Activity URLから候補行の「比較」を320ではtouch、1280ではmouseで操作し、
  正しい元画像の候補欄へ戻ることを確認。`candidate-activity.json`（2件passed）。
- 通常Libraryで3画像と既存4面GLBを320/1280で表示。GLBの回転による描画変化も確認。
  初回は最後のPC画像closeが10秒timeoutで7/8件まで。未成功を成功へ変えず、
  その1画像だけを再表示しPCのpointer操作でcloseを確認した。
  `library.json` の7件と `library-close-readback.json` の1件を別の証跡として保持。
- 実WSの採用前検査は3画像すべてで元画像/来歴/画素検査を通過し、
  `requires_visual_confirmation` / `not_inferred` を返した。これは画質採用ではない。
- 初回の生成helperと再表示helperは比較対象への入力が成立せずtimeout。
  また比較後の固定navからActivityへ進む自動操作は入力を確認できずtimeout。
  固定nav経由の同一フローを受入済みとはしない。中央へスクロールした比較と、
  Activity URLからの復元受入を区別する。失敗log/JSONをすべて保持。

### 見た目の判定: この3枚は3Dへ採用しない

- right: 要求した厳密な右面・image left向きでなく、image right向きの背面寄り。
  元にない斜めのストラップも増えた。体形/ケース形状が変わった。
- back: 背面自体は描かれたが、ケースが画面右に残り、元正面と比べ持つ手が入れ替わる。
  正面のケースは画面右なので、正しい背面では画面左に見える必要がある。
- left: 指定のimage right向きは出たが、体形/衣服/ケース形状が元と異なる。

単なるコピーではない一方、right/leftが近い向きになる意味上の不整合がある。
この組を自動で3Dへ送らず、通常画像として比較用にLibraryへ残した。
`candidate-quality.json` に実画素/観察を保存。生成Job成功と品質合格を混同しない。

NOT TESTED / 未受入: この組の3D生成（品質不合格のため未実行）、installed UIでの
採用完了、新UIのinstalled取消、物理スマホ、比較後の固定navフロー。
新UIの採用/取消自体はソースの制御通信ブラウザで確認済みだが、上記と分離する。
製品コードは全2576pass/345.50秒のgate後から変更なし。今回は受入記録のみ。
全体goal継続。
