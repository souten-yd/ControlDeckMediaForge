# G8 / GA 拡張 — 高品質MCP 3Dアセット制作計画

Date: 2026-09-13
Status: implementation plan / PR #526 の M1 基盤を前提に、M2以降の高品質化を具体化
Target: ControlDeckMediaForge

関連する正:

- `docs/base-plan.md`
- `docs/design-game-asset-authoring.md`
- `docs/research/ai-blender-game-asset-authoring.md`
- `docs/agent-3d-authoring-guide.md`
- `docs/implementation/g8-3d-studio-plan.md`
- `docs/controldeck-integration-plan.md`

本計画は既存GA-0〜8を置き換えない。利用者が要求する「高精細キャラクター、アニメーション、髪、草木、道具、武器、防具、魔法、ロボット、機械、乗り物、建物等を、MCPから高品質に制作できる状態」を、既存の型付きMediaForge/ControlDeck Agent MCP経路で完成させるための実装順・品質gate・アセット群別手順を固定する。

---

## 0. 現在地

2026-09-13時点のmainはBlender runtime / scene revision / Web Blender / Library / material binding / OpenCode制作 / grant配置まで既に大きく成立している。PR #526 `ux1/3d-authored-mesh` では、既存recipeへbounded `mesh.create` と制作ガイドを加えるM1基盤が進行中である。

PR #526の実測では、実Blender 4.5.9で28 mesh / 2,312 vertices / 4,512 triangles / 56 operationsを0.494秒で構築し、81,264 bytesのGLB再importでも28 mesh / 4,512 trianglesを維持した。一方、生成した人型はblockoutとしては成立しても、髪根元・房、顔、手、衣服、防具の高品質目標には届いていない。したがって、raw頂点を増やすだけではなく、**観察→診断→局所修正→表面→変形→実engine**を次の主経路にする。

現段階でBlenderMCP等の別常駐addonをMediaForgeへ追加しない。外部Blender MCPの知見は調査・操作設計に利用するが、実行経路は既存のControlDeck Agent MCP → MediaForge typed recipe → durable Job → immutable revision → Blender workerを維持する。任意Pythonは通常制作のfallbackにしない。

---

## 1. Web / コミュニティ調査から採用する判断

Community項目は経験談・実装例であり製品性能の証拠ではない。採用判断はBlender/Khronos等の一次資料、既存MediaForge境界、実機受入を優先する。詳細な一次資料・研究・外部repoの固定点は`docs/research/ai-blender-game-asset-authoring.md`にも記録する。

### 1.1 直接LLMに「完成品を一発生成」させるのは主経路にしない

Blender MCPのコミュニティ報告では、LLMはblockout、配置、材質の一括変更、簡単なrig、camera/previzでは有用だが、高品質な人物や複雑な3Dでは「それらしく見える」段階を早く合格扱いしやすいという報告がある。実務例でも、自然言語だけで全3D工程を完遂するより、blockout・modular set・既存rig・atlas・反復修正を組み合わせる方が安定している。

採用する:

- 一発巨大recipeではなく、短いrevisionごとの工程。
- 見た目の合格は複数視点の実画像で行う。
- 形状、UV、weight、clip、collision等は数値auditを権威にする。
- 人の最終確認を残せる。VLM点数だけで完成扱いにしない。

### 1.2 「auditで異常箇所を絞ってから多視点で見る」を採用する

2026年のBlender MCPコミュニティでは、gap等のmesh auditを先に実行し、異常箇所だけを識別しやすいdebug materialで描画し、複数の計算済み角度からAIへ見せることで、主観的な全体画像だけより修正しやすいという報告がある。

MediaForgeではこれを一般化して採用する。

```text
revision
  -> deterministic audit
  -> issue set (object/element/bounds/severity)
  -> diagnostic render mode
  -> focused multi-view image assets
  -> VLM / human critique
  -> typed bounded edit
  -> new immutable revision
  -> same-condition re-evaluation
```

VLMへ毎回全sceneを見せない。問題箇所、対象ID、camera、比較元revision、debug modeを固定する。

### 1.3 MCP toolを100個そのまま常時露出しない

コミュニティ実装では、Blenderの機能を100+ toolへ分解するとtool schema量が大きくなり、categoryのlazy discoveryが必要になるという実装例がある。MediaForgeは既に`media.scene.*`とrecipe operationを使うため、この方向を強化する。

採用する:

- MCP tool数を増殖させず、`media.capabilities` / scene operation catalogからカテゴリを発見。
- recipe operationは型付き・bounded・versioned。
- agentは今必要なカテゴリだけschema/guideを読む。
- 「Blenderに機能がある」ことを「MCP operationがavailable」と読み替えない。

