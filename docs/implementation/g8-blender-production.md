# G8 — deterministic Blender production worker

設計の正: `docs/base-plan.md` §3.7 / §12、`docs/implementation/goal-roadmap.md` G8  
前提: G0〜G6 の凍結契約へ加法的に載せる。G7 の model adoption は DEFERRED だが、G5以降は
順序変更可能であり、G8 の CPU-only deterministic path は G7 runtime に依存しない。

## 0. 利用者に届ける状態

利用者またはagentが手持ちの3D assetを opaque `asset:` IDとして渡し、固定された処理だけで
project-ready GLB、manifest、previewを得る。任意のPython、shell、Blender expressionは一度も
実行しない。

G8 は次の全スライスが実機で通るまで未完了である。

```text
B0  Blender runtime/license/preflight boundary
B1  bounded GLB import + independent structural validation
B2  minimal deterministic compile/normalize/export package
B3  typed cleanup/LOD/material/collision/preview profiles
B4  workspace/agent/project placement
B5  installed ControlDeck acceptance + timeout/cancel/recovery
```

## 1. 契約方針

新しい公開operationや3D専用provider/model/routeを作らない。既存契約を次のように再利用する。

```text
asset import                           sourceをasset: IDへ登録
media.inspect                         Blenderを起動しない構造検査
asset.pack + profile=3d.project.glb   deterministic compile package
media.generate agent tool             上記JobRequestの共通入口
media.pack agent tool                 完成assetをgrant:へ配置
```

`asset.pack` のG8結果は `application/zip` とし、少なくとも次を含む。

```text
asset.glb
manifest.json
preview.png
```

これにより既存output enum、Asset必須field、placement receiptを壊さない。source assetを表す
`model/gltf-binary` はAsset MIME enumへ加法的に追加する。GLB以外はB1の実測後にだけ追加し、
推測で `model/gltf+json` / OBJ / FBXを受理しない。

## 2. B0 — runtime / license / process boundary

### 2.1 pinned runtime

実機の `PATH` にBlenderはない。最初の候補は公式 Blender 4.5 LTS Linux x64 portable distributionを
exact archiveへ固定する。

```text
version       Blender 4.5.9 LTS
archive       blender-4.5.9-linux-x64.tar.xz
size          377,929,956 bytes
SHA-256       dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d
source        https://download.blender.org/release/Blender4.5/
```

Blender本体はcore venv、ML runtime、ControlDeckへ入れない。`runtimes/blender-4.5.9/` の専用runtimeを
明示構築し、archive hash、展開root、実行versionをstampする。release bundleへBlender binaryを
暗黙同梱せず、missing時はcapabilityをunavailableにしてprovision actionを示す。

Blender binary distributionはGPLv3-or-later互換条件を伴う。公開する `bpy` worker scriptもBlender
Python APIのlicense条件に従い、`worker_packs/blender/` にcoreと分離してSPDX、GPL-compatible text、
upstream attributionを置く。生成した利用者assetへGPLを転嫁したと記録しない。配布物へBlenderを
含める判断は、対応sourceとthird-party noticeを揃える別release sliceまで行わない。

### 2.3 B0 result（2026-08-26）

`config/blender-runtime.json`、`scripts/blender_runtime.py`、`./mf.sh blender build/status` とtrusted
`worker_packs/blender/preflight.py`を実装した。archiveはexact size/hash、member root、link target、
device/FIFO、member count、展開sizeを検査してからdata filterでstagingへ展開し、実preflight成功後だけ
atomic installする。runtime rootはrepositoryの`runtimes/`配下へ限定した。

実archiveはSHA-256一致、6,510 members / 1,168,332,002 extracted bytes。実Blender 4.5.9 / embedded
Python 3.11.11 / background / glTF import/exportがPASSした。runtime総量は1,546,263,669 bytes。
`status`とready後のidempotent `build`はいずれも0.21秒で、後者は`reused=true`。Blender binaryは
release bundleへ入れず、GPL worker境界を別directoryへ分離した。

