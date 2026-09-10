# ゲーム用アセット制作 — 設計・実装計画

Date: 2026-09-09
Status: 利用者依頼に基づく拡張計画 / GA-1最初のslice着手

## 1. 目標と「全部」の範囲

利用者の「ゲーム制作に必要そうな機能は全部使えるようにしたい」を、
Blender/MCPの文脈で**ゲーム用アセットの制作からエンジンへの受渡しまで**
として扱う。ゲーム本体のロジック・エンジン・レベルエディタをMediaForge内に再実装しない。
静的な小物だけを作れる状態を、この拡張全体の完成とはしない。
エンジン・ジャンル・対象機器は未指定。まずGLB/glTFを基準にするが、
Unity/Unreal/Godotへの対応を、ファイル生成だけで確認済みとはしない。

上位の正はbase-plan §12、Host境界はcontroldeck-integration-plan §18。
PR #213のGOAL-01〜10・3DS-0〜8・A〜Fは独立に保持し、残件を本計画で消さない。
3DS-X（Expert）と従来後続扱いのリグ/アニメーション等を本計画の段階へ明示する。
G9の生成3Dモデル、外部アセットのライセンス同意は別ゲートのまま。

## 2. 方針と選択理由

実行機能をMediaForge側へ拡張するCを主軸とし、Blender Skillsの制作知識は
ControlDeck向けadapter（B）で利用する。BlenderMCP常駐/addon/9876を別に導入するAは採らない。
既存のJobs/immutable revision/権限/Broker/停止/署名配布を一つの経路で守れるためである。
工程説明だけで終わらず、MCPで実行・検証・Asset参照まで返す。

- 通常のエージェント操作: bounded typed recipes。各段階でschemaを加法拡張。
- 手作業: 既存の隔離Web Blender。Blenderで操作できることとMCPから操作できることは別に表示。
- 複雑な手順: trusted templateとして型付き公開、または別権限のExpert script。
  任意Pythonを既存recipeへ紛れ込ませず、脱出negative/resource/cancelゲート後にだけ提供。
- スキル: 実際のoperation一覧/schemaと現在のscene snapshotを読む。
  上流94スキルの存在は94種の実行対応の証明ではない。実際にdirectorを読み込んだ
  OpenCode traceと生成物を受入証拠にする。固定7操作の説明の更新経路も検証する。
- UI: Createは指示中心、Library/Activity/Settingsは共通。別addon/DB/ノードエディタは作らない。

## 3. 段階・依存・成果物

| 段階 | 制作できるもの / 実装対象 | 依存 | 実機のexit gate |
|---|---|---|---|
| GA-0 | operation/schema/capability対応表、予算・品質profile、skill実読込証拠 | 既存3DS | 新旧クライアントのschema互換、未対応を実行可と出さない |
| GA-1 | 静的prop/建物: 複製、mirror/array/Boolean、join/delete、適用transform/origin、選択付きextrude/inset/bevel、curve、cleanup/normals | GA-0 | 対称武器/家具/モジュール壁をMCPで制作、寸法・triangle・実GLB再import、旧版不変 |
| GA-2 | sculpt/high-polyとretopology、UV編集・seam/unwrap/pack、texel density、複数material slot、全PBR channel、atlas、high→low normal/AO等bake | GA-1 | 既存/生成画像を貼る→比較→採用/破棄→再実行。UV/色空間/normal方向/依存hash、low-poly形状とhigh-polyとの差の確認 |
| GA-3 | ゲーム向け最適化: LOD、triangulation、collision proxy、socket/pivot、instance/mesh統合、budget report | GA-1/2 | 各LODの実triangle/境界、collision形状、mesh/material/texture memory予算、manifestと実bytes一致 |
| GA-4 | キャラクター: armature/bone hierarchy、bind/weight painting、自動weightと補正、IK/FK、pose、morph/shape keys | GA-1/2 | 関節変形の実pose比較、joint/weight正規化、未重みvertex/影響数制限、skinned GLB再import |
| GA-5 | アニメーション: keyframe/action/clip、NLA/bake、loop、root motion、retarget、morph animation | GA-4 | 待機/歩行/攻撃clipの再生、duration/fps/loop境界/root差分、エンジン再生と旧clip保持 |
| GA-6 | 環境/VFX: terrain/foliage/scatter、procedural trusted templates、simulation bake、flipbook/sprite/impostor | GA-1/2/3 | seed再現、instance上限、cache予算、cancel/解放、ゲームで再生可能なbaked出力 |
| GA-7 | engine delivery: generic package、選択engine向けscale/axis/material/rig/collision/LOD設定、import report、必要形式のFBX/OBJ等import/export | GA-3/5/6 | 正規grant/receipt、実engineでstatic/skinned/animated asset取込、表示/再生/衝突確認。形式追加はparser/外部URI/autoexec/容量のnegative受入後 |
| GA-X | Expertのscript artifact/別権限/OS隔離・capability | 3DS-X隔離仕様/資源管理 | filesystem/network/credential/process脱出拒否、timeout/cancel/出力上限、再現可能provenance |
| GA-8 | 統合受入・署名配布/導入・回帰 | 全必須段階 | 代表static/character/environmentをskill→MCP→制作→engineまで完走、update/rollback/旧asset保持 |

