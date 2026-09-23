# MediaForge 0.33.18

MCPの生成要求が受理後に失敗・取消になっても、エラー応答へJob IDと確定した状態を残します。
後片付けの待機切れでも同じJobを追跡でき、成功した生成を誤って再送せず確認できます。
未受理の要求にJob IDは付けず、既存の成功応答は維持します。

Host/MCPでの追跡情報の保持はControlDeckの汎用修正と組み合わせます。
モデル・runtimeの追加取得はありません。[検証記録](implementation/agent-failure-reference-20260923.md)。
