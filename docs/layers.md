# 層とサブプロジェクトの対応

詳細はルート README と [subprojects.md](subprojects.md) を参照。

| 層 | サブプロジェクト |
| --- | --- |
| 1 機械同士 | Zipilogue (A) |
| 2 文単位多言語 | TesseraTalk (B) |
| 3 人間ギリギリ | ShorthandEdge (C) |
| 4 文内・文法最小 | MorphoZip (E) |
| 横断ルーティング | ConvoHub (D) |

JUnit は CI で `build/test-results/pytest-<ver>.xml` に置き、artifact 名は `junit-py*` です（Aoi / ascii_artist と同系）。

語彙ヘルパーは `shared/lex_policy.py`。担当は:

- **C**: FILLER 除去・UNIQUE_COMPACT（短縮クリップ）
- **E**: UNIQUE_READINGS（長い形）・ETYMON_ALIGN（information→ℹ️）・冠詞落とし・スペル数字・`I'll`・助数詞。フィラー/compact は既定オフ
- **D**: `C,E` パイプラインなら C が先にフィラーを落とす

F は当面なし。
