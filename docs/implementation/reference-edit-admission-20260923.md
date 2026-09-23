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
