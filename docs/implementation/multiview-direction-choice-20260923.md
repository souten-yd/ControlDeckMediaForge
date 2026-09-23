# 複数面の追加方向を選ぶ（2026-09-23）

## 変更

利用者が正面＋左側面/背面などの組合せを要求。枚数によって右→背面→左を必須にしていた
UIとbackendの制限を解除した。正面を基準に右/背面/左の任意の部分集合（計7通り）を受理。
方向の重複、同一Asset/画素の重複、共通canvas、元画像pin/来歴、1枚経路は維持する。
既存のdirection enum/schemaを変更せず受理範囲を広げる加法変更。cameraは方向名で
0/90/180/270度に対応し、追加順や入力枚数で置き換えない。

「追加する方向」の選択欄と「この方向を追加」で、未追加の方向だけを選ぶ。
AI候補の採用時も選んだ方向のみ追加し、先行する方向の空欄を作らない。
簡易/詳細・端末の画像取込・方向単位の削除・1枚への復帰は保持。
斜め方向/個別の自由角度/任意写真の自動校正/AI方向生成品質の改善は本sliceに含まない。

## ソース実測

branch ux1/multiview-direction-choice、base cc45959、版0.33.24。
証跡rootはmanaged maintenance/view-directions-20260923。

- scene multiview/generation API/view candidatesの対象49件pass。7組合せの全親画像/依存/
  実worker境界、任意追加順の正規化、左/背面のcamera中心、旧拒否条件と取消を確認。
- 実Chrome opaque iframe、1280/320px、source-ui-v3.jsonの20check成功。
  全7組合せ/不要方向を作らない候補採用/表示画像と選択ID一致/4面/方向単位の削除/
  再追加/端末取込/1枚復帰/取消/詳細camera/英語、overflow0/errors0/44px。
  通信は制御fixtureでありinstalled成功ではない。初回helperは旧自動追加順の前提で
  timeout、修正後の結果と分離。画像は読み込み完了を待って画面と選択IDを再確認した。
- 正面＋左側面: 実Pixal3D Vulkan/Q8_0 flows+F16共有重み、132.273743秒、
  device全体観測最大5,841,215,488 B、26renew、lease released。
  正面＋背面: 136.900591秒、最大5,657,628,672 B、27renew、released。
  既存の人物＋片手の赤いバッグの整合したRGBAを使用。新規モデル取得0。
- 入力方向/Asset/実SHA/画素SHAとstaging、生成物の2親/dependency/mixed precision来歴を
  実source adapterとBlender4.5.13 importで検査。generated.glbを再生成せず検査する。
  左は989,446tris/763,635vertices、4096角の画像2枚。背面入力の出力は992,350tris。両GLBのCPU4方向描画で人物1人・脚2本・
  片側バッグ・画像材質を確認。rig/任意写真の品質受入とは分離する。

初回source helperは再起動後の旧card0計測pathで生成開始前に失敗、lease released。
実GPUはPCI0000:03:00.0/card1と再照合し補正。次の左生成自体は成功したが、helperが
workspace.initializeを呼んでいなかったため取り込みdirectory不足。recipeだけの作成でも
validationが不足することを記録し、通常initialize後、同じGLBを再生成せず取り込み成功。
result.jsonの失敗を残しimport-recovery.jsonと分けた。背面はimportまで成功。

最初のfullは2591passed/1failed/2warnings/318.68秒。既存の40ms idle timeout試験
`test_connected_activity_delays_idle_timeout_then_session_is_retained`がreadyではなくinterrupted。
同試験単独は変更なしでpass。実生成/CPU描画終了後に同一codeで再実行した
最終 `./mf.sh test` は2592passed/2warnings/304.89秒、exit0。以後code変更なし。
最初の予備gateは公開schemaの方向説明を補足するため
所有pytestだけSIGINT/exit2で終了し、full-tests.logに保持。成功扱いしない。
full-tests-final.logに失敗を保持し、再確認はfull-tests-quiet.logへ記録する。
稼働0.33.23はHostのrequested_enabled=trueに対して再起動後serviceが停止していたため
既存user unitだけstartしてhealthyを確認。Host再起動/設定変更/モデル取得0。
0.33.24の署名公開・installed操作/生成、物理スマホはこの時点でNOT TESTED。

## 0.33.24の署名公開と通常更新

PR662、merge b0e218526b54b6432cb56d3e8240996ce5c803a5。受入済みsourceと
mainのtree一致を確認し、既存鍵で署名。公開4assetを再取得してtrusted catalogの公開鍵で
署名/改ざん拒否/manifest/版/サイズ/SHA/同梱source一致を検証した。
証跡はmanaged maintenance/release-0.33.24-20260923。

