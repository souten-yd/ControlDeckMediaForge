# Codex実装指示 — Media Forge 完成までのゴール機能ロードマップ

対象リポジトリ: `souten-yd/ControlDeckMediaForge`
参照（読み取り専用）: `souten-yd/ControlDeck`（`8681eb7` 以降）
設計の正: `docs/base-plan.md` / `docs/controldeck-integration-plan.md`

先行指示: [`mf0-addon-core.md`](mf0-addon-core.md)（G0 に相当。本書はその続きを含む全体）
環境: [`mf0-0-environment.md`](mf0-0-environment.md)

---

## 0. 進め方の原則

### 0.1 ゴール機能で進める

技術レイヤ（API層 → worker層 → UI層）で横に積まない。
**「利用者が何をできるようになるか」で縦に切る。**

各ゴールは単独で出荷可能であること。
「基盤だけできたが誰も何もできない」状態を作らない。

```text
G0  Add-onとして成立する          （基盤・fake worker）
G1  ローカルで画像が作れる
G2  画像を壊さずに直せる
G3  同じキャラ・同じ絵柄で作れる
G4  コーディングエージェントが素材を置ける
G5  M5Stack companion が実運用できる
G6  2Dゲーム素材一式が出せる
G7  動かせる（動画・アニメーション）
G8  3D素材がプロジェクトに載る
G9  3Dを生成できる（実験的）
G10 手持ち資料を参照源にできる
```

G0〜G4 までで「実用的な local media service」として成立する。
G5 以降は用途別の上積みであり、順序は入れ替えてよい。
**G7 以降を先に着手しない。** 理由は §0.4。

### 0.2 各ゴールの完了定義

ゴールは以下がすべて満たされたときに完了とする。

```text
1. 利用者の言葉で書かれた受け入れ条件を、実機で満たす
2. public API / addon.json / schemas が前ゴールから変わっていない
   （変わる場合は §0.3 の手続きを踏む）
3. 実ハードウェア（R9700 32GB / ROCm / NVMe）で実測値を記録した
4. 前ゴールまでのテストが1件も壊れていない
5. docs/implementation-status.md に「何を実測し、何が NOT TESTED か」を記録した
```

lint 成功・build 成功を「動く」と記録しない。

### 0.3 契約凍結

**G1 完了時点で public 契約を凍結する。**

```text
凍結対象
    schemas/ 配下の公開JSON schema
    addon.json の contribution 定義
    agent tool 名と引数
    workflow executor の type と schema
    asset / provenance の必須フィールド
```

以降のゴールで契約を変更したくなったら、それは**設計が漏れているサイン**。
まず「追加で済むか」を検討する。追加なら可。破壊的変更は以下を全部書いてからのみ:

```text
なぜ追加では足りないか
既存 asset / workflow / agent 設定への影響
移行手順
version bump（schema_version / contract range）
```

これを書かずに変更しないこと。

### 0.4 順序を守る理由

`docs/base-plan.md` §3.7 が既に判断している。動画・3D は
品質・VRAM・AMD対応・ライセンスのいずれも予測が難しい。
先に着手すると、不安定な領域の都合で public 契約が歪む。

先に安定領域（画像・編集・一貫性・エージェント連携）で契約を固め、
不安定領域はその契約に**従わせる**。逆にしない。

### 0.5 モデル採用ゲート

新しいモデル／ランタイムを既定に昇格させる前に、
`docs/base-plan.md` §24 の10項目に答えを書くこと。

特に **#10「後で削除しても public API が変わらないか」** に No なら採用しない。
これは設計の異常を示す。

実機ベンチ未実施のモデルを既定にしない。
ベンチは R9700 / ROCm / NVMe 上で、VRAM実測・所要時間・失敗率を記録する。

### 0.6 GPU 共存の義務

すべてのゴールで、GPU を使う job は以下を守る。

