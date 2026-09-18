# v0.28.85 installed reference-authoring acceptance

## Scope and provenance

利用者の追加要求は実VLM評価、可動版導入、恐竜の品質比較。
source/fakeの成功をinstalled/semanticの成功へ読み替えない。
作業worktreeは `/tmp/mediaforge-reference-plan-20260918`。
利用者root `feat/release-gpu-on-demand` / `9304129` は変更していない。

## Signed release and installed data preservation

PR536〜545を依存順にmainへ統合。PR546のrelease mergeは
`df70be4a0f36431302f9588f0335086d1d48f556`。
固定commitから `./mf.sh bundle build 0.28.85` で構築し既存発行鍵で署名した。
Host catalogのtrusted public keyとの一致を検査。公開後の4ファイルを再取得し、
元配布物とのbyte一致、Ed25519署名、manifest identity/version/hash/sizeを独立検査した。

- Release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.85
- Linux bundle: 31,765,402 bytes
- SHA256: `0c040d809b6bd0de6f969db5a2828b7b07719d9634f1db3deebf97cb57805d10`
- Release code full gate: 2,162 passed, 2 warnings, 229.83 seconds; Node mixer 6 passed.
- 通常更新: Host repositoryで `./deck.sh feature update media-forge`。
  応答version=0.28.85、previous_version=0.28.84、health=healthy。
- installed `current` は `versions/0.28.85`、systemd MainPID=1954080、active/running。
- 実 `GET http://127.0.0.1:9130/health` はhealthy。
  `media.scene.observe/review/refine/bake` を含むcontribution availableを確認。

更新直前にJobs1437件、GUI72件、runtime operations43件が全終端であることを検査。
DB全16tableの論理row hash、asset file2604件の名前/size/mtime属性hash、
Blender runtime registry hashを更新前後で採取し `cmp` exit0。
これはasset全byte再hashの主張ではない。SQLite/registry復旧snapshotを保持している。

証跡root:
`/data1tb/ControlDeck/data/feature-data/media-forge/maintenance/release-0.28.85-20260918`
の `download-verification.json`、`bundle-audit.json`、`update.log`、
`preinstall.json`、`after.json`。

## Discovery defect found during installed acceptance

実MCP `tools/list` は26toolsでobserve/review/refine/bakeを含む一方、
scene.create/editは欠落。Hostの実装でschema response decoded bytesの上限64KiBを確認。
installed HTTP responseはcreate75,500B/edit75,434Bで上限超過だった。
health availableはtool schemaの実利用可否を保証しない。

MediaForgeのschema endpointのみJSONResponseへ変更し、canonical schemaを内容不変で
compactに配信する。Host変更なし。実source HTTP(:9149)ではcreate42,547B/
edit42,609B、JSON parsed equalityとmedia typeを確認。全公開schemaのHTTP内容一致と
64KiB上限を回帰試験で検査する。schemasの契約フィールド変更なし。
証跡は `installed-contracts-before-fix.json` と `schema-http-comparison.json`。
source serverの初回はPYTHONPATHにrepo rootがなくimport失敗、修正後の実HTTPを採用。
署名更新版でのMCP再確認はこの時点ではNOT TESTED。

## Real OpenCode and VLM

既存private MCP-only configの受入runnerへcustom task機能を追加。
既存global OpenCode設定/Hostコード/model weightsは変更しない。
新規project `MF3DS-Trex-VLM-20260918` から旧T-Rexの固定revisionを観察した。
実run exit0、530.018秒、10tool calls、session `ses_f4d5915d7ffeXkBc6Y76IxCDPq`。
初回応答まで359.845秒で、title/build起動時の待機を含む。待機を除外した値ではない。

- scene `scene_9258c7732eff4374858fd3ea6fb91480`
- revision `revision_9156adc10d1b4d4e8635ee50c7fbed3f`
- observe Job `job_8d451ed5345f4007aaababf6f5f5e103`: succeeded、4.679秒。
- review Job `job_d3b4394bd650496d80e2a5003574011f`: succeeded、22.986秒。
  Job時刻差は待機を含み、モデル単体生成秒ではない。
- report Asset `asset_d63493666af94e39a059a82f2a0314bf`。
- 納品 `/data1tb/ControlDeck/CodeDEV/MF3DS-Trex-VLM-20260918/exports/baseline-review.zip`。

