# 3D Studio compatibility baseline

Status: 3DS-0〜1 VERIFIED / 3DS-2以降は未実装
Date: 2026-09-05

この表は統合3D Studio着手時の互換性基準である。既存画像・G8・公開契約を、後続実装の
「動いたはず」ではなくfixtureと実測で比較する。固定fixtureは
`tests/fixtures/3ds-baseline-contract.json`、検査は `tests/test_3d_studio_baseline.py`。

## 対象状態

| 対象 | 実測した状態 |
|---|---|
| MediaForge source | `origin/main` `9469d8e4e4980752082f5081da7ba6e95d184622`（PR #213 merge） |
| installed MediaForge | `current -> versions/0.27.0`、systemd user unit `cdapp-feature-media-forge.service`、PID 1241393、127.0.0.1:9130 |
| installed health | `healthy`、contract 2.0、既存contribution 10件available |
| installed image | `image.text_to_image=available / local / measured / local_only`。最新保持Assetは704x1472 PNG、7,262 B |
| source Blender | 4.5.9 / Python 3.11.11、background・GLTF import/export probeすべてtrue |
| source runtime | `runtimes/blender-4.5.9`、1,546,263,669 B、legacy stamp/archive hash一致 |
| installed G8 capability | `asset.3d_project_pack=unavailable / runtime_not_installed`。bundleにBlenderを同梱しない既存境界どおり |
| GPU | AMD Radeon AI PRO R9700 / gfx1201 / VRAM 34,208,743,424 B。採取時使用27,134,840,832 B |
| ControlDeck | `07f1c207903c64ff05c8f4e6857b6e025b76a98d`。既存dirty `frontend/tsconfig.tsbuildinfo`は変更していない |

installed imageの行は新規生成を実行したという意味ではない。0.27.0のlive capability応答と、
同じlive storeに保持された2026-09-03の実PNG Assetを確認した。画像生成の新しいGPU job、実ブラウザ、
画面操作は本sliceでは **NOT TESTED**。

## G8実process回帰

一時data rootと実Uvicorn `127.0.0.1:9164`を起動し、コード生成したmaterial付きcube GLBを
HTTP importして `asset.pack + profile=3d.project.glb` を2回実行した。入力は796 B、SHA-256
`f61f0c984f3967aee9840bac635be4fb8533631ae5ab5caeb9bf37837b8d75a8`。

両jobはsucceededし、ZIPは44,292 B、SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`でbyte-identical。
2回目のHTTP受付から終端観測までは1,055 ms。ZIP entryは順に `asset.glb`、
`manifest.json`、`preview.png`、固定timestampは1980-01-01だった。終了後work entry 0、
実Blender child 0。これはsoftware renderingの既存G8経路であり、GPU Blenderの証拠ではない。

設計PR headでは `./mf.sh test` が848 passed / warning 1件 / 61.84秒。3DS-0 fixture追加後は
851 passed / warning 1件 / 62.14秒。focused 176件、Python compileall、frontend JavaScript構文、
shell構文、変更Markdownの相対link、`git diff --check`もPASSした。

## 未確定事項

| ID | 2026-09-05 baseline | 次の証拠 |
|---|---|---|
| CHECK-01 | Hostにbinary WS relayのコードはあるがnoVNC往復は未実測 | opaque iframe、nonce/subprotocol、長時間、取消 |
| CHECK-02 | systemd userで現行serviceは動くがGUI runner隔離は未実装 | filesystem/network/process脱出negative |
| CHECK-03 | GPU型番・VRAMは実測。GUI/Cyclesは未実測 | display/OpenGL/Cyclesを別々にprobe |
| CHECK-04 | current Host/OpenCode processは存在。3DS長時間jobは未実装 | 120秒超、refresh、restart、cancel |
| CHECK-05 | GLB 64 MiBとworkspace JSON上限は既存どおり | bounded .blend chunk/grant transport |
| CHECK-06 | frozen契約fixtureを追加し既存値を固定 | 新schemaごとにold fixture + Host parser |
| CHECK-07 | legacy runtimeをopaque IDで登録しresolver経由G8がbaselineと同一hash。registryはmode 0600でraw pathなし | 3DS-2 side-by-side更新、失敗rollback、参照保護 |
| CHECK-08 | 単一4.5.9だけ。新旧保存互換は未実測 | revision分離、実.blend比較 |

## 3DS-0判定

baseline fixture、互換性表、source/installed/Host/GPU状態、既存G8実process回帰を取得したため
3DS-0のexit gateを満たす。3DS-1からruntime resolverとread-only設定診断を実装する。
Web Blender、scene/revision、GLB viewer、材質、OpenCode制作、runtime lifecycleは
**NOT IMPLEMENTED / NOT TESTED** のままであり、3DS-0成功をそれらの証拠へ読み替えない。

## 3DS-1 runtime resolver / 設定診断

versioned registryとresolverをMediaForge側へ追加し、既存4.5.9 runtimeを
`legacy-blender-4.5.9`として登録した。registryは258 B / mode 0600で、保持するlocationは
`legacy`だけであり、`/data1tb`、`/home`、`/tmp`を含まない。symlink registry、managed root脱出、
壊れたstamp/executable/manifest/trusted workerはfail-closedにする。active runtimeが将来別版に
変わっても、既存G8は正確に4.5.9のready runtimeだけを選ぶ。

実Uvicorn `127.0.0.1:9164`でstatusは`ready`、active/G8は同じopaque ID、4検査はすべてtrue、
fingerprintは`c5015f19e7a0fb8228e426386d0e7aee19be7501852d814da1c08c0f163ebcd9`だった。
resolver経由でbaselineと同じ796 B cubeを加工し、job
`job_23d828f247fa420995b451d07b0a5246`は1.462秒でsucceeded。ZIPは44,292 B、SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`で3DS-0と同一、
entry 3件、終了後work entry 0 / Blender child 0だった。

standalone ChromeでSettingsのready/missing、診断展開、日英切替を確認した。320 pxでは
clientWidth/scrollWidthとも320、更新ボタン高さ39 px、最終console/page/HTTP errorは0件。
基本runtimeと未導入Web操作packは別表示され、missing時も画像機能を利用できる旨を表示した。
実ControlDeck workspaceは未認証ブラウザが`/login`へ遷移したため、installed opaque iframeでの
3DS-1操作は **NOT TESTED**。lifecycle操作、Web Blender、scene/revision、viewer、材質、
OpenCode制作、GPU Blenderも **NOT IMPLEMENTED / NOT TESTED**。
