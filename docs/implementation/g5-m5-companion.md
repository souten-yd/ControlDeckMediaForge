# G5 M5 companion 実装

## 目的

M5Companion の新しい shared-canvas 制作仕様を Media Forge の既存
`image.generate` / `image.edit` / `asset.pack` 上で実行可能にする。M5 専用の生成・編集
route、worker、model 選択は作らない。

## 設計差分の解決

M5Companion には旧 4x4 sheet packer と新 shared-canvas brief が併存する。旧 pack の
human-measured pupil は既存画面へ合わせた互換値であり、新しい layer delivery の正は
`docs/ASSET_BRIEF.md` の 1280x960 shared canvas とする。旧資産を fixture に使う場合は
左右 layer を新 anchor へ登録してから入力する。検出値を黙って golden 値へ昇格しない。

## 実装契約

```text
profile catalog    profiles/m5/*.json / GET /api/v1/domain-profiles
source canvas      1280x960 / PNG / RGBA / real transparent background
face safe rect     (40,40)-(1240,736)
eyes               (384,328)-(896,504), pupil (544,448)/(736,448)
mouth              (512,496)-(768,656), anchor (640,576)
pose                40px side/top/bottom margin
strict edit         G2 mask + protected-pixel validatorを再利用
pack                asset.pack + profile=m5.companion.pack + output.format=zip
pack inputs         base/front + fixed 12 eye slots + fixed 8 mouth slots
pack outputs        immutable PNGs + atlas/manifest + firmware M5A/manifest in reproducible ZIP
```

open-center は blue/cool pupil pixel を左右別に測り、各 anchor から 4px を超えたら fail
closed とする。他の eye state は pupil が存在しないため layer rectangle と transparency を
検証し、anchor を捏造しない。edit mask は layer rectangle と最大変更面積の両方で制限し、
生成後は従来どおり mask 外差分 0 を core validator が独立確認する。

## 公開契約の加法的変更

- `JobRequest.inputs` の上限を 16 から 32 へ緩和する。既存 request は不変。
- `output.format` に `zip` を追加する。`asset.pack` 以外では reject する。
- Asset MIME に `application/zip` を追加する。
- `m5-companion-manifest.json` と `/api/v1/domain-profiles` を追加する。

既存 operation 名、agent tool、required field、Host grant 境界は変更しない。
`media.pack` は ZIP も同じ staged upload / SHA-256 / atomic commit で配置する。

## 受け入れ

```text
local golden
  exact canvas/mode/alpha/safe rect
  open-center actual-pixel anchor
  layer-bounded mask / maximum change area
  fixed filename set / manifest schema / atlas geometry
  M5A magic/version/RGB565-BE/frame geometry/byte length
  same inputs -> byte-identical ZIP SHA-256

real installed
  M5Companion real template -> shared-canvas registration
  installed ControlDeck -> image.edit(strict) -> protected diff 0
  21 immutable assets -> asset.pack -> ZIP/atlas/manifest
  browser errors 0 / Broker cleanup 0 / no remaining worker
```

実機を行っていない時点では G5 COMPLETE と記録しない。
