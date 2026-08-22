# UX1 引き継ぎ状態

**次のセッションはこのファイルを最初に読む。** 他の文書より優先する。
更新義務は `ux1-workspace.md` §14.3。commit のたびに書き換える。

---

## 現在地

```text
最終更新    2026-08-22
main        d330c5207edc54427c8ce6eab9b7660292886cef
ブランチ    ux1/creative-intelligence-a0
PR          UX1 #21〜#33 / UX2 M0 #35〜C4 #42 マージ済み
状態        Creative Intelligence A0 の設計 + provider-neutral Host AI seam を実装済み、NOT TESTED
Host依存    ControlDeck PR #224 `feat(addons): provider-neutral AI gateway for add-ons` は open / NOT TESTED
リリース    installed host は v0.2.4（この新規スライスは未収録）
```

## PR 進捗

| PR | 内容 | 状態 |
|---|---|---|
| — | 設計 + 実装計画 + 運用ルール | #21 マージ済み |
| — | G3 profiles backend | #22 マージ済み |
| PR-U0 | /ws 追加メソッドと保存基盤 | #23 マージ済み（転送量 -85.9%） |
| PR-U1 | シェル刷新（3ナビ・モード・モバイル IA） | #24 マージ済み |
| PR-U2 | 作成体験 | #25 マージ済み |
| PR-U3 | マスクエディタ・外側拡張 | #26 マージ済み |
| PR-U4 | 状況と結果ステージ | #32 マージ済み |
| — | 実使用で見つかった不具合 | #28 #29 マージ済み |
| PR-U5 | ライブラリ viewer | #33 マージ済み |
| UX2 M0-M2 | モデルregistry/install/UI | #35〜#37 マージ済み |
| UX2 C0 | CreativeSpec / compiler | #38 マージ済み |
| UX2 C1 | Create creative controls | #39 マージ済み |
| UX2 C2 | role-aware Character/Style references | #40 マージ済み |
| UX2 C3 | intentional variation batches | #41 マージ済み |
| UX2 C4 | deterministic multi-cut Composer | #42 マージ済み |
| UX2 C5 | semantic evaluator + R9700 acceptance | 未完了。Creative Intelligence A6/A7で一般化して完了条件へ接続する |
| CI A0 | Host AI seam + typed planning models + design | 実装済み / NOT TESTED |

## 今回追加した設計

```text
docs/design-creative-intelligence.md
docs/implementation/creative-intelligence.md
```

重要な決定:

```text
1. Text prompt refinement と image understanding を分離する。
     text.generate     -> Prompt Planner / Refiner
     vision.analyze    -> Reference Analyzer / Evaluator (VLM)
2. Media Forge は Ollama / llama.cpp / provider / port / model を決め打ちしない。
3. ControlDeck の scoped Add-on Runtime AI capability を通す。
4. 画像の色・サイズ・alpha等、機械的に測れる事実は VLM ではなく deterministic code で取る。
5. original_intent は不変。AIが足した内容は suggestion と user fact を分ける。
6. Simple の人物中心 Pose UI を今すぐ消さない。内部Pose/Action構造は C3 variation / 評価 / provenanceに必要。
   A5で既存UIを流用し、自然文 + 参考画像で共通操作が足りることを実測してから Simple Pose を縮退/条件表示する。
7. semantic retry は既存 QA budget を超えない。無制限 generate -> judge loop は禁止。
```

## A0 のコード

```text
backend/mediaforge/host/ai.py
  HostAIGateway
  text.generate / vision.analyze の capability だけを指定
  provider/model/port を受け取らない
  Hostが将来provider/model情報を返しても無視する

backend/mediaforge/creative_intelligence.py
  PromptPlan
  SubjectSpec
  ActionStateSpec
  VisualFacts
  VisualAnalysis
  EvaluationResult
  PromptPlanner
  prompt_plan_to_creative_details()

  A0では既存JobRequest/Create動作へまだ接続しない。
```

テストコード `tests/test_creative_intelligence.py` も追加したが、このChatGPT実行環境からリポジトリを実行できないため **結果は NOT TESTED**。成功したと記録しないこと。

