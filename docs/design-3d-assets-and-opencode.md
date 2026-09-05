# 3Dアセット・画像材質・OpenCodeの統合設計

Status: 実装目標 / 新契約は未公開  
Date: 2026-09-05  
上位設計: [統合3D Studio](design-3d-studio.md)

## 1. 既存機能を基礎にする

既存の `image.generate` / `image.edit` / `media.inspect` / `media.pack` とasset/provenanceを再利用する。
G8の `asset.pack`、`profile=3d.project.glb` は入力GLBを固定compilerで加工し、
`asset.glb`、`manifest.json`、`preview.png` のZIPを返す契約を維持する。
この既存profileへ任意Pythonや任意Blender operatorを追加しない。

3D制作は同じMediaForge内のdomain serviceから既存画像jobを呼ぶ。
HTTPで自分自身へ特権callを回す、二重の画像API・画像DB・コピー用アドオンを作る必要はない。
SonicForgeのDBやPythonをimportしない。将来音声が必要なら公開Host契約で別連携する。

## 2. assetと制作working copy

| Entity | 役割と不変条件 |
|---|---|
| 既存Asset | immutable bytes、hash、owner、MIME、provenanceを持つ。画像と3Dで共通 |
| SceneDocument（追加） | 制作の論理ID。現在の採用revision、名称、タグ、collection、単位を保持 |
| SceneRevision（追加） | `.blend` source asset、parent revision、runtime version、依存画像、作成jobを固定 |
| WorkingCopy（追加） | revisionから作るsession専用編集領域。single writer lock付き |
| MaterialBinding（追加） | object/material slotの安定IDと画像asset、UV、色空間等の対応 |
| Derivative（既存関係を拡張） | GLB、thumbnail、turntable、LOD、collisionと生成元revisionの関係 |
| ValidationReport（追加） | validator版、検査項目、pass/fail/not_checked、統計、警告 |

既存asset必須fieldを変えず、追加metadata/schema versionで3D情報を表す。
MediaForge内の `asset_...` とHostの `asset:` / `grant:` は異なるID体系であり変換を推測しない。
Hostへの配置は既存output commitとreceiptを使う。生pathをAPIへ持ち込まない。

`.blend`は制作保存形式、GLBはビューワー・配布用派生物とする。
`.blend`をブラウザで直接解釈しない。外部Blender読込時はembedded scriptを自動実行しない。
元版を保存してから新しいBlender版で開く。新しい版の保存を旧版で開けるとは保証しない。

## 3. import/exportと検証

| 対象 | 初期方針 |
|---|---|
| GLB入力 | 既存64MiB制限・URI禁止・構造検証を維持 |
| 画像 | 既存import/decoderとサイズ制限。材質用にも同じassetを参照 |
| `.blend`入力 | 新機能。隔離runnerへstageし、autoexec無効で検査。初期上限256MiB案 |
| GLTF+外部ファイル、FBX、OBJ、USD | 現行G8入力へ暗黙追加しない。形式別の後続受入後 |
| 出力 | 初期GLB・PNG/WebP・既存ZIP profile。制作版として.blendも保持 |

256MiB等は新形式の設計値で、既存GLB/API上限を緩める値ではない。
現在のworkspace JSON request 1MiB、preview 12MiB、Host一般response上限があるため、
大型.blendはbounded chunk uploadまたはHost scoped file streamとして別設計・試験する。
base64で一枚のWebSocket JSONへ詰めて上限を一括解除しない。
uploadはowner、upload ID、総量、chunk checksum、offset、期限、cancelを持ち、最終hash確認後にimportする。

検査項目: finite座標、node/triangle数、accessor範囲、外部URI、texture寸法・総画素、
UV有無、材質slot、単位・軸・原点、animation duration、許可extension、license/provenance。
Blenderの成功終了だけで検証済みにせず、既存独立GLB/PNG検査と再importを組み合わせる。
形状の美しさ、UVの目立つ継ぎ目、指示適合は別の人手/画像評価で記録し、未確認はnot_checked。

## 4. 軽量3Dビューワー