GA-4等は「BlenderのGUIにメニューがある」だけで完了にしない。
GA-Xは通常操作を実装しない言い訳にしない。特定機能をExpertだけで満たす場合は
用途、権限、実行手順、再現性、残る制限を個別に記録する。
動画/音声は既存MediaForge/SonicForge公開契約を使う。音声内部codeや第二生成基盤は作らない。

## 4. GA-1最初のslice — 複製とミラー

静的prop制作の基礎としてobject.duplicateとmodifier.mirrorを追加する。
既存media.scene.create/editのrecipe@1を加法拡張し、既存7操作の意味は変えない。
旧bundleは新operationを拒否する。クライアントはavailableなsupported_operationsと
現在配信されたschemaを確認し、古いHost/workerへ新operationを送らない。

| operation | 入力 / 意味 | 上限・拒否 |
|---|---|---|
| object.duplicate | source_object_id→新object_id/name、任意のabsolute location/dimensions/rotation。mesh datablockを独立copyし元geometryを保護 | meshのみ、同ID/既存ID/不明sourceを拒否。親/constraint/animation/shape-key付きsourceは今回未対応として拒否 |
| modifier.mirror | object_id、重複なしaxes(X/Y/Z)、任意reference_object_id、merge_threshold。非破壊modifier | meshのみ、自己reference/不明referenceを拒否。1 objectにつきmirror1個、axes最大3、merge距離はlocal mesh座標で0〜0.1 |

ミラーはlocal origin、reference指定時はそのobject座標系を基準にする。
merge距離のworld換算はobject scaleの影響を受ける。メートル指定と偽らない。
中心に対称なcubeをさらにmirrorしただけで、意図した形状ができたと扱わない。
複製はmeshを独立にするが材質Assetは共有参照。copy後の材質差替えが元objectのslotを変えないことを確認。
従来どおり64操作/recipe、workerのtimeout/cancelと独立GLB検証を維持。
新機能の増幅は事前geometry予算で拒否し、巨大allocation後の検証だけに頼らない。

初回fixtureは左右支柱と梁の小型ゲート。複製先の変形が元geometryを変えないこと、
ミラーの実評価geometry/GLBに左右があること、stable IDs/材質/旧版hashを検査する。
ユニット・契約試験の後、実Blender worker/domain、署名installed MCP/OpenCodeへ順に進む。
このsliceだけでarray/Boolean/rig/animation/GA-1全体完成としない。

### GA-1 配列複製の加法slice（2026-09-10）

`modifier.array`でstatic meshへ固定個数の非破壊配列を追加する。
入力はstable `object_id`、`count`（元形状を含む2〜64）、非零の`local_offset`（XYZ）。
offsetはlocal mesh座標であり、objectのscale/rotationでworldの間隔・方向が変わる。
relative/object/curve offset、fit length、cap object、vertex mergeはこの操作には含めない。
一つのobjectにつきarrayは一つ。既存parent/constraint/animation/shape-key付きmeshを拒否する。
duplicate/mirror/bevelと組合せた増幅をallocation前に保守的に見積り、既存100万geometry予算で拒否。
GUI由来の未知array設定を安全な固定配列と仮定せず、後続の形状増幅も拒否する。
static階段をfixtureに、元meshの頂点不変、6段の実評価geometryとGLB再import後の形状・寸法、
別revisionでの移動、旧blend/GLB hash保持、過大個数/二重array/増幅予算超過の拒否を確認する。
このsliceで接合Boolean、organic weights、歩行、engine受入を代替しない。

