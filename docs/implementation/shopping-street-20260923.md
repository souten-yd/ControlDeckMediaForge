# 歩ける商店街: OpenCode / Qwen3.8-27B / MCP 制作受入

Status: IN PROGRESS。主人公の参照画像1枚を実生成・目視確認済み。3D/HTMLは未完了。

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

## 現在の実測（2026-09-23）

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