### 1.4 modular / family制作を優先する

コミュニティのゲーム制作例では、一品ずつ独立生成するより、共通rig・共通material・modular prop set・variantを作る方が生産性と一貫性が高い。MediaForgeでも`AssetFamilySpec`を導入し、武器variant、兵士variant、建築kit、草木speciesなどを共通基盤から派生させる。

### 1.5 髪はcurvesを制作表現の主経路にするが、納品表現は分ける

Blender 4.5の新hair systemはHair Curves / Geometry Nodesを中心にしており、Generate Hair Curvesはsurface + UVへcurveを生成できる。コミュニティでもmesh hairやhair cardsの制作元としてcurvesを使う例が多い。

ただしゲーム納品は別である。

```text
authoring representation
  hair curves / guide curves

runtime representation
  A: stylized mesh clumps
  B: hair cards + alpha texture
  C: engine-native groom（engine profileで実測した場合のみ）
```

「hair curvesが作れた」だけでゲーム対応としない。

### 1.6 Geometry Nodesはtrusted procedural generatorに向く

Blender 4.5のGeometry Nodesはmesh / curve / point cloud / volume / instanceを扱い、Repeat Zoneは建物階層の反復、For Each Geometry Elementはfaceごとの建物やcurveごとのtree生成のような用途を公式に例示している。Instance on Points / Distribute Points on Facesは大量草木へ適する。

任意node graphをLLMに自由生成させるのではなく、MediaForge管理のversioned trusted node-group templateとして使う。

### 1.7 生成3DモデルはG9候補であり、MCP制作の必須依存にしない

BlenderMCP upstreamはHunyuan3D等も統合しているが、MediaForgeの通常制作へ外部生成を黙ってfallbackしない。Hunyuan3D 2.1公式はshape 10GB、texture 21GB、shape+texture合計29GB VRAMを掲げる一方、公式実装はCUDA/PyTorch中心である。TRELLIS.2公式もLinux + NVIDIA 24GB以上を要件としている。AMD/Vulkan系community portは興味深いが、R9700/ROCm/Vulkanで固定commit・速度・VRAM・品質・licenseを実測するまでdefaultにしない。

G9を採用する場合も出力は完成品ではなく**candidate source**であり、同じretopo/UV/PBR/rig/LOD/engine gateへ通す。

---

## 2. 高品質の定義

「高品質」をtriangle数、texture解像度、VLM点数だけで定義しない。制作開始時に`QualityEnvelope`を作り、用途で必要な品質を決める。

```text
QualityEnvelope
  asset_class
  target_engine / renderer
  target_platform
  camera_distance / screen_coverage
  physical_scale
  topology_budget
  material_budget
  texture_budget
  alpha_budget
  bone_budget / max_influences
  animation_requirements
  lod_policy
  collision_policy
  socket/pivot requirements
  accepted_runtime_representation
  required_observation_views[]
  required_deformation_tests[]
  required_engine_tests[]
```

固定の「AAAなら100k triangles」のような万能値は置かない。対象ゲームの実測からbudget profileを作る。未指定なら安全な仮定として記録し、後で差替えられるようにする。

品質gateは必ず分離する。

| gate | 権威 | 例 |
|---|---|---|
| execution | MCP trace / durable Job | operationが本当に実行されたか |
| geometry | Blender/GLB deterministic audit | degenerate、non-manifold方針、gap、交差、triangle、bbox |
| visual | fixed multi-view images + human/VLM | silhouette、顔、髪、装備、表面 |
| surface | UV/PBR/bake audit | overlap、texel density、normal、channel、色空間 |
| deformation | weight + pose + clip audit | 肩、肘、膝、cloth/armor干渉 |
| delivery | package/grant/receipt | 実bytes/hash、依存asset |
| runtime | fixed engine/version | import、描画、animation、collision、性能 |

一つのgateを別のgateの代用にしない。

---

## 3. MCP実行モデル

### 3.1 toolは少数、operationはカテゴリ化

外部agentに100個以上のtop-level MCP toolを露出しない。現在のscene toolを維持し、recipe内部operationをカテゴリ別に増やす。

推奨カテゴリ:

```text
geometry.basic
geometry.local_edit
geometry.curve_surface
geometry.high_low
surface.uv
surface.material
surface.bake
hair.authoring
rig.skeleton
rig.weights
rig.constraints
animation.clip
procedural.environment
procedural.building
vfx.game
observation.render
observation.audit
delivery.game
```

`media.capabilities`はカテゴリのavailable/experimental/unavailable、schema version、limits、必要runtimeを返す。詳細schemaは必要カテゴリだけ取得できるようにする。exact transportは既存ControlDeck MCP projectionと後方互換を保つ最小形にする。

