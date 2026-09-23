# 歩ける商店街: OpenCode / Qwen3.8-27B / MCP 制作受入

Status: HTML制作・実MCP納品・不具合修正・通常Hostでの受入完了。MediaForge 0.33.23で再確認。
物理スマートフォンの性能・操作品質と、任意画像からの正確な別方向生成は未受入。

## 最終成果物と2026-09-23の再監査

ControlDeckの **Project Lab → MF3DS-ShoppingStreet-20260923 → index.html** から開く。
左スティックで移動、右側のドラッグで視点変更。PCはWASD/矢印キーを使う。
店舗4種類を8軒、操作人物1人、歩行者2種類を計6人配置した三人称HTML。
モデル・テクスチャ・Three.jsはローカル同梱。商店街のコードとモデルは今回変更していない。

通常認証HTTP runner `scripts/shopping_street_opencode.py` は、この制作で使用した
OpenCode実行のモデル固定・送信前receipt・同一Job観測を再現する補助スクリプト。
既存receiptの再送を拒否し、観測HTTPの失敗をJob終了にしない。自動停止処理はない。
今回のpreflightも通常ログインで成功し、Qwen3.8-27B/runtime v1を確認した。

| 受入 | 証拠と結果 |
|---|---|
| 実OpenCode/ローカルLLM/MCP | 店舗Host Job25f23f603894、人物Job781d15da871f。projectのdiscovery/references/shop-packs/npc-delivery JSONに実tool・画像・GLB・grant receiptを保持 |
| HTML制作と修正 | OpenCodeのWeb Jobe67c69a17071はHost再起動でinterrupted。書き出されたHTML/CSS/JSを保持し、監督側で読み込み判定/独立clone/接地/停止/衝突/画像読み込みを修正。初回Jobを成功へ書き換えていない |
| 実成果物の独立検査 | manifestの7GLBと実SHAが全一致。合計24,931,924 B。各2画像をGLB内に保持し外部URIなし。店舗各30,000tris、人物41,827/85,647/85,343tris |
| 人物rig | 全3人物にskin、12 joints、JOINTS_0/WEIGHTS_0、1秒/36channelのwalk clip。既受入の実25frame変形・左右脚非交差の対象と同じ成果物。骨格の存在だけを変形品質の証明にはしない |
| 通常Host表示 | opaque iframeで7モデル/15配置の画像読み込み、8店舗/主人公/6NPCを再確認。PC/320/390pxの実画面も目視。灰色モデルで成功扱いしない |
| 操作 | PC前進、320/390pxで同時touch移動＋視点操作、help開閉、再読込で7モデル再現。移動距離1.205913/1.050369m、横overflow0、page error/console warning0 |
| 接地と性能 | 7人物の足底Y=.062m。PC内蔵Radeon/Chromeで300frame/5.0024秒、59.971214fps、p95 16.8ms。ready観測時performance.now=1628.1ms。ResourceTimingのdecodedBytes=0はopaque iframeでの観測値であり転送量0ではない |
| 不具合修正 | 脚交差、微小weight欠損、失敗段retry、rig結果契約、軽量化設定のMCP掲載、形状保持、Host内画像CSP、pack既定形式、失敗Job ID保持を別sliceで修正・通常導入・実MCP/描画で再受入 |

上記修正はmainに統合・署名リリース済み。稼働MediaForgeは0.33.23/PID770023、
HostはPID674922/NRestarts0。この最終監査は追加生成0・モデルdownload0。
2026-09-23T12:29:09Zの通常auth/me成功、active MediaForge Job0/lease0、Asset1597。
原root `feat/g9-image-to-3d` は変更しない。

今回の直接証跡はmanaged `maintenance/shopping-street-20260923/final-audit-0.33.23/` の
`artifact-audit.json`、`host-street-acceptance.json`、PC/320/390px PNG、`inputs-and-idle.json`。
実行は `private-browser.py street-final-audit.mjs`（通常ログイン/実Chrome/実Project Lab）。
以前の衝突・停止fade・blur・WebGL loss/recoveryはprojectの
`evidence/web-actual-mechanics.json`、変形・納品は`evidence/acceptance-summary.md`参照。
同一SHAの再確認により対応付け、今回すべての故障注入を再実行したとは記録しない。

