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
