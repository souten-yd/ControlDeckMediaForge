# 直立人物の自動rig: 実生成からの修正

Status: 0.33.11 merged/released/installed。主人公512版の歩行修正を通常Host UIで再登録・実測。1024候補は別のbind失敗。

OpenCode / Qwen3.8-27B / MCP pipelineで実画像から作成した主人公を検査。
scene_889d23ec8c874d91bfa6347b3d4076a5の版2は88687 triangles、6 bones、
walk1秒、skin1。実Three.jsで時刻0/.25/.5/.75/1を評価し、最大頂点変位
.421049/.000000282/.232567/0m（身長1.8mへの表示正規化後）。ループは一致するが、
腕が脚に引かれ、上半身の形が変わる。Job成功/skin存在を品質合格にしない。

原因: measureは低部の2つの脚を見つけた後、全高60%以下の半平面を脚として集める。
人物の手・腕も混ざり、頂点密度の順位から取った膝が全高約46%に上がる。
rootは足底から頭頂まで貫き、上部の頭/髪をextraと扱い、腕用骨がない。
歩行も放射状多脚用の局所Z回転を含み、人物の前後歩行とは一致しない。

修正設計:

- 脚2本、左右に分離した手/腕と中央の胴を複数の水平断面で確認できる場合だけ直立人物を選ぶ。
- 胴の幅で腕と脚の測定点を分離する。膝/股/足首は高さごとの断面中心から測り、頂点密度に依存しない。
- 骨盤から胴を支えるroot、headと左右の上腕/前腕/手を支える骨を作り、既存armature.create/bind_autoを使う。
- 人物の歩行は前後の脚振りと逆位相の腕振り。多脚用の既存推定/歩行は保持する。
- 検出できない姿勢を人物として断定しない。成功した検出も変形の実測を要する。
- 公開operation追加、任意Python経路、別asset/Job基盤は作らない。

実測（source候補。installed修正の受入とは分離）:

- managed Blender4.5.13のtrusted scene_recipe.pyで同じ未rig版を編集、scene_document.pyでGLB出力。
  元Assetを直接編集せず専用fixtureへコピー。ratio=.6は88687 triangles、ratio=.15は22122。
  両方12 bones/1 skin/1秒loop。軽量版のworker1.817872秒、export.364070秒。
- 実Blenderの全25frameを身長1.8m換算で計測。旧版の足首X間隔は最小−.225459m、
  足表面のX間隔−.383876mで、利用者が指摘した脚の交差を再現。
  修正版.6は足首最小.258441m/足表面.105670m、.15は.243628m/.098814m。
  膝間隔も正で、両候補に交差なし。終端と始端の頂点は一致。
- 手領域の脚bone weight平均は旧.989627から両候補0。
  軽量版9104verticesの全vertexに有限・正規化済み最大4影響、unweighted0。
  画像2枚のpacked SHAは旧版と両候補で一致（1024²）。
- Chrome/Three.jsで4方向と歩行3時刻を描画し、page error0。
  再測定した軽量版最大サンプル変位.268673/.243383m（.25/.75秒）、1秒で0。
- 軽量化で平坦な胴の頂点が減るため、42〜58%の複数高さで断面を検査。
  胴より外側に出た靴を手と誤認しないよう腕の高さ範囲を分離。
  合成人物/密な手/疎な腰/幅広靴/スケール移動/2・4・6脚/歩行の回帰17件通過。
- 残る品質制限: 足底は周期中最大.018875m下がる。頭の局所変位最大.024980m。
  地面接地と自然な歩行全体の受入はWeb移動との組合せで別途確認する。
  肌/服の色は引き続き不一致。これらを「自然な人物完成」と扱わない。
- 最初の全testは長いbasetempがUnix socket上限へ達し20 failed/2417 passed/165.53秒。
  test用basetempを短くして全gateを再実行: `PYTEST_ADDOPTS=--basetemp=/tmp/mfr-test-20260923 ./mf.sh test`
  2437 passed, 3 warnings in 294.66s (0:04:54)。製品のsocket上限検査は変更しない。

NOT TESTED: 修正版のsigned installed/MCP、物理モバイル端末。
別件の肌/上着の色ずれは生成済みテクスチャ自体にあり、このrig修正では解決しない。


## 署名releaseとinstalled再受入

PR632 / merge e2bbbe931762f3a5dd6b062b43c90f4d7f9544f9を固定して0.33.11を構築・署名・公開。
公開物を再取得し署名/改ざん拒否/embedded rig_auto.py・rig_humanoid.pyのsource一致を確認。
38,054,468 B、SHA256 4ca217d344af8dd192adb442e7ff31f78e98adb36498af505fb313a95f4cde4a。
新規dataでpackage起動.865497秒、Blender未導入をunavailableと表示。

active MF Job/Blender session0でDB backup、通常deck.sh feature updateとservice restart。
current0.33.11/PID52808/healthy.825814秒、更新前1559 Asset metadata保持、代表3 HTTP SHAと配信source一致。
利用者の通常login cookieを非表示stdinで渡し、正規Host opaque iframeで自作主人公を操作。
元の版1を新しい版3へ復元してからratio15%でrigを1回実行、Job690ef644... succeeded。
scene_889d23ec8c874d91bfa6347b3d4076a5は第4版revision_496964560f624255ae5698c1c94275bdへ。
GLB asset_0480355b176141a4ae51f17f8eee66b7、Blender asset_621924b6c9304e14aa29cc377b92a297。
元版1/旧歩行版2は保持。320px表示22122tris/1material/1animation、overflow0/page errors0。
installed .blendを全25frameで再測定し、足表面X間隔最小+.098814m/手の脚重み0を確認。

browser自動操作の初回はdetailsの開閉/非表示、次はrange入力の未反映で送信前に停止。
復元済み版3を照合して再開し、編集tabを明示選択、range input eventと通常submitで成功。
同じrigの二重送信はない。物理touchでsliderを変更した受入とはしない。

同じ画像/seedをTRELLIS1024で生成した別sceneは、0.33.11の実OpenCode/MCP rigでfailed。
Host2506347a7351、pipeline_9dd4bab1fef94853bba40dcc8f0a30bd、Jobdcd564c6...。
原因はautomatic binding left vertices without weights。重み欠損のままrevisionを公開せず、
export未実行。512版修正の成功を任意生成メッシュのrig保証に拡張しない。
1024候補の欠損頂点/形状を別途調べる。商店街HTML・移動時接地・物理電話はNOT TESTED。