### 統合時の検証

PR631へmain d0ee4b6を統合後、`./mf.sh test` は2581passed/3skipped/3warnings、
387.39秒、exit0。署名3件だけは作業treeにbuild runtime参照がなくskipしたため、
手元の既存build venvへsymlinkを追加し、
`.venv/bin/python -m pytest tests/test_release_signing.py -q` で全3件pass/exit0。
新規依存取得なし。これらを「fullでskipなし」と書き換えない。
ログは最終監査rootのfull-tests.log/signing-tests.log。以後code変更なし。
変更文書4件の相対リンクとgit diff --checkも通過。

このPRは配布外の評価runner/tests/prompts/記録だけで、0.33.23の製品payload差分は0。
新たな版数更新・再配布・Host再起動は不要。商店街projectの最終記録はlocal commit6a8056b。

### 追加依頼の範囲と残る限界

- 手動1/2/3/4面のVulkan生成とモバイルUIは0.33.20で導入済み。
  既存4面の実contentを再取得し、ファイルSHA/透過を考慮した画素SHAが記録と一致、
  全4枚相異を確認。同じ正面の複製ではない。商店街本体の制作は単一画像経路である。
- 1枚から右/背面/左候補を作り、元画像と比較して明示選択するUIは0.33.23で導入済み。
  実3候補をLibraryに保存したが、向き・バッグを持つ手・形状の差で3Dには未採用。
  自動校正/任意画像での正しい3面生成を完成とはしない。比較と判断を挟む範囲を提供する。
- OpenCodeは利用者の方針どおり明示停止まで継続可能。owner/RBAC付き個別停止は
  Host PR340/341で導入・実OpenCode Jobcfce488f01aaの320px停止で受入。
  実推論中のHost再起動、cold要求の厳密な同時到着は追加の未試験条件として残す。
- 物理スマホの速度/タッチ品質はNOT TESTED。人物20kの初期目安は未達であり、
  形状を保つ約85kを選んだ。全端末での快適さ、高品質な自動rig全般の保証にはしない。

以下は制作途中の履歴であり、現在の未完了状態ではない。失敗結果と元Assetは保持する。

## 利用者の目標（完了条件を縮めない）

OpenCodeとローカルQwen3.8-27Bを実際に使用し、MCPで画像から商店街・操作キャラ・
歩行者の3Dを生成する。人物にボーンと歩行を付け、モバイルから三人称で歩けるHTMLを
納品する。実制作を評価し、MCP等の不具合を再現・修正設計・修正・再受入する。
ブロックモデル、静止人物、ソーステストだけを最終成果物の代わりにしない。

## 制作方針と受入

指定のない外観は、暖かな日本の小さな商店街・様式を揃えた立体イラスト調とする。
パン屋/喫茶店/花屋/本屋の最低4種類を別画像から生成し、配置した8店舗以上で通りを構成。
操作キャラ1種類と歩行者2種類を別画像から生成し、ボーン付き歩行者6人以上を配置する。
建物/人物モデルはMCPでの実画像生成→image-to-3D→必要な軽量化→人物rig→GLB納品。
道/歩道/照明/衝突形状はWebの補助geometryでよい。店舗・人物をprimitiveで代替しない。

| 条件 | 直接確認する証拠 |
|---|---|
| OpenCode + 指定ローカルLLM | Host通常起動Job、実OpenCode session/モデル識別、MCP tool入出力 |
| 実画像→3D | 画像/scene/GLB Asset ID、Job ID、lineage SHA、grant配置receipt |
| 統一された商店街 | 地上・遠景・左右店舗の実描画。少なくとも4種類、8店舗、連続した歩道 |
| 操作キャラと人通り | 主人公1人+歩行者6人以上。人物3種類の生成元、同一骨格の独立clone |
| ボーンと歩行 | skins/joints/weights、歩行clip、複数時刻の実頂点変形と足元映像。物体移動だけは不可 |
| 三人称で歩ける | カメラ追従/旋回、前後左右移動、建物の貫通防止、停止時アニメーション遷移 |
| モバイル | 320/390px touchの左右スティック/ドラッグ、同時移動/視点変更、44px、横overflow0 |
| HTML納品 | 実配信URL、ローカル同梱GLB/JS、読み込み失敗の表示、再読み込み後再現、秘密値なし |
| 体感と資源 | FPS/frame時間、ロード時間/bytes、描画calls/triangles、操作中page errorとcontext loss |
| 不具合修正 | 再現条件/期待と実際/原因/修正設計/差分/回帰/修正版の同じ経路での実測 |

