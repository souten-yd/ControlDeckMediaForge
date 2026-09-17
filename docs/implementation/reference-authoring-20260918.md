# 参照画像制作計画とM1前提試験 — 2026-09-18

## 設計反映

[調査・採用判断](../research/reference-guided-3d-authoring.md)と
[slice表](g8-high-quality-mcp-3d-assets.md#19-reference-guided-authoring-slices-2026-09-18)を追加し、
base-plan §25、integration §18、game asset設計と同期した。
対象は汎用の曲面stylized制作、animation込み、Blender＋MediaForge viewer受入。
R0文書は実装済み。ReferenceSet/observe/review/curve/weight/IKの新機能はまだ未実装。

## M1実OpenCode受入

installed MediaForge0.28.84 / OpenCode1.18.30 / local Qwen3.8-27B / Blender4.5.13。
Host MCP tools/listは24 tools、実media.capabilitiesはmesh.createを含む16 operations。
image.single_reference_edit/multi_reference_edit/semantic_reviewはavailableと応答したが、
今回その実生成・実画像評価は行っていない。3d.image_to_3dはplanned_for_g9/unavailable。

最初の標準M1 promptは487.794秒、skill/capabilitiesの2 callsのみ、納品0。
session ses_f4e54e525ffeWymkZJZYN3h3ZS / run ce517d8f。
provider header timeout300秒後、tool-call stream減少の500エラーが
23:26:23.018 / 23:27:05.362 / 23:27:38.057 UTCに3件発生した。
同じ不改善反復として所有OpenCode子1793154をTERM、runner exit1/child -15。
生成途中の引数を補完して実行していない。

実runtime pathはllama-gpu-b10917/rocm/extracted/bin/llama-server。
既存実測のbuild b1-8ea2902に対応する
[固定source common/chat.cpp](https://github.com/ggml-org/llama.cpp/blob/8ea290247c87ced2ab245b056ffe96dbcf90d36c/common/chat.cpp#L249)
の差分検査はtool_callsの減少時に同じ例外を投げる。
これは発生箇所の照合であり、model/decoder/parserの根本原因特定や修正ではない。

比較試験はpromptの形状説明だけを「6頂点、三角柱の側面3 quad＋端面2 triangle」へ変更。
頂点座標/面indexはLLMが決定し、require_closed=true、2 operations、1 create、既存verifierを維持。
schemaにないmaterial.nameを加えないこととtool前の説明不要を付記した。
同時に複数条件を変えたため成功原因を頂点数だけと断定しない。
既存runnerをrunpyから起動し、その実行だけのpromptを置換した。製品/Host/global設定変更なし。

- session: ses_f4e4d06b1ffefgECLiGK8NngLH
- elapsed: 183.572秒、8 tool calls、exit0
- job: job_cd5f760debc045c6a306095dc29aa9d0（succeeded / host_terminal_sent=true）
- scene: scene_882422607ecb44b4bb9c481ea83e121c
- revision: revision_5fcb40bdec674e4a93eeb67bdf123ba8
- source: asset_b127700e6e524fa49ac84f358e1a6ba7
- GLB: asset_3ed51b30a03d40c39a45ad94399f9d73
- delivery: MF3DS-M1-SixVertex-20260918/exports/armor.glb、1260B
- SHA256: 2efa90962d694a1050e311d592dcca207dbac666ac774719c7fa3f64decf2c28

実行は既存scripts/3ds_opencode_flow_e2e.pyの--director-authored-mesh経路。
診断wrapper/promptは上記projectのevidence/run_six_vertex.pyとprompt.txtへ保存。
実行環境はCONTROL_DECK_CONFIG=/data1tb/ControlDeck/app/config/config.yaml、
PYTHONPATH=/data1tb/ControlDeck/app/backend、Host診断用.venv/bin/python。
MediaForge製品にHost importを加えていない。

独立検証:

```bash
PYTHONPATH=backend .venv/bin/python scripts/3ds_verify_opencode_flow.py \
  --evidence-dir /data1tb/ControlDeck/CodeDEV/MF3DS-M1-SixVertex-20260918/evidence/six-vertex \
  --database /data1tb/ControlDeck/data/feature-data/media-forge/data/media-forge.sqlite3
```

exit0 / verified=true。実skill読込→capability→require_closed付き作成→Job成功→
snapshot/export同revision→grant/receipt→実file/metadata/provenance hash一致を検証した。
managed Blender4.5.13をbackground/factory-startup/disable-autoexec/python-exit-code1で起動し、
実納品GLBを再import。1 mesh / 6 vertices / 8 triangles、寸法0.400000006/0.079999998/0.5mを確認。
evidence/inspect_glb.py、six-vertex/reimport.jsonに保存。

M1の小さいauthored closed mesh操作・installed MCP/LLM納品gateはこの試験でPASS。
一般の長い引数stream安定性は未解決。高品質、VLM、参照画像、変形、animation、engineはNOT TESTED。
M2の着手条件を満たすが、恐竜の品質向上や計画全体の完了ではない。

## 文書sliceの検証

隔離worktree /tmp/mediaforge-reference-plan-20260918、branch ux1/reference-guided-3d-plan。
PR536の30e2971をbaseとし、利用者rootのfeat/release-gpu-on-demand/9304129は保持。
./mf.sh test: exit0 / 1949 passed / 3 skipped / 2 warnings / 206.37秒。
3 skipはworktreeにbundle-build runtimeが無かった署名試験。
既存MediaForge bundle-build venvを参照して同3件を追加実行し全PASS。
Host venvをcore testへ流用していない。新model重み、runtime、公開schema/tool追加なし。