- 正式bundleは38,054,353 B、SHA256
  `b2a3dfd641ba2f339218f44964e67611d2fa4a258e1fcaf7fa0fe95277ccc904`。
  tar6entry/embedded244entry。重み/DB/venv/秘密鍵の混入なし。
- 既存build venvにpillow-heifが不足した最初の32,019,409 Bのbundleは公開せず棄却。
  `mf.sh env build bundle-build`はruntime metadataなしで終了したため、既存のbuild venvへ
  coreと同じpillow-heif1.7.0を既存cacheから導入して再build。モデル取得0。
  private検証にPython/native decoder/libheifの同梱必須検査を追加した。
- 修正後の実bundleを新規data/cacheで起動。0.911408秒のclean smokeでsetup_required、
  Blenderなしの3D unavailable、候補のJob前拒否、pack既定ZIP/不正output拒否を確認。
  実HEICをHTTPで取り込み201、PNG320×240の保存と再取得を確認。
  最初のhelperは追加HEIC取り込みの来歴Jobを数えず件数assertに失敗。
  ログを保持し、import1＋pack1へ訂正して同じbundleで全check成功。
- active Job/Blender/model操作/scene task/leaseがないことを確認し、SQLiteをprivate backup。
  通常 `deck.sh feature update media-forge` によりcurrent0.33.24/PID29370/healthy。
  更新直前の1599 Asset metadata、代表3実content SHA、runtime全JSONを保持。
  配信app.js/styles.css/viewerとschemaはsourceに一致、3D capabilityは更新前と同じ。
  Host PID2418/NRestarts0。Hostコード・設定・runtimeの変更なし。

## 通常installed画面での選択・実生成

通常operator loginからHostのopaque iframe（origin null/allow-same-originなし）へ入り、
実Chrome320/1280×844pxで、全7組合せの方向選択/異なる画像選択/準備完了/
方向単位の削除/1枚復帰を確認（14check、overflow0）。日本語の左側面/背面を表示。
最初のhelperは必須の素材名を入力せずsubmit enabledを期待して失敗し、Jobは作成していない。
`name-missing-*`へ失敗を保持し、素材名を先に入力する修正後、以下の1件だけ送信した。

- 320pxの「3Dを生成」で `job_a9a6fa664f8f44d3a034888b12e4cf80` を作成。
  UI送信から成功まで130.635秒、native Vulkan生成123.798415秒。
  正面 `asset_62eafeae60dc4662883843d73304494c` と
  左側面 `asset_6933732b7af340aaa5307f63d9dbadec` の実content/画素SHAは相異。
  Q8_0 flows/F16共有重み、方向名front/left、2親/依存と来歴をHTTP再取得で照合した。
- Libraryに「複数面：正面＋左側面（方向選択の確認）」を保存。
  scene `scene_e8044033ff8242298472ab115630a186`、
  GLB `asset_a7763a4cad074d08a1b9e2493f293725`、.blendとGLBの実SHAを検証。
  989,446tris/材質1/埋込み画像2/アニメ0。元画像を同じ画像で代用していない。
- 同じ実GLBを320/1280pxで開き、画像材質・人物1人・2脚・片側の赤いバッグを目視。
  viewer表示/閉じるを含め計16check、page error0。
  服表面の細かな斑点が見えるため、任意入力の材質品質保証やrig受入とはしない。
- Host Job `e6cea94b42f2` とMediaForgeともsucceeded、lease1 released/active0。
  最後のactive Job0、Asset1601、既存1599 metadata/代表3SHA/runtime全JSON保持。
  current0.33.24/PID29370/healthy、Host PID2418/NRestarts0を再確認。

物理スマホ、斜め/自由角度、AI別方向候補の品質改善はNOT TESTED/本slice対象外。
AI候補の選んだ方向だけの採用はsource fixtureで確認し、今回installedでは手動画像を使用した。
文書のみの追記で製品codeは全2592passのgateから不変。新規モデル取得0。

## 完了後の検証実体の回収

受入終了後、今回所有の隔離source-left-v2/source-back-v2のDB/生成GLB/PLY/中間画像等
556,050,635 Bを回収した。result/import-recovery/render JSON、失敗log、CPU4方向PNGは保持。
棄却bundle/再取得duplicate70,073,762 B、受入後の重複bundleと今回のprivate DB backup
53,123,537 Bも削除。cleanup JSONに対象/サイズ/単独ファイルのSHA/理由を記録した。
公開された署名release、current/managed rollback版、正式Library、元の入力fixture、runtimeは
変更していない。回収したraw GLB/DBは保存済みと扱わない。
