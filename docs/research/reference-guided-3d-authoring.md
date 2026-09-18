# 参照画像から曲面・アニメーション付き3Dへ

調査日: 2026-09-18。状態: 設計採用・実装・署名0.28.86導入済み。実LLM/VLM pilotは実施、造形品質FAIL。
[実測比較と残gate](../implementation/installed-reference-acceptance-20260918.md#completed-short-request-pilot-and-quality-comparison)を参照。R2全27試行は未実施。

## 結論と対象

MediaForgeで同じ個体の正面・側面などを生成し、Blenderの形状制作を拘束する方法は
採用可能である。ただし2枚から正しい立体・関節topologyを一意に復元できるわけではない。
画像は設計資料、曲面生成は型付き操作、接合・変形は実geometry、見た目は実renderで検査する。
画像生成の精細さを、そのまま3D精度やアニメーション品質と呼ばない。

利用者が選択した範囲は、曲面のあるstylizedなゲーム表現、アニメーション込み、
恐竜専用ではない汎用制作基盤、最初の表示受入先はBlenderとMediaForge viewer。
Unity/Godot/Unrealの実受入は今回の初回gateには含めず、既存GA計画の残件として維持する。

実比較元は[OpenCode T-Rex試験](../implementation/trex-opencode-20260918.md)と
[PR536](https://github.com/souten-yd/ControlDeckMediaForge/pull/536)。
既存local LLM→MCP→Blenderは実行でき、自然言語修正で尾・足先は改善したが、
箱型の胴と隠れた歯が残った。これはprimitive制作の実測であり、
新しい曲面・VLM評価・rigの成功証拠ではない。

## 方法の比較と選択

| 方法 | 有効な用途 | 制約 | 判断 |
|---|---|---|---|
| 参照画像＋loft/sweep/control cage | 形状・比率を制御したstylized生物、角、尾、道具 | 見えない形とjoint loopsを設計する必要 | 主経路 |
| 既存mesh/rigの利用と変形 | 共通体型・asset family、安定した変形 | 利用権・由来・適合性が必要 | 正規importとlineageで併用 |
| image-to-3D / multi-view-to-3D | 素早い形状候補 | topology、遮蔽部、GPU互換、cleanup費用 | optional G9比較 |
| sculpt＋retopology | 複雑な高密度形状 | 自動化範囲と変形用low-poly制作が別 | 後続M3/M4の補助 |
| photogrammetry | 実在する同一物体の多数写真 | 独立生成した2枚では対応点・カメラが矛盾 | 実写真の別用途 |
| voxel union/remesh | 接合やsculpt用high-poly | 関節のedge flowを保証しない | 補助、animation-ready判定不可 |

### 一次資料とローカル適合性

外部公称値はこのPCの実測ではない。以下の全候補はR9700上の性能・品質・安定性が
**NOT TESTED**。重みの取得、利用同意、runtime採用は本調査から自動実行しない。

- [Hunyuan3D-2 multiview example](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/examples/textured_shape_gen_multiview.py)
  はfront/left/back画像辞書をHunyuan3D-2mvへ入力する実装例を持つ。
  2mvの形状候補を比較対象にする。複数画像を入力できることと整合しない画像を解決できることは別。
- [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
  の公称VRAMはshape 10GB / texture 21GB / combined 29GB。
  CUDA依存を含むため容量だけでROCm可と判断しない。2mvの必要量と混同しない。
- [TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
  は公式要件がLinux / NVIDIA GPU 24GB以上。品質比較候補だがAMD可用性を主張しない。
  本体と依存物・重みのlicenseを採用時の固定revisionでそれぞれ確認する。
- [Stable Fast 3D](https://github.com/Stability-AI/stable-fast-3d)
  はCPU実行指定SF3D_USE_CPU=1と既定GPU約6GBの説明を持つ。
  CPU経路は候補だが実用時間は未測定。重みはgatedで、同意前に取得しない。
- [Wonder3D](https://github.com/xxlong0/Wonder3D)
  は整合した複数視点RGB/normalからの復元という参考になる。
  CUDA系依存を持ち、MediaForgeの既存画像生成が同じ整合性を持つとは扱わない。
- [COLMAP tutorial](https://colmap.github.io/tutorial.html)
  は同一物体の重なりのある写真と十分な視点を前提とする。
  独立した生成画像の正面・側面を通常の写真測量へ渡す案は主経路に適さない、というのが本計画の判断。
- [UniRig](https://github.com/VAST-AI-Research/UniRig)
  は自動skeleton/skinの候補だがCUDA系の依存を持つ。初期rigは既存armature/bindを使い、
  新runtime依存にしない。自動rigの存在を変形品質の受入に代用しない。

## ReferenceSetと制作ループ

最初にcanonical designを1枚決め、既存image.generate/editと利用可能なreference条件付けで
同じ個体のfront/side/back/three-quarterを作る。独立したtext-only生成を4回行って
同じ個体と決めつけない。正投影、同じpose/比率/色/床面を依頼し、結果を検査する。
矛盾があれば修正またはneeds_reviewとして停止し、暗黙に平均した形状を合格にしない。

ReferenceSetは既存Assetに属するversioned manifestを目標とする。
viewごとのimage asset ID/hash、軸、scale、landmarks、part/attachment意図、由来、license、
生成条件と承認状態を保持する。生path、外部URL、モデル名必須の公開契約にはしない。
sceneとの参照関係は加法的に追加し、画像差替えは新ReferenceSet revisionとする。

```text
accepted references → bounded shape → deterministic audit
 → fixed multi-view observations → image-based review
 → up to 3 local issues → candidate revision → same-condition comparison
 → clay shape gate → UV/material → rig/weights → pose → clips → viewer
```

Observationはsource revisionとcamera/light/scale/renderer条件を固定するdurable Job。
通常材質、clay、silhouette、object IDと必要部位のcloseupを既存画像Assetへ保存する。
reviewは実画像をHost vision.analyzeへ渡し、対象ID・画像根拠・修正候補を構造化する。
VLM unavailable、画像未取得、timeoutを合格に変換しない。数値auditと視覚判断は別記録。
同じissue群で2回改善しなければ停止し、悪化した候補を自動採用しない。

形状はloft断面、sweep経路、制御点編集、boundary bridge、subdivisionの小さいパラメータで
指定し、trusted workerがmeshへ展開する。topology変更後の古いselectionは拒否する。
生物control cageには肩/股/膝等の変形loopを設ける。恐竜templateだけを埋め込まない。

## アニメーション受入

part graphから明示skeleton、既存auto-bind、局所weight set/smooth/normalize、脚IKとbakeへ進む。
既存rotation trackを保持してtranslation trackを加法追加する。
初期恐竜の目標は24fps、idle 2秒、in-place walk 1秒、attack 1.5秒。
idle/walkはloop、attackはnon-loop。durationは終端frameを含むkeyframe時刻で定義し、
歩行接地・loop速度・関節制限を実pose/実clipで確認する。
納品はdeform skeletonとbaked clips。root motion、表情morph、retargetは後続。

## 比較試験と合格条件

T-Rex、四足生物、小物を同じ汎用操作で制作する。
text-only baseline / reference-guided / reference＋curve＋observe-reviewの3条件を
同一briefで各3試行し、成功件数、修正回数、wall time、peak memoryを記録する。
未測定を0にしない。旧T-Rexは歴史的baselineであり、3試行分の代用ではない。

T-Rex全長3m±5%は新試験の目標値。接続・前方・接地・口/歯の可視性を確認する。
rig後は未重み頂点、影響数、weight和、poseでのcollapse/離脱/貫通を検査する。
GLB実再import、viewer clip再生/loop/切替/停止/解放を別gateで記録する。
owner/revision不一致、未対応VLM、resource待ち、取消、再起動、過大入力のnegative受入を含める。

導入順は[実装slice表](../implementation/g8-high-quality-mcp-3d-assets.md#19-reference-guided-authoring-slices-2026-09-18)。
現時点でReferenceSet・observe/review・curve編集・新weight/IKの実装完了を宣言しない。
