# asset.packの出力形式省略を修正

Status: source実HTTP/既存Blender受入、0.33.17の通常配布・ローカル更新と実OpenCode/MCP受入済み。
Branch: `ux1/pack-output-default`。商店街の実OpenCode/MCPで観測した失敗への修正。

## 問題と変更

既存店舗を`asset.pack`でまとめる要求が`output.format`を省略すると、画像用のPNG既定値が
入り、Job作成後に`unsupported_pack_profile`で失敗した。同じ形式省略を繰り返す要因となった。
`docs/base-plan.md`へ先に既定値解決と互換性を記載し、次を実装した。

- `asset.pack`で`output`または`format`を省略した場合はZIPを選ぶ。
- 明示PNG等またはcountが1以外なら、必要な値を示し、Job作成前に422で拒否する。
- 画像の既定PNG、既存の正常なZIP要求、元Asset/来歴は保持する。
- 呼出元が共有するOutputOptionsを変更しない。過去の保存要求は旧値のまま読める。

公開schemaへ条件と案内を追加。以前から実行成功できなかった形式・個数を入口で拒否する修正で、
成功していたpack形式を削除しない。Host/モデル/runtime、UIに変更はない。

## 実HTTPとBlenderによる確認

証跡はmanaged dataの`maintenance/shopping-street-20260923/pack-default-source`。
`PYTHONPATH=backend:. .venv/bin/python <maintenance>/pack-default-source.py`で
独立Uvicornを起動し、商店街の既存cafe GLBを入力。既存G8固定Blender4.5.9を使った。
新規画像/3D推論、モデル取得は0。稼働DB/runtime registryに変更を加えていない。

| 要求 | 観測 |
| --- | --- |
| output省略 | succeeded、ZIP/count1、3.660855秒 |
| ZIP/count1明示 | succeeded、1.017983秒 |
| PNG明示、count2 | 各422、追加Job0 |

両ZIPは1,380,849BでSHA256が一致:
`4304aa085fc01f374cb8ae05d8196697107eb3532d77b8ebd83041a79759b3ea`。
実ファイルのhash、asset.glb/manifest.json/preview.pngの3項目、GLB検証とPNG読み込み、
親Asset、元GLB不変を独立確認した。試験用HTTPプロセスは終了済み。

初回は試験子プロセスのPYTHONPATH不足で起動失敗。次にStudio用4.5.13だけを登録したため
G8固定4.5.9が見つからずJob失敗。試験設定を既存4.5.9へ修正し、上記を実測した。
これらの失敗証跡も保持し、runtimeを追加取得したり固定条件を緩めたりしていない。

## 回帰確認と残件

省略4形態の決定的ZIP/来歴、共有options、明示不正要求とJob未作成、過去要求の読み取りを検査。
最初の全体testは1 failed/2508 passed/3warnings/444.54秒。
旧`test_unavailable_operation_fails_explicitly`がpackにもPNGを指定していたため、
ZIPを指定するfixtureに修正し、unsupported profileの失敗確認という意図は維持した。
最終`PYTEST_ADDOPTS=--basetemp=/tmp/mfs17-final ./mf.sh test`は
2509 passed/3warnings/426.99秒、exit0。以後product code変更なし。
ログは`pack-default-full-test-final.log`。

このpack修正のsource/配布/installed/MCP受入は下記まで完了。
多視点生成の採用/UIと汎用MCP失敗時Job IDの伝達は別の残件。
Pixal3D Vulkan版は導入済み。既存重みを使い、追加モデル取得をしない。

## 0.33.17の通常配布・ローカル更新

PR645、merge `77464d97d2282de00d1ed8cb9ca6239c8b9675b8`を固定してbuild。
実test対象edcaa27とmerge treeの差分0を確認した。
既存publisher鍵で署名し、Host trusted keyによる検証とmanifest改ざん拒否を確認。
bundleは38,063,858B、SHA256
`5d7eed276ed4c5d06c3c7c249f0833277d4b4b817c1ba7365ee4c204a02d090f`。
tar6項目/embedded244項目を検査し、sourceとschema/worker/frontendが一致、
重み・venv・制作物・秘密値を含めていない。公開4assetの再取得でも署名/hash検証成功。

新しい隔離data/cacheへ展開した実bundle HTTPで、health/setup_required、既存3D unavailable、
pack省略時ZIP、明示PNG/count2の422と追加Job0を0.872629秒で確認した。
この隔離試験は存在しない入力IDで既定値解決を検査するもので、pack生成成功の証拠には使わない。
生成成功は前節の実Blender記録を使う。

更新直前に一般Job、scene task、WebBlender、Blender runtime操作、モデル操作が全て0件と確認。
SQLite backupを取り、通常`./deck.sh feature update media-forge`を実行。
current=0.33.17、PID281578のexe/cwdと配布版が一致、health=healthy。
既存1584 Asset metadata、代表3 Asset実content SHA、3D生成capability、
data/runtime-stateの全JSON hashを保持した。稼働frontend配信内容も固定sourceと一致。
追加のservice restartは不要だった。追加モデル取得0。

証跡: managed data `maintenance/release-0.33.17-20260923`のbuild/sign/verification、
clean-smoke、before/runtime-before、pre-update.sqlite3、update.log、installed-check.json。
[公開版](https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.33.17)。

実OpenCode/Qwen3.8-27Bから既存cafe GLBのpackだけを1回要求。
Host Job `c2118762e2c4`、session `ses_f33587ddbffeAW8B6vNj0HHIvQ`。
元の商店街コード/画像/3Dに変更せず、output全体を省略したMCP tool引数と実ZIPを照合する。
Host Jobはsucceeded。実toolはmedia.generate 1回とmedia.inspect 1回のみ。
実際のtool入力にoutputがないことをOpenCode DBで確認し、MediaForge保存要求はZIP/count1。
MF Job `job_0b8b79c3e24c452fb488da3d41dbf233` succeeded、
ZIP Asset `asset_0324c8fdf8d04bba9371cba8500d7b98`、3,949,008B、SHA256
`be603b4d9509a3c7c01e55a1f2fba10c657cd9d92013de8904c61d9e55c5c59a`。
元GLB Assetは`asset_47380d9455c64d268ddf5f89033f6f3b`。
実content/hash、ZIP3項目、GLB/PNG検証、元Asset metadata/content不変を独立照合した。
Job作成05:06:41.792791Z→終端05:06:43.683960Z、差1.891169秒。
商店街projectのgit作業treeはcleanのまま。画像/3D生成・モデル取得・再送は0。
証跡は`pack-output-0.33.17.json`、`pack-output-independent.py/.json`。