review.jsonのsemantic_review=completed、verdict=issues_found、asset_approval=not_granted。
実VLMは歯の不可視、細い円錐状の尾、腕/爪の不明瞭さの3件を画像方向付きで指摘。
`modeling.add_teeth/detail_arms/reshape_tail` は未対応操作として記録され、実行しない。
4入力画像＋ZIPのbyte hash/metadata/provenance一致、画像evidenceのID/hashを独立検証。
`baseline-independent/` に実画像・report・来歴を保存し、親エージェントも斜め画像を目視。

この結果は実installed OpenCode→MCP→Blender観察→Host VLM→ZIP/grant納品のPASS。
構造validatorのPASSと対照的に形状は粗く、造形品質はFAIL/改善対象。
旧T-Rexは歴史的baselineであり、R2の同一brief各3試行の代用ではない。

schema修正後full gateは2,171 passed / 2 warnings / 229.08秒、exit0。
参照画像生成の新規project `MF3DS-Trex-References-20260918` は実行中。

## Canonical-conditioned references and packaging discovery failure

実OpenCode project `MF3DS-Trex-References-20260918` はcanonical1枚と同canonicalを
入力にしたfront/side/back3枚を実生成。4画像のhash/来歴、3editの親canonical一致を独立検証。
既存採用FLUX.2-klein-4B、runtime0.40.0、CPU offload/int8配置。新weights導入なし。
canonical `asset_40fcc3b7ab5f4ea38405e1ea84dab470`、front `asset_4f416d60cdc24d74877f43d70e8e210e`、
side `asset_a1b7799ed95b472bae22477e98f8baf9`、back `asset_4927ce10fc1044dd99fb9fa50ad3fdf3`。
親の目視では体色/体形は概ね保持するが腕が長く指/趾数はbrief不一致、側面も厳密な正投影を
保証できない。生成成功を解剖学/多視点整合性の承認にしない。

最初のLLMはgrant:placeholderを誤使用し失敗。その後canonical/edit生成は成功したが、
ReferenceSet packでconstraintsをasset_briefへ置換/省略し繰返しinvalid_reference_set。
途中image.generate/profile=3d.reference_set/intent=placeholderの不要な画像生成も1件発生した。
この診断runだけPID1967321をTERM、399.653秒/10tool calls/exit-15/納品0。
停止後MediaForge active Job0を確認。失敗runは成功扱いせず、生成済み4画像/全Jobは保持。

実MCP公開job-request schemaのconstraints.propertiesにReferenceSetSpec項目がないため、
必要なname/views/scale_m/origin_notes等を加法的に掲載し、同じ既存asset.packへ送れるよう修正。
既存generic required/自由拡張を保持。別toolや第二storeは追加しない。
実source HTTPではjob-request14,429Bでcanonical JSON一致、必要項目あり。
regressionは公開schemaに従う実pack要求と通常image.generate/free-form互換を確認。
0.28.86へ含め、再生成せず4画像のpack/納品のみを新規projectで再検証する。

## Review vocabulary correction

旧T-Rex実VLMはmodeling.add_teeth等を提案したが、review promptは既知のobject IDのみを
渡し、検査対象のoperation語彙を渡していなかった。現在のscene_operation_typesを明示し、
該当しない提案はnullとする案内を追加。未対応提案の記録/needs_review/非実行は保持する。
実候補修正に進めるかは更新後の別評価で確認し、prompt変更だけで改善成功とはしない。

## Remaining gates

実canonical条件付き参照画像の整合性承認、修正後pack納品、実VLM比較・候補改善、R2の3条件×各3試行、
完成恐竜の変形・接地・自然なclip品質はNOT TESTED。

0.28.86最終./mf.sh test: 2,172 passed, 2 warnings, 228.15秒、exit0。以後product変更なし。

## v0.28.86 signed installation and repaired MCP discovery

PR548 merge `bb0a9917ef3515b97adee5461e6f39df8ac828b6` is tree-identical to tested80b183c。
[Release](https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.86)。
Bundle31,768,618B / SHA256 `14c8569f0eb6da2c04dc329686b06c4b5638874c8b109e38014f9993f286a664`。
既存鍵署名、公開先の4file再取得byte一致、Host現在のtrusted keyによるEd25519検証、
manifest version/identity/size/hash、6tar entries/224embedded resourcesを検査。
診断の初回auditは公開CA証明書certifi/cacert.pemをprivate keyと誤分類してFAIL。
証明書だけを例外としPRIVATE KEYを含まないことを追加確認した最終auditはPASS。
product修正や配布物の差替えは行っていない。