```text
ControlDeck broker から lease を取得してから実行する
estimated_runtime_sec を必ず申告する（未申告は ControlDeck 側で退避判断不能）
vram の resident / execution_peak / cold_load_peak / headroom を分けて申告する
confidence を実測に応じて更新する（fake=low、実測後=measured）
lease を renew する。TTL 切れの強制回収に依存しない
cancel で必ず解放する
```

Media Forge 側に独自のグローバルGPUスケジューラを作らない。
worker ローカルの安全ガード（同時実行数など）だけ持つ。

---

## G0 — Add-on として成立する

**別紙 [`mf0-addon-core.md`](mf0-addon-core.md) に従う。本書では詳細を繰り返さない。**
環境構築は [`mf0-0-environment.md`](mf0-0-environment.md)（MF0-0）が先行する。

利用者から見たゴール:

> ControlDeck の「拡張機能」から Media Forge を有効にすると Media が現れ、
> 無効にすると跡形もなく消える。中身はまだ fake だが、体験は完成している。

完了条件の本体:

```text
fake worker を実 worker に差し替えるとき、
api/ ・ schemas/ ・ addon.json を変更しなくてよい構造になっている
```

---

## G1 — ローカルで画像が作れる

### 利用者から見たゴール

> ControlDeck の Media を開いて、作りたいものを書いて実行すると、
> クラウドを使わずにローカルGPUで画像ができる。
> どのモデルで作られたかを後から確認できる。

### 実装

```text
ROCm/PyTorch image worker（worker_packs/image/）
Diffusers アダプタ
native アダプタ interface（Diffusers非対応モデル用の口だけ作る）
モデルレジストリの実体化（インストール済みモデルの検出・capability記述）
capability router（auto / fast / balanced / quality / low_vram / manual）
text_to_image
Create UI の実動作化
Library のサムネイル・履歴
deterministic validator（寸法・mode・alpha・非空）
```

worker は **別プロセス・別 Python 環境**にする。
`backend/mediaforge` に PyTorch を import しない。
これを守らないと ControlDeck 側の依存分離が意味を失う。

### 初回ベンチ候補

FLUX.2 [klein] 4B（Apache-2.0、多参照編集に強い候補）。
ただし §0.5 のゲートを通ること。gfx1201 で動かない・遅すぎる場合は
Qwen-Image 系へ切り替える。**候補に固執しない。**

実測して記録する項目:

```text
モデルロード時間（cold / warm）
1枚あたり生成時間（解像度・step別）
VRAM: resident / execution peak / cold-load peak
連続生成時の安定性
ROCm での既知の不具合と回避策
```

この実測値がそのまま lease request の VRAM 見積りになる。
推定値で埋めない。

### 契約不変条件

```text
public API に model_id が必須引数として現れない（model_policy=auto で動く）
capability 名で routing する（image.text_to_image）
G0 の job / asset / provenance schema を変えない
```

### テスト

```text
router: capability + policy + VRAM から決定的にモデルを選ぶ（fake registry）
router: 適合モデル無し -> 明示エラー（黙って別capabilityへ落ちない）
worker crash -> job failed、lease 解放、プロセス巻き添えなし
OOM -> resource_oom へ正規化し、次回 admission の floor を上げる
local_only: remote 指定が backend で拒否される
validator: 寸法 / mode / alpha
provenance に実 model_id / weights_hash / license が入る
```

### 実機E2E

```text
Create から実生成 -> ControlDeck Jobs に出る -> 完了 -> Library に出る
LLM 稼働中に画像生成 -> broker が両立させるか、待機理由が表示される
生成中に cancel -> lease 解放を ControlDeck の /api/v1/resources で確認
provenance を開いてモデル・seed・license が読める
同じ seed / 同じ設定で再生成すると同一出力になる
```

### 完了条件

> M5 も game も preset も使わずに、普通の画像生成がクラウド無しで動く。

---

## G2 — 画像を壊さずに直せる

