# MCPのGLB軽量化設定を公開する

## 実際の失敗

0.33.14 installed、通常Host OpenCode/Qwen3.8/MCP Job5304c9bb2c0cで、
既存の店GLBを3万trianglesへ軽量化するasset.pack要求を実行した。
公開job schemaのconstraintsはReferenceSetSpecの項目だけを明示し、
compilerが既に受けるcompile_optionsはadditionalProperties経由でしか表現されていなかった。
LLMがmedia.generateの空引数を8回反復した後、canonical_asset_id等の参照設定を入れ、
invalid_compile_optionsになった。所有Jobを通常APIで取消し、実unitのinactive/MainPID0を確認。
生成済み画像と元GLBは保持した。緩いJSONschemaの入力受理だけではLLMの発見可能性を証明できなかった。

## 修正と確認

schemas/job-request.jsonへconstraints.compile_optionsと既存CompileOptionsの$defsを加法追加。
型は実装のmodel_json_schemaと一致させる。既存compilerの実行契約/既定値/保存データは不変。
ReferenceSetSpecとの用途を説明し、docs/api.mdも同期。2テストで明示型、上限内配信、
3万triangle入力、最小値違反とadditionalProperties=falseを確認。
既存compilerを含めたfocused gateは17passed。

実source serviceを隔離data/loopback19135で起動し、GET /schemas/job-request.jsonを取得。
HTTP200、16186B、SHA256 a232fbcd69463f5a93e3c46a6f42a21bffa79eae34a2f91fffb5f2ebbc001bfb。
parsed schemaはsourceと一致し、Hostの64KiB上限内。TestClientだけの受入にはしていない。

初回./mf.sh testは2472passed/1failed/3warnings/465.13秒。
失敗は既存Blender sessionの40ms idle timeout試験がreadyより先にstoppingへ進んだもの。
変更箇所はschema/版数/文書だけでsession処理は不変。関連fileの独立再実行はexit0。
負荷の影響と断定はせず全体gateを再実行し、2473passed/3warnings/341.53秒、exit0。
以後の変更は実測記録のみ。

証跡: maintenance/shopping-street-20260923/compile-discovery-{focused,full,flake-recheck,full-recheck}.log、
compile-discovery-source-http.json。signed release/local update、実Host projected MCP schema、
実OpenCodeから3万triangle GLBを作る再受入はNOT TESTED。


## 0.33.15 signed release and local update

PR639 merged f11bd3388e4b07cf98eb3ce90201d646b21614c8。製品sourceは最終2473tests gateから不変。
固定commitから構築し既存publisher鍵で署名。bundle38,061,607B、SHA256
3141c62c3cff49682c39f5c15fe1c41cc7ebe3af2ab9d8f81b637dd43d4315f0。
署名/改ざん拒否、6tar entries/243embedded entries、frontend/worker/schema source一致を確認。
新規dataの実packageは0.868546秒でsetup_required。実runtimeなしをunavailableと正しく表示。
公開releaseの4artifactを再取得して同じ検証を通過。

MediaForge active Job/session0で通常ControlDeck feature update、その後restart。
current versions/0.33.15、PID178386、healthyまで0.827180秒。
更新前1576 Asset metadata一致、代表3Assetの実HTTP content SHA一致、
served frontend/source一致、従来3D.image_to_3d capability一致。
実installed GET /schemas/job-request.jsonは16186Bでcompile_optionsの型を明示。
証跡maintenance/release-0.33.15-20260923。既存Pixal/Trellis runtime設定は変更していない。

実OpenCode/Qwen/MCPの明示再実行Job25f23f603894を開始し、runningを確認。
新promptはinputの不要なrole項目も除去し、最新版tool_contractの再確認を指示。
実MCPの軽量GLB出力・納品・最終商店街受入はまだNOT TESTED。

## 0.33.15の実OpenCode再実行完了

Job25f23f603894はsucceeded。4店舗を実MCP asset.packで各30000三角形へ加工し、
通常grant/media.packでprojectへ納品。独立検査で全ZIPの固定3entry、ZIP Asset SHA、
manifestの元GLB SHA、展開GLB SHA、最終project GLB SHAが一致。2texture/店舗を保持。
証跡shopping-street-20260923/shop-packs-independent.json、project/evidence/shop-packs-final.json。
LLMがoutput.format=zipを省略した3要求はunsupported_pack_profileで失敗し、明示後に成功。
省略時の分かりにくいエラーは未修正。納品成功を最終商店街描画の品質受入とはしない。