モバイル向けの初期予算は人物1体20k triangles、建物1種類30k、画像1024px以下。
実測と外観を見て調整する。片側だけの見た目や足滑りを隠して合格にしない。
最初に1人物の画像→3D→歩行を検証し、破綻した形を大量複製しない。

## 初回着手時の実測（履歴）

- rootはfeat/g9-image-to-3d /524553dでclean。変更せずorigin/main 5dc52bfから別worktree。
- installed MediaForge0.33.10/healthy、active Jobs0。商店街用既存projectなし。
- installed capabilities: TRELLIS Vulkan512/1024、Pixal1024がexperimental。
  公表済み計測98.430916/507.788254秒、Pixal1172.211559秒。今回の生成実測ではない。
- typed rig.auto/animation.clip、scene-rig schemaとendpointが存在。
  healthにはscene.rigが明示されていないが、Hostは未記載contributionをavailableと扱う。
  この差だけで「MCPから使えない不具合」とは判定しない。
- dedicated operator session不在。実Host auth/meとopencode/statusはいずれもHTTP401。
  通常loginを依頼済み。旧3ds_opencode_flow_e2e.pyはHost内部import/credential発行に依存するため
  今回は流用せず、通常のHost HTTPでOpenCodeを起動する。認証やbrokerを迂回しない。
- `maintenance/shopping-street-20260923/initial-audit.json` と initial-capabilities.jsonに保存。

## 進め方

1. 認証後に実OpenCode statusとgatewayのモデル対応を確認。指定モデル以外へ自動代替しない。
2. 専用CodeDEV projectを通常Host APIで作成。短い工程ごとにOpenCodeからMCPを呼ぶ。
3. 同じJobを終端まで追跡する。観測timeout/一時失敗で別Jobを再発行しない。
4. 画像/3D/rig/HTMLを各段で評価し、問題を分類して最小の製品sliceで修正する。
5. 最後に本物の生成済みAssetを使うHTMLを実ブラウザで操作し、全条件を再監査する。

## 認証後の実制作

利用者の通常login後、専用operator session経由のauth/meが通過。
Hostの通常project作成/API起動でOpenCode1.18.30を実行。設定のautoは変えず、
この実行だけ登録済みQwen3.8-27Bを明示。実プロセスの重みは
Qwen3.8-27B-UD-Q4_K_M.gguf、131072 context / parallel1。

- Host Job736a2ac69b4fはsucceeded。OpenCode session ses_f348269feffePwu5Vb5dh78XZFで
  controldeck/Qwen3.8-27Bとmedia.capabilities実呼び出しを確認。
- 実成果はCodeDEV/MF3DS-ShoppingStreet-20260923/evidence/discovery.md。
  主agentのscene.*非露出はHostの専門agent分離設定によるもので、contribution欠落ではない。
  主agentに露出するpipeline.start/statusで段ごとの制作を進められる。
- 主人公画像の実生成Job976d364e...は167.215978秒でfailed、
  host_unreachable / WriteTimeout。MCPはHTTP502で元Job IDを返さなかった。
  OpenCodeが未生成と推測して再送したため、Host Job90b2be3c7dcdを通常cancel。
- 再送Job72f0b74b...は30.369037秒でsucceeded。
  asset_ba425dadeebc4238ab8d05bd45c1874b、1024x1024 PNG、599238 B、
  SHA256 5408f63c7657d42b8029d846dd9cc1d90647b4c3b3df23f405c27f443e4f318c。
  目視で全身/足先/腕と胴の隙間/脚の隙間/黄色上着と青緑パンツを確認。
  顔は若く様式化されている。背面・立体・変形はまだ検証していない。
- 新規生成を止め、同じ成功Assetをinspect/packするだけの回収Job996d740d02a6を開始。
  HTTPエラーを未生成と扱わず、同じJob/pipelineを保持する規約をpromptで補強。

## 不具合記録