### 利用者から見たゴール

> 既存の画像の一部だけを直したい。
> 指定した範囲の外側は 1 ピクセルも変わらないと保証してほしい。

### 実装

```text
image.edit（single reference）
image.inpaint / outpaint
strict_edit capability（base-plan §2.6）
    編集マスクの受領または導出
    マスク領域のみ生成
    元画像へ合成
    マスク外を bit-for-bit コピー
    マスク外のピクセル差分検証
multi_reference_edit（モデルが対応する場合）
variation
VLM semantic review（bounded retry）
```

### strict_edit の実装規則

**生成モデルに全体を作り直させない。** これが G2 の核心。

```text
1. 元画像を保持
2. マスク領域だけを生成
3. 合成
4. マスク外の全ピクセルを元画像からコピー
5. 検証: マスク外の差分が 0 でなければ fail
```

手順5で fail したら成功として返さない。**再生成でごまかさない。**

### VLM review の制約

```text
retry budget を必ず持つ（無限ループ禁止）
deterministic 失敗を semantic pass が上書きしてはいけない
主観的な品質判断は「代替案を返す」を既定にし、
  自動再生成は明示 opt-in のときだけ
VLM は ControlDeck の LLM Gateway 経由でもよい（別モデル常駐を避けられる）
```

VLM を Media Forge 側に常駐させるか Gateway 経由にするかは、
VRAM 実測を見て決める。Gateway 経由なら broker の residency 管理に乗る利点がある。

### 契約不変条件

```text
strict_edit は image.edit の constraint であり、別 operation にしない
マスクは asset_id で渡す（path を渡さない）
```

### テスト

```text
strict_edit: マスク外のピクセル差分 0（複数解像度・alpha有無）
strict_edit: マスク不正（サイズ不一致・空・全面）-> 明示エラー
strict_edit: 検証失敗時に success を返さない
retry budget を超えたら明示的に失敗する
semantic pass が deterministic fail を上書きしない
lineage: 編集結果の親が元 asset になる
```

### 実機E2E

```text
実画像で strict_edit -> マスク外差分 0 を実測で確認
edit -> 再 edit -> lineage が3世代辿れる
VLM review 有効時に retry が budget で止まる
```

### 完了条件

> 「ここだけ直して」が、ピクセル単位の保証付きで通る。

---

## G3 — 同じキャラ・同じ絵柄で作れる

### 利用者から見たゴール

> 同じキャラクターを、別のポーズ・別の表情で何枚も作りたい。
> 毎回顔が変わるのは困る。

### 実装

`docs/base-plan.md` §10 の順序を守る。

```text
1. 参照アセット集合（reference collection）
2. Character Profile / Style Profile（構造化された記述）
3. 多参照生成・編集
4. LoRA / fine-tuning は「必要になったら」
```

**4 を前提にしない。** 学習を必須にすると、素材1枚作るのに数時間かかる製品になる。

```text
CharacterProfile   外見・服装・色・特徴・NGリスト・参照asset群
StyleProfile       画風・線・彩色・質感・参照asset群
reference collection の管理UI
profile を constraint として generate/edit に渡す
一貫性の自己評価（VLM で「同一キャラに見えるか」を advisory 判定）
```

### 契約不変条件

```text
profile は constraint であり、専用 operation を作らない
    image.generate(character_profile_id=...) であって
    character.generate ではない
profile が無くても generate は動く
```

### テスト

```text
profile 指定が constraint として router / worker に伝わる
profile 削除後も過去 asset の provenance から内容が復元できる
参照 asset のハッシュが provenance に記録される
profile 無しでも generate が動く（必須化していない）
```

### 実機E2E

```text
1キャラを5枚生成し、同一性を目視確認
表情違いを strict_edit で作り、キャラが崩れないことを確認
```

### 完了条件

> 学習なしで、同じキャラが続けて作れる。

---

## G4 — コーディングエージェントが素材を置ける

