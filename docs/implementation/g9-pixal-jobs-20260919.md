# 2026-09-19 Pixal3Dの既存Scene Jobs接続

branch `ux1/pixal3d-scene-jobs`、親PR572 / `0e2b870be9d4e193ae689b1654710ac1af58c476`。
前ターンのprivate workerをcoreの既存Scene Jobsへ接続した。採用receipt・学習済み重み・
正規Host leaseは作成していない。sourceの接続実装、契約テスト、実CPUプロセス管理の受入を
分けて記録し、installedの画像生成やVulkan採用が完了したとはしない。

## 接続と採用境界

`pixal_runtime.py`に独立したprivate `media-forge.pixal3d-runtime@1` を追加。
読取先は `<data-dir>/runtime-state/pixal3d-runtime.json`。既存TRELLIS receiptは維持する。
runtime root/worker/venv/interpreter/native、descriptor、11役割のmodel/checkpoint identity、
license同意、実測device/VRAM/時間/output hashが必要。合成descriptorは採用経路で拒否する。
公開requestは既存 `engine=pixal3d` を使い、model名/path/任意scriptを追加しない。
public resolutionは実測1024のみ。native 1536を公開採用済みとはしない。

Python launcherはruntime内のvenvパスを保つ。binディレクトリのsymlink脱出は拒否し、
launcher本体だけが明示hash付き基底interpreterを参照できる。core venvとsystem site packagesを
拒否し、環境を最小化、`-E -s -B` とprivate pycache prefixで未記録の隣接bytecodeを使わない。
coreへTorch/worker moduleをimportしない。runtime inventoryは採用対象のworker/環境/共有依存を
列挙するoperator側の契約であり、この変更でinstalled venvを採用・変更した意味ではない。

`ThreeDGenerator`がreceiptを選択する。`auto`は存在するTRELLIS receiptを優先し、不正・未実測なら
失敗する。TRELLIS receiptがないときだけPixalを選ぶ。明示engineとcapabilityの`engines`を追加。
CPU前処理は `prepare_3d_input`、終了・hash検証後に既存child identityのGPU予約へ進む。
descriptor/入力画像/seed/前処理出力を束縛し、待機後にもadoptionと入力の検証を行う。
GPU processのdrain中はlease更新を続け、reap後にrelease、CPU Blender→既存Scene/Assetへ渡す。

取消中のspawn、hash thread、出力pipe上限、wrapperの異常終了を扱う。作成済み子を回収し、
同じprocess groupに生存processが残る間は戻らない。強制終了でもleaseを先に返さない。
既存のqueued取消・late grant回収・retry pin・lease lossの境界を維持する。
provenanceはdescriptor/prepared/input hashとCPU/F32前処理・Vulkan/F32生成を加法記録する。

## 契約テスト

```bash
.venv/bin/python -m pytest tests/test_pixal_runtime.py \
  tests/test_scene_generation_jobs.py tests/test_three_d_runtime.py \
  tests/test_scene_generation_import.py -q
```

最終対象51件、exit0。`targeted-final.log`に保存。
最終 `./mf.sh test`: **2242 passed / 2 warnings / 249.79秒 / exit0**。
warningは既存Starlette/httpxとPillow getdata非推奨。以後product/checker変更なし。
Pixal用の小さい隔離venvとprotocol専用script、既存fake Host/Blenderを使う。
fixtureの`checkpoint`/`vulkan` reportとreceipt値は契約入力であり、重みやGPU実測値ではない。
確認した主要境界:

- 前処理process終了後のGPU要求、2^24+1 seed、同じScene/Asset/provenanceへの接続。
- CPU前処理中の取消ではresource request/asset追加なし。native中・queued・late grantも回収。
- 不正grant、lease更新失敗、再試行のidentity、待機中にadoption変更したときの非activate/release。
- 取消されたworkerのcleanup待機中にもlease更新が続き、終了前にはreleaseしない。
- synthetic採用拒否、モデル/descriptor/worker/interpreterの変更、512拒否、autoの非fallback。
- manifest/生成backend/device/GLB/前処理arrayの不一致拒否、生成前改竄はworkerを起動しない。
- prepare/generate timeoutと繰返しcancel、128KiB出力上限を超えたpipe、started hash threadのdrain。

