# AIによるBlenderゲームアセット制作

## 1. 結論と適用範囲

MediaForgeでは、既存の型付きMCP制作経路を拡張し、制作知識と実行可能な操作を明確に分ける。
優先すべきものは、任意形状の作成、対象を限定した修正、版に紐付く複数方向の観察、
UV・材質、変形検証、ゲームエンジンへの受渡しである。Web Blenderの画面操作は並行する製品目標だが、
MCP制作の前提条件にしない。Blenderで可能な機能を、そのまま現在のMCPで可能とは表示しない。

本書の対象はキャラクター、クリーチャー、環境物、道具、乗り物、武器、防具のローカル制作である。
LLMには制作計画・型付き操作の選択・実行結果の整理を担当させ、VLMには実際に渡された画像の
比較と可視欠陥の指摘を担当させる。ファイル構造、寸法、重量、UV、変形、納品の正否は、
対応する検査結果を根拠にする。VLMの好評価だけで構造検査やエンジン受入を省略しない。

共通の交換形式はまずGLBとする。glTFはメートル単位の右手系でY上方向を定義し、
skin、morph target、アニメーションを表現できるが、これはMediaForgeの全機能対応を意味しない。[^1]
Blender側のZ上方向・recipeの度指定と、書き出し後の表現の違いはexporter境界で扱う。
LLMが事前にもう一度軸変換して二重変換することを防ぐ。

以下の「資料の事実」は一次資料に基づく。「推奨設計」はMediaForge向けの判断であり、
未実装の機能・未測定の品質を保証しない。実装状態の正はimplementation-statusと実配信capabilityである。
調査時点は2026-09-13、対象の実測Blenderは4.5.9。公式マニュアルは4.5系を優先し、
一部は同版の翻訳ページまたはUATESTページを参照した。UI文言や新しいAPIの存在をそのまま
4.5.9の実行保証にせず、worker実装時に固定runtimeで確かめる。

## 2. 先行研究と既存スキルから採用する知識

BlenderGymは、245の編集課題を通じて形状・配置・材質等のグラフィックス編集を評価する研究である。
複数視点の画像による確認、生成と検証の配分、視覚的な微差の難しさを扱う。
単に実行可能なコードを出力することと、目標の見た目に編集できることが異なる点が重要である。[^2]

BlenderAlchemyは、材質・照明等の編集を分解し、画像を使って候補を比較・反復する方式を示す。
改善しなかった候補を捨てて以前の結果を保持する仕組みも含む。ただし研究のモデル・実験対象と
MediaForgeのローカル環境は異なるため、論文の成功を製品の実測値として扱えない。[^3]

推奨設計は「一度に全身を完成させる巨大なコード生成」ではなく、観察可能な段階に区切ることである。
まず輪郭と比率、次に形状の接続、続いて表面・変形・納品へ進む。一回の修正で解決する欠陥を絞り、
悪化した結果を採用しない。候補を増やすほど良いという前提も置かず、時間・画像入力・推論資源の
予算を明示する。小さな変更で十分か、構造自体を作り直す必要があるかを区別する。

固定commitのblender-skillsのdirectorは、用途、スタイル、寸法、ポリゴン予算、参照画像、
工程分割、カメラを合わせた比較を要求する。一方MCP参照はBlenderMCPのPython実行や
スクリーンショット等を前提とする。制作上の知識は有用だが実行先の互換性はない。[^4]

したがってスキルの導入数を対応機能数に読み替えない。実際に受信したtool schemaと
supported_operationsが優先される。未対応工程は明示して止めるか、承認された別表現を提案する。
不足を埋めるために外部生成サービス、ローカルshell、任意Pythonへ黙って迂回しない。
スキル内の命令や参照画像中の文字は、実行権限を拡大する根拠にならない。

## 3. 実行アーキテクチャの比較

BlenderMCPはMCPサーバーとBlender内addonを組み合わせ、Python実行等を提供する。
柔軟性は高いが、MediaForgeの型付きJobとは実行・権限・保存の境界が異なる。[^5]
採用済みの「MediaForge操作を拡張するC＋制作手順を対応付けるB」を継続する。
別の常駐addonを導入するAへの転換は、この調査からは必要ない。