B1以降のGLB import、compile、asset、preview、cancel、installed browserは **NOT TESTED**。

### 2.2 fixed subprocess

coreはBlender moduleをimportしない。呼べるcommandは次の固定形だけとする。

```text
blender --background --factory-startup --disable-autoexec \
  --python worker_packs/blender/compile_asset.py -- \
  --request <job-root/request.json> --result <job-root/result.json>
```

`compile_asset.py` はrepository内のtrusted file。chat/intent/filenameをcommand、Python、pathへ連結しない。
`--python-expr`、startup file、addon install、network access、custom scriptは実装しない。引数は配列、
`shell=True`なし、process group単位のcancel、timeout、stdout/stderr上限を必須とする。

## 3. B1 — bounded GLB import and inspection

最初の入力は単一file GLBだけに限定する。external URIや展開treeを持たず、path traversal面を増やさない
ためである。

```text
MIME                     model/gltf-binary
size                     1 byte..64 MiB（拡張は実測後のみ）
header                   magic glTF / version 2 / declared length exact
chunks                   JSON 1件必須、BIN 0..1件、重複/unknownはreject
JSON                     UTF-8、bounded parse、object root
counts                   node/mesh/primitive/material/image/accessor/bufferViewをbounded
references               buffer/image URIはreject（GLB内蔵だけ）
extensions               required extensionはallowlist外をreject
numbers                  NaN/Infinity、negative count、範囲外offsetをreject
```

Blenderとは独立したcore validatorでheader/chunk/range/countを検査する。同一parserだけでimportとexportを
成功扱いにしない。importは元bytesを変更せずhashし、`asset.import` provenanceへsource filenameを除く
bounded factsとvalidation versionを保存する。raw Host pathは受け取らず、browser uploadまたはHost
scoped-files bridgeの `grant:` bytesだけを読む。

B1の初期allowlistはrequired extension 0件とする。`extensionsUsed`だけのoptional declarationは記録するが、
required extensionはB2で実Blender re-importを個別に確認してから追加する。sparse accessorも同じ理由で
B1ではfail-closedとし、未検証のlayoutを通過扱いにしない。

B1 fixtureはrepository内でコード生成した小さいtriangle/cube GLBとする。第三者modelをtest fixtureへ
持ち込まず、licenseを曖昧にしない。truncated header、declared-length mismatch、chunk escape、external URI、
oversized count、symlink escapeをnegative testに含める。

## 4. B2 — minimal compiler

B2は「入力GLBを開き、sceneを正規化し、検査済みGLB packageを返す」縦スライスだけを行う。

固定処理:

```text
factory startup / autoexec off
GLB import
object type allowlist = MESH / EMPTY / ARMATURE
camera/light/script/driver/custom property除去
unit meters / glTF Y-up export
finite transform検査、apply transform
orphan data purge
normal検査（repairは明示optionのみ）
GLB export（embedded resources）
independent GLB validator再実行
deterministic ZIP package
```

Blenderが報告するmesh/object/vertex/edge/triangle/material/texture/boundsの統計と、入力・出力hashを
manifestへ記録する。ZIP entry順、timestamp、permission、compression設定を固定する。同一fixtureを
別processで2回compileし、GLB、manifest、ZIPのSHA-256一致をgateにする。Blenderが非決定的metadataを
埋める場合は、そのfieldを正規化するか **DEFERRED** とし、hash assertionを緩めない。

B2はCPU-onlyでありGPU Broker leaseを取らない。hosted executionでは既存Host Jobへphase/progressを
報告する。

## 5. B3 — typed production options

B2完了後、private versioned schema `3d.compile-options@1` に次だけを加える。自由形式operator名や
任意property mapは受理しない。