### 利用者から見たゴール

> OpenCode に「このゲームに敵キャラを追加して」と言うと、
> 素材が生成され、プロジェクトの正しい場所に置かれ、コードから参照できる。

### 実装

```text
agent tool の実動作化（media.capabilities / generate / edit / inspect / pack）
asset pack 出力（images / frames / manifest / preview）
project への commit（ControlDeck の grant 経由）
プロジェクト規約の inspect（命名・配置・形式の読み取り）
Workflow executor の実動作化
Context action の実動作化（Files / Project Lab）
```

### 権限の規則

```text
agent が media tool を呼んだからといって、
Media Forge に project 全体のアクセスを渡さない

要求単位で
    scoped project grant
    scoped input file
    scoped output destination
だけを受け取る

path 文字列を受け取らない。grant: ID のみ
```

ControlDeck 側にはbrowser file/export grantとRuntime output commitがある。
ただしOpenCode MCP tokenを現在projectへ束縛し、非対話でproject output grantを発行する
汎用経路は未実装である。`controldeck-integration-plan.md` §11.1のHost prerequisiteを
先に実装する。**path がMedia Forgeへ渡ってきたらControlDeck側のバグとして報告する。**
受け入れない。

### エージェント体験の要件

```text
agent には job_id / asset_id を返す。ログからファイル名を拾わせない
capability は available / unavailable / experimental を返す
モデル名を返さない（ユーザーが明示 pin したときのみ）
生成は候補を返し、採用は別アクション（勝手に上書きしない）
```

### テスト

```text
tool 応答にモデル名が含まれない
grant 外への書き込みが拒否される
symlink / realpath 脱出が拒否される
agent が job_id / asset_id を受け取る
capability の unavailable が discovery に反映される
workflow dry-run が Media Forge を呼ばない
```

### 実機E2E

```text
OpenCode から実際に素材を生成し、実プロジェクトへ配置
Files の Open with -> edit-image が動く
Workflow に media.generate を組み込んで実行
Add-on disable 後、保存済み workflow が unavailable 表示で壊れない
```

### 完了条件

> エージェントが人間の手を借りずに素材を作って置ける。
> ただしファイルシステムの境界は一度も越えていない。

---

## G5 — M5Stack companion が実運用できる

### 利用者から見たゴール

> 今 手作業でやっている M5 companion の表情差分作成を、
> Media Forge に置き換えられる。寸法もアルファも安全領域も保証される。

### 実装

```text
profiles/m5/ プロファイル群
    m5.companion.base / eyes / mouth / expression / pose / pack
制約: 正確なキャンバス寸法、RGBA必須、透過背景、
      safe rectangle、アンカー／瞳中心、レイヤ境界、
      最大変更領域、ファイル命名規則
deterministic validator（base-plan §9.3）
pack exporter（atlas + manifest）
golden test 用の実テンプレート fixture
```

G2 の strict_edit をそのまま使う。**M5専用の編集経路を作らない。**

### テスト（golden）

実テンプレートを fixture にして固定する。

```text
キャンバス寸法が完全一致
背景が透過
safe region 内に収まる
アンカー座標が期待値
許可マスク外のピクセルが 1 つも変わっていない
期待するファイル名一式が揃う
manifest schema が妥当
```

### 完了条件

> 現在の M5 companion 作業が Media Forge で完結し、
> 出力が手作業と同等以上の厳密さを持つ。

---

## G6 — 2Dゲーム素材一式が出せる

### 利用者から見たゴール

> キャラのスプライト、敵、アイコン、UI、背景を、
> エンジンにそのまま取り込める形で一括生成したい。

### 実装

```text
profiles/game2d/
    portrait / sprite frames / spritesheet / enemy pack /
    item・icon pack / UI pack / tiles・background / VFX
決定的な frame 正規化・クロップ・アトラス packing
engine 出力（godot / generic）
pack manifest
```

