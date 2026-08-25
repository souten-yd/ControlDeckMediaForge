# 実装引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 更新義務は
`ux1-workspace.md` §14.3。推測ではなく current Git/PR/process を再確認する。

## 現在地

```text
最終更新    2026-08-26
branch      g7/video-runtime-contract（origin/main 6f5818b から作成）
slice       G7 V0 additive video contract + deterministic FFmpeg boundary
状態        実装・focused/full gate・実 FFmpeg・実 standalone HTTP 完了
baseline    683 passed, 1 warning in 50.24s
installed   Media Forge v0.9.0 / 127.0.0.1:9130 / healthy
GPU         R9700 idle、KFD process 0（V0 は GPU を使わない）
PR          Media Forge #119 作成済み
```

`origin/main` の最新は Media Forge #118 merge。旧 handoff に残っていた #72/#73 と
ControlDeck #238 は merge 済みで、resource-turn 物理受け入れも status に記録済み。
古い G6 再実行を次作業として扱わない。

## この slice の結果

```text
完了  video.generate / video.edit を frozen contract へ加法追加
完了  MP4/WebM output、video MIME、任意 duration/fps metadata
完了  runtime 未実測の間は capability unavailable / job fail-closed
完了  worker_packs/video FFmpeg normalize + ffprobe validation
完了  MP4 H.264 無音と WebM VP9/Opus の実ファイル検証
完了  保存済み future job の degraded 読み出し回帰を維持
完了  installed v0.9.0 が healthy のままを確認
未実施 動画モデル/R9700/Broker/UI/installed playback（V1〜V4）
```

実測値と SHA は `docs/implementation-status.md` の
「G7 V0 — additive video contract と FFmpeg 正規化境界」に記録した。証跡ファイルは
`/data1tb/mediaforge-g7-v0-evidence/2026-08-26/`。

## 次にやること（1つだけ）

```text
1. Media Forge #119 の exact head / diff / mergeability を再確認して merge する
2. origin/main から G7 V1 branch を切る
3. 公式 primary source で Wan2.2 TI2V-5B の revision/license/runtime を再確認し、
   base-plan §24 の10項目を埋めた bounded R9700 probe を設計する
```

V1 で snapshot 取得済みという理由だけで available/default にしない。最小 smoke、
実用最短 clip、wall time、VRAM 4区分、RAM/swap、cancel latency、decode/frames/fps/尺を
実測する。gfx1201 で動かない、VRAM が収まらない、Host watchdog を巻き込む場合は延期し、
カーネル自作へ進まない。

## 境界と外部状態

```text
ControlDeck は原則 read-only。Host 側でしか解けない汎用機能だけ別 repo/別 PR。
ControlDeck #239 publisher-signature hardening は open（G7 runtime とは別件）。
ControlDeck #240 generic gateway control plane は open（G7 V0 の前提ではない）。
SonicForge acceptance service は 127.0.0.1:9140 で並行稼働中。
GPU 実測前に Broker/resource state と rocm-smi/KFD process を確認する。
Media Forge に独自グローバル GPU scheduler を作らない。
```

## 参照

```text
設計正          docs/base-plan.md / docs/controldeck-integration-plan.md
全体 roadmap    docs/implementation/goal-roadmap.md
G7 実装指示     docs/implementation/g7-video-runtime.md
実測            docs/implementation-status.md
公開契約        schemas/ / docs/api.md
```