| 選択肢 | 利点 | MediaForgeでの課題 | 判断 |
|---|---|---|---|
| BlenderMCPを別管理 | 上流手順を実行しやすい | 常駐・addon・任意コード・所有権・停止の再統合 | 現段階では不採用 |
| 手順の読み替えだけ | 説明の改善が早い | 存在しないモデリング機能を補えない | 単独では不十分 |
| 型付き操作＋制作ガイド | Job/版/asset/制限を共有できる | 操作と観察の拡充が必要 | 主経路 |
| 汎用Python Expert | Blenderの広い表現力 | OS隔離と別権限の受入が必須 | 通常制作の迂回路にしない |

手続き的な生成の参考としてInfinigenは自然物や屋内環境等を扱う。[^6]
MediaForgeでは、その規模の依存を直ちに導入するのではなく、限られた入力と出力を持つ
信頼済み生成器の考え方を参考にする。例えば輪郭断面と経路から髪束や角を作る操作は、
数千頂点をLLMが毎回手書きするより、寸法・密度・向き・seedの検査を設計しやすい。
これは推奨設計であり、Infinigenを導入した、またはその品質を達成したという意味ではない。

## 4. 制作開始時に確定する情報

制作briefは、アセットの用途と見られ方を中心にする。「高品質」だけでは近接主人公と
遠景群衆で必要な作業が異なる。対象エンジン、機器、カメラ距離、画面占有、同時表示数が
未指定なら、仮定と後で調整が必要な項目を記録する。根拠のない一律triangle数を推奨値として固定しない。

最低限、種類、スタイル、実寸、正面、原点、可動部、必要な装備、必要clip、textureの用途を整理する。
参照画像は利用可能な権利と出典を保持し、正面・側面・背面の相違や透視歪みを区別する。
単一の画像から見えない背面や内部構造を確定事項として説明しない。

計画にはtriangleだけでなく、material/primitive数、texture解像度と枚数、骨数、頂点当たりの影響数、
透明部分、LOD、collision、納品先も含める。予算には根拠となる実際のエンジン計測を紐付ける。
初回の小規模fixture予算は開発上の安全上限であって、ゲームの性能保証ではない。

名前は可読性のため、stable object IDは操作対象の特定のために使う。表示名が一致しても同一対象とは限らない。
scene、revision、runtime、入力assetのIDを工程ごとに保存する。同じ外見を再生成したものと、
以前のassetを再利用したものをlineageで区別できるようにする。

## 5. アセット群ごとの制作フロー

| 群 | 最初に合わせる形 | 中盤の重点 | 納品前の代表的な失敗 |
|---|---|---|---|
| 人型キャラクター | 身長、頭身、肩幅、手足、顔の印象 | 関節ループ、手、顔、髪、衣服、装備 | 肩潰れ、服貫通、髪の隙間、表情破綻 |
| クリーチャー | 胴体比率、重心、脚数、頭・尾 | 肢の可動範囲、鱗/皮膚、角、翼 | 足の接地不良、尾の潰れ、左右の意図しない非対称 |
| 環境物 | モジュール寸法、グリッド、輪郭 | UV反復、接合、LOD、collision | 継ぎ目、light漏れ、重複面、近景だけで成立 |
| 道具 | 使用姿勢、握り、接触面 | 厚み、接合、摩耗の理由 | 部品が浮く、取っ手が握れない、原点不適切 |
| 乗り物 | 全長・軸距・車輪径・地面 | 車体と可動部の分離、pivot、内外面 | 車輪軸ずれ、操舵干渉、薄い板の裏面消失 |
| 武器 | 柄と本体の接続、重心、寸法 | 刃/銃身等の輪郭、材質、socket | 部品間の隙間、手への取付ずれ、輪郭の弱さ |
| 防具 | 装着対象と被覆範囲 | 板厚、縁、留め具、関節の逃げ | 腕上げで胴体貫通、重なり順の不自然さ |

すべてを人型の同じテンプレートで処理しない。カメレオンなら脚と指の把握、尾の巻き方、
目の配置が形の識別に寄与し、ロボットならパネルの厚み、関節軸、部品間のクリアランスが重要になる。
これは評価項目の設計例であり、特定の生物構造や機構を資料なしに正確に再現できるという主張ではない。