通常 `./deck.sh feature update media-forge` 成功、installed0.28.86/PID1986947/healthy。
preinstall/preupdate/after DB論理hash・asset属性hash・runtime registry hashが一致。
新生成画像を含むSQLite/registry復旧snapshotも保持。
実MCPは28toolsでcreate/edit復帰、新曲面/weight/IK/translation操作、参照pack項目を確認。
実HTTP create42547B/edit42609B/job-request14429B。Host上限は変更していない。
証跡rootはmaintenance/release-0.28.86-20260918、installed-mcp.json/update.log/
download-verification.json/preinstall.json/after.json。

旧GLBを実Blender4.5.13へ再importし、ground名を除外した実vertexのworld boundsは
幅1.182475m/長さ3.155000m/高さ1.782249m、1474triangles。
3m±5%の長さgateはごく僅かに超過。bboxは接合/接地/変形の証明ではない。
証跡baseline-glb-inspection.json、scriptは前release証跡rootのinspect-comparison-glb.py。

## Reference packing retry through installed OpenCode

`MF3DS-Trex-ReferencePack-20260918` / `ses_f4d395788ffeQ0rXgutCTxR5EG`:
156.978秒、3tool calls、exit0。Job `job_ab3a487a678f40f8bee258a61e6d2864` succeeded。
ReferenceSet Asset `asset_8624a6f9f9fd46be8ae4f9cadd50ff11`、1,490,959B。
既存4画像だけを使い、生成追加0。exportsへcanonical/front/side/back PNGとreference-set.zip。
実fileとAssetのbyte一致、ZIP各image hash、全親来歴、needs_review/unverifiedを独立検証。
証跡reference-pack-opencode/、reference-pack-verified.json。

次の新規project `MF3DS-Trex-Curved-20260918` はこの参照セットをsceneへ固定し、
座標/断面/操作を実ローカルLLMに設計させる。親は自然言語briefと検証だけを担当する。
同じ512px/clay4view/center(0,0,1)/span4mで旧T-Rexとのpilot比較を行う。
これは歴史的baseline対1新規制作の比較であり、R2の同一brief3条件各3回の代用ではない。
参照画像自体の解剖学/投影欠点はbriefと分離し、VLMの不確実判定を無視しない。

## Bounded authoring requests and actual local stream failure

The first `MF3DS-Trex-Curved-20260918` attempt spent calls trying to read a spilled
capability result through invalid Asset/Job IDs and out-of-project input grants.
Those requests failed closed. Its scene-create call was aborted with empty input;
parent stopped only PID1988375, exit-15, 373.432s, 11 tool calls, no delivered file.

Added optional `--mcp-tool` to the diagnostic runner: exact canonical names only,
validated against actual discovery. Private build-agent permissions expose only the
chosen MCP tools; shell/read/write/task remain denied. Real `debug agent` verifies
both allowed and denied tools. Global OpenCode settings and Host code are unchanged.
The scoped attempt verified this boundary but hit native streaming error
`Invalid diff: now finding less tool calls` at2026-09-18T04:42:53.835Z while generating
scene.create arguments. It was not a Blender geometry error or a proven timeout.
Only PID1990921 was stopped; exit-15, 287.211s, 3 tool events, no delivery.
MediaForge active Jobs were zero after both stops. No other inference was canceled.

The third attempt `MF3DS-Trex-Steps-20260918` keeps the ten-tool scope and limits each
create/edit to at most three operations, compact JSON, and omitted defaults.
The initial two-operation body create succeeded, followed by a successful small edit.
Remaining anatomy, real review/refinement and output quality are still in progress.
The diagnostic code's full gate passed:2,177 tests/2 warnings/230.83s, exit0.

## Completed short-request pilot and quality comparison

The third run completed through the installed local OpenCode → MCP → Blender and
Host VLM path: session `ses_f4d29fed0ffeDkKDSJWj0CbJaQ`, 929.597s, 43 tool calls,
exit0. Private ten-tool permissions were verified; no shell/read/write was enabled.
The authoring brief requested at most three operations per call; this is a measured
prompt workaround, not a new public API limit or a proven cure for the native stream bug.
The LLM chose all coordinates. It created the body with loft/subdivision, added limbs
with small edits, then observed, reviewed, refined and delivered four files.
Primitive toes/fingers were also used, despite the brief reserving primitives for eyes/teeth.

