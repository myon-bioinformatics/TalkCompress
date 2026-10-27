# 層とサブプロジェクトの対応

詳細はルート README と [subprojects.md](subprojects.md) を参照。

| 層 | サブプロジェクト |
| --- | --- |
| 1 機械同士 | Zipilogue (A) |
| 2 文単位多言語 | TesseraTalk (B) — LID/RLE モザイク + **翻訳トークン最短**（並列多言語→短さ＋揺らぎ。Romance/Germanic/Greek + JA/ZH・自然短形。C 台帳は使わない） |
| 3 人間ギリギリ | ShorthandEdge (C) |
| 4 文内・文法最小 | MorphoZip (E) |
| 横断ルーティング | DispatchHub (D) |

> **TODO（D）:** DispatchHub は仮置き。後に別名・別責務へ変わりうる。現状はルーター専用（台帳は持たない）。

JUnit は CI で `build/test-results/pytest-<ver>.xml` に置き、artifact 名は `junit-py*` です（Aoi / ascii_artist と同系）。

語彙ヘルパーは `shared/lex_policy.py`。合意済み規約の台帳は **C** の `ShorthandEdge/ledger/conventions.json`（読込は `shared/ledger.py`）。担当は:

- **B**: LID/RLE モザイク。文ごとに翻訳候補（fixtures）でトークンが減るなら採用。EN+ZH+JA は開始セットであり天井ではない（Romance es/fr/pt/it、Germanic de/nl/en、Greek el、ja/zh がスコープ）。自然短形 OK。ライブ MT（`--translate-engine=deep|argos`）は対象言語へ並列翻訳し、短さ＋揺らぎで選ぶ。C 合意台帳パッチは適用しない
- **C**: FILLER 除去・UNIQUE_COMPACT（短縮クリップ）・同一言語の省略（`I'll` など）・スペル数字→桁・**合意台帳 lex**（under/below→下、家具 `table`→机/桌 ほか多言語の机相当、デコボコ→凹凸 など）。ベース語彙は EN+ZH+JA 寄りだが他言語 cognate も可。接続詞短縮は **曖昧さゲート**（`also` 衝突時や `--prefer-precision` で原文維持）
- **E**: UNIQUE_READINGS（長い形）・ETYMON_ALIGN（information→ℹ️）・冠詞落とし・助数詞・**コンパクト代名詞在庫**（コア N=4→2bit: I/君/彼/they\|them\|y'all；她は彼スロットの表層；it は拡張で3bit）。フィラー/compact/`I'll`/スペル数字/台帳 lex は既定オフ
- **D**: 層横断ルーター（pipeline / auto / budget / window / profile / quality / compare）のみ。`C,E` パイプラインなら C が先にフィラー・I'll・スペル数字・台帳 lex を処理し、E が ℹ️・冠詞・助数詞を適用する

**テスト分担:** D 専用 pytest は実質ゼロ。層単体 → `tests/test_*.py`；層またぎ（pipeline C→E・compare・budget/window/profile 等）→ `tests/integration/`（結合・総合）。`DispatchHub/tests/` にテストモジュールは置かない。同一ケースの二重断言は避け、層単体は 1 箇所・またぎは integration に寄せる。

A の RuleBook（`Zipilogue/rulebook.py`）は機械同士で育つスラング台帳で、C の静的合意台帳とは別物。

F は当面なし。