### 4.1 次の制作受入 — 接合とシルエット

2026-09-09利用者は剣の隙間を指摘し、格好よいロボットやカメレオンの制作を希望した。
実skill/MCP呼出・322 trianglesという構造検査だけでは制作品質を満たさなかった。
次のfixtureはstylized robotとし、頭/胴/肩/腕/手/腰/脚/足の接続意図を先に定義する。
装甲の意図的な隙間と、関節/芯材がなく部品が浮いた欠陥を区別する。
正面/側面/斜めの実renderでシルエット・比率・左右対称・接合部を比較し、
評価後meshの接触/離隔と合わせて判定する。AABBの重なりだけを接触の証明にしない。
機械検査合格を「格好よい」の証明とはせず、ユーザーにpreviewを提示する。
ロボットはまずstatic prop。動く関節/rig/animationはGA-4/5の別受入。
利用者は同日、Blenderのボーンを用いた動きアニメーションも明示要求した。
Unreal Pawnではなくarmature/boneとして扱う。static段階の終了を全体完了にしない。
最初のrig sliceはbounded骨格階層とロボット部品の剛体的なbone割当て、rest/pose比較。
続いて有機モデルのvertex weights、関節変形、待機/歩行clipを実装する。
骨数/階層循環/零長bone/weight正規化/影響数/キー数を制限し、
スキンとアニメーションを含むGLBの再import・再生を確認する。
現在のscene検証/export制約を先に監査し、任意bpyを通常recipeへ開放して代用しない。
カメレオンは胴体から手足への連続面、目、指、巻いた尾が必要なorganic fixtureとして
GA-1 curve/mesh編集とGA-2 sculpt/retopologyの受入へ含める。球の寄せ集めで完成扱いにしない。

## 5. 契約・安全・リソース

### GA-5 first typed slice

animation.clipを加法追加する。typed rigの既知boneに対するrest-local XYZ回転trackを
昇順frame/LINEAR補間で定義し、未指定boneは各clip内でrest回転を明示的に保持する。
frame0からframe_countまで、fps1〜60、最大600 frames/120秒、128 tracks、
1 track2〜256 keys、scene32 clips/262144 scalar keys/250000 bone-frame samplesを上限とする。
loop指定時は各trackの両端回転が一致することを検査するが、滑らかな速度連続性は別の品質検査。
同じrigのclip ID重複は既定で上書きせず拒否。明示replace=trueの場合だけ既存typed clipの
全track/name/loop/frame_countを新しい制作版内で置換する。不在IDへのreplaceは拒否する。
既存actionの構造・予算・参照を検査し、他IDから参照されるactionを巻き込まない。
旧revisionのsource/GLB、無関係なclipは不変。FPS変更/任意actionの変換は許可しない。
置換後のscene全体に同じclip/key/sample上限を適用し、上限到達時でも同容量の置換は可能にする。
既存clipはmuted NLA stashとして保存し、
新clipをactiveにする。全typed clipsはscene共通fpsとし、追加で既存clipの時間を変えない。
任意action/driver/constraint/非typed rigとの混在は拒否する。保存済みcurveを実計数して予算を再検査。
まずidleと腕振りの別clipを作り、別revisionへ追加して旧clipが不変なこと、
実frame評価とGLB再import後の同時刻の動き・duration・両端一致を検証する。
歩行/root motion/IK/retarget/有機変形はこの最初のsliceだけで完了にしない。

### GA-4 automatic binding slice（2026-09-10）

