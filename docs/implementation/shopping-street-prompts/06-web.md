この工程は商店街のHTML実装です。BRIEF.mdとassets/manifest.jsonを読んで、index.html、
styles.css、app.jsをこのprojectに作ってください。静的HTTPだけで起動できるES Modulesです。
import {THREE, GLTFLoader, cloneSkeleton} from './vendor/three.js'を使い、CDNやnpm取得は不要。
画像→3DとrigはMCPで作ったexportsの実GLBだけを利用。欠けた店舗/人物を箱やカプセルの
見た目で代用して完成扱いにしない。未配置なら分かる読み込みエラーを出す。

外観は「ひだまり商店街」、温かい昼下がり、クリーム色と青緑の控えめなUI。
生成された最低4種類の店を8軒以上、通りの両側へ配置。歩道と道は普通のgeometryでよい。
操作キャラ1人とNPC最低6人、NPCには最低2つの生成人物モデルを用いる。
SkeletonUtilsのcloneSkeletonで骨格を独立cloneし、実walk clipをAnimationMixerで再生。
移動停止で歩行が止まり、動作時に身体が変形する。rootの平行移動だけでは不十分。

三人称カメラが主人公の後ろから追従。左の仮想スティックで移動、右側ドラッグで視点。
PCはWASD/矢印、マウスドラッグ。二本指で同時に移動と視点変更できるようpointer IDを
別管理し、pointercancel/blur/visibilitychangeで入力を必ず解放する。44px以上の操作領域。
320px縦/横でも横スクロールなし。スクロールや選択の誤動作を抑えるが説明文は読める。
建物と歩道境界に衝突、NPCは通りを自律歩行して折り返す。カメラの壁抜けを防ぐ。
歩行速度/向き/カメラはdelta time基準。tab復帰の巨大deltaで壁を抜けない。

読み込み進行、失敗と再試行、操作説明を自然な日本語で提供。完成画面にMCP/Job/Asset ID/
内部パス/検証用ラベルを並べない。診断はURLの?debug=1かwindow.__streetAuditへ分離。
生成モデルに埋め込まれた色/テクスチャを保持し、過剰な暗転や色の上書きをしない。

自動受入のため、window.__streetAudit.snapshot()にready/error、player位置、camera位置、
NPC位置、読み込んだモデルURL、skins/bones/animation名、frame数と描画statsを返す。
window.__streetAudit.reset()で開始位置と視点へ戻せるようにする。
WebGL/context lossや未処理promise拒否を握り潰さず画面案内と診断に出す。
作ったコードと残っている不足をevidence/web-implementation.mdへ記録する。