### 3.2 操作は対象・revision・増幅をboundする

すべての編集operationは最低限次を持つ。

- base scene / base revision。
- stable object/element selector。
- result amplification preflight。
- cancel/timeout。
- deterministic input digest。
- new immutable revision。
- independent output inspection。

任意operator文字列、任意`bpy`、host path、shellを通常schemaへ入れない。

### 3.3 AssetFamilySpec

シリーズ制作のために加法的なprivate orchestrationを用意する。

```text
AssetFamilySpec
  family_id
  base_scene_or_asset
  shared_style / materials
  shared_rig
  shared_sockets
  variant_axes[]
  allowed_parts[]
  random_seed_policy
  per_variant_budget
```

例:

- 剣: blade / guard / grip / pommelのvariant。
- 兵士: body rig共通、髪/顔/装備/色variant。
- house kit: wall/window/door/roof modules。
- grass species: blade mesh / material / density/seed variant。

variant生成でも既存assetを複製してlineageを残す。似たものを毎回ゼロから生成しない。

---

## 4. 観察・診断 surface（最優先M2）

高品質化の次の最重要sliceは「見えること」である。PR #526のblockout結果は、構造成功だけでは高品質にならないことを示した。

### 4.1 revision固定multi-view

新しい観察Jobを、既存asset/provenanceに乗せる。

標準view:

- front / back / left / right。
- front-3q / rear-3q。
- top / bottom（必要なasset class）。
- face / hands / hair root / weapon grip / wheel joint等のfocus views。

camera、FOV、距離、背景、照明、resolution、render modeをObservationSpecへ固定する。同じassetの修正前後を同条件で比較する。

### 4.2 diagnostic render mode

最低限次を段階実装する。

- neutral clay / matcap-like。
- silhouette。
- object ID / material ID。
- face orientation。
- wireframe overlay。
- normal/tangent visualization。
- UV checker / density heatmap。
- skin weight heatmap。
- collision/LOD overlay。
- issue-focus segmentation。

### 4.3 deterministic issue detector

画像より先に数値で検出できるものを列挙する。

- zero-area / duplicate face / duplicate vertex。
- unexpected open boundary（asset profile依存。cloth/leafは許可）。
- disconnected island。
- self / pair intersectionのbounded BVH check。
- tiny gap / intended attachment proximity。
- inverted normals / inconsistent winding。
- geometry amplification / modifier realized count。
- UV overlap / out-of-range / density spread。
- unweighted vertices / weight sum / influence count。
- bone/socket/pivot alignment。

検出結果はstable issue IDとbbox/affected IDsを返し、focused renderへ渡す。

### 4.4 VLM loop

VLMは実画像がある場合のみ使う。

```text
max 3 issues per turn
max 2 ineffective correction cycles per issue group
```

改善しなければ止める。VLMは`next_edit`として実配信schemaに存在するoperationだけを提案する。存在しないoperationを実行可能と偽らない。

---

## 5. 形状制作の拡張 M3

PR #526の`mesh.create`は基礎として維持し、以降は数千頂点の手書きを避けるため、局所編集と曲線/断面ベース生成を優先する。

### 5.1 local topology operations

候補operation family:

- selected vertices move / scale / relax。
- face/region extrude。
- inset。
- bevel edge group。
- bridge edge loops。
- subdivide / dissolve / merge。
- loop/ring selectionをstable queryから生成。
- Boolean union/difference/intersect。
- solidify。
- subdivision surface。
- shrinkwrap。
- limited decimate。
- normals / smooth-by-angle cleanup。

selectionは現revisionへbindし、topology変更後に古いindex setを再利用しない。

### 5.2 curve/loft/sweep

高品質な髪束、角、ケーブル、パイプ、剣の柄、車体フレーム、植物茎にはcurve/path + profileを使う。

- bounded polyline / Bezier guide。
- profile circle/oval/custom bounded section。
- taper / twist / radius along path。
- loft between bounded sections。
- sweep and optional controlled mesh conversion。

これによりLLMが大量頂点を直接列挙する必要を減らす。

### 5.3 hard-surface profile

武器、ロボット、機械、車両、建物へ共通:

```text
blockout
 -> mirror/array
 -> boolean openings/cuts
 -> bevel/chamfer
 -> controlled normals
 -> panel separation
 -> mechanical pivots/sockets
 -> high/low split if needed
 -> UV/PBR/bake
```

Booleanの存在だけで良いlow-poly topologyになると仮定しない。silhouetteとnormal bakeで評価する。

---

## 6. UV / PBR / bake M4

### 6.1 UV

必要operation:

- seam mark/clear。
- unwrap。
- pack islands。
- texel density report/normalize。
- UV overlap audit。
- secondary UV set（lightmap等。engine profileが必要な場合）。

