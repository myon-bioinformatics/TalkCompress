# TokenCostHeuristic

共有のトークンコスト推定器。旧 TesseraTalk（現 SentenceCalibratedMosaic）本体にあった `estimate_tokens` と校正データを切り出したもの。

- モジュール: `TokenCostHeuristic/token_cost_heuristic.py`（stdlib のみ）
- データ: `fixtures/o200k_calib.json`（`scripts/calibrate_estimate.py --write` で再生成）、`fixtures/en_wordlist.txt`（`scripts/build_en_wordlist.py`）
- 利用側: `shared/ledger.py`・`shared/struct_bullet.py`・`shared/claude_token_stub.py`・`scripts/tokenizer_compat.py` などはここから import する。SentenceCalibratedMosaic も翻訳候補の比較にここを使い、互換のため `estimate_tokens` を再エクスポートする。

`estimate_tokens` は実 tokenizer の計測値ではなく、コミット済み校正表と文字範囲に基づく推定。
