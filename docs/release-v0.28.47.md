# v0.28.47 — ボーン・剛体スキン・ポーズ・アニメーションクリップ

既存の型付き3D制作へarmature.create / skin.bind / pose.set / animation.clipを
加法追加します。ロボット等の部品を骨格へ割り当て、ポーズや回転クリップを制作できます。
operation一覧はcapabilityのsupported_operationsと現在の公開schemaで確認してください。

## 対応範囲

- 骨格: ordered hierarchy、1 rig128/scene256 bones。零長・重複・不明parentを拒否。
- スキン: 独立した静的meshの全vertexを1 boneへweight1で割当て。既存weights等を上書きしません。
- ポーズ: typed/static rigのrest-local XYZ回転。静止GLBは現在poseをexport restとして保持します。
- クリップ: bone回転のLINEAR keys、共通fps、loop端点一致、既存clipの保持と新規追加。
  最大600 frames/120秒、32 clips/scene、key・bone-frame sample予算を適用します。

滑らかな分布weights、歩行/root motion、IK/FK、retarget、任意action編集、
ゲームエンジン取込みの完成を宣言する版ではありません。既存GUI骨格全般を自動変換しません。
clipの自然さや見た目の承認は別の品質検査です。

## 検証と配布状態

PR #365/#366で実装。隔離source/domainの実Blender4.5.9/4.5.13で
11 bones/25部品、rest形状不変、60度pose、idle2秒/arm_swing1秒の保存と再importを確認。
GLBのskin/weights、同時刻のmesh位置、既存clip/旧revisionの保持を検証しました。
CPU動画も生成し、開始・中間・終了付近のフレームを確認しています。
現時点はrelease準備で、署名公開・導入環境・実MCP受入は別途記録します。

## 互換性

DB migrationはありません。recipe@1へ新operationだけを追加し、旧操作の意味は維持します。
旧bundleでは新operationを含むrecipeを再実行できません。
生成済み.blend/GLBと旧revisionを保持します。Blender runtimeのpinは自動変更しません。
更新/rollback前にGUIを保存・終了し、稼働Jobがないことを確認してください。
既存untyped/animated sceneのGLB export設定は変更しません。

全体計画・未完了項目は[ゲーム制作計画](design-game-asset-authoring.md)と
[実装状況](implementation-status.md)を参照してください。
