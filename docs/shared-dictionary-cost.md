# Shared dictionary session cost

タイルの再利用と同じく、辞書は繰り返し使って初めて初期費用を回収する。
既存 RuleBook を変更せず、辞書配布・本文・再送の全体費用を比較する。

```sh
python -m Zipilogue.session_cost
python -m unittest discover -s tests -p test_session_cost.py
```

`measure_session(book, messages)` はコンパクトな export JSON を一度配布し、
各メッセージを既存の規則で符号化して、受信側の辞書で復号する。
`recovery_messages` に実際の再送内容を渡すと、その費用も加算する。
再接続による辞書再配布も、該当ターンの再送内容に含めること。
辞書は固定し、自動学習・規則の更新・既存圧縮出力には介入しない。

既定値は **UTF-8バイト数**。トークン数ではない。
対象 tokenizer の `count(text) -> int` と `unit="tokens"` を指定すると
同じ集計をトークン単位で利用できる。tokenizer・モデルを自動取得しない。
カウンターは各メッセージを独立に計測する。履歴全体を毎回送り直す方式、
プロンプト包装、通信ヘッダー、推論時間は別途計上が必要。

- `first_saving_turn`: 累積費用が初めて元本文を下回ったターン。
  後続の再送などで再び赤字になる場合があり、永続的な損益分岐点ではない。
- `beneficial`: 最終費用が減り、全ターンが文字列として完全往復した場合のみ真。
- `exact_roundtrip`: 短縮語の衝突や大文字小文字の消失も失敗として記録する。
  意味的な品質やLLMによる理解を評価したものではない。

合成例は1往復・32往復・毎回全文再送を比較する。
実運用の採用判断には未使用の会話、実 tokenizer、モデルによるタスク成功率を
追加し、辞書不一致・途中参加・復旧も含めて比較する。
