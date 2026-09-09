# v0.28.46 — ゲーム小物向けの複製とミラー

型付き3D制作へobject.duplicateとmodifier.mirrorを追加します。
独立したメッシュ複製、位置・寸法の指定、ローカルまたは参照物体を基準とした
ミラーで、左右対称・反復配置のある小物を制作できます。
capabilityは現在のsupported_operationsを返し、既存7操作の契約は維持します。

複製の親/constraint/animation/shape-key、増幅時のmirror/bevel以外の未適用modifierは
今回未対応です。mirrorは1個/object、XYZ軸を選択、merge距離はlocal mesh座標です。
64操作と事前geometry増幅予算、実workerのtimeout/cancel、独立GLB検証を維持します。

## 検証と状態

PR #360で実装。隔離source/domainの実Blender4.5.9/4.5.13で小型ゲートを制作・編集。
mesh/材質slotの独立性、旧版保持、60 triangles/幅2.4m、
6,864 BのGLB一致とprovenanceを確認しています。
ゲーム制作の全機能やengine importの完了を宣言するリリースではありません。
詳細は[ゲーム制作計画](design-game-asset-authoring.md)。

この文書追加時点はリリース準備中です。署名公開・consumer検証・標準updateと
installed MCP/Blender Skills読込の受入は実施後にimplementation-statusへ記録します。

## 互換性

0.28.45からDB/schemaの保存形式を変えず、recipeのoperationを加法拡張します。
旧版は新operationを含むrecipeの再実行を拒否するため、同じ制作を続ける場合は
0.28.46以上と現在のcapability/schemaを確認してください。
生成済み.blend/GLB/過去revisionは維持します。Blenderのpinは自動移行しません。
更新・rollback前にはWeb Blenderを保存して終了し、稼働Jobがないことを確認してください。