1. Host同時cold start: 最初のタイトル要求がGPU30979147560 Bを予約。
   2.021286秒後の本体要求がcold予算のまま待機し、モデル起動/slot idle後も
   自分と同じownerの23138320384 Bに阻まれ、300秒でexpired。
   同じOpenCode実行が自動retryして進行。resource snapshotをmaintenanceへ保存。
   MediaForge側ではgatewayの見積り時点を変えられないため、Host別worktree/PRで修正。
   再現テストでは実Brokerとgatewayの同時2要求のうち後続がtimeout。
   同一aliasの見積り→ready区間を直列にし、推論は直列化しない修正後30 tests通過。
   実Host適用後のcold再受入は未実施。
2. MCP生成失敗時の追跡情報不足: HTTP502に元Job IDがなく、LLMが未生成と誤推測。
   今回DB読取では初回失敗/次成功。重複成功はなかったが、同じ判断での再送は安全でない。
   Host/MFのerror経路と元WriteTimeoutを調査中。製品修正・再受入は未完了。

NOT TESTED: 3D生成、人物の変形品質、HTML表示/操作、物理モバイル端末。
目標はactive。通常HTTP runnerのfixture通過は実画像/3D品質受入とは分ける。

## 制作runnerの検証

通常認証HTTPでのpreflight/start/status、指定ローカルモデル固定、送信前receipt保存、
応答喪失時の再送拒否、観測401/404/503でも元Job状態保持をfixture8件で確認。
`PYTEST_ADDOPTS=--basetemp=/data1tb/mf-street-test ./mf.sh test`:
2436 passed /3 warnings /171.40秒。rootはcleanのまま。
回収Job996d740d02a6はsucceeded、MCP inspect/packのreceiptと実PNG SHAが一致。
主人公3Dのconfirm pipelineを開始するHost Jobb5bfee084e46を起動し追跡中。

## 2026-09-23 09:40 JST checkpoint