最初の単体テストはvenv fixtureがsymlinkでなくcopyを作る既定値だったため、symlink前提のassertが
失敗した。fixtureを`symlinks=True`へ修正して実運用のlauncher形態を検証。製品側の規則は緩和なし。

## 実CPUプロセス検証

`scripts/3ds_pixal_worker_process_e2e.py` は新しいcoreのprocess supervisorを呼ぶ。
`PixalWorkerLaunch`だけを使い、adoption/Host identity/leaseを捏造せず、既存PR572の合成重みと
native binaryを別の証跡rootへ複写・再hashしてCPU backendで起動した。全学習済み重みの取得/使用0。

実行済みコマンド（変数は絶対pathの省略表記）:

```bash
PIXAL_MANAGED=/data1tb/ControlDeck/data/feature-data/media-forge
PIXAL_EVIDENCE="$PIXAL_MANAGED/maintenance"
PIXAL_RUNTIME="$PIXAL_MANAGED/runtimes"
PYTHONPATH=.:backend .venv/bin/python scripts/3ds_pixal_worker_process_e2e.py \
  --allowed-root "$PIXAL_MANAGED" \
  --output-dir "$PIXAL_EVIDENCE/g9-pixal-jobs-20260919/cpu-final" \
  --fixtures "$PIXAL_EVIDENCE/g9-pixal-worker-20260919/cpu-first" \
  --worker-source runtimes/trellis-cpp-pixal \
  --worker-python "$PIXAL_RUNTIME/pixal3d-probe/.venv/bin/python" \
  --native-binary /tmp/mediaforge-pixal-worker-build/pixal-generate \
  --opaque-image "$PIXAL_EVIDENCE/g9-pixal-background-20260919/cpu-first/opaque.png" \
  --alpha-image "$PIXAL_EVIDENCE/g9-pixal-camera-20260919/cpu-verified/input.png" \
  --blender "$PIXAL_RUNTIME/blender/blender-4.5.9-linux-x64/install/blender"
```

最終run exit0、`cpu-final/report.json` / `cpu-final.log`。

| 対象 | 実測 |
|---|---|
| 不透明画像CPU prepare | 22.244655秒。前回のframing/low/high/camera 4出力と全byte一致 |
| native CPU generate | 1.324380秒、48,532byte GLB、590三角形、texture128²×2 |
| 前回GLB比較 | provenance以外の全JSONと全binary一致 |
| 構造 | core validator1.1.0 passed、`EXT_texture_webp`、skin/animation0 |
| Blender4.5.9 | 実再import0.254814秒、UV/画像/材質接続passed、armature0 |
| SS flow中の繰返し取消 | 実Python/native PID2486165/2486166を0.062088秒でreap、owned生成出力なし |
| core timeout0.7秒 | 実PID2486168/2486169、SS flowを観測、開始から0.762311秒でreap、owned生成出力なし |

両取消ケースでnative子のprocess groupがworker PIDと一致し、終了後に両PIDが`/proc`から消えた。
独立前処理用alpha prepareは5.203846秒。元fixture/native/runtimeには変更を加えていない。
最終GLB SHA-256は`a83fd02bf7a8a66a8b789e3de1fa2c76095428ce907c5bdde045c4f32a963d5a`。
core6ファイルとコピーしたworker sourceのhashをreportへ保存した。

初回起動は`PYTHONPATH=backend`だけでrepository直下`scripts`をimportできず、worker起動前に失敗。
`PYTHONPATH=.:backend`へ修正後の`cpu-second`は成功。per-process pycacheによるbytecode分離を
追加後、上記`cpu-final`を再実行した。初回失敗と前段成功のlogも保持している。

## 証跡と未完了

証跡rootはmanaged `maintenance/g9-pixal-jobs-20260919/`。対象テストlog、CPU checkerの各run、
full-test.log、最終source provenanceを保存する。実CPU checkerはScene Jobs全体やHost経路の
受入ではない。契約テストのfake値をGPU/adoptionの実測へ読み替えない。

NOT TESTED: 正規Host child identity/admission経由のPixal生成、trained/full幅/品質、Vulkan実機、
adoption receipt発行、署名導入、installed画像生成→Library、ブラウザ操作、骨付きanimation。
既存LibraryのTRELLIS2点と合成Pixal1点は保持し、今回は追加登録なし。
ライセンス同意・正規leaseは未取得。全体目標は未完了。