smart projectはfallbackであり、顔、衣服、武器模様の最終解ではない。

### 6.2 material

標準PBRはGLBで扱いやすいmetal/rough workflowを基準にする。

- Base Color。
- Metallic。
- Roughness。
- Normal。
- AO。
- Emissive。
- Alpha（用途/engine profileで制約）。

色画像をnormal/roughness等へ流用しない。channelのsource、colorspace、UV set、asset hashを記録する。

### 6.3 high -> low bake

Cycles bakeをJob化し、source high / target low / cage / ray / margin / texture resolutionをschema化する。

最低限:

- tangent normal。
- AO。
- optional curvature/thickness等はgame pipelineで利用価値を確認して追加。

high-polyへゲーム用UVを強制しない。low-poly silhouetteがhighと大きく違う場合、normal mapで補えると誤認しない。

---

## 7. 高精細キャラクター M5/M6

### 7.1 キャラクター形状

工程:

1. body proportion blockout。
2. face/hands/feetの近接品質。
3. deformationを意識したretopo。
4. cloth/armor separate objects。
5. UV/PBR/bake。
6. hair。
7. rig / weights。
8. facial morph。
9. pose test。
10. clips。
11. engine acceptance。

voxel remeshはsculpt/high-poly cleanupには使えるが、最終deformation topologyの自動解とはしない。肩、肘、股、膝、顔のedge flowは別gate。

### 7.2 hair

3経路を実装する。

**Hair A — stylized mesh clumps**

curve/sweepで大きな房を作り、root connection、parting、tip、back silhouetteを観察する。最初に実装しやすく、GLBへ確実に載せられる。

**Hair B — hair cards**

curve guideからribbon/cardsを作り、MediaForge image assetをalpha atlasへ構成。card orientation、root density、mipmap edge、double-sided/alpha mode、overdrawをengineで検査する。

**Hair C — native hair/groom**

Generate/Interpolate/Curl等のHair Curvesをtrusted templateとして扱う。authoring/renderには使えるが、game deliveryは選択engineのgroom対応を実測した場合だけavailable。

### 7.3 clothes / armor

- close-fit cloth: bodyからweight transfer + correction。
- loose cloth: separate low-poly / bone-assisted / baked cloth候補。
- rigid armor: parent/socket/limited weights。

Data Transferをweight/UV初期化に利用できるが、最終品質にはpose matrixを必須にする。

試験pose:

- arms up / forward。
- elbow 90° / deep bend。
- crouch。
- leg stride。
- weapon grip。

penetrationとvolume collapseを数値＋画像で確認する。

### 7.4 rig

実装順:

- explicit armature hierarchy。
- bind auto。
- weights normalize/limit/smooth/set。
- weight transfer。
- IK chain / pole target / FK controls。
- game-deform skeleton export。
- Rigifyはauthoring helper候補。直接runtime skeletonと同一視しない。

RigifyはBlender同梱でhuman/quadruped等のmetarigを提供するが、生成control rigをそのまま全engineのgame rigとして保証しない。必要ならdeform boneだけをexportするprofileを持つ。

### 7.5 facial

- blink。
- jaw open。
- smile/frown等の最小expression set。
- visemeは必要なprojectのみ。

shape keysとbone face rigを混ぜる場合、export/driver compatibilityを実GLBで検査する。

---

## 8. アニメーション M6

既存`pose.set` / `animation.clip`を拡張し、以下を型付きにする。

- action/clip identity。
- frame range / fps。
- bone/object keyframes。
- interpolation。
- loop policy。
- in-place / root-motion。
- root delta report。
- NLA/action export mapping。
- additive layerはengine profileで必要性を確認。
- retarget mapping。
- morph animation。

代表clip:

- idle。
- walk/run。
- attack/use tool。
- hit/death optional。
- vehicle/robot mechanical cycle。

loopはstart/end poseだけでなく速度と接地を検査する。foot sliding detector、root displacement、joint limit、contact markerのauditを追加する。

GLBはobject transform、pose bone、shape key animationを扱える一方、material/light/physics animationは同じようには搬送されない。magic/VFXやcloth simulationは別のbake/runtime表現へ変換する。

---

## 9. 草木・環境・建物 M7

### 9.1 grass / foliage

trusted Geometry Nodes template:

```text
surface
 + density mask
 + slope/height mask
 + seed
 + species collection
 -> Distribute Points on Faces
 -> Instance on Points
 -> bounded instances
```

instancingを維持し、必要な時だけrealizeする。大量grassを個別meshとしてLLMが作らない。

必須:

- stable seed。
- density/instance limit。
- species weights。
- slope/height exclusion。
- camera-distance LOD / culling profile。
- wind mask attribute（engine shader用の場合）。
- collisionの有無。

