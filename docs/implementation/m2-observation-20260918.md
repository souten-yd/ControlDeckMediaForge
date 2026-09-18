# M2a — revision固定の観察画像

Date: 2026-09-18。状態: source実装・実Blender受入 / signed installed・実OpenCodeはNOT TESTED。

## 実装

`media.scene.observe`を加法追加。scene_id/revision_idと明示したcenter/span_mを受け、
既存SceneRecipeJobManagerのdetached Job、owner、runtime pin、retry、取消、terminal outboxを再利用する。
画像は既存Asset/Provenanceへ登録する。scene headや旧revisionは変更しない。
新しいJob/Asset DBやHost固有経路は作っていない。

front（-Y）/side（+X）/back（+Y）/three-quarter、Z上の固定正投影。
material/clay/silhouette/object_id、256/512px、CPU Cycles 2 threads / 16 samples / frame0。
修正前後は同じObservationSpecとrenderer版を使う。scene任せの自動fitはしない。
上限256 mesh / 1024 objects / 保守的geometry cost100万、4画像×4MiB、report128KiB。
mesh/armature/empty/light/cameraと既存bevel/mirror/fixed array/armature modifierを対象にし、
curve/volume/instances/particles/未知modifierは部分成功にせず拒否する。

coreが画像型/寸法/size、source hash、workerの実行条件、view対応を独立検証する。
PNGの内部path/日付/timing metadataは公開前に除去し、画素だけを保存する。
画像symbolic link（許可root内の別画像へのlinkも含む）は拒否する。
全画像検証後に登録し、途中の登録失敗は回収する。取消時はworker終端を待ってstagingを回収。
再起動時のpublish_observation段階もservice_restartedへ終端する。

公開request schema、addon tool、health contribution、capability、API/agent guideを同期。
既存scene workflowのcreate/edit/materialは変更しない。
Libraryの検査名に「3D観察画像の出力」を追加した。
VLM判定やmedia.scene.review、ReferenceSet、曲面操作の実装ではない。

## 実測

managed Blender4.5.13と新sourceのSceneWorkspace/Storeを使用。
実M1の閉mesh sourceを専用scratchへimportし、4 mode×4 viewの16 PNGを既存Assetへ登録。
正規installed DBは入力sourceのread-only参照。scratchのJob/scene/assetは独立している。

| mode | 4方向のwall time（秒） |
|---|---:|
| material | 1.073 |
| clay | 0.856 |
| silhouette | 0.444 |
| object_id | 0.449 |

各PNG256×256、計220675B。hashと来歴のrevision/spec/source hash一致、metadataなしをassert。
同じrevisionを同条件で再観察した4画像のSHA256は一致。
typed editでarmorをX方向0.08m移動し、同条件のfront画像が変化したことを確認。
その後に旧revisionを観察すると元4画像のSHA256に戻り、scene headは編集後の版を保持した。
実比較は表示品質の合格ではなく、固定条件・旧版不変の検証である。

実CPU描画の最初のfront.pngが生成された時点で取消。
worker process生存中であることを確認してtask.cancel、終了後PID不在、staging空、
新規公開Asset0、runtime reference0をassertした。
VLM/画像生成/GLB変形/animation/engine、新toolのsigned installed MCP受入はNOT TESTED。

証跡はControlDeck project `MF3DS-M1-SixVertex-20260918/evidence/observation-source/`。
report.json / comparison.json / cancel.json / 16 PNG / run_domain.py / run_cancel.pyを保持。
実行はsource worktreeで`PYTHONPATH=backend:. .venv/bin/python <run_domain.py>`。
新scene/画像の実体と再現条件はreport内の実IDに対応し、架空のrender結果は含めない。

## 検証・次段階

focusedは契約/独立worker入力検査、owner/過去版、全画像検証、rollback、途中取消、
queued取消と同入力retry、再起動4段階、HTTP agent経路、未対応geometry/増幅拒否を含む。
最初の全体試験で新validatorの日本語label不足を検出して修正。
PNG metadata内の内部path、同root symlink、publication段階の再起動処理も修正して追加検証した。
最終全体gateの値はimplementation-statusの同日節を参照する。

次はこのsourceを通常の署名配布へ載せ、新toolの実installed projectionを照合して
OpenCode→observe→Job→image Assets→grant/receiptを受入する。
それまではM2aのinstalled gateをPASSにせず、M2b/M3の品質成功へ読み替えない。
