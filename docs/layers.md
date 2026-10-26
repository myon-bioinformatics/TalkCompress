# 層とサブプロジェクトの対応

詳細はルート README と [subprojects.md](subprojects.md) を参照。

| 層 | サブプロジェクト |
| --- | --- |
| 1 機械同士 | Zipilogue (A) |
| 2 文単位多言語 | TesseraTalk (B) |
| 3 人間ギリギリ | ShorthandEdge (C) |
| 4 文内・文法最小 | MorphoZip (E) |
| 横断ルーティング＋合意台帳 | ConvoHub (D) |

JUnit は CI で `build/test-results/pytest-<ver>.xml` に置き、artifact 名は `junit-py*` です（Aoi / ascii_artist と同系）。

語彙ヘルパーは `shared/lex_policy.py`。合意済み規約の台帳は **D** の `ConvoHub/ledger/conventions.json`（読込は `shared/ledger.py`）。担当は:

- **C**: FILLER 除去・UNIQUE_COMPACT（短縮クリップ）・同一言語の省略（`I'll` など）・スペル数字→桁
- **E**: UNIQUE_READINGS（長い形）・ETYMON_ALIGN（information→ℹ️）・冠詞落とし・助数詞・一人称→I・**D 台帳の lex**（under/below→下、デコボコ→凹凸 など）。フィラー/compact/`I'll`/スペル数字は既定オフ
- **D**: 層横断ルーター（pipeline / auto / budget / window / profile / quality / compare）＋ **合意済み規約の台帳（ledger）**。`C,E` パイプラインなら C が先にフィラー・I'll・スペル数字を処理し、E が ℹ️・冠詞・助数詞・台帳 lex を適用する

A の RuleBook（`Zipilogue/rulebook.py`）は機械同士で育つスラング台帳で、D の静的合意台帳とは別物。

F は当面なし。