New scene `scene_245a22d2554c45ef9986ec76ff9ffe5d`, authored revision
`revision_ad5998a80e0449d2bc6ea2f0d42e4fa7`. Observe Job
`job_8798b5ab77aa499296c151e70102fc52` produced front/side/back/three-quarter PNGs
at 512px, clay, center(0,0,1), span4m, matching the old scene's observation settings.
Copied PNGs were checked against their Asset hashes and provenance.
Review Job `job_02d9041cf3ea44968962eeeb6871a20b` succeeded in54.800s
(terminal timestamp difference including queue), report `asset_1f34fa2f6a30476da347a587e45ae6a3`.
It reported issues in head/jaw/teeth, torso silhouette and arms, reference consistency
uncertain, review_state=needs_review, no unsupported suggested operation names.
The VLM's claim that the reference requires an angular dorsal silhouette is advisory;
it did not adequately identify the axis mismatch and floating teeth visible in the render.

Refinement made another real review and stopped with `baseline_needs_review`,
zero attempts, shape_gate=advisory_only, asset_approval=not_granted.
Report `asset_83b85e1cff6145d79c3df34a7a56c768`; original/selected revision is unchanged.
Independent SQLite inspection confirmed the original scene head. This exercises
uncertainty-stop behavior, **not successful candidate improvement**.

All four committed delivery receipts were independently matched to the actual Asset
bytes, SHA256 and output file size. `curved-before.glb` and `curved-final.glb` are
byte-identical,129520B, SHA256
`f9d2dc1de3b437fcb266c6f94e406408f605088b783539e30ca1cad42dd533c6`.
`curved-review.zip` is7378B; `refinement-report.zip` is2515B. Terminal active Jobs=0.

Real Blender4.5.13 reimport, excluding meshes named ground/floor:

| Measurement | Historical primitive T-Rex | New reference + curves |
|---|---:|---:|
| Triangles | 1474 | 4524 |
| X extent (m) | 1.182475 | 3.217136 |
| Y extent (m) | 3.155000 | 1.416754 |
| Z extent (m) | 1.782249 | 2.351730 |
| Minimum vertex Z (m) | -0.002249 | -0.025000 |
| Requested 3m±5% length | FAIL (slightly above3.15) | FAIL |
| ≤5000 triangles | PASS | PASS |
| Visual quality | Boxy torso/hidden teeth/thin tail | FAIL: axis and attachment defects |

The new body/jaws extend along X while eyes/limbs use the requested -Y-forward
convention. The smooth body does not establish anatomical improvement: eyes sit in
the wrong region and teeth visibly float away from the jaws. Bounding boxes do not
prove mesh connectivity, contact or deformation. Reference images themselves have
finger/toe-count and projection defects, so the unverified ReferenceSet is not an
approved anatomical blueprint. No UV/rig/animation quality claim is made for this model.
This is one historical baseline versus one successful new authoring run, following
two failed authoring attempts; it is not the R2 controlled27-trial benchmark.

Installed viewer acceptance was attempted with the existing harness and no source
overlay. Chrome launch timed out after180000ms before the first page: viewer pixels,
controls and mobile acceptance remain **NOT TESTED**. No product failure is inferred
from this browser-launch failure. Evidence: curved-installed-viewer.log.

Evidence under maintenance/release-0.28.86-20260918:
curved-steps-opencode/{events.jsonl,observations.json,prompt.txt},
curved-independent/{observation.json,review.json,review-metadata.json,*.png},
curved-glb-inspection.{json,log}, curved-delivery-verified.json.
The comparison artifact at
`/data1tb/ControlDeck/CodeDEV/MF3DS-Trex-Steps-20260918/comparison/index.html`
has four switchable paired views, actual metrics, GLB/report links and comparison.json.
Its eight images are byte copies of the observation Assets. It makes no network requests.

### Next acceptance work, in dependency order

1. Correct and approve same-individual reference views: consistent projection, arms,
   two fingers and three principal toes. Keep needs_review until actually inspected.
2. Before detail generation, inspect a low-cost body/jaw/eye/limb landmark fixture in
   one explicit common coordinate frame. Use snapshots and orthographic renders to
   detect orientation/attachment errors, then add teeth. Do not infer attachment from
   object names or a successful tool response. This is a follow-up, not measured progress.
3. Re-run fixed-view shape acceptance; preserve original and compare candidates.
   VLM suggestions remain advisory and require geometric checks; do not bypass the
   current uncertainty stop merely to make a refinement report appear successful.
4. Only after shape acceptance evaluate surface, joint deformation, gait/contact and
   actual installed viewer. Re-run browser acceptance once Chrome can launch.
5. Execute the full R2 matrix (T-Rex/quadruped/prop ×3methods ×3trials), including
   failure counts and measured resource/runtime costs. It remains NOT TESTED.

Implementation/deployment/real-VLM pilot comparison are complete; high-quality asset
acceptance is not. Full code gate:2177passed/2warnings/230.83s, exit0; subsequent changes
are documentation and standalone evidence artifacts only.