### 9.2 trees / bushes

最初からInfinigen規模の依存を導入しない。versioned trusted tree generatorを小さく始める。

- trunk path / taper。
- branch level / angle / length distribution。
- leaf source mesh/cards。
- seed。
- optional LOD / impostor。

close-up hero treeとbackground forestは別QualityEnvelope。

### 9.3 rocks / terrain

- terrain heightfield / bounded mesh。
- erosion-like lookはtrusted procedural modifierとして分離。
- rock familyはseed variant。
- collision proxy / nav clearance。
- tiling/triplanar等はengine profileで評価。

### 9.4 modular buildings / houses

Repeat Zone / For Each Elementの考え方を用い、建物を巨大な一枚meshでLLMに生成させない。

```text
BuildingSpec
  footprint
  floor_count / floor_height
  grid/module size
  wall kit
  window/door kit
  roof kit
  corner policy
  seed / variation
```

成果はmodule instances + optional realized export。doors/windowsはlogical socketsを持つ。light leak、inside/outside normals、collision、nav opening、LODを検査する。

---

## 10. 道具・武器・防具・ロボット・機械・乗り物 M7

### 10.1 tools / weapons

共通要求:

- physical scale。
- grip socket。
- forward/up orientation。
- center of mass reference。
- muzzle / blade / effect socket。
- first-person近接viewがある場合は専用QualityEnvelope。
- collision。

high/low bakeで傷を増やす前にsilhouette、handle厚、接続を合わせる。

### 10.2 armor

- wearer rig / body dependency。
- rigid/flexible classification。
- attach bone/socket。
- weight transfer policy。
- pose penetration matrix。
- removable part identity。

### 10.3 robots / machines

柔らかいcharacter skinningとは別profileにする。

- part hierarchy。
- revolute/prismatic joint axis。
- min/max range。
- hard pivot alignment。
- piston/rod linkage。
- cable/pipe guides。
- panel/fastener family。
- collision clearance。

bone rigまたはobject hierarchyのどちらを使うかbriefで決める。

### 10.4 vehicles

- wheelbase / track / wheel radius。
- wheel pivot / steering axis。
- suspension travel。
- body/wheel/door/turret等のseparate moving parts。
- driver/seat/weapon/camera sockets。
- ground contact。
- interior/exterior levelの指定。

車両のanimationはcharacter clipとは別にmechanical constraint testを持つ。

---

## 11. 魔法・VFX M8

Blender上の見栄えとゲーム納品を分離する。

Authoring候補:

- curve trail / ribbon mesh。
- emissive material。
- animated mesh transforms。
- Geometry Nodes simulation。
- volume smoke/fire preview。
- particle/instance preview。

Game delivery候補:

- flipbook / sprite sheet。
- mesh trail + UV/vertex color。
- emissive mesh。
- noise/flow/distortion textures。
- impact decal texture。
- engine-specific particle descriptor（対象engineを固定した後）。

Blenderのvolume/material animationをGLBへそのまま運べると仮定しない。必要な見た目をbaked outputへ落とし、engine上で再生確認する。

MagicEffectSpec例:

```text
kind: projectile | beam | aura | slash | impact | area
color/emission palette
path / lifetime
width/radius curve
noise seed
flipbook fps/frame count
collision/effect socket
runtime representation
```

MediaForgeの画像/動画生成をtexture/flipbook素材に使う場合も、asset ID/provenanceを保持し、第二の無管理生成基盤を作らない。

---

## 12. trusted procedural template pack

Geometry Nodes / node-based toolsは、LLMが任意graphを作るより、署名・version固定したtemplateとして管理する。

`Trusted3DTemplate`:

```text
template_id
version
source_hash
blender_runtime_range
category
parameter_schema
seed_policy
estimated_amplification
output_kind
engine_delivery_modes
license/provenance
```

初期template候補:

- hair.clump。
- hair.cards。
- foliage.scatter。
- tree.simple。
- building.modular。
- cable.bundle。
- fence/road curve。
- rock.family。
- vfx.trail。
- vfx.flipbook-stage。

Blender Asset BrowserはGeometry Node toolをassetとして共有できるため、managed Blender runtimeにbundled asset libraryとして持たせる案を評価する。runtime version差を実probeし、任意ユーザーAsset Libraryを勝手に変更しない。

---

## 13. engine delivery M9

共通出口はまずGLB。実engine profileを追加するときは固定versionでacceptanceする。

```text
EngineProfile
  engine/version
  scale/axis
  static/skinned import
  material/alpha rules
  bone influence limit
  animation import mode
  root motion rule
  collision convention
  LOD convention
  socket/extras convention
  VFX representation
```