## ControlDeck 側の依存

ControlDeck main `23aae9ce50b3b6c26e5566f055856370caa2f213` を調査し、以下を確認した。

```text
既存:
  RuntimeChatRequest / runtime_provider
  provider別 multimodal message conversion
  structured response fallback
  llama.cpp mmproj_path
  Ollama vlm_enabled
  Add-on Runtime service-token capability auth

不足:
  Add-on Runtime から scoped に text/VLM inference を呼ぶgeneric API
```

そのため別リポジトリの **ControlDeck PR #224** を作成した。

```text
branch  feat/addon-ai-gateway
PR      #224
scope   generic host only
cap     ai.inference
API     GET  /api/v1/addon-runtime/{addon_id}/ai/capabilities
        POST /api/v1/addon-runtime/{addon_id}/ai/complete
logical capability
        text.generate
        vision.analyze
```

ControlDeck #224 もこの環境では未実行なので **merge禁止**。ローカル backend test + 実 text/VLM 呼び出しを通すこと。

既存の ControlDeck `/api/v1/llm/v1` gateway API key を Media Forge へコピーする案は却下。Add-on service token + `ai.inference` が正しい境界。

## 次にやること（1つだけ）

```text
A0 をローカルgateする。

1. ControlDeck PR #224:
   - backend/tests/test_addon_runtime_ai.py
   - 通常backend test
   - fake/test add-on service tokenで text.generate 1回
   - VLM設定済み環境で vision.analyze 1回
   - provider/model identityをAdd-on responseへ出さない確認

2. Media Forge A0:
   - ./mf.sh test
   - tests/test_creative_intelligence.py
   - 既存 prompt-only generation の回帰がないこと
   - grepで新規production pathに Ollama/llama.cpp/11434//api/chat がないこと

3. 実測結果だけ docs/implementation-status.md に追記。
4. A0 PRを作成/mergeするのは上記gate後。
5. その後 A1: 既存 direct Ollama semantic reviewer を ControlDeck `vision.analyze` へ置換する。
```

## その後の実装順

```text
A1  direct Ollama semantic reviewer -> ControlDeck vision.analyze
A2  deterministic VisualFacts + cache
A3  VLM VisualAnalysis + reference roles / CreativeSpec suggestion
A4  text Prompt Planner / Refiner backend
A5  既存Createへ「指示を整える」+ reference analysis UI（新wizardを作らない）
A6  multidimensional Evaluator + ranking + bounded retry
A7  installed-host / R9700 / ControlDeck runtime swap acceptance
```

## 未解決の判断

```text
1. worker が core を import している層違反
   worker_packs/image/adapters/diffusers_flux2.py が mediaforge.image_edit / outpaint を import。
   新adapterを増やす前に整理する。strict edit validatorはcore側に独立して残す。

2. 動画モデル管理
   installer/catalogは capability-driven + media_types image/video/audio_video を維持。
   Wan/LTXは G7候補のまま。Creative IntelligenceのCamera/Actionは将来MotionSpecへ加法拡張する。

3. Simple Pose control
   直ちに削除しない。A5/A7実測後に、自然文/VLM解析で通常操作が足りる場合のみ
   Simpleから縮退またはsubject-aware表示へ変更。Advanced/内部Pose/Actionは残す。
```

## 再開コマンド

```bash
cd /data1tb/ControlDeckMediaForge
cat docs/implementation/ux1-handoff.md
git fetch --all --prune && git log --oneline -8
gh pr list --state open
cat docs/design-creative-intelligence.md
cat docs/implementation/creative-intelligence.md
./mf.sh test
```

## 参照

```text
設計の正        docs/base-plan.md
Host境界の正    docs/controldeck-integration-plan.md
UIの正          docs/design-workspace-ux.md
UX2設計         docs/design-model-scene-ux.md
CI設計          docs/design-creative-intelligence.md
CI実装指示      docs/implementation/creative-intelligence.md
進捗と実測      docs/implementation-status.md（実測値のみ。推測を書かない）
ControlDeck     PR #224 / docs/design-addon-ai-gateway.md
```