ブロックアウトではmatcap相当の単純な表面で輪郭と接続を確認する。細かな傷や装飾を追加しても、
肩幅や頭身、刃と柄の隙間は直らない。照明やカメラで欠陥を隠した結果を形状改善として採用しない。
制作段階ごとに正面、側面、背面、斜め、必要箇所の近接画像を比較対象として固定する。

## 6. トポロジー・曲面と修正の粒度

Blenderのvoxel remeshは均一なメッシュ化に使えるが、評価対象のmodifierやshape keyをそのまま
引き継ぐ万能工程ではない。remeshとアニメーション向けの最終トポロジーは区別が必要である。[^7]
MediaForgeでは、見た目の曲面生成と、変形を目的としたedge flowの確認を別のgateにする。

mesh.createはこの基礎になる。有限の頂点・面を受け、範囲外index、重複face、未参照頂点、
零面積fan triangle等を拒否する。ただしmanifold、自己交差、面のねじれ、意図した法線方向、
関節のedge flowを完全に証明するものではない。開いた布や葉の縁を一律エラーにしないことも必要である。

次の実装は、選択集合に対する頂点移動、面の押出・差込、edge bevel、断面loft、経路sweep等を
小さな契約に分ける。何でもできるoperator文字列を追加しない。入力段階で選択数・結果増幅を制限し、
base revisionに対するindexの意味を束縛する。トポロジー変更後の古い選択は無条件に再利用しない。

形状の全置換はUV・skin・morphを壊し得る。後続のreplace/delete実装では依存のある対象を拒否するか、
明示した再構築手順を要求する。外見が似ているから重みや形状キーがそのまま使える、と推論させない。
鏡像・配列・subdivision等は実体化後のtriangleとメモリを測り、入力面数だけで安全と扱わない。

## 7. 髪の毛の表現と段階的対応

髪は三段階に分ける。第一段階は厚みのあるメッシュ束で、スタイライズ向けの輪郭と房の流れを作る。
第二段階はヘアカードで、薄い面と透明textureを使う。第三段階はガイド曲線や多数の毛と、
必要に応じたシミュレーションである。これらは見た目・負荷・輸出表現が異なるため同じ「髪対応」にまとめない。

BlenderのGenerate Hair Curvesはsurfaceとsurface UV、密度、曲線点数等を入力として扱う。[^8]
曲線ガイドのcurlも独立したパラメータを持つ。[^9] こうしたBlender内機能が存在しても、
GLBや対象ゲームで同じ表現が再生される保証にはならない。native groomを公開する前に、
mesh化、カード化、または対象エンジンの対応形式のいずれを納品するか確定する。

最初の髪束では、根元の頭皮への接続、分け目、主要な流れ、房の太さの変化、先端、耳と目の見え方を
確認する。同じ断面を並べただけの棒状の束は髪の自然さを作らない。前髪を増やして顔の不出来を隠さない。
裏面・頭頂・背面からの隙間や頭皮露出を評価し、ヘアキャップと房の役割を分ける。

カード対応ではalpha mode、裏面、重なり、mipmap時の縁、近景と遠景での読みやすさを確認する計画とする。
現在の材質入力にalpha関連の全設定があるとは仮定しない。透明の描画負荷やエンジン差は
実際のターゲット上で評価する。曲線やカードの導入だけで毛の物理演算まで利用可とは表示しない。

## 8. 服・防具の制作と変形

衣服には着用位置、余裕、厚み、裾や袖口、縫い目、素材の違いがある。静止姿勢のshellが体に沿うことと、
歩行・腕上げで破綻しないことを分ける。身体に密着する服、ゆとりのある布、剛体的な防具で
同じ重み付け・変形方法を適用しない。

BlenderのData Transferはメッシュ間のvertex groupやUV等の転送を扱い、対応付け方法が結果に影響する。[^10]
これを衣服へのweight transferの設計参考にするが、自動転送を最終品質とはしない。
腕が胴体に近い箇所や左右の脚が接近する箇所では、誤った対応を検出できる姿勢確認を用意する。
転送前後の頂点影響、正規化、未重み頂点を数値で記録する。

