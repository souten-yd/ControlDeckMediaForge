# 3D Studio設計の参照と現状照合

調査日: 2026-09-05。GitHubのmainを下記commitで照合した。
参照文書の古い「未実装」「次の作業」を現在の実装状態と混同しない。
実装開始時には最新main・導入済みHost・既存PRを再確認する。

| リポジトリ | 調査commit |
|---|---|
| ControlDeck | `739b981a321b73b209cfe4a1f0064f862072bb65` |
| ControlDeckMediaForge | `8b263b829aa16a1f73ce8219511453fb18357e11` |
| ControlDeckSonicForge | `f53b22fb932851f4a88e4a3c33e5a7445362909f` |

## 1. ControlDeck

- [AGENTS.md](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/AGENTS.md): 非root、systemd user、shell禁止、認証、監査、mobile。
- [Add-on Platform v2](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/docs/design-addon-platform-v2.md): opaque iframe、Jobs、grant、OpenCode tool投影。
- [Generic AI / Media Gateway](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/docs/design-generic-ai-media-gateway.md): 共通基盤、工程ごとのresource admission。
- [AI Resource Broker](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/docs/design-ai-resource-broker.md): 資源申告、競合、queue、lease、安全回収。
- [Add-on UX](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/docs/addon-ux-guidelines.md): 状態表示、理由・次操作、テーマ、通知。
- [release_bundle.py](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/backend/app/features/release_bundle.py): publisher_keys、Ed25519、canonical manifest、stage/provision/health/rollback。
- [trusted catalog](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/backend/app/features/trusted-catalog.json): media-forge/sonic-forgeの既存署名鍵とcapability allowlist。
- [proxy.py](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/backend/app/addons/proxy.py): Origin/nonce/service token、text/binary WS中継。noVNC実機対応は未確認。
- [runtime jobs.py](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/backend/app/addon_runtime/jobs.py): detached job、所有者付きjob credential、CPU-onlyでも利用できるrefresh。
- [OpenCode MCP bridge](https://github.com/souten-yd/ControlDeck/blob/739b981a321b73b209cfe4a1f0064f862072bb65/backend/app/integrations/opencode/addon_mcp_bridge.py): thin stdio転送。専用OpenCode pluginを追加しない根拠。

## 2. MediaForge

- [AGENTS.md](https://github.com/souten-yd/ControlDeckMediaForge/blob/8b263b829aa16a1f73ce8219511453fb18357e11/AGENTS.md): 設計優先順位、独立環境、契約凍結、実機証拠、PR/handoff。
- [G8実装記録](https://github.com/souten-yd/ControlDeckMediaForge/blob/8b263b829aa16a1f73ce8219511453fb18357e11/docs/implementation/g8-blender-production.md): 固定Blender、GLB validator、typed compiler、provenance。
- [Blender compiler](https://github.com/souten-yd/ControlDeckMediaForge/blob/8b263b829aa16a1f73ce8219511453fb18357e11/backend/mediaforge/blender_compile.py): 固定runtime path、compile option、timeout/cancel、検証。
- [runtime builder](https://github.com/souten-yd/ControlDeckMediaForge/blob/8b263b829aa16a1f73ce8219511453fb18357e11/scripts/blender_runtime.py): 既存導入・stamp・展開検証を拡張する基礎。
- [API](https://github.com/souten-yd/ControlDeckMediaForge/blob/8b263b829aa16a1f73ce8219511453fb18357e11/docs/api.md): private workspace、model operation、画像job、G8・media.packと制限。
- [signer](https://github.com/souten-yd/ControlDeckMediaForge/blob/8b263b829aa16a1f73ce8219511453fb18357e11/scripts/sign_release.py): 既存publisher署名方式。

## 3. SonicForge

- [AGENTS.md](https://github.com/souten-yd/ControlDeckSonicForge/blob/f53b22fb932851f4a88e4a3c33e5a7445362909f/AGENTS.md): 1 PR/1 slice、境界、日英UI、ローカル受入、現実の証拠。
- [環境管理](https://github.com/souten-yd/ControlDeckSonicForge/blob/f53b22fb932851f4a88e4a3c33e5a7445362909f/docs/02-runtime-environment-and-setup.md): core/重いruntime/永続data分離、staging、修復。
- [品質gate](https://github.com/souten-yd/ControlDeckSonicForge/blob/f53b22fb932851f4a88e4a3c33e5a7445362909f/docs/08-development-process-and-quality-gates.md): clean setup、resource lifecycle、cancel/reconnect、release negative。
- [リリース設計](https://github.com/souten-yd/ControlDeckSonicForge/blob/f53b22fb932851f4a88e4a3c33e5a7445362909f/docs/13-release-distribution-and-signing.md): canonical署名、identity、鍵管理。
- [日英UX](https://github.com/souten-yd/ControlDeckSonicForge/blob/f53b22fb932851f4a88e4a3c33e5a7445362909f/docs/14-bilingual-ux-and-critical-review.md): Simple/Advanced、日英、状態と操作。

SonicForge release文書の2026-08-25時点「Host署名未対応」は、今回調査の現行Hostには当てはまらない。
MediaForge handoff冒頭の古いbranch/version、workspace設計冒頭の歴史的未実装表記も、
最新mainや新3D機能の動作確認として流用しない。既存の記録は履歴として保持する。

## 4. 外部一次資料

- [Blender command line](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html): background、factory-startup、disable-autoexec等。採用版で再確認。
- [Blender background rendering](https://docs.blender.org/manual/en/latest/advanced/command_line/render.html): GUIなしのbatch実行とGUIセッションの区別。
- [noVNC公式](https://novnc.com/): VNC/WebSocket方式。配信候補の根拠。
- [noVNC公式repository](https://github.com/novnc/noVNC): 実装時のversion/依存/license確認元。

外部資料は仕組みの根拠であり、対象Ubuntu/GPU/Host proxyでの互換性や性能の実測ではない。
