# 3D Studioの開発・管理・リリース規約

Status: 3D拡張に適用する開発規約  
Date: 2026-09-05

## 1. 継承する規則

この計画はMediaForgeの `AGENTS.md` と既存設計を置き換えない。
ControlDeckの非root・systemd user管理・認証・監査・grant・Brokerを守る。
SonicForgeからは独立runtime、durable setup、日英UI、実機受入、署名・negative testの作法を継承する。
SonicForge固有のtool名・音声schema・起動script・リリース版数はコピーしない。

| 項目 | 適用 |
|---|---|
| 作業単位 | 1 PR = 1つの利用者価値と検証可能なslice |
| branch | 既存MediaForge規則に合わせ `ux1/3d-<slug>` |
| 再開 | handoff、最新main/PR、implementation-status、対象設計を照合 |
| 実装 | schema → fake/contract → durable orchestration → real worker → UI → 実機受入 |
| 設計変更 | base-plan / integration / UXの正を先に更新。却下した案の記録を消さない |
| commit | 実装変更では `./mf.sh test` と影響範囲の検証、handoff更新を済ませる |
| 記録 | 実行したコマンド・観測・環境・NOT TESTEDを明記 |
| push / PR | 関連文書を含めcommit/pushし、変更理由・利用者動作・証拠をPRに記載 |
| Host変更 | 必要理由・汎用性・互換性を記載したControlDeckの別PR |
| merge | 対象headの必要受入・required checksを満たす。保護規則の迂回はしない |

既存画像UI/frameworkを3D導入の都合で全面移行しない。Viewer/noVNC等の重い依存は遅延ロード。
frontendのbuild方式・lockfileは作業時の現行実装に合わせる。
文書だけのPRではリンク・設計整合性を検証し、アプリやGPUテストを実行したとは書かない。
既存CIが文書PRでも必須にしているcheckは省略しない。

## 2. 契約凍結とモジュール境界

- 既存 `addon.json` のID、tool、workflow、Asset必須fieldを維持。
- `api_version=2` と現在のAdd-on contract rangeを保持し、検証前に拡大しない。
- 新しいscene schemaは公開前にfixture化。追加field・operationの互換性を確認。
- 破壊的変更が必要なら追加で済まない理由、影響、移行、version bumpを先に記載。
- coreは軽量。Blender Python API、画像ML、画面配信はpack/runner境界に置く。
- 同一MediaForge内のdomain service連携は許容。ControlDeck/SonicForge内部importは禁止。
- user inputのshell連結、`shell=True`、秘密値ログ、path traversalを禁止。

提案する責務分割は `scene document/revisions`、`runtime resolver/setup`、`GUI sessions`、
`typed Blender operations`、`viewer UI`。正確なファイル名は既存構造を調査して決める。
設計の都合だけで第二のJob engine、asset store、監査DBを作らない。

## 3. リリースはMediaForgeに統合

3D Studioを含む軽量core/UI/worker codeは、既存MediaForge GitHub Release bundleで配布する。
Blender binary、OS driver、巨大runtimeは軽量bundleへ混入させず、別の明示setupで管理する。
3D Studio専用feature ID、publisher key、バージョン番号、GitHub Releaseは作らない。

既存ファイルを正とする:

- `scripts/build_release_bundle.py`
- `scripts/sign_release.py`
- `tests/test_release_bundle.py`
- `tests/test_release_signing.py`
- ControlDeck `backend/app/features/release_bundle.py` とtrusted catalog

配布asset名は既存 `control-deck-media-forge-<version>-<platform>-<arch>.tar.gz`。
同名末尾の `.manifest.json` と `.manifest.json.sig` を公開する。
署名manifestは `schema_version`、`feature_id=media-forge`、version、platform、architecture、
artifact_name、sha256、size_bytesを束縛する既存canonical JSON / Ed25519方式。
canonical encodingは既存signerの `sort_keys=True, separators=(",", ":"), ensure_ascii=True` と一致させる。