布シミュレーションにはcacheがあり、形状の変更後にはclear/rebakeが必要になる。[^11]
MediaForgeで将来提供する場合は、入力版、フレーム範囲、設定、cache容量、キャンセル、再開条件を
Jobに束縛する。Blenderのcacheを置いただけでゲーム内の布シミュレーション対応とはしない。
静的な皺のbake、骨で近似した動き、実エンジンのcloth設定を区別して受け渡す。

防具は、縁の厚み、面の張り、留め具、重ね順、可動部の逃げをまず設計する。肩当てを球状の塊として
置いただけでは板金らしい面構成にならない。腕を上げる、肘を曲げる、しゃがむ等の試験姿勢を用意し、
装着部と遠位部の追従を別々に確認する。着脱や武器socketが必要ならbriefに含める。

## 9. UV・画像貼付・PBRとbake

画像の生成とUVへの割当ては別工程である。単一の参照画像を全身に貼り付けるだけでは、背面や
側面での対応、継ぎ目、歪みが解決しない。base colorに照明や影が描き込まれている場合は、
照明下で不自然に二重の陰影が現れないか確認する。入力画像の権利と生成履歴は依存assetとして保持する。

BlenderのUV seamは複雑なメッシュの切り開き方を制御し、packは島の配置と余白を扱う。[^12]
推奨するMCP拡張はseam、unwrap、pack、texel density検査を個別にすることである。
現在のsmart projectは初期値として使えても、衣服模様や顔の連続性の保証にはならない。
UVは頂点位置だけでなく面cornerとの対応を持つため、トポロジー変更後の再利用にも注意が要る。[^13]

normal mapは画像としてそれらしく見えるだけでは不十分である。Blenderのbakeにはtangent normal、
selected-to-active、ray/cageの条件があり、変形するmeshでの用途を区別する。[^14]
high/lowの対応、cageの食い込み、hard edge、UV seam、normal方向を固定した試験を設ける。
生成した色画像をnormalへ流用する、AOをmetallicとして使う、といった誤りを説明とschemaで防ぐ。

材質検査にはチャンネル、色空間、画像hash、UV set、対応object/slotを記録する。
GLB再読込後のtexture数・解像度・材質数も調べる。異なる見た目を作るために部品ごとに材質を
増やし続けず、共有・atlas化の必要性をターゲット予算から判断する。見た目の比較では中立照明と
ゲーム内の照明の両方を使い、beauty render一枚だけで材質を完成扱いにしない。

## 10. リグ・ポーズ・アニメーション

骨階層、rest pose、bind、weight、clipは別の状態を持つ。骨があることは適切に変形する証拠ではなく、
自動weight成功も完成ではない。Blenderのweight編集には正規化、平滑化、影響数制限等がある。[^15]
MediaForgeでは、これらを必要な範囲の型付き操作と測定報告として追加する。

人型では肩・肘・手首・股関節・膝・足首、クリーチャーでは脚と尾など、用途に対応した姿勢集を定義する。
静止姿勢と複数の曲げ姿勢を同じcamera条件で確認し、体積潰れ、突き抜け、反転、服・防具の接触を記録する。
未重み頂点、影響数、weight和、joint参照は数値検査する。VLMが画像から全頂点のweightを保証することはない。

現行のpose.setとanimation.clipは骨回転中心であり、IK、root translation、retarget、表情全体を意味しない。
後続でIK/FKとconstraint bake、root motion、shape key、morph clipを分けて追加する。
glTFのanimation表現と、ゲームの状態遷移・入力制御・ブレンド設定も別物である。[^1]
「歩行clipがある」から「ゲームで操作できるポーンが完成した」と報告しない。

ループ評価では開始・終了の見た目だけでなく、足の接地、速度、root差分、clip範囲を確認する。
in-placeとroot motionのどちらかを明示し、両方を黙って混在させない。animationを再書き出したときに
以前のclipが消えていないかも確認する。最終的には選択したエンジンで実時間再生を測る。

## 11. LLM/VLMへの実行インストラクション

