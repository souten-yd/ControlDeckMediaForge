# v0.28.82 — 閉じたメッシュの明示検査

mesh.createへrequire_closedを加法追加します。trueを指定すると、境界辺、
3面以上で共有した辺、隣接面の向きの不整合をcore/Blender workerが独立に拒否します。
省略時はfalseで、開いた布や従来のrecipeは引き続き使えます。
自己交差、頂点fan、体積、外向き、見た目の品質を保証する機能ではありません。

制作ガイドとM1実行試験も更新します。新fieldを現在のschemaで確認し、閉じた装甲では
検査を有効にします。拒否された際にfalseへ変えて条件を回避しないよう案内します。
推論サーバーのtool-call streamエラーはこの版で修正していません。

sourceでは実Blender4.5.13で閉mesh作成、開布互換、前回LLMが生成した欠損meshの
allocation前拒否を確認しました。signed installed/OpenCode受入は配布後に別途記録します。
M1全体、高品質キャラクター、実画像/VLM/変形/engine受入は未完了です。

DB migrationはありません。既存の制作物とruntime登録を保持します。
旧版はこのfieldを契約として持たないため、rollback後に検査付きrecipeを送信しないでください。
