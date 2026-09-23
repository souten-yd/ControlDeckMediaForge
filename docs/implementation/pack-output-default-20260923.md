# asset.packの出力形式省略を修正

Status: source実HTTP/既存Blenderで受入。0.33.17の通常配布・installed MCPは未実施。
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

NOT TESTED: 0.33.17の署名配布・通常更新・実OpenCode/MCPによる形式省略要求。
多視点生成の採用/UIと汎用MCP失敗時Job IDの伝達は別の残件。
Pixal3D Vulkan版は導入済み。既存重みを使い、追加モデル取得をしない。