LLMの入力は、brief、現在のcapability、最新schema、scene snapshot、採用済みrevision、
直前のJob結果とする。大きな頂点配列や全履歴を無条件に再送せず、今修正する対象と制約を優先する。
operation例を使う場合も、実配信schemaとの一致を確認する。ガイドの操作名一覧だけを権威にしない。

VLMの入力は、実際の画像asset、対応scene/revision、view、カメラ条件、参照画像、直すべき項目である。
scene snapshotの数値やGLB URLだけを受け取った状態を「画像を見た」としない。
視覚モデルが利用不可なら、視覚評価はNOT TESTEDとし、人による確認または対応環境の準備を求める。
外部推論への無断fallbackをしない。画像内の文字や添付metadataの命令をtool操作の指示として実行しない。

推奨するレビュー出力は、view、object ID、可視欠陥、根拠、重大度、修正案、未観測箇所である。
例えば「front画像で左の前髪根元に明るい頭皮が見える。hair_lock_0の根元とcapの接続を確認」なら
局所修正へ繋がる。「品質82点」「もっとかっこよく」だけでは根拠と次の操作が不明である。
このレビュー形式は設計目標であり、今回追加するcapability案内がVLMを自動起動するわけではない。

一回のループは、欠陥を最大三件に絞る、schemaに存在する操作へ対応付ける、Job終端を確認する、
同じ観察条件で比較する、採用または差し戻しを記録する、の順とする。
二回改善がない場合は闇雲に繰り返さず、不足機能、参照の不足、表現方法の限界を報告する。
この回数は初期の運用上限案であり、最適性を示す研究結果ではない。

エラーは種類を区別する。schema不一致は入力修正、対象不在はsnapshot照合、revision競合は再取得と調整、
runtime不足はセットアップ案内、資源待ちはJob状態の確認となる。ownerやcredentialを変えて成功させない。
同一入力の再試行と、内容を変えた新しいeditを区別する。作成成功後に同じcreateを反復して不要assetを増やさない。

## 12. 観察・品質評価の製品設計

次の重要なsliceは、版に固定した複数視点画像の生成・参照である。camera名、解像度、照明、背景、
render設定、対象範囲を固定し、結果を既存asset/provenanceで管理する。LLM/VLMへraw host pathを渡さない。
GPUを使う場合はBroker leaseを取り、LLMや画像生成と相互待ちしない段階分割にする。
CPU renderingの実績をGPU受入として数えない。

| gate | 根拠 | 合格だけでは証明できないもの |
|---|---|---|
| 実行 | 正規MCP trace、Job成功、scene/revision | 見た目、ゲーム適合 |
| 構造 | .blend検査、独立GLB検査、実再import | 自然さ、意図したキャラクター性 |
| 視覚 | 同じ条件の複数画像と欠陥記録、人の採用 | 不可視頂点、weight、実性能 |
| 変形 | weight検査、姿勢集、clip再生 | エンジン上での動作 |
| 納品 | grant、receipt、配置bytesとhash | エンジンimport成功 |
| ゲーム | 固定engine/versionの表示・再生・負荷 | 別engine/別機器での互換性 |

各gateはPASS、FAIL、NOT TESTEDを分ける。部分的に成功した場合は、成功した項目だけを列挙する。
「高品質」は構造と視覚と用途の複合条件であり、polygon数、skin数、texture枚数から自動的には導けない。
少なくとも正面・側面・背面の輪郭、近接顔/髪、衣服と防具、曲げ姿勢、ゲーム画面での評価を必要とする。

初回のsource-domain fixtureは、28 mesh、2,312頂点、4,512 triangle、56操作を実Blender4.5.9で生成し、
GLB再importで28 meshと4,512 triangleを確認した。GLBは81,264 bytes、制作処理は0.494秒だった。
これは手書きrecipeのworker評価であり、実OpenCode/MCPによる自律制作の新機能受入ではない。
詳細なコマンド・hash・実行条件は[実装記録](../implementation-status.md)に記す。