`skin.bind_auto`を加法追加する。stable `object_id`でtyped rig、`mesh_object_ids`で
1〜16個の未bind meshを指定し、Blender bone heatで分布weightを求める。既存`skin.bind`は変更しない。
rest/identityのtyped rig、独立mesh data、親/weight/constraint/animation/shape key/modifierなしを前提にする。
modifier適用・既存weightの置換は暗黙実行しない。全選択mesh合計50,000 vertices/100,000 polygons、
300,000 face corners、vertices×deform bones合計1,000,000を処理前に制限し、既存worker timeout/cancelを維持する。
finite geometry・非零の有限face area・正の非特異transform・有効なdeform bonesを検査してからCPUで実行する。
heatの成功戻り値だけを信頼せず、全頂点に既知骨の有限非負weightがあることを検査。
各頂点の上位4影響（同値はgroup index順）を残して正規化し、保存値の合計誤差1e-5未満を再検査する。
weight欠落/不正/heat失敗は別の剛体割当てへfallbackせず、工程失敗とする。
rest geometryが変わらないことも検査する。成功後のpose/clipは既存操作を用い、GLB skinを保持する。
処理は既存候補workspace内のみ。途中失敗や後続操作失敗では新revisionをcommitせず旧版を保持する。
実連続meshを2骨へbindし、複数骨影響・rest/pose/clip・GLB再import・旧版不変を検証する。
小規模fixtureの成功を複雑なキャラクター品質、weight painting、IK、歩行やengine受入の代替にしない。

### GA-4 rigid binding（既存）

armature.createでidentity transformの骨格を作成する。親は同一操作内で先に定義したboneに限定、
1回128 bones/scene合計256 bones、有限head/tail、零長と重複IDを拒否する。
skin.bindはまずロボット等の剛体部品を対象に、mesh全vertexを指定boneへweight=1で割り当てる。
既存parent/constraints/weights/armature/shape-key/animationがあるmeshは上書きせず拒否する。
pose.setは既知boneのrest-local XYZ回転を置換する。未指定boneを勝手にresetしない。
このsliceはポーズの生成であり、時間軸のaction/clipや有機モデルの分布weightsは次slice。
実bone階層・bind前後のrest形状不変・poseによるworld頂点移動・旧revision不変・
GLB skin/joints/weights再importを検証する。既存GUI骨格はtyped上限/対応条件に合う場合だけ操作する。
現段階のGLBは、全rigがtypedかつactionsなしの場合だけcurrent poseをexport restへ使用する。
元blendのbone restは変更しない。pose.setはaction/他種rigとの混在を拒否する。
既存GUI/animated入力の設定は保持し、clip対応時のrest/pose/animation選択は別受入する。

- schemaはschemas/、docs/apiと同期。追加operationと旧fixtureを両方検証する。
- 依存objectはstable ID、選択はbounded selector。任意bpy path/operator文字列/評価式を受けない。
- 選択集合、vertices/triangles、modifier増幅、texture総画素、bones/weights、frames/clips、
  simulation cache、出力bytesを工程前に制限し、評価済み結果を独立検査する。
- CPU/GPU経路を区別。GPUは処理の存続期間に対応するHost leaseとestimated_runtime_sec、
  renew、取消時の実process回収。別stageのleaseを持ったまま待たない。
- 追加の同期DB/filesystem/Blender処理をasync event loopへ入れない。
- 任意スクリプトは既存Web Blenderの存在だけで安全宣言しない。
- 稼働中Blender、外部install、利用者global設定・鍵・重みを勝手に変更しない。
- 依存・source/commit/hash/licenseは固定。未導入や未検証はunavailable/planned。
- scene/asset/revision/job基盤を再利用。失敗は新revisionをcommitせず候補・理由を保持。

## 6. 利用者の操作・モバイル

MCP: 「門を作る」→構造/予算→typed制作→preview→画像貼付→比較採用→engine export。
複雑な未対応依頼は不足工程を具体的に示し、簡略物を元依頼の完成品と偽らない。
Web: 選択sceneから同じ版を開いて詳細編集、保存/復旧/停止を一貫させる。
モバイル: Libraryの±XYZ/zoom・依頼・進捗/停止・設定を維持。
現行767px以下のGUI起動禁止はフルGUI対応ではない。将来の入力補助/
全画面/タッチ・キーボード/背景復帰を別受入し、PC推奨という説明だけで対応済みにしない。

## 7. 完了証拠と管理

各sliceに実行command、exact commit/runtime、fixture、実測、NOT TESTED、
既存画像/G8/3DS回帰、PR、署名release/installed版を記録する。
同じ制作物で作成→材質→最適化→rig/animation（該当asset）→engine取込を追跡する。
機械検査は見た目・関節変形・ゲーム内品質の代替ではない。
各engineの対応表は対象version/import設定を固定し、実機検証後だけ更新する。
計画・コード・テスト・公開・導入・実使用確認の状態を分離し、
予定日や全機能対応を根拠なく約束しない。