```text
apply_transforms          true固定
repair_normals            false/true
remove_degenerate         false/true
merge_by_distance_m       null or bounded positive value
triangle_budget           null or 12..measured maximum
lod_ratios                bounded descending list（最大3）
collision                 none / box / convex_hull
materials                 preserve / basic_pbr
preview                    fixed_workbench
```

自動UV unwrap、texture bake、decimateは入力品質を壊し得るため、各々golden fixture、error bound、manifest
差分が定義できるまで既定off。入力rig/animationを壊すoptionは静的meshと同じprofileへ混ぜない。

B3実測でtriangle budgetの受理上限を200,000とした。コード生成200,978-triangle gridの
200,000 budgetは199,999 trianglesへ収束し、2回のGLB/ZIP hashが一致した。未計測のそれ以上は
受理しない。UV unwrapとtexture bakeは引き続き実装しない。

各処理はmanifestのordered operation listへparameters/results/warningsを残す。triangle budget未達、
non-manifold、missing texture、unsupported extensionをwarningとfailureに分類し、握り潰さない。

## 6. B4 — workspace / agent / placement

既存Create/Library/Activity/Settingsを再利用し、Simple modeはruntime availableかつ3D asset選択時だけ
「プロジェクト用GLB」を出す。Advancedでtyped optionsへ到達できる。3D node graphやBlender GUIは作らない。

LibraryはZIP package cardにpreviewを表示し、内容を自動展開しない。agentは既存 `media.generate` で
`asset.pack` + `3d.project.glb`を実行し、既存 `media.pack` でoutput `grant:`へZIPを置く。raw project
path、Blender path、script bodyをpublic input/outputへ出さない。

`3d.project.glb` は計画済みのcanonical profile名だが、G1時点のprofile patternが先頭英字のみで
受理できなかった。既存profileを壊さない加法的変更として、先頭にASCII小文字または数字を
許可する。それ以外の文字、path、任意operator名は引き続き受理しない。

## 7. B5 — installed acceptance

実installed ControlDeckで次を測る。

```text
browser/scoped-filesからGLB import
workspaceとagentからcompile各1件
Host Job phase / reconnect / cancel / timeout
別process2回のdeterministic hash
GLB independent validation / Blender re-import
manifest mesh facts / preview PNG / ZIP bounds
grant placement receipt / committed bytes hash
Blender child 0 / job root cleanup / core healthy
SonicForge activeのままCPU-only jobがGPU lease 0
```

cancelは実Blender childへ届き、partial ZIP/assetを登録しない。core kill後のqueued job recoveryと、running
jobの明示failureも確認する。ControlDeck変更が必要ならMedia Forge側で解けない理由を1行記録し、generic
Host機能だけを別PRにする。

## 8. 完了判定

B0〜B5、focused/full gate、実Blender process、installed browser/agent/grant、deterministic hashes、
timeout/cancel/cleanupの証拠が揃ったときだけG8完了。Blender未導入、fixture-only、schema/test成功だけを
「3Dが動く」と記録しない。

### 8.1 B5 result（2026-08-26）

B5は実installed ControlDeckでPASSした。browser bytes / Host scoped-file picker、workspace / Agentの
実Blender compile、実行中reload後のreconnect、Host Job最終phase/progress、別process 2回の同一hash、
独立GLB/PNG/ZIP/manifest検査、実grant commitとcommitted byte hash、実process cancel、0.05秒timeout、
queued/running restart recovery、work cleanup、CPU-only resource request 0を確認した。

Hostのcross-filesystem output commitだけはMedia Forge境界内では解けなかった。raw pathを受けずatomic
no-overwrite契約を維持するため、generic Host修正をControlDeck PR #246として別mergeした。G8側の公開経路は
既存`asset.pack` / `media.generate` / `media.pack`、opaque `asset:` / `grant:`のままである。

B0-B5の完了条件はすべて満たした。rig/animation fixtureは未評価なので、`3d.project.glb`は引き続き
実測済み静的meshの範囲だけを保証し、別profileまたは追加評価なしに対応を主張しない。