- 生成元7画像（主人公、パン屋/カフェ/花屋/本屋、歩行者2人）を実生成・目視確認。
  6画像batchのHost Jobefcdd0c284eb/session ses_f3460aa98ffepr3co9Rgep8CPlはsucceeded。
  exports/*-source.pngへMCP inspect/packで配置しevidence/references.jsonへreceipt保存。
- 主人公model Hostb5bfee084e46/session ses_f346f056cffeQ79iSbxHiUf08U succeeded。
  pipeline_9840d28cf9164e0288c10cf8f80da18b、scene_889d23ec8c874d91bfa6347b3d4076a5。
  native TRELLIS Vulkan512/seed1729、生成74.206241秒。GLB asset_0b420f1f16584fccb9c0283e790af61f。
  148034tris/1material/2embedded images。元画像に比べ肌が赤く黄色上着が茶色。外観FAIL。
- 続きのrig/export Host4ed3fd8be8f5/session ses_f3469baf4ffens73MH0YssF81i succeeded。
  版revision_bf86dc9e51b3454ea75c772119da3603、GLB asset_62cde187b3ea449fb8b67bcbfbbc4afb。
  88687tris/6bones/skin1/1s walk、MCP pack後bytes一致。
  実描画で腕の巻き込みと脚交差を確認、利用者も交差を指摘。rig品質FAIL。
- 別slice ux1/humanoid-rigで人物用測定/12bones/前後歩行を修正中。
  source実Blenderで旧足表面X間隔−.383876m→22122tris候補+.098814m、手の脚重み平均.989627→0。
  まだinstalled修正/正式Asset再登録ではない。詳細は同sliceのhumanoid-rig-20260923.md。
- Host cold同時起動のPR336はmerge ea7212865c834bd1955e0beacf9262e73195e437。
  最終./deck.sh test:1141passed/2skipped/109.40秒。
  rootをff更新し通常deck.shでrebuild/restart、PID11639/HTTPhealth200。
  実cold再試験はNOT TESTED。warmの新規OpenCode実行は継続している。
- 更新後の通常認証Host opaque iframeで主人公のLibrary viewerを1280/320pxで表示。
  88687 triangles/1 material/1 animation、overflow0/page errors0。物理電話は未試験。
- パン屋のみOpenCode Hostea1473f4ad30から3D化を開始、同じpipelineを追跡中。
  pipeline_6bc96c7c443b40ac90e8a6f07d75e64a、model Job17a78add...はDB読取でsucceeded。
  packing完了/外観は未検証。ほかの店舗・歩行者3D/HTMLはまだ未作成。

NOT TESTED: 修正版installed人物rig、色の修正、商店街全体、HTML/操作/移動時接地/性能、物理端末。
MCP502の元Job情報不足は別途未修正。目標はactive。


## 2026-09-23 installed walk continuation

歩行修正PR632を0.33.11として署名公開・通常ローカル更新。元の主人公sceneは第4版
revision_496964560f624255ae5698c1c94275bdへ再rigしてLibrary登録、旧版を保持。
GLB asset_0480355b176141a4ae51f17f8eee66b7は22122tris/12bones、全25frameで脚交差なし。
同じ元画像/seedの1024比較Host35fef7cff431は成功し、scene_37ab4d0bcec24c8d9d55cabd0e0ab356、
未rig GLB asset_2d6fb609125b4cafa0497b09ffb198dc（279538tris）。肌の赤さは改善、服はまだ茶色。
続く実MCP Host2506347a7351は新規startせず同じpipelineを継続したが、rig Jobdcd564c6...が
unweighted verticesでfailed。出力を公開せずexport/packなし。欠損部位を実Blenderで調査中。

パン屋Hostea1473f4ad30は成功、MCP export/pack済み。
GLB asset_bed82e10e6c14c4f97c76a10ea4eda01、134392tris、SHA867d2437e4dc37ddaf218f47ec1bc390f94429262cca0d252c6a4597540c94e6。
屋根/庇/売場は立体化されているが、看板文字は潰れ、部分的に表面に傷が見える。
そのまま高品質合格とはしない。HTMLでの距離と軽量化後に再評価する。
残るカフェ/花屋/本屋（512）とNPC2種類（1024）のmodel段のみをHost03447db06990で開始。
receipt remaining-models-job.jsonとproject evidence/remaining-models.jsonを継続観測。
rig/export承認前で止め、モデルごとの形状・材質・bind可能性を先に確認する。

## 0.33.12 installed / retryとWeb実装の継続

高解像度主人公の肩14頂点だけの重み欠損をbounded repairで修正し、0.33.12として
署名公開・通常更新。current0.33.12/実PID78171/healthy、1567既存Asset metadata保持。
実Blenderの元入力再実行ではgeometry/UV/画像不変、足間隔最小+.111551m。
MCP pipelineのfailed段にはretryがないため、同じ元modelを保持して再開する追加契約を
別slice ux1/pipeline-retryで検証中。実MCP再開前であり登録完了とはしない。

残り5modelのHost03447db06990は終了。カフェ/花屋はmodel succeeded/export待ち、
本屋/NPC2種はresource_wait_timeout。新規pipelineを乱発せず、同じfailed Jobを指定した
明示retryで1件ずつ再開予定。生成元7画像は保持する。

Webのみの実装をOpenCode/Qwen3.8-27Bに開始、Hoste67c69a17071、
session ses_f34235b71ffep1Np1UF6Cgo821、receipt web-job.json。
06b promptは実GLBの最終URLを読むHTML/CSS/JSだけを編集し、MCPや別agent呼出しはしない。
欠けたGLBは読み込み失敗として扱い、旧不良rigやprimitiveへの代替は禁止。
project BRIEFの古い認証待ちを履歴表示へ直し、assets/manifest.jsonに7納品先を固定。
物理電話/最終HTML/性能/移動時接地/残りモデルの品質はNOT TESTED。

0.33.13の明示retryを署名公開・ローカル適用後、Web実装と独立したCPUだけの
主人公1024再rig＋完成済みカフェ/花屋exportをHost718d8c07704dで開始。
receipt rig-ready-exports-job.json、prompt07a。GPUを使う本屋/NPC再生成はこの工程に含めない。
Web Jobe67c69a17071はまだ実装中。中間app.jsのfoot座標/店舗clone/カメラなどの
sourceレビュー指摘はmaintenance/web-review-before.mdへ保存し、書込み終了後に実描画で再検証する。
中間実装の存在をHTML完成とは扱わない。