現在のHostには `publisher_keys` による署名検証が実装済み。毎リリースのSHAをHostコードへ
貼り替える方式へ戻さない。新しいHost capabilityが必要なら既存catalog allowlistとの適合を別途確認。
署名が有効でも過剰capability、identity違い、downgrade、unsafe extractionを許さない。

## 4. release gate

1. MediaForge版、addon版、feature manifest版、tag、signed manifest版を一致させる。
2. ローカル検証、既存画像・G8回帰、該当3D受入を完了。
3. 軽量bundle生成、秘密値・venv・model・制作物・Blender binaryの混入を検査。
4. 正規release eventだけでpublisher秘密鍵へアクセスし署名・自己検証。
5. artifact/manifest/signatureを公開し、consumer経路で再取得して検証。
6. clean install、既存環境update、rollback、Blenderなし/ありのhealthを確認。

通常PR/テストには一時鍵を使う。実秘密鍵をrepo・test・log・bundleへ渡さない。
今回の文書PRでは鍵生成、版数更新、tag、リリース公開、OS環境変更を行わない。

Host既存lifecycleは署名・integrity・safe extraction → provision → doctor →
version配置とcurrent切替 → service起動とhealth → Add-on登録、失敗時rollbackである。
health前にcurrentが一時的に切り替わる実装なので「healthまでcurrentは一切変わらない」と記述しない。
Blender runtime更新のactive切替は別orchestratorがprobe後に実施し、稼働session pinを保持する。

## 5. migration / rollback

DB migrationは追加的に行い、既存Asset/Jobs/画像設定を壊さない。
runtime registryやscene table導入前にbackupを作り、失敗時の復旧と古いfixtureを検証する。
旧版MediaForgeへ戻す場合のschema互換性をrelease noteへ記載する。
非互換migrationならservice rollbackだけで済むと扱わず、書込停止・DB snapshot restore手順を準備。
新しいBlenderで保存した.blendは旧Blenderへ自動変換しない。旧revisionを再開する。
アドオン削除、Blender削除、cache削除、制作データ削除を別操作にする。

## 6. third-party管理

Blender、noVNC、VNC server、display、viewer依存ごとにversion/source/digest/license/noticeを記録。
Blender互換scriptの配置・ライセンスは既存 `worker_packs/blender/LICENSE.md` に合わせる。
再配布条件の判断は実際に同梱する版と配布方式に対して行い、生成assetの権利と区別する。
画像モデル・入力画像・textureの由来もprovenanceに保持する。
第三者runtimeのtrustはMediaForge署名と別物。署名済みcatalogの範囲内でも実体hashを検証する。

## 7. quality gateと証拠

| 領域 | 必須証拠 |
|---|---|
| 既存回帰 | 画像生成/編集・Library・既存G8 ZIP・media.pack・OpenCode |
| setup | clean/idempotent、切断再開、容量不足、hash不一致、cancel、修復、削除保護 |
| viewer | 実GLB、texture/animation、model切替のmemory解放、mobile、context loss |
| GUI | 実Blender操作、日英入力、保存、再接続、idle終了、crash recovery、権限取消 |
| resources | CPU経路、GPU lease取得/renew/終了、画像/LLMとの競合、待機cancel |
| assets | 新revision・旧版維持、依存画像、独立検証、grant/receipt、GC保護 |
| security | owner分離、隔離からの脱出negative test、token秘匿、path/URI/archive上限 |
| release | 署名/asset改ざん・wrong identity/key/size・downgrade・capability拒否、rollback |

性能はscene fixture ID、GPU/driver/Blender/display版、LAN、解像度、cold/warmを添えて記録。
ローカル実行を先に行い、重いGPU/GUI CIは明示hardware runnerで節目にまとめる。
CIにGPUがないことを実機検証の代替にしない。任意の追加testingで無関係な作業を広げない。