候補:

- generic.glb。
- web/Three.js。
- Godot。
- Unity。
- Unreal。

一つのengineで通った結果を他engineへ一般化しない。GLBのvalidityとengine import successも別gate。

---

## 14. optional G9 — AI 3D generation adapter

G9は「制作を加速する候補生成器」として後段に置く。

評価候補:

- Hunyuan3D 2.1: image→shape + PBR paint。公式は10GB shape / 21GB texture / 29GB combinedのVRAM目安。
- TRELLIS.2:高品質image→3D候補だが公式runtimeはNVIDIA 24GB+前提。
- Stable Fast 3D:単一画像からUV付きmesh/material候補。
- community Vulkan/native ports: AMD候補だが正式採用は固定commitとR9700実測後。

採用gate:

1. license / source pin。
2. local-only。
3. R9700 runtime compatibility。
4. cold/warm time。
5. peak VRAM/RAM/swap。
6. GLB parse。
7. topology/UV/PBR audit。
8. Blender cleanup経路。
9. rig/animation suitabilityは別評価。
10. model outputはcandidateとしてprovenance保持。

これらをMCP通常制作の必須依存にしない。

---

## 15. 実装順序

PR #526をM1として完了させ、その後は原則次の順序で小PRへ分割する。

M1受入時はLLM引数生成/stream、MCP受付、worker終端、export/配置を別々に記録する。
2026-09-13のR3ではprovider streamが中断し、scripted MCPの別診断は実行/配置まで成功した。
後者を実OpenCode受入へ代用しない。小さいauthored meshで有効なJSONと閉じたtopologyを
確認してから規模を上げる。parser障害時に生成途中の引数を自動補完して副作用を実行しない。
実測の正はimplementation-status。M1のsource merge/signed導入とLLM受入完了を区別する。
M1の閉装甲fixtureでは新schemaのrequire_closed=trueを必須とし、boundary edgeのある
入力をcore/workerで拒否する。false/省略は布の互換性用で、閉装甲の検査回避に使わない。
全辺の共有条件だけの検査をself-intersection-free solidや視覚品質の保証へ拡張解釈しない。

| 順序 | slice | 主な成果 | exit gate |
|---|---|---|---|
| M1 | authored mesh / guidance | `mesh.create` + guide | PR #526の新operation実MCP/OpenCode、source→signed installed |
| M2 | observation/audit | revision固定multi-view + issue focus | 実画像asset、同条件before/after、VLMは実画像trace |
| M3 | local edit / curve / hard-surface | extrude/inset/bevel/bridge/boolean/sweep/loft | hair clump、weapon、robot panel、building moduleを局所修正 |
| M4 | UV/PBR/bake | seam/unwrap/pack、PBR、high-low bake | UV/normal/AO/GLB再import、依存hash |
| M5 | character/hair/clothes/rig | weights/transfer/IK/shape key | hero characterでhair+cloth+armor、pose matrix |
| M6 | animation | clip/NLA/root/retarget/morph | idle/walk/attack実再生 + export/import |
| M7 | environment/mechanical generators | foliage/tree/building/vehicle/robot + LOD/collision | seed再現、LOD、collision、mechanical pivots |
| M8 | VFX/magic | trail/flipbook/impostor | projectile/impactをengineで再生 |
| M9 | engine profiles | GLB + target engines | static/skinned/animated/VFXの実import |
| M10 | optional G9 adapters | AI 3D candidate | AMD実測 + cleanup pipeline、default off |

依存を飛ばしてM5の見た目だけ先に作らない。特にM2観察surfaceとM3局所修正がない状態で、高精細characterをraw mesh再生成だけで追い込まない。

---

## 16. 代表受入作品

「機能がある」ではなく、複数の代表assetで完成度を示す。

1. **Hero character**: 顔/手、mesh/card hair、衣服、部分防具、4+表情、idle/walk/attack、近接多視点。
2. **Creature**: 四足、尾/角、skin deformation、walk。
3. **Weapon/tool family**: 近接武器+遠距離武器、grip/muzzle/effect sockets、LOD/collision。
4. **Armor set**: body依存、装着/着脱、pose penetration。
5. **Robot/mech**: 複数関節、hinge/slider、panel、cable、mechanical clip。
6. **Vehicle**: 4輪、steering/suspension、door/turret optional、driver sockets。
7. **Environment kit**: grass/trees/rocks + modular wall/window/door/roof + scatter + LOD。
8. **Magic VFX**: projectile + trail + impact flipbook/mesh、emissive runtime。
9. **Building**: 2階程度のmodular house、doors/windows、collision/nav openings、LOD。

各作品についてexecution / geometry / visual / surface / deformation / delivery / runtimeを個別にPASS/FAIL/NOT TESTEDで報告する。