ブラウザWebGLのGLB viewerを遅延ロードする。初期実装はThree.js 0.185.1の
`WebGLRenderer` / `GLTFLoader` / `OrbitControls`をMIT license notice付きでMediaForge bundleへ固定する。
npm registry integrityは
`sha512-5aojFCXKwnjBRZvUnt3WFfEcvUJgkN5LlijRFN95hMy8WVkG4I0QNcJE+OuWvuJ0bOdStrbfXn0pkd6/QyiAlg==`。
外部CDNへ依存せず、bundle生成はlockfileから再現し、生成済みviewer moduleのhashも検査する。
DRACO/KTX2/Meshopt decoderは同梱せず、required extensionをbackend検証が受理した場合だけ追加する。
外部CDN・外部texture URIを自動取得しない。認証付きasset deliveryから必要なbytesだけを読む。

必須: orbit/pan/zoom、fit、背景・light preset、material/wireframe、bounding box、triangle数、
animation play/pause、前後版比較、材質slot選択、画像差替えpreview、Blenderで編集。
追加: normals/UV表示、LOD比較。unsupported extensionは理由を出して検証済みpreviewへ戻る。

viewerへ渡すGLBは64 MiB以下、textureは1辺8,192 px以下かつ合計67,108,864 px以下とし、
展開後RGBA textureの上限を256 MiB相当に固定する。大型sceneは低LOD派生物を使う。
モデル切替・画面退出時にgeometry/material/textureをdisposeし、不要なfetchをabortする。
非表示タブは描画loopを止め、WebGL context loss/recoveryを扱う。
同一assetのimmutable hashでcacheを再利用する。Libraryはthumbnailとmetadataを先に取得する。
viewer上の材質previewは未保存と表示し、採用操作でserver revisionへ確定する。

opaque iframeではGLB bytesを生URLやserver pathで渡さない。既存認証WebSocket上でconnection-scopedな
opaque viewer handleを発行し、512 KiB以下のchunkとして読む。project ZIPはexact entry/hashを検証して
session専用stagingへ一度だけ展開し、close・asset切替・socket切断で回収する。standalone development
mirrorも同じdomain validationを通す。Library 50件の表示はGLB本体を一括取得しない。

## 5. 画像から材質への流れ

1. scene revision、対象material slot、UV set、用途を選択。
2. Libraryの既存画像を指定、または同じMediaForgeの画像生成・編集を依頼。
3. 画像jobの成功assetをimmutable参照として受け取る。
4. 型付きMaterialBindingを作り、Blender workerで適用。
5. GLB派生物とpreviewを生成、構造・色空間・依存を検証。
6. 前後比較して採用し、新しいSceneRevisionへ確定。

MaterialBinding案:

| フィールド | 意味 |
|---|---|
| material_slot_id / object_id | 名前変更で壊れないdocument内ID |
| channel | base_color / normal / roughness / metallic / ao / emission / alpha |
| image_asset_id | 既存MediaForge画像asset ID |
| uv_set / transform / wrap | UV index、scale/offset、repeat/clamp |
| color_space | base color等はsRGB、normal/roughness等はdataとして明示 |
| normal_convention | OpenGL/DirectXを明示し必要時に変換 |
| alpha_mode / cutoff | opaque / mask / blendと閾値 |
| source_revision_id | 割当て元の版。競合検出に使用 |

base colorを生成しただけでnormal/roughness/metallicも正しく得られたとは扱わない。
PBR channelは実際に存在・検査したものだけを表示する。データ画像へ色補正を暗黙適用しない。
UVなしは「UVを作成」工程を明示し、投影mappingとの違いを示す。
UDIM、複数材質atlas、bake、seam処理は後続profileとして追加し、元画像を上書きしない。
材質が参照する画像の削除時は依存revisionを示し、参照中blobをGCしない。

## 6. OpenCode経路

OpenCode → ControlDeck `controldeck_addons` stdio MCP → MediaForge agent contribution → durable job。
ユーザーのグローバルOpenCode configを書き換えず、Hostの実行単位config・署名identityを利用する。
利用者のpromptをshell commandやPython式として直接連結しない。

既存の `media.capabilities`、`media.generate`、`media.inspect`、`media.pack` は継続。
画像生成・既存G8加工は現在のschemaで呼ぶ。新しい制作コマンドは加法的schemaの設計・互換試験後に公開。

提案する追加surface（名前は公開前に衝突検査し固定。現時点で利用不可）:

| 提案tool | 入力と役割 |
|---|---|
| `media.scene.create` | validated scene recipeから新規sceneを作る |
| `media.scene.edit` | scene ID + base revision + typed operationsで修正 |
| `media.scene.material` | scene/revision + MaterialBindingの検証・適用 |
| `media.scene.snapshot` | 所有sceneの安全な構造・preview参照を返す |
| `media.scene.export` | 固定profileでGLB等のassetを生成。配置はmedia.pack |
| `media.job.status` / `media.job.cancel` | 長時間jobの状態と取消。既存公開surfaceがあればそれを再利用 |

workflowにも同じdomain orchestrationを投影し、UI・agent・workflowで別実装を作らない。
ツール数をBlender全operator数まで増やさない。scene recipeと操作schemaが機能の本体。

## 7. 型付き制作とExpert script

通常モードではtrusted adapterに渡す型付き操作を採用する。
初期対象: primitive、寸法・transform、安定IDでのobject参照、bounded modifier、材質割当て、
UV preset、light/camera preset、保存、export。許可されない操作や未実装機能は明示エラー。
OpenCodeは現在のscene snapshotとschemaからrecipeを組み立て、失敗箇所を限定して修正する。

Expert scriptは別権限・別schema・別capabilityとして後続提供する。
`asset.pack + 3d.project.glb`を任意script実行へ変更しない。

- scriptは監査可能なartifactとして保存し、hash、生成元、適用scene版を記録。
- 任意Pythonは「安全な文字列検査」でsandbox化できない。AST/禁止語検査は補助に限定。
- OS境界でnetwork、credential、home、Host filesystemを遮断し、read-only runtimeと専用workだけを渡す。
- timeout、memory、CPU、process数、出力容量、process group終了を強制する。
- OpenCode自身の自由なshell経路から隔離を迂回しないよう、当該制作実行のtool権限も制限する。
- Blender GUIにもPython consoleやfile browserがあるため、同じOS隔離を適用する。
- 隔離ゲートが通らない機器ではExpertを公開しない。typed recipeと既存G8は継続可能。

## 8. 長時間job・認証・再実行

Host agent経路の現行120秒上限へ長時間GUIやrenderを詰め込まない。
開始callはdurable MediaForge jobを確定し、Host Runtime `detached=true` の所有child Jobと
正規job credentialを取得した後、job referenceを早く返す。親call完了後もchildの所有者を保持する。
この経路の長時間実行は実装受入で検証し、コード存在だけで保証しない。

- job ID、Host job ID、owner、input hash、runtime pin、base revision、stage、idempotency keyを永続化。
- Host側のJob表示・cancelとMediaForge側journalを同期する。終端updateはoutboxで再送可能にする。
- credentialは現在有効な間にHostのjob credential refreshを使う。期限切れtokenから自己再発行しない。
- CPU-only setup/sessionにも同じrefresh経路を使う。core再起動後に正規identityが戻らなければ
  interrupted / 再認証待ちとし、安全に停止する。ブラウザCookieを代用品にしない。
- 既存public state enumは不用意に変更しない。詳細stage/wait_reasonは追加metadataとして扱う。
- cancelはqueuedなら即時取消、runningなら所有runnerへ通知、終了確認後に資源回収。
- retryは成功済みの画像assetを再利用し、失敗stageから新しい試行として開始。
- LLM提案・画像生成・Blender加工はstageごとのBroker管理。別stageのleaseを保持したまま待たない。
- 新revisionのcommitはbase revision一致を条件にする。競合時は上書きせずbranch revisionを提案。

## 9. 公開・復旧・provenance

jobの中間成果物はstagingへ出力し、検証後だけimmutable assetとして登録する。
失敗時に採用revisionを変更しない。partialは成功assetとしてLibraryへ並べない。
出力には入力asset/hash、recipe/script hash、Blender/worker版、生成画像job、seed/設定、
検証結果、手作業保存の区別、license情報を残す。秘密値・生Host pathは含めない。

autosave、正式revision、export derivative、cacheは別の保持policy。
バックアップはDB・asset・依存画像・runtime pin・recipeを一貫したsnapshotとして扱う。
restore時にmissing dependencyを検出し、画像や.Blendの実体がない状態を復旧成功と表示しない。
