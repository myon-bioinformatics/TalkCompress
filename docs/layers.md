# 層とサブプロジェクトの対応

詳細はルート README と [subprojects.md](subprojects.md) を参照。

| 層 | サブプロジェクト |
| --- | --- |
| 1 機械同士 | Zipilogue (A) |
| 2 文単位多言語 | TesseraTalk (B) — LID/RLE モザイク + **翻訳トークン最短**（並列多言語→短さ＋揺らぎ。Romance/Germanic/Greek + JA/ZH・自然短形。C 台帳は使わない） |
| 3 人間ギリギリ | ShorthandEdge (C) |
| 4 文内・文法最小 | MorphoZip (E) |
| 横断 + density | DensityZip (D) |

### Zip 名の区別

単独の「Zip」は使わない。常にフルネーム:

| ID | フルネーム | 役割 |
| --- | --- | --- |
| A | **Zipilogue** | 層1 — 共有ルール / 任意封筒（density ではない） |
| D | **DensityZip** | 横断 — density 指標ファサード + 層オーケストレーション |
| E | **MorphoZip** | 層4 — 形態・閉じた品詞在庫ビット・文法最小 |

JUnit は CI で `build/test-results/pytest-<ver>.xml` に置き、artifact 名は `junit-py*` です（Aoi / ascii_artist と同系）。

語彙ヘルパーは `shared/lex_policy.py`。合意済み規約の台帳は **C** の `ShorthandEdge/ledger/conventions.json`（読込は `shared/ledger.py`）。担当は:

- **B**: LID/RLE モザイク。文ごとに翻訳候補（fixtures）でトークンが減るなら採用。EN+ZH+JA は開始セットであり天井ではない（Romance es/fr/pt/it、Germanic de/nl/en、Greek el、ja/zh がスコープ）。自然短形 OK。ライブ MT（`--translate-engine=deep|argos`）は対象言語へ並列翻訳し、短さ＋揺らぎで選ぶ。C 合意台帳パッチは適用しない。**`estimate_tokens` / translate-min の本体**
- **C**: FILLER 除去・UNIQUE_COMPACT（短縮クリップ）・同一言語の省略（`I'll` など）・スペル数字→桁・**合意台帳 lex**（under/below→下、家具 `table`→机/桌 ほか多言語の机相当、デコボコ→凹凸 など）。ベース語彙は EN+ZH+JA 寄りだが他言語 cognate も可。接続詞短縮は **曖昧さゲート**（`also` 衝突時や `--prefer-precision` で原文維持）
- **E**: UNIQUE_READINGS（長い形）・ETYMON_ALIGN（information→ℹ️）・助数詞・**閉じた品詞在庫（ビット主）**: 代名詞 I/君/彼/they（2bit；她=彼表層；it 拡張3bit）／冠詞 ∅（the/a/an 落とし・0bit）／接続 &|/|bc|∴（2bit；moreover 等は C）／副詞 tho|~|˅|esp.（2bit）／助動詞 can|will|must|may（2bit；I'll は C）／前置 w/|4|fr|@（2bit；under/above は C；in/on 見送り；for→4 は数字と揺らぎうるため別評価・将来 4R 等の可能性）。API: `closed_inventory_bits` / `closed_bit_cost` および各 `*_bit_cost`；`density().closed`。フィラー/compact/`I'll`/スペル数字/台帳 lex は既定オフ
- **D DensityZip**: 層横断オーケストレーション（pipeline / auto / budget / window / profile / quality / compare）+ **density 指標ファサード**（token 寄りは budget / compare / B `estimate_tokens` の表出、bit 寄りは E `density()` / `closed_bit_cost`（代名詞含む）の集約）。`C,E` パイプラインなら C が先にフィラー・I'll・スペル数字・台帳 lex を処理し、E が ℹ️・冠詞・助数詞を適用する。台帳は持たない

**テスト分担:** D 専用 pytest は実質ゼロ。層単体 → `tests/test_*.py`；層またぎ（pipeline C→E・compare・budget/window/profile 等）→ `tests/integration/`（結合・総合）。`DensityZip/tests/` にテストモジュールは置かない。同一ケースの二重断言は避け、層単体は 1 箇所・またぎは integration に寄せる。

A の RuleBook（`Zipilogue/rulebook.py`）は機械同士で育つスラング台帳で、C の静的合意台帳とは別物。

**A Zipilogue 実験方針（2026-10-27）:** **llama.cpp または同等の軽量 GGUF** スタック（同クラス；既定では重いフル精度サーバは使わない）で継続会話を回し、間隔観察で共有スラング（RuleBook）が育つかを見る。二者固定より**複数エージェント並列グループ**を優先。ランナー実装は未着手（方針のみ）。

F は当面なし。