---

## 17. 完了条件

この計画は、少なくとも以下を満たすまでCOMPLETEにしない。

- Coding agentが自然言語briefからcapabilityを発見し、存在するtyped operationだけで制作できる。
- 高精細characterを一回のmesh dumpではなく、観察・局所修正・surface・rig・animation工程で完成できる。
- hairのauthoring表現とgame runtime表現を区別し、最低mesh clumpとhair cardsを実engineで確認する。
- foliage/building等をseed付きtrusted procedural templateで再現できる。
- tools/weapons/armor/robot/machine/vehicleへpivot/socket/joint/collisionを持たせられる。
- magic/VFXをgame-readyなbaked/mesh/texture表現へ変換できる。
- VLMへ実画像を渡したtraceがあり、数値auditと役割分担できる。
- 失敗したrevisionを採用せず、旧版を不変保持できる。
- sourceだけでなくsigned installed ControlDeck + OpenCode/Codex MCPで受入する。
- 少なくとも一つの固定engine/versionでstatic/skinned/animated/environment/VFXを実importする。
- Broker/worker/session/grantが終端で回収される。
- 未測定G9モデルをdefaultにしない。

---

## 18. 調査資料

一次資料:

- Blender 4.5 Retopology/Remeshing: https://docs.blender.org/manual/en/4.5/modeling/meshes/retopology.html
- Blender 4.5 Hair Curves generation: https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/generation/generate_hair_curves.html
- Blender 4.5 Geometry Nodes instances: https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/instances.html
- Blender 4.5 Distribute Points on Faces: https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/point/distribute_points_on_faces.html
- Blender 4.5 Repeat Zone: https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/utilities/repeat_zone.html
- Blender 4.5 For Each Geometry Element: https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/utilities/for_each_geometry_zone.html
- Blender 4.5 Rigify: https://docs.blender.org/manual/en/4.5/addons/rigging/rigify/index.html
- Blender 4.5 Data Transfer: https://docs.blender.org/manual/en/4.5/modeling/modifiers/modify/data_transfer.html
- Blender 4.5 Cycles baking: https://docs.blender.org/manual/en/4.5/render/cycles/baking.html
- Blender 4.5 Simulation Nodes: https://docs.blender.org/manual/en/4.5/physics/simulation_nodes.html
- Blender 4.5 Asset Browser / node tools: https://docs.blender.org/manual/en/4.5/editors/asset_browser.html
- Blender 4.5 glTF 2.0 exporter: https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html
- BlenderMCP upstream: https://github.com/ahujasid/blender-mcp
- Hunyuan3D 2.1: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- TRELLIS.2: https://github.com/microsoft/trellis.2
- Stable Fast 3D: https://github.com/Stability-AI/stable-fast-3d

Community observations used only as design input, not as product evidence:

- Blender MCP subjective-quality / audit + focused multi-view discussion: https://www.reddit.com/r/ClaudeAI/comments/1vuccmd/might_have_cracked_blender_mcp_for_claude/
- Modular asset / rig / atlas workflow report: https://www.reddit.com/r/aigamedev/comments/1va4iop/new_workflow/
- Blender MCP good at blockout/material/rig but not a full VFX pipeline: https://www.reddit.com/r/generativeAI/comments/1u41j5f/dan_diego_the_ai_gold_rush_a_case_study_of_using/
- Hair workflow discussion (curves as common authoring base): https://www.reddit.com/r/blender/comments/1ufa4l7/any_suggestions_for_hair_workflow/
- Hair cards with Geometry Nodes for a game pipeline: https://www.reddit.com/r/IndieDev/comments/1ux6iql/hair_cards_for_painterly_art_style_a_geo_nodes/
- MCP large-tool-set lazy-loading architecture discussion: https://www.reddit.com/r/mcp/comments/1ro7ifh/blender_mcp_pro_100_tools_mcp_server_for_blender/

Community source is anecdotal.採用判断はBlender一次資料、MediaForgeの境界、実機受入を優先する。


## 19. Reference-guided authoring slices (2026-09-18)

M3b sourceはcandidate編集とbounded refine loopを追加。原head保持/2不改善停止は
controlled応答と実Blenderで検証、実Host推論・品質はNOT TESTED。

M3a sourceはbounded loft/sweep、断面更新、開端接合、subdivisionと実mesh selectorを追加。
実曲面fixtureとinstalled/LLM/品質の受入は分離する。