**アトラス幾何を生成モデルに任せない。** 生成後に決定的に配置する。

### 契約不変条件

```text
pack は asset.pack operation の profile であり、専用APIを作らない
engine 出力は後付け可能な形にする（godot 固定にしない）
```

### 完了条件

> 生成した pack を Godot にドロップして、そのまま使える。

---

## G7 — 動かせる（動画・アニメーション）

**ここから不安定領域。G1〜G4 の契約に従わせる。**

### 利用者から見たゴール

> 静止画から短いアニメーションを作りたい。
> 長時間GPUを占有するが、その間もチャットは使えるか、
> 少なくとも何が起きているか分かる。

### 実装

```text
video runtime アダプタ
FFmpeg worker（正規化・fps・寸法・尺・サムネ・フレーム抽出・ループ）
text_to_video / image_to_video
multi_keyframe（対応モデルのみ）
長時間 job の進捗・キャンセル
animation 向け profile
```

### 候補

Wan2.2 系 / LTX-2 系。§0.5 のゲートを通ること。
gfx1201 での動作可否が最大のリスク。**動かなければ延期する。** 無理に通さない。

### GPU 共存がここで効く

動画は 20GB 超・数分単位。ここで初めて
ControlDeck の managed supervision（LLM退避）が実際に必要になる。

```text
estimated_runtime_sec を正確に申告する（退避判断の入力）
実測を重ねて confidence を measured へ上げる
待機中の理由・見込み・キャンセルが ControlDeck UI に出ることを確認する
job 完了後に lease を確実に解放し、LLM が復帰することを確認する
```

**ControlDeck 側の warm reload cost の実サンプルは、ここで初めて貯まる。**
G7 の実機検証では、退避が起きた回数と抑止理由を記録すること。

### 重要な判断

2Dゲームのアニメーションに動画モデルを自動で使わない。
ポーズ／キーフレーム生成＋フレーム整形＋決定的アトラスの方が
安定して安く済む場合がある。router に安い経路を選ばせること。

### 完了条件

> 普通のチャット操作から動画が作れる。
> 生成中も ControlDeck 全体が固まらず、何が起きているか分かる。

---

## G8 — 3D素材がプロジェクトに載る

### 利用者から見たゴール

> 手持ちの 3D モデルを、ゲームで使える形に整えてほしい。
> AI生成ではなく、確実な処理として。

### 実装

Blender を**決定的なアセットコンパイラ**として扱う。GUI 自動操作ではない。

```text
Blender background worker
typed operation: import / 変換正規化 / mesh検証・クリーンアップ /
    法線修復 / decimate / LOD / UV / マテリアル / ベイク /
    コリジョンプロキシ / ターンテーブル / GLB・GLTF・FBX export
3D asset manifest とプレビュー
agent 向け blender tool
```

### 安全規則（必須）

```text
chat から出た任意の Blender Python を実行しない
検証済み operation schema と信頼テンプレートのみ
bounded worker job / 隔離作業ディレクトリ / timeout / cancel
パス allowlist
custom script は別権限の expert mode（既定 off）
```

### 完了条件

> エージェントが既存 3D アセットを安全に処理して
> プロジェクト用 GLB を出せる。任意スクリプト実行は一度も発生しない。

---

## G9 — 3Dを生成できる（実験的）

### 利用者から見たゴール

> 画像から 3D を作ってみたい。品質は保証されなくてよいが、
> 出てきたものは G8 の処理を通って製品形式になってほしい。

### 実装

```text
image-to-3D プロバイダ アダプタ（Hunyuan3D 2.1 等）
参照・多視点の準備
raw mesh -> Blender production pipeline
experimental ラベルの明示
```

```text
concept/reference 画像
  -> 多視点参照（任意）
  -> 実験的3Dジェネレータ
  -> raw mesh / materials
  -> Blender worker
  -> 検証 + LOD + export
  -> GLB + preview + manifest
```

### 規則