CPU renderの画像では、髪束の根元と頭皮の接続、棒状の房、簡素な顔・手、皺や縫い目のない服、
丸い塊に見える肩当てが課題として観察された。高品質キャラクター目標は未達である。
texture、skin、clipを含まないため、アニメーション用ゲームキャラクターの完成例にも数えない。
この結果は、raw mesh追加だけではなく、曲面の制御・観察・修正を優先すべきという判断の根拠になる。

## 13. 実装順序と受入計画

次の順序を推奨する。各行は独立した小PRで、schema、worker、Job、negative test、実物検証までを揃える。
機能名は計画中の分類であり、未提供toolを呼ぶための一覧ではない。

| 順序 | slice | 必須の実機証拠 |
|---|---|---|
| M1 | bounded authored mesh＋capability内の制作ガイド | 形状生成/GLB再読込、上限拒否、旧版保持、実MCP受入 |
| M2 | revisionに固定した多視点観察 | 実画像assetとID、旧版との同条件比較、取消/資源回収 |
| M3 | loft/sweep・選択付き局所修正 | 髪束、角、板状防具の修正前後と欠陥の改善 |
| M4 | seam/unwrap/pack・材質共有・high/low bake | UV連続性、normal方向、texture依存、GLB一致 |
| M5 | weight補正/転送・姿勢集・rig拡張 | 衣服付き関節変形、未重みと影響数検査、実再import |
| M6 | clip拡張・root/morph・対象engine | 歩行/動作/表情、loop、実engine表示再生、grant receipt |
| M7 | LOD/collision・各アセット群の生成器 | prop/creature/環境/乗り物の実例と負荷計測 |

M1で本書の基礎を実装し始めるが、M2以降を含む全体は未完了である。GA計画との対応は
[設計・実装計画](../design-game-asset-authoring.md)で管理する。実配布版への反映前は
sourceで新operationが動いてもinstalledで使えるとは報告しない。

代表的な受入作品は、髪・服・部分防具を持つスタイライズ人型、四足クリーチャー、
接合のある武器、モジュール環境、車輪など可動部を持つ乗り物とする。
最初の人型を全機能の代理にせず、共通基盤が整った段階で各群の弱点を評価する。
見た目の目標は実際の参照と利用距離に結び付け、合意なしに「フォトリアル」へ膨らませない。

## 14. 互換性・配布・残る不確実性

Godot公式資料はglTFを推奨し、.blend importも内部でBlenderを使った変換として説明する。[^16]
形式の採用だけで全engineの同じ挙動を保証しない。Unity/Unreal/Godotのどれを優先するかは
実engine受入に入る前に確定し、その版・import設定を固定する。現時点では共通GLB出口の設計までとする。

LLM/VLMの実力はモデル、画像入力、解像度、prompt、文脈長で変わる。本書は特定のローカルモデルが
必要品質を満たすと主張しない。利用可能なruntimeを実測し、入力画像が本当にモデルへ渡ったtraceを確認する。
評価モデルがないことを成功や空の欠陥一覧に置き換えない。新しい重みを採用する場合の同意・ライセンス・
ハードウェア評価は、既存の採用gateを維持する。

導入物はMediaForge data_dirの管理領域に限定し、ユーザーのBlender、~/.claude、
~/.config/opencodeを変更しない。参照した外部repoは固定commitで識別し、本調査では追加runtimeを導入しない。
テスト用ファイルは作成一覧と使用中参照を確認して回収し、結果と再現手順をPRへ残す。
PRに要約を残すことと、raw画像やDBを保存することは別である。

## Sources

