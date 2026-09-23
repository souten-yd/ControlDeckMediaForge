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