```text
capability を experimental として返す。available と偽らない
G9 の失敗が G8 の安定機能を巻き込まないこと
トポロジ品質を約束しない（UIでも明示）
```

### 完了条件

> 生成3Dが同じ asset lineage と検証パイプラインを流れる。
> 失敗しても Blender 機能は無傷。

---

## G10 — 手持ち資料を参照源にできる

### 利用者から見たゴール

> 所有している資料アーカイブを取り込んで、
> 参照・検索・キャラ設定の材料として使いたい。

### 実装

```text
ZIP / CBZ 取り込み（原本は read-only 保持）
ページ抽出・キャッシュ・重複／ハッシュ検出
メタデータと権利・利用方針フィールド
任意ワーカー: パネル分割 / OCR / 吹き出し領域 /
    embeddings 検索 / キャラクタクラスタリング（ユーザー訂正可） / タグ付け
参照コレクション / Character Profile / Style Profile への流し込み
```

### 権利の扱い（必須）

```text
取り込みが自動的に学習データ化されないこと
UI で3つの許可を明確に分ける
    参照・検索
    生成時参照
    学習
学習は別権限・明示 opt-in・利用者の権利確認が前提
```

単一利用者のローカル環境でも分ける。
混在ライブラリの将来の誤用を防ぐため。

### 完了条件

> 所有アーカイブが検索可能な参照コーパスとして使える。
> 学習データには一度も自動変換されていない。

---

## 1. 全ゴール共通の不変条件

各ゴールの完了時に必ず確認する。1つでも崩れていれば未完了。

```text
public API にモデル名が必須で現れていない
capability 名で routing している
provenance が全生成物に付いている（fake 由来でも）
lineage が辿れる
local_only が backend で強制されている
path 文字列を ControlDeck から受け取っていない
GPU 使用 job が lease を取り、estimated_runtime_sec を申告している
worker crash が Media Forge 本体を巻き込まない
Media Forge の障害が ControlDeck の障害として現れない
disable でデータが消えない
前ゴールのテストが全部通る
```

---

## 2. 止める判断

以下に当たったら、無理に完成させずに延期して記録する。

```text
モデルが gfx1201 / ROCm で安定動作しない
    -> 代替候補を探す。カスタムカーネルの自作へ踏み込まない
VRAM が実測で収まらない
    -> 量子化・解像度制限を検討し、それでも駄目なら延期
public 契約を壊さないと実装できない
    -> 設計の見直し。契約を曲げない
依存が ControlDeck 側へ漏れそうになる
    -> 境界が間違っている。実装を止めて設計へ戻る
```

延期は失敗ではない。`docs/implementation-status.md` に
「なぜ延期したか」「再開条件は何か」を書けば正しい進行。

---

## 3. ドキュメント運用

```text
docs/implementation-status.md
    ゴール単位で、実測値・NOT TESTED・延期理由を記録
docs/api.md
    公開API。schemas/ と常に同期
docs/models.md
    採用モデルと §0.5 ゲートの回答、実測ベンチ
docs/base-plan.md
    ゴール完了状況を反映。設計変更時のみ本文を更新
```

`docs/base-plan.md` §3（却下した案）は**消さない**。
同じ議論に戻らないための記録なので、判断が変わったら追記する形で残す。

---

## 4. 完成の定義

Media Forge は以下が成立したときに「完成」とする。

> ローカルGPU上で、画像・編集・一貫性・エージェント連携が実用水準で動き、
> 用途別プロファイル（M5 / 2Dゲーム）が厳密な保証付きで production に使え、
> 動画・3D・参照ライブラリが同じ契約の上に載っている。
>
> かつ、ここまでのどの機能追加でも、ControlDeck 本体に
> Media 固有のコード・依存・ルートが 1 行も入っていない。

後半が守れていなければ、前半が全部動いても未完成とする。
汎用 Add-on Platform を作った意味が消えるため。