実行経路の追補（2026-09-13）: [OpenCode issue #15906](https://github.com/anomalyco/opencode/issues/15906)
にはproviderの不正なtool-call差分と`Tool execution aborted`の組合せが報告されている。
閲覧時はclosed as not plannedであり、修正提供の証拠ではない。
[llama.cpp common/chat.cpp](https://github.com/ggml-org/llama.cpp/blob/master/common/chat.cpp)
にもtool-call数の減少を拒否する同文言がある。これは調査用参照で、未固定HEADを導入しない。
今回の実ログとの照合はimplementation-statusに分離して記録する。
論点は3D操作の追加だけではない。LLMが有効な引数を完了できること、MCPが受理したこと、
workerが目的の形を保存したことの各gateが必要であり、silent retry/JSON補完を品質保証にしない。

以下は本文の資料番号に対応する一次資料一覧。翻訳/UATESTの注記は適用範囲を限定するためのもので、
将来版の機能を現在のruntime対応として扱うためではない。

[^1]: Khronos Group. [glTF 2.0 Specification](https://github.com/KhronosGroup/glTF/blob/c18432787e6d545a1218c1926ccdcfaffd4c116b/specification/2.0/Specification.adoc), snapshot c18432787e6d545a1218c1926ccdcfaffd4c116b. Coordinate System and Units / Skins / Morph Targets / Animation.
[^2]: Gu et al. [BlenderGym: Benchmarking Foundational Model Systems for Graphics Editing](https://arxiv.org/html/2504.01786v1). 2025, CVPR / arXiv v1.
[^3]: [BlenderAlchemy: Editing 3D Graphics with Vision-Language Models](https://arxiv.org/html/2404.17672v1). 2024, arXiv v1, Method / Experiments.
[^4]: arjun988. [blender-director](https://github.com/arjun988/blender-skills/blob/8f778d2405a214b508d4c7d80742be8e43acdd52/.claude/skills/blender-director/SKILL.md) and [MCP tools reference](https://github.com/arjun988/blender-skills/blob/8f778d2405a214b508d4c7d80742be8e43acdd52/.claude/skills/references/mcp-tools.md). Fixed commit 8f778d2405a214b508d4c7d80742be8e43acdd52.
[^5]: ahujasid. [BlenderMCP](https://github.com/ahujasid/blender-mcp). README, architecture/features; 2026-09-13閲覧。調査時HEAD 5f8ddaf6e987c4aa0c3467fcc548838b28f64477、未導入。
[^6]: Princeton Vision & Learning Lab. [Infinigen](https://infinigen.org/) and [official repository](https://github.com/princeton-vl/infinigen). 2023 onward; 2026-09-13閲覧。調査時HEAD 3f58bb886bb1bda681d41240344fe3126ac0e9bd、未導入。
[^7]: Blender Foundation. [Retopology / Remeshing](https://docs.blender.org/manual/en/4.5/modeling/meshes/retopology.html). Blender 4.5 Manual.
[^8]: Blender Foundation. [Generate Hair Curves](https://docs.blender.org/manual/ja/4.5/modeling/geometry_nodes/hair/generation/generate_hair_curves.html). Blender 4.5 Manual, Japanese.
[^9]: Blender Foundation. [Curl Hair Curves](https://docs.blender.org/manual/en/4.5/modeling/geometry_nodes/hair/guides/curl_hair_curves.html). Blender 4.5 Manual.
[^10]: Blender Foundation. [Data Transfer Modifier](https://docs.blender.org/UATEST/manual/en/4.5/modeling/modifiers/modify/data_transfer.html). 4.5 UATEST documentation.
[^11]: Blender Foundation. [Cloth Cache](https://docs.blender.org/manual/it/4.5/physics/cloth/settings/cache.html). Blender 4.5 Manual, Italian.
[^12]: Blender Foundation. [UV Seams](https://docs.blender.org/manual/id/4.5/modeling/meshes/uv/unwrapping/seams.html) and [UV Editing](https://docs.blender.org/UATEST/manual/en/4.5/modeling/meshes/uv/editing.html). Blender 4.5 Manual, Indonesian / UATEST.
[^13]: Blender Foundation. [UV Unwrap Node](https://docs.blender.org/UATEST/manual/en/4.5/modeling/geometry_nodes/mesh/uv/uv_unwrap.html). 4.5 UATEST documentation, face-corner storage.
[^14]: Blender Foundation. [Render Baking](https://docs.blender.org/manual/de/4.5/render/cycles/baking.html). Blender 4.5 Manual, German.
[^15]: Blender Foundation. [Weight Paint Editing](https://docs.blender.org/manual/zh-hans/4.5/sculpt_paint/weight_paint/editing.html). Blender 4.5 Manual, Simplified Chinese.
[^16]: Godot Engine contributors. [Available 3D formats](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html). Stable documentation, 2026-09-13閲覧。対象engine版の受入は別途必要。
