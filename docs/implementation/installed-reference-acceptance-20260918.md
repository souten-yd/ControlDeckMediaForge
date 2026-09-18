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