実装状態: R0記録とM1小閉meshのinstalled実OpenCode受入は完了。
M2a観察は[source実装・実Blender受入](m2-observation-20260918.md)まで進行。
R1の保存・scene参照部分は既存asset.packの3d.reference_set profileで実装。
canonical条件付き画像生成と4方向整合性の実受入は別途継続する。
M2bは[レビューsource実装・実入力準備](m2-review-20260918.md)まで進行。
Host実VLM判定・provider取消/解放・installed新toolはNOT TESTED。
新toolのsigned installed/OpenCode受入はNOT TESTED。M2全体や高品質制作の完了とはしない。

採用理由・一次資料・比較手法は[参照画像調査](../research/reference-guided-3d-authoring.md)。
利用者の指定は汎用基盤、曲面のstylized表現、animation込み、初回Blender＋MediaForge viewer。
既存M1〜M10/GAの範囲を削除せず、その中に次の小sliceを配置する。

| slice | 依存 | 実装・契約 | exit gate |
|---|---|---|---|
| R0 | 既存baseline | 一次資料、採用判断、共通manifest/品質方針、実装順を記録 | 文書整合、実測と計画の区別 |
| M1-gate | installed mesh.create | 実OpenCode authored closed mesh→Job→snapshot→export→grant | guard有効、trace、receipt/hash、実GLB再import |
| R1 reference | M1-gate | 既存画像Asset上のReferenceSet manifest/lineage、scene参照を加法追加 | owner/hash/view/axis検査、整合したfront/side/back/3q、矛盾時needs_review |
| M2a observe | M1-gate | media.scene.observe、revision固定ObservationSpec、既存durable Jobs・画像Asset | material/clay/silhouette/object ID、実render、before/after同条件、取消/再起動/解放 |
| M2b review | R1/M2a | media.scene.review、Host vision.analyze、構造化issue report | 実画像trace、対象ID/根拠、VLM不在・失敗は非成功 |
| M3a curve | M2a | bounded loft/sweep、制御点/断面編集、bridge、subdivision | 恐竜・四足・prop、独立予算検査、接合、閉殻方針、旧selection拒否 |
| M3b iteration | M2b/M3a | audit→最大3issue→局所修正→同条件比較、2回不改善で停止 | immutable candidate、旧版保護、悪化非採用、clay形状gate |
| M4 surface | M3b | 既存material/image経路＋UV/PBR/bake拡張 | 形状合格後に表面、依存画像hash、実GLB |
| M5 deformation | M3b/M4 | part graph/skeleton、既存auto-bind＋weight set/smooth/normalize、脚IK/bake | 関節pose、weight和/影響数/未重み、collapse/離脱/貫通 |
| M6 motion | M5 | rotation互換のtranslation tracks、deform skeleton＋baked clips | 24fps idle2秒/walk1秒/attack1.5秒、GLB再import、viewer再生/loop/切替/停止 |
| R2 comparison | R1〜M6 | T-Rex/四足/propの同一brief、3条件×各3試行 | 成功数、修正数、秒、memory、全gate別PASS/FAIL/NOT TESTED |
| M10 optional | 独立G9 gate | Hunyuan3D-2mv/SF3D/TRELLIS.2候補adapter | 明示license同意、AMD/CPU実測、cleanupと変形、default off |

### 加法契約と失敗条件

ReferenceSetは既存Assetのversioned manifest。image asset ID/hash、view、scale、forward/up軸、
landmarks、parts/attachments、provenance/license、承認状態を保持し、画像変更は新版にする。
scene参照はoptional。既存scene/recipeの意味と必須fieldは変えない。
未実装のtoolやmanifest型をaddon.json/capabilitiesへ先行広告しない。

observe/reviewはscene_id・revision_id・ReferenceSet asset IDを認可し、入力digestを固定する。
画像枚数・解像度・frame/focus対象・出力bytes・geometry増幅・timeoutをboundedにする。
観察Jobがsceneの最新revisionを進める必要はない。render対象はpinしたrevisionから変えない。
実装時にrequest/response/schema/API/agent guide/Host projectionを同時更新する。

reviewは既存Host AI gatewayと画像縮小処理を再利用する。実画像がモデルへ届いた証跡と
数値auditを分離する。画像IDを列挙しただけのtext-only評価をvisual PASSにしない。
提案operationが現在schemaに無ければunsupported、入力不足ならneeds_reviewで終了する。

shape操作は少数の断面/経路/制御点をworkerで展開する。高密度raw JSONをLLMへ要求しない。
新旧topologyとselection/revisionの対応を検証し、古い頂点indexを推測で再利用しない。
voxelで融合しただけの形状をdeformation合格にしない。

各sliceはowner違い、revision違い、過大入力、資源待ち、取消、再起動のnegativeを含む。
source試験、署名installed、実OpenCode制作、品質受入は別欄に記録する。
M1-gate未達の間はM2以降の実装完了・品質完了を宣言せず、具体的な障害と再開条件を残す。
