# 単一参照画像編集の実測枠と入力寸法

## 実機で再現した失敗

通常Host media.generate: Host8a2765972b00 / MFjob_ea504bbddcdd4382825976fd190da193。
512角を要求、1024角の既存正面Assetを参照した。開始前のdevice270,532,608B/active lease0。
resource_oomはHIPのworker上限8.80GiBで2.25GiBの確保に失敗したもの。device空きは23.20GiB。
他の作業やLLMを終了して空きを作る問題ではなく、参照編集に通常生成用の枠が使われていた。
従来の参照adapterは元画像の寸法で推論してから指定サイズへ縮小していた。

## 変更

既存FLUX.2-klein/int8/CPU offloadにreference_edit測定欄を追加。重み/revision/量子化の既定を保持。
単一参照・非strict・追加profileなしの場合だけ、device観測ピーク17,675,771,904B＋既存余白を
Hostへ申告。PyTorch allocatorは実測12GiBか、実grantの小さい方を上限にする。
推論は全参照画像を指定canvasへ合わせてから行い、途中で大きい元寸法へ戻らない。
minimum_bytesも編集枠にそろえ、同じmodelでも小さい前Jobのleaseは引き継がない。
leaseを返す前に自身の待機workerを終了する。Hostの他の処理は終了しない。
通常生成・厳密な部分編集・outpaint・複数参照は従来の契約を保持。材質編集は既存の別測定値を使う。
workerはreference.fit_to_outputを来歴へ返し、元のAsset bytesを変更しない。

## 実測

証跡root: managed data maintenance/multiview-20260923。

- reference-budget-12gはGPU可視性assertで開始前に終了（追加モデル取得0）。
- reference-budget-12g-gpu0はPyTorch枠12GiB/Host枠14GiB。device差分がHost枠を超えたため、
  private supervisorが自身の子だけを停止、lease解放。PyTorch外の割当を除いて採用しない。
- reference-budget-12g-device22gはHost枠22GiBで同じ入力を評価。23.066648秒/exit0/released。
  device最大17,675,771,904B、PyTorch allocated8,588,162,048B/reserved11,018,436,608B。
  生成は18.087888秒。出力は前後に顔がある不正な側面で、視点画像としては不合格。
- reference-worker-candidateは実worker/既存重み、Host枠20,038,003,916B、allocator12GiB。
  512角15.579260秒、1024角12.855111秒、1024×768は196.525990秒で各指定寸法の画像を生成。
  参照fit来歴・元画像SHA不変を確認。全226.749668秒/exit0、45renew/released、
  device最大15,673,860,096B、process tree RSS最大13,205,983,232B。
  PyTorch peakは同一process内の累積最大であり、3枚目単独の峰と扱わない。
  長方形の初回が遅いため、推論時間申告には今回の最大196.525990秒/枚を保守的に使う。

512角候補は片側の顔になったが、元との材質/構図/厳密な90度一致は未受入。
1024角は前後の顔の重複が残る。いずれも複数面3Dへ投入していない。
全画像・stdout/stderr・Broker receipt・telemetryを保存。モデルDL/重みコピー0。

## 検証状態

対象84tests通過（2warnings）。最初の全testはcode reviewで小さいleaseの持ち回りを発見したため
自身のpytestへSIGINTで終了。新しい回帰を追加し、最終 ./mf.sh test は2517passed/3skipped/3warnings/352.92秒、exit0。
0.33.19を準備。製品codeは最終全test後に変更なし。installed Host経由の生成/Library登録、署名通常更新はNOT TESTED。
複数面runtime/UIの採用はこの修正の範囲外であり、別の評価を継続する。


## 0.33.19の通常公開・installed受入

PR651 / merge90788fcee2900d4214868aa7e1ec3107bcd174ebを固定しbundleを構築。
38,063,572B、SHA256 b7c460d4f6ddf6bcb9e8e6aac3c4a5cf3a4664ebfe504b5a5efce2f5b0424f56。
既存publisher keyで署名、Host trusted key照合/改変拒否、秘密値・重み混入なし、公開物を再取得して再検証。
全testの3skipはbuild venvへの参照不足による署名testで、既存環境を参照して当該3件を全て通過。
製品codeは最終全test後に変更なし。clean bundleは0.873154秒で起動、setup_required/
3D unavailableを確認し、実環境のhealthyとは混同しない。

実行中Jobs/GUI/runtime操作/Host lease0、両prefixのOpenCode unit0を確認し通常feature update。
current0.33.19/PID513777/healthy、更新前1585 Asset metadata/代表3content SHA/runtime全JSONを保持。
Hostコード、採用済み単視点Pixal/trellis runtime、モデル重みは変更しない。

通常Host media.generate Job50f9ce2160f3 / MFjob_76034e60aa5c4ebd84d3881b9d742a4d:
succeeded、Host timestamp差17.511011秒、再送0。
Library Asset asset_74dbc48f1ac24554b03c3e56f486fbe5、512×512 RGBA/260,317B、
SHA256 e5eac5767803252a5fb35351a9515e3cb3f717e5a8a24210a719ae76b7058eb6。
元Asset asset_3fdf91288b124c6eab6b3f946af73f13の親参照/画像SHAを保持し、provenanceに
image.edit、FLUX.2-klein-4B、0.33.19、reference.fit_to_outputを確認。
元Assetは公式正面とdecoded RGBA画素が全て一致（PNG保存形式のSHAは異なる）。
新候補の顔は片側になったが、厳密なcamera/構図/材質一致は未受入で、複数面3Dへ投入していない。

実Hostの通常LibraryからPC1280とtouch320pxでカードを開き、512角画像の読み込み、
opaque origin、横overflow0、page error0をassertしPNGも目視。物理スマホはNOT TESTED。
証跡: maintenance/release-0.33.19-20260923/{installed-check,library,source-image-integrity}.json。
生成の入力/Host終端/Asset/来歴/PNGはmultiview-20260923/generated-right-512-installed-0.33.19。

表示確認の後に専用operator sessionのローカル有効期限切れを検出。
installed lease終端の追加HTTP照会はNOT TESTEDとして記録し、認証を迂回しない。
期限切れの専用sessionだけを通常logoutで無効化し、利用者へ再ログインを依頼。
公開・更新・生成・保存・Library表示の受入は完了。追加MV評価は再認証後に継続する。

利用者の通常再ログイン後、2026-09-23T07:50:53Zに同じHost Job50f9ce2160f3のlease
057d8785-5975-439f-ad44-1696285ce14cを通常`GET /api/v1/resources`で照会し、
`released`を確認。その時点のactive/reservedは0。この追加終端照会のNOT TESTEDを解消した。
再生成/認証迂回なし。証跡release-0.33.19-20260923/resource-check-after-login.json。
